"""
会话存档路由
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.chat_archive import chat_archive_service
from app.services.chat_archive_binding import chat_archive_binding_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class CreateRoomBindingRequest(BaseModel):
    roomid: str = Field(..., min_length=1, max_length=128)
    room_name: str = Field(..., min_length=1, max_length=128)


class UpdateRoomBindingRequest(BaseModel):
    room_name: str = Field(..., min_length=1, max_length=128)


def _ok(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(payload)
    result.setdefault("errcode", 0)
    result.setdefault("errmsg", "ok")
    return result


def _err(errcode: int, errmsg: str, **extra: Any) -> Dict[str, Any]:
    return {
        "errcode": errcode,
        "errmsg": errmsg,
        **extra,
    }


def _value_error_code(message: str, default_code: int = 400) -> int:
    if "未绑定" in message:
        return 404
    if "已存在" in message:
        return 409
    return default_code


@router.get("/archive/room-binding/admin")
async def room_binding_admin_page():
    """会话存档群聊绑定管理页面。"""
    page_path = Path(__file__).resolve().parents[1] / "static" / "chat_archive_binding_admin.html"
    return FileResponse(path=str(page_path), media_type="text/html")


@router.post("/archive")
async def chat_archive():
    """拉取会话内容存档并保存到本地 JSON 文件。"""
    try:
        logger.info("收到会话存档请求")
        result = chat_archive_service.archive_messages()
        logger.info(
            "会话存档完成: saved_count=%s, skip_duplicate_count=%s, save_path=%s",
            result.get("saved_count", 0),
            result.get("skip_duplicate_count", 0),
            result.get("save_path"),
        )

        files = result.get("files") or []
        roomids = [
            item.get("roomid")
            for item in files
            if isinstance(item, dict) and item.get("roomid")
        ]
        if roomids:
            room_name_map = chat_archive_binding_service.get_room_name_map(roomids=roomids)
            for item in files:
                if not isinstance(item, dict):
                    continue
                roomid = item.get("roomid")
                if roomid:
                    item["room_name"] = room_name_map.get(roomid)

        return _ok(result)
    except Exception as e:
        logger.exception("会话存档失败")
        return _err(-1, str(e), saved_count=0)


@router.get("/archive/group-modules")
async def list_group_archive_modules(keyword: Optional[str] = Query(default=None)):
    """按本地 JSON 文件列出群聊模块，并返回绑定关系。"""
    try:
        result = chat_archive_service.list_group_archive_modules(keyword=keyword)
        items = result.get("items") or []

        roomids = [
            item.get("roomid")
            for item in items
            if isinstance(item, dict) and item.get("roomid")
        ]
        room_name_map = (
            chat_archive_binding_service.get_room_name_map(roomids=roomids)
            if roomids
            else {}
        )

        for item in items:
            if not isinstance(item, dict):
                continue
            roomid = item.get("roomid")
            room_name = room_name_map.get(roomid) if roomid else None
            item["room_name"] = room_name
            item["is_bound"] = bool(room_name)

        return _ok(result)
    except Exception as e:
        logger.exception("查询群聊存档模块失败")
        return _err(-1, str(e), count=0, items=[])


@router.get("/archive/group-module/{filename}")
async def get_group_archive_module(filename: str):
    """按 JSON 文件名读取群聊存档模块详情。"""
    try:
        result = chat_archive_service.get_group_archive_module(filename=filename)
        roomid = str(result.get("roomid") or "").strip()
        room_name = chat_archive_binding_service.get_room_name(roomid=roomid)
        if room_name:
            result["room_name"] = room_name
        result["is_bound"] = bool(room_name)
        return _ok(result)
    except Exception as e:
        logger.exception("查询群聊存档模块详情失败: filename=%s", filename)
        return _err(-1, str(e), filename=filename, count=0, messages=[])


@router.get("/archive/group/{roomid}")
async def get_group_archive_messages(roomid: str):
    """查看指定群聊(roomid)的全部本地聊天记录。"""
    try:
        result = chat_archive_service.get_group_archived_messages(roomid=roomid)
        room_name = chat_archive_binding_service.get_room_name(roomid=roomid)
        if room_name:
            result["room_name"] = room_name
        return _ok(result)
    except Exception as e:
        logger.exception("查询群聊存档失败: roomid=%s", roomid)
        return _err(-1, str(e), roomid=roomid, count=0, files=[], messages=[])


@router.post("/archive/room-binding")
async def create_room_binding(payload: CreateRoomBindingRequest):
    """创建 roomid 与群聊名绑定。"""
    try:
        result = chat_archive_binding_service.create_binding(
            roomid=payload.roomid,
            room_name=payload.room_name,
        )
        return _ok(result)
    except ValueError as e:
        return _err(_value_error_code(str(e)), str(e))
    except Exception as e:
        logger.exception("创建 roomid 绑定失败")
        return _err(-1, str(e))


@router.get("/archive/room-binding/{roomid}")
async def get_room_binding(roomid: str):
    """获取单个 roomid 的绑定信息。"""
    try:
        result = chat_archive_binding_service.get_binding(roomid=roomid)
        return _ok(result)
    except ValueError as e:
        return _err(_value_error_code(str(e), default_code=404), str(e), roomid=roomid)
    except Exception as e:
        logger.exception("查询 roomid 绑定失败: roomid=%s", roomid)
        return _err(-1, str(e), roomid=roomid)


@router.get("/archive/room-bindings")
async def list_room_bindings(keyword: Optional[str] = Query(default=None)):
    """分页前置接口：列出全部 roomid 绑定，可按关键字过滤。"""
    try:
        result = chat_archive_binding_service.list_bindings(keyword=keyword)
        return _ok(result)
    except Exception as e:
        logger.exception("查询 roomid 绑定列表失败")
        return _err(-1, str(e), count=0, items=[])


@router.put("/archive/room-binding/{roomid}")
async def update_room_binding(roomid: str, payload: UpdateRoomBindingRequest):
    """更新指定 roomid 的群聊名。"""
    try:
        result = chat_archive_binding_service.update_binding(
            roomid=roomid,
            room_name=payload.room_name,
        )
        return _ok(result)
    except ValueError as e:
        return _err(_value_error_code(str(e), default_code=404), str(e), roomid=roomid)
    except Exception as e:
        logger.exception("更新 roomid 绑定失败: roomid=%s", roomid)
        return _err(-1, str(e), roomid=roomid)


@router.delete("/archive/room-binding/{roomid}")
async def delete_room_binding(roomid: str):
    """删除指定 roomid 的绑定信息。"""
    try:
        result = chat_archive_binding_service.delete_binding(roomid=roomid)
        return _ok(result)
    except ValueError as e:
        return _err(_value_error_code(str(e)), str(e), roomid=roomid)
    except Exception as e:
        logger.exception("删除 roomid 绑定失败: roomid=%s", roomid)
        return _err(-1, str(e), roomid=roomid)
