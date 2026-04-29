"""
企业微信内部群聊服务 - 直接调用 API，不存数据库
"""

import logging
import re
import uuid
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.services.wecom_api import wecom_api_client

logger = logging.getLogger(__name__)


class ChatGroupService:
    """企业微信群聊服务 - 仅调用 API，不存数据库"""

    @staticmethod
    def _normalize_userlist(userlist: List[str]) -> List[str]:
        users = [str(user).strip() for user in userlist if str(user).strip()]
        if len(users) < 2:
            raise ValueError("userlist 至少需要 2 个成员")
        if len(users) > 2000:
            raise ValueError("userlist 最多允许 2000 个成员")
        return users

    @staticmethod
    def _validate_chatid(chatid: Optional[str]) -> Optional[str]:
        if chatid is None:
            return None
        chatid = str(chatid).strip()
        if not chatid:
            return None
        if len(chatid) > 32:
            raise ValueError("chatid 最多 32 个字符")
        if not re.fullmatch(r"[0-9A-Za-z]+", chatid):
            raise ValueError("chatid 只允许 0-9、a-z、A-Z")
        return chatid

    @staticmethod
    def _sanitize_user_ids(user_ids: Optional[List[str]]) -> List[str]:
        if not user_ids:
            return []
        return [str(user).strip() for user in user_ids if str(user).strip()]

    @staticmethod
    def _validate_external_chat_id(chat_id: str) -> str:
        value = str(chat_id or "").strip()
        if not value:
            raise ValueError("chat_id 不能为空")
        return value

    def create_chat_group(
        self,
        userlist: List[str],
        name: Optional[str] = None,
        owner: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建企业微信群聊会话。"""
        token = wecom_api_client.get_access_token(secret=settings.app_secret)
        if not token:
            raise RuntimeError("无法获取企业微信 access_token")

        members = self._normalize_userlist(userlist)
        payload: Dict[str, Any] = {"userlist": members}

        if name:
            payload["name"] = str(name).strip()[:50]
        if owner:
            payload["owner"] = str(owner).strip()

        final_chatid = uuid.uuid4().hex
        payload["chatid"] = final_chatid

        url = f"https://qyapi.weixin.qq.com/cgi-bin/appchat/create?access_token={token}"
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, json=payload)
                data = resp.json()
            if data.get("errcode") != 0:
                raise RuntimeError(f"创建群聊失败: {data}")
            return data
        except Exception as e:
            logger.exception("创建群聊会话失败")
            raise RuntimeError(f"创建群聊会话异常: {e}") from e

    def get_chat_group(self, chatid: str) -> Dict[str, Any]:
        """获取企业微信群聊信息。"""
        validated_chatid = self._validate_chatid(chatid)
        if not validated_chatid:
            raise ValueError("chatid 不能为空")

        token = wecom_api_client.get_access_token(secret=settings.app_secret)
        if not token:
            raise RuntimeError("无法获取企业微信 access_token")

        url = (
            "https://qyapi.weixin.qq.com/cgi-bin/appchat/get"
            f"?access_token={token}&chatid={validated_chatid}"
        )

        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                data = resp.json()
            if data.get("errcode") != 0:
                raise RuntimeError(f"获取群聊会话失败: {data}")
            return data
        except Exception as e:
            logger.exception("获取群聊会话失败")
            raise RuntimeError(f"获取群聊会话异常: {e}") from e

    def update_chat_group(
        self,
        chatid: str,
        name: Optional[str] = None,
        owner: Optional[str] = None,
        add_user_list: Optional[List[str]] = None,
        del_user_list: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """修改企业微信群聊。"""
        validated_chatid = self._validate_chatid(chatid)
        if not validated_chatid:
            raise ValueError("chatid 不能为空")

        add_users = self._sanitize_user_ids(add_user_list)
        del_users = self._sanitize_user_ids(del_user_list)
        has_update_field = bool(
            (name and str(name).strip())
            or (owner and str(owner).strip())
            or add_users
            or del_users
        )
        if not has_update_field:
            raise ValueError("name、owner、add_user_list、del_user_list 至少传一个")

        token = wecom_api_client.get_access_token(secret=settings.app_secret)
        if not token:
            raise RuntimeError("无法获取企业微信 access_token")

        payload: Dict[str, Any] = {"chatid": validated_chatid}
        if name and str(name).strip():
            payload["name"] = str(name).strip()[:50]
        if owner and str(owner).strip():
            payload["owner"] = str(owner).strip()
        if add_users:
            payload["add_user_list"] = add_users
        if del_users:
            payload["del_user_list"] = del_users

        url = f"https://qyapi.weixin.qq.com/cgi-bin/appchat/update?access_token={token}"
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, json=payload)
                data = resp.json()
            if data.get("errcode") != 0:
                raise RuntimeError(f"修改群聊失败: {data}")
            return data
        except Exception as e:
            logger.exception("修改群聊会话失败")
            raise RuntimeError(f"修改群聊会话异常: {e}") from e

    def send_markdown_message(self, chatid: str, content: str) -> Dict[str, Any]:
        """向指定群聊发送 markdown 消息。"""
        validated_chatid = self._validate_chatid(chatid)
        if not validated_chatid:
            raise ValueError("chatid 不能为空")

        final_content = str(content).strip()
        if not final_content:
            raise ValueError("content 不能为空")
        if len(final_content.encode("utf-8")) > 2048:
            raise ValueError("content 最长不超过 2048 字节")

        token = wecom_api_client.get_access_token(secret=settings.app_secret)
        if not token:
            raise RuntimeError("无法获取企业微信 access_token")

        payload = {
            "chatid": validated_chatid,
            "msgtype": "markdown",
            "markdown": {"content": final_content},
        }
        url = f"https://qyapi.weixin.qq.com/cgi-bin/appchat/send?access_token={token}"

        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, json=payload)
                data = resp.json()
            if data.get("errcode") != 0:
                raise RuntimeError(f"发送 markdown 消息失败: {data}")
            return data
        except Exception as e:
            logger.exception("发送 markdown 消息���败")
            raise RuntimeError(f"发送 markdown 消息异常: {e}") from e

    def get_customer_group_detail(self, chat_id: str, need_name: int = 0) -> Dict[str, Any]:
        """获取客户群详情（externalcontact/groupchat/get）。"""
        validated_chat_id = self._validate_external_chat_id(chat_id)

        if need_name not in (0, 1):
            raise ValueError("need_name 只允许 0 或 1")

        secret = settings.wecom_contact_secret or settings.app_secret
        token = wecom_api_client.get_access_token(secret=secret)
        if not token:
            raise RuntimeError("无法获取客户联系 access_token")

        payload: Dict[str, Any] = {
            "chat_id": validated_chat_id,
            "need_name": int(need_name),
        }
        url = (
            "https://qyapi.weixin.qq.com/cgi-bin/externalcontact/groupchat/get"
            f"?access_token={token}"
        )

        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, json=payload)
                data = resp.json()
        except Exception as e:
            logger.exception("调用 externalcontact/groupchat/get 接口异常")
            raise RuntimeError(f"调用 externalcontact/groupchat/get 接口异常: {e}") from e

        if data.get("errcode") != 0:
            raise RuntimeError(f"获取客户群详情失败: {data}")

        return data


chat_group_service = ChatGroupService()