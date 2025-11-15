"""add daily metrics rollup table for fast metrics queries

Revision ID: add_daily_metrics_rollup
Revises: 9f0e_add_fulltext_search
Create Date: 2025-11-08 10:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision = 'add_daily_metrics_rollup'
down_revision = '9f0e_add_fulltext_search'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create daily metrics rollup table and populate with historical data.
    This table stores pre-aggregated metrics per user, per day, per model
    to enable fast metrics dashboard queries without scanning chat_message.
    """
    conn = op.get_bind()
    dialect_name = conn.dialect.name
    
    # Create the rollup table
    op.create_table(
        'metrics_daily_rollup',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False, index=True),
        sa.Column('date', sa.Date(), nullable=False, index=True),
        sa.Column('model_id', sa.Text(), nullable=True, index=True),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_cost', sa.Numeric(precision=10, scale=8), nullable=False, server_default='0'),
        sa.Column('total_input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_reasoning_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('distinct_chat_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
    )
    
    # Create unique constraint on (user_id, date, model_id) to prevent duplicates
    op.create_unique_constraint(
        'uq_metrics_daily_rollup_user_date_model',
        'metrics_daily_rollup',
        ['user_id', 'date', 'model_id']
    )
    
    # Create composite index for common query patterns
    op.create_index(
        'ix_metrics_daily_rollup_user_date',
        'metrics_daily_rollup',
        ['user_id', 'date']
    )
    
    op.create_index(
        'ix_metrics_daily_rollup_user_model_date',
        'metrics_daily_rollup',
        ['user_id', 'model_id', 'date']
    )
    
    # Create composite index on chat_message to optimize EXISTS queries in triggers
    # This index supports fast lookups for checking if a chat has other messages on a given day/model
    # Include role to help filter out user messages efficiently
    if dialect_name == 'postgresql':
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_message_chatid_createdat_model_role 
            ON chat_message (chat_id, created_at, model_id, role)
        """)
    
    # Backfill historical data
    print("Backfilling historical metrics data...")
    
    if dialect_name == 'postgresql':
        # PostgreSQL: Use efficient SQL aggregation
        op.execute("""
            INSERT INTO metrics_daily_rollup (
                id, user_id, date, model_id, message_count, total_cost,
                total_input_tokens, total_output_tokens, total_reasoning_tokens,
                distinct_chat_count, created_at, updated_at
            )
            SELECT 
                md5(c.user_id || '|' || DATE(to_timestamp(cm.created_at))::text || '|' || COALESCE(cm.model_id, ''))::text as id,
                c.user_id,
                DATE(to_timestamp(cm.created_at)) as date,
                cm.model_id,
                COUNT(cm.id) as message_count,
                COALESCE(SUM(cm.cost), 0) as total_cost,
                COALESCE(SUM(cm.input_tokens), 0) as total_input_tokens,
                COALESCE(SUM(cm.output_tokens), 0) as total_output_tokens,
                COALESCE(SUM(cm.reasoning_tokens), 0) as total_reasoning_tokens,
                COUNT(DISTINCT cm.chat_id) as distinct_chat_count,
                EXTRACT(EPOCH FROM NOW())::bigint as created_at,
                EXTRACT(EPOCH FROM NOW())::bigint as updated_at
            FROM chat_message cm
            JOIN chat c ON cm.chat_id = c.id
            WHERE cm.role != 'user'  -- Only count assistant messages (user messages have no model/cost/tokens)
            AND cm.model_id IS NOT NULL
            GROUP BY c.user_id, DATE(to_timestamp(cm.created_at)), cm.model_id
            ON CONFLICT (user_id, date, model_id) DO NOTHING
        """)
        
        # Create trigger function to update rollup table on INSERT/UPDATE/DELETE
        # Uses incremental updates (O(1)) instead of full recalculations (O(n))
        # Uses epoch range checks instead of DATE() functions for better index usage
        op.execute("""
            CREATE OR REPLACE FUNCTION update_metrics_daily_rollup()
            RETURNS TRIGGER AS $$
            DECLARE
                v_user_id TEXT;
                v_date DATE;
                v_model_id TEXT;
                v_old_user_id TEXT;
                v_old_date DATE;
                v_old_model_id TEXT;
                v_date_changed BOOLEAN;
                v_model_changed BOOLEAN;
                v_is_new_chat_for_day BOOLEAN;
                v_was_last_message_for_chat BOOLEAN;
                v_day_start_epoch BIGINT;
                v_day_end_epoch BIGINT;
                v_old_day_start_epoch BIGINT;
                v_old_day_end_epoch BIGINT;
            BEGIN
                -- Handle INSERT
                IF TG_OP = 'INSERT' THEN
                    -- Skip user messages - they have no model/cost/tokens
                    IF NEW.role = 'user' THEN
                        RETURN NEW;
                    END IF;
                    
                    -- Get user_id from chat table
                    SELECT user_id INTO v_user_id FROM chat WHERE id = NEW.chat_id;
                    IF v_user_id IS NULL THEN
                        RETURN NEW;
                    END IF;
                    
                    -- Calculate date from timestamp
                    v_date := DATE(to_timestamp(NEW.created_at));
                    v_model_id := NEW.model_id;
                    
                    -- Skip if no model_id (shouldn't happen for assistant messages, but be safe)
                    IF v_model_id IS NULL THEN
                        RETURN NEW;
                    END IF;
                    
                    -- Calculate epoch range for the day (start and end of day in UTC)
                    v_day_start_epoch := EXTRACT(EPOCH FROM DATE_TRUNC('day', to_timestamp(NEW.created_at)))::BIGINT;
                    v_day_end_epoch := v_day_start_epoch + 86400 - 1; -- end of day (23:59:59)
                    
                    -- Check if this is the first message from this chat for this day/model combo
                    -- (for distinct_chat_count increment)
                    -- Use epoch range check instead of DATE() function for index usage
                    -- Only count assistant messages
                    SELECT NOT EXISTS (
                        SELECT 1 FROM chat_message cm
                        WHERE cm.chat_id = NEW.chat_id
                        AND cm.id != NEW.id
                        AND cm.role != 'user'
                        AND cm.created_at >= v_day_start_epoch
                        AND cm.created_at <= v_day_end_epoch
                        AND (cm.model_id = v_model_id OR (cm.model_id IS NULL AND v_model_id IS NULL))
                    ) INTO v_is_new_chat_for_day;
                    
                    -- Insert or update rollup row incrementally
                    INSERT INTO metrics_daily_rollup (
                        id, user_id, date, model_id, message_count, total_cost,
                        total_input_tokens, total_output_tokens, total_reasoning_tokens,
                        distinct_chat_count, created_at, updated_at
                    )
                    VALUES (
                        md5(v_user_id || '|' || v_date::text || '|' || COALESCE(v_model_id, ''))::text,
                        v_user_id,
                        v_date,
                        v_model_id,
                        1,
                        COALESCE(NEW.cost, 0),
                        COALESCE(NEW.input_tokens, 0),
                        COALESCE(NEW.output_tokens, 0),
                        COALESCE(NEW.reasoning_tokens, 0),
                        CASE WHEN v_is_new_chat_for_day THEN 1 ELSE 0 END,
                        EXTRACT(EPOCH FROM NOW())::bigint,
                        EXTRACT(EPOCH FROM NOW())::bigint
                    )
                    ON CONFLICT (user_id, date, model_id) DO UPDATE SET
                        message_count = metrics_daily_rollup.message_count + 1,
                        total_cost = metrics_daily_rollup.total_cost + COALESCE(NEW.cost, 0),
                        total_input_tokens = metrics_daily_rollup.total_input_tokens + COALESCE(NEW.input_tokens, 0),
                        total_output_tokens = metrics_daily_rollup.total_output_tokens + COALESCE(NEW.output_tokens, 0),
                        total_reasoning_tokens = metrics_daily_rollup.total_reasoning_tokens + COALESCE(NEW.reasoning_tokens, 0),
                        distinct_chat_count = metrics_daily_rollup.distinct_chat_count + 
                            CASE WHEN v_is_new_chat_for_day THEN 1 ELSE 0 END,
                        updated_at = EXTRACT(EPOCH FROM NOW())::bigint;
                END IF;
                
                -- Handle UPDATE
                IF TG_OP = 'UPDATE' THEN
                    -- Skip user messages - they have no model/cost/tokens
                    IF NEW.role = 'user' AND OLD.role = 'user' THEN
                        RETURN NEW;
                    END IF;
                    
                    -- Get user_ids from chat table
                    SELECT user_id INTO v_user_id FROM chat WHERE id = NEW.chat_id;
                    SELECT user_id INTO v_old_user_id FROM chat WHERE id = OLD.chat_id;
                    
                    -- Calculate dates from timestamps
                    v_date := DATE(to_timestamp(NEW.created_at));
                    v_old_date := DATE(to_timestamp(OLD.created_at));
                    v_model_id := NEW.model_id;
                    v_old_model_id := OLD.model_id;
                    
                    -- Handle role change from assistant to user
                    IF NEW.role = 'user' AND OLD.role != 'user' THEN
                        -- Treat as DELETE - remove from rollup
                        IF v_old_user_id IS NOT NULL AND v_old_model_id IS NOT NULL THEN
                            v_day_start_epoch := EXTRACT(EPOCH FROM DATE_TRUNC('day', to_timestamp(OLD.created_at)))::BIGINT;
                            v_day_end_epoch := v_day_start_epoch + 86400 - 1;
                            
                            SELECT NOT EXISTS (
                                SELECT 1 FROM chat_message cm
                                WHERE cm.chat_id = OLD.chat_id
                                AND cm.id != OLD.id
                                AND cm.role != 'user'
                                AND cm.created_at >= v_day_start_epoch
                                AND cm.created_at <= v_day_end_epoch
                                AND (cm.model_id = v_old_model_id OR (cm.model_id IS NULL AND v_old_model_id IS NULL))
                            ) INTO v_was_last_message_for_chat;
                            
                            UPDATE metrics_daily_rollup
                            SET
                                message_count = GREATEST(0, message_count - 1),
                                total_cost = GREATEST(0, total_cost - COALESCE(OLD.cost, 0)),
                                total_input_tokens = GREATEST(0, total_input_tokens - COALESCE(OLD.input_tokens, 0)),
                                total_output_tokens = GREATEST(0, total_output_tokens - COALESCE(OLD.output_tokens, 0)),
                                total_reasoning_tokens = GREATEST(0, total_reasoning_tokens - COALESCE(OLD.reasoning_tokens, 0)),
                                distinct_chat_count = GREATEST(0, distinct_chat_count - 
                                    CASE WHEN v_was_last_message_for_chat THEN 1 ELSE 0 END),
                                updated_at = EXTRACT(EPOCH FROM NOW())::bigint
                            WHERE user_id = v_old_user_id
                            AND date = v_old_date
                            AND (model_id = v_old_model_id OR (model_id IS NULL AND v_old_model_id IS NULL));
                            
                            DELETE FROM metrics_daily_rollup
                            WHERE user_id = v_old_user_id
                            AND date = v_old_date
                            AND (model_id = v_old_model_id OR (model_id IS NULL AND v_old_model_id IS NULL))
                            AND message_count = 0;
                        END IF;
                        RETURN NEW;
                    END IF;
                    
                    -- Skip if no model_id for new message
                    IF v_model_id IS NULL THEN
                        RETURN NEW;
                    END IF;
                    
                    v_date_changed := (v_date != v_old_date);
                    v_model_changed := (v_model_id IS DISTINCT FROM v_old_model_id);
                    
                    -- If date or model_id changed, we need to update both old and new rollup rows
                    IF v_date_changed OR v_model_changed THEN
                        -- Calculate epoch ranges for old and new days
                        v_old_day_start_epoch := EXTRACT(EPOCH FROM DATE_TRUNC('day', to_timestamp(OLD.created_at)))::BIGINT;
                        v_old_day_end_epoch := v_old_day_start_epoch + 86400 - 1;
                        v_day_start_epoch := EXTRACT(EPOCH FROM DATE_TRUNC('day', to_timestamp(NEW.created_at)))::BIGINT;
                        v_day_end_epoch := v_day_start_epoch + 86400 - 1;
                        
                        -- Check if OLD was the last message from this chat for the old day/model combo
                        -- Use epoch range check instead of DATE() function for index usage
                        -- Only count assistant messages
                        SELECT NOT EXISTS (
                            SELECT 1 FROM chat_message cm
                            WHERE cm.chat_id = OLD.chat_id
                            AND cm.id != OLD.id
                            AND cm.role != 'user'
                            AND cm.created_at >= v_old_day_start_epoch
                            AND cm.created_at <= v_old_day_end_epoch
                            AND (cm.model_id = v_old_model_id OR (cm.model_id IS NULL AND v_old_model_id IS NULL))
                        ) INTO v_was_last_message_for_chat;
                        
                        -- Decrement old rollup row incrementally
                        IF v_old_user_id IS NOT NULL THEN
                            UPDATE metrics_daily_rollup
                            SET
                                message_count = GREATEST(0, message_count - 1),
                                total_cost = GREATEST(0, total_cost - COALESCE(OLD.cost, 0)),
                                total_input_tokens = GREATEST(0, total_input_tokens - COALESCE(OLD.input_tokens, 0)),
                                total_output_tokens = GREATEST(0, total_output_tokens - COALESCE(OLD.output_tokens, 0)),
                                total_reasoning_tokens = GREATEST(0, total_reasoning_tokens - COALESCE(OLD.reasoning_tokens, 0)),
                                distinct_chat_count = GREATEST(0, distinct_chat_count - 
                                    CASE WHEN v_was_last_message_for_chat THEN 1 ELSE 0 END),
                                updated_at = EXTRACT(EPOCH FROM NOW())::bigint
                            WHERE user_id = v_old_user_id
                            AND date = v_old_date
                            AND (model_id = v_old_model_id OR (model_id IS NULL AND v_old_model_id IS NULL));
                            
                            -- Delete rollup row if all counts are zero
                            DELETE FROM metrics_daily_rollup
                            WHERE user_id = v_old_user_id
                            AND date = v_old_date
                            AND (model_id = v_old_model_id OR (model_id IS NULL AND v_old_model_id IS NULL))
                            AND message_count = 0;
                        END IF;
                        
                        -- Check if NEW is the first message from this chat for the new day/model combo
                        -- Use epoch range check instead of DATE() function for index usage
                        -- Only count assistant messages
                        SELECT NOT EXISTS (
                            SELECT 1 FROM chat_message cm
                            WHERE cm.chat_id = NEW.chat_id
                            AND cm.id != NEW.id
                            AND cm.role != 'user'
                            AND cm.created_at >= v_day_start_epoch
                            AND cm.created_at <= v_day_end_epoch
                            AND (cm.model_id = v_model_id OR (cm.model_id IS NULL AND v_model_id IS NULL))
                        ) INTO v_is_new_chat_for_day;
                        
                        -- Increment new rollup row incrementally
                        IF v_user_id IS NOT NULL THEN
                            INSERT INTO metrics_daily_rollup (
                                id, user_id, date, model_id, message_count, total_cost,
                                total_input_tokens, total_output_tokens, total_reasoning_tokens,
                                distinct_chat_count, created_at, updated_at
                            )
                            VALUES (
                                md5(v_user_id || '|' || v_date::text || '|' || COALESCE(v_model_id, ''))::text,
                                v_user_id,
                                v_date,
                                v_model_id,
                                1,
                                COALESCE(NEW.cost, 0),
                                COALESCE(NEW.input_tokens, 0),
                                COALESCE(NEW.output_tokens, 0),
                                COALESCE(NEW.reasoning_tokens, 0),
                                CASE WHEN v_is_new_chat_for_day THEN 1 ELSE 0 END,
                                EXTRACT(EPOCH FROM NOW())::bigint,
                                EXTRACT(EPOCH FROM NOW())::bigint
                            )
                            ON CONFLICT (user_id, date, model_id) DO UPDATE SET
                                message_count = metrics_daily_rollup.message_count + 1,
                                total_cost = metrics_daily_rollup.total_cost + COALESCE(NEW.cost, 0),
                                total_input_tokens = metrics_daily_rollup.total_input_tokens + COALESCE(NEW.input_tokens, 0),
                                total_output_tokens = metrics_daily_rollup.total_output_tokens + COALESCE(NEW.output_tokens, 0),
                                total_reasoning_tokens = metrics_daily_rollup.total_reasoning_tokens + COALESCE(NEW.reasoning_tokens, 0),
                                distinct_chat_count = metrics_daily_rollup.distinct_chat_count + 
                                    CASE WHEN v_is_new_chat_for_day THEN 1 ELSE 0 END,
                                updated_at = EXTRACT(EPOCH FROM NOW())::bigint;
                        END IF;
                    ELSE
                        -- Date and model_id didn't change, just update the metrics values incrementally
                        IF v_user_id IS NOT NULL THEN
                            UPDATE metrics_daily_rollup
                            SET
                                -- Adjust differences: subtract OLD values, add NEW values
                                total_cost = metrics_daily_rollup.total_cost - COALESCE(OLD.cost, 0) + COALESCE(NEW.cost, 0),
                                total_input_tokens = metrics_daily_rollup.total_input_tokens - COALESCE(OLD.input_tokens, 0) + COALESCE(NEW.input_tokens, 0),
                                total_output_tokens = metrics_daily_rollup.total_output_tokens - COALESCE(OLD.output_tokens, 0) + COALESCE(NEW.output_tokens, 0),
                                total_reasoning_tokens = metrics_daily_rollup.total_reasoning_tokens - COALESCE(OLD.reasoning_tokens, 0) + COALESCE(NEW.reasoning_tokens, 0),
                                updated_at = EXTRACT(EPOCH FROM NOW())::bigint
                            WHERE user_id = v_user_id
                            AND date = v_date
                            AND (model_id = v_model_id OR (model_id IS NULL AND v_model_id IS NULL));
                        END IF;
                    END IF;
                END IF;
                
                -- Handle DELETE
                IF TG_OP = 'DELETE' THEN
                    -- Skip user messages - they shouldn't be in rollup anyway
                    IF OLD.role = 'user' THEN
                        RETURN OLD;
                    END IF;
                    
                    -- Get user_id from chat table
                    SELECT user_id INTO v_old_user_id FROM chat WHERE id = OLD.chat_id;
                    IF v_old_user_id IS NULL THEN
                        RETURN OLD;
                    END IF;
                    
                    -- Calculate date from timestamp
                    v_old_date := DATE(to_timestamp(OLD.created_at));
                    v_old_model_id := OLD.model_id;
                    
                    -- Skip if no model_id
                    IF v_old_model_id IS NULL THEN
                        RETURN OLD;
                    END IF;
                    
                    -- Calculate epoch range for the day
                    v_day_start_epoch := EXTRACT(EPOCH FROM DATE_TRUNC('day', to_timestamp(OLD.created_at)))::BIGINT;
                    v_day_end_epoch := v_day_start_epoch + 86400 - 1;
                    
                    -- Check if this was the last message from this chat for this day/model combo
                    -- Use epoch range check instead of DATE() function for index usage
                    -- Only count assistant messages
                    SELECT NOT EXISTS (
                        SELECT 1 FROM chat_message cm
                        WHERE cm.chat_id = OLD.chat_id
                        AND cm.id != OLD.id
                        AND cm.role != 'user'
                        AND cm.created_at >= v_day_start_epoch
                        AND cm.created_at <= v_day_end_epoch
                        AND (cm.model_id = v_old_model_id OR (cm.model_id IS NULL AND v_old_model_id IS NULL))
                    ) INTO v_was_last_message_for_chat;
                    
                    -- Decrement rollup row incrementally
                    UPDATE metrics_daily_rollup
                    SET
                        message_count = GREATEST(0, message_count - 1),
                        total_cost = GREATEST(0, total_cost - COALESCE(OLD.cost, 0)),
                        total_input_tokens = GREATEST(0, total_input_tokens - COALESCE(OLD.input_tokens, 0)),
                        total_output_tokens = GREATEST(0, total_output_tokens - COALESCE(OLD.output_tokens, 0)),
                        total_reasoning_tokens = GREATEST(0, total_reasoning_tokens - COALESCE(OLD.reasoning_tokens, 0)),
                        distinct_chat_count = GREATEST(0, distinct_chat_count - 
                            CASE WHEN v_was_last_message_for_chat THEN 1 ELSE 0 END),
                        updated_at = EXTRACT(EPOCH FROM NOW())::bigint
                    WHERE user_id = v_old_user_id
                    AND date = v_old_date
                    AND (model_id = v_old_model_id OR (model_id IS NULL AND v_old_model_id IS NULL));
                    
                    -- Delete rollup row if all counts are zero
                    DELETE FROM metrics_daily_rollup
                    WHERE user_id = v_old_user_id
                    AND date = v_old_date
                    AND (model_id = v_old_model_id OR (model_id IS NULL AND v_old_model_id IS NULL))
                    AND message_count = 0;
                END IF;
                
                RETURN COALESCE(NEW, OLD);
            END;
            $$ LANGUAGE plpgsql;
        """)
        
        # Create triggers
        op.execute("""
            DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_insert ON chat_message;
            CREATE TRIGGER trigger_update_metrics_daily_rollup_insert
            AFTER INSERT ON chat_message
            FOR EACH ROW
            EXECUTE FUNCTION update_metrics_daily_rollup();
        """)
        
        op.execute("""
            DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_update ON chat_message;
        CREATE TRIGGER trigger_update_metrics_daily_rollup_update
        AFTER UPDATE OF cost, input_tokens, output_tokens, reasoning_tokens, model_id, created_at, role ON chat_message
        FOR EACH ROW
        WHEN (OLD.cost IS DISTINCT FROM NEW.cost 
              OR OLD.input_tokens IS DISTINCT FROM NEW.input_tokens
              OR OLD.output_tokens IS DISTINCT FROM NEW.output_tokens
              OR OLD.reasoning_tokens IS DISTINCT FROM NEW.reasoning_tokens
              OR OLD.model_id IS DISTINCT FROM NEW.model_id
              OR OLD.created_at IS DISTINCT FROM NEW.created_at
              OR OLD.role IS DISTINCT FROM NEW.role)
        EXECUTE FUNCTION update_metrics_daily_rollup();
        """)
        
        op.execute("""
            DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_delete ON chat_message;
            CREATE TRIGGER trigger_update_metrics_daily_rollup_delete
            AFTER DELETE ON chat_message
            FOR EACH ROW
            EXECUTE FUNCTION update_metrics_daily_rollup();
        """)
        
        # Analyze table for query planner
        op.execute("ANALYZE metrics_daily_rollup")
        op.execute("ANALYZE chat_message")  # Analyze chat_message to update stats for new index
        
        print("Daily metrics rollup table created and populated for PostgreSQL")
        print("NOTE: Consider running a nightly reconciliation sweep to fix any drift.")
        print("      The triggers use incremental updates which are fast but may accumulate")
        print("      small errors over time. A nightly full recalculation can correct these.")
        
    else:
        # SQLite: Use Python-based backfill (triggers not well supported)
        # For SQLite, we'll need to handle updates via application code
        # or periodic refresh jobs
        print("SQLite detected: Backfilling metrics (triggers not supported, will need application-level updates)")
        
        # Backfill using Python
        result = conn.execute(sa.text("""
            SELECT 
                c.user_id,
                DATE(datetime(cm.created_at, 'unixepoch')) as date,
                cm.model_id,
                COUNT(cm.id) as message_count,
                COALESCE(SUM(cm.cost), 0) as total_cost,
                COALESCE(SUM(cm.input_tokens), 0) as total_input_tokens,
                COALESCE(SUM(cm.output_tokens), 0) as total_output_tokens,
                COALESCE(SUM(cm.reasoning_tokens), 0) as total_reasoning_tokens,
                COUNT(DISTINCT cm.chat_id) as distinct_chat_count
            FROM chat_message cm
            JOIN chat c ON cm.chat_id = c.id
            WHERE cm.model_id IS NOT NULL
            GROUP BY c.user_id, DATE(datetime(cm.created_at, 'unixepoch')), cm.model_id
        """))
        
        import hashlib
        import time
        now_ts = int(time.time())
        
        for row in result:
            user_id, date_str, model_id, msg_count, cost, in_tokens, out_tokens, reason_tokens, chat_count = row
            rollup_id = hashlib.md5(f"{user_id}|{date_str}|{model_id or ''}".encode()).hexdigest()
            
            conn.execute(sa.text("""
                INSERT OR REPLACE INTO metrics_daily_rollup (
                    id, user_id, date, model_id, message_count, total_cost,
                    total_input_tokens, total_output_tokens, total_reasoning_tokens,
                    distinct_chat_count, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :date, :model_id, :msg_count, :cost,
                    :in_tokens, :out_tokens, :reason_tokens, :chat_count, :created_at, :updated_at
                )
            """), {
                "id": rollup_id,
                "user_id": user_id,
                "date": date_str,
                "model_id": model_id,
                "msg_count": msg_count,
                "cost": cost,
                "in_tokens": in_tokens,
                "out_tokens": out_tokens,
                "reason_tokens": reason_tokens,
                "chat_count": chat_count,
                "created_at": now_ts,
                "updated_at": now_ts,
            })
        
        # Also handle messages without model_id
        result = conn.execute(sa.text("""
            SELECT 
                c.user_id,
                DATE(datetime(cm.created_at, 'unixepoch')) as date,
                COUNT(cm.id) as message_count,
                COALESCE(SUM(cm.cost), 0) as total_cost,
                COALESCE(SUM(cm.input_tokens), 0) as total_input_tokens,
                COALESCE(SUM(cm.output_tokens), 0) as total_output_tokens,
                COALESCE(SUM(cm.reasoning_tokens), 0) as total_reasoning_tokens,
                COUNT(DISTINCT cm.chat_id) as distinct_chat_count
            FROM chat_message cm
            JOIN chat c ON cm.chat_id = c.id
            WHERE cm.model_id IS NULL
            GROUP BY c.user_id, DATE(datetime(cm.created_at, 'unixepoch'))
        """))
        
        for row in result:
            user_id, date_str, msg_count, cost, in_tokens, out_tokens, reason_tokens, chat_count = row
            rollup_id = hashlib.md5(f"{user_id}|{date_str}|".encode()).hexdigest()
            
            conn.execute(sa.text("""
                INSERT OR REPLACE INTO metrics_daily_rollup (
                    id, user_id, date, model_id, message_count, total_cost,
                    total_input_tokens, total_output_tokens, total_reasoning_tokens,
                    distinct_chat_count, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :date, NULL, :msg_count, :cost,
                    :in_tokens, :out_tokens, :reason_tokens, :chat_count, :created_at, :updated_at
                )
            """), {
                "id": rollup_id,
                "user_id": user_id,
                "date": date_str,
                "msg_count": msg_count,
                "cost": cost,
                "in_tokens": in_tokens,
                "out_tokens": out_tokens,
                "reason_tokens": reason_tokens,
                "chat_count": chat_count,
                "created_at": now_ts,
                "updated_at": now_ts,
            })
        
        conn.commit()
        print("Daily metrics rollup table created and populated for SQLite")
        print("NOTE: SQLite does not support triggers. You'll need to update the rollup table")
        print("      via application code when chat_message is modified.")


def downgrade() -> None:
    """
    Remove daily metrics rollup table and triggers.
    """
    conn = op.get_bind()
    dialect_name = conn.dialect.name
    
    if dialect_name == 'postgresql':
        # Drop triggers
        op.execute("DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_delete ON chat_message")
        op.execute("DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_update ON chat_message")
        op.execute("DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_insert ON chat_message")
        
        # Drop function
        op.execute("DROP FUNCTION IF EXISTS update_metrics_daily_rollup()")
        
        # Drop chat_message index created for trigger optimization
        op.execute("DROP INDEX IF EXISTS idx_chat_message_chatid_createdat_model_role")
    
    # Drop indexes
    op.drop_index('ix_metrics_daily_rollup_user_model_date', table_name='metrics_daily_rollup')
    op.drop_index('ix_metrics_daily_rollup_user_date', table_name='metrics_daily_rollup')
    
    # Drop unique constraint
    op.drop_constraint('uq_metrics_daily_rollup_user_date_model', 'metrics_daily_rollup', type_='unique')
    
    # Drop table
    op.drop_table('metrics_daily_rollup')

