"""MQTT addon – starts the MQTT client and provides status info."""
import asyncio
import logging

from app.addons.base import BaseAddon

logger = logging.getLogger(__name__)


class Plugin(BaseAddon):
    async def initialize(self) -> None:
        from app.services import mqtt as mqtt_svc
        from app.config import settings as app_settings

        if not app_settings.mqtt_host:
            logger.info("MQTT: MQTT_HOST not set, broker connection skipped")
            return

        loop = asyncio.get_running_loop()
        mqtt_svc.set_event_loop(loop)
        mqtt_svc.get_client()
        logger.info("MQTT addon: broker connection started (%s:%s)", app_settings.mqtt_host, app_settings.mqtt_port)

    async def shutdown(self) -> None:
        from app.services import mqtt as mqtt_svc
        mqtt_svc.shutdown()

    async def handle_request(self, path, request, user, db, addon_settings):
        from fastapi.responses import JSONResponse
        from app.services import mqtt as mqtt_svc
        from app.config import settings as app_settings

        if path == "status":
            client = mqtt_svc.get_client()
            return JSONResponse({
                "broker_host": app_settings.mqtt_host,
                "broker_port": app_settings.mqtt_port,
                "connected": mqtt_svc._connected,
            })

        return JSONResponse({"error": "Not found"}, status_code=404)
