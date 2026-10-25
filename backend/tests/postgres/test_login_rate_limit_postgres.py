"""Shared login throttling across isolated API processes on PostgreSQL."""

from __future__ import annotations

import multiprocessing
from queue import Empty
from uuid import uuid4

from sqlalchemy import delete, select

from app.api import _login_identifier_hash
from app.models import AuthSession, LoginAttemptBucket, User


def _login_process(email, start_barrier, results):
    """Send one failed login through an isolated process-local ASGI app."""
    from fastapi.testclient import TestClient

    import app.api as api
    from app.main import app as application

    # Keep this concurrency check focused on the shared database throttle and
    # avoid spending CPU/memory on password hashing in eleven child processes.
    api.verify_password = lambda *_args: False
    try:
        start_barrier.wait(timeout=30)
        with TestClient(application) as client:
            response = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "invalid-synthetic-password"},
            )
        results.put(response.status_code)
    except BaseException as exc:
        results.put(("error", type(exc).__name__))


def test_login_throttle_is_shared_across_independent_api_processes(
    postgres_test_sessions,
):
    sessions = postgres_test_sessions
    context = multiprocessing.get_context("spawn")
    email = f"pg-login-{uuid4().hex}@example.test"
    user_id = None
    identifier_hash = _login_identifier_hash(email)
    with sessions.begin() as db:
        user = User(
            email=email,
            display_name="PostgreSQL login-throttle test",
            password_hash="unused-by-mocked-verification",
            role="user",
            permissions=[],
        )
        db.add(user)
        db.flush()
        user_id = user.id

    process_count = 11  # Ten failures are allowed; the next receives 429.
    barrier = context.Barrier(process_count)
    results = context.Queue()
    processes = [
        context.Process(target=_login_process, args=(email, barrier, results))
        for _ in range(process_count)
    ]
    try:
        for process in processes:
            process.start()
        statuses = []
        for process in processes:
            process.join(timeout=45)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                raise AssertionError("PostgreSQL login process timed out")
            assert process.exitcode == 0
        try:
            statuses = [results.get(timeout=5) for _ in processes]
        except Empty as exc:
            raise AssertionError("A PostgreSQL login process returned no result") from exc

        assert all(isinstance(status, int) for status in statuses), statuses
        assert statuses.count(401) == 10
        assert statuses.count(429) == 1
        with sessions() as db:
            bucket = db.get(LoginAttemptBucket, identifier_hash)
            assert bucket is not None
            assert bucket.attempt_count == process_count
            assert db.scalar(
                select(AuthSession.jti).where(AuthSession.user_id == user_id)
            ) is None
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        results.close()
        results.join_thread()
        with sessions.begin() as db:
            db.execute(
                delete(LoginAttemptBucket).where(
                    LoginAttemptBucket.identifier_hash == identifier_hash
                )
            )
            db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
            db.execute(delete(User).where(User.id == user_id))
