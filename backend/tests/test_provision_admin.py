import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.provision_admin import provision_super_admin
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


def test_bootstrap_rejects_short_password(client):
    with SessionLocal.begin() as db:
        with pytest.raises(ValueError, match="12–128"):
            provision_super_admin(
                db,
                email="short@example.com",
                display_name="Short Password",
                password="short",
            )
