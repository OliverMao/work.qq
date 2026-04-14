"""
企业微信配置管理
"""

import os
from pathlib import Path
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
    def chat_archive_secret(self) -> str:
        return self._env.get("WECOM_CHAT_ARCHIVE_SECRET", "")

    @property
    def rsa_private_key_path(self) -> str:
        default = Path(__file__).parent.parent / "keys" / "private.pem"
        return self._env.get("WECOM_RSA_PRIVATE_KEY_PATH", str(default))

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
        return self._env.get("WECOM_CHAT_ARCHIVE_SECRET", "")

    def is_configured(self) -> bool:
        return bool(self.corp_id and self.token and self.encoding_aes_key)


settings = Settings()
