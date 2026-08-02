from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.auth import get_current_user
from app.db import get_db
from app.models import User, UserPreference

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


class PreferencesBody(BaseModel):
    """All keys optional — clients send only what they want to change."""
    default_profile: str | None = None        # "car" | "motorhome" | "bike" | "foot"
    gps_source: str | None = None             # "browser" | "server" | "url" | "simulate"
    map_pitch: int | None = None              # 0 | 60
    map_bearing_mode: str | None = None       # "north" | "heading"
    tts_enabled: bool | None = None
    default_vehicle_id: str | None = None     # "" = no specific vehicle selected
    alt_backend_url: str | None = None        # Alternativer Server für Routing + Suche
    # Kartenstile (mapstyle add-on)
    map_style_light: str | None = None        # z.B. "carto_voyager"
    map_style_dark: str | None = None         # z.B. "carto_voyager_night"
    # Tankstellen
    stations_enabled: bool | None = None
    stations_radius: int | None = None        # km
    stations_fuel: str | None = None          # "e5" | "e10" | "diesel"


async def _get_or_create(db: AsyncSession, user: User) -> UserPreference:
    pref = await db.scalar(
        select(UserPreference).where(UserPreference.user_id == user.id)
    )
    if not pref:
        pref = UserPreference(user_id=user.id, data={})
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
    return pref


@router.get("/")
async def get_preferences(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    pref = await _get_or_create(db, user)
    return pref.data or {}


@router.put("/")
async def update_preferences(
    body: PreferencesBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    pref = await _get_or_create(db, user)
    incoming = body.model_dump(exclude_none=True)
    merged = {**(pref.data or {}), **incoming}
    pref.data = merged
    # SQLAlchemy's JSON change-tracking is opt-in for in-place dict mutation;
    # since we assigned a new dict above, flag the column dirty either way.
    flag_modified(pref, "data")
    await db.commit()
    return pref.data
