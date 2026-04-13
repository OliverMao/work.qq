"""
企业微信配置管理
"""

from dotenv import dotenv_values
import os


class Settings:
    def __init__(self):
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        self._env = dotenv_values(env_file)

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


settings = Settings()
