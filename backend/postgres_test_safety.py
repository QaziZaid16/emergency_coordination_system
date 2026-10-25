"""Fail-closed configuration checks for the opt-in PostgreSQL test path.

This module parses URLs only. It never opens a database connection.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from sqlalchemy.engine import URL, make_url


POSTGRES_TEST_MODE = "ECS_POSTGRES_TEST_MODE"
POSTGRES_TEST_DATABASE_URL = "ECS_POSTGRES_TEST_DATABASE_URL"
POSTGRES_TEST_DISPOSABLE = "ECS_POSTGRES_TEST_TARGET_DISPOSABLE"
POSTGRES_TEST_RUN_ID = "ECS_POSTGRES_TEST_RUN_ID"
POSTGRES_TEST_ALLOWED_HOSTS = "ECS_POSTGRES_TEST_ALLOWED_HOSTS"
POSTGRES_TEST_ALLOWED_DATABASES = "ECS_POSTGRES_TEST_ALLOWED_DATABASES"

_RUN_ID = re.compile(r"[a-z0-9]{8,32}\Z")


def _parse_url(value: str) -> URL:
    try:
        return make_url(value)
    except Exception:
        # SQLAlchemy parser exceptions may include the original URL.
        raise ValueError("database URL is malformed; value withheld") from None


def _allowlist(environ: Mapping[str, str], name: str) -> set[str]:
    raw = environ.get(name, "")
    values = {item.strip().casefold() for item in raw.split(",") if item.strip()}
    if not values or any("*" in item for item in values):
        raise ValueError(f"{name} must contain exact allowlist entries")
    return values


def validate_postgres_test_target(
    environ: Mapping[str, str], *, runtime_database_url: str
) -> URL:
    """Return a parsed test URL only when explicit isolation gates all pass.

    No credentials or URL strings are included in raised errors.
    """
    if environ.get(POSTGRES_TEST_MODE) != "1":
        raise ValueError(f"{POSTGRES_TEST_MODE}=1 is required")
    if environ.get(POSTGRES_TEST_DISPOSABLE) != "1":
        raise ValueError(f"{POSTGRES_TEST_DISPOSABLE}=1 is required")

    raw_url = environ.get(POSTGRES_TEST_DATABASE_URL, "")
    if not raw_url:
        raise ValueError(f"{POSTGRES_TEST_DATABASE_URL} is required")
    run_id = environ.get(POSTGRES_TEST_RUN_ID, "").casefold()
    if not _RUN_ID.fullmatch(run_id):
        raise ValueError(f"{POSTGRES_TEST_RUN_ID} must be a unique 8-32 character token")
    target = _parse_url(raw_url)
    if target.drivername != "postgresql+psycopg":
        raise ValueError("test database must use the postgresql+psycopg driver")

    host = (target.host or "").rstrip(".").casefold()
    database = target.database or ""
    if not host or not target.username or not database:
        raise ValueError("test database URL must include host, user, and database")
    if database.casefold() != f"ecs_test_{run_id}":
        raise ValueError("test database name must match the unique test run token")
    if database.casefold() == "coordination" or host == "db":
        raise ValueError("persistent Compose database target is not allowed")

    allowed_hosts = _allowlist(environ, POSTGRES_TEST_ALLOWED_HOSTS)
    allowed_databases = _allowlist(environ, POSTGRES_TEST_ALLOWED_DATABASES)
    if host not in allowed_hosts:
        raise ValueError("test database host is not allowlisted")
    if database.casefold() not in allowed_databases:
        raise ValueError("test database name is not allowlisted")

    configured = _parse_url(runtime_database_url)
    configured_host = (configured.host or "").rstrip(".").casefold()
    if (
        configured.drivername.startswith("postgresql")
        and configured_host == host
        and (configured.port or 5432) == (target.port or 5432)
    ):
        raise ValueError("test database must not share the configured runtime PostgreSQL host")

    return target
