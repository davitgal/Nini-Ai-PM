"""add workspace_id to unified_tasks

Revision ID: d4a848414799
Revises: 69d753fb93ad
Create Date: 2026-04-06 16:03:06.080371

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a848414799'
down_revision: Union[str, None] = '69d753fb93ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# TrueCodeLab workspace UUID (already exists in DB)
TRUECODELLAB_WS_ID = "00000000-0000-0000-0000-000000000010"


def upgrade() -> None:
    # 1. Add nullable column
    op.add_column('unified_tasks', sa.Column('workspace_id', sa.UUID(), nullable=True))
    op.create_index('idx_tasks_workspace', 'unified_tasks', ['workspace_id'], unique=False)
    op.create_foreign_key('fk_tasks_workspace', 'unified_tasks', 'workspaces', ['workspace_id'], ['id'])

    # 2. Backfill all existing tasks → TrueCodeLab workspace
    op.execute(
        f"UPDATE unified_tasks SET workspace_id = '{TRUECODELLAB_WS_ID}' WHERE workspace_id IS NULL"
    )


def downgrade() -> None:
    op.drop_constraint('fk_tasks_workspace', 'unified_tasks', type_='foreignkey')
    op.drop_index('idx_tasks_workspace', table_name='unified_tasks')
    op.drop_column('unified_tasks', 'workspace_id')
