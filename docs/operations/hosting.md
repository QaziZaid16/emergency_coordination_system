# Cloud deployment readiness

## Live deployment status

**Not deployed.** No Vercel, Render, or Supabase project is connected to this repository, no cloud API or dashboard URL has been issued, no remote database has been migrated, and no cloud login or persistence test has run. Do not treat the example hostnames below as live URLs.

The current repository already contains the static dashboard build (`vercel.json`), FastAPI Docker image (`backend/Dockerfile`), PostgreSQL migrations, health endpoints, and local/CI checks. This document and `render.yaml` prepare a no-purchase demonstration deployment. Provider account authorization and project creation remain owner actions.

## Target layout

| Component | Target | Reason and boundary |
|---|---|---|
| Browser dashboard | Vercel Hobby static deployment, `main` branch | The HTML/CSS/JavaScript site is static and already has a Vercel build configuration. Git integration provides preview and production deployments. Hobby is for personal, non-commercial use. |
| API | Render Free Docker web service | Uses the existing FastAPI image and `render.yaml`; HTTPS and the `onrender.com` subdomain are provided by Render. It sleeps when idle. |
| Database | Supabase Free PostgreSQL | Persistent PostgreSQL rather than a container-local SQLite file. Use Supabase's IPv4 session pooler from Render. Free projects may pause after inactivity and have no managed backups. |
| AI | Disabled (`AI_PROVIDER=none`) | No provider or key is selected. The deterministic backend baseline remains in use. |
| Notifications | Existing persistent in-app records only | FCM, device tokens, email notifications, and delivery tracking are not configured. SMTP invitations need a separately configured mail provider. |

This is a prototype hosting arrangement, not production service assurance. Keep real emergency and sensitive location data out of it.

## Deployment checklist

- [ ] Owner creates/authorizes free Vercel, Render, and Supabase accounts; keep every service on its $0 plan and do not add billing or paid add-ons. Whether an account signup flow asks for a card was not verified.
- [ ] A Supabase Free project is created; the Session pooler connection string is stored only in Render's service settings.
- [ ] The Vercel project is connected to this GitHub repository, with root directory `/`, production branch `main`, build command `node scripts/build_web_config.mjs --required`, and output directory `web`.
- [ ] Vercel project variable `ECS_API_BASE_URL` contains the actual Render HTTPS origin. Do not use a placeholder.
- [ ] Render creates the service from [`render.yaml`](../../render.yaml), with the actual Vercel origin in `CORS_ORIGINS` and `PUBLIC_APP_URL`.
- [ ] The Render API passes `/health/live` and `/health/ready`; database connectivity and migrations are verified.
- [ ] Vercel Deployment Checks are configured to wait for the GitHub Actions `Quality checks` workflow before production promotion.
- [ ] A protected, owner-controlled Android signing key and repository API URL variable are configured before the signed APK job can run.
- [ ] A synthetic end-to-end incident and restart/persistence check succeeds before sharing the demonstration.

## Provider setup sequence

### 1. Create the Supabase database

1. Create a Free Plan project in the owner's Supabase organization. Keep the database password in a password manager.
2. Open **Connect** in the project and select **Session pooler**. Supabase identifies this shared pooler as IPv4 accessible, including on Free. Render's free service is not an IPv6-only network assumption.
3. Store the returned hostname, port, database, username, and password in the private Render `DATABASE_URL` setting, using SQLAlchemy's `postgresql+psycopg://` driver URL and `?sslmode=require`. Percent-encode reserved characters in the password. Do not commit or paste this URL into an issue or chat.
4. The Render startup command applies `alembic upgrade head` before starting Uvicorn. It retries a failing database connection a bounded number of times, then fails closed. It never runs the demo seed.

Supabase currently lists two active Free projects, 500 MB database size per project, 5 GB egress, and no automatic backups. Free projects may be paused after about a week of low activity; a paused project can be restored for up to one year. Export backups regularly and keep them in an encrypted destination outside this repository. A manual PostgreSQL dump/restore runbook is in [backup and recovery](backup-and-recovery.md); no cloud backup or restore has been tested.

