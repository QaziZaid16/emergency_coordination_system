# Architecture and design decisions

## Product and architecture

### Current delivered prototype

The existing Flutter client contains coordinator and responder demo workspaces and stores simulated records in one app-private JSON file. It has no backend, identity, synchronization or real GPS. The responder selector is not authentication. Do not treat its records or coordinates as live operational data.

### Target architecture (evolution in progress)

Use one Flutter application with three explicit role entry points and one shared FastAPI service. The service owns credentials, role authorization, incidents, responder capability/availability, assignments, resources, status transitions, and audit history. SQLite supports local development and automated tests; PostgreSQL is the deployment database because assignment uniqueness and concurrent writes must be transactional. API clients never write directly to the legacy JSON store in authenticated mode. The legacy coordinator/responder experience remains an explicitly labeled, isolated training mode until a deliberate migration is approved.

```text
Flutter (Admin / User / Responder portals; optional isolated training mode)
                  │ HTTPS bearer session + idempotency key
                  ▼
FastAPI (validation, role/ownership checks, assignment transaction, audit)
                  │ SQLAlchemy transaction
                  ▼
PostgreSQL for deployment / SQLite for local tests
```

The current implementation milestone adds the runnable API and role-specific workflows without claiming a hosted service, verified agency integration, push delivery, or production readiness. Deployment must provide TLS, a managed PostgreSQL instance, secure environment secrets, backups, monitoring, retention and incident-response policy. Pollable authorized change feeds are the synchronization fallback; upgrades to a managed push/SSE channel can follow without changing ownership rules.

### Migration strategy

1. Keep the existing JSON and sample dataset in local training mode; never import it automatically as real users, responders, resources, incidents, locations or assignments.
2. Create backend accounts and operational data through authenticated/admin-controlled API operations. Provision the first administrator only with a one-time CLI command requiring email and password from the operator; there is no hardcoded default account.
3. Select the server portal at sign-in and keep each token/session scoped to its server-side role. The client may not elevate roles by choosing a portal.
4. Move deployments only after operator identity, legal location handling, retention, backup and emergency-service boundaries have been reviewed.

```text
Flutter presentation (coordinator + responder workspaces)
                │ validated commands / view state
                ▼
Domain services (priority, matching, lifecycle, reporting)
                │ state transitions
                ▼
Repository interface ── local JSON persistence in app-private files
                └── explicitly simulated seed workspace
```

Presentation handles navigation/forms/status feedback. The local training domain/store remains local and explicitly simulated. In shared mode the API owns durable operational entities and all authorization and transition decisions. The existing priority calculation and skill/availability/location matching remain the baseline; distance is shown only when coordinates are recorded with a timestamp/accuracy and never uses the legacy sample coordinates.

## Domain records

- Incident: ID, category, description, urgency/severity, coordinates and display location, timestamps, priority/status, assigned responder/resource IDs.
- Responder: ID/name/type/skills, availability/status, coordinates, current incident ID.
- Resource: ID/name/type, quantity and availability, status, linked incident IDs.
- Message: ID, incident ID, sender role/name, body and time.
- Activity event: ID, incident ID, kind, summary, actor and timestamp; append on create, assignment, status and completion.

## Rules

- Priority is derived from category, severity and urgency by the explicit policy in `lib/domain/dispatch_rules.dart`; rationale is visible. Decision support only.
- Eligible responders are available, skill-compatible and unassigned; the one-active-incident capacity rule excludes responders carrying workload. The incident queue sorts Critical, High, Medium, then Low. Within an incident, recommendations sort by straight-line distance, then fewer listed skills as a deterministic tie-break; a human coordinator confirms. These are transparent prototype heuristics, not operational policy.
- Lifecycle: New → Queued or Assigned → En Route → Responding → Resolved. Invalid transitions are rejected. Resolution releases assignments.
- Coordinates are manually entered/simulated. Haversine is a rough distance, not routed ETA.
- On Android, a small MethodChannel exposes the app-private files directory and Dart writes a single JSON workspace file; no Android storage permission is required. This is appropriate for the small prototype; production needs transactional/cloud storage, retention, privacy, identity, backup and recovery decisions.

## UI structure

Overview; incident intake/list/detail; responders; resources; incident communication; reports/history; responder workspace. A shared Material 3 theme in `lib/presentation/design_system.dart` sets the operational teal palette, warm urgency accent, typography, touch-sized controls, cards, fields and navigation. The overview groups operational counts into compact metric cards and makes the training-only state visible in the app bar. Incident search, concise section headers, clear empty states and a lifecycle progress indicator help people scan cases and understand their current step. Android is target; web platform scaffolding is for development only.

## Limits and costs

This repository is a development implementation, not an operational emergency dispatch service. Until deployed behind TLS with managed PostgreSQL, secured secrets, monitoring, backup/restore, privacy/retention policy, penetration testing, accessibility review, and trained organizational procedures, use only for development/demo scenarios. No verified ambulance/fire/police integration or push-notification provider is present; request receipt is not agency dispatch. Priority remains a prototype heuristic, never approved triage policy. Legacy JSON records are simulated and are never silently migrated. Real location sharing is sensitive data and requires an explicit privacy/legal review before deployment.
