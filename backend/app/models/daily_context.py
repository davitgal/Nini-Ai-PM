"""Daily context model — tracks user activity and interaction history for the current day."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class DailyContext(Base, TenantMixin, TimestampMixin):
    """One record per user per day — evolving context used for adaptive decision-making.

    Tracks:
    - When the user was last active (for smart interruption decisions)
    - What interactions happened today (type, tone, summary)
    - Current risks surfaced during the day
    - Goals for the day (extracted from morning plan)
    """

    __tablename__ = "daily_contexts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    context_date: Mapped[date] = mapped_column(Date, nullable=False)

    # User activity
    user_last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_active_today: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Interaction history: list of {type, category, timestamp, summary, tone}
    # type: "user_message" | "ritual" | "reminder"
    # category: "command" | "free_text" | "morning" | "midday" | "eod"
    # tone: "soft" | "neutral" | "assertive" | "casual"
    interactions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")

    # Current risks extracted from plans (updated each ritual)
    current_risks: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")

    # Goals for today (from morning plan)
    goals: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")

    # Free-form AI notes about the day (optional context for future prompts)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # One context record per user per day
        Index("idx_daily_contexts_user_date", "user_id", "context_date", unique=True),
    )
