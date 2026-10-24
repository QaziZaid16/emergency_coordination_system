#!/bin/sh
set -eu

: "${API_BASE_URL:?Set API_BASE_URL to the real production HTTPS API origin}"
: "${ANDROID_KEYSTORE_PATH:?Set the path to the protected Android release keystore}"
: "${ANDROID_KEYSTORE_PASSWORD:?Set the Android release keystore password}"
: "${ANDROID_KEY_ALIAS:?Set the Android release key alias}"
: "${ANDROID_KEY_PASSWORD:?Set the Android release key password}"

if [ ! -f "$ANDROID_KEYSTORE_PATH" ]; then
  echo "ANDROID_KEYSTORE_PATH does not point to a file." >&2
  exit 1
fi

node - "$API_BASE_URL" <<'NODE'
const raw = process.argv[2];
let url;
try {
  url = new URL(raw);
} catch {
  throw new Error('API_BASE_URL must be an absolute HTTPS URL.');
}
const hostname = url.hostname.toLowerCase();
const labels = hostname.split('.');
if (
  url.protocol !== 'https:' ||
  !hostname ||
  url.username ||
  url.password ||
  url.search ||
  url.hash ||
  labels.includes('your-api-host') ||
  labels.includes('example') ||
  ['test', 'invalid', 'localhost'].includes(labels.at(-1))
) {
  throw new Error('API_BASE_URL must be a real HTTPS origin, not a placeholder.');
}
NODE

exec flutter build apk --release --dart-define="API_BASE_URL=$API_BASE_URL" "$@"
