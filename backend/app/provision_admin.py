"""Provision the first Super Admin directly in an already-migrated database."""

import argparse
import getpass
import sys

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def provision_super_admin(
    db: Session, *, email: str, display_name: str, password: str
) -> User:
    if db.scalar(select(User).where(User.role == "super_admin")):
        raise ValueError("A Super Admin already exists; bootstrap is one-time only.")
    try:
        normalized_email = validate_email(
            email.strip(), check_deliverability=False
        ).normalized.lower()
    except EmailNotValidError as error:
        raise ValueError("Enter a valid administrator email address.") from error
    if not display_name.strip() or len(display_name.strip()) > 120:
        raise ValueError("Display name must contain 1–120 characters.")
    if db.scalar(select(User).where(User.email == normalized_email)):
        raise ValueError("An account with this email already exists.")
    if len(password) < 12 or len(password) > 128:
        raise ValueError("Password must contain 12–128 characters.")
    account = User(
        email=normalized_email,
        display_name=display_name.strip(),
        password_hash=hash_password(password),
        role="super_admin",
        permissions=[],
        active=True,
    )
    db.add(account)
    db.flush()
    return account


def main() -> None:
    settings = get_settings()
    if settings.environment.lower() not in {"development", "production"}:
        raise SystemExit("Admin provisioning is disabled in this environment.")
    if settings.environment.lower() == "production" and not settings.database_url.startswith(
        "postgresql+psycopg://"
    ):
        raise SystemExit("Production admin provisioning requires PostgreSQL.")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    args = parser.parse_args()
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise SystemExit("Run this command from an interactive terminal to enter the password safely.")
    password = getpass.getpass("New Super Admin password (12+ characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords did not match.")

    with SessionLocal.begin() as db:
        if db.get_bind().dialect.name == "postgresql":
            # Serialize concurrent bootstrap attempts across processes.
            db.execute(text("SELECT pg_advisory_xact_lock(827364510219)"))
        account = provision_super_admin(
            db,
            email=args.email,
            display_name=args.display_name,
            password=password,
        )
    print(f"Created Super Admin {account.email} (role: {account.role}).")


if __name__ == "__main__":
    main()
