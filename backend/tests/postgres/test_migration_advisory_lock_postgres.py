"""Concurrent Alembic migration tests against the opted-in disposable target."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.migration_lock import ALEMBIC_MIGRATION_LOCK_KEY


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PARENT_REVISION = "4e5b0b6a92d1"
HEAD_REVISION = "d6b85f2c0a71"


def _migration_env(application_name: str) -> dict[str, str]:
    environment = os.environ.copy()
    environment["AI_PROVIDER"] = "none"
    environment["OPENROUTER_API_KEY"] = ""
    environment["ENVIRONMENT"] = "test"
    environment["PGAPPNAME"] = application_name
    return environment


def _start_alembic(application_name: str, *arguments: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND_ROOT,
        env=_migration_env(application_name),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _run_alembic(application_name: str, *arguments: str) -> int:
    process = _start_alembic(application_name, *arguments)
    try:
        _stdout, _stderr = process.communicate(timeout=45)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=5)
        pytest.fail("Alembic subprocess timed out; output withheld")
    return process.returncode


def _current_revision(engine) -> str:
    with engine.connect() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def _login_attempt_table_exists(engine) -> bool:
    with engine.connect() as connection:
        return bool(
            connection.execute(
                text(
                    "SELECT to_regclass('public.login_attempt_buckets') IS NOT NULL"
                )
            ).scalar_one()
        )


def _lock_state(engine, application_name: str):
    key_high = ALEMBIC_MIGRATION_LOCK_KEY >> 32
    key_low = ALEMBIC_MIGRATION_LOCK_KEY & 0xFFFFFFFF
    with engine.connect() as connection:
        activity = connection.execute(
            text(
                "SELECT wait_event_type, wait_event "
                "FROM pg_stat_activity "
                "WHERE application_name = :application_name "
                "AND datname = current_database()"
            ),
            {"application_name": application_name},
        ).one_or_none()
        granted = connection.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_locks l "
                "JOIN pg_stat_activity a ON a.pid = l.pid "
                "WHERE a.application_name = :application_name "
                "AND a.datname = current_database() "
                "AND l.locktype = 'advisory' AND l.classid = :key_high "
                "AND l.objid = :key_low AND l.objsubid = 1 AND l.granted)"
            ),
            {"application_name": application_name, "key_high": key_high, "key_low": key_low},
        ).scalar_one()
        waiting = connection.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_locks l "
                "JOIN pg_stat_activity a ON a.pid = l.pid "
                "WHERE a.application_name = :application_name "
                "AND a.datname = current_database() "
                "AND l.locktype = 'advisory' AND l.classid = :key_high "
                "AND l.objid = :key_low AND l.objsubid = 1 AND NOT l.granted)"
            ),
            {"application_name": application_name, "key_high": key_high, "key_low": key_low},
        ).scalar_one()
    return activity, granted, waiting


def _login_attempt_index_exists(engine) -> bool:
    with engine.connect() as connection:
        return bool(
            connection.execute(
                text(
                    "SELECT to_regclass('public.ix_login_attempt_buckets_window') "
                    "IS NOT NULL"
                )
            ).scalar_one()
        )


def _wait_for_state(engine, application_name: str, expected: str, process):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail("Alembic process exited before its expected lock state; output withheld")
        activity, granted, waiting = _lock_state(engine, application_name)
        if activity is not None:
            wait_type, wait_event = activity
            if expected == "holder_blocked_on_table" and granted and (
                wait_type == "Lock" and wait_event == "relation"
            ):
                return
            if expected == "waiter_blocked_on_advisory" and waiting and (
                wait_type == "Lock" and wait_event == "advisory"
            ):
                return
        time.sleep(0.05)
    pytest.fail(f"Alembic process did not reach expected state {expected}; output withheld")


def _finish_successfully(process):
    try:
        _stdout, _stderr = process.communicate(timeout=45)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=5)
        pytest.fail("Alembic subprocess timed out; output withheld")
    assert process.returncode == 0, "Alembic subprocess failed; output withheld"


def _terminate(process):
    if process is not None and process.poll() is None:
        process.kill()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def test_concurrent_alembic_processes_serialize_before_revision_lookup(
    postgres_test_engine,
):
    engine = postgres_test_engine
    assert _run_alembic(f"ecs-p23-down-{uuid4().hex[:8]}", "downgrade", PARENT_REVISION) == 0
    assert _current_revision(engine) == PARENT_REVISION
    assert not _login_attempt_table_exists(engine)
    assert not _login_attempt_index_exists(engine)

    first_name = f"ecs-p23-first-{uuid4().hex[:8]}"
    second_name = f"ecs-p23-second-{uuid4().hex[:8]}"
    first = second = None
    gate = engine.connect()
    transaction = gate.begin()
    try:
        # Alembic acquires its advisory lock before reading alembic_version.
        # Blocking that read proves the first runner holds the advisory lock
        # while the second runner waits for it.
        gate.execute(text("LOCK TABLE alembic_version IN ACCESS EXCLUSIVE MODE"))

        first = _start_alembic(first_name, "upgrade", "head")
        _wait_for_state(engine, first_name, "holder_blocked_on_table", first)

        second = _start_alembic(second_name, "upgrade", "head")
        _wait_for_state(engine, second_name, "waiter_blocked_on_advisory", second)

        # The first runner owns the advisory lock while blocked on the table;
        # the second is observably waiting on that exact lock.
        transaction.commit()
        _finish_successfully(first)
        _finish_successfully(second)
    finally:
        if transaction.is_active:
            transaction.rollback()
        gate.close()
        _terminate(first)
        _terminate(second)

    assert _current_revision(engine) == HEAD_REVISION
    assert _login_attempt_table_exists(engine)
    assert _login_attempt_index_exists(engine)


def test_failed_migration_rolls_back_releases_lock_and_later_upgrade_succeeds(
    postgres_test_engine,
):
    engine = postgres_test_engine
    assert _run_alembic(f"ecs-p23-down-{uuid4().hex[:8]}", "downgrade", PARENT_REVISION) == 0
    assert _current_revision(engine) == PARENT_REVISION
    assert not _login_attempt_table_exists(engine)
    assert not _login_attempt_index_exists(engine)

    # A separately committed duplicate table makes the login-bucket migration
    # fail inside its Alembic transaction after acquiring the advisory lock.
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE login_attempt_buckets ("
                "identifier_hash VARCHAR(64) PRIMARY KEY, "
                "window_started_at TIMESTAMP WITH TIME ZONE NOT NULL, "
                "attempt_count INTEGER NOT NULL)"
            )
        )
    failed_name = f"ecs-p23-failure-{uuid4().hex[:8]}"
    retry_name = f"ecs-p23-retry-{uuid4().hex[:8]}"
    process = None
    try:
        process = _start_alembic(failed_name, "upgrade", "head")
        try:
            _stdout, _stderr = process.communicate(timeout=45)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
            pytest.fail("expected failing migration timed out; output withheld")
        assert process.returncode != 0
        assert _current_revision(engine) == PARENT_REVISION
        assert _login_attempt_table_exists(engine)
        assert not _login_attempt_index_exists(engine)

        # Removing only the injected test fault leaves this disposable target
        # at the parent revision, ready for a clean retry.
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE login_attempt_buckets"))
        assert _run_alembic(retry_name, "upgrade", "head") == 0
        assert _current_revision(engine) == HEAD_REVISION
        assert _login_attempt_table_exists(engine)
        assert _login_attempt_index_exists(engine)
    finally:
        _terminate(process)
        # Restore the disposable database to head if an assertion interrupted
        # the test after injecting the duplicate table.
        revision = _current_revision(engine)
        if revision == PARENT_REVISION:
            if _login_attempt_table_exists(engine):
                with engine.begin() as connection:
                    connection.execute(text("DROP TABLE login_attempt_buckets"))
            result = _run_alembic(
                f"ecs-p23-cleanup-{uuid4().hex[:8]}", "upgrade", "head"
            )
            assert result == 0, "disposable PostgreSQL cleanup upgrade failed; output withheld"
