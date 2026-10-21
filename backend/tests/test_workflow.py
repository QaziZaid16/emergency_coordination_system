from sqlalchemy import select

from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def create_admin():
    with SessionLocal() as db:
        admin = User(email="admin@example.com", display_name="Control Admin", password_hash=hash_password("AdminPassword-1234"), role="admin")
        db.add(admin)
        db.commit()


def login(client, email, password, portal):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password, "portal": portal})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_user_admin_responder_workflow_and_role_isolation(client):
    create_admin()
    registered = client.post("/api/v1/auth/register", json={
        "email": "caller@example.com", "display_name": "Caller One", "password": "CallerPassword-1234",
    })
    assert registered.status_code == 201, registered.text
    user_token = registered.json()["access_token"]
    admin_token = login(client, "admin@example.com", "AdminPassword-1234", "admin")

    wrong_portal = client.post("/api/v1/auth/login", json={
        "email": "caller@example.com", "password": "CallerPassword-1234", "portal": "admin",
    })
    assert wrong_portal.status_code == 403
    assert client.get("/api/v1/admin/dashboard", headers=auth(user_token)).status_code == 403
    assert client.get("/api/v1/responder/profile", headers=auth(user_token)).status_code == 403

    created_responder = client.post("/api/v1/admin/users", headers=auth(admin_token), json={
        "email": "responder@example.com", "display_name": "Medical Responder",
        "password": "ResponderPassword-1234", "role": "responder", "capabilities": ["medical"],
    })
    assert created_responder.status_code == 201, created_responder.text
    responder_id = created_responder.json()["id"]
    responder_token = login(client, "responder@example.com", "ResponderPassword-1234", "responder")

    payload = {
        "emergency_type": "Ambulance / Medical Emergency", "description": "Caller needs medical assistance",
        "location_label": "Current phone location", "location_source": "gps",
        "latitude": 30.7, "longitude": 76.7, "accuracy_m": 18.5,
        "location_at": datetime.now(timezone.utc).isoformat(), "severity": 5, "urgency": 5,
    }
    headers = {**auth(user_token), "Idempotency-Key": "same-request-key-123"}
    first = client.post("/api/v1/user/incidents", headers=headers, json=payload)
    assert first.status_code == 201, first.text
    duplicate = client.post("/api/v1/user/incidents", headers=headers, json=payload)
    assert duplicate.status_code == 200
    incident = first.json()
    assert duplicate.json()["id"] == incident["id"]
    assert incident["status"] == "Unassigned"
    assert incident["priority"] == "Critical"
    stale_location = {**payload, "location_at": "2020-01-01T00:00:00Z"}
    stale = client.post("/api/v1/user/incidents", headers={**auth(user_token), "Idempotency-Key": "stale-request-key-123"}, json=stale_location)
    assert stale.status_code == 422

    dashboard = client.get("/api/v1/admin/dashboard", headers=auth(admin_token)).json()
    assert dashboard["unassigned"] == 1
    assert client.get("/api/v1/incidents", headers=auth(responder_token)).json() == []
    another_user = client.post("/api/v1/auth/register", json={
        "email": "other@example.com", "display_name": "Other Caller", "password": "OtherPassword-1234",
    }).json()["access_token"]
    assert client.get(f"/api/v1/incidents/{incident['id']}", headers=auth(another_user)).status_code == 404

    resource = client.post("/api/v1/admin/resources", headers=auth(admin_token), json={"name": "Medical unit 01", "kind": "Ambulance", "quantity": 1})
    assert resource.status_code == 201
    assigned = client.post(f"/api/v1/admin/incidents/{incident['id']}/assign", headers=auth(admin_token), json={"responder_id": responder_id, "resource_id": resource.json()["id"]})
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["status"] == "Assigned"
    assert assigned.json()["resource_name"] == "Medical unit 01"
    assigned_dashboard = client.get("/api/v1/admin/dashboard", headers=auth(admin_token)).json()
    assert assigned_dashboard["assigned"] == 1
    assert assigned_dashboard["responders_busy"] == 1
    assert len(client.get("/api/v1/incidents", headers=auth(responder_token)).json()) == 1
    assert client.post(f"/api/v1/admin/incidents/{incident['id']}/assign", headers=auth(admin_token), json={"responder_id": responder_id}).status_code == 409

    out_of_order = client.post(f"/api/v1/responder/incidents/{incident['id']}/status", headers=auth(responder_token), json={"status": "En Route"})
    assert out_of_order.status_code == 409
    for next_status in ["Accepted", "En Route", "On Scene", "Resolved"]:
        result = client.post(f"/api/v1/responder/incidents/{incident['id']}/status", headers=auth(responder_token), json={"status": next_status})
        assert result.status_code == 200, result.text
        assert result.json()["status"] == next_status
    assert client.get("/api/v1/admin/dashboard", headers=auth(admin_token)).json()["resolved"] == 1
    assert client.get("/api/v1/admin/dashboard", headers=auth(admin_token)).json()["resources_allocated"] == 0
    assert len(client.get("/api/v1/incidents", headers=auth(responder_token)).json()) == 1
    assert client.post(f"/api/v1/incidents/{incident['id']}/updates", headers=auth(responder_token), json={"message": "Late update"}).status_code == 409
    assert client.get("/api/v1/admin/audit", headers=auth(admin_token)).status_code == 200


