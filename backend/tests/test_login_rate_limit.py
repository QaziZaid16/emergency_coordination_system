from uuid import uuid4

import pytest
from sqlalchemy import select

import app.api as api
from app.database import SessionLocal
from app.api import _login_identifier_hash
from app.models import AuthSession, LoginAttemptBucket, User
from app.security import hash_password


PASSWORD = "Synthetic-login-password-1234"


def _create_account(role="user"):
    with SessionLocal.begin() as db:
        account = User(
            email=f"login-{uuid4().hex}@example.org",
            display_name=f"Synthetic {role}",
            password_hash=hash_password(PASSWORD),
            role=role,
            permissions=[],
        )
        db.add(account)
        db.flush()
        return account.email, account.id


def _login(client, email, password=PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


def test_repeated_failed_logins_are_limited_without_account_disclosure(client):
    email, _ = _create_account()

    first_failure = _login(client, email, "incorrect-password")
    missing_account = _login(
        client, f"missing-{uuid4().hex}@example.org", "incorrect-password"
    )
    assert first_failure.status_code == missing_account.status_code == 401
    assert first_failure.json() == missing_account.json() == {
        "detail": "Email or password is incorrect"
    }

    for _ in range(9):
        response = _login(client, email, "incorrect-password")
        assert response.status_code == 401
        assert response.json() == first_failure.json()

    limited = _login(client, email)
    assert limited.status_code == 429
    assert limited.json() == {
        "detail": "Too many login attempts. Try again later."
    }


def test_limit_is_per_identifier_and_success_clears_its_bucket(client):
    limited_email, _ = _create_account()
    other_email, _ = _create_account()

    for _ in range(10):
        assert _login(client, limited_email, "incorrect-password").status_code == 401

    allowed = _login(client, other_email)
    assert allowed.status_code == 200
    assert allowed.json()["user"]["role"] == "user"
    assert client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {allowed.json()['access_token']}"},
    ).status_code == 200

    # A valid login before the threshold removes only its own failure bucket.
    recovering_email, recovering_id = _create_account()
    for _ in range(3):
        assert _login(client, recovering_email, "incorrect-password").status_code == 401
    successful = _login(client, recovering_email)
    assert successful.status_code == 200
    with SessionLocal() as db:
        assert db.scalar(
            select(LoginAttemptBucket.identifier_hash).where(
                LoginAttemptBucket.identifier_hash == _login_identifier_hash(recovering_email)
            )
        ) is None
        assert db.scalar(
            select(AuthSession.jti).where(AuthSession.user_id == recovering_id)
        ) is not None
        assert db.scalar(
            select(LoginAttemptBucket.identifier_hash).where(
                LoginAttemptBucket.identifier_hash == _login_identifier_hash(limited_email)
            )
        ) is not None


def test_success_does_not_clear_a_failure_reserved_while_it_was_verifying(
    client, monkeypatch
):
    email, _ = _create_account()
    identifier_hash = _login_identifier_hash(email)
    reserve = api._reserve_login_attempt

    def reserve_with_interleaved_failure(db, key):
        success_reservation = reserve(db, key)
        # Model another request reserving a failed attempt after this successful
        # request has reserved its count but before password verification ends.
        with SessionLocal() as concurrent_db:
            reserve(concurrent_db, key)
        return success_reservation

    monkeypatch.setattr(api, "_reserve_login_attempt", reserve_with_interleaved_failure)

    response = _login(client, email)

    assert response.status_code == 200
    with SessionLocal() as db:
        bucket = db.get(LoginAttemptBucket, identifier_hash)
        assert bucket is not None
        assert bucket.attempt_count == 2


@pytest.mark.parametrize("role", ["user", "responder", "admin", "super_admin"])
def test_successful_login_preserves_role_and_creates_session(client, role):
    email, account_id = _create_account(role)

    response = _login(client, email)

    assert response.status_code == 200
    assert response.json()["user"]["role"] == role
    token = response.json()["access_token"]
    current = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert current.status_code == 200
    assert current.json()["id"] == account_id
