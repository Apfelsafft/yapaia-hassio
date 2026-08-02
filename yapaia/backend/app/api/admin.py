from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminUserOut(BaseModel):
    id: str
    email: str
    display_name: str
    plan: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateUserBody(BaseModel):
    plan: str | None = None
    is_active: bool | None = None
    is_admin: bool | None = None


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(select(User).order_by(User.created_at.desc()))
    return list(result)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: str,
    body: UpdateUserBody,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User nicht gefunden")
    if body.plan is not None:
        if body.plan not in ("free", "premium"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ungültiger Plan")
        target.plan = body.plan
    if body.is_active is not None:
        if target.id == admin.id and not body.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "Du kannst dich nicht selbst deaktivieren")
        target.is_active = body.is_active
    if body.is_admin is not None:
        if target.id == admin.id and not body.is_admin:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "Du kannst dir nicht selbst die Admin-Rechte entziehen")
        target.is_admin = body.is_admin
    await db.commit()
    await db.refresh(target)
    return target


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Du kannst dich nicht selbst löschen")
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User nicht gefunden")
    await db.delete(target)
    await db.commit()
    return None
