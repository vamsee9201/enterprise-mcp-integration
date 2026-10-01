from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
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
        db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
def invalid_request(request: Request, error: RequestValidationError):
    messages = [".".join(map(str, item["loc"])) + ": " + item["msg"] for item in error.errors()]
    return JSONResponse(
        status_code=422, content={"error": {"message": "; ".join(messages), "code": 422}}
    )
