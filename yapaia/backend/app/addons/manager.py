"""Addon manager: loads, tracks and dispatches to installed addons."""
import importlib.util
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from app.addons.base import AddonManifest, BaseAddon

logger = logging.getLogger(__name__)

ADDONS_DIR = Path("/app/addons")
DATA_DIR = Path("/data/addons")

_addons: Dict[str, BaseAddon] = {}
_manifests: Dict[str, AddonManifest] = {}

# user_id → set of addon_ids the user has installed
_user_addons: Dict[str, Set[str]] = {}


def _load_addon(addon_dir: Path) -> Optional[BaseAddon]:
    manifest_path = addon_dir / "manifest.json"
    plugin_path = addon_dir / "plugin.py"

    if not manifest_path.exists() or not plugin_path.exists():
        return None

    try:
        manifest = AddonManifest.from_file(manifest_path)
        spec = importlib.util.spec_from_file_location(
            f"navi_addon_{manifest.id}", plugin_path
        )
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        plugin_class = getattr(module, "Plugin", None)
        if plugin_class is None:
            logger.error("Addon %s: no 'Plugin' class in plugin.py", manifest.id)
            return None

        instance: BaseAddon = plugin_class()
        instance.manifest = manifest
        instance.addon_id = manifest.id
        return instance
    except Exception:
        logger.exception("Failed to load addon from %s", addon_dir)
        return None


async def load_all(db_factory) -> None:
    """Scan ADDONS_DIR, initialise every valid addon, and restore user associations."""
    if not ADDONS_DIR.exists():
        logger.info("No addons directory at %s", ADDONS_DIR)
        return

    for addon_dir in sorted(ADDONS_DIR.iterdir()):
        if not addon_dir.is_dir():
            continue
        await _activate(addon_dir, db_factory)

    # Restore per-user addon associations from DB into in-memory cache
    try:
        from sqlalchemy import select
        from app.models import UserAddon
        async with db_factory() as db:
            rows = (await db.execute(select(UserAddon))).scalars().all()
            for row in rows:
                _user_addons.setdefault(row.user_id, set()).add(row.addon_id)
        logger.info("Restored user-addon associations for %d users", len(_user_addons))
    except Exception:
        logger.exception("Failed to restore user-addon associations")


async def _activate(addon_dir: Path, db_factory) -> bool:
    instance = _load_addon(addon_dir)
    if instance is None:
        return False

    data_dir = DATA_DIR / instance.addon_id
    data_dir.mkdir(parents=True, exist_ok=True)
    instance.set_context(db_factory, data_dir)

    try:
        await instance.initialize()
        _addons[instance.addon_id] = instance
        _manifests[instance.addon_id] = instance.manifest
        logger.info("Addon loaded: %s v%s", instance.manifest.name, instance.manifest.version)
        return True
    except Exception:
        logger.exception("Addon %s initialisation failed", instance.addon_id)
        return False


async def reload_addon(addon_id: str, db_factory) -> bool:
    """Dynamically load or reload a single addon (used after install)."""
    addon_dir = ADDONS_DIR / addon_id
    if not addon_dir.exists():
        return False

    if addon_id in _addons:
        try:
            await _addons[addon_id].shutdown()
        except Exception:
            pass
        _addons.pop(addon_id, None)
        _manifests.pop(addon_id, None)

    return await _activate(addon_dir, db_factory)


async def unload_addon(addon_id: str) -> bool:
    """Shutdown and remove an addon from memory (does not touch disk)."""
    if addon_id not in _addons:
        return False
    try:
        await _addons[addon_id].shutdown()
    except Exception:
        logger.exception("Error shutting down addon %s", addon_id)
    _addons.pop(addon_id, None)
    _manifests.pop(addon_id, None)
    return True


# ── Per-user tracking ─────────────────────────────────────────────────────────

def register_user_addon(user_id: str, addon_id: str) -> None:
    _user_addons.setdefault(user_id, set()).add(addon_id)


def unregister_user_addon(user_id: str, addon_id: str) -> None:
    _user_addons.get(user_id, set()).discard(addon_id)


def user_has_addon(user_id: str, addon_id: str) -> bool:
    return addon_id in _user_addons.get(user_id, set())


def user_addon_ids(user_id: str) -> Set[str]:
    return set(_user_addons.get(user_id, set()))


def get(addon_id: str) -> Optional[BaseAddon]:
    return _addons.get(addon_id)


def is_loaded(addon_id: str) -> bool:
    return addon_id in _addons


def list_manifests() -> List[dict]:
    return [m.to_dict() for m in _manifests.values()]


def manifest_for(addon_id: str) -> Optional[dict]:
    m = _manifests.get(addon_id)
    return m.to_dict() if m else None


async def shutdown_all() -> None:
    for addon in _addons.values():
        try:
            await addon.shutdown()
        except Exception:
            logger.exception("Error shutting down addon %s", addon.addon_id)


async def notify_gps(
    user_id: str, lat: float, lon: float, speed: float, heading: float
) -> None:
    """Broadcast a GPS position to all addons the user has installed."""
    user_installed = _user_addons.get(user_id, set())
    for addon in list(_addons.values()):
        if addon.addon_id not in user_installed:
            continue
        try:
            await addon.on_gps_update(user_id, lat, lon, speed, heading)
        except Exception:
            logger.debug("GPS hook error in addon %s", addon.addon_id, exc_info=True)


async def get_user_settings(addon_id: str, user_id: str, db) -> dict:
    """Load a user's settings for one addon from the database."""
    from sqlalchemy import select
    from app.models import AddonUserSettings

    result = await db.execute(
        select(AddonUserSettings).where(
            AddonUserSettings.user_id == user_id,
            AddonUserSettings.addon_id == addon_id,
        )
    )
    row = result.scalar_one_or_none()
    return row.settings if row else {}
