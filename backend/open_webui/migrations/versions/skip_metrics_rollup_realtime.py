"""Allow metrics triggers to be skipped during realtime streaming saves

Revision ID: skip_metrics_rollup_realtime
Revises: remove_feedback_snapshot
Create Date: 2025-11-20 12:00:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "skip_metrics_rollup_realtime"
down_revision = "remove_feedback_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    skip_condition = "COALESCE(current_setting('open_webui.skip_metrics_rollup', true), 'off') <> 'on'"

    op.execute(
        f"""
        DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_insert ON chat_message;
        CREATE TRIGGER trigger_update_metrics_daily_rollup_insert
        AFTER INSERT ON chat_message
        FOR EACH ROW
        WHEN ({skip_condition})
        EXECUTE FUNCTION update_metrics_daily_rollup();
    """
    )

    op.execute(
        f"""
        DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_update ON chat_message;
        CREATE TRIGGER trigger_update_metrics_daily_rollup_update
        AFTER UPDATE OF cost, input_tokens, output_tokens, reasoning_tokens, model_id, selected_model_id, created_at, role ON chat_message
        FOR EACH ROW
        WHEN (
            (
                OLD.cost IS DISTINCT FROM NEW.cost
                OR OLD.input_tokens IS DISTINCT FROM NEW.input_tokens
                OR OLD.output_tokens IS DISTINCT FROM NEW.output_tokens
                OR OLD.reasoning_tokens IS DISTINCT FROM NEW.reasoning_tokens
                OR OLD.model_id IS DISTINCT FROM NEW.model_id
                OR OLD.selected_model_id IS DISTINCT FROM NEW.selected_model_id
                OR OLD.created_at IS DISTINCT FROM NEW.created_at
                OR OLD.role IS DISTINCT FROM NEW.role
            )
            AND {skip_condition}
        )
        EXECUTE FUNCTION update_metrics_daily_rollup();
    """
    )

    op.execute(
        f"""
        DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_delete ON chat_message;
        CREATE TRIGGER trigger_update_metrics_daily_rollup_delete
        AFTER DELETE ON chat_message
        FOR EACH ROW
        WHEN ({skip_condition})
        EXECUTE FUNCTION update_metrics_daily_rollup();
    """
    )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    op.execute(
        """
        DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_insert ON chat_message;
        CREATE TRIGGER trigger_update_metrics_daily_rollup_insert
        AFTER INSERT ON chat_message
        FOR EACH ROW
        EXECUTE FUNCTION update_metrics_daily_rollup();
    """
    )

    op.execute(
        """
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
    """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trigger_update_metrics_daily_rollup_delete ON chat_message;
        CREATE TRIGGER trigger_update_metrics_daily_rollup_delete
        AFTER DELETE ON chat_message
        FOR EACH ROW
        EXECUTE FUNCTION update_metrics_daily_rollup();
    """
    )

