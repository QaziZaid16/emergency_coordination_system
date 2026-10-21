from datetime import datetime, timedelta, timezone
import re
import secrets
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dispatch import distance_km, priority_for
from app.models import Assignment, AuditEvent, AuthSession, Incident, IncidentAnalysis, IncidentUpdate, ResponderProfile, Resource, User, now_utc
from app.schemas import AssignmentCreate, AvailabilityUpdate, CopilotQuestion, IncidentCreate, LoginRequest, LoginResponse, MessageCreate, RefreshRequest, ResponderLocation, ResourceCreate, StatusUpdate, UserCreate, UserRegister, UserView
from app.intelligence import analyze_incident_task, find_duplicate_candidates
from app.security import bearer, current_user, encode_access_token, hash_password, hash_refresh_token, issue_token, require_roles, verify_password

router = APIRouter()
ACTIVE_ASSIGNMENTS = ("Assigned", "Accepted", "En Route", "On Scene")
RESPONDER_VISIBLE_ASSIGNMENTS = (*ACTIVE_ASSIGNMENTS, "Resolved", "Completed")
NEXT_STATUS = {"Assigned": "Accepted", "Accepted": "En Route", "En Route": "On Scene", "On Scene": "Resolved"}


def resource_matches_incident(kind: str, emergency_type: str) -> bool:
    normalized_kind = kind.casefold()
    normalized_type = emergency_type.casefold()
    if "medical" in normalized_type or "ambulance" in normalized_type:
        return any(term in normalized_kind for term in ("ambulance", "medical", "ems"))
    if "fire" in normalized_type or "rescue" in normalized_type:
        return any(term in normalized_kind for term in ("fire", "rescue", "engine"))
    if "police" in normalized_type or "security" in normalized_type:
        return any(term in normalized_kind for term in ("police", "security", "patrol"))
    return True


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def audit(db: Session, actor: User, action: str, entity_type: str, entity_id: str, details: dict | None = None):
    db.add(AuditEvent(actor_id=actor.id, action=action, entity_type=entity_type, entity_id=entity_id, details=details or {}))


def incident_view(db: Session, incident: Incident, include_analysis: bool = True) -> dict:
    assignment = db.scalar(select(Assignment).where(
        Assignment.incident_id == incident.id,
        Assignment.status.in_(RESPONDER_VISIBLE_ASSIGNMENTS),
    ).order_by(Assignment.assigned_at.desc()))
    responder = db.get(User, assignment.responder_id) if assignment else None
    resource = db.get(Resource, assignment.resource_id) if assignment and assignment.resource_id else None
    result = {
        "id": incident.id,
        "reference": incident.reference,
        "reporter_id": incident.reporter_id,
        "emergency_type": incident.emergency_type,
        "description": incident.description,
        "location_label": incident.location_label,
        "location_source": incident.location_source,
        "latitude": incident.latitude,
        "longitude": incident.longitude,
        "accuracy_m": incident.accuracy_m,
        "location_at": incident.location_at,
        "severity": incident.severity,
        "urgency": incident.urgency,
        "priority": incident.priority,
        "priority_reason": incident.priority_reason,
        "status": incident.status,
        "responder_id": responder.id if responder else None,
        "responder_name": responder.display_name if responder else None,
        "resource_id": resource.id if resource else None,
        "resource_name": resource.name if resource else None,
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
    }
    if include_analysis:
        analysis = db.get(IncidentAnalysis, incident.id)
        result["analysis"] = {
            "status": analysis.status,
            "provider": analysis.provider,
            "model": analysis.model,
            "result": analysis.result,
            "validation_outcome": analysis.validation_outcome,
            "completed_at": analysis.completed_at,
        } if analysis else None
    return result


def require_incident_scope(db: Session, user: User, incident_id: str) -> Incident:
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    if user.role == "user" and incident.reporter_id != user.id:
        raise HTTPException(404, "Incident not found")
    if user.role == "responder":
        assignment = db.scalar(select(Assignment).where(
            Assignment.incident_id == incident.id,
            Assignment.responder_id == user.id,
            Assignment.status.in_(RESPONDER_VISIBLE_ASSIGNMENTS),
        ))
        if not assignment:
            raise HTTPException(404, "Incident not found")
    return incident


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash) or not user.active:
        raise HTTPException(401, "Email or password is incorrect")
    if user.role != body.portal:
        raise HTTPException(403, "This account does not belong to the selected portal")
    token, expires, refresh_token, session_expires = issue_token(user, db, body.remember_me)
    return {
        "access_token": token,
        "expires_at": expires,
        "refresh_token": refresh_token,
        "session_expires_at": session_expires,
        "user": user,
    }


@router.post("/auth/register", status_code=201, response_model=LoginResponse)
def register_user(body: UserRegister, db: Session = Depends(get_db)):
    email = str(body.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, display_name=body.display_name.strip(), password_hash=hash_password(body.password), role="user")
    db.add(user)
    db.flush()
    audit(db, user, "user.registered", "user", user.id)
    db.commit()
    db.refresh(user)
    token, expires, refresh_token, session_expires = issue_token(user, db, body.remember_me)
    return {
        "access_token": token,
        "expires_at": expires,
        "refresh_token": refresh_token,
        "session_expires_at": session_expires,
        "user": user,
    }


