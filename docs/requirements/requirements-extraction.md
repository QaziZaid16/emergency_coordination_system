# Requirements extraction

Sources: `Synopsis1.pdf` (16 pages) and `Emergency Coordination System PPT.pdf` (18 slides), supplied 2026-10-21. Text was extracted from every page/slide and embedded PPT images were visually reviewed. The Synopsis is authoritative; the PPT supplements it.

## Verified source facts

- Academic software prototype and decision-support tool; it must not replace trained staff, official dispatch protocols, or legally mandated infrastructure (Synopsis pp. 6, 9).
- Lifecycle: request, registration, location identification, priority assessment, resource review, suitable responder assignment, response monitoring/status updates, closure and resource release (Synopsis pp. 5, 8–12; PPT slides 2, 9–11).
- Roles include coordinators/dispatchers, responders/teams, supervisors/resource managers and administrators (Synopsis p. 9; PPT slide 7).
- Matching considers incident priority, responder availability, proximity, suitability and workload. Priority classes include Critical, High, Medium and Low (Synopsis pp. 10–12; PPT slide 11).
- Concurrent incidents, shared resource allocation, incident/assignment/activity records, dashboards, communication, monitoring and reporting are in scope (Synopsis pp. 7–15; PPT slides 5–10, 14).
- Flutter/Dart and Android are specified. PPT describes simulated testing and excludes real GPS hardware, live traffic and external agency APIs. Synopsis allows simulated data and places advanced routing/analytics and agency integrations in future scope (Synopsis pp. 9, 12–15; PPT slides 7, 12–17).

## Interpretation, assumptions and unresolved details

- “Real-time” means immediate updates within this app instance and persistence on device. Cross-device synchronization is not specified.
- This prototype has coordinator and responder workspaces. A role switch is a demonstration selector, not authentication or security; authentication is unspecified.
- Coordinates are manually entered or selected from built-in simulated locations. Live GPS, map tiles, geocoding, Firebase and agency interfaces are excluded by the PPT prototype boundary or lack of service/credential requirements.
- Priority is transparent decision support from type, severity and urgency. A human coordinator confirms dispatch; no autonomous life-critical decision is made.
- Sample records and resource categories are marked simulated because no production catalogue is provided.
- One device stores one workspace. Each responder can hold one active incident; assigned responders are unavailable until release. Skill match is required. No eligible responder leaves an incident queued. Recommendations rank by straight-line proximity then workload; coordinator confirms. Closure releases linked resources.
- Neither source specifies numeric priority thresholds, required fields, quantities, authentication, database platform, map provider, retention, or report formats; minimal prototype rules are documented in `docs/audit/architecture.md`.
- The Synopsis emphasizes a responder mobile interface and monitoring/reporting records; the PPT additionally defines an Android-only simulated prototype without live GPS or agency integration. One Flutter Android app supplies coordinator and responder workspaces and keeps data local.
- The pasted master prompt terminates at “Create and maintain the following documentation as app/”; the rest of its list is absent. This project provides standard requirements, architecture, traceability, verification, setup and handover documents.
