# Verification record

## Current implementation

- Baseline before this audit: `flutter analyze` clean; 8 Flutter tests passed.
- Flutter static analysis after changes: `flutter analyze` — clean (Flutter 3.47.7 / Dart 3.13.5).
- Flutter suite after changes: `flutter test` — 21 tests passed. Coverage includes dispatch/store regressions, Remember Me storage, server validation, access expiry and refresh rotation, revoked/expired sessions, offline restore behavior, role routing, logout cleanup and account switching, and a compact large-text login layout.
- Backend suite: `python -m pytest -q` — 6 tests passed (one upstream Starlette/httpx deprecation warning). Coverage includes role isolation, 30-minute access expiry, 30-day remembered-session deadline, refresh rotation/replay rejection, logout revocation, and incident/assignment/resource lifecycle.
- Alembic: both migrations applied to clean SQLite databases. The running local demo database was upgraded to the refresh-token schema.
- Live API: remembered admin login, `/auth/me`, refresh rotation, old-refresh rejection, and logout revocation passed against the local SQLite-backed API.
- Android builds: debug APK built with the local API URL; release APK built from current source. `aapt dump resources` confirmed the adaptive foreground/background, Android 13 monochrome layer, density launcher assets, and app ID `edu.cgc.university.emergency_coordination_system` are packaged.
- Device check: ADB reported no connected Android devices during this audit, so the new build could not be installed for a fresh physical-device restart or visual check. Earlier phone/API evidence predates the Remember Me changes and is not counted as device verification for this audit.
- PostgreSQL/Compose: configuration is included, but Docker/PostgreSQL were unavailable and were not verified.
- Current release APK: `release/emergency-coordination-system-demo.apk`; SHA-256 `3262297dce56f1f2305216a47e88dc8cc6d4740b479bb98b6bb2d388cfeafda0`. It is debug-signed and has no production API URL compiled in.

## Remaining limitations

No hosted API, production database, HTTPS endpoint, push provider, map/routing provider, or emergency-agency integration is configured. Android KeyStore behavior is provided through `flutter_secure_storage` but was not exercised on a connected device in this audit. Permission-denied behavior across Android versions, PostgreSQL concurrency, complete accessibility, performance, backup recovery, penetration testing, email recovery/MFA/rate limiting, and operational approval remain unverified.

See [`deep-bug-audit.md`](deep-bug-audit.md) for confirmed findings and remaining security/design items.
