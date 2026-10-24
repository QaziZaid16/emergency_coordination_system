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
| Admin session restoration | The browser trusted the user object in `sessionStorage` and reopened the dashboard without checking whether its token was still valid. | Restore now validates `/auth/me`, refreshes the displayed account/permissions, and returns to sign-in when the session is expired or revoked. Logout calls the API and clears only this portal's session keys. |
| Admin API errors | FastAPI validation details are arrays of objects; the portal passed them to `Error` directly and displayed `[object Object]`. The local demo account also used the validator-rejected reserved `.test` domain. | Structured API details are converted to readable field errors. The local development admin now uses `superadmin@example.com`. |
| Co-Admin management lists | A Co-Admin granted only `manage_responders` or `manage_resources` could see the matching page but received 403 when the page loaded its list. | Read access to each management list now accepts its matching management permission while preserving server-side checks. Regression tests cover both roles. |
| Target account status | Responder suspension was shown to responder managers, but the API always required `manage_users` for account-status changes. | The backend selects the required permission from the target account role; responder managers cannot change ordinary user accounts. |
| Admin assignment workflow | Assignment used a browser prompt and omitted compatible resource choices and the recommendation rationale. | Assignment now uses an accessible in-app dialog populated by the live eligibility/recommendation endpoint and compatible resources; the API remains the final authority. |
| Incident review | Incident tables lacked a convenient detail/history view and dashboard activity was absent. | Added incident detail and history dialogs, priority-aware queue ordering, live operational metrics, and recent audit activity. |
| Co-Admin account listing | A Co-Admin with `manage_responders` could omit the role filter from `GET /admin/users`; the API then returned every account, including public users and administrator records. | Co-Admins must now specify a role. Existing backend permission checks authorize only the matching user or responder listing, and administrator roles remain Super Admin only. Regression coverage verifies unfiltered access and cross-role access are denied. |

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
