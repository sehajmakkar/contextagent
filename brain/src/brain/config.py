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
    embed_model: str = "gemini-embedding-2"
    embed_dims: int = 768  # must match migrations/005_vectors.sql

    user_name: str = "Sehaj Preet"
    user_email: str = "sehaj.demo@example.com"

    # Must match the Swift app, which looks for the token file here.
    data_dir: Path = Path.home() / "Library" / "Application Support" / "ContextAgent"

    port: int = 8765
    auto_detect: bool = True             # background detection while `brain serve` runs
    detect_min_interval_s: float = 6.0   # ≤ 10 detection calls a minute
    # Live screen captures go to Gemini only on the paid tier, unless you opt in (test data only!).
    allow_free_tier_live: bool = False

    @property
    def db_path(self) -> Path:
        return self.data_dir.expanduser() / "brain.db"

    @property
    def token_path(self) -> Path:
        return self.data_dir.expanduser() / "brain.token"

    @property
    def live_detection_allowed(self) -> bool:
        """ADR-027: free-tier content may be used by Google, so real screens need paid or an explicit opt-in."""
        return self.gemini_tier == "paid" or self.allow_free_tier_live


@lru_cache
def get_settings() -> Settings:
    return Settings()
