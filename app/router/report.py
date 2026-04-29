"""
学习报告生成路由
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.report_generation import report_generation_service

router = APIRouter(prefix="/api/report", tags=["Report"])


class GenerateReportRequest(BaseModel):
    roomid: str
    chat_name: Optional[str] = None


@router.get("/chats")
async def list_chats():
    """列出可用的群聊"""
    return {"items": report_generation_service.list_available_chats()}


@router.post("/generate")
async def generate_report(req: GenerateReportRequest):
    """生成学习报告"""
    result = report_generation_service.generate_report(
        roomid=req.roomid,
        chat_name=req.chat_name,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result