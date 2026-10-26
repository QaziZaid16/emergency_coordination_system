"""Bounded, repeatable importers for public historical hazard datasets."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
import math
import random
import time as sleep_time
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PublicDatasetSync, PublicEarthquake, PublicFemaDeclaration, now_utc

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
FEMA_URL = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"
USGS_SOURCE = "usgs_earthquake_catalog"
FEMA_SOURCE = "fema_disaster_declarations"
USGS_ATTRIBUTION = "Data provided by the USGS Earthquake Hazards Program."
FEMA_ATTRIBUTION = "Data from FEMA OpenFEMA. This product is not endorsed by FEMA."


class PublicDataImportError(RuntimeError):
    """The upstream source could not be fetched or parsed safely."""


def utc_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value / 1000, timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(value[:10]), time.min)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def parse_usgs_geojson(payload: Any, imported_at: datetime | None = None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
        raise PublicDataImportError("USGS response is not a GeoJSON feature collection")
    fetched_at = imported_at or now_utc()
    result: dict[str, dict[str, Any]] = {}
    for feature in payload["features"]:
        if not isinstance(feature, dict):
            continue
        properties, geometry = feature.get("properties"), feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            continue
        source_id = feature.get("id")
        coordinates = geometry.get("coordinates")
        if not isinstance(source_id, str) or not source_id.strip() or not isinstance(coordinates, list) or len(coordinates) < 3:
            continue
        if source_id in result:
            continue
        magnitude = _finite_number(properties.get("mag"))
        longitude, latitude, depth = (_finite_number(value) for value in coordinates[:3])
        event_time = utc_datetime(properties.get("time"))
        event_url = properties.get("url")
        if (magnitude is None or event_time is None or longitude is None or latitude is None
                or not -180 <= longitude <= 180 or not -90 <= latitude <= 90
                or (depth is not None and not -100 <= depth <= 1000)
                or not isinstance(event_url, str) or not event_url.startswith("https://")):
            continue
        result[source_id] = {
            "source_id": source_id[:64], "magnitude": magnitude,
            "place": properties.get("place")[:500] if isinstance(properties.get("place"), str) else None,
            "event_time": event_time, "longitude": longitude, "latitude": latitude,
            "depth_km": depth, "event_url": event_url[:1000], "source_url": USGS_URL,
            "attribution": USGS_ATTRIBUTION, "imported_at": fetched_at,
        }
    return list(result.values())


def parse_fema_declarations(payload: Any, imported_at: datetime | None = None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("DisasterDeclarationsSummaries"), list):
        raise PublicDataImportError("FEMA response is missing DisasterDeclarationsSummaries")
    fetched_at = imported_at or now_utc()
    result: dict[str, dict[str, Any]] = {}
    for item in payload["DisasterDeclarationsSummaries"]:
        if not isinstance(item, dict):
            continue
        source_id = item.get("id")
        declaration_date = utc_datetime(item.get("declarationDate"))
        number = item.get("disasterNumber")
        declaration_type, state = item.get("declarationType"), item.get("state")
        if (not isinstance(source_id, str) or not source_id.strip() or len(source_id) > 64
                or isinstance(number, bool) or not isinstance(number, (int, float)) or int(number) != number
                or not isinstance(declaration_type, str) or not declaration_type.strip()
                or not isinstance(state, str) or not state.strip() or declaration_date is None):
            continue
        if source_id in result:
            continue
        optional_text = lambda key, size: item.get(key)[:size] if isinstance(item.get(key), str) else None
        result[source_id] = {
            "source_id": source_id, "disaster_number": int(number),
            "declaration_string": optional_text("femaDeclarationString", 32),
            "declaration_type": declaration_type[:8], "state": state[:80],
            "designated_area": optional_text("designatedArea", 240),
            "incident_type": optional_text("incidentType", 120),
            "title": optional_text("declarationTitle", 500),
            "incident_begin_date": utc_datetime(item.get("incidentBeginDate")),
            "incident_end_date": utc_datetime(item.get("incidentEndDate")),
            "declaration_date": declaration_date, "source_url": FEMA_URL,
            "attribution": FEMA_ATTRIBUTION, "imported_at": fetched_at,
        }
    return list(result.values())


def _get_json(client: httpx.Client, url: str, params: dict[str, Any], attempts: int = 3) -> Any:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = client.get(url, params=params)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt + 1 < attempts:
                    retry_after = response.headers.get("Retry-After", "")
                    try:
                        delay = min(5.0, max(0.0, float(retry_after)))
                    except ValueError:
                        delay = min(2.0, 0.25 * (2**attempt) + random.random() * 0.1)
                    sleep_time.sleep(delay)
                    continue
            if not response.is_success:
                raise PublicDataImportError(f"Public data source returned HTTP {response.status_code}")
            try:
                return response.json()
            except ValueError as exc:
                raise PublicDataImportError("Public data source returned malformed JSON") from exc
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                sleep_time.sleep(min(2.0, 0.25 * (2**attempt) + random.random() * 0.1))
                continue
        except PublicDataImportError:
            raise
    raise PublicDataImportError("Public data source request failed after bounded retries") from last_error


def fetch_usgs(client: httpx.Client, start: date, end: date, min_magnitude: float, limit: int) -> Any:
    if start > end or not -1 <= min_magnitude <= 10 or not 1 <= limit <= 5000:
        raise ValueError("Invalid or unbounded USGS import parameters")
    return _get_json(client, USGS_URL, {
        "format": "geojson", "starttime": f"{start.isoformat()}T00:00:00",
        "endtime": f"{end.isoformat()}T23:59:59",
        "minmagnitude": min_magnitude, "limit": limit + 1, "orderby": "time",
    })


def fetch_fema(client: httpx.Client, start: date, end: date, limit: int, page_size: int = 1000) -> list[Any]:
    if start > end or not 1 <= limit <= 10001 or not 1 <= page_size <= 1000:
        raise ValueError("Invalid or unbounded FEMA import parameters")
    filter_text = f"declarationDate ge '{start.isoformat()}T00:00:00.000z' and declarationDate le '{end.isoformat()}T23:59:59.999z'"
    records: list[Any] = []
    while len(records) < limit:
        top = min(page_size, limit - len(records))
        payload = _get_json(client, FEMA_URL, {
            "$filter": filter_text, "$orderby": "declarationDate,id", "$top": top, "$skip": len(records),
        })
        if not isinstance(payload, dict) or not isinstance(payload.get("DisasterDeclarationsSummaries"), list):
            raise PublicDataImportError("FEMA response is missing DisasterDeclarationsSummaries")
        page = payload["DisasterDeclarationsSummaries"]
        if len(page) > top:
            raise PublicDataImportError("FEMA returned more records than the requested page size")
        records.extend(page)
        if len(page) < top:
            break
    return records


def upsert_rows(db: Session, model: type, rows: list[dict[str, Any]]) -> int:
    """Idempotently insert/update source-keyed data and return unique rows seen."""
    for row in rows:
        existing = db.get(model, row["source_id"])
        if existing is None:
            db.add(model(**row))
        else:
            for key, value in row.items():
                if key != "source_id":
                    setattr(existing, key, value)
    db.flush()
    return len(rows)


def record_sync(db: Session, source: str, start: date, end: date, count: int,
                *, error: str | None = None, was_limited: bool = False,
                timestamp: datetime | None = None) -> None:
    state = db.get(PublicDatasetSync, source)
    if state is None:
        state = PublicDatasetSync(source=source, imported_count=0)
        db.add(state)
    state.last_attempt_at = timestamp or now_utc()
    state.last_error = error[:240] if error else None
    if error is None:
        state.last_success_at = state.last_attempt_at
        state.range_start = datetime.combine(start, time.min, timezone.utc)
        state.range_end = datetime.combine(end, time.max, timezone.utc)
        state.imported_count = count
        state.was_limited = was_limited


def create_http_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=False,
                        headers={"User-Agent": "EmergencyCoordinationHistoricalData/1.0"})
