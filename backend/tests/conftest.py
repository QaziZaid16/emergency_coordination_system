import os
from pathlib import Path

os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test-only-secret-with-more-than-32-characters"
# Never allow a developer's local provider settings or credentials to make a
# network request during tests. Individual adapter tests inject mock providers.
os.environ["AI_PROVIDER"] = "none"
os.environ["OPENROUTER_API_KEY"] = ""

_postgres_mode = os.environ.get("ECS_POSTGRES_TEST_MODE")
if _postgres_mode not in (None, "0", "1"):
    raise RuntimeError("ECS_POSTGRES_TEST_MODE must be unset, 0, or 1")
POSTGRES_TEST_ENABLED = _postgres_mode == "1"
if POSTGRES_TEST_ENABLED:
    # Resolve the application's existing runtime target (including .env) before
    # overriding DATABASE_URL, so the safety helper can reject the same server.
    from app.config import Settings
    from postgres_test_safety import validate_postgres_test_target

    try:
        _runtime_database_url = Settings().database_url
        _test_database_url = validate_postgres_test_target(
            os.environ, runtime_database_url=_runtime_database_url
        )
    except Exception:
        # Do not expose a URL or chained parser/settings details in pytest output.
        raise RuntimeError(
            "PostgreSQL test configuration rejected; verify opt-in gates and allowlists"
        ) from None
    os.environ["DATABASE_URL"] = _test_database_url.render_as_string(
        hide_password=False
    )
else:
    # Preserve the existing ordinary-suite isolation and override any developer
    # DATABASE_URL before application imports.
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient

from app import models  # noqa: F401
from app.database import Base, engine
from app.main import app


@pytest.fixture
def client():
    if POSTGRES_TEST_ENABLED:
        pytest.fail(
            "the ordinary SQLite client fixture is disabled in PostgreSQL test mode"
        )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


def pytest_collection_modifyitems(items):
    if not POSTGRES_TEST_ENABLED:
        return
    postgres_tests = Path(__file__).parent / "postgres"
    if any(not Path(item.path).resolve().is_relative_to(postgres_tests) for item in items):
        raise pytest.UsageError(
            "PostgreSQL test mode may collect only tests under tests/postgres/"
        )
