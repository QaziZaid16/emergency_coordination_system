# External requirements

No new credentials are needed for the implemented onboarding, design tokens, tests, or local synthetic-data seeder.

For connected environments, configure existing dependencies only where the feature is used:

| Feature | Configuration | Safe location | Until configured |
|---|---|---|---|
| Authenticated mobile/admin API | `API_BASE_URL` Dart define; HTTPS for release builds | Build/CI environment; not source files | Isolated local training mode remains available; shared portals report missing service configuration |
| API signing and database | `JWT_SECRET`, `DATABASE_URL` | Private backend `.env` locally; deployment secret store in hosted environments | API will refuse to start without a sufficiently long signing secret |
| Responder invitation email | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `PUBLIC_APP_URL` | Private backend environment/secret manager; never Flutter or browser bundle | Local development can use activation URLs; production requires successful email delivery |
| Optional incident text analysis | `AI_PROVIDER`, `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY` | Private backend environment only | Deterministic local rules analysis remains active; no provider call is made |
| Browser dashboard cross-origin access | Dashboard origin in `CORS_ORIGINS` | Backend environment | Host dashboard and API on an allowed origin |

Map/geocoding, push/SMS, emergency-agency dispatch, and hosted production deployment are not integrated or required by this local demo. If later added, they require separate privacy, security, cost, and operational review. Never paste secrets into Git or this document.
