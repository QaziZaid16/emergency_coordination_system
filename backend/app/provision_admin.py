"""Provision the first Super Admin directly in an already-migrated database."""

import argparse
import getpass
import os
import secrets
import sys
from pathlib import Path

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def write_credentials_file(path: Path, *, email: str, password: str) -> None:
    """Create a private, new-only local credential file (never overwrite)."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as credentials:
            credentials.write(f"email={email.strip().lower()}\npassword={password}\n")
            credentials.flush()
            os.fsync(credentials.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        path.unlink(missing_ok=True)
        raise


def validate_generated_credentials_target(environment: str, database_url: str) -> None:
    if environment.lower() != "development" or not database_url.lower().startswith("sqlite:"):
        raise SystemExit(
            "Generated credential files are allowed only for a development SQLite database."
        )


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
    parser.add_argument(
        "--credentials-file",
        type=Path,
        help="development only: save a generated one-time password to a new mode-0600 local file",
    )
    args = parser.parse_args()
    if args.credentials_file:
        validate_generated_credentials_target(
            settings.environment, settings.database_url
        )

    generated_file = args.credentials_file
    if generated_file:
        password = secrets.token_urlsafe(32)
        try:
            write_credentials_file(generated_file, email=args.email, password=password)
        except FileExistsError as error:
            raise SystemExit("Credentials file already exists; choose a new path.") from error
        except OSError as error:
            raise SystemExit("Could not securely create the credentials file.") from error
    else:
        if not sys.stdin.isatty() or not sys.stderr.isatty():
            raise SystemExit("Run this command from an interactive terminal to enter the password safely.")
        password = getpass.getpass("New Super Admin password (12+ characters): ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            raise SystemExit("Passwords did not match.")

    try:
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
    except BaseException:
        if generated_file:
            generated_file.unlink(missing_ok=True)
        raise
    print(f"Created Super Admin {account.email} (role: {account.role}).")
    if generated_file:
        print(f"One-time credentials saved in the private file: {generated_file}")


if __name__ == "__main__":
    main()
