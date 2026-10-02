"""Transport boundary: trusted identity, scopes, serialization and safe logging."""

import json
import logging
from time import monotonic
from uuid import uuid4
from anyio import to_thread
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token
from backend.app.auth.context import ActorContext, ServiceError
from backend.app.auth.tokens import resolve_token
from backend.app.services import portal

log = logging.getLogger("portal.mcp")
REVIEW = {
    "approve_timesheet",
    "reject_timesheet",
    "approve_leave",
    "reject_leave",
    "list_pending_approvals",
}


def emit(event, **safe):
    log.info(json.dumps({"event": event, **safe}))


async def invoke(operation, **args):
    request_id = str(uuid4())
    start = monotonic()
    outcome = "FAILED"
    replayed = False
    try:
        token = get_access_token()
        if token is None:
            raise ServiceError("Authentication required", 401)
        credential = await to_thread.run_sync(lambda: resolve_token(token.token, kind="MCP"))
        scope = (
            "portal:review"
            if operation in REVIEW
            else ("portal:write" if portal.OPERATIONS[operation] else "portal:read")
        )
        if scope not in credential.scopes:
            raise ServiceError(f"Credential requires {scope}", 403)
        actor = ActorContext(credential.user_id, "MCP", request_id)
        data = await to_thread.run_sync(lambda: portal.run(actor, operation, **args))
        outcome = "SUCCESS"
        if "items" in data:
            return {**data, "request_id": request_id}
        replayed = data.pop("replayed", False)
        return {"record": data, "request_id": request_id, "replayed": replayed}
    except ServiceError as exc:
        outcome = "DENIED" if exc.code in (401, 403) else "FAILED"
        categories = {
            401: "authentication_required",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            422: "validation_error",
        }
        raise ToolError(
            json.dumps(
                {
                    "code": categories.get(exc.code, "business_error"),
                    "message": exc.message,
                    "request_id": request_id,
                }
            )
        ) from exc
    except Exception:
        raise ToolError(
            json.dumps(
                {"code": "internal_error", "message": "Operation failed", "request_id": request_id}
            )
        ) from None
    finally:
        emit(
            "tool_call",
            operation=operation,
            request_id=request_id,
            outcome=outcome,
            replayed=replayed,
            duration_ms=round((monotonic() - start) * 1000),
        )
