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
python -m app.provision_admin --email admin@example.org --display-name 'Operations Admin'
```

Run the service:

```sh
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The OpenAPI interface is at `http://127.0.0.1:8000/docs`; liveness and database readiness are `/health/live` and `/health/ready`. Public user registration creates only the `user` role. Host the complete `web/` directory as one static site: open `/admin/`, and serve `/activate.html` for invitation links. The dashboard uses this same API/database. Configure `ECS_API_BASE_URL` for the hosted static build, or enter a local development URL at sign-in; include the site's origin in `CORS_ORIGINS`.

To add a repeatable local demo dataset, run `python -m app.seed_demo --confirm-demo-seed` while `ENVIRONMENT=development` and `DATABASE_URL` points to SQLite. The command refuses other environments and database engines, creates 50 synthetic responders and ten assigned sample incidents, and is safe to repeat. First-run generated demo passwords are printed once; see [`docs/DEMO_ACCOUNTS.md`](../docs/DEMO_ACCOUNTS.md). Never seed production data.

## Administration, Co-Admins, and responder invitations

Run `alembic upgrade head` after updating. Only a Super Admin can create Co-Admins or change their explicit permissions. The API checks each permission on every request, so permission revocation also applies to active sessions. A Co-Admin starts with no permissions unless the Super Admin grants them. The dashboard supports live incident/responder/resource views, assignment, invitation, audit review, and Co-Admin permission editing.

The permissions migration promotes the oldest active legacy `admin` account to `super_admin` so an existing installation retains one usable root account; other legacy admins receive no Co-Admin permissions until a Super Admin grants them. The one-time bootstrap CLI creates the initial Super Admin only after migrations; it does not create tables or print the password. Production configuration requires PostgreSQL and HTTPS dashboard/activation origins.

Responder onboarding creates an inactive responder and a hashed, single-use token valid for 24 hours. Invitation creation/resend is limited to five attempts per administrator per hour in this single-process development service. Set `PUBLIC_APP_URL` to the deployed client origin. Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM` to deliver invitation email. In development only, when SMTP is absent, the API returns an activation URL to the authenticated administrator; production requires HTTPS and treats missing or failed email delivery as an error without reporting the invite as sent. Serve `web/activate.html` at the configured public app URL. Passwords are established by the responder during activation. Use a shared gateway or datastore rate limiter, account recovery flow, and MFA before public production deployment.

Mobile login no longer asks for a role or portal. The API returns the account's stored role; users and responders open their respective portals, while admin accounts receive a dashboard-only message in the mobile client.

The legacy direct administrator endpoint refuses responder creation; responder accounts must use the invitation and activation flow.

## In-app notifications and automatic assignment

Apply the new migration with `alembic upgrade head`. The authenticated `GET /api/v1/notifications` endpoint returns only the current account's persistent in-app events. Mark one with `PATCH /api/v1/notifications/{id}/read` or all with `PATCH /api/v1/notifications/read-all`. Notification writes are part of the incident/assignment/status transaction and are idempotent per account/event key. This is not push or email delivery.

`GET /api/v1/admin/automation` reports the coordination policy. Only a Super Admin may `PUT` that endpoint with `{"enabled": true, "max_severity": 3}`. It defaults disabled. When enabled, it uses deterministic eligible-responder checks and the configured distance/workload ranking weights. Both incident and responder GPS must be ≤100 m accuracy and ≤15 minutes old; capability, active account, availability, no existing active task, and configured severity ceiling also apply. Otherwise the case stays unassigned for review. Assignment source and the algorithm decision are visible in incident data/audit. The same transaction and existing database uniqueness indexes protect assignment state; a conflict leaves the incident recorded as unassigned and emits a coordinator review event.

The policy's demo default is severity 3/5. This is a configurable academic example, not an emergency triage rule. The service still has no FCM, device tokens, remote notification delivery attempts, or notification email provider.

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
# Set API_BASE_URL to the actual deployed HTTPS origin first.
sh scripts/build_android_release.sh
```

No API URL is hardcoded into the mobile application. If it is omitted, the app opens its direct login form and explains sign-in unavailability only after a sign-in attempt. API URL validation rejects malformed URLs, placeholders, non-HTTPS release URLs, and non-loopback debug HTTP. The isolated training workspace appears only in a debug build that explicitly sets `ENABLE_TRAINING_WORKSPACE=true`.

## PostgreSQL with Compose

Docker Compose is provided for a local PostgreSQL 17 development service. Docker is not bundled with this repository. Copy `.env.example` to `.env`, generate unique `JWT_SECRET` and `POSTGRES_PASSWORD` values, and keep `ENVIRONMENT=development`. Production settings require real HTTPS origins and are validated separately in the automated suite. The compose API port binds to `127.0.0.1` only.

