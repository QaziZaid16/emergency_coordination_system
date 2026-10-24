#!/bin/sh
set -eu

: "${API_BASE_URL:?Set API_BASE_URL to the real production HTTPS API origin}"

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

exec flutter build apk --release --dart-define="API_BASE_URL=$API_BASE_URL"
