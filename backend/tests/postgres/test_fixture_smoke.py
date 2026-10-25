import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url


pytestmark = pytest.mark.postgres


def test_opt_in_fixture_connects_only_to_designated_postgres_target(
    postgres_test_engine,
):
    expected = make_url(os.environ["ECS_POSTGRES_TEST_DATABASE_URL"])

    assert postgres_test_engine.url.drivername == "postgresql+psycopg"
    assert postgres_test_engine.url.host == expected.host
    assert postgres_test_engine.url.database == expected.database

    # Read-only reachability check: no schema is created, changed, or migrated.
    with postgres_test_engine.connect() as connection:
        connected_database, version_num, server_address, server_port = connection.execute(
            text(
                "SELECT current_database(), "
                "current_setting('server_version_num')::integer, "
                "inet_server_addr()::text, inet_server_port()"
            )
        ).one()

    assert connected_database == expected.database
    assert version_num // 10000 == 17
    assert server_address.partition("/")[0] == "127.0.0.1"
    assert server_port == expected.port
