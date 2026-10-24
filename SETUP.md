# Build from the Seagate/exFAT checkout

This note covers the macOS staging workaround for this checkout. For ordinary setup and commands, see the [root README](README.md).

If AppleDouble `._*` metadata files on the Seagate/exFAT volume interfere with Flutter or Android builds, stage source on a local APFS filesystem and omit generated files:

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
```

For a release build, set `API_BASE_URL` to the real HTTPS API origin and provide a protected release keystore using the required Android signing environment variables before invoking the wrapper. The Android release build is no longer debug-signed:

```sh
API_BASE_URL="${API_BASE_URL:?Set a real HTTPS API_BASE_URL}" \
  sh scripts/build_android_release.sh
```

The resulting APK stays in the staging directory at `build/app/outputs/flutter-apk/app-release.apk`. Inspect and verify it before copying it into the repository; the checked-in demo APK is a separate, older artifact. See [cloud deployment readiness](docs/operations/hosting.md) for signing key setup and the existing installed app's signing migration constraint.
