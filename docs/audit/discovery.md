# Discovery report

Date: 2026-10-21 (client local date). Target: `/Volumes/Seagate Por/emergency_coordination_system`.

## Source inventory

- User supplied `Synopsis1.pdf` (16 pages) and `Emergency Coordination System PPT.pdf` (18 slides). All pages/slides yielded extractable text; embedded PPT graphics were reviewed. Text extraction and image previews were performed.
- The pasted master prompt contains implementation and workflow requirements but ends in its required-document list at “as app/”. Its remaining list is unavailable.
- Workspace root was `/Volumes/Seagate Por/resilio_flutter`. It contains an existing Flutter app, backend source and a local database file. `git status` reports that it is not a Git repository. It was inspected only as reference and was not changed by this rebuild.
- The mounted Seagate volume is `/dev/disk4s1`, mounted at `/Volumes/Seagate Por`, filesystem exFAT, 1.8 TiB capacity and approximately 515 GiB available at inspection. New project directory did not exist before this work; no formatting, repartitioning or broad cleanup was performed.
- exFAT/macOS AppleDouble behavior affects Gradle intermediates and Flutter's default test discovery. APK build is performed from an APFS staging copy; Android emulator build/run and a physical CPH2691 phone install/launch succeeded from that copy.

## Location decision

Create the new project beside the existing app in its own directory. This preserves the original tree and makes the rebuild independently identifiable. Generated output for Gradle is staged on APFS because exFAT metadata files break Android resource parsing. The clean project and documentation remain on the external drive.

## Verified starting state

- Flutter SDK available: Flutter 3.47.7, Dart 3.13.5; Android SDK 36 and emulator `emulator-5554` available.
- Android Studio bundled Java 25 is selected by Flutter. Direct Gradle invocation used system JDK 26 and failed in `jlink`; Flutter-driven build avoided that specific path.
- No third-party service credentials or live-agency endpoints were provided or used.
