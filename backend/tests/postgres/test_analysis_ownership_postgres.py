"""PostgreSQL-backed ownership tests; requires a migrated disposable target."""

import asyncio
import multiprocessing
import os
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

from app import api, intelligence
from app.config import Settings
from app.database import build_engine
from app.intelligence import ProviderOutput
from app.models import AuditEvent, Incident, IncidentAnalysis, User, now_utc


def _valid_provider_data():
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


class _PostgresMockProvider:
    name = "postgres_test_mock"

    def __init__(self, calls, label, entered=None, release=None, failure=False):
        self.calls = calls
        self.label = label
        self.entered = entered
        self.release = release
        self.failure = failure

    async def analyze(self, _incident, _settings):
        with self.calls.get_lock():
            self.calls.value += 1
        if self.entered is not None:
            self.entered.set()
        if self.release is not None and not self.release.wait(30):
            raise RuntimeError("synthetic provider gate timed out")
        if self.failure:
            raise RuntimeError("synthetic provider failure")
        return ProviderOutput(
            data=_valid_provider_data(),
            model=f"mock-{self.label}",
            usage_tokens=7,
            http_status_code=200,
        )


def _deny_provider_network(*_args, **_kwargs):
    raise AssertionError("provider network boundary reached in PostgreSQL ownership test")


def _postgres_task_process(
    incident_id,
    calls,
    label,
    start_barrier,
    entered,
    release,
    failure,
    results,
):
    database_url = os.environ["DATABASE_URL"]
    engine = build_engine(database_url)
    intelligence.SessionLocal = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    intelligence.get_settings = lambda: Settings(
        environment="test", ai_provider="none", _env_file=None
    )
    intelligence._configured_provider = lambda _settings: _PostgresMockProvider(
        calls, label, entered=entered, release=release, failure=failure
    )
    intelligence.httpx.AsyncClient = _deny_provider_network
    intelligence.urlopen = _deny_provider_network
    try:
        if start_barrier is not None:
            start_barrier.wait(timeout=30)
        asyncio.run(intelligence.analyze_incident_task(incident_id))
        results.put(("ok", os.getpid()))
    except BaseException as exc:
        results.put(("error", os.getpid(), type(exc).__name__))
    finally:
        engine.dispose()


def _start_process(context, incident_id, calls, label, *, barrier=None,
                   entered=None, release=None, failure=False, results=None):
    results = results if results is not None else context.Queue()
    process = context.Process(
        target=_postgres_task_process,
        args=(incident_id, calls, label, barrier, entered, release,
              failure, results),
    )
    process.start()
    return process, results


def _join_process(process, results):
    process.join(timeout=30)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        pytest.fail("PostgreSQL task process did not finish within its event gates")
    assert process.exitcode == 0
    assert results.get(timeout=5) == ("ok", process.pid)
    results.close()
    results.join_thread()


def _new_incident(db):
    suffix = uuid4().hex
    reporter = User(
        email=f"pg-{suffix}@example.test",
        display_name="PostgreSQL ownership test",
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
        location_label="Synthetic PostgreSQL test location",
        location_source="manual",
        severity=2,
        urgency=2,
        priority="Low",
        priority_reason="isolated ownership test",
        status="Unassigned",
        idempotency_key=f"pg-analysis-{suffix}",
    )
    db.add(incident)
    db.flush()
    db.add(IncidentAnalysis(incident_id=incident.id, status="pending"))
    db.flush()
    return incident.id, reporter.id


@pytest.fixture
def pg_incident(postgres_test_sessions):
    sessions = postgres_test_sessions
    with sessions.begin() as db:
        incident_id, reporter_id = _new_incident(db)
    yield incident_id, reporter_id
    with sessions.begin() as db:
        db.execute(delete(AuditEvent).where(AuditEvent.entity_id == incident_id))
        db.execute(delete(IncidentAnalysis).where(IncidentAnalysis.incident_id == incident_id))
        db.execute(delete(Incident).where(Incident.id == incident_id))
        db.execute(delete(User).where(User.id == reporter_id))


def _read_row(sessions, incident_id):
    with sessions() as db:
        job = db.get(IncidentAnalysis, incident_id)
        return {
            "status": job.status,
            "provider": job.provider,
            "model": job.model,
            "claim_token": job.claim_token,
            "attempt_count": job.attempt_count,
            "result": job.result,
            "validation_outcome": job.validation_outcome,
            "last_error_type": job.last_error_type,
        }


