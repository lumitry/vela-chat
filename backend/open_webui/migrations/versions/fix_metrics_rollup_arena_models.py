"""fix metrics rollup to use selected_model_id for arena models

Revision ID: fix_metrics_rollup_arena_models
Revises: add_daily_metrics_rollup
Create Date: 2025-11-08 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'fix_metrics_rollup_arena_models'
down_revision = 'add_daily_metrics_rollup'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Fix metrics rollup to use selected_model_id when present (for arena models).
    Arena models have model_id='arena-model' but selected_model_id contains the actual model used.
    We need to aggregate by the actual model, not the arena name.
    """
    conn = op.get_bind()
    dialect_name = conn.dialect.name
    
    if dialect_name != 'postgresql':
        print("Skipping arena model fix for non-PostgreSQL database")
        return
    
    # Drop existing triggers and function
    print("Dropping existing triggers and function...")
    op.execute("DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_delete ON chat_message")
    op.execute("DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_update ON chat_message")
    op.execute("DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_insert ON chat_message")
    op.execute("DROP FUNCTION IF EXISTS update_metrics_daily_rollup()")
    
    # Truncate and re-backfill the rollup table with correct model_id logic
    print("Truncating rollup table...")
    op.execute("TRUNCATE TABLE metrics_daily_rollup")
    
    # Re-backfill with COALESCE(selected_model_id, model_id) logic
    # CRITICAL: Only include assistant messages (role != 'user') - user messages have no model/cost/tokens
    print("Re-backfilling metrics with arena model support (excluding user messages)...")
    op.execute("""
        INSERT INTO metrics_daily_rollup (
            id, user_id, date, model_id, message_count, total_cost,
            total_input_tokens, total_output_tokens, total_reasoning_tokens,
            distinct_chat_count, created_at, updated_at
        )
        SELECT 
            md5(c.user_id || '|' || DATE(to_timestamp(cm.created_at))::text || '|' || COALESCE(COALESCE(cm.selected_model_id, cm.model_id), ''))::text as id,
            c.user_id,
            DATE(to_timestamp(cm.created_at)) as date,
            COALESCE(cm.selected_model_id, cm.model_id) as model_id,
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
        WHERE cm.role != 'user'
        AND COALESCE(cm.selected_model_id, cm.model_id) IS NOT NULL
        GROUP BY c.user_id, DATE(to_timestamp(cm.created_at)), COALESCE(cm.selected_model_id, cm.model_id)
        ON CONFLICT (user_id, date, model_id) DO NOTHING
    """)
    
    # Recreate trigger function with arena model support
    print("Recreating trigger function with arena model support...")
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
                -- Use selected_model_id if present, otherwise model_id (for arena models)
                v_model_id := COALESCE(NEW.selected_model_id, NEW.model_id);
                
                -- Skip if no model_id (shouldn't happen for assistant messages, but be safe)
                IF v_model_id IS NULL THEN
                    RETURN NEW;
                END IF;
                
                -- Calculate epoch range for the day (start and end of day in UTC)
                v_day_start_epoch := EXTRACT(EPOCH FROM DATE_TRUNC('day', to_timestamp(NEW.created_at)))::BIGINT;
                v_day_end_epoch := v_day_start_epoch + 86400 - 1; -- end of day (23:59:59)
                
                -- Check if this is the first message from this chat for this day/model combo
                -- Use epoch range check instead of DATE() function for index usage
                -- Check both model_id and selected_model_id separately for better index usage
                -- Only count assistant messages
                SELECT NOT EXISTS (
                    SELECT 1 FROM chat_message cm
                    WHERE cm.chat_id = NEW.chat_id
                    AND cm.id != NEW.id
                    AND cm.role != 'user'
                    AND cm.created_at >= v_day_start_epoch
                    AND cm.created_at <= v_day_end_epoch
                    AND (
                        (v_model_id IS NULL AND cm.model_id IS NULL AND cm.selected_model_id IS NULL)
                        OR (v_model_id IS NOT NULL AND (
                            (cm.selected_model_id = v_model_id)
                            OR (cm.selected_model_id IS NULL AND cm.model_id = v_model_id)
                        ))
                    )
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
                -- If role changed from assistant to user, remove from rollup
                -- If role changed from user to assistant, add to rollup
                IF NEW.role = 'user' AND OLD.role != 'user' THEN
                    -- Role changed to user - remove from rollup (handle as DELETE)
                    -- Fall through to DELETE logic below
                ELSIF NEW.role = 'user' THEN
                    -- Already a user message, skip
                    RETURN NEW;
                END IF;
                
                -- Get user_ids from chat table
                SELECT user_id INTO v_user_id FROM chat WHERE id = NEW.chat_id;
                SELECT user_id INTO v_old_user_id FROM chat WHERE id = OLD.chat_id;
                
                -- Calculate dates from timestamps
                v_date := DATE(to_timestamp(NEW.created_at));
                v_old_date := DATE(to_timestamp(OLD.created_at));
                -- Use selected_model_id if present, otherwise model_id (for arena models)
                v_model_id := COALESCE(NEW.selected_model_id, NEW.model_id);
                v_old_model_id := COALESCE(OLD.selected_model_id, OLD.model_id);
                
                -- Handle role change from assistant to user
                IF NEW.role = 'user' AND OLD.role != 'user' THEN
                    -- Treat as DELETE for the old assistant message
                    -- (fall through to DELETE handling - we'll handle this after the UPDATE block)
                    -- Actually, let's handle it here by jumping to DELETE logic
                    -- But we need to use OLD values, so let's duplicate the DELETE logic
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
                            AND (
                                (v_old_model_id IS NULL AND cm.model_id IS NULL AND cm.selected_model_id IS NULL)
                                OR (v_old_model_id IS NOT NULL AND (
                                    (cm.selected_model_id = v_old_model_id)
                                    OR (cm.selected_model_id IS NULL AND cm.model_id = v_old_model_id)
                                ))
                            )
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
                    -- Check both model_id and selected_model_id separately for better index usage
                    -- Only count assistant messages
                    SELECT NOT EXISTS (
                        SELECT 1 FROM chat_message cm
                        WHERE cm.chat_id = OLD.chat_id
                        AND cm.id != OLD.id
                        AND cm.role != 'user'
                        AND cm.created_at >= v_old_day_start_epoch
                        AND cm.created_at <= v_old_day_end_epoch
                        AND (
                            (v_old_model_id IS NULL AND cm.model_id IS NULL AND cm.selected_model_id IS NULL)
                            OR (v_old_model_id IS NOT NULL AND (
                                (cm.selected_model_id = v_old_model_id)
                                OR (cm.selected_model_id IS NULL AND cm.model_id = v_old_model_id)
                            ))
                        )
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
                    -- Check both model_id and selected_model_id separately for better index usage
                    -- Only count assistant messages
                    SELECT NOT EXISTS (
                        SELECT 1 FROM chat_message cm
                        WHERE cm.chat_id = NEW.chat_id
                        AND cm.id != NEW.id
                        AND cm.role != 'user'
                        AND cm.created_at >= v_day_start_epoch
                        AND cm.created_at <= v_day_end_epoch
                        AND (
                            (v_model_id IS NULL AND cm.model_id IS NULL AND cm.selected_model_id IS NULL)
                            OR (v_model_id IS NOT NULL AND (
                                (cm.selected_model_id = v_model_id)
                                OR (cm.selected_model_id IS NULL AND cm.model_id = v_model_id)
                            ))
                        )
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
                -- Use selected_model_id if present, otherwise model_id (for arena models)
                v_old_model_id := COALESCE(OLD.selected_model_id, OLD.model_id);
                
                -- Skip if no model_id
                IF v_old_model_id IS NULL THEN
                    RETURN OLD;
                END IF;
                
                -- Calculate epoch range for the day
                v_day_start_epoch := EXTRACT(EPOCH FROM DATE_TRUNC('day', to_timestamp(OLD.created_at)))::BIGINT;
                v_day_end_epoch := v_day_start_epoch + 86400 - 1;
                
                -- Check if this was the last message from this chat for this day/model combo
                -- Check both model_id and selected_model_id separately for better index usage
                -- Only count assistant messages
                SELECT NOT EXISTS (
                    SELECT 1 FROM chat_message cm
                    WHERE cm.chat_id = OLD.chat_id
                    AND cm.id != OLD.id
                    AND cm.role != 'user'
                    AND cm.created_at >= v_day_start_epoch
                    AND cm.created_at <= v_day_end_epoch
                    AND (
                        (v_old_model_id IS NULL AND cm.model_id IS NULL AND cm.selected_model_id IS NULL)
                        OR (v_old_model_id IS NOT NULL AND (
                            (cm.selected_model_id = v_old_model_id)
                            OR (cm.selected_model_id IS NULL AND cm.model_id = v_old_model_id)
                        ))
                    )
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
    
    # Recreate triggers
    print("Recreating triggers...")
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
        AFTER UPDATE OF cost, input_tokens, output_tokens, reasoning_tokens, model_id, selected_model_id, created_at, role ON chat_message
        FOR EACH ROW
        WHEN (OLD.cost IS DISTINCT FROM NEW.cost 
              OR OLD.input_tokens IS DISTINCT FROM NEW.input_tokens
              OR OLD.output_tokens IS DISTINCT FROM NEW.output_tokens
              OR OLD.reasoning_tokens IS DISTINCT FROM NEW.reasoning_tokens
              OR OLD.model_id IS DISTINCT FROM NEW.model_id
              OR OLD.selected_model_id IS DISTINCT FROM NEW.selected_model_id
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
    
    # Update index to include selected_model_id and role for better EXISTS query performance
    print("Updating index to support selected_model_id lookups...")
    op.execute("DROP INDEX IF EXISTS idx_chat_message_chatid_createdat_model_role")
    op.execute("""
        CREATE INDEX idx_chat_message_chatid_createdat_model_role 
        ON chat_message (chat_id, created_at, model_id, selected_model_id, role)
    """)
    
    # Analyze tables
    op.execute("ANALYZE metrics_daily_rollup")
    op.execute("ANALYZE chat_message")
    
    print("Metrics rollup updated with arena model support!")


def downgrade() -> None:
    """
    Revert to previous version (without arena model support).
    Note: This will lose the corrected arena model data.
    """
    conn = op.get_bind()
    dialect_name = conn.dialect.name
    
    if dialect_name != 'postgresql':
        return
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_delete ON chat_message")
    op.execute("DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_update ON chat_message")
    op.execute("DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_insert ON chat_message")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS update_metrics_daily_rollup()")
    
    # Recreate original index
    op.execute("DROP INDEX IF EXISTS idx_chat_message_chatid_createdat_model_role")
    op.execute("""
        CREATE INDEX idx_chat_message_chatid_createdat_model_role 
        ON chat_message (chat_id, created_at, model_id, role)
    """)
    
    # Note: We don't re-backfill here since downgrade should be rare
    # The rollup table will be empty until next upgrade

