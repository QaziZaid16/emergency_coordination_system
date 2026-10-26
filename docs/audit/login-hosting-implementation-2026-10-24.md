# Login and hosting implementation audit

> Historical record from before the React website migration. Static-dashboard paths and test results refer to the implementation at the time; see [the current website migration record](../architecture/frontend-migration.md).

Audit date: 2026-10-24. Repository-only review; no physical device, hosted service, DNS, or production database was accessed.

## Verified baseline before these changes

- Branch was `main`, clean, at `8f75847` (`feat: improve onboarding and unify coordination UX`), one commit ahead of `origin/main`. The preceding commit was `4641d8c` (`Complete release readiness audit and document status`).
- The root README, requirements traceability, architecture, deep bug audit, release-readiness report, CI audit, demo-account notes, and external requirements were reviewed.
- Mobile is Flutter/Android. `lib/main.dart` opened `PortalEntryPage`. Its state restored a remembered server session and handled onboarding, but when logged out it rendered a separate portal page with a restoration error card, “Continue to your account”, a training-workspace shortcut, and service configuration text. Only the continue card opened `PortalLoginPage`; this was the source of the screenshot flow.
- `ApiClient.restoreSession` returned normally when no saved session existed; remembered sessions were refreshed and checked against `/auth/me`, including role comparison. Login/register returned the server role. Logout deleted local credentials and attempted revocation. Remember Me was opt-in, using secure storage and server-side rotating refresh credentials. Existing tests covered these client paths.
- Mobile `API_BASE_URL` was a raw compile-time string with a prefix-only check. Its error text exposed the build flag and an example placeholder. No real URL was present. The repository has no deployed API, domain, or live backend credentials.
- Web is plain static HTML/CSS/JavaScript in `web/admin/`, including login, overview, incident queue, responders, users, resources, reports, audit, and Super Admin-only Co-Admin management. Its login verifies the returned role and the API enforces permissions per request. It asks for a service URL in local/manual mode. Password reset is not implemented.
- Backend CORS allowed only GET, POST, and PATCH, while the dashboard sends a PUT to update responder capabilities. Added PUT to the allowlist and a preflight regression test.
- Backend is FastAPI, SQLAlchemy, Alembic, Argon2 password hashes, JWT access tokens, and hashed rotating refresh tokens. It has SQLite development/tests and PostgreSQL Compose configuration, `/health/live` and DB-checking `/health/ready`, development-only synthetic seeding, and no hosted deployment. The earlier admin provisioning CLI already used a password prompt in local-development documentation, but production-mode database/config safety and first-admin-only enforcement needed explicit implementation.
- Existing release-readiness notes identify outstanding production risks: no live deployment, debug-signed Android release, no login/refresh rate limiter, no PostgreSQL execution in this environment, and no tested backup restore.

## Changes in this follow-up

- Startup now goes onboarding → direct login for a new installation, and remembered-session validation → authorized workspace or direct login for a returning installation. Normal logged-out startup has no error. A saved-session network failure stays on login with a compact retry/dismiss notification.
- Login has no role/portal interstitial, session-restoration diagnostics, service URL display, or normal-flow training button. The local simulator remains reachable only when a debug build explicitly sets `ENABLE_TRAINING_WORKSPACE=true`; `kDebugMode` also excludes it from release builds.
- Added centralized mobile API URL validation: absolute URL syntax; HTTPS in release; only known loopback HTTP hosts in debug; placeholder origins rejected in production. Missing configuration is shown as a user-facing sign-in availability message only after submit. The API client never treats missing/invalid configuration as authentication success.
- Added a static dashboard build configuration (`ECS_API_BASE_URL`) and Vercel static routing. The API origin is public client configuration, not a credential. The build generator rejects empty/malformed/non-HTTPS/placeholder production origins.
- Backend production settings now require PostgreSQL and HTTPS dashboard/activation origins. The container binds to the host-provided `PORT`; health endpoints are in the app. Migrations remain explicit and production startup does not create schema.
- Added a first-Super-Admin-only CLI path that prompts for a password twice, requires 12–128 characters, hashes with the project's Argon2 implementation, and refuses an existing Super Admin. The PostgreSQL path serializes concurrent bootstrap attempts with an advisory transaction lock. It never prints the password.
- Added hosting steps for Vercel static dashboard plus a Docker-capable API host and managed PostgreSQL. This is preparation only; no provider account, URL, secrets, DNS, migrations, database, or live admin was provisioned.
- The web dashboard source audit found working navigation areas and role-conditioned controls; backend permissions are authoritative. No password reset flow exists. No browser automation, accessibility conformance scan, visual browser matrix, or live API journey was available/performed for this audit.

## Verification boundaries

Automated results for this follow-up are maintained in `docs/audit/test-results.md`. A local bootstrap-to-login test proves the CLI's hash/role contract against the test database only; it does not verify a real production account. A URL placeholder is not supplied as a service address. Device installation/runtime testing is intentionally not part of this audit.
