"""add industry-related fields to serp_result

Revision ID: 9c8b7a6d5e4f
Revises: a12b3c4d5e6f
Create Date: 2025-10-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c8b7a6d5e4f"
down_revision = "a12b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns introduced by Rank GPT prompt updates
    op.add_column(
        "serp_result",
        sa.Column("has_column_section", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "serp_result",
        sa.Column("industry", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "serp_result",
        sa.Column("industry_confidence", sa.SmallInteger(), nullable=True),
    )


def downgrade():
    # Remove newly added columns
    op.drop_column("serp_result", "industry_confidence")
    op.drop_column("serp_result", "industry")
    op.drop_column("serp_result", "has_column_section")
