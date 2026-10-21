# Verification record

## Current implementation

- Baseline before this audit: `flutter analyze` clean; 8 Flutter tests passed.
- Flutter static analysis after changes: `flutter analyze` — clean (Flutter 3.47.7 / Dart 3.13.5).
- Flutter suite after changes: `flutter test` — 23 tests passed. Coverage includes dispatch/store regressions, Remember Me storage, server validation, access expiry and refresh rotation, revoked/expired sessions, offline restore behavior, role routing, logout cleanup and account switching, SVG rendering, and compact large-text portal/workspace layouts including incident details and all five training sections.
- Backend suite: `python -m pytest -q` — 6 tests passed (one upstream Starlette/httpx deprecation warning). Coverage includes role isolation, 30-minute access expiry, 30-day remembered-session deadline, refresh rotation/replay rejection, logout revocation, and incident/assignment/resource lifecycle.
- Alembic: both migrations applied to clean SQLite databases. The running local demo database was upgraded to the refresh-token schema.
- Live API: remembered admin login, `/auth/me`, refresh rotation, old-refresh rejection, and logout revocation passed against the local SQLite-backed API.
- Branding: `assets/brand/official-logo.svg` is a byte-for-byte copy of the supplied source. Android foreground and monochrome vectors use the same logo paths; legacy launcher and PWA raster assets were generated proportionally. The icon PNG was visually inspected and resource packaging confirmed by `aapt`.
- Android builds: debug APK built with the local API URL; release APK built from current source. `aapt dump resources` confirmed the adaptive foreground/background, monochrome drawable, and app ID `edu.cgc.university.emergency_coordination_system` are packaged.
- Device check: the debug build was installed and launched on CPH2691 (Android 16). The portal chooser and authenticated Admin dashboard were inspected on-device; the supplied logo and dark palette rendered, and the dashboard loaded backend incident counts. This was a visual smoke check, not a pixel-diff comparison against the collage.
- PostgreSQL/Compose: configuration is included, but Docker/PostgreSQL were unavailable and were not verified.
- Current release APK: `release/emergency-coordination-system-demo.apk`; SHA-256 `8b01f78da2837c1cdb27d6d00db166ff2a956f04747e4143d0674ca2d87d2141`. It is debug-signed and has no production API URL compiled in.

## Remaining limitations

No hosted API, production database, HTTPS endpoint, push provider, map/routing provider, or emergency-agency integration is configured. Remembered-session restart recovery, permission-denied behavior across Android versions, PostgreSQL concurrency, comprehensive screen-reader/switch-access testing, broader text-scale coverage, performance, backup recovery, penetration testing, email recovery/MFA/rate limiting, and operational approval remain unverified.

See [`deep-bug-audit.md`](deep-bug-audit.md) for confirmed findings and remaining security/design items.
