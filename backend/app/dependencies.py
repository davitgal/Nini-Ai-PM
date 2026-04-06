import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory

# Hardcoded user ID for Phase 1 (single user — Davit)
# Will be replaced with proper auth in multi-tenant phase
DAVIT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def get_current_user_id() -> uuid.UUID:
    """Returns current user ID. Hardcoded for Phase 1."""
    return DAVIT_USER_ID