Official references: [Supabase plans and quotas](https://supabase.com/pricing), [project pausing](https://supabase.com/docs/guides/platform/free-project-pausing), [PostgreSQL connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres), and [backups](https://supabase.com/docs/guides/platform/backups).

### 2. Create the Render API service

1. Connect Render to the GitHub account that can access this repository.
2. Choose **New → Blueprint** for the repository on `main`. Review `render.yaml`; it creates one Free Docker web service and no Render database or other paid resources.
3. For `DATABASE_URL`, enter the protected Supabase Session pooler URL. Set `CORS_ORIGINS` and `PUBLIC_APP_URL` to the eventual HTTPS Vercel site origin (for example, the actual `https://<project>.vercel.app` shown by Vercel). If the Vercel URL is not known yet, use a valid temporary HTTPS origin, complete the initial deployment, and replace it before testing dashboard sign-in.
4. Render generates `JWT_SECRET`. Keep the `ENVIRONMENT=production` and `AI_PROVIDER=none` values declared in the Blueprint.
5. Once created, record the actual `https://<service>.onrender.com` URL from Render; do not guess the slug. The service uses `/health/ready` for its health check and auto-deploys from `main` only after connected GitHub checks pass.

Production migrations run at container start because Render Free does not provide pre-deploy commands. Keep schema changes backward-compatible with the currently running application and use expand/contract migrations. A failed migration prevents the API from starting; the app does not run `create_all` or seed data in production.

### 3. Create the Vercel dashboard

1. Import this repository into the owner's personal Vercel Hobby account and select `/` as the project root. Keep the checked-in `vercel.json` build and output settings.
2. Set `ECS_API_BASE_URL` to the actual Render HTTPS origin. It is a public endpoint, not a secret.
3. Set `main` as the production branch and deploy. Vercel assigns the free `vercel.app` site URL. Add that exact origin to Render `CORS_ORIGINS` and `PUBLIC_APP_URL`, then redeploy the API.
4. Reopen the dashboard and verify login and API-backed data. The direct path is `/admin/`; responder activation is `/activate`.
5. In Vercel project settings, configure **Deployment Checks** to block production promotion until the repository's `Quality checks` workflow passes. Vercel can build a deployment before checks finish; the check prevents it becoming the production alias until selected checks pass. Preview deployments remain available for review.

Vercel Hobby is free for personal, non-commercial use, includes GitHub integration and automatic preview/production deployments, and pauses usage-dependent features when quotas are exceeded. The owner must satisfy Vercel's Hobby account/commit-author rules. A custom domain is not required.

Official references: [Vercel Hobby plan](https://vercel.com/docs/plans/hobby), [Git deployments](https://vercel.com/docs/git), [Deployment Checks](https://vercel.com/docs/deployment-checks).

### 4. Configure GitHub Actions and Android signing

`main` is the production branch. `.github/workflows/quality.yml` runs backend tests, Dart format/analyze and Flutter tests, and validates the static web configuration build on PRs and pushes. Render is configured to deploy after checks pass; Vercel production promotion requires the Deployment Checks setting above.

The same workflow builds an Android APK after those checks on `main` when the repository variable `API_BASE_URL` is present. APKs are uploaded as a 30-day Actions artifact. A `v*` tag creates a GitHub Release with the APK and build metadata. Workflow manual dispatch is available from `main`.

Set repository variable `API_BASE_URL` to the actual Render HTTPS origin. In **Repository → Settings → Secrets and variables → Actions**, add these four secrets:

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | Base64 encoding of the private Android release keystore |
| `ANDROID_KEYSTORE_PASSWORD` | Keystore password |
| `ANDROID_KEY_ALIAS` | Signing-key alias |
| `ANDROID_KEY_PASSWORD` | Signing-key password |

Do not commit the keystore, `key.properties`, or passwords. Generate a new key with `keytool` only if the owner accepts the app-signing migration described below, keep an encrypted offline backup, and upload secrets using the GitHub settings UI. This repository does not contain a production key. The workflow fails with a clear error if the secret or API variable is missing.

On a machine with the Android JDK installed, this command prompts for the new keystore and key passwords instead of putting them in shell history:

```sh
keytool -genkeypair -v -keystore ecs-upload.jks -alias ecs-upload \
  -keyalg RSA -keysize 2048 -validity 10000
```

Base64-encode that file locally and enter the result in the GitHub `ANDROID_KEYSTORE_BASE64` secret field; enter its passwords and alias in the other listed secret fields. Never print or commit the encoded key.

The currently installed APK on the demonstration phone is signed with a debug certificate. A new production keystore has a different signer and Android will reject it as an in-place update for that installed package. Do not uninstall or overwrite it automatically. Before distributing production-signed APKs, the owner must either authorize a one-time uninstall/reinstall (which removes local app data), or provide the existing signing identity. The default Android debug key is not suitable for public release distribution. The package ID remains `edu.cgc.university.emergency_coordination_system`.

The version code for CI artifacts increases from the manifest version using the workflow run number. GitHub Actions artifacts expire after 30 days; tagged GitHub Releases are the longer-lived download option. APK installation is manual—this workflow does not update phones automatically.

### 5. Configure SMTP only if responder invitation email is required

The backend can send responder activation links through SMTP, but no provider is selected or configured. Render Free blocks outbound SMTP on ports 25, 465, and 587. Use a provider offering a permitted submission port (such as 2525 where supported) or an approved HTTPS mail API integration; do not add credentials until one is selected. In-app notification records do not send email or push messages.

## Configuration and secret boundaries

| Setting | Location | Secret? |
|---|---|---|
| `DATABASE_URL` | Render environment | Yes; includes the database password |
| `JWT_SECRET` | Render environment, generated by Blueprint | Yes |
| `CORS_ORIGINS`, `PUBLIC_APP_URL` | Render environment | No, but must match the actual Vercel origin |
| `ECS_API_BASE_URL` | Vercel project build environment | No; public API URL |
| `API_BASE_URL` | GitHub Actions repository variable | No; same public API URL for release APKs |
| `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD` | GitHub Actions repository secrets | Yes |
| `AI_PROVIDER` | Render environment | `none`; optional AI is not configured |
| `OPENROUTER_API_KEY` | Render secret environment, only if enabling AI | Yes; never put in GitHub build variables, Flutter, or web config |
| `OPENROUTER_MODEL` | Render environment | Defaults to `google/gemma-4-31b-it`; do not add `:free` unless that alternative is explicitly chosen |
| `OPENROUTER_BASE_URL` | Render environment | Defaults to `https://openrouter.ai/api/v1` |
| `AI_TIMEOUT_SECONDS`, `AI_MAX_ATTEMPTS`, `AI_RATE_LIMIT_PER_MINUTE`, `AI_SHARE_INCIDENT_LOCATION` | Render environment | Bounded request settings; location sharing defaults off |
| `SMTP_*` | Render environment | Not configured; outbound SMTP restrictions apply |

Never place database/JWT/SMTP/signing secrets in `ECS_API_BASE_URL`, `API_BASE_URL`, a Flutter `--dart-define`, web assets, workflow YAML, or Git.

## Verification and persistence test

After the owner has created and deployed all three provider projects:

```sh
curl -fsS https://<actual-render-service>.onrender.com/health/live
curl -fsS https://<actual-render-service>.onrender.com/health/ready
curl -fsSI https://<actual-vercel-project>.vercel.app/admin/
```

The expected API responses are `{"status":"ok"}` and `{"status":"ready"}`. Replace the bracketed values only with URLs displayed by the providers. Then, using only synthetic records in this academic demo:

1. Provision the first Super Admin through a secure Render shell/one-off task or an approved secure database/API setup. Do not seed production or use a default password.
2. Sign into the Vercel dashboard and a production-configured APK on a phone using the HTTPS API.
3. Create a synthetic user incident; confirm it appears in the dashboard and API/database.
4. Assign a synthetic responder, update its status from the responder client, and verify the user and admin views observe the change.
5. Restart/redeploy the API and confirm the incident and status history remain in Supabase.
6. Test invalid credentials, role denial, CORS preflight, and `/health/ready` during an unavailable database.

None of these live tests have been run because the provider projects and credentials are absent. SQLite tests do not establish PostgreSQL concurrency or cloud persistence.

## Cost and reliability limits checked 2026-10-24

- **Vercel Hobby:** $0 for the documented personal/non-commercial use case; usage limits apply and deployments/features can pause at quotas. GitHub integration and TLS are provider-managed. [Plan limits](https://vercel.com/docs/plans/hobby).
- **Render Free API:** sleeps after 15 minutes without inbound traffic and can take about a minute to wake. Free web services have ephemeral filesystems, can restart, do not support pre-deploy commands or SSH, and share 750 free instance hours per workspace/month. No payment method means over-quota services can be suspended rather than billed; adding a payment method can permit charges for some overages. SMTP ports 25/465/587 are blocked. [Render free limits](https://render.com/docs/free).
- **Supabase Free database:** $0 at current published quotas, up to 500 MB database size/project and 5 GB egress; low-activity projects can pause after a week. Automatic backups and point-in-time recovery are not included on Free. Keep manual encrypted backups and do not promise indefinite free persistence. [Supabase pricing](https://supabase.com/pricing), [pausing](https://supabase.com/docs/guides/platform/free-project-pausing), [backups](https://supabase.com/docs/guides/platform/backups).
- **GitHub Actions:** standard hosted runners are free for public repositories; private repositories have plan-specific minute and storage quotas. APK artifacts in this workflow are retained for 30 days. [Actions usage](https://docs.github.com/en/actions/concepts/billing-and-usage).
- **OpenRouter AI:** no key is configured and `AI_PROVIDER=none`, so the deployment design makes no inference calls. OpenRouter publicly lists `google/gemma-4-31b-it`; current standard endpoint pricing is about $0.09/M input and $0.34/M output tokens. This is not the separately named `:free` endpoint. Account access, model inference, limits, and costs for a specific account have not been verified; usage can incur charges. See [OpenRouter model pricing and endpoint details](https://openrouter.ai/google/gemma-4-31b-it). The app uses strict structured output only on provider endpoints that advertise the required parameter. Report descriptions are disclosed to the provider when enabled; the key remains in Render only.
- **Push notifications:** no FCM/device delivery is implemented or configured, so no push cost is incurred.

These are provider limits reviewed from official docs on the date above; they can change. No provider account was available to verify its signup/card flow or project-specific quota. These free tiers are suitable only for a small, synthetic academic demo, not reliable emergency operations.

## Rollback

- **Vercel:** use the provider's previous deployment/rollback controls after checking which commit and API origin it contains.
- **Render:** use one of the recent successful deploys or revert the repository commit; check database migration compatibility first. Do not assume rolling application code back reverses a migration.
- **Supabase:** restore only from a verified export into an isolated database, validate it, and change the Render `DATABASE_URL` only after explicit operator approval. No automated backup, point-in-time recovery, or restore drill is included on Free.

No rollback or backup recovery has been exercised against a live service.
