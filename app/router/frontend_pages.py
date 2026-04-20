"""
前端页面路由
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["frontend"])

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def _serve_html(filename: str) -> FileResponse:
    page_path = STATIC_DIR / filename
    return FileResponse(path=str(page_path), media_type="text/html")


@router.get("/index")
async def frontend_index_page():
    """会话存档前端首页。"""
    return _serve_html("chat_archive_index.html")


@router.get("/index/", include_in_schema=False)
async def frontend_index_page_with_slash():
    return _serve_html("chat_archive_index.html")


@router.get("/index/modules")
async def frontend_modules_page():
    """会话存档模块管理页。"""
    return _serve_html("chat_archive_binding_admin.html")
