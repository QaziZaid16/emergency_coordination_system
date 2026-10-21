# Shared coordination API

This directory contains the executable FastAPI service, its SQLAlchemy models, an initial Alembic migration, role/ownership checks, and the local API tests. Flutter's authenticated Admin, User, and Responder portals use this same API. The older local coordinator/responder workspace remains an isolated training mode and is not imported into the server database.

This is a development implementation. Do not connect it to emergency operations or expose it to the public Internet until the deployment, privacy, reliability, security, and operational reviews in the root README are complete.

## Local development with SQLite

Requirements: Python 3.12 or newer.

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Edit `backend/.env`. Keep `ENVIRONMENT=development`, use the example SQLite URL, and set a fresh random JWT secret. Generate secrets with `python -c 'import secrets; print(secrets.token_hex(32))'`. Do not commit `.env`.

Create/update the local schema and provision the first administrator through the password-prompting CLI:

```sh
alembic upgrade head
python -m app.provision_admin --email admin@example.org --name 'Operations Admin'
```

Run the service:

```sh
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The OpenAPI interface is at `http://127.0.0.1:8000/docs`; liveness and database readiness are `/health/live` and `/health/ready`. Public user registration creates only the `user` role. The first admin is provisioned separately; an admin creates responder accounts and their capabilities from the Admin Portal.

Run the backend workflow suite:

```sh
python -m pytest -q
```

Tests use an in-memory SQLite database. SQLite is convenient for local development and tests; it is not the production concurrency target.

## Connect the Flutter app

Build a development APK with the API host compiled into the app:

```sh
cd ..
flutter build apk --debug --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

For a USB-connected Android device while the API runs on the same development computer, use Android Platform Tools:

```sh
adb reverse tcp:8000 tcp:8000
flutter run -d <device-serial> --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

The manifest permits cleartext HTTP only in Android debug builds to support this loopback development setup. Release builds explicitly disallow cleartext and must use a real HTTPS API endpoint:

```sh
flutter build apk --release --dart-define=API_BASE_URL=https://api.example.org
```

No API URL is hardcoded into the repository. If it is omitted, the app still opens the local Training Workspace; the three authenticated portals show that shared service configuration is missing and do not pretend to log in.

## PostgreSQL with Compose

Docker Compose is provided for a local PostgreSQL 17 development service. Docker is not bundled with this repository. Copy `.env.example` to `.env`, generate unique `JWT_SECRET` and `POSTGRES_PASSWORD` values, and set `ENVIRONMENT=production` to exercise the deployment code path locally. The compose API port binds to `127.0.0.1` only.

```sh
docker compose up -d db
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.provision_admin --email admin@example.org --name 'Operations Admin'
docker compose up -d api
```

The example Compose file does not terminate TLS or provide production-grade secrets, backups, monitoring, scaling, or rate limiting. Put deployment behind an HTTPS reverse proxy and keep the database on a private network before connecting a release client. Docker/PostgreSQL execution was unavailable in the development environment used for this implementation; only SQLite migrations and tests were run here.

## Security and behavior

- Passwords use Argon2 through `pwdlib`; bearer JWTs expire after the configured interval and each token has a server-side revocable session row. Logout revokes the row. Deactivating an account revokes its sessions.
- Portal selection is included in login and must match the stored server role. Authorization is checked on each protected route.
- Users see only their own incidents. Responders see current assignments and their own completed task history; a reassigned responder cannot update the old task. Admin-only resources, accounts, dashboard, assignments, and audit routes reject other roles.
- Only an admin can assign/reassign. Availability, skill capability, current workload, and resource capacity are checked in a transaction. Partial unique database indexes prevent one active responder or incident from having conflicting active assignments. Conflicts return `409`.
- SOS submission requires a per-request `Idempotency-Key`. GPS coordinates require a paired latitude/longitude and a timestamp no older than 15 minutes; the API rejects stale/future GPS. Manual text locations are allowed without coordinates and are never replaced with simulated coordinates.
- Distance recommendations are included only when both caller and responder locations are recent (15 minutes), recorded with accuracy of at most 100 m, and present. They use straight-line distance, not road routing or ETA.
- Clients poll authorized incident state every 12 seconds. No WebSocket, push provider, maps, emergency call, ambulance/fire/police agency, or external dispatch integration is configured.
- The priority function mirrors the existing prototype formula; it is not a validated triage policy.
