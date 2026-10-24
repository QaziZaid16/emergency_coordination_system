# CI/CD audit

**Status before this execution:** no repository GitHub Actions workflow existed.

Added `.github/workflows/quality.yml` for pull requests and pushes to `main`. It grants only `contents: read` and runs:

- Backend dependency install and `pytest` against test-mode SQLite.
- Flutter dependency resolution, format check, analyzer, and the explicit tracked test file list.
- `node --check` for the administrative dashboard JavaScript.

No deployment, release signing, secrets, or artifact upload is configured. The workflow has not yet run remotely; branch protection and required-check settings need GitHub repository administrator access. The currently available local full Flutter test discovery is affected by AppleDouble sidecar files, so the workflow names the tracked Dart tests explicitly.
