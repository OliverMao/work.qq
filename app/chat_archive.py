"""
企业微信会话内容存档 — C SDK 版
使用企业微信提供的 C SDK 动态库进行会话内容拉取和解密
"""

import base64
import ctypes
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class Slice(ctypes.Structure):
    _fields_ = [
        ("content", ctypes.c_char_p),
        ("len", ctypes.c_uint),
    ]


class WeWorkFinanceSDK:
    """企业微信会话存档 SDK 封装"""

    def __init__(self, sdk_path: str, rsa_key_path: str):
        if not os.path.exists(sdk_path):
            raise FileNotFoundError(f"SDK 库不存在: {sdk_path}")

        self.lib = ctypes.CDLL(sdk_path)

        self.lib.NewSdk.restype = ctypes.c_void_p
        self.lib.DestroySdk.argtypes = [ctypes.c_void_p]
        self.lib.DestroySdk.restype = None

        self.lib.Init.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.Init.restype = ctypes.c_int

        self.lib.GetChatData.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulonglong,
            ctypes.c_uint,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.POINTER(Slice),
        ]
        self.lib.GetChatData.restype = ctypes.c_int

        self.lib.DecryptData.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.POINTER(Slice),
        ]
        self.lib.DecryptData.restype = ctypes.c_int

        self.lib.FreeSlice.argtypes = [ctypes.c_void_p]
        self.lib.FreeSlice.restype = None

        self.sdk = self.lib.NewSdk()

        rsa_key = self._load_rsa_key(rsa_key_path)
        ret = self.lib.Init(
            self.sdk,
            settings.corp_id.encode(),
            settings.chat_archive_secret.encode(),
        )
        if ret != 0:
            raise RuntimeError(f"SDK Init 失败, ret={ret}")

    def _load_rsa_key(self, path: str) -> str:
        with open(path, "r") as f:
            return f.read()

    def rsa_decrypt(self, encrypted: str, rsa_key: str) -> Optional[str]:
        """Python 实现 RSA 解密"""
        from Crypto.Cipher import PKCS1_v1_5
        from Crypto.PublicKey import RSA

        encrypted_data = base64.b64decode(encrypted)
        key = RSA.import_key(rsa_key)
        cipher = PKCS1_v1_5.new(key)
        try:
            return cipher.decrypt(encrypted_data, None).decode("utf-8")
        except Exception as e:
            logger.error(f"RSA 解密失败: {e}")
            return None

    def get_chat_data(self, seq: int = 0, limit: int = 1000) -> List[Dict]:
        """拉取会话数据"""
        chat_slice = Slice()
        ret = self.lib.GetChatData(
            self.sdk,
            seq,
            limit,
            b"",
            b"",
            30,
            ctypes.byref(chat_slice),
        )
        if ret != 0:
            raise RuntimeError(f"GetChatData 失败, ret={ret}")

        data = chat_slice.content[: chat_slice.len].decode("utf-8")
        self.lib.FreeSlice(ctypes.byref(chat_slice))

        result = json.loads(data)
        if result.get("errcode", 0) != 0:
            raise RuntimeError(f"GetChatData API 错误: {result}")

        return result.get("chatdata", [])

    def decrypt_message(
        self, encrypt_key: str, encrypt_msg: str, rsa_key: str
    ) -> Optional[Dict]:
        """解密���条消息"""
        aes_key = self.rsa_decrypt(encrypt_key, rsa_key)
        if not aes_key:
            return None

        msg_slice = Slice()
        ret = self.lib.DecryptData(
            self.sdk,
            aes_key.encode(),
            encrypt_msg.encode(),
            ctypes.byref(msg_slice),
        )
        if ret != 0:
            logger.warning(f"DecryptData 失败, ret={ret}")
            return None

        data = msg_slice.content[: msg_slice.len].decode("utf-8")
        self.lib.FreeSlice(ctypes.byref(msg_slice))

        return json.loads(data)

    def __del__(self):
        if hasattr(self, "sdk") and self.sdk:
            self.lib.DestroySdk(self.sdk)


def archive_to_file(
    starttime: Optional[int] = None,
    endtime: Optional[int] = None,
    save_dir: Optional[str] = None,
) -> dict:
    """
    使用 C SDK 拉取会话内容并保存为 JSON 文件

    Returns:
        {
            "errcode": 0,
            "errmsg": "ok",
            "saved_count": 123,
            "save_path": "/path/to/archive_xxx.json",
            "messages": [{...}, ...]
        }
    """
    now_ts = int(time.time())
    if not endtime:
        endtime = now_ts
    if not starttime:
        starttime = now_ts - 86400

    save_dir = save_dir or settings.chat_archive_save_dir
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    rsa_key_path = settings.rsa_private_key_path or str(
        Path(__file__).parent.parent / "keys" / "private.pem"
    )
    sdk_lib_path = "/www/workqq/work.qq/sdk/C_sdk/libWeWorkFinanceSdk_C.so"

    try:
        sdk = WeWorkFinanceSDK(sdk_lib_path, rsa_key_path)
    except Exception as e:
        return {
            "errcode": -1,
            "errmsg": f"SDK 初始化失败: {e}",
            "saved_count": 0,
        }

    with open(rsa_key_path, "r") as f:
        rsa_key = f.read()

    all_messages: List[Dict[str, Any]] = []
    seq = 0

    while True:
        try:
            chat_list = sdk.get_chat_data(seq=seq, limit=1000)
        except Exception as e:
            logger.error(f"GetChatData 失败: {e}")
            break

        if not chat_list:
            break

        for chat in chat_list:
            try:
                msg = sdk.decrypt_message(
                    chat.get("encrypt_random_key", ""),
                    chat.get("encrypt_chat_msg", ""),
                    rsa_key,
                )
                if msg:
                    all_messages.append(msg)
            except Exception as e:
                logger.warning(f"解密消息失败: {e}")
                continue

        if len(chat_list) < 1000:
            break
        seq = chat_list[-1].get("seq", seq)

    if not all_messages:
        return {
            "errcode": 0,
            "errmsg": "没有会话记录",
            "saved_count": 0,
            "save_path": None,
            "messages": [],
        }

    ts_str = datetime.fromtimestamp(starttime).strftime("%Y%m%d_%H%M%S")
    ts_end = datetime.fromtimestamp(endtime).strftime("%Y%m%d_%H%M%S")
    filename = f"archive_{ts_str}_{ts_end}.json"
    save_path = os.path.join(save_dir, filename)

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(all_messages, f, ensure_ascii=False, indent=2)

    logger.info("已保存 %d 条会话记录 => %s", len(all_messages), save_path)
    return {
        "errcode": 0,
        "errmsg": "ok",
        "saved_count": len(all_messages),
        "save_path": save_path,
        "messages": all_messages,
    }
