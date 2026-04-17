"""
通讯录路由
"""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.user_directory import user_directory_service

router = APIRouter(prefix="/user", tags=["user"])


class ListMemberIdsRequest(BaseModel):
    cursor: Optional[str] = None
    limit: int = Field(default=10000, ge=1, le=10000)


@router.post("/list-id")
async def list_member_ids(payload: ListMemberIdsRequest):
    return user_directory_service.list_member_ids(
        cursor=payload.cursor,
        limit=payload.limit,
    )
