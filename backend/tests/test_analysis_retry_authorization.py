import asyncio
import threading
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient

from app import api, intelligence
from app.config import Settings
from app.database import SessionLocal
from app.intelligence import ProviderOutput, analyze_incident_task
from app.models import AuditEvent, Incident, IncidentAnalysis, User, now_utc
from app.security import hash_password, issue_token


def _identity(*, role, permissions=None):
    with SessionLocal() as db:
        user = User(
            email=f"retry-{uuid4().hex}@example.test",
            display_name="Retry authorization test",
            password_hash=hash_password("SyntheticPassword-1234"),
            role=role,
            permissions=permissions or [],
        )
        db.add(user)
        db.commit()
        token, _, _, _ = issue_token(user, db)
        return user.id, token


def _incident(*, status="pending", token=None, last_error=None, last_attempt=None):
    reporter_id, _ = _identity(role="user")
    incident_id = str(uuid4())
    suffix = incident_id.replace("-", "")
    with SessionLocal.begin() as db:
        db.add(
            Incident(
                id=incident_id,
                reference=f"RT-{suffix[:8].upper()}",
                reporter_id=reporter_id,
                emergency_type="Other Emergency",
                description="Smoke visible at the north entrance",
                location_label="Synthetic test location",
                location_source="manual",
                severity=2,
                urgency=2,
                priority="Low",
                priority_reason="synthetic retry test",
                status="Unassigned",
                idempotency_key=f"retry-{suffix}",
            )
        )
        db.add(
            IncidentAnalysis(
                incident_id=incident_id,
                status=status,
                provider="mock_previous",
                model="mock-previous-model",
                result={"summary": "Previous synthetic analysis"},
                validation_outcome="validated" if status == "ready" else "pending",
                last_error_type=last_error,
                claim_token=token,
                last_attempt_at=last_attempt,
            )
        )
    return incident_id


def _analysis_state(incident_id):
    with SessionLocal() as db:
        row = db.get(IncidentAnalysis, incident_id)
        return {
            "status": row.status,
            "claim_token": row.claim_token,
            "provider": row.provider,
            "model": row.model,
            "result": row.result,
            "validation_outcome": row.validation_outcome,
            "last_error_type": row.last_error_type,
        }


def _forbid_provider_network(*_args, **_kwargs):
    raise AssertionError("provider network boundary reached in retry test")


def _install_provider_guards(monkeypatch):
    monkeypatch.setattr(intelligence.httpx, "AsyncClient", _forbid_provider_network)
    monkeypatch.setattr(intelligence, "urlopen", _forbid_provider_network)


def test_retry_endpoint_rejects_unauthenticated_request(client, monkeypatch):
    incident_id = _incident(status="unavailable", token="current-owner")
    _install_provider_guards(monkeypatch)

    response = client.post(
        f"/api/v1/admin/incidents/{incident_id}/analysis/retry"
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "A valid session is required"}
    assert _analysis_state(incident_id)["claim_token"] == "current-owner"


def test_retry_endpoint_rejects_user_role(client, monkeypatch):
    incident_id = _incident(status="unavailable", token="current-owner")
    _, token = _identity(role="user")
    _install_provider_guards(monkeypatch)

    response = client.post(
        f"/api/v1/admin/incidents/{incident_id}/analysis/retry",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Your role cannot perform this operation"}
    assert _analysis_state(incident_id)["claim_token"] == "current-owner"


def test_retry_endpoint_requires_update_incidents_permission_for_admin(
    client, monkeypatch
):
    incident_id = _incident(status="unavailable", token="current-owner")
    _, token = _identity(role="admin", permissions=["view_dashboard"])
    _install_provider_guards(monkeypatch)

    response = client.post(
        f"/api/v1/admin/incidents/{incident_id}/analysis/retry",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Missing permission: update_incidents"}
    assert _analysis_state(incident_id)["claim_token"] == "current-owner"


@pytest.mark.parametrize(
    ("status", "last_error", "last_attempt_age"),
    [
        ("processing", None, "fresh"),
        ("ready", None, "old"),
    ],
    ids=("active-task", "already-validated"),
)
def test_retry_business_rejection_preserves_analysis_and_does_not_dispatch(
    client, monkeypatch, status, last_error, last_attempt_age
):
    incident_id = _incident(
        status=status,
        token="current-owner",
        last_error=last_error,
        last_attempt=(
            now_utc()
            if last_attempt_age == "fresh"
            else now_utc() - timedelta(minutes=5)
        ),
    )
    _, token = _identity(role="super_admin")
    dispatched = []
    monkeypatch.setattr(api, "analyze_incident_task", lambda incident_id: dispatched.append(incident_id))
    _install_provider_guards(monkeypatch)
    before = _analysis_state(incident_id)

    response = client.post(
        f"/api/v1/admin/incidents/{incident_id}/analysis/retry",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Incident analysis is already running"
            if status == "processing"
            else "Validated analysis is already available"
        )
    }
    assert _analysis_state(incident_id) == before
    assert dispatched == []


def test_authorized_admin_retry_commits_invalidation_then_dispatches(
    client, monkeypatch
):
    incident_id = _incident(
        status="processing",
        token="previous-owner",
        last_attempt=now_utc() - timedelta(minutes=2),
    )
    _, token = _identity(role="admin", permissions=["update_incidents"])
    observed = []

    async def observe_dispatched_task(dispatched_id):
        with SessionLocal() as db:
            row = db.get(IncidentAnalysis, dispatched_id)
            observed.append((dispatched_id, row.status, row.claim_token, row.validation_outcome))

    monkeypatch.setattr(api, "analyze_incident_task", observe_dispatched_task)
    _install_provider_guards(monkeypatch)

    response = client.post(
        f"/api/v1/admin/incidents/{incident_id}/analysis/retry",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 202
    assert response.json() == {
        "incident_id": incident_id,
        "analysis_status": "pending",
    }
    assert observed == [(incident_id, "pending", None, "retry_requested")]
    with SessionLocal() as db:
        event = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "incident.analysis_retry_requested",
                AuditEvent.entity_id == incident_id,
            )
        )
        assert event is not None


