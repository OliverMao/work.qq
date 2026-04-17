"""
企业微信 API 访问公共能力
"""

import logging
import time
from typing import Dict, Optional, Tuple

import requests

from app.config import settings

logger = logging.getLogger(__name__)


class WecomAPIClient:
    """封装 access_token 获取与缓存。"""

    def __init__(self):
        self._token_cache: Dict[str, Tuple[str, float]] = {}

    def get_access_token(self, secret: Optional[str] = None) -> Optional[str]:
        corp_id = settings.corp_id
        secret = secret or settings.corp_secret
        if not corp_id or not secret:
            logger.error("企业微信配置不完整，无法获取 access_token")
            return None

        cache_key = f"{corp_id}:{secret}"
        cached = self._token_cache.get(cache_key)
        if cached and time.time() < cached[1]:
            return cached[0]

        url = (
            "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
            f"?corpid={corp_id}&corpsecret={secret}"
        )
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if data.get("errcode") == 0:
                token = data.get("access_token")
                expires_at = time.time() + data.get("expires_in", 7200) - 300
                self._token_cache[cache_key] = (token, expires_at)
                return token
            logger.error("获取access_token失败: %s", data)
        except Exception as e:
            logger.error("获取access_token异常: %s", e)
        return None


wecom_api_client = WecomAPIClient()
