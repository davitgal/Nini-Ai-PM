"""Pydantic models for ClickUp API responses."""

from pydantic import BaseModel, Field


class ClickUpUser(BaseModel):
    id: int
    username: str | None = None
    email: str | None = None
    color: str | None = None
    profile_picture: str | None = Field(None, alias="profilePicture")


class ClickUpStatus(BaseModel):
    status: str
    color: str | None = None
    type: str | None = None  # "unstarted", "active", "done", "closed", "custom"
    orderindex: int | None = None


class ClickUpPriority(BaseModel):
    id: str | None = None
    priority: str | None = None  # "1"=urgent, "2"=high, "3"=normal, "4"=low
    color: str | None = None


class ClickUpCustomFieldOption(BaseModel):
    id: str
    name: str
    color: str | None = None
    orderindex: int | None = None


class ClickUpCustomField(BaseModel):
    id: str
    name: str
    type: str
    value: str | int | float | list | dict | None = None
    type_config: dict | None = None


class ClickUpTag(BaseModel):
    name: str
    tag_fg: str | None = None
    tag_bg: str | None = None


class ClickUpListRef(BaseModel):
    id: str
    name: str | None = None


class ClickUpFolderRef(BaseModel):
    id: str
    name: str | None = None
    hidden: bool | None = None


class ClickUpSpaceRef(BaseModel):
    id: str


class ClickUpTask(BaseModel):
    id: str
    custom_id: str | None = None
    name: str
    description: str | None = None
    text_content: str | None = None
    status: ClickUpStatus
    priority: ClickUpPriority | None = None
    assignees: list[ClickUpUser] = []
    creator: ClickUpUser | None = None
    tags: list[ClickUpTag] = []
    custom_fields: list[ClickUpCustomField] = []
    due_date: str | None = None  # ms epoch as string
    start_date: str | None = None
    date_created: str | None = None
    date_updated: str | None = None
    date_closed: str | None = None
    date_done: str | None = None
    time_estimate: int | None = None
    time_spent: int | None = None
    points: float | None = None
    archived: bool = False
    url: str | None = None
    list: ClickUpListRef | None = None
    folder: ClickUpFolderRef | None = None
    space: ClickUpSpaceRef | None = None
    parent: str | None = None  # parent task ID if subtask

    model_config = {"extra": "allow"}


class ClickUpList(BaseModel):
    id: str
    name: str
    folder: ClickUpFolderRef | None = None
    space: ClickUpSpaceRef | None = None
    statuses: list[ClickUpStatus] = []
    task_count: int | None = None


class ClickUpFolder(BaseModel):
    id: str
    name: str
    lists: list[ClickUpList] = []
    space: ClickUpSpaceRef | None = None


class ClickUpSpace(BaseModel):
    id: str
    name: str
    statuses: list[ClickUpStatus] = []
    features: dict = Field(default_factory=dict)


class ClickUpWebhook(BaseModel):
    id: str
    userid: int | None = None
    team_id: int | None = None
    endpoint: str
    client_id: str | None = None
    events: list[str] = []
    status: str | None = None
    secret: str | None = None
