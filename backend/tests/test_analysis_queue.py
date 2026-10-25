import asyncio
import multiprocessing
import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import sessionmaker

from fastapi.testclient import TestClient

from app import api, database as app_database, intelligence, main as app_main
from app.config import Settings
from app.database import Base, SessionLocal, build_engine
from app.intelligence import ProviderOutput, ProviderTransientError
from app.models import AuditEvent, Incident, IncidentAnalysis, User, now_utc
from app.security import hash_password, issue_token


@pytest.fixture
def analysis_sessions(monkeypatch):
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(intelligence, "SessionLocal", sessions)
    try:
        yield sessions
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def race_database(tmp_path):
    database_path = (tmp_path / "phase10-analysis-race.sqlite3").resolve()
    assert database_path.parent == tmp_path.resolve()
    database_url = f"sqlite:///{database_path}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield database_url, database_path, engine, sessions
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
        for suffix in ("", "-journal", "-wal", "-shm"):
            os.unlink(f"{database_path}{suffix}") if os.path.exists(
                f"{database_path}{suffix}"
            ) else None


def _queued_incident(
    db, *, status="pending", attempts=0, last_attempt_at=None, claim_token=None
):
    suffix = uuid4().hex
    reporter = User(
        email=f"{suffix}@example.test",
        display_name="Queue test user",
        password_hash="unused",
        role="user",
    )
    db.add(reporter)
    db.flush()
    incident = Incident(
        reference=f"ECS-{suffix[:8].upper()}",
        reporter_id=reporter.id,
        emergency_type="Other Emergency",
        description="Smoke visible at the north entrance",
        location_label="North entrance",
        location_source="manual",
        severity=2,
        urgency=2,
        priority="Low",
        priority_reason="queue test",
        status="Unassigned",
        idempotency_key=f"analysis-{suffix}",
    )
    db.add(incident)
    db.flush()
    db.add(
        IncidentAnalysis(
            incident_id=incident.id,
            status=status,
            attempt_count=attempts,
            claim_token=claim_token,
            last_attempt_at=last_attempt_at,
        )
    )
    db.flush()
    return incident.id


def _install_mock_provider(monkeypatch, provider):
    settings = Settings(
        environment="test",
        ai_provider="openrouter",
        openrouter_api_key="synthetic-test-key-not-used",
        ai_max_attempts=1,
        _env_file=None,
    )
    monkeypatch.setattr(intelligence, "get_settings", lambda: settings)
    monkeypatch.setattr(intelligence, "OpenRouterProvider", lambda: provider)


