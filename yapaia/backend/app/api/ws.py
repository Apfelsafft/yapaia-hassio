import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.addons import manager as addon_manager
from app.config import settings as app_settings
from app.db import AsyncSessionLocal

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"


def _user_id_from_token(token: str) -> str:
    if not token:
        return ""
    try:
        payload = jwt.decode(token, app_settings.secret_key, algorithms=[_ALGORITHM])
        return payload.get("sub", "")
    except JWTError:
        return ""


async def _load_ha_settings(user_id: str) -> tuple[str, str]:
    """Load HA URL + token from addon_user_settings (home_assistant addon)."""
    if not user_id or not addon_manager.is_loaded("home_assistant"):
        return "", ""
    try:
        async with AsyncSessionLocal() as db:
            s = await addon_manager.get_user_settings("home_assistant", user_id, db)
            return s.get("ha_base_url", ""), s.get("ha_token", "")
    except Exception:
        return "", ""


async def _handle_incoming(
    websocket: WebSocket,
    user_id: str,
    ha_url: str,
    ha_token: str,
    cmd_queue: asyncio.Queue,
) -> None:
    # Lazily import services so they are only used when their addon is active
    from app.services import ha as ha_svc
    from app.services import mqtt as mqtt_svc

    while True:
        data = await websocket.receive_json()
        msg_type = data.get("type")

        if msg_type == "position":
            lat = data.get("lat", 0.0)
            lon = data.get("lon", 0.0)
            speed = data.get("speed", 0.0)
            heading = data.get("heading", 0.0)

            if addon_manager.is_loaded("mqtt_client"):
                mqtt_svc.publish_position(lat, lon, speed, heading)

            if user_id:
                asyncio.create_task(addon_manager.notify_gps(user_id, lat, lon, speed, heading))

        elif msg_type == "instruction":
            if addon_manager.is_loaded("mqtt_client"):
                mqtt_svc.publish_instruction(
                    data.get("text", ""), data.get("distance", 0),
                    data.get("sign", 0), data.get("street", ""),
                )

        elif msg_type == "route":
            if addon_manager.is_loaded("mqtt_client"):
                mqtt_svc.publish_route(
                    data.get("distance_remaining", 0),
                    data.get("duration_remaining", 0),
                    data.get("destination", ""),
                )

        elif msg_type == "status":
            navigating = data.get("navigating", False)

            if addon_manager.is_loaded("mqtt_client"):
                mqtt_svc.publish_status(navigating)

            if addon_manager.is_loaded("home_assistant") and ha_url and ha_token:
                asyncio.create_task(ha_svc.push_navigation_state(
                    ha_url=ha_url, ha_token=ha_token, navigating=navigating,
                    lat=data.get("lat"), lon=data.get("lon"),
                    speed=data.get("speed", 0), instruction=data.get("instruction", ""),
                    distance_remaining=data.get("distance_remaining", 0),
                    duration_remaining=data.get("duration_remaining", 0),
                    destination=data.get("destination", ""),
                ))

        elif msg_type == "nav_started":
            if user_id:
                asyncio.create_task(addon_manager.notify_gps(user_id, 0, 0, 0, 0))

        # Forward any addon-specific message types to the addon
        elif msg_type and msg_type.startswith("addon_"):
            pass  # reserved for future addon WebSocket protocol


async def _forward_commands(websocket: WebSocket, cmd_queue: asyncio.Queue) -> None:
    while True:
        cmd = await cmd_queue.get()
        await websocket.send_json(cmd)


@router.websocket("/ws/navigation")
async def ws_navigation(websocket: WebSocket, token: str = ""):
    user_id = _user_id_from_token(token)
    ha_url, ha_token = await _load_ha_settings(user_id)

    await websocket.accept()
    logger.info(
        "Navigation WebSocket verbunden (user_id=%s, HA=%s, MQTT=%s)",
        user_id or "anonym",
        bool(ha_url),
        addon_manager.is_loaded("mqtt_client"),
    )

    cmd_queue: asyncio.Queue = asyncio.Queue(maxsize=16)

    # Subscribe to MQTT commands only when the mqtt_client addon is active
    if addon_manager.is_loaded("mqtt_client"):
        from app.services import mqtt as mqtt_svc
        mqtt_svc.subscribe_commands(cmd_queue)

    recv_task = asyncio.create_task(
        _handle_incoming(websocket, user_id, ha_url, ha_token, cmd_queue)
    )
    send_task = asyncio.create_task(_forward_commands(websocket, cmd_queue))
    try:
        done, pending = await asyncio.wait(
            [recv_task, send_task], return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
        for t in done:
            if not t.cancelled():
                t.result()
    except WebSocketDisconnect:
        logger.info("Navigation WebSocket getrennt")
    except Exception as exc:
        logger.warning("WebSocket Fehler: %s", exc)
    finally:
        if addon_manager.is_loaded("mqtt_client"):
            from app.services import mqtt as mqtt_svc
            mqtt_svc.unsubscribe_commands(cmd_queue)
