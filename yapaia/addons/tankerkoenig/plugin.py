"""Tankerkönig addon – gas station prices via the MTS-K API."""
from app.addons.base import BaseAddon
from app.services import tankerkonig

VALID_FUELS = {"e5", "e10", "diesel"}


class Plugin(BaseAddon):
    async def handle_request(self, path, request, user, db, addon_settings):
        from fastapi.responses import JSONResponse

        api_key = addon_settings.get("api_key", "")
        if not api_key:
            return JSONResponse(
                {"error": "API-Key nicht konfiguriert", "addon": "tankerkoenig"},
                status_code=503,
            )

        default_fuel = addon_settings.get("fuel_type", "e5")
        default_radius = float(addon_settings.get("radius", 5))

        if path == "nearby":
            lat = float(request.query_params.get("lat", 0))
            lon = float(request.query_params.get("lon", 0))
            radius = float(request.query_params.get("radius", default_radius))
            fuel = request.query_params.get("fuel", default_fuel)
            if fuel not in VALID_FUELS:
                fuel = "e5"
            stations = await tankerkonig.fetch_nearby(lat, lon, min(radius, 25.0), fuel, api_key)
            return JSONResponse({"stations": stations, "fuel": fuel, "count": len(stations)})

        if path == "route":
            body = await request.json()
            coords = body.get("coordinates", [])
            radius = float(body.get("radius", default_radius))
            fuel = body.get("fuel", default_fuel)
            corridor = float(body.get("corridor", 2.0))
            if fuel not in VALID_FUELS:
                fuel = "e5"
            stations = await tankerkonig.fetch_along_route(
                coords, min(radius, 25.0), fuel, api_key, min(corridor, 10.0)
            )
            return JSONResponse({"stations": stations, "fuel": fuel, "count": len(stations)})

        if path == "enabled":
            return JSONResponse({"enabled": True, "addon": True})

        return JSONResponse({"error": "Not found"}, status_code=404)
