# Implementation roadmap

## Prototype delivered and verified in this project

1. Flutter Android foundation and private local workspace storage.
2. Incident intake with editable location, type, severity and urgency; transparent Critical/High/Medium/Low decision rule.
3. Priority queue and recommendation logic based on availability, skill compatibility, proximity and exclusive assignment.
4. Responder profiles, off-duty/available control, active incident status transitions and responder workspace.
5. Resource allocation/release, incident message history, audit events and local operation reports.
6. Requirements, architecture, setup and verification records; unit/store/widget tests, Android emulator workflow verification, and a physical Android phone release install/launch. Static analysis is clean; verification evidence and limits are listed in `test-results.md`.

## Deferred / outside documented prototype boundary

Live GPS/device location, maps/routing, traffic, external agency APIs, cloud synchronization, push messaging, production identity/authorization, predictive analytics/ML, autonomous dispatch, production hosting, production signing and real-world safety validation. These require clarified operational, privacy, provider, cost and security requirements and must not be represented as working features in this prototype.
