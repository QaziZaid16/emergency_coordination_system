from datetime import timedelta
from types import SimpleNamespace

from sqlalchemy import select

import app.api as api
from app.database import SessionLocal
from app.models import AccountInvitation, AuditEvent, ResponderProfile, User, now_utc
from app.security import hash_password, hash_refresh_token


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
    monkeypatch.setattr("app.api.get_settings", lambda: SimpleNamespace(environment="development", jwt_secret="test-only-secret-with-more-than-32-characters", public_app_url="https://portal.example.test", smtp_host="", smtp_port=587, smtp_username="", smtp_password="", smtp_from=""))
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
    assert "activate.html#token=" in invited.json()["activation_url"]
    activation = invited.json()["activation_url"].split("token=", 1)[1]
    assert "RootPassword" not in invited.text
    accepted = client.post("/api/v1/auth/accept-invitation", json={"token": activation, "password": "ResponderPassword-1234"})
    assert accepted.status_code == 200
    repeated = client.post("/api/v1/auth/accept-invitation", json={"token": activation, "password": "AnotherPassword-1234"})
    assert repeated.status_code == 400
    activated = client.post("/api/v1/auth/login", json={"email": "new-responder@example.com", "password": "ResponderPassword-1234"})
    assert activated.status_code == 200
    assert activated.json()["user"]["role"] == "responder"


def test_staging_activation_handoff_is_admin_only_single_use_and_not_cached(
    client, monkeypatch, caplog
):
    make_admin()
    raw_token = "synthetic-staging-handoff-token-1234567890"
    resend_token = "synthetic-staging-resend-token-1234567890"
    generated_tokens = iter(["synthetic-placeholder-password", raw_token, resend_token])
    monkeypatch.setattr(
        api,
        "get_settings",
        lambda: SimpleNamespace(
            environment="staging",
            jwt_secret="test-only-secret-with-more-than-32-characters",
            public_app_url="https://staging.example.test",
            smtp_host="",
            smtp_port=587,
            smtp_username="",
            smtp_password="",
            smtp_from="",
            staging_responder_invitation_handoff=True,
        ),
    )
    monkeypatch.setattr(api.secrets, "token_urlsafe", lambda _length: next(generated_tokens))
    monkeypatch.setattr(
        api,
        "send_invitation_email",
        lambda *_args: (_ for _ in ()).throw(AssertionError("SMTP must remain disabled")),
    )
    admin_token = sign_in(client)
    payload = {
        "email": "staging-responder@example.com",
        "display_name": "Staging Responder",
        "capabilities": ["medical"],
    }

    assert client.post("/api/v1/admin/invitations/responders", json=payload).status_code == 401
    user = client.post(
        "/api/v1/auth/register",
        json={
            "email": "ordinary-user@example.com",
            "display_name": "Ordinary User",
            "password": "Ordinary-User-Password-1234",
        },
    )
    with SessionLocal() as db:
        underprivileged = User(
            email="underprivileged-admin@example.com",
            display_name="Underprivileged Admin",
            password_hash=hash_password("Underprivileged-Admin-1234"),
            role="admin",
            permissions=["view_dashboard"],
        )
        db.add(underprivileged)
        db.commit()
    underprivileged_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "underprivileged-admin@example.com",
            "password": "Underprivileged-Admin-1234",
        },
    )
    assert underprivileged_login.status_code == 200
    underprivileged_response = client.post(
        "/api/v1/admin/invitations/responders",
        headers={
            "Authorization": f"Bearer {underprivileged_login.json()['access_token']}"
        },
        json=payload,
    )
    assert underprivileged_response.status_code == 403
    forbidden = client.post(
        "/api/v1/admin/invitations/responders",
        headers={"Authorization": f"Bearer {user.json()['access_token']}"},
        json=payload,
    )
    assert forbidden.status_code == 403

    invited = client.post(
        "/api/v1/admin/invitations/responders",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )

    assert invited.status_code == 201, invited.text
    invitation = invited.json()
    assert invitation["invitation_status"] == "activation_handoff"
    assert invitation["activation_url"] == (
        "https://staging.example.test/activate.html#token=" + raw_token
    )
    assert invited.headers["cache-control"] == "no-store"
    assert raw_token not in caplog.text
    with SessionLocal() as db:
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "responder.activation_handoff_issued"
            )
        ).all()
        assert len(events) == 1
        assert raw_token not in str(events[0].details)

    with SessionLocal() as db:
        pending_responder = User(
            email="resend-staging-responder@example.com",
            display_name="Resend Staging Responder",
            password_hash=hash_password("Temporary-Responder-Password-1234"),
            role="responder",
            active=False,
        )
        db.add(pending_responder)
        db.flush()
        db.add(
            AccountInvitation(
                user_id=pending_responder.id,
                token_hash=hash_refresh_token("expired-resend-token-placeholder"),
                expires_at=now_utc() - timedelta(seconds=1),
            )
        )
        db.commit()
        pending_responder_id = pending_responder.id
    resent = client.post(
        f"/api/v1/admin/invitations/responders/{pending_responder_id}/resend",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resent.status_code == 201
    assert resent.json()["invitation_status"] == "activation_handoff"
    assert resent.json()["activation_url"] == (
        "https://staging.example.test/activate.html#token=" + resend_token
    )
    assert resent.headers["cache-control"] == "no-store"
    assert resend_token not in caplog.text

    accepted = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": raw_token, "password": "Staging-Responder-Password-1234"},
    )
    assert accepted.status_code == 200
    accepted_resend = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": resend_token, "password": "Staging-Resend-Password-1234"},
    )
    assert accepted_resend.status_code == 200
    activated_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": payload["email"],
            "password": "Staging-Responder-Password-1234",
        },
    )
    assert activated_login.status_code == 200
    assert activated_login.json()["user"]["role"] == "responder"
    reused = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": raw_token, "password": "Another-Responder-Password-1234"},
    )
    assert reused.status_code == 400


