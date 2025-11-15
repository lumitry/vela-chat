"""add embedding metrics tracking

Revision ID: add_embedding_metrics_tracking
Revises: exclude_imported_chats_metrics
Create Date: 2025-11-14 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'add_embedding_metrics_tracking'
down_revision = 'exclude_imported_chats_metrics'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create embedding_generation and embedding_metrics_daily_rollup tables
    for tracking embedding costs and usage.
    """
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    # Create embedding_generation table
    op.create_table(
        'embedding_generation',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('chat_id', sa.String(), nullable=True),
        sa.Column('message_id', sa.String(), nullable=True),
        sa.Column('knowledge_base_id', sa.String(), nullable=True),
        sa.Column('embedding_type', sa.Text(), nullable=False),
        sa.Column('embedding_model_type', sa.Text(), nullable=False),
        sa.Column('model_id', sa.Text(), nullable=False),
        sa.Column('embedding_engine', sa.Text(), nullable=False),
        sa.Column('total_input_tokens', sa.Integer(), nullable=True),
        sa.Column('cost', sa.Numeric(precision=10, scale=8), nullable=True),
        sa.Column('usage', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
    )

    # Create indexes for embedding_generation
    op.create_index('ix_embedding_generation_user_id',
                    'embedding_generation', ['user_id'])
    op.create_index('ix_embedding_generation_chat_id',
                    'embedding_generation', ['chat_id'])
    op.create_index('ix_embedding_generation_message_id',
                    'embedding_generation', ['message_id'])
    op.create_index('ix_embedding_generation_knowledge_base_id',
                    'embedding_generation', ['knowledge_base_id'])
    op.create_index('ix_embedding_generation_embedding_type',
                    'embedding_generation', ['embedding_type'])
    op.create_index('ix_embedding_generation_model_id',
                    'embedding_generation', ['model_id'])
    op.create_index('ix_embedding_generation_user_created',
                    'embedding_generation', ['user_id', 'created_at'])
    op.create_index('ix_embedding_generation_chat_message',
                    'embedding_generation', ['chat_id', 'message_id'])
    op.create_index('ix_embedding_generation_type_created',
                    'embedding_generation', ['embedding_type', 'created_at'])

    # Create embedding_metrics_daily_rollup table
    op.create_table(
        'embedding_metrics_daily_rollup',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('embedding_type', sa.Text(), nullable=False),
        sa.Column('embedding_model_type', sa.Text(), nullable=False),
        sa.Column('model_id', sa.Text(), nullable=False),
        sa.Column('task_count', sa.Integer(),
                  nullable=False, server_default='0'),
        sa.Column('total_cost', sa.Numeric(precision=10, scale=8),
                  nullable=False, server_default='0'),
        sa.Column('total_input_tokens', sa.Integer(),
                  nullable=False, server_default='0'),
        sa.Column('distinct_chat_count', sa.Integer(),
                  nullable=False, server_default='0'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
    )

    # Create indexes for embedding_metrics_daily_rollup
    op.create_index('ix_embedding_metrics_rollup_user_id',
                    'embedding_metrics_daily_rollup', ['user_id'])
    op.create_index('ix_embedding_metrics_rollup_date',
                    'embedding_metrics_daily_rollup', ['date'])
    op.create_index('ix_embedding_metrics_rollup_embedding_type',
                    'embedding_metrics_daily_rollup', ['embedding_type'])
    op.create_index('ix_embedding_metrics_rollup_model_id',
                    'embedding_metrics_daily_rollup', ['model_id'])
    op.create_index('ix_embedding_metrics_rollup_user_date',
                    'embedding_metrics_daily_rollup', ['user_id', 'date'])
    op.create_index('ix_embedding_metrics_rollup_user_model_date',
                    'embedding_metrics_daily_rollup', ['user_id', 'model_id', 'date'])

    # Create unique constraint
    op.create_unique_constraint(
        'uq_embedding_metrics_rollup_unique',
        'embedding_metrics_daily_rollup',
        ['user_id', 'date', 'embedding_type', 'model_id', 'embedding_model_type']
    )


def downgrade() -> None:
    """Drop embedding metrics tracking tables"""
    op.drop_table('embedding_metrics_daily_rollup')
    op.drop_table('embedding_generation')