def _completion_count(sessions, incident_id):
    with sessions() as db:
        return db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.action == "incident.analysis_completed",
                AuditEvent.entity_id == incident_id,
            )
        )


def test_two_postgres_processes_compete_for_one_pending_claim(
    postgres_test_engine, postgres_test_sessions, pg_incident
):
    incident_id, _ = pg_incident
    context = multiprocessing.get_context("spawn")
    calls = context.Value("i", 0)
    barrier = context.Barrier(2)
    entered, release = context.Event(), context.Event()
    results = context.Queue()
    processes = [
        _start_process(
            context, incident_id, calls, f"claim-{i}", barrier=barrier,
            entered=entered, release=release, results=results,
        )
        for i in range(2)
    ]
    try:
        assert entered.wait(20), "no task reached the mocked provider"
        # The losing claim completes while the winning owner's provider call is gated.
        finished = results.get(timeout=20)
        if finished[0] != "ok":
            pytest.fail(f"claim process failed: {finished[2]}")
        loser = next(process for process, _ in processes if process.pid == finished[1])
        loser.join(timeout=20)
        assert loser.exitcode == 0
        assert calls.value == 1
        release.set()
        other = next(process for process, _ in processes if process.pid != finished[1])
        other.join(timeout=30)
        assert not other.is_alive()
        assert other.exitcode == 0
        assert results.get(timeout=5) == ("ok", other.pid)
    finally:
        release.set()
        for process, _process_results in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        results.close()
        results.join_thread()

    row = _read_row(postgres_test_sessions, incident_id)
    assert calls.value == 1
    assert row["status"] == "ready"
    assert row["provider"] == "postgres_test_mock"
    assert row["attempt_count"] == 1
    assert row["claim_token"] is None
    assert _completion_count(postgres_test_sessions, incident_id) == 1


@pytest.mark.parametrize(
    ("old_failure", "new_failure"),
    [(False, False), (True, False), (False, True), (True, True)],
    ids=("old-success-new-success", "old-failure-new-success",
         "old-success-new-fallback", "old-failure-new-fallback"),
)
def test_postgres_recovery_fences_late_success_and_failure(
    postgres_test_engine, postgres_test_sessions, pg_incident, monkeypatch,
    old_failure, new_failure,
):
    incident_id, _ = pg_incident
    sessions = postgres_test_sessions
    monkeypatch.setattr(intelligence, "SessionLocal", sessions)
    context = multiprocessing.get_context("spawn")
    calls = context.Value("i", 0)
    old_entered, old_release = context.Event(), context.Event()
    new_entered, new_release = context.Event(), context.Event()
    old, old_results = _start_process(
        context, incident_id, calls, "old", entered=old_entered,
        release=old_release, failure=old_failure,
    )
    new = new_results = None
    try:
        assert old_entered.wait(20), "old task did not reach the mocked provider"
        old_token = _read_row(sessions, incident_id)["claim_token"]
        assert old_token
        with sessions.begin() as db:
            db.get(IncidentAnalysis, incident_id).last_attempt_at = (
                now_utc() - timedelta(minutes=10)
            )
        dispatched_id = intelligence.next_pending_analysis_job()
        recovered_row = _read_row(sessions, incident_id)
        assert recovered_row["status"] == "pending"
        assert recovered_row["claim_token"] is None
        assert dispatched_id == incident_id, (
            f"recovered row was not selected (dispatch={dispatched_id!r}, "
            f"status={recovered_row['status']!r}, attempts={recovered_row['attempt_count']})"
        )

        new, new_results = _start_process(
            context, incident_id, calls, "current", entered=new_entered,
            release=new_release, failure=new_failure,
        )
        assert new_entered.wait(20), "recovered task did not reach mocked provider"
        current_token = _read_row(sessions, incident_id)["claim_token"]
        assert current_token and current_token != old_token
        new_release.set()
        _join_process(new, new_results)
        new = new_results = None
        old_release.set()
        _join_process(old, old_results)
        old = old_results = None
    finally:
        old_release.set()
        new_release.set()
        for process, results in ((old, old_results), (new, new_results)):
            if process is not None and process.is_alive():
                process.terminate()
                process.join(timeout=5)
            if results is not None:
                results.close()
                results.join_thread()

    row = _read_row(sessions, incident_id)
    assert calls.value == 2
    assert row["status"] == "ready"
    assert row["attempt_count"] == 2
    assert row["claim_token"] is None
    if new_failure:
        assert row["provider"] == "rules_baseline"
        assert row["model"] is None
        assert row["validation_outcome"] == "invalid_or_unavailable"
        assert row["result"]["summary"] == "Smoke visible at the north entrance"
    else:
        assert row["provider"] == "postgres_test_mock"
        assert row["model"] == "mock-current"
        assert row["validation_outcome"] == "validated"
    assert _completion_count(sessions, incident_id) == 1


