# Isolated React staging dashboard

This Vite + React + TypeScript app is isolated from the static dashboard at `web/admin/`, the Flutter Web entry point at `web/index.html`, the root Vercel rewrites, and responder activation hosting. It calls the existing FastAPI `/api/v1` routes directly; it adds no backend endpoints.

## Local development

1. Copy `.env.example` to `.env.local` and set `VITE_ECS_API_ORIGIN` to a real HTTPS API origin (origin only: no credentials, path, query, or fragment).
2. From `web/react-dashboard/`, run `npm ci` after checkout, then `npm run dev`.
3. Open the local Vite URL shown by the command. Vite does not configure a backend proxy; the API must allow the local development origin through its existing CORS configuration.
4. Run `npm test` and `VITE_ECS_API_ORIGIN=https://api.coordination-services.org npm run build` to verify tests and a production build. Use your actual service origin in a real deployment; example and placeholder domains are rejected.

The app intentionally uses `sessionStorage`, matching the prior dashboard's tab-scoped session behavior. It verifies a stored session with `GET /auth/me` on reload, clears it on a `401`, and does not persist a refresh token. Browser storage cannot provide the same protection as an HTTP-only cookie against same-origin script compromise; the API remains the authorization boundary. All API calls reject redirects.

## Separate Vercel staging project (manual later step)

Create a new Vercel project only after review and separate approval. Set **Root Directory** to `web/react-dashboard`, **Framework Preset** to Vite, **Build Command** to `npm run build`, and **Output Directory** to `dist`. Set `VITE_ECS_API_ORIGIN` in the staging project's build environment to the intended real HTTPS API origin. The value is public browser configuration, never a server secret.

Do not change the existing Vercel project or its root routes for this staging app. `/activate` remains hosted by the existing project. The backend currently constructs invitation links from its `PUBLIC_APP_URL` and appends `/activate.html#token=...`; ensure staging invitation handoff points to the existing activation host before using it. Provider setup and deployment remain separate, manual actions.

## Verified implementation scope and gaps

Implemented UI workflows use the current backend contracts: login/logout/me, dashboard, incidents/detail/updates/report, recommendations and assignment/reassignment, resolve/cancel/report review, analysis retry, responder list/invite/resend/capability/availability/account activation, user listing/account activation, resource list/create/update, analytics/export, audit, co-admin CRUD/permission updates, notifications/read state, and automatic assignment policy. Contract definitions are in `backend/app/api.py` and request schemas in `backend/app/schemas.py`.

The dashboard intentionally does not create ordinary user accounts: although `POST /admin/users` exists, the backend's visible `create_account` implementation rejects responder creation through that route, and role/permission semantics for creating ordinary users are not part of the current dashboard workflow. Incident details display persisted analysis and report fields returned by the service, with a human-review label; no AI behavior is generated in the browser. Push notifications, email delivery, live maps/tracking, and real-time updates are not claimed.
