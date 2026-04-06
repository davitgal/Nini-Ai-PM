"""Sync management endpoints — trigger sync, register webhooks, view logs."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import direct_session_factory
from app.dependencies import get_current_user_id, get_db
from app.models.sync_log import SyncLog
from app.models.task import UnifiedTask
from app.models.workspace import Workspace
from app.schemas.sync import SyncLogEntry, SyncResult, SyncStatusResponse
from app.services.clickup.client import ClickUpClient
from app.services.sync_engine import SyncEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sync", tags=["sync"])

WEBHOOK_EVENTS = [
    "taskCreated",
    "taskUpdated",
    "taskDeleted",
    "taskStatusUpdated",
    "taskAssigneeUpdated",
    "taskDueDateUpdated",
    "taskPriorityUpdated",
    "taskMoved",
    "taskCommentPosted",
]


@router.get("/workspaces")
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """List all workspaces with sync info."""
    result = await db.execute(
        select(Workspace).where(Workspace.user_id == user_id)
    )
    workspaces = result.scalars().all()
    return [
        {
            "id": str(ws.id),
            "name": ws.name,
            "clickup_team_id": ws.clickup_team_id,
            "sync_enabled": ws.sync_enabled,
            "last_full_sync": ws.last_full_sync,
            "webhook_active": ws.webhook_id is not None,
        }
        for ws in workspaces
    ]


@router.post("/full", response_model=list[SyncResult])
async def trigger_full_sync(
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Trigger full sync for all enabled workspaces.

    Uses direct DB connection (bypasses PgBouncer) for long-running sync.
    """
    async with direct_session_factory() as db:
        try:
            result = await db.execute(
                select(Workspace).where(
                    Workspace.user_id == user_id,
                    Workspace.sync_enabled.is_(True),
                )
            )
            workspaces = result.scalars().all()

            if not workspaces:
                return []

            results = []
            engine = SyncEngine(db, user_id)
            for ws in workspaces:
                try:
                    sr = await engine.full_sync(ws)
                    results.append(
                        SyncResult(
                            workspace=ws.name,
                            created=sr.created,
                            updated=sr.updated,
                            skipped=sr.skipped,
                            archived=sr.archived,
                            errors=sr.errors,
                        )
                    )
                except Exception:
                    logger.exception("Sync failed for workspace %s", ws.name)
                    results.append(
                        SyncResult(
                            workspace=ws.name,
                            created=0,
                            updated=0,
                            skipped=0,
                            archived=0,
                            errors=1,
                        )
                    )

            return results
        except Exception as e:
            logger.exception("Full sync failed: %s", e)
            raise HTTPException(
                status_code=500,
                detail=f"Sync failed: {str(e)}",
            )


@router.post("/workspace/{workspace_id}", response_model=SyncResult)
async def sync_single_workspace(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Trigger full sync for a single workspace.

    Uses direct DB connection (bypasses PgBouncer) for long-running sync.
    """
    async with direct_session_factory() as db:
        try:
            result = await db.execute(
                select(Workspace).where(
                    Workspace.id == workspace_id,
                    Workspace.user_id == user_id,
                )
            )
            workspace = result.scalar_one_or_none()
            if not workspace:
                raise HTTPException(status_code=404, detail="Workspace not found")

            engine = SyncEngine(db, user_id)
            sr = await engine.full_sync(workspace)
            return SyncResult(
                workspace=workspace.name,
                created=sr.created,
                updated=sr.updated,
                skipped=sr.skipped,
                archived=sr.archived,
                errors=sr.errors,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Sync failed for workspace %s: %s", workspace_id, e)
            raise HTTPException(
                status_code=500,
                detail=f"Sync failed: {str(e)}",
            )


@router.get("/status", response_model=list[SyncStatusResponse])
async def sync_status(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Get sync status for all workspaces."""
    result = await db.execute(
        select(Workspace).where(Workspace.user_id == user_id)
    )
    workspaces = result.scalars().all()

    statuses = []
    for ws in workspaces:
        task_count = await db.execute(
            select(func.count(UnifiedTask.id)).where(
                UnifiedTask.user_id == user_id,
                UnifiedTask.workspace_id == ws.id,
            )
        )
        statuses.append(
            SyncStatusResponse(
                workspace_name=ws.name,
                last_full_sync=ws.last_full_sync,
                tasks_synced=task_count.scalar() or 0,
                webhook_active=ws.webhook_id is not None,
            )
        )

    return statuses


@router.get("/log", response_model=list[SyncLogEntry])
async def sync_log(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Get recent sync log entries."""
    result = await db.execute(
        select(SyncLog)
        .where(SyncLog.user_id == user_id)
        .order_by(SyncLog.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/register-webhook")
async def register_webhook(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Register a ClickUp webhook for a workspace."""
    from app.config import settings

    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.user_id == user_id,
        )
    )
    workspace = result.scalar_one_or_none()
    if not workspace or not workspace.clickup_api_token:
        return {"error": "Workspace not found or no API token configured"}

    endpoint = f"{settings.webhook_base_url}/api/v1/webhooks/clickup"

    client = ClickUpClient(workspace.clickup_api_token)
    try:
        webhook = await client.create_webhook(
            workspace.clickup_team_id, endpoint, WEBHOOK_EVENTS
        )
        workspace.webhook_id = webhook.id
        workspace.webhook_secret = webhook.secret
        await db.commit()

        return {
            "webhook_id": webhook.id,
            "endpoint": endpoint,
            "events": WEBHOOK_EVENTS,
        }
    finally:
        await client.close()


@router.delete("/webhook")
async def deregister_webhook(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Deregister a ClickUp webhook."""
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.user_id == user_id,
        )
    )
    workspace = result.scalar_one_or_none()
    if not workspace or not workspace.webhook_id or not workspace.clickup_api_token:
        return {"error": "No active webhook found"}

    client = ClickUpClient(workspace.clickup_api_token)
    try:
        await client.delete_webhook(workspace.webhook_id)
        workspace.webhook_id = None
        workspace.webhook_secret = None
        await db.commit()
        return {"status": "webhook removed"}
    finally:
        await client.close()