def _valid_analysis():
    return {
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


class MockProvider:
    name = "openrouter"

    def __init__(self, *, data=None, error=None):
        self.data = data
        self.error = error
        self.calls = 0

    async def analyze(self, _incident, _settings):
        self.calls += 1
        if self.error:
            raise self.error
        return ProviderOutput(
            data=self.data,
            model="google/gemma-4-31b-it",
            usage_tokens=23,
            http_status_code=200,
            completion_id="mock-completion-001",
            finish_reason="stop",
        )


def _race_analysis(summary, evidence_quote):
    return {
        "suggested_category": "Other Emergency",
        "summary": summary,
        "factual_details": [
            {"statement": evidence_quote, "source_quote": evidence_quote}
        ],
        "hazards_to_verify": [],
        "missing_information": ["Number of people affected, if known"],
        "urgency_indicators": [],
        "explanation": "The report provides the quoted detail.",
        "confidence_note": "Not independently calibrated.",
        "human_review_required": True,
    }


class _RaceProvider:
    name = "mock_provider"

    def __init__(
        self,
        calls,
        summary,
        evidence_quote,
        entered=None,
        release=None,
        failure=False,
        on_invocation=None,
    ):
        self.calls = calls
        self.summary = summary
        self.evidence_quote = evidence_quote
        self.entered = entered
        self.release = release
        self.failure = failure
        self.on_invocation = on_invocation

    async def analyze(self, _incident, _settings):
        with self.calls.get_lock():
            self.calls.value += 1
        if self.entered is not None:
            self.entered.set()
        if self.release is not None and not self.release.wait(20):
            raise RuntimeError("mock provider gate timed out")
        if self.on_invocation is not None:
            self.on_invocation()
        if self.failure:
            raise RuntimeError("controlled mock provider failure")
        return ProviderOutput(
            data=_race_analysis("Smoke visible at the north entrance", "Smoke visible"),
            model=self.summary,
            usage_tokens=11,
            http_status_code=200,
        )


def _forbid_network(*_args, **_kwargs):
    raise AssertionError("provider HTTP boundary must not be reached in race tests")


def _multiprocess_task(
    database_url,
    incident_id,
    calls,
    summary,
    evidence_quote,
    start_barrier,
    provider_entered,
    provider_release,
    task_finished,
    provider_failure,
    persistence_ready,
    persistence_release,
    results,
):
    engine = build_engine(database_url)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    intelligence.SessionLocal = sessions
    settings = Settings(environment="test", ai_provider="none", _env_file=None)
    intelligence.get_settings = lambda: settings
    intelligence._configured_provider = lambda _settings: _RaceProvider(
        calls,
        summary,
        evidence_quote,
        provider_entered,
        provider_release,
        provider_failure,
    )
    intelligence.httpx.AsyncClient = _forbid_network
    intelligence.urlopen = _forbid_network
    if persistence_ready is not None:
        real_analyze = intelligence.analyze_incident_payload

        async def gated_analyze(payload):
            outcome = await real_analyze(payload)
            persistence_ready.set()
            if not persistence_release.wait(20):
                raise RuntimeError("persistence gate timed out")
            return outcome

        intelligence.analyze_incident_payload = gated_analyze
    try:
        if start_barrier is not None:
            start_barrier.wait(timeout=20)
        asyncio.run(intelligence.analyze_incident_task(incident_id))
        results.put(("ok", os.getpid()))
    except BaseException as exc:
        results.put(("error", os.getpid(), type(exc).__name__))
    finally:
        if task_finished is not None:
            task_finished.set()
        engine.dispose()


def _join_process(process):
    process.join(timeout=20)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        pytest.fail("race-test process did not finish within its event gates")


def _assert_process_result(results, process):
    assert process.exitcode == 0
    result = results.get(timeout=5)
    assert result == ("ok", process.pid)


def _race_process(
    context,
    database_url,
    incident_id,
    calls,
    label,
    *,
    barrier=None,
    entered=None,
    release=None,
    failure=False,
    persistence_ready=None,
    persistence_release=None,
):
    results = context.Queue()
    process = context.Process(
        target=_multiprocess_task,
        args=(
            database_url,
            incident_id,
            calls,
            f"{label} result",
            f"{label} evidence",
            barrier,
            entered,
            release,
            None,
            failure,
            persistence_ready,
            persistence_release,
            results,
        ),
    )
    return process, results, None


def _race_row(sessions, incident_id):
    with sessions() as db:
        job = db.get(IncidentAnalysis, incident_id)
        return {
            "status": job.status,
            "provider": job.provider,
            "model": job.model,
            "claim_token": job.claim_token,
            "attempt_count": job.attempt_count,
            "summary": job.result["summary"] if job.result else None,
            "validation_outcome": job.validation_outcome,
            "last_error_type": job.last_error_type,
        }


def test_persisted_pending_analysis_is_claimed_and_completed(analysis_sessions):
    with analysis_sessions.begin() as db:
        incident_id = _queued_incident(db)

    assert intelligence.next_pending_analysis_job() == incident_id
    asyncio.run(intelligence.analyze_incident_task(incident_id))

    with analysis_sessions() as db:
        job = db.get(IncidentAnalysis, incident_id)
        assert job.status == "ready"
        assert job.attempt_count == 1
        assert job.provider == "rules_baseline"


def test_analysis_task_persists_validated_provider_result(analysis_sessions, monkeypatch):
    with analysis_sessions.begin() as db:
        incident_id = _queued_incident(db)

    provider = MockProvider(data=_valid_analysis())
    _install_mock_provider(monkeypatch, provider)

    asyncio.run(intelligence.analyze_incident_task(incident_id))

    assert provider.calls == 1
    with analysis_sessions() as db:
        assert db.get(Incident, incident_id) is not None
        job = db.get(IncidentAnalysis, incident_id)
        assert job.status == "ready"
        assert job.attempt_count == 1
        assert job.provider == "openrouter"
        assert job.model == "google/gemma-4-31b-it"
        assert job.validation_outcome == "validated"
        assert job.usage_tokens == 23
        assert job.last_error_type is None
        assert job.claim_token is None
        assert job.result["summary"] == "Smoke visible at the north entrance"
        assert job.result["human_review_required"] is True
        assert job.result["explanation"] == (
            "Model output is advisory. Verify every detail against the original report."
        )
        assert job.result["confidence_note"] == "Not independently calibrated."
        assert job.completed_at is not None
        audit_event = db.query(AuditEvent).filter_by(
            action="incident.analysis_completed", entity_id=incident_id
        ).one()
        assert audit_event.details["provider"] == "openrouter"
        assert audit_event.details["validation_outcome"] == "validated"


def test_analysis_task_persists_deterministic_fallback_after_provider_failure(
    analysis_sessions, monkeypatch
):
    provider = MockProvider(
        error=ProviderTransientError(retry_after=0, status_code=503)
    )
    _install_mock_provider(monkeypatch, provider)
    with analysis_sessions.begin() as db:
        incident_id = _queued_incident(db)

    asyncio.run(intelligence.analyze_incident_task(incident_id))

    assert provider.calls == 1
    with analysis_sessions() as db:
        assert db.get(Incident, incident_id) is not None
        job = db.get(IncidentAnalysis, incident_id)
        assert job.status == "ready"
        assert job.attempt_count == 1
        assert job.provider == "rules_baseline"
        assert job.model is None
        assert job.validation_outcome == "transient_provider_failure"
        assert job.last_error_type == "ProviderTransientError"
        assert job.claim_token is None
        assert job.result["summary"] == "Smoke visible at the north entrance"
        assert job.result["confidence_note"].startswith("Rules-based")
        audit_event = db.query(AuditEvent).filter_by(
            action="incident.analysis_completed", entity_id=incident_id
        ).one()
        assert audit_event.details["provider"] == "rules_baseline"
        assert audit_event.details["validation_outcome"] == "transient_provider_failure"
        assert audit_event.details["provider_error_category"] == "ProviderTransientError"


def test_analysis_task_rejects_malformed_provider_output_and_persists_fallback(
    analysis_sessions, monkeypatch
):
    provider = MockProvider(data={"summary": "Invented responders are on scene"})
    _install_mock_provider(monkeypatch, provider)
    with analysis_sessions.begin() as db:
        incident_id = _queued_incident(db)

    asyncio.run(intelligence.analyze_incident_task(incident_id))

    assert provider.calls == 1
    with analysis_sessions() as db:
        job = db.get(IncidentAnalysis, incident_id)
        assert job.status == "ready"
        assert job.provider == "rules_baseline"
        assert job.model is None
        assert job.validation_outcome == "invalid_or_unavailable"
        assert job.last_error_type == "invalid_or_unavailable"
        assert job.result["summary"] == "Smoke visible at the north entrance"
        assert job.result["human_review_required"] is True
        assert "Invented responders are on scene" not in str(job.result)


@pytest.mark.parametrize(
    ("provider_error", "expected_outcome", "expected_provider"),
    [
        (False, "validated", "openrouter"),
        (True, "transient_provider_failure", "rules_baseline"),
    ],
)
def test_polling_worker_dispatches_real_task_and_persists_result(
    analysis_sessions, monkeypatch, provider_error, expected_outcome, expected_provider
):
    """Exercise one real poll/dispatch/task cycle without a provider boundary."""
    provider = MockProvider(
        data=_valid_analysis() if not provider_error else None,
        error=(
            ProviderTransientError(retry_after=0, status_code=503)
            if provider_error
            else None
        ),
    )
    _install_mock_provider(monkeypatch, provider)
    monkeypatch.setattr(intelligence.httpx, "AsyncClient", _forbid_network)
    monkeypatch.setattr(intelligence, "urlopen", _forbid_network)
    with analysis_sessions.begin() as db:
        incident_id = _queued_incident(db)

    real_next_pending = intelligence.next_pending_analysis_job
    polls = 0

    def next_pending_then_stop():
        nonlocal polls
        polls += 1
        if polls == 1:
            return real_next_pending()
        raise asyncio.CancelledError

    monkeypatch.setattr(
        intelligence, "next_pending_analysis_job", next_pending_then_stop
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(intelligence.run_analysis_recovery_worker())

    assert polls == 2
    assert provider.calls == 1
    with analysis_sessions() as db:
        job = db.get(IncidentAnalysis, incident_id)
        assert job.status == "ready"
        assert job.provider == expected_provider
        assert job.validation_outcome == expected_outcome
        assert job.claim_token is None
        assert job.completed_at is not None
        if provider_error:
            assert job.result["confidence_note"].startswith("Rules-based")
        else:
            assert job.result["summary"] == "Smoke visible at the north entrance"
        assert db.query(AuditEvent).filter_by(
            action="incident.analysis_completed", entity_id=incident_id
        ).count() == 1


@pytest.mark.parametrize(
    ("failure", "expected_provider", "expected_outcome", "expected_error"),
    [
        (False, "openrouter", "validated", None),
        (True, "rules_baseline", "transient_provider_failure", "ProviderTransientError"),
    ],
)
def test_incident_submission_schedules_real_analysis_task(
    client,
    monkeypatch,
    failure,
    expected_provider,
    expected_outcome,
    expected_error,
):
    provider = MockProvider(
        data=_valid_analysis(),
        error=(
            ProviderTransientError(retry_after=0, status_code=503)
            if failure
            else None
        ),
    )
    _install_mock_provider(monkeypatch, provider)
    real_task = intelligence.analyze_incident_task
    observed_before_task = []

    async def observe_committed_state_then_run(incident_id):
        with SessionLocal() as db:
            incident = db.get(Incident, incident_id)
            job = db.get(IncidentAnalysis, incident_id)
            observed_before_task.append(
                (incident is not None, job.status if job else None)
            )
        await real_task(incident_id)

    # The router still schedules through FastAPI BackgroundTasks. This wrapper
    # observes the committed pre-task state and delegates to the real task.
    monkeypatch.setattr(api, "analyze_incident_task", observe_committed_state_then_run)

    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": "task-integration@example.com",
            "display_name": "Synthetic Caller",
            "password": "SyntheticPassword-1234",
        },
    )
    assert registration.status_code == 201
    token = registration.json()["access_token"]
    response = client.post(
        "/api/v1/user/incidents",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "task-integration-key-001",
        },
        json={
            "emergency_type": "Other Emergency",
            "description": "Smoke visible at the north entrance",
            "location_label": "Synthetic test location",
            "location_source": "manual",
            "severity": 2,
            "urgency": 2,
        },
    )

    assert response.status_code == 201, response.text
    incident_id = response.json()["id"]
    assert observed_before_task == [(True, "pending")]
    assert provider.calls == 1

    with SessionLocal() as db:
        incident = db.get(Incident, incident_id)
        job = db.get(IncidentAnalysis, incident_id)
        assert incident is not None
        assert incident.status == "Unassigned"
        assert job.status == "ready"
        assert job.provider == expected_provider
        assert job.validation_outcome == expected_outcome
        assert job.last_error_type == expected_error
        if failure:
            assert job.model is None
            assert job.result["summary"] == incident.description
            assert job.result["confidence_note"].startswith("Rules-based")
        else:
            assert job.model == "google/gemma-4-31b-it"
            assert job.result["summary"] == incident.description
            assert job.result["explanation"] == (
                "Model output is advisory. Verify every detail against the original report."
            )


