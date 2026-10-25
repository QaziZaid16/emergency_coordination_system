"""PostgreSQL coordination for concurrent Alembic migration processes."""

from sqlalchemy import text


# Dedicated bigint advisory-lock namespace key: ASCII "ECSMIGR".
# Keep distinct from the Super Admin bootstrap lock in provision_admin.py.
ALEMBIC_MIGRATION_LOCK_KEY = 0x4543534D494752


def acquire_alembic_migration_lock(connection) -> None:
    """Acquire a transaction-scoped PostgreSQL lock before revision lookup.

    The caller must already be inside Alembic's outer transaction. PostgreSQL
    releases this lock automatically when that transaction commits or rolls
    back. Non-PostgreSQL migration behavior is unchanged.
    """
    if connection.dialect.name != "postgresql":
        return
    if not connection.in_transaction():
        raise RuntimeError(
            "PostgreSQL migration lock requires an active Alembic transaction"
        )
    connection.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": ALEMBIC_MIGRATION_LOCK_KEY},
    ).scalar_one()
