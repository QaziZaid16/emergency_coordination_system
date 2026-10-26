"""Explicit operator command for bounded USGS and FEMA historical imports."""

import argparse
from datetime import date

from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database import SessionLocal
from app.models import PublicEarthquake, PublicFemaDeclaration
from app.public_data import (
    FEMA_SOURCE, USGS_SOURCE, PublicDataImportError, create_http_client,
    fetch_fema, fetch_usgs, parse_fema_declarations, parse_usgs_geojson,
    record_sync, upsert_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2020, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--usgs-min-magnitude", type=float, default=3.0)
    parser.add_argument("--usgs-limit", type=int, default=2500)
    parser.add_argument("--fema-limit", type=int, default=5000)
    parser.add_argument("--confirm-public-sync", action="store_true")
    parser.add_argument("--allow-production-sync", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not args.confirm_public_sync:
        raise SystemExit("Pass --confirm-public-sync to fetch and persist public historical records.")
    if settings.environment.casefold() == "production" and not args.allow_production_sync:
        raise SystemExit("Production imports require --allow-production-sync and separate operator authorization.")
    if args.start_date > args.end_date:
        raise SystemExit("--start-date must be on or before --end-date.")

    failures = 0
    with create_http_client() as client, SessionLocal() as db:
        for source, model in ((USGS_SOURCE, PublicEarthquake), (FEMA_SOURCE, PublicFemaDeclaration)):
            try:
                if source == USGS_SOURCE:
                    raw = fetch_usgs(client, args.start_date, args.end_date, args.usgs_min_magnitude, args.usgs_limit)
                    features = raw.get("features", []) if isinstance(raw, dict) else []
                    if not isinstance(features, list):
                        raise PublicDataImportError("USGS response is not a GeoJSON feature collection")
                    was_limited = len(features) > args.usgs_limit
                    if was_limited:
                        raw = {**raw, "features": features[:args.usgs_limit]}
                    rows = parse_usgs_geojson(raw)
                else:
                    raw = fetch_fema(client, args.start_date, args.end_date, args.fema_limit + 1)
                    was_limited = len(raw) > args.fema_limit
                    rows = parse_fema_declarations({"DisasterDeclarationsSummaries": raw[:args.fema_limit]})
                with db.begin_nested():
                    count = upsert_rows(db, model, rows)
                    record_sync(db, source, args.start_date, args.end_date, count, was_limited=was_limited)
                db.commit()
                limited_note = " (result cap reached; selection may be incomplete)" if was_limited else ""
                print(f"{source}: synchronized {count} validated records for {args.start_date} through {args.end_date}{limited_note}.")
            except (PublicDataImportError, ValueError, SQLAlchemyError) as exc:
                db.rollback()
                failures += 1
                with db.begin():
                    record_sync(db, source, args.start_date, args.end_date, 0,
                                error=f"{type(exc).__name__}: public data synchronization failed")
                print(f"{source}: failed; previous imported records remain available.")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