def test_abandoned_analysis_is_recovered_and_exhausted_jobs_are_stopped(
    analysis_sessions,
):
    stale = now_utc() - timedelta(minutes=6)
    with analysis_sessions.begin() as db:
        recoverable_id = _queued_incident(
            db,
            status="processing",
            attempts=1,
            last_attempt_at=stale,
            claim_token=str(uuid4()),
        )
        exhausted_id = _queued_incident(
            db,
            status="processing",
            attempts=3,
            last_attempt_at=stale,
            claim_token=str(uuid4()),
        )

    assert intelligence.next_pending_analysis_job() == recoverable_id
    with analysis_sessions() as db:
        recoverable = db.get(IncidentAnalysis, recoverable_id)
        exhausted = db.get(IncidentAnalysis, exhausted_id)
        assert recoverable.status == "pending"
        assert recoverable.validation_outcome == "recovered_after_restart"
        assert recoverable.claim_token is None
        assert exhausted.status == "unavailable"
        assert exhausted.validation_outcome == "retries_exhausted"
        assert exhausted.claim_token is None


def test_multiprocess_pending_claim_calls_provider_once(race_database):
    database_url, database_path, engine, sessions = race_database
    assert database_path == Path(database_url.removeprefix("sqlite:///")).resolve()
    with sessions.begin() as db:
        incident_id = _queued_incident(db)

    context = multiprocessing.get_context("spawn")
    calls = context.Value("i", 0)
    barrier = context.Barrier(2)
    processes = [
        _race_process(
            context,
            database_url,
            incident_id,
            calls,
            f"worker-{number}",
            barrier=barrier,
        )
        for number in range(2)
    ]
    try:
        for process, _, _ in processes:
            process.start()
        for process, results, _ in processes:
            _join_process(process)
            _assert_process_result(results, process)
    finally:
        for process, result_queue, _ in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            result_queue.close()
            result_queue.join_thread()

    assert len({process.pid for process, _, _ in processes}) == 2
    assert calls.value == 1
    row = _race_row(sessions, incident_id)
    assert row["status"] == "ready"
    assert row["provider"] == "mock_provider"
    assert row["model"] in ("worker-0 result", "worker-1 result")
    assert row["attempt_count"] == 1
    assert row["summary"] == "Smoke visible at the north entrance"
    assert row["validation_outcome"] == "validated"
    with sessions() as db:
        assert db.query(AuditEvent).filter_by(
            action="incident.analysis_completed", entity_id=incident_id
        ).count() == 1