@pytest.mark.parametrize("old_failure", [False, True], ids=["late-success", "late-failure"])
def test_postgres_manual_retry_invalidates_inflight_claim(
    postgres_test_engine, postgres_test_sessions, pg_incident, monkeypatch, old_failure
):
    incident_id, reporter_id = pg_incident
    sessions = postgres_test_sessions
    monkeypatch.setattr(intelligence, "SessionLocal", sessions)
    context = multiprocessing.get_context("spawn")
    calls = context.Value("i", 0)
    entered, release = context.Event(), context.Event()
    old, old_results = _start_process(
        context, incident_id, calls, "old", entered=entered,
        release=release, failure=old_failure,
    )
    try:
        assert entered.wait(20), "old task did not reach the mocked provider"
        old_token = _read_row(sessions, incident_id)["claim_token"]
        assert old_token
        with sessions.begin() as db:
            db.get(IncidentAnalysis, incident_id).last_attempt_at = (
                now_utc() - timedelta(minutes=2)
            )
            admin = db.get(User, reporter_id)

        retry_calls = []

        class RetryProvider:
            name = "postgres_retry_mock"

            async def analyze(self, _incident, _settings):
                with calls.get_lock():
                    calls.value += 1
                retry_calls.append(_read_row(sessions, incident_id)["claim_token"])
                return ProviderOutput(
                    data=_valid_provider_data(), model="mock-retry", usage_tokens=3
                )

        monkeypatch.setattr(intelligence, "get_settings", lambda: Settings(
            environment="test", ai_provider="none", _env_file=None
        ))
        monkeypatch.setattr(intelligence, "_configured_provider", lambda _s: RetryProvider())
        monkeypatch.setattr(intelligence.httpx, "AsyncClient", _deny_provider_network)
        monkeypatch.setattr(intelligence, "urlopen", _deny_provider_network)
        background = BackgroundTasks()
        with sessions() as db:
            response = api.retry_incident_analysis(
                incident_id, background, admin, db
            )
        assert response == {"incident_id": incident_id, "analysis_status": "pending"}
        retry_token = _read_row(sessions, incident_id)["claim_token"]
        assert retry_token is None  # endpoint invalidates before task claims
        asyncio.run(background())
        assert len(retry_calls) == 1
        assert retry_calls[0] and retry_calls[0] != old_token

        release.set()
        _join_process(old, old_results)
        old = old_results = None
    finally:
        release.set()
        if old is not None and old.is_alive():
            old.terminate()
            old.join(timeout=5)
        if old_results is not None:
            old_results.close()
            old_results.join_thread()

    row = _read_row(sessions, incident_id)
    assert calls.value == 2
    assert row["status"] == "ready"
    assert row["provider"] == "postgres_retry_mock"
    assert row["model"] == "mock-retry"
    assert row["attempt_count"] == 1
    assert _completion_count(sessions, incident_id) == 1
    with sessions() as db:
        retry_events = db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.action == "incident.analysis_retry_requested",
                AuditEvent.entity_id == incident_id,
            )
        )
    assert retry_events == 1


def test_postgres_claim_commit_rollback_and_fresh_session_visibility(
    postgres_test_sessions, pg_incident
):
    incident_id, _ = pg_incident
    sessions = postgres_test_sessions
    committed_token = str(uuid4())
    with sessions.begin() as db:
        job = db.get(IncidentAnalysis, incident_id)
        job.status = "processing"
        job.claim_token = committed_token
    assert _read_row(sessions, incident_id)["claim_token"] == committed_token

    with pytest.raises(RuntimeError, match="rollback sentinel"):
        with sessions.begin() as db:
            job = db.get(IncidentAnalysis, incident_id)
            job.status = "pending"
            job.claim_token = None
            raise RuntimeError("rollback sentinel")

    row = _read_row(sessions, incident_id)
    assert row["status"] == "processing"
    assert row["claim_token"] == committed_token
    with sessions.begin() as db:
        job = db.get(IncidentAnalysis, incident_id)
        job.status = "pending"
        job.claim_token = None
    assert _read_row(sessions, incident_id)["status"] == "pending"
