"""add projects api_call_count cache

Revision ID: 9d2a4b6e1c11
Revises: 5c1a7e3d9b20
Create Date: 2026-03-11 11:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d2a4b6e1c11"
down_revision: Union[str, Sequence[str], None] = "5c1a7e3d9b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "api_call_count", sa.BigInteger(), nullable=False, server_default="0"
        ),
    )
    op.execute(
        """
        UPDATE projects p
        SET api_call_count = usage_counts.call_count
        FROM (
            SELECT project_id, COUNT(*)::bigint AS call_count
            FROM api_usage
            WHERE project_id IS NOT NULL AND status_code = 200
            GROUP BY project_id
        ) AS usage_counts
        WHERE p.id = usage_counts.project_id
        """
    )
    op.alter_column("projects", "api_call_count", server_default=None)


def downgrade() -> None:
    op.drop_column("projects", "api_call_count")
