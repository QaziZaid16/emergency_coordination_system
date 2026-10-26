import re
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


def normalize_database_url(value: str) -> str:
    """Use the installed psycopg 3 driver for provider PostgreSQL URLs."""
    value = value.strip()
    scheme = value.partition("://")[0].casefold()
    if scheme in {"postgres", "postgresql"}:
        return "postgresql+psycopg://" + value.partition("://")[2]
    return value


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/coordination.db"
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=5, ge=0, le=100)
    database_pool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    database_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400)
    jwt_secret: str = ""
    access_token_minutes: int = 30
    remember_me_days: int = Field(default=30, ge=1, le=365)
    cors_origins: str = "http://localhost:3000,http://localhost:8080"
    public_app_url: str = "http://localhost:8000"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    environment: str = "development"
    staging_responder_invitation_handoff: bool = False
    ai_provider: str = "none"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemma-4-31b-it"
    # Backward-compatible generic adapter settings for existing local setups.
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout_seconds: float = Field(default=8.0, ge=1, le=30)
    ai_max_attempts: int = Field(default=2, ge=1, le=3)
    ai_rate_limit_per_minute: int = Field(default=60, ge=1, le=600)
    ai_share_incident_location: bool = False
    recommendation_distance_weight: int = Field(default=45, ge=0, le=100)
    recommendation_capability_weight: int = Field(default=35, ge=0, le=100)
    recommendation_workload_weight: int = Field(default=20, ge=0, le=100)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_driver(cls, value: str) -> str:
        return normalize_database_url(value)

    @model_validator(mode="after")
    def validate_production(self):
        mode = self.environment.strip().casefold()
        if mode not in {"development", "test", "staging", "production"}:
            raise ValueError(
                "ENVIRONMENT must be development, test, staging, or production"
            )
        if self.environment != mode:
            self.environment = mode
        provider = self.ai_provider.strip().casefold()
        if provider not in {"", "none", "off", "openrouter", "openai_compatible"}:
            raise ValueError("AI_PROVIDER is not a supported provider")
        self.ai_provider = provider
        if self.staging_responder_invitation_handoff and mode != "staging":
            raise ValueError(
                "Staging responder invitation handoff is available only in staging mode"
            )
        if self.staging_responder_invitation_handoff and self.smtp_host:
            raise ValueError(
                "Staging responder invitation handoff requires SMTP to remain disabled"
            )
        if self.ai_provider.casefold() == "openrouter":
            provider_url = urlsplit(self.openrouter_base_url)
            if (
                not self.openrouter_api_key
                or provider_url.scheme != "https"
                or not provider_url.hostname
                or provider_url.username
                or provider_url.password
                or provider_url.query
                or provider_url.fragment
            ):
                raise ValueError("OpenRouter requires a server-side key and HTTPS base URL")
        if mode not in {"production", "staging"}:
            return self
        if re.search(r"%(?![0-9a-fA-F]{2})", self.database_url):
            raise ValueError(
                "Production and staging require a valid PostgreSQL DATABASE_URL"
            )
        try:
            database_url = make_url(self.database_url)
        except Exception:
            raise ValueError(
                "Production and staging require a valid PostgreSQL DATABASE_URL"
            ) from None
        if (
            database_url.drivername != "postgresql+psycopg"
            or not database_url.host
            or not database_url.database
            or not database_url.username
        ):
            raise ValueError(
                "Production and staging require a complete PostgreSQL DATABASE_URL"
            )
        sslmode = str(database_url.query.get("sslmode", "")).casefold()
        if sslmode not in {
            "require",
            "verify-ca",
            "verify-full",
        }:
            raise ValueError(
                "Production and staging DATABASE_URL must require PostgreSQL TLS"
            )
        origins = self.cors_origin_list
        if not origins or any(not origin.startswith("https://") for origin in origins):
            raise ValueError("Production CORS_ORIGINS must list HTTPS dashboard origins")
        if any(
            "*" in origin
            or urlsplit(origin).path not in ("", "/")
            or urlsplit(origin).query
            or urlsplit(origin).fragment
            or not urlsplit(origin).hostname
            or "example" in urlsplit(origin).hostname.split(".")
            or urlsplit(origin).hostname.endswith((".test", ".invalid", ".localhost"))
            for origin in origins
        ):
            raise ValueError("Production CORS_ORIGINS cannot contain wildcard or placeholder origins")
        public_app = urlsplit(self.public_app_url)
        if (
            public_app.scheme != "https"
            or not public_app.hostname
            or public_app.username
            or public_app.password
            or public_app.path not in ("", "/")
            or public_app.query
            or public_app.fragment
        ):
            raise ValueError("Production PUBLIC_APP_URL must be a real HTTPS origin")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if "environment" not in settings.model_fields_set:
        raise RuntimeError("ENVIRONMENT must be explicitly configured")
    if settings.environment != "test" and len(settings.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 characters")
    return settings
