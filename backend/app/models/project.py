import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin

ClickUpEntityType = Enum("space", "folder", "list", name="clickup_entity_type")


class Project(TenantMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("idx_projects_company", "user_id", "company_tag"),
        {"schema": None},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id")
    )
    clickup_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    clickup_type: Mapped[str] = mapped_column(ClickUpEntityType, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    company_tag: Mapped[str | None] = mapped_column(String)
    priority_tier: Mapped[int | None] = mapped_column(SmallInteger)
    settings: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
