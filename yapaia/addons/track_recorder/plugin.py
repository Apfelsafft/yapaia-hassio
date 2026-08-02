"""Track Recorder addon – records GPS trips and exposes them via REST."""
from __future__ import annotations

import asyncio
import json
import math
import time
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from app.addons.base import BaseAddon


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _ActiveTrack:
    def __init__(self, gap_seconds: float = 300):
        self.id = str(uuid4())
        self.start_time = _now_iso()
        self.last_update = time.monotonic()
        self.gap_seconds = gap_seconds
        self.points: List[dict] = []
        self.total_distance = 0.0
        self.max_speed = 0.0

    def add_point(self, lat: float, lon: float, speed: float, heading: float) -> None:
        if self.points:
            last = self.points[-1]
            self.total_distance += _haversine_m(last["lat"], last["lon"], lat, lon)
        if speed > self.max_speed:
            self.max_speed = speed
        self.points.append({
            "lat": lat, "lon": lon,
            "speed": round(speed, 1), "heading": round(heading, 1),
            "ts": _now_iso(),
        })
        self.last_update = time.monotonic()

    def is_stale(self) -> bool:
        return (time.monotonic() - self.last_update) > self.gap_seconds

    def to_record(self) -> dict:
        speeds = [p["speed"] for p in self.points if p["speed"] > 0]
        avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
        return {
            "id": self.id,
            "start_time": self.start_time,
            "end_time": _now_iso(),
            "distance_km": round(self.total_distance / 1000, 3),
            "max_speed": round(self.max_speed, 1),
            "avg_speed": round(avg_speed, 1),
            "point_count": len(self.points),
            "locked": False,
            "points": self.points,
        }