@pytest.mark.parametrize(
    ("release_order", "original_failure", "recovered_failure"),
    [
        ("recovered_first", False, False),
        ("original_first", False, False),
        ("recovered_first", True, False),
        ("recovered_first", False, True),
    ],
)
def test_stale_recovery_invalidates_inflight_attempt(
    race_database, release_order, original_failure, recovered_failure
):
    database_url, _, _, sessions = race_database
    with sessions.begin() as db:
        incident_id = _queued_incident(db)

    context = multiprocessing.get_context("spawn")
    calls = context.Value("i", 0)
    first_entered, first_release = context.Event(), context.Event()
    first, first_results, _ = _race_process(
        context,
        database_url,
        incident_id,
        calls,
        "original",
        entered=first_entered,
        release=first_release,
        failure=original_failure,
    )
    second_entered, second_release = context.Event(), context.Event()
    second, second_results, _ = _race_process(
        context,
        database_url,
        incident_id,
        calls,
        "recovered",
        entered=second_entered,
        release=second_release,
        failure=recovered_failure,
    )
    try:
        first.start()
        assert first_entered.wait(15), "original task did not reach mocked provider"
        original_token = _race_row(sessions, incident_id)["claim_token"]
        assert original_token
        with sessions.begin() as db:
            job = db.get(IncidentAnalysis, incident_id)
            job.last_attempt_at = now_utc() - timedelta(minutes=6)

        monkeypatch_sessions = intelligence.SessionLocal
        intelligence.SessionLocal = sessions
        try:
            assert intelligence.next_pending_analysis_job() == incident_id
        finally:
            intelligence.SessionLocal = monkeypatch_sessions
        recovered_row = _race_row(sessions, incident_id)
        assert recovered_row["status"] == "pending"
        assert recovered_row["claim_token"] is None

        second.start()
        assert second_entered.wait(15), "recovered task did not reach mocked provider"
        recovered_token = _race_row(sessions, incident_id)["claim_token"]
        assert recovered_token
        assert recovered_token != original_token
        if release_order == "recovered_first":
            second_release.set()
            _join_process(second)
            _assert_process_result(second_results, second)
            first_release.set()
            _join_process(first)
            _assert_process_result(first_results, first)
            expected_model = "recovered result"
        else:
            first_release.set()
            _join_process(first)
            _assert_process_result(first_results, first)
            second_release.set()
            _join_process(second)
            _assert_process_result(second_results, second)
            expected_model = "recovered result"
    finally:
        first_release.set()
        second_release.set()
        for process in (first, second):
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        for result_queue in (first_results, second_results):
            result_queue.close()
            result_queue.join_thread()

    assert calls.value == 2
    row = _race_row(sessions, incident_id)
    if recovered_failure:
        assert row == {
            "status": "ready",
            "provider": "rules_baseline",
            "model": None,
            "claim_token": None,
            "attempt_count": 2,
            "summary": "Smoke visible at the north entrance",
            "validation_outcome": "invalid_or_unavailable",
            "last_error_type": "invalid_or_unavailable",
        }
    else:
        assert row == {
            "status": "ready",
            "provider": "mock_provider",
            "model": expected_model,
            "claim_token": None,
            "attempt_count": 2,
            "summary": "Smoke visible at the north entrance",
            "validation_outcome": "validated",
            "last_error_type": None,
        }
    with sessions() as db:
        assert db.query(AuditEvent).filter_by(
            action="incident.analysis_completed", entity_id=incident_id
        ).count() == 1


