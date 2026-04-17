"""
SQLAlchemy ORM 模型
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# class ChatGroupRecord(Base):
    # """本地群聊记录。"""

    # __tablename__ = "chat_groups"

    # chatid: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)
    # name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # userlist_json: Mapped[str] = mapped_column(Text, nullable=False)
    # chat_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
