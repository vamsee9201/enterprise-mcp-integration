import hashlib
import secrets
from datetime import timedelta
from sqlalchemy import select
from backend.app.database.connection import SessionLocal
from backend.app.models.entities import SessionToken, User, utcnow
from backend.app.auth.context import ServiceError


def digest(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(user_id):
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    with SessionLocal.begin() as db:
        user = db.get(User, user_id)
        if not user or not user.active:
            raise ServiceError("Account unavailable", 401)
        db.add(
            SessionToken(
                user_id=user_id,
                kind="WEB",
                token_hash=digest(token),
                csrf_token=csrf,
                expires_at=utcnow() + timedelta(hours=8),
            )
        )
    return token, csrf


def resolve_token(token: str, kind="WEB"):
    with SessionLocal() as db:
        session = db.scalar(
            select(SessionToken).where(
                SessionToken.token_hash == digest(token),
                SessionToken.kind == kind,
                SessionToken.expires_at > utcnow(),
            )
        )
        if not session:
            raise ServiceError("Authentication required or credential expired", 401)
        user = db.get(User, session.user_id)
        if not user or not user.active:
            raise ServiceError("Account unavailable", 401)
        return session


def revoke_token(token: str):
    with SessionLocal.begin() as db:
        session = db.scalar(select(SessionToken).where(SessionToken.token_hash == digest(token)))
        if session:
            db.delete(session)
