"""add cost column to chat_message for analytics

Revision ID: add_cost_to_chat_message
Revises: add_position_to_chat_message
Create Date: 2025-11-03 21:23:38.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
import json


# revision identifiers, used by Alembic.
revision = 'add_cost_to_chat_message'
down_revision = 'add_position_to_chat_message'
branch_labels = None
depends_on = None


def extract_cost_from_usage(usage_json):
    """Extract cost from usage JSON, matching the same logic as the application."""
    if not usage_json or not isinstance(usage_json, dict):
        return None
    
    # Priority 1: Direct cost field
    if 'cost' in usage_json and usage_json['cost'] is not None:
        try:
            return float(usage_json['cost'])
        except (ValueError, TypeError):
            pass
    
    # Priority 2: Total cost from estimates
    if 'estimates' in usage_json and isinstance(usage_json['estimates'], dict):
        estimates = usage_json['estimates']
        if 'total_cost' in estimates and estimates['total_cost'] is not None:
            try:
                return float(estimates['total_cost'])
            except (ValueError, TypeError):
                pass
    
    # Priority 3: Sum of input and output costs
    if 'estimates' in usage_json and isinstance(usage_json['estimates'], dict):
        estimates = usage_json['estimates']
        input_cost = 0.0
        output_cost = 0.0
        
        if 'input_cost' in estimates and estimates['input_cost'] is not None:
            try:
                input_cost = float(estimates['input_cost'])
            except (ValueError, TypeError):
                pass
        
        if 'output_cost' in estimates and estimates['output_cost'] is not None:
            try:
                output_cost = float(estimates['output_cost'])
            except (ValueError, TypeError):
                pass
        
        if input_cost > 0 or output_cost > 0:
            return input_cost + output_cost
    
    return None


def upgrade() -> None:
    # Add cost column to chat_message table
    # Using DECIMAL(10, 8) to store cost values with high precision (8 decimal places)
    # Check if column already exists (for cases where migration was run manually)
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('chat_message')]
    
    if 'cost' not in columns:
        op.add_column('chat_message', sa.Column('cost', sa.Numeric(precision=10, scale=8), nullable=True))
    
    # Backfill cost values from existing usage JSON
    dialect_name = conn.dialect.name
    
    # Get all messages with usage data
    if dialect_name == 'sqlite':
        # SQLite approach: fetch all and update in Python
        result = conn.execute(sa.text("""
            SELECT id, usage
            FROM chat_message
            WHERE usage IS NOT NULL
        """))
        
        for row in result:
            msg_id, usage_json_str = row
            if not usage_json_str:
                continue
            
            # Parse JSON string
            try:
                if isinstance(usage_json_str, str):
                    usage_json = json.loads(usage_json_str)
                else:
                    usage_json = usage_json_str
                
                cost = extract_cost_from_usage(usage_json)
                if cost is not None:
                    # Convert to Decimal for proper numeric storage
                    from decimal import Decimal
                    cost_decimal = Decimal(str(cost))
                    conn.execute(sa.text("""
                        UPDATE chat_message
                        SET cost = :cost
                        WHERE id = :msg_id
                    """), {"cost": cost_decimal, "msg_id": msg_id})
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                # Skip invalid JSON
                continue
    else:
        # PostgreSQL approach: use JSON operators
        # For PostgreSQL, we can use JSON operators but still need to handle the extraction logic
        # Since we need complex logic, we'll do it in Python
        result = conn.execute(sa.text("""
            SELECT id, usage
            FROM chat_message
            WHERE usage IS NOT NULL
        """))
        
        for row in result:
            msg_id, usage_json = row
            if not usage_json:
                continue
            
            # PostgreSQL returns JSON as dict, SQLite as string
            if isinstance(usage_json, str):
                try:
                    usage_json = json.loads(usage_json)
                except json.JSONDecodeError:
                    continue
            
            cost = extract_cost_from_usage(usage_json)
            if cost is not None:
                # Convert to Decimal for proper numeric storage
                from decimal import Decimal
                cost_decimal = Decimal(str(cost))
                conn.execute(sa.text("""
                    UPDATE chat_message
                    SET cost = :cost
                    WHERE id = :msg_id
                """), {"cost": cost_decimal, "msg_id": msg_id})
    
    # Create index for efficient analytics queries (cost by model_id, cost by chat_id, etc.)
    # Index on (model_id, cost) for aggregations by model
    op.create_index(
        'ix_chat_message_model_cost',
        'chat_message',
        ['model_id', 'cost'],
        unique=False
    )
    
    # Index on (chat_id, cost) for per-chat analytics
    op.create_index(
        'ix_chat_message_chat_cost',
        'chat_message',
        ['chat_id', 'cost'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_chat_message_chat_cost', table_name='chat_message')
    op.drop_index('ix_chat_message_model_cost', table_name='chat_message')
    op.drop_column('chat_message', 'cost')

