"""
学习报告生成服务
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.chat_archive_binding import chat_archive_binding_service

logger = logging.getLogger(__name__)


class ReportGenerationService:
    """学习报告生成服务"""

    def _load_auto_reply_config(self) -> dict:
        """加载自动发信配置，获取使用的模型"""
        prompt_dir = Path(settings.teacher_agent_prompt_dir)
        config_file = prompt_dir / "auto_reply_config.txt"

        config = {
            "model": "deepseek/deepseek-v4-flash",
            "target_chatid": "fangya001",
        }

        if config_file.exists():
            try:
                content = config_file.read_text(encoding="utf-8")
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip()
            except Exception as e:
                logger.warning("读取自动发信配置失败: %s", e)

        return config

    def _load_report_prompt(self) -> str:
        """加载报告生成 Prompt"""
        prompt_dir = Path(settings.teacher_agent_prompt_dir)
        template_file = prompt_dir / "report_template.txt"

        if template_file.exists():
            return template_file.read_text(encoding="utf-8").strip()

        return "请根据下面的对话记录生成一份学习报告，包括概述、关键话题、优秀回答和建议。"

    def _load_chat_messages(self, roomid: str) -> List[Dict[str, Any]]:
        """加载指定群聊的消息"""
        archive_save_dir = Path(settings.chat_archive_save_dir)
        json_files = list(archive_save_dir.glob("*.json"))

        for f in json_files:
            try:
                with open(f, encoding="utf-8") as fp:
                    messages = json.load(fp)
                if messages and any(m.get("roomid") == roomid for m in messages):
                    return messages
            except Exception as e:
                logger.warning("读取文件失败 %s: %s", f, e)

        return []

    def generate_report(self, roomid: str, chat_name: Optional[str] = None) -> Dict[str, Any]:
        """生成学习报告"""
        messages = self._load_chat_messages(roomid)

        if not messages:
            return {
                "ok": False,
                "error": f"未找到群聊 {roomid} 的消息记录",
            }

        if not chat_name:
            room_names = chat_archive_binding_service.get_room_name_map([roomid])
            chat_name = room_names.get(roomid, roomid)

        text_messages = []
        for msg in messages:
            msgtype = msg.get("msgtype", "")
            if msgtype == "text":
                text_obj = msg.get("text", {})
                content = text_obj.get("content", "") if isinstance(text_obj, dict) else ""
                if content:
                    from_user = msg.get("from", "unknown")
                    text_messages.append(f"{from_user}: {content}")

        if not text_messages:
            return {
                "ok": False,
                "error": "群聊中没有文本消息",
            }

        conversation_text = "\n\n".join(text_messages[:100])

        config = self._load_auto_reply_config()
        model = config.get("model", "deepseek/deepseek-v4-flash")

        prompt_template = self._load_report_prompt()
        chat_name = chat_name or roomid

        user_prompt = f"""{prompt_template}

## 对话记录
{conversation_text}

请根据以上对话记录生成学习报告。
"""

        try:
            from app.services.agent.agent import TeacherAssistantRAGAgent
            from app.config import settings as cfg

            agent = TeacherAssistantRAGAgent()

            model_aliases = cfg.teacher_agent_model_aliases
            actual_model = model_aliases.get(model, model)

            result = agent.generate_teacher_reply(
                stu_message=user_prompt,
                chat_id=roomid,
                model=actual_model,
                auto_build_index=False,
            )

            return {
                "ok": True,
                "roomid": roomid,
                "chat_name": chat_name,
                "message_count": len(text_messages),
                "report": result.get("reply", ""),
                "model": model,
            }

        except Exception as e:
            logger.error("生成报告失败: %s", e)
            return {
                "ok": False,
                "error": str(e),
            }

    def list_available_chats(self) -> List[Dict[str, Any]]:
        """列出可用的群聊"""
        archive_save_dir = Path(settings.chat_archive_save_dir)
        json_files = list(archive_save_dir.glob("*.json"))

        chat_map = {}
        for f in json_files:
            try:
                with open(f, encoding="utf-8") as fp:
                    messages = json.load(fp)

                for msg in messages:
                    rid = msg.get("roomid", "")
                    if rid:
                        if rid not in chat_map:
                            chat_map[rid] = {"roomid": rid, "filename": f.name, "message_count": 0}
                        chat_map[rid]["message_count"] += 1
            except Exception:
                continue

        roomids = list(chat_map.keys())
        if roomids:
            name_map = chat_archive_binding_service.get_room_name_map(roomids)
            for rid in chat_map:
                if rid in name_map:
                    chat_map[rid]["room_name"] = name_map[rid]

        return list(chat_map.values())


report_generation_service = ReportGenerationService()