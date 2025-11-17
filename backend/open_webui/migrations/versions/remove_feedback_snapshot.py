"""remove snapshot column from feedback table

Revision ID: remove_feedback_snapshot
Revises: remove_chat_message_history
Create Date: 2025-11-16 20:48:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_feedback_snapshot'
down_revision = 'remove_chat_message_history'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Remove the snapshot column from the feedback table.
    
    The snapshot column stored redundant chat history that is already
    available in the chats table. This migration removes the column
    to reduce database bloat.
    """
    op.drop_column('feedback', 'snapshot')


def downgrade() -> None:
    """
    Restore the snapshot column to the feedback table.
    
    Note: This will restore the column structure but will not restore
    any previously stored snapshot data.
    """
    op.add_column(
        'feedback',
        sa.Column('snapshot', sa.JSON(), nullable=True)
    )

