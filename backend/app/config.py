"""Application settings, loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
ARTIFACT_DIR = BACKEND_DIR / "app" / "ml" / "artifacts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RockGuard AI"
    environment: str = "development"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    database_url: str = "sqlite:///./data/rockguard.db"

    sensor_tick_seconds: int = 5

    threshold_medium: float = 35.0
    threshold_high: float = 60.0
    threshold_critical: float = 80.0

    alert_cooldown_minutes: int = 2

    # Optional outbound providers. Blank => SIMULATED dispatch only.
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    alert_recipients: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def recipient_list(self) -> list[str]:
        return [r.strip() for r in self.alert_recipients.split(",") if r.strip()]

    @property
    def sms_configured(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_from_number)


@lru_cache
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()


settings = get_settings()
