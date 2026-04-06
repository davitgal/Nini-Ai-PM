"""Normalize ClickUp task JSON into unified_tasks schema."""

import hashlib
import logging
from datetime import UTC, datetime

from app.services.clickup.models import ClickUpTask

logger = logging.getLogger(__name__)

# Known "Company" custom field dropdown values
COMPANY_FIELD_NAME = "Company"
TYPE_FIELD_NAME = "Type"


def ms_epoch_to_datetime(ms: str | int | None) -> datetime | None:
    """Convert ClickUp millisecond epoch string to datetime."""
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=UTC)
    except (ValueError, TypeError, OSError):
        return None


def extract_dropdown_value(task: ClickUpTask, field_name: str) -> str | None:
    """Extract the selected value from a dropdown custom field.

    ClickUp dropdown fields store the selected option index as an integer value.
    The actual option name is in type_config.options.
    """
    for field in task.custom_fields:
        if field.name == field_name:
            if field.value is None:
                return None
            # For dropdown fields, value is the index (int) into type_config.options
            if field.type == "drop_down" and field.type_config:
                options = field.type_config.get("options", [])
                try:
                    idx = int(field.value)
                    if 0 <= idx < len(options):
                        return options[idx].get("name")
                except (ValueError, TypeError):
                    pass
            # Fallback: value might be the string directly
            if isinstance(field.value, str):
                return field.value
            return None
    return None


def resolve_company_tag(task: ClickUpTask, folder_name: str | None = None) -> str | None:
    """Resolve company tag: custom field first, then folder name fallback."""
    company = extract_dropdown_value(task, COMPANY_FIELD_NAME)
    if company:
        return company
    if folder_name:
        return folder_name
    return None


def compute_sync_hash(normalized: dict) -> str:
    """Compute MD5 hash of key task fields for change detection."""
    fields_to_hash = [
        str(normalized.get("title", "")),
        str(normalized.get("description", "")),
        str(normalized.get("status", "")),
        str(normalized.get("clickup_priority")),
        str(normalized.get("due_date")),
        str(normalized.get("start_date")),
        str(normalized.get("assignees")),
        str(normalized.get("company_tag")),
        str(normalized.get("archived")),
    ]
    combined = "|".join(fields_to_hash)
    return hashlib.md5(combined.encode()).hexdigest()


def normalize_task(
    task: ClickUpTask,
    folder_name: str | None = None,
) -> dict:
    """Convert a ClickUp task to a flat dict matching unified_tasks columns."""
    assignees = [
        {"id": a.id, "username": a.username}
        for a in task.assignees
    ]

    priority_val = None
    if task.priority and task.priority.id:
        try:
            priority_val = int(task.priority.id)
        except ValueError:
            pass

    company_tag = resolve_company_tag(task, folder_name)
    task_type_tag = extract_dropdown_value(task, TYPE_FIELD_NAME)

    custom_fields_dict = {
        f.name: f.value for f in task.custom_fields
    }

    tags = [t.name for t in task.tags]

    normalized = {
        # ClickUp identity
        "clickup_task_id": task.id,
        "clickup_custom_id": task.custom_id,
        "clickup_list_id": task.list.id if task.list else None,
        "clickup_url": task.url,
        # Core fields
        "title": task.name,
        "description": task.text_content or task.description or "",
        "status": task.status.status,
        "status_type": task.status.type,
        "source": "clickup",
        # Priority
        "clickup_priority": priority_val,
        # Context
        "company_tag": company_tag,
        "task_type_tag": task_type_tag,
        # People
        "assignees": assignees,
        "creator_id": task.creator.id if task.creator else None,
        # Dates
        "due_date": ms_epoch_to_datetime(task.due_date),
        "start_date": ms_epoch_to_datetime(task.start_date),
        "date_created": ms_epoch_to_datetime(task.date_created),
        "date_updated": ms_epoch_to_datetime(task.date_updated),
        "date_closed": ms_epoch_to_datetime(task.date_closed),
        "date_done": ms_epoch_to_datetime(task.date_done),
        # Metadata
        "tags": tags,
        "custom_fields": custom_fields_dict,
        "time_estimate": task.time_estimate,
        "time_spent": task.time_spent or 0,
        "points": task.points,
        "archived": task.archived,
    }

    normalized["sync_hash"] = compute_sync_hash(normalized)
    return normalized
