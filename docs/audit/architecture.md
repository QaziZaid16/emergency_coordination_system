# Architecture and design decisions

## Product and architecture

Single Flutter Android app for the academic prototype. Local-first storage supports simulated operations without undocumented Firebase billing, cloud infrastructure, accounts or agency integrations.

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

Presentation handles navigation/forms/status feedback. Domain services own validation, transitions, priority, matching, exclusive resource allocation and reporting. Repository owns durable incidents, responders, resources, messages and activity events. No API/backend/authentication/cloud sync is specified. A future service adapter can replace local storage when deployment, privacy, identity and availability requirements are known.

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

Overview; incident intake/list/detail; responders; resources; incident communication; reports/history; responder workspace. Use high contrast priority/state labels, touch-sized actions, explicit simulated-data marker, responsive narrow layouts, validation and useful empty/error feedback. Android is target; web platform scaffolding is for development only.

## Limits and costs

No paid or recurring infrastructure. No login/security boundary, app-level encryption, managed backup, cross-device sync, live GPS/map/traffic/geocoding, push notification, emergency phone dispatch or external system integration. Local storage loss is possible if app data is cleared. Never use this prototype for real emergency operations. Future cloud/maps/notifications require provider, privacy, cost and credential approval.
