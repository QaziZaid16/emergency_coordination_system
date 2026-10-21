# Verification record

## Current implementation

- Flutter static analysis: `flutter analyze` — clean (Flutter 3.47.7 / Dart 3.13.5).
- Flutter suite: `flutter test` — 8 tests passed.
- Backend suite: `python -m pytest -q` — 5 tests passed (one upstream Starlette/httpx deprecation warning).
- Alembic initial migration: applied to a clean in-memory SQLite database from the APFS staging copy.
- API and Android client: local SQLite-backed FastAPI service exercised from the connected Android phone through `adb reverse`. A user account submitted an SOS request and retrieved its server status. This verifies local development connectivity only; it does not contact emergency services.
- Release artifact: rebuilt successfully from current source; `release/emergency-coordination-system-demo.apk`, SHA-256 `317aa90a47ad819e08e2770f11a45cc55fb493277526964582721f5558eb126b`. This demo artifact is debug-signed.
- PostgreSQL/Compose: configuration is included, but Docker/PostgreSQL were unavailable and were not verified.

## Backend workflow coverage

Automated API tests cover public user registration, role mismatch and access isolation, stale GPS rejection, idempotent SOS submission, priority calculation, admin dashboard counts, assignment/resource allocation and conflict handling, responder status ordering, status history, resource release, responder history, reassign access revocation, and logout session revocation.

## Limitations

No hosted API, production database, HTTPS endpoint, push provider, map/routing provider, or emergency-agency integration is configured. The physical phone check used a local development API and SQLite database. Android permission-denied behavior, PostgreSQL concurrency, accessibility, performance, backup recovery, penetration testing, and operational approval remain unverified.

## Previous prototype verification

The prior local-only training workspace had a physical-device walkthrough and seven passing Flutter tests before the shared portals were added. That is historical evidence for the training workspace; it does not replace the current suite results above.
