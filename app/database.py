"""
数据库连接与会话管理
"""

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session


DB_PATH = Path(__file__).resolve().parent.parent / "sql.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _ensure_chat_groups_columns() -> None:
    """兼容已存在的 sqlite 表结构，补齐新增字段。"""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(chat_groups)"))
        columns = {row[1] for row in result.fetchall()}
        if not columns:
            return

        if "userlist_json" not in columns:
            conn.execute(
                text("ALTER TABLE chat_groups ADD COLUMN userlist_json TEXT NOT NULL DEFAULT '[]'")
            )
        if "chat_type" not in columns:
            conn.execute(text("ALTER TABLE chat_groups ADD COLUMN chat_type INTEGER"))
        if "created_at" not in columns:
            conn.execute(text("ALTER TABLE chat_groups ADD COLUMN created_at DATETIME"))
        conn.commit()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # 延迟导入，避免循环依赖
    from app import db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_chat_groups_columns()
