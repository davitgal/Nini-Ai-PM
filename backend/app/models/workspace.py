import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class Workspace(TenantMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("user_id", "clickup_team_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    clickup_team_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Each workspace can have its own API token (different ClickUp accounts)
    clickup_api_token: Mapped[str | None] = mapped_column(Text)
    webhook_id: Mapped[str | None] = mapped_column(String)
    webhook_secret: Mapped[str | None] = mapped_column(Text)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_full_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
