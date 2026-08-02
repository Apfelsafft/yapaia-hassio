import datetime
import sys

from fastapi import APIRouter

router = APIRouter(tags=["health"])

_START_TIME = datetime.datetime.now(datetime.timezone.utc).isoformat()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/info")
async def info() -> dict:
    from app.config import settings
    return {
        "version": "0.4.0",
        "start_time": _START_TIME,
        "python_version": sys.version.split()[0],
        "marketplace_url": settings.marketplace_url,
    }
