# Setup and handover

## Android development

1. Install Flutter 3.47.7 (or a compatible later stable release), Android Studio with Android SDK/build tools, and an Android emulator or Android 8.0+ device.
2. Open this directory in Android Studio or VS Code.
3. Run `flutter pub get`.
4. Confirm `flutter devices` lists an Android device.
5. Run `flutter run -d <android-device-id>`.

The app obtains the sandboxed Android files directory over a method channel in `MainActivity.kt`, then stores `emergency_workspace.json` there. It requests no location, contacts, network or broad file access permission. Android app data deletion resets the local workspace and its simulated seed records.

## Checks

```sh
flutter analyze
flutter test test/dispatch_rules_test.dart test/operations_store_test.dart test/widget_test.dart
```

Name test files explicitly: macOS AppleDouble `._*.dart` metadata files on exFAT are not Dart sources but Flutter's default test discovery may attempt to parse them.

## Install the included release APK

Connect an Android device with USB debugging enabled, confirm `adb devices` lists it, then install and launch:

```sh
adb install -r release/emergency-coordination-system-demo.apk
adb shell am start -n edu.cgc.university.emergency_coordination_system/.MainActivity
```

The included APK was installed and launched on a physical Android CPH2691. SHA-256: `24ff2c9842fef6cef592c5c445a07d08467838fb0d5f77d91fb4d8dce7a08960`.

## Build a new release APK for classroom demonstration

The Seagate volume is exFAT. Gradle writes intermediate Android resource directories there, and macOS AppleDouble metadata may be interpreted as resources. Stage the source to an APFS path, excluding generated metadata/build caches, then build:

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

APK output: `build/app/outputs/flutter-apk/app-release.apk`. The current generated release variant signs with the debug key. Do not distribute it as a production release. A production keystore, secure signing configuration, privacy/security design, service hosting and field validation are outside this academic prototype scope.

## Operating the prototype

- Register incidents in the Incidents tab. Enter type, description, location/landmark, severity and reported urgency. The priority and rule rationale update before registration.
- Open a queued incident to review eligible responders ordered by straight-line distance and select Assign. A matching available unit is reserved when present.
- Advance the incident Assigned → En route → Responding → Resolved. Resolution releases the responder and resource.
- Use Responder workspace from the profile menu to select a simulated responder, read the assignment and update status or add an incident message.
- Use Response teams to mark an unassigned responder off duty/available. Assigned responders cannot be taken off duty.
- Resources and Reports show current allocation and local operation history.

All times/data are local to the device. Messages are stored on that device and are not delivered to other users.
