"""Base classes for the Navi addon system."""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass
class SettingsField:
    key: str
    type: Literal["text", "password", "number", "boolean", "select", "range"]
    label: str
    required: bool = False
    default: Any = None
    placeholder: str = ""
    description: str = ""
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: list[dict] = field(default_factory=list)


@dataclass
class AddonManifest:
    id: str
    name: str
    version: str
    description: str
    icon: str
    author: str
    category: str
    capabilities: list[str]
    settings_schema: list[SettingsField]
    min_navi_version: str = "0.4.0"

    @classmethod
    def from_file(cls, path: Path) -> "AddonManifest":
        data = json.loads(path.read_text())
        data["settings_schema"] = [
            SettingsField(**f) for f in data.get("settings_schema", [])
        ]
        return cls(**data)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


class BaseAddon:
    """Base class for all Navi addons.

    Subclass this and name the class ``Plugin`` in your plugin.py.
    """

    manifest: AddonManifest
    addon_id: str
    _db_factory = None
    _data_dir: Path | None = None

    def set_context(self, db_factory, data_dir: Path) -> None:
        self._db_factory = db_factory
        self._data_dir = data_dir

    async def initialize(self) -> None:
        """Called once after loading. Use for async setup (DB tables, etc.)."""

    async def handle_request(
        self,
        path: str,
        request: Any,
        user: Any,
        db: Any,
        addon_settings: dict,
    ) -> Any:
        """Handle an API call to /api/addons/{addon_id}/{path}.

        ``addon_settings`` is the calling user's saved settings for this addon.
        Return any FastAPI-compatible response object.
        """
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Not implemented"}, status_code=404)

    async def shutdown(self) -> None:
        """Called on app shutdown. Clean up resources."""

    async def on_gps_update(
        self,
        user_id: str,
        lat: float,
        lon: float,
        speed: float,
        heading: float,
    ) -> None:
        """Called for every GPS position message from the navigation WebSocket."""

    async def get_map_layer(self, user_id: str, addon_settings: dict) -> dict | None:
        """Return a GeoJSON FeatureCollection for an addon-provided map layer, or None."""
        return None
