from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import get_current_user
from app.config import settings as app_settings
from app.models import User
from app.services import tankerkonig

router = APIRouter(prefix="/api/stations", tags=["stations"])


def _require_api_key() -> str:
    key = app_settings.tankerkonig_api_key
    if not key:
        raise HTTPException(503, "Tankerkönig API-Key nicht konfiguriert (TANKERKONIG_API_KEY fehlt in .env)")
    return key


class RouteBody(BaseModel):
    coordinates: list[list[float]]  # [[lon, lat], ...]
    radius: float = 5.0
    fuel: str = "e5"
    corridor: float = 2.0


@router.get("/nearby")
async def stations_nearby(
    lat: float = Query(..., description="Breitengrad"),
    lon: float = Query(..., description="Längengrad"),
    radius: float = Query(5.0, ge=1.0, le=25.0, description="Suchradius in km"),
    fuel: str = Query("e5", description="e5 | e10 | diesel"),
    user: User = Depends(get_current_user),
):
    if fuel not in tankerkonig.VALID_FUELS:
        raise HTTPException(422, f"Ungültige Kraftstoffsorte '{fuel}'. Erlaubt: e5, e10, diesel")
    api_key = _require_api_key()
    stations = await tankerkonig.fetch_nearby(lat, lon, radius, fuel, api_key)
    return {"stations": stations, "fuel": fuel, "count": len(stations)}


@router.post("/route")
async def stations_along_route(
    body: RouteBody,
    user: User = Depends(get_current_user),
):
    fuel = body.fuel if body.fuel in tankerkonig.VALID_FUELS else "e5"
    api_key = _require_api_key()
    stations = await tankerkonig.fetch_along_route(
        body.coordinates,
        min(body.radius, 25.0),
        fuel,
        api_key,
        corridor_km=min(body.corridor, 10.0),
    )
    return {"stations": stations, "fuel": fuel, "count": len(stations)}


@router.get("/enabled")
async def stations_feature_enabled(user: User = Depends(get_current_user)):
    """Prüft ob der Tankerkönig API-Key konfiguriert ist."""
    return {"enabled": bool(app_settings.tankerkonig_api_key)}
