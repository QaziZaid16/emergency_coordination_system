from datetime import datetime, timedelta, timezone
import re
import secrets
import smtplib
from email.message import EmailMessage
from collections import defaultdict, deque
from threading import Lock
import time
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dispatch import distance_km, priority_for
from app.models import AccountInvitation, Assignment, AuditEvent, AuthSession, CoordinationPolicy, Incident, IncidentAnalysis, IncidentReport, IncidentUpdate, Notification, ResponderProfile, Resource, User, now_utc
from app.schemas import AssignmentCreate, AutomaticAssignmentPolicyUpdate, AvailabilityUpdate, CoAdminCreate, CopilotQuestion, IncidentCreate, IntakeAnswers, InvitationAccept, LoginRequest, LoginResponse, MessageCreate, RefreshRequest, ReportReview, ResponderInviteCreate, ResponderLocation, ResourceCreate, RewriteRequest, StatusUpdate, UserCreate, UserRegister, UserView
from app.intelligence import analyze_incident_task, find_duplicate_candidates, rewrite_responder_note
from app.security import bearer, current_user, encode_access_token, hash_password, hash_refresh_token, issue_token, require_roles, verify_password

router = APIRouter()
ACTIVE_ASSIGNMENTS = ("Assigned", "Accepted", "En Route", "On Scene")
RESPONDER_VISIBLE_ASSIGNMENTS = (*ACTIVE_ASSIGNMENTS, "Resolved", "Completed")
NEXT_STATUS = {"Assigned": "Accepted", "Accepted": "En Route", "En Route": "On Scene", "On Scene": "Resolved"}
_invite_attempts: dict[str, deque[float]] = defaultdict(deque)
_invite_attempts_lock = Lock()


def require_account_management(
    request: Request,
    admin: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> User:
    if admin.role == "super_admin":
        return admin
    if admin.role != "admin":
        raise HTTPException(403, "Your role cannot manage accounts")
    target = db.get(User, request.path_params.get("user_id", ""))
    if not target or target.role in ("admin", "super_admin"):
        raise HTTPException(404, "Account not found")
    permission = "manage_responders" if target.role == "responder" else "manage_users"
    if permission not in (admin.permissions or []):
        raise HTTPException(403, f"Missing permission: {permission}")
    return admin


def limit_invitation_requests(actor_id: str):
    now = time.monotonic()
    with _invite_attempts_lock:
        history = _invite_attempts[actor_id]
        while history and now - history[0] >= 3600:
            history.popleft()
        if len(history) >= 5:
            raise HTTPException(429, "Invitation limit reached. Try again later.")
        history.append(now)


def send_invitation_email(email: str, display_name: str, link: str) -> bool:
    settings = get_settings()
    if not settings.smtp_host:
        return settings.environment == "development"
    message = EmailMessage()
    message["Subject"] = "Activate your Emergency Coordination responder account"
    message["From"] = settings.smtp_from or settings.smtp_username
    message["To"] = email
    message.set_content(f"Hello {display_name},\n\nActivate your responder account using this one-time link (expires in 24 hours):\n{link}\n\nIf you did not expect this invitation, ignore this message.")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        return False


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


def notify(db: Session, recipient_id: str, key: str, kind: str, title: str, message: str, incident_id: str | None = None):
    if not db.scalar(select(Notification.id).where(Notification.user_id == recipient_id, Notification.event_key == key)):
        db.add(Notification(user_id=recipient_id, incident_id=incident_id, event_key=key, kind=kind, title=title, message=message))


def notify_coordinators(db: Session, key: str, kind: str, title: str, message: str, incident_id: str | None = None):
    coordinators = db.scalars(select(User).where(User.active.is_(True), User.role.in_(("admin", "super_admin")))).all()
    for coordinator in coordinators:
        if coordinator.role == "admin" and "view_incidents" not in (coordinator.permissions or []):
            continue
        notify(db, coordinator.id, key, kind, title, message, incident_id)


def notify_status_change(db: Session, incident: Incident, status: str):
    key = "incident:" + incident.id + ":status:" + status
    notify(db, incident.reporter_id, key, "incident_status", "Incident status updated", f"Your incident {incident.reference} is now {status}.", incident.id)


def automatic_candidate(db: Session, incident: Incident) -> tuple[User, ResponderProfile, float, list[str]] | None:
    if incident.latitude is None or incident.longitude is None or not incident.location_at or incident.accuracy_m is None or incident.accuracy_m > 100:
        return None
    now = now_utc()
    if now - as_utc(incident.location_at) > timedelta(minutes=15):
        return None
    active_ids = set(db.scalars(select(Assignment.responder_id).where(Assignment.status.in_(ACTIVE_ASSIGNMENTS))).all())
    category = incident.emergency_type.casefold()
    if "medical" in category or "ambulance" in category:
        required = ("medical", "ambulance", "paramedic", "ems")
    elif "fire" in category or "rescue" in category:
        required = ("fire", "rescue")
    elif "police" in category or "security" in category:
        required = ("police", "security")
    else:
        required = ("other", "general", "emergency")
    recent_workload: dict[str, int] = {}
    since = now - timedelta(hours=24)
    for row in db.scalars(select(Assignment).where(Assignment.status.in_(("Completed", "Resolved")), Assignment.ended_at.is_not(None), Assignment.ended_at >= since)).all():
        recent_workload[row.responder_id] = recent_workload.get(row.responder_id, 0) + 1
    settings = get_settings()
    distance_weight = settings.recommendation_distance_weight
    workload_weight = settings.recommendation_workload_weight
    total_weight = max(0.0, distance_weight) + max(0.0, workload_weight)
    candidates = []
    for account, profile in db.execute(select(User, ResponderProfile).join(ResponderProfile).where(User.role == "responder", User.active.is_(True), ResponderProfile.available.is_(True))).all():
        if account.id in active_ids or not any(any(term in str(skill).casefold() for term in required) for skill in (profile.capabilities or [])):
            continue
        if profile.latitude is None or profile.longitude is None or profile.location_accuracy_m is None or profile.location_accuracy_m > 100 or not profile.location_at or now - as_utc(profile.location_at) > timedelta(minutes=15):
            continue
        distance = distance_km(incident.latitude, incident.longitude, profile.latitude, profile.longitude)
        workload = recent_workload.get(account.id, 0)
        distance_score = max(0.0, 1.0 - min(distance, 100.0) / 100.0)
        workload_score = 1.0 / (1.0 + workload)
        score = (max(0.0, distance_weight) * distance_score + max(0.0, workload_weight) * workload_score) / total_weight if total_weight else 0.0
        reasons = [f"Matching capability and eligible availability", f"Fresh accurate GPS: {distance:.1f} km away", f"Completed assignments in last 24 hours: {workload}"]
        candidates.append((-score, account.display_name.casefold(), account, profile, score, reasons))
    candidates.sort(key=lambda row: (row[0], row[1]))
    return (candidates[0][2], candidates[0][3], round(candidates[0][4] * 100, 1), candidates[0][5]) if candidates else None


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
        "assignment_source": assignment.assignment_source if assignment else None,
        "resource_id": resource.id if resource else None,
        "resource_name": resource.name if resource else None,
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
        "intake_data": incident.intake_data or {},
    }
    if include_analysis:
        analysis = db.get(IncidentAnalysis, incident.id)
        result["analysis"] = {
            "status": analysis.status,
            "provider": analysis.provider,
            "model": analysis.model,
            "result": analysis.result,
            "validation_outcome": analysis.validation_outcome,
            "attempt_count": analysis.attempt_count,
            "last_error_type": analysis.last_error_type,
            "completed_at": analysis.completed_at,
        } if analysis else None
    return result


