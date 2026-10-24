import asyncio
from datetime import timedelta
from uuid import uuid4

from sqlalchemy.orm import sessionmaker

from app import intelligence
from app.database import Base, build_engine
from app.models import Incident, IncidentAnalysis, User, now_utc


def _queued_incident(db, *, status="pending", attempts=0, last_attempt_at=None):
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
            last_attempt_at=last_attempt_at,
        )
    )
    db.flush()
    return incident.id


def test_persisted_pending_analysis_is_claimed_and_completed(tmp_path, monkeypatch):
    engine = build_engine(f"sqlite:///{tmp_path / 'analysis-queue.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(intelligence, "SessionLocal", sessions)
    try:
        with sessions.begin() as db:
            incident_id = _queued_incident(db)

        assert intelligence.next_pending_analysis_job() == incident_id
        asyncio.run(intelligence.analyze_incident_task(incident_id))

        with sessions() as db:
            job = db.get(IncidentAnalysis, incident_id)
            assert job.status == "ready"
            assert job.attempt_count == 1
            assert job.provider == "rules_baseline"
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_abandoned_analysis_is_recovered_and_exhausted_jobs_are_stopped(
    tmp_path, monkeypatch
):
    engine = build_engine(f"sqlite:///{tmp_path / 'analysis-recovery.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(intelligence, "SessionLocal", sessions)
    stale = now_utc() - timedelta(minutes=6)
    try:
        with sessions.begin() as db:
            recoverable_id = _queued_incident(
                db, status="processing", attempts=1, last_attempt_at=stale
            )
            exhausted_id = _queued_incident(
                db, status="processing", attempts=3, last_attempt_at=stale
            )

        assert intelligence.next_pending_analysis_job() == recoverable_id
        with sessions() as db:
            recoverable = db.get(IncidentAnalysis, recoverable_id)
            exhausted = db.get(IncidentAnalysis, exhausted_id)
            assert recoverable.status == "pending"
            assert recoverable.validation_outcome == "recovered_after_restart"
            assert exhausted.status == "unavailable"
            assert exhausted.validation_outcome == "retries_exhausted"
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
