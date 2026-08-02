import httpx
from fastapi import APIRouter, HTTPException, Query

from app.services.graphhopper import get_route

router = APIRouter(tags=["route"])


@router.get("/route")
async def route(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    via: list[str] = Query(default=[]),
    profile: str = "car",
    routing_mode: str = "fastest",
    vehicle_height: float | None = None,
    vehicle_weight: float | None = None,
    vehicle_width: float | None = None,
) -> dict:
    via_coords: list[tuple[float, float]] = []
    for entry in via:
        try:
            lat_s, lon_s = entry.split(",", 1)
            via_coords.append((float(lat_s), float(lon_s)))
        except ValueError:
            raise HTTPException(422, f"Ungültiger via-Parameter: '{entry}'")
    try:
        return await get_route(
            from_lon=from_lon,
            from_lat=from_lat,
            to_lon=to_lon,
            to_lat=to_lat,
            via=via_coords or None,
            profile=profile,
            routing_mode=routing_mode,
            vehicle_height=vehicle_height,
            vehicle_weight=vehicle_weight,
            vehicle_width=vehicle_width,
        )
    except httpx.ConnectError:
        raise HTTPException(503, "Routing-Service nicht erreichbar (GraphHopper startet noch oder OSM-Daten fehlen)")
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("message", str(e)) if e.response.content else str(e)
        raise HTTPException(e.response.status_code, detail)
    except httpx.TimeoutException:
        raise HTTPException(504, "Routing-Service Timeout")
