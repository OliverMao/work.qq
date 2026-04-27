"""
企业微信通讯录服务
"""

import logging
from typing import Any, Dict, Optional

import httpx

from app.config import settings
from app.services.wecom_api import wecom_api_client

logger = logging.getLogger(__name__)


class UserDirectoryService:
    """封装企业微信通讯录相关接口。"""

    def list_member_ids(
        self,
        cursor: Optional[str] = None,
        limit: int = 10000,
    ) -> Dict[str, Any]:
        """获取企业成员 userid 与部门 ID 列表。"""
        if limit < 1 or limit > 10000:
            raise ValueError("limit 取值范围为 1 ~ 10000")

        token = wecom_api_client.get_access_token(secret=settings.wecom_contact_secret)
        if not token:
            raise RuntimeError("无法获取企业微信通讯录 access_token")

        payload: Dict[str, Any] = {"limit": limit}
        if cursor:
            payload["cursor"] = cursor

        url = f"https://qyapi.weixin.qq.com/cgi-bin/user/list_id?access_token={token}"
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, json=payload)
                data = resp.json()
        except Exception as e:
            logger.exception("调用 user/list_id 接口异常")
            raise RuntimeError(f"调用 user/list_id 接口异常: {e}") from e

        if data.get("errcode") != 0:
            raise RuntimeError(f"获取成员ID列表失败: {data}")

        return {
            "errcode": data.get("errcode", 0),
            "errmsg": data.get("errmsg", "ok"),
            "next_cursor": data.get("next_cursor", ""),
            "dept_user": data.get("dept_user", []),
        }


user_directory_service = UserDirectoryService()