@router.post("/auth/refresh", response_model=LoginResponse)
def refresh_session(body: RefreshRequest, db: Session = Depends(get_db)):
    session = db.scalar(
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == hash_refresh_token(body.refresh_token))
        .with_for_update()
    )
    now = now_utc()
    if (
        not session
        or session.revoked_at
        or session.expires_at.replace(tzinfo=timezone.utc) <= now
    ):
        raise HTTPException(401, "The remembered session is no longer valid")
    user = db.get(User, session.user_id)
    if not user or not user.active:
        if session and not session.revoked_at:
            session.revoked_at = now
            db.commit()
        raise HTTPException(401, "The remembered session is no longer valid")

    refresh_token = secrets.token_urlsafe(48)
    session.refresh_token_hash = hash_refresh_token(refresh_token)
    session_expires = session.expires_at
    if session_expires.tzinfo is None:
        session_expires = session_expires.replace(tzinfo=timezone.utc)
    access_expires = now + timedelta(minutes=get_settings().access_token_minutes)
    access_token = encode_access_token(user, session.jti, now, access_expires)
    db.commit()
    return {
        "access_token": access_token,
        "expires_at": access_expires,
        "refresh_token": refresh_token,
        "session_expires_at": session_expires,
        "user": user,
    }


@router.post("/auth/logout", status_code=204)
def logout(user: User = Depends(current_user), credentials=Depends(bearer), db: Session = Depends(get_db)):
    import jwt
    from app.config import get_settings
    claims = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=["HS256"])
    session = db.get(AuthSession, claims["jti"])
    if session and not session.revoked_at:
        session.revoked_at = now_utc()
        db.commit()
    return Response(status_code=204)


@router.get("/auth/me", response_model=UserView)
def me(user: User = Depends(current_user)):
    return user


@router.post("/user/incidents", status_code=201)
def create_user_incident(
    body: IncidentCreate,
    background_tasks: BackgroundTasks,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    user: User = Depends(require_roles("user")),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(Incident).where(Incident.reporter_id == user.id, Incident.idempotency_key == idempotency_key))
    if existing:
        return JSONResponse(status_code=200, content=jsonable_encoder(incident_view(db, existing, include_analysis=False)))
    priority, reason = priority_for(body.emergency_type, body.severity, body.urgency)
    incident = Incident(
        reference=f"ECS-{secrets.token_hex(3).upper()}", reporter_id=user.id,
        emergency_type=body.emergency_type, description=body.description.strip(),
        location_label=body.location_label.strip(), location_source=body.location_source,
        latitude=body.latitude, longitude=body.longitude, accuracy_m=body.accuracy_m,
        location_at=body.location_at, severity=body.severity, urgency=body.urgency,
        priority=priority, priority_reason=reason, status="Unassigned", idempotency_key=idempotency_key,
    )
    db.add(incident)
    db.flush()
    db.add(IncidentAnalysis(incident_id=incident.id, status="pending", provider="pending", validation_outcome="pending"))
    db.add(IncidentUpdate(incident_id=incident.id, actor_id=user.id, kind="submitted", message="Request received by the coordination system. No external service has been contacted."))
    audit(db, user, "incident.submitted", "incident", incident.id, {"reference": incident.reference})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Incident).where(Incident.reporter_id == user.id, Incident.idempotency_key == idempotency_key))
        if existing:
            return JSONResponse(status_code=200, content=jsonable_encoder(incident_view(db, existing, include_analysis=False)))
        raise HTTPException(409, "A conflicting request was recorded; refresh your incidents")
    db.refresh(incident)
    background_tasks.add_task(analyze_incident_task, incident.id)
    return incident_view(db, incident, include_analysis=False)


