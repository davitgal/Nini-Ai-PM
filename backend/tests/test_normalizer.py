"""Tests for the ClickUp task normalizer."""


from app.services.clickup.models import ClickUpTask
from app.services.clickup.normalizer import (
    ms_epoch_to_datetime,
    normalize_task,
)


def test_ms_epoch_to_datetime():
    # April 5, 2024 00:00:00 UTC
    result = ms_epoch_to_datetime("1712275200000")
    assert result is not None
    assert result.year == 2024
    assert result.month == 4
    assert result.tzinfo is not None


def test_ms_epoch_none():
    assert ms_epoch_to_datetime(None) is None
    assert ms_epoch_to_datetime("") is None


def test_normalize_task(sample_clickup_task_json):
    task = ClickUpTask.model_validate(sample_clickup_task_json)
    result = normalize_task(task, folder_name="Yerevan Mall")

    assert result["clickup_task_id"] == "86b8ph9jq"
    assert result["title"] == "Fix login bug on admin panel"
    assert result["status"] == "to do"
    assert result["status_type"] == "unstarted"
    assert result["clickup_priority"] == 2
    assert result["company_tag"] == "Yerevan Mall"  # from custom field
    assert result["task_type_tag"] == "Дефолтная работа"
    assert result["creator_id"] == 60900172
    assert result["due_date"] is not None
    assert result["time_estimate"] == 3600000
    assert result["time_spent"] == 1200000
    assert result["archived"] is False
    assert len(result["assignees"]) == 1
    assert result["assignees"][0]["id"] == 60900172
    assert "bug" in result["tags"]
    assert result["sync_hash"] is not None


def test_company_tag_from_custom_field(sample_clickup_task_json):
    """Company custom field should take priority over folder name."""
    task = ClickUpTask.model_validate(sample_clickup_task_json)
    result = normalize_task(task, folder_name="SomethingElse")
    assert result["company_tag"] == "Yerevan Mall"


def test_company_tag_fallback_to_folder(sample_clickup_task_json):
    """When custom field has no value, fall back to folder name."""
    sample_clickup_task_json["custom_fields"][0]["value"] = None
    task = ClickUpTask.model_validate(sample_clickup_task_json)
    result = normalize_task(task, folder_name="TrueCodeLab")
    assert result["company_tag"] == "TrueCodeLab"


def test_sync_hash_consistency(sample_clickup_task_json):
    """Same input should produce same hash."""
    task = ClickUpTask.model_validate(sample_clickup_task_json)
    r1 = normalize_task(task)
    r2 = normalize_task(task)
    assert r1["sync_hash"] == r2["sync_hash"]


def test_sync_hash_changes_on_status_change(sample_clickup_task_json):
    """Different status should produce different hash."""
    task1 = ClickUpTask.model_validate(sample_clickup_task_json)
    r1 = normalize_task(task1)

    sample_clickup_task_json["status"]["status"] = "in progress"
    task2 = ClickUpTask.model_validate(sample_clickup_task_json)
    r2 = normalize_task(task2)

    assert r1["sync_hash"] != r2["sync_hash"]
