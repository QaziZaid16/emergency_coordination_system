from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(16), index=True)
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


class ResponderProfile(Base):
    __tablename__ = "responders"
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    latitude: Mapped[float | None]
    longitude: Mapped[float | None]
    location_accuracy_m: Mapped[float | None]
    location_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountInvitation(Base):
    __tablename__ = "account_invitations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint("severity BETWEEN 1 AND 5", name="ck_incident_severity"),
        CheckConstraint("urgency BETWEEN 1 AND 5", name="ck_incident_urgency"),
        CheckConstraint(
            "latitude IS NULL OR (latitude BETWEEN -90 AND 90)",
            name="ck_incident_latitude",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude BETWEEN -180 AND 180)",
            name="ck_incident_longitude",
        ),
        UniqueConstraint(
            "reporter_id", "idempotency_key", name="uq_incident_reporter_idempotency"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reference: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    emergency_type: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    location_label: Mapped[str] = mapped_column(String(240))
    location_source: Mapped[str] = mapped_column(String(16))
    latitude: Mapped[float | None]
    longitude: Mapped[float | None]
    accuracy_m: Mapped[float | None]
    location_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    severity: Mapped[int] = mapped_column(Integer, default=3)
    urgency: Mapped[int] = mapped_column(Integer, default=3)
    priority: Mapped[str] = mapped_column(String(16), index=True)
    priority_reason: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(24), default="Submitted", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class IncidentAnalysis(Base):
    __tablename__ = "incident_analyses"
    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    provider: Mapped[str] = mapped_column(String(64), default="pending")
    model: Mapped[str | None] = mapped_column(String(120))
    result: Mapped[dict | None] = mapped_column(JSON)
    validation_outcome: Mapped[str] = mapped_column(String(32), default="pending")
    usage_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_type: Mapped[str | None] = mapped_column(String(80))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint(
            "quantity >= 0 AND allocated >= 0 AND allocated <= quantity",
            name="ck_resource_quantity",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    kind: Mapped[str] = mapped_column(String(48), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    allocated: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        Index(
            "uq_active_assignment_responder",
            "responder_id",
            unique=True,
            sqlite_where=text(
                "status IN ('Assigned','Accepted','En Route','On Scene')"
            ),
            postgresql_where=text(
                "status IN ('Assigned','Accepted','En Route','On Scene')"
            ),
        ),
        Index(
            "uq_active_assignment_incident",
            "incident_id",
            unique=True,
            sqlite_where=text(
                "status IN ('Assigned','Accepted','En Route','On Scene')"
            ),
            postgresql_where=text(
                "status IN ('Assigned','Accepted','En Route','On Scene')"
            ),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    responder_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    resource_id: Mapped[str | None] = mapped_column(ForeignKey("resources.id"))
    status: Mapped[str] = mapped_column(String(24), default="Assigned", index=True)
    assigned_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assignment_source: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IncidentUpdate(Base):
    __tablename__ = "incident_updates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(24))
    message: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "event_key", name="uq_notification_user_event"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    event_key: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(String(240))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class CoordinationPolicy(Base):
    __tablename__ = "coordination_policy"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default="default")
    auto_assignment_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_assign_max_severity: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index(
            "uq_auth_sessions_refresh_token_hash",
            "refresh_token_hash",
            unique=True,
            sqlite_where=text("refresh_token_hash IS NOT NULL"),
            postgresql_where=text("refresh_token_hash IS NOT NULL"),
        ),
    )
    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    refresh_token_hash: Mapped[str | None] = mapped_column(String(64))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
