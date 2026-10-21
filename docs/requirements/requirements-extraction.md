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

- The original academic documents do not define cross-device synchronization. The later user-provided evolution brief adds a shared backend; the current portal implementation polls the API every 12 seconds.
- This prototype has coordinator and responder workspaces. A role switch is a demonstration selector, not authentication or security; authentication is unspecified.
- The original training workspace uses simulated coordinates. The later user request adds foreground device GPS for authenticated SOS and responder location sharing, with manual SOS fallback. Maps, geocoding, background tracking, and agency interfaces remain absent.
- Priority is transparent decision support from type, severity and urgency. A human coordinator confirms dispatch; no autonomous life-critical decision is made.
- Sample records and resource categories are marked simulated because no production catalogue is provided.
- The original training workspace remains one-device and local. Shared portals store records in the API database. A responder can hold one active assignment; assignment/resource conflicts are guarded by database constraints. Fresh accurate locations can inform straight-line recommendations; an administrator confirms each assignment. Closure releases linked resources.
- Neither academic source specifies numeric priority thresholds, retention, map provider, or report formats. The evolution brief requests authentication and persistent shared data; implementation choices and remaining operational decisions are documented in `docs/audit/architecture.md`.
- The Synopsis emphasizes a responder interface and monitoring/reporting records; the PPT describes an Android simulated prototype without live GPS or agency integration. The later user evolution request expands this to a shared role-based platform. Original training and new shared portals are kept separate.
- The pasted master prompt terminates at “Create and maintain the following documentation as app/”; the rest of its list is absent. This project provides standard requirements, architecture, traceability, verification, setup and handover documents.