def test_recovery_winning_before_final_update_rejects_result_and_audit(race_database):
    database_url, _, _, sessions = race_database
    with sessions.begin() as db:
        incident_id = _queued_incident(db)

    context = multiprocessing.get_context("spawn")
    calls = context.Value("i", 0)
    persistence_ready, persistence_release = context.Event(), context.Event()
    process, results, _ = _race_process(
        context,
        database_url,
        incident_id,
        calls,
        "obsolete",
        persistence_ready=persistence_ready,
        persistence_release=persistence_release,
    )
    try:
        process.start()
        assert persistence_ready.wait(15), "task did not reach the final persistence gate"
        old_token = _race_row(sessions, incident_id)["claim_token"]
        assert old_token
        with sessions.begin() as db:
            db.get(IncidentAnalysis, incident_id).last_attempt_at = (
                now_utc() - timedelta(minutes=6)
            )

        monkeypatch_sessions = intelligence.SessionLocal
        intelligence.SessionLocal = sessions
        try:
            assert intelligence.next_pending_analysis_job() == incident_id
        finally:
            intelligence.SessionLocal = monkeypatch_sessions

        recovered = _race_row(sessions, incident_id)
        assert recovered["status"] == "pending"
        assert recovered["claim_token"] is None
        persistence_release.set()
        _join_process(process)
        _assert_process_result(results, process)
    finally:
        persistence_release.set()
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        results.close()
        results.join_thread()

    assert calls.value == 1
    with sessions() as db:
        job = db.get(IncidentAnalysis, incident_id)
        assert job.status == "pending"
        assert job.claim_token is None
        assert job.result is None
        assert db.query(AuditEvent).filter_by(
            action="incident.analysis_completed", entity_id=incident_id
        ).count() == 0


