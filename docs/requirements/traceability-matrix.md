# Requirements traceability matrix

| ID | Requirement / acceptance criterion | Source | Implementation | Status |
|---|---|---|---|---|
| FR-001 | Register incident with type, description, location, time, urgency and severity; validate required inputs. | Synopsis pp. 8,11; PPT 9–10 | Incident form and repository | Verified — see verification record |
| FR-002 | Maintain incident lifecycle from registration/queue through assignment, response and closure. | Synopsis pp. 8–9,12; PPT 2,9 | Incident actions/history | Verified — see verification record |
| FR-003 | Derive Critical/High/Medium/Low from type, severity and urgency; show rationale. | Synopsis pp. 11–12; PPT 11 | Explicit scoring rule | Verified; thresholds are documented prototype assumptions |
| FR-004 | Maintain responder identity, type, skills, location, availability, status, workload and assignment. | Synopsis pp. 8–9,11; PPT 10–11 | Responder management | Verified — see verification record |
| FR-005 | Recommend suitable responder using priority, availability, proximity, skills and workload; coordinator confirms. | Synopsis pp. 8,11–12; PPT 9–11 | Deterministic matcher | Verified — see verification record |
| FR-006 | Keep concurrent incidents visible and prevent double allocation. | Synopsis pp. 6–9,11–12; PPT 3,8,11 | Priority queue and exclusive assignment | Verified — see verification record |
| FR-007 | Update Assigned, En Route, Responding, Completed; release responder/resource at closure. | Synopsis pp. 8,12; PPT 9,11 | Lifecycle transitions | Verified — see verification record |
| FR-008 | Manage resource inventory and availability across incidents. | Synopsis pp. 7–9,11–12; PPT 5–6,8,10 | Resource inventory/allocation | Verified; sample quantities are assumed |
| FR-009 | Share incident information and coordinator/responder messages. | Synopsis pp. 5,7,9,12; PPT 6,8,10,14 | Training-mode local threads; shared-mode API updates and server history | Local prototype verified; API message scope covered by backend workflow tests |
| FR-010 | Dashboard shows active incidents, priority, assignments, location and responder state. | Synopsis pp. 7,12,14; PPT 5,8,10 | Overview | Verified — see verification record |
| FR-011 | Preserve incident, assignment, response and completion records for reports. | Synopsis pp. 7,9,14–15 | History and reports | Verified — see verification record |
| FR-012 | Responder workspace shows assigned details and permits status/messages. | Synopsis pp. 8–9; PPT 7 | Responder workspace | Verified; selector is a training control, not authentication |
| FR-013 | Maintain location details and use distance in recommendations. | Synopsis pp. 8,11–12; PPT 6,9–11 | Training mode simulated points; shared mode foreground GPS/manual fallback and fresh-accuracy recommendations | API validation covered; no routed ETA or background location |
| NFR-001 | Flutter/Dart Android app. | Synopsis pp. 12–14; PPT 12–13 | Flutter Android project | Verified; release APK builds and launches on Android |
| NFR-002 | Simulated prototype; no claim of official-service integration. | Synopsis 9; PPT 7,16 | Local simulated workspace | Verified — see verification record |
| NFR-003 | Records survive app restart. | Implied Synopsis pp. 7,9,14–15 | Training workspace JSON; shared SQL database | Training persistence tested; shared persistence covered by API/database workflow tests |
| NFR-004 | Human coordinator owns dispatch decisions. | Synopsis p. 6 | Recommendation + confirmation | Verified — see verification record |
| NFR-005 | Keep live traffic, predictive/ML, agencies and autonomous dispatch out of scope. | Synopsis 9; PPT 16–17 | No such integration | Scope review complete |
| SEC-001 | No hardcoded secrets or credential-dependent integrations. | Master prompt; prototype boundary | No external service calls | Verified |
| UI-001 | Provide validation, feedback, useful empty states and navigable controls. | Master prompt; implied workflows | Flutter UI | Core form/navigation/control flows verified; assistive-technology audit remains unevaluated |

## Shared platform evolution requirements

These additional user-requested requirements extend the original academic prototype. They are not inferred from the attached academic documents.

| ID | Requirement / acceptance criterion | Implementation | Status |
|---|---|---|---|
| EVO-001 | Separate Admin, User, and Responder portals with server-enforced roles. | Flutter portal chooser; API role dependencies and scoped queries. | Implemented; API access isolation tested. |
| EVO-002 | Authenticated multi-user accounts and secure sessions. | Argon2 password hashes, signed expiring tokens, revocable session records, first-admin CLI. | Implemented; login/logout/session tests. Account recovery and rate limits remain outstanding. |
| EVO-003 | Persist shared incidents, assignments, resources, updates, and audit records. | SQLAlchemy schema, Alembic migration, SQLite development/test, PostgreSQL Compose configuration. | SQLite migration and workflow tested; PostgreSQL not verified. |
| EVO-004 | User SOS submission with current location or manual fallback and duplicate protection. | Foreground geolocation client, fallback form, stale/future fix validation, idempotency key. | API and local phone flow exercised; multiple Android permission/device cases remain unverified. |
| EVO-005 | Admin-managed assignment, reassignment, resource allocation, and operational changes. | Transactional endpoints, conflict constraints, responder recommendations, admin portal. | API workflow and conflicts tested. No live routing or external dispatch. |
| EVO-006 | Responder task updates, communication, and location sharing. | Scoped task portal, ordered status workflow, updates, one-time foreground location. | Implemented; backend workflow tested. Broad physical-device role walkthrough remains unverified. |
| EVO-007 | Synchronize visible changes across clients. | Authenticated update polling at 12-second intervals. | Implemented. No WebSocket/push service. |
| EVO-008 | Production deployment to a shared secured service. | Deployment configuration and handover documentation only. | Not complete: no hosted service, TLS endpoint, operational credentials, or PostgreSQL verification. |
| EVO-009 | Remember Me is opt-in and restores only a server-validated role session. | Android secure storage, `/auth/me` validation, rotating refresh credentials, role-bound portal routing. | Implemented; client and widget tests pass; local API flow verified. |
| EVO-010 | Expiry, revocation, logout and account switching clear local auth and block protected screens. | Refresh session revocation, storage cleanup, root portal reset and 401 handling. | Implemented; client/API regression tests pass. Offline server revocation is reported as unconfirmed. |
| EVO-011 | Apply a distinct launcher identity consistently across Android and entry surfaces. | SVG master, adaptive foreground/background, monochrome vector, density PNGs, splash, PWA and in-app mark. | Release build packages the resources; no connected device was available for current physical visual review. |

Test evidence and remaining verification limits are recorded in `docs/audit/test-results.md`.
