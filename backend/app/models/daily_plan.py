"""Daily plan and EOD report model for proactive AI scheduling."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class DailyPlan(Base, TenantMixin, TimestampMixin):
    """Stores morning plans, midday replans, and EOD reports."""

    __tablename__ = "daily_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    # morning | midday | eod
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Structured task lists — list of compact task dicts
    must_do: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    should_do: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    can_wait: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    blocked: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    deferred: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    completed: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    risks: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")

    # User-facing Telegram message (HTML)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_to_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Job execution metadata
    job_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job_status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    affected_tasks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_daily_plans_user_date", "user_id", "plan_date"),
        # One record per (user, date, type)
        Index("idx_daily_plans_user_date_type", "user_id", "plan_date", "plan_type", unique=True),
    )
