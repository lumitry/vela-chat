"""add token columns to chat_message for analytics

Revision ID: add_tokens_to_chat_message
Revises: add_cost_to_chat_message
Create Date: 2025-11-03 21:23:38.000000

"""

from alembic import op
import sqlalchemy as sa
import json


# revision identifiers, used by Alembic.
revision = 'add_tokens_to_chat_message'
down_revision = 'add_cost_to_chat_message'
branch_labels = None
depends_on = None


def extract_tokens_from_usage(usage_json):
    """
    Extract token counts from usage JSON.
    Returns (input_tokens, output_tokens, reasoning_tokens) tuple.
    """
    if not usage_json or not isinstance(usage_json, dict):
        return (None, None, None)
    
    # Extract input tokens (prompt_tokens)
    input_tokens = None
    if 'prompt_tokens' in usage_json and usage_json['prompt_tokens'] is not None:
        try:
            input_tokens = int(usage_json['prompt_tokens'])
        except (ValueError, TypeError):
            pass
    
    # Extract total output tokens (completion_tokens)
    output_tokens = None
    if 'completion_tokens' in usage_json and usage_json['completion_tokens'] is not None:
        try:
            output_tokens = int(usage_json['completion_tokens'])
        except (ValueError, TypeError):
            pass
    
    # Extract reasoning tokens (completion_tokens_details.reasoning_tokens)
    reasoning_tokens = None
    if 'completion_tokens_details' in usage_json and isinstance(usage_json['completion_tokens_details'], dict):
        details = usage_json['completion_tokens_details']
        if 'reasoning_tokens' in details and details['reasoning_tokens'] is not None:
            try:
                reasoning_tokens = int(details['reasoning_tokens'])
            except (ValueError, TypeError):
                pass
    
    return (input_tokens, output_tokens, reasoning_tokens)


def upgrade() -> None:
    # Add token columns for analytics
    op.add_column('chat_message', sa.Column('input_tokens', sa.Integer(), nullable=True))
    op.add_column('chat_message', sa.Column('output_tokens', sa.Integer(), nullable=True))
    op.add_column('chat_message', sa.Column('reasoning_tokens', sa.Integer(), nullable=True))
    
    # Backfill token values from existing usage JSON
    conn = op.get_bind()
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
                
                input_tokens, output_tokens, reasoning_tokens = extract_tokens_from_usage(usage_json)
                
                # Build update dict with only non-None values
                set_clauses = []
                params = {"msg_id": msg_id}
                if input_tokens is not None:
                    set_clauses.append("input_tokens = :input_tokens")
                    params["input_tokens"] = input_tokens
                if output_tokens is not None:
                    set_clauses.append("output_tokens = :output_tokens")
                    params["output_tokens"] = output_tokens
                if reasoning_tokens is not None:
                    set_clauses.append("reasoning_tokens = :reasoning_tokens")
                    params["reasoning_tokens"] = reasoning_tokens
                
                if set_clauses:
                    conn.execute(sa.text(f"""
                        UPDATE chat_message
                        SET {', '.join(set_clauses)}
                        WHERE id = :msg_id
                    """), params)
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                # Skip invalid JSON
                continue
        
        conn.commit()
    else:
        # PostgreSQL approach: fetch all and update in Python
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
            
            input_tokens, output_tokens, reasoning_tokens = extract_tokens_from_usage(usage_json)
            
            # Build update dict with only non-None values
            set_clauses = []
            params = {"msg_id": msg_id}
            if input_tokens is not None:
                set_clauses.append("input_tokens = :input_tokens")
                params["input_tokens"] = input_tokens
            if output_tokens is not None:
                set_clauses.append("output_tokens = :output_tokens")
                params["output_tokens"] = output_tokens
            if reasoning_tokens is not None:
                set_clauses.append("reasoning_tokens = :reasoning_tokens")
                params["reasoning_tokens"] = reasoning_tokens
            
            if set_clauses:
                conn.execute(sa.text(f"""
                    UPDATE chat_message
                    SET {', '.join(set_clauses)}
                    WHERE id = :msg_id
                """), params)
        
        conn.commit()


def downgrade() -> None:
    op.drop_column('chat_message', 'reasoning_tokens')
    op.drop_column('chat_message', 'output_tokens')
    op.drop_column('chat_message', 'input_tokens')

