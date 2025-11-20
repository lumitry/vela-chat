#!/usr/bin/env python3
"""
Script to check full-text search index usage and performance.
Run this to diagnose why full-text search might be slow.
"""

import sys
from pathlib import Path

# Add the backend directory to the path
script_dir = Path(__file__).parent.absolute()
backend_dir = script_dir
sys.path.insert(0, str(backend_dir))

from backend.open_webui.internal.db import get_db
from sqlalchemy import text

def main():
    """Check full-text search setup and performance."""
    print("=" * 60)
    print("Full-Text Search Performance Diagnostics")
    print("=" * 60)
    print()
    
    with get_db() as db:
        # Check if columns exist
        print("1. Checking if full-text search columns exist...")
        result = db.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND (table_name = 'chat' AND column_name = 'title_search')
               OR (table_name = 'chat_message' AND column_name = 'content_text_search')
            ORDER BY table_name, column_name
        """))
        columns = result.fetchall()
        if columns:
            for col in columns:
                print(f"   ✓ Found: {col[0]} ({col[1]})")
        else:
            print("   ✗ Full-text search columns not found!")
            return
        print()
        
        # Check if indexes exist
        print("2. Checking if GIN indexes exist...")
        result = db.execute(text("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND (indexname LIKE '%title_search%' OR indexname LIKE '%content_text_search%')
            ORDER BY indexname
        """))
        indexes = result.fetchall()
        if indexes:
            for idx in indexes:
                print(f"   ✓ Found: {idx[0]}")
                print(f"     {idx[1]}")
        else:
            print("   ✗ GIN indexes not found!")
        print()
        
        # Check table statistics
        print("3. Checking table statistics...")
        result = db.execute(text("""
            SELECT 
                schemaname,
                relname as tablename,
                n_live_tup as row_count,
                last_analyze,
                last_autoanalyze
            FROM pg_stat_user_tables
            WHERE relname IN ('chat', 'chat_message')
            ORDER BY relname
        """))
        stats = result.fetchall()
        for stat in stats:
            print(f"   {stat[1]}: {stat[2]:,} rows")
            if stat[3]:
                print(f"     Last analyzed: {stat[3]}")
            elif stat[4]:
                print(f"     Last auto-analyzed: {stat[4]}")
            else:
                print(f"     ⚠ WARNING: Never analyzed! Run ANALYZE {stat[1]};")
        print()
        
        # Check index usage
        print("4. Checking index sizes...")
        result = db.execute(text("""
            SELECT 
                indexname,
                pg_size_pretty(pg_relation_size(indexname::regclass)) as size
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND (indexname LIKE '%title_search%' OR indexname LIKE '%content_text_search%')
            ORDER BY indexname
        """))
        index_sizes = result.fetchall()
        for idx in index_sizes:
            print(f"   {idx[0]}: {idx[1]}")
        print()
        
        # Test query performance
        print("5. Testing query performance (this may take a moment)...")
        test_query = """
            EXPLAIN ANALYZE
            SELECT chat.id
            FROM chat
            WHERE chat.title_search @@ plainto_tsquery('english', 'test')
               OR EXISTS (
                   SELECT 1
                   FROM chat_message
                   WHERE chat_message.chat_id = chat.id
                     AND chat_message.content_text IS NOT NULL
                     AND chat_message.content_text_search @@ plainto_tsquery('english', 'test')
               )
            LIMIT 10
        """
        result = db.execute(text(test_query))
        explain_output = result.fetchall()
        print("   Query plan:")
        for row in explain_output:
            print(f"   {row[0]}")
        print()
        
        # Recommendations
        print("=" * 60)
        print("Recommendations:")
        print("=" * 60)
        
        # Check if tables need analyzing
        needs_analyze = False
        for stat in stats:
            if not stat[3] and not stat[4]:
                needs_analyze = True
                break
        
        if needs_analyze:
            print("⚠ Run ANALYZE to update statistics:")
            print("   ANALYZE chat;")
            print("   ANALYZE chat_message;")
            print()
        
        # Check if indexes are being used
        if explain_output:
            plan_text = ' '.join([row[0] for row in explain_output])
            if 'Bitmap Index Scan' in plan_text or 'Index Scan' in plan_text:
                print("✓ Indexes appear to be used in query plan")
            else:
                print("⚠ Indexes may not be used - check query plan above")
                print("  Consider running ANALYZE if statistics are stale")
        print()

if __name__ == "__main__":
    main()

