"""add full-text search with tsvector and GIN indexes for PostgreSQL

Revision ID: 9f0e_add_fulltext_search
Revises: 9f0d_migrate_base64_images
Create Date: 2025-11-07 20:50:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f0e_add_fulltext_search'
down_revision = '9f0d_migrate_base64_images'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add PostgreSQL full-text search support using tsvector and GIN indexes.
    This migration only applies to PostgreSQL databases.
    """
    conn = op.get_bind()
    dialect_name = conn.dialect.name
    
    if dialect_name != 'postgresql':
        # Skip for SQLite and other databases
        print(f"Skipping full-text search migration for {dialect_name} (PostgreSQL only)")
        return
    
    # 1. Add tsvector columns to chat_message table
    op.execute("""
        ALTER TABLE chat_message 
        ADD COLUMN IF NOT EXISTS content_text_search tsvector
    """)
    
    # 2. Add tsvector column to chat table for title search
    op.execute("""
        ALTER TABLE chat 
        ADD COLUMN IF NOT EXISTS title_search tsvector
    """)
    
    # 3. Create GIN indexes for fast full-text search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_message_content_text_search 
        ON chat_message USING GIN (content_text_search)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_title_search 
        ON chat USING GIN (title_search)
    """)
    
    # 4. Populate tsvector columns with existing data
    # For chat_message: convert content_text to tsvector
    op.execute("""
        UPDATE chat_message 
        SET content_text_search = to_tsvector('english', COALESCE(content_text, ''))
        WHERE content_text_search IS NULL
    """)
    
    # For chat: convert title to tsvector
    op.execute("""
        UPDATE chat 
        SET title_search = to_tsvector('english', COALESCE(title, ''))
        WHERE title_search IS NULL
    """)
    
    # 5. Create triggers to automatically update tsvector columns
    # Trigger function for chat_message
    op.execute("""
        CREATE OR REPLACE FUNCTION update_chat_message_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.content_text_search := to_tsvector('english', COALESCE(NEW.content_text, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        DROP TRIGGER IF EXISTS trigger_chat_message_search_vector ON chat_message;
        CREATE TRIGGER trigger_chat_message_search_vector
        BEFORE INSERT OR UPDATE OF content_text ON chat_message
        FOR EACH ROW
        EXECUTE FUNCTION update_chat_message_search_vector();
    """)
    
    # Trigger function for chat title
    op.execute("""
        CREATE OR REPLACE FUNCTION update_chat_title_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.title_search := to_tsvector('english', COALESCE(NEW.title, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        DROP TRIGGER IF EXISTS trigger_chat_title_search_vector ON chat;
        CREATE TRIGGER trigger_chat_title_search_vector
        BEFORE INSERT OR UPDATE OF title ON chat
        FOR EACH ROW
        EXECUTE FUNCTION update_chat_title_search_vector();
    """)
    
    # Analyze tables to update statistics for query planner
    # This is critical for the query planner to use the GIN indexes effectively
    op.execute("ANALYZE chat")
    op.execute("ANALYZE chat_message")
    
    print("Full-text search migration complete for PostgreSQL")


def downgrade() -> None:
    """
    Remove full-text search support.
    """
    conn = op.get_bind()
    dialect_name = conn.dialect.name
    
    if dialect_name != 'postgresql':
        return
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trigger_chat_message_search_vector ON chat_message")
    op.execute("DROP TRIGGER IF EXISTS trigger_chat_title_search_vector ON chat")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS update_chat_message_search_vector()")
    op.execute("DROP FUNCTION IF EXISTS update_chat_title_search_vector()")
    
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_chat_message_content_text_search")
    op.execute("DROP INDEX IF EXISTS idx_chat_title_search")
    
    # Drop columns
    op.execute("ALTER TABLE chat_message DROP COLUMN IF EXISTS content_text_search")
    op.execute("ALTER TABLE chat DROP COLUMN IF EXISTS title_search")

