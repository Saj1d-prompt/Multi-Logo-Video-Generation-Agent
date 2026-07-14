from fastapi import FastAPI, Header, HTTPException

from app.models import BatchRequest
from app.settings import settings


app = FastAPI(
    title=settings.app_name,
    version="1.0.0"
)


def verify_api_key(api_key: str | None) -> None:
    if api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )


@app.get("/")
def root():
    return {
        "application": settings.app_name,
        "environment": settings.app_env,
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": settings.app_name
    }


@app.post("/dry-run")
def dry_run(
    request: BatchRequest,
    x_api_key: str | None = Header(default=None)
):
    verify_api_key(x_api_key)

    return {
        "status": "success",
        "message": "Request accepted for testing",
        "received": request.model_dump()
    }