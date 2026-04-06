"""Pydantic schemas for ClickUp webhook payloads."""

from typing import Any

from pydantic import BaseModel


class WebhookUser(BaseModel):
    id: int
    username: str | None = None
    email: str | None = None


class HistoryItem(BaseModel):
    id: str
    type: int
    date: str
    field: str
    parent_id: str
    before: Any = None
    after: Any = None
    user: WebhookUser | None = None


class WebhookPayload(BaseModel):
    webhook_id: str
    event: str
    task_id: str | None = None
    history_items: list[HistoryItem] = []
