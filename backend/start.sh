#!/bin/sh
set -eu

# Render Free does not support pre-deploy commands. Run the explicit Alembic
# migration before binding the service, with a short retry for a waking database.
attempt=1
while ! alembic upgrade head; do
  if [ "$attempt" -ge 5 ]; then
    echo "Database migration failed after ${attempt} attempts; refusing to start." >&2
    exit 1
  fi
  echo "Database migration attempt ${attempt} failed; retrying shortly." >&2
  sleep $((attempt * 5))
  attempt=$((attempt + 1))
done

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
