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


def issue_mcp_token(user_id, scopes=None, hours=8):
    from backend.app.config import settings
    from backend.app.database.seed import USERS

    if not settings.demo_mode or user_id not in {u["id"] for u in USERS}:
        raise ServiceError(
            "Demo credential issuance is disabled or account is not allowlisted", 403
        )
    scopes = list(dict.fromkeys(scopes if scopes is not None else ["portal:read", "portal:write"]))
    if not scopes or set(scopes) - {"portal:read", "portal:write", "portal:review"}:
        raise ServiceError("Invalid credential scopes", 422)
    if not 0 < hours <= 24:
        raise ServiceError("Credential lifetime must be between zero and 24 hours", 422)
    token = secrets.token_urlsafe(32)
    with SessionLocal.begin() as db:
        user = db.get(User, user_id)
        if not user or not user.active:
            raise ServiceError("Account unavailable", 401)
        if "portal:review" in scopes and user.role not in ("MANAGER", "ADMIN"):
            raise ServiceError("Review scope requires a manager or admin", 403)
        credential = SessionToken(
            user_id=user_id,
            kind="MCP",
            token_hash=digest(token),
            scopes=scopes,
            expires_at=utcnow() + timedelta(hours=hours),
        )
        db.add(credential)
        db.flush()
        return token, credential.id


def revoke_mcp_credential(credential_id):
    from backend.app.config import settings

    if not settings.demo_mode:
        raise ServiceError("Demo administration is disabled", 403)
    with SessionLocal.begin() as db:
        record = db.get(SessionToken, credential_id)
        if not record or record.kind != "MCP":
            raise ServiceError("MCP credential not found", 404)
        db.delete(record)


def consume_mcp_request(token, maximum):
    # Persistent counters avoid per-worker limit bypass. Call only after token validation.
    from datetime import timezone

    if maximum <= 0:
        raise ServiceError("MCP rate limit must be positive", 500)
    with SessionLocal.begin() as db:
        record = db.scalar(
            select(SessionToken)
            .where(
                SessionToken.token_hash == digest(token),
                SessionToken.kind == "MCP",
                SessionToken.expires_at > utcnow(),
            )
            .with_for_update()
        )
        if not record:
            raise ServiceError("Credential expired or revoked", 401)
        now = utcnow()
        window = record.rate_window
        if window and window.tzinfo is None:
            window = window.replace(tzinfo=timezone.utc)
        if not window or (now - window).total_seconds() >= 60:
            record.rate_window, record.rate_count = now, 0
        if record.rate_count >= maximum:
            raise ServiceError("MCP request limit reached; retry after one minute", 429)
        record.rate_count += 1
