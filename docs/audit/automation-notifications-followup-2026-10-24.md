# Automatic coordination and notifications follow-up

Date: 2026-10-24

This is an academic demonstration project. Nothing in this report indicates contact with a real emergency service or authorization for operational dispatch.

## A. Existing project audit

The repository is a Flutter Android client, static HTML/CSS/JavaScript administrator dashboard, and FastAPI/SQLAlchemy API with SQLite development/test support and PostgreSQL deployment preparation. It already had server-enforced roles, session rotation, idempotent incident submission, status history, constrained manual assignment, deterministic recommendations, optional structured AI analysis, admin read-only copilot, and 12-second mobile polling. Direct login was already repaired and previously verified. Before this change, there were no persisted notifications or runtime automatic assignment policy.

## B. Automatic assignment

- Added a persisted policy, default disabled with maximum severity 3/5. Only a Super Admin can change it. The Super Admin dashboard exposes the setting.
- A candidate must have an active responder account, an available profile, a matching emergency capability, no active assignment, and fresh (≤15 minutes), accurate (≤100 m) GPS. Incident GPS must meet the same freshness and accuracy limits.
- Deterministic ranking uses configured distance and 24-hour completed-workload weights with responder name as stable tie-break. Distance is straight-line, not travel time. Skill match, account state, availability, and existing workload are eligibility gates.
- Critical/high cases above the configured severity ceiling, stale or missing locations, or no eligible responder stay unassigned for coordinator review.
- Assignment, source, status history, audit decision, and inbox events commit together. Existing unique active-assignment indexes protect responder and incident exclusivity. Automatic assignment conflicts roll back the savepoint and preserve the incident as unassigned with an admin review event.
- Manual assignment remains available. Incident data and dashboard label automatic versus manual.

## C. AI integration

No provider/model was newly selected. The existing backend has an AnalysisProvider abstraction, OpenAI-compatible implementation, validated structured output, bounded timeout/retry/rate controls, and deterministic fallback. The default AI_PROVIDER=none does not call a hosted model. No API credential was present, so hosted inference was not enabled or verified. AI cannot make dispatch decisions. An external provider needs a server-side key, a selected model and data-handling review. Hugging Face's provider pricing currently documents limited monthly free credits and pay-as-you-go beyond that allowance; open-weight does not mean hosted inference is free. See [Hugging Face Inference Providers pricing](https://huggingface.co/docs/inference-providers/en/pricing).

## D. Notifications

Persistent recipient-scoped in-app notification records are created in the business transaction, with uniqueness per recipient and event key. User, responder, and administrator APIs can list/read their own inbox; mobile User and Responder portals and the web administrator dashboard render it. Events cover incident receipt, assignment, reassignment, cancellation, meaningful status transitions, and automatic-assignment review/failure. Push (FCM), device token registration, delivery attempts to external providers, and notification email are not implemented or claimed. FCM needs a Firebase project, mobile configuration, backend credentials, and device verification per [Firebase's Flutter setup](https://firebase.google.com/docs/cloud-messaging/flutter/get-started).

## E. End-to-end workflow

Automated backend tests exercised incident submission, persisted assignment, responder inbox visibility, responder status transitions through resolution, and reporter resolution notification. The synthetic workflow is covered in an in-memory SQLite test service. It is not a live mobile/API/device journey. Admin overview and notification inbox use browser polling every 12 seconds while visible; mobile portals already poll on the same interval.

## F. UI/UX and login

The unwanted intermediate portal/direct-login issue was already fixed and physically verified in the previous Android follow-up documented in test-results.md. This change adds a notification inbox to mobile User/Responder app bars and Notifications/Automation Policy views to the browser dashboard. Flutter static analysis and widget suite pass. A browser-based interactive walkthrough of these new views was not run.

## G. Hosting

Existing Docker, static hosting configuration, production API URL validation, CORS, health checks, migrations, and runbook remain repository-side preparation only. No service URL, hosting credentials, Firebase project, or production database was provided. No live deployment, remote PostgreSQL test, production APK, or public API endpoint was produced in this follow-up. Hosting evaluation and free-tier persistence/sleep limits are documented in docs/operations/hosting.md; no paid service was created.

## H. Testing

- backend/.venv/bin/python -m pytest -q — **35 passed**, one existing Starlette/httpx deprecation warning. Includes new recipient isolation/read tests, automatic policy authorization/eligibility/manual fallback cases, and the synthetic assignment-to-resolution notification flow.
- Explicit Flutter test suite (api_client_test.dart, api_configuration_test.dart, dispatch_rules_test.dart, operations_store_test.dart, widget_test.dart) — **31 passed**.
- flutter analyze — passed with no issues.
- Alembic upgrade head and current on a disposable SQLite DB — passed at b271c7e05d3a.
- node --check web/admin/app.js and git diff --check — passed.
- python -m compileall -q app migrations tests — attempted but discovers exFAT AppleDouble ._*.py metadata files and fails with null-byte syntax errors. The normal Python test suite imports and exercises the changed modules successfully. The source checkout remains subject to the previously documented sidecar limitation.
- Dart formatter wrote the updated Dart file, then the formatter process returned an error trying to update telemetry metadata under the read-only user SDK directory. A dry formatting check reported no changed files before the same telemetry error. Analyzer and Flutter tests pass.
- Not run: PostgreSQL concurrency/migrations, GitHub-hosted CI, live browser E2E/accessibility test, actual FCM/email delivery, cloud deployment, or a new Android build/install.

## I. Demo preparation

Existing development seeding creates 50 synthetic responders and ten sample assigned incidents, and is restricted to development SQLite. This follow-up did not seed the project database. Use the documented command in docs/DEMO_ACCOUNTS.md only against a disposable local development database. Demo credentials are generated at first creation and printed once.

## J. Git

At the time this report was written, the working branch was main; changes had not yet been committed.

## K. External inputs required

- A real HTTPS API origin, managed PostgreSQL service, and hosting-account credentials are required for public deployment; configure secrets through the chosen provider, not Git. No endpoint can be placed in the app without this.
- A Firebase project, Android app registration/config, and backend service credentials are required only if push notifications are wanted. Store server credentials in host secrets and put only client Firebase configuration in the Android build as required by Firebase.
- A chosen hosted AI provider/model and server-side API key are required only to enable hosted inference. Store its key in backend hosting secrets and review provider cost/privacy terms first.
- Production Android signing material and protected release pipeline secrets are required to produce a production-signed APK. This repo's current debug signing is not a Play-ready release.

None of those external services or costs was provisioned for this task.
