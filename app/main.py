"""
FastAPI 主应用 - 企业微信消息接收
"""

import logging
import subprocess
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.database import init_db
from app.router import router as api_router
from app.services.redis_queue import redis_queue_service
from app.services.chat_archive import chat_archive_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _ensure_redis_running() -> bool:
    """检查并启动 Redis（如未运行）"""
    try:
        import redis
        from app.config import settings
        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        logger.info("Redis 已连接")
        return True
    except Exception:
        pass

    logger.info("Redis 未运行，尝试启动...")
    compose_file = Path(__file__).resolve().parent.parent / "redis-compose.yml"
    if not compose_file.exists():
        logger.error("找不到 redis-compose.yml")
        return False

    try:
        result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "up", "-d"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info("Redis 容器启动成功")
            return True
        else:
            logger.error("Redis 启动失败: %s", result.stderr)
            return False
    except FileNotFoundError:
        logger.error("未找到 docker-compose 命令")
        return False
    except Exception as e:
        logger.error("启动 Redis 失败: %s", e)
        return False


def _chat_archive_callback(msgid: str) -> dict:
    """/chat/archive 同步会话回调"""
    return chat_archive_service.archive_messages(limit=1000, auto_build_index=False)


def _build_index_callback(rebuild: bool = False) -> dict:
    """/api/agent/build-index 增量构建向量回调"""
    from app.services.agent.agent import build_teacher_assistant_index

    return build_teacher_assistant_index(rebuild=rebuild)


def _send_notification_callback(msgid: str, archive_result: dict) -> None:
    """发送通知回调 - 通过msgid查找消息，生成回复并发送到群"""
    if not msgid:
        logger.warning("msgid 为空，无法处理")
        return

    messages = archive_result.get("messages", [])
    if not messages:
        logger.warning("archive_result 中没有新消息")
        return

    target_msg = None
    for msg in messages:
        msg_id = msg.get("msgid", "")
        if str(msg_id) == str(msgid):
            target_msg = msg
            break

    if not target_msg:
        logger.warning("未找到 msgid=%s 对应的消息", msgid)
        return

    roomid = target_msg.get("roomid", "")
    stu_message = target_msg.get("content", "")

    if not stu_message:
        stu_message = target_msg.get("msg", "")

    if not stu_message:
        logger.warning("无法获取学生消息内容")
        return

    logger.info("生成回复: msgid=%s, roomid=%s, msg=%s", msgid, roomid, stu_message[:50])

    model = "deepseek/deepseek-v4-flash"
    aliases = settings.teacher_agent_model_aliases
    actual_model = aliases.get(model, model)

    try:
        from app.services.agent.agent import TeacherAssistantRAGAgent

        agent = TeacherAssistantRAGAgent()
        result = agent.generate_teacher_reply(
            stu_message=stu_message,
            chat_id=roomid,
            model=actual_model,
            auto_build_index=False,
        )
        reply_content = result.get("reply", "")

        if not reply_content:
            logger.warning("Agent 未生成回复内容")
            return

        logger.info("回复内容: %s", reply_content[:100])

        from app.services.chat_group_in import ChatGroupService

        chat_group_service = ChatGroupService()
        chat_group_service.send_markdown_message(chatid="fangya001", content=reply_content)
        logger.info("消息已发送到群: fangya001")

    except Exception as e:
        logger.error("发送通知失败: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    init_db()

    # 确保 Redis 运行
    if not _ensure_redis_running():
        logger.warning("Redis 启动失败或不可用")

    # 启动 Redis 消费者线程
    redis_queue_service.start_consumer(
        chat_archive_callback=_chat_archive_callback,
        build_index_callback=_build_index_callback,
        send_notification_callback=_send_notification_callback,
    )

    yield

    # 关闭时执行
    redis_queue_service.stop_consumer()

app = FastAPI(title="WeCom Message Receiver", lifespan=lifespan)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


app.include_router(api_router)


