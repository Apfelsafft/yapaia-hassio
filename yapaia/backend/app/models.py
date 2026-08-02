import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    plan: Mapped[str] = mapped_column(String(20), default="free")  # free | premium
    # Eigener Token für /api/gps/push — pro User eindeutig, regenerierbar.
    gps_push_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    @property
    def has_password(self) -> bool:
        return bool(self.hashed_password)

    vehicles: Mapped[list["Vehicle"]] = relationship("Vehicle", back_populates="user",
                                                      cascade="all, delete-orphan")
    favorites: Mapped[list["Favorite"]] = relationship("Favorite", back_populates="user",
                                                        cascade="all, delete-orphan")
    preferences: Mapped["UserPreference | None"] = relationship(
        "UserPreference", back_populates="user", cascade="all, delete-orphan", uselist=False,
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="car")  # car | motorhome | bike
    # Abmessungen für Wohnmobil-Routing (Meter / Tonnen)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    length: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Kraftstoffsorte für Tankstellen-Feature
    fuel_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Freitext-Notizen (z. B. Kennzeichen, Versicherung)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship("User", back_populates="vehicles")


class Favorite(Base):
    """Saved place. `kind` is 'home' | 'work' (max one each per user) or 'custom'.

    `label` is the display name (e.g. "Zuhause", "Arbeit" or user-given);
    `address` is the geocoded address from the search, kept separately so
    the settings UI can show the real address while the chip shows the name.
    """
    __tablename__ = "favorites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    type: Mapped[str] = mapped_column(String(50), default="")  # POI category from geocoder
    show_chip: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship("User", back_populates="favorites")


class UserPreference(Base):
    """Per-user preferences. Free-form JSON blob to keep adding new keys cheap."""
    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    user: Mapped["User"] = relationship("User", back_populates="preferences")


class AddonUserSettings(Base):
    """Per-user settings for each installed addon (free-form JSON blob)."""
    __tablename__ = "addon_user_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    addon_id: Mapped[str] = mapped_column(String(100), nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class UserAddon(Base):
    """Which add-ons a user has installed (+ optional license key for paid add-ons)."""
    __tablename__ = "user_addons"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    addon_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="NOW()")
    license_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # free | valid | expired | unverified
    license_status: Mapped[str] = mapped_column(String(20), default="free", nullable=False)

    user: Mapped["User"] = relationship("User")
