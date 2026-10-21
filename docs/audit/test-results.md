# Verification record

## Baseline

- Flutter Android/Web scaffold generated and dependencies resolved successfully in the clean target project.
- Text extracted from 18 PPT slides and 16 Synopsis pages; PPT visuals reviewed.
- Static analysis completed with `No issues found`.
- Targeted test suite completed: `flutter test` — 7 tests passed. Tests run from the APFS staging copy because the exFAT source volume contains macOS `._*` AppleDouble files.
- Release APK built successfully from `/private/tmp/ecs_android_build` using Flutter 3.47.7 / Dart 3.13.5; handoff copy is `release/emergency-coordination-system-demo.apk` (SHA-256 `235657e11b6e84ed4b377ac803fda0097cca2552c7be074bf13632275744040e`).
- Custom adaptive, legacy, and themed launcher resources compile; rebuilt APK installed and launched on physical Android device `CPH2691` (ADB serial `a102172d`); process confirmed running. This is a local demonstration build signed with the generated debug key.

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
| T-009 | UI-001 | Forms, navigation, empty states and controls work on Android. | Pass — release UI walkthrough on physical CPH2691, including Overview, incident search/list, detail lifecycle, creation, responders, resources and reports; rebuilt APK relaunched successfully. |

The phone launch confirms installation and startup. Broad device usability, screen reader support, performance and production security have not been evaluated. Live GPS, external APIs, network sync and authentication are outside prototype scope.
