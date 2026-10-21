# Deep bug audit

Audit date: 2026-10-22. Baseline Flutter checks were run before edits: `flutter analyze` clean; 8 Flutter tests passed. Repository, portal navigation, auth API, secure storage dependency, Android manifest/resources, and backend schema/tests were inspected.

## Confirmed findings

| Area | Confirmed issue | Change |
|---|---|---|
| Remember Me | Every login wrote its bearer token to secure storage whether the person wanted persistence or not. | Added an opt-in control; unchecked sessions stay in memory only. Old v1 saved sessions are deleted during upgrade so consent is not inferred. |
| Startup authentication | App startup never read or validated the stored session, so users saw the chooser and no server check protected restoration. | Startup reads only an opted-in session, refreshes it if needed, validates identity/role through `/auth/me`, and routes directly to that role's portal. |
| Session expiry | Server issued only a 30-minute access token and the client had no refresh path or expiry redirect. | Added rotating opaque refresh credentials, hashed refresh-token persistence, bounded 30-day server session, proactive client refresh, and redirect/cleanup for expired or revoked sessions. |
| Session revocation | Logout errors were silently swallowed after local state changed. | Local data is cleared on logout; if the backend cannot confirm revocation, the chooser reports that server revocation could not be confirmed. |
| Account switching | There was no explicit cleanup/revocation step before a new login. | A new login is blocked if revocation of a previous remembered account cannot be confirmed; an already-invalid session is cleared before proceeding. |
| Branding | The previous custom mark did not match the supplied official logo. | The original red-and-green SVG is now the Flutter brand mark; proportion-preserving Android adaptive, monochrome, density, splash, and PWA assets derive from it. |
| Login polish | Password visibility control had no explicit accessibility tooltip; email validation only checked for `@`. | Added named show/hide controls, a basic address-shape validator, keyboard actions, opt-in setting, loading/validation behavior, and branded entry screens. |
| Responsive layout | The training workspace app bar overflowed at 320 px with larger text because its title, training subtitle, and workspace action competed for width. | Removed the redundant app-bar subtitle; the training status remains on the overview banner and the page title ellipsizes on narrow screens. |
| Visual system | UI surfaces used a light palette despite the supplied reference's dark interface. | Centralized reference-led dark colors, spacing, radii, component themes, and Android system-bar styling for all portals and training screens. |

## Reviewed and preserved

- Role mismatch is rejected by the API; protected endpoints verify the server-side role and incident ownership/assignment.
- SOS requests already use idempotency keys and require a confirmation step; the success text states that the platform does not contact emergency services.
- Assignment uses transaction checks and database uniqueness constraints; responder status progression, reassignment scope, resource release, and audit behavior are covered by backend tests.
- Training workspace persistence remains separate from server records.

## Remaining risks / dependencies

- Refresh-token rotation is single-current-token rotation. PostgreSQL and multi-process concurrency behavior still require deployment-level verification.
- Persistent sessions can last up to 30 days by default (configurable 1–365); production operators should select a policy, rate-limit refresh/login, and monitor abuse.
- No email verification, password reset, MFA, lockout/rate limiting, or breached-password checks exist.
- Android KeyStore behavior and restart recovery should be retested on the final rebuilt APK. A widget layout regression currently covers 320 px width at 1.25 text scale; it is not a substitute for broader accessibility testing.
- Screen-reader, switch-access, comprehensive text-scale, and cross-version launcher-mask reviews remain outstanding.
- The API is local development only; no hosted HTTPS backend was available for production-wide login validation.
