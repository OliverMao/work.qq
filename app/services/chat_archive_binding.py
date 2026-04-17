"""
会话存档群聊绑定服务
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.db_models import ChatArchiveRoomBinding

logger = logging.getLogger(__name__)


class ChatArchiveBindingService:
    """管理会话存档 roomid 与群聊名绑定关系。"""

    @staticmethod
    def _normalize_roomid(roomid: str) -> str:
        value = str(roomid or "").strip()
        if not value:
            raise ValueError("roomid 不能为空")
        if len(value) > 128:
            raise ValueError("roomid 最长 128 个字符")
        return value

    @staticmethod
    def _normalize_room_name(room_name: str) -> str:
        value = str(room_name or "").strip()
        if not value:
            raise ValueError("room_name 不能为空")
        if len(value) > 128:
            raise ValueError("room_name 最长 128 个字符")
        return value

    @staticmethod
    def _serialize(record: ChatArchiveRoomBinding) -> Dict[str, Any]:
        return {
            "id": record.id,
            "roomid": record.roomid,
            "room_name": record.room_name,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

    def create_binding(self, roomid: str, room_name: str) -> Dict[str, Any]:
        roomid_value = self._normalize_roomid(roomid)
        room_name_value = self._normalize_room_name(room_name)

        db = SessionLocal()
        try:
            existing = (
                db.query(ChatArchiveRoomBinding)
                .filter(ChatArchiveRoomBinding.roomid == roomid_value)
                .first()
            )
            if existing:
                raise ValueError(f"roomid 已存在绑定: {roomid_value}")

            record = ChatArchiveRoomBinding(roomid=roomid_value, room_name=room_name_value)
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._serialize(record)
        except SQLAlchemyError as db_err:
            db.rollback()
            logger.exception("创建 roomid 绑定失败")
            raise RuntimeError(f"创建 roomid 绑定失败: {db_err}") from db_err
        finally:
            db.close()

    def get_binding(self, roomid: str) -> Dict[str, Any]:
        roomid_value = self._normalize_roomid(roomid)

        db = SessionLocal()
        try:
            record = (
                db.query(ChatArchiveRoomBinding)
                .filter(ChatArchiveRoomBinding.roomid == roomid_value)
                .first()
            )
            if not record:
                raise ValueError(f"roomid 未绑定: {roomid_value}")
            return self._serialize(record)
        except SQLAlchemyError as db_err:
            logger.exception("查询 roomid 绑定失败")
            raise RuntimeError(f"查询 roomid 绑定失败: {db_err}") from db_err
        finally:
            db.close()

    def list_bindings(self, keyword: Optional[str] = None) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            query = db.query(ChatArchiveRoomBinding)
            keyword_value = str(keyword or "").strip()
            if keyword_value:
                like_value = f"%{keyword_value}%"
                query = query.filter(
                    or_(
                        ChatArchiveRoomBinding.roomid.like(like_value),
                        ChatArchiveRoomBinding.room_name.like(like_value),
                    )
                )

            records = (
                query.order_by(
                    ChatArchiveRoomBinding.updated_at.desc(),
                    ChatArchiveRoomBinding.id.desc(),
                ).all()
            )
            items = [self._serialize(item) for item in records]
            return {
                "count": len(items),
                "items": items,
            }
        except SQLAlchemyError as db_err:
            logger.exception("查询 roomid 绑定列表失败")
            raise RuntimeError(f"查询 roomid 绑定列表失败: {db_err}") from db_err
        finally:
            db.close()

    def update_binding(self, roomid: str, room_name: str) -> Dict[str, Any]:
        roomid_value = self._normalize_roomid(roomid)
        room_name_value = self._normalize_room_name(room_name)

        db = SessionLocal()
        try:
            record = (
                db.query(ChatArchiveRoomBinding)
                .filter(ChatArchiveRoomBinding.roomid == roomid_value)
                .first()
            )
            if not record:
                raise ValueError(f"roomid 未绑定: {roomid_value}")

            record.room_name = room_name_value
            db.commit()
            db.refresh(record)
            return self._serialize(record)
        except SQLAlchemyError as db_err:
            db.rollback()
            logger.exception("更新 roomid 绑定失败")
            raise RuntimeError(f"更新 roomid 绑定失败: {db_err}") from db_err
        finally:
            db.close()

    def delete_binding(self, roomid: str) -> Dict[str, Any]:
        roomid_value = self._normalize_roomid(roomid)

        db = SessionLocal()
        try:
            record = (
                db.query(ChatArchiveRoomBinding)
                .filter(ChatArchiveRoomBinding.roomid == roomid_value)
                .first()
            )
            if not record:
                return {
                    "roomid": roomid_value,
                    "deleted": False,
                }

            db.delete(record)
            db.commit()
            return {
                "roomid": roomid_value,
                "deleted": True,
            }
        except SQLAlchemyError as db_err:
            db.rollback()
            logger.exception("删除 roomid 绑定失败")
            raise RuntimeError(f"删除 roomid 绑定失败: {db_err}") from db_err
        finally:
            db.close()

    def get_room_name(self, roomid: str) -> Optional[str]:
        roomid_value = str(roomid or "").strip()
        if not roomid_value:
            return None

        db = SessionLocal()
        try:
            record = (
                db.query(ChatArchiveRoomBinding.room_name)
                .filter(ChatArchiveRoomBinding.roomid == roomid_value)
                .first()
            )
            return record[0] if record else None
        except SQLAlchemyError as db_err:
            logger.exception("读取 room_name 失败")
            raise RuntimeError(f"读取 room_name 失败: {db_err}") from db_err
        finally:
            db.close()

    def get_room_name_map(self, roomids: List[str]) -> Dict[str, str]:
        normalized_roomids = [str(item or "").strip() for item in roomids if str(item or "").strip()]
        if not normalized_roomids:
            return {}

        db = SessionLocal()
        try:
            records = (
                db.query(ChatArchiveRoomBinding.roomid, ChatArchiveRoomBinding.room_name)
                .filter(ChatArchiveRoomBinding.roomid.in_(normalized_roomids))
                .all()
            )
            return {roomid: room_name for roomid, room_name in records}
        except SQLAlchemyError as db_err:
            logger.exception("批量读取 room_name 失败")
            raise RuntimeError(f"批量读取 room_name 失败: {db_err}") from db_err
        finally:
            db.close()


chat_archive_binding_service = ChatArchiveBindingService()
