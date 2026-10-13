from uuid import UUID
from backend.app.models.entities import User
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from backend.app.api.routes import router
from backend.app.auth.context import ServiceError
from backend.app.database.connection import SessionLocal

app = FastAPI(title="Pied Piper Operations", version="1.0.0")
app.include_router(router)


@app.exception_handler(ServiceError)
def service_error(request: Request, error: ServiceError):
    return JSONResponse(
        status_code=error.code, content={"error": {"message": error.message, "code": error.code}}
    )


@app.get("/health")
def health():
    with SessionLocal() as db:
        db.get(User, UUID("00000000-0000-4000-8000-000000000001"))
    return {"status": "ok", "storage": "firestore"}


@app.exception_handler(RequestValidationError)
def invalid_request(request: Request, error: RequestValidationError):
    messages = [".".join(map(str, item["loc"])) + ": " + item["msg"] for item in error.errors()]
    return JSONResponse(
        status_code=422, content={"error": {"message": "; ".join(messages), "code": 422}}
    )
