"""
企业微信会话存档服务
"""

import argparse
import base64
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Set

import requests

try:
    from app.config import settings
    from app.services.wecom_api import wecom_api_client
except ModuleNotFoundError:
    # 兼容直接运行本文件: python app/services/chat_archive.py
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from app.config import settings
    from app.services.wecom_api import wecom_api_client

logger = logging.getLogger(__name__)


class ChatArchiveService:
    """
    企业微信会话存档服务 - 封装 SDK 拉取和解密逻辑
    """

    def __init__(self):
        self._chat_info_cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _sdktools_path() -> str:
        env_path = os.getenv("WECOM_SDKTOOLS_PATH", "").strip()
        if env_path:
            return env_path
        return "/www/workqq/work.qq/sdk/C_sdk/sdktools"

    def _resolve_sdktools(self) -> str:
        sdktools_path = self._sdktools_path()
        if not os.path.exists(sdktools_path):
            raise FileNotFoundError(
                f"找不到 sdktools 可执行文件: {sdktools_path}\n"
                f"请编译 C SDK 并配置 WECOM_SDKTOOLS_PATH 到 .env"
            )
        if not os.access(sdktools_path, os.X_OK):
            raise PermissionError(f"sdktools 不可执行: {sdktools_path}")
        return sdktools_path

    @staticmethod
    def _extract_json_fragment(text: str, marker: str) -> Optional[Dict[str, Any]]:
        idx = text.find(marker)
        if idx < 0:
            return None
        payload = text[idx + len(marker):].strip()
        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _extract_decrypt_payload(text: str) -> Optional[Dict[str, Any]]:
        # sdktools 输出格式: chatdata :{...} ret :0
        match = re.search(r"chatdata\s*:(\{.*\})\s*ret\s*:\s*(-?\d+)", text)
        if not match:
            return None
        ret = int(match.group(2))
        if ret != 0:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    def _ensure_sdktools_config(self, sdk_dir: str) -> None:
        config_path = os.path.join(sdk_dir, "config.txt")
        corp_id = settings.corp_id.strip()
        corp_secret = settings.corp_secret.strip()
        if not corp_id or not corp_secret:
            raise RuntimeError("WECOM_CORP_ID 或 WECOM_CORP_SECRET 未配置")
        expected = f"{corp_id}\n{corp_secret}\n"
        current = ""
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                current = f.read()
        if current != expected:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(expected)

    def _run_sdktools(self, args: List[str]) -> str:
        sdktools_path = self._resolve_sdktools()
        sdk_dir = str(Path(sdktools_path).parent)
        self._ensure_sdktools_config(sdk_dir)

        result = subprocess.run(
            [sdktools_path, *args],
            cwd=sdk_dir,
            capture_output=True,
            text=True,
            timeout=45,
        )
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        if result.returncode != 0:
            raise RuntimeError(
                f"sdktools 执行失败, code={result.returncode}, output={output.strip()}"
            )
        return output

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

    def _pull_decrypted_records(
        self,
        limit: int = 1000,
        known_msgids: Optional[Set[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """通过 sdktools 拉取并解密会话，返回原始聊天元数据 + 解密消息。"""
        records: List[Dict[str, Any]] = []
        skip_duplicate_count = 0
        known_msgid_set = set(known_msgids or set())

        try:
            logger.info("会话存档使用 sdktools 模式")
            seq = 0
            while True:
                logger.info("开始拉取会话: seq=%s, limit=%s", seq, min(limit, 1000))
                fetch_started = time.time()
                output = self._run_sdktools(
                    ["1", str(seq), str(min(limit, 1000)), "", "", "30"]
                )
                logger.info(
                    "sdktools GetChatData返回: elapsed=%.3fs",
                    time.time() - fetch_started,
                )

                chat_json = self._extract_json_fragment(output, "data:")
                if chat_json is None:
                    logger.error("无法解析 sdktools GetChatData 输出: %s", output)
                    break
                if chat_json.get("errcode", 0) != 0:
                    logger.error("GetChatData API 错误: %s", chat_json)
                    break

                chat_list = chat_json.get("chatdata", [])
                logger.info("本批会话条数: %s", len(chat_list))
                if not chat_list:
                    logger.info("会话拉取结束: chatdata为空")
                    break

                for chat in chat_list:
                    msgid = str(chat.get("msgid") or "").strip()
                    if msgid and msgid in known_msgid_set:
                        skip_duplicate_count += 1
                        continue

                    encrypt_key = self.rsa_decrypt(chat.get("encrypt_random_key", ""))
                    if not encrypt_key:
                        logger.warning("RSA 解密失败, msgid=%s", chat.get("msgid"))
                        continue

                    dec_payload = self._extract_decrypt_payload(
                        self._run_sdktools(
                            [
                                "3",
                                encrypt_key,
                                chat.get("encrypt_chat_msg", ""),
                            ]
                        )
                    )
                    if dec_payload is None:
                        logger.warning("DecryptData 失败, msgid=%s", chat.get("msgid"))
                        continue

                    if msgid and not str(dec_payload.get("msgid") or "").strip():
                        dec_payload["msgid"] = msgid

                    if msgid:
                        known_msgid_set.add(msgid)

                    records.append(
                        {
                            "chat": chat,
                            "message": dec_payload,
                        }
                    )

                if len(chat_list) < min(limit, 1000):
                    logger.info("会话拉取结束: 返回条数小于limit")
                    break
                seq = chat_list[-1].get("seq", seq)
                logger.info("更新seq为: %s", seq)

        except Exception as e:
            raise RuntimeError(f"SDK 拉取失败: {e}") from e

        logger.info(
            "会话拉取结束: decrypt_count=%s, skip_duplicate_count=%s",
            len(records),
            skip_duplicate_count,
        )
        return records, skip_duplicate_count


    @staticmethod
    def _safe_roomid(roomid: str) -> str:
        safe = "".join(
            ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in roomid
        )
        safe = safe.strip("_")
        if not safe:
            safe = "unknown_group"
        return safe[:80]

    @staticmethod
    def _safe_chat_name(chat_name: Optional[str]) -> str:
        raw = (chat_name or "unknown_chat").strip()
        # Windows 文件名非法字符: \\ / : * ? " < > |
        safe = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in raw)
        safe = " ".join(safe.split())
        if not safe:
            safe = "unknown_chat"
        return safe[:80]

    @staticmethod
    def _load_messages_from_file(file_path: Path) -> List[Dict[str, Any]]:
        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    @staticmethod
    def _extract_msgid(message: Dict[str, Any]) -> Optional[str]:
        if not isinstance(message, dict):
            return None
        msgid = message.get("msgid")
        if msgid is None:
            msgid = message.get("msg_id")
        if msgid is None:
            return None
        value = str(msgid).strip()
        return value or None

    def _collect_existing_msgids(self, save_dir: Path) -> Set[str]:
        if not save_dir.exists():
            return set()

        file_paths = [path for path in save_dir.glob("*.json") if path.is_file()]
        msgids: Set[str] = set()
        for file_path in file_paths:
            try:
                messages = self._load_messages_from_file(file_path)
            except Exception as e:
                logger.warning("读取存档文件失败: %s, error=%s", file_path, e)
                continue

            for message in messages:
                msgid = self._extract_msgid(message)
                if msgid:
                    msgids.add(msgid)

        logger.info(
            "读取本地msgid索引完成: files=%s, msgids=%s",
            len(file_paths),
            len(msgids),
        )
        return msgids

    def get_group_archived_messages(self, roomid: str) -> Dict[str, Any]:
        """读取指定群聊(roomid)的全部本地存档消息。"""
        roomid = str(roomid or "").strip()
        if not roomid:
            raise ValueError("roomid 不能为空")

        save_dir = Path(settings.chat_archive_save_dir)
        if not save_dir.exists():
            raise FileNotFoundError(f"存档目录不存在: {save_dir}")

        safe_roomid = self._safe_roomid(roomid)
        candidate_files: List[Path] = []

        # 当前实现默认使用 roomid.json 命名
        default_file = save_dir / f"{safe_roomid}.json"
        if default_file.exists():
            candidate_files.append(default_file)

        # 兼容历史命名: unknown_chat+<roomid>.json
        legacy_patterns = [
            f"*+{roomid}.json",
            f"*+{safe_roomid}.json",
        ]
        for pattern in legacy_patterns:
            for matched in sorted(save_dir.glob(pattern)):
                if matched.is_file() and matched not in candidate_files:
                    candidate_files.append(matched)

        if not candidate_files:
            raise FileNotFoundError(f"未找到群聊存档文件: roomid={roomid}")

        all_messages: List[Dict[str, Any]] = []
        for file_path in candidate_files:
            try:
                all_messages.extend(self._load_messages_from_file(file_path))
            except Exception as e:
                logger.warning("读取存档文件失败: %s, error=%s", file_path, e)

        all_messages.sort(key=lambda item: int(item.get("msgtime", 0) or 0))
        return {
            "roomid": roomid,
            "count": len(all_messages),
            "files": [str(path) for path in candidate_files],
            "messages": all_messages,
        }

    @staticmethod
    def _extract_roomid_from_filename(file_path: Path) -> str:
        stem = file_path.stem.strip()
        if "+" in stem:
            # 兼容历史文件名: chat_name+roomid.json
            tail = stem.rsplit("+", 1)[-1].strip()
            if tail:
                return tail
        return stem

    @staticmethod
    def _extract_roomid_from_messages(messages: List[Dict[str, Any]]) -> Optional[str]:
        for item in messages:
            if not isinstance(item, dict):
                continue
            roomid = str(item.get("roomid", "")).strip()
            if roomid:
                return roomid
        return None

    @staticmethod
    def _extract_latest_msgtime(messages: List[Dict[str, Any]]) -> Optional[int]:
        latest = 0
        for item in messages:
            if not isinstance(item, dict):
                continue
            try:
                msgtime = int(item.get("msgtime", 0) or 0)
            except Exception:
                msgtime = 0
            latest = max(latest, msgtime)
        return latest or None

    @staticmethod
    def _normalize_module_filename(filename: str) -> str:
        value = Path(str(filename or "").strip()).name
        if not value:
            raise ValueError("filename 不能为空")
        if not value.lower().endswith(".json"):
            raise ValueError("filename 必须是 .json 文件")
        return value

    def get_group_archive_module(self, filename: str) -> Dict[str, Any]:
        """按 JSON 文件名读取单个群聊存档模块详情。"""
        save_dir = Path(settings.chat_archive_save_dir)
        if not save_dir.exists():
            raise FileNotFoundError(f"存档目录不存在: {save_dir}")

        normalized_filename = self._normalize_module_filename(filename)
        file_path = save_dir / normalized_filename
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"未找到存档模块文件: {normalized_filename}")

        messages = self._load_messages_from_file(file_path)
        messages.sort(key=lambda item: int(item.get("msgtime", 0) or 0))

        roomid = (
            self._extract_roomid_from_messages(messages)
            or self._extract_roomid_from_filename(file_path)
        )
        stat = file_path.stat()

        return {
            "filename": normalized_filename,
            "roomid": roomid,
            "save_path": str(file_path),
            "count": len(messages),
            "latest_msgtime": self._extract_latest_msgtime(messages),
            "file_mtime": int(stat.st_mtime),
            "messages": messages,
        }

    def list_group_archive_modules(self, keyword: Optional[str] = None) -> Dict[str, Any]:
        """按 JSON 文件列出群聊存档模块，供前端管理界面展示。"""
        save_dir = Path(settings.chat_archive_save_dir)
        if not save_dir.exists():
            return {
                "count": 0,
                "items": [],
            }

        keyword_value = str(keyword or "").strip().lower()
        modules: List[Dict[str, Any]] = []

        file_paths = sorted(
            [path for path in save_dir.glob("*.json") if path.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for file_path in file_paths:
            parse_error: Optional[str] = None
            messages: List[Dict[str, Any]] = []

            try:
                messages = self._load_messages_from_file(file_path)
            except Exception as e:
                parse_error = str(e)
                logger.warning("读取存档文件失败: %s, error=%s", file_path, e)

            roomid = (
                self._extract_roomid_from_messages(messages)
                or self._extract_roomid_from_filename(file_path)
            )

            filename = file_path.name
            if keyword_value:
                matched = (
                    keyword_value in filename.lower()
                    or keyword_value in roomid.lower()
                )
                if not matched:
                    continue

            stat = file_path.stat()
            modules.append(
                {
                    "filename": filename,
                    "roomid": roomid,
                    "save_path": str(file_path),
                    "message_count": len(messages),
                    "latest_msgtime": self._extract_latest_msgtime(messages),
                    "file_mtime": int(stat.st_mtime),
                    "parse_error": parse_error,
                }
            )

        return {
            "count": len(modules),
            "items": modules,
        }



    def archive_messages(
        self,
        limit: int = 1000,
    ) -> dict:
        """
        拉取并保存会话内容到本地文件（按群聊拆分）

        Args:
            begin_time: 开始时间戳 (秒)
            end_time:   结束时间戳 (秒)
            limit:      拉取条数 (最大1000)

                Returns:
                        {
                            "saved_count": N,
                            "save_path": "...",  # 仅有一个群聊文件时返回
                            "save_dir": "...",
                            "files": [...],
                            "messages": [...]
                        }
        """


        save_dir = settings.chat_archive_save_dir
        save_dir_path = Path(save_dir)
        save_dir_path.mkdir(parents=True, exist_ok=True)

        existing_msgids = self._collect_existing_msgids(save_dir_path)

        records, skip_duplicate_count = self._pull_decrypted_records(
            limit=limit,
            known_msgids=existing_msgids,
        )

        group_messages: Dict[str, List[Dict[str, Any]]] = {}

        for record in records:
            chat = record.get("chat", {})
            message = record.get("message", {})

            roomid = str(message.get("roomid") or "").strip()
            if not roomid:
                continue

            msgid = str(chat.get("msgid") or self._extract_msgid(message) or "").strip()
            if msgid and not self._extract_msgid(message):
                message = dict(message)
                message["msgid"] = msgid
        
            group_messages.setdefault(roomid, []).append(message)

        if not group_messages:
            logger.info("会话存档完成: 没有可保存的消息")
            return {
                "saved_count": 0,
                "save_path": None,
                "save_dir": save_dir,
                "skip_duplicate_count": skip_duplicate_count,
                "files": [],
                "messages": [],
            }

        saved_files: List[Dict[str, Any]] = []
        all_new_messages: List[Dict[str, Any]] = []
        saved_count = 0
        merge_duplicate_count = 0

        for roomid, items in group_messages.items():
            items.sort(key=lambda x: int(x.get("msgtime", 0) or 0))

            safe_roomid = self._safe_roomid(roomid)
            filename = f"{safe_roomid}.json"
            file_path = os.path.join(save_dir, filename)
            file_path_obj = Path(file_path)

            existing_messages: List[Dict[str, Any]] = []
            existing_msgids_in_room: Set[str] = set()
            if file_path_obj.exists():
                try:
                    existing_messages = self._load_messages_from_file(file_path_obj)
                except Exception as e:
                    logger.warning("读取历史群聊存档失败: %s, error=%s", file_path_obj, e)
                    existing_messages = []

                for message in existing_messages:
                    existing_msgid = self._extract_msgid(message)
                    if existing_msgid:
                        existing_msgids_in_room.add(existing_msgid)

            new_messages: List[Dict[str, Any]] = []
            for message in items:
                msgid = self._extract_msgid(message)
                if msgid and msgid in existing_msgids_in_room:
                    merge_duplicate_count += 1
                    continue

                if msgid:
                    existing_msgids_in_room.add(msgid)
                new_messages.append(message)

            if not new_messages:
                saved_files.append(
                    {
                        "roomid": roomid,
                        "count": 0,
                        "total_count": len(existing_messages),
                        "save_path": file_path,
                    }
                )
                continue

            merged_messages = existing_messages + new_messages
            merged_messages.sort(key=lambda x: int(x.get("msgtime", 0) or 0))

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(merged_messages, f, ensure_ascii=False, indent=2)

            saved_count += len(new_messages)
            all_new_messages.extend(new_messages)
            saved_files.append(
                {
                    "roomid": roomid,
                    "count": len(new_messages),
                    "total_count": len(merged_messages),
                    "save_path": file_path,
                }
            )

        saved_files.sort(key=lambda x: x["count"], reverse=True)
        non_empty_files = [item for item in saved_files if int(item.get("count", 0)) > 0]
        primary_path = non_empty_files[0]["save_path"] if len(non_empty_files) == 1 else None

        return {
            "saved_count": saved_count,
            "skip_duplicate_count": skip_duplicate_count + merge_duplicate_count,
            "save_path": primary_path,
            "save_dir": save_dir,
            "files": saved_files,
            "messages": all_new_messages,
        }


chat_archive_service = ChatArchiveService()


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="测试企业微信会话存档 archive_messages 功能"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="拉取条数上限，最大1000，默认1000",
    )
    return parser


def _run_main() -> None:
    parser = _build_cli_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    service = ChatArchiveService()
    limit = max(1, min(int(args.limit), 1000))

    print("=== 测试: archive_messages ===")
    save_result = service.archive_messages(limit=limit)
    print(
        json.dumps(
            {
                "saved_count": save_result.get("saved_count", 0),
                "save_dir": save_result.get("save_dir"),
                "files": save_result.get("files", []),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    _run_main()
