# Release-readiness engineering report

Date: 2026-10-24. Scope: repository and local development environment only. No production system was accessed, modified, or deployed. The checkout contained pre-existing uncommitted changes before this follow-up; they were preserved.

## 1. Executive summary

The repository contains a Flutter Android app, a static administrative web client, and a FastAPI service with SQLAlchemy/Alembic. Local Flutter analysis/tests and backend tests pass. Alembic's five-revision chain upgrades a clean SQLite database and reports no model drift when run from a clean APFS staging copy. A two-worker database race test confirms SQLite's active-assignment unique index prevents duplicate active assignments for one incident.

Release readiness is **BLOCKED** for an Android artifact from this execution environment and **NOT VERIFIED** for PostgreSQL, production deployment, accessibility conformance, and backup restoration. The Flutter SDK and its caches are outside the writable sandbox; PostgreSQL clients and Docker are absent. No production secrets, signing keys, live service, or real responder/user data were used.

## 2. Architecture and environment discovered

- **Mobile:** Flutter 3.47.7 / Dart 3.13.5, Android target. The app includes authenticated User, Responder, and Admin portals plus a device-local training workspace. Shared operational records are read and written through the API.
- **Web:** static HTML, CSS, and JavaScript in `web/admin/`; responder activation page in `web/activate.html`. No separate web bundler is configured.
- **Backend:** FastAPI, SQLAlchemy 2, Alembic, psycopg 3, JWT access tokens, hashed rotating refresh credentials, role and object checks.
- **Databases:** SQLite is the default local setting and the automated test database. `backend/compose.yaml` defines PostgreSQL 17 Alpine and a private Compose volume for development; it binds the API to loopback and does not publish the database port.
- **Migrations:** five linear revisions, one head `a40b1331ee91`. Migration source files include exFAT AppleDouble sidecars; Alembic history scanning from this checkout can read those sidecars as Python. Run Alembic from a clean APFS staging copy on this machine.
- **Android build versions:** Gradle wrapper 9.3.1, Android Gradle Plugin 9.1.0, Kotlin plugin 2.4.0. Project `compileSdk`, `minSdk`, and `targetSdk` are inherited from Flutter constants. The app ID is `edu.cgc.university.emergency_coordination_system`. Release currently uses the debug signing config; it is not a production release signing setup.
- **Android permissions:** internet, coarse location, and fine location. Debug allows HTTP for local loopback development; release manifest traffic is configured to disallow cleartext.
- **Local environment:** macOS 26.6.2 arm64. Flutter is installed at `/Users/qazizaid/flutter`; Android SDK at `/Users/qazizaid/Library/Android/sdk`, with platforms 35, 36, and 37.0 and build tools 36.0. `/usr/bin/java` reports JDK 26. Android Studio's bundled JDK 25 was identified by the prior Flutter doctor output in the repository's verification record. `android/local.properties` points at these machine-local SDK paths and is not tracked.
- No repository CI workflow, production deployment manifest, backup job, backup script, or accessibility scanner configuration was found.

## 3. Baseline and build environment

Pre-existing working-tree changes are listed by `git status`; they were not discarded. The system Python does not have FastAPI, while `backend/.venv` has the project test dependencies. The current machine's exFAT checkout also contains `._*` files that break broad Flutter test discovery and direct Alembic revision scanning.

Flutter can be invoked and reported the expected SDK versions, but its SDK, pub cache, and Gradle cache paths are not writable from this sandbox. A debug build attempt emitted `Operation not permitted` while Flutter tried to write `bin/cache/engine.stamp.tmp` and `bin/cache/engine.realm`. `/private/tmp` is writable. No broad chmod, SDK replacement, or cache deletion was attempted. A Flutter doctor attempt in this turn hit the same SDK write restriction before completing its checks. The earlier Flutter diagnostic output recorded Android SDK 36 and accepted Android licenses; that is not a substitute for this turn's blocked build.

**Android debug build — BLOCKED.** Command attempted in an APFS source staging copy: `flutter build apk --debug --dart-define=API_BASE_URL=http://127.0.0.1:8000`. No new artifact was produced. The SDK write restriction is the observed blocker; JDK/Gradle compilation was not reached in this run. No device installation or runtime test was performed in this run. Existing prior APK/device checks are separately recorded in `test-results.md` and predate this verification.

## 4. Database and migrations

**PASS — SQLite migration history:** From a clean APFS staging copy, `alembic history` listed all five revisions and `alembic heads` returned only `a40b1331ee91`.

