"""add position column to chat_message for sibling ordering

Revision ID: add_position_to_chat_message
Revises: 9f0b_backfill_chat_messages
Create Date: 2025-01-15 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_position_to_chat_message'
down_revision = '9f0b_backfill_chat_messages'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add position column to chat_message table
    op.add_column('chat_message', sa.Column('position', sa.Integer(), nullable=True, server_default='0'))
    
    # Backfill position values based on created_at ordering for existing messages
    # For each (chat_id, parent_id) group, assign positions 0, 1, 2, ... based on creation order
    conn = op.get_bind()
    dialect_name = conn.dialect.name
    
    # Get all unique (chat_id, parent_id) combinations
    if dialect_name == 'sqlite':
        # SQLite doesn't support ROW_NUMBER() with UPDATE...FROM
        # We'll use a Python-side approach
        result = conn.execute(sa.text("""
            SELECT DISTINCT chat_id, COALESCE(parent_id, 'NULL') as parent_id_key
            FROM chat_message
        """))
        
        for row in result:
            chat_id, parent_id_key = row
            parent_id = None if parent_id_key == 'NULL' else parent_id_key
            
            # Get all messages for this group, ordered by created_at
            if parent_id:
                messages = conn.execute(sa.text("""
                    SELECT id FROM chat_message
                    WHERE chat_id = :chat_id AND parent_id = :parent_id
                    ORDER BY created_at ASC
                """), {"chat_id": chat_id, "parent_id": parent_id}).fetchall()
            else:
                messages = conn.execute(sa.text("""
                    SELECT id FROM chat_message
                    WHERE chat_id = :chat_id AND parent_id IS NULL
                    ORDER BY created_at ASC
                """), {"chat_id": chat_id}).fetchall()
            
            # Update position for each message
            for idx, msg_row in enumerate(messages):
                msg_id = msg_row[0] if isinstance(msg_row, (tuple, list)) else msg_row
                conn.execute(sa.text("""
                    UPDATE chat_message
                    SET position = :position
                    WHERE id = :msg_id
                """), {"position": idx, "msg_id": msg_id})
    else:
        # PostgreSQL and other databases that support ROW_NUMBER() with UPDATE...FROM
        result = conn.execute(sa.text("""
            SELECT DISTINCT chat_id, parent_id
            FROM chat_message
        """))
        
        for row in result:
            chat_id, parent_id = row
            
            # Update positions for this group, ordered by created_at
            if parent_id:
                conn.execute(sa.text("""
                    UPDATE chat_message
                    SET position = subquery.row_num - 1
                    FROM (
                        SELECT id, ROW_NUMBER() OVER (ORDER BY created_at ASC) as row_num
                        FROM chat_message
                        WHERE chat_id = :chat_id AND parent_id = :parent_id
                    ) AS subquery
                    WHERE chat_message.id = subquery.id
                """), {"chat_id": chat_id, "parent_id": parent_id})
            else:
                # For root messages (parent_id IS NULL)
                conn.execute(sa.text("""
                    UPDATE chat_message
                    SET position = subquery.row_num - 1
                    FROM (
                        SELECT id, ROW_NUMBER() OVER (ORDER BY created_at ASC) as row_num
                        FROM chat_message
                        WHERE chat_id = :chat_id AND parent_id IS NULL
                    ) AS subquery
                    WHERE chat_message.id = subquery.id
                """), {"chat_id": chat_id})
    
    # Create index for efficient sibling queries
    op.create_index(
        'ix_chat_message_chat_parent_position',
        'chat_message',
        ['chat_id', 'parent_id', 'position']
    )


def downgrade() -> None:
    op.drop_index('ix_chat_message_chat_parent_position', table_name='chat_message')
    op.drop_column('chat_message', 'position')

