"""add project router supporting indexes

Revision ID: 5c1a7e3d9b20
Revises: 8f3c1b2a9d4e
Create Date: 2026-03-11 00:00:02.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "5c1a7e3d9b20"
down_revision: Union[str, Sequence[str], None] = "8f3c1b2a9d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_api_usage_project_id_status_code_request_time ON public.api_usage USING btree (project_id, status_code, request_time)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_project_memberships_user_id_project_id ON public.project_memberships USING btree (user_id, project_id)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_project_memberships_project_id_user_id ON public.project_memberships USING btree (project_id, user_id)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_project_invites_project_id ON public.project_invites USING btree (project_id)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_project_invites_project_id_email ON public.project_invites USING btree (project_id, email)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_project_invites_email_accepted ON public.project_invites USING btree (email, accepted)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS public.ix_project_invites_email_accepted"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS public.ix_project_invites_project_id_email"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS public.ix_project_invites_project_id"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS public.ix_project_memberships_project_id_user_id"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS public.ix_project_memberships_user_id_project_id"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS public.ix_api_usage_project_id_status_code_request_time"
        )
