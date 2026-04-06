"""Periodic full sync as a safety net for missed webhooks."""

import asyncio
import logging

from sqlalchemy import select

from app.database import direct_session_factory
from app.dependencies import DAVIT_USER_ID
from app.models.workspace import Workspace
from app.services.sync_engine import SyncEngine

logger = logging.getLogger(__name__)

SYNC_INTERVAL_HOURS = 6


async def periodic_full_sync() -> None:
    """Run full sync for all enabled workspaces on a schedule."""
    while True:
        await asyncio.sleep(SYNC_INTERVAL_HOURS * 3600)
        logger.info("Starting scheduled full sync")
        try:
            async with direct_session_factory() as db:
                result = await db.execute(
                    select(Workspace).where(
                        Workspace.user_id == DAVIT_USER_ID,
                        Workspace.sync_enabled.is_(True),
                    )
                )
                workspaces = result.scalars().all()

                engine = SyncEngine(db, DAVIT_USER_ID)
                for ws in workspaces:
                    try:
                        sr = await engine.full_sync(ws)
                        logger.info(
                            "Scheduled sync %s: created=%d updated=%d skipped=%d errors=%d",
                            ws.name,
                            sr.created,
                            sr.updated,
                            sr.skipped,
                            sr.errors,
                        )
                    except Exception:
                        logger.exception("Scheduled sync failed for %s", ws.name)
        except Exception:
            logger.exception("Scheduled sync loop error")