class Plugin(BaseAddon):
    def __init__(self):
        self._active: Dict[str, _ActiveTrack] = {}
        self._settings_cache: Dict[str, dict] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        self._cleanup_task = asyncio.create_task(self._stale_track_sweeper())

    async def shutdown(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
        for user_id, track in list(self._active.items()):
            if len(track.points) >= 2:
                self._save_track(user_id, track, max_tracks=20)
        self._active.clear()

    async def _stale_track_sweeper(self) -> None:
        while True:
            await asyncio.sleep(60)
            for user_id, track in list(self._active.items()):
                if track.is_stale():
                    if len(track.points) >= 2:
                        settings = self._settings_cache.get(user_id, {})
                        self._save_track(user_id, track, int(settings.get("max_tracks", 20)))
                    del self._active[user_id]

    # ── GPS hook ──────────────────────────────────────────────────────────────

    async def on_gps_update(self, user_id, lat, lon, speed, heading) -> None:
        if not user_id or (lat == 0 and lon == 0):
            return

        settings = self._settings_cache.get(user_id, {})
        gap_seconds = int(settings.get("gap_minutes", 5)) * 60
        max_tracks = int(settings.get("max_tracks", 20))
        min_dist = float(settings.get("min_distance_m", 100))

        if user_id in self._active:
            track = self._active[user_id]
            if track.is_stale():
                if len(track.points) >= 2:
                    self._save_track(user_id, track, max_tracks)
                track = _ActiveTrack(gap_seconds)
                self._active[user_id] = track
        else:
            track = _ActiveTrack(gap_seconds)
            self._active[user_id] = track

        if track.points:
            last = track.points[-1]
            if _haversine_m(last["lat"], last["lon"], lat, lon) < min_dist and speed < 2:
                return

        track.add_point(lat, lon, speed, heading)

    # ── Storage helpers ───────────────────────────────────────────────────────

    def _tracks_dir(self, user_id: str) -> Path:
        d = self._data_dir / "tracks" / user_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _save_track(self, user_id: str, track: _ActiveTrack, max_tracks: int) -> None:
        d = self._tracks_dir(user_id)
        record = track.to_record()
        (d / f"{track.id}.json").write_text(json.dumps(record, ensure_ascii=False))
        # Purge oldest non-locked tracks if over limit
        files = sorted(d.glob("*.json"), key=lambda f: f.stat().st_mtime)
        unlocked = [f for f in files if not self._is_locked(f)]
        while len(files) > max_tracks and unlocked:
            unlocked.pop(0).unlink(missing_ok=True)
            files = sorted(d.glob("*.json"), key=lambda f: f.stat().st_mtime)
            unlocked = [f for f in files if not self._is_locked(f)]

    def _is_locked(self, path: Path) -> bool:
        try:
            return json.loads(path.read_text()).get("locked", False)
        except Exception:
            return False

    def _list_tracks(self, user_id: str) -> List[dict]:
        d = self._tracks_dir(user_id)
        summaries = []
        for f in sorted(d.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text())
                summaries.append({k: v for k, v in data.items() if k != "points"})
            except Exception:
                pass
        return summaries

    def _get_track(self, user_id: str, track_id: str) -> Optional[dict]:
        p = self._tracks_dir(user_id) / f"{track_id}.json"
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except Exception:
            return None

    def _delete_track(self, user_id: str, track_id: str) -> bool:
        p = self._tracks_dir(user_id) / f"{track_id}.json"
        if p.exists():
            p.unlink()
            return True
        return False

    def _toggle_lock(self, user_id: str, track_id: str) -> Optional[bool]:
        p = self._tracks_dir(user_id) / f"{track_id}.json"
        if not p.exists():
            return None
        data = json.loads(p.read_text())
        data["locked"] = not data.get("locked", False)
        p.write_text(json.dumps(data, ensure_ascii=False))
        return data["locked"]

    # ── Export formats ────────────────────────────────────────────────────────

    def _export_gpx(self, track: dict) -> str:
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gpx version="1.1" creator="Navi" xmlns="http://www.topografix.com/GPX/1/1">',
            "  <trk>",
            f'    <name>Track {track["start_time"]}</name>',
            "    <trkseg>",
        ]
        for p in track.get("points", []):
            lines.append(f'      <trkpt lat="{p["lat"]}" lon="{p["lon"]}">')
            lines.append(f'        <time>{p["ts"]}</time>')
            if p.get("speed"):
                lines.append(f'        <extensions><speed>{p["speed"]}</speed></extensions>')
            lines.append("      </trkpt>")
        lines += ["    </trkseg>", "  </trk>", "</gpx>"]
        return "\n".join(lines)

    def _export_geojson(self, track: dict) -> str:
        coords = [[p["lon"], p["lat"]] for p in track.get("points", [])]
        feature = {
            "type": "Feature",
            "properties": {
                "name": f"Track {track['start_time']}",
                "start_time": track["start_time"],
                "end_time": track["end_time"],
                "distance_km": track["distance_km"],
                "avg_speed": track["avg_speed"],
                "max_speed": track["max_speed"],
            },
            "geometry": {"type": "LineString", "coordinates": coords},
        }
        return json.dumps(feature, ensure_ascii=False, indent=2)

    def _export_kml(self, track: dict) -> str:
        coord_str = " ".join(
            f'{p["lon"]},{p["lat"]},0' for p in track.get("points", [])
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
            "  <Placemark>\n"
            f'    <name>Track {track["start_time"]}</name>\n'
            "    <LineString>\n"
            f"      <coordinates>{coord_str}</coordinates>\n"
            "    </LineString>\n"
            "  </Placemark>\n"
            "</kml>"
        )

    def _export_csv(self, track: dict) -> str:
        buf = StringIO()
        buf.write("timestamp,lat,lon,speed_kmh,heading\n")
        for p in track.get("points", []):
            buf.write(f'{p["ts"]},{p["lat"]},{p["lon"]},{p["speed"]},{p["heading"]}\n')
        return buf.getvalue()

    # ── HTTP handler ──────────────────────────────────────────────────────────

    async def handle_request(self, path, request, user, db, addon_settings):
        from fastapi.responses import JSONResponse, Response

        self._settings_cache[user.id] = addon_settings

        # GET tracks/
        if path == "tracks" and request.method == "GET":
            tracks = self._list_tracks(user.id)
            return JSONResponse({"tracks": tracks, "count": len(tracks)})

        # GET tracks/{id}/export?format=gpx|geojson|kml|csv
        if path.startswith("tracks/") and "/export" in path and request.method == "GET":
            track_id = path.split("/")[1]
            fmt = request.query_params.get("format", "gpx").lower()
            track = self._get_track(user.id, track_id)
            if track is None:
                return JSONResponse({"error": "Track nicht gefunden"}, status_code=404)

            if fmt == "gpx":
                return Response(
                    content=self._export_gpx(track),
                    media_type="application/gpx+xml",
                    headers={"Content-Disposition": f'attachment; filename="track_{track_id}.gpx"'},
                )
            if fmt == "geojson":
                return Response(
                    content=self._export_geojson(track),
                    media_type="application/geo+json",
                    headers={"Content-Disposition": f'attachment; filename="track_{track_id}.geojson"'},
                )
            if fmt == "kml":
                return Response(
                    content=self._export_kml(track),
                    media_type="application/vnd.google-earth.kml+xml",
                    headers={"Content-Disposition": f'attachment; filename="track_{track_id}.kml"'},
                )
            if fmt == "csv":
                return Response(
                    content=self._export_csv(track),
                    media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="track_{track_id}.csv"'},
                )
            return JSONResponse({"error": f"Unbekanntes Format: {fmt}"}, status_code=400)

        # GET tracks/{id}
        if path.startswith("tracks/") and request.method == "GET":
            track_id = path.split("/", 1)[1]
            track = self._get_track(user.id, track_id)
            if track is None:
                return JSONResponse({"error": "Track nicht gefunden"}, status_code=404)
            return JSONResponse(track)

        # DELETE tracks/{id}
        if path.startswith("tracks/") and request.method == "DELETE":
            track_id = path.split("/", 1)[1]
            track = self._get_track(user.id, track_id)
            if track and track.get("locked"):
                return JSONResponse({"error": "Track ist gesperrt"}, status_code=409)
            ok = self._delete_track(user.id, track_id)
            return JSONResponse({"ok": ok})

        # PATCH tracks/{id}/lock
        if path.startswith("tracks/") and path.endswith("/lock") and request.method == "PATCH":
            track_id = path.split("/")[1]
            new_state = self._toggle_lock(user.id, track_id)
            if new_state is None:
                return JSONResponse({"error": "Track nicht gefunden"}, status_code=404)
            return JSONResponse({"ok": True, "locked": new_state})

        # GET active
        if path == "active" and request.method == "GET":
            track = self._active.get(user.id)
            if not track:
                return JSONResponse({"active": False})
            return JSONResponse({
                "active": True,
                "point_count": len(track.points),
                "distance_km": round(track.total_distance / 1000, 3),
                "start_time": track.start_time,
            })

        # POST finalize
        if path == "finalize" and request.method == "POST":
            track = self._active.pop(user.id, None)
            if track and len(track.points) >= 2:
                max_tracks = int(addon_settings.get("max_tracks", 20))
                self._save_track(user.id, track, max_tracks)
                return JSONResponse({"ok": True, "saved": True})
            return JSONResponse({"ok": True, "saved": False})

        return JSONResponse({"error": "Not found"}, status_code=404)
