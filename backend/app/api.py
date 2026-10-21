from datetime import datetime, timezone
from datetime import timedelta
import secrets
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dispatch import distance_km, priority_for
from app.models import Assignment, AuditEvent, AuthSession, Incident, IncidentUpdate, ResponderProfile, Resource, User, now_utc
from app.schemas import AssignmentCreate, AvailabilityUpdate, IncidentCreate, LoginRequest, LoginResponse, MessageCreate, ResponderLocation, ResourceCreate, StatusUpdate, UserCreate, UserRegister, UserView
from app.security import bearer, current_user, hash_password, issue_token, require_roles, verify_password

router = APIRouter()
ACTIVE_ASSIGNMENTS = ("Assigned", "Accepted", "En Route", "On Scene")
RESPONDER_VISIBLE_ASSIGNMENTS = (*ACTIVE_ASSIGNMENTS, "Resolved", "Completed")
NEXT_STATUS = {"Assigned": "Accepted", "Accepted": "En Route", "En Route": "On Scene", "On Scene": "Resolved"}


def audit(db: Session, actor: User, action: str, entity_type: str, entity_id: str, details: dict | None = None):
    db.add(AuditEvent(actor_id=actor.id, action=action, entity_type=entity_type, entity_id=entity_id, details=details or {}))


def incident_view(db: Session, incident: Incident) -> dict:
    assignment = db.scalar(select(Assignment).where(
        Assignment.incident_id == incident.id,
        Assignment.status.in_(RESPONDER_VISIBLE_ASSIGNMENTS),
    ).order_by(Assignment.assigned_at.desc()))
    responder = db.get(User, assignment.responder_id) if assignment else None
    resource = db.get(Resource, assignment.resource_id) if assignment and assignment.resource_id else None
    return {
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
    token, expires = issue_token(user, db)
    return {"access_token": token, "expires_at": expires, "user": user}


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
    token, expires = issue_token(user, db)
    return {"access_token": token, "expires_at": expires, "user": user}


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
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    user: User = Depends(require_roles("user")),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(Incident).where(Incident.reporter_id == user.id, Incident.idempotency_key == idempotency_key))
    if existing:
        return JSONResponse(status_code=200, content=jsonable_encoder(incident_view(db, existing)))
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
    db.add(IncidentUpdate(incident_id=incident.id, actor_id=user.id, kind="submitted", message="Request received by the coordination system. No external service has been contacted."))
    audit(db, user, "incident.submitted", "incident", incident.id, {"reference": incident.reference})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Incident).where(Incident.reporter_id == user.id, Incident.idempotency_key == idempotency_key))
        if existing:
            return JSONResponse(status_code=200, content=jsonable_encoder(incident_view(db, existing)))
        raise HTTPException(409, "A conflicting request was recorded; refresh your incidents")
    db.refresh(incident)
    return incident_view(db, incident)


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
    return [incident_view(db, item) for item in db.scalars(statement).all()]


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return incident_view(db, require_incident_scope(db, user, incident_id))


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
    profiles = db.execute(select(User, ResponderProfile).join(ResponderProfile).where(User.role == "responder", User.active, ResponderProfile.available.is_(True))).all()
    now = now_utc()
    incident_location_fresh = bool(
        incident.latitude is not None and incident.location_at
        and incident.accuracy_m is not None and incident.accuracy_m <= 100
        and (now - incident.location_at.replace(tzinfo=timezone.utc)) <= timedelta(minutes=15)
    )
    recommendations = []
    for account, profile in profiles:
        if not any(skill in category or category in skill for skill in profile.capabilities):
            continue
        responder_location_fresh = bool(
            profile.latitude is not None and profile.location_at
            and profile.location_accuracy_m is not None and profile.location_accuracy_m <= 100
            and (now - profile.location_at.replace(tzinfo=timezone.utc)) <= timedelta(minutes=15)
        )
        reliable = incident_location_fresh and responder_location_fresh and incident.longitude is not None and profile.longitude is not None
        recommendations.append({
            "responder_id": account.id,
            "display_name": account.display_name,
            "capabilities": profile.capabilities,
            "distance_km": distance_km(incident.latitude, incident.longitude, profile.latitude, profile.longitude) if reliable else None,
            "distance_basis": "fresh_gps" if reliable else "unavailable_or_stale_location",
        })
    recommendations.sort(key=lambda item: (item["distance_km"] is None, item["distance_km"] or 0.0, len(item["capabilities"])))
    return recommendations


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
