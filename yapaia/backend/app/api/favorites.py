from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import Favorite, User

router = APIRouter(prefix="/api/favorites", tags=["favorites"])

_ALLOWED_KINDS = {"home", "work", "custom"}


class FavoriteBody(BaseModel):
    kind: str = Field(..., pattern="^(home|work|custom)$")
    label: str = Field(..., min_length=1, max_length=200)
    address: str = Field("", max_length=300)
    lat: float
    lon: float
    type: str = ""
    show_chip: bool = True


class FavoritePatch(BaseModel):
    show_chip: bool


class FavoriteOut(BaseModel):
    id: str
    kind: str
    label: str
    address: str
    lat: float
    lon: float
    type: str
    show_chip: bool

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[FavoriteOut])
async def list_favorites(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(Favorite).where(Favorite.user_id == user.id).order_by(Favorite.created_at)
    )
    return list(rows)


@router.post("/", response_model=FavoriteOut, status_code=201)
async def create_favorite(
    body: FavoriteBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.kind not in _ALLOWED_KINDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ungültiger Favoriten-Typ")

    # Special kinds (home/work) replace any existing entry of the same kind.
    if body.kind in ("home", "work"):
        existing = await db.scalar(
            select(Favorite).where(Favorite.user_id == user.id, Favorite.kind == body.kind)
        )
        if existing:
            existing.label = body.label
            existing.address = body.address
            existing.lat = body.lat
            existing.lon = body.lon
            existing.type = body.type
            # show_chip beim Überschreiben von home/work nicht zurücksetzen
            await db.commit()
            await db.refresh(existing)
            return existing

    fav = Favorite(
        user_id=user.id,
        kind=body.kind,
        label=body.label,
        address=body.address,
        lat=body.lat,
        lon=body.lon,
        type=body.type,
        show_chip=body.show_chip,
    )
    db.add(fav)
    await db.commit()
    await db.refresh(fav)
    return fav


@router.patch("/{fav_id}", response_model=FavoriteOut)
async def patch_favorite(
    fav_id: str,
    body: FavoritePatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    fav = await db.scalar(
        select(Favorite).where(Favorite.id == fav_id, Favorite.user_id == user.id)
    )
    if not fav:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Favorit nicht gefunden")
    fav.show_chip = body.show_chip
    await db.commit()
    await db.refresh(fav)
    return fav


@router.delete("/{fav_id}", status_code=204)
async def delete_favorite(
    fav_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    fav = await db.scalar(
        select(Favorite).where(Favorite.id == fav_id, Favorite.user_id == user.id)
    )
    if not fav:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Favorit nicht gefunden")
    await db.delete(fav)
    await db.commit()