@router.get("/incidents")
def list_incidents(
    status_filter: str | None = Query(default=None, alias="status"),
    query: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    statement = select(Incident).order_by(Incident.created_at.desc())
    if user.role == "user":
        statement = statement.where(Incident.reporter_id == user.id)
    elif user.role == "responder":
        assigned = select(Assignment.incident_id).where(
            Assignment.responder_id == user.id,
            Assignment.status.in_(RESPONDER_VISIBLE_ASSIGNMENTS),
        )
        statement = statement.where(Incident.id.in_(assigned))
    if status_filter:
        statement = statement.where(Incident.status == status_filter)
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where((Incident.reference.ilike(pattern)) | (Incident.emergency_type.ilike(pattern)) | (Incident.description.ilike(pattern)) | (Incident.location_label.ilike(pattern)))
    return [incident_view(db, item, include_analysis=user.role != "user") for item in db.scalars(statement).all()]


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return incident_view(db, require_incident_scope(db, user, incident_id), include_analysis=user.role != "user")


@router.get("/incidents/{incident_id}/updates")
def get_updates(incident_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    incident = require_incident_scope(db, user, incident_id)
    rows = db.scalars(select(IncidentUpdate).where(IncidentUpdate.incident_id == incident.id).order_by(IncidentUpdate.created_at)).all()
    return [{"id": row.id, "kind": row.kind, "message": row.message, "actor_id": row.actor_id, "created_at": row.created_at} for row in rows]


@router.post("/incidents/{incident_id}/updates", status_code=201)
def add_update(incident_id: str, body: MessageCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    incident = require_incident_scope(db, user, incident_id)
    if user.role == "responder" and not db.scalar(select(Assignment.id).where(
        Assignment.incident_id == incident.id,
        Assignment.responder_id == user.id,
        Assignment.status.in_(ACTIVE_ASSIGNMENTS),
    )):
        raise HTTPException(409, "Only the currently assigned responder can add operational updates")
    if user.role == "user" and incident.status in ("Resolved", "Cancelled"):
        raise HTTPException(409, "Closed incidents cannot receive updates")
    row = IncidentUpdate(incident_id=incident.id, actor_id=user.id, kind="message", message=body.message.strip())
    db.add(row)
    audit(db, user, "incident.message", "incident", incident.id)
    db.commit()
    return {"id": row.id, "kind": row.kind, "message": row.message, "created_at": row.created_at}


@router.get("/admin/dashboard")
def admin_dashboard(_admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    incidents = db.scalars(select(Incident)).all()
    responders = db.scalars(select(ResponderProfile)).all()
    active_assignments = db.scalars(select(Assignment).where(Assignment.status.in_(ACTIVE_ASSIGNMENTS))).all()
    return {
        "total_incidents": len(incidents),
        "active_incidents": sum(item.status not in ("Resolved", "Cancelled") for item in incidents),
        "unassigned": sum(item.status == "Unassigned" for item in incidents),
        "assigned": sum(item.status == "Assigned" for item in incidents),
        "in_progress": sum(item.status in ("Accepted", "En Route", "On Scene") for item in incidents),
        "resolved": sum(item.status == "Resolved" for item in incidents),
        "responders_available": sum(item.available for item in responders),
        "responders_busy": len(active_assignments),
        "responders_unavailable": sum(not item.available for item in responders) - len(active_assignments),
        "resources_total": sum(row.quantity for row in db.scalars(select(Resource)).all()),
        "resources_allocated": sum(row.allocated for row in db.scalars(select(Resource)).all()),
    }


@router.get("/admin/analytics")
def admin_analytics(
    days: int = Query(default=30, ge=1, le=90),
    _admin: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Descriptive metrics only; no forecast is presented as operational fact."""
    now = now_utc()
    cutoff = now - timedelta(days=days)
    incidents = db.scalars(select(Incident).where(Incident.created_at >= cutoff)).all()
    status_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    daily_counts: dict[str, int] = {}
    for item in incidents:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1
        category_counts[item.emergency_type] = category_counts.get(item.emergency_type, 0) + 1
        created = item.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        day = created.date().isoformat()
        daily_counts[day] = daily_counts.get(day, 0) + 1

    assignment_rows = db.scalars(select(Assignment).where(Assignment.assigned_at >= cutoff)).all()
    delays = []
    completion_durations = []
    workload: dict[str, int] = {}
    for assignment in assignment_rows:
        incident = db.get(Incident, assignment.incident_id)
        if incident:
            assigned = assignment.assigned_at
            created = incident.created_at
            if assigned.tzinfo is None:
                assigned = assigned.replace(tzinfo=timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            delays.append(max(0.0, (assigned - created).total_seconds() / 60))
        if assignment.ended_at and assignment.status in ("Completed", "Resolved"):
            ended = assignment.ended_at
            assigned = assignment.assigned_at
            if ended.tzinfo is None:
                ended = ended.replace(tzinfo=timezone.utc)
            if assigned.tzinfo is None:
                assigned = assigned.replace(tzinfo=timezone.utc)
            completion_durations.append(max(0.0, (ended - assigned).total_seconds() / 60))
        workload[assignment.responder_id] = workload.get(assignment.responder_id, 0) + 1
    average = lambda values: round(sum(values) / len(values), 1) if values else None
    resources = db.scalars(select(Resource).where(Resource.active)).all()
    return {
        "period_days": days,
        "from": cutoff,
        "to": now,
        "incident_count": len(incidents),
        "category_counts": category_counts,
        "status_counts": status_counts,
        "daily_incident_counts": dict(sorted(daily_counts.items())),
        "assignment_count": len(assignment_rows),
        "average_assignment_delay_minutes": average(delays),
        "completed_assignment_count": len(completion_durations),
        "average_assignment_to_completion_minutes": average(completion_durations),
        "assignments_per_responder": workload,
        "resource_units_total": sum(resource.quantity for resource in resources),
        "resource_units_allocated": sum(resource.allocated for resource in resources),
        "forecast": None,
        "data_note": "Descriptive metrics from records in the selected period; no forecast or dispatch recommendation.",
    }


@router.post("/admin/copilot")
def admin_copilot(
    body: CopilotQuestion,
    admin: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Read-only intent router over fixed, authorized operational queries."""
    question = body.question.strip()
    lowered = question.casefold()
    source_records: list[dict] = []
    intent = "help"

    reference_match = re.search(r"\bECS-[A-Z0-9]{4,12}\b", question, re.IGNORECASE)
    if reference_match:
        intent = "incident_lookup"
        reference = reference_match.group(0).upper()
        incident = db.scalar(select(Incident).where(Incident.reference == reference))
        if incident:
            source_records = [{
                "reference": incident.reference,
                "emergency_type": incident.emergency_type,
                "status": incident.status,
                "priority": incident.priority,
                "severity": incident.severity,
                "urgency": incident.urgency,
                "created_at": incident.created_at,
                "summary": incident.description[:240],
            }]
            answer = (
                f"{incident.reference}: {incident.emergency_type}, {incident.status}, "
                f"{incident.priority} priority. Report: {incident.description[:240]}"
            )
        else:
            answer = f"No report with reference {reference} is present in the coordination database."
    elif any(term in lowered for term in ("historical", "history", "trend", "analytics", "assignment delay", "resolution time")):
        intent = "descriptive_analytics"
        analytics = admin_analytics(days=30, _admin=admin, db=db)
        source_records = [analytics]
        average_delay = analytics["average_assignment_delay_minutes"]
        average_resolution = analytics["average_assignment_to_completion_minutes"]
        answer = (
            f"In the last {analytics['period_days']} days, {analytics['incident_count']} reports were recorded. "
            f"Average assignment delay: {str(average_delay) + ' minutes' if average_delay is not None else 'not available'}. "
            f"Average assignment-to-completion duration: {str(average_resolution) + ' minutes' if average_resolution is not None else 'not available'}. "
            "These are descriptive records, not a forecast."
        )
    elif any(term in lowered for term in ("unassigned", "awaiting assignment", "waiting assignment")):
        intent = "unassigned_incidents"
        rows = db.scalars(select(Incident).where(Incident.status == "Unassigned").order_by(Incident.created_at)).all()
        source_records = [{
            "reference": row.reference,
            "emergency_type": row.emergency_type,
            "priority": row.priority,
            "created_at": row.created_at,
        } for row in rows[:20]]
        answer = f"{len(rows)} report(s) are awaiting responder assignment."
        if rows:
            answer += " References: " + ", ".join(row.reference for row in rows[:20]) + "."
    elif any(term in lowered for term in ("responder", "responders", "available", "busy")):
        intent = "responder_availability"
        rows = db.execute(
            select(User, ResponderProfile)
            .join(ResponderProfile, ResponderProfile.user_id == User.id)
            .where(User.role == "responder", User.active)
            .order_by(User.display_name)
        ).all()
        assignments = db.scalars(select(Assignment).where(Assignment.status.in_(ACTIVE_ASSIGNMENTS))).all()
        active_by_responder = {row.responder_id: row for row in assignments}
        for account, profile in rows:
            active = active_by_responder.get(account.id)
            effective_available = profile.available and active is None
            source_records.append({
                "name": account.display_name,
                "availability": "available" if effective_available else "busy" if active else "unavailable",
                "incident_reference": db.get(Incident, active.incident_id).reference if active else None,
                "capabilities": profile.capabilities,
            })
        available_count = sum(item["availability"] == "available" for item in source_records)
        busy_count = sum(item["availability"] == "busy" for item in source_records)
        answer = f"{available_count} active responder(s) are available; {busy_count} have an active assignment."
        if source_records:
            answer += " See the sourced responder list for details."
    elif any(term in lowered for term in ("resource", "ambulance", "vehicle", "equipment", "utilization")):
        intent = "resource_utilization"
        rows = db.scalars(select(Resource).where(Resource.active).order_by(Resource.kind, Resource.name)).all()
        source_records = [{
            "name": row.name,
            "kind": row.kind,
            "allocated": row.allocated,
            "available": row.quantity - row.allocated,
            "total": row.quantity,
        } for row in rows]
        total = sum(row.quantity for row in rows)
        allocated = sum(row.allocated for row in rows)
        answer = f"{allocated} of {total} active resource unit(s) are allocated; {total - allocated} are available."
    elif any(term in lowered for term in ("volume", "count", "category", "status", "incidents")):
        intent = "incident_totals"
        rows = db.scalars(select(Incident)).all()
        status_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        for row in rows:
            status_counts[row.status] = status_counts.get(row.status, 0) + 1
            category_counts[row.emergency_type] = category_counts.get(row.emergency_type, 0) + 1
        answer = f"The database contains {len(rows)} report(s). By status: "
        answer += ", ".join(f"{key}: {value}" for key, value in sorted(status_counts.items())) or "no reports"
        answer += ". By category: "
        answer += ", ".join(f"{key}: {value}" for key, value in sorted(category_counts.items())) or "no reports"
        source_records = [{"status_counts": status_counts, "category_counts": category_counts}]
    else:
        answer = (
            "I can answer read-only questions about unassigned reports, incident status or category counts, "
            "responder availability, resources, or a report reference such as ECS-ABC123. "
            "This assistant uses fixed database queries; it cannot dispatch or change records."
        )

    audit(db, admin, "admin.copilot_queried", "copilot", admin.id, {"intent": intent, "source_count": len(source_records)})
    db.commit()
    return {"answer": answer, "intent": intent, "sources": source_records, "read_only": True, "generated_by": "rules_based"}


@router.get("/admin/responders")
def admin_responders(admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    rows = db.execute(select(User, ResponderProfile).join(ResponderProfile, ResponderProfile.user_id == User.id).where(User.active)).all()
    result = []
    active_by_responder = {a.responder_id: a for a in db.scalars(select(Assignment).where(Assignment.status.in_(ACTIVE_ASSIGNMENTS))).all()}
    for account, profile in rows:
        active = active_by_responder.get(account.id)
        result.append({"id": account.id, "display_name": account.display_name, "email": account.email,
                       "capabilities": profile.capabilities, "available": profile.available,
                       "active_incident_id": active.incident_id if active else None,
                       "latitude": profile.latitude, "longitude": profile.longitude,
                       "location_accuracy_m": profile.location_accuracy_m, "location_at": profile.location_at})
    return result


@router.get("/admin/users")
def admin_users(role: str | None = Query(default=None, pattern="^(user|responder|admin)$"), admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    statement = select(User).order_by(User.created_at.desc())
    if role:
        statement = statement.where(User.role == role)
    rows = db.scalars(statement).all()
    return [{"id": row.id, "email": row.email, "display_name": row.display_name, "role": row.role, "active": row.active, "created_at": row.created_at} for row in rows]


@router.put("/admin/responders/{responder_id}/capabilities")
def set_capabilities(responder_id: str, capabilities: list[str], admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    profile = db.get(ResponderProfile, responder_id)
    if not profile:
        raise HTTPException(404, "Responder not found")
    normalized = sorted({value.strip().lower() for value in capabilities if value.strip()})
    if not normalized or len(normalized) > 20:
        raise HTTPException(422, "Provide between 1 and 20 capabilities")
    profile.capabilities = normalized
    audit(db, admin, "responder.capabilities_changed", "user", responder_id, {"capabilities": normalized})
    db.commit()
    return {"responder_id": responder_id, "capabilities": normalized}


@router.get("/admin/incidents/{incident_id}/recommendations")
def responder_recommendations(incident_id: str, _admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    category = incident.emergency_type.lower()
    settings = get_settings()
    weights = {
        "distance": settings.recommendation_distance_weight,
        "capability": settings.recommendation_capability_weight,
        "workload": settings.recommendation_workload_weight,
    }
    active_assignments = db.scalars(select(Assignment).where(Assignment.status.in_(ACTIVE_ASSIGNMENTS))).all()
    busy_responders = {row.responder_id for row in active_assignments}
    workload_since = now_utc() - timedelta(hours=24)
    recent_workload: dict[str, int] = {}
    for row in db.scalars(select(Assignment).where(
        Assignment.status.in_(("Completed", "Resolved")),
        Assignment.ended_at.is_not(None),
        Assignment.ended_at >= workload_since,
    )).all():
        recent_workload[row.responder_id] = recent_workload.get(row.responder_id, 0) + 1
    profiles = db.execute(select(User, ResponderProfile).join(ResponderProfile).where(User.role == "responder", User.active, ResponderProfile.available.is_(True))).all()
    now = now_utc()
    incident_location_fresh = bool(
        incident.latitude is not None and incident.location_at
        and incident.accuracy_m is not None and incident.accuracy_m <= 100
        and (now - as_utc(incident.location_at)) <= timedelta(minutes=15)
    )
    recommendations = []
    for account, profile in profiles:
        if account.id in busy_responders:
            continue
        skills = {str(skill).strip().casefold() for skill in profile.capabilities}
        if "medical" in category:
            required = {"medical", "ambulance", "paramedic", "ems"}
        elif "fire" in category or "rescue" in category:
            required = {"fire", "rescue", "fire and rescue"}
        elif "police" in category or "security" in category:
            required = {"police", "security"}
        else:
            required = {"other", "general", "emergency"}
        matching_skills = sorted(skill for skill in skills if skill in required or any(token in skill for token in required))
        if not matching_skills:
            continue
        responder_location_fresh = bool(
            profile.latitude is not None and profile.location_at
            and profile.location_accuracy_m is not None and profile.location_accuracy_m <= 100
            and (now - as_utc(profile.location_at)) <= timedelta(minutes=15)
        )
        reliable = incident_location_fresh and responder_location_fresh and incident.longitude is not None and profile.longitude is not None
        distance = distance_km(incident.latitude, incident.longitude, profile.latitude, profile.longitude) if reliable else None
        workload = recent_workload.get(account.id, 0)
        score = 0.0
        reasons = [f"Eligible service capability: {', '.join(matching_skills)}"]
        if distance is not None:
            distance_score = max(0.0, 1.0 - min(distance, 100.0) / 100.0)
            score += weights["distance"] * distance_score
            reasons.append(f"Fresh accurate GPS: {distance:.1f} km away")
        else:
            reasons.append("Distance not scored: incident or responder GPS is missing, stale, or inaccurate")
        workload_score = 1.0 / (1.0 + workload)
        score += weights["workload"] * workload_score
        reasons.append(f"Completed assignments in last 24 hours: {workload}")
        score += weights["capability"]
        max_weight = sum(weights.values())
        recommendations.append({
            "responder_id": account.id,
            "display_name": account.display_name,
            "capabilities": profile.capabilities,
            "matching_capabilities": matching_skills,
            "score": round(score * 100 / max_weight, 1) if max_weight else 0.0,
            "reasons": reasons,
            "recent_completed_assignments": workload,
            "distance_km": distance,
            "distance_basis": "fresh_gps" if reliable else "unavailable_or_stale_location",
        })
    recommendations.sort(key=lambda item: (-item["score"], item["display_name"].casefold()))
    resources_for_incident = [
        {"id": row.id, "name": row.name, "kind": row.kind, "available": row.quantity-row.allocated}
        for row in db.scalars(select(Resource).where(Resource.active, Resource.quantity > Resource.allocated)).all()
        if resource_matches_incident(row.kind, incident.emergency_type)
    ]
    return {
        "recommended_responder_id": recommendations[0]["responder_id"] if recommendations else None,
        "weight_config": weights,
        "human_approval_required": True,
        "compatible_resources": resources_for_incident,
        "eligible_responders": recommendations,
    }


@router.get("/admin/incidents/{incident_id}/duplicates")
def incident_duplicate_candidates(incident_id: str, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    candidates = find_duplicate_candidates(db, incident)
    audit(db, admin, "incident.duplicates_reviewed", "incident", incident.id, {"candidate_count": len(candidates)})
    db.commit()
    return {"candidates": candidates, "auto_merge": False}


@router.post("/admin/incidents/{incident_id}/analysis/retry", status_code=202)
def retry_incident_analysis(
    incident_id: str,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    analysis = db.get(IncidentAnalysis, incident.id)
    if not analysis:
        analysis = IncidentAnalysis(incident_id=incident.id)
        db.add(analysis)
    elif analysis.status == "ready":
        raise HTTPException(409, "Validated analysis is already available")
    elif analysis.status == "processing":
        started = analysis.completed_at or analysis.created_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if now_utc() - started < timedelta(seconds=90):
            raise HTTPException(409, "Incident analysis is already running")
    analysis.status = "pending"
    analysis.provider = "pending"
    analysis.validation_outcome = "retry_requested"
    analysis.completed_at = None
    audit(db, admin, "incident.analysis_retry_requested", "incident", incident.id)
    db.commit()
    background_tasks.add_task(analyze_incident_task, incident.id)
    return {"incident_id": incident.id, "analysis_status": "pending"}


@router.post("/admin/users", status_code=201, response_model=UserView)
def create_account(body: UserCreate, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    email = str(body.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, display_name=body.display_name.strip(), password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.flush()
    if body.role == "responder":
        db.add(ResponderProfile(user_id=user.id, capabilities=[x.strip().lower() for x in body.capabilities], available=True))
    audit(db, admin, "user.created", "user", user.id, {"role": user.role})
    db.commit()
    db.refresh(user)
    return user


@router.patch("/admin/users/{user_id}/active")
def set_account_active(user_id: str, active: bool = Query(...), admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    account = db.get(User, user_id)
    if not account or account.role == "admin" or account.id == admin.id:
        raise HTTPException(404, "Account not found")
    account.active = active
    audit(db, admin, "user.activation_changed", "user", account.id, {"active": active})
    if not active:
        db.query(AuthSession).filter(AuthSession.user_id == account.id, AuthSession.revoked_at.is_(None)).update({"revoked_at": now_utc()})
    db.commit()
    return {"id": account.id, "active": account.active}


@router.patch("/admin/responders/{responder_id}/availability")
def set_availability(responder_id: str, body: AvailabilityUpdate, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    profile = db.get(ResponderProfile, responder_id)
    if not profile:
        raise HTTPException(404, "Responder not found")
    busy = db.scalar(select(Assignment.id).where(Assignment.responder_id == responder_id, Assignment.status.in_(ACTIVE_ASSIGNMENTS)))
    if busy and body.available:
        raise HTTPException(409, "A responder with an active assignment cannot be marked available")
    profile.available = body.available
    audit(db, admin, "responder.availability_changed", "user", responder_id, {"available": body.available})
    db.commit()
    return {"responder_id": responder_id, "available": profile.available}


@router.get("/admin/resources")
def list_resources(_admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    return [{"id": r.id, "name": r.name, "kind": r.kind, "quantity": r.quantity, "allocated": r.allocated, "available": r.quantity-r.allocated, "active": r.active}
            for r in db.scalars(select(Resource).order_by(Resource.kind, Resource.name)).all()]


@router.post("/admin/resources", status_code=201)
def create_resource(body: ResourceCreate, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    if db.scalar(select(Resource).where(Resource.name == body.name.strip())):
        raise HTTPException(409, "Resource name already exists")
    row = Resource(name=body.name.strip(), kind=body.kind.strip(), quantity=body.quantity)
    db.add(row)
    db.flush()
    audit(db, admin, "resource.created", "resource", row.id)
    db.commit()
    return {"id": row.id, "name": row.name, "kind": row.kind, "quantity": row.quantity, "allocated": row.allocated}


@router.patch("/admin/resources/{resource_id}")
def update_resource(resource_id: str, body: ResourceCreate, active: bool = Query(default=True), admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    row = db.scalar(select(Resource).where(Resource.id == resource_id).with_for_update())
    if not row:
        raise HTTPException(404, "Resource not found")
    if body.quantity < row.allocated:
        raise HTTPException(409, "Quantity cannot be lower than currently allocated units")
    row.name, row.kind, row.quantity, row.active = body.name.strip(), body.kind.strip(), body.quantity, active
    audit(db, admin, "resource.updated", "resource", row.id, {"quantity": row.quantity, "active": row.active})
    db.commit()
    return {"id": row.id, "name": row.name, "kind": row.kind, "quantity": row.quantity, "allocated": row.allocated, "active": row.active}


@router.post("/admin/incidents/{incident_id}/assign")
def assign_incident(incident_id: str, body: AssignmentCreate, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    incident = db.scalar(select(Incident).where(Incident.id == incident_id).with_for_update())
    profile = db.scalar(select(ResponderProfile).where(ResponderProfile.user_id == body.responder_id).with_for_update())
    responder = db.get(User, body.responder_id)
    if not incident or incident.status in ("Resolved", "Cancelled"):
        raise HTTPException(404, "Open incident not found")
    if not profile or not responder or responder.role != "responder" or not responder.active:
        raise HTTPException(422, "Select an active responder account")
    category = incident.emergency_type.lower()
    if not profile.available or not any(skill in category or category in skill for skill in profile.capabilities):
        raise HTTPException(409, "Responder is unavailable or does not match this service capability")
    active_existing = db.scalar(select(Assignment).where(Assignment.incident_id == incident.id, Assignment.status.in_(ACTIVE_ASSIGNMENTS)).with_for_update())
    if active_existing:
        raise HTTPException(409, "Incident already has an active assignment; revoke it before reassigning")
    if body.resource_id:
        resource = db.scalar(select(Resource).where(Resource.id == body.resource_id, Resource.active).with_for_update())
        if not resource:
            raise HTTPException(404, "Resource not found")
        if not resource_matches_incident(resource.kind, incident.emergency_type):
            raise HTTPException(409, "The selected resource is not a compatible type for this emergency")
        changed = db.execute(update(Resource).where(Resource.id == resource.id, Resource.allocated < Resource.quantity).values(allocated=Resource.allocated + 1))
        if changed.rowcount != 1:
            raise HTTPException(409, "Resource has no available units")
    assignment = Assignment(incident_id=incident.id, responder_id=responder.id, resource_id=body.resource_id, assigned_by=admin.id, status="Assigned")
    db.add(assignment)
    profile.available = False
    incident.status = "Assigned"
    incident.updated_at = now_utc()
    db.add(IncidentUpdate(incident_id=incident.id, actor_id=admin.id, kind="assigned", message=f"Assigned to {responder.display_name}."))
    audit(db, admin, "incident.assigned", "incident", incident.id, {"responder_id": responder.id, "resource_id": body.resource_id})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Responder or incident was assigned concurrently; refresh and try again")
    return incident_view(db, incident)


@router.post("/admin/incidents/{incident_id}/reassign")
def reassign_incident(incident_id: str, body: AssignmentCreate, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    incident = db.scalar(select(Incident).where(Incident.id == incident_id).with_for_update())
    if not incident or incident.status in ("Resolved", "Cancelled"):
        raise HTTPException(404, "Open incident not found")
    old = db.scalar(select(Assignment).where(Assignment.incident_id == incident.id, Assignment.status.in_(ACTIVE_ASSIGNMENTS)).with_for_update())
    if not old:
        raise HTTPException(409, "Incident has no active assignment; use assign instead")
    previous_profile = db.get(ResponderProfile, old.responder_id)
    if previous_profile:
        previous_profile.available = True
    if old.resource_id:
        old_resource = db.get(Resource, old.resource_id)
        if old_resource: old_resource.allocated = max(0, old_resource.allocated - 1)
    old.status, old.ended_at = "Revoked", now_utc()
    db.flush()
    # The replacement is created in this transaction; any validation/constraint failure rolls back revocation too.
    profile = db.get(ResponderProfile, body.responder_id)
    responder = db.get(User, body.responder_id)
    category = incident.emergency_type.lower()
    if not profile or not responder or responder.role != "responder" or not responder.active or not profile.available or not any(skill in category or category in skill for skill in profile.capabilities):
        raise HTTPException(409, "Replacement responder is unavailable or not capable")
    resource_id = body.resource_id
    if resource_id:
        resource = db.scalar(select(Resource).where(Resource.id == resource_id, Resource.active).with_for_update())
        if resource and not resource_matches_incident(resource.kind, incident.emergency_type):
            raise HTTPException(409, "The selected resource is not a compatible type for this emergency")
        if not resource or db.execute(update(Resource).where(Resource.id == resource_id, Resource.allocated < Resource.quantity).values(allocated=Resource.allocated + 1)).rowcount != 1:
            raise HTTPException(409, "Replacement resource is unavailable")
    replacement = Assignment(incident_id=incident.id, responder_id=responder.id, resource_id=resource_id, assigned_by=admin.id, status="Assigned")
    db.add(replacement)
    profile.available = False
    incident.status = "Assigned"
    db.add(IncidentUpdate(incident_id=incident.id, actor_id=admin.id, kind="reassigned", message=f"Reassigned to {responder.display_name}."))
    audit(db, admin, "incident.reassigned", "incident", incident.id, {"from": old.responder_id, "to": responder.id})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Responder was assigned concurrently; refresh and try again")
    return incident_view(db, incident)


@router.post("/admin/incidents/{incident_id}/cancel")
def cancel_incident(incident_id: str, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    incident = db.scalar(select(Incident).where(Incident.id == incident_id).with_for_update())
    if not incident or incident.status in ("Resolved", "Cancelled"):
        raise HTTPException(404, "Open incident not found")
    assignment = db.scalar(select(Assignment).where(Assignment.incident_id == incident.id, Assignment.status.in_(ACTIVE_ASSIGNMENTS)).with_for_update())
    if assignment:
        assignment.status, assignment.ended_at = "Revoked", now_utc()
        profile = db.get(ResponderProfile, assignment.responder_id)
        if profile: profile.available = True
        if assignment.resource_id:
            resource = db.get(Resource, assignment.resource_id)
            if resource: resource.allocated = max(0, resource.allocated - 1)
    incident.status = "Cancelled"
    db.add(IncidentUpdate(incident_id=incident.id, actor_id=admin.id, kind="cancelled", message="Incident request cancelled by an administrator."))
    audit(db, admin, "incident.cancelled", "incident", incident.id)
    db.commit()
    return incident_view(db, incident)


@router.post("/admin/incidents/{incident_id}/resolve")
def admin_resolve_incident(incident_id: str, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    incident = db.scalar(select(Incident).where(Incident.id == incident_id).with_for_update())
    if not incident or incident.status in ("Resolved", "Cancelled"):
        raise HTTPException(404, "Open incident not found")
    assignment = db.scalar(select(Assignment).where(Assignment.incident_id == incident.id, Assignment.status.in_(ACTIVE_ASSIGNMENTS)).with_for_update())
    if assignment:
        assignment.status, assignment.ended_at = "Completed", now_utc()
        profile = db.get(ResponderProfile, assignment.responder_id)
        if profile: profile.available = True
        if assignment.resource_id:
            resource = db.get(Resource, assignment.resource_id)
            if resource: resource.allocated = max(0, resource.allocated - 1)
    incident.status = "Resolved"
    db.add(IncidentUpdate(incident_id=incident.id, actor_id=admin.id, kind="resolved", message="Incident marked resolved by an administrator."))
    audit(db, admin, "incident.resolved_by_admin", "incident", incident.id)
    db.commit()
    return incident_view(db, incident)


@router.post("/responder/incidents/{incident_id}/status")
def update_status(incident_id: str, body: StatusUpdate, responder: User = Depends(require_roles("responder")), db: Session = Depends(get_db)):
    incident = db.scalar(select(Incident).where(Incident.id == incident_id).with_for_update())
    assignment = db.scalar(select(Assignment).where(Assignment.incident_id == incident_id, Assignment.responder_id == responder.id, Assignment.status.in_(ACTIVE_ASSIGNMENTS)).with_for_update())
    if not incident or not assignment:
        raise HTTPException(404, "Assigned task not found")
    expected = NEXT_STATUS.get(assignment.status)
    if body.status != expected:
        raise HTTPException(409, f"Next permitted status is {expected or 'none'}")
    assignment.status = body.status
    assignment.updated_at = now_utc()
    incident.status = body.status
    incident.updated_at = now_utc()
    if body.status == "Resolved":
        assignment.ended_at = now_utc()
        profile = db.get(ResponderProfile, responder.id)
        if profile: profile.available = True
        if assignment.resource_id:
            resource = db.get(Resource, assignment.resource_id)
            if resource: resource.allocated = max(0, resource.allocated - 1)
    db.add(IncidentUpdate(incident_id=incident.id, actor_id=responder.id, kind="status", message=f"Status updated to {body.status}."))
    audit(db, responder, "incident.status_changed", "incident", incident.id, {"status": body.status})
    db.commit()
    return incident_view(db, incident)


@router.get("/responder/profile")
def responder_profile(responder: User = Depends(require_roles("responder")), db: Session = Depends(get_db)):
    profile = db.get(ResponderProfile, responder.id)
    return {"id": responder.id, "display_name": responder.display_name,
            "capabilities": profile.capabilities, "available": profile.available}


@router.put("/responder/location")
def update_responder_location(
    body: ResponderLocation,
    responder: User = Depends(require_roles("responder")),
    db: Session = Depends(get_db),
):
    now = now_utc()
    captured = body.captured_at.replace(tzinfo=timezone.utc) if body.captured_at.tzinfo is None else body.captured_at
    if (now - captured) > timedelta(minutes=15) or captured > now + timedelta(minutes=1):
        raise HTTPException(422, "Location must be captured within the last 15 minutes")
    profile = db.get(ResponderProfile, responder.id)
    if not profile:
        raise HTTPException(404, "Responder profile not found")
    profile.latitude, profile.longitude = body.latitude, body.longitude
    profile.location_accuracy_m, profile.location_at = body.accuracy_m, captured
    audit(db, responder, "responder.location_updated", "user", responder.id, {"accuracy_m": body.accuracy_m})
    db.commit()
    return {"location_at": captured, "accuracy_m": body.accuracy_m, "distance_use": "Only used for recommendations while fresh and accurate."}


@router.get("/admin/audit")
def list_audit(
    limit: int = Query(default=100, ge=1, le=500),
    _admin: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [{"id": x.id, "actor_id": x.actor_id, "action": x.action, "entity_type": x.entity_type,
             "entity_id": x.entity_id, "details": x.details, "created_at": x.created_at} for x in rows]


@router.get("/changes")
def changes_since(after: datetime | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    statement = select(Incident).order_by(Incident.updated_at.desc())
    if user.role == "user": statement = statement.where(Incident.reporter_id == user.id)
    elif user.role == "responder":
        allowed = select(Assignment.incident_id).where(
            Assignment.responder_id == user.id,
            Assignment.status.in_(RESPONDER_VISIBLE_ASSIGNMENTS),
        )
        statement = statement.where(Incident.id.in_(allowed))
    if after: statement = statement.where(Incident.updated_at > after)
    return {"server_time": now_utc(), "incidents": [incident_view(db, row) for row in db.scalars(statement).all()]}
