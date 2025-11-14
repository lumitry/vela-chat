import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any

from open_webui.internal.db import get_db
from open_webui.models.embeddings import EmbeddingGeneration, EmbeddingMetricsDailyRollup
from open_webui.models.chats import Chat
from open_webui.constants import EMBEDDING_TYPES
from open_webui.env import SRC_LOG_LEVELS
from sqlalchemy import func

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS.get("MODELS", logging.INFO))


def determine_embedding_model_type(embedding_engine: str, model_id: str) -> str:
    """
    Determine if embedding model is internal or external.
    Returns 'internal' or 'external'.
    """
    if embedding_engine in ["", "sentencetransformers", "ollama"]:
        return "internal"
    elif embedding_engine == "openai":
        return "external"
    else:
        # Default to external for unknown engines
        return "external"


def extract_embedding_usage(engine: str, response_data: dict) -> dict:
    """
    Extract usage information from embedding API response.

    Args:
        engine: Embedding engine ("openai", "ollama", or "" for sentencetransformers)
        response_data: Response data from the embedding API

    Returns:
        Dictionary with usage information: {"prompt_tokens": int, "cost": float, ...}
    """
    usage = {}

    if engine == "openai":
        # OpenAI/OpenRouter format
        api_usage = response_data.get("usage", {})
        usage["prompt_tokens"] = api_usage.get("prompt_tokens")
        usage["total_tokens"] = api_usage.get("total_tokens")
        usage["cost"] = api_usage.get("cost")
    elif engine == "ollama":
        # Ollama format - metadata contains prompt_eval_count
        usage["prompt_eval_count"] = response_data.get("prompt_eval_count")
        # Ollama doesn't return cost, will be set to 0
        usage["cost"] = 0
    else:
        # SentenceTransformers - no usage data from API, will be calculated via tokenize
        usage["cost"] = 0

    return usage


def get_sentence_transformer_tokens(ef, texts: list[str]) -> int:
    """
    Get token count for SentenceTransformers model using tokenize method.

    Args:
        ef: SentenceTransformer model instance
        texts: List of text strings to tokenize

    Returns:
        Total number of input tokens across all texts
    """
    try:
        tokens = ef.tokenize(texts)
        # tokens["input_ids"] is a tensor with shape [batch_size, sequence_length]
        # Sum up the lengths of all sequences
        if hasattr(tokens, "input_ids"):
            input_ids = tokens["input_ids"]
            if hasattr(input_ids, "shape"):
                # For PyTorch tensors
                return int(input_ids.shape[0] * input_ids.shape[1])
            elif isinstance(input_ids, list):
                # For lists
                return sum(len(seq) for seq in input_ids)
        return 0
    except Exception as e:
        log.debug(f"Error getting SentenceTransformer tokens: {e}")
        return 0


def record_embedding_generation(
    embedding_type: str,
    user_id: str,
    embedding_engine: str,
    model_id: str,
    total_input_tokens: Optional[int],
    cost: Optional[float],
    usage: Optional[dict],
    chat_id: Optional[str] = None,
    message_id: Optional[str] = None,
    knowledge_base_id: Optional[str] = None,
) -> Optional[str]:
    """
    Record an embedding generation in the database.

    Args:
        embedding_type: Type of embedding (from EMBEDDING_TYPES enum)
        user_id: ID of the user
        embedding_engine: Embedding engine ("sentencetransformers", "ollama", "openai")
        model_id: ID of the model used
        total_input_tokens: Number of input tokens
        cost: Cost of the embedding (0 for internal models)
        usage: Raw usage data from API
        chat_id: ID of the chat (optional, null for knowledge base uploads)
        message_id: ID of the message (optional, null for knowledge base uploads)
        knowledge_base_id: ID of the knowledge base (optional, for knowledge base embeddings)

    Returns:
        The embedding_generation ID if successful, None otherwise
    """
    try:
        # Determine embedding model type
        embedding_model_type = determine_embedding_model_type(embedding_engine, model_id)

        # Create embedding generation record
        generation_id = str(uuid.uuid4())
        ts = int(time.time())

        with get_db() as db:
            # Verify user exists (optional check, but good for data integrity)
            # We'll just proceed with the user_id provided

            embedding_gen = EmbeddingGeneration(
                id=generation_id,
                user_id=user_id,
                chat_id=chat_id,
                message_id=message_id,
                knowledge_base_id=knowledge_base_id,
                embedding_type=embedding_type,
                embedding_model_type=embedding_model_type,
                model_id=model_id,
                embedding_engine=embedding_engine,
                total_input_tokens=total_input_tokens,
                cost=cost,
                usage=usage,
                created_at=ts,
                updated_at=ts,
            )

            db.add(embedding_gen)
            db.commit()

            log.debug(
                f"Recorded embedding generation: {generation_id} "
                f"(type={embedding_type}, engine={embedding_engine}, model={model_id}, "
                f"tokens={total_input_tokens or 0}, cost={cost or 0})"
            )

            return generation_id

    except Exception as e:
        log.error(f"Error recording embedding generation: {e}", exc_info=True)
        return None


