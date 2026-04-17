"""
SQLAlchemy ORM 模型
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChatArchiveRoomBinding(Base):
    """会话存档群聊绑定：roomid 与群聊名称映射。"""

    __tablename__ = "chat_archive_room_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    roomid: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    room_name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
