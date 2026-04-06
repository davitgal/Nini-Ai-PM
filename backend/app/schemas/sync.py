"""Pydantic schemas for sync API endpoints."""

from datetime import datetime

from pydantic import BaseModel


class SyncStatusResponse(BaseModel):
    workspace_name: str
    last_full_sync: datetime | None
    tasks_synced: int
    webhook_active: bool


class SyncLogEntry(BaseModel):
    direction: str
    event_type: str | None
    clickup_task_id: str | None
    status: str
    error_message: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class SyncResult(BaseModel):
    workspace: str
    created: int
    updated: int
    skipped: int
    archived: int = 0
    errors: int
