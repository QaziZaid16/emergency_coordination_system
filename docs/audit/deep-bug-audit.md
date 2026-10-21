# Deep bug audit

Audit date: 2026-10-22. Baseline Flutter checks were run before edits: `flutter analyze` clean; 8 Flutter tests passed. Repository, portal navigation, auth API, secure storage dependency, Android manifest/resources, and backend schema/tests were inspected.

## Confirmed findings

| Area | Confirmed issue | Change |
|---|---|---|
| Remember Me | Every login wrote its bearer token to secure storage whether the person wanted persistence or not. | Added an opt-in control; unchecked sessions stay in memory only. Old v1 saved sessions are deleted during upgrade so consent is not inferred. |
| Startup authentication | App startup never read or validated the stored session, so users saw the chooser and no server check protected restoration. | Startup reads only an opted-in session, refreshes it if needed, validates identity/role through `/auth/me`, and routes directly to that role's portal. |
| Session expiry | Server issued only a 30-minute access token and the client had no refresh path or expiry redirect. | Added rotating opaque refresh credentials, hashed refresh-token persistence, bounded 30-day server session, proactive client refresh, and redirect/cleanup for expired or revoked sessions. |
| Session revocation | Logout errors were silently swallowed after local state changed. | Local data is cleared on logout; if the backend cannot confirm revocation, the chooser reports that server revocation could not be confirmed. |
| Account switching | There was no explicit cleanup/revocation step before a new login. | New login attempts best-effort revoke the previously remembered session before clearing it; role is always checked against the backend. |
| Icon | Existing mark had four unrelated node colors, a shield/pulse layered inside a circle, and small details competing at launcher sizes. | Replaced it with a location hub silhouette and two connected response nodes using the app's refined teal/coral palette. Updated Android adaptive, monochrome, density, and PWA assets. |
| Login polish | Password visibility control had no explicit accessibility tooltip; email validation only checked for `@`. | Added named show/hide controls, a basic address-shape validator, keyboard actions, opt-in setting, loading/validation behavior, and branded entry screens. |

## Reviewed and preserved

- Role mismatch is rejected by the API; protected endpoints verify the server-side role and incident ownership/assignment.
- SOS requests already use idempotency keys and require a confirmation step; the success text states that the platform does not contact emergency services.
- Assignment uses transaction checks and database uniqueness constraints; responder status progression, reassignment scope, resource release, and audit behavior are covered by backend tests.
- Training workspace persistence remains separate from server records.

## Remaining risks / dependencies

- Refresh-token rotation is single-current-token rotation. PostgreSQL and multi-process concurrency behavior still require deployment-level verification.
- Persistent sessions can last up to 30 days by default (configurable 1–365); production operators should select a policy, rate-limit refresh/login, and monitor abuse.
- No email verification, password reset, MFA, lockout/rate limiting, or breached-password checks exist.
- Android KeyStore behavior and restart recovery need a physical-device test using the final rebuilt APK. The Android build verifies resources compile and package but does not replace a device restart test.
- Screen-reader, switch-access, broad text-scale, dark-theme, and cross-version launcher-mask reviews have not been completed.
- The API is local development only; no hosted HTTPS backend was available for production-wide login validation.
