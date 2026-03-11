"""add api_usage user indexes

Revision ID: 2a4e7b9c1d2f
Revises: 03cb3994f22a
Create Date: 2026-03-11 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2a4e7b9c1d2f"
down_revision: Union[str, Sequence[str], None] = "03cb3994f22a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_api_usage_user_id ON public.api_usage USING btree (user_id)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_api_usage_user_id_request_time ON public.api_usage USING btree (user_id, request_time)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_api_usage_project_id ON public.api_usage USING btree (project_id)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_api_usage_project_id_request_time ON public.api_usage USING btree (project_id, request_time)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS public.ix_api_usage_project_id_request_time"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS public.ix_api_usage_project_id")
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS public.ix_api_usage_user_id_request_time"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS public.ix_api_usage_user_id")
