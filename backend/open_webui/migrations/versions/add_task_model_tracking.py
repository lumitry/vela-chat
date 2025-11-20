"""add task model tracking tables

Revision ID: add_task_model_tracking
Revises: fix_metrics_rollup_arena_models
Create Date: 2025-11-09 9:45:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'add_task_model_tracking'
down_revision = 'fix_metrics_rollup_arena_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create task model tracking tables:
    - task_prompt_template: Stores prompt templates with deduplication
    - task_generation: Stores individual task generation records
    - task_metrics_daily_rollup: Pre-aggregated daily metrics for tasks
    """
    conn = op.get_bind()
    dialect_name = conn.dialect.name
    
    # Create task_prompt_template table
    op.create_table(
        'task_prompt_template',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('task_type', sa.Text(), nullable=False),
        sa.Column('template', sa.Text(), nullable=False),
        sa.Column('template_hash', sa.Text(), nullable=False),
        sa.Column('source', sa.Text(), nullable=False, server_default='default'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
    )
    
    op.create_index('ix_task_prompt_template_task_type', 'task_prompt_template', ['task_type'])
    op.create_unique_constraint(
        'uq_task_prompt_template_task_hash',
        'task_prompt_template',
        ['task_type', 'template_hash']
    )
    
    # Create task_generation table
    op.create_table(
        'task_generation',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('chat_id', sa.String(), nullable=False),
        sa.Column('message_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('task_type', sa.Text(), nullable=False),
        sa.Column('prompt_template_id', sa.String(), nullable=False),
        sa.Column('model_id', sa.Text(), nullable=False),
        sa.Column('task_model_type', sa.Text(), nullable=False),
        sa.Column('response_text', sa.Text(), nullable=True),
        sa.Column('usage', sa.JSON(), nullable=True),
        sa.Column('cost', sa.Numeric(precision=10, scale=8), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('reasoning_tokens', sa.Integer(), nullable=True),
        sa.Column('is_success', sa.Boolean(), nullable=True),
        sa.Column('error', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
    )
    
    # Create indexes for task_generation
    op.create_index('ix_task_generation_chat_id', 'task_generation', ['chat_id'])
    op.create_index('ix_task_generation_message_id', 'task_generation', ['message_id'])
    op.create_index('ix_task_generation_user_id', 'task_generation', ['user_id'])
    op.create_index('ix_task_generation_task_type', 'task_generation', ['task_type'])
    op.create_index('ix_task_generation_model_id', 'task_generation', ['model_id'])
    op.create_index('ix_task_generation_task_model_type', 'task_generation', ['task_model_type'])
    op.create_index('ix_task_generation_prompt_template_id', 'task_generation', ['prompt_template_id'])
    op.create_index('ix_task_generation_user_created', 'task_generation', ['user_id', 'created_at'])
    op.create_index('ix_task_generation_user_task_created', 'task_generation', ['user_id', 'task_type', 'created_at'])
    op.create_index('ix_task_generation_model_created', 'task_generation', ['model_id', 'created_at'])
    op.create_index('ix_task_generation_chat_message', 'task_generation', ['chat_id', 'message_id'])
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_task_generation_prompt_template',
        'task_generation',
        'task_prompt_template',
        ['prompt_template_id'],
        ['id']
    )
    
    # Create task_metrics_daily_rollup table
    op.create_table(
        'task_metrics_daily_rollup',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('task_type', sa.Text(), nullable=False),
        sa.Column('task_model_type', sa.Text(), nullable=False),
        sa.Column('model_id', sa.Text(), nullable=False),
        sa.Column('task_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_cost', sa.Numeric(precision=10, scale=8), nullable=False, server_default='0'),
        sa.Column('total_input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_reasoning_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('distinct_chat_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
    )
    
    # Create indexes for task_metrics_daily_rollup
    op.create_index('ix_task_metrics_rollup_user_id', 'task_metrics_daily_rollup', ['user_id'])
    op.create_index('ix_task_metrics_rollup_date', 'task_metrics_daily_rollup', ['date'])
    op.create_index('ix_task_metrics_rollup_task_type', 'task_metrics_daily_rollup', ['task_type'])
    op.create_index('ix_task_metrics_rollup_task_model_type', 'task_metrics_daily_rollup', ['task_model_type'])
    op.create_index('ix_task_metrics_rollup_model_id', 'task_metrics_daily_rollup', ['model_id'])
    op.create_index('ix_task_metrics_rollup_user_date', 'task_metrics_daily_rollup', ['user_id', 'date'])
    op.create_index('ix_task_metrics_rollup_user_model_date', 'task_metrics_daily_rollup', ['user_id', 'model_id', 'date'])
    
    # Create unique constraint
    op.create_unique_constraint(
        'uq_task_metrics_rollup_unique',
        'task_metrics_daily_rollup',
        ['user_id', 'date', 'task_type', 'model_id', 'task_model_type']
    )
    
    # Create PostgreSQL triggers for automatic rollup updates (similar to metrics_daily_rollup)
    if dialect_name == 'postgresql':
        print("Creating PostgreSQL triggers for task_metrics_daily_rollup...")
        
        # Create trigger function for task_generation INSERT/UPDATE/DELETE
        op.execute("""
            CREATE OR REPLACE FUNCTION update_task_metrics_daily_rollup()
            RETURNS TRIGGER AS $$
            DECLARE
                v_user_id TEXT;
                v_date DATE;
                v_task_type TEXT;
                v_model_id TEXT;
                v_task_model_type TEXT;
                v_old_user_id TEXT;
                v_old_date DATE;
                v_old_task_type TEXT;
                v_old_model_id TEXT;
                v_old_task_model_type TEXT;
                v_date_changed BOOLEAN;
                v_task_type_changed BOOLEAN;
                v_model_changed BOOLEAN;
                v_task_model_type_changed BOOLEAN;
                v_is_new_chat_for_day BOOLEAN;
                v_was_last_task_for_chat BOOLEAN;
                v_day_start_epoch BIGINT;
                v_day_end_epoch BIGINT;
                v_old_day_start_epoch BIGINT;
                v_old_day_end_epoch BIGINT;
            BEGIN
                -- Handle INSERT
                IF TG_OP = 'INSERT' THEN
                    -- Get user_id from chat table
                    SELECT user_id INTO v_user_id FROM chat WHERE id = NEW.chat_id;
                    IF v_user_id IS NULL THEN
                        RETURN NEW;
                    END IF;
                    
                    -- Calculate date from timestamp
                    v_date := DATE(to_timestamp(NEW.created_at));
                    v_task_type := NEW.task_type;
                    v_model_id := NEW.model_id;
                    v_task_model_type := NEW.task_model_type;
                    
                    -- Calculate epoch range for the day
                    v_day_start_epoch := EXTRACT(EPOCH FROM DATE_TRUNC('day', to_timestamp(NEW.created_at)))::BIGINT;
                    v_day_end_epoch := v_day_start_epoch + 86400 - 1;
                    
                    -- Check if this is the first task from this chat for this day/task_type/model combo
                    SELECT NOT EXISTS (
                        SELECT 1 FROM task_generation tg
                        WHERE tg.chat_id = NEW.chat_id
                        AND tg.id != NEW.id
                        AND tg.created_at >= v_day_start_epoch
                        AND tg.created_at <= v_day_end_epoch
                        AND tg.task_type = v_task_type
                        AND tg.model_id = v_model_id
                        AND tg.task_model_type = v_task_model_type
                    ) INTO v_is_new_chat_for_day;
                    
                    -- Insert or update rollup row incrementally
                    INSERT INTO task_metrics_daily_rollup (
                        id, user_id, date, task_type, task_model_type, model_id,
                        task_count, total_cost, total_input_tokens, total_output_tokens,
                        total_reasoning_tokens, distinct_chat_count, created_at, updated_at
                    )
                    VALUES (
                        md5(v_user_id || '|' || v_date::text || '|' || v_task_type || '|' || COALESCE(v_model_id, '') || '|' || v_task_model_type)::text,
                        v_user_id,
                        v_date,
                        v_task_type,
                        v_task_model_type,
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
                    ON CONFLICT (user_id, date, task_type, model_id, task_model_type) DO UPDATE SET
                        task_count = task_metrics_daily_rollup.task_count + 1,
                        total_cost = task_metrics_daily_rollup.total_cost + COALESCE(NEW.cost, 0),
                        total_input_tokens = task_metrics_daily_rollup.total_input_tokens + COALESCE(NEW.input_tokens, 0),
                        total_output_tokens = task_metrics_daily_rollup.total_output_tokens + COALESCE(NEW.output_tokens, 0),
                        total_reasoning_tokens = task_metrics_daily_rollup.total_reasoning_tokens + COALESCE(NEW.reasoning_tokens, 0),
                        distinct_chat_count = task_metrics_daily_rollup.distinct_chat_count + 
                            CASE WHEN v_is_new_chat_for_day THEN 1 ELSE 0 END,
                        updated_at = EXTRACT(EPOCH FROM NOW())::bigint;
                END IF;
                
                -- Handle UPDATE
                IF TG_OP = 'UPDATE' THEN
                    -- Get user_ids from chat table
                    SELECT user_id INTO v_user_id FROM chat WHERE id = NEW.chat_id;
                    SELECT user_id INTO v_old_user_id FROM chat WHERE id = OLD.chat_id;
                    
                    -- Calculate dates from timestamps
                    v_date := DATE(to_timestamp(NEW.created_at));
                    v_old_date := DATE(to_timestamp(OLD.created_at));
                    v_task_type := NEW.task_type;
                    v_old_task_type := OLD.task_type;
                    v_model_id := NEW.model_id;
                    v_old_model_id := OLD.model_id;
                    v_task_model_type := NEW.task_model_type;
                    v_old_task_model_type := OLD.task_model_type;
                    
                    v_date_changed := (v_date != v_old_date);
                    v_task_type_changed := (v_task_type != v_old_task_type);
                    v_model_changed := (v_model_id IS DISTINCT FROM v_old_model_id);
                    v_task_model_type_changed := (v_task_model_type != v_old_task_model_type);
                    
                    -- If any key changed, we need to update both old and new rollup rows
                    IF v_date_changed OR v_task_type_changed OR v_model_changed OR v_task_model_type_changed THEN
                        -- Calculate epoch ranges for old and new days
                        v_old_day_start_epoch := EXTRACT(EPOCH FROM DATE_TRUNC('day', to_timestamp(OLD.created_at)))::BIGINT;
                        v_old_day_end_epoch := v_old_day_start_epoch + 86400 - 1;
                        v_day_start_epoch := EXTRACT(EPOCH FROM DATE_TRUNC('day', to_timestamp(NEW.created_at)))::BIGINT;
                        v_day_end_epoch := v_day_start_epoch + 86400 - 1;
                        
                        -- Check if OLD was the last task from this chat for the old day/task_type/model combo
                        SELECT NOT EXISTS (
                            SELECT 1 FROM task_generation tg
                            WHERE tg.chat_id = OLD.chat_id
                            AND tg.id != OLD.id
                            AND tg.created_at >= v_old_day_start_epoch
                            AND tg.created_at <= v_old_day_end_epoch
                            AND tg.task_type = v_old_task_type
                            AND tg.model_id = v_old_model_id
                            AND tg.task_model_type = v_old_task_model_type
                        ) INTO v_was_last_task_for_chat;
                        
                        -- Decrement old rollup row incrementally
                        IF v_old_user_id IS NOT NULL THEN
                            UPDATE task_metrics_daily_rollup
                            SET
                                task_count = GREATEST(0, task_count - 1),
                                total_cost = GREATEST(0, total_cost - COALESCE(OLD.cost, 0)),
                                total_input_tokens = GREATEST(0, total_input_tokens - COALESCE(OLD.input_tokens, 0)),
                                total_output_tokens = GREATEST(0, total_output_tokens - COALESCE(OLD.output_tokens, 0)),
                                total_reasoning_tokens = GREATEST(0, total_reasoning_tokens - COALESCE(OLD.reasoning_tokens, 0)),
                                distinct_chat_count = GREATEST(0, distinct_chat_count - 
                                    CASE WHEN v_was_last_task_for_chat THEN 1 ELSE 0 END),
                                updated_at = EXTRACT(EPOCH FROM NOW())::bigint
                            WHERE user_id = v_old_user_id
                            AND date = v_old_date
                            AND task_type = v_old_task_type
                            AND model_id = v_old_model_id
                            AND task_model_type = v_old_task_model_type;
                            
                            -- Delete rollup row if all counts are zero
                            DELETE FROM task_metrics_daily_rollup
                            WHERE user_id = v_old_user_id
                            AND date = v_old_date
                            AND task_type = v_old_task_type
                            AND model_id = v_old_model_id
                            AND task_model_type = v_old_task_model_type
                            AND task_count = 0;
                        END IF;
                        
                        -- Check if NEW is the first task from this chat for the new day/task_type/model combo
                        SELECT NOT EXISTS (
                            SELECT 1 FROM task_generation tg
                            WHERE tg.chat_id = NEW.chat_id
                            AND tg.id != NEW.id
                            AND tg.created_at >= v_day_start_epoch
                            AND tg.created_at <= v_day_end_epoch
                            AND tg.task_type = v_task_type
                            AND tg.model_id = v_model_id
                            AND tg.task_model_type = v_task_model_type
                        ) INTO v_is_new_chat_for_day;
                        
                        -- Increment new rollup row incrementally
                        IF v_user_id IS NOT NULL THEN
                            INSERT INTO task_metrics_daily_rollup (
                                id, user_id, date, task_type, task_model_type, model_id,
                                task_count, total_cost, total_input_tokens, total_output_tokens,
                                total_reasoning_tokens, distinct_chat_count, created_at, updated_at
                            )
                            VALUES (
                                md5(v_user_id || '|' || v_date::text || '|' || v_task_type || '|' || COALESCE(v_model_id, '') || '|' || v_task_model_type)::text,
                                v_user_id,
                                v_date,
                                v_task_type,
                                v_task_model_type,
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
                            ON CONFLICT (user_id, date, task_type, model_id, task_model_type) DO UPDATE SET
                                task_count = task_metrics_daily_rollup.task_count + 1,
                                total_cost = task_metrics_daily_rollup.total_cost + COALESCE(NEW.cost, 0),
                                total_input_tokens = task_metrics_daily_rollup.total_input_tokens + COALESCE(NEW.input_tokens, 0),
                                total_output_tokens = task_metrics_daily_rollup.total_output_tokens + COALESCE(NEW.output_tokens, 0),
                                total_reasoning_tokens = task_metrics_daily_rollup.total_reasoning_tokens + COALESCE(NEW.reasoning_tokens, 0),
                                distinct_chat_count = task_metrics_daily_rollup.distinct_chat_count + 
                                    CASE WHEN v_is_new_chat_for_day THEN 1 ELSE 0 END,
                                updated_at = EXTRACT(EPOCH FROM NOW())::bigint;
                        END IF;
                    ELSE
                        -- Date and keys didn't change, just update the metrics values incrementally
                        IF v_user_id IS NOT NULL THEN
                            UPDATE task_metrics_daily_rollup
                            SET
                                -- Adjust differences: subtract OLD values, add NEW values
                                total_cost = task_metrics_daily_rollup.total_cost - COALESCE(OLD.cost, 0) + COALESCE(NEW.cost, 0),
                                total_input_tokens = task_metrics_daily_rollup.total_input_tokens - COALESCE(OLD.input_tokens, 0) + COALESCE(NEW.input_tokens, 0),
                                total_output_tokens = task_metrics_daily_rollup.total_output_tokens - COALESCE(OLD.output_tokens, 0) + COALESCE(NEW.output_tokens, 0),
                                total_reasoning_tokens = task_metrics_daily_rollup.total_reasoning_tokens - COALESCE(OLD.reasoning_tokens, 0) + COALESCE(NEW.reasoning_tokens, 0),
                                updated_at = EXTRACT(EPOCH FROM NOW())::bigint
                            WHERE user_id = v_user_id
                            AND date = v_date
                            AND task_type = v_task_type
                            AND model_id = v_model_id
                            AND task_model_type = v_task_model_type;
                        END IF;
                    END IF;
                END IF;
                
                -- Handle DELETE
                IF TG_OP = 'DELETE' THEN
                    -- Get user_id from chat table
                    SELECT user_id INTO v_old_user_id FROM chat WHERE id = OLD.chat_id;
                    IF v_old_user_id IS NULL THEN
                        RETURN OLD;
                    END IF;
                    
                    -- Calculate date from timestamp
                    v_old_date := DATE(to_timestamp(OLD.created_at));
                    v_old_task_type := OLD.task_type;
                    v_old_model_id := OLD.model_id;
                    v_old_task_model_type := OLD.task_model_type;
                    
                    -- Calculate epoch range for the day
                    v_old_day_start_epoch := EXTRACT(EPOCH FROM DATE_TRUNC('day', to_timestamp(OLD.created_at)))::BIGINT;
                    v_old_day_end_epoch := v_old_day_start_epoch + 86400 - 1;
                    
                    -- Check if this was the last task from this chat for this day/task_type/model combo
                    SELECT NOT EXISTS (
                        SELECT 1 FROM task_generation tg
                        WHERE tg.chat_id = OLD.chat_id
                        AND tg.id != OLD.id
                        AND tg.created_at >= v_old_day_start_epoch
                        AND tg.created_at <= v_old_day_end_epoch
                        AND tg.task_type = v_old_task_type
                        AND tg.model_id = v_old_model_id
                        AND tg.task_model_type = v_old_task_model_type
                    ) INTO v_was_last_task_for_chat;
                    
                    -- Decrement rollup row incrementally
                    UPDATE task_metrics_daily_rollup
                    SET
                        task_count = GREATEST(0, task_count - 1),
                        total_cost = GREATEST(0, total_cost - COALESCE(OLD.cost, 0)),
                        total_input_tokens = GREATEST(0, total_input_tokens - COALESCE(OLD.input_tokens, 0)),
                        total_output_tokens = GREATEST(0, total_output_tokens - COALESCE(OLD.output_tokens, 0)),
                        total_reasoning_tokens = GREATEST(0, total_reasoning_tokens - COALESCE(OLD.reasoning_tokens, 0)),
                        distinct_chat_count = GREATEST(0, distinct_chat_count - 
                            CASE WHEN v_was_last_task_for_chat THEN 1 ELSE 0 END),
                        updated_at = EXTRACT(EPOCH FROM NOW())::bigint
                    WHERE user_id = v_old_user_id
                    AND date = v_old_date
                    AND task_type = v_old_task_type
                    AND model_id = v_old_model_id
                    AND task_model_type = v_old_task_model_type;
                    
                    -- Delete rollup row if all counts are zero
                    DELETE FROM task_metrics_daily_rollup
                    WHERE user_id = v_old_user_id
                    AND date = v_old_date
                    AND task_type = v_old_task_type
                    AND model_id = v_old_model_id
                    AND task_model_type = v_old_task_model_type
                    AND task_count = 0;
                END IF;
                
                RETURN COALESCE(NEW, OLD);
            END;
            $$ LANGUAGE plpgsql;
        """)
        
        # Create triggers
        op.execute("""
            CREATE TRIGGER trigger_update_task_metrics_daily_rollup_insert
            AFTER INSERT ON task_generation
            FOR EACH ROW
            EXECUTE FUNCTION update_task_metrics_daily_rollup();
        """)
        
        op.execute("""
            CREATE TRIGGER trigger_update_task_metrics_daily_rollup_update
            AFTER UPDATE ON task_generation
            FOR EACH ROW
            EXECUTE FUNCTION update_task_metrics_daily_rollup();
        """)
        
        op.execute("""
            CREATE TRIGGER trigger_update_task_metrics_daily_rollup_delete
            AFTER DELETE ON task_generation
            FOR EACH ROW
            EXECUTE FUNCTION update_task_metrics_daily_rollup();
        """)
        
        print("PostgreSQL triggers created successfully.")
    else:
        print(f"Skipping trigger creation for {dialect_name} database (triggers are PostgreSQL-only)")


def downgrade() -> None:
    """Drop task model tracking tables and triggers"""
    conn = op.get_bind()
    dialect_name = conn.dialect.name
    
    if dialect_name == 'postgresql':
        # Drop triggers first
        op.execute("DROP TRIGGER IF EXISTS trigger_update_task_metrics_daily_rollup_delete ON task_generation")
        op.execute("DROP TRIGGER IF EXISTS trigger_update_task_metrics_daily_rollup_update ON task_generation")
        op.execute("DROP TRIGGER IF EXISTS trigger_update_task_metrics_daily_rollup_insert ON task_generation")
        op.execute("DROP FUNCTION IF EXISTS update_task_metrics_daily_rollup()")
    
    # Drop tables (foreign key constraints will be dropped automatically)
    op.drop_table('task_metrics_daily_rollup')
    op.drop_table('task_generation')
    op.drop_table('task_prompt_template')

