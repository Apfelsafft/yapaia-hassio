import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User
from app.services.gps import GpsPosition, get_service

router = APIRouter(tags=["gps"])


class GpsPushBody(BaseModel):
    lat: float
    lon: float
    speed: Optional[float] = 0.0
    heading: Optional[float] = 0.0


@router.get("/api/gps/position")
async def gps_position():
    pos = get_service().get_position()
    if pos is None:
        return {"available": False}
    return {
        "available": True,
        "lat": pos.lat,
        "lon": pos.lon,
        "speed": pos.speed,
        "heading": pos.heading,
        "source": pos.source,
    }


@router.get("/api/gps/push")
async def gps_push(
    token: str = Query(..., description="GPS-Push-Token des Users"),
    lat: float = Query(..., description="Breitengrad"),
    lon: float = Query(..., description="Längengrad"),
    speed: float = Query(0.0, description="Geschwindigkeit km/h"),
    heading: float = Query(0.0, description="Richtung Grad"),
    db: AsyncSession = Depends(get_db),
):
    """Empfängt GPS-Position von externer Quelle (GPSLogger, OwnTracks, etc.).

    Token aus Einstellungen → GPS muss als Query-Parameter mitgesendet werden.
    """
    user = await db.scalar(select(User).where(User.gps_push_token == token))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Ungültiger oder fehlender Token")
    get_service().publish(
        GpsPosition(lat=lat, lon=lon, speed=speed, heading=heading, source="url")
    )
    return {"ok": True}


@router.post("/api/gps/push")
async def gps_push_post(
    token: str = Query(..., description="GPS-Push-Token des Users"),
    body: Optional[GpsPushBody] = None,
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    speed: float = Query(0.0),
    heading: float = Query(0.0),
    db: AsyncSession = Depends(get_db),
):
    """POST-Variante des GPS-Push-Endpoints. Akzeptiert lat/lon als Query-Params oder JSON-Body."""
    user = await db.scalar(select(User).where(User.gps_push_token == token))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Ungültiger oder fehlender Token")

    if body is not None:
        pos_lat, pos_lon, pos_speed, pos_heading = body.lat, body.lon, body.speed or 0.0, body.heading or 0.0
    elif lat is not None and lon is not None:
        pos_lat, pos_lon, pos_speed, pos_heading = lat, lon, speed, heading
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "lat/lon fehlen (Query-Params oder JSON-Body)")

    get_service().publish(
        GpsPosition(lat=pos_lat, lon=pos_lon, speed=pos_speed, heading=pos_heading, source="url")
    )
    return {"ok": True}


@router.websocket("/ws/gps")
async def ws_gps(websocket: WebSocket):
    await websocket.accept()
    svc = get_service()
    q = svc.subscribe()
    try:
        pos = svc.get_position()
        if pos:
            await websocket.send_json(
                {"lat": pos.lat, "lon": pos.lon, "speed": pos.speed,
                 "heading": pos.heading, "source": pos.source}
            )
        while True:
            try:
                pos = await asyncio.wait_for(q.get(), timeout=25.0)
                await websocket.send_json(
                    {"lat": pos.lat, "lon": pos.lon, "speed": pos.speed,
                     "heading": pos.heading, "source": pos.source}
                )
            except asyncio.TimeoutError:
                await websocket.send_json({"ping": True})
    except WebSocketDisconnect:
        pass
    finally:
        svc.unsubscribe(q)
