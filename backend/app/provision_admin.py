import argparse
from getpass import getpass

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def main():
    parser = argparse.ArgumentParser(description="Provision the first administrator account")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    password = getpass("Admin password (12+ characters): ")
    confirm = getpass("Confirm password: ")
    if len(password) < 12 or password != confirm:
        raise SystemExit("Passwords must match and contain at least 12 characters.")
    with SessionLocal() as db:
        email = args.email.strip().lower()
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("That account already exists; provisioning did not change it.")
        existing_super_admin = db.scalar(select(User).where(User.role == "super_admin", User.active.is_(True)))
        role = "admin" if existing_super_admin else "super_admin"
        account = User(email=email, display_name=args.name.strip(), password_hash=hash_password(password), role=role, permissions=[])
        db.add(account)
        db.commit()
    print(f"{role.replace('_', ' ').title()} provisioned for {email}. Store the password in your approved secret manager.")


if __name__ == "__main__":
    main()
