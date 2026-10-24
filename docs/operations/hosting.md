# Production hosting preparation

## Current deployment state

This repository has not been deployed. There is no verified public API URL, dashboard URL, production database, domain, hosting account, or provisioned live administrator. The selected repository-side layout is a Vercel static build for the HTML/JavaScript dashboard and a Docker-capable backend host with managed PostgreSQL. `vercel.json` configures the static output and short routes; `backend/Dockerfile` listens on the host-provided `PORT`. Hosting credentials and external resources still need to be created by the operator.

The frontend is plain HTML/CSS/JavaScript under `web/`, with no framework bundler. The backend is FastAPI with SQLAlchemy and Alembic. SQLite is supported for local development and tests. Production settings now require PostgreSQL, HTTPS dashboard CORS origins, and an HTTPS activation origin. Production startup does not create tables: migrations must run as a deliberate release step.

## Local development

Backend, from `backend/`:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
# Set a random JWT_SECRET of at least 32 characters in .env.
alembic upgrade head
python -m app.provision_admin --email admin@example.test --display-name 'Local Super Admin'
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The CLI prompts twice for a password and stores an Argon2 hash. It creates the first Super Admin only and refuses when a Super Admin already exists. To use the local dashboard, set its Service URL to `http://127.0.0.1:8000`, add the dashboard origin to `CORS_ORIGINS`, and open `web/admin/index.html`. The root README documents Android USB development and `adb reverse`.

## Vercel static dashboard

1. Import this repository into the Vercel project; use the repository root as the project root.
2. Set the build-time environment variable `ECS_API_BASE_URL` to the real backend HTTPS origin, for example `https://api.<your-domain>` (replace the placeholder with the provisioned service origin).
3. Use the checked-in build command `node scripts/build_web_config.mjs --required`; output directory is `web` as declared in `vercel.json`.
4. Add the final dashboard origin, such as `https://<your-dashboard-domain>`, to the backend `CORS_ORIGINS` value.
5. Open `https://<your-dashboard-domain>/admin/`. The generated client configuration contains only the public API origin, never credentials. It is intentionally not a secret.

The script rejects absent, non-HTTPS, malformed, or obvious placeholder API origins. Preview deployments must also be included in backend CORS if they are to call the service. Do not add database, JWT, SMTP, or other server secrets to Vercel frontend variables.

### Demonstration-tier limits reviewed (2026-10-24)

The repository's Vercel static-site choice avoids running an application server for the dashboard; a live deploy still requires an owned project, API origin, and review of the selected Vercel plan limits. A possible backend alternative, Render Free, is unsuitable for durable emergency-style demonstration data: free web services sleep after 15 minutes without inbound traffic, restart takes about a minute, and local filesystem data is ephemeral. Render Free Postgres is capped at 1 GB, expires 30 days after creation, and has no backups. See [Render Free service limits](https://render.com/docs/free). A production or persistent academic demo must select an appropriate managed database and budget/backup policy rather than assume free tier means persistent or always available.

For Android release builds, set `API_BASE_URL` to the same verified HTTPS API origin and run `sh scripts/build_android_release.sh`. That wrapper rejects empty or placeholder values before invoking Flutter. Android production signing is still not configured; the current Gradle release signing setup uses the debug key and is not distributable.

For local static preview, `ECS_API_BASE_URL` may be omitted and the dashboard keeps its manual service URL field:

```sh
python3 -m http.server 8080 --directory web
```

## Backend service and database

Use a Docker-capable web-service host with a managed PostgreSQL database on a private network. Build from `backend/Dockerfile`; the container starts `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Configure these backend environment variables in the host's secret/configuration store:

| Name | Required production value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | Managed PostgreSQL URL using SQLAlchemy's `postgresql+psycopg://` driver form |
| `JWT_SECRET` | Random secret with at least 32 characters; generate in the host secret manager |
| `CORS_ORIGINS` | Comma-separated exact HTTPS dashboard origins; no wildcard or path |
| `PUBLIC_APP_URL` | HTTPS dashboard origin used to construct responder activation links |
| `ACCESS_TOKEN_MINUTES` | Optional; defaults to 30 |
| `REMEMBER_ME_DAYS` | Optional; defaults to 30, bounded 1–365 |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | Required to deliver responder invitations in production |

