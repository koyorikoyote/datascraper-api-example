"""add_partial_rank_status_to_keyword

Revision ID: a12b3c4d5e6f
Revises: e7df60fdd4f7
Create Date: 2025-10-03 10:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a12b3c4d5e6f'
down_revision = 'e7df60fdd4f7'
branch_labels = None
depends_on = None


def upgrade():
    # Guard against adding the column if it already exists
    bind = op.get_bind()
    insp = sa.inspect(bind)

    existing_columns = [col["name"] for col in insp.get_columns("keyword")]
    if "partial_rank_status" not in existing_columns:
        op.add_column(
            "keyword",
            sa.Column(
                "partial_rank_status",
                sa.String(length=20),
                nullable=True,
                server_default=sa.text("'pending'"),
            ),
        )
    # ### end Alembic commands ###


def downgrade():
    # Drop the column only if it exists
    bind = op.get_bind()
    insp = sa.inspect(bind)

    existing_columns = [col["name"] for col in insp.get_columns("keyword")]
    if "partial_rank_status" in existing_columns:
        op.drop_column("keyword", "partial_rank_status")
    # ### end Alembic commands ###
