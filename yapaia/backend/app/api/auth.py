import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.config import settings as app_settings
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    plan: str
    is_admin: bool = False
    gps_push_token: str | None = None
    has_password: bool = False  # False = Google-only-Account (kein lokales Passwort)

    model_config = {"from_attributes": True}


@router.post("/register", response_model=UserOut, status_code=201)
async def register(body: RegisterBody, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "E-Mail bereits registriert")
    if len(body.password) < 8:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Passwort muss mindestens 8 Zeichen haben")
    # First registered user automatically becomes admin
    user_count = await db.scalar(select(func.count(User.id)))
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name,
        is_admin=(user_count == 0),
        gps_push_token=secrets.token_urlsafe(24),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.email == form.username))
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Ungültige Anmeldedaten")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


class UpdateProfileBody(BaseModel):
    display_name: str | None = None
    email: EmailStr | None = None
    current_password: str | None = None
    new_password: str | None = None


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UpdateProfileBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.display_name is not None:
        name = body.display_name.strip()
        if not name:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Name darf nicht leer sein")
        user.display_name = name

    if body.email is not None and body.email != user.email:
        if user.hashed_password:
            if not verify_password(body.current_password or "", user.hashed_password):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Aktuelles Passwort ist falsch")
        taken = await db.scalar(select(User).where(User.email == body.email))
        if taken and taken.id != user.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "E-Mail-Adresse bereits vergeben")
        user.email = body.email

    if body.new_password is not None:
        if len(body.new_password) < 8:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "Neues Passwort muss mindestens 8 Zeichen haben")
        if user.hashed_password:
            if not verify_password(body.current_password or "", user.hashed_password):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Aktuelles Passwort ist falsch")
        user.hashed_password = hash_password(body.new_password)

    await db.commit()
    await db.refresh(user)
    return user


@router.get("/providers")
async def auth_providers() -> dict:
    return {"google": bool(app_settings.google_client_id)}


@router.get("/google")
async def google_login():
    if not app_settings.google_client_id:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Google OAuth nicht konfiguriert")
    params = urlencode({
        "client_id": app_settings.google_client_id,
        "redirect_uri": app_settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/google/callback")
async def google_callback(
    code: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
):
    if error or not code:
        return RedirectResponse("/?auth_error=google_denied")

    async with httpx.AsyncClient(timeout=10.0) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": app_settings.google_client_id,
                "client_secret": app_settings.google_client_secret,
                "redirect_uri": app_settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            return RedirectResponse("/?auth_error=google_token")

        access_token = token_resp.json().get("access_token", "")
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            return RedirectResponse("/?auth_error=google_userinfo")

    info = userinfo_resp.json()
    google_id = info.get("sub", "")
    email = info.get("email", "")
    name = info.get("name") or (email.split("@")[0] if email else "Google User")

    if not google_id or not email:
        return RedirectResponse("/?auth_error=google_missing_data")

    user = await db.scalar(select(User).where(User.google_id == google_id))
    if not user:
        user = await db.scalar(select(User).where(User.email == email))
        if user:
            user.google_id = google_id
    if not user:
        user_count = await db.scalar(select(func.count(User.id)))
        user = User(
            email=email,
            hashed_password="",
            display_name=name,
            google_id=google_id,
            is_admin=(user_count == 0),
            gps_push_token=secrets.token_urlsafe(24),
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)
    jwt = create_access_token(user.id)
    return RedirectResponse(f"/?token={jwt}")


@router.post("/gps-token/regenerate", response_model=UserOut)
async def regenerate_gps_token(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Erzeugt einen neuen GPS-Push-Token. Alter Token wird ungültig."""
    user.gps_push_token = secrets.token_urlsafe(24)
    await db.commit()
    await db.refresh(user)
    return user
