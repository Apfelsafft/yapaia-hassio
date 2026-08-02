import logging

import httpx
from fastapi import APIRouter, HTTPException

from app.services.photon import search as geocode

log = logging.getLogger(__name__)
router = APIRouter(tags=["search"])


@router.get("/search")
async def search(
    q: str,
    lat: float | None = None,
    lon: float | None = None,
    limit: int = 6,
) -> dict:
    if not q.strip():
        return {"results": []}
    try:
        return await geocode(q=q, lat=lat, lon=lon, limit=limit)
    except httpx.ConnectError as e:
        log.error("Geocoder unreachable: %s", e)
        raise HTTPException(503, "Adresssuche nicht erreichbar (kein Internetzugang?)")
    except httpx.TimeoutException:
        raise HTTPException(504, "Adresssuche Timeout — bitte erneut versuchen")
    except httpx.HTTPStatusError as e:
        log.error("Geocoder HTTP %s: %s", e.response.status_code, e.response.text[:200])
        raise HTTPException(502, f"Geocoder Fehler: {e.response.status_code}")
    except Exception as e:
        log.exception("Geocoder unexpected error")
        raise HTTPException(500, f"Adresssuche fehlgeschlagen: {type(e).__name__}")
