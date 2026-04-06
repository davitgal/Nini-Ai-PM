"""Pydantic schemas for task API endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class TaskResponse(BaseModel):
    id: uuid.UUID
    clickup_task_id: str | None
    title: str
    description: str
    status: str
    status_type: str | None
    clickup_priority: int | None
    nini_priority: str
    company_tag: str | None
    task_type_tag: str | None
    assignees: list[dict]
    due_date: datetime | None
    start_date: datetime | None
    date_created: datetime | None
    date_updated: datetime | None
    clickup_url: str | None
    tags: list
    archived: bool
    last_synced_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskUpdate(BaseModel):
    status: str | None = None
    clickup_priority: int | None = None
    due_date: datetime | None = None
    nini_priority: str | None = None
    priority_reason: str | None = None


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int
    page: int
    limit: int


class TaskStatsResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    by_company: dict[str, int]
    by_priority: dict[str, int]
    overdue: int
