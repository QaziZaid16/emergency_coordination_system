import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_accepts_postgres_and_https_origins():
    settings = Settings(
        environment="production",
        jwt_secret="x" * 40,
        database_url="postgresql+psycopg://user:password@db.internal/coordination",
        cors_origins="https://dashboard.coordination-service.org",
        public_app_url="https://dashboard.coordination-service.org",
    )
    assert settings.cors_origin_list == ["https://dashboard.coordination-service.org"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"database_url": "sqlite:///./data/production.db"},
        {"cors_origins": "*"},
        {"cors_origins": "http://localhost:8080"},
        {"cors_origins": "https://dashboard.example.test"},
        {"cors_origins": "https://dashboard.example.com"},
        {"cors_origins": "https://dashboard.coordination-service.org/path"},
        {"public_app_url": "http://localhost:8000"},
    ],
)
def test_production_rejects_unsafe_or_ephemeral_configuration(overrides):
    values = {
        "environment": "production",
        "jwt_secret": "x" * 40,
        "database_url": "postgresql+psycopg://user:password@db.internal/coordination",
        "cors_origins": "https://dashboard.coordination-service.org",
        "public_app_url": "https://dashboard.coordination-service.org",
    }
    values.update(overrides)
    with pytest.raises(ValidationError):
        Settings(**values)
