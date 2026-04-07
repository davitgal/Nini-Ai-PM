"""add_daily_plans_table

Revision ID: a3f9e1b2c7d0
Revises: 714780a6cd43
Create Date: 2026-04-07 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "a3f9e1b2c7d0"
down_revision: Union[str, None] = "714780a6cd43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("plan_type", sa.String(20), nullable=False),
        sa.Column("must_do", JSONB(), nullable=False, server_default="[]"),
        sa.Column("should_do", JSONB(), nullable=False, server_default="[]"),
        sa.Column("can_wait", JSONB(), nullable=False, server_default="[]"),
        sa.Column("blocked", JSONB(), nullable=False, server_default="[]"),
        sa.Column("deferred", JSONB(), nullable=False, server_default="[]"),
        sa.Column("completed", JSONB(), nullable=False, server_default="[]"),
        sa.Column("risks", JSONB(), nullable=False, server_default="[]"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("sent_to_user", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("job_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("job_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("job_status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("affected_tasks_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_daily_plans_user_date", "daily_plans", ["user_id", "plan_date"])
    op.create_index(
        "idx_daily_plans_user_date_type",
        "daily_plans",
        ["user_id", "plan_date", "plan_type"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_daily_plans_user_date_type", table_name="daily_plans")
    op.drop_index("idx_daily_plans_user_date", table_name="daily_plans")
    op.drop_table("daily_plans")
