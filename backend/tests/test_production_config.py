from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import app.config as app_config
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


def test_staging_uses_production_database_and_https_validation():
    settings = Settings(
        environment="staging",
        jwt_secret="x" * 40,
        database_url="postgresql+psycopg://user:password@db.internal/coordination",
        cors_origins="https://staging-dashboard.coordination-service.org",
        public_app_url="https://staging-dashboard.coordination-service.org",
        staging_responder_invitation_handoff=True,
    )
    assert settings.staging_responder_invitation_handoff is True
    assert settings.environment == "staging"


def test_staging_invitation_handoff_defaults_disabled():
    settings = Settings(
        environment="staging",
        jwt_secret="x" * 40,
        database_url="postgresql+psycopg://user:password@db.internal/coordination",
        cors_origins="https://staging-dashboard.coordination-service.org",
        public_app_url="https://staging-dashboard.coordination-service.org",
        _env_file=None,
    )

    assert settings.staging_responder_invitation_handoff is False


@pytest.mark.parametrize("environment", ["prod", "stagng", "", "preview"])
def test_unknown_environment_names_cannot_bypass_deployment_validation(environment):
    with pytest.raises(ValidationError, match="ENVIRONMENT"):
        Settings(environment=environment, _env_file=None)


@pytest.mark.parametrize("jwt_secret", ["", "too-short"])
def test_runtime_settings_reject_missing_or_short_jwt_secret(
    monkeypatch, jwt_secret
):
    app_config.get_settings.cache_clear()
    monkeypatch.setattr(
        app_config,
        "Settings",
        lambda: SimpleNamespace(
            environment="staging",
            jwt_secret=jwt_secret,
            model_fields_set={"environment", "jwt_secret"},
        ),
    )

    with pytest.raises(
        RuntimeError, match="JWT_SECRET must contain at least 32 characters"
    ):
        app_config.get_settings()

    app_config.get_settings.cache_clear()


def test_runtime_settings_reject_unset_environment(monkeypatch):
    settings_class = app_config.Settings
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setattr(
        app_config, "Settings", lambda: settings_class(_env_file=None)
    )
    app_config.get_settings.cache_clear()

    with pytest.raises(
        RuntimeError, match="ENVIRONMENT must be explicitly configured"
    ):
        app_config.get_settings()

    app_config.get_settings.cache_clear()


def test_environment_name_is_normalized_case_insensitively():
    settings = Settings(
        environment="STAGING",
        jwt_secret="x" * 40,
        database_url="postgresql+psycopg://user:password@db.internal/coordination",
        cors_origins="https://staging-dashboard.coordination-service.org",
        public_app_url="https://staging-dashboard.coordination-service.org",
    )

    assert settings.environment == "staging"


@pytest.mark.parametrize(
    "overrides",
    [
        {"database_url": "sqlite:///./data/staging.db"},
        {"cors_origins": "http://localhost:8080"},
        {"public_app_url": "http://localhost:8000"},
    ],
)
def test_staging_rejects_non_production_safe_configuration(overrides):
    values = {
        "environment": "staging",
        "jwt_secret": "x" * 40,
        "database_url": "postgresql+psycopg://user:password@db.internal/coordination",
        "cors_origins": "https://staging-dashboard.coordination-service.org",
        "public_app_url": "https://staging-dashboard.coordination-service.org",
    }
    values.update(overrides)
    with pytest.raises(ValidationError):
        Settings(**values)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://",
        "postgresql+psycopg://user@/coordination",
        "postgresql+psycopg://user@db.internal",
        "postgresql+psycopg://user:password@db.internal/",
        "postgresql+psycopg://%zz@db.internal/coordination",
    ],
)
def test_staging_rejects_incomplete_or_malformed_postgres_urls(database_url):
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(
            environment="staging",
            jwt_secret="x" * 40,
            database_url=database_url,
            cors_origins="https://staging-dashboard.coordination-service.org",
            public_app_url="https://staging-dashboard.coordination-service.org",
            _env_file=None,
        )


def test_staging_rejects_unknown_ai_provider_selector():
    with pytest.raises(ValidationError, match="AI_PROVIDER"):
        Settings(
            environment="staging",
            jwt_secret="x" * 40,
            database_url="postgresql+psycopg://user:password@db.internal/coordination",
            cors_origins="https://staging-dashboard.coordination-service.org",
            public_app_url="https://staging-dashboard.coordination-service.org",
            ai_provider="openroter",
            _env_file=None,
        )


def test_staging_handoff_cannot_be_enabled_in_production_or_with_smtp():
    values = {
        "environment": "production",
        "jwt_secret": "x" * 40,
        "database_url": "postgresql+psycopg://user:password@db.internal/coordination",
        "cors_origins": "https://dashboard.coordination-service.org",
        "public_app_url": "https://dashboard.coordination-service.org",
        "staging_responder_invitation_handoff": True,
    }
    with pytest.raises(ValidationError, match="only in staging"):
        Settings(**values)
    values["environment"] = "staging"
    values["smtp_host"] = "smtp.test.invalid"
    values["cors_origins"] = "https://staging-dashboard.coordination-service.org"
    values["public_app_url"] = "https://staging-dashboard.coordination-service.org"
    with pytest.raises(ValidationError, match="SMTP to remain disabled"):
        Settings(**values)


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
