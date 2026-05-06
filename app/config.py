"""
企业微信配置管理
"""

import os
from pathlib import Path
from typing import Dict, List
from dotenv import dotenv_values


class Settings:
    def __init__(self):
        project_root = Path(__file__).parent.parent
        env_file = project_root / ".env"
        if env_file.exists():
            self._env = dotenv_values(env_file)
        else:
            self._env = {}

    @property
    def corp_id(self) -> str:
        return self._env.get("WECOM_CORP_ID", "")

    @property
    def token(self) -> str:
        return self._env.get("WECOM_TOKEN", "")

    @property
    def encoding_aes_key(self) -> str:
        return self._env.get("WECOM_ENCODING_AES_KEY", "")

    @property
    def agent_id(self) -> int:
        return int(self._env.get("WECOM_AGENT_ID", "0"))

    @property
    def rsa_private_key_path(self) -> str:
        default = Path(__file__).parent.parent / "keys" / "private.pem"
        return self._env.get("WECOM_RSA_PRIVATE_KEY_PATH", str(default))

    @property
    def wecom_contact_secret(self) -> str:
        return self._env.get("WECOM_CONTACT_SECRET", "")

    # WECOM_APP_SECRET
    @property
    def app_secret(self) -> str:
        return self._env.get("WECOM_APP_SECRET", "")

    @property
    def chat_archive_save_dir(self) -> str:
        return self._env.get(
            "WECOM_CHAT_ARCHIVE_SAVE_DIR",
            str(Path(__file__).parent.parent / "archive_data"),
        )

    @property
    def sdk_lib_path(self) -> str:
        default = "/www/workqq/work.qq/sdk/C_sdk/libWeWorkFinanceSdk_C.so"
        return self._env.get("WECOM_SDK_LIB_PATH", default)

    @property
    def chat_archive_use_sdk(self) -> bool:
        return self._env.get("WECOM_CHAT_ARCHIVE_USE_SDK", "0").strip() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @property
    def corp_secret(self) -> str:
        return self._env.get("WECOM_CORP_SECRET", "")

    @property
    def teacher_agent_archive_dir(self) -> str:
        default = Path(__file__).parent.parent / "archive_data" / "save"
        return self._env.get("TEACHER_AGENT_ARCHIVE_DIR", str(default))

    @property
    def teacher_agent_vector_dir(self) -> str:
        default = Path(__file__).parent.parent / "archive_data" / "vector_db" / "teacher_assistant"
        return self._env.get("TEACHER_AGENT_VECTOR_DIR", str(default))

    @property
    def teacher_agent_prompt_dir(self) -> str:
        default = Path(__file__).parent / "services" / "agent" / "prompt"
        return self._env.get("TEACHER_AGENT_PROMPT_DIR", str(default))

    @property
    def teacher_agent_exclude_roomids(self) -> List[str]:
        value = self._env.get("TEACHER_AGENT_EXCLUDE_ROOMIDS", "")
        if not value:
            return []
        return [v.strip() for v in value.split(",") if v.strip()]

    @property
    def teacher_agent_collection_name(self) -> str:
        return self._env.get("TEACHER_AGENT_COLLECTION_NAME", "teacher_assistant_dialogue_v1")

    @property
    def teacher_agent_window_size(self) -> int:
        return int(self._env.get("TEACHER_AGENT_WINDOW_SIZE", "6"))

    @property
    def teacher_agent_window_overlap(self) -> int:
        return int(self._env.get("TEACHER_AGENT_WINDOW_OVERLAP", "2"))

    @property
    def teacher_agent_same_chat_top_k(self) -> int:
        return int(self._env.get("TEACHER_AGENT_SAME_CHAT_TOP_K", "4"))

    @property
    def teacher_agent_global_top_k(self) -> int:
        return int(self._env.get("TEACHER_AGENT_GLOBAL_TOP_K", "3"))

    @property
    def teacher_agent_min_same_chat_hits(self) -> int:
        return int(self._env.get("TEACHER_AGENT_MIN_SAME_CHAT_HITS", "2"))

    @property
    def teacher_agent_max_context_chunks(self) -> int:
        return int(self._env.get("TEACHER_AGENT_MAX_CONTEXT_CHUNKS", "6"))

    @property
    def teacher_agent_distance_threshold(self) -> float:
        return float(self._env.get("TEACHER_AGENT_DISTANCE_THRESHOLD", "1.25"))

    @property
    def teacher_agent_embedding_provider(self) -> str:
        return self._env.get("TEACHER_AGENT_EMBEDDING_PROVIDER", "openai")

    @property
    def teacher_agent_embedding_model(self) -> str:
        return self._env.get("TEACHER_AGENT_EMBEDDING_MODEL", "text-embedding-3-small")

    @property
    def teacher_agent_embedding_api_key(self) -> str:
        return self._env.get(
            "TEACHER_AGENT_EMBEDDING_API_KEY",
            self._env.get("TEACHER_AGENT_EMBEDDING_TOKEN", ""),
        )

    @property
    def teacher_agent_embedding_base_url(self) -> str:
        return self._env.get(
            "TEACHER_AGENT_EMBEDDING_BASE_URL",
            self._env.get("TEACHER_AGENT_EMBEDDING_HOST", ""),
        )

    @property
    def teacher_agent_llm_model(self) -> str:
        return self._env.get("TEACHER_AGENT_LLM_MODEL", "gpt-4o-mini")

    @property
    def teacher_agent_llm_api_key(self) -> str:
        return self._env.get(
            "TEACHER_AGENT_LLM_API_KEY",
            self._env.get("TEACHER_AGENT_LLM_TOKEN", ""),
        )

    @property
    def teacher_agent_llm_base_url(self) -> str:
        return self._env.get(
            "TEACHER_AGENT_LLM_BASE_URL",
            self._env.get("TEACHER_AGENT_LLM_HOST", ""),
        )

    @property
    def teacher_agent_llm_temperature(self) -> float:
        return float(self._env.get("TEACHER_AGENT_LLM_TEMPERATURE", "0.4"))

    @property
    def teacher_agent_model_aliases(self) -> Dict[str, str]:
        raw = self._env.get("TEACHER_AGENT_MODEL_ALIASES", "")
        if not raw:
            return {}
        result = {}
        for item in raw.split(","):
            if not item or ":" not in item:
                continue
            parts = item.split(":", 1)
            if len(parts) == 2:
                result[parts[0].strip()] = parts[1].strip()
        return result

    @property
    def teacher_agent_default_models(self) -> List[Dict[str, str]]:
        raw = self._env.get("TEACHER_AGENT_DEFAULT_MODELS", "")
        if not raw:
            return []
        result = []
        for item in raw.split(","):
            if not item or ":" not in item:
                continue
            parts = item.split(":", 1)
            if len(parts) == 2:
                result.append({"id": parts[0].strip(), "name": parts[1].strip()})
        return result

    @property
    def redis_url(self) -> str:
        return self._env.get("REDIS_URL", "redis://localhost:6379/0")

    @property
    def redis_queue_name(self) -> str:
        return self._env.get("REDIS_QUEUE_NAME", "wecom_msgaudit_queue")

    def is_configured(self) -> bool:
        return bool(self.corp_id and self.token and self.encoding_aes_key)


settings = Settings()
