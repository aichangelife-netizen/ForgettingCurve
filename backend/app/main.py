from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.services.exceptions import ServiceError

app = FastAPI(title="ForgettingCurve API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["content-type"],
)
app.include_router(api_router)


@app.exception_handler(ServiceError)
def service_error_handler(_request: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