def test_logout_revokes_session_and_admin_only_routes_are_protected(client):
    create_admin()
    token = login(client, "admin@example.com", "AdminPassword-1234", "admin")
    assert client.get("/api/v1/admin/dashboard", headers=auth(token)).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=auth(token)).status_code == 204
    assert client.get("/api/v1/admin/dashboard", headers=auth(token)).status_code == 401


def test_reassignment_revokes_previous_responder_and_releases_resource(client):
    create_admin()
    admin_token = login(client, "admin@example.com", "AdminPassword-1234", "admin")
    user_token = client.post("/api/v1/auth/register", json={
        "email": "reassignment-caller@example.com", "display_name": "Caller", "password": "CallerPassword-1234",
    }).json()["access_token"]

    responders = []
    responder_tokens = []
    for index in (1, 2):
        created = client.post("/api/v1/admin/users", headers=auth(admin_token), json={
            "email": f"field{index}@example.com", "display_name": f"Field Responder {index}",
            "password": f"ResponderPassword-{index}234", "role": "responder", "capabilities": ["medical"],
        })
        assert created.status_code == 201, created.text
        responders.append(created.json()["id"])
        responder_tokens.append(login(client, f"field{index}@example.com", f"ResponderPassword-{index}234", "responder"))

    incident = client.post("/api/v1/user/incidents", headers={
        **auth(user_token), "Idempotency-Key": "reassignment-case-0001",
    }, json={
        "emergency_type": "Ambulance / Medical Emergency", "description": "Need medical assistance",
        "location_label": "Main street entrance", "location_source": "manual", "severity": 3, "urgency": 3,
    }).json()
    resource = client.post("/api/v1/admin/resources", headers=auth(admin_token), json={
        "name": "Reassignment ambulance", "kind": "Ambulance", "quantity": 1,
    }).json()
    assigned = client.post(f"/api/v1/admin/incidents/{incident['id']}/assign", headers=auth(admin_token), json={
        "responder_id": responders[0], "resource_id": resource["id"],
    })
    assert assigned.status_code == 200
    reassigned = client.post(f"/api/v1/admin/incidents/{incident['id']}/reassign", headers=auth(admin_token), json={
        "responder_id": responders[1],
    })
    assert reassigned.status_code == 200, reassigned.text
    assert reassigned.json()["responder_id"] == responders[1]
    assert reassigned.json()["resource_id"] is None
    assert client.get("/api/v1/incidents", headers=auth(responder_tokens[0])).json() == []
    assert client.get("/api/v1/incidents", headers=auth(responder_tokens[1])).json()[0]["id"] == incident["id"]
    rejected = client.post(f"/api/v1/responder/incidents/{incident['id']}/status", headers=auth(responder_tokens[0]), json={"status": "Accepted"})
    assert rejected.status_code == 404
    current = client.get(f"/api/v1/incidents/{incident['id']}", headers=auth(user_token)).json()
    assert current["responder_id"] == responders[1]
    resource_list = client.get("/api/v1/admin/resources", headers=auth(admin_token)).json()
    assert resource_list[0]["allocated"] == 0
