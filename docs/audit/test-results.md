# Verification record

## Baseline

- Flutter Android/Web scaffold generated and dependencies resolved successfully in the clean target project.
- Text extracted from 18 PPT slides and 16 Synopsis pages; PPT visuals reviewed.
- Static analysis completed with `No issues found`.
- Targeted test suite completed: `flutter test test/dispatch_rules_test.dart test/operations_store_test.dart test/widget_test.dart` — 7 tests passed. Default test discovery on the exFAT source volume encounters macOS `._*` AppleDouble files; targeted tests run from the APFS staging copy.
- Release APK built successfully from `/private/tmp/ecs_android_build` using Flutter 3.47.7 / Dart 3.13.5; handoff copy is `release/emergency-coordination-system-demo.apk` (SHA-256 `c8baf5ec96b646476b3387dd08cd264d6ce2db7af2b9a9e76b63b3e969b857f6`).
- APK installed and launched on physical Android device `CPH2691` (ADB serial `a102172d`); process confirmed running. This is a local demonstration build signed with the generated debug key.

## Test cases

| Case | Requirements | Expected result | Status / evidence |
|---|---|---|---|
| T-001 | FR-001, FR-003 | Required fields validated; valid incident saved with priority explanation. | Pass — widget test; Android form validation and valid incident creation verified. |
| T-002 | FR-005, FR-006 | Busy/ineligible responders excluded; concurrent incidents cannot double-assign. | Pass — dispatch rule tests. |
| T-003 | FR-007 | Legal status changes recorded; resolve releases resources. | Pass — store test and Android lifecycle walkthrough through Resolved. |
| T-004 | FR-008 | Availability changes on allocation and restores on closure. | Pass — store test and Android walkthrough. |
| T-005 | FR-009, FR-012 | Incident message visible to coordinator and responder views. | Pass — store/widget tests. |
| T-006 | FR-010–011 | Dashboard and reports reflect operations and closures. | Pass — Android walkthrough verified dashboard and resolved report. |
| T-007 | NFR-003 | Restart restores incidents, responders, resources and messages. | Pass — Android force-stop/relaunch preserved locally stored incident. |
| T-008 | NFR-001 | Static analysis and Android debug build succeed. | Pass — analyzer clean; release APK also built successfully from APFS staging. |
| T-009 | UI-001 | Forms, navigation, empty states and controls work on Android. | Pass — emulator walkthrough and release app launch on physical Android phone. |

The phone launch confirms installation and startup. Broad device usability, screen reader support, performance and production security have not been evaluated. Live GPS, external APIs, network sync and authentication are outside prototype scope.
