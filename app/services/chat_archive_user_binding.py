"""
会话存档用户昵称绑定服务
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.db_models import ChatArchiveUserBinding

logger = logging.getLogger(__name__)


class ChatArchiveUserBindingService:
    """管理会话存档 from user_id 与昵称映射关系。"""

    @staticmethod
    def _normalize_user_id(user_id: str) -> str:
        value = str(user_id or "").strip()
        if not value:
            raise ValueError("user_id 不能为空")
        if len(value) > 128:
            raise ValueError("user_id 最长 128 个字符")
        return value

    @staticmethod
    def _normalize_nickname(nickname: str) -> str:
        value = str(nickname or "").strip()
        if not value:
            raise ValueError("nickname 不能为空")
        if len(value) > 128:
            raise ValueError("nickname 最长 128 个字符")
        return value

    @staticmethod
    def _serialize(record: ChatArchiveUserBinding) -> Dict[str, Any]:
        return {
            "id": record.id,
            "user_id": record.user_id,
            "nickname": record.nickname,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

    def create_binding(self, user_id: str, nickname: str) -> Dict[str, Any]:
        user_id_value = self._normalize_user_id(user_id)
        nickname_value = self._normalize_nickname(nickname)

        db = SessionLocal()
        try:
            existing = (
                db.query(ChatArchiveUserBinding)
                .filter(ChatArchiveUserBinding.user_id == user_id_value)
                .first()
            )
            if existing:
                raise ValueError(f"user_id 已存在绑定: {user_id_value}")

            record = ChatArchiveUserBinding(user_id=user_id_value, nickname=nickname_value)
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._serialize(record)
        except SQLAlchemyError as db_err:
            db.rollback()
            logger.exception("创建 user_id 昵称绑定失败")
            raise RuntimeError(f"创建 user_id 昵称绑定失败: {db_err}") from db_err
        finally:
            db.close()

    def get_binding(self, user_id: str) -> Dict[str, Any]:
        user_id_value = self._normalize_user_id(user_id)

        db = SessionLocal()
        try:
            record = (
                db.query(ChatArchiveUserBinding)
                .filter(ChatArchiveUserBinding.user_id == user_id_value)
                .first()
            )
            if not record:
                raise ValueError(f"user_id 未绑定: {user_id_value}")
            return self._serialize(record)
        except SQLAlchemyError as db_err:
            logger.exception("查询 user_id 昵称绑定失败")
            raise RuntimeError(f"查询 user_id 昵称绑定失败: {db_err}") from db_err
        finally:
            db.close()

    def list_bindings(self, keyword: Optional[str] = None) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            query = db.query(ChatArchiveUserBinding)
            keyword_value = str(keyword or "").strip()
            if keyword_value:
                like_value = f"%{keyword_value}%"
                query = query.filter(
                    or_(
                        ChatArchiveUserBinding.user_id.like(like_value),
                        ChatArchiveUserBinding.nickname.like(like_value),
                    )
                )

            records = (
                query.order_by(
                    ChatArchiveUserBinding.updated_at.desc(),
                    ChatArchiveUserBinding.id.desc(),
                ).all()
            )
            items = [self._serialize(item) for item in records]
            return {
                "count": len(items),
                "items": items,
            }
        except SQLAlchemyError as db_err:
            logger.exception("查询 user_id 昵称绑定列表失败")
            raise RuntimeError(f"查询 user_id 昵称绑定列表失败: {db_err}") from db_err
        finally:
            db.close()

    def update_binding(self, user_id: str, nickname: str) -> Dict[str, Any]:
        user_id_value = self._normalize_user_id(user_id)
        nickname_value = self._normalize_nickname(nickname)

        db = SessionLocal()
        try:
            record = (
                db.query(ChatArchiveUserBinding)
                .filter(ChatArchiveUserBinding.user_id == user_id_value)
                .first()
            )
            if not record:
                raise ValueError(f"user_id 未绑定: {user_id_value}")

            record.nickname = nickname_value
            db.commit()
            db.refresh(record)
            return self._serialize(record)
        except SQLAlchemyError as db_err:
            db.rollback()
            logger.exception("更新 user_id 昵称绑定失败")
            raise RuntimeError(f"更新 user_id 昵称绑定失败: {db_err}") from db_err
        finally:
            db.close()

    def upsert_binding(self, user_id: str, nickname: str) -> Dict[str, Any]:
        """存在则更新，不存在则创建。"""
        user_id_value = self._normalize_user_id(user_id)
        nickname_value = self._normalize_nickname(nickname)

        db = SessionLocal()
        try:
            record = (
                db.query(ChatArchiveUserBinding)
                .filter(ChatArchiveUserBinding.user_id == user_id_value)
                .first()
            )

            action = "unchanged"
            if not record:
                record = ChatArchiveUserBinding(user_id=user_id_value, nickname=nickname_value)
                db.add(record)
                db.commit()
                db.refresh(record)
                action = "created"
            elif record.nickname != nickname_value:
                record.nickname = nickname_value
                db.commit()
                db.refresh(record)
                action = "updated"

            result = self._serialize(record)
            result["action"] = action
            return result
        except SQLAlchemyError as db_err:
            db.rollback()
            logger.exception("upsert user_id 昵称绑定失败")
            raise RuntimeError(f"upsert user_id 昵称绑定失败: {db_err}") from db_err
        finally:
            db.close()

    def delete_binding(self, user_id: str) -> Dict[str, Any]:
        user_id_value = self._normalize_user_id(user_id)

        db = SessionLocal()
        try:
            record = (
                db.query(ChatArchiveUserBinding)
                .filter(ChatArchiveUserBinding.user_id == user_id_value)
                .first()
            )
            if not record:
                return {
                    "user_id": user_id_value,
                    "deleted": False,
                }

            db.delete(record)
            db.commit()
            return {
                "user_id": user_id_value,
                "deleted": True,
            }
        except SQLAlchemyError as db_err:
            db.rollback()
            logger.exception("删除 user_id 昵称绑定失败")
            raise RuntimeError(f"删除 user_id 昵称绑定失败: {db_err}") from db_err
        finally:
            db.close()

    def get_nickname(self, user_id: str) -> Optional[str]:
        user_id_value = str(user_id or "").strip()
        if not user_id_value:
            return None

        db = SessionLocal()
        try:
            record = (
                db.query(ChatArchiveUserBinding.nickname)
                .filter(ChatArchiveUserBinding.user_id == user_id_value)
                .first()
            )
            return record[0] if record else None
        except SQLAlchemyError as db_err:
            logger.exception("读取 user nickname 失败")
            raise RuntimeError(f"读取 user nickname 失败: {db_err}") from db_err
        finally:
            db.close()

    def get_nickname_map(self, user_ids: List[str]) -> Dict[str, str]:
        normalized_ids = [str(item or "").strip() for item in user_ids if str(item or "").strip()]
        if not normalized_ids:
            return {}

        db = SessionLocal()
        try:
            records = (
                db.query(ChatArchiveUserBinding.user_id, ChatArchiveUserBinding.nickname)
                .filter(ChatArchiveUserBinding.user_id.in_(normalized_ids))
                .all()
            )
            return {user_id: nickname for user_id, nickname in records}
        except SQLAlchemyError as db_err:
            logger.exception("批量读取 user nickname 失败")
            raise RuntimeError(f"批量读取 user nickname 失败: {db_err}") from db_err
        finally:
            db.close()


chat_archive_user_binding_service = ChatArchiveUserBindingService()
