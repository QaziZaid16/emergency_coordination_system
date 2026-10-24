from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base, build_engine
from app.models import Assignment, Incident, Resource, User


def test_concurrent_assignments_cannot_claim_one_incident_twice(tmp_path):
    """Exercise the active-assignment partial unique index using independent sessions."""
    engine = build_engine(f"sqlite:///{tmp_path / 'assignment-race.db'}")
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with sessions.begin() as db:
            reporter = User(email="reporter@example.com", display_name="Reporter", password_hash="unused", role="user")
            coordinator = User(email="coordinator@example.com", display_name="Coordinator", password_hash="unused", role="super_admin")
            responders = [
                User(email=f"responder-{number}@example.com", display_name=f"Responder {number}", password_hash="unused", role="responder")
                for number in (1, 2)
            ]
            db.add_all([reporter, coordinator, *responders])
            db.flush()
            incident = Incident(
                reference="ECS-RACE01",
                reporter_id=reporter.id,
                emergency_type="Medical",
                description="Concurrent assignment test",
                location_label="Test location",
                location_source="manual",
                severity=3,
                urgency=3,
                priority="Medium",
                priority_reason="Test fixture",
                status="Unassigned",
                idempotency_key="race-test-key-0001",
            )
            db.add(incident)
            db.flush()
            incident_id, coordinator_id = incident.id, coordinator.id
            responder_ids = [responder.id for responder in responders]

        start = Barrier(2)

        def attempt(responder_id):
            with sessions() as db:
                start.wait(timeout=5)
                db.add(Assignment(
                    incident_id=incident_id,
                    responder_id=responder_id,
                    assigned_by=coordinator_id,
                    status="Assigned",
                ))
                try:
                    db.commit()
                    return "committed"
                except IntegrityError:
                    db.rollback()
                    return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, responder_ids))

        assert sorted(results) == ["committed", "conflict"]
        with sessions() as db:
            active_count = db.scalar(
                select(func.count(Assignment.id)).where(
                    Assignment.incident_id == incident_id,
                    Assignment.status.in_(("Assigned", "Accepted", "En Route", "On Scene")),
                )
            )
        assert active_count == 1
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_concurrent_reservations_cannot_exceed_resource_capacity(tmp_path):
    """Verify the capacity predicate and increment are one atomic database update."""
    engine = build_engine(f"sqlite:///{tmp_path / 'resource-race.db'}")
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with sessions.begin() as db:
            resource = Resource(name="Single response unit", kind="ambulance", quantity=1, allocated=0, active=True)
            db.add(resource)
            db.flush()
            resource_id = resource.id

        start = Barrier(2)

        def reserve_once(_worker):
            with sessions() as db:
                start.wait(timeout=5)
                result = db.execute(
                    update(Resource)
                    .where(Resource.id == resource_id, Resource.allocated < Resource.quantity)
                    .values(allocated=Resource.allocated + 1)
                )
                db.commit()
                return result.rowcount

        with ThreadPoolExecutor(max_workers=2) as pool:
            row_counts = list(pool.map(reserve_once, (1, 2)))

        assert sorted(row_counts) == [0, 1]
        with sessions() as db:
            resource = db.get(Resource, resource_id)
            assert resource.allocated == 1
            assert resource.allocated <= resource.quantity
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
