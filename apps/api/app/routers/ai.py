"""AI provider status endpoint.

Exposes only safe provider metadata. API keys are never returned.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.ai.registry import get_ai_status
from app.config import get_settings
from app.db.models.user import User
from app.models.responses import ApiResponse
from app.schemas.analysis import AIStatusResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status", response_model=ApiResponse[AIStatusResponse])
async def ai_status(
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[AIStatusResponse]:
    """Return the effective provider/model and whether fixture mode is active."""
    status_payload = get_ai_status(get_settings())
    return ApiResponse.ok(AIStatusResponse(**status_payload))
