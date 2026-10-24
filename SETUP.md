# Setup and handover

This is a development implementation with an Android Flutter client and FastAPI backend. Shared portals work only after configuring and running the backend. The local Training Workspace remains separate and appears only in an explicitly enabled debug build.

## Android client

1. Install Flutter 3.47.7/Dart 3.13.5 (or a compatible later stable SDK), Android Studio/Android SDK, and Platform Tools.
2. On the phone, enable USB debugging and approve this computer. Confirm `flutter devices` lists the phone.
3. Run `flutter pub get` and `flutter run -d <device-id>`; first launch shows onboarding, then the direct login screen.

To use the authenticated portals with a backend running on this development computer, first start the backend below, then:

```sh
adb reverse tcp:8000 tcp:8000
flutter run -d <device-id> --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Android debug builds permit loopback HTTP for this local-only setup. Release builds disallow cleartext and require a real HTTPS host:

```sh
# Set API_BASE_URL to the actual deployed HTTPS origin first.
sh scripts/build_android_release.sh
```

No production API URL is configured in this repository. If `API_BASE_URL` is empty or invalid, the direct login remains visible and gives a brief sign-in unavailable message after a sign-in attempt. The developer-only simulator can be included in a debug build with `--dart-define=ENABLE_TRAINING_WORKSPACE=true`.

## Local API with SQLite

Requirements: Python 3.12+. See [backend/README.md](backend/README.md) for PostgreSQL/Compose setup and API details.

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Set a fresh `JWT_SECRET` of at least 32 characters in `.env`. Keep `ENVIRONMENT=development` and the example SQLite URL. Apply the schema and provision the first administrator; the password is entered through a hidden terminal prompt, with no default credential:

```sh
alembic upgrade head
python -m app.provision_admin --email admin@example.org --display-name 'Operations Admin'
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for the development API reference. Public registration can create user accounts only. An admin creates responder accounts and their service capabilities. Use HTTPS and a secrets manager for any deployment; do not expose this local development server to the public Internet.

## Tests and migration verification

Flutter client:

```sh
flutter analyze
flutter test
```

Backend, from `backend/`:

```sh
python -m pytest -q
```

Backend tests use in-memory SQLite. The initial Alembic migration has been applied against a clean SQLite database. The PostgreSQL Compose file is included but Docker/PostgreSQL were not available for verification in this development environment.

## Build from the Seagate/exFAT checkout

macOS AppleDouble metadata can interfere with Flutter Android builds on the Seagate drive. Use an APFS staging copy and exclude generated caches and the backend virtual environment:

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
API_BASE_URL="${API_BASE_URL:?Set a real HTTPS API_BASE_URL}"
sh scripts/build_android_release.sh
cp build/app/outputs/flutter-apk/app-release.apk \
  "$project_dir/release/emergency-coordination-system-demo.apk"
shasum -a 256 "$project_dir/release/emergency-coordination-system-demo.apk"
```

The generated release is debug-signed for local demonstration. Production distribution requires protected signing, a deployed HTTPS service, and operational/privacy/security review.

## Data boundaries

- The old coordinator/responder training app stores simulated data in Android's private `emergency_workspace.json` file.
- Admin/User/Responder portal data resides only in the configured server database. The backend is authoritative; the client does not import training data.
- Remember Me is unchecked by default. When enabled, a rotating refresh token and short-lived access token are stored in Android secure storage; app startup validates the session with the backend before opening the role-matched portal. The remembered session expires after 30 days by default. Without it, the token is memory-only and app reopen requires sign-in. Logout clears local tokens and asks the server to revoke the session; an offline server can prevent confirmation of remote revocation. Apply Alembic migrations before using Remember Me on an existing database.
- GPS is requested in foreground only. A user may manually enter a location if permission or GPS is unavailable. No live agency dispatch, push notification, map service, or public API host is configured.

## Verification snapshot

Latest results and limitations are recorded in [docs/audit/test-results.md](docs/audit/test-results.md). Automated tests do not replace PostgreSQL concurrency testing, Android denied-permission testing on a range of devices, penetration/accessibility review, backup recovery, or real operational approval.
