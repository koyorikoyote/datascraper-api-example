"""add_sqs_message_history_table

Revision ID: 13726d8b54bd
Revises: 55813b41ffe3
Create Date: 2025-09-29 14:49:56.520116

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '13726d8b54bd'
down_revision = '55813b41ffe3'
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types first
    message_status_enum = sa.Enum('queued', 'processing', 'completed', 'failed', 'dlq', 'deleted', name='messagestatus')
    message_type_enum = sa.Enum('fetch', 'partial_rank', 'full_rank', name='messagetype')

    # Create the sqs_message_history table
    op.create_table('sqs_message_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),

        # SQS Message identifiers
        sa.Column('sqs_message_id', sa.String(255), nullable=False),
        sa.Column('job_id', sa.String(255), nullable=True),

        # Message details
        sa.Column('message_type', message_type_enum, nullable=True),
        sa.Column('keyword_ids', sa.JSON(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('user_full_name', sa.String(100), nullable=True),

        # Processing details
        sa.Column('status', message_status_enum, nullable=False, server_default='queued'),
        sa.Column('retry_count', sa.Integer(), server_default='0'),

        # Error tracking
        sa.Column('error_details', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),

        # Timestamps
        sa.Column('queued_at', sa.DateTime(), nullable=True),
        sa.Column('started_processing_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),

        # Additional metadata
        sa.Column('queue_name', sa.String(100), nullable=True),
        sa.Column('receipt_handle', sa.Text(), nullable=True),
        sa.Column('visibility_timeout', sa.Integer(), nullable=True),
        sa.Column('receive_count', sa.Integer(), server_default='0'),

        # Full message data
        sa.Column('message_body', sa.JSON(), nullable=True),
        sa.Column('message_attributes', sa.JSON(), nullable=True),

        # Audit fields
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),

        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_sqs_message_history_sqs_message_id', 'sqs_message_history', ['sqs_message_id'])
    op.create_index('ix_sqs_message_history_job_id', 'sqs_message_history', ['job_id'])
    op.create_index('ix_sqs_message_history_user_id', 'sqs_message_history', ['user_id'])
    op.create_index('ix_sqs_message_history_status', 'sqs_message_history', ['status'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_sqs_message_history_status', table_name='sqs_message_history')
    op.drop_index('ix_sqs_message_history_user_id', table_name='sqs_message_history')
    op.drop_index('ix_sqs_message_history_job_id', table_name='sqs_message_history')
    op.drop_index('ix_sqs_message_history_sqs_message_id', table_name='sqs_message_history')

    # Drop table
    op.drop_table('sqs_message_history')

    # Drop enum types
    sa.Enum(name='messagestatus').drop(op.get_bind())
    sa.Enum(name='messagetype').drop(op.get_bind())
