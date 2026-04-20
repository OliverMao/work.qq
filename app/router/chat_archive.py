"""
会话存档路由
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.services.chat_archive import chat_archive_service
from app.services.chat_archive_binding import chat_archive_binding_service
from app.services.chat_archive_user_binding import chat_archive_user_binding_service
from app.services.wecom_api import wecom_api_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class CreateRoomBindingRequest(BaseModel):
    roomid: str = Field(..., min_length=1, max_length=128)
    room_name: str = Field(..., min_length=1, max_length=128)


class UpdateRoomBindingRequest(BaseModel):
    room_name: str = Field(..., min_length=1, max_length=128)


class CreateUserBindingRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    nickname: str = Field(..., min_length=1, max_length=128)


class UpdateUserBindingRequest(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=128)


class AutoBindUsersRequest(BaseModel):
    keyword: Optional[str] = None
    only_unbound: bool = True
    limit: int = Field(default=1000, ge=1, le=10000)


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


def _is_wecom_user_id(user_id: str) -> bool:
    value = str(user_id or "").strip().lower()
    return value.startswith("wo") or value.startswith("wm")


def _fetch_wecom_user_nickname(access_token: str, user_id: str) -> str:
    url = "https://qyapi.weixin.qq.com/cgi-bin/user/get"
    resp = httpx.get(
        url,
        params={"access_token": access_token, "userid": user_id},
        timeout=10,
    )
    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"user/get 失败: {data}")

    nickname = str(data.get("name") or data.get("alias") or "").strip()
    if not nickname:
        raise RuntimeError("user/get 未返回可用昵称")
    return nickname

def _fetch_externalcontact_user_nickname(access_token: str, user_id: str) -> str:
    url = "https://qyapi.weixin.qq.com/cgi-bin/externalcontact/get"
    resp = httpx.get(
        url,
        params={"access_token": access_token, "external_userid": user_id},
        timeout=10,
    )
    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"externalcontact/get 失败: {data}")

    nickname = str(data.get("name") or data.get("alias") or "").strip()
    if not nickname:
        raise RuntimeError("externalcontact/get 未返回可用昵称")
    return nickname


def _enrich_from_display(messages: Any) -> None:
    if not isinstance(messages, list):
        return

    user_ids = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        user_id = str(item.get("from") or "").strip()
        if user_id:
            user_ids.append(user_id)

    nickname_map = chat_archive_user_binding_service.get_nickname_map(user_ids=user_ids)

    for item in messages:
        if not isinstance(item, dict):
            continue
        user_id = str(item.get("from") or "").strip()
        if not user_id:
            continue
        nickname = nickname_map.get(user_id)
        item["from_nickname"] = nickname
        item["from_display"] = nickname or user_id


@router.get("/archive/room-binding/admin")
async def room_binding_admin_page():
    """会话存档群聊绑定管理页面。"""
    page_path = Path(__file__).resolve().parents[1] / "static" / "frontend" / "modules.html"
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
        messages = result.get("messages")
        _enrich_from_display(messages)

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
        messages = result.get("messages")
        _enrich_from_display(messages)

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


@router.post("/archive/user-binding")
async def create_user_binding(payload: CreateUserBindingRequest):
    """创建 user_id 与昵称绑定。"""
    try:
        result = chat_archive_user_binding_service.create_binding(
            user_id=payload.user_id,
            nickname=payload.nickname,
        )
        return _ok(result)
    except ValueError as e:
        return _err(_value_error_code(str(e)), str(e))
    except Exception as e:
        logger.exception("创建 user_id 昵称绑定失败")
        return _err(-1, str(e))


@router.get("/archive/user-binding/{user_id}")
async def get_user_binding(user_id: str):
    """获取单个 user_id 的昵称绑定信息。"""
    try:
        result = chat_archive_user_binding_service.get_binding(user_id=user_id)
        return _ok(result)
    except ValueError as e:
        return _err(_value_error_code(str(e), default_code=404), str(e), user_id=user_id)
    except Exception as e:
        logger.exception("查询 user_id 昵称绑定失败: user_id=%s", user_id)
        return _err(-1, str(e), user_id=user_id)


@router.get("/archive/user-bindings")
async def list_user_bindings(keyword: Optional[str] = Query(default=None)):
    """列出全部 user_id 昵称绑定，可按关键字过滤。"""
    try:
        result = chat_archive_user_binding_service.list_bindings(keyword=keyword)
        return _ok(result)
    except Exception as e:
        logger.exception("查询 user_id 昵称绑定列表失败")
        return _err(-1, str(e), count=0, items=[])


@router.get("/archive/user-candidates")
async def list_archive_user_candidates(keyword: Optional[str] = Query(default=None)):
    """读取全部聊天文件，返回去重后的 user_id 候选列表。"""
    try:
        result = chat_archive_service.list_archive_distinct_user_ids(keyword=keyword)
        items = result.get("items") or []

        user_ids = [
            item.get("user_id")
            for item in items
            if isinstance(item, dict) and item.get("user_id")
        ]
        nickname_map = (
            chat_archive_user_binding_service.get_nickname_map(user_ids=user_ids)
            if user_ids
            else {}
        )

        for item in items:
            if not isinstance(item, dict):
                continue
            user_id = str(item.get("user_id") or "").strip()
            nickname = nickname_map.get(user_id)
            item["nickname"] = nickname
            item["display_name"] = nickname or user_id
            item["is_bound"] = bool(nickname)
            item["can_auto_query"] = True

        return _ok(result)
    except Exception as e:
        logger.exception("查询 user_id 候选列表失败")
        return _err(-1, str(e), count=0, files_scanned=0, messages_scanned=0, items=[])


@router.post("/archive/user-bindings/auto-bind")
async def auto_query_and_bind_users(payload: AutoBindUsersRequest):
    """一键查询并绑定：扫描全部 user_id，按规则自动查询昵称并写入绑定表。"""
    try:
        result = chat_archive_service.list_archive_distinct_user_ids(keyword=payload.keyword)
        items = result.get("items") or []

        all_user_ids = [
            str(item.get("user_id") or "").strip()
            for item in items
            if isinstance(item, dict) and str(item.get("user_id") or "").strip()
        ]
        nickname_map = (
            chat_archive_user_binding_service.get_nickname_map(user_ids=all_user_ids)
            if all_user_ids
            else {}
        )

        target_user_ids = []
        skipped_not_queryable = 0
        skipped_already_bound = 0

        for user_id in all_user_ids:
            if payload.only_unbound and nickname_map.get(user_id):
                skipped_already_bound += 1
                continue
            target_user_ids.append(user_id)

        truncated = False
        if len(target_user_ids) > payload.limit:
            target_user_ids = target_user_ids[: payload.limit]
            truncated = True

        if not target_user_ids:
            return _ok(
                {
                    "total_user_ids": len(all_user_ids),
                    "queryable_user_ids": len(all_user_ids) - skipped_not_queryable,
                    "selected_user_ids": 0,
                    "skipped_not_queryable": skipped_not_queryable,
                    "skipped_already_bound": skipped_already_bound,
                    "queried_count": 0,
                    "success_count": 0,
                    "created_count": 0,
                    "updated_count": 0,
                    "unchanged_count": 0,
                    "failed_count": 0,
                    "truncated": truncated,
                    "bound_items": [],
                    "failed_items": [],
                }
            )

        app_secret = str(settings.app_secret or "").strip()
        if not app_secret:
            raise RuntimeError("WECOM_APP_SECRET 未配置，无法执行一键查询绑定")

        access_token = wecom_api_client.get_access_token(secret=app_secret)
        if not access_token:
            raise RuntimeError("无法获取企业微信 access_token")

        queried_count = 0
        created_count = 0
        updated_count = 0
        unchanged_count = 0
        failed_items = []
        bound_items = []

        for user_id in target_user_ids:
            queried_count += 1
            try:
                if _is_wecom_user_id(user_id):
                    nickname = _fetch_wecom_user_nickname(access_token=access_token, user_id=user_id)
                else:
                    nickname = _fetch_externalcontact_user_nickname(access_token=access_token, user_id=user_id)
                bind_result = chat_archive_user_binding_service.upsert_binding(
                    user_id=user_id,
                    nickname=nickname,
                )
                action = str(bind_result.get("action") or "")
                if action == "created":
                    created_count += 1
                elif action == "updated":
                    updated_count += 1
                else:
                    unchanged_count += 1

                bound_items.append(
                    {
                        "user_id": user_id,
                        "nickname": bind_result.get("nickname"),
                        "action": action,
                    }
                )
            except Exception as err:
                failed_items.append(
                    {
                        "user_id": user_id,
                        "error": str(err),
                    }
                )

        success_count = created_count + updated_count + unchanged_count
        return _ok(
            {
                "total_user_ids": len(all_user_ids),
                "queryable_user_ids": len(all_user_ids) - skipped_not_queryable,
                "selected_user_ids": len(target_user_ids),
                "skipped_not_queryable": skipped_not_queryable,
                "skipped_already_bound": skipped_already_bound,
                "queried_count": queried_count,
                "success_count": success_count,
                "created_count": created_count,
                "updated_count": updated_count,
                "unchanged_count": unchanged_count,
                "failed_count": len(failed_items),
                "truncated": truncated,
                "bound_items": bound_items,
                "failed_items": failed_items,
            }
        )
    except Exception as e:
        logger.exception("一键查询并绑定 user_id 失败")
        return _err(-1, str(e))


@router.put("/archive/user-binding/{user_id}")
async def update_user_binding(user_id: str, payload: UpdateUserBindingRequest):
    """更新指定 user_id 的昵称。"""
    try:
        result = chat_archive_user_binding_service.update_binding(
            user_id=user_id,
            nickname=payload.nickname,
        )
        return _ok(result)
    except ValueError as e:
        return _err(_value_error_code(str(e), default_code=404), str(e), user_id=user_id)
    except Exception as e:
        logger.exception("更新 user_id 昵称绑定失败: user_id=%s", user_id)
        return _err(-1, str(e), user_id=user_id)


@router.delete("/archive/user-binding/{user_id}")
async def delete_user_binding(user_id: str):
    """删除指定 user_id 的昵称绑定信息。"""
    try:
        result = chat_archive_user_binding_service.delete_binding(user_id=user_id)
        return _ok(result)
    except ValueError as e:
        return _err(_value_error_code(str(e)), str(e), user_id=user_id)
    except Exception as e:
        logger.exception("删除 user_id 昵称绑定失败: user_id=%s", user_id)
        return _err(-1, str(e), user_id=user_id)
