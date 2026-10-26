from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import PublicEarthquake, PublicFemaDeclaration, User
from app.public_data import (
    FEMA_URL, USGS_URL, PublicDataImportError, fetch_fema, fetch_usgs,
    parse_fema_declarations, parse_usgs_geojson, upsert_rows,
)


def test_usgs_geojson_parses_valid_features_deduplicates_and_skips_malformed():
    payload = {"features": [
        {"id": "us123", "properties": {"mag": 4.2, "place": "Near coast", "time": 1700000000000,
                                               "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us123"},
         "geometry": {"type": "Point", "coordinates": [-120.5, 38.2, 7.1]}},
        {"id": "us123", "properties": {"mag": 5.0, "place": "Updated place", "time": 1700000000000,
                                               "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us123"},
         "geometry": {"type": "Point", "coordinates": [-120.5, 38.2, 8.0]}},
        {"id": "bad", "properties": {"mag": None}, "geometry": {"coordinates": [181, 0, 1]}},
        {"id": "missing-geometry", "properties": {}, "geometry": None},
    ]}
    rows = parse_usgs_geojson(payload)
    assert len(rows) == 1
    assert rows[0]["source_id"] == "us123"
    assert rows[0]["magnitude"] == 4.2
    assert rows[0]["longitude"] == -120.5
    assert rows[0]["event_time"] == datetime.fromtimestamp(1700000000, timezone.utc)
    assert rows[0]["attribution"].startswith("Data provided by the USGS")


def test_usgs_rejects_invalid_collection_shape():
    with pytest.raises(PublicDataImportError):
        parse_usgs_geojson({"type": "FeatureCollection", "features": None})


def test_fema_schema_preserves_fields_nulls_and_deduplicates_by_stable_id():
    payload = {"DisasterDeclarationsSummaries": [
        {"id": "fema-1", "disasterNumber": 1234, "femaDeclarationString": "DR-1234-CA",
         "declarationType": "DR", "state": "CA", "designatedArea": "Example County",
         "incidentType": "Fire", "declarationTitle": "Test fire",
         "incidentBeginDate": "2024-08-01T00:00:00.000Z", "incidentEndDate": None,
         "declarationDate": "2024-08-02T00:00:00.000Z"},
        {"id": "fema-1", "disasterNumber": 1234, "declarationType": "DR", "state": "CA",
         "declarationDate": "2024-08-02"},
        {"id": "invalid", "disasterNumber": "not numeric", "declarationType": "DR",
         "state": "CA", "declarationDate": "2024-08-02"},
        {"id": "missing-date", "disasterNumber": 2, "declarationType": "EM", "state": "TX"},
    ]}
    rows = parse_fema_declarations(payload)
    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == "fema-1"
    assert row["declaration_string"] == "DR-1234-CA"
    assert row["incident_end_date"] is None
    assert row["state"] == "CA"
    assert "not endorsed by FEMA" in row["attribution"]


def test_fema_rejects_unexpected_response_shape():
    with pytest.raises(PublicDataImportError):
        parse_fema_declarations({"Other": []})


