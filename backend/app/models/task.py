import uuid
from datetime import datetime

from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin

TaskSource = Enum("clickup", "manual", "telegram", name="task_source")
NiniPriority = Enum("critical", "high", "medium", "low", "none", name="nini_priority")


class UnifiedTask(TenantMixin, Base):
    __tablename__ = "unified_tasks"
    __table_args__ = (
        Index("idx_tasks_user_status", "user_id", "status"),
        Index("idx_tasks_user_company", "user_id", "company_tag"),
        Index("idx_tasks_user_priority", "user_id", "nini_priority"),
        Index("idx_tasks_due", "user_id", "due_date", postgresql_where="due_date IS NOT NULL"),
        Index("idx_tasks_clickup", "clickup_task_id"),
        Index("idx_tasks_updated", "user_id", "date_updated"),
        Index("idx_tasks_workspace", "workspace_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id")
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id")
    )

    # ClickUp identity
    clickup_task_id: Mapped[str | None] = mapped_column(String, unique=True)
    clickup_custom_id: Mapped[str | None] = mapped_column(String)
    clickup_list_id: Mapped[str | None] = mapped_column(String)
    clickup_url: Mapped[str | None] = mapped_column(Text)

    # Normalized fields
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[str] = mapped_column(String, nullable=False)
    status_type: Mapped[str | None] = mapped_column(String)
    source: Mapped[str] = mapped_column(TaskSource, server_default="clickup")

    # Priority
    clickup_priority: Mapped[int | None] = mapped_column(SmallInteger)
    nini_priority: Mapped[str] = mapped_column(NiniPriority, server_default="none")
    priority_reason: Mapped[str | None] = mapped_column(Text)

    # Company/workspace context
    company_tag: Mapped[str | None] = mapped_column(String)
    task_type_tag: Mapped[str | None] = mapped_column(String)

    # People
    assignees: Mapped[list] = mapped_column(JSONB, server_default="[]")
    creator_id: Mapped[int | None] = mapped_column(BigInteger)

    # Dates
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_created: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_closed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_done: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Metadata
    tags: Mapped[list] = mapped_column(JSONB, server_default="[]")
    custom_fields: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    time_estimate: Mapped[int | None] = mapped_column(BigInteger)
    time_spent: Mapped[int] = mapped_column(BigInteger, server_default="0")
    points: Mapped[float | None] = mapped_column(REAL)
    archived: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # Sync metadata
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    sync_hash: Mapped[str | None] = mapped_column(String)
    sync_direction: Mapped[str] = mapped_column(String, server_default="inbound")
    sync_conflict: Mapped[bool] = mapped_column(Boolean, server_default="false")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
