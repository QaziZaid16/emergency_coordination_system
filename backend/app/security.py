from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AuthSession, User

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def hash_password(raw: str) -> str:
    return password_hash.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return password_hash.verify(raw, hashed)
    except Exception:
        return False


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def encode_access_token(user: User, jti: str, now: datetime, expires: datetime) -> str:
    return jwt.encode(
        {"sub": user.id, "role": user.role, "iat": now, "exp": expires, "jti": jti},
        get_settings().jwt_secret,
        algorithm="HS256",
    )


def issue_token(
    user: User, db: Session, remember_me: bool = False
) -> tuple[str, datetime, str | None, datetime]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    access_expires = now + timedelta(minutes=settings.access_token_minutes)
    session_expires = (
        now + timedelta(days=settings.remember_me_days)
        if remember_me
        else access_expires
    )
    jti = str(uuid4())
    refresh_token = secrets.token_urlsafe(48) if remember_me else None
    token = encode_access_token(user, jti, now, access_expires)
    db.add(AuthSession(
        jti=jti,
        user_id=user.id,
        expires_at=session_expires,
        refresh_token_hash=hash_refresh_token(refresh_token) if refresh_token else None,
    ))
    db.commit()
    return token, access_expires, refresh_token, session_expires


def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="A valid session is required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=["HS256"])
        user = db.get(User, claims.get("sub"))
        session = db.get(AuthSession, claims.get("jti"))
    except (jwt.InvalidTokenError, TypeError):
        raise unauthorized
    now = datetime.now(timezone.utc)
    if (not user or not user.active or not session or session.revoked_at
            or session.expires_at.replace(tzinfo=timezone.utc) <= now
            or claims.get("role") != user.role):
        raise unauthorized
    if user.role == "admin":
        path = request.url.path
        required = None
        if path.endswith("/incidents") or path.endswith("/changes") or path.startswith("/api/v1/incidents/"):
            required = "update_incidents" if request.method in ("POST", "PATCH", "PUT", "DELETE") else "view_incidents"
        if required and required not in (user.permissions or []):
            alternative = (
                path == "/api/v1/admin/responders" and request.method == "GET" and "manage_responders" in (user.permissions or [])
            ) or (
                path == "/api/v1/admin/resources" and request.method == "GET" and "manage_resources" in (user.permissions or [])
            )
            if not alternative:
                raise HTTPException(status_code=403, detail=f"Missing permission: {required}")
    return user


def require_roles(*roles: str):
    def dependency(request: Request, user: User = Depends(current_user)) -> User:
        accepted = set(roles)
        if "admin" in accepted:
            accepted.add("super_admin")
        if user.role not in accepted:
            raise HTTPException(status_code=403, detail="Your role cannot perform this operation")
        if user.role == "admin":
            path = request.url.path
            method = request.method
            required = "view_dashboard"
            if "/admin/responders" in path:
                required = "manage_responders" if method != "GET" else "view_dashboard"
            elif "/admin/invitations" in path:
                required = "manage_responders"
            elif "/admin/users" in path:
                required = "manage_users" if method != "GET" or request.query_params.get("role") == "user" else "manage_responders"
            elif "/incidents/" in path and method in ("POST", "PATCH", "PUT", "DELETE"):
                required = "assign_responders" if path.endswith(("/assign", "/reassign")) else "update_incidents"
            elif "/incidents/" in path or path.endswith("/incidents"):
                required = "view_incidents"
            elif "/responders" in path or ("/users" in path and method != "GET"):
                required = "manage_responders" if "/responders" in path else "manage_users"
            elif "/resources" in path:
                required = "manage_resources" if method != "GET" else "view_dashboard"
            elif path == "/api/v1/admin/public-disaster-data" and method == "GET":
                required = "view_reports"
            elif "/audit" in path:
                required = "view_audit_logs"
            elif "/analytics" in path:
                required = "view_reports"
            permissions = set(user.permissions or [])
            listing_override = (
                path == "/api/v1/admin/responders" and method == "GET" and "manage_responders" in permissions
            ) or (
                path == "/api/v1/admin/resources" and method == "GET" and "manage_resources" in permissions
            )
            if required not in permissions and not listing_override:
                raise HTTPException(status_code=403, detail=f"Missing permission: {required}")
        return user
    return dependency