def require_incident_scope(db: Session, user: User, incident_id: str) -> Incident:
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    if user.role == "admin" and "view_incidents" not in (user.permissions or []):
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


def create_resolution_report(db: Session, incident: Incident) -> IncidentReport:
    existing = db.scalar(select(IncidentReport).where(IncidentReport.incident_id == incident.id).order_by(IncidentReport.version.desc()))
    if existing:
        return existing
    updates = db.scalars(select(IncidentUpdate).where(IncidentUpdate.incident_id == incident.id).order_by(IncidentUpdate.created_at)).all()
    assignments = db.scalars(select(Assignment).where(Assignment.incident_id == incident.id).order_by(Assignment.assigned_at)).all()
    sources = [{"type": "incident", "id": incident.id, "created_at": incident.created_at.isoformat()}]
    timeline = [{"at": row.created_at.isoformat(), "source": row.kind, "actor_id": row.actor_id, "detail": row.message} for row in updates]
    for row in assignments:
        timeline.append({"at": row.assigned_at.isoformat(), "source": "assignment", "actor_id": row.assigned_by or "system", "detail": f"Assignment recorded with status {row.status}; source {row.assignment_source}."})
        sources.append({"type": "assignment", "id": row.id})
    sources.extend({"type": "incident_update", "id": row.id} for row in updates)
    timeline.sort(key=lambda item: item["at"])
    actions = [row.message for row in updates if row.kind in ("message", "status")]
    content = {
        "incident_overview": {"incident_id": incident.id, "reference": incident.reference, "category": incident.emergency_type, "reported_at": incident.created_at.isoformat(), "location": incident.location_label, "original_description": incident.description, "priority": incident.priority, "status": incident.status},
        "what_happened": "Summary of persisted user report and responder observations; no independent verification performed.",
        "response_timeline": timeline,
        "actions_taken": actions,
        "outcome": f"Stored incident status is {incident.status}. No further outcome is inferred.",
        "cause": "Cause not established from the available information.",
        "follow_up_recommendations": [],
        "evidence_and_limitations": {"source_record_ids": [item.get("id") for item in sources], "limitations": ["This is an evidence-based summary of application records, not an independent investigation.", "Cause and outcomes are not independently verified."]},
        "report_metadata": {"version": 1, "generated_at": now_utc().isoformat(), "reviewed": False},
    }
    report = IncidentReport(incident_id=incident.id, version=1, status="generated", content=content, source_records=sources, generated_by="evidence_template")
    db.add(report)
    notify(db, incident.reporter_id, f"incident:{incident.id}:report:1", "incident_report", "Resolution report available", f"A report for incident {incident.reference} is available in your account.", incident.id)
    notify_coordinators(db, f"incident:{incident.id}:report:1", "incident_report", "Resolution report generated", f"A report for incident {incident.reference} is ready for review.", incident.id)
    return report


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash) or not user.active:
        raise HTTPException(401, "Email or password is incorrect")
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


