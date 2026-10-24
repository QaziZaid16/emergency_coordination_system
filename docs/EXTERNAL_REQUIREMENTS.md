# External requirements

No new credentials are needed for the implemented onboarding, design tokens, tests, or local synthetic-data seeder.

For connected environments, configure existing dependencies only where the feature is used:

| Feature | Configuration | Safe location | Until configured |
|---|---|---|---|
| Authenticated mobile API | `API_BASE_URL` Dart define; HTTPS for release, loopback HTTP only for debug | Mobile build environment; public URL only | Direct login stays usable; sign-in is unavailable until an API origin is configured |
| Hosted admin dashboard API origin | `ECS_API_BASE_URL` at static build time; HTTPS required | Vercel build environment; public URL only | Local development page permits manual service URL entry |
| API signing and database | `JWT_SECRET`, `DATABASE_URL` | Private backend `.env` locally; deployment secret store in hosted environments | API will refuse to start without a sufficiently long signing secret |
| Responder invitation email | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `PUBLIC_APP_URL` | Private backend environment/secret manager; never Flutter or browser bundle | Local development can use activation URLs; production requires successful email delivery |
| Optional Gemma incident analysis | `AI_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, optional `OPENROUTER_MODEL`, `OPENROUTER_BASE_URL`; bounded by `AI_TIMEOUT_SECONDS`, `AI_MAX_ATTEMPTS`, `AI_RATE_LIMIT_PER_MINUTE` | Private backend environment/secret manager only | `AI_PROVIDER=none` keeps deterministic local rules active; no provider call is made |
| Browser dashboard cross-origin access | Exact HTTPS dashboard origin(s) in `CORS_ORIGINS` | Backend environment | Browser requests are blocked until the origin is allowed |

No real backend or dashboard URL has been configured or deployed. See [production hosting readiness](operations/hosting.md) for environment variables and deployment sequence.

Map/geocoding, push/SMS, emergency-agency dispatch, and hosted production deployment are not integrated or required by this local demo. If later added, they require separate privacy, security, cost, and operational review. Never paste secrets into Git or this document.
