#!/usr/bin/env python3
"""
Script to analyze legacy chat usage costs by model_id.
Connects to a separate Postgres database, parses the legacy chat.chat JSON column,
and extracts usage.cost from ALL messages with usage data (matching normalized approach).
"""

import sys
import time
import argparse
from collections import defaultdict
from typing import Optional, Dict, Any

# SQLAlchemy imports
from sqlalchemy import create_engine, Column, String, Text, JSON, BigInteger
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Chat(Base):
    """Legacy Chat table model for the separate database."""
    __tablename__ = "chat"
    
    id = Column(String, primary_key=True)
    user_id = Column(String)
    title = Column(Text)
    chat = Column(JSON)  # This is the legacy JSON blob
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


def extract_cost_from_usage(usage: Optional[dict]) -> float:
    """
    Extract cost from usage JSON.
    Looks for usage.cost directly.
    """
    if not usage or not isinstance(usage, dict):
        return 0.0
    
    # Look for direct cost field
    if 'cost' in usage and usage['cost'] is not None:
        try:
            return float(usage['cost'])
        except (ValueError, TypeError):
            pass
    
    return 0.0




def parse_chat_messages(chat_json: Optional[Dict]) -> Dict[str, Any]:
    """Extract messages from legacy chat JSON structure."""
    if not chat_json or not isinstance(chat_json, dict):
        return {}
    
    # Handle nested structure: chat.chat.history.messages
    if 'chat' in chat_json and isinstance(chat_json['chat'], dict):
        chat_json = chat_json['chat']
    
    history = chat_json.get('history', {})
    if isinstance(history, dict):
        return history.get('messages', {}) or {}
    
    return {}


def main():
    """Main function to analyze legacy usage costs."""
    parser = argparse.ArgumentParser(
        description='Analyze usage costs from legacy chat format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python3 analyze_legacy_usage_costs.py "postgresql://user:mySecurePassword@localhost:5432/dbname"
  
  Or with environment variable:
  export LEGACY_DB_URL="postgresql://user:mySecurePassword@localhost:5432/dbname"
  python3 analyze_legacy_usage_costs.py
        """
    )
    parser.add_argument(
        'database_url',
        nargs='?',
        help='PostgreSQL database connection URL (e.g., postgresql://user:mySecurePassword@host:port/dbname)'
    )
    parser.add_argument(
        '--env',
        action='store_true',
        help='Read database URL from LEGACY_DB_URL environment variable'
    )
    
    args = parser.parse_args()
    
    # Get database URL
    database_url = None
    if args.env or not args.database_url:
        import os
        database_url = os.environ.get('LEGACY_DB_URL')
        if not database_url and not args.env:
            print("Error: No database URL provided and LEGACY_DB_URL environment variable not set", file=sys.stderr)
            parser.print_help()
            sys.exit(1)
    else:
        database_url = args.database_url
    
    if not database_url:
        print("Error: No database URL provided", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
    
    print("Starting legacy usage cost analysis...")
    print("=" * 60)
    print(f"Database URL: {database_url.split('@')[0]}@***")  # Hide password
    print("=" * 60)
    
    start_time = time.time()
    
    # Dictionary to store total costs per model_id
    model_costs = defaultdict(float)
    total_chats = 0
    chats_processed = 0
    total_messages = 0
    messages_with_usage = 0
    messages_with_cost = 0
    
    try:
        # Create engine and session for the separate database
        engine = create_engine(database_url, pool_pre_ping=True)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        with SessionLocal() as db:
            # Query all chats with chat JSON data
            print("Querying chat table...")
            chats = db.query(Chat).filter(Chat.chat.isnot(None)).all()
            
            total_chats = len(chats)
            print(f"Found {total_chats} chats with chat data")
            
            # Process each chat
            for chat in chats:
                chats_processed += 1
                
                # Parse messages from legacy format
                messages = parse_chat_messages(chat.chat)
                
                if not messages:
                    continue
                
                # Process ALL messages with usage data (matching normalized approach)
                for message_id, message in messages.items():
                    # Check if message has usage data
                    usage = message.get('usage')
                    if usage is None:
                        continue
                    
                    messages_with_usage += 1
                    total_messages += 1
                    
                    # Extract cost from usage
                    cost = extract_cost_from_usage(usage)
                    
                    if cost > 0:
                        messages_with_cost += 1
                        # Get model_id from message (could be 'model' or 'modelName')
                        model_id = message.get('model') or message.get('modelName') or "unknown"
                        model_costs[model_id] += cost
        
        # Sort by total cost (descending) and get top 10
        sorted_models = sorted(
            model_costs.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        elapsed_time = time.time() - start_time
        
        # Print results
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"\nTotal chats processed: {total_chats}")
        print(f"Chats with messages: {chats_processed}")
        print(f"Total messages processed: {total_messages}")
        print(f"Messages with usage data: {messages_with_usage}")
        print(f"Messages with cost information: {messages_with_cost}")
        print("\nTop 10 model_id's by total spend:\n")
        
        if sorted_models:
            print(f"{'Rank':<6} {'Model ID':<50} {'Total Spend':>15}")
            print("-" * 71)
            for rank, (model_id, total_cost) in enumerate(sorted_models, 1):
                print(f"{rank:<6} {model_id:<50} ${total_cost:>14,.8f}")
            
            print("\n" + "=" * 60)
            total_spend = sum(model_costs.values())
            print(f"Total spend across all models: ${total_spend:,.8f}")
        else:
            print("No cost information found in any messages.")
        
        print(f"\nAnalysis completed in {elapsed_time:.3f} seconds")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError during analysis: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