def compute_rollup_id(user_id: str, date: str, embedding_type: str, model_id: str, embedding_model_type: str) -> str:
    """Compute rollup ID from key fields"""
    key = f"{user_id}|{date}|{embedding_type}|{model_id}|{embedding_model_type}"
    return hashlib.md5(key.encode('utf-8')).hexdigest()


def update_embedding_metrics_rollup(
    user_id: str,
    date: str,  # ISO date string (YYYY-MM-DD)
    embedding_type: str,
    model_id: str,
    embedding_model_type: str,
    # {"total_cost": float, "total_tokens": int, "count": int, "distinct_chat_count": int}
    aggregated_usage: Dict[str, Any],
) -> bool:
    """
    Update the daily rollup table with aggregated embedding metrics.
    Uses INSERT ... ON CONFLICT DO UPDATE to incrementally update metrics.

    Args:
        user_id: ID of the user
        date: ISO date string (YYYY-MM-DD) in UTC
        embedding_type: Type of embedding
        model_id: ID of the model
        embedding_model_type: "internal" or "external"
        aggregated_usage: Dictionary with aggregated metrics:
            - total_cost: Total cost for this batch
            - total_tokens: Total input tokens for this batch
            - count: Number of embedding requests in this batch
            - distinct_chat_count: Number of distinct chats (0 or 1 for a single batch)

    Returns:
        True if successful, False otherwise
    """
    try:
        rollup_id = compute_rollup_id(user_id, date, embedding_type, model_id, embedding_model_type)
        ts = int(time.time())

        total_cost = aggregated_usage.get("total_cost", 0) or 0
        total_tokens = aggregated_usage.get("total_tokens", 0) or 0
        count = aggregated_usage.get("count", 1) or 1
        distinct_chat_count = aggregated_usage.get("distinct_chat_count", 0) or 0

        with get_db() as db:
            # Check if rollup row exists
            existing = db.query(EmbeddingMetricsDailyRollup).filter_by(
                user_id=user_id,
                date=date,
                embedding_type=embedding_type,
                model_id=model_id,
                embedding_model_type=embedding_model_type
            ).first()

            if existing:
                # Update existing row
                existing.task_count += count
                existing.total_cost += total_cost
                existing.total_input_tokens += total_tokens
                existing.distinct_chat_count += distinct_chat_count
                existing.updated_at = ts
                db.commit()
            else:
                # Create new row
                rollup = EmbeddingMetricsDailyRollup(
                    id=rollup_id,
                    user_id=user_id,
                    date=date,
                    embedding_type=embedding_type,
                    embedding_model_type=embedding_model_type,
                    model_id=model_id,
                    task_count=count,
                    total_cost=total_cost,
                    total_input_tokens=total_tokens,
                    distinct_chat_count=distinct_chat_count,
                    created_at=ts,
                    updated_at=ts,
                )
                db.add(rollup)
                db.commit()

            log.debug(
                f"Updated embedding metrics rollup: {rollup_id} "
                f"(type={embedding_type}, model={model_id}, "
                f"count={count}, cost={total_cost}, tokens={total_tokens})"
            )

            return True

    except Exception as e:
        log.error(f"Error updating embedding metrics rollup: {e}", exc_info=True)
        return False


def associate_pending_embeddings_with_message(
    file_ids: list[str],
    chat_id: str,
    message_id: str,
    pending_metadata: dict,
) -> int:
    """
    Associate pending embedding metadata with a chat message.
    Updates embedding_generation records with chat_id and message_id.

    Args:
        file_ids: List of file IDs to associate
        chat_id: ID of the chat
        message_id: ID of the message
        pending_metadata: Dictionary of pending metadata keyed by file_id

    Returns:
        Number of embedding records updated
    """
    updated_count = 0

    try:
        with get_db() as db:
            for file_id in file_ids:
                if file_id not in pending_metadata:
                    continue

                metadata = pending_metadata[file_id]
                embedding_type = metadata.get("embedding_type")
                user_id = metadata.get("user_id")

                if not embedding_type or not user_id:
                    continue

                # Find embedding_generation records for this file_id that don't have chat_id/message_id
                # We store file_id in the usage JSON when recording, so we can query by that
                cutoff_time = int(time.time()) - 3600  # 1 hour ago

                records = db.query(EmbeddingGeneration).filter(
                    EmbeddingGeneration.user_id == user_id,
                    EmbeddingGeneration.embedding_type == embedding_type,
                    EmbeddingGeneration.chat_id.is_(None),
                    EmbeddingGeneration.message_id.is_(None),
                    EmbeddingGeneration.created_at >= cutoff_time,
                ).all()

                for record in records:
                    # Check if usage contains file_id
                    usage = record.usage or {}
                    if usage.get("file_id") == file_id:
                        record.chat_id = chat_id
                        record.message_id = message_id
                        record.updated_at = int(time.time())
                        updated_count += 1

                # Remove from pending metadata
                del pending_metadata[file_id]

            if updated_count > 0:
                db.commit()
                log.debug(f"Associated {updated_count} embedding records with chat {chat_id}, message {message_id}")

    except Exception as e:
        log.error(f"Error associating pending embeddings: {e}", exc_info=True)

    return updated_count


