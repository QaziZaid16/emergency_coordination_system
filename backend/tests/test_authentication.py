from uuid import uuid4

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.security import verify_password


def _register(client, email, password="Synthetic-Password-1234", **extra):
    return client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Synthetic Test User",
            "email": email,
            "password": password,
            **extra,
        },
    )


def test_public_registration_hashes_password_and_issues_user_session(client):
    email = f"auth-{uuid4().hex}@example.org"
    password = "Synthetic-Password-1234"

    response = _register(client, email.upper(), password, remember_me=True)

    assert response.status_code == 201
    result = response.json()
    assert result["user"]["email"] == email
    assert result["user"]["role"] == "user"
    assert result["refresh_token"]
    assert "password_hash" not in result["user"]
    assert "password" not in result["user"]
    with SessionLocal() as db:
        account = db.scalar(select(User).where(User.email == email))
        assert account is not None
        assert account.role == "user"
        assert account.password_hash != password
        assert verify_password(password, account.password_hash)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email.upper(), "password": password, "remember_me": True},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["role"] == "user"
    assert client.get("/api/v1/admin/dashboard", headers=headers).status_code == 403


def test_registration_validates_email_password_and_duplicate_email(client):
    email = f"duplicate-{uuid4().hex}@example.org"
    first = _register(client, email)
    assert first.status_code == 201

    duplicate = _register(client, email.upper())
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "An account with this email already exists"

    invalid_email = _register(client, "not-an-email")
    assert invalid_email.status_code == 422
    short_password = _register(client, f"short-{uuid4().hex}@example.org", "short")
    assert short_password.status_code == 422
    long_password = _register(
        client, f"long-{uuid4().hex}@example.org", "x" * 129
    )
    assert long_password.status_code == 422


def test_public_registration_cannot_assign_a_privileged_role(client):
    email = f"role-{uuid4().hex}@example.org"
    response = _register(client, email, role="super_admin")

    assert response.status_code == 201
    assert response.json()["user"]["role"] == "user"
    token = response.json()["access_token"]
    assert (
        client.get(
            "/api/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 403
    )


def test_login_errors_do_not_disclose_account_existence(client):
    email = f"login-{uuid4().hex}@example.org"
    assert _register(client, email).status_code == 201

    known_account = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Incorrect-Synthetic-1234"},
    )
    unknown_account = client.post(
        "/api/v1/auth/login",
        json={
            "email": f"missing-{uuid4().hex}@example.org",
            "password": "Incorrect-Synthetic-1234",
        },
    )

    assert known_account.status_code == unknown_account.status_code == 401
    assert known_account.json() == unknown_account.json()


def test_logout_revokes_the_access_session(client):
    email = f"logout-{uuid4().hex}@example.org"
    registration = _register(client, email)
    token = registration.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