@router.post("/auth/accept-invitation", status_code=200)
def accept_invitation(body: InvitationAccept, db: Session = Depends(get_db)):
    invitation = db.scalar(select(AccountInvitation).where(AccountInvitation.token_hash == hash_refresh_token(body.token)).with_for_update())
    now = now_utc()
    if not invitation or invitation.accepted_at or invitation.revoked_at or as_utc(invitation.expires_at) <= now:
        raise HTTPException(400, "This invitation is invalid or expired. Ask an administrator for a new invitation.")
    user = db.get(User, invitation.user_id)
    if not user or user.role != "responder":
        raise HTTPException(400, "This invitation is invalid or expired. Ask an administrator for a new invitation.")
    user.password_hash = hash_password(body.password)
    user.active = True
    profile = db.get(ResponderProfile, user.id)
    if profile:
        profile.available = True
    invitation.accepted_at = now
    audit(db, user, "responder.invitation_accepted", "user", user.id)
    db.commit()
    return {"activated": True, "email": user.email}


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
    notify_coordinators(db, "incident:" + incident.id + ":submitted", "new_incident", "New incident received", f"Incident {incident.reference} was received by the coordination system.", incident.id)
    notify(db, incident.reporter_id, "incident:" + incident.id + ":status:Unassigned", "incident_status", "Incident received", f"Your incident {incident.reference} was received by the coordination system.", incident.id)
    policy = db.get(CoordinationPolicy, "default")
    auto_enabled = bool(policy and policy.auto_assignment_enabled)
    if auto_enabled and body.severity <= policy.auto_assign_max_severity:
        candidate = automatic_candidate(db, incident)
        if candidate:
            responder, profile, ranking_score, ranking_reasons = candidate
            try:
                with db.begin_nested():
                    db.add(Assignment(incident_id=incident.id, responder_id=responder.id, resource_id=None, assigned_by=None, assignment_source="automatic", status="Assigned"))
                    profile.available = False
                    incident.status = "Assigned"
                    db.add(IncidentUpdate(incident_id=incident.id, actor_id=user.id, kind="auto_assigned", message="Automatically assigned to an eligible responder under the configured policy."))
                    audit(db, user, "incident.auto_assigned", "incident", incident.id, {"responder_id": responder.id, "score": ranking_score, "reasons": ranking_reasons, "policy": "deterministic-v1"})
                    notify(db, responder.id, "incident:" + incident.id + ":assigned:" + responder.id, "assignment", "New incident assigned", f"Incident {incident.reference} is ready to review.", incident.id)
                    notify(db, incident.reporter_id, "incident:" + incident.id + ":status:Assigned", "incident_status", "Responder assigned", f"A responder has been assigned to incident {incident.reference}.", incident.id)
                    notify_coordinators(db, "incident:" + incident.id + ":auto_assigned", "auto_assignment", "Automatic assignment completed", f"Incident {incident.reference} was assigned automatically.", incident.id)
                    db.flush()
            except IntegrityError:
                incident.status = "Unassigned"
                audit(db, user, "incident.auto_assignment_failed", "incident", incident.id, {"reason": "Concurrent assignment constraint", "policy": "deterministic-v1"})
                notify_coordinators(db, "incident:" + incident.id + ":auto_assignment_failed", "automation_failure", "Automatic assignment needs review", f"Assignment for incident {incident.reference} conflicted with another operation; it remains unassigned.", incident.id)
        else:
            notify_coordinators(db, "incident:" + incident.id + ":auto_assignment_review", "automation_review", "Manual review required", f"Incident {incident.reference} was left unassigned because no responder met the automatic policy's skill, availability, and fresh-location requirements.", incident.id)
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


@router.get("/notifications")
def list_notifications(limit: int = Query(default=100, ge=1, le=200), user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(limit)).all()
    return [{"id": row.id, "incident_id": row.incident_id, "kind": row.kind, "title": row.title, "message": row.message, "read": row.read_at is not None, "created_at": row.created_at} for row in rows]


