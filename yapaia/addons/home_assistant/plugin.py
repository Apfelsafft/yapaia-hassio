"""Home Assistant addon – REST state push."""
from app.addons.base import BaseAddon


class Plugin(BaseAddon):
    async def handle_request(self, path, request, user, db, addon_settings):
        from fastapi.responses import JSONResponse
        from app.services import ha as ha_svc

        ha_url = addon_settings.get("ha_base_url", "")
        ha_token = addon_settings.get("ha_token", "")

        if path == "test":
            if not ha_url or not ha_token:
                return JSONResponse(
                    {"ok": False, "detail": "URL und Token müssen zuerst gespeichert werden"},
                    status_code=400,
                )
            import httpx
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        f"{ha_url.rstrip('/')}/api/",
                        headers={"Authorization": f"Bearer {ha_token}"},
                    )
                if resp.status_code == 200:
                    return JSONResponse({"ok": True, "detail": "Verbindung erfolgreich ✓"})
                return JSONResponse(
                    {"ok": False, "detail": f"HA antwortete mit HTTP {resp.status_code}"}
                )
            except Exception as exc:
                return JSONResponse({"ok": False, "detail": f"Nicht erreichbar: {exc}"})

        if path == "status":
            return JSONResponse({
                "configured": bool(ha_url and ha_token),
                "ha_base_url": ha_url,
                "ha_token_set": bool(ha_token),
            })

        return JSONResponse({"error": "Not found"}, status_code=404)