```sh
docker compose up -d db
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose run --rm -it api python -m app.provision_admin --email admin@example.org --display-name 'Operations Admin'
docker compose up -d api
```

The example Compose file does not terminate TLS or provide production-grade secrets, backups, monitoring, scaling, or rate limiting. Put deployment behind an HTTPS reverse proxy and keep the database on a private network before connecting a release client. Docker/PostgreSQL execution was unavailable in the development environment used for this implementation; only SQLite migrations and tests were run here.

## Security and behavior

- Passwords use Argon2 through `pwdlib`; registration, invitations, admin account creation, and login all enforce the existing 12-character minimum. This is stricter than the prompt's eight-character floor and preserves the established create-account policy. Access JWTs expire after `ACCESS_TOKEN_MINUTES` (30 by default). If the user opts into Remember Me, login/register also returns a high-entropy opaque refresh token. Only its SHA-256 hash is stored server-side; refresh rotates the credential and the session expires after `REMEMBER_ME_DAYS` (30 by default, configurable 1–365). The client stores credentials only in secure storage and validates the session at startup. Logout revokes the row; deactivation revokes sessions. There is no email recovery, MFA, or rate limiting yet.
- Portal selection is included in login and must match the stored server role. Authorization is checked on each protected route.
- Users see only their own incidents. Responders see current assignments and their own completed task history; a reassigned responder cannot update the old task. Admin-only resources, accounts, dashboard, assignments, and audit routes reject other roles.
- Only an admin can assign/reassign. Availability, skill capability, current workload, and resource capacity are checked in a transaction. Partial unique database indexes prevent one active responder or incident from having conflicting active assignments. Conflicts return `409`.
- SOS submission requires a per-request `Idempotency-Key`. GPS coordinates require a paired latitude/longitude and a timestamp no older than 15 minutes; the API rejects stale/future GPS. Manual text locations are allowed without coordinates and are never replaced with simulated coordinates.
- Distance recommendations are included only when both caller and responder locations are recent (15 minutes), recorded with accuracy of at most 100 m, and present. They use straight-line distance, not road routing or ETA.
- Clients poll authorized incident state every 12 seconds. No WebSocket, push provider, maps, emergency call, ambulance/fire/police agency, or external dispatch integration is configured.
- The priority function mirrors the existing prototype formula; it is not a validated triage policy.
- Incident submissions persist immediately with a pending `incident_analyses` work record in the same database transaction. A FastAPI background task processes new work; a database-polling worker recovers pending or stale-processing jobs after restart. Analysis attempts and a safe failure category are persisted; stale processing is recovered after five minutes and stopped after three interrupted attempts until an administrator requests retry. Automatic assignment is separately evaluated and persisted in the incident transaction. The default `AI_PROVIDER=none` uses a deterministic source-text baseline. It retains the caller-selected category, surfaces only matched terms, and never changes priority or assignment. For OpenRouter, set `AI_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, and optionally `OPENROUTER_MODEL` / `OPENROUTER_BASE_URL`; the requested model default is `google/gemma-4-31b-it`. The async client requests strict JSON-schema output, has a bounded timeout and retries only explicit transient HTTP statuses (a timeout is not retried because the provider may have processed/billed it), and validates evidence against the original report. Invalid, rate-limited, or failed responses fall back to local analysis. The request-rate limit is process-local and needs a shared gateway for multiple workers. Report text is sent to OpenRouter; location text is excluded unless `AI_SHARE_INCIDENT_LOCATION=true`, and coordinates are never sent. Inference may cost money. The key is server-only and no key is configured in this repository.
- Validated analysis metadata/results are stored separately in `incident_analyses`; incident data and the original report remain unchanged. Admin and currently assigned responders can see decision support; callers do not receive internal analysis. Model/vendor logs omit report content. Review the configured database retention and provider retention terms before operational use.
- Admin recommendations deterministically filter active, available, capability-matched, non-busy responders and rank eligible people by configurable distance/capability/recent-workload weights. Fresh GPS is used only if both readings are accurate to 100 m and no older than 15 minutes. Missing GPS gives no distance score, never a fake ETA. The admin explicitly chooses; assignment revalidates and commits transactionally. Compatible resource types are filtered for the recommendation and checked again during assignment.
- Admin Copilot uses fixed, read-only query intents for incident counts/refs, responder availability, resource totals, and reference lookup. It is rules-based (no model or arbitrary SQL) and includes source records where relevant. It cannot mutate operations.
- Possible duplicate reports are identified through category, word overlap, time window, and reliable proximity signals. Candidates are review-only; originals are never discarded or merged automatically.
- The recommendation scoring weights default to distance 45, capability match 35, recent completed workload 20. These are transparent prototype weights, not validated dispatch policy. There is not enough verified history to forecast demand; the copilot provides descriptive current-data summaries only.
