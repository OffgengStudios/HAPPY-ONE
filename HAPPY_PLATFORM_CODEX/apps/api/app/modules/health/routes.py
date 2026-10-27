from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.version import API_VERSION, RELEASE_VERSION
from app.db.session import check_database
from app.modules.iam.dependencies import Database, Principal, require
from app.storage.s3 import check_object_storage

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str
    request_id: str
    checked_at: datetime
    release_version: str
    api_version: str


@router.get("/live", response_model=HealthResponse)
def liveness(request: Request) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        request_id=request.state.request_id,
        checked_at=datetime.now(UTC),
        release_version=RELEASE_VERSION,
        api_version=API_VERSION,
    )


@router.get("/ready", response_model=HealthResponse)
def readiness(request: Request) -> HealthResponse:
    try:
        check_database()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database readiness check failed",
        ) from None

    try:
        check_object_storage()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage readiness check failed",
        ) from exc

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        request_id=request.state.request_id,
        checked_at=datetime.now(UTC),
        release_version=RELEASE_VERSION,
        api_version=API_VERSION,
    )


@router.get("/operations")
def operational_health(
    db: Database,
    actor: Annotated[Principal, Depends(require("integration_event:view"))],
) -> dict[str, Any]:
    from app.core.operational_health import snapshot

    return snapshot(db)
