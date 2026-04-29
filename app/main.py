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


def _chat_archive_callback() -> dict:
    """/chat/archive 同步会话回调"""
    return chat_archive_service.archive_messages(limit=1000, auto_build_index=False)


def _build_index_callback(rebuild: bool = False) -> dict:
    """/api/agent/build-index 增量构建向量回调"""
    from app.services.agent.agent import build_teacher_assistant_index

    return build_teacher_assistant_index(rebuild=rebuild)


def _load_auto_reply_config() -> dict:
    """加载自动发信配置"""
    from app.config import settings
    from pathlib import Path

    prompt_dir = Path(settings.teacher_agent_prompt_dir)
    config_file = prompt_dir / "auto_reply_config.txt"

    config = {
        "model": "deepseek/deepseek-v4-flash",
        "target_chatid": "fangya001",
    }

    if config_file.exists():
        try:
            content = config_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()
        except Exception as e:
            logger.warning("读取自动发信配置失败: %s", e)

    return config


def _send_notification_callback(message: str) -> None:
    """发送通知回调 - 生成回复并发送到群"""
    import json
    from pathlib import Path

    from app.services.agent.agent import TeacherAssistantRAGAgent
    from app.services.chat_group_in import ChatGroupService
    from app.config import settings

    auto_reply_config = _load_auto_reply_config()
    target_chatid = auto_reply_config.get("target_chatid", "fangya001")
    target_model = auto_reply_config.get("model", "deepseek/deepseek-v4-flash")

    try:
        archive_save_dir = Path(settings.chat_archive_save_dir)
        json_files = sorted(archive_save_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not json_files:
            logger.warning("没有找到聊天存档文件")
            return

        latest_file = json_files[0]
        with open(latest_file, encoding="utf-8") as f:
            messages = json.load(f)

        if not messages:
            logger.warning("消息列表为空")
            return

        latest_msg = messages[-1]
        logger.info(latest_msg)
        roomid = latest_msg.get("roomid", "")

        msg_obj = latest_msg.get("text", {})
        stu_message = msg_obj.get("content", "") if isinstance(msg_obj, dict) else ""

        if not stu_message:
            stu_message = latest_msg.get("content", "")

        if not stu_message:
            stu_message = latest_msg.get("msg", "")

        if not stu_message:
            logger.warning("无法获取学生消息内容")
            return

        logger.info("生成回复: roomid=%s, msg=%s, model=%s", roomid, stu_message[:50], target_model)

        agent = TeacherAssistantRAGAgent()
        result = agent.generate_teacher_reply(
            stu_message=stu_message,
            chat_id=roomid,
            model=target_model,
            auto_build_index=False,
        )
        reply_content = result.get("reply", "")

        if not reply_content:
            logger.warning("Agent 未生成回复内容")
            return

        logger.info("回复内容: %s", reply_content[:100])

        chat_group_service = ChatGroupService()
        chat_group_service.send_markdown_message(chatid=target_chatid, content=reply_content)
        logger.info("消息已发送到群: %s", target_chatid)

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


