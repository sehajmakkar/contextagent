from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    gemini_api_key: SecretStr | None = None
    gemini_tier: Literal["free", "paid"] = "free"
    llm_model: str = "gemini-3.8-flash"

    user_name: str = "Sehaj Preet"
    user_email: str = "sehaj.demo@example.com"

    data_dir: Path = Path.home() / "Library" / "Application Support" / "ContextAgent"

    @property
    def db_path(self) -> Path:
        return self.data_dir.expanduser() / "brain.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
