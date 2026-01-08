"""add_fetch_and_rank_to_messagetype_enum

Revision ID: 0b68692f4ea0
Revises: 13726d8b54bd
Create Date: 2025-09-29 10:01:22.054057

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0b68692f4ea0'
down_revision = '13726d8b54bd'
branch_labels = None
depends_on = None


def upgrade():
    # MySQL doesn't support ALTER TYPE for enums, so we need to modify the column
    # to add the new enum value 'fetch_and_rank'

    # For MySQL, we need to use raw SQL to alter the enum
    op.execute("""
        ALTER TABLE sqs_message_history
        MODIFY COLUMN message_type
        ENUM('fetch', 'partial_rank', 'full_rank', 'fetch_and_rank')
    """)


def downgrade():
    # Remove 'fetch_and_rank' from the enum by reverting to the original values
    # Note: This will fail if there are any rows with 'fetch_and_rank' value
    op.execute("""
        ALTER TABLE sqs_message_history
        MODIFY COLUMN message_type
        ENUM('fetch', 'partial_rank', 'full_rank')
    """)