**PASS — clean SQLite upgrade:** All five revisions applied to a new temporary database.

**PASS — model drift check:** `alembic check` reported `No new upgrade operations detected` against that migrated database.

**NOT RUN — PostgreSQL:** `docker`, `psql`, and `pg_dump` are not installed/available in the execution environment. No PostgreSQL server was reachable or configured. PostgreSQL-specific locking behavior, constraints, migration DDL, and application integration are therefore unverified. No production database was targeted.

The models define foreign keys, severity/urgency and coordinate checks, resource quantity checks, unique reporter/idempotency keys, unique user email, and partial unique active-assignment indexes for incident and responder. SQLite validates only its own implementation of these constraints; PostgreSQL still needs a clean-database migration and integrity run.

## 5. Concurrency and data integrity

**PASS — bounded database race tests (SQLite only):** `backend/tests/test_concurrency.py` uses independent sessions and synchronized two-worker starts. Two responders competing for one incident produce one committed assignment and one unique-constraint conflict. Two workers reserving a single resource produce one successful conditional update and one zero-row result; `allocated` remains equal to capacity.

The API assignment path additionally uses PostgreSQL `FOR UPDATE` locks on incident/responder records and a conditional `UPDATE ... allocated < quantity` for resource capacity. Those mechanisms were source-reviewed, not exercised against PostgreSQL. No load or latency benchmark was performed; none is inferred from the correctness test.

## 6. Deployment and security review

### Fixed and verified

- **High — account-list authorization leak:** Co-Admins with responder management could request an unfiltered account list that included unrelated roles. The endpoint now requires Co-Admins to specify a role; existing server permission checks scope the allowed role. Regression coverage checks unfiltered denial, responder-only results, and cross-role denial. Backend suite passes.
- The backend requires a 32-character JWT secret outside test mode. CORS origins and SMTP/AI settings are environment-configured; the checked-in environment example uses placeholders. Compose does not publish PostgreSQL externally and binds the API to localhost.
- Password hashes, role checks, incident owner/assignment scope, refresh-token hashes, invitation token hashes, and idempotent incident creation are implemented in the inspected API/model paths and covered to varying degrees by the backend suite.

### Unresolved risks

- **High — no production release signing:** the Android `release` build type currently uses the debug signing config. A production artifact requires an independently managed signing key and protected CI/secret handling.
- **High — no login/refresh rate limiting:** invitation issuance has an in-process limit, but login/refresh abuse controls are absent. An in-memory limit would not reliably protect a multi-worker deployment; choose a shared mechanism before public exposure.
- **High — no production deployment verified:** there is no configured HTTPS endpoint, production proxy/headers configuration, managed database, network policy, monitoring, or deployment rollback procedure. CORS defaults are local-development origins and must be explicitly set for deployment.
- **Medium — account recovery/MFA:** password reset, verified email, MFA, and breached-password controls are not implemented. Product/operator policy is needed.
- **Medium — dependency vulnerability scan:** not run; no scanner result is claimed. Dependencies use broad compatible ranges, with `pubspec.lock` present for Flutter and Python requirements not fully lock-pinned.
- The dashboard stores its short-lived bearer token in `sessionStorage`; deployment must serve it only over HTTPS and retain careful XSS controls. This source review did not constitute a penetration test.

No production infrastructure was accessed. No dependency upgrades or credential changes were made.

## 7. Accessibility audit

**Source review and fixes:** Flutter icon-only clear-search and incident-refresh controls now have explicit tooltips in `lib/presentation/portals.dart`. The dashboard source includes semantic navigation, labeled form controls, native modal dialog markup, table headers, and live status/error regions.

**NOT RUN:** WCAG 2.2 AA conformance, automated axe or equivalent scans, screen-reader tests, switch access, keyboard-only browser traversal, and Android TalkBack checks were not run. The existing compact-width/text-scale widget test is useful regression coverage but does not establish accessibility conformance. Contrast values and touch targets were not exhaustively measured.

## 8. Backup and disaster recovery

No backup system, encrypted destination, retention policy, approved RPO/RTO, PostgreSQL client tools, or recovery database is configured. `docs/operations/backup-and-recovery.md` now provides PostgreSQL service-file based logical backup and isolated restore-drill procedures. It explicitly requires protected credentials, encrypted approved storage, a disposable target, integrity checks, and operator approval before production cutover. For discussion only, that runbook proposes RPO ≤24 hours and RTO ≤8 hours for the current development platform; these values are unapproved and unmeasured, and are not proposed for operational emergency-response use.

