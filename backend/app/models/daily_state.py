"""Daily state model — tracks ritual execution and reminder state per day."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class DailyState(Base, TenantMixin, TimestampMixin):
    """One record per user per day — tracks what rituals ran and how many reminders were sent."""

    __tablename__ = "daily_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Morning ritual (10:30 local)
    morning_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending | done | skipped
    morning_executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    morning_reminder_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    morning_last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Midday ritual (14:00 local)
    midday_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    midday_executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    midday_reminder_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    midday_last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # EOD ritual (21:00 local)
    eod_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    eod_executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eod_reminder_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eod_last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # One state record per user per day
        Index("idx_daily_states_user_date", "user_id", "state_date", unique=True),
    )
