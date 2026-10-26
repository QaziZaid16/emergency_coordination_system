"""Strict parsers and idempotent persistence for owner-provided historical CSVs."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import io
import math
from pathlib import PurePosixPath
import re
from typing import Any
import zipfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PublicDatasetSync, PublicEarthquake, PublicFemaDeclaration, now_utc

FEMA_KEY = "uploaded_fema_declarations"
EARTHQUAKE_KEY = "uploaded_earthquakes"
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_CSV_BYTES = 16 * 1024 * 1024
MAX_FEMA_ROWS = 50_000
MAX_EARTHQUAKE_ROWS = 5_000
USER_ATTRIBUTION = "User-provided dataset; origin not independently verified."

FEMA_COLUMNS = (
    "Declaration Number", "Declaration Type", "Declaration Date", "State", "County",
    "Disaster Type", "Disaster Title", "Start Date", "End Date", "Close Date",
    "Individual Assistance Program", "Individuals & Households Program",
    "Public Assistance Program", "Hazard Mitigation Program",
)
EARTHQUAKE_COLUMNS = (
    "title", "magnitude", "date_time", "cdi", "mmi", "alert", "tsunami", "sig",
    "net", "nst", "dmin", "gap", "magType", "depth", "latitude", "longitude",
    "location", "continent", "country",
)


class UploadedDatasetError(ValueError):
    """An uploaded file is unsafe or does not match its expected dataset schema."""


def _safe_filename(value: str) -> str:
    name = PurePosixPath(value.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")
    if not name or len(name) > 180:
        raise UploadedDatasetError("The uploaded filename is invalid.")
    return name


def _csv_bytes(content: bytes, filename: str, *, zipped: bool) -> tuple[bytes, str]:
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise UploadedDatasetError("The uploaded file is empty or exceeds the 12 MB limit.")
    name = _safe_filename(filename)
    if zipped:
        if not name.lower().endswith(".zip"):
            raise UploadedDatasetError("The declarations file must be a ZIP containing database.csv.")
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                members = [info for info in archive.infolist() if not info.is_dir()]
                if len(members) != 1 or members[0].filename != "database.csv":
                    raise UploadedDatasetError("The ZIP must contain only a root-level database.csv file.")
                info = members[0]
                if info.file_size > MAX_CSV_BYTES or info.file_size > max(1, info.compress_size) * 250:
                    raise UploadedDatasetError("The declarations CSV exceeds the safe expanded-size limit.")
                with archive.open(info) as member:
                    body = member.read(MAX_CSV_BYTES + 1)
                if len(body) > MAX_CSV_BYTES:
                    raise UploadedDatasetError("The declarations CSV exceeds the 16 MB limit.")
        except (zipfile.BadZipFile, OSError, RuntimeError, EOFError) as exc:
            raise UploadedDatasetError("The declarations ZIP is invalid.") from exc
        return body, f"{name}!/database.csv"
    if name.lower() != "earthquake_1995-2023.csv":
        raise UploadedDatasetError("The earthquake file must be earthquake_1995-2023.csv.")
    if len(content) > MAX_CSV_BYTES:
        raise UploadedDatasetError("The earthquake CSV exceeds the 16 MB limit.")
    return content, name


def _read_rows(content: bytes, required_columns: tuple[str, ...], row_limit: int) -> tuple[list[dict[str, str]], int]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UploadedDatasetError("CSV files must use UTF-8 text encoding.") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    if reader.fieldnames is None or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise UploadedDatasetError("The CSV header is missing or contains duplicate columns.")
    if tuple(reader.fieldnames) != required_columns:
        raise UploadedDatasetError("The CSV columns do not match the expected attached dataset schema.")
    rows: list[dict[str, str]] = []
    try:
        for row in reader:
            if len(rows) >= row_limit:
                raise UploadedDatasetError("The CSV exceeds the configured row limit.")
            # DictReader uses None for an over-wide row; reject rather than silently shifting fields.
            if None in row or any(value is None for value in row.values()):
                rows.append({"__invalid_row__": "wrong number of columns"})
            else:
                rows.append({key: (value or "").strip() for key, value in row.items()})
    except csv.Error as exc:
        raise UploadedDatasetError("The CSV contains malformed quoting or row structure.") from exc
    return rows, len(rows)


def _date(value: str) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%m/%d/%Y").replace(tzinfo=timezone.utc)


def _number(value: str, *, integer: bool = False) -> int | float | None:
    if not value:
        return None
    number = float(value)
    if not math.isfinite(number) or (integer and not number.is_integer()):
        raise ValueError("not a finite valid number")
    return int(number) if integer else number


def _flag(value: str) -> bool | None:
    if value.casefold() == "yes":
        return True
    if value.casefold() == "no":
        return False
    if not value:
        return None
    raise ValueError("expected Yes, No, or empty")


def parse_uploaded_fema(content: bytes, filename: str) -> dict[str, Any]:
    csv_content, source_filename = _csv_bytes(content, filename, zipped=True)
    raw_rows, total = _read_rows(csv_content, FEMA_COLUMNS, MAX_FEMA_ROWS)
    imported_at = now_utc()
    accepted: dict[str, dict[str, Any]] = {}
    rejected: dict[str, int] = {}
    for raw in raw_rows:
        try:
            if "__invalid_row__" in raw:
                raise ValueError("wrong number of columns")
            declaration = raw["Declaration Number"]
            number_match = re.search(r"(\d+)$", declaration)
            state = raw["State"].strip()
            if not number_match or not state:
                raise ValueError("missing declaration number or state")
            declared = _date(raw["Declaration Date"])
            if declared is None:
                raise ValueError("missing declaration date")
            start_date, end_date, close_date = (_date(raw[key]) for key in ("Start Date", "End Date", "Close Date"))
            flags = {
                "individual_assistance": _flag(raw["Individual Assistance Program"]),
                "individuals_households_program": _flag(raw["Individuals & Households Program"]),
                "public_assistance": _flag(raw["Public Assistance Program"]),
                "hazard_mitigation": _flag(raw["Hazard Mitigation Program"]),
            }
            identity = "\x1f".join((declaration, state, raw["County"]))
            source_id = "upload-fema-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:48]
            row = {
                "source_id": source_id, "source_key": FEMA_KEY,
                "disaster_number": int(number_match.group(1)),
                "declaration_string": declaration[:32], "declaration_type": raw["Declaration Type"][:32] or "Unspecified",
                "state": state[:80], "designated_area": raw["County"] or None,
                "incident_type": raw["Disaster Type"][:120] or None,
                "title": raw["Disaster Title"][:500] or None,
                "incident_begin_date": start_date, "incident_end_date": end_date,
                "declaration_date": declared, "close_date": close_date, **flags,
                "source_url": f"uploaded://{source_filename}", "attribution": USER_ATTRIBUTION,
                "imported_at": imported_at,
            }
            accepted[source_id] = row
        except (KeyError, ValueError, OverflowError):
            reason = "invalid date, declaration fields, or assistance flag"
            rejected[reason] = rejected.get(reason, 0) + 1
    return {"source": FEMA_KEY, "dataset_name": "User-provided FEMA-style disaster declarations",
            "source_filename": source_filename, "geographic_scope": "United States (as represented in uploaded file)",
            "range_start": min((r["declaration_date"] for r in accepted.values()), default=None),
            "range_end": max((r["declaration_date"] for r in accepted.values()), default=None),
            "total_rows": total, "rows": list(accepted.values()), "rejected": rejected,
            "duplicate_rows": total - len(accepted) - sum(rejected.values()),
            "unique_declarations": len({row["disaster_number"] for row in accepted.values()})}


def parse_uploaded_earthquakes(content: bytes, filename: str) -> dict[str, Any]:
    csv_content, source_filename = _csv_bytes(content, filename, zipped=False)
    raw_rows, total = _read_rows(csv_content, EARTHQUAKE_COLUMNS, MAX_EARTHQUAKE_ROWS)
    imported_at = now_utc()
    accepted: dict[str, dict[str, Any]] = {}
    rejected: dict[str, int] = {}
    for raw in raw_rows:
        try:
            if "__invalid_row__" in raw:
                raise ValueError("wrong number of columns")
            event_time = datetime.strptime(raw["date_time"], "%d-%m-%Y %H:%M").replace(tzinfo=timezone.utc)
            magnitude = _number(raw["magnitude"])
            latitude, longitude = _number(raw["latitude"]), _number(raw["longitude"])
            if (not raw["title"] or magnitude is None or latitude is None or longitude is None
                    or not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
                raise ValueError("missing title, magnitude, or valid coordinates")
            if not -2 <= magnitude <= 10:
                raise ValueError("magnitude outside valid range")
            tsunami_value = _number(raw["tsunami"], integer=True)
            if tsunami_value not in (0, 1):
                raise ValueError("invalid tsunami flag")
            network = raw["net"]
            identity = "\x1f".join((network, raw["date_time"], raw["latitude"], raw["longitude"]))
            source_id = "upload-eq-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:48]
            row = {
                "source_id": source_id, "source_key": EARTHQUAKE_KEY,
                "magnitude": magnitude, "place": raw["location"][:500] or raw["title"][:500],
                "title": raw["title"][:500],
                "event_time": event_time, "longitude": longitude, "latitude": latitude,
                "depth_km": _number(raw["depth"]), "event_url": None,
                "source_url": f"uploaded://{source_filename}", "attribution": USER_ATTRIBUTION,
                "imported_at": imported_at,
                "cdi": _number(raw["cdi"]), "mmi": _number(raw["mmi"]),
                "alert": raw["alert"][:24] or None, "tsunami": bool(tsunami_value),
                "significance": _number(raw["sig"], integer=True), "network": network[:32] or None,
                "station_count": _number(raw["nst"], integer=True),
                "minimum_distance": _number(raw["dmin"]), "azimuthal_gap": _number(raw["gap"]),
                "magnitude_type": raw["magType"][:32] or None,
                "location": raw["location"][:500] or None,
                "continent": raw["continent"][:120] or None, "country": raw["country"][:120] or None,
            }
            if row["depth_km"] is not None and not -100 <= row["depth_km"] <= 1000:
                raise ValueError("depth outside valid range")
            accepted[source_id] = row
        except (KeyError, ValueError, OverflowError):
            reason = "invalid date, number, magnitude, or coordinate"
            rejected[reason] = rejected.get(reason, 0) + 1
    return {"source": EARTHQUAKE_KEY, "dataset_name": "User-provided earthquake records",
            "source_filename": source_filename, "geographic_scope": "Global (as represented in uploaded file)",
            "range_start": min((r["event_time"] for r in accepted.values()), default=None),
            "range_end": max((r["event_time"] for r in accepted.values()), default=None),
            "total_rows": total, "rows": list(accepted.values()), "rejected": rejected,
            "duplicate_rows": total - len(accepted) - sum(rejected.values()),
            "unique_declarations": None}


def _existing_ids(db: Session, model: type, ids: list[str]) -> dict[str, Any]:
    existing: dict[str, Any] = {}
    for offset in range(0, len(ids), 500):
        chunk = ids[offset:offset + 500]
        for item in db.scalars(select(model).where(model.source_id.in_(chunk))).all():
            existing[item.source_id] = item
    return existing


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, datetime) and isinstance(right, datetime):
        if left.tzinfo is None:
            left = left.replace(tzinfo=timezone.utc)
        if right.tzinfo is None:
            right = right.replace(tzinfo=timezone.utc)
        return left.astimezone(timezone.utc) == right.astimezone(timezone.utc)
    return left == right


def persist_uploaded_dataset(db: Session, parsed: dict[str, Any]) -> dict[str, int]:
    model = PublicEarthquake if parsed["source"] == EARTHQUAKE_KEY else PublicFemaDeclaration
    rows = parsed["rows"]
    existing = _existing_ids(db, model, [row["source_id"] for row in rows])
    inserted = updated = skipped = 0
    for row in rows:
        current = existing.get(row["source_id"])
        if current is None:
            db.add(model(**row))
            inserted += 1
            continue
        changed = False
        for key, value in row.items():
            if key in {"source_id", "imported_at"}:
                continue
            if not _same_value(getattr(current, key), value):
                setattr(current, key, value)
                changed = True
        if changed:
            current.imported_at = row["imported_at"]
            updated += 1
        else:
            skipped += 1

    sync = db.get(PublicDatasetSync, parsed["source"])
    if sync is None:
        sync = PublicDatasetSync(source=parsed["source"])
        db.add(sync)
    timestamp = now_utc()
    sync.dataset_name = parsed["dataset_name"]
    sync.source_filename = parsed["source_filename"]
    sync.provenance = "Uploaded by an authorized Super Admin; provider and authenticity not independently verified."
    sync.geographic_scope = parsed["geographic_scope"]
    sync.last_attempt_at = timestamp
    sync.last_success_at = timestamp
    sync.range_start = parsed["range_start"]
    sync.range_end = parsed["range_end"]
    sync.imported_count = len(rows)
    sync.was_limited = False
    sync.last_error = None
    db.flush()
    return {"inserted": inserted, "updated": updated, "skipped": skipped,
            "rejected": sum(parsed["rejected"].values()), "duplicate_rows": parsed["duplicate_rows"],
            "rejected_reasons": parsed["rejected"], "total_rows": parsed["total_rows"],
            "unique_declarations": parsed["unique_declarations"],
            "range_start": parsed["range_start"], "range_end": parsed["range_end"],
            "last_success_at": timestamp}
