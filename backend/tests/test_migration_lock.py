from types import SimpleNamespace

import pytest

from app.migration_lock import (
    ALEMBIC_MIGRATION_LOCK_KEY,
    acquire_alembic_migration_lock,
)


class _Result:
    def scalar_one(self):
        return None


class _Connection:
    def __init__(self, dialect, *, in_transaction):
        self.dialect = SimpleNamespace(name=dialect)
        self._in_transaction = in_transaction
        self.calls = []

    def in_transaction(self):
        return self._in_transaction

    def execute(self, statement, parameters):
        self.calls.append((str(statement), parameters))
        return _Result()


def test_non_postgresql_migration_connection_is_unchanged():
    connection = _Connection("sqlite", in_transaction=False)

    acquire_alembic_migration_lock(connection)

    assert connection.calls == []


def test_postgresql_lock_requires_active_transaction():
    connection = _Connection("postgresql", in_transaction=False)

    with pytest.raises(RuntimeError, match="active Alembic transaction"):
        acquire_alembic_migration_lock(connection)

    assert connection.calls == []


def test_postgresql_lock_uses_dedicated_key_and_propagates_errors():
    connection = _Connection("postgresql", in_transaction=True)

    acquire_alembic_migration_lock(connection)

    assert len(connection.calls) == 1
    statement, parameters = connection.calls[0]
    assert "pg_advisory_xact_lock" in statement
    assert parameters == {"lock_key": ALEMBIC_MIGRATION_LOCK_KEY}
    assert ALEMBIC_MIGRATION_LOCK_KEY != 827364510219

    class FailedConnection(_Connection):
        def execute(self, statement, parameters):
            raise OSError("synthetic lock acquisition failure")

    with pytest.raises(OSError, match="synthetic lock acquisition failure"):
        acquire_alembic_migration_lock(
            FailedConnection("postgresql", in_transaction=True)
        )
