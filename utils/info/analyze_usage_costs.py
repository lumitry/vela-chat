#!/usr/bin/env python3
"""
Script to analyze chat message usage costs by model_id.
Uses the cost column for fast SQL aggregation instead of parsing JSON.
"""

import sys
import time
from pathlib import Path

# Add the backend directory to the path so we can import open_webui modules
script_dir = Path(__file__).parent.absolute()
backend_dir = script_dir
sys.path.insert(0, str(backend_dir))

from backend.open_webui.internal.db import get_db
from backend.open_webui.models.chat_messages import ChatMessage
from sqlalchemy import func


def main():
    """Main function to analyze usage costs."""
    print("Starting usage cost analysis (using cost column)...")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        with get_db() as db:
            # Get statistics first
            print("Querying chat_message table...")
            
            # Count total messages with cost data
            total_messages_with_cost = db.query(func.count(ChatMessage.id)).filter(
                ChatMessage.cost.isnot(None)
            ).scalar()
            
            # Count total messages with usage data (for comparison)
            total_messages_with_usage = db.query(func.count(ChatMessage.id)).filter(
                ChatMessage.usage.isnot(None)
            ).scalar()
            
            print(f"Found {total_messages_with_cost} messages with cost data")
            print(f"Found {total_messages_with_usage} messages with usage data")
            
            # Use SQL aggregation to get costs by model_id - MUCH faster!
            print("Aggregating costs by model_id...")
            results = db.query(
                func.coalesce(ChatMessage.model_id, 'unknown').label('model_id'),
                func.count(ChatMessage.id).label('message_count'),
                func.sum(ChatMessage.cost).label('total_cost')
            ).filter(
                ChatMessage.cost.isnot(None)
            ).group_by(
                func.coalesce(ChatMessage.model_id, 'unknown')
            ).order_by(
                func.sum(ChatMessage.cost).desc()
            ).limit(10).all()
        
        # Get total spend across all models
        with get_db() as db:
            total_spend_result = db.query(
                func.sum(ChatMessage.cost)
            ).filter(
                ChatMessage.cost.isnot(None)
            ).scalar()
            total_spend = float(total_spend_result) if total_spend_result else 0.0
        
        elapsed_time = time.time() - start_time
        
        # Print results
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"\nTotal messages with cost data: {total_messages_with_cost}")
        print(f"Total messages with usage data: {total_messages_with_usage}")
        print("\nTop 10 model_id's by total spend:\n")
        
        if results:
            print(f"{'Rank':<6} {'Model ID':<50} {'Message Count':>15} {'Total Spend':>15}")
            print("-" * 86)
            for rank, row in enumerate(results, 1):
                model_id = row.model_id
                message_count = row.message_count
                total_cost = float(row.total_cost) if row.total_cost else 0.0
                print(f"{rank:<6} {model_id:<50} {message_count:>15} ${total_cost:>14,.8f}")
            
            print("\n" + "=" * 60)
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

