"""
MJPEG camera streaming.

Browser → WS /ws/camera/{slot}  (pushes raw JPEG frames)
Client  → GET /api/camera/stream/{slot}  (MJPEG, no-auth for now)
"""

import asyncio
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

router = APIRouter()

# Latest JPEG frame per camera slot ("0", "1", …)
_frames: dict[str, bytes] = {}


@router.websocket("/ws/camera/{slot}")
async def camera_ingest(websocket: WebSocket, slot: str):
    """Receives JPEG frames from the browser for a given camera slot."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            _frames[slot] = data
    except WebSocketDisconnect:
        _frames.pop(slot, None)


@router.get("/api/camera/stream/{slot}")
async def camera_stream(slot: str):
    """MJPEG stream — compatible with Home Assistant, VLC, and any browser."""

    async def generate():
        last: Optional[bytes] = None
        idle = 0
        while True:
            frame = _frames.get(slot)
            if frame is not None and frame is not last:
                last = frame
                idle = 0
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" +
                    frame +
                    b"\r\n"
                )
            else:
                idle += 1
                if idle > 600:   # ~30 s without a new frame → close
                    break
            await asyncio.sleep(0.05)   # poll at ≤20 fps

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # disables nginx proxy buffering
        },
    )