`AI_PROVIDER` defaults to `none`; no AI key is required. Do not configure optional AI processing without a separate privacy and cost decision. Hosted open-weight inference was not selected because no provider/model, key, or data-retention approval was available. Hugging Face currently documents $0.10 monthly Inference Provider credits for Free accounts, subject to change, then pay-as-you-go when additional credits are purchased; model weights do not make provider inference free. See [Hugging Face pricing](https://huggingface.co/docs/inference-providers/en/pricing). Database credentials, JWT secret, and SMTP credentials stay in the backend host's secret store and never enter Flutter, Vercel, browser assets, or Git.

Deployment sequence:

1. Provision managed PostgreSQL and configure `DATABASE_URL` for the API service.
2. Configure the environment variables above and deploy the container.
3. Run `alembic upgrade head` once for the release against the target database, using the same backend image and production environment. Do not run demo seeds or automatic `create_all` in production.
4. Provision the first administrator from a one-off backend container/task after migration:

   ```sh
   python -m app.provision_admin --email "$ADMIN_EMAIL" --display-name 'Operations Admin'
   ```

   Set `ADMIN_EMAIL` to the actual operator address before running this command. The password is entered interactively; it is never an argument, environment variable, or printed by the program. The CLI refuses a second bootstrap and exits if it cannot use a terminal without echo. If the host's task runner is noninteractive, attach a secure terminal rather than putting the password into shell history or logs.
5. Configure `ECS_API_BASE_URL` in the Vercel project, build/deploy the dashboard, then set its final origin in backend `CORS_ORIGINS` and redeploy the API.
6. Confirm `https://<api-domain>/health/live` returns `{"status":"ok"}` and `/health/ready` returns `{"status":"ready"}`. Readiness checks database connectivity, not admin login.
7. Open `/admin/` and sign in with the bootstrap email and password entered in step 4. Verify the returned account role is `super_admin`; create Co-Admins from that dashboard with only required permissions.

An administrator account has not been provisioned in a live environment and no live login test has been performed. A local integration test covers generated password hashing and successful API login in the in-memory test database.

## Database, migrations, backups, and rollback

- The backend image includes Alembic migrations. Production lifespan deliberately does not call `Base.metadata.create_all`; run `alembic upgrade head` as an explicit release step.
- Use managed PostgreSQL with persistent storage and a private service connection. Do not use the local SQLite file or container filesystem as production data storage.
- Enable encrypted managed backups and point-in-time recovery according to the service's approved retention/RPO/RTO policy. This repository's [backup runbook](backup-and-recovery.md) describes a manual PostgreSQL logical backup and isolated restore drill; a recovery drill has not been performed here.
- Before rollback, check migration compatibility. Application rollback does not automatically reverse schema changes; restore a tested database snapshot only under the service's incident procedure. Never run `alembic downgrade` or destructive seed/reset commands against production without an approved recovery plan.
- Pin backend dependencies and run database integration/concurrency tests against the selected PostgreSQL service before real operational use. Existing automated backend tests use SQLite.

## Smoke checks and remaining release gates

After deployment, verify the health endpoints, dashboard asset loading, CORS preflight, admin login, role-based dashboard visibility, invalid credentials, responder invitation delivery, and one synthetic incident lifecycle in a non-operational staging database. Verify the API rejects unauthorized Co-Admin actions. Do not use live emergency data for a smoke test.

This preparation does not constitute deployment or production approval. No hosting credentials, DNS changes, migrations, live admin account, production signing key, rate-limit gateway, monitoring, penetration review, PostgreSQL integration result, or tested backup restoration is present. Keep this system out of real emergency response until those gates and the privacy/operational review in the release-readiness report are complete.
