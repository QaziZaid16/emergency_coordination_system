from datetime import datetime, timedelta, timezone
import io
import zipfile

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Assignment, AuthSession, Incident, PublicEarthquake, PublicFemaDeclaration, User
from app.security import encode_access_token


FEMA_HEADER = (
    "Declaration Number,Declaration Type,Declaration Date,State,County,Disaster Type,Disaster Title,"
    "Start Date,End Date,Close Date,Individual Assistance Program,Individuals & Households Program,"
    "Public Assistance Program,Hazard Mitigation Program\n"
)
EQ_HEADER = (
    "title,magnitude,date_time,cdi,mmi,alert,tsunami,sig,net,nst,dmin,gap,magType,depth,latitude,"
    "longitude,location,continent,country\n"
)


def zipped_fema(rows: str = "") -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("database.csv", (FEMA_HEADER + rows).encode())
    return stream.getvalue()


def earthquake_csv(rows: str = "") -> bytes:
    return (EQ_HEADER + rows).encode()


def test_uploaded_fema_parser_rejects_blank_required_declaration_date():
    from app.uploaded_public_data import parse_uploaded_fema

    parsed = parse_uploaded_fema(zipped_fema(
        "DR-1,Disaster,,GA,Example County,Tornado,Tornado,,,,Yes,No,Yes,No\n"
    ), "database.csv.zip")

    assert parsed["total_rows"] == 1
    assert parsed["rows"] == []
    assert parsed["rejected"] == {
        "invalid date, declaration fields, or assistance flag": 1
    }


def test_uploaded_parsers_preserve_area_rows_nulls_and_reject_bad_rows():
    from app.uploaded_public_data import parse_uploaded_earthquakes, parse_uploaded_fema

    declarations = parse_uploaded_fema(zipped_fema(
        "DR-1,Disaster,05/02/1953,GA,,Tornado,Tornado,05/02/1953,05/02/1953,06/01/1954,Yes,No,Yes,Yes\n"
        "DR-1,Disaster,05/02/1953,GA,Example County,Tornado,Tornado,05/02/1953,05/02/1953,,Yes,No,Yes,Yes\n"
        "DR-2,Disaster,invalid,TX,Other County,Flood,Flood,05/02/1953,,,,Yes,No,Yes,Yes\n"
    ), "database.csv.zip")
    assert declarations["total_rows"] == 3
    assert len(declarations["rows"]) == 2
    assert declarations["duplicate_rows"] == 0
    assert declarations["rejected"] == {"invalid date, declaration fields, or assistance flag": 1}
    assert len({row["source_id"] for row in declarations["rows"]}) == 2
    assert declarations["rows"][0]["designated_area"] is None
    assert declarations["rows"][0]["close_date"].date().isoformat() == "1954-06-01"
    assert declarations["rows"][0]["individual_assistance"] is True
    assert declarations["rows"][0]["individuals_households_program"] is False

    quakes = parse_uploaded_earthquakes(earthquake_csv(
        "M 6.5 sample,6.5,16-08-2023 12:47,7,4,,0,657,us,114,7.177,25,mww,192.955,-13.8814,167.158,Sola,,\n"
        "bad,6.0,not-a-date,,,,0,1,us,1,1,1,mww,10,0,0,,,,\n"
    ), "earthquake_1995-2023.csv")
    assert len(quakes["rows"]) == 1
    row = quakes["rows"][0]
    assert row["event_time"].isoformat() == "2023-08-16T12:47:00+00:00"
    assert row["alert"] is None and row["continent"] is None and row["country"] is None
    assert row["tsunami"] is False and row["station_count"] == 114
    assert quakes["rejected"]


