"""
企业微信群聊管理路由
"""

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.chat_group_in import chat_group_service

router = APIRouter(prefix="/chat", tags=["chat"])


class CreateChatGroupRequest(BaseModel):
    userlist: List[str]
    name: Optional[str] = None
    owner: Optional[str] = None


class UpdateChatGroupRequest(BaseModel):
    chatid: str
    name: Optional[str] = None
    owner: Optional[str] = None
    add_user_list: Optional[List[str]] = None
    del_user_list: Optional[List[str]] = None


class SendMarkdownMessageRequest(BaseModel):
    chatid: str
    content: str


class CustomerGroupDetailRequest(BaseModel):
    chat_id: str
    need_name: int = 0


@router.post("/group")
async def create_chat_group(payload: CreateChatGroupRequest):
    """创建企业微信群聊会话。"""
    return chat_group_service.create_chat_group(
        userlist=payload.userlist,
        name=payload.name,
        owner=payload.owner
    )


@router.get("/group/{chatid}")
async def get_chat_group(chatid: str):
    """获取企业微信群聊信息。"""
    return chat_group_service.get_chat_group(chatid=chatid)


@router.post("/group/update")
async def update_chat_group(payload: UpdateChatGroupRequest):
    """修改企业微信群聊会话。"""
    return chat_group_service.update_chat_group(
        chatid=payload.chatid,
        name=payload.name,
        owner=payload.owner,
        add_user_list=payload.add_user_list,
        del_user_list=payload.del_user_list,
    )


@router.post("/group/send/markdown")
async def send_group_markdown(payload: SendMarkdownMessageRequest):
    """向指定群聊发送 markdown 消息。"""
    return chat_group_service.send_markdown_message(
        chatid=payload.chatid,
        content=payload.content,
    )


@router.post("/customer-group/detail")
async def get_customer_group_detail(payload: CustomerGroupDetailRequest):
    """获取客户群详情（externalcontact/groupchat/get）。"""
    return chat_group_service.get_customer_group_detail(
        chat_id=payload.chat_id,
        need_name=payload.need_name,
    )