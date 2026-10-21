# Emergency Coordination System

Flutter Android prototype for coordinating simulated emergency incidents, response teams and resources. The coordinator can register requests, review priority and responder recommendations, confirm assignments, track status changes, coordinate through incident notes and review history. A separate responder workspace displays assignments and lets a selected training profile update status and message the coordinator view on the same device.

> **Training prototype only.** The app does not contact emergency services, dispatch real responders, share live location or connect to an agency system. Do not use it for real emergency operations.

## Install the demonstration build

A ready-to-install Android release APK is included at [`release/emergency-coordination-system-demo.apk`](release/emergency-coordination-system-demo.apk). Connect an Android device with USB debugging enabled, then run:

```sh
adb devices
adb install -r release/emergency-coordination-system-demo.apk
adb shell am start -n edu.cgc.university.emergency_coordination_system/.MainActivity
```

The APK was installed and launched on a physical Android CPH2691 during verification. SHA-256: `c8baf5ec96b646476b3387dd08cd264d6ce2db7af2b9a9e76b63b3e969b857f6`.

## Run from source

Requirements: Flutter SDK, Android SDK/Studio and Android emulator/device. The delivered project was generated with Flutter 3.47.7 / Dart 3.13.5. From the project directory:

```sh
flutter pub get
flutter analyze
flutter test test/dispatch_rules_test.dart test/operations_store_test.dart test/widget_test.dart
flutter run -d <android-device-id>
```

The project lives on an exFAT volume. macOS creates `._*` AppleDouble files there, and Gradle can mistake those for Android resource directories. For Android builds, stage the source on a native APFS volume (example below), build there, then copy the APK back:

```sh
project_dir="$PWD"
build_dir="/private/tmp/ecs_android_build"
mkdir -p "$build_dir"
rsync -a --exclude='._*' --exclude='build/' --exclude='.dart_tool/' --exclude='android/.gradle/' "$project_dir/" "$build_dir/"
cd "$build_dir"
flutter pub get
flutter build apk --release
cp build/app/outputs/flutter-apk/app-release.apk \
  "$project_dir/release/emergency-coordination-system-demo.apk"
```

The release build uses the generated debug signing key. It is for local demonstration only; configure a protected production keystore before distribution. The delivered prototype does not have a production signing configuration.

## Data and integrations

Android stores one JSON workspace in the app-private files directory using a small Flutter-to-Kotlin method channel. Android does not request broad storage permissions. Sample incidents, responder coordinates, skills and equipment are simulated and visibly labeled. The initial record is seeded once; app data can be cleared from Android settings to reset the workspace.

No login, access control, cloud synchronization, backups, live GPS/maps/traffic, push notifications, external agency APIs or autonomous dispatch are implemented. The responder profile selector is not authentication. Priority and matching rules are documented in `docs/audit/architecture.md` and are decision support; a human coordinator confirms assignments.

## Project documents

- `docs/requirements/requirements-extraction.md` — source findings, assumptions and unresolved items.
- `docs/requirements/traceability-matrix.md` — requirement IDs and implementation/test evidence.
- `docs/audit/architecture.md` — architecture, model and operational boundaries.
- `docs/audit/discovery.md` — source inventory and storage decision.
- `docs/audit/test-results.md` — actual verification results and limits.
- `docs/audit/implementation-roadmap.md` — build scope and deferred work.

See `SETUP.md` for the detailed run/build and handover procedure.
