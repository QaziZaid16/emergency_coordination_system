
# Emergency Coordination System

A Flutter-based Android client, a static browser coordinator dashboard, and a FastAPI service for an **academic emergency-coordination demonstration**.

> **Demonstration software only. Do not use this system to report or coordinate a real emergency.** It does not contact emergency services or dispatch responders. Priority and responder recommendations are prototype decision support, not validated triage or dispatch policy.

## Current status

The repository contains client and API implementations, migration history, tests, a local PostgreSQL Compose definition, and deployment templates. It has **no verified public deployment, connected hosting project, or approved operational database**. The checked-in Android APK is an older debug-signed artifact, not a release build.

Provider-off tests and local client checks pass in this workspace; that does not establish hosted behavior. The integration audit records one earlier successful Gemma adapter-level completion and earlier disposable PostgreSQL 17.11 migration/ownership results. Neither establishes live incident-to-analysis deployment or production readiness. See [the integration audit](docs/GEMMA_INTEGRATION_AUDIT.md).

The proposed local demo is limited to synthetic data and up to three phones on trusted Wi-Fi. It is **not ready to run**: database-volume ownership, backup/restore evidence, exact LAN/firewall scope, and separate runtime authorization remain open. Free cloud staging is now user-authorized but no provider project, persistent database, public URL, or deployment has been configured or verified. Production remains **NO-GO**.

## Contents