def test_fema_pagination_is_bounded_and_uses_supported_query_parameters(monkeypatch):
    calls = []
    pages = [[{"id": str(i)} for i in range(2)], [{"id": "2"}]]

    def handler(request):
        calls.append(dict(request.url.params))
        return httpx.Response(200, json={"DisasterDeclarationsSummaries": pages[len(calls) - 1]})

    monkeypatch.setattr("app.public_data.sleep_time.sleep", lambda _delay: None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows = fetch_fema(client, date(2024, 1, 1), date(2024, 12, 31), limit=3, page_size=2)
    assert len(rows) == 3
    assert [call["$skip"] for call in calls] == ["0", "2"]
    assert all(call["$top"] in ("2", "1") and "$filter" in call for call in calls)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client, pytest.raises(ValueError):
        fetch_fema(client, date(2024, 1, 1), date(2024, 1, 2), limit=10002)


def test_usgs_request_is_bounded_and_retries_rate_limit(monkeypatch):
    calls=[]
    def handler(request):
        calls.append(request)
        if len(calls)==1:
            return httpx.Response(429, headers={"Retry-After":"0"})
        return httpx.Response(200,json={"type":"FeatureCollection","features":[]})
    monkeypatch.setattr("app.public_data.sleep_time.sleep",lambda _delay:None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        payload=fetch_usgs(client,date(2025,1,1),date(2025,1,7),5.0,1)
    assert payload["features"]==[]
    assert len(calls)==2
    assert str(calls[-1].url).startswith(USGS_URL)
    assert calls[-1].url.params["limit"]=="2"  # one extra row detects a capped result
    assert calls[-1].url.params["endtime"].endswith("23:59:59")


def test_public_source_http_errors_and_timeouts_fail_closed(monkeypatch):
    monkeypatch.setattr("app.public_data.sleep_time.sleep",lambda _delay:None)
    with httpx.Client(transport=httpx.MockTransport(lambda _request:httpx.Response(503))) as client:
        with pytest.raises(PublicDataImportError,match="HTTP 503"):
            fetch_fema(client,date(2024,1,1),date(2024,1,2),limit=1)
    def timeout(request):
        raise httpx.ReadTimeout("upstream timeout",request=request)
    with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(PublicDataImportError,match="bounded retries"):
            fetch_fema(client,date(2024,1,1),date(2024,1,2),limit=1)
    assert FEMA_URL.endswith("DisasterDeclarationsSummaries")


def test_public_record_upsert_is_repeatable_and_keeps_entities_separate(client):
    earthquake = {
        "source_id": "repeat-usgs", "magnitude": 4.1, "place": "Test location",
        "event_time": datetime(2024, 1, 1, tzinfo=timezone.utc), "longitude": 1.0,
        "latitude": 2.0, "depth_km": 3.0, "event_url": "https://earthquake.usgs.gov/event/repeat-usgs",
        "source_url": "https://earthquake.usgs.gov/fdsnws/event/1/query", "attribution": "USGS",
        "imported_at": datetime.now(timezone.utc),
    }
    with SessionLocal() as db:
        assert upsert_rows(db, PublicEarthquake, [earthquake]) == 1
        db.commit()
        earthquake["magnitude"] = 4.4
        upsert_rows(db, PublicEarthquake, [earthquake])
        db.commit()
        assert db.scalar(select(PublicEarthquake).where(PublicEarthquake.source_id == "repeat-usgs")).magnitude == 4.4
        assert db.scalars(select(PublicFemaDeclaration)).all() == []


def test_public_dataset_api_is_role_authorized_and_separate_from_incidents(client):
    admin = User(email="public-data-admin@example.org", display_name="Public Data Admin",
                 password_hash="not-used", role="super_admin")
    no_reports = User(email="public-data-limited@example.org", display_name="Limited Admin",
                     password_hash="not-used", role="admin", permissions=["view_dashboard"])
    reports_only = User(email="public-data-reports@example.org", display_name="Reports Admin",
                       password_hash="not-used", role="admin", permissions=["view_reports"])
    with SessionLocal() as db:
        db.add_all([admin, no_reports, reports_only])
        db.add(PublicEarthquake(source_id="api-usgs-1", magnitude=4.4, place="Public event",
                                event_time=datetime(2024, 1, 1, tzinfo=timezone.utc), longitude=-120,
                                latitude=35, depth_km=5, event_url="https://earthquake.usgs.gov/event/api-usgs-1",
                                source_url="https://earthquake.usgs.gov/fdsnws/event/1/query",
                                attribution="USGS", imported_at=datetime.now(timezone.utc)))
        db.add(PublicFemaDeclaration(source_id="api-fema-1", disaster_number=4321,
                                     declaration_string="DR-4321-CA", declaration_type="DR", state="CA",
                                     designated_area="Example County", incident_type="Fire", title="Historical fire",
                                     incident_begin_date=None, incident_end_date=None,
                                     declaration_date=datetime(2024, 2, 1, tzinfo=timezone.utc),
                                     source_url="https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries",
                                     attribution="FEMA OpenFEMA", imported_at=datetime.now(timezone.utc)))
        db.commit()
    # Issue test tokens with the app's JWT helper and seed its revocation/session rows.
    from app.security import encode_access_token
    from app.models import AuthSession
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        for user in (admin, no_reports, reports_only):
            db.add(AuthSession(jti=f"test-{user.id}", user_id=user.id,
                               expires_at=now + timedelta(days=1)))
        db.commit()
    admin_token = encode_access_token(admin, f"test-{admin.id}", now, now + timedelta(hours=1))
    limited_token = encode_access_token(no_reports, f"test-{no_reports.id}", now, now + timedelta(hours=1))
    reports_token = encode_access_token(reports_only, f"test-{reports_only.id}", now, now + timedelta(hours=1))
    response = client.get("/api/v1/admin/public-disaster-data", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert response.json()["label"] == "Historical/Public Disaster Data"
    assert response.json()["earthquakes"]["count"] == 1
    assert response.json()["fema"]["count"] == 1
    assert response.json()["earthquakes"]["records"][0]["id"] == "api-usgs-1"
    assert response.json()["fema"]["records"][0]["declaration_string"] == "DR-4321-CA"
    assert client.get("/api/v1/incidents", headers={"Authorization": f"Bearer {admin_token}"}).json() == []
    empty_range = client.get("/api/v1/admin/public-disaster-data?start_date=2020-01-01&end_date=2020-12-31", headers={"Authorization": f"Bearer {admin_token}"})
    assert empty_range.status_code == 200
    assert empty_range.json()["earthquakes"]["count"] == 0
    assert client.get("/api/v1/admin/public-disaster-data?start_date=1900-01-01&end_date=2024-01-01", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 422
    assert client.get("/api/v1/admin/public-disaster-data", headers={"Authorization": f"Bearer {limited_token}"}).status_code == 403
    assert client.get("/api/v1/admin/public-disaster-data", headers={"Authorization": f"Bearer {reports_token}"}).status_code == 200
    assert client.get("/api/v1/admin/public-disaster-data").status_code == 401
