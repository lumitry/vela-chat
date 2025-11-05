"""init chat messages tables

Revision ID: 9f0a_chat_messages_init
Revises: 
Create Date: 2025-11-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f0a_chat_messages_init'
down_revision = '3781e22d8b01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'chat_message',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('chat_id', sa.String(), index=True, nullable=False),
        sa.Column('parent_id', sa.String(), index=True, nullable=True),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('model_id', sa.Text(), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('content_json', sa.JSON(), nullable=True),
        sa.Column('status', sa.JSON(), nullable=True),
        sa.Column('usage', sa.JSON(), nullable=True),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.Column('annotation', sa.JSON(), nullable=True),  # Feedback/evaluation annotation
        sa.Column('feedback_id', sa.String(), nullable=True),  # Feedback ID
        sa.Column('selected_model_id', sa.Text(), nullable=True),  # Selected model for arena mode
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
    )
    op.create_index('ix_chat_message_chat_parent', 'chat_message', ['chat_id', 'parent_id'])
    op.create_index('ix_chat_message_chat_created', 'chat_message', ['chat_id', 'created_at'])

    op.create_table(
        'chat_message_attachment',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('message_id', sa.String(), sa.ForeignKey('chat_message.id', ondelete='CASCADE'), index=True),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('file_id', sa.String(), nullable=True),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('mime_type', sa.Text(), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('chat_message_attachment')
    op.drop_index('ix_chat_message_chat_created', table_name='chat_message')
    op.drop_index('ix_chat_message_chat_parent', table_name='chat_message')
    op.drop_table('chat_message')


