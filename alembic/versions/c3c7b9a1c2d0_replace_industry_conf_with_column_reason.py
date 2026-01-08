"""replace industry_confidence with column_determination_reason

Revision ID: c3c7b9a1c2d0
Revises: 9c8b7a6d5e4f
Create Date: 2025-10-21 01:56:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3c7b9a1c2d0'
down_revision = '9c8b7a6d5e4f'
branch_labels = None
depends_on = None


def upgrade():
    # Add new column for column determination reason
    op.add_column('serp_result', sa.Column('column_determination_reason', sa.Text(), nullable=True))
    # Drop old confidence column
    with op.batch_alter_table('serp_result') as batch_op:
        try:
            batch_op.drop_column('industry_confidence')
        except Exception:
            # Column may already be absent in some environments
            pass


def downgrade():
    # Recreate old column
    op.add_column('serp_result', sa.Column('industry_confidence', sa.SmallInteger(), nullable=True))
    # Drop the new reason column
    with op.batch_alter_table('serp_result') as batch_op:
        try:
            batch_op.drop_column('column_determination_reason')
        except Exception:
            pass
