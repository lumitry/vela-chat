"""remove message history from chat JSON blobs

Revision ID: remove_chat_message_history
Revises: add_embedding_metrics_tracking
Create Date: 2025-11-16 15:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String, JSON

import json


# revision identifiers, used by Alembic.
revision = 'remove_chat_message_history'
down_revision = 'add_embedding_metrics_tracking'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Remove message history from chat JSON blobs.
    
    This migration removes:
    - history.messages (the object containing message data)
    - messages (the array of messages)
    
    Everything else in the chat JSON blob is preserved, including:
    - history.currentId and other history properties
    - params
    - files
    - Any other metadata
    """
    conn = op.get_bind()
    
    chat_table = table(
        'chat',
        column('id', String),
        column('chat', JSON),
    )
    
    # Fetch all chats with their JSON blobs
    rows = conn.execute(sa.select(chat_table.c.id, chat_table.c.chat)).fetchall()
    
    updated_count = 0
    skipped_count = 0
    skipped_null = 0
    skipped_no_messages = 0
    skipped_not_dict = 0
    error_count = 0
    
    for row in rows:
        chat_id = row.id
        chat_json = row.chat
        
        if not chat_json:
            skipped_count += 1
            skipped_null += 1
            continue
        
        # Normalize chat_json type (handle string JSON)
        if isinstance(chat_json, str):
            try:
                chat_json = json.loads(chat_json)
            except Exception as e:
                print(f"Error parsing JSON for chat {chat_id}: {e}")
                error_count += 1
                continue
        
        if not isinstance(chat_json, dict):
            skipped_count += 1
            skipped_not_dict += 1
            continue
        
        # Track if we made any changes
        updated = False
        
        # Remove history.messages if it exists
        if 'history' in chat_json and isinstance(chat_json['history'], dict):
            if 'messages' in chat_json['history']:
                del chat_json['history']['messages']
                updated = True
        
        # Remove messages array if it exists
        if 'messages' in chat_json:
            del chat_json['messages']
            updated = True
        
        # Only update if we made changes
        if updated:
            try:
                conn.execute(
                    sa.update(chat_table)
                    .where(chat_table.c.id == chat_id)
                    .values(chat=chat_json)
                )
                updated_count += 1
            except Exception as e:
                print(f"Error updating chat {chat_id}: {e}")
                error_count += 1
        else:
            # Chat had no message data to remove (already normalized)
            skipped_count += 1
            skipped_no_messages += 1
    
    print("Migration complete:")
    print(f"  Updated: {updated_count} chats (removed message history)")
    print(f"  Skipped: {skipped_count} chats total")
    print(f"    - Already normalized (no messages): {skipped_no_messages}")
    print(f"    - NULL/empty chat JSON: {skipped_null}")
    print(f"    - Not a dict: {skipped_not_dict}")
    print(f"  Errors: {error_count} chats")
    
    # Important: Reclaim disk space after UPDATE operations
    # PostgreSQL doesn't automatically reclaim space after UPDATEs - old versions remain until VACUUM
    # VACUUM cannot run inside a transaction, so it must be run manually after the migration
    dialect_name = conn.dialect.name
    if dialect_name == 'postgresql':
        print("\n" + "="*70)
        print("IMPORTANT: Run VACUUM ANALYZE to reclaim disk space")
        print("="*70)
        print("PostgreSQL doesn't automatically reclaim space after UPDATE operations.")
        print("The old data is still on disk until you run VACUUM.")
        print("\nRun this command manually after the migration completes:")
        print("  VACUUM ANALYZE chat;")
        print("\n⚠️  Note: Regular VACUUM may not reclaim all space from large JSON columns.")
        print("   For maximum space reclamation (especially TOAST storage), use:")
        print("   VACUUM FULL chat;")
        print("   (WARNING: VACUUM FULL requires an exclusive lock and rewrites the table)")
        print("\nTo check actual space usage breakdown:")
        print("  SELECT pg_size_pretty(pg_total_relation_size('chat')) AS total,")
        print("         pg_size_pretty(pg_relation_size('chat')) AS table,")
        print("         pg_size_pretty(pg_total_relation_size('chat') - pg_relation_size('chat')) AS indexes,")
        print("         pg_size_pretty((SELECT SUM(pg_total_relation_size(oid))")
        print("                        FROM pg_class WHERE reltoastrelid = 'chat'::regclass)) AS toast;")
        print("="*70)
    elif dialect_name == 'sqlite':
        print("\nNote: For SQLite, you may want to run VACUUM manually to reclaim space.")
        print("SQLite VACUUM requires exclusive access to the database.")


def downgrade() -> None:
    """
    Downgrade is not possible as we've destroyed the message history.
    The message data has been removed and cannot be restored from the chat JSON blobs.
    However, if messages were migrated to the normalized chat_message table,
    they can be restored from there if needed.
    """
    print("Downgrade not supported: Message history has been removed from chat JSON blobs.")
    print("If messages were migrated to the chat_message table, they can be restored from there.")

