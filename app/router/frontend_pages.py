"""
前端页面路由
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["frontend"])

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def _serve_html(*parts: str) -> FileResponse:
    page_path = STATIC_DIR.joinpath(*parts)
    return FileResponse(path=str(page_path), media_type="text/html")


@router.get("/index")
async def frontend_index_page():
    """会话存档前端首页。"""
    return _serve_html("frontend", "index.html")


@router.get("/index/", include_in_schema=False)
async def frontend_index_page_with_slash():
    return _serve_html("frontend", "index.html")


@router.get("/index/modules")
async def frontend_modules_page():
    """会话存档模块管理页。"""
    return _serve_html("frontend", "modules.html")


@router.get("/index/users")
async def frontend_users_page():
    """用户昵称绑定管理页。"""
    return _serve_html("frontend", "users.html")
