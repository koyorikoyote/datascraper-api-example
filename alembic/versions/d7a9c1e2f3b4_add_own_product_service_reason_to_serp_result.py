"""add own_product_service_determination_reason to serp_result

Revision ID: d7a9c1e2f3b4
Revises: b6f1d2c3a4e5
Create Date: 2025-11-06 01:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d7a9c1e2f3b4"
down_revision = "b6f1d2c3a4e5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "serp_result",
        sa.Column("own_product_service_determination_reason", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("serp_result", "own_product_service_determination_reason")
