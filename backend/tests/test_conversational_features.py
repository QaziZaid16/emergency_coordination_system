import asyncio

from app.config import Settings
from app.database import SessionLocal
from app.models import User
from app.security import hash_password
from app.intelligence import rewrite_responder_note


def _login(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_optional_category_followups_persist_without_gating_submission(client):
    registered = client.post("/api/v1/auth/register", json={
        "email": "fire-caller@example.com", "display_name": "Caller",
        "password": "CallerPassword-1234",
    })
    assert registered.status_code == 201
    token = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    submitted = client.post("/api/v1/user/incidents", headers={**token, "Idempotency-Key": "fire-intake-key-001"}, json={
        "emergency_type": "Fire and Rescue", "description": "Smoke in a building room",
        "location_label": "North building", "location_source": "manual",
        "severity": 4, "urgency": 5,
    })
    assert submitted.status_code == 201
    incident = submitted.json()
    assert incident["status"] == "Unassigned"
    intake = client.get(f"/api/v1/incidents/{incident['id']}/intake", headers=token)
    assert intake.status_code == 200
    assert {item["key"] for item in intake.json()["questions"]} >= {"people_at_risk", "spread"}
    saved = client.post(f"/api/v1/incidents/{incident['id']}/intake/answers", headers=token, json={"answers": {"people_at_risk": "unknown", "spread": "Smoke is increasing"}})
    assert saved.status_code == 201
    assert saved.json()["answers"]["people_at_risk"] is None
    assert saved.json()["answers"]["spread"] == "Smoke is increasing"
    assert saved.json()["dispatch_status"] == "Unassigned"
    invalid = client.post(f"/api/v1/incidents/{incident['id']}/intake/answers", headers=token, json={"answers": {"invented_field": "value"}})
    assert invalid.status_code == 422


def test_resolution_report_is_persisted_scoped_and_explicit_about_unknown_cause(client):
    registered = client.post("/api/v1/auth/register", json={
        "email": "report-caller@example.com", "display_name": "Caller",
        "password": "CallerPassword-1234",
    })
    user_token = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    with SessionLocal() as db:
        db.add(User(email="report-admin@example.com", display_name="Admin", password_hash=hash_password("AdminPassword-1234"), role="super_admin"))
        db.commit()
    admin_token = _login(client, "report-admin@example.com", "AdminPassword-1234")
    incident_response = client.post("/api/v1/user/incidents", headers={**user_token, "Idempotency-Key": "report-case-key-001"}, json={
        "emergency_type": "Other Emergency", "description": "A fallen tree blocks the driveway",
        "location_label": "12 Oak Street", "location_source": "manual",
    })
    incident_id = incident_response.json()["id"]
    resolved = client.post(f"/api/v1/admin/incidents/{incident_id}/resolve", headers=admin_token)
    assert resolved.status_code == 200
    report = client.get(f"/api/v1/incidents/{incident_id}/report", headers=user_token)
    assert report.status_code == 200
    assert report.json()["content"]["cause"] == "Cause not established from the available information."
    assert report.json()["source_records"]
    other = client.post("/api/v1/auth/register", json={
        "email": "other-caller@example.com", "display_name": "Other Caller",
        "password": "CallerPassword-1234",
    })
    other_token = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.get(f"/api/v1/incidents/{incident_id}/report", headers=other_token).status_code == 404
    reviewed = client.post(f"/api/v1/admin/incidents/{incident_id}/report/review", headers=admin_token, json={"note": "Reviewed against the incident record."})
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed"


def test_rewrite_falls_back_when_model_changes_uncertainty(monkeypatch):
    class Response:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "The person is safe."}}]}

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr("app.intelligence.httpx.AsyncClient", Client)
    settings = Settings(ai_provider="openrouter", openrouter_api_key="test-key", openrouter_base_url="https://openrouter.ai/api/v1")
    original = "I think the person may be safe."
    rewritten, outcome = asyncio.run(rewrite_responder_note(original, settings))
    assert rewritten == original
    assert outcome == "fallback_uncertainty_changed"
