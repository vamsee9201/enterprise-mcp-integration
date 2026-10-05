"""Protected demo chat with independent authenticated persona conversations."""

import logging
import os
import secrets
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from anyio import to_thread
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text

from backend.app.auth.tokens import digest, resolve_token
from backend.app.auth.context import ServiceError
from backend.app.config import settings
from backend.app.database.connection import SessionLocal
from backend.app.database.seed import USERS
from backend.app.models.entities import ChatConversation, SessionToken, User, utcnow
from chat_app.agent import MODEL, run_agent

app = FastAPI(title="Pied Piper Agent", docs_url=None, redoc_url=None, openapi_url=None)
STATIC = Path(__file__).parent / "static"
ALLOWED = {item["id"] for item in USERS}
ORIGINS = set(
    os.environ.get("CHAT_ALLOWED_ORIGINS", "http://localhost:3400,http://127.0.0.1:3400").split(",")
)
logger = logging.getLogger("portal.chat")


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: UUID


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4000)
    turn_id: UUID


def profile_view(user):
    return {"id": str(user.id), "name": user.name, "role": user.role, "department": user.department}


def cookie_name(profile_id):
    return "pied_chat_" + str(profile_id)


def check_origin(request):
    if request.headers.get("origin") not in ORIGINS:
        raise HTTPException(403, "Origin is not allowed")


def authenticated(request, profile_id, mutation=False):
    try:
        token = request.cookies.get(cookie_name(profile_id), "")
        session = resolve_token(token, "CHAT")
    except ServiceError:
        raise HTTPException(
            401, "Select this profile to start an authenticated conversation"
        ) from None
    if session.user_id != profile_id or profile_id not in ALLOWED:
        raise HTTPException(403, "Conversation belongs to a different profile")
    if mutation:
        check_origin(request)
        if not secrets.compare_digest(
            request.headers.get("x-csrf-token", ""), session.csrf_token or ""
        ):
            raise HTTPException(403, "CSRF token is required")
    return session


@app.middleware("http")
async def secure_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    return response


@app.get("/health")
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("select id from chat_conversations limit 1"))
        return {"status": "ready", "model": MODEL}
    except Exception:
        raise HTTPException(503, "Database unavailable") from None


@app.get("/chat/profiles")
def profiles():
    if not settings.demo_mode:
        raise HTTPException(503, "Demo profile selection is disabled")
    with SessionLocal() as db:
        users = db.scalars(select(User).where(User.id.in_(ALLOWED), User.active.is_(True))).all()
        priority = {"ADMIN": 0, "MANAGER": 1, "EMPLOYEE": 2}
        return {
            "profiles": sorted(
                [profile_view(user) for user in users],
                key=lambda p: (priority[p["role"]], p["name"]),
            ),
            "model": MODEL,
        }


@app.post("/chat/login")
def login(payload: Login, request: Request, response: Response):
    check_origin(request)
    if not settings.demo_mode or payload.profile_id not in ALLOWED:
        raise HTTPException(403, "Profile is not allowlisted")
    raw, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with SessionLocal.begin() as db:
        user = db.get(User, payload.profile_id)
        if not user or not user.active:
            raise HTTPException(403, "Profile is unavailable")
        session = SessionToken(
            user_id=user.id,
            kind="CHAT",
            token_hash=digest(raw),
            csrf_token=csrf,
            expires_at=utcnow() + timedelta(hours=8),
        )
        db.add(session)
        db.flush()
        conversation = ChatConversation(id=session.id, user_id=user.id)
        db.add(conversation)
        result = {
            "profile": profile_view(user),
            "csrf_token": csrf,
            "conversation_id": str(conversation.id),
            "messages": [],
        }
    response.set_cookie(
        cookie_name(payload.profile_id),
        raw,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        max_age=8 * 3600,
    )
    return result


@app.get("/chat/session/{profile_id}")
def get_session(profile_id: UUID, request: Request):
    session = authenticated(request, profile_id)
    with SessionLocal() as db:
        conversation = db.get(ChatConversation, session.id)
        if not conversation or conversation.user_id != profile_id:
            raise HTTPException(404, "Conversation not found")
        return {
            "profile": profile_view(db.get(User, profile_id)),
            "csrf_token": session.csrf_token,
            "conversation_id": str(conversation.id),
            "messages": conversation.messages,
        }


def start_turn(session_id, profile_id, payload):
    with SessionLocal.begin() as db:
        conversation = db.scalar(
            select(ChatConversation).where(ChatConversation.id == session_id).with_for_update()
        )
        if not conversation or conversation.user_id != profile_id:
            raise HTTPException(403, "Conversation access denied")
        key = str(payload.turn_id)
        if key in conversation.results:
            saved = conversation.results[key]
            if saved["input"] != payload.text:
                raise HTTPException(409, "Turn key was already used for a different message")
            return {"replayed": True, "message": saved["message"]}
        # A lost worker never silently replays a potentially committed tool operation.
        if conversation.busy_until:
            raise HTTPException(
                409,
                "A turn is running or was interrupted. Start a new chat and check current records before repeating a write.",
            )
        if len(conversation.results) >= 30:
            raise HTTPException(409, "Start a new chat after 30 messages")
        conversation.busy_until = utcnow() + timedelta(minutes=4)
        conversation.messages = conversation.messages + [{"role": "user", "text": payload.text}]
        return {"profile": profile_view(db.get(User, profile_id)), "events": conversation.events}


def finish_turn(session_id, payload, result):
    with SessionLocal.begin() as db:
        conversation = db.scalar(
            select(ChatConversation).where(ChatConversation.id == session_id).with_for_update()
        )
        conversation.events = result["events"]
        conversation.messages = conversation.messages + [result["message"]]
        conversation.results = {
            **conversation.results,
            str(payload.turn_id): {"input": payload.text, "message": result["message"]},
        }
        conversation.busy_until = None
    return {"message": result["message"], "replayed": False}


@app.post("/chat/message/{profile_id}")
async def send_message(profile_id: UUID, payload: Message, request: Request):
    if not payload.text.strip():
        raise HTTPException(422, "Message cannot be blank")
    session = await to_thread.run_sync(lambda: authenticated(request, profile_id, True))
    state = await to_thread.run_sync(lambda: start_turn(session.id, profile_id, payload))
    if state.get("replayed"):
        return state
    try:
        result = await run_agent(state["profile"], state["events"], payload.text, payload.turn_id)
    except Exception as exc:
        logger.warning("chat_setup_failed exception_type=%s", type(exc).__name__)
        result = {
            "events": state["events"],
            "message": {
                "role": "assistant",
                "text": "I couldn’t connect to the agent. Check current records before retrying any write.",
                "actions": [],
                "failed": True,
            },
        }
    return await to_thread.run_sync(lambda: finish_turn(session.id, payload, result))


@app.post("/chat/logout/{profile_id}")
def logout(profile_id: UUID, request: Request, response: Response):
    session = authenticated(request, profile_id, True)
    with SessionLocal.begin() as db:
        db.get(SessionToken, session.id).expires_at = utcnow()
    response.delete_cookie(cookie_name(profile_id))
    return {"signed_out": True}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
