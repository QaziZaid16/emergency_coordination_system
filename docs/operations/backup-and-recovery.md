# Database backup and recovery runbook

## Scope and current status

The shared API database is PostgreSQL in the supplied Compose development setup (`postgres:17-alpine`) and SQLite in local tests/development. Compose stores PostgreSQL data in the named `coordination-data` volume. This repository does not configure a production database, backup destination, encryption key, retention schedule, or automated backup job. No backup or restore was performed during this audit because PostgreSQL client tools and a disposable PostgreSQL server are unavailable.

Incident records may contain precise or manually entered location information and other sensitive data. Store dumps only in an approved encrypted destination with access limited to the database operators. Do not put dumps in the repository, a shared workstation folder, or an unapproved cloud drive. A logical dump is not encrypted by `pg_dump` itself.

## Provision credentials without putting passwords in commands

On the approved backup host, configure a PostgreSQL service entry in a user-owned `pg_service.conf` and a matching `.pgpass` file. Keep the service entry free of a plaintext password; set `.pgpass` to mode `0600`. Set `PGSERVICEFILE` and `PGPASSFILE` to those files and select the service using `PGSERVICE`. Do not put a password in a connection URL passed as a command argument.

For a restore drill, use a separate service entry pointing to a newly created disposable database. Confirm the database name and host before any restore command. Never point a drill at production.

## Create and verify a logical backup

Run with `PGSERVICE` set to the intended database service and `BACKUP_DIR` set to an approved encrypted, access-controlled destination with sufficient free space:

```sh
set -eu
umask 077
: "${PGSERVICE:?Select the PostgreSQL service name}"
: "${PGSERVICEFILE:?Set the protected pg_service.conf path}"
: "${PGPASSFILE:?Set the protected .pgpass path}"
: "${BACKUP_DIR:?Set an approved encrypted backup directory}"
test -d "$BACKUP_DIR"
test -w "$BACKUP_DIR"
backup_file="$BACKUP_DIR/ecs-$(date -u +%Y%m%dT%H%M%SZ).dump"
test ! -e "$backup_file"
temporary_file=$(mktemp "$BACKUP_DIR/.ecs-dump.XXXXXX")
trap 'rm -f "$temporary_file"' EXIT HUP INT TERM
pg_dump --format=custom --no-owner --no-acl --dbname="service=$PGSERVICE" --file="$temporary_file"
test -s "$temporary_file"
pg_restore --list "$temporary_file" >/dev/null
ln "$temporary_file" "$backup_file"
rm "$temporary_file"
trap - EXIT HUP INT TERM
shasum -a 256 "$backup_file"
```

The command refuses to replace an existing timestamped backup. Record the printed digest and backup time in the operator's approved backup inventory. Copy or replicate the verified dump only through the approved encrypted storage mechanism. Monitor command exit status and free space; an absent or failed dump is an alert, not a successful backup.

## Restore drill

Restore only into a newly created, disposable database with an explicitly selected restore service. Keep the known-good dump unchanged.

```sh
set -eu
: "${PGSERVICE:?Select the disposable restore database service}"
: "${PGSERVICEFILE:?Set the protected pg_service.conf path}"
: "${PGPASSFILE:?Set the protected .pgpass path}"
: "${BACKUP_FILE:?Select a verified backup file}"
test -s "$BACKUP_FILE"
pg_restore --list "$BACKUP_FILE" >/dev/null
pg_restore --exit-on-error --no-owner --no-acl --dbname="service=$PGSERVICE" "$BACKUP_FILE"
psql "service=$PGSERVICE" -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version'
psql "service=$PGSERVICE" -v ON_ERROR_STOP=1 -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
```

After schema checks, point a test API process only at the disposable restore service and verify representative incident, assignment, user, and audit reads. Confirm expected row counts against a pre-backup inventory where one exists. Record restore duration and the checks performed. If restore fails, preserve the dump and failed database for diagnosis; create another disposable database for a retry instead of cleaning up automatically.

## Recovery procedure

1. **Contain and assess:** stop writes to the affected instance if safe, preserve logs, identify the incident time window, and notify the responsible operator. Do not run an improvised restore over the only live database.
2. **Select recovery point:** identify the latest verified dump and any provider-supported point-in-time recovery. Confirm its digest and the intended target database.
3. **Restore in isolation:** restore to a new database or a provider-managed recovery instance using the steps above.
4. **Validate:** inspect migration head, critical table counts, foreign-key integrity, and representative application workflows. Review sensitive location data access.
5. **Cut over only after approval:** switching the deployed API to a recovered database changes production service state and requires the system owner's explicit authorization. Preserve the previous database until recovery is accepted.
6. **Review:** record data loss window, recovery duration, cause, and follow-up controls.

## Targets and gaps

There are no owner-approved Recovery Point Objective (RPO) or Recovery Time Objective (RTO) values. For discussion only, a **provisional development-platform target** could be RPO ≤24 hours and RTO ≤8 hours, supported by a daily verified backup and an exercised restore procedure. These are proposals requiring service-owner approval, are not measured, and must not be adopted for an operational emergency-response service without a separate risk review and materially appropriate service objectives. The service owner must approve RPO/RTO, backup frequency, retention, encryption/key custody, off-site isolation, monitoring, and restore-test cadence before operational use. Point-in-time recovery, file/object backups, and production cutover are not configured here.