class _RetryRaceProvider:
    name = "mock_retry_race"

    def __init__(self):
        self.calls = 0
        self.entered = threading.Event()
        self.release_old = threading.Event()
        self.lock = threading.Lock()

    async def analyze(self, _incident, _settings):
        with self.lock:
            self.calls += 1
            call_number = self.calls
        if call_number == 1:
            self.entered.set()
            released = await asyncio.to_thread(self.release_old.wait, 20)
            if not released:
                raise RuntimeError("synthetic old provider gate timed out")
        data = {
            "suggested_category": "Other Emergency",
            "summary": "Smoke visible at the north entrance",
            "factual_details": [
                {"statement": "Smoke visible", "source_quote": "Smoke visible"}
            ],
            "hazards_to_verify": [],
            "missing_information": ["Number of people affected, if known"],
            "urgency_indicators": [],
            "explanation": "The report describes smoke.",
            "confidence_note": "Not independently calibrated.",
            "human_review_required": True,
        }
        return ProviderOutput(
            data=data,
            model="mock-old-result" if call_number == 1 else "mock-retry-result",
            usage_tokens=5,
            http_status_code=200,
        )


def test_late_pre_retry_task_cannot_overwrite_http_retry_result(client, monkeypatch):
    incident_id = _incident()
    _, admin_token = _identity(role="super_admin")
    provider = _RetryRaceProvider()
    monkeypatch.setattr(
        intelligence,
        "get_settings",
        lambda: Settings(
            environment="test",
            ai_provider="openrouter",
            openrouter_api_key="synthetic-key-not-used",
            ai_max_attempts=1,
            _env_file=None,
        ),
    )
    monkeypatch.setattr(intelligence, "_configured_provider", lambda _settings: provider)
    _install_provider_guards(monkeypatch)
    task_errors = []

    def run_old_task():
        try:
            asyncio.run(analyze_incident_task(incident_id))
        except BaseException as exc:
            task_errors.append(type(exc).__name__)

    old_thread = threading.Thread(target=run_old_task)
    old_thread.start()
    try:
        assert provider.entered.wait(10), "old task did not reach mocked provider"
        with SessionLocal.begin() as db:
            analysis = db.get(IncidentAnalysis, incident_id)
            old_token = analysis.claim_token
            assert analysis.status == "processing"
            assert old_token
            analysis.last_attempt_at = now_utc() - timedelta(minutes=2)

        response = client.post(
            f"/api/v1/admin/incidents/{incident_id}/analysis/retry",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 202, response.text
        retry_result = _analysis_state(incident_id)
        assert retry_result["status"] == "ready"
        assert retry_result["provider"] == "mock_retry_race"
        assert retry_result["model"] == "mock-retry-result"
        assert retry_result["claim_token"] is None

        provider.release_old.set()
        old_thread.join(timeout=15)
        assert not old_thread.is_alive()
        assert task_errors == []
    finally:
        provider.release_old.set()
        old_thread.join(timeout=15)

    final = _analysis_state(incident_id)
    assert provider.calls == 2
    assert final == retry_result
    with SessionLocal() as db:
        assert db.query(AuditEvent).filter_by(
            action="incident.analysis_completed", entity_id=incident_id
        ).count() == 1
