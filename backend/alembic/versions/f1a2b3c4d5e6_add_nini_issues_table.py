"""add_nini_issues_table

Revision ID: f1a2b3c4d5e6
Revises: d8e9f0a1b2c3
Create Date: 2026-04-08 19:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nini_issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("issue_type", sa.String(length=50), server_default="logic", nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="medium", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("source", sa.String(length=30), server_default="nini", nullable=False),
        sa.Column("task_title", sa.String(length=255), nullable=True),
        sa.Column("conversation_snippet", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_nini_issues_user_status", "nini_issues", ["user_id", "status"], unique=False)
    op.create_index("idx_nini_issues_user_severity", "nini_issues", ["user_id", "severity"], unique=False)
    op.create_index("idx_nini_issues_user_created", "nini_issues", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_nini_issues_user_created", table_name="nini_issues")
    op.drop_index("idx_nini_issues_user_severity", table_name="nini_issues")
    op.drop_index("idx_nini_issues_user_status", table_name="nini_issues")
    op.drop_table("nini_issues")
