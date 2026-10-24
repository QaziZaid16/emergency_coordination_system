"""Create a repeatable local-only demonstration dataset.

Never call this from application startup or a production migration. New demo
passwords are generated at creation time, hashed immediately, and printed once.
"""

import argparse
import secrets
from datetime import timedelta

from sqlalchemy import select

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import Assignment, Incident, ResponderProfile, Resource, User, now_utc
from app.security import hash_password

RESPONDERS = 50
OFF_DUTY_RESPONDERS = {2, 3, 4, 5, 7, 8, 9, 10, 12, 13, 14, 15}
SERVICE_CAPABILITIES = (
    [["medical", "ambulance"] for _ in range(10)]
    + [["fire", "rescue"] for _ in range(10)]
    + [["rescue", "search"] for _ in range(10)]
    + [["security", "police"] for _ in range(10)]
    + [["other", "technical"] for _ in range(10)]
)
DEMO_ACCOUNTS = (
    ("admin", "demo.admin@example.org", "Demo Super Admin"),
    ("coadmin", "demo.coadmin@example.org", "Demo Co-Admin"),
    ("user", "demo.user@example.org", "Demo Caller"),
)


def new_password() -> str:
    # url-safe output is 32 characters and never written to the database.
    return secrets.token_urlsafe(24)


def _demo_user(db, email: str) -> User | None:
    account = db.scalar(select(User).where(User.email == email))
    if account is None and email.endswith("@example.org"):
        # Preserve logins created by older seeds while moving from .test,
        # which the API's EmailStr login validation correctly rejects.
        legacy_email = email.removesuffix("@example.org") + "@example.test"
        account = db.scalar(select(User).where(User.email == legacy_email))
        if account is not None:
            account.email = email
    return account


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-demo-seed",
        action="store_true",
        help="confirm that synthetic records should be added to this local database",
    )
    args = parser.parse_args()
    settings = get_settings()
    if settings.environment.lower() != "development":
        raise SystemExit("Demo seeding is allowed only with ENVIRONMENT=development.")
    if engine.dialect.name != "sqlite":
        raise SystemExit("Demo seeding is limited to a local SQLite database.")
    if not args.confirm_demo_seed:
        raise SystemExit("Pass --confirm-demo-seed to add development-only records.")

    Base.metadata.create_all(bind=engine)
    generated_credentials: list[tuple[str, str, str]] = []
    with SessionLocal.begin() as db:
        accounts: dict[str, User] = {}
        for key, email, display_name in DEMO_ACCOUNTS:
            account = _demo_user(db, email)
            if account is None:
                password = new_password()
                account = User(
                    email=email,
                    display_name=display_name,
                    password_hash=hash_password(password),
                    role={"admin": "super_admin", "coadmin": "admin", "user": "user"}[key],
                    permissions=["view_dashboard"] if key == "coadmin" else [],
                    active=True,
                )
                db.add(account)
                db.flush()
                generated_credentials.append((key, email, password))
            accounts[key] = account

        responder_users: list[User] = []
        for number in range(1, RESPONDERS + 1):
            email = f"demo.responder{number:02d}@example.org"
            account = _demo_user(db, email)
            if account is None:
                password = new_password()
                account = User(
                    email=email,
                    display_name=f"Synthetic Responder {number:02d}",
                    password_hash=hash_password(password),
                    role="responder",
                    active=True,
                )
                db.add(account)
                db.flush()
                if number == 1:
                    generated_credentials.append(("responder", email, password))
            responder_users.append(account)
            profile = db.get(ResponderProfile, account.id)
            if profile is None:
                profile = ResponderProfile(
                    user_id=account.id,
                    capabilities=SERVICE_CAPABILITIES[number - 1],
                    available=number not in OFF_DUTY_RESPONDERS,
                    latitude=None,
                    longitude=None,
                    location_accuracy_m=None,
                    location_at=None,
                )
                db.add(profile)

        # Ten responders receive genuine assignment rows so dashboard workload
        # and the database uniqueness rules are real. Seed reruns leave states
        # that an operator has since changed intact.
        caller = accounts["user"]
        admin = accounts["admin"]
        for number in range(1, 11):
            reference = f"DEMO-{number:04d}"
            incident = db.scalar(select(Incident).where(Incident.reference == reference))
            if incident is None:
                created = now_utc() - timedelta(hours=number * 2)
                incident = Incident(
                    reference=reference,
                    reporter_id=caller.id,
                    emergency_type=(
                        "Ambulance / Medical Emergency"
                        if (number - 1) // 2 == 0
                        else "Fire and Rescue"
                        if (number - 1) // 2 == 1
                        else "Fire and Rescue"
                        if (number - 1) // 2 == 2
                        else "Police / Security"
                        if (number - 1) // 2 == 3
                        else "Other Emergency"
                    ),
                    description=f"Synthetic demonstration report {number:02d}.",
                    location_label=f"Simulated Sector {60 + number}, Mohali",
                    location_source="manual",
                    latitude=None,
                    longitude=None,
                    accuracy_m=None,
                    location_at=None,
                    severity=2 + number % 4,
                    urgency=2 + number % 4,
                    priority="High" if number % 3 == 0 else "Medium",
                    priority_reason="Synthetic demonstration value; not a triage recommendation.",
                    status="Assigned",
                    idempotency_key=f"demo-seed-{number:04d}",
                    created_at=created,
                    updated_at=created,
                )
                db.add(incident)
                db.flush()
            service_group = (number - 1) // 2
            responder = responder_users[service_group * 10 + (number - 1) % 2 * 5]
            assignment = db.scalar(
                select(Assignment).where(
                    Assignment.incident_id == incident.id,
                    Assignment.responder_id == responder.id,
                )
            )
            if assignment is None:
                db.add(
                    Assignment(
                        incident_id=incident.id,
                        responder_id=responder.id,
                        assigned_by=admin.id,
                        status="Assigned",
                        assigned_at=incident.created_at,
                    )
                )
                db.get(ResponderProfile, responder.id).available = False

        resource = db.scalar(select(Resource).where(Resource.name == "DEMO Medical Unit"))
        if resource is None:
            db.add(Resource(name="DEMO Medical Unit", kind="medical", quantity=3, allocated=0, active=True))

    print("Local demo seed completed. Existing demo accounts and records were retained.")
    print("Fifty synthetic responders are present; no simulated GPS is included in their profiles.")
    if generated_credentials:
        print("\nNew development-only login credentials (copy now; passwords are not retrievable):")
        for role, email, password in generated_credentials:
            print(f"{role}: {email}  password: {password}")
    else:
        print("No credentials were generated. Existing passwords are unchanged and cannot be recovered by this command.")


if __name__ == "__main__":
    main()