def update_rollup_from_embedding_generations(
    user_id: str,
    date: str,  # ISO date string (YYYY-MM-DD)
    embedding_type: str,
    model_id: str,
    embedding_model_type: str,
) -> bool:
    """
    Update the rollup table by aggregating all embedding_generation records
    for the given user, date, embedding_type, model_id, and embedding_model_type.

    This should be called after all embeddings for a batch are complete to ensure
    proper aggregation and avoid race conditions.

    Args:
        user_id: ID of the user
        date: ISO date string (YYYY-MM-DD) in UTC
        embedding_type: Type of embedding
        model_id: ID of the model
        embedding_model_type: "internal" or "external"

    Returns:
        True if successful, False otherwise
    """
    try:
        # Parse date string to get start and end of day in UTC
        date_obj = datetime.fromisoformat(date).date()
        start_of_day = datetime.combine(date_obj, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_of_day = datetime.combine(date_obj, datetime.max.time()).replace(tzinfo=timezone.utc)
        start_ts = int(start_of_day.timestamp())
        end_ts = int(end_of_day.timestamp())

        with get_db() as db:
            # Aggregate all embedding_generation records for this user/date/type/model/model_type
            result = db.query(
                func.count(EmbeddingGeneration.id).label('count'),
                func.sum(EmbeddingGeneration.total_input_tokens).label('total_tokens'),
                func.sum(EmbeddingGeneration.cost).label('total_cost'),
                func.count(func.distinct(EmbeddingGeneration.chat_id)).label('distinct_chats')
            ).filter(
                EmbeddingGeneration.user_id == user_id,
                EmbeddingGeneration.embedding_type == embedding_type,
                EmbeddingGeneration.model_id == model_id,
                EmbeddingGeneration.embedding_model_type == embedding_model_type,
                EmbeddingGeneration.created_at >= start_ts,
                EmbeddingGeneration.created_at <= end_ts,
            ).first()

            if not result:
                return False

            task_count = result.count or 0
            total_tokens = int(result.total_tokens or 0) if result.total_tokens else 0
            total_cost = float(result.total_cost or 0)   if result.total_cost   else 0
            distinct_chat_count = result.distinct_chats or 0

            if task_count == 0:
                return True  # No records to aggregate

            # Update or create rollup row
            rollup_id = compute_rollup_id(user_id, date, embedding_type, model_id, embedding_model_type)
            ts = int(time.time())

            existing = db.query(EmbeddingMetricsDailyRollup).filter_by(
                user_id=user_id,
                date=date,
                embedding_type=embedding_type,
                model_id=model_id,
                embedding_model_type=embedding_model_type
            ).first()

            if existing:
                # Recalculate from all records (not increment, to avoid double-counting)
                existing.task_count = task_count
                existing.total_cost = total_cost
                existing.total_input_tokens = total_tokens
                existing.distinct_chat_count = distinct_chat_count
                existing.updated_at = ts
                db.commit()
            else:
                # Create new row
                rollup = EmbeddingMetricsDailyRollup(
                    id=rollup_id,
                    user_id=user_id,
                    date=date,
                    embedding_type=embedding_type,
                    embedding_model_type=embedding_model_type,
                    model_id=model_id,
                    task_count=task_count,
                    total_cost=total_cost,
                    total_input_tokens=total_tokens,
                    distinct_chat_count=distinct_chat_count,
                    created_at=ts,
                    updated_at=ts,
                )
                db.add(rollup)
                db.commit()

            log.debug(
                f"Updated embedding metrics rollup from aggregations: {rollup_id} "
                f"(type={embedding_type}, model={model_id}, "
                f"count={task_count}, cost={total_cost}, tokens={total_tokens})"
            )

            return True

    except Exception as e:
        log.error(f"Error updating rollup from embedding generations: {e}", exc_info=True)
        return False
