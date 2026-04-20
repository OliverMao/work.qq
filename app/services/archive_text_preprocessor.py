from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Union


class ArchiveTextPreprocessor:
    """Convert archive json messages into role-prefixed plain text lines."""

    def __init__(
        self,
        source_dir: Union[str, Path],
        output_dir: Union[str, Path],
    ) -> None:
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)

    def run(self) -> Dict[str, Any]:
        if not self.source_dir.exists() or not self.source_dir.is_dir():
            raise FileNotFoundError(f"source directory not found: {self.source_dir}")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        json_files = sorted(
            file_path
            for file_path in self.source_dir.rglob("*.json")
            if file_path.is_file() and not self._is_in_output_dir(file_path)
        )

        processed_files = 0
        total_lines = 0

        for file_path in json_files:
            lines = self._process_file(file_path)
            output_path = self.output_dir / file_path.with_suffix(".txt").name
            output_path.write_text("\n".join(lines), encoding="utf-8")
            processed_files += 1
            total_lines += len(lines)

        return {
            "processed_files": processed_files,
            "total_lines": total_lines,
            "source_dir": str(self.source_dir),
            "output_dir": str(self.output_dir),
        }

    def _is_in_output_dir(self, file_path: Path) -> bool:
        try:
            file_path.resolve().relative_to(self.output_dir.resolve())
            return True
        except ValueError:
            return False

    def _process_file(self, file_path: Path) -> List[str]:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        messages = self._extract_messages(payload)

        text_messages = [
            item for item in messages if str(item.get("msgtype", "")).lower() == "text"
        ]
        text_messages.sort(key=self._extract_msgtime)

        output_lines: List[str] = []
        for message in text_messages:
            content = self._extract_text_content(message)
            if not content:
                continue
            role = self._resolve_role(message.get("from"))
            output_lines.append(f"{role}:{content}")

        return output_lines

    @staticmethod
    def _extract_messages(payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            raw_messages = payload
        elif isinstance(payload, dict) and isinstance(payload.get("messages"), list):
            raw_messages = payload["messages"]
        else:
            raw_messages = []

        return [item for item in raw_messages if isinstance(item, dict)]

    @staticmethod
    def _extract_msgtime(message: Dict[str, Any]) -> int:
        try:
            return int(message.get("msgtime", 0) or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _resolve_role(user_id: Any) -> str:
        sender = str(user_id or "").strip().lower()
        return "Stu" if sender.startswith("wm") else "Tea"

    @staticmethod
    def _extract_text_content(message: Dict[str, Any]) -> str:
        text_payload = message.get("text")
        if not isinstance(text_payload, dict):
            return ""

        content = text_payload.get("content")
        if content is None:
            return ""

        content_text = str(content).replace("\r\n", "\n").replace("\r", "\n").strip()
        return content_text.replace("\n", "\\n")
