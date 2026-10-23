from fastapi import APIRouter
from sqlalchemy import text

from app.api.dependencies import DbSession
from app.core.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}


@router.get("/readiness")
def readiness(db: DbSession) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}
