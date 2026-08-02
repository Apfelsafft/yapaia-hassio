import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import admin, auth, camera, favorites, gps, health, map, preferences, route, search, settings, vehicles, ws
from app.api import addons as addons_api
from app.addons import manager as addon_manager
from app.config import settings as app_settings
from app.db import AsyncSessionLocal, init_db
from app.models import UserAddon  # noqa: F401 — ensures table is registered with Base.metadata
from app.services.gps import get_service as get_gps_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await addon_manager.load_all(AsyncSessionLocal)
    if app_settings.gps_serial_port:
        get_gps_service().start_serial(app_settings.gps_serial_port, app_settings.gps_serial_baud)
    yield
    await addon_manager.shutdown_all()


app = FastAPI(title="Navi", version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(route.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(map.router, prefix="/api")
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(vehicles.router)
app.include_router(settings.router)
app.include_router(favorites.router)
app.include_router(preferences.router)
app.include_router(ws.router)
app.include_router(gps.router)
app.include_router(camera.router)
app.include_router(addons_api.router)

# Im HA Add-on (Single-Container) liegt das gebaute Frontend unter backend/static/
_static = Path(__file__).parent.parent / "static"
if _static.is_dir():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="frontend")
