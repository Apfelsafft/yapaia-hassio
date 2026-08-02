from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_premium
from app.db import get_db
from app.models import User, Vehicle

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])

_FREE_VEHICLE_LIMIT = 1


class VehicleIn(BaseModel):
    name: str
    type: str = "car"
    fuel_type: str | None = None  # e5 | e10 | diesel | lpg | electric | None
    height: float | None = None
    width: float | None = None
    length: float | None = None
    weight: float | None = None
    notes: str = ""


class VehicleOut(BaseModel):
    id: str
    name: str
    type: str
    fuel_type: str | None
    height: float | None
    width: float | None
    length: float | None
    weight: float | None
    notes: str

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[VehicleOut])
async def list_vehicles(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(select(Vehicle).where(Vehicle.user_id == user.id))
    return result.all()


@router.post("/", response_model=VehicleOut, status_code=201)
async def create_vehicle(
    body: VehicleIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await db.scalar(
        select(Vehicle).where(Vehicle.user_id == user.id)
    )
    existing = await db.scalars(select(Vehicle).where(Vehicle.user_id == user.id))
    if len(existing.all()) >= _FREE_VEHICLE_LIMIT and user.plan == "free":
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "Free-Plan erlaubt nur 1 Fahrzeug. Upgrade auf Premium für unbegrenzte Fahrzeuge.",
        )
    vehicle = Vehicle(user_id=user.id, **body.model_dump())
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    return vehicle


@router.put("/{vehicle_id}", response_model=VehicleOut)
async def update_vehicle(
    vehicle_id: str,
    body: VehicleIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vehicle = await db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fahrzeug nicht gefunden")
    for k, v in body.model_dump().items():
        setattr(vehicle, k, v)
    await db.commit()
    await db.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}", status_code=204)
async def delete_vehicle(
    vehicle_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vehicle = await db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fahrzeug nicht gefunden")
    await db.delete(vehicle)
    await db.commit()
