import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GpsPosition:
    lat: float
    lon: float
    speed: float = 0.0
    heading: float = 0.0
    source: str = "unknown"
    timestamp: datetime = field(default_factory=datetime.utcnow)


class GpsService:
    def __init__(self):
        self._position: Optional[GpsPosition] = None
        self._subscribers: list[tuple[asyncio.Queue, asyncio.AbstractEventLoop]] = []

    def get_position(self) -> Optional[GpsPosition]:
        return self._position

    def publish(self, pos: GpsPosition):
        self._position = pos
        dead = []
        for q, loop in list(self._subscribers):
            try:
                loop.call_soon_threadsafe(q.put_nowait, pos)
            except Exception:
                dead.append((q, loop))
        for item in dead:
            try:
                self._subscribers.remove(item)
            except ValueError:
                pass

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        loop = asyncio.get_running_loop()
        self._subscribers.append((q, loop))
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers = [(sq, lo) for sq, lo in self._subscribers if sq is not q]

    def start_serial(self, port: str, baud: int = 9600):
        t = threading.Thread(target=self._serial_worker, args=(port, baud), daemon=True)
        t.start()
        logger.info("Serial GPS thread started for %s", port)

    def _serial_worker(self, port: str, baud: int):
        import time
        while True:
            try:
                import serial  # pyserial
                with serial.Serial(port, baud, timeout=1) as ser:
                    logger.info("Serial GPS connected on %s at %d baud", port, baud)
                    while True:
                        raw = ser.readline()
                        if not raw:
                            continue
                        line = raw.decode("ascii", errors="ignore").strip()
                        pos = _parse_nmea(line)
                        if pos:
                            self.publish(pos)
            except ImportError:
                logger.error("pyserial not installed — serial GPS disabled")
                return
            except Exception as exc:
                logger.warning("Serial GPS %s: %s — retrying in 5 s", port, exc)
                time.sleep(5)


def _parse_nmea(sentence: str) -> Optional[GpsPosition]:
    """Parse GPRMC/GNRMC NMEA sentences (lat, lon, speed, heading)."""
    if not sentence.startswith("$"):
        return None
    parts = sentence.split(",")
    tag = parts[0]

    if tag not in ("$GPRMC", "$GNRMC") or len(parts) < 9:
        return None
    if parts[2] != "A":  # A = active / valid fix
        return None
    try:
        lat = _nmea_to_decimal(parts[3], parts[4])
        lon = _nmea_to_decimal(parts[5], parts[6])
        speed = float(parts[7]) * 1.852 if parts[7] else 0.0
        heading_raw = parts[8].split("*")[0] if parts[8] else ""
        heading = float(heading_raw) if heading_raw else 0.0
        return GpsPosition(lat=lat, lon=lon, speed=speed, heading=heading, source="serial")
    except (ValueError, IndexError):
        return None


def _nmea_to_decimal(value: str, direction: str) -> float:
    degrees = int(float(value) / 100)
    minutes = float(value) - degrees * 100
    decimal = degrees + minutes / 60
    if direction in ("S", "W"):
        decimal = -decimal
    return decimal


_service = GpsService()


def get_service() -> GpsService:
    return _service
