"""
群聊管理路由
"""

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.chat_group import chat_group_service

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
    need_name: int = Field(default=0, ge=0, le=1)


@router.post("/group")
async def create_chat_group(payload: CreateChatGroupRequest):
    """创建企业微信群聊会话。"""
    return chat_group_service.create_chat_group(
        userlist=payload.userlist,
        name=payload.name,
        owner=payload.owner
    )


@router.get("/groups")
async def list_chat_groups():
    """列出所有已创建的企业微信群聊会话。"""
    return chat_group_service.list_all_chat_groups()


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


@router.get("/group/sync")
async def sync_chat_group(chatid: str):
    """从企业微信获取群聊信息并同步到本地数据库。"""
    return chat_group_service.get_chat_group_and_sync(chatid=chatid)


@router.delete("/group/{chatid}")
async def delete_chat_group(chatid: str):
    """删除本地数据库中的群聊记录。"""
    return chat_group_service.delete_chat_group(chatid)


@router.post("/group/send/markdown")
async def send_group_markdown(payload: SendMarkdownMessageRequest):
    """向指定群聊发送 markdown 消息。"""
    return chat_group_service.send_markdown_message(
        chatid=payload.chatid,
        content=payload.content,
    )


@router.post("/groups/sync")
async def batch_sync_groups_from_cloud():
    """批量从企业微信云端同步群聊信息到本地数据库。"""
    return chat_group_service.batch_sync_chat_groups_from_cloud()


@router.post("/customer-group/detail")
async def get_customer_group_detail(payload: CustomerGroupDetailRequest):
    """获取客户群详情（externalcontact/groupchat/get）。"""
    return chat_group_service.get_customer_group_detail(
        chat_id=payload.chat_id,
        need_name=payload.need_name,
    )
