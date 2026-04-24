from __future__ import annotations

from typing import Any

from app.services.agent.parser import collect_source_files, parse_dialogue_file
from app.services.agent.types import DialogueChunk, DialogueTurn
from app.services.agent.vectorstore import VectorStoreManager


def build_teacher_assistant_index(*args: Any, **kwargs: Any):
    from app.services.agent.agent import build_teacher_assistant_index as _impl

    return _impl(*args, **kwargs)


def generate_teacher_reply(*args: Any, **kwargs: Any):
    from app.services.agent.agent import generate_teacher_reply as _impl

    return _impl(*args, **kwargs)


def __getattr__(name: str):
    if name in {"TeacherAssistantRAGAgent", "teacher_assistant_agent"}:
        from app.services.agent.agent import (
            TeacherAssistantRAGAgent,
            teacher_assistant_agent,
        )

        if name == "TeacherAssistantRAGAgent":
            return TeacherAssistantRAGAgent
        return teacher_assistant_agent
    raise AttributeError(f"module {__name__} has no attribute {name}")

__all__ = [
    "TeacherAssistantRAGAgent",
    "teacher_assistant_agent",
    "build_teacher_assistant_index",
    "generate_teacher_reply",
    "DialogueChunk",
    "DialogueTurn",
    "VectorStoreManager",
    "collect_source_files",
    "parse_dialogue_file",
]
