#!/bin/sh
set -eu

run_migrations() {
  # Retain the existing retry for a waking database. Migration-only mode uses
  # this same path but exits before starting the API process.
  attempt=1
  while ! alembic upgrade head; do
    if [ "$attempt" -ge 5 ]; then
      echo "Database migration failed after ${attempt} attempts; refusing to continue." >&2
      return 1
    fi
    echo "Database migration attempt ${attempt} failed; retrying shortly." >&2
    sleep $((attempt * 5))
    attempt=$((attempt + 1))
  done
}

if [ "$#" -gt 1 ]; then
  echo "Usage: $0 [serve|migrate]" >&2
  exit 2
fi

mode=${1:-serve}
case "$mode" in
  migrate)
    run_migrations
    exit 0
    ;;
  serve)
    run_migrations || exit 1
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
  *)
    echo "Usage: $0 [serve|migrate]" >&2
    exit 2
    ;;
esac
