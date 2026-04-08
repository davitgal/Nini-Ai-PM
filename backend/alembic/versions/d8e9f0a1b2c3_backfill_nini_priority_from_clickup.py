"""backfill_nini_priority_from_clickup

Revision ID: d8e9f0a1b2c3
Revises: c7f3a2b1d9e8
Create Date: 2026-04-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, None] = "c7f3a2b1d9e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Map clickup_priority (1=urgent→critical, 2=high, 3=normal→medium, 4=low)
    # to nini_priority for all existing tasks that still have default "none"
    op.execute("""
        UPDATE unified_tasks
        SET nini_priority = (CASE clickup_priority
            WHEN 1 THEN 'critical'
            WHEN 2 THEN 'high'
            WHEN 3 THEN 'medium'
            WHEN 4 THEN 'low'
            ELSE 'none'
        END)::nini_priority
        WHERE nini_priority = 'none'::nini_priority
          AND clickup_priority IS NOT NULL
    """)


def downgrade() -> None:
    # Can't reliably undo — leave as-is
    pass
