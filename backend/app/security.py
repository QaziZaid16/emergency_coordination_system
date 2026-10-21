from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException, status
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


def issue_token(user: User, db: Session) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.access_token_minutes)
    jti = str(uuid4())
    token = jwt.encode(
        {"sub": user.id, "role": user.role, "iat": now, "exp": expires, "jti": jti},
        settings.jwt_secret,
        algorithm="HS256",
    )
    db.add(AuthSession(jti=jti, user_id=user.id, expires_at=expires))
    db.commit()
    return token, expires


def current_user(
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
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Your role cannot perform this operation")
        return user
    return dependency
