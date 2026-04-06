import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin

SyncDirection = Enum("inbound", "outbound", "full_sync", name="sync_direction_enum")
SyncStatus = Enum("success", "failed", "skipped", "conflict", name="sync_status_enum")


class SyncLog(TenantMixin, Base):
    __tablename__ = "sync_log"
    __table_args__ = (
        Index("idx_sync_log_idempotency", "payload_hash"),
        Index("idx_sync_log_user_time", "user_id", "created_at"),
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
    direction: Mapped[str] = mapped_column(SyncDirection, nullable=False)
    event_type: Mapped[str | None] = mapped_column(String)
    clickup_task_id: Mapped[str | None] = mapped_column(String)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("unified_tasks.id")
    )
    status: Mapped[str] = mapped_column(SyncStatus, nullable=False)
    payload_hash: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
