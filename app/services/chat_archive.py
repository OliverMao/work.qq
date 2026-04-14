"""
企业微信会话存档服务
"""

import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from ctypes import (
    Structure,
    c_int,
    c_void_p,
    c_char_p,
    c_ulonglong,
    c_ulong,
    byref,
    string_at,
)

from app.config import settings

logger = logging.getLogger(__name__)


class Slice(Structure):
    _fields_ = [("buf", c_void_p), ("len", c_int)]


class ChatArchiveService:
    """
    企业微信会话存档服务 - 封装 SDK 拉取和解密逻辑
    """

    def __init__(self):
        self._lib = None
        self._sdk = None

    def _init_sdk(self):
        """初始化 SDK"""
        sdk_lib_path = settings.sdk_lib_path
        if not sdk_lib_path or not os.path.exists(sdk_lib_path):
            raise FileNotFoundError(
                f"找不到 SDK 库文件: {sdk_lib_path}\n"
                f"请下载: https://wwcdn.weixin.qq.com/node/wework/images/sdk_20240606.tgz\n"
                f"并配置 WECOM_SDK_LIB_PATH 到 .env"
            )

        import ctypes

        lib = ctypes.CDLL(sdk_lib_path)

        lib.NewSdk.restype = c_void_p
        lib.Init.argtypes = [c_void_p, c_char_p, c_char_p]
        lib.Init.restype = c_int
        lib.GetChatData.argtypes = [
            c_void_p,
            c_ulonglong,
            c_ulong,
            c_char_p,
            c_char_p,
            c_int,
            ctypes.POINTER(Slice),
        ]
        lib.GetChatData.restype = c_int
        lib.DecryptData.argtypes = [
            c_char_p,
            c_char_p,
            ctypes.POINTER(Slice),
        ]
        lib.DecryptData.restype = c_int
        lib.DestroySdk.argtypes = [c_void_p]
        lib.DestroySdk.restype = None

        sdk = lib.NewSdk()
        ret = lib.Init(
            sdk, settings.corp_id.encode(), settings.chat_archive_secret.encode()
        )
        if ret != 0:
            raise RuntimeError(f"SDK Init 失败, ret={ret}")

        self._lib = lib
        self._sdk = sdk
        return lib, sdk

    def _get_rsa_private_key(self) -> str:
        key_path = settings.rsa_private_key_path
        if not key_path or not os.path.exists(key_path):
            raise FileNotFoundError(
                f"找不到 RSA 私钥: {key_path}\n"
                f"请在 .env 中配置 WECOM_RSA_PRIVATE_KEY_PATH"
            )
        with open(key_path, "rb") as f:
            return f.read()

    def rsa_decrypt(self, encrypt_random_key: str) -> Optional[str]:
        """使用 RSA 私钥解密 encrypt_random_key"""
        from Crypto.Cipher import PKCS1_v1_5
        from Crypto.PublicKey import RSA

        rsa_key = self._get_rsa_private_key()
        encrypted = base64.b64decode(encrypt_random_key)
        key = RSA.import_key(rsa_key)
        cipher = PKCS1_v1_5.new(key)
        try:
            return cipher.decrypt(encrypted, None).decode("utf-8")
        except Exception as e:
            logger.error("RSA 解密失败: %s", e)
            return None

    def _pull_decrypted_records(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """通过 SDK 拉取并解密会话，返回原始聊天元数据 + 解密消息。"""
        records: List[Dict[str, Any]] = []

        try:
            logger.info("会话存档使用 SDK 模式")
            lib, sdk = self._init_sdk()
            seq = 0
            while True:
                logger.info("开始拉取会话: seq=%s, limit=%s", seq, min(limit, 1000))
                fetch_started = time.time()
                result_slice = Slice()
                ret = lib.GetChatData(
                    sdk,
                    seq,
                    min(limit, 1000),
                    c_char_p(None),
                    c_char_p(None),
                    c_int(30),
                    byref(result_slice),
                )
                logger.info(
                    "GetChatData返回: ret=%s, elapsed=%.3fs",
                    ret,
                    time.time() - fetch_started,
                )
                if ret != 0:
                    logger.error("GetChatData 失败, ret=%d", ret)
                    break

                if not result_slice.buf or result_slice.len <= 0:
                    logger.error("GetChatData 返回成功但 Slice 为空")
                    break

                raw_text = string_at(result_slice.buf, result_slice.len).decode("utf-8")
                chat_json = json.loads(raw_text)
                if chat_json.get("errcode", 0) != 0:
                    logger.error("GetChatData API 错误: %s", chat_json)
                    break

                chat_list = chat_json.get("chatdata", [])
                logger.info("本批会话条数: %s", len(chat_list))
                if not chat_list:
                    logger.info("会话拉取结束: chatdata为空")
                    break

                for chat in chat_list:
                    encrypt_key = self.rsa_decrypt(chat.get("encrypt_random_key", ""))
                    if not encrypt_key:
                        logger.warning("RSA 解密失败, msgid=%s", chat.get("msgid"))
                        continue

                    decrypt_slice = Slice()
                    ret = lib.DecryptData(
                        c_char_p(encrypt_key.encode()),
                        c_char_p(chat.get("encrypt_chat_msg", "").encode()),
                        byref(decrypt_slice),
                    )
                    if ret != 0:
                        logger.warning(
                            "DecryptData 失败, ret=%d, msgid=%s", ret, chat.get("msgid")
                        )
                        continue

                    if not decrypt_slice.buf or decrypt_slice.len <= 0:
                        logger.warning(
                            "DecryptData 返回成功但 Slice 为空, msgid=%s",
                            chat.get("msgid"),
                        )
                        continue

                    dec_text = string_at(decrypt_slice.buf, decrypt_slice.len).decode(
                        "utf-8"
                    )
                    records.append(
                        {
                            "chat": chat,
                            "message": json.loads(dec_text),
                        }
                    )

                if len(chat_list) < min(limit, 1000):
                    logger.info("会话拉取结束: 返回条数小于limit")
                    break
                seq = chat_list[-1].get("seq", seq)
                logger.info("更新seq为: %s", seq)

        except Exception as e:
            raise RuntimeError(f"SDK 拉取失败: {e}") from e
        finally:
            try:
                if self._lib is not None and self._sdk:
                    self._lib.DestroySdk(self._sdk)
                    self._lib = None
                    self._sdk = None
            except Exception:
                pass

        return records

    @staticmethod
    def _extract_group_id(
        chat: Dict[str, Any], message: Dict[str, Any]
    ) -> Optional[str]:
        for key in ("roomid", "chatid", "conversation_id", "external_chatid"):
            value = message.get(key) if isinstance(message, dict) else None
            if value:
                return str(value)
            value = chat.get(key) if isinstance(chat, dict) else None
            if value:
                return str(value)
        return None

    @staticmethod
    def _safe_group_filename(group_id: str) -> str:
        safe = "".join(
            ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in group_id
        )
        safe = safe.strip("_")
        if not safe:
            safe = "unknown_group"
        return safe[:80]

    def archive_messages(
        self,
        begin_time: int = 0,
        end_time: int = 0,
        limit: int = 1000,
    ) -> dict:
        """
        拉取并保存会话内容到本地文件

        Args:
            begin_time: 开始时间戳 (秒)
            end_time:   结束时间戳 (秒)
            limit:      拉取条数 (最大1000)

        Returns:
            {"saved_count": N, "save_path": "...", "messages": [...]}
        """
        import time as _time

        if not end_time:
            end_time = int(_time.time())
        if not begin_time:
            begin_time = end_time - 86400

        save_dir = settings.chat_archive_save_dir
        Path(save_dir).mkdir(parents=True, exist_ok=True)

        records = self._pull_decrypted_records(limit=limit)
        messages = [r.get("message", {}) for r in records]

        if not messages:
            logger.info("会话存档完成: 没有可保存的消息")
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

    def archive_group_messages(
        self,
        days: int = 5,
        limit: int = 1000,
    ) -> dict:
        """拉取最近 N 天消息，并按群聊维度分文件保存。"""
        now_ts = int(time.time())
        begin_time = now_ts - max(days, 1) * 86400
        end_time = now_ts

        records = self._pull_decrypted_records(limit=limit)
        group_messages: Dict[str, List[Dict[str, Any]]] = {}

        for record in records:
            chat = record.get("chat", {})
            message = record.get("message", {})
            msg_time = int(chat.get("msgtime", message.get("msgtime", 0)) or 0)
            if msg_time and (msg_time < begin_time or msg_time > end_time):
                continue

            group_id = self._extract_group_id(chat, message)
            if not group_id:
                continue

            group_messages.setdefault(group_id, []).append(
                {
                    "seq": chat.get("seq"),
                    "msgid": chat.get("msgid"),
                    "msgtime": msg_time,
                    "from": chat.get("from"),
                    "tolist": chat.get("tolist"),
                    "roomid": chat.get("roomid", message.get("roomid")),
                    "chatid": chat.get("chatid", message.get("chatid")),
                    "message": message,
                }
            )

        if not group_messages:
            return {
                "errcode": 0,
                "errmsg": f"最近{days}天没有群聊记录",
                "group_count": 0,
                "saved_count": 0,
                "save_dir": None,
                "files": [],
            }

        base_save_dir = settings.chat_archive_save_dir
        archive_dir = os.path.join(
            base_save_dir, f"group_archive_{begin_time}_{end_time}"
        )
        Path(archive_dir).mkdir(parents=True, exist_ok=True)

        saved_files: List[Dict[str, Any]] = []
        total_messages = 0
        for group_id, items in group_messages.items():
            items.sort(key=lambda x: x.get("msgtime") or 0)
            filename = f"group_{self._safe_group_filename(group_id)}.json"
            file_path = os.path.join(archive_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)

            total_messages += len(items)
            saved_files.append(
                {
                    "group_id": group_id,
                    "count": len(items),
                    "save_path": file_path,
                }
            )

        saved_files.sort(key=lambda x: x["count"], reverse=True)
        return {
            "errcode": 0,
            "errmsg": "ok",
            "days": days,
            "group_count": len(saved_files),
            "saved_count": total_messages,
            "save_dir": archive_dir,
            "files": saved_files,
        }


chat_archive_service = ChatArchiveService()