def test_failed_invitation_email_revokes_token_without_exposing_it(
    client, monkeypatch, caplog
):
    make_admin()
    raw_token = "synthetic-one-time-token-not-for-logs"
    resend_token = "synthetic-resend-token-not-for-logs"
    generated_tokens = iter(
        ["synthetic-placeholder-password", raw_token, resend_token]
    )
    monkeypatch.setattr(
        api,
        "get_settings",
        lambda: SimpleNamespace(
            environment="production",
            jwt_secret="test-only-secret-with-more-than-32-characters",
            public_app_url="https://portal.example.test",
            smtp_host="smtp.test.invalid",
            smtp_port=587,
            smtp_username="",
            smtp_password="",
            smtp_from="",
        ),
    )
    monkeypatch.setattr(api.secrets, "token_urlsafe", lambda _length: next(generated_tokens))

    class FailingSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self):
            pass

        def send_message(self, _message):
            raise OSError("synthetic mail transport failure")

    monkeypatch.setattr(api.smtplib, "SMTP", FailingSMTP)
    admin_token = sign_in(client)

    response = client.post(
        "/api/v1/admin/invitations/responders",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "mail-failure-responder@example.com",
            "display_name": "Mail Failure Responder",
            "capabilities": ["medical"],
        },
    )

    assert response.status_code == 502
    assert raw_token not in response.text
    assert raw_token not in caplog.text
    with SessionLocal() as db:
        responder = db.scalar(
            select(User).where(User.email == "mail-failure-responder@example.com")
        )
        assert responder is not None
        responder_id = responder.id
    resend_response = client.post(
        f"/api/v1/admin/invitations/responders/{responder_id}/resend",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resend_response.status_code == 502
    assert resend_token not in resend_response.text
    assert resend_token not in caplog.text
    with SessionLocal() as db:
        invitations = db.scalars(
            select(AccountInvitation).where(
                AccountInvitation.token_hash.in_(
                    [hash_refresh_token(raw_token), hash_refresh_token(resend_token)]
                )
            )
        ).all()
        assert len(invitations) == 2
        assert all(invitation.revoked_at is not None for invitation in invitations)
        responder = db.get(User, responder_id)
        assert responder is not None
        assert responder.active is False
        failure_events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "responder.invitation_delivery_failed"
            )
        ).all()
        assert len(failure_events) == 2
        assert all(
            raw_token not in str(event.details)
            and resend_token not in str(event.details)
            for event in failure_events
        )


def test_unknown_and_expired_responder_invitation_tokens_are_rejected(client):
    unknown = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": "unknown-synthetic-invitation-token", "password": "ResponderPassword-1234"},
    )
    assert unknown.status_code == 400
    expected = {
        "detail": "This invitation is invalid or expired. Ask an administrator for a new invitation."
    }
    assert unknown.json() == expected

    expired_token = "expired-synthetic-invitation-token"
    with SessionLocal() as db:
        responder = User(
            email="expired-responder@example.com",
            display_name="Expired Responder",
            password_hash=hash_password("TemporaryPassword-1234"),
            role="responder",
            active=False,
        )
        db.add(responder)
        db.flush()
        db.add(
            AccountInvitation(
                user_id=responder.id,
                token_hash=hash_refresh_token(expired_token),
                expires_at=now_utc() - timedelta(seconds=1),
            )
        )
        db.commit()

    expired = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": expired_token, "password": "ResponderPassword-1234"},
    )
    assert expired.status_code == 400
    assert expired.json() == expected

    revoked_token = "revoked-synthetic-invitation-token"
    with SessionLocal() as db:
        responder = User(
            email="revoked-responder@example.com",
            display_name="Revoked Responder",
            password_hash=hash_password("TemporaryPassword-5678"),
            role="responder",
            active=False,
        )
        db.add(responder)
        db.flush()
        db.add(
            AccountInvitation(
                user_id=responder.id,
                token_hash=hash_refresh_token(revoked_token),
                expires_at=now_utc() + timedelta(hours=1),
                revoked_at=now_utc(),
            )
        )
        db.commit()

    revoked = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": revoked_token, "password": "ResponderPassword-1234"},
    )
    assert revoked.status_code == 400
    assert revoked.json() == expected
