"""
NyayaSaar API — Auth router
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_async_session
from app.models.responses import ApiResponse
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth import get_current_user, login_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=ApiResponse[TokenResponse], status_code=201)
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[TokenResponse]:
    user, token, expires_in = await register_user(db, body.email, body.password, body.full_name)
    return ApiResponse.ok(
        TokenResponse(access_token=token, token_type="bearer", expires_in=expires_in)
    )


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[TokenResponse]:
    user, token, expires_in = await login_user(db, body.email, body.password)
    return ApiResponse.ok(
        TokenResponse(access_token=token, token_type="bearer", expires_in=expires_in)
    )


@router.get("/me", response_model=ApiResponse[UserResponse])
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[UserResponse]:
    return ApiResponse.ok(UserResponse.model_validate(current_user))
