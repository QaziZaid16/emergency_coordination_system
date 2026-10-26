# CI/CD status

> Historical audit snapshot from before the React website migration. The current workflow and deployment target are described in [hosting operations](operations/hosting.md) and [the frontend migration record](architecture/frontend-migration.md).

## Repository workflows

`.github/workflows/quality.yml` runs on pull requests, pushes to `main`, `v*` tags, and manual dispatch. It grants read-only repository permission by default and checks:

- Backend pytest suite on SQLite.
- Flutter dependency resolution, Dart format, analyzer, and the tracked Flutter test suite.
- JavaScript syntax and a configured static dashboard build.
- A signed Android release build after successful checks when the `API_BASE_URL` repository variable and Android signing secrets are configured. The APK is an Actions artifact retained 30 days; a deliberate `v*` tag also creates a GitHub Release.

The Android release job is skipped on `main` until `API_BASE_URL` is present. It then fails clearly if any release signing secret is missing. The job does not install APKs on phones. See [cloud deployment readiness](operations/hosting.md) for the exact GitHub variable/secrets and the installed debug-app signing constraint.

## Provider deployment status

Vercel is prepared by `vercel.json` for static output at `web/`; Render's Git-backed Docker API service is described in `render.yaml`. Provider accounts, GitHub integrations, Supabase database, environment variables, and public URLs are not configured here. Vercel Deployment Checks and Render's `checksPass` trigger both require owner-side provider setup. Do not report Git auto-deployment as active until a connected provider reports a successful deployment from `main`.

The GitHub CLI session available in the implementation environment is not authenticated. No cloud provider token or Android signing secret was present. The checked-in configuration is therefore prepared but has not been remotely exercised.
