"""
NyayaSaar API — Auth service (JWT + bcrypt).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.user import User
from app.db.session import get_async_session

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Password hashing (bcrypt directly — passlib is unmaintained)
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash a password with bcrypt (bcrypt only uses the first 72 bytes)."""
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        # Malformed hash in storage — treat as verification failure.
        return False


# ---------------------------------------------------------------------------
# JWT (PyJWT)
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=True)


def _get_secret() -> str:
    return settings.jwt_secret_key or settings.app_secret_key


def create_access_token(user_id: str, email: str) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    expire_minutes = settings.jwt_access_token_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, _get_secret(), algorithm=settings.jwt_algorithm)
    return token, expire_minutes * 60


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, _get_secret(), algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI dependency — current authenticated user
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> User:
    payload = decode_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return user


# ---------------------------------------------------------------------------
# Register / Login helpers (called from router)
# ---------------------------------------------------------------------------


async def register_user(db: AsyncSession, email: str, password: str, full_name: str | None) -> tuple[User, str, int]:
    """Create a new user. Raises HTTPException on duplicate email."""
    email = email.lower().strip()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
    )
    db.add(user)
    await db.flush()  # populate user.id
    token, expires_in = create_access_token(user.id, user.email)
    return user, token, expires_in


async def login_user(db: AsyncSession, email: str, password: str) -> tuple[User, str, int]:
    """Authenticate user. Raises HTTPException on bad credentials."""
    email = email.lower().strip()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    token, expires_in = create_access_token(user.id, user.email)
    return user, token, expires_in