**NOT RUN — backup and restore:** no dump was produced and no database was restored. A documented command is not evidence of a tested backup. RPO/RTO and backup retention remain owner decisions; proposed discussion values are not approved, and there is no restore-duration or data-loss measurement.

## 9. Final regression results

| Check | Status | Evidence |
|---|---|---|
| Flutter analysis | PASS | `flutter analyze` — no issues, Flutter 3.47.7 / Dart 3.13.5. |
| Flutter tests | PASS | Explicit real test files: 26 passed. Broad `flutter test` discovery fails on AppleDouble `._` files. |
| Android debug build | BLOCKED | SDK cache write denied before compilation; no artifact from this run. |
| Backend tests | PASS | `backend/.venv/bin/python -m pytest -q` — 19 passed; one Starlette/httpx deprecation warning. |
| Concurrent assignment and capacity invariants | PASS (SQLite only) | Competing assignments: one commit and one constraint conflict. Competing capacity updates: one success and one zero-row update; capacity not exceeded. |
| Alembic clean migration | PASS (SQLite only) | Five revisions applied to new temporary database; one head. |
| Alembic model drift | PASS (SQLite only) | `alembic check`: no upgrade operations detected. |
| PostgreSQL migration/integration | NOT RUN | PostgreSQL server and client tooling unavailable. |
| Web JavaScript syntax | PASS | `node --check web/admin/app.js`. Static source only; no browser journey this turn. |
| Accessibility scans/manual AT | NOT RUN | No scanner or screen reader validation executed. |
| Backup/restore | NOT RUN | No PostgreSQL tools/server or backup target. |
| `git diff --check` | PASS | No whitespace errors. |

## 10. Files changed in this follow-up

- `backend/tests/test_concurrency.py` — synchronized, independent-session race coverage for the active-assignment uniqueness invariant.
- `lib/presentation/portals.dart` — accessible names for two icon-only controls.
- `docs/operations/backup-and-recovery.md` — protected PostgreSQL logical backup and isolated restore-drill runbook; not executed.
- `docs/audit/test-results.md` — fresh test/build/migration results.
- This report — verified findings, blockers, and release prerequisites.

The prior account-list security change is recorded in `backend/app/api.py`, `backend/tests/test_admin_security.py`, and `docs/audit/deep-bug-audit.md`; it predates this follow-up and its test is included in the 19-test pass.

## 11. Commands and outcomes

From the repository root:

```sh
flutter analyze
flutter test test/api_client_test.dart test/operations_store_test.dart test/dispatch_rules_test.dart test/widget_test.dart
node --check web/admin/app.js
git diff --check
```

From `backend/`:

```sh
./.venv/bin/python -m pytest -q
```

Alembic `history`, `heads`, `upgrade head`, and `check` all passed against a temporary SQLite database from a clean APFS copy. Direct Alembic history scanning from the exFAT checkout failed on binary AppleDouble sidecars; no sidecar files were deleted.

## 12. Local run instructions

Backend setup and migrations: follow `backend/README.md`; set a private `JWT_SECRET`, create/use a development database, run `alembic upgrade head`, provision the first administrator, then start `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.

Flutter: `flutter pub get`, then `flutter run -d <device-id>`. For a USB-connected Android device using local API, run `adb reverse tcp:8000 tcp:8000` and pass `--dart-define=API_BASE_URL=http://127.0.0.1:8000`. Release builds must use HTTPS and a non-debug signing setup before distribution.

Web: serve the complete `web/` directory with a static server and configure its origin in backend `CORS_ORIGINS`; open `/admin/index.html`. The web client has no separate compile/build command.

## 13. Release prerequisites and recommended order

1. Build Android in a writable, correctly configured CI/developer environment with the project's pinned toolchain; configure protected release signing, then install and exercise the resulting APK.
2. Provision isolated PostgreSQL 17 test infrastructure; run clean migration, schema/integrity, API integration, and concurrency tests there.
3. Define a production deployment, TLS termination, allowed origins, secret custody, least-privilege DB role, rate limiting, monitoring, and rollback procedures.
4. Approve data retention, location privacy, backup encryption/retention, RPO/RTO, and recovery ownership; execute and time an isolated restore drill.
5. Run WCAG-oriented automated scans and manual keyboard, TalkBack/screen-reader, contrast, text scaling, and touch-target review on supported devices.
6. Run dependency vulnerability scanning and a focused security review before any public deployment.

No deployment was performed. This repository remains a development coordination platform, not an operational emergency dispatch service.