def test_authenticated_admin_retry_can_overlap_inflight_task(
    race_database, monkeypatch
):
    database_url, _, engine, sessions = race_database
    with sessions() as db:
        incident_id = _queued_incident(db)
        admin = User(
            email="race-admin@example.test",
            display_name="Race Test Admin",
            password_hash=hash_password("SyntheticPassword-1234"),
            role="super_admin",
        )
        db.add(admin)
        db.commit()
        token, _, _, _ = issue_token(admin, db)

    monkeypatch.setattr(app_database, "SessionLocal", sessions)
    monkeypatch.setattr(intelligence, "SessionLocal", sessions)
    monkeypatch.setattr(app_main, "engine", engine)
    monkeypatch.setattr(
        app_main,
        "settings",
        Settings(
            environment="test",
            database_url=database_url,
            ai_provider="none",
            _env_file=None,
        ),
    )

    def isolated_db():
        with sessions() as db:
            yield db

    monkeypatch.setitem(app_main.app.dependency_overrides, app_database.get_db, isolated_db)
    context = multiprocessing.get_context("spawn")
    calls = context.Value("i", 0)
    first_entered, first_release = context.Event(), context.Event()
    first, first_results, _ = _race_process(
        context,
        database_url,
        incident_id,
        calls,
        "original",
        entered=first_entered,
        release=first_release,
    )
    try:
        first.start()
        assert first_entered.wait(15), "original task did not reach mocked provider"
        original_token = _race_row(sessions, incident_id)["claim_token"]
        assert original_token
        with sessions.begin() as db:
            job = db.get(IncidentAnalysis, incident_id)
            job.last_attempt_at = now_utc() - timedelta(seconds=91)

        retry_tokens = []
        provider = _RaceProvider(
            calls,
            "retry result",
            "retry evidence",
            on_invocation=lambda: retry_tokens.append(
                _race_row(sessions, incident_id)["claim_token"]
            ),
        )
        monkeypatch.setattr(intelligence, "SessionLocal", sessions)
        monkeypatch.setattr(intelligence, "_configured_provider", lambda _settings: provider)
        monkeypatch.setattr(intelligence, "get_settings", lambda: Settings(
            environment="test", ai_provider="none", _env_file=None
        ))
        monkeypatch.setattr(intelligence.httpx, "AsyncClient", _forbid_network)
        monkeypatch.setattr(intelligence, "urlopen", _forbid_network)
        with TestClient(app_main.app) as client:
            response = client.post(
                f"/api/v1/admin/incidents/{incident_id}/analysis/retry",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 202, response.text
        assert calls.value == 2
        assert len(retry_tokens) == 1
        assert retry_tokens[0]
        assert retry_tokens[0] != original_token
        assert _race_row(sessions, incident_id) == {
            "status": "ready",
            "provider": "mock_provider",
            "model": "retry result",
            "claim_token": None,
            "attempt_count": 1,
            "summary": "Smoke visible at the north entrance",
            "validation_outcome": "validated",
            "last_error_type": None,
        }

        first_release.set()
        _join_process(first)
        _assert_process_result(first_results, first)
        assert _race_row(sessions, incident_id)["model"] == "retry result"
        with sessions() as db:
            assert db.query(AuditEvent).filter_by(
                action="incident.analysis_completed", entity_id=incident_id
            ).count() == 1
    finally:
        first_release.set()
        if first.is_alive():
            first.terminate()
            first.join(timeout=5)
        first_results.close()
        first_results.join_thread()
