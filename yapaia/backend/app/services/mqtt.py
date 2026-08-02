import asyncio
import json
import logging
import threading
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from app.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_client: mqtt.Client | None = None
_connected = False

# Command subscribers: frontend WebSocket sessions register here to receive
# commands sent from HA via MQTT yapaia/command.
_cmd_subscribers: list[asyncio.Queue] = []
_main_loop: asyncio.AbstractEventLoop | None = None


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def subscribe_commands(q: asyncio.Queue) -> None:
    _cmd_subscribers.append(q)


def unsubscribe_commands(q: asyncio.Queue) -> None:
    try:
        _cmd_subscribers.remove(q)
    except ValueError:
        pass

_BASE = "yapaia"
_DEVICE_INFO = {
    "identifiers": ["yapaia_server"],
    "name": "Yapaia Go",
    "manufacturer": "Yapaia",
    "sw_version": "0.4.0",
}


def _on_message(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
    if msg.topic != f"{_BASE}/command":
        return
    if not _main_loop or not _cmd_subscribers:
        return
    try:
        payload = json.loads(msg.payload)
        cmd = {"type": "command", **payload}
        for q in list(_cmd_subscribers):
            _main_loop.call_soon_threadsafe(q.put_nowait, cmd)
    except Exception as e:
        logger.debug(f"yapaia/command parse error: {e}")


def _on_connect(client: mqtt.Client, userdata, flags, rc: int):
    global _connected
    _connected = rc == 0
    if rc == 0:
        logger.info("MQTT verbunden")
        client.subscribe(f"{_BASE}/command")
        _publish_discovery(client)
    else:
        logger.warning(f"MQTT Verbindungsfehler rc={rc}")


def _on_disconnect(client, userdata, rc: int):
    global _connected
    _connected = False
    if rc != 0:
        logger.warning(f"MQTT unerwartet getrennt rc={rc}")


def get_client() -> mqtt.Client | None:
    global _client
    if _client is not None:
        return _client
    if not settings.mqtt_host:
        return None
    with _lock:
        if _client is not None:
            return _client
        c = mqtt.Client(client_id="yapaia-backend", clean_session=True, protocol=mqtt.MQTTv311)
        c.on_connect = _on_connect
        c.on_disconnect = _on_disconnect
        c.on_message = _on_message
        c.reconnect_delay_set(min_delay=2, max_delay=60)
        try:
            c.connect_async(settings.mqtt_host, settings.mqtt_port, keepalive=60)
            c.loop_start()
            _client = c
        except Exception as e:
            logger.warning(f"MQTT connect fehlgeschlagen: {e}")
    return _client


def _pub(topic: str, payload: dict | str, retain: bool = False):
    client = get_client()
    if client is None or not _connected:
        return
    data = json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else payload
    client.publish(f"{_BASE}/{topic}", data, qos=0, retain=retain)


def _publish_discovery(client: mqtt.Client):
    sensors = [
        dict(id="status", name="Navigation Status",
             state_topic=f"{_BASE}/status", icon="mdi:navigation"),
        dict(id="instruction", name="Aktuelle Anweisung",
             state_topic=f"{_BASE}/instruction",
             value_template="{{ value_json.text }}", icon="mdi:sign-direction"),
        dict(id="distance", name="Verbleibende Distanz",
             state_topic=f"{_BASE}/route",
             value_template="{{ value_json.distance_remaining }}",
             unit_of_measurement="m", icon="mdi:map-marker-distance"),
        dict(id="eta", name="Ankunft in",
             state_topic=f"{_BASE}/route",
             value_template="{{ value_json.duration_remaining }}",
             unit_of_measurement="s", icon="mdi:clock-outline"),
        dict(id="speed", name="Geschwindigkeit",
             state_topic=f"{_BASE}/position",
             value_template="{{ value_json.speed }}",
             unit_of_measurement="km/h", icon="mdi:speedometer"),
    ]
    for s in sensors:
        sid = s.pop("id")
        client.publish(
            f"homeassistant/sensor/yapaia_{sid}/config",
            json.dumps({**s, "unique_id": f"yapaia_{sid}", "device": _DEVICE_INFO}, ensure_ascii=False),
            retain=True,
        )

    # Device Tracker — zeigt Fahrzeugposition auf der HA-Karte
    client.publish(
        "homeassistant/device_tracker/yapaia_vehicle/config",
        json.dumps({
            "unique_id": "yapaia_vehicle",
            "name": "Yapaia Go Fahrzeug",
            "state_topic": f"{_BASE}/status",
            "json_attributes_topic": f"{_BASE}/position",
            "icon": "mdi:car",
            "device": _DEVICE_INFO,
        }, ensure_ascii=False),
        retain=True,
    )


def publish_position(lat: float, lon: float, speed: float = 0.0, heading: float = 0.0):
    _pub("position", {
        "lat": lat, "lon": lon,
        "latitude": lat, "longitude": lon,  # HA device_tracker erwartet diese Keys
        "speed": round(speed),
        "heading": round(heading),
        "gps_accuracy": 10,
        "ts": datetime.now(timezone.utc).isoformat(),
    })


def publish_instruction(text: str, distance: float, sign: int, street: str = ""):
    _pub("instruction", {
        "text": text,
        "distance": round(distance),
        "sign": sign,
        "street": street,
    })


def publish_route(distance_remaining: float, duration_remaining: float, destination: str = ""):
    _pub("route", {
        "distance_remaining": round(distance_remaining),
        "duration_remaining": round(duration_remaining),
        "destination": destination,
    })


def publish_status(navigating: bool):
    # HA device_tracker erwartet "home" oder "not_home" als State
    _pub("status", "not_home" if navigating else "home", retain=True)


def shutdown():
    global _client, _connected
    if _client:
        _client.loop_stop()
        _client.disconnect()
        _client = None
        _connected = False
