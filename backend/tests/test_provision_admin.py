import os

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.provision_admin import (
    provision_super_admin,
    validate_generated_credentials_target,
    write_credentials_file,
)
from app.security import verify_password


def test_bootstrap_account_authenticates_with_super_admin_role(client):
    with SessionLocal.begin() as db:
        account = provision_super_admin(
            db,
            email=" First.Admin@example.com ",
            display_name="First Admin",
            password="Correct-Horse-5678",
        )
        account_id = account.id
        assert account.role == "super_admin"
        assert account.email == "first.admin@example.com"
        assert account.password_hash != "Correct-Horse-5678"
        assert verify_password("Correct-Horse-5678", account.password_hash)

    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.id == account_id)).role == "super_admin"
        with pytest.raises(ValueError, match="one-time"):
            provision_super_admin(
                db,
                email="second.admin@example.test",
                display_name="Second Admin",
                password="Correct-Horse-5678",
            )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "first.admin@example.com", "password": "Correct-Horse-5678"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "super_admin"
    invalid = client.post(
        "/api/v1/auth/login",
        json={"email": "first.admin@example.com", "password": "Incorrect-Horse-5678"},
    )
    assert invalid.status_code == 401


def test_bootstrap_rejects_short_password(client):
    with SessionLocal.begin() as db:
        with pytest.raises(ValueError, match="12–128"):
            provision_super_admin(
                db,
                email="short@example.com",
                display_name="Short Password",
                password="short",
            )


def test_generated_credentials_file_is_private_and_never_overwritten(tmp_path):
    path = tmp_path / "initial-admin.txt"
    write_credentials_file(
        path,
        email="Admin@example.org",
        password="one-time-test-password",
    )

    assert path.read_text() == (
        "email=admin@example.org\npassword=one-time-test-password\n"
    )
    assert os.stat(path).st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_credentials_file(path, email="other@example.org", password="replacement")
    assert "replacement" not in path.read_text()


def test_generated_credentials_are_limited_to_development_sqlite():
    validate_generated_credentials_target("development", "sqlite:///./local.db")
    with pytest.raises(SystemExit, match="development SQLite"):
        validate_generated_credentials_target("production", "postgresql+psycopg://db")
    with pytest.raises(SystemExit, match="development SQLite"):
        validate_generated_credentials_target("development", "postgresql+psycopg://db")
