"""
Redis 队列服务 - 处理企业微信消息存档通知
"""

import json
import logging
import threading
import time
from typing import Any, Dict, Optional, Callable

import redis

from app.config import settings

logger = logging.getLogger(__name__)


class RedisQueueService:
    """Redis 队列服务 - 生产者/消费者模式"""

    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None
        self._consumer_thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def redis_client(self) -> redis.Redis:
        if self._redis_client is None:
            self._redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
        return self._redis_client

    def push_message(self, message: Dict[str, Any]) -> bool:
        """生产者：推送消息到队列"""
        try:
            queue_name = settings.redis_queue_name
            payload = json.dumps(message, ensure_ascii=False)
            self.redis_client.rpush(queue_name, payload)
            logger.info("推送到Redis队列成功: queue=%s, msg=%s", queue_name, payload[:200])
            return True
        except Exception as e:
            logger.error("推送到Redis队列失败: %s", e)
            return False

    def pop_message(self, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """消费者：从队列获取消息"""
        try:
            queue_name = settings.redis_queue_name
            result = self.redis_client.blpop(queue_name, timeout=timeout)
            if result is None:
                return None
            _, payload = result
            return json.loads(payload)
        except Exception as e:
            logger.error("从Redis队列获取消息失败: %s", e)
            return None

    def process_message(
        self,
        message: Dict[str, Any],
        chat_archive_callback: Optional[Callable[[], Dict[str, Any]]] = None,
        build_index_callback: Optional[Callable[[bool], Dict[str, Any]]] = None,
        send_notification_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """处理单条消息"""
        try:
            logger.info("开始处理消息: %s", message)

            if chat_archive_callback:
                logger.info("调用 /chat/archive 同步会话...")
                archive_result = chat_archive_callback()
                logger.info(
                    "/chat/archive 返回: saved_count=%s",
                    archive_result.get("saved_count", 0),
                )
            else:
                logger.info("模拟调用 /chat/archive 同步会话: 归档完成")

            if build_index_callback:
                logger.info("调用 /api/agent/build-index 增量构建向量...")
                index_result = build_index_callback(rebuild=False)
                logger.info(
                    "/api/agent/build-index 返回: added_chunk_count=%s",
                    index_result.get("added_chunk_count", 0),
                )
            else:
                logger.info("模拟调用 /api/agent/build-index: 增量构建完成")

            if send_notification_callback:
                send_notification_callback("会话存档和索引构建完成")
            else:
                logger.info("模拟发送通知: 会话存档和索引构建完成")

            return True
        except Exception as e:
            logger.error("处理消息失败: %s", e)
            return False

    def _consumer_loop(
        self,
        chat_archive_callback: Optional[Callable[[], Dict[str, Any]]] = None,
        build_index_callback: Optional[Callable[[bool], Dict[str, Any]]] = None,
        send_notification_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """消费者主循环"""
        logger.info("Redis 消费者启动: queue=%s", settings.redis_queue_name)
        while self._running:
            message = self.pop_message(timeout=1)
            if message:
                self.process_message(
                    message,
                    chat_archive_callback,
                    build_index_callback,
                    send_notification_callback,
                )
        logger.info("Redis 消费者已停止")

    def start_consumer(
        self,
        chat_archive_callback: Optional[Callable[[], Dict[str, Any]]] = None,
        build_index_callback: Optional[Callable[[bool], Dict[str, Any]]] = None,
        send_notification_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """启动消费者线程"""
        if self._running:
            logger.warning("消费者已在运行中")
            return

        self._running = True
        self._consumer_thread = threading.Thread(
            target=self._consumer_loop,
            args=(
                chat_archive_callback,
                build_index_callback,
                send_notification_callback,
            ),
            daemon=True,
        )
        self._consumer_thread.start()
        logger.info("消费者线程已启动")

    def stop_consumer(self) -> None:
        """停止消费者线程"""
        if not self._running:
            return
        self._running = False
        if self._consumer_thread:
            self._consumer_thread.join(timeout=5)
        logger.info("消费者线程已停止")


redis_queue_service = RedisQueueService()