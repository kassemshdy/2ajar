from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "dev-insecure-jwt-secret-change-me-0123456789"  # noqa: S105 (dev-only default, rejected outside development)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["development", "test", "staging", "production"] = "development"
    database_url: str = "postgresql+psycopg://ajar:ajar@localhost:5432/ajar_dev"

    jwt_secret: str = _DEV_JWT_SECRET
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    cookie_secure: bool = False
    cookie_domain: str | None = None
    cors_origins: str = "http://localhost:3000"

    public_web_base_url: str = "http://localhost:3000"
    demo_mode: bool = False
    listing_ttl_days: int = 30
    publish_requires_media: bool = True
    consent_text_version: str = "2026-11-v1"

    storage_backend: Literal["local", "s3"] = "local"
    media_root: Path = Path("var/media")
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_region: str = "auto"

    max_upload_bytes: int = 8 * 1024 * 1024
    max_media_per_listing: int = 20
    rate_limit_enabled: bool = True
    # Proxies that append to X-Forwarded-For before the API (Railway edge = 1; +1 behind Cloudflare proxy).
    forwarded_trusted_hops: int = 0

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        # Railway exposes postgres:// or postgresql:// URLs; we use the psycopg 3 driver.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix) :]
        return v

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if self.env in ("production", "staging"):
            if self.jwt_secret == _DEV_JWT_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set to a random value of at least 32 characters")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true outside development")
        if self.env == "production" and self.demo_mode:
            raise ValueError("DEMO_MODE must not be enabled in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
