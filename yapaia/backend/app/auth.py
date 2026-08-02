from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import User

_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_ALGORITHM = "HS256"
_ACCESS_TTL = timedelta(days=30)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + _ACCESS_TTL
    return jwt.encode({"sub": user_id, "exp": expire}, settings.secret_key, algorithm=_ALGORITHM)


async def get_current_user(
    token: str = Depends(_oauth2),
    db: AsyncSession = Depends(get_db),
) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ungültiges oder abgelaufenes Token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
        user_id: str = payload.get("sub", "")
    except JWTError:
        raise exc

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise exc
    return user


async def require_premium(user: User = Depends(get_current_user)) -> User:
    if user.plan != "premium":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Diese Funktion erfordert ein Premium-Abonnement",
        )
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin-Rechte erforderlich",
        )
    return user
