from fastapi import APIRouter

from app.router.chat_archive import router as chat_archive_router
from app.router.chat_group import router as chat_group_router
from app.router.user_directory import router as user_directory_router
from app.router.wecom_callback import router as wecom_callback_router

router = APIRouter()
router.include_router(wecom_callback_router)
router.include_router(chat_archive_router)
router.include_router(chat_group_router)
router.include_router(user_directory_router)
