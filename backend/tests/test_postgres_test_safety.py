import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from postgres_test_safety import validate_postgres_test_target


TEST_URL = (
    "postgresql+psycopg://ecs_test_user:synthetic-only-password@"
    "pg-test.example.invalid:5432/ecs_test_a1b2c3d4"
)


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("synthetic URL validation must not access the network")

    monkeypatch.setattr(socket, "getaddrinfo", unexpected_network)
    monkeypatch.setattr(socket, "create_connection", unexpected_network)


def valid_environment():
    return {
        "ECS_POSTGRES_TEST_MODE": "1",
        "ECS_POSTGRES_TEST_TARGET_DISPOSABLE": "1",
        "ECS_POSTGRES_TEST_RUN_ID": "a1b2c3d4",
        "ECS_POSTGRES_TEST_DATABASE_URL": TEST_URL,
        "ECS_POSTGRES_TEST_ALLOWED_HOSTS": "pg-test.example.invalid",
        "ECS_POSTGRES_TEST_ALLOWED_DATABASES": "ecs_test_a1b2c3d4",
    }


def assert_rejected(environment, runtime_database_url="sqlite:///:memory:"):
    with pytest.raises(ValueError) as error:
        validate_postgres_test_target(
            environment, runtime_database_url=runtime_database_url
        )
    assert "synthetic-only-password" not in str(error.value)
    assert "postgresql+psycopg://" not in str(error.value)


def test_validated_target_requires_no_network_and_returns_parsed_metadata():
    target = validate_postgres_test_target(
        valid_environment(), runtime_database_url="sqlite:///:memory:"
    )

    assert target.drivername == "postgresql+psycopg"
    assert target.host == "pg-test.example.invalid"
    assert target.database == "ecs_test_a1b2c3d4"
    assert target.username == "ecs_test_user"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda env: env.pop("ECS_POSTGRES_TEST_MODE"),
        lambda env: env.pop("ECS_POSTGRES_TEST_DATABASE_URL"),
        lambda env: env.update(ECS_POSTGRES_TEST_TARGET_DISPOSABLE="0"),
        lambda env: env.pop("ECS_POSTGRES_TEST_RUN_ID"),
        lambda env: env.update(ECS_POSTGRES_TEST_RUN_ID="deadbeef"),
        lambda env: env.update(ECS_POSTGRES_TEST_ALLOWED_HOSTS=""),
        lambda env: env.update(ECS_POSTGRES_TEST_ALLOWED_DATABASES=""),
        lambda env: env.update(ECS_POSTGRES_TEST_ALLOWED_HOSTS="*"),
        lambda env: env.update(
            ECS_POSTGRES_TEST_DATABASE_URL="sqlite:///synthetic-test.db"
        ),
        lambda env: env.update(
            ECS_POSTGRES_TEST_DATABASE_URL=(
                "postgresql+psycopg://u:p@unlisted.example.invalid:5432/"
                "ecs_test_a1b2c3d4"
            )
        ),
        lambda env: env.update(
            ECS_POSTGRES_TEST_ALLOWED_DATABASES="ecs_test_other_a1b2c3d4"
        ),
        lambda env: env.update(
            ECS_POSTGRES_TEST_DATABASE_URL=(
                "postgresql+psycopg://u:p@db:5432/ecs_test_a1b2c3d4"
            ),
            ECS_POSTGRES_TEST_ALLOWED_HOSTS="db",
        ),
        lambda env: env.update(
            ECS_POSTGRES_TEST_DATABASE_URL=(
                "postgresql+psycopg://u:p@pg-test.example.invalid:5432/coordination"
            ),
            ECS_POSTGRES_TEST_ALLOWED_DATABASES="coordination",
        ),
    ],
    ids=[
        "opt-in-required",
        "test-url-required",
        "disposable-designation-required",
        "unique-run-token-required",
        "database-must-match-run-token",
        "host-allowlist-required",
        "database-allowlist-required",
        "wildcard-host-rejected",
        "non-postgresql-url-rejected",
        "unlisted-host-rejected",
        "unlisted-database-rejected",
        "compose-service-host-rejected",
        "compose-database-rejected",
    ],
)
def test_invalid_target_configuration_fails_closed(mutation):
    environment = valid_environment()
    mutation(environment)
    assert_rejected(environment)


def test_target_on_configured_runtime_postgres_host_is_rejected():
    assert_rejected(
        valid_environment(),
        runtime_database_url=(
            "postgresql+psycopg://runtime_user:synthetic-runtime-password@"
            "pg-test.example.invalid:5432/production"
        ),
    )


def test_database_name_must_be_unique_test_name():
    environment = valid_environment()
    environment["ECS_POSTGRES_TEST_DATABASE_URL"] = (
        "postgresql+psycopg://u:p@pg-test.example.invalid:5432/analysis"
    )
    environment["ECS_POSTGRES_TEST_ALLOWED_DATABASES"] = "analysis"
    assert_rejected(environment)


def test_requested_postgres_mode_without_target_fails_before_app_import():
    environment = os.environ.copy()
    environment.update(
        {
            "ECS_POSTGRES_TEST_MODE": "1",
            "AI_PROVIDER": "none",
            "OPENROUTER_API_KEY": "",
            "ENVIRONMENT": "test",
            "JWT_SECRET": "synthetic-test-secret-that-is-not-printed",
            "DATABASE_URL": "sqlite:///:memory:",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    for name in (
        "ECS_POSTGRES_TEST_TARGET_DISPOSABLE",
        "ECS_POSTGRES_TEST_RUN_ID",
        "ECS_POSTGRES_TEST_DATABASE_URL",
        "ECS_POSTGRES_TEST_ALLOWED_HOSTS",
        "ECS_POSTGRES_TEST_ALLOWED_DATABASES",
    ):
        environment.pop(name, None)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/test_postgres_test_safety.py",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "PostgreSQL test configuration rejected" in output
    assert "synthetic-test-secret-that-is-not-printed" not in output


def test_disabled_postgres_mode_keeps_ordinary_tests_enabled():
    environment = os.environ.copy()
    environment.update(
        {
            "ECS_POSTGRES_TEST_MODE": "0",
            "AI_PROVIDER": "none",
            "OPENROUTER_API_KEY": "",
            "SMTP_HOST": "",
            "SMTP_USERNAME": "",
            "SMTP_PASSWORD": "",
            "SMTP_FROM": "",
            "ENVIRONMENT": "test",
            "DATABASE_URL": "sqlite:///:memory:",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/test_health.py",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "2 passed" in output
    assert "skipped" not in output
