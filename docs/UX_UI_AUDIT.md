# UX and UI audit

**Review date:** 2026-10-24
**Status:** Source review and automated checks; no physical-device or full screen-reader audit.

## Verified architecture and capabilities

- Flutter Android client: `lib/main.dart`, `lib/presentation/portals.dart`, and `lib/presentation/home_page.dart`.
- FastAPI service with SQLAlchemy/Alembic and SQLite development support; role authorization is enforced on the API.
- Vanilla JavaScript browser admin at `web/admin/`; routes cover overview, incidents, responders, users, resources, reports, audit history, and Super Admin-only Co-Admin management.
- Authenticated mobile sessions are routed using server-returned roles. Remembered sessions use secure storage, refresh rotation, `/auth/me` revalidation, and server logout revocation.
- Separate local-only training mode is intentionally isolated from backend accounts and incidents.

## Issues addressed in this execution

- First launch previously opened sign-in without introductory context. Added three slides, Back/Next/Skip/Get started actions, progress semantics, truthful feature copy, and a local completion marker. Existing validated remembered sessions bypass onboarding. A failed network revalidation does not clear the saved session or mark onboarding complete.
- The browser already had responsive operational sections, role-scoped navigation, API error display, forms, and focus styles. Its blue/navy palette differed from the Flutter coral/charcoal theme and it downloaded Google Fonts at runtime. Flutter colors now share the browser palette, urgent red remains semantic, and the browser uses system fonts offline.
- Public account, invitation, and admin creation already required 12-character passwords, but login accepted shorter values. The API and mobile form now enforce the same existing 12-character policy.
- Added explicit, SQLite-only, development-only seeding for 50 synthetic responder profiles, role demo accounts, and real assignment rows.
- Added a least-privilege GitHub Actions workflow for backend tests, Flutter checks, and browser JavaScript syntax.

## Implementation sequence used

1. Preserve the existing FastAPI API, role permissions, incident ownership, secure refresh-token flow, and isolated training workspace.
2. Add local first-launch onboarding only for users without a validated remembered session; preserve explicit logout and existing role routing.
3. Align Flutter palette and browser typography without changing dashboard routes or business actions.
4. Align login password checks with the pre-existing 12-character account-creation policy.
5. Add opt-in, local SQLite seed data outside startup and migrations; validate idempotency, capability matching, and production rejection.
6. Run targeted client/API checks, build from a clean staging copy, document limitations, then commit only scoped files.

## Remaining issues and limits

- Mobile layout/screens were source-reviewed and widget-tested, but this run did not perform manual Android device/resolution or TalkBack testing.
- Browser dashboard was source-reviewed and syntax-checked; no browser automation or manual keyboard journey was available.
- The app and API are not production emergency dispatch software. The API has no configured email delivery, push notifications, live tracking, maps, emergency-agency integration, shared multi-process rate limiter, or production deployment.
- Mobile administrative accounts receive a dashboard-only message; the admin dashboard is browser-only by design.

## Baseline checks

- `flutter analyze`: passed before these changes.
- `flutter test`: runner failed before complete test execution because macOS AppleDouble `._*.dart` files in the checkout are not UTF-8, then surfaced constructor call sites affected by the new onboarding parameter. The explicit tracked Dart test list is used for later verification and CI.
- `backend/.venv/bin/python -m pytest -q`: 19 passed; one upstream Starlette/httpx deprecation warning.
- `node --check web/admin/app.js`: passed.
- Worktree was clean on `main` before this execution.
