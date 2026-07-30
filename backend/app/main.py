from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.services.exceptions import ServiceError

app = FastAPI(title="ForgettingCurve API")
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