@router.patch("/notifications/read-all")
def read_all_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))).all()
    stamp = now_utc()
    for row in rows:
        row.read_at = stamp
    db.commit()
    return {"updated": len(rows)}


@router.patch("/notifications/{notification_id}/read")
def read_notification(notification_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
    if not row:
        raise HTTPException(404, "Notification not found")
    row.read_at = row.read_at or now_utc()
    db.commit()
    return {"read": True, "id": row.id}


@router.get("/admin/automation")
def get_automation_policy(_admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    policy = db.get(CoordinationPolicy, "default")
    if not policy:
        policy = CoordinationPolicy(id="default", auto_assignment_enabled=False, auto_assign_max_severity=3)
        db.add(policy)
        db.commit()
    return {"enabled": policy.auto_assignment_enabled, "max_severity": policy.auto_assign_max_severity, "requires_fresh_accurate_location": True, "version": "deterministic-v1"}


@router.put("/admin/automation")
def update_automation_policy(body: AutomaticAssignmentPolicyUpdate, admin: User = Depends(require_roles("super_admin")), db: Session = Depends(get_db)):
    policy = db.scalar(select(CoordinationPolicy).where(CoordinationPolicy.id == "default").with_for_update())
    if not policy:
        policy = CoordinationPolicy(id="default")
        db.add(policy)
    policy.auto_assignment_enabled = body.enabled
    policy.auto_assign_max_severity = body.max_severity
    policy.updated_by = admin.id
    policy.updated_at = now_utc()
    audit(db, admin, "automation.policy_updated", "coordination_policy", "default", {"enabled": body.enabled, "max_severity": body.max_severity})
    db.commit()
    return {"enabled": policy.auto_assignment_enabled, "max_severity": policy.auto_assign_max_severity, "requires_fresh_accurate_location": True, "version": "deterministic-v1"}


@router.get("/incidents")
def list_incidents(
    status_filter: str | None = Query(default=None, alias="status"),
    query: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if user.role == "admin" and "view_incidents" not in (user.permissions or []):
        raise HTTPException(403, "Missing permission: view_incidents")
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
    return [{"id": row.id, "kind": row.kind, "message": row.message, "original_message": row.original_message, "ai_assisted": row.ai_assisted, "actor_id": row.actor_id, "created_at": row.created_at} for row in rows]


@router.get("/incidents/{incident_id}/intake")
def get_incident_intake(incident_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    incident = require_incident_scope(db, user, incident_id)
    stored = incident.intake_data or {}
    category = incident.emergency_type.casefold()
    if "fire" in category:
        candidates = [("people_at_risk", "Is anyone injured or trapped?"), ("spread", "Is the fire or smoke spreading?"), ("area", "What area is affected, if known?"), ("hazards", "Are there other immediate hazards, if known?")]
    elif "medical" in category or "ambulance" in category:
        candidates = [("injuries", "What injuries or symptoms are visible, if known?"), ("people_at_risk", "How many people need help, if known?"), ("hazards", "Is it safe for responders to approach?")]
    elif "police" in category or "security" in category:
        candidates = [("threat", "Is there an immediate threat to anyone?"), ("people_at_risk", "Is anyone injured or trapped?"), ("hazards", "Are there hazards responders should know about?")]
    else:
        candidates = [("people_at_risk", "Is anyone injured or trapped?"), ("hazards", "Are there immediate hazards responders should know about?"), ("details", "What additional detail may help responders?")]
    report_text = (incident.description + " " + incident.location_label).casefold()
    described = {
        "people_at_risk": any(term in report_text for term in ("injur", "trapped", "casualt", "no one", "nobody")),
        "spread": any(term in report_text for term in ("spreading", "not spreading", "contained")),
        "area": any(term in report_text for term in ("room", "building", "vehicle", "outdoor", "floor", "kitchen", "warehouse")),
        "hazards": any(term in report_text for term in ("hazard", "gas leak", "chemical", "fuel", "cylinder", "live wire", "weapon")),
        "injuries": any(term in report_text for term in ("injur", "pain", "bleeding", "unconscious")),
        "threat": any(term in report_text for term in ("threat", "attack", "weapon", "gun")),
    }
    questions = [{"key": key, "question": question} for key, question in candidates if key not in stored and not described.get(key, False)]
    analysis = db.get(IncidentAnalysis, incident.id)
    suggested = (analysis.result or {}).get("missing_information", []) if analysis and analysis.result else []
    return {"incident_id": incident.id, "answers": stored, "questions": questions[:3], "ai_missing_information": suggested[:3], "dispatch_status": incident.status, "answers_optional": True}


@router.post("/incidents/{incident_id}/intake/answers", status_code=201)
def submit_intake_answers(incident_id: str, body: IntakeAnswers, user: User = Depends(current_user), db: Session = Depends(get_db)):
    incident = require_incident_scope(db, user, incident_id)
    allowed = {"people_at_risk", "spread", "area", "hazards", "injuries", "threat", "details"}
    if set(body.answers) - allowed:
        raise HTTPException(422, "Unsupported intake answer field")
    data = dict(incident.intake_data or {})
    normalized = {key: (value.strip() if value and value.strip().casefold() not in ("unknown", "skip", "skipped") else None) for key, value in body.answers.items()}
    data.update(normalized)
    incident.intake_data = data
    summary = "; ".join(f"{key.replace('_', ' ')}: {value if value is not None else 'unknown/not provided'}" for key, value in normalized.items())
    db.add(IncidentUpdate(incident_id=incident.id, actor_id=user.id, kind="intake_answer", message=f"Follow-up answers recorded (user-reported): {summary}"[:1000]))
    audit(db, user, "incident.intake_answered", "incident", incident.id, {"fields": sorted(normalized)})
    db.commit()
    return {"incident_id": incident.id, "answers": incident.intake_data, "dispatch_status": incident.status}


@router.post("/responder/incidents/{incident_id}/rewrite")
async def rewrite_update(incident_id: str, body: RewriteRequest, responder: User = Depends(require_roles("responder")), db: Session = Depends(get_db)):
    incident = require_incident_scope(db, responder, incident_id)
    if incident.status in ("Resolved", "Cancelled") or not db.scalar(select(Assignment.id).where(Assignment.incident_id == incident.id, Assignment.responder_id == responder.id, Assignment.status.in_(ACTIVE_ASSIGNMENTS))):
        raise HTTPException(409, "Only the currently assigned responder can draft an update")
    draft, outcome = await rewrite_responder_note(body.note)
    audit(db, responder, "incident.note_rewrite_requested", "incident", incident.id, {"outcome": outcome})
    db.commit()
    return {"original": body.note.strip(), "suggestion": draft, "outcome": outcome, "requires_responder_review": True}


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
    if body.ai_assisted and (user.role != "responder" or not body.original_message):
        raise HTTPException(422, "AI-assisted updates require the responder's original note")
    row = IncidentUpdate(incident_id=incident.id, actor_id=user.id, kind="message", message=body.message.strip(), original_message=body.original_message.strip() if body.original_message else None, ai_assisted=body.ai_assisted)
    db.add(row)
    audit(db, user, "incident.message", "incident", incident.id)
    db.commit()
    return {"id": row.id, "kind": row.kind, "message": row.message, "created_at": row.created_at}


@router.get("/incidents/{incident_id}/report")
def get_incident_report(incident_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    incident = require_incident_scope(db, user, incident_id)
    report = db.scalar(select(IncidentReport).where(IncidentReport.incident_id == incident.id).order_by(IncidentReport.version.desc()))
    if report is None:
        raise HTTPException(404, "No resolution report is available")
    return {"id": report.id, "incident_id": report.incident_id, "version": report.version, "status": report.status, "content": report.content, "source_records": report.source_records, "generated_by": report.generated_by, "reviewed_by": report.reviewed_by, "reviewed_at": report.reviewed_at, "review_note": report.review_note, "created_at": report.created_at}


@router.post("/admin/incidents/{incident_id}/report/review")
def review_incident_report(incident_id: str, body: ReportReview, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    if admin.role == "admin" and "update_incidents" not in (admin.permissions or []):
        raise HTTPException(403, "Missing permission: update_incidents")
    incident = db.get(Incident, incident_id)
    report = db.scalar(select(IncidentReport).where(IncidentReport.incident_id == incident_id).order_by(IncidentReport.version.desc()))
    if not incident or not report:
        raise HTTPException(404, "Incident report not found")
    report.status, report.reviewed_by, report.reviewed_at, report.review_note = "reviewed", admin.id, now_utc(), body.note.strip()
    audit(db, admin, "incident.report_reviewed", "incident_report", report.id, {"version": report.version})
    db.commit()
    return {"id": report.id, "version": report.version, "status": report.status, "reviewed_at": report.reviewed_at}


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
    rows = db.execute(select(User, ResponderProfile).join(ResponderProfile, ResponderProfile.user_id == User.id).order_by(User.display_name)).all()
    result = []
    active_by_responder = {a.responder_id: a for a in db.scalars(select(Assignment).where(Assignment.status.in_(ACTIVE_ASSIGNMENTS))).all()}
    for account, profile in rows:
        active = active_by_responder.get(account.id)
        active_incident = db.get(Incident, active.incident_id) if active else None
        active_resource = db.get(Resource, active.resource_id) if active and active.resource_id else None
        invitation = db.scalar(select(AccountInvitation).where(AccountInvitation.user_id == account.id).order_by(AccountInvitation.created_at.desc()))
        result.append({"id": account.id, "display_name": account.display_name, "email": account.email,
                       "capabilities": profile.capabilities, "available": profile.available,
                       "active": account.active, "invitation_status": "accepted" if invitation and invitation.accepted_at else "revoked" if invitation and invitation.revoked_at else "pending" if invitation else "none",
                       "invitation_expires_at": invitation.expires_at if invitation and not invitation.accepted_at and not invitation.revoked_at else None,
                       "active_incident_id": active.incident_id if active else None,
                       "active_incident_reference": active_incident.reference if active_incident else None,
                       "active_resource_name": active_resource.name if active_resource else None,
                       "latitude": profile.latitude, "longitude": profile.longitude,
                       "location_accuracy_m": profile.location_accuracy_m, "location_at": profile.location_at})
    return result


@router.post("/admin/invitations/responders", status_code=201)
def invite_responder(body: ResponderInviteCreate, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    limit_invitation_requests(admin.id)
    settings = get_settings()
    if settings.environment == "production" and not settings.public_app_url.startswith("https://"):
        raise HTTPException(503, "Responder activation requires an HTTPS public application URL")
    email = str(body.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    capabilities = sorted({x.strip().lower() for x in body.capabilities if x.strip()})
    if not capabilities:
        raise HTTPException(422, "At least one responder capability is required")
    user = User(email=email, display_name=body.display_name.strip(), password_hash=hash_password(secrets.token_urlsafe(40)), role="responder", active=False)
    db.add(user)
    db.flush()
    db.add(ResponderProfile(user_id=user.id, capabilities=capabilities, available=False))
    raw_token = secrets.token_urlsafe(48)
    invitation = AccountInvitation(user_id=user.id, token_hash=hash_refresh_token(raw_token), expires_at=now_utc() + timedelta(hours=24))
    db.add(invitation)
    audit(db, admin, "responder.invitation_created", "user", user.id, {"capabilities": capabilities})
    db.commit()
    link = f"{get_settings().public_app_url.rstrip('/')}/activate.html?token={raw_token}"
    delivered = send_invitation_email(email, user.display_name, link)
    if not delivered:
        invitation.revoked_at = now_utc()
        user.active = False
        audit(db, admin, "responder.invitation_delivery_failed", "user", user.id)
        db.commit()
        raise HTTPException(502, "Invitation email delivery failed. Check the mail configuration and resend.")
    return {"user_id": user.id, "email": user.email, "invitation_status": "sent" if get_settings().smtp_host else "development_link", "expires_at": invitation.expires_at, "activation_url": link if not get_settings().smtp_host and get_settings().environment == "development" else None}


@router.get("/admin/invitations")
def list_invitations(_admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    rows = db.scalars(select(AccountInvitation).order_by(AccountInvitation.created_at.desc())).all()
    return [{"id": x.id, "user_id": x.user_id, "email": (db.get(User, x.user_id).email if db.get(User, x.user_id) else ""),
             "created_at": x.created_at, "expires_at": x.expires_at, "accepted_at": x.accepted_at, "revoked_at": x.revoked_at} for x in rows]


@router.post("/admin/invitations/{invitation_id}/revoke")
def revoke_invitation(invitation_id: str, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    row = db.get(AccountInvitation, invitation_id)
    if not row or row.accepted_at or row.revoked_at:
        raise HTTPException(404, "Pending invitation not found")
    row.revoked_at = now_utc()
    account = db.get(User, row.user_id)
    if account:
        audit(db, admin, "responder.invitation_revoked", "user", account.id)
    db.commit()
    return {"revoked": True}


@router.post("/admin/invitations/responders/{user_id}/resend", status_code=201)
def resend_responder_invitation(user_id: str, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    limit_invitation_requests(admin.id)
    user = db.get(User, user_id)
    if not user or user.role != "responder" or user.active:
        raise HTTPException(404, "Pending responder invitation not found")
    latest = db.scalar(select(AccountInvitation).where(AccountInvitation.user_id == user.id).order_by(AccountInvitation.created_at.desc()))
    if latest and not latest.accepted_at and not latest.revoked_at and as_utc(latest.expires_at) > now_utc():
        raise HTTPException(409, "The current invitation is still valid")
    if latest and not latest.accepted_at and not latest.revoked_at:
        latest.revoked_at = now_utc()
    raw_token = secrets.token_urlsafe(48)
    invitation = AccountInvitation(user_id=user.id, token_hash=hash_refresh_token(raw_token), expires_at=now_utc() + timedelta(hours=24))
    db.add(invitation)
    audit(db, admin, "responder.invitation_resent", "user", user.id)
    db.commit()
    link = f"{get_settings().public_app_url.rstrip('/')}/activate.html?token={raw_token}"
    delivered = send_invitation_email(user.email, user.display_name, link)
    if not delivered:
        invitation.revoked_at = now_utc()
        db.commit()
        raise HTTPException(502, "Invitation email delivery failed. Check the mail configuration and try again.")
    return {"invitation_status": "sent" if get_settings().smtp_host else "development_link", "expires_at": invitation.expires_at,
            "activation_url": link if not get_settings().smtp_host and get_settings().environment == "development" else None}


@router.get("/admin/users")
def admin_users(role: str | None = Query(default=None, pattern="^(user|responder|admin|super_admin)$"), admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    # An unfiltered account listing includes user and administrator records. Co-Admins
    # must request an explicitly scoped role so a management permission cannot expose
    # accounts outside that role's authorization boundary.
    if role is None and admin.role != "super_admin":
        raise HTTPException(403, "Co-Admins must specify an account role to view")
    if role in ("admin", "super_admin") and admin.role != "super_admin":
        raise HTTPException(403, "Only a Super Admin may view protected administrator accounts")
    statement = select(User).order_by(User.created_at.desc())
    if role:
        statement = statement.where(User.role == role)
    rows = db.scalars(statement).all()
    return [{"id": row.id, "email": row.email, "display_name": row.display_name, "role": row.role, "active": row.active, "created_at": row.created_at} for row in rows]


@router.get("/admin/coadmins")
def list_coadmins(admin: User = Depends(require_roles("super_admin")), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).where(User.role == "admin").order_by(User.created_at.desc())).all()
    return [{"id": row.id, "email": row.email, "display_name": row.display_name, "active": row.active,
             "permissions": row.permissions or [], "created_at": row.created_at} for row in rows]


@router.post("/admin/coadmins", status_code=201)
def create_coadmin(body: CoAdminCreate, admin: User = Depends(require_roles("super_admin")), db: Session = Depends(get_db)):
    email = str(body.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    allowed = {"view_dashboard", "view_incidents", "update_incidents", "assign_responders", "manage_responders", "manage_users", "manage_resources", "view_reports", "export_reports", "view_audit_logs"}
    requested = sorted(set(body.permissions))
    if not set(requested) <= allowed:
        raise HTTPException(422, "One or more requested permissions are not supported")
    account = User(email=email, display_name=body.display_name.strip(), password_hash=hash_password(body.password), role="admin", permissions=requested)
    db.add(account)
    db.flush()
    audit(db, admin, "coadmin.created", "user", account.id, {"permissions": requested})
    db.commit()
    return {"id": account.id, "email": account.email, "display_name": account.display_name, "role": account.role, "permissions": account.permissions}


@router.patch("/admin/coadmins/{user_id}/active")
def set_coadmin_active(user_id: str, active: bool = Query(...), admin: User = Depends(require_roles("super_admin")), db: Session = Depends(get_db)):
    account = db.get(User, user_id)
    if not account or account.role != "admin":
        raise HTTPException(404, "Co-Admin not found")
    account.active = active
    if not active:
        db.query(AuthSession).filter(AuthSession.user_id == account.id, AuthSession.revoked_at.is_(None)).update({"revoked_at": now_utc()})
    audit(db, admin, "coadmin.access_changed", "user", account.id, {"active": active})
    db.commit()
    return {"id": account.id, "active": account.active}


@router.patch("/admin/coadmins/{user_id}/permissions")
def update_coadmin_permissions(user_id: str, permissions: list[str], admin: User = Depends(require_roles("super_admin")), db: Session = Depends(get_db)):
    account = db.get(User, user_id)
    if not account or account.role != "admin":
        raise HTTPException(404, "Co-Admin not found")
    allowed = {"view_dashboard", "view_incidents", "update_incidents", "assign_responders", "manage_responders", "manage_users", "manage_resources", "view_reports", "export_reports", "view_audit_logs"}
    normalized = sorted(set(permissions))
    if not set(normalized) <= allowed:
        raise HTTPException(422, "One or more requested permissions are not supported")
    account.permissions = normalized
    audit(db, admin, "coadmin.permissions_changed", "user", account.id, {"permissions": normalized})
    db.commit()
    return {"id": account.id, "permissions": normalized}


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
    elif analysis.status == "ready" and not analysis.last_error_type:
        raise HTTPException(409, "Validated analysis is already available")
    elif analysis.status == "processing":
        started = analysis.completed_at or analysis.last_attempt_at or analysis.created_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if now_utc() - started < timedelta(seconds=90):
            raise HTTPException(409, "Incident analysis is already running")
    analysis.status = "pending"
    analysis.provider = "pending"
    analysis.validation_outcome = "retry_requested"
    analysis.attempt_count = 0
    analysis.last_attempt_at = None
    analysis.last_error_type = None
    analysis.completed_at = None
    audit(db, admin, "incident.analysis_retry_requested", "incident", incident.id)
    db.commit()
    background_tasks.add_task(analyze_incident_task, incident.id)
    return {"incident_id": incident.id, "analysis_status": "pending"}


@router.post("/admin/users", status_code=201, response_model=UserView)
def create_account(body: UserCreate, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    if body.role == "responder":
        raise HTTPException(409, "Responders must be created through the email invitation and activation workflow")
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
def set_account_active(user_id: str, active: bool = Query(...), admin: User = Depends(require_account_management), db: Session = Depends(get_db)):
    account = db.get(User, user_id)
    if not account or account.role in ("admin", "super_admin") or account.id == admin.id:
        raise HTTPException(404, "Account not found")
    if account.role == "responder":
        profile = db.get(ResponderProfile, account.id)
        pending_invitation = db.scalar(select(AccountInvitation).where(AccountInvitation.user_id == account.id, AccountInvitation.accepted_at.is_(None), AccountInvitation.revoked_at.is_(None)))
        if active and pending_invitation:
            raise HTTPException(409, "Responder must complete the invitation before activation")
        if not active and db.scalar(select(Assignment.id).where(Assignment.responder_id == account.id, Assignment.status.in_(ACTIVE_ASSIGNMENTS))):
            raise HTTPException(409, "Reassign or resolve the active task before deactivating this responder")
        if profile:
            profile.available = active
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
    allocation_rows = db.execute(select(
        Assignment.resource_id,
        Assignment.incident_id,
        Incident.reference,
        User.display_name,
    ).join(Incident, Incident.id == Assignment.incident_id)
     .join(User, User.id == Assignment.responder_id)
     .where(Assignment.resource_id.is_not(None), Assignment.status.in_(ACTIVE_ASSIGNMENTS))
     .order_by(Assignment.assigned_at.desc())).all()
    allocations_by_resource: dict[str, list[dict]] = {}
    for row in allocation_rows:
        allocations_by_resource.setdefault(row.resource_id, []).append({
            "incident_id": row.incident_id,
            "incident_reference": row.reference,
            "responder_name": row.display_name,
        })
    result = []
    for resource in db.scalars(select(Resource).order_by(Resource.kind, Resource.name)).all():
        result.append({"id": resource.id, "name": resource.name, "kind": resource.kind,
                       "quantity": resource.quantity, "allocated": resource.allocated,
                       "available": resource.quantity-resource.allocated, "active": resource.active,
                       "allocations": allocations_by_resource.get(resource.id, [])})
    return result


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
    assignment = Assignment(incident_id=incident.id, responder_id=responder.id, resource_id=body.resource_id, assigned_by=admin.id, assignment_source="manual", status="Assigned")
    db.add(assignment)
    profile.available = False
    incident.status = "Assigned"
    incident.updated_at = now_utc()
    db.add(IncidentUpdate(incident_id=incident.id, actor_id=admin.id, kind="assigned", message=f"Assigned to {responder.display_name}."))
    audit(db, admin, "incident.assigned", "incident", incident.id, {"responder_id": responder.id, "resource_id": body.resource_id})
    notify(db, responder.id, "incident:" + incident.id + ":assigned:" + responder.id, "assignment", "New incident assigned", f"Incident {incident.reference} is ready to review.", incident.id)
    notify_status_change(db, incident, "Assigned")
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
    replacement = Assignment(incident_id=incident.id, responder_id=responder.id, resource_id=resource_id, assigned_by=admin.id, assignment_source="manual", status="Assigned")
    db.add(replacement)
    profile.available = False
    incident.status = "Assigned"
    db.add(IncidentUpdate(incident_id=incident.id, actor_id=admin.id, kind="reassigned", message=f"Reassigned to {responder.display_name}."))
    audit(db, admin, "incident.reassigned", "incident", incident.id, {"from": old.responder_id, "to": responder.id})
    notify(db, old.responder_id, "incident:" + incident.id + ":reassigned_from:" + old.responder_id, "assignment_changed", "Incident reassigned", f"Incident {incident.reference} was reassigned.", incident.id)
    notify(db, responder.id, "incident:" + incident.id + ":assigned:" + responder.id, "assignment", "New incident assigned", f"Incident {incident.reference} is ready to review.", incident.id)
    notify_status_change(db, incident, "Assigned")
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
    if assignment:
        notify(db, assignment.responder_id, "incident:" + incident.id + ":cancelled:" + assignment.responder_id, "assignment_changed", "Incident cancelled", f"Incident {incident.reference} was cancelled.", incident.id)
    notify_status_change(db, incident, "Cancelled")
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
    if assignment:
        notify(db, assignment.responder_id, "incident:" + incident.id + ":resolved:" + assignment.responder_id, "incident_status", "Incident resolved", f"Incident {incident.reference} was marked resolved.", incident.id)
    notify_status_change(db, incident, "Resolved")
    create_resolution_report(db, incident)
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
    notify_status_change(db, incident, body.status)
    notify_coordinators(db, "incident:" + incident.id + ":status:" + body.status, "incident_status", "Incident status changed", f"Incident {incident.reference} is now {body.status}.", incident.id)
    if body.status == "Resolved":
        create_resolution_report(db, incident)
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
