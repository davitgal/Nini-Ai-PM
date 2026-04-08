"""Schemas for Nini issue backlog endpoints."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NiniIssueCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(default="", max_length=8000)
    issue_type: str = Field(default="logic", max_length=50)
    severity: str = Field(default="medium", max_length=20)
    source: str = Field(default="manual", max_length=30)
    task_title: str | None = Field(default=None, max_length=255)
    conversation_snippet: str | None = Field(default=None, max_length=8000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NiniIssueUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=20)
    severity: str | None = Field(default=None, max_length=20)
    resolution_notes: str | None = Field(default=None, max_length=8000)


class NiniIssueResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    issue_type: str
    severity: str
    status: str
    source: str
    task_title: str | None
    conversation_snippet: str | None
    metadata: dict[str, Any]
    resolved_at: datetime | None
    resolution_notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NiniIssueListResponse(BaseModel):
    items: list[NiniIssueResponse]
    total: int
