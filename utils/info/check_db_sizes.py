#!/usr/bin/env python3
"""
Script to check PostgreSQL database table sizes, with detailed breakdown.
Shows total size, table size, index size, and row counts for all tables.
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_database_url():
    """Get database URL from environment or docker-compose.yaml"""
    # Try environment variable first
    db_url = os.environ.get("DATABASE_URL")
    
    if db_url:
        # Replace postgres:// with postgresql:// if needed
        if "postgres://" in db_url:
            db_url = db_url.replace("postgres://", "postgresql://")
        return db_url
    
    # Fallback: try to read from docker-compose.yaml
    try:
        import yaml
        with open("docker-compose.yaml", "r") as f:
            compose = yaml.safe_load(f)
            env_vars = compose.get("services", {}).get("open-webui", {}).get("environment", [])
            for env_var in env_vars:
                if env_var.startswith("DATABASE_URL="):
                    db_url = env_var.split("=", 1)[1]
                    if "postgres://" in db_url:
                        db_url = db_url.replace("postgres://", "postgresql://")
                    return db_url
    except Exception as e:
        print(f"Warning: Could not read docker-compose.yaml: {e}", file=sys.stderr)
    
    return "postgresql://user:password@localhost:5432/velachat"


def format_bytes(bytes_value):
    """Format bytes to human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


def get_table_sizes(engine: Engine):
    """Get sizes for all tables"""
    with engine.connect() as conn:
        # Query to get all table sizes
        query = text("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
                pg_total_relation_size(schemaname||'.'||tablename) AS total_size_bytes,
                pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
                pg_relation_size(schemaname||'.'||tablename) AS table_size_bytes,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS indexes_size,
                (pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS indexes_size_bytes
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
        """)
        
        result = conn.execute(query)
        return result.fetchall()


def get_row_counts(engine: Engine, table_name: str):
    """Get row count for a specific table"""
    with engine.connect() as conn:
        query = text(f"SELECT COUNT(*) FROM {table_name}")
        result = conn.execute(query)
        return result.scalar()


def get_table_details(engine: Engine, table_name: str):
    """Get detailed information about a specific table"""
    with engine.connect() as conn:
        # Get column information
        columns_query = text("""
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table_name
            ORDER BY ordinal_position;
        """)
        
        columns = conn.execute(columns_query, {"table_name": table_name}).fetchall()
        
        # Get index information
        indexes_query = text("""
            SELECT 
                indexname,
                pg_size_pretty(pg_relation_size(indexname::regclass)) AS index_size,
                pg_relation_size(indexname::regclass) AS index_size_bytes
            FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = :table_name
            ORDER BY pg_relation_size(indexname::regclass) DESC;
        """)
        
        indexes = conn.execute(indexes_query, {"table_name": table_name}).fetchall()
        
        return columns, indexes


def main():
    db_url = get_database_url()
    
    # Mask password in output
    display_url = db_url.split("@")[0].split(":")[0] + ":***@" + "@".join(db_url.split("@")[1:])
    print(f"Connecting to: {display_url}")
    print()
    
    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        print("✓ Connected successfully\n")
        
        # Get all table sizes
        print("=" * 100)
        print("DATABASE TABLE SIZES")
        print("=" * 100)
        print(f"{'Table Name':<30} {'Total Size':<15} {'Table Size':<15} {'Indexes Size':<15} {'Rows':<15}")
        print("-" * 100)
        
        tables = get_table_sizes(engine)
        total_db_size = 0
        chat_message_info = None
        
        for row in tables:
            schemaname, tablename, total_size, total_bytes, table_size, table_bytes, indexes_size, indexes_bytes = row
            
            # Get row count
            try:
                row_count = get_row_counts(engine, tablename)
            except Exception as e:
                row_count = "N/A"
            
            total_db_size += total_bytes
            
            # Format row count
            if isinstance(row_count, int):
                row_count_str = f"{row_count:,}"
            else:
                row_count_str = str(row_count)
            
            print(f"{tablename:<30} {total_size:<15} {table_size:<15} {indexes_size:<15} {row_count_str:<15}")
            
            # Store chat_message info for detailed view
            if tablename == "chat_message":
                chat_message_info = {
                    "total_size": total_size,
                    "total_bytes": total_bytes,
                    "table_size": table_size,
                    "table_bytes": table_bytes,
                    "indexes_size": indexes_size,
                    "indexes_bytes": indexes_bytes,
                    "row_count": row_count
                }
        
        print("-" * 100)
        print(f"{'TOTAL DATABASE SIZE':<30} {format_bytes(total_db_size):<15}")
        print("=" * 100)
        print()
        
        # Detailed information for chat_message table
        if chat_message_info:
            print("=" * 100)
            print("DETAILED INFORMATION: chat_message TABLE")
            print("=" * 100)
            print(f"Total Size (including indexes): {chat_message_info['total_size']} ({chat_message_info['total_bytes']:,} bytes)")
            print(f"Table Size (data only):         {chat_message_info['table_size']} ({chat_message_info['table_bytes']:,} bytes)")
            print(f"Indexes Size:                   {chat_message_info['indexes_size']} ({chat_message_info['indexes_bytes']:,} bytes)")
            print(f"Row Count:                      {chat_message_info['row_count']:,}")
            print()
            
            # Get column and index details
            columns, indexes = get_table_details(engine, "chat_message")
            
            print("Columns:")
            print("-" * 100)
            for col in columns:
                col_name, data_type, max_length, nullable = col
                length_str = f"({max_length})" if max_length else ""
                null_str = "NULL" if nullable == "YES" else "NOT NULL"
                print(f"  {col_name:<30} {data_type}{length_str:<20} {null_str}")
            
            print()
            print("Indexes:")
            print("-" * 100)
            if indexes:
                for idx in indexes:
                    idx_name, idx_size, idx_bytes = idx
                    print(f"  {idx_name:<50} {idx_size:<15} ({idx_bytes:,} bytes)")
            else:
                print("  No indexes found")
            
            print()
            
            # Calculate average row size
            if isinstance(chat_message_info['row_count'], int) and chat_message_info['row_count'] > 0:
                avg_row_size = chat_message_info['table_bytes'] / chat_message_info['row_count']
                print(f"Average row size: {format_bytes(avg_row_size)}")
                print()
        
        # Summary statistics
        print("=" * 100)
        print("SUMMARY STATISTICS")
        print("=" * 100)
        print(f"Total number of tables: {len(tables)}")
        if chat_message_info:
            percentage = (chat_message_info['total_bytes'] / total_db_size * 100) if total_db_size > 0 else 0
            print(f"chat_message table represents {percentage:.2f}% of total database size")
        print("=" * 100)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
















