"""Shared test fixtures."""

import pytest


@pytest.fixture
def sample_clickup_task_json() -> dict:
    """A realistic ClickUp task payload for testing."""
    return {
        "id": "86b8ph9jq",
        "custom_id": None,
        "name": "Fix login bug on admin panel",
        "description": "Users can't log in after password reset",
        "text_content": "Users can't log in after password reset",
        "status": {"status": "to do", "color": "#d3d3d3", "type": "unstarted", "orderindex": 0},
        "priority": {"id": "2", "priority": "high", "color": "#ffcc00"},
        "assignees": [
            {"id": 60900172, "username": "Davit Galstyan", "email": "davit.onlywork@gmail.com"}
        ],
        "creator": {"id": 60900172, "username": "Davit Galstyan"},
        "tags": [{"name": "bug"}],
        "custom_fields": [
            {
                "id": "cf_company",
                "name": "Company",
                "type": "drop_down",
                "value": 0,
                "type_config": {
                    "options": [
                        {"id": "opt1", "name": "Yerevan Mall", "orderindex": 0},
                        {"id": "opt2", "name": "TrueCodeLab", "orderindex": 1},
                        {"id": "opt3", "name": "Cubics Soft", "orderindex": 2},
                    ]
                },
            },
            {
                "id": "cf_type",
                "name": "Type",
                "type": "drop_down",
                "value": 2,
                "type_config": {
                    "options": [
                        {"id": "t1", "name": "Весит годами", "orderindex": 0},
                        {"id": "t2", "name": "Что-то новенькое", "orderindex": 1},
                        {"id": "t3", "name": "Дефолтная работа", "orderindex": 2},
                    ]
                },
            },
        ],
        "due_date": "1712275200000",
        "start_date": "1711929600000",
        "date_created": "1711843200000",
        "date_updated": "1712100000000",
        "date_closed": None,
        "date_done": None,
        "time_estimate": 3600000,
        "time_spent": 1200000,
        "points": None,
        "archived": False,
        "url": "https://app.clickup.com/t/86b8ph9jq",
        "list": {"id": "901410057231", "name": "All tasks"},
        "folder": {"id": "90144609752", "name": "Yerevan Mall", "hidden": False},
        "space": {"id": "90142606205"},
        "parent": None,
    }
