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

    def is_configured(self) -> bool:
        return bool(self.corp_id and self.token and self.encoding_aes_key)


settings = Settings()
