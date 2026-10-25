"""Fixtures for explicitly enabled tests against a disposable PostgreSQL DB."""

import os
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker


def pytest_collection_modifyitems(items):
    postgres_tests = Path(__file__).parent.resolve()
    if os.environ.get("ECS_POSTGRES_TEST_MODE") == "1":
        for item in items:
            if Path(item.path).resolve().is_relative_to(postgres_tests):
                item.add_marker(pytest.mark.postgres)
        return
    skip_postgres = pytest.mark.skip(
        reason="PostgreSQL tests require explicit fail-closed opt-in"
    )
    for item in items:
        if Path(item.path).resolve().is_relative_to(postgres_tests):
            item.add_marker(skip_postgres)


@pytest.fixture(autouse=True)
def forbid_provider_network(monkeypatch):
    from app import intelligence

    def unexpected_provider_request(*_args, **_kwargs):
        raise AssertionError("PostgreSQL tests must not access provider HTTP boundaries")

    monkeypatch.setattr(intelligence.httpx, "AsyncClient", unexpected_provider_request)
    monkeypatch.setattr(intelligence, "urlopen", unexpected_provider_request)


@pytest.fixture(scope="session")
def postgres_test_engine():
    if os.environ.get("ECS_POSTGRES_TEST_MODE") != "1":
        pytest.skip("PostgreSQL test mode is disabled")

    # Root conftest already validated this target before importing app modules.
    # This fixture does not create schema, migrate, truncate, or drop anything.
    from app.database import engine
    from sqlalchemy.engine import make_url

    try:
        requested = make_url(os.environ["ECS_POSTGRES_TEST_DATABASE_URL"])
    except Exception:
        pytest.fail("validated PostgreSQL test target became unavailable", pytrace=False)
    if engine.url != requested:
        pytest.fail("application engine does not match validated PostgreSQL test target", pytrace=False)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def postgres_test_sessions(postgres_test_engine):
    return sessionmaker(
        bind=postgres_test_engine,
        autoflush=False,
        expire_on_commit=False,
    )
