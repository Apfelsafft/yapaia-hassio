import json
import threading
from pathlib import Path

_FILE = Path("/data/navi-settings.json")
_DEFAULTS: dict[str, str] = {"ha_base_url": "", "ha_token": ""}
_lock = threading.Lock()
_data: dict[str, str] = {}


def _load():
    global _data
    try:
        stored = json.loads(_FILE.read_text()) if _FILE.exists() else {}
        _data = {**_DEFAULTS, **stored}
    except Exception:
        _data = dict(_DEFAULTS)


def get(key: str) -> str:
    return _data.get(key, "")


def update(values: dict[str, str]):
    with _lock:
        _data.update(values)
        try:
            _FILE.parent.mkdir(parents=True, exist_ok=True)
            _FILE.write_text(json.dumps(_data, indent=2, ensure_ascii=False))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Settings konnten nicht gespeichert werden: %s", e)


_load()
