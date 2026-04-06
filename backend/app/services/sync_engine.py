"""Orchestrates full and incremental sync between ClickUp and Supabase."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.task import UnifiedTask
from app.models.workspace import Workspace
from app.services.clickup.client import ClickUpClient
from app.services.clickup.normalizer import normalize_task

logger = logging.getLogger(__name__)


class SyncResult:
    def __init__(self):
        self.created = 0
        self.updated = 0
        self.skipped = 0
        self.errors = 0
        self.archived = 0


class SyncEngine:
    def __init__(self, db: AsyncSession, user_id: uuid.UUID):
        self.db = db
        self.user_id = user_id

    async def full_sync(self, workspace: Workspace) -> SyncResult:
        """Walk entire workspace hierarchy, sync all tasks."""
        result = SyncResult()

        token = workspace.clickup_api_token
        if not token:
            logger.error("No API token for workspace %s", workspace.name)
            return result

        # Track all clickup_task_ids seen during this sync for reconciliation
        self._seen_clickup_ids: set[str] = set()

        client = ClickUpClient(token)
        try:
            team_id = workspace.clickup_team_id
            logger.info("Starting full sync for workspace %s (team_id=%s)", workspace.name, team_id)

            # Disable statement timeout for long-running sync operations
            await self.db.execute(text("SET statement_timeout = 0"))

            spaces = await client.get_spaces(team_id)
            for space in spaces:
                # Upsert space as project
                space_project_id = await self._upsert_project(
                    workspace_id=workspace.id,
                    clickup_id=space.id,
                    clickup_type="space",
                    name=space.name,
                    parent_id=None,
                    company_tag=None,
                )
                await self.db.commit()
                logger.info("Synced space: %s", space.name)

                # Folderless lists in the space
                folderless_lists = await client.get_folderless_lists(space.id)
                for lst in folderless_lists:
                    await self.db.execute(text("SET statement_timeout = 0"))
                    list_project_id = await self._upsert_project(
                        workspace_id=workspace.id,
                        clickup_id=lst.id,
                        clickup_type="list",
                        name=lst.name,
                        parent_id=space_project_id,
                        company_tag=None,
                    )
                    await self._sync_list_tasks(client, lst.id, list_project_id, None, result)
                    await self.db.commit()

                # Folders in the space
                folders = await client.get_folders(space.id)
                for folder in folders:
                    await self.db.execute(text("SET statement_timeout = 0"))
                    folder_project_id = await self._upsert_project(
                        workspace_id=workspace.id,
                        clickup_id=folder.id,
                        clickup_type="folder",
                        name=folder.name,
                        parent_id=space_project_id,
                        company_tag=folder.name,  # folder name as potential company tag
                    )
                    await self.db.commit()
                    logger.info("Synced folder: %s", folder.name)

                    lists = await client.get_lists(folder.id)
                    for lst in lists:
                        await self.db.execute(text("SET statement_timeout = 0"))
                        list_project_id = await self._upsert_project(
                            workspace_id=workspace.id,
                            clickup_id=lst.id,
                            clickup_type="list",
                            name=lst.name,
                            parent_id=folder_project_id,
                            company_tag=folder.name,
                        )
                        await self._sync_list_tasks(
                            client, lst.id, list_project_id, folder.name, result
                        )
                        await self.db.commit()

            # Reconciliation: archive tasks that exist in DB but not in ClickUp
            # Scoped strictly to this workspace to avoid touching other workspaces
            db_tasks = await self.db.execute(
                select(UnifiedTask).where(
                    UnifiedTask.workspace_id == workspace.id,
                    UnifiedTask.user_id == self.user_id,
                    UnifiedTask.archived.is_(False),
                    UnifiedTask.clickup_task_id.isnot(None),
                )
            )
            for task in db_tasks.scalars().all():
                if task.clickup_task_id not in self._seen_clickup_ids:
                    task.archived = True
                    task.sync_direction = "inbound"
                    task.last_synced_at = datetime.now(UTC)
                    result.archived += 1
            await self.db.commit()

            if result.archived:
                logger.info(
                    "Reconciliation: archived %d tasks no longer in ClickUp for %s",
                    result.archived,
                    workspace.name,
                )

            # Update last_full_sync timestamp
            workspace.last_full_sync = datetime.now(UTC)
            await self.db.commit()

            logger.info(
                "Full sync complete for %s: created=%d, updated=%d, skipped=%d, archived=%d, errors=%d",
                workspace.name,
                result.created,
                result.updated,
                result.skipped,
                result.archived,
                result.errors,
            )
        finally:
            await client.close()

        return result

    async def sync_single_task(
        self, client: ClickUpClient, clickup_task_id: str, folder_name: str | None = None
    ) -> str:
        """Sync a single task from ClickUp. Returns 'created', 'updated', or 'skipped'."""
        task = await client.get_task(clickup_task_id)
        normalized = normalize_task(task, folder_name=folder_name)
        return await self._upsert_task(normalized)

    async def _sync_list_tasks(
        self,
        client: ClickUpClient,
        list_id: str,
        project_id: uuid.UUID,
        folder_name: str | None,
        result: SyncResult,
    ) -> None:
        """Sync all tasks in a ClickUp list."""
        try:
            tasks = await client.get_all_tasks(list_id, include_closed=True)
            for task in tasks:
                try:
                    normalized = normalize_task(task, folder_name=folder_name)
                    normalized["project_id"] = project_id
                    action = await self._upsert_task(normalized)
                    if action == "created":
                        result.created += 1
                    elif action == "updated":
                        result.updated += 1
                    else:
                        result.skipped += 1
                except Exception:
                    logger.exception("Error syncing task %s", task.id)
                    result.errors += 1
        except Exception:
            logger.exception("Error fetching tasks for list %s", list_id)
            result.errors += 1

    async def _upsert_task(self, normalized: dict) -> str:
        """Insert or update a task. Returns 'created', 'updated', or 'skipped'."""
        clickup_task_id = normalized["clickup_task_id"]

        # Track this ID for reconciliation
        if hasattr(self, "_seen_clickup_ids"):
            self._seen_clickup_ids.add(clickup_task_id)

        # Check if task already exists
        existing = await self.db.execute(
            select(UnifiedTask).where(UnifiedTask.clickup_task_id == clickup_task_id)
        )
        existing_task = existing.scalar_one_or_none()

        if existing_task:
            # Check sync_hash — skip if unchanged
            if existing_task.sync_hash == normalized.get("sync_hash"):
                return "skipped"

            # Update existing task
            for key, value in normalized.items():
                if key != "clickup_task_id" and hasattr(existing_task, key):
                    setattr(existing_task, key, value)
            existing_task.last_synced_at = datetime.now(UTC)
            existing_task.sync_direction = "inbound"
            await self.db.flush()
            return "updated"
        else:
            # Create new task
            task = UnifiedTask(
                user_id=self.user_id,
                **normalized,
            )
            self.db.add(task)
            await self.db.flush()
            return "created"

    async def _upsert_project(
        self,
        workspace_id: uuid.UUID,
        clickup_id: str,
        clickup_type: str,
        name: str,
        parent_id: uuid.UUID | None,
        company_tag: str | None,
    ) -> uuid.UUID:
        """Upsert a project (space/folder/list) and return its ID."""
        existing = await self.db.execute(
            select(Project).where(Project.clickup_id == clickup_id)
        )
        project = existing.scalar_one_or_none()

        if project:
            project.name = name
            project.company_tag = company_tag
            await self.db.flush()
            return project.id

        project = Project(
            user_id=self.user_id,
            workspace_id=workspace_id,
            parent_id=parent_id,
            clickup_id=clickup_id,
            clickup_type=clickup_type,
            name=name,
            company_tag=company_tag,
        )
        self.db.add(project)
        await self.db.flush()
        return project.id
