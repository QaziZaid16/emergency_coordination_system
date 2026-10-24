# Verification record

## Current implementation

- Baseline before this audit: `flutter analyze` clean; 8 Flutter tests passed.
- Flutter static analysis after changes: `flutter analyze` — clean (Flutter 3.47.7 / Dart 3.13.5).
- Flutter suite (2026-10-22 final run): `flutter test` — 26 tests passed. `flutter analyze` reported no issues. Checks ran from `/private/tmp/ecs_android_build`, an APFS staging copy, because Flutter's source-volume discovery reads AppleDouble metadata as Dart files.
- Backend suite (2026-10-22 final run): `python -m pytest -q` — 17 tests passed with one upstream Starlette/httpx deprecation warning. This includes the permission-scoped admin regressions and existing authentication, incident, assignment, resource, and intelligence tests.
- Admin browser smoke check: headless Chrome signed in to the local API, rendered the overview and all seven admin sections, exercised logout, and reported no JavaScript exceptions. At 390 px the document had no horizontal overflow; mobile navigation opened and sign-out remained available. The development database contained no incidents, so the overview correctly showed zero values and empty states.
- Alembic: both migrations applied to clean SQLite databases. The running local demo database was upgraded to the refresh-token schema.
- Live API: remembered admin login, `/auth/me`, refresh rotation, old-refresh rejection, and logout revocation passed against the local SQLite-backed API.
- Branding: `assets/brand/official-logo.svg` is a byte-for-byte copy of the supplied source. Android foreground and monochrome vectors use the same logo paths; legacy launcher and PWA raster assets were generated proportionally. The icon PNG was visually inspected and resource packaging confirmed by `aapt`.
- Android build: version `1.0.1+2`, ARM64 debug APK built from the APFS staging copy with `API_BASE_URL=http://127.0.0.1:8001`; path `/private/tmp/ecs_android_build/build/app/outputs/flutter-apk/app-debug.apk`. The repository's previously published demo APK was left unchanged.
- Connected phone: selected the only ADB device, CPH2691 (`a102172d`, Android 16 / API 36), package `edu.cgc.university.emergency_coordination_system`. The installed app and APK had the same Android Debug certificate. `adb install -r` succeeded and package metadata reports version `1.0.1` / code `2`; the launch intent was accepted. The earlier startup capture showed the sign-in screen and local API URL, but the phone's foreground changed to Android system UI during final verification. The recent logcat scan found no fatal app crash. Interactive user SOS and responder task workflows were not exercised on the phone during this run.
- Web build: the admin client is static HTML/CSS/JavaScript with no separate bundler/build target; the updated files were served directly by the existing static server.
- PostgreSQL/Compose: configuration is included, but Docker/PostgreSQL were unavailable and were not verified.
- Current release APK: `release/emergency-coordination-system-demo.apk`; SHA-256 `8b01f78da2837c1cdb27d6d00db166ff2a956f04747e4143d0674ca2d87d2141`. It is debug-signed and has no production API URL compiled in.

## Remaining limitations

No hosted API, production database, HTTPS endpoint, push provider, map/routing provider, or emergency-agency integration is configured. Remembered-session restart recovery, permission-denied behavior across Android versions, PostgreSQL concurrency, comprehensive screen-reader/switch-access testing, broader text-scale coverage, performance, backup recovery, penetration testing, email recovery/MFA/rate limiting, and operational approval remain unverified.

See [`deep-bug-audit.md`](deep-bug-audit.md) for confirmed findings and remaining security/design items. The connected-phone check was a launch smoke test; full role workflows were covered by automated tests and browser/API verification, not on-device interaction.

## Fresh verification on 2026-10-24

- `flutter analyze` — clean on Flutter 3.47.7 / Dart 3.13.5.
- `flutter test` — direct discovery failed because Flutter attempted to decode exFAT/macOS AppleDouble files (`test/._widget_test.dart`, `test/._api_client_test.dart`). Running the four real test files explicitly with `flutter test test/api_client_test.dart test/operations_store_test.dart test/dispatch_rules_test.dart test/widget_test.dart` passed all 26 tests.
- `backend/.venv/bin/python -m pytest -q` — 17 passed, with one Starlette/httpx deprecation warning. The default system Python lacks FastAPI; the repository virtual environment was used.
- A temporary SQLite database migrated successfully through Alembic head `a40b1331ee91`.
- `git diff --check` — clean.
- An Android debug build was attempted from an APFS staging copy. Flutter could not update its SDK cache under `/Users/qazizaid/flutter` because that path is outside the permitted writable workspace; no new APK was produced. The earlier Android build recorded above predates this verification run.
- PostgreSQL, Compose, hosted API behavior, and interactive physical-device workflows were not tested in this run.

## Release-readiness follow-up

See [release-readiness-2026-10-24.md](release-readiness-2026-10-24.md) for the environment, security, accessibility, database, and recovery report. Follow-up results: backend suite 19 passed; two synchronized independent-session race tests passed on SQLite; clean APFS-staged Alembic `history`, `heads`, `upgrade head`, and `check` passed; JavaScript syntax and `git diff --check` passed. PostgreSQL, Android build, accessibility tooling/manual assistive technology, and backup/restore remain blocked or not run as detailed in that report.
