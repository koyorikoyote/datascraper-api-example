"""add has_own_product_service_offer to serp_result

Revision ID: b6f1d2c3a4e5
Revises: c3c7b9a1c2d0
Create Date: 2025-10-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b6f1d2c3a4e5"
down_revision = "c3c7b9a1c2d0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "serp_result",
        sa.Column("has_own_product_service_offer", sa.Boolean(), nullable=True),
    )


def downgrade():
    op.drop_column("serp_result", "has_own_product_service_offer")
