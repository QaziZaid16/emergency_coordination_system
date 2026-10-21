# Emergency Coordination System

A Flutter and Dart Android training prototype for coordinating simulated emergency incidents, responders, and resources. It includes a coordinator console and a responder workspace on one device, local operation records, priority recommendations, incident status tracking, and reports.

> **Training prototype only. Do not use this app to report or coordinate a real emergency.** It does not contact emergency services, dispatch real responders, share live location, authenticate users, or connect to an agency system. For a real emergency, use the emergency number and procedures applicable to your location.

## Contents

- [Install the demo app](#install-the-demo-app)
- [First launch](#first-launch)
- [Use the coordinator console](#use-the-coordinator-console)
- [Use the responder workspace](#use-the-responder-workspace)
- [Understand priority and recommendations](#understand-priority-and-recommendations)
- [Saved data and reset](#saved-data-and-reset)
- [Run from source](#run-from-source)
- [Build a new Android APK](#build-a-new-android-apk)
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

The APK was installed and launched on a physical Android CPH2691 during verification. It is a demonstration release signed with the generated debug key, not a Play Store or production-signed build. SHA-256:

```text
c8baf5ec96b646476b3387dd08cd264d6ce2db7af2b9a9e76b63b3e969b857f6
```

To verify the downloaded APK, run `shasum -a 256 release/emergency-coordination-system-demo.apk` on macOS or `sha256sum release/emergency-coordination-system-demo.apk` on Linux.

## First launch

The app opens to **Operations overview**. On the first launch it creates a simulated training workspace containing one sample medical incident, four responder profiles, and four resource records. All seeded sample content is for demonstration; it is not a real emergency report or live resource inventory.

The app has five tabs in the bottom navigation:

| Tab | What it shows |
|---|---|
| **Overview** | Active incident counts, critical cases, ready responders, priority queue, and recent activity. Tap an incident card to open its details. |
| **Incidents** | Searchable incident list with **All**, **Active**, and **Resolved** filters. Use **New incident** to register a training record. |
| **Responders** | Simulated responder teams, skills, assigned case, availability, and off-duty/available controls. |
| **Resources** | Sample vehicles/resources, their type, and whether they are available or allocated. |
| **Reports** | Local case totals, resolution summary, resolved incident history, and recent activity records. |

Tap the profile icon in the upper-right corner to choose **Coordinator console** (returns to Overview) or open **Responder workspace**. The profile menu is a demonstration shortcut, not a sign-in or a security boundary.

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

- On Android, the workspace is stored as `emergency_workspace.json` in the app's private files directory. No broad storage permission is requested.
- Incidents, assignments, responder availability, resources, messages, and activity remain after closing and reopening the app.
- Data is not backed up or synchronized to a server or another device.
- To clear the training workspace and restore the initial sample data, open Android **Settings → Apps → Emergency Coordination → Storage → Clear data**. Names in Android Settings may vary by device. Clearing app data permanently removes the records saved by this installation.
- Uninstalling the app also removes its private workspace data. Do not use the sample workspace for real or irreplaceable records.

## Run from source

### Requirements

- Flutter 3.47.7 and Dart 3.13.5 (or a compatible Flutter SDK).
- Android Studio/Android SDK and Android build tools.
- Android phone or emulator compatible with the installed Flutter SDK.
- For a physical phone: Android Platform Tools (`adb`) and USB debugging enabled.

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

To stop the running debug session, press `q` in the terminal where `flutter run` is active, or press `Ctrl+C`.

**Seagate/exFAT checkout:** this project is stored on an exFAT external volume, where macOS AppleDouble files can interfere with Android Gradle builds. For the checkout on that drive, stage the project to APFS before `flutter run` or `flutter build`; use the staging procedure in [Build a new Android APK](#build-a-new-android-apk). A clone on a normal APFS volume can be run directly.

### Run checks

```sh
flutter analyze
flutter test test/dispatch_rules_test.dart test/operations_store_test.dart test/widget_test.dart
```

The targeted test command runs the dispatch rules, local store behavior, and widget test files. Explicit file names are used because macOS AppleDouble `._*` metadata files on the exFAT source volume can confuse default Flutter test discovery.

## Build a new Android APK

This project is stored on an exFAT Seagate volume. macOS AppleDouble metadata on that volume can interfere with Gradle Android resource processing. Build from an APFS staging folder instead. From the project root, run:

```sh
project_dir="$PWD"
build_dir="/private/tmp/ecs_android_build"
mkdir -p "$build_dir"
rsync -a \\
  --exclude='.git/' \\
  --exclude='._*' \\
  --exclude='build/' \\
  --exclude='.dart_tool/' \\
  --exclude='android/.gradle/' \\
  "$project_dir/" "$build_dir/"
cd "$build_dir"
flutter pub get
flutter analyze
flutter test test/dispatch_rules_test.dart test/operations_store_test.dart test/widget_test.dart
flutter build apk --release
cp build/app/outputs/flutter-apk/app-release.apk \\
  "$project_dir/release/emergency-coordination-system-demo.apk"
```

The APK output is `build/app/outputs/flutter-apk/app-release.apk` inside the staging folder. After copying it back, calculate a new checksum if you plan to distribute the APK:

```sh
shasum -a 256 "$project_dir/release/emergency-coordination-system-demo.apk"
```

The current release variant signs with the generated debug key. It is suitable for local classroom demonstration only. A distributable production release requires a protected signing key, a production security and privacy design, and operational validation; those are not part of this prototype.

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

The Android app uses a method channel in `MainActivity.kt` to obtain its app-private files directory. Run the Android app through Flutter or install the included Android APK; a web build does not provide this Android storage channel.

### A changed APK will not install over an existing one

The included local demo uses a debug signing key. Android permits in-place updates only when the signing key matches. If you intentionally switch to a differently signed build, uninstall the existing app first; uninstalling clears its local workspace data.

## Project layout and documentation

```text
lib/
  data/                 Local persistence and operational workflows
  domain/               Incident/responder models and dispatch rules
  presentation/          Coordinator screens and responder workspace
android/                 Android host and app-private storage channel
test/                    Dispatch, store/persistence, and widget tests
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
- [`SETUP.md`](SETUP.md) — condensed setup and handover procedure.

## Known limitations

- Android academic prototype; the responder selector is not authentication or access control.
- One device and one local JSON workspace; no cloud sync, backup, account system, or cross-device messaging.
- Simulated responders, resources, and Mohali-area coordinates. No live GPS, map, geocoding, routing, traffic, push notification, call, or agency API.
- Priority thresholds and recommendation ranking are assumptions documented for this prototype, not a substitute for approved dispatch policy.
- The APK is demo-signed with a debug key. No production signing, hosting, security review, accessibility audit, or field validation has been performed.
