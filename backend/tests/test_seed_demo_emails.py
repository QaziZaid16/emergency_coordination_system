from pydantic import EmailStr, TypeAdapter

from app.database import SessionLocal
from app.models import User
from app.security import hash_password
from app.seed_demo import DEMO_ACCOUNTS, RESPONDERS, _demo_user


def test_demo_seed_accounts_pass_login_email_validation():
    validate_email = TypeAdapter(EmailStr).validate_python

    seeded_emails = [email for _key, email, _display_name in DEMO_ACCOUNTS]
    seeded_emails.extend(
        f"demo.responder{number:02d}@example.org"
        for number in range(1, RESPONDERS + 1)
    )

    assert all(validate_email(email) == email for email in seeded_emails)


def test_legacy_demo_user_address_migrates_without_resetting_password(client):
    password = "demo-seed-password-123"
    with SessionLocal.begin() as db:
        account = User(
            email="demo.user@example.test",
            display_name="Demo Caller",
            password_hash=hash_password(password),
            role="user",
            permissions=[],
            active=True,
        )
        db.add(account)
        db.flush()
        account_id = account.id
        password_hash_before = account.password_hash

    with SessionLocal.begin() as db:
        account = _demo_user(db, "demo.user@example.org")
        assert account is not None
        assert account.id == account_id
        assert account.password_hash == password_hash_before

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "demo.user@example.org", "password": password},
    )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "demo.user@example.org"
