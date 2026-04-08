import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class NiniIssue(TenantMixin, TimestampMixin, Base):
    """Backlog item for Nini behavior issues and product gaps."""

    __tablename__ = "nini_issues"
    __table_args__ = (
        Index("idx_nini_issues_user_status", "user_id", "status"),
        Index("idx_nini_issues_user_severity", "user_id", "severity"),
        Index("idx_nini_issues_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, server_default="", nullable=False)

    # categorization
    issue_type: Mapped[str] = mapped_column(String(50), server_default="logic", nullable=False)
    severity: Mapped[str] = mapped_column(String(20), server_default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="open", nullable=False)
    source: Mapped[str] = mapped_column(String(30), server_default="nini", nullable=False)

    # optional context for faster triage
    task_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    conversation_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, server_default="{}", nullable=False)

    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
