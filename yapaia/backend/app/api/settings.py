import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.auth import get_current_user
from app.db import get_db
from app.models import User, UserPreference

router = APIRouter(prefix="/api/settings", tags=["settings"])


class HASettings(BaseModel):
    ha_base_url: str = ""
    ha_token: str | None = None  # None = bestehendes Token beibehalten


async def _get_or_create(db: AsyncSession, user: User) -> UserPreference:
    pref = await db.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
    if not pref:
        pref = UserPreference(user_id=user.id, data={})
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
    return pref


@router.get("/ha")
async def get_ha_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    pref = await _get_or_create(db, user)
    data = pref.data or {}
    return {
        "ha_base_url": data.get("ha_base_url", ""),
        "ha_token_set": bool(data.get("ha_token", "")),
    }


@router.put("/ha")
async def update_ha_settings(
    body: HASettings,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    pref = await _get_or_create(db, user)
    data = dict(pref.data or {})
    data["ha_base_url"] = body.ha_base_url
    if body.ha_token is not None:
        data["ha_token"] = body.ha_token
    pref.data = data
    flag_modified(pref, "data")
    await db.commit()
    return {"ok": True}


@router.get("/ha/test")
async def test_ha_connection(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    pref = await _get_or_create(db, user)
    data = pref.data or {}
    url = data.get("ha_base_url", "")
    token = data.get("ha_token", "")
    if not url or not token:
        return {"ok": False, "detail": "URL oder Token nicht konfiguriert"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{url.rstrip('/')}/api/",
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code == 200:
            return {"ok": True, "detail": "Verbindung erfolgreich ✓"}
        return {"ok": False, "detail": f"HA antwortete mit HTTP {resp.status_code}"}
    except httpx.ConnectError:
        return {"ok": False, "detail": "Verbindung verweigert — URL prüfen"}
    except httpx.TimeoutException:
        return {"ok": False, "detail": "Timeout — ist HA erreichbar?"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}
