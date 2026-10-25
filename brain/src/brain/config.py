from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    gemini_api_key: SecretStr | None = None
    llm_model: str = "gemini-3.8-flash"
    embed_model: str = "gemini-embedding-2"
    embed_dims: int = 768  # must match migrations/005_vectors.sql

    user_name: str = "Sehaj Preet"
    user_email: str = "sehaj.demo@example.com"

    # Must match the Swift app, which looks for the token file here.
    data_dir: Path = Path.home() / "Library" / "Application Support" / "ContextAgent"

    port: int = 8765
    # The OAuth client you download from Google Cloud (gitignored: credentials*.json). See plan.md, Phase 5.
    gmail_client_secrets: Path = REPO_ROOT / "credentials.json"
    auto_detect: bool = True             # background detection while `brain serve` runs
    detect_min_interval_s: float = 6.0   # ≤ 10 detection calls a minute

    @property
    def db_path(self) -> Path:
        return self.data_dir.expanduser() / "brain.db"

    @property
    def token_path(self) -> Path:
        return self.data_dir.expanduser() / "brain.token"



@lru_cache
def get_settings() -> Settings:
    return Settings()
