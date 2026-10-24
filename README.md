# Emergency Coordination System

A Flutter and Dart Android app with unified role-routed sign-in for Users and Responders, plus a responsive browser administration dashboard for Super Admins and permission-scoped Co-Admins. The clients share one FastAPI service for accounts, incidents, assignments, resources, status history, and audit records. The original isolated local training workspace remains available only through an explicit debug-build option. This repository does not include a hosted service or agency integration.

> **Development platform only. Do not use this app to report or coordinate a real emergency.** A configured instance can capture and share device location with its coordination backend, but it does not contact emergency services or dispatch an ambulance, fire service, or police. Priority is a prototype heuristic, not a validated triage policy. For a real emergency, use the emergency number and procedures applicable to your location.

## Contents

- [Browser administration dashboard](#browser-administration-dashboard)
- [Install the demo app](#install-the-demo-app)
- [First launch](#first-launch)
- [Configure the shared portals](#configure-the-shared-portals)
- [Use the administration dashboard](#browser-administration-dashboard)
- [Use the User Portal](#use-the-user-portal)
- [Use the Responder Portal](#use-the-responder-portal)
- [Use the isolated training workspace](#use-the-isolated-training-workspace)
- [Use the coordinator console](#use-the-coordinator-console)
- [Use the responder workspace](#use-the-responder-workspace)
- [Understand priority and recommendations](#understand-priority-and-recommendations)
- [Saved data and reset](#saved-data-and-reset)
- [Run from source](#run-from-source)
- [Build a new Android APK](#build-a-new-android-apk)
- [Run the backend tests](#run-the-backend-tests)
- [Troubleshooting](#troubleshooting)
- [Project layout and documentation](#project-layout-and-documentation)
- [Known limitations](#known-limitations)

## Browser administration dashboard

The dedicated responsive administrative client is in `web/admin/`. Host the complete `web/` directory on a static web server, open `/admin/index.html`, and sign in with the shared API URL and an authorized administrator account. Follow the backend README for Super Admin provisioning, migrations, invitation email settings, and local development-link behavior.

## Install the demo app

The repository includes a ready-to-install APK at [`release/emergency-coordination-system-demo.apk`](release/emergency-coordination-system-demo.apk). You can install it without Flutter or Android Studio. To install with a USB-connected Android phone, you need Android Platform Tools (`adb`) and USB debugging enabled on the phone.

1. Connect the phone to your computer and accept its USB debugging prompt.
2. Check that ADB can see it:

   ```sh
   adb devices -l
   ```

   If more than one device is listed, copy the phone's serial from the first column and use `-s <serial>` in the commands below.

3. Install or update the app:

   ```sh
   adb install -r release/emergency-coordination-system-demo.apk
   # If multiple devices are connected:
   adb -s <serial> install -r release/emergency-coordination-system-demo.apk
   ```

4. Start it from the Android launcher, or launch it with ADB:

   ```sh
   adb shell am start -n edu.cgc.university.emergency_coordination_system/.MainActivity
   # If multiple devices are connected:
   adb -s <serial> shell am start -n edu.cgc.university.emergency_coordination_system/.MainActivity
   ```

The current repository APK is a local demonstration release signed with the generated debug key, not a Play Store or production-signed build. Shared portals require building with the deployed API's HTTPS URL. SHA-256:

```text
8b01f78da2837c1cdb27d6d00db166ff2a956f04747e4143d0674ca2d87d2141
```

To verify the downloaded APK, run `shasum -a 256 release/emergency-coordination-system-demo.apk` on macOS or `sha256sum release/emergency-coordination-system-demo.apk` on Linux.

The checked-in APK was built before the current source follow-up and does not include the new onboarding and password-validation changes. A fresh debug build of this source was validated in `/private/tmp/ecs_redesign_android_build/build/app/outputs/flutter-apk/app-debug.apk`; it has no API URL compiled in and was not installed on a device. Do not treat the checked-in APK as evidence for the current source UI.

## First launch

On a fresh install, the app presents three onboarding slides and then opens the login form directly. Later launches validate a Remember Me session first; if none exists or it is invalid, the login form opens directly. The app does not show an intermediate role portal. Users and Responders are routed from the server-verified account role. Administrative accounts are directed to a dashboard-only message in the mobile app. New public registrations can create only user accounts. The first Super Admin is provisioned with the backend CLI.

The supplied official logo is a red location pin containing a green coordination cross. The original vector is [`assets/brand/official-logo.svg`](assets/brand/official-logo.svg); Flutter renders this SVG directly. Proportion-preserving derivatives are used for Android adaptive, legacy-density, themed monochrome, splash, and PWA icons.

The isolated training workspace has five tabs in the bottom navigation. It appears only when a debug build is launched with `--dart-define=ENABLE_TRAINING_WORKSPACE=true`; it is not part of normal sign-in and cannot be enabled in a release build.

| Tab | What it shows |
|---|---|
| **Overview** | Active incident counts, critical cases, ready responders, priority queue, and recent activity. Tap an incident card to open its details. |
| **Incidents** | Searchable incident list with **All**, **Active**, and **Resolved** filters. Use **New incident** to register a training record. |
| **Responders** | Simulated responder teams, skills, assigned case, availability, and off-duty/available controls. |
| **Resources** | Sample vehicles/resources, their type, and whether they are available or allocated. |
| **Reports** | Local case totals, resolution summary, resolved incident history, and recent activity records. |

### Training workspace interface notes

- The overview puts the active workload first, then shows critical cases, assigned cases, and ready responders as separate scan-friendly counts. Select an incident card to go straight to its details.
- The incident queue combines a text search for type, location, or description with status filters. Use the clear button to reset the search. Select a case to review its priority explanation, assignment, communication, and lifecycle actions.
- Incident details show the response lifecycle as a progress track from **New** through **Resolved**, so the current stage and next action are easier to understand.
- The shared interface follows the reference's charcoal surfaces, bright coral primary actions, rounded cards, and clear status colors. Critical, warning, success, and informational states retain distinct colors; the training banner identifies the isolated simulator.
- Content pages scroll vertically on smaller screens. Use the five-item bottom bar to move between Overview, Incidents, Responders, Resources, and Reports; use the top-right workspace menu to enter the separate responder demo view. The page title stays on one line on compact layouts, and the overview banner identifies the training workspace.
- Empty queues and reports explain that there is no matching content yet. Search and list filters can be cleared or changed without modifying saved records.

Within the training workspace, the profile icon switches between the simulated **Coordinator console** and **Responder workspace**. That training-only menu is not a sign-in or a security boundary.

## Configure the shared portals

The repository contains the actual API implementation in [`backend/`](backend/README.md), its SQLAlchemy schema and initial Alembic migration, SQLite development support, PostgreSQL Compose configuration, secure administrator provisioning, and API tests. There is no hosted API URL, PostgreSQL service, TLS endpoint, push provider, or emergency-agency integration checked into this repository.

To run a local backend, follow [backend/README.md](backend/README.md): create a Python environment, set a private `JWT_SECRET`, apply `alembic upgrade head`, provision the first administrator at a password prompt, then run Uvicorn. Docker Compose can run PostgreSQL locally when Docker is installed. PostgreSQL and Compose could not be exercised in the implementation environment; the tested backend uses in-memory SQLite.

For a clearly synthetic, repeatable local demonstration dataset, follow [docs/DEMO_ACCOUNTS.md](docs/DEMO_ACCOUNTS.md). The opt-in seed command is restricted to development SQLite and creates 50 responder profiles plus role-based demo accounts and real assignment rows. Passwords are generated and shown only at first creation.

The mobile client compiles its public API origin into the app. For local USB-device development, use `adb reverse tcp:8000 tcp:8000` and run Flutter with `--dart-define=API_BASE_URL=http://127.0.0.1:8000`; debug builds permit this loopback HTTP only. Release Android builds reject cleartext traffic and require a real HTTPS endpoint. The client validates the URL and refuses empty, malformed, insecure, or obvious placeholder configuration. No API origin is configured in this repository, so the login stays available but server authentication cannot succeed until an operator configures the real backend URL.

```sh
# Set API_BASE_URL to the actual deployed HTTPS origin first.
sh scripts/build_android_release.sh
```

Remember Me is unchecked by default. When selected, the app stores a rotating refresh credential in Android secure storage, validates the server identity and role at startup, and restores the matching workspace. Access tokens last 30 minutes; remembered sessions last up to 30 days by default. Without Remember Me, the token stays in memory and reopening the app requires sign-in. Clients refresh backend data every 12 seconds and show errors when they cannot synchronize. The separate local training simulator is available only in debug builds compiled with `--dart-define=ENABLE_TRAINING_WORKSPACE=true`; it is not shown in the ordinary login flow or production builds.

### Initial account setup

1. A server operator applies database migrations, sets `ADMIN_EMAIL` to the administrator's actual email, then runs:

   ```sh
   python -m app.provision_admin --email "$ADMIN_EMAIL" --display-name 'Operations Admin'
   ```

   The password is entered twice at a hidden terminal prompt. This one-time process creates the first Super Admin and refuses to run again once one exists. There is no built-in default administrator.
2. The Super Admin opens the browser dashboard, creates Co-Admins with selected permissions, and invites responders with capabilities such as `medical`, `fire`, `rescue`, `security`, or `other`. Responders set their password through the one-time email activation link.
3. People may register as Users from the mobile sign-in screen. Public registration cannot create an admin or responder.
4. Use separate accounts and sessions to test each role. The mobile client does not ask people to choose a role; the server makes every authorization decision.

## Use the administration dashboard

Host the `web/` directory on a static server, add that site's origin to backend `CORS_ORIGINS`, configure `ECS_API_BASE_URL` for the static build (or enter the service URL on the local development login page), and open `/admin/`. The overview, incident queue, responder list, user list, resource inventory, reports, and audit history load current API data. Co-Admins see only views permitted by their account, and the API rejects unauthorized requests even if a client control is bypassed. See [production hosting readiness](docs/operations/hosting.md).

The Super Admin creates Co-Admins and grants a small set of permissions. Responder creation sends a one-time invitation link; in development without SMTP the dashboard displays the local activation link, while production requires a working SMTP configuration. Incident assignment remains a human decision and the API validates responder compatibility, availability, and resource capacity. More dashboard setup detail is in [backend/README.md](backend/README.md).

## Use the User Portal

1. Sign in or create a user account from the unified screen. The server issues the role-bound session and automatically opens the User Portal. Check **Remember me on this device** only on a trusted personal device; this allows automatic return for up to 30 days.
2. Tap **SOS · Request help**. The app requests device location permission and attempts a fresh GPS fix with a 12-second timeout. It shows the timestamp and accuracy.
3. If permission is denied, location services are off, or a current fix is unavailable, enter an address, area, or landmark manually. The app never substitutes the training sample coordinates.
4. Select Ambulance / Medical, Fire and Rescue, Police / Security, or Other Emergency. Add a short description, review the confirmation, then submit.
5. The service records the request with an idempotency key. Repeated taps/retries of the same form return the same incident instead of creating another. The app displays a reference and the current system status. **Received by this coordination system does not mean an emergency service has been contacted or a responder dispatched.**
6. **My requests** refreshes every 12 seconds and displays assignment and response status changes for only the signed-in user's reports. Tap a report to see its status history.

GPS readings older than 15 minutes are rejected by the service. If submission fails, the app displays a connection error and does not show a success message. Location data is sensitive: production use requires a reviewed legal basis, retention limit, access policy, protected TLS deployment, and incident response plan.

Incident submission persists first and runs the separate analysis task afterward. With default `AI_PROVIDER=none`, the backend performs a rules-based source-text scan; it does not call a model. To enable a compatible language model, configure `AI_PROVIDER=openai_compatible`, `AI_BASE_URL`, `AI_MODEL`, and a server-side `AI_API_KEY` in the backend environment. Do not put provider keys in Flutter or commit `.env`. By default the provider receives only the report text, selected category, severity, and urgency; location text is excluded unless `AI_SHARE_INCIDENT_LOCATION=true`, and GPS coordinates are not sent. External model use may cost money and disclose report text to the chosen provider. Configure it only after cost, retention, and privacy review. Model output is schema-validated and source-checked; failures fall back to the rules baseline. The label and audit trail identify the selected provider/model. AI has no dispatch authority.

## Use the Responder Portal

- Activate the invitation sent by the administrator, set a password, then sign in through the unified mobile screen. The server returns only current assignments and that responder's permitted completed history.
- Open a task to review type, description, priority/rationale, report time, reported location, and coordinates if provided.
- Advance one controlled step at a time: **Assigned → Accepted → En Route → On Scene → Resolved**. The server rejects invalid order or attempts to update another responder's task.
- **Add update** records a message visible to the assigned user and admins. **Updates** shows the task history.
- **Share current location once** requests foreground GPS permission, then sends one timestamped, accuracy-labelled point. It does not track in the background. The point is considered for recommendation ranking only while it remains fresh and accurate.
- If an administrator reassigns a task, the previous responder immediately loses write access. Resolving a task releases its associated resource and makes the responder available again.

## Use the isolated training workspace

For a local debug build, pass `--dart-define=ENABLE_TRAINING_WORKSPACE=true` to expose the separate developer training entry on the login screen. The coordinator and responder demonstration workflows below use a device-local JSON file, seeded sample records, simulated coordinates, and a role selector that is not authentication. Data entered here never syncs to the backend or transfers to another device.

## Use the coordinator console

### Register a training incident

1. Open **Incidents** in the bottom navigation.
2. Tap **New incident**.
3. Select an incident type: Medical, Fire, Rescue, Security, or Utility.
4. Enter a short description in **What happened?**. This field is required.
5. Select a simulated area. For a custom landmark, choose **Landmark / other**, then enter the location text. The text is saved as entered; coordinates remain the app's generic simulated “other” point because live GPS and geocoding are not connected.
6. Adjust **Severity** and **Reported urgency** from 1 to 5. The app shows its calculated priority and a brief reason as you change the values.
7. Tap **Register incident**. The incident is saved to this device and appears in the queue. A blank description or location is rejected with a validation message.

### Find and review incidents

- In **Incidents**, enter text in the search field to match an incident's type, location, or description.
- Select **All**, **Active**, or **Resolved** to filter the list.
- Tap an incident card in the queue or on Overview to open **Incident details**.
- The details page shows the priority, status, description, location, report time, severity/urgency, and priority rationale.

### Assign a responder

1. Open an incident whose status is **Queued**.
2. Review **Responder recommendation**. Eligible profiles must be available, unassigned, and have a skill matching the incident type.
3. Compare the shown team, skills, and approximate straight-line distance. Recommendations are ranked by distance; the app does not calculate a route or travel time.
4. Tap **Assign** next to the responder chosen by the coordinator. Assignment is confirmed only after this action. If no eligible responder exists, the case remains queued for review.
5. When a compatible sample resource is available, the app allocates it with the responder. If none is available, the responder can still be assigned and the details will show **No unit available**.

### Advance an incident and close it

From **Incident details**, use the main action button to advance one step at a time:

```text
Queued → Assigned → En route → Responding → Resolved
```

The button label changes with the current status: **Mark en route**, **Mark responding**, then **Resolve incident**. Each update is recorded in the activity history. Resolving a case sets its completion time, releases its responder and allocated resource, and moves it into Reports history. A resolved incident cannot be advanced again.

A responder can also advance the same case from the Responder workspace. Because both views share the same on-device workspace, the coordinator view reflects those changes when you return to it.

### Send a coordination message

1. Open an active incident's details.
2. Type an update under **Coordination messages**.
3. Tap the send icon. The message is saved to the case thread and listed in the activity history.

Messages are local records on this one device. They are not transmitted to another person's phone or account.

### Manage team availability

1. Open **Responders**.
2. Review the responder's team, skills, and status.
3. Tap **Set off duty** to make an unassigned responder ineligible for recommendations, or **Set available** to return them to the available pool.

Responders with an active assignment cannot be marked off duty. The action is hidden while the responder is assigned.

### Review resources and reports

- Open **Resources** to see each simulated vehicle/resource and its allocation. A resource is reserved when a matching type is available during assignment, and released when its incident resolves.
- Open **Reports** for total and resolved case counts, average recorded resolution time, currently available responders, resolved case history, and the 30 most recent activity events.
- These are local summaries of this device's stored records; they are not exported or submitted to an agency.

## Use the responder workspace

1. Tap the profile icon at the top-right of the coordinator console.
2. Select **Responder workspace**.
3. Use **Training profile** to select one of the simulated responders.
4. If the selected responder has no active assignment, the page shows their availability and **No active assignment**.
5. If assigned, review the incident's priority, status, type, location, and description.
6. Tap **Acknowledge & en route**, **Arrived · start response**, and **Mark operation complete** to advance the case in order.
7. Enter an update under **Incident coordination** and tap the send icon to add it to the case thread.
8. Tap the dashboard icon in the upper-right to return to the coordinator console.

The responder selector lets you demonstrate role-specific screens; it does not verify the person's identity or limit access. Both workspaces use the same local data and the same installation.

## Understand priority and recommendations

Priority is a prototype heuristic, not an approved operational triage policy. The app calculates:

```text
score = severity × 2 + urgency × 2 + incident-type factor
```

The incident-type factor is +2 for Medical or Fire, +1 for Rescue or Security, and +0 for Utility. The score maps to priority as follows:

| Score | Displayed priority |
|---:|---|
| 18–22 | Critical |
| 14–17 | High |
| 9–13 | Medium |
| 4–8 | Low |

The incident queue puts Critical before High, Medium, and Low, then shows newer incidents first within a priority. For an individual queued incident, only available, unassigned responders with the matching skill are eligible. They are sorted by straight-line distance, with a deterministic skill-count tie-break. A coordinator must choose **Assign**; the app never autonomously dispatches a responder.

The built-in location choices have simulated coordinates around Mohali. **Landmark / other** uses a generic simulated coordinate. The displayed distance is not a live GPS reading, route, or ETA.

## Saved data and reset

- **Training Workspace:** stored as `emergency_workspace.json` in the Android app's private files directory. This contains only the simulator's local records.
- **Shared portals:** incidents, accounts, assignments, resources, messages, and audit history live in the configured server database. Clearing the app does not remove those shared server records.
- With Remember Me enabled, the app stores the short-lived access token and rotating refresh credential using platform secure storage. Without it, authentication remains in memory only and is not restored after closing the app. Sign out revokes the server session when reachable and always clears local credentials; if the server is offline, the app reports that remote revocation could not be confirmed. Clearing app data removes local training data and credentials, but leaves server records intact.
- The sample workspace is never automatically migrated to the backend. Do not upload sample cases/coordinates as real operations.

## Run from source

### Requirements

- Flutter 3.47.7 and Dart 3.13.5 (or a compatible Flutter SDK).
- Android Studio/Android SDK and Android build tools.
- Android phone or emulator compatible with the installed Flutter SDK.
- For a physical phone: Android Platform Tools (`adb`) and USB debugging enabled.
- For authenticated portals: Python 3.12+ for local FastAPI, or a deployed HTTPS backend; see [`backend/README.md`](backend/README.md).

### Get the source

For the private GitHub repository, authenticate to GitHub first, then clone it:

```sh
git clone https://github.com/QaziZaid16/emergency_coordination_system.git
cd emergency_coordination_system
```

If you already have the project folder, open a terminal in that directory instead.

If that checkout is on the Seagate exFAT drive, stage it to APFS before running Flutter's Android commands:

```sh
project_dir="$PWD"
working_dir="/private/tmp/ecs_android_build"
mkdir -p "$working_dir"
rsync -a \
  --exclude='.git/' \
  --exclude='._*' \
  --exclude='build/' \
  --exclude='.dart_tool/' \
  --exclude='android/.gradle/' \
  --exclude='backend/.venv/' \
  --exclude='backend/__pycache__/' \
  "$project_dir/" "$working_dir/"
cd "$working_dir"
```

Now run Flutter commands from the cloned folder or this staging folder:

```sh
flutter doctor
flutter pub get
flutter devices
```

Choose the Android device ID shown by `flutter devices` and start the debug app:

```sh
flutter run -d <android-device-id>
```

To use a local API from the connected phone, start Uvicorn on port 8000, run `adb reverse tcp:8000 tcp:8000`, then start Flutter with `--dart-define=API_BASE_URL=http://127.0.0.1:8000`. For a deployed service, pass its real HTTPS base URL at build/run time. If configuration is missing, the direct login screen stays usable and reports sign-in unavailability only when sign-in is attempted.

To stop the running debug session, press `q` in the terminal where `flutter run` is active, or press `Ctrl+C`.

**Seagate/exFAT checkout:** this project is stored on an exFAT external volume, where macOS AppleDouble files can interfere with Android Gradle builds. For the checkout on that drive, stage the project to APFS before `flutter run` or `flutter build`; use the staging procedure in [Build a new Android APK](#build-a-new-android-apk). A clone on a normal APFS volume can be run directly.

### Run checks

```sh
flutter analyze
flutter test
```

This runs the dispatch rules, local store behavior, widget tests, and role-login configuration check. Run it from APFS staging because macOS AppleDouble `._*` metadata files on the exFAT source volume can confuse Flutter test discovery.

Backend tests run separately from `backend/` with `python -m pytest -q`. They use in-memory SQLite; API code and migration files are run from an APFS staging copy on this Mac because the exFAT checkout contains AppleDouble metadata.

## Build a new Android APK

This project is stored on an exFAT Seagate volume. macOS AppleDouble metadata on that volume can interfere with Gradle Android resource processing. Build from an APFS staging folder instead. From the project root, run:

```sh
project_dir="$PWD"
build_dir="/private/tmp/ecs_android_build"
mkdir -p "$build_dir"
rsync -a \
  --exclude='.git/' \
  --exclude='._*' \
  --exclude='build/' \
  --exclude='.dart_tool/' \
  --exclude='android/.gradle/' \
  --exclude='backend/.venv/' \
  --exclude='backend/__pycache__/' \
  "$project_dir/" "$build_dir/"
cd "$build_dir"
flutter pub get
flutter analyze
flutter test
# Set API_BASE_URL to an HTTPS deployment URL for authenticated portals.
API_BASE_URL="${API_BASE_URL:?Set a real HTTPS API_BASE_URL}"
sh scripts/build_android_release.sh
cp build/app/outputs/flutter-apk/app-release.apk \
  "$project_dir/release/emergency-coordination-system-demo.apk"
```

The APK output is `build/app/outputs/flutter-apk/app-release.apk` inside the staging folder. After copying it back, calculate a new checksum if you plan to distribute the APK:

```sh
shasum -a 256 "$project_dir/release/emergency-coordination-system-demo.apk"
```

The release variant signs with the generated debug key. It is suitable for local development/demo only. A release build requires a real HTTPS API URL; production distribution also requires protected signing, a deployed and secured backend, security/privacy review, and operational validation. The local simulator is development-only and excluded from release builds.

## Troubleshooting

### `adb devices` shows no phone

- Unlock the phone and turn on **Developer options → USB debugging**.
- Reconnect the USB cable and accept the phone's debugging authorization prompt.
- Run `adb devices -l` again. If it shows `unauthorized`, accept the prompt on the phone. If it shows `offline`, reconnect or restart ADB with `adb kill-server` followed by `adb start-server`.

### More than one device or emulator is connected

Pass the intended device serial explicitly:

```sh
adb -s <serial> install -r release/emergency-coordination-system-demo.apk
```

For Flutter, use the device ID from `flutter devices` with `flutter run -d <android-device-id>`.

### The app says no responder is eligible

Recommendations require a responder who is available, has no active incident, and has a skill matching the incident type. Check the **Responders** tab for off-duty or assigned responders. Keep the case queued until a suitable simulated team is available.

### The incident has no resource assigned

A responder can be assigned without a vehicle/resource if no unallocated resource of that same type is available. Check **Resources**, or resolve another simulated case to release its allocation.

### Gradle reports unexpected Android resource files or `._` entries

Build from the APFS staging directory shown above. Do not delete broad directories from the Seagate drive to work around AppleDouble metadata.

### The project fails to start because Android storage is unavailable

The Android app uses a method channel in `MainActivity.kt` to open the optional device-local training workspace. Run the Android app through Flutter or install the included Android APK.

### A shared portal says the service URL is missing or unavailable

Build/run with `--dart-define=API_BASE_URL=...`. For local USB development, start the local backend, use `adb reverse tcp:8000 tcp:8000`, and set `http://127.0.0.1:8000` in a debug build. Release builds require HTTPS. Remember Me is opt-in. The backend migration for rotating refresh credentials must be applied before enabling it on an existing database. The client restores sessions through the API, refreshes access tokens, and returns to sign-in after expiry or revocation. See [the deep audit](docs/audit/deep-bug-audit.md) for the session policy and remaining limitations.

### A changed APK will not install over an existing one

The included local demo uses a debug signing key. Android permits in-place updates only when the signing key matches. If you intentionally switch to a differently signed build, uninstall the existing app first; uninstalling clears its local workspace data.

## Project layout and documentation

```text
lib/
  data/                 Training JSON store and shared API client
  domain/               Incident/responder models and dispatch rules
  presentation/          Admin, User, Responder portals and isolated training UI
backend/                 FastAPI service, SQLAlchemy schema, migrations, tests
android/                 Android host and app-private storage channel
test/                    Flutter dispatch, store, and role-login widget tests
backend/tests/            API auth, ownership, assignment and lifecycle tests
docs/requirements/       Source extraction and traceability matrix
docs/audit/              Architecture, discovery, roadmap, verification
docs/                    Design system, UX, CI, demos, external requirements
release/                 Installable classroom-demonstration APK
```

Detailed records:

- [`docs/requirements/requirements-extraction.md`](docs/requirements/requirements-extraction.md) — source findings, assumptions, and unresolved items.
- [`docs/requirements/traceability-matrix.md`](docs/requirements/traceability-matrix.md) — requirement IDs, implementation mapping, and verification status.
- [`docs/audit/architecture.md`](docs/audit/architecture.md) — design, data model, rules, and boundaries.
- [`docs/audit/discovery.md`](docs/audit/discovery.md) — source inventory and target-directory decision.
- [`docs/audit/test-results.md`](docs/audit/test-results.md) — executed checks, outcomes, evidence, and limits.
- [`docs/UX_UI_AUDIT.md`](docs/UX_UI_AUDIT.md) and [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md) — UX findings and shared mobile/web tokens.
- [`docs/DEMO_ACCOUNTS.md`](docs/DEMO_ACCOUNTS.md) — safe local demo seed command and first-run credentials.
- [`docs/CI_CD_AUDIT.md`](docs/CI_CD_AUDIT.md) — CI workflow scope and remote verification limits.
- [`docs/EXTERNAL_REQUIREMENTS.md`](docs/EXTERNAL_REQUIREMENTS.md) — existing environment configuration and secret locations.
- [`docs/audit/release-readiness-2026-10-24.md`](docs/audit/release-readiness-2026-10-24.md) — current Android, database, concurrency, security, accessibility, and recovery status.
- [`docs/operations/backup-and-recovery.md`](docs/operations/backup-and-recovery.md) — PostgreSQL logical backup and isolated restore-drill procedure.
- [`docs/audit/implementation-roadmap.md`](docs/audit/implementation-roadmap.md) — delivered prototype scope and deferred work.
- [`backend/README.md`](backend/README.md) — API setup, roles, security, migrations, and local device integration.
- [`SETUP.md`](SETUP.md) — condensed setup and handover procedure.

## Latest release-readiness status

As of 2026-10-24, `flutter analyze`, the 28 explicitly selected Flutter tests, all 19 backend tests, SQLite migration checks, and two SQLite concurrency tests pass. The Android debug APK builds from a clean APFS staging copy; the exFAT checkout itself contains AppleDouble metadata that breaks broad test discovery and Gradle resource scanning. PostgreSQL migration/concurrency behavior, accessibility conformance, and backup restoration have not been verified. The Android release build still uses debug signing, and login/refresh rate limiting is not implemented. This remains a development platform, not a production or emergency-dispatch service; see the [release-readiness report](docs/audit/release-readiness-2026-10-24.md) for evidence and blockers.

## Known limitations

- No backend is hosted by this repository. Shared portals need an operator-provisioned service URL and database; PostgreSQL/Compose were not available for integration testing in this environment.
- No map provider, geocoding/routing/traffic, push notification provider, phone call, or external ambulance/fire/police integration is configured. Clients use 12-second polling and one-time foreground responder location sharing.
- The isolated training responder selector is not authentication. Its simulated responders, resource inventory, and Mohali-area coordinates remain separate from server data.
- Priority and proximity rankings are prototype decision support, not approved dispatch/triage policies.
- The APK is demo-signed with a debug key. No production signing, hosting, rate-limit gateway, security penetration review, backup/restore validation, accessibility audit, or field validation has been completed.
