"""add ui_locator_cache project indexes

Revision ID: 8f3c1b2a9d4e
Revises: 2a4e7b9c1d2f
Create Date: 2026-03-11 00:00:01.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8f3c1b2a9d4e"
down_revision: Union[str, Sequence[str], None] = "2a4e7b9c1d2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ui_locator_cache_project_id ON public.ui_locator_cache USING btree (project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ui_locator_cache_project_id_created_at ON public.ui_locator_cache USING btree (project_id, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_ui_locator_cache_project_id_created_at")
    op.execute("DROP INDEX IF EXISTS public.ix_ui_locator_cache_project_id")
