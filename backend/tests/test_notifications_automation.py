from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import Notification, ResponderProfile, User
from app.security import hash_password


def authorization(token):
    return {"Authorization": f"Bearer {token}"}


def create_admin():
    with SessionLocal() as db:
        row = User(email="policy@example.com", display_name="Policy Owner", password_hash=hash_password("PolicyPassword-1234"), role="super_admin")
        db.add(row)
        db.commit()
        return row.id


def create_responder():
    with SessionLocal() as db:
        row = User(email="candidate@example.com", display_name="Candidate Responder", password_hash=hash_password("ResponderPassword-1234"), role="responder")
        db.add(row)
        db.flush()
        db.add(ResponderProfile(user_id=row.id, capabilities=["medical"], available=True, latitude=30.7, longitude=76.7, location_accuracy_m=20, location_at=datetime.now(timezone.utc)))
        db.commit()
        return row.id


def register_user(client, email="caller@example.com"):
    response = client.post("/api/v1/auth/register", json={"email": email, "display_name": "Caller", "password": "CallerPassword-1234"})
    assert response.status_code == 201
    return response.json()["access_token"]


def test_incident_notifications_are_persisted_and_private(client):
    admin_id = create_admin()
    with SessionLocal() as db:
        coadmin = User(email="scoped@example.com", display_name="Scoped Co-Admin", password_hash=hash_password("ScopedPassword-1234"), role="admin", permissions=[])
        db.add(coadmin)
        db.commit()
    user_token = register_user(client)
    result = client.post("/api/v1/user/incidents", headers={**authorization(user_token), "Idempotency-Key": "notify-event-123"}, json={
        "emergency_type": "Ambulance / Medical Emergency",
        "description": "Medical assistance requested",
        "location_label": "Main street",
        "location_source": "manual",
        "severity": 3,
        "urgency": 3,
    })
    assert result.status_code == 201
    user_notifications = client.get("/api/v1/notifications", headers=authorization(user_token)).json()
    assert [item["kind"] for item in user_notifications] == ["incident_status"]
    admin_login = client.post("/api/v1/auth/login", json={"email": "policy@example.com", "password": "PolicyPassword-1234"})
    admin_token = admin_login.json()["access_token"]
    admin_notifications = client.get("/api/v1/notifications", headers=authorization(admin_token)).json()
    assert admin_notifications[0]["kind"] == "new_incident"
    scoped_token = client.post("/api/v1/auth/login", json={"email": "scoped@example.com", "password": "ScopedPassword-1234"}).json()["access_token"]
    assert client.get("/api/v1/notifications", headers=authorization(scoped_token)).json() == []
    other_token = register_user(client, "other@example.com")
    notification_id = user_notifications[0]["id"]
    assert client.patch(f"/api/v1/notifications/{notification_id}/read", headers=authorization(other_token)).status_code == 404
    assert client.patch(f"/api/v1/notifications/{notification_id}/read", headers=authorization(user_token)).status_code == 200
    assert client.get("/api/v1/notifications", headers=authorization(user_token)).json()[0]["read"] is True
    with SessionLocal() as db:
        assert db.query(Notification).count() >= 2
        assert db.get(User, admin_id) is not None


def test_automatic_assignment_requires_super_admin_policy_and_reliable_match(client):
    create_admin()
    responder_id = create_responder()
    admin_token = client.post("/api/v1/auth/login", json={"email": "policy@example.com", "password": "PolicyPassword-1234"}).json()["access_token"]
    assert client.put("/api/v1/admin/automation", headers=authorization(admin_token), json={"enabled": True, "max_severity": 3}).status_code == 200
    user_token = register_user(client)
    timestamp = datetime.now(timezone.utc).isoformat()
    result = client.post("/api/v1/user/incidents", headers={**authorization(user_token), "Idempotency-Key": "auto-event-123"}, json={
        "emergency_type": "Ambulance / Medical Emergency",
        "description": "Medical assistance requested",
        "location_label": "Verified phone location",
        "location_source": "gps",
        "latitude": 30.7,
        "longitude": 76.7,
        "accuracy_m": 20,
        "location_at": timestamp,
        "severity": 3,
        "urgency": 3,
    })
    assert result.status_code == 201, result.text
    assert result.json()["status"] == "Assigned"
    assert result.json()["responder_id"] == responder_id
    assert result.json()["assignment_source"] == "automatic"
    responder_token = client.post("/api/v1/auth/login", json={"email": "candidate@example.com", "password": "ResponderPassword-1234"}).json()["access_token"]
    inbox = client.get("/api/v1/notifications", headers=authorization(responder_token)).json()
    assert inbox[0]["kind"] == "assignment"
    assert client.get(f"/api/v1/incidents/{result.json()['id']}", headers=authorization(responder_token)).status_code == 200
    for status in ("Accepted", "En Route", "On Scene", "Resolved"):
        transition = client.post(f"/api/v1/responder/incidents/{result.json()['id']}/status", headers=authorization(responder_token), json={"status": status})
        assert transition.status_code == 200, transition.text
    reporter_inbox = client.get("/api/v1/notifications", headers=authorization(user_token)).json()
    assert any(item["message"].endswith("Resolved.") for item in reporter_inbox)
    assert client.get("/api/v1/incidents", headers=authorization(user_token)).json()[0]["status"] == "Resolved"


def test_auto_assignment_skips_high_severity_and_unreliable_location(client):
    create_admin()
    create_responder()
    admin_token = client.post("/api/v1/auth/login", json={"email": "policy@example.com", "password": "PolicyPassword-1234"}).json()["access_token"]
    client.put("/api/v1/admin/automation", headers=authorization(admin_token), json={"enabled": True, "max_severity": 2})
    user_token = register_user(client)
    result = client.post("/api/v1/user/incidents", headers={**authorization(user_token), "Idempotency-Key": "manual-review-123"}, json={
        "emergency_type": "Ambulance / Medical Emergency",
        "description": "Urgent medical assistance",
        "location_label": "Caller provided location",
        "location_source": "manual",
        "severity": 5,
        "urgency": 5,
    })
    assert result.status_code == 201
    assert result.json()["status"] == "Unassigned"


def test_auto_assignment_without_fresh_responder_location_stays_unassigned(client):
    create_admin()
    responder_id = create_responder()
    with SessionLocal() as db:
        profile = db.get(ResponderProfile, responder_id)
        profile.latitude = None
        profile.longitude = None
        profile.location_at = None
        profile.location_accuracy_m = None
        db.commit()
    admin_token = client.post("/api/v1/auth/login", json={"email": "policy@example.com", "password": "PolicyPassword-1234"}).json()["access_token"]
    client.put("/api/v1/admin/automation", headers=authorization(admin_token), json={"enabled": True, "max_severity": 3})
    user_token = register_user(client)
    result = client.post("/api/v1/user/incidents", headers={**authorization(user_token), "Idempotency-Key": "gps-review-123"}, json={
        "emergency_type": "Ambulance / Medical Emergency",
        "description": "Medical assistance requested",
        "location_label": "Verified phone location",
        "location_source": "gps",
        "latitude": 30.7,
        "longitude": 76.7,
        "accuracy_m": 20,
        "location_at": datetime.now(timezone.utc).isoformat(),
        "severity": 2,
        "urgency": 2,
    })
    assert result.status_code == 201
    assert result.json()["status"] == "Unassigned"
    admin_inbox = client.get("/api/v1/notifications", headers=authorization(admin_token)).json()
    assert any(item["kind"] == "automation_review" for item in admin_inbox)
