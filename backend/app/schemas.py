from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

Role = Literal["super_admin", "admin", "user", "responder"]
EmergencyType = Literal[
    "Ambulance / Medical Emergency",
    "Fire and Rescue",
    "Police / Security",
    "Other Emergency",
]


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["user", "responder"]
    capabilities: list[str] = Field(default_factory=list, max_length=20)


class CoAdminCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    permissions: list[str] = Field(default_factory=list, max_length=20)


class ResponderInviteCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    capabilities: list[str] = Field(min_length=1, max_length=20)


class InvitationAccept(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=12, max_length=128)


class UserRegister(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    remember_me: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    remember_me: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=128)


class UserView(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    role: Role
    permissions: list[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    refresh_token: str | None = None
    session_expires_at: datetime
    user: UserView


class IncidentCreate(BaseModel):
    emergency_type: EmergencyType
    description: str = Field(min_length=3, max_length=2000)
    location_label: str = Field(min_length=2, max_length=240)
    location_source: Literal["gps", "manual"]
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=100000)
    location_at: datetime | None = None
    severity: int = Field(default=3, ge=1, le=5)
    urgency: int = Field(default=3, ge=1, le=5)

    @model_validator(mode="after")
    def validate_location(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if self.location_source == "gps" and (
            self.latitude is None or self.location_at is None
        ):
            raise ValueError(
                "GPS location requires coordinates and a capture timestamp"
            )
        if self.location_source == "gps":
            captured = self.location_at
            if captured is not None and captured.tzinfo is None:
                captured = captured.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if captured is not None and (
                now - captured > timedelta(minutes=15)
                or captured > now + timedelta(minutes=1)
            ):
                raise ValueError(
                    "GPS location must be captured within the last 15 minutes"
                )
        return self


class AssignmentCreate(BaseModel):
    responder_id: str
    resource_id: str | None = None


class StatusUpdate(BaseModel):
    status: Literal["Accepted", "En Route", "On Scene", "Resolved"]


class MessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ResourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(min_length=1, max_length=48)
    quantity: int = Field(ge=0, le=10000)


class AvailabilityUpdate(BaseModel):
    available: bool


class AutomaticAssignmentPolicyUpdate(BaseModel):
    enabled: bool
    max_severity: int = Field(ge=1, le=5)


class ResponderLocation(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(ge=0, le=100000)
    captured_at: datetime


class CopilotQuestion(BaseModel):
    question: str = Field(min_length=2, max_length=240)
