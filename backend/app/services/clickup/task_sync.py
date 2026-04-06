"""Outbound sync: push local changes to ClickUp."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync_log import SyncLog
from app.models.task import UnifiedTask
from app.models.workspace import Workspace
from app.services.clickup.client import ClickUpClient
from app.services.clickup.normalizer import ms_epoch_to_datetime

logger = logging.getLogger(__name__)


class OutboundSync:
    def __init__(self, db: AsyncSession, user_id: uuid.UUID):
        self.db = db
        self.user_id = user_id

    async def push_task_to_clickup(self, task_id: uuid.UUID) -> str:
        """Push local task changes to ClickUp.

        Returns: 'pushed', 'conflict', or 'skipped'
        """
        # Load local task
        result = await self.db.execute(
            select(UnifiedTask).where(
                UnifiedTask.id == task_id,
                UnifiedTask.user_id == self.user_id,
            )
        )
        task = result.scalar_one_or_none()
        if not task or not task.clickup_task_id:
            return "skipped"

        # Find workspace with API token
        workspace = await self._find_workspace_for_task(task)
        if not workspace or not workspace.clickup_api_token:
            logger.warning("No workspace/token found for task %s", task_id)
            return "skipped"

        client = ClickUpClient(workspace.clickup_api_token)
        try:
            # Fetch current task from ClickUp for conflict detection
            remote_task = await client.get_task(task.clickup_task_id)
            remote_updated = ms_epoch_to_datetime(remote_task.date_updated)

            # Conflict check: if ClickUp was updated after our last sync, flag conflict
            if remote_updated and task.last_synced_at and remote_updated > task.last_synced_at:
                logger.warning(
                    "Conflict detected for task %s: remote updated %s > local sync %s",
                    task.clickup_task_id,
                    remote_updated,
                    task.last_synced_at,
                )
                task.sync_conflict = True
                await self._log("conflict", task)
                await self.db.commit()
                return "conflict"

            # Build update payload (only changed fields)
            update_data: dict = {}
            if task.status != remote_task.status.status:
                update_data["status"] = task.status
            if task.clickup_priority is not None:
                has_remote = remote_task.priority and remote_task.priority.id
                remote_priority = int(remote_task.priority.id) if has_remote else None
                if task.clickup_priority != remote_priority:
                    update_data["priority"] = task.clickup_priority
            if task.due_date:
                local_due_ms = str(int(task.due_date.timestamp() * 1000))
                if local_due_ms != remote_task.due_date:
                    update_data["due_date"] = int(task.due_date.timestamp() * 1000)

            if not update_data:
                return "skipped"

            # Push to ClickUp
            await client.update_task(task.clickup_task_id, update_data)

            # Update sync metadata
            task.last_synced_at = datetime.now(UTC)
            task.sync_direction = "outbound"
            task.sync_conflict = False
            await self._log("success", task)
            await self.db.commit()

            logger.info("Pushed task %s to ClickUp: %s", task.clickup_task_id, update_data)
            return "pushed"
        finally:
            await client.close()

    async def _find_workspace_for_task(self, task: UnifiedTask) -> Workspace | None:
        """Find workspace that owns this task (via project → workspace)."""
        if not task.project_id:
            # Fallback: return first workspace with a token
            result = await self.db.execute(
                select(Workspace).where(
                    Workspace.user_id == self.user_id,
                    Workspace.clickup_api_token.isnot(None),
                ).limit(1)
            )
            return result.scalar_one_or_none()

        from app.models.project import Project

        result = await self.db.execute(
            select(Workspace)
            .join(Project, Project.workspace_id == Workspace.id)
            .where(Project.id == task.project_id)
        )
        return result.scalar_one_or_none()

    async def _log(self, status: str, task: UnifiedTask) -> None:
        log = SyncLog(
            user_id=self.user_id,
            direction="outbound",
            event_type="task_push",
            clickup_task_id=task.clickup_task_id,
            task_id=task.id,
            status=status,
        )
        self.db.add(log)
