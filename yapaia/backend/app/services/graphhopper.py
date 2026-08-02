import httpx
from app.config import settings

SIGN_TEXT = {
    -7: "Links abbiegen", -3: "Scharf links", -1: "Leicht links",
    0: "Geradeaus", 1: "Leicht links", 2: "Links abbiegen",
    3: "Scharf links", 4: "Ziel erreicht", 5: "Zwischenziel",
    6: "Rechts abbiegen", 7: "Scharf rechts",
}


async def get_route(
    from_lon: float,
    from_lat: float,
    to_lon: float,
    to_lat: float,
    via: list[tuple[float, float]] | None = None,
    profile: str = "car",
    locale: str = "de",
    vehicle_height: float | None = None,
    vehicle_weight: float | None = None,
    vehicle_width: float | None = None,
    routing_mode: str = "fastest",
) -> dict:
    # `motorcycle` has no separate GH profile — use `car` (same road access).
    # Curvy routing is handled via custom_model below.
    gh_profile = "car" if profile == "motorcycle" else profile

    via_points = [[lon, lat] for lat, lon in (via or [])]
    payload: dict = {
        "points": [[from_lon, from_lat], *via_points, [to_lon, to_lat]],
        "profile": gh_profile,
        "locale": locale,
        "instructions": True,
        "calc_points": True,
        "points_encoded": False,
        # OSM max_speed per segment, returned as [[from_pt_idx, to_pt_idx, value], ...]
        "details": ["max_speed"],
    }

    # CH (Contraction Hierarchies) is only precomputed for car+bike with default
    # weighting. foot, motorhome, and any custom routing_mode need flexible mode.
    needs_flexible = gh_profile in ("foot", "motorhome") or routing_mode != "fastest"
    if needs_flexible:
        payload["ch.disable"] = True

    # Build custom_model by collecting priority rules and distance_influence.
    priority: list[dict] = []
    distance_influence: int | None = None

    if routing_mode == "shortest":
        # distance_influence 0–1000: 0 = fastest (time only), 1000 = shortest (distance only)
        distance_influence = 999

    elif routing_mode == "curvy":
        # Prefer secondary/tertiary roads, avoid motorways/trunks.
        # road_class is a built-in GH encoded value — no graph rebuild required.
        priority = [
            {"if": "road_class == MOTORWAY",     "multiply_by": "0.3"},
            {"if": "road_class == TRUNK",        "multiply_by": "0.4"},
            {"if": "road_class == PRIMARY",      "multiply_by": "0.8"},
            {"if": "road_class == SECONDARY",    "multiply_by": "1.3"},
            {"if": "road_class == TERTIARY",     "multiply_by": "1.4"},
            {"if": "road_class == UNCLASSIFIED", "multiply_by": "1.2"},
        ]

    elif routing_mode == "very_curvy":
        priority = [
            {"if": "road_class == MOTORWAY",     "multiply_by": "0.05"},
            {"if": "road_class == TRUNK",        "multiply_by": "0.1"},
            {"if": "road_class == PRIMARY",      "multiply_by": "0.5"},
            {"if": "road_class == SECONDARY",    "multiply_by": "1.5"},
            {"if": "road_class == TERTIARY",     "multiply_by": "1.6"},
            {"if": "road_class == UNCLASSIFIED", "multiply_by": "1.4"},
            {"if": "road_class == LIVING_STREET","multiply_by": "1.2"},
        ]

    # Motorhome dimension restrictions (merged into priority list)
    if profile == "motorhome":
        if vehicle_height:
            priority.append({"if": f"max_height < {vehicle_height}", "multiply_by": "0"})
        if vehicle_weight:
            priority.append({"if": f"max_weight < {vehicle_weight}", "multiply_by": "0"})
        if vehicle_width:
            priority.append({"if": f"max_width < {vehicle_width}", "multiply_by": "0"})

    if priority or distance_influence is not None:
        custom_model: dict = {}
        if priority:
            custom_model["priority"] = priority
        if distance_influence is not None:
            custom_model["distance_influence"] = distance_influence
        payload["custom_model"] = custom_model

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{settings.graphhopper_url}/route", json=payload)
        resp.raise_for_status()
        data = resp.json()

    path = data["paths"][0]
    coords = path["points"]["coordinates"]

    instructions = []
    for inst in path.get("instructions", []):
        idx = inst["interval"][0]
        coord = coords[idx] if idx < len(coords) else None
        instructions.append({
            "text": inst.get("text") or SIGN_TEXT.get(inst["sign"], ""),
            "street": inst.get("street_name", ""),
            "distance": inst["distance"],
            "duration": inst["time"] // 1000,
            "sign": inst["sign"],
            "exit_number": inst.get("exit_number", 0),
            "coordinate": [coord[1], coord[0]] if coord else None,
        })

    max_speed = path.get("details", {}).get("max_speed", [])

    return {
        "distance": path["distance"],
        "duration": path["time"] // 1000,
        "geometry": path["points"],
        "bbox": path.get("bbox"),
        "instructions": instructions,
        # Per-segment OSM speed limits: list of [from_pt_idx, to_pt_idx, value_kmh|null]
        "max_speed": max_speed,
    }
