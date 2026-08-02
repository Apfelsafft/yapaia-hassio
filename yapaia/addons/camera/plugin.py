"""Camera addon – MJPEG streaming via the browser's camera.

The actual streaming routes (/ws/camera/{slot}, /api/camera/stream/{slot})
are registered globally in the backend because WebSockets cannot be mounted
dynamically after app startup. This plugin controls whether the camera UI
is visible in the frontend.
"""
from app.addons.base import BaseAddon


class Plugin(BaseAddon):
    async def initialize(self) -> None:
        pass
