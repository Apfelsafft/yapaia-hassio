import logging

import httpx

logger = logging.getLogger(__name__)


async def _post_state(ha_url: str, ha_token: str, entity_id: str, state: str, attributes: dict | None = None):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{ha_url.rstrip('/')}/api/states/{entity_id}",
                json={"state": state, "attributes": attributes or {}},
                headers={
                    "Authorization": f"Bearer {ha_token}",
                    "Content-Type": "application/json",
                },
            )
    except Exception as e:
        logger.debug(f"HA REST fehlgeschlagen ({entity_id}): {e}")


async def push_navigation_state(
    ha_url: str,
    ha_token: str,
    navigating: bool,
    lat: float | None = None,
    lon: float | None = None,
    speed: float = 0,
    instruction: str = "",
    distance_remaining: float = 0,
    duration_remaining: float = 0,
    destination: str = "",
):
    if not ha_url or not ha_token:
        return

    await _post_state(ha_url, ha_token, "sensor.yapaia_status", "navigating" if navigating else "idle",
                      {"friendly_name": "Navigation Status"})

    if lat is not None and lon is not None:
        await _post_state(ha_url, ha_token, "device_tracker.yapaia_vehicle", "not_home", {
            "latitude": lat,
            "longitude": lon,
            "gps_accuracy": 10,
            "speed": round(speed),
            "friendly_name": "Yapaia Go Fahrzeug",
        })

    if instruction:
        await _post_state(ha_url, ha_token, "sensor.yapaia_instruction", instruction[:255],
                          {"friendly_name": "Aktuelle Anweisung"})

    if distance_remaining:
        await _post_state(ha_url, ha_token, "sensor.yapaia_distance", str(round(distance_remaining)),
                          {"unit_of_measurement": "m", "friendly_name": "Verbleibende Distanz"})

    if duration_remaining:
        await _post_state(ha_url, ha_token, "sensor.yapaia_eta", str(round(duration_remaining)),
                          {"unit_of_measurement": "s", "friendly_name": "Ankunft in"})
