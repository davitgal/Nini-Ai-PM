"""add_daily_state_and_context_tables

Revision ID: b1c2d3e4f5a6
Revises: a3f9e1b2c7d0
Create Date: 2026-04-07 13:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a3f9e1b2c7d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- daily_states ---
    op.create_table(
        "daily_states",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("state_date", sa.Date(), nullable=False),
        # Morning
        sa.Column("morning_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("morning_executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("morning_reminder_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("morning_last_reminder_at", sa.DateTime(timezone=True), nullable=True),
        # Midday
        sa.Column("midday_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("midday_executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("midday_reminder_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("midday_last_reminder_at", sa.DateTime(timezone=True), nullable=True),
        # EOD
        sa.Column("eod_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("eod_executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eod_reminder_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("eod_last_reminder_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_daily_states_user_date",
        "daily_states",
        ["user_id", "state_date"],
        unique=True,
    )

    # --- daily_contexts ---
    op.create_table(
        "daily_contexts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("context_date", sa.Date(), nullable=False),
        sa.Column("user_last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_active_today", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("interaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interactions", JSONB(), nullable=False, server_default="[]"),
        sa.Column("current_risks", JSONB(), nullable=False, server_default="[]"),
        sa.Column("goals", JSONB(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_daily_contexts_user_date",
        "daily_contexts",
        ["user_id", "context_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_daily_contexts_user_date", table_name="daily_contexts")
    op.drop_table("daily_contexts")
    op.drop_index("idx_daily_states_user_date", table_name="daily_states")
    op.drop_table("daily_states")
