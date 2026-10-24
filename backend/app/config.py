from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/coordination.db"
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
    ai_provider: str = "none"
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout_seconds: float = Field(default=8.0, ge=1, le=30)
    ai_max_attempts: int = Field(default=1, ge=1, le=3)
    ai_rate_limit_per_minute: int = Field(default=60, ge=1, le=600)
    ai_share_incident_location: bool = False
    recommendation_distance_weight: int = Field(default=45, ge=0, le=100)
    recommendation_capability_weight: int = Field(default=35, ge=0, le=100)
    recommendation_workload_weight: int = Field(default=20, ge=0, le=100)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production(self):
        if self.environment.lower() != "production":
            return self
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("Production requires a durable PostgreSQL DATABASE_URL")
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
    if settings.environment != "test" and len(settings.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 characters")
    return settings
