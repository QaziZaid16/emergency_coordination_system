from types import SimpleNamespace

from sqlalchemy import select

from app.database import SessionLocal
from app.models import ResponderProfile, User
from app.security import hash_password


def make_admin(email="root@example.com", role="super_admin", permissions=None):
    with SessionLocal() as db:
        account = User(email=email, display_name="Root Admin", password_hash=hash_password("RootPassword-1234"), role=role, permissions=permissions or [])
        db.add(account)
        db.commit()
        return account.id


def sign_in(client, email="root@example.com", password="RootPassword-1234"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_coadmin_permissions_are_backend_enforced_and_take_effect_immediately(client):
    make_admin()
    root_token = sign_in(client)
    created = client.post("/api/v1/admin/coadmins", headers={"Authorization": f"Bearer {root_token}"}, json={
        "email": "coadmin@example.com", "display_name": "Limited Admin", "password": "LimitedPassword-1234", "permissions": ["view_dashboard"]
    })
    assert created.status_code == 201, created.text
    login = client.post("/api/v1/auth/login", json={"email": "coadmin@example.com", "password": "LimitedPassword-1234"})
    assert login.json()["user"]["role"] == "admin"
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/admin/dashboard", headers=headers).status_code == 200
    assert client.get("/api/v1/incidents", headers=headers).status_code == 403
    assert client.post("/api/v1/admin/coadmins", headers=headers, json={}).status_code == 403
    with SessionLocal() as db:
        account = db.scalar(select(User).where(User.email == "coadmin@example.com"))
        account.permissions = []
        db.commit()
    assert client.get("/api/v1/admin/dashboard", headers=headers).status_code == 403
    revoked = client.patch(f"/api/v1/admin/coadmins/{created.json()['id']}/active?active=false", headers={"Authorization": f"Bearer {root_token}"})
    assert revoked.status_code == 200
    assert client.get("/api/v1/admin/dashboard", headers=headers).status_code == 401


def test_management_permissions_allow_reading_their_management_lists(client):
    make_admin()
    root_token = sign_in(client)
    created = client.post("/api/v1/admin/coadmins", headers={"Authorization": f"Bearer {root_token}"}, json={
        "email": "resource-manager@example.com", "display_name": "Resource Manager", "password": "ResourcePassword-1234", "permissions": ["manage_resources"]
    })
    assert created.status_code == 201, created.text
    token = sign_in(client, "resource-manager@example.com", "ResourcePassword-1234")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/admin/resources", headers=headers).status_code == 200
    assert client.post("/api/v1/admin/resources", headers=headers, json={"name": "Van", "kind": "ambulance", "quantity": 1}).status_code == 201
    assert client.get("/api/v1/admin/dashboard", headers=headers).status_code == 403
    responder_admin = client.post("/api/v1/admin/coadmins", headers={"Authorization": f"Bearer {root_token}"}, json={
        "email": "responder-manager@example.com", "display_name": "Responder Manager", "password": "ResponderPassword-1234", "permissions": ["manage_responders"]
    })
    assert responder_admin.status_code == 201, responder_admin.text
    responder_token = sign_in(client, "responder-manager@example.com", "ResponderPassword-1234")
    responder_headers = {"Authorization": f"Bearer {responder_token}"}
    assert client.get("/api/v1/admin/responders", headers=responder_headers).status_code == 200
    assert client.get("/api/v1/admin/dashboard", headers=responder_headers).status_code == 403
    with SessionLocal() as db:
        public_user = User(email="public-user@example.com", display_name="Public User", password_hash=hash_password("UserPassword-1234"), role="user")
        responder = User(email="field-responder@example.com", display_name="Field Responder", password_hash=hash_password("ResponderPassword-1234"), role="responder")
        db.add_all([public_user, responder])
        db.flush()
        db.add(ResponderProfile(user_id=responder.id, capabilities=["medical"], available=True))
        db.commit()
        responder_id = responder.id
    # A responder-management grant must not become an unfiltered account directory.
    assert client.get("/api/v1/admin/users", headers=responder_headers).status_code == 403
    scoped_accounts = client.get("/api/v1/admin/users?role=responder", headers=responder_headers)
    assert scoped_accounts.status_code == 200, scoped_accounts.text
    assert [account["id"] for account in scoped_accounts.json()] == [responder_id]
    assert client.get("/api/v1/admin/users?role=user", headers=responder_headers).status_code == 403
    suspended = client.patch(f"/api/v1/admin/users/{responder_id}/active?active=false", headers=responder_headers)
    assert suspended.status_code == 200, suspended.text
    assert client.patch(f"/api/v1/admin/users/{responder_id}/active?active=true", headers=headers).status_code == 403


def test_responder_invitation_activates_once_and_never_returns_in_production(client, monkeypatch):
    make_admin()
    monkeypatch.setattr("app.api.get_settings", lambda: SimpleNamespace(environment="development", public_app_url="https://portal.example.test", smtp_host="", smtp_port=587, smtp_username="", smtp_password="", smtp_from=""))
    token = sign_in(client)
    headers = {"Authorization": f"Bearer {token}"}
    rejected_direct_create = client.post("/api/v1/admin/users", headers=headers, json={
        "email": "unsafe@example.com", "display_name": "Unsafe", "password": "ResponderPassword-1234", "role": "responder", "capabilities": ["medical"]
    })
    assert rejected_direct_create.status_code == 409
    invited = client.post("/api/v1/admin/invitations/responders", headers=headers, json={
        "email": "new-responder@example.com", "display_name": "New Responder", "capabilities": ["medical"]
    })
    assert invited.status_code == 201, invited.text
    activation = invited.json()["activation_url"].split("token=", 1)[1]
    assert "RootPassword" not in invited.text
    accepted = client.post("/api/v1/auth/accept-invitation", json={"token": activation, "password": "ResponderPassword-1234"})
    assert accepted.status_code == 200
    repeated = client.post("/api/v1/auth/accept-invitation", json={"token": activation, "password": "AnotherPassword-1234"})
    assert repeated.status_code == 400
    activated = client.post("/api/v1/auth/login", json={"email": "new-responder@example.com", "password": "ResponderPassword-1234"})
    assert activated.status_code == 200
    assert activated.json()["user"]["role"] == "responder"
