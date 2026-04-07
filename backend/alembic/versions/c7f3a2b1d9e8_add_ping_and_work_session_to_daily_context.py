"""add_ping_and_work_session_to_daily_context

Revision ID: c7f3a2b1d9e8
Revises: b1c2d3e4f5a6
Create Date: 2026-04-07 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c7f3a2b1d9e8"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Proactive ping tracking
    op.add_column(
        "daily_contexts",
        sa.Column("last_ping_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "daily_contexts",
        sa.Column("ping_count", sa.Integer(), nullable=False, server_default="0"),
    )
    # Current work session: {task_title, estimate_min, started_at, mid_checked, result_asked}
    op.add_column(
        "daily_contexts",
        sa.Column("work_session", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("daily_contexts", "work_session")
    op.drop_column("daily_contexts", "ping_count")
    op.drop_column("daily_contexts", "last_ping_at")