- [Capabilities and verification status](#capabilities-and-verification-status)
- [Architecture](#architecture)
- [Repository map](#repository-map)
- [Prerequisites](#prerequisites)
- [Local development setup](#local-development-setup)
- [Configuration reference](#configuration-reference)
- [Running the components](#running-the-components)
- [HTTP API reference](#http-api-reference)
- [Data model and migrations](#data-model-and-migrations)
- [End-to-end workflows](#end-to-end-workflows)
- [Testing and validation](#testing-and-validation)
- [Security, privacy, and safety](#security-privacy-and-safety)
- [Troubleshooting](#troubleshooting)
- [Contribution workflow](#contribution-workflow)
- [Deployment and operations](#deployment-and-operations)
- [Limitations and deferred work](#limitations-and-deferred-work)
- [Further documentation](#further-documentation)

## Capabilities and verification status

| Capability | Implementation | Evidence and limits |
|---|---|---|
| User, responder, Super Admin, and scoped Co-Admin portals | Flutter client and static JavaScript coordinator dashboard; FastAPI owns identity and authorization | Local workflow, API, and widget tests. No hosted login verified. |
| Incident intake and persistence | Validated API request, idempotency key, transaction-bound incident/history/in-app notification records | Local SQLite tests cover the flow. No external emergency dispatch exists. |
| Deterministic priority and dispatch eligibility | Deterministic rules; backend revalidates responder, assignment, and resource constraints | Prototype rules only. Automatic assignment defaults off and is controlled by Super Admin policy. |
| Incident analysis | Durable analysis row, optional OpenRouter adapter, schema/evidence validation, rules-based fallback, recovery polling | Provider-isolated tests cover success, malformed output, failure, fallback, and ownership fencing. Live end-to-end operation is unverified. |
| Responder recommendation and assignment | Deterministic eligibility/ranking; coordinator selects; backend checks again within assignment transaction | Local tests cover implemented behavior. Scores are not validated dispatch policy. |
| Follow-up, responder-note drafts, resolution report | Rule-based optional questions; optional AI rewrite draft with review; deterministic evidence-template report on resolution | Application paths are tested locally. The report does not establish cause or replace an investigation. |
| Notifications | Recipient-scoped persistent in-app records | Local tests cover persistence/read state. Push delivery is absent; SMTP is used only for responder invitations when configured. |
| Admin Copilot | Fixed read-only intent handlers over operational records | Rules-based; no LLM, arbitrary SQL, or mutation authority. |
| PostgreSQL queue/migration safety | Claim-token result persistence and transaction-scoped PostgreSQL Alembic advisory lock | Earlier disposable PostgreSQL test results are recorded in the audit. Hosted PostgreSQL, replicas, and rollout behavior remain unverified. |
| Web and Android builds | Static dashboard configuration, Flutter Android app, Flutter web target | Local Flutter web build and client tests passed. No deployed site or API URL exists. |

Status labels in this table describe repository implementation and local evidence only. They do not imply a hosted test or operational readiness.

## Technology stack

| Area | Technologies verified from project configuration |
|---|---|
| Mobile/client UI | Flutter and Dart; Material widgets; HTML/CSS/vanilla JavaScript for the separate browser dashboard |
| API | Python, FastAPI, Uvicorn, Pydantic and Pydantic Settings |
| Persistence | SQLAlchemy 2.x, Alembic; SQLite for local development/tests and PostgreSQL via psycopg for production configuration |
| Authentication | PyJWT HS256 access tokens, Argon2 password hashing through pwdlib, hashed rotating refresh tokens |
| Optional AI | HTTPX OpenRouter adapter for google/gemma-4-31b-it; optional OpenAI-compatible adapter; provider-off rules baseline |
| Mobile packages | http, geolocator, flutter_secure_storage, flutter_svg |
| Tests | pytest/httpx, Flutter test/analyze, Node's built-in test runner |
| Deployment definitions | Dockerfile/Compose, Render blueprint, Vercel static-site config, GitHub Actions |

Backend dependency ranges are declared in backend/requirements.txt and backend/requirements-dev.txt. Flutter dependency constraints are in pubspec.yaml and resolved versions in pubspec.lock. The CI workflow currently selects Python 3.13, Flutter 3.47.7, Java 17, and Node 24; these are CI settings, not proof that every developer machine has them installed.

## Architecture

### Components and boundaries

- **Flutter client:** one app with User, Responder, and Admin portals. Session identity and role come from the server. The local training workspace is separate from authenticated API records and is not imported into the server database.
- **Browser dashboard:** static HTML, CSS, and JavaScript in **web/**. It calls the same API and is not served by Uvicorn. Its service URL can be supplied at build time or entered on the sign-in screen.
- **Isolated React staging dashboard:** a separate Vite + React + TypeScript app in **web/react-dashboard/**. It uses the existing `/api/v1` contracts and has its own build output; it does not replace the static dashboard or activation routes.
- **FastAPI backend:** validates requests, enforces authentication/permissions/ownership, applies workflow policy, manages SQLAlchemy transactions, and exposes health endpoints.
- **Database:** SQLite for local development and tests; PostgreSQL is required by production configuration. The Compose PostgreSQL service uses a persistent named volume.
- **Analysis worker:** analysis rows are durable database records. FastAPI BackgroundTasks handles new work; a polling loop in each non-test API process recovers pending and stale work. This is not Celery, Redis, or a separately coordinated queue service.
- **Optional provider:** server-side OpenRouter support defaults off. Deterministic analysis is the baseline. Provider output cannot authorize responder assignment.

~~~mermaid
flowchart LR
  F[Flutter User and Responder portals] -->|Bearer API requests| A[FastAPI]
  W[Static coordinator dashboard] -->|Bearer API requests| A
  A -->|SQLAlchemy transactions| D[(SQLite local and tests; PostgreSQL deployment)]
  A --> Q[(Durable incident_analyses rows)]
  Q --> B[Background task and per-process recovery poller]
  B --> A
  A -. optional server-side HTTPS .-> O[OpenRouter Gemma adapter]
  A --> N[Persistent in-app notifications and audit records]
~~~

### Request and analysis lifecycle

~~~mermaid
sequenceDiagram
  participant Client
  participant API as FastAPI API
  participant DB as SQL database
  participant Task as Analysis task
  participant Provider as Optional provider
  Client->>API: Submit incident and Idempotency-Key
  API->>DB: Validate and persist incident, pending analysis and events
  API-->>Client: Return incident after commit
  API->>Task: Schedule post-commit BackgroundTask
  Task->>DB: Atomically claim pending row with UUID token
  Task->>Provider: Optional analysis request
  Provider-->>Task: Candidate structured result
  Task->>Task: Validate result or build deterministic fallback
  Task->>DB: Persist only if claim token is current
~~~

## Application behavior

### Intake and coordination

1. A User submits an incident at POST /api/v1/user/incidents with an Idempotency-Key.
2. Pydantic validation checks category, description, location, and severity/urgency. GPS latitude and longitude must be supplied together; GPS submissions require a recent capture timestamp.
3. In one transaction, the API writes the incident, initial update, pending analysis row, audit event, and in-app notifications. Reusing the same key for the same reporter returns the existing incident.
4. Deterministic rules calculate priority. Automatic assignment is attempted only if the separate policy is enabled and all constraints pass; otherwise the incident remains for coordinator review.
5. Coordinators review, assign, reassign, cancel, or resolve through authenticated routes. Responders can advance only their own active assignment through permitted states.

### Analysis, fallback, and recovery

- **AI_PROVIDER=none** (default) selects the rules-based baseline without a provider request.
- OpenRouter uses the configured model (default **google/gemma-4-31b-it**) and structured output. The response is parsed and validated against the result schema and source evidence before persistence.
- Invalid, unavailable, rate-limited, and failed output follows deterministic fallback paths.
- **AI_MAX_ATTEMPTS** defaults to 2 (maximum 3). Retries apply to explicit transient provider-status errors. Timeouts and connection failures are not automatically retried by that adapter path because a provider may already have received the request.
- Each task claim gets a UUID ownership token. Result updates and completion audit events require the current token. Recovery and authorized admin retry invalidate earlier tokens.
- The polling loop processes pending work and recovers processing rows older than five minutes. The job attempt limit is three; exhausted work becomes unavailable. A poller runs inside each non-test API process.
- Ownership fencing protects persistence, not provider delivery. A crash after provider acceptance but before result persistence can lead to a duplicate provider request. Exactly-once delivery is not guaranteed.

### Authentication and permissions

- Passwords are hashed with Argon2 through pwdlib and must be 12–128 characters.
- Access JWTs are short-lived (30 minutes by default) and checked against an active database session and current account role on authenticated requests.
- Remember Me is unchecked by default. When selected, the server issues a random refresh token, stores only its hash, and rotates it during refresh. Flutter uses secure storage; the browser dashboard uses sessionStorage.
- Public registration creates only User accounts. The first Super Admin is provisioned by the CLI; responder accounts use invitations and activation.
- Co-Admin permissions are enforced by backend dependencies on every request. Hiding controls in a client is not an authorization boundary.
- Invitation throttling is process-local, not a shared multi-instance limiter.

## Repository map

~~~
.
├── .github/workflows/quality.yml       CI checks and gated signed Android release
├── android/                            Android manifests, Gradle and launcher assets
├── assets/brand/                       Flutter brand asset
├── backend/
│   ├── app/
│   │   ├── api.py                      HTTP routes and request orchestration
│   │   ├── config.py                   Settings and production validation
│   │   ├── database.py                 SQLAlchemy engine, sessions and SQLite setup
│   │   ├── dispatch.py                 Deterministic priority and distance helpers
│   │   ├── intelligence.py             Provider adapters, validation, fallback and queue
│   │   ├── main.py                     FastAPI lifespan, CORS and health endpoints
│   │   ├── migration_lock.py           PostgreSQL transaction advisory lock
│   │   ├── models.py                   ORM schema and constraints
│   │   ├── provision_admin.py          One-time Super Admin bootstrap CLI
│   │   ├── schemas.py                  Pydantic request/response models
│   │   ├── seed_demo.py                Opt-in synthetic SQLite dataset
│   │   └── security.py                 Password, JWT, session and role dependencies
│   ├── migrations/                     Alembic environment and revision history
│   ├── tests/                           SQLite tests and opt-in PostgreSQL tests
│   ├── compose.yaml                     PostgreSQL 17 and persistent volume
│   ├── postgres_test_safety.py           Fail-closed PostgreSQL test validation
│   ├── start.sh                         Migration-before-Uvicorn entry point
│   └── requirements*.txt                Backend/test dependency ranges
├── docs/
│   ├── audit/                           Architecture, discovery and test audits
│   ├── operations/                      Hosting and backup/recovery guidance
│   ├── requirements/                    Requirements and traceability
│   ├── DEMO_ACCOUNTS.md                 Synthetic seed-account behavior
│   ├── DESIGN_SYSTEM.md                 UI design tokens
│   ├── EXTERNAL_REQUIREMENTS.md         Environment/external requirements
│   ├── GEMMA_INTEGRATION_AUDIT.md       Provider, queue, migration and release evidence
│   └── UX_UI_AUDIT.md                   UI/UX findings
├── lib/
│   ├── data/                            API client, URL validation and training store
│   ├── domain/                          Client-side deterministic rules/models
│   ├── presentation/                    Flutter portals, design system and training UI
│   └── main.dart                        Flutter application entry point
├── scripts/                             Web config and protected Android release build
├── test/                                Flutter unit, API-client and widget tests
├── web/
│   ├── admin/                           Static coordinator dashboard and analytics tests
│   ├── activate.html                    Invitation activation page
│   ├── react-dashboard/                 Isolated React staging dashboard
│   └── index.html                       Flutter Web entry point
├── render.yaml                          Render API service template
├── vercel.json                          Static dashboard build/output configuration
├── pubspec.yaml / pubspec.lock          Flutter dependencies and lock file
└── README.md                            This guide
~~~

Root files also include **SETUP.md** (legacy build-staging notes), **analysis_options.yaml**, and an older debug APK in **release/**. Generated directories, local virtual environments, and secret files are intentionally omitted.

## Prerequisites

| Component | Requirement | Use |
|---|---|---|
| Python | 3.12 or newer; CI uses 3.13 | API, migrations, CLI, tests |
| Flutter/Dart | Flutter 3.47.7 in CI; Dart SDK constraint 3.13.5+ | Android client, widget tests, Flutter web target |
| Java | JDK 17 for Android builds | Gradle/Android toolchain |
| Android SDK / Platform Tools | Emulator/device and APK builds | Android client |
| Node.js | Node 24 in CI | Static dashboard checks and isolated React dashboard |
| Docker Compose | Optional; only for PostgreSQL development | Compose PostgreSQL service |
| PostgreSQL | PostgreSQL 17 in Compose; production configuration requires PostgreSQL | Deployment and explicitly approved PG tests |

Redis, Celery, and a message broker are not used. External provider accounts are not needed for ordinary local development or tests. Hosting accounts are not configured in the repository.

## Local development setup

These steps describe a new isolated development database. Do not point them at a shared or unidentified database.

### Backend with SQLite

From the repository root:

~~~sh
git clone https://github.com/QaziZaid16/emergency_coordination_system.git
cd emergency_coordination_system
git switch main

cd backend
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
~~~

Configure the new backend/.env locally; never commit or paste it. Safe local defaults:

- ENVIRONMENT=development
- DATABASE_URL=sqlite:///./data/coordination.db
- A newly generated private JWT_SECRET of at least 32 characters
- AI_PROVIDER=none and an empty provider key
- SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_FROM unset/empty unless invitation email is deliberately configured

Pydantic loads process environment settings and backend/.env (when running from backend/); process environment takes precedence. Never use real incident information or passwords in a demo.

On a new SQLite path, migrate and provision the initial administrator:

~~~sh
alembic upgrade head
python -m app.provision_admin --email admin@example.org --display-name 'Local Operations Admin'
~~~

The provisioning CLI prompts for a password without echo and creates only the first Super Admin. Its optional credentials-file mode is restricted to local SQLite development and writes generated credentials to a new private mode-0600 file; keep that file out of Git and shared directories.

Start the API bound to loopback:

~~~sh
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
~~~

In a second terminal, serve only static files on loopback:

~~~sh
cd /path/to/emergency_coordination_system
python3 -m http.server 8080 --bind 127.0.0.1 --directory web
~~~

Open http://localhost:8080/admin/ and enter http://127.0.0.1:8000 as the API origin. Default development CORS includes localhost:8080. The dashboard has no default login.

For an Android emulator, the host alias is commonly 10.0.2.2. For a USB-connected device, Android Platform Tools can reverse the port:

~~~sh
adb reverse tcp:8000 tcp:8000
flutter run -d <device-id> --dart-define=API_BASE_URL=http://127.0.0.1:8000
~~~

The client validator permits only loopback/emulator HTTP in debug builds; release builds require HTTPS. Private-LAN HTTP for phones is not enabled. Do not broaden the API bind, publish a port, or weaken client URL validation without approved network scope and implementation review.

For a fresh Flutter checkout, run flutter doctor -v, then flutter pub get from the repository root. Android emulator/device runs additionally need an Android SDK and Platform Tools. The browser dashboard has no npm dependency installation step; Node is used by its configuration/build checks.

### Optional synthetic seed

The seed utility requires development mode, SQLite, and an explicit confirmation flag. It is additive/repeatable and does not reset existing data. It creates synthetic accounts, responders, incidents, assignments, and a resource. Generated passwords are printed once on first creation; protect them. Never seed production or an unknown/shared database. See [demo account details](docs/DEMO_ACCOUNTS.md).

### PostgreSQL Compose warning

backend/compose.yaml declares PostgreSQL 17 and a persistent volume named **coordination-data**. The API host port is loopback-only; PostgreSQL has no published host port. The repository does not establish the actual volume's identity, ownership, history, or contents. **Do not attach, migrate, reset, or delete an existing volume unless an authorized operator has verified it is dedicated and safe.** Do not run docker compose down -v. The Compose database is not an approved disposable test target.

## Configuration reference

Defaults below come from source and checked-in configuration; they are not a recommendation to reuse production credentials locally.

| Variable | Purpose | Required/default | Secret? / notes |
|---|---|---|---|
| DATABASE_URL | SQLAlchemy target | SQLite file default; production requires postgresql+psycopg URL | Credential-bearing URLs are secret |
| ENVIRONMENT | Lifecycle/config mode | development | Production has stricter validation and does not create schema in app lifespan |
| STAGING_RESPONDER_INVITATION_HANDOFF | Return a one-time responder activation link to an authorized staging administrator | false | Accepted only with ENVIRONMENT=staging and SMTP_HOST empty; production rejects it |
| JWT_SECRET | JWT signing | Required outside tests; 32+ characters | Secret; use a private random value |
| ACCESS_TOKEN_MINUTES | Access token lifetime | 30 | No |
| REMEMBER_ME_DAYS | Refresh session lifetime | 30; range 1–365 | No |
| CORS_ORIGINS | Allowed browser origins | Localhost development origins | Use exact HTTPS origins in production |
| PUBLIC_APP_URL | Invitation links/public origin | Localhost default | Production requires a real HTTPS origin |
| SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM | Responder invitation email | Host blank; port 587 | Credentials secret; empty host prevents SMTP delivery |
| AI_PROVIDER | Analysis provider selection | none | none/off selects deterministic analysis |
| OPENROUTER_API_KEY | Server-side provider credential | Empty | Secret; never put in a client build |
| OPENROUTER_BASE_URL | OpenRouter base URL | https://openrouter.ai/api/v1 | OpenRouter requires HTTPS |
| OPENROUTER_MODEL | OpenRouter model | google/gemma-4-31b-it | Model identifier |
| AI_BASE_URL, AI_API_KEY, AI_MODEL | Legacy OpenAI-compatible adapter settings | Blank | AI_API_KEY is secret |
| AI_TIMEOUT_SECONDS | Provider timeout | 8 seconds; range 1–30 | No |
| AI_MAX_ATTEMPTS | Eligible transient response attempts | 2; range 1–3 | No; not exactly-once |
| AI_RATE_LIMIT_PER_MINUTE | Process-local provider-call limit | 60; range 1–600 | Not shared across replicas |
| AI_SHARE_INCIDENT_LOCATION | Include location label in provider payload | false | Coordinates are not sent |
| RECOMMENDATION_DISTANCE_WEIGHT, RECOMMENDATION_CAPABILITY_WEIGHT, RECOMMENDATION_WORKLOAD_WEIGHT | Responder ranking weights | 45, 35, 20 | Prototype scoring |
| PORT | Deployment Uvicorn port | 8000 fallback | Platform supplied where applicable |
| POSTGRES_PASSWORD | Local Compose database password | Required by Compose interpolation | Secret; local Compose only |
| API_BASE_URL | Flutter compile-time API origin | Empty/unconfigured | Public URL, not secret; release requires HTTPS |
| ENABLE_TRAINING_WORKSPACE | Debug feature flag | Disabled unless explicitly true | Compile-time flag; local training data only |
| ECS_API_BASE_URL | Static dashboard build-time API origin | Empty permits manual entry; required by Vercel build | Public URL; script requires HTTPS and rejects placeholders |
| ECS_POSTGRES_TEST_MODE | Opt into PostgreSQL test configuration | Disabled unless 1 | Never enable without an approved disposable target |
| ECS_POSTGRES_TEST_DATABASE_URL | Dedicated PostgreSQL test URL | Required in opt-in mode | Keep credential-bearing URL protected |
| ECS_POSTGRES_TEST_TARGET_DISPOSABLE | Disposable-target declaration | Must equal 1 | Declaration alone does not prove isolation |
| ECS_POSTGRES_TEST_RUN_ID | Unique run token | 8–32 lowercase alphanumeric characters | Database must be ecs_test_<run_id> |
| ECS_POSTGRES_TEST_ALLOWED_HOSTS | Exact hostname allowlist | Required in opt-in mode | Comma-separated exact hosts |
| ECS_POSTGRES_TEST_ALLOWED_DATABASES | Exact database allowlist | Required in opt-in mode | Comma-separated exact database names |

The PostgreSQL fixture parses and validates the test URL before app imports. It rejects SQLite, broad allowlists, mismatched database names, the Compose service/database, and a PostgreSQL host matching the runtime target. PostgreSQL tests are skipped by default. Some tests deliberately change the disposable target schema; use only an explicitly approved disposable PostgreSQL 17 database. The fixture does not provision or clean up a database.

Android release signing values are supplied only to protected GitHub Actions jobs; see [hosting guidance](docs/operations/hosting.md) and [the CI workflow](.github/workflows/quality.yml). Never put signing keys or passwords in Dart defines, web assets, or the repository.

## Running the components

### API

From backend/ with the development environment active:

~~~sh
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
~~~

The development/test lifespan creates missing tables with SQLAlchemy metadata. For a new database, run Alembic first. If an earlier startup used create_all and Alembic later reports existing tables, stop and preserve the database; do not delete or blindly stamp it. See [backend setup](backend/README.md).

- OpenAPI: http://127.0.0.1:8000/docs
- Liveness: http://127.0.0.1:8000/health/live
- Database readiness: http://127.0.0.1:8000/health/ready

### Browser dashboard

The static site lives in web/. It can be served locally with Python's static file server; the API remains a separate process. The dashboard polls operational and notification data while visible and provides manual refresh.

### Isolated React coordinator dashboard

The React application in `web/react-dashboard/` is for separate staging review. It does not change the current `/`, `/admin`, or `/activate` routes. From the repository root:

~~~sh
cp web/react-dashboard/.env.example web/react-dashboard/.env.local
# Set VITE_ECS_API_ORIGIN in .env.local to the real HTTPS API origin (origin only).
npm ci --prefix web/react-dashboard
npm run dev --prefix web/react-dashboard
~~~

The API must allow the local Vite origin through its existing CORS configuration. The React app rejects HTTP, placeholder domains, and API URLs containing credentials, paths, queries, or fragments. For tests and a production build, run:

~~~sh
npm test --prefix web/react-dashboard
VITE_ECS_API_ORIGIN=https://your-real-api-host.tld npm run build --prefix web/react-dashboard
npm run preview --prefix web/react-dashboard
~~~

The production build is written to `web/react-dashboard/dist/`, separate from Flutter's `build/web/`. To stage it later, configure a **separate Vercel project** with Root Directory `web/react-dashboard`, Framework Preset Vite, Build Command `npm run build`, Output Directory `dist`, and public build variable `VITE_ECS_API_ORIGIN` set to the real HTTPS API origin. Keep the existing Vercel project and invitation activation host unchanged; responder invitations currently point to the activation host configured by the backend. Provider setup and deployment are separate manual steps.

### Flutter

~~~sh
flutter run -d <device-id> --dart-define=API_BASE_URL=http://127.0.0.1:8000
flutter build apk --debug --dart-define=API_BASE_URL=http://127.0.0.1:8000
flutter build web --no-pub
~~~

The Flutter web target is separate from the static deployment site: Vercel publishes `web/`, whose `/` and `/admin` routes open the static coordinator dashboard; the Flutter web build is emitted separately under `build/web/`. A Flutter build without API_BASE_URL can show the login UI but cannot connect to a service.

## HTTP API reference

The router prefix is /api/v1. Use the running OpenAPI page at /docs for generated field-level request and response schemas. The table lists routes declared in backend/app/api.py; server-side authorization also checks account state, incident ownership, and Co-Admin permission scopes.

### Authentication

| Method and path | Access | Request and successful result |
|---|---|---|
| POST /api/v1/auth/login | Public | LoginRequest: email, password, optional remember_me; returns LoginResponse with access token, expiry, optional refresh token, session expiry, and UserView. |
| POST /api/v1/auth/register | Public | UserRegister: email, display_name, 12–128 character password, optional remember_me; creates only User role, 201. |
| POST /api/v1/auth/accept-invitation | Public invitation token | InvitationAccept: token and password; activates invited responder. |
| POST /api/v1/auth/refresh | Refresh credential | RefreshRequest; rotates refresh token and issues LoginResponse. |
| POST /api/v1/auth/logout | Authenticated | Revokes current session; 204. |
| GET /api/v1/auth/me | Authenticated | Returns current UserView. |

### Incidents, updates, intake, reports, and notifications

| Method and path | Access | Request / result |
|---|---|---|
| POST /api/v1/user/incidents | User | IncidentCreate and Idempotency-Key header (8–128 chars); first request 201, matching replay 200. |
| GET /api/v1/incidents | Signed-in; role/permission and ownership filtered | Optional status/query filters; returns permitted incidents. |
| GET /api/v1/incidents/{incident_id} | Signed-in; authorized reporter, assigned responder, or coordinator | Returns one incident view. |
| GET /api/v1/incidents/{incident_id}/updates | Signed-in; incident access required | Returns update history. |
| GET /api/v1/incidents/{incident_id}/intake | Signed-in; incident access required | Returns questions, saved answers, and dispatch status. |
| POST /api/v1/incidents/{incident_id}/intake/answers | Reporter | IntakeAnswers; stores user-reported answers. |
| POST /api/v1/incidents/{incident_id}/updates | Authorized reporter or assigned responder | MessageCreate; persists an update subject to route rules. |
| POST /api/v1/responder/incidents/{incident_id}/rewrite | Assigned responder | RewriteRequest; returns a draft and status, does not change incident state. |
| GET /api/v1/incidents/{incident_id}/report | Authorized reporter, assigned responder, or coordinator | Returns deterministic resolution report when available. |
| POST /api/v1/admin/incidents/{incident_id}/report/review | Admin with applicable permission | ReportReview; records review note and reviewer metadata. |
| GET /api/v1/notifications | Authenticated | Current account's in-app notifications. |
| PATCH /api/v1/notifications/read-all | Authenticated | Marks current account's notifications read. |
| PATCH /api/v1/notifications/{notification_id}/read | Authenticated owner | Marks one notification read. |

### Coordinator and administration

| Method and path | Access | Request / result |
|---|---|---|
| GET /api/v1/admin/dashboard | Admin with dashboard access | Coordinator dashboard summary. |
| GET /api/v1/admin/analytics | Admin with reports access | Optional days window; descriptive database aggregates, not forecasts. |
| POST /api/v1/admin/copilot | Admin with read permissions | CopilotQuestion; rules-based read-only answer with sources where applicable. |
| GET /api/v1/admin/responders | Admin with dashboard or responder-management permission | Responder accounts and profiles. |
| POST /api/v1/admin/invitations/responders | Admin with manage_responders | ResponderInviteCreate; may send email only if SMTP is configured. |
| GET /api/v1/admin/invitations | Admin with manage_responders | Invitation status; stored token hashes are not exposed. |
| POST /api/v1/admin/invitations/{invitation_id}/revoke | Admin with manage_responders | Revokes invitation. |
| POST /api/v1/admin/invitations/responders/{user_id}/resend | Admin with manage_responders | Rotates/resends eligible invitation; rate limited. |
| GET /api/v1/admin/users | Admin with applicable account permission | Optional role filter; returns accounts. |
| POST /api/v1/admin/users | Admin with manage_users | UserCreate; creates User or Responder per schema. |
| PATCH /api/v1/admin/users/{user_id}/active | Authorized account manager | Query parameter active; deactivation revokes sessions. |
| GET /api/v1/admin/coadmins | Super Admin | Lists Co-Admins. |
| POST /api/v1/admin/coadmins | Super Admin | CoAdminCreate; creates scoped permissions. |
| PATCH /api/v1/admin/coadmins/{user_id}/active | Super Admin | Query parameter active. |
| PATCH /api/v1/admin/coadmins/{user_id}/permissions | Super Admin | Permission list. |
| PUT /api/v1/admin/responders/{responder_id}/capabilities | Admin with manage_responders | Capability list. |
| PATCH /api/v1/admin/responders/{responder_id}/availability | Admin with manage_responders | AvailabilityUpdate. |
| GET /api/v1/admin/resources | Admin with dashboard or resource-management access | Lists resources. |
| POST /api/v1/admin/resources | Admin with manage_resources | ResourceCreate. |
| PATCH /api/v1/admin/resources/{resource_id} | Admin with manage_resources | ResourceCreate and optional active query parameter. |
| GET /api/v1/admin/incidents/{incident_id}/recommendations | Admin with incident view access | Eligible responder candidates and reasons. |
| GET /api/v1/admin/incidents/{incident_id}/duplicates | Admin with incident view access | Review-only duplicate candidates. |
| POST /api/v1/admin/incidents/{incident_id}/analysis/retry | Admin with update permission | Queues eligible retry; 202 and old claim invalidated. |
| POST /api/v1/admin/incidents/{incident_id}/assign | Admin with assignment permission | AssignmentCreate; backend rechecks eligibility/resource compatibility. |
| POST /api/v1/admin/incidents/{incident_id}/reassign | Admin with assignment permission | AssignmentCreate; requires active assignment. |
| POST /api/v1/admin/incidents/{incident_id}/cancel | Admin with update permission | Cancels eligible incident and records state/audit events. |
| POST /api/v1/admin/incidents/{incident_id}/resolve | Admin with update permission | Resolves eligible incident and creates deterministic report. |
| GET /api/v1/admin/automation | Admin | Reads automatic-assignment policy. |
| PUT /api/v1/admin/automation | Super Admin | AutomaticAssignmentPolicyUpdate; policy defaults disabled. |
| GET /api/v1/admin/audit | Admin with audit permission | Optional limit; returns authorized audit events. |

### Responder and change-feed routes

| Method and path | Access | Request / result |
|---|---|---|
| GET /api/v1/responder/profile | Responder | Current responder profile. |
| PUT /api/v1/responder/location | Responder | ResponderLocation; stores timestamped location for recommendations. |
| POST /api/v1/responder/incidents/{incident_id}/status | Assigned responder | StatusUpdate; only permitted forward states accepted. |
| GET /api/v1/changes | Authenticated and permission-filtered | Optional after timestamp; authorized changes for client polling. |

Authentication failures use 401, role/permission failures 403, schema validation failures 422, and route-specific missing/conflict/rate-limit cases use route-defined statuses. OpenAPI is the source for exact payload details.

### Common request and response shapes

- **LoginResponse:** access_token, token_type, expires_at, optional refresh_token, session_expires_at, and a UserView containing id, email, display_name, role, and permissions.
- **IncidentCreate:** emergency_type is one of Ambulance / Medical Emergency, Fire and Rescue, Police / Security, or Other Emergency; description is 3–2000 characters; location_label is 2–240; location_source is gps or manual; optional latitude/longitude must be supplied together and within geographic ranges; GPS requires a capture timestamp within the accepted freshness window; severity and urgency are 1–5.
- **Incident view:** includes id/reference, reporter, category, description/location, severity/urgency, calculated priority/reason, status, current responder/resource fields, timestamps, and intake data. Analysis metadata/result is included only in authorized views, not in the reporting user's incident view.
- **AssignmentCreate:** responder_id and optional resource_id. The server returns the updated incident view after transactional checks.
- **StatusUpdate:** next status is one of Accepted, En Route, On Scene, or Resolved; actual transitions are checked against the assignment's current state.
- **MessageCreate:** message is 1–1000 characters, with optional original_message and ai_assisted fields. **IntakeAnswers** accepts at most 12 answer entries; supported keys and value limits are enforced by the API.
- **Account/resource/location models:** UserCreate and CoAdminCreate enforce valid email, 1–120 character display name, and 12–128 character password; ResourceCreate validates name, kind, and quantity; ResponderLocation validates coordinate/accuracy ranges and capture time.
- **Other JSON results:** dashboard summary returns count fields; notification endpoints return recipient-scoped notification records; GET /api/v1/changes returns server_time and authorized incident views. Route-specific result shapes are visible in the generated OpenAPI document.

FastAPI validation errors use a JSON detail field; validation detail may be a list of field errors. Domain errors use route-specific detail messages. Do not make clients depend on internal traceback text.

## Data model and migrations

Important tables:

| Table | Purpose |
|---|---|
| users | Accounts, role, permissions, active state, Argon2 password hash |
| responders | Capabilities, availability, optional timestamped responder location |
| incidents | Reporter, report/location fields, severity/urgency, priority, status, idempotency key |
| incident_analyses | One durable analysis state per incident, result/validation metadata, attempts, timestamps, current claim token |
| assignments | Incident/responder/resource assignment, state, source, timestamps |
| incident_updates | Submission and responder/user updates, original/final note, AI-assisted marker |
| account_invitations | Hashed single-use tokens and lifecycle timestamps |
| resources | Inventory quantity, allocation, active state |
| notifications | Recipient-scoped in-app events with unique per-recipient event key |
| coordination_policy | Automatic-assignment flag and severity ceiling |
| incident_reports | Versioned deterministic reports and review metadata |
| audit_events | Actor, action, entity, structured audit details |
| auth_sessions | JWT session identifiers, refresh-token hash, expiry, revocation |

Foreign keys and database constraints enforce key ownership links, severity/coordinate ranges, idempotency uniqueness per reporter, unique resource names, one active assignment per responder, and unique notification event keys. The Alembic chain starts with the shared coordination schema and adds sessions, analysis, permissions, invitations, notifications/automation, durable recovery, conversational intake/reports, and claim ownership.

The checked-in linear revisions are de28b59bc889 (initial schema), 78f7c901c52a (remembered-session refresh), 1bcb3409a6a1 (incident intelligence), 5fa2c57e31c0 (admin permissions), a40b1331ee91 (account invitations), b271c7e05d3a (notifications/automatic assignment), 9ce4b8b2241a (durable analysis recovery), c2a71d0e48bf (conversational intake/reports), and 4e5b0b6a92d1 (claim ownership).

For online PostgreSQL migrations, a dedicated transaction-scoped advisory lock is acquired on the migration connection before revision discovery and execution. It serializes migration transactions only; it does not drain old app processes or make mixed-version queue processing safe. The latest migration adds nullable incident_analyses.claim_token; downgrade removes it and is not a substitute for rolling back application code.

See [backup and recovery](docs/operations/backup-and-recovery.md) for procedures and stop conditions. Never restore over an unidentified or only known database.

## End-to-end workflows

### Manual assignment

1. An Admin opens a stored incident and its recommendation list.
2. The server filters active, available, capable responders without active assignments. Distance is used only when both location readings are at most 100 m accuracy and no older than 15 minutes.
3. The Admin submits an explicit assignment request.
4. The backend rechecks incident state, responder eligibility, resource compatibility, and uniqueness in a transaction.
5. Assignment, incident status/history, audit event, notifications, responder availability, and resource allocation commit together. Conflicts do not erase the incident.

### Automatic assignment

A Super Admin must enable the policy and set a severity ceiling. Intake attempts assignment only when severity, fresh accurate incident/responder location, capability, active account, availability, workload, and resource checks pass. A missing match leaves the incident for review. Model output is never an assignment input.

### Responder status and resolution

The assigned responder submits a valid next status. The API persists status, history, audit, and in-app notification state. Resolution creates a versioned evidence-template report that references records and limitations; it does not infer cause.

### Invitation

An Admin creates an invitation. The API stores a hash of a random one-use token with expiry/revocation state. Configured SMTP attempts delivery; development without SMTP can return an activation link to the authenticated administrator. Production treats missing or failed delivery as failure. Invitation throttling is process-local.

## Testing and validation

### Backend

Run from backend/ in a local Python environment:

~~~sh
AI_PROVIDER=none OPENROUTER_API_KEY= SMTP_HOST= SMTP_USERNAME= SMTP_PASSWORD= SMTP_FROM= ECS_POSTGRES_TEST_MODE=0 python -m pytest -q -p no:cacheprovider tests
~~~

The test conftest sets provider-off before application imports and forces ordinary tests to in-memory SQLite. PostgreSQL tests are skipped unless explicit opt-in validation passes. SMTP variables above are blank so tests cannot deliver invitations.

Focused suites:

~~~sh
python -m pytest -q tests/test_workflow.py tests/test_analysis_queue.py
python -m pytest -q tests/test_analysis_retry_authorization.py tests/test_analysis_worker_lifecycle.py
python -m pytest -q tests/test_intelligence.py tests/test_conversational_features.py
~~~

### PostgreSQL-specific tests

Do not run these against production, shared, local Compose, or runtime databases. They require a separately approved disposable PostgreSQL 17 target and all fail-closed environment variables above. The fixture smoke test makes a read-only connection; migration/concurrency tests deliberately downgrade/upgrade schema and inject a test DDL fault. The fixture does not create or drop a database. Run only after target validation and separate authorization.

### Flutter and static-site tests

~~~sh
flutter pub get
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test test/api_client_test.dart test/api_configuration_test.dart test/dispatch_rules_test.dart test/operations_store_test.dart test/widget_test.dart
node --test web/admin/analytics.test.cjs
node --check web/admin/app.js
node --check scripts/build_web_config.mjs
npm test --prefix web/react-dashboard
VITE_ECS_API_ORIGIN=https://your-real-api-host.tld npm run build --prefix web/react-dashboard
~~~

The test framework uses provider/HTTP mocks or blocks outbound HTTP in widget tests. Do not configure a live provider or SMTP to run the offline suite.

### Latest local verification in this workspace

On 2026-10-25:

- Provider-off backend suite including ordinary SQLite tests and default PostgreSQL skips: **117 passed, 11 skipped, 1 Starlette/httpx deprecation warning**.
- Flutter tests: **31 passed**.
- Flutter analysis: **no issues**.
- Flutter web compilation: **succeeded**, with a non-fatal Cupertino icon font warning.
- Static dashboard analytics tests: **7 passed**.
- Git whitespace validation: **passed**.

The Dart formatter could not run because the Flutter SDK attempted a cache write outside the repository and the environment denied it. PostgreSQL tests were not run in the latest verification. Earlier PostgreSQL 17.11 tests and one live adapter-level completion are described in the audit; neither is a current deployment check. There is no verified public URL.

Phase 60 targeted checks later passed: backend login/auth/config regressions **22 passed** (one Starlette/httpx warning), Flutter API configuration **3 passed**, dashboard analytics/deployment checks **9 passed**, Flutter analysis clean, and Flutter web build succeeded. The build output was confirmed under `build/web/`; no database migration or browser/runtime test was run. The Dart formatter remains blocked by the SDK cache permission error.

## Security, privacy, and safety

- Use synthetic demo accounts/incidents only. Do not include real incident information or precise real locations.
- Never store secrets in Git, Flutter defines, static assets, browser storage, command output, or issue reports.
- Keep the OpenRouter key server-side. A key alone does not select a provider.
- If AI is enabled, report text is sent to the selected provider. The location label is omitted unless AI_SHARE_INCIDENT_LOCATION is true; coordinates are not sent.
- Keep SMTP unset to prevent invitation email. In-app notification records are not proof of external delivery.
- Keep PostgreSQL private. Do not publish port 5432 or attach an unidentified Compose volume.
- Set CORS_ORIGINS to exact browser origins. Development defaults are localhost origins.
- Android release builds require HTTPS. Debug builds permit only loopback, RFC1918 IPv4, and IPv6 unique-local HTTP API origins; that traffic is unencrypted and still requires an approved, restricted demo network and firewall policy.
- Login attempts are limited to 10 per 15-minute window per normalized email identifier, stored as a keyed HMAC digest in the shared application database. This is shared across API processes using that database; PostgreSQL concurrency still requires staging verification. Invitation and AI-provider limits remain process-local. MFA, account recovery, push delivery, and production operational monitoring are absent.
- Do not enable prototype assignment rules for real-world incidents.
- Logs and audit rows may contain sensitive operational metadata; provider error logs intentionally omit request/response content and credentials.

## Troubleshooting

| Symptom | Likely source-backed cause | Safe next step |
|---|---|---|
| API refuses to start outside tests | JWT_SECRET missing/short or production settings invalid | Check presence and length without printing its value; verify production database URL and HTTPS origins. |
| Alembic reports existing local SQLite tables | A development startup may have used SQLAlchemy create_all without an Alembic revision | Stop and preserve the database; compare its schema before any stamp/migration. Use a separate SQLite file if uncertain. |
| Dashboard cannot reach the API | API stopped, incorrect entered origin, or CORS does not include the exact browser origin | Confirm local service state and URL; do not open LAN ports to solve a local URL issue. |
| Flutter reports API_BASE_URL empty/invalid | API origin was not supplied at build time | Rebuild with intended origin; debug HTTP is loopback/emulator-only and release requires HTTPS. |
| Analysis remains pending/unavailable | Worker/database problem, stale attempts exhausted, provider failure, or invalid model output | Review persisted status/safe failure category; use authorized Admin retry only for eligible records. |
| Migration tests begin contacting a DB | PostgreSQL opt-in was enabled or misconfigured | Stop. Ordinary tests must set ECS_POSTGRES_TEST_MODE=0; never substitute another target. |
| Generated demo login is lost | Seed passwords print once on first creation; stored hashes are irreversible | Do not attempt to recover a password from its hash. Use only an approved isolated development database and supported account workflow. |

## Contribution workflow

1. Confirm repository path and branch before editing.
2. Inspect Git status and current diffs; preserve unrelated work.
3. Make a focused source change and add a regression at the appropriate boundary.
4. Add a new Alembic revision for schema changes; never edit an applied revision.
5. Run provider-off SQLite tests, client tests, static checks, and git diff --check as relevant.
6. Review the full staged diff. Never stage all files blindly or include .env, virtual environments, build output, datasets, or credentials.
7. Commit only after review; push only to the verified repository and branch.

## Deployment and operations

### Checked-in configuration

- **Render:** render.yaml defines one Docker web service named emergency-coordination-api with plan free, startup through backend/start.sh, automatic deploy after checks, and /health/ready health check. It does not define a PostgreSQL resource.
- **Startup:** backend/start.sh runs alembic upgrade head with up to five attempts before Uvicorn binds 0.0.0.0 and PORT (default 8000). Every service start runs migrations. The advisory lock serializes PostgreSQL migration transactions but does not coordinate application-version overlap.
- **Docker:** backend/Dockerfile uses Python 3.12 slim. Its default command starts Uvicorn directly; it does not run start.sh unless deployment configuration selects it. Local Compose API host binding is 127.0.0.1:8000; the database has no published host port.
- **Static site:** vercel.json publishes `web/`; its root and `/admin` routes resolve to the static coordinator dashboard, and `/activate` resolves to the activation page. `scripts/build_web_config.mjs` requires a real HTTPS `ECS_API_BASE_URL` for the configured deployment build. The isolated React dashboard has its own Vercel staging project instructions in `web/react-dashboard/README.md`. The Flutter web artifact is separate under `build/web/`.
- **CI/CD:** .github/workflows/quality.yml runs backend, Flutter, static-web, and isolated React dashboard checks/build. The signed Android release job requires protected repository variables/secrets and is gated on them.

These are templates/configuration, not proof of hosted resources. The hosting guide proposes Vercel/Render/Supabase, but this repository contains no verified connected project, database, public URL, or current hosting cost.

### Release controls

Before deployment, operators must verify hosting/database ownership and cost, backup/restore, secrets, CORS, replica/process count, worker topology, and monitoring. Drain incompatible old application/worker versions before schema changes; start only compatible code after migration succeeds. Do not downgrade the schema while newer code may use claim_token. Application rollback and database downgrade are separate decisions. See the [integration audit](docs/GEMMA_INTEGRATION_AUDIT.md) and [hosting guide](docs/operations/hosting.md).

## Limitations and deferred work

- Prototype only; not an operational emergency response service.
- No emergency-agency integration, public safety call, FCM/mobile push, or responder SMS.
- Hosted worker lifecycle, hosting-platform PostgreSQL behavior, replica coordination, backup restoration, and deployment drain/rollback remain unverified.
- Old and new application versions must not process queue work together; older code does not enforce current claim-token ownership.
- Duplicate provider calls remain possible across crash/recovery/retry.
- Production reset/recovery policy and service-level objectives are not approved.
- Local multi-phone demo remains blocked by volume/backup evidence, network/firewall scope, and separate runtime/service-start authorization.
- Cloud staging is not authorized; production is NO-GO.

## Further documentation

- [Backend setup and API notes](backend/README.md)
- [Architecture decisions](docs/audit/architecture.md)
- [Requirements and traceability](docs/requirements/traceability-matrix.md)
- [Demo seed accounts](docs/DEMO_ACCOUNTS.md)
- [UI design system](docs/DESIGN_SYSTEM.md)
- [UI/UX audit](docs/UX_UI_AUDIT.md)
- [Backup and recovery](docs/operations/backup-and-recovery.md)
- [Hosting and release checklist](docs/operations/hosting.md)
- [CI/CD audit](docs/CI_CD_AUDIT.md)
- [Gemma integration and release audit](docs/GEMMA_INTEGRATION_AUDIT.md)
