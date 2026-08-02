"""Tankerkönig API client with 5-minute in-memory cache."""
import asyncio
import logging
import math
import time

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://creativecommons.tankerkoenig.de/json"
_TTL = 300.0  # 5 minutes

# Cache: key -> (timestamp, stations_list)
_CACHE: dict[str, tuple[float, list[dict]]] = {}

VALID_FUELS = {"e5", "e10", "diesel"}


def _cache_key(lat: float, lon: float, radius: float, fuel: str) -> str:
    return f"{round(lat, 3)},{round(lon, 3)},{radius},{fuel}"


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def fetch_nearby(
    lat: float,
    lon: float,
    radius_km: float,
    fuel: str,
    api_key: str,
) -> list[dict]:
    key = _cache_key(lat, lon, radius_km, fuel)
    now = time.time()
    if key in _CACHE and now - _CACHE[key][0] < _TTL:
        return _CACHE[key][1]

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{_BASE}/list.php", params={
                "lat": lat,
                "lng": lon,
                "rad": radius_km,
                "sort": "price",
                "type": fuel,
                "apikey": api_key,
            })
            resp.raise_for_status()
            data = resp.json()

        if not data.get("ok"):
            logger.warning("Tankerkönig API error: %s", data.get("message", "unknown"))
            return []

        stations = data.get("stations", [])
        _CACHE[key] = (now, stations)
        return stations

    except Exception as exc:
        logger.warning("Tankerkönig fetch failed: %s", exc)
        return []


async def fetch_along_route(
    coordinates: list[list[float]],  # [[lon, lat], ...]
    radius_km: float,
    fuel: str,
    api_key: str,
    corridor_km: float = 2.0,
) -> list[dict]:
    """Sample evenly-spaced points along the route, fetch stations, deduplicate."""
    if len(coordinates) < 2:
        return []

    # Pick at most 6 evenly-spaced sample points (including start + end)
    n = len(coordinates)
    step = max(1, n // 5)
    indices = list(range(0, n, step))
    if indices[-1] != n - 1:
        indices.append(n - 1)

    tasks = [
        fetch_nearby(coordinates[i][1], coordinates[i][0], radius_km, fuel, api_key)
        for i in indices
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    seen: dict[str, dict] = {}
    for result in results:
        if isinstance(result, list):
            for s in result:
                seen[s["id"]] = s

    # Keep only stations within corridor_km of any sample point
    sample_coords = [(coordinates[i][1], coordinates[i][0]) for i in indices]
    filtered = []
    corridor_m = corridor_km * 1000
    for s in seen.values():
        slat, slon = s["lat"], s["lng"]
        if any(_haversine_m(slat, slon, plat, plon) <= corridor_m for plat, plon in sample_coords):
            filtered.append(s)

    # Sort by price ascending (None/0 prices last)
    def _price(s: dict) -> float:
        p = s.get("price") or s.get(fuel) or 0
        return p if p else 999.0

    filtered.sort(key=_price)
    return filtered
