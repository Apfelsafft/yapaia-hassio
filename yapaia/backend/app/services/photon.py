import logging
import re

import httpx

from app.config import settings as app_settings

# Primary: lokale Photon-Instanz (settings.photon_url, Default http://photon:2322).
# Postcode-prefix queries use Nominatim's structured endpoint (more reliable).
# Final fallback: free-text Nominatim.
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_HEADERS = {"User-Agent": "Navi/0.4.0 (self-hosted; https://github.com/Apfelsafft/yapaia-hassio)"}

_DACH_COUNTRY_NAMES = {
    "Deutschland", "Österreich", "Schweiz",
    "Germany", "Austria", "Switzerland",
}

# "12345 Hauptstraße" → ("12345", "Hauptstraße").
# German conventions put the postcode first, but every geocoder ranks better
# when the street name is the primary token and the postcode acts as a filter.
_POSTCODE_PREFIX = re.compile(r"^\s*(\d{4,5})\s+(.+)$")

log = logging.getLogger(__name__)


def _parse_nominatim_item(item: dict) -> dict | None:
    addr = item.get("address", {})
    name = item.get("name", "")
    road = addr.get("road", "")
    house = addr.get("house_number", "")
    postcode = addr.get("postcode", "")
    city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county", "")
    state = addr.get("state", "")

    street = f"{road} {house}".strip() if road else ""
    city_full = f"{postcode} {city}".strip() if postcode else city
    seen: set[str] = set()
    deduped: list[str] = []
    for p in (name, street, city_full, state):
        if p and p not in seen:
            seen.add(p)
            deduped.append(p)
    label = ", ".join(deduped) if deduped else item.get("display_name", "")

    try:
        lat = float(item["lat"])
        lon = float(item["lon"])
    except (KeyError, TypeError, ValueError):
        return None

    return {
        "label": label or "Unbekannter Ort",
        "lat": lat,
        "lon": lon,
        "type": item.get("type", ""),
    }


async def _search_photon(q: str, lat: float | None, lon: float | None, limit: int) -> list[dict]:
    photon_url = f"{app_settings.photon_url.rstrip('/')}/api"
    params: dict = {
        "q": q,
        "limit": limit,
        "lang": "de",
        "lat": lat if lat is not None else 51.16,
        "lon": lon if lon is not None else 10.45,
    }
    async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
        resp = await client.get(photon_url, params=params)
        resp.raise_for_status()
        data = resp.json()

    results: list[dict] = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates") or [None, None]
        lon_, lat_ = coords[0], coords[1]
        if lon_ is None or lat_ is None:
            continue
        country = props.get("country", "")
        if country and country not in _DACH_COUNTRY_NAMES:
            continue

        name = props.get("name", "")
        street = props.get("street", "")
        house = props.get("housenumber", "")
        city = props.get("city") or props.get("town") or props.get("village") or props.get("county", "")
        postcode = props.get("postcode", "")
        state = props.get("state", "")

        street_full = f"{street} {house}".strip() if street else ""
        city_full = f"{postcode} {city}".strip() if postcode else city
        seen: set[str] = set()
        parts: list[str] = []
        for p in (name, street_full, city_full, state):
            if p and p not in seen:
                seen.add(p)
                parts.append(p)
        label = ", ".join(parts) if parts else "Unbekannter Ort"

        results.append({
            "label": label,
            "lat": float(lat_),
            "lon": float(lon_),
            "type": props.get("osm_value") or props.get("type", ""),
        })
    return results


async def _search_nominatim_structured(postcode: str, street: str, limit: int) -> list[dict]:
    """Use Nominatim's structured endpoint — postcode is an explicit filter, not part of free text."""
    params: dict = {
        "postalcode": postcode,
        "street": street,
        "format": "json",
        "limit": limit,
        "accept-language": "de",
        "countrycodes": "de,at,ch",
        "addressdetails": "1",
    }
    async with httpx.AsyncClient(timeout=10.0, headers=_NOMINATIM_HEADERS) as client:
        resp = await client.get(_NOMINATIM_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    return [r for r in (_parse_nominatim_item(it) for it in data) if r]


async def _search_nominatim_freetext(q: str, lat: float | None, lon: float | None, limit: int) -> list[dict]:
    params: dict = {
        "q": q,
        "format": "json",
        "limit": limit,
        "accept-language": "de",
        "countrycodes": "de,at,ch",
        "addressdetails": "1",
    }
    if lat is not None and lon is not None:
        params["lat"] = lat
        params["lon"] = lon
    async with httpx.AsyncClient(timeout=10.0, headers=_NOMINATIM_HEADERS) as client:
        resp = await client.get(_NOMINATIM_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    return [r for r in (_parse_nominatim_item(it) for it in data) if r]


async def search(
    q: str,
    lat: float | None = None,
    lon: float | None = None,
    limit: int = 6,
) -> dict:
    """Postcode-prefix → Nominatim structured. Otherwise: Photon → Nominatim fallback."""
    m = _POSTCODE_PREFIX.match(q)
    if m:
        postcode, street = m.group(1), m.group(2).strip()
        try:
            results = await _search_nominatim_structured(postcode, street, limit)
            if results:
                return {"results": results}
        except Exception as e:
            log.warning("Nominatim structured failed (%s)", type(e).__name__, exc_info=e)

    try:
        results = await _search_photon(q=q, lat=lat, lon=lon, limit=limit)
        if results:
            return {"results": results}
    except Exception as e:
        log.warning("Photon search failed (%s), falling back to Nominatim", type(e).__name__, exc_info=e)

    results = await _search_nominatim_freetext(q=q, lat=lat, lon=lon, limit=limit)
    return {"results": results}