def test_authenticated_file_import_is_atomic_repeatable_and_operationally_isolated(client):
    declaration_rows = (
        "DR-12,Disaster,01/02/2001,AK,North County,Earthquake,Historical example,01/01/2001,01/03/2001,,"
        "Yes,No,Yes,No\n"
        "DR-12,Disaster,01/02/2001,AK,South County,Earthquake,Historical example,01/01/2001,01/03/2001,,"
        "Yes,No,Yes,No\n"
    )
    quake_rows = (
        "M 6.5 sample,6.5,16-08-2023 12:47,7,4,,1,657,us,114,7.177,25,mww,192.955,-13.8814,167.158,Sola,,\n"
    )
    fema = zipped_fema(declaration_rows)
    earthquake = earthquake_csv(quake_rows)
    admin = User(email="upload-admin@example.org", display_name="Upload Admin", password_hash="unused", role="super_admin")
    scoped = User(email="upload-scoped@example.org", display_name="Scoped Admin", password_hash="unused", role="admin", permissions=["view_reports"])
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        db.add_all([admin, scoped])
        db.flush()
        db.add_all([
            AuthSession(jti="upload-root-session", user_id=admin.id, expires_at=now + timedelta(hours=1)),
            AuthSession(jti="upload-scoped-session", user_id=scoped.id, expires_at=now + timedelta(hours=1)),
        ])
        db.commit()
    root_token = encode_access_token(admin, "upload-root-session", now, now + timedelta(minutes=30))
    scoped_token = encode_access_token(scoped, "upload-scoped-session", now, now + timedelta(minutes=30))
    files = {
        "fema_file": ("database.csv.zip", fema, "application/zip"),
        "earthquake_file": ("earthquake_1995-2023.csv", earthquake, "text/csv"),
    }
    assert client.post("/api/v1/admin/public-disaster-data/import", files=files).status_code == 401
    denied = client.post("/api/v1/admin/public-disaster-data/import", files=files, headers={"Authorization": f"Bearer {scoped_token}"})
    assert denied.status_code == 403
    rejected = client.post("/api/v1/admin/public-disaster-data/import", files={
        "fema_file": ("database.csv.zip", fema, "application/zip"),
        "earthquake_file": ("earthquake_1995-2023.csv", b"unexpected columns\n", "text/csv"),
    }, headers={"Authorization": f"Bearer {root_token}"})
    assert rejected.status_code == 422
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(PublicFemaDeclaration)) == 0
        assert db.scalar(select(func.count()).select_from(PublicEarthquake)) == 0
    before_incidents = client.get("/api/v1/incidents", headers={"Authorization": f"Bearer {root_token}"}).json()
    before_assignments = client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {root_token}"}).json().get("active_incidents")

    uploaded = client.post("/api/v1/admin/public-disaster-data/import", files=files, headers={"Authorization": f"Bearer {root_token}"})
    assert uploaded.status_code == 200, uploaded.text
    first = uploaded.json()["results"]
    assert first["uploaded_fema_declarations"]["inserted"] == 2
    assert first["uploaded_earthquakes"]["inserted"] == 1
    assert first["uploaded_fema_declarations"]["rejected"] == 0

    repeated = client.post("/api/v1/admin/public-disaster-data/import", files=files, headers={"Authorization": f"Bearer {root_token}"})
    assert repeated.status_code == 200
    second = repeated.json()["results"]
    assert second["uploaded_fema_declarations"]["inserted"] == 0
    assert second["uploaded_fema_declarations"]["skipped"] == 2
    assert second["uploaded_earthquakes"]["inserted"] == 0
    assert second["uploaded_earthquakes"]["skipped"] == 1

    data = client.get("/api/v1/admin/public-disaster-data", headers={"Authorization": f"Bearer {root_token}"})
    assert data.status_code == 200
    model = data.json()
    assert model["fema"]["count"] == 2 and model["earthquakes"]["count"] == 1
    assert {row["designated_area"] for row in model["fema"]["records"]} == {"North County", "South County"}
    assert model["earthquakes"]["records"][0]["tsunami"] is True
    assert model["earthquakes"]["records"][0]["event_url"] is None
    assert any(source["id"] == "uploaded_fema_declarations" and "not independently verified" in source["attribution"] for source in model["sources"])
    assert client.get("/api/v1/incidents", headers={"Authorization": f"Bearer {root_token}"}).json() == before_incidents
    assert client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {root_token}"}).json().get("active_incidents") == before_assignments
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Incident)) == 0
        assert db.scalar(select(func.count()).select_from(Assignment)) == 0
