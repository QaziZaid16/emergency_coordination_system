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

## Product redesign follow-up

- `flutter analyze` — passed, no issues (Flutter 3.47.7 / Dart 3.13.5). The first sandboxed invocation could not write Flutter SDK cache metadata outside the repository; the requested local check then passed with SDK cache access.
- `flutter test test/api_client_test.dart test/dispatch_rules_test.dart test/operations_store_test.dart test/widget_test.dart` — passed, 28 tests, including onboarding persistence/skip, login password validation, remembered session restore/logout, revoked sessions, narrow layout, API session behavior, and dispatch/storage workflows.
- Unrestricted `flutter test` discovery — failed due non-source AppleDouble `._*.dart` sidecars in the mounted checkout. The explicit real test files above pass; CI runs on a normal Git checkout and lists these files explicitly.
- `backend/.venv/bin/python -m pytest -q` — passed, 19 tests, including the new short-password login validation assertion. One pre-existing Starlette/httpx deprecation warning remains.
- Demo seed — passed on a disposable SQLite database with 50 responders, ten assigned incidents, one resource, and demo role accounts. A repeat run and counts/assignment-capability invariants were checked. No project database was seeded during this run; generated temporary database credentials were discarded.
- `node --check web/admin/app.js` and `git diff --check` — passed.
- GitHub-hosted workflow execution, browser end-to-end/accessibility review, PostgreSQL, and physical-device testing — not run. No phone was installed, modified, or used.
- Android debug build — passed from `/private/tmp/ecs_redesign_android_build` after excluding source-volume AppleDouble sidecars. Artifact: `/private/tmp/ecs_redesign_android_build/build/app/outputs/flutter-apk/app-debug.apk` (162,037,826 bytes, SHA-256 `5395a15367d718cc3556774eb1a1c3cf2c51bcf8baa489e8f06759f1bf2087b3`). The direct exFAT checkout build failed at `parseDebugLocalResources` on `._drawable`; no phone installation was attempted.

## Direct login and hosting follow-up

- Flutter 3.47.7 / Dart 3.13.5, APFS staging copy: `flutter analyze` — passed with no issues. Explicit tracked suite (`api_client_test.dart`, `api_configuration_test.dart`, `dispatch_rules_test.dart`, `operations_store_test.dart`, `widget_test.dart`) — 30 passed. This includes direct login without API config, onboarding-to-login flow, no normal-flow portal/training shortcut, URL validation, and existing remembered-session and workflow tests.
- Backend from `backend/`: `.venv/bin/python -m pytest -q` — 31 passed, one existing Starlette/httpx deprecation warning. New coverage verifies one-time bootstrap password hashing and a successful `/auth/login` response with `super_admin` role in the in-memory SQLite test service, production configuration validation, health endpoints, and dashboard CORS preflight for responder-capability PUT.
- `python -m compileall` on modified backend implementation/tests — passed. `node --check` for admin JS, config generator, and config file; `sh -n scripts/build_android_release.sh`; `vercel.json` JSON parse; `git diff --check` — passed.
- `node scripts/build_web_config.mjs` — prepared local static config with no API URL. Required production web config correctly rejects a missing `ECS_API_BASE_URL`; Android release wrapper correctly rejects a missing `API_BASE_URL`. A production static build/mobile release build was not run because there is no verified API URL.
- Local static preview at `http://localhost:8080/admin/index.html` and `/admin/config.js` returned HTTP 200. This is a local static-file preview only; no backend was configured or running for it.
- No physical Android device was accessed, installed, or modified. No real administrator was provisioned. The admin authentication check used only an ephemeral test database. No cloud deployment, DNS, PostgreSQL server, live browser/API end-to-end journey, accessibility scan, or backup restore was run.

## Android install and startup follow-up (2026-10-24)

- A remembered session on the device exposed one remaining no-API startup issue: the app correctly routed to login, but displayed a restore warning. Startup now suppresses that warning when the API origin is absent, while retaining the saved session and showing sign-in unavailability only after the user submits the login form. A widget regression covers that case.
- Flutter 3.47.7 / Dart 3.13.5 from `/private/tmp/ecs_android_install`: `flutter analyze` — clean; full `flutter test` discovery — 31 passed after removing three exFAT AppleDouble `._*.dart` sidecars from the temporary staging copy; `dart format` — clean. The first unrestricted discovery attempt hit those non-source sidecars and crashed; no repository tests failed.
- `flutter build apk --debug` — passed. APK: `/private/tmp/ecs_android_install/build/app/outputs/flutter-apk/app-debug.apk`; package `edu.cgc.university.emergency_coordination_system`; version `1.0.1+2`; SHA-256 `42a345a7d21b6194f155d128be319970bcbc4c8a247c9d2127c4d163b61edf29`. Its Android Debug certificate SHA-256 matched the installed package's certificate.
- Device `a102172d` (`CPH2691IN`, Android 16/API 36): `adb install -r` succeeded in place. The app launched without clearing data. Onboarding Skip led to the direct login screen; a force-stop and relaunch returned directly to login. Screen captures were inspected; the service URL portal and startup warning were absent. Recent logcat contained no fatal exception for this package.
- The installed debug build has no API origin and no backend is running on the phone's network path. Login and live authentication were not attempted; they remain unavailable until a real API origin and backend are configured. No production release was built, and no cloud deployment or production login was verified.

## Persistent notifications and automatic assignment follow-up (2026-10-24)

- `backend/.venv/bin/python -m pytest -q` — **35 passed**, one existing Starlette/httpx deprecation warning. Added checks for persisted incident/admin inbox events, per-account read authorization, scoped Co-Admin event visibility, opt-in severity-bounded automatic assignment, assignment source, missing fresh responder GPS review, and the assignment → responder status lifecycle → resolution notification to the reporting user.
- Flutter explicit tracked suite (`test/api_client_test.dart test/api_configuration_test.dart test/dispatch_rules_test.dart test/operations_store_test.dart test/widget_test.dart`) — **31 passed**. `flutter analyze` — passed with no issues.
- Disposable SQLite Alembic `upgrade head` and `current` — passed; head is `b271c7e05d3a`. This includes the assignment-source column and nullable actor for system-created assignments.
- `node --check web/admin/app.js` and `git diff --check` — passed.
- Dart formatter updated `lib/presentation/portals.dart` and reported zero changes on a later dry run, but both commands exited non-zero after Dart attempted to update telemetry-session metadata in the read-only user SDK directory. Flutter analyzer and tests succeeded after the source formatting.
- `python -m compileall -q app migrations tests` was attempted and failed because recursive discovery reads AppleDouble `._*.py` sidecars as Python and raises null-byte syntax errors. The backend tests import the real modules and all pass.
- PostgreSQL, concurrent automatic-assignment race simulation, remote CI, browser interactive/accessibility testing, production hosting, FCM/email delivery, and a new APK build/install were not run.
