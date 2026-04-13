"""
企业微信会话内容存档 API Client + SDK 集成
"""

import base64
import json
import logging
import os
import time
import threading
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import requests

from app.config import settings

logger = logging.getLogger(__name__)

WECOM_API_BASE = "https://qyapi.weixin.qq.com"
TOKEN_LOCK = threading.Lock()


class ChatArchiveClient:
    """
    企业微信会话内容存档客户端
    流程:
    1. 获取 access_token
    2. 调用 GetCurPageCount / GetPageContent (新版 API)
       或使用 C SDK 的 GetChatData + DecryptData
    本实现优先使用 REST API (无需 C SDK)，如果配置了 SDK 路径则使用 SDK 方式
    """

    def __init__(self):
        self._access_token: str = ""
        self._token_expires_at: float = 0

    # ==================== access_token ====================

    def get_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        with TOKEN_LOCK:
            if self._access_token and time.time() < self._token_expires_at:
                return self._access_token

            url = f"{WECOM_API_BASE}/cgi-bin/gettoken"
            resp = requests.get(
                url,
                params={
                    "corpid": settings.corp_id,
                    "corpsecret": settings.chat_archive_secret,
                },
                timeout=10,
            )
            data = resp.json()
            if data.get("errcode", 0) != 0:
                raise RuntimeError(f"获取 access_token 失败: {data}")
            self._access_token = data["access_token"]
            self._token_expires_at = time.time() + data.get("expires_in", 7200) - 300
            return self._access_token

    # ==================== REST API (推荐方式) ====================

    def get_page_count(self, start_time: int, end_time: int) -> int:
        """
        获取指定时间范围内有多少页数据 (每页100条)
        API: GET /cgi-bin/finance/getcurpagecount?access_token=TOKEN
        """
        url = f"{WECOM_API_BASE}/cgi-bin/finance/getcurpagecount"
        resp = requests.get(
            url,
            timeout=10,
            params={
                "access_token": self.get_access_token(),
                "starttime": start_time,
                "endtime": end_time,
            },
        )
        data = resp.json()
        if data.get("errcode", 0) != 0:
            raise RuntimeError(f"GetCurPageCount 失败: {data}")
        return data.get("page_cnt", 0)

    def get_page_content(self, start_time: int, end_time: int, page: int) -> dict:
        """
        获取指定页数据 (每页100条)
        API: GET /cgi-bin/finance/getpagecontent?access_token=TOKEN
        """
        url = f"{WECOM_API_BASE}/cgi-bin/finance/getpagecontent"
        resp = requests.get(
            url,
            timeout=30,
            params={
                "access_token": self.get_access_token(),
                "starttime": start_time,
                "endtime": end_time,
                "page": page,
            },
        )
        data = resp.json()
        if data.get("errcode", 0) != 0:
            raise RuntimeError(f"GetPageContent 失败: {data}")
        return data

    # ==================== C SDK 调用方式 ====================

    def init_sdk(self):
        """初始化 SDK，返回 sdk_ptr"""
        sdk_lib_path = settings.sdk_lib_path
        if not sdk_lib_path or not os.path.exists(sdk_lib_path):
            raise FileNotFoundError(
                f"找不到 SDK 库文件: {sdk_lib_path}\n"
                f"请下载: https://wwcdn.weixin.qq.com/node/wework/images/sdk_20240606.tgz\n"
                f"并配置 WECOM_SDK_LIB_PATH 到 .env"
            )

        import ctypes

        lib = ctypes.CDLL(sdk_lib_path)

        lib.NewSdk.restype = ctypes.c_void_p
        lib.Init.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        lib.Init.restype = ctypes.c_int
        lib.GetChatData.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulonglong,
            ctypes.c_uint,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
        lib.GetChatData.restype = ctypes.c_int
        lib.DecryptData.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p]
        lib.DecryptData.restype = ctypes.c_int
        lib.FreeSlice.argtypes = [ctypes.c_void_p]
        lib.FreeSlice.restype = ctypes.c_int

        sdk = lib.NewSdk()
        ret = lib.Init(
            sdk, settings.corp_id.encode(), settings.chat_archive_secret.encode()
        )
        if ret != 0:
            raise RuntimeError(f"SDK Init 失败, ret={ret}")

        return lib, sdk

    def rsa_decrypt(self, encrypt_random_key: str) -> Optional[str]:
        """
        使用 RSA 私钥解密 encrypt_random_key
        使用 PKCS1 v1.5 填充
        """
        from Crypto.Cipher import PKCS1_v1_5
        from Crypto.PublicKey import RSA

        key_path = settings.rsa_private_key_path
        if not key_path or not os.path.exists(key_path):
            raise FileNotFoundError(
                f"找不到 RSA 私钥: {key_path}\n"
                f"请在 .env 中配置 WECOM_RSA_PRIVATE_KEY_PATH"
            )

        encrypted = base64.b64decode(encrypt_random_key)
        with open(key_path, "rb") as f:
            rsa_key = RSA.import_key(f.read())

        cipher = PKCS1_v1_5.new(rsa_key)
        try:
            decrypted = cipher.decrypt(encrypted, None)
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error("RSA 解密失败: %s", e)
            return None

    # ==================== 核心拉取 + 保存逻辑 ====================

    def archive_messages(
        self,
        begin_time: int = 0,
        end_time: int = 0,
        limit: int = 1000,
        save_dir: Optional[str] = None,
    ) -> dict:
        """
        拉取并保存会话内容到本地文件

        Args:
            begin_time: 开始时间戳 (秒)
            end_time:   结束时间戳 (秒)
            limit:      拉取条数 (最大1000)
            save_dir:   保存目录路径 (默认: 配置中的 archive_data/)

        Returns:
            {"saved_count": N, "save_path": "...", "messages": [...]}
        """
        import time as _time

        if not end_time:
            end_time = int(_time.time())
        if not begin_time:
            begin_time = end_time - 86400

        save_dir = save_dir or settings.chat_archive_save_dir
        Path(save_dir).mkdir(parents=True, exist_ok=True)

        messages: List[Dict[str, Any]] = []

        try:
            lib, sdk = self.init_sdk()
            seq = 0
            total = 0
            while True:
                from ctypes import (
                    Structure,
                    c_char_p,
                    c_int,
                    create_string_buffer,
                    cast,
                )

                chat_buf = create_string_buffer(1024 * 1024 * 2)
                ret = lib.GetChatData(
                    sdk,
                    seq,
                    min(limit, 1000),
                    b"",
                    b"",
                    30,
                    cast(chat_buf, c_char_p),
                )
                if ret != 0:
                    logger.error("GetChatData 失败, ret=%d", ret)
                    break

                chat_json = json.loads(chat_buf.raw.decode("utf-8").split("\x00")[0])
                if chat_json.get("errcode", 0) != 0:
                    logger.error("GetChatData API 错误: %s", chat_json)
                    break

                chat_list = chat_json.get("chatdata", [])
                if not chat_list:
                    break

                for chat in chat_list:
                    encrypt_key = self.rsa_decrypt(chat["encrypt_random_key"])
                    if not encrypt_key:
                        logger.warning("RSA 解密失败, msgid=%s", chat.get("msgid"))
                        continue

                    decrypt_buf = create_string_buffer(1024 * 512)
                    ret = lib.DecryptData(
                        encrypt_key.encode(),
                        chat["encrypt_chat_msg"].encode(),
                        cast(decrypt_buf, c_char_p),
                    )
                    if ret != 0:
                        logger.warning(
                            "DecryptData 失败, ret=%d, msgid=%s", ret, chat.get("msgid")
                        )
                        continue

                    msg = json.loads(decrypt_buf.raw.decode("utf-8").split("\x00")[0])
                    messages.append(msg)

                if len(chat_list) < min(limit, 1000):
                    break
                seq = chat_list[-1].get("seq", seq)
                total += len(chat_list)

        except (FileNotFoundError, RuntimeError) as e:
            logger.warning("SDK 模式不可用，切换到 REST API 模式: %s", e)
            return self._archive_via_rest(begin_time, end_time, save_dir, messages)

        if not messages:
            return {"saved_count": 0, "save_path": None, "messages": []}

        filename = f"archive_{begin_time}_{end_time}.json"
        save_path = os.path.join(save_dir, filename)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)

        return {
            "saved_count": len(messages),
            "save_path": save_path,
            "messages": messages,
        }

    def _archive_via_rest(
        self, begin_time: int, end_time: int, save_dir: str, messages: list
    ) -> dict:
        """REST API 方式拉取"""
        page_count = self.get_page_count(begin_time, end_time)
        logger.info("page_count=%d", page_count)

        for page in range(page_count):
            data = self.get_page_content(begin_time, end_time, page)
            chat_list = data.get("chat_data", [])
            for item in chat_list:
                messages.append(item)

        if not messages:
            return {"saved_count": 0, "save_path": None, "messages": []}

        filename = f"archive_{begin_time}_{end_time}.json"
        save_path = os.path.join(save_dir, filename)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)

        return {
            "saved_count": len(messages),
            "save_path": save_path,
            "messages": messages,
        }


chat_archive = ChatArchiveClient()
