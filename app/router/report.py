"""
学习报告生成路由
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.report_generation import report_generation_service

router = APIRouter(prefix="/api/report", tags=["Report"])


class GenerateReportRequest(BaseModel):
    roomid: str
    chat_name: Optional[str] = None


def _ok(**data: Any) -> Dict[str, Any]:
    return {"errcode": 0, "errmsg": "ok", **data}


def _error(errcode: int, errmsg: str, **extra: Any) -> Dict[str, Any]:
    return {"errcode": errcode, "errmsg": errmsg, **extra}


@router.get("/chats")
async def list_chats():
    """列出可用的群聊"""
    items = report_generation_service.list_available_chats()
    return _ok(items=items)


@router.post("/generate")
async def generate_report(req: GenerateReportRequest):
    """生成学习报告"""
    result = report_generation_service.generate_report(
        roomid=req.roomid,
        chat_name=req.chat_name,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return _ok(
        roomid=result.get("roomid"),
        chat_name=result.get("chat_name"),
        message_count=result.get("message_count"),
        report=result.get("report"),
        model=result.get("model"),
    )