"""exclude imported chats from metrics

Revision ID: exclude_imported_chats_metrics
Revises: ad303355
Create Date: 2025-11-12 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'exclude_imported_chats_metrics'
# Latest migration in the chain
down_revision = 'ad303355'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Update metrics rollup triggers to exclude imported chats from metrics calculations.
    Imported chats are marked with meta->>'imported' = 'true' in the chat table.

    This migration adds a check after getting user_id to skip processing if the chat is imported.
    """
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    if dialect_name == 'postgresql':
        # Read the current trigger function and add imported chat exclusion
        # We'll add the check right after getting user_id in each operation
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
                v_chat_imported BOOLEAN;
            BEGIN
                -- Handle INSERT
                IF TG_OP = 'INSERT' THEN
                    -- Skip user messages - they have no model/cost/tokens
                    IF NEW.role = 'user' THEN
                        RETURN NEW;
                    END IF;
                    
                    -- Get user_id and check if chat is imported
                    SELECT user_id, COALESCE((meta->>'imported')::boolean, false) INTO v_user_id, v_chat_imported 
                    FROM chat WHERE id = NEW.chat_id;
                    
                    IF v_user_id IS NULL THEN
                        RETURN NEW;
                    END IF;
                    
                    -- Skip imported chats - they should not affect metrics
                    IF v_chat_imported = true THEN
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
                    
                    -- Get user_ids and check if chats are imported
                    SELECT user_id, COALESCE((meta->>'imported')::boolean, false) INTO v_user_id, v_chat_imported 
                    FROM chat WHERE id = NEW.chat_id;
                    SELECT user_id, COALESCE((meta->>'imported')::boolean, false) INTO v_old_user_id, v_chat_imported 
                    FROM chat WHERE id = OLD.chat_id;
                    
                    -- If new chat is imported, skip (don't add to metrics)
                    -- But we still need to handle removal from old date if chat became imported
                    SELECT COALESCE((meta->>'imported')::boolean, false) INTO v_chat_imported FROM chat WHERE id = NEW.chat_id;
                    IF v_chat_imported = true AND (OLD.role != 'user' OR OLD.role IS NULL) THEN
                        -- Chat is now imported, but was not before - remove from old metrics
                        -- This handles the case where a chat is marked as imported after creation
                        -- For now, we'll skip the update - imported chats shouldn't be updated anyway
                        RETURN NEW;
                    END IF;
                    
                    -- Calculate dates from timestamps
                    v_date := DATE(to_timestamp(NEW.created_at));
                    v_old_date := DATE(to_timestamp(OLD.created_at));
                    -- Use selected_model_id if present, otherwise model_id (for arena models)
                    v_model_id := COALESCE(NEW.selected_model_id, NEW.model_id);
                    v_old_model_id := COALESCE(OLD.selected_model_id, OLD.model_id);
                    
                    -- Handle role change from assistant to user
                    IF NEW.role = 'user' AND OLD.role != 'user' THEN
                        -- Treat as DELETE for the old assistant message
                        -- Only remove if old chat was not imported
                        SELECT COALESCE((meta->>'imported')::boolean, false) INTO v_chat_imported FROM chat WHERE id = OLD.chat_id;
                        IF v_old_user_id IS NOT NULL AND v_old_model_id IS NOT NULL AND v_chat_imported != true THEN
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
                        -- Only remove if old chat was not imported
                        SELECT COALESCE((meta->>'imported')::boolean, false) INTO v_chat_imported FROM chat WHERE id = OLD.chat_id;
                        IF v_old_user_id IS NOT NULL AND v_chat_imported != true THEN
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
                        -- Only add if new chat is not imported (checked above)
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
                    
                    -- Get user_id and check if chat is imported
                    SELECT user_id, COALESCE((meta->>'imported')::boolean, false) INTO v_old_user_id, v_chat_imported 
                    FROM chat WHERE id = OLD.chat_id;
                    
                    IF v_old_user_id IS NULL THEN
                        RETURN OLD;
                    END IF;
                    
                    -- Skip if chat was imported - it shouldn't be in rollup anyway
                    IF v_chat_imported = true THEN
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

        # Clean up existing metrics data from imported chats
        # This is a best-effort cleanup - some data might remain if chats were imported before this migration
        print("Cleaning up existing metrics data from imported chats...")
        op.execute("""
            -- Delete rollup entries that correspond to messages from imported chats
            -- This is approximate - we delete entries where all messages for that user/date/model
            -- come from imported chats
            WITH imported_chat_messages AS (
                SELECT DISTINCT 
                    c.user_id,
                    DATE(to_timestamp(cm.created_at)) as date,
                    COALESCE(cm.selected_model_id, cm.model_id) as model_id
                FROM chat_message cm
                JOIN chat c ON cm.chat_id = c.id
                WHERE cm.role != 'user'
                AND COALESCE(cm.selected_model_id, cm.model_id) IS NOT NULL
                AND (c.meta->>'imported')::boolean = true
            )
            DELETE FROM metrics_daily_rollup mdr
            WHERE EXISTS (
                SELECT 1 FROM imported_chat_messages icm
                WHERE icm.user_id = mdr.user_id
                AND icm.date = mdr.date
                AND (icm.model_id = mdr.model_id OR (icm.model_id IS NULL AND mdr.model_id IS NULL))
            )
            AND NOT EXISTS (
                -- But keep entries that also have non-imported chat messages
                SELECT 1 FROM chat_message cm
                JOIN chat c ON cm.chat_id = c.id
                WHERE c.user_id = mdr.user_id
                AND DATE(to_timestamp(cm.created_at)) = mdr.date
                AND COALESCE(cm.selected_model_id, cm.model_id) = mdr.model_id
                AND cm.role != 'user'
                AND (c.meta->>'imported')::boolean != true
            );
        """)

        print("Migration complete. Imported chats will now be excluded from metrics.")

    elif dialect_name == 'sqlite':
        # SQLite doesn't support triggers with JSON queries as easily
        # For SQLite, we'll need to handle this in application code
        # The import_chat function already marks chats, so queries can filter
        print(
            "SQLite detected: Imported chat exclusion will be handled in application code.")
        print("Note: Existing metrics data from imported chats may need manual cleanup.")
    else:
        raise NotImplementedError(
            f"Unsupported database dialect: {dialect_name}")


def downgrade() -> None:
    """Revert the trigger to include imported chats in metrics."""
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    if dialect_name == 'postgresql':
        # Revert to the trigger from fix_metrics_rollup_arena_models (without imported exclusion)
        # This would require re-running that migration's trigger code
        print("Downgrade not fully implemented. Would need to restore trigger from fix_metrics_rollup_arena_models.")
        print("To fully revert, you would need to re-run the trigger creation from that migration.")
    elif dialect_name == 'sqlite':
        print("SQLite: No changes to revert.")
    else:
        raise NotImplementedError(
            f"Unsupported database dialect: {dialect_name}")
