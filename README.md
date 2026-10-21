# Emergency Coordination System

A Flutter and Dart Android app with three role-specific portals—Admin, User, and Responder—connected to a shared FastAPI service, plus the original isolated local training workspace. The service owns authenticated multi-user incidents, role access, assignments, resources, status history, and audit records. Backend and mobile clients are included; this repository does not include a hosted service or agency integration.

> **Development platform only. Do not use this app to report or coordinate a real emergency.** A configured instance can capture and share device location with its coordination backend, but it does not contact emergency services or dispatch an ambulance, fire service, or police. Priority is a prototype heuristic, not a validated triage policy. For a real emergency, use the emergency number and procedures applicable to your location.

## Contents

- [Install the demo app](#install-the-demo-app)
- [First launch](#first-launch)
- [Configure the shared portals](#configure-the-shared-portals)
- [Use the Admin Portal](#use-the-admin-portal)
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
3262297dce56f1f2305216a47e88dc8cc6d4740b479bb98b6bb2d388cfeafda0
```

To verify the downloaded APK, run `shasum -a 256 release/emergency-coordination-system-demo.apk` on macOS or `sha256sum release/emergency-coordination-system-demo.apk` on Linux.

## First launch

The app opens to a portal chooser. Choose **Admin Portal**, **User Portal**, or **Responder Portal** to sign in to the shared backend. New public registrations can create only user accounts. An administrator provisions the first admin with the backend CLI and creates responder accounts; changing the portal selection cannot elevate an account's stored role. **Open isolated training workspace** enters the original local-only simulator, whose sample records are stored separately on that device and are never imported into the shared database.

The custom mark combines a location pin with a centered coordination point and two linked response nodes in the app’s teal/coral palette. The identity appears in Android adaptive icons, legacy density assets, Android 13 themed monochrome icons, the native splash screen, portal headers, and web/PWA assets. The editable vector source is [`assets/brand/emergency-coordination-icon.svg`](assets/brand/emergency-coordination-icon.svg).

The isolated training workspace has five tabs in the bottom navigation:

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
- The shared interface uses deep teal for primary actions, warm coral for urgency emphasis, high contrast status labels, and consistent card and form styles. The training label remains visible in the top bar.
- Content pages scroll vertically on smaller screens. Use the five-item bottom bar to move between Overview, Incidents, Responders, Resources, and Reports; use the top-right workspace menu to enter the separate responder demo view.
- Empty queues and reports explain that there is no matching content yet. Search and list filters can be cleared or changed without modifying saved records.

Within the training workspace, the profile icon switches between the simulated **Coordinator console** and **Responder workspace**. That training-only menu is not a sign-in or a security boundary.

## Configure the shared portals

The repository contains the actual API implementation in [`backend/`](backend/README.md), its SQLAlchemy schema and initial Alembic migration, SQLite development support, PostgreSQL Compose configuration, secure administrator provisioning, and API tests. There is no hosted API URL, PostgreSQL service, TLS endpoint, push provider, or emergency-agency integration checked into this repository.

To run a local backend, follow [backend/README.md](backend/README.md): create a Python environment, set a private `JWT_SECRET`, apply `alembic upgrade head`, provision the first administrator at a password prompt, then run Uvicorn. Docker Compose can run PostgreSQL locally when Docker is installed. PostgreSQL and Compose could not be exercised in the implementation environment; the tested backend uses in-memory SQLite.

The mobile client compiles its API host into the app. For local USB-device development, use `adb reverse tcp:8000 tcp:8000` and run Flutter with `--dart-define=API_BASE_URL=http://127.0.0.1:8000`; debug builds permit this loopback HTTP only. Release Android builds reject cleartext traffic and require an HTTPS endpoint:

```sh
flutter build apk --release --dart-define=API_BASE_URL=https://your-deployed-api.example
```

If no API host is supplied, portal login shows that it is not configured. The app still offers the isolated training workspace. The sign-in screen has an unchecked **Remember me on this device** option. When selected, the app stores a rotating refresh credential in Android secure storage, validates the server identity and role at startup, and restores the matching portal. Access tokens last 30 minutes; the remembered server session lasts up to 30 days by default, after which the user signs in again. Without the option, the token stays in memory and reopening the app requires sign-in. Clients refresh backend data every 12 seconds and show errors when they cannot synchronize.

### Initial account setup

1. A server operator applies database migrations and runs `python -m app.provision_admin --email ... --name ...`. The password is entered twice at a hidden terminal prompt; there is no built-in default administrator.
2. The administrator signs in through **Admin Portal** and creates responder accounts, including lower-case service capabilities such as `medical`, `fire`, `rescue`, `security`, or `other`.
3. People may create user accounts from **User Portal**. Public registration cannot create an admin or responder.
4. Use separate accounts and sessions to test each role. The app's role chooser is only a login entry point; the server makes every authorization decision.

## Use the Admin Portal

- **Dashboard** shows total, active, unassigned, assigned, in-progress, and resolved reports; responder availability; and resource allocation from the backend.
- **Incidents** supports search by reference, type, description, location, priority, status, or responder, plus All, Active, Unassigned, and Resolved filters. Cards show priority rationale, severity, urgency, report time, reported location, and coordinates/accuracy when available.
- Select **Assign** or **Reassign**, review eligible available responders, and select one. Distance appears only when the user's and responder's GPS readings are no older than 15 minutes and each has recorded accuracy of 100 m or better. Otherwise distance is shown as unavailable; the admin still chooses the responder.
- An optional available resource can be allocated with an assignment. The backend checks current availability and serializes assignment/resource changes in a database transaction. Database constraints reject conflicting active assignments.
- **Responders** can be created, have capabilities edited, and be marked available/unavailable. **Users** can be deactivated/reactivated; deactivation revokes their active sessions. **Resources** can be added, edited, enabled, or disabled. **Audit** shows administrative and operational changes.
- Resolve and cancel actions require confirmation. Both close the record and release the current responder/resource. This is an internal platform update; no external agency is notified.

## Use the User Portal

1. Choose **User Portal**. Register a user account or sign in. The server issues the role-bound session. Check **Remember me on this device** only on a trusted personal device; this allows automatic return to the User Portal for up to 30 days.
2. Tap **SOS · Request help**. The app requests device location permission and attempts a fresh GPS fix with a 12-second timeout. It shows the timestamp and accuracy.
3. If permission is denied, location services are off, or a current fix is unavailable, enter an address, area, or landmark manually. The app never substitutes the training sample coordinates.
4. Select Ambulance / Medical, Fire and Rescue, Police / Security, or Other Emergency. Add a short description, review the confirmation, then submit.
5. The service records the request with an idempotency key. Repeated taps/retries of the same form return the same incident instead of creating another. The app displays a reference and the current system status. **Received by this coordination system does not mean an emergency service has been contacted or a responder dispatched.**
6. **My requests** refreshes every 12 seconds and displays assignment and response status changes for only the signed-in user's reports. Tap a report to see its status history.

GPS readings older than 15 minutes are rejected by the service. If submission fails, the app displays a connection error and does not show a success message. Location data is sensitive: production use requires a reviewed legal basis, retention limit, access policy, protected TLS deployment, and incident response plan.

## Use the Responder Portal

- Sign in with an administrator-created responder account. The server returns only current assignments and that responder's permitted completed history.
- Open a task to review type, description, priority/rationale, report time, reported location, and coordinates if provided.
- Advance one controlled step at a time: **Assigned → Accepted → En Route → On Scene → Resolved**. The server rejects invalid order or attempts to update another responder's task.
- **Add update** records a message visible to the assigned user and admins. **Updates** shows the task history.
- **Share current location once** requests foreground GPS permission, then sends one timestamped, accuracy-labelled point. It does not track in the background. The point is considered for recommendation ranking only while it remains fresh and accurate.
- If an administrator reassigns a task, the previous responder immediately loses write access. Resolving a task releases its associated resource and makes the responder available again.

## Use the isolated training workspace

Open **Isolated training workspace** on the portal chooser. The existing coordinator and responder demonstration workflows below continue to use a device-local JSON file, seeded sample records, simulated coordinates, and a role selector that is not authentication. Data entered here never syncs to the backend or transfers to another device.

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

To use a local API from the connected phone, start Uvicorn on port 8000, run `adb reverse tcp:8000 tcp:8000`, then start Flutter with `--dart-define=API_BASE_URL=http://127.0.0.1:8000`. For a deployed service, pass its HTTPS base URL at build/run time. The portal login pages explain when the URL is missing.

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
API_BASE_URL="${API_BASE_URL:-}"
flutter build apk --release --dart-define=API_BASE_URL="$API_BASE_URL"
cp build/app/outputs/flutter-apk/app-release.apk \
  "$project_dir/release/emergency-coordination-system-demo.apk"
```

The APK output is `build/app/outputs/flutter-apk/app-release.apk` inside the staging folder. After copying it back, calculate a new checksum if you plan to distribute the APK:

```sh
shasum -a 256 "$project_dir/release/emergency-coordination-system-demo.apk"
```

The release variant signs with the generated debug key. It is suitable for local development/demo only. Use an HTTPS API URL to enable server-backed portals in a build; leaving it blank disables authenticated API calls but keeps the isolated training workspace available. A distributable production release requires a protected signing key, a deployed and secured backend, security/privacy review, and operational validation.

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
release/                 Installable classroom-demonstration APK
```

Detailed records:

- [`docs/requirements/requirements-extraction.md`](docs/requirements/requirements-extraction.md) — source findings, assumptions, and unresolved items.
- [`docs/requirements/traceability-matrix.md`](docs/requirements/traceability-matrix.md) — requirement IDs, implementation mapping, and verification status.
- [`docs/audit/architecture.md`](docs/audit/architecture.md) — design, data model, rules, and boundaries.
- [`docs/audit/discovery.md`](docs/audit/discovery.md) — source inventory and target-directory decision.
- [`docs/audit/test-results.md`](docs/audit/test-results.md) — executed checks, outcomes, evidence, and limits.
- [`docs/audit/implementation-roadmap.md`](docs/audit/implementation-roadmap.md) — delivered prototype scope and deferred work.
- [`backend/README.md`](backend/README.md) — API setup, roles, security, migrations, and local device integration.
- [`SETUP.md`](SETUP.md) — condensed setup and handover procedure.

## Known limitations

- No backend is hosted by this repository. Shared portals need an operator-provisioned service URL and database; PostgreSQL/Compose were not available for integration testing in this environment.
- No map provider, geocoding/routing/traffic, push notification provider, phone call, or external ambulance/fire/police integration is configured. Clients use 12-second polling and one-time foreground responder location sharing.
- The isolated training responder selector is not authentication. Its simulated responders, resource inventory, and Mohali-area coordinates remain separate from server data.
- Priority and proximity rankings are prototype decision support, not approved dispatch/triage policies.
- The APK is demo-signed with a debug key. No production signing, hosting, rate-limit gateway, security penetration review, backup/restore validation, accessibility audit, or field validation has been completed.
