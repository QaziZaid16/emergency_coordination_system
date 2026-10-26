# Public historical disaster datasets

The React admin dashboard has a **Historical/Public Data** view backed by two read-only historical tables. These records are deliberately separate from operational `incidents`, responders, resources, assignments, notifications, and dispatch decisions.

## Sources and attribution

- **USGS Earthquake Catalog:** [FDSN Event Web Service](https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson), requested as bounded GeoJSON. Stored values include USGS event ID, magnitude, place, original event time, longitude, latitude, depth, and event URL. Display attribution: data provided by the USGS Earthquake Hazards Program. USGS recommends GeoJSON feeds for real-time display; this implementation uses bounded catalog queries for historical selection and is not an alert feed.
- **FEMA OpenFEMA Disaster Declarations Summaries v2:** [API endpoint](https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries) and [dataset documentation](https://www.fema.gov/openfema-data-page/disaster-declarations-summaries-v2). Each stored row is one designated area within a declaration, so a disaster number may appear in several counties or tribal areas. Stored values include FEMA record ID, disaster number and declaration string/type, state, designated area, incident type/title, incident/declaration dates, source URL, attribution, and local import time. Display attribution states that this source is OpenFEMA data and the product is not endorsed by FEMA.

The sources have different geographic coverage: USGS is global earthquake data; FEMA covers U.S. declarations and designated areas. Neither source represents comprehensive current emergency activity.

## Storage and API

Alembic revision `efc190e2d7a4` adds `public_earthquakes`, `public_fema_declarations`, and `public_dataset_syncs`. Revision `f4a2d610c981` adds source keys, import-file provenance, FEMA close dates and assistance flags, and earthquake event measures/location fields to those same tables; it does not create a second copy of the historical data schema. Upstream IDs are primary keys; repeated syncs update the same row. Uploaded rows use stable source-appropriate identities and repeat uploads skip unchanged rows. Sync state records the date window, last attempt/success, row count, source filename, geographic scope, and provenance.

The authenticated `GET /api/v1/admin/public-disaster-data` route requires an administrator and `view_reports` for scoped administrators. The default date range starts at the earliest stored historical record; explicit ranges can span up to 100 years. It returns source-separated metadata and records, capped at 50,000 rows per dataset. It does not join or create operational incident records.

## Owner-provided CSV upload

The React Historical/Public Data page allows only a Super Admin to upload both provided files through `POST /api/v1/admin/public-disaster-data/import`. The endpoint parses them server-side and commits both datasets in one transaction. It accepts the expected root-level `database.csv` in the declarations ZIP and `earthquake_1995-2023.csv`; per-file size is capped at 12 MB, the expanded ZIP CSV at 16 MB, and row counts at 50,000 FEMA rows / 5,000 earthquake rows. The archive must contain exactly one root-level CSV member. It rejects unexpected headers, unsafe archive layouts, malformed CSV, invalid dates, out-of-range numbers/coordinates, and invalid program flags. Valid rows are retained when individual rows are invalid, with rejected counts returned; a structural/file validation error writes nothing.

The declaration table retains one row per declaration/state/county area, plus declaration type/date, start/end/close dates, disaster type/title, and all four assistance flags. In the uploaded file, declaration numbers repeat across area rows; the import reports unique numbers separately from area-row count. The earthquake table retains the uploaded title, magnitude/time/coordinates, and available CDI/MMI, alert, tsunami flag, significance, network, station count, minimum distance, gap, magnitude type, depth, location, continent, and country. Missing nullable source fields remain null. Re-imports use stable IDs to update changed rows and skip unchanged rows.

These attachments are labeled **user-provided**. Their provider and authenticity are not independently verified by this application. The upload metadata records the original filenames, file-derived geographic scope, range, row counts, and import time. Uploaded earthquake rows have no fabricated USGS event URL; uploaded FEMA rows do not link to an official source. They are kept in the existing historical/public tables and are never converted into `incidents`, assignments, responders, notifications, or dispatch activity. User-provided U.S. historical declarations must not be described as current Indian emergency activity.

## Explicit bounded synchronization

The importer runs only when an operator calls it; application startup does not fetch external data. From `backend/`, use:

```sh
python -m app.sync_public_datasets --confirm-public-sync
```

Defaults select 2020-01-01 through the current date, USGS magnitude 3.0+, at most 2,500 USGS events (one extra fetched to detect truncation), and at most 5,000 FEMA designated-area rows with pages of up to 1,000. Requests have 15-second timeouts and up to three attempts for timeouts, rate limits, and upstream server errors. The command validates fields, ignores malformed rows, deduplicates within responses, upserts on the upstream ID, preserves the previous successful import if fetching fails, and exits nonzero if either source fails. It stores a failed-attempt status without printing upstream response bodies.

Operators can change the date range and caps, for example:

```sh
python -m app.sync_public_datasets \
  --start-date 2022-01-01 --end-date 2026-10-26 \
  --usgs-min-magnitude 4.0 --usgs-limit 1000 --fema-limit 3000 \
  --confirm-public-sync
```

The command uses the backend's configured `DATABASE_URL`; no dataset-specific credentials or frontend secrets are required. It refuses production execution unless `--allow-production-sync` is supplied. That switch is a safeguard, not authorization; this repository task does not authorize a hosted import or migration. Apply the Alembic migration before running against a deployed service.

## Coverage and refresh

No automatic schedule is configured. Run the bounded command deliberately (for example, during a staging refresh), then inspect the dashboard's last-sync, imported-window, stale, and cap indicators. Each run updates returned source records but does not delete local historical rows. Re-importing the same window is idempotent. The dashboard filters the records present in storage; it does not call the providers on page render.

Result limits mean a remotely synchronized window can be incomplete. Reaching a configured cap is recorded and displayed; absence of a row does not prove an event/declaration did not occur. FEMA summaries can be revised upstream and are grouped by designated area; historical county coverage differs over time. USGS catalogs can also be revised. These datasets must not be used to dispatch responders or presented as comprehensive emergency feeds.

## Synthetic operational demo data

The existing [`backend/app/seed_demo.py`](../../backend/app/seed_demo.py) is the repeatable development-only seed for synthetic users, responders, resources, and `DEMO-*` operational incidents. It requires `ENVIRONMENT=development`, a SQLite database, and `--confirm-demo-seed`; it is not run during startup. The operational dashboard labels detected `DEMO-*` records as synthetic. Public USGS/FEMA records never enter this seed or the operational incident tables.

## Verification record

Automated parser, retry, pagination, upsert, authorization, and separation tests use deterministic fixtures/mocks. Live source access and imports are reported separately in the implementation completion note; passing fixtures alone do not establish that real records were imported.
