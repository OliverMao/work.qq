"""
会话存档路由
"""

import logging

from fastapi import APIRouter

from app.services.chat_archive import chat_archive_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/archive")
async def chat_archive():
    """拉取会话内容存档并保存到本地 JSON 文件。"""
    try:
        logger.info("收到会话存档请求")
        result = chat_archive_service.archive_messages()
        logger.info(
            "会话存档完成: saved_count=%s, save_path=%s",
            result.get("saved_count", 0),
            result.get("save_path"),
        )
        result.setdefault("errcode", 0)
        result.setdefault("errmsg", "ok")
        return result
    except Exception as e:
        logger.exception("会话存档失败")
        return {
            "errcode": -1,
            "errmsg": str(e),
            "saved_count": 0,
        }


@router.get("/archive/group/{roomid}")
async def get_group_archive_messages(roomid: str):
    """查看指定群聊(roomid)的全部本地聊天记录。"""
    try:
        result = chat_archive_service.get_group_archived_messages(roomid=roomid)
        result.setdefault("errcode", 0)
        result.setdefault("errmsg", "ok")
        return result
    except Exception as e:
        logger.exception("查询群聊存档失败: roomid=%s", roomid)
        return {
            "errcode": -1,
            "errmsg": str(e),
            "roomid": roomid,
            "count": 0,
            "files": [],
            "messages": [],
        }
