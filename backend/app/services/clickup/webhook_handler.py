"""Process inbound ClickUp webhook events."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.sync_log import SyncLog
from app.models.task import UnifiedTask
from app.models.workspace import Workspace
from app.schemas.clickup import WebhookPayload
from app.services.clickup.client import ClickUpClient
from app.services.clickup.normalizer import normalize_task
from app.services.sync_engine import SyncEngine

logger = logging.getLogger(__name__)

# Events that trigger a full task fetch and upsert
TASK_EVENTS = {
    "taskCreated",
    "taskUpdated",
    "taskStatusUpdated",
    "taskAssigneeUpdated",
    "taskDueDateUpdated",
    "taskPriorityUpdated",
    "taskMoved",
}


class WebhookHandler:
    def __init__(self, db: AsyncSession, user_id: uuid.UUID):
        self.db = db
        self.user_id = user_id

    async def handle(self, payload: WebhookPayload) -> None:
        """Route and process a webhook event."""
        # Build idempotency key
        idempotency_key = self._build_idempotency_key(payload)
        if idempotency_key and await self._already_processed(idempotency_key):
            logger.debug("Skipping duplicate webhook event: %s", idempotency_key)
            return

        logger.info("Processing webhook event: %s for task %s", payload.event, payload.task_id)

        try:
            if payload.event == "taskDeleted":
                await self._handle_task_deleted(payload)
            elif payload.event in TASK_EVENTS and payload.task_id:
                await self._handle_task_change(payload)
            else:
                logger.debug("Ignoring unhandled event type: %s", payload.event)

            await self._log_sync(
                payload=payload,
                status="success",
                idempotency_key=idempotency_key,
            )
        except Exception as e:
            logger.exception("Error processing webhook: %s", e)
            await self._log_sync(
                payload=payload,
                status="failed",
                idempotency_key=idempotency_key,
                error=str(e),
            )
            raise

        await self.db.commit()

    async def _handle_task_change(self, payload: WebhookPayload) -> None:
        """Fetch full task from ClickUp API and upsert."""
        # Find workspace by webhook_id to get the right API token
        workspace = await self._get_workspace_by_webhook(payload.webhook_id)
        if not workspace or not workspace.clickup_api_token:
            logger.warning("No workspace found for webhook_id %s", payload.webhook_id)
            return

        client = ClickUpClient(workspace.clickup_api_token)
        try:
            task = await client.get_task(payload.task_id)

            # Resolve folder name for company_tag fallback
            folder_name = task.folder.name if task.folder and task.folder.name else None

            normalized = normalize_task(task, folder_name=folder_name)

            # Find project_id from the list
            if task.list:
                project = await self.db.execute(
                    select(Project).where(Project.clickup_id == task.list.id)
                )
                proj = project.scalar_one_or_none()
                if proj:
                    normalized["project_id"] = proj.id

            # Check sync_hash to prevent loops from our own outbound pushes
            existing = await self.db.execute(
                select(UnifiedTask).where(
                    UnifiedTask.clickup_task_id == payload.task_id
                )
            )
            existing_task = existing.scalar_one_or_none()

            if existing_task and existing_task.sync_hash == normalized["sync_hash"]:
                logger.debug("Task %s unchanged (sync_hash match), skipping", payload.task_id)
                return

            engine = SyncEngine(self.db, self.user_id)
            action = await engine._upsert_task(normalized)
            logger.info("Webhook %s: task %s → %s", payload.event, payload.task_id, action)
        finally:
            await client.close()

    async def _handle_task_deleted(self, payload: WebhookPayload) -> None:
        """Soft-delete a task (set archived=true)."""
        if not payload.task_id:
            return
        result = await self.db.execute(
            select(UnifiedTask).where(UnifiedTask.clickup_task_id == payload.task_id)
        )
        task = result.scalar_one_or_none()
        if task:
            task.archived = True
            task.updated_at = datetime.now(UTC)
            logger.info("Soft-deleted task %s", payload.task_id)

    async def _get_workspace_by_webhook(self, webhook_id: str) -> Workspace | None:
        result = await self.db.execute(
            select(Workspace).where(Workspace.webhook_id == webhook_id)
        )
        return result.scalar_one_or_none()

    def _build_idempotency_key(self, payload: WebhookPayload) -> str | None:
        if payload.history_items:
            return f"{payload.webhook_id}:{payload.history_items[0].id}"
        return f"{payload.webhook_id}:{payload.event}:{payload.task_id}"

    async def _already_processed(self, idempotency_key: str) -> bool:
        result = await self.db.execute(
            select(SyncLog).where(SyncLog.payload_hash == idempotency_key).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _log_sync(
        self,
        payload: WebhookPayload,
        status: str,
        idempotency_key: str | None = None,
        error: str | None = None,
    ) -> None:
        log = SyncLog(
            user_id=self.user_id,
            direction="inbound",
            event_type=payload.event,
            clickup_task_id=payload.task_id,
            status=status,
            payload_hash=idempotency_key,
            error_message=error,
        )
        self.db.add(log)
