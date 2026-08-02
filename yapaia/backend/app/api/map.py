import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(tags=["map"])

TILES_DIR = Path("/data/tiles")
CDN_STYLE_URL = "https://cdn.protomaps.com/styles/protomaps-theme-base.json"

_style_cache: dict = {"style": None, "ts": 0.0, "tile": None}
_STYLE_TTL = 3600.0

_OSM_RASTER_STYLE = {
    "version": 8,
    "sources": {
        "osm": {
            "type": "raster",
            "tiles": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            "tileSize": 256,
            "attribution": "© OpenStreetMap contributors",
        }
    },
    "layers": [{"id": "osm", "type": "raster", "source": "osm"}],
}


def _find_local_tile() -> str | None:
    if not TILES_DIR.exists():
        return None
    for p in sorted(TILES_DIR.iterdir()):
        if p.suffix == ".pmtiles":
            return p.name
    return None


def _apply_local_tile(style: dict, tile_name: str) -> dict:
    """Replace the protomaps tile source URL with the locally served PMTiles file."""
    tile_url = f"pmtiles:///api/map/tiles/{tile_name}"
    sources = style.get("sources", {})
    if "protomaps" in sources:
        sources["protomaps"]["url"] = tile_url
    else:
        # Fallback: patch the first vector source found
        for src in sources.values():
            if src.get("type") == "vector":
                src["url"] = tile_url
                break
    return style


@router.get("/map/style")
async def map_style() -> JSONResponse:
    local_tile = _find_local_tile()
    now = time.time()

    # Cache valid and tile situation unchanged → serve cached style
    if (
        _style_cache["style"]
        and _style_cache["ts"] + _STYLE_TTL > now
        and _style_cache["tile"] == local_tile
    ):
        return JSONResponse(_style_cache["style"])

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(CDN_STYLE_URL)
            resp.raise_for_status()
            style = resp.json()

        if local_tile:
            style = _apply_local_tile(style, local_tile)

        _style_cache.update({"style": style, "ts": now, "tile": local_tile})
        return JSONResponse(style)
    except Exception:
        return JSONResponse(_OSM_RASTER_STYLE)


@router.get("/map/tiles")
async def list_tiles() -> dict:
    if not TILES_DIR.exists():
        return {"tiles": []}
    tiles = [p.name for p in TILES_DIR.iterdir() if p.suffix in {".pmtiles", ".mbtiles"}]
    return {"tiles": sorted(tiles)}


@router.get("/map/tiles/{filename}")
async def serve_tile(filename: str) -> FileResponse:
    if ".." in filename or "/" in filename:
        raise HTTPException(400, "Ungültiger Dateiname")
    path = TILES_DIR / filename
    if not path.exists() or path.suffix not in {".pmtiles", ".mbtiles"}:
        raise HTTPException(404, "Tile-Datei nicht gefunden")
    return FileResponse(str(path), media_type="application/octet-stream")
