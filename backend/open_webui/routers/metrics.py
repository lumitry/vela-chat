import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from decimal import Decimal
import numpy as np

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, and_, or_, case, text
from sqlalchemy.orm import aliased

from open_webui.internal.db import get_db
from open_webui.models.chat_messages import ChatMessage, MetricsDailyRollup
from open_webui.models.tasks import TaskMetricsDailyRollup
from open_webui.models.embeddings import EmbeddingMetricsDailyRollup
from open_webui.models.chats import Chat
from open_webui.models.knowledge import Knowledges
from open_webui.utils.auth import get_verified_user
from open_webui.utils.models import get_all_models
from open_webui.env import SRC_LOG_LEVELS
from open_webui.models.users import UserModel
from open_webui.retrieval.vector.connector import VECTOR_DB_CLIENT
from open_webui.config import VECTOR_DB

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()

# In-memory cache for model ownership map
# Key: user_id, Value: Dict[str, str] mapping model_id -> owned_by
_model_ownership_cache: Dict[str, Dict[str, str]] = {}

# In-memory cache for model name mapping
# Key: user_id, Value: Dict[str, str] mapping model_id -> model_name
_model_names_cache: Dict[str, Dict[str, str]] = {}


# Response Models
class ModelMetricsResponse(BaseModel):
    model_id: str
    model_name: str
    spend: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    message_count: int


class DailyTokenUsageResponse(BaseModel):
    date: str  # ISO format date string
    input_tokens: int
    output_tokens: int
    total_tokens: int


class DailySpendResponse(BaseModel):
    date: str
    cost: float


class ModelDailyTokensResponse(BaseModel):
    date: str
    model_id: str
    model_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int


class ModelDailyCostResponse(BaseModel):
    date: str
    model_id: str
    model_name: str
    cost: float


class CostPerMessageDailyResponse(BaseModel):
    date: str
    avg_cost: float
    message_count: int
    total_cost: float


class MessageCountDailyResponse(BaseModel):
    date: str
    count: int


class ModelPopularityResponse(BaseModel):
    model_id: str
    model_name: str
    chat_count: int
    message_count: int


class CostPerTokenDailyResponse(BaseModel):
    date: str
    avg_cost_per_token: float
    total_tokens: int
    total_cost: float


class TaskGenerationTypesDailyResponse(BaseModel):
    date: str
    task_type: str
    task_count: int


class IndexGrowthDailyResponse(BaseModel):
    date: str
    vector_count: int  # Cumulative count of vectors up to this date


class EmbeddingVisualizationResponse(BaseModel):
    x: List[float]
    y: List[float]
    z: List[float]
    labels: List[str]  # Document names/file names
    collection_names: List[str]  # Which collection each point belongs to


# Helper function to get model ownership map
async def get_model_ownership_map(request: Request, user: UserModel) -> Dict[str, str]:
    """Get mapping of model_id to owned_by (ollama/openai/arena)
    
    Uses in-memory cache since model ownership doesn't change for a given model_id.
    Cache is cleared on server restart (which is fine for the rare case of ownership changes or collision).
    """
    global _model_ownership_cache
    
    # Check cache first
    if user.id in _model_ownership_cache:
        log.debug(f"Model ownership cache HIT for user {user.id}")
        return _model_ownership_cache[user.id]
    
    # Cache miss - fetch from API
    log.debug(f"Model ownership cache MISS for user {user.id}, fetching models...")
    start_time = time.time()
    models = await get_all_models(request, user=user)
    fetch_time = (time.time() - start_time) * 1000
    log.debug(f"Fetched {len(models)} models in {fetch_time:.2f}ms")
    
    ownership_map = {model["id"]: model.get("owned_by", "unknown") for model in models}
    
    # Cache it
    _model_ownership_cache[user.id] = ownership_map
    log.debug(f"Cached model ownership map for user {user.id} ({len(ownership_map)} models)")
    
    return ownership_map


# Helper function to get model name mapping (cached)
async def get_model_names_map(request: Request, user: UserModel) -> Dict[str, str]:
    """Get mapping of model_id to model_name
    
    Uses in-memory cache since model names don't change frequently.
    Cache is cleared on server restart.
    """
    global _model_names_cache
    
    # Check cache first
    if user.id in _model_names_cache:
        log.debug(f"Model names cache HIT for user {user.id}")
        return _model_names_cache[user.id]
    
    # Cache miss - fetch from API
    log.debug(f"Model names cache MISS for user {user.id}, fetching models...")
    start_time = time.time()
    all_models = await get_all_models(request, user=user)
    fetch_time = (time.time() - start_time) * 1000
    log.debug(f"Fetched {len(all_models)} models for names in {fetch_time:.2f}ms")
    
    names_map = {model["id"]: model.get("name", model["id"]) for model in all_models}
    
    # Cache it
    _model_names_cache[user.id] = names_map
    log.debug(f"Cached model names map for user {user.id} ({len(names_map)} models)")
    
    return names_map


# Helper function to convert timestamp to date string (ISO format)
def timestamp_to_date_str(timestamp: int) -> str:
    """Convert Unix timestamp to ISO date string (YYYY-MM-DD) in UTC"""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()


# Helper function to get date range from query params (returns both timestamps and date objects)
def get_date_range(start_date: Optional[str], end_date: Optional[str]) -> tuple[int, int]:
    """Convert date strings to timestamps. Defaults to last 30 days if not provided.
    Validates that start_date <= end_date. For single-day ranges, sets end_ts to end of day.
    All timestamps are in UTC to match database date extraction."""
    if end_date:
        end_date_obj = datetime.fromisoformat(end_date).date()
        # For single-day ranges, include the entire day (end of day) in UTC
        end_dt = datetime.combine(end_date_obj, datetime.max.time(), tzinfo=timezone.utc)
        end_ts = int(end_dt.timestamp())
    else:
        end_ts = int(datetime.now(timezone.utc).timestamp())
    
    if start_date:
        start_date_obj = datetime.fromisoformat(start_date).date()
        # Start of day in UTC
        start_dt = datetime.combine(start_date_obj, datetime.min.time(), tzinfo=timezone.utc)
        start_ts = int(start_dt.timestamp())
    else:
        # Default to 30 days ago in UTC
        start_ts = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp())
    
    # Validate that start <= end
    if start_ts > end_ts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be less than or equal to end_date"
        )
    
    return start_ts, end_ts


# Helper function to get date objects from date strings (for rollup table queries)
def get_date_range_objects(start_date: Optional[str], end_date: Optional[str]) -> tuple[datetime.date, datetime.date]:
    """Convert date strings to date objects. Defaults to last 30 days if not provided."""
    if end_date:
        end_date_obj = datetime.fromisoformat(end_date).date()
    else:
        end_date_obj = datetime.now(timezone.utc).date()
    
    if start_date:
        start_date_obj = datetime.fromisoformat(start_date).date()
    else:
        # Default to 30 days ago
        start_date_obj = (datetime.now(timezone.utc) - timedelta(days=30)).date()
    
    # Validate that start <= end
    if start_date_obj > end_date_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be less than or equal to end_date"
        )
    
    return start_date_obj, end_date_obj


# Helper function to filter by model type
def filter_by_model_type(
    query, model_ownership_map: Dict[str, str], model_type: str, model_id_column
):
    """Filter query by model type (local/external/both)
    """
    if model_type == "local":
        # Only ollama models
        local_model_ids = [
            model_id for model_id, owned_by in model_ownership_map.items()
            if owned_by == "ollama"
        ]
        if local_model_ids:
            return query.filter(model_id_column.in_(local_model_ids))
        else:
            return query.filter(False)  # No local models
    elif model_type == "external":
        # Only external models (openai, not arena)
        external_model_ids = [
            model_id for model_id, owned_by in model_ownership_map.items()
            if owned_by == "openai"
        ]
        if external_model_ids:
            return query.filter(model_id_column.in_(external_model_ids))
        else:
            return query.filter(False)  # No external models
    else:  # both
        return query


@router.get("/models", response_model=List[ModelMetricsResponse])
async def get_model_metrics(
    request: Request,
    limit: int = Query(15, ge=1, le=100),
    model_type: str = Query("both", regex="^(local|external|both)$"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_tasks: bool = Query(True, description="Include task model generations in metrics"),
    include_embeddings: bool = Query(False, description="Include embedding model generations in metrics"),
    user: UserModel = Depends(get_verified_user),
):
    """Get top N models with aggregated metrics"""
    endpoint_start = time.time()
    try:
        start_date_obj, end_date_obj = get_date_range_objects(start_date, end_date)
        
        model_ownership_start = time.time()
        model_ownership_map = await get_model_ownership_map(request, user)
        model_ownership_time = (time.time() - model_ownership_start) * 1000
        log.debug(f"[PERF] /models: get_model_ownership_map took {model_ownership_time:.2f}ms")
        
        db_query_start = time.time()
        with get_db() as db:
            # Query message rollup table
            message_query = (
                db.query(
                    MetricsDailyRollup.model_id,
                    func.sum(MetricsDailyRollup.total_cost).label("total_cost"),
                    func.sum(MetricsDailyRollup.total_input_tokens).label("total_input_tokens"),
                    func.sum(MetricsDailyRollup.total_output_tokens).label("total_output_tokens"),
                    func.sum(MetricsDailyRollup.message_count).label("message_count"),
                )
                .filter(
                    MetricsDailyRollup.user_id == user.id,
                    MetricsDailyRollup.date >= start_date_obj,
                    MetricsDailyRollup.date <= end_date_obj,
                    MetricsDailyRollup.model_id.isnot(None),
                )
                .group_by(MetricsDailyRollup.model_id)
            )
            
            # Filter by model type
            message_query = filter_by_model_type(message_query, model_ownership_map, model_type, MetricsDailyRollup.model_id)
            
            message_results = message_query.all()
            
            # Query task rollup table if include_tasks is True
            task_results = []
            if include_tasks:
                task_query = (
                    db.query(
                        TaskMetricsDailyRollup.model_id,
                        func.sum(TaskMetricsDailyRollup.total_cost).label("total_cost"),
                        func.sum(TaskMetricsDailyRollup.total_input_tokens).label("total_input_tokens"),
                        func.sum(TaskMetricsDailyRollup.total_output_tokens).label("total_output_tokens"),
                        func.sum(TaskMetricsDailyRollup.task_count).label("task_count"),
                    )
                    .filter(
                        TaskMetricsDailyRollup.user_id == user.id,
                        TaskMetricsDailyRollup.date >= start_date_obj,
                        TaskMetricsDailyRollup.date <= end_date_obj,
                    )
                    .group_by(TaskMetricsDailyRollup.model_id)
                )
                
                # Filter by model type based on task_model_type
                if model_type == "local":
                    task_query = task_query.filter(TaskMetricsDailyRollup.task_model_type == "internal")
                elif model_type == "external":
                    task_query = task_query.filter(TaskMetricsDailyRollup.task_model_type == "external")
                # else "both" - no filter
                
                task_results = task_query.all()
            
            # Query embedding rollup table if include_embeddings is True
            embedding_results = []
            if include_embeddings:
                embedding_query = (
                    db.query(
                        EmbeddingMetricsDailyRollup.model_id,
                        func.sum(EmbeddingMetricsDailyRollup.total_cost).label("total_cost"),
                        func.sum(EmbeddingMetricsDailyRollup.total_input_tokens).label("total_input_tokens"),
                        func.sum(EmbeddingMetricsDailyRollup.task_count).label("task_count"),
                    )
                    .filter(
                        EmbeddingMetricsDailyRollup.user_id == user.id,
                        EmbeddingMetricsDailyRollup.date >= start_date_obj,
                        EmbeddingMetricsDailyRollup.date <= end_date_obj,
                    )
                    .group_by(EmbeddingMetricsDailyRollup.model_id)
                )
                
                # Filter by model type based on embedding_model_type
                if model_type == "local":
                    embedding_query = embedding_query.filter(EmbeddingMetricsDailyRollup.embedding_model_type == "internal")
                elif model_type == "external":
                    embedding_query = embedding_query.filter(EmbeddingMetricsDailyRollup.embedding_model_type == "external")
                # else "both" - no filter
                
                embedding_results = embedding_query.all()
            
            # Merge results by model_id
            model_metrics = {}
            for row in message_results:
                model_id = row.model_id
                model_metrics[model_id] = {
                    "model_id": model_id,
                    "total_cost": float(row.total_cost or 0),
                    "total_input_tokens": int(row.total_input_tokens or 0),
                    "total_output_tokens": int(row.total_output_tokens or 0),
                    "message_count": int(row.message_count or 0),
                }
            
            # Add task metrics
            for row in task_results:
                model_id = row.model_id
                if model_id in model_metrics:
                    model_metrics[model_id]["total_cost"] += float(row.total_cost or 0)
                    model_metrics[model_id]["total_input_tokens"] += int(row.total_input_tokens or 0)
                    model_metrics[model_id]["total_output_tokens"] += int(row.total_output_tokens or 0)
                    model_metrics[model_id]["message_count"] += int(row.task_count or 0)  # Add task_count to message_count
                else:
                    model_metrics[model_id] = {
                        "model_id": model_id,
                        "total_cost": float(row.total_cost or 0),
                        "total_input_tokens": int(row.total_input_tokens or 0),
                        "total_output_tokens": int(row.total_output_tokens or 0),
                        "message_count": int(row.task_count or 0),
                    }
            
            # Add embedding metrics (embeddings only have input tokens, no output tokens)
            for row in embedding_results:
                model_id = row.model_id
                if model_id in model_metrics:
                    model_metrics[model_id]["total_cost"] += float(row.total_cost or 0)
                    model_metrics[model_id]["total_input_tokens"] += int(row.total_input_tokens or 0)
                    model_metrics[model_id]["message_count"] += int(row.task_count or 0)  # Add task_count to message_count
                else:
                    model_metrics[model_id] = {
                        "model_id": model_id,
                        "total_cost": float(row.total_cost or 0),
                        "total_input_tokens": int(row.total_input_tokens or 0),
                        "total_output_tokens": 0,  # Embeddings don't have output tokens
                        "message_count": int(row.task_count or 0),
                    }
            
            # Convert to list and sort by total tokens
            results_list = list(model_metrics.values())
            results_list.sort(
                key=lambda x: x["total_input_tokens"] + x["total_output_tokens"],
                reverse=True
            )
            results_list = results_list[:limit]
            
        db_query_time = (time.time() - db_query_start) * 1000
        log.debug(f"[PERF] /models: database query took {db_query_time:.2f}ms, returned {len(results_list)} rows")
        
        # Map model IDs to names (cached)
        model_names_start = time.time()
        model_id_to_name = await get_model_names_map(request, user)
        model_names_time = (time.time() - model_names_start) * 1000
        log.debug(f"[PERF] /models: get_model_names_map took {model_names_time:.2f}ms")
        
        response = []
        for row in results_list:
            model_id = row["model_id"]
            total_input = row["total_input_tokens"]
            total_output = row["total_output_tokens"]
            total_tokens = total_input + total_output
            
            # Skip models with zero tokens
            if total_tokens == 0:
                continue
            
            response.append(
                ModelMetricsResponse(
                    model_id=model_id,
                    model_name=model_id_to_name.get(model_id) or model_id,
                    spend=row["total_cost"],
                    input_tokens=total_input,
                    output_tokens=total_output,
                    total_tokens=total_tokens,
                    message_count=row["message_count"],
                )
            )
        
        total_time = (time.time() - endpoint_start) * 1000
        log.debug(f"[PERF] /models: total endpoint time {total_time:.2f}ms (ownership: {model_ownership_time:.2f}ms, db: {db_query_time:.2f}ms, names: {model_names_time:.2f}ms)")
        
        return response
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/tokens/daily", response_model=List[DailyTokenUsageResponse])
async def get_daily_token_usage(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    model_type: str = Query("both", regex="^(local|external|both)$"),
    include_tasks: bool = Query(True, description="Include task model generations in metrics"),
    include_embeddings: bool = Query(False, description="Include embedding model generations in metrics"),
    user: UserModel = Depends(get_verified_user),
):
    """Get daily token usage (input + output) segmented"""
    endpoint_start = time.time()
    try:
        start_date_obj, end_date_obj = get_date_range_objects(start_date, end_date)
        
        model_ownership_start = time.time()
        model_ownership_map = await get_model_ownership_map(request, user)
        model_ownership_time = (time.time() - model_ownership_start) * 1000
        log.debug(f"[PERF] /tokens/daily: get_model_ownership_map took {model_ownership_time:.2f}ms")
        
        db_query_start = time.time()
        with get_db() as db:
            # Query message rollup table
            message_query = (
                db.query(
                    MetricsDailyRollup.date,
                    func.sum(MetricsDailyRollup.total_input_tokens).label("input_tokens"),
                    func.sum(MetricsDailyRollup.total_output_tokens).label("output_tokens"),
                )
                .filter(
                    MetricsDailyRollup.user_id == user.id,
                    MetricsDailyRollup.date >= start_date_obj,
                    MetricsDailyRollup.date <= end_date_obj,
                    MetricsDailyRollup.model_id.isnot(None),  # Only include model-specific rows
                )
                .group_by(MetricsDailyRollup.date)
            )
            
            # Filter by model type
            message_query = filter_by_model_type(message_query, model_ownership_map, model_type, MetricsDailyRollup.model_id)
            
            message_results = message_query.all()
            
            # Query task rollup table if include_tasks is True
            task_results = []
            if include_tasks:
                task_query = (
                    db.query(
                        TaskMetricsDailyRollup.date,
                        func.sum(TaskMetricsDailyRollup.total_input_tokens).label("input_tokens"),
                        func.sum(TaskMetricsDailyRollup.total_output_tokens).label("output_tokens"),
                    )
                    .filter(
                        TaskMetricsDailyRollup.user_id == user.id,
                        TaskMetricsDailyRollup.date >= start_date_obj,
                        TaskMetricsDailyRollup.date <= end_date_obj,
                    )
                    .group_by(TaskMetricsDailyRollup.date)
                )
                
                # Filter by model type based on task_model_type
                if model_type == "local":
                    task_query = task_query.filter(TaskMetricsDailyRollup.task_model_type == "internal")
                elif model_type == "external":
                    task_query = task_query.filter(TaskMetricsDailyRollup.task_model_type == "external")
                # else "both" - no filter
                
                task_results = task_query.all()
            
            # Query embedding rollup table if include_embeddings is True
            embedding_results = []
            if include_embeddings:
                embedding_query = (
                    db.query(
                        EmbeddingMetricsDailyRollup.date,
                        func.sum(EmbeddingMetricsDailyRollup.total_input_tokens).label("input_tokens"),
                    )
                    .filter(
                        EmbeddingMetricsDailyRollup.user_id == user.id,
                        EmbeddingMetricsDailyRollup.date >= start_date_obj,
                        EmbeddingMetricsDailyRollup.date <= end_date_obj,
                    )
                    .group_by(EmbeddingMetricsDailyRollup.date)
                )
                
                # Filter by model type based on embedding_model_type
                if model_type == "local":
                    embedding_query = embedding_query.filter(EmbeddingMetricsDailyRollup.embedding_model_type == "internal")
                elif model_type == "external":
                    embedding_query = embedding_query.filter(EmbeddingMetricsDailyRollup.embedding_model_type == "external")
                # else "both" - no filter
                
                embedding_results = embedding_query.all()
            
            # Merge results by date
            date_metrics = {}
            for row in message_results:
                date_str = str(row.date)
                date_metrics[date_str] = {
                    "date": date_str,
                    "input_tokens": int(row.input_tokens or 0),
                    "output_tokens": int(row.output_tokens or 0),
                }
            
            # Add task metrics
            for row in task_results:
                date_str = str(row.date)
                if date_str in date_metrics:
                    date_metrics[date_str]["input_tokens"] += int(row.input_tokens or 0)
                    date_metrics[date_str]["output_tokens"] += int(row.output_tokens or 0)
                else:
                    date_metrics[date_str] = {
                        "date": date_str,
                        "input_tokens": int(row.input_tokens or 0),
                        "output_tokens": int(row.output_tokens or 0),
                    }
            
            # Add embedding metrics (embeddings only have input tokens)
            for row in embedding_results:
                date_str = str(row.date)
                if date_str in date_metrics:
                    date_metrics[date_str]["input_tokens"] += int(row.input_tokens or 0)
                else:
                    date_metrics[date_str] = {
                        "date": date_str,
                        "input_tokens": int(row.input_tokens or 0),
                        "output_tokens": 0,
                    }
            
            # Convert to list and sort by date
            results_list = sorted(date_metrics.values(), key=lambda x: x["date"])
            
        db_query_time = (time.time() - db_query_start) * 1000
        log.debug(f"[PERF] /tokens/daily: database query took {db_query_time:.2f}ms, returned {len(results_list)} rows")
        
        response = []
        for row in results_list:
            input_tokens = row["input_tokens"]
            output_tokens = row["output_tokens"]
            
            response.append(
                DailyTokenUsageResponse(
                    date=row["date"],
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                )
            )
        
        total_time = (time.time() - endpoint_start) * 1000
        log.debug(f"[PERF] /tokens/daily: total endpoint time {total_time:.2f}ms (ownership: {model_ownership_time:.2f}ms, db: {db_query_time:.2f}ms)")
        
        return response
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/spend/daily", response_model=List[DailySpendResponse])
async def get_daily_spend(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    model_type: str = Query("both", regex="^(local|external|both)$"),
    include_tasks: bool = Query(True, description="Include task model generations in metrics"),
    include_embeddings: bool = Query(False, description="Include embedding model generations in metrics"),
    user: UserModel = Depends(get_verified_user),
):
    """Get daily spending"""
    endpoint_start = time.time()
    try:
        start_date_obj, end_date_obj = get_date_range_objects(start_date, end_date)
        
        model_ownership_start = time.time()
        model_ownership_map = await get_model_ownership_map(request, user)
        model_ownership_time = (time.time() - model_ownership_start) * 1000
        log.debug(f"[PERF] /spend/daily: get_model_ownership_map took {model_ownership_time:.2f}ms")
        
        db_query_start = time.time()
        with get_db() as db:
            # Query message rollup table
            message_query = (
                db.query(
                    MetricsDailyRollup.date,
                    func.sum(MetricsDailyRollup.total_cost).label("total_cost"),
                )
                .filter(
                    MetricsDailyRollup.user_id == user.id,
                    MetricsDailyRollup.date >= start_date_obj,
                    MetricsDailyRollup.date <= end_date_obj,
                    MetricsDailyRollup.model_id.isnot(None),  # Only include model-specific rows
                )
                .group_by(MetricsDailyRollup.date)
            )
            
            message_query = filter_by_model_type(message_query, model_ownership_map, model_type, MetricsDailyRollup.model_id)
            
            message_results = message_query.all()
            
            # Query task rollup table if include_tasks is True
            task_results = []
            if include_tasks:
                task_query = (
                    db.query(
                        TaskMetricsDailyRollup.date,
                        func.sum(TaskMetricsDailyRollup.total_cost).label("total_cost"),
                    )
                    .filter(
                        TaskMetricsDailyRollup.user_id == user.id,
                        TaskMetricsDailyRollup.date >= start_date_obj,
                        TaskMetricsDailyRollup.date <= end_date_obj,
                    )
                    .group_by(TaskMetricsDailyRollup.date)
                )
                
                # Filter by model type based on task_model_type
                if model_type == "local":
                    task_query = task_query.filter(TaskMetricsDailyRollup.task_model_type == "internal")
                elif model_type == "external":
                    task_query = task_query.filter(TaskMetricsDailyRollup.task_model_type == "external")
                # else "both" - no filter
                
                task_results = task_query.all()
            
            # Query embedding rollup table if include_embeddings is True
            embedding_results = []
            if include_embeddings:
                embedding_query = (
                    db.query(
                        EmbeddingMetricsDailyRollup.date,
                        func.sum(EmbeddingMetricsDailyRollup.total_cost).label("total_cost"),
                    )
                    .filter(
                        EmbeddingMetricsDailyRollup.user_id == user.id,
                        EmbeddingMetricsDailyRollup.date >= start_date_obj,
                        EmbeddingMetricsDailyRollup.date <= end_date_obj,
                    )
                    .group_by(EmbeddingMetricsDailyRollup.date)
                )
                
                # Filter by model type based on embedding_model_type
                if model_type == "local":
                    embedding_query = embedding_query.filter(EmbeddingMetricsDailyRollup.embedding_model_type == "internal")
                elif model_type == "external":
                    embedding_query = embedding_query.filter(EmbeddingMetricsDailyRollup.embedding_model_type == "external")
                # else "both" - no filter
                
                embedding_results = embedding_query.all()
            
            # Merge results by date
            date_metrics = {}
            for row in message_results:
                date_str = str(row.date)
                date_metrics[date_str] = {
                    "date": date_str,
                    "cost": float(row.total_cost or 0),
                }
            
            # Add task metrics
            for row in task_results:
                date_str = str(row.date)
                if date_str in date_metrics:
                    date_metrics[date_str]["cost"] += float(row.total_cost or 0)
                else:
                    date_metrics[date_str] = {
                        "date": date_str,
                        "cost": float(row.total_cost or 0),
                    }
            
            # Add embedding metrics
            for row in embedding_results:
                date_str = str(row.date)
                if date_str in date_metrics:
                    date_metrics[date_str]["cost"] += float(row.total_cost or 0)
                else:
                    date_metrics[date_str] = {
                        "date": date_str,
                        "cost": float(row.total_cost or 0),
                    }
            
            # Convert to list and sort by date
            results_list = sorted(date_metrics.values(), key=lambda x: x["date"])
            
        db_query_time = (time.time() - db_query_start) * 1000
        log.debug(f"[PERF] /spend/daily: database query took {db_query_time:.2f}ms, returned {len(results_list)} rows")
        
        response = []
        for row in results_list:
            response.append(
                DailySpendResponse(
                    date=row["date"],
                    cost=row["cost"],
                )
            )
        
        total_time = (time.time() - endpoint_start) * 1000
        log.debug(f"[PERF] /spend/daily: total endpoint time {total_time:.2f}ms (ownership: {model_ownership_time:.2f}ms, db: {db_query_time:.2f}ms)")
        
        return response
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/tokens/model/daily", response_model=List[ModelDailyTokensResponse])
async def get_model_daily_tokens(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    model_type: str = Query("both", regex="^(local|external|both)$"),
    limit: int = Query(10, ge=1, le=50),
    user: UserModel = Depends(get_verified_user),
):
    """Get tokens per model per day"""
    endpoint_start = time.time()
    try:
        start_date_obj, end_date_obj = get_date_range_objects(start_date, end_date)
        
        model_ownership_start = time.time()
        model_ownership_map = await get_model_ownership_map(request, user)
        model_ownership_time = (time.time() - model_ownership_start) * 1000
        log.debug(f"[PERF] /tokens/model/daily: get_model_ownership_map took {model_ownership_time:.2f}ms")
        
        # Map model IDs to names (cached)
        model_names_start = time.time()
        model_id_to_name = await get_model_names_map(request, user)
        model_names_time = (time.time() - model_names_start) * 1000
        log.debug(f"[PERF] /tokens/model/daily: get_model_names_map took {model_names_time:.2f}ms")
        
        db_query_start = time.time()
        with get_db() as db:
            # First, get top N models by total tokens from rollup table
            top_models_query = (
                db.query(
                    MetricsDailyRollup.model_id,
                    func.sum(MetricsDailyRollup.total_input_tokens + MetricsDailyRollup.total_output_tokens).label("total_tokens"),
                )
                .filter(
                    MetricsDailyRollup.user_id == user.id,
                    MetricsDailyRollup.date >= start_date_obj,
                    MetricsDailyRollup.date <= end_date_obj,
                    MetricsDailyRollup.model_id.isnot(None),
                )
                .group_by(MetricsDailyRollup.model_id)
            )
            
            # Filter by model type BEFORE order_by and limit
            top_models_query = filter_by_model_type(top_models_query, model_ownership_map, model_type, MetricsDailyRollup.model_id)
            
            top_models_query = (
                top_models_query
                .order_by(func.sum(MetricsDailyRollup.total_input_tokens + MetricsDailyRollup.total_output_tokens).desc())
                .limit(limit)
            )
            top_model_ids = [row.model_id for row in top_models_query.all()]
            
            if not top_model_ids:
                db_query_time = (time.time() - db_query_start) * 1000
                log.debug(f"[PERF] /tokens/model/daily: database query took {db_query_time:.2f}ms, no models found")
                total_time = (time.time() - endpoint_start) * 1000
                log.debug(f"[PERF] /tokens/model/daily: total endpoint time {total_time:.2f}ms")
                return []
            
            # Now get daily breakdown for these models from rollup table
            query = (
                db.query(
                    MetricsDailyRollup.date,
                    MetricsDailyRollup.model_id,
                    func.sum(MetricsDailyRollup.total_input_tokens).label("input_tokens"),
                    func.sum(MetricsDailyRollup.total_output_tokens).label("output_tokens"),
                )
                .filter(
                    MetricsDailyRollup.user_id == user.id,
                    MetricsDailyRollup.date >= start_date_obj,
                    MetricsDailyRollup.date <= end_date_obj,
                    MetricsDailyRollup.model_id.in_(top_model_ids),
                )
                .group_by(MetricsDailyRollup.date, MetricsDailyRollup.model_id)
                .order_by(MetricsDailyRollup.date, MetricsDailyRollup.model_id)
            )
            
            results = query.all()
        db_query_time = (time.time() - db_query_start) * 1000
        log.debug(f"[PERF] /tokens/model/daily: database query took {db_query_time:.2f}ms, returned {len(results)} rows")
        
        response = []
        for row in results:
            date_str = str(row.date)
            input_tokens = int(row.input_tokens or 0)
            output_tokens = int(row.output_tokens or 0)
            
            response.append(
                ModelDailyTokensResponse(
                    date=date_str,
                    model_id=row.model_id,
                    model_name=model_id_to_name.get(row.model_id) or row.model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                )
            )
        
        total_time = (time.time() - endpoint_start) * 1000
        log.debug(f"[PERF] /tokens/model/daily: total endpoint time {total_time:.2f}ms (ownership: {model_ownership_time:.2f}ms, names: {model_names_time:.2f}ms, db: {db_query_time:.2f}ms)")
        
        return response
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/cost/model/daily", response_model=List[ModelDailyCostResponse])
async def get_model_daily_cost(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    model_type: str = Query("both", regex="^(local|external|both)$"),
    limit: int = Query(10, ge=1, le=50),
    user: UserModel = Depends(get_verified_user),
):
    """Get cost per model per day"""
    endpoint_start = time.time()
    try:
        start_date_obj, end_date_obj = get_date_range_objects(start_date, end_date)
        
        model_ownership_start = time.time()
        model_ownership_map = await get_model_ownership_map(request, user)
        model_ownership_time = (time.time() - model_ownership_start) * 1000
        log.debug(f"[PERF] /cost/model/daily: get_model_ownership_map took {model_ownership_time:.2f}ms")
        
        # Map model IDs to names (cached)
        model_names_start = time.time()
        model_id_to_name = await get_model_names_map(request, user)
        model_names_time = (time.time() - model_names_start) * 1000
        log.debug(f"[PERF] /cost/model/daily: get_model_names_map took {model_names_time:.2f}ms")
        
        db_query_start = time.time()
        with get_db() as db:
            # First, get top N models by total cost from rollup table
            top_models_query = (
                db.query(
                    MetricsDailyRollup.model_id,
                    func.sum(MetricsDailyRollup.total_cost).label("total_cost"),
                )
                .filter(
                    MetricsDailyRollup.user_id == user.id,
                    MetricsDailyRollup.date >= start_date_obj,
                    MetricsDailyRollup.date <= end_date_obj,
                    MetricsDailyRollup.model_id.isnot(None),
                    MetricsDailyRollup.total_cost.isnot(None),  # Only models with cost data
                )
                .group_by(MetricsDailyRollup.model_id)
            )
            
            # Filter by model type BEFORE order_by and limit
            top_models_query = filter_by_model_type(top_models_query, model_ownership_map, model_type, MetricsDailyRollup.model_id)
            
            top_models_query = (
                top_models_query
                .order_by(func.sum(MetricsDailyRollup.total_cost).desc())
                .limit(limit)
            )
            top_model_ids = [row.model_id for row in top_models_query.all()]
            
            if not top_model_ids:
                db_query_time = (time.time() - db_query_start) * 1000
                log.debug(f"[PERF] /cost/model/daily: database query took {db_query_time:.2f}ms, no models found")
                total_time = (time.time() - endpoint_start) * 1000
                log.debug(f"[PERF] /cost/model/daily: total endpoint time {total_time:.2f}ms")
                return []
            
            # Now get daily breakdown for these models from rollup table
            query = (
                db.query(
                    MetricsDailyRollup.date,
                    MetricsDailyRollup.model_id,
                    func.sum(MetricsDailyRollup.total_cost).label("cost"),
                )
                .filter(
                    MetricsDailyRollup.user_id == user.id,
                    MetricsDailyRollup.date >= start_date_obj,
                    MetricsDailyRollup.date <= end_date_obj,
                    MetricsDailyRollup.model_id.in_(top_model_ids),
                )
                .group_by(MetricsDailyRollup.date, MetricsDailyRollup.model_id)
                .order_by(MetricsDailyRollup.date, MetricsDailyRollup.model_id)
            )
            
            results = query.all()
        db_query_time = (time.time() - db_query_start) * 1000
        log.debug(f"[PERF] /cost/model/daily: database query took {db_query_time:.2f}ms, returned {len(results)} rows")
        
        response = []
        for row in results:
            date_str = str(row.date)
            cost = float(row.cost or 0)
            
            response.append(
                ModelDailyCostResponse(
                    date=date_str,
                    model_id=row.model_id,
                    model_name=model_id_to_name.get(row.model_id) or row.model_id,
                    cost=cost,
                )
            )
        
        total_time = (time.time() - endpoint_start) * 1000
        log.debug(f"[PERF] /cost/model/daily: total endpoint time {total_time:.2f}ms (ownership: {model_ownership_time:.2f}ms, names: {model_names_time:.2f}ms, db: {db_query_time:.2f}ms)")
        
        return response
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/cost/message/daily", response_model=List[CostPerMessageDailyResponse])
async def get_cost_per_message_daily(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    model_type: str = Query("both", regex="^(local|external|both)$"),
    user: UserModel = Depends(get_verified_user),
):
    """Get average cost per message over time"""
    endpoint_start = time.time()
    try:
        start_date_obj, end_date_obj = get_date_range_objects(start_date, end_date)
        
        model_ownership_start = time.time()
        model_ownership_map = await get_model_ownership_map(request, user)
        model_ownership_time = (time.time() - model_ownership_start) * 1000
        log.debug(f"[PERF] /cost/message/daily: get_model_ownership_map took {model_ownership_time:.2f}ms")
        
        db_query_start = time.time()
        with get_db() as db:
            # Query rollup table - calculate avg cost from total_cost / message_count
            query = (
                db.query(
                    MetricsDailyRollup.date,
                    func.sum(MetricsDailyRollup.total_cost).label("total_cost"),
                    func.sum(MetricsDailyRollup.message_count).label("message_count"),
                )
                .filter(
                    MetricsDailyRollup.user_id == user.id,
                    MetricsDailyRollup.date >= start_date_obj,
                    MetricsDailyRollup.date <= end_date_obj,
                    MetricsDailyRollup.model_id.isnot(None),  # Only include model-specific rows
                )
                .group_by(MetricsDailyRollup.date)
                .order_by(MetricsDailyRollup.date)
            )
            
            query = filter_by_model_type(query, model_ownership_map, model_type, MetricsDailyRollup.model_id)
            
            results = query.all()
        db_query_time = (time.time() - db_query_start) * 1000
        log.debug(f"[PERF] /cost/message/daily: database query took {db_query_time:.2f}ms, returned {len(results)} rows")
        
        response = []
        for row in results:
            date_str = str(row.date)
            total_cost = float(row.total_cost or 0)
            message_count = int(row.message_count or 0)
            avg_cost = (total_cost / message_count) if message_count > 0 else 0.0
            
            response.append(
                CostPerMessageDailyResponse(
                    date=date_str,
                    avg_cost=avg_cost,
                    message_count=message_count,
                    total_cost=total_cost,
                )
            )
        
        total_time = (time.time() - endpoint_start) * 1000
        log.debug(f"[PERF] /cost/message/daily: total endpoint time {total_time:.2f}ms (ownership: {model_ownership_time:.2f}ms, db: {db_query_time:.2f}ms)")
        
        return response
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/messages/daily", response_model=List[MessageCountDailyResponse])
async def get_message_count_daily(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: UserModel = Depends(get_verified_user),
):
    """Get message count per day"""
    endpoint_start = time.time()
    try:
        start_date_obj, end_date_obj = get_date_range_objects(start_date, end_date)
        
        db_query_start = time.time()
        with get_db() as db:
            # Query rollup table directly - sum message_count across all models per day
            results = (
                db.query(
                    MetricsDailyRollup.date,
                    func.sum(MetricsDailyRollup.message_count).label("count"),
                )
                .filter(
                    MetricsDailyRollup.user_id == user.id,
                    MetricsDailyRollup.date >= start_date_obj,
                    MetricsDailyRollup.date <= end_date_obj,
                )
                .group_by(MetricsDailyRollup.date)
                .order_by(MetricsDailyRollup.date)
                .all()
            )
        db_query_time = (time.time() - db_query_start) * 1000
        log.debug(f"[PERF] /messages/daily: database query took {db_query_time:.2f}ms, returned {len(results)} rows")
        
        response = []
        for row in results:
            date_str = str(row.date)
            
            response.append(
                MessageCountDailyResponse(
                    date=date_str,
                    count=int(row.count or 0),
                )
            )
        
        total_time = (time.time() - endpoint_start) * 1000
        log.debug(f"[PERF] /messages/daily: total endpoint time {total_time:.2f}ms (db: {db_query_time:.2f}ms)")
        
        return response
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/models/popularity", response_model=List[ModelPopularityResponse])
async def get_model_popularity(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    model_type: str = Query("both", regex="^(local|external|both)$"),
    limit: int = Query(15, ge=1, le=100),
    user: UserModel = Depends(get_verified_user),
):
    """Get model popularity (number of chats using each model)"""
    endpoint_start = time.time()
    try:
        start_date_obj, end_date_obj = get_date_range_objects(start_date, end_date)
        
        model_ownership_start = time.time()
        model_ownership_map = await get_model_ownership_map(request, user)
        model_ownership_time = (time.time() - model_ownership_start) * 1000
        log.debug(f"[PERF] /models/popularity: get_model_ownership_map took {model_ownership_time:.2f}ms")
        
        # Map model IDs to names (cached)
        model_names_start = time.time()
        model_id_to_name = await get_model_names_map(request, user)
        model_names_time = (time.time() - model_names_start) * 1000
        log.debug(f"[PERF] /models/popularity: get_model_names_map took {model_names_time:.2f}ms")
        
        db_query_start = time.time()
        with get_db() as db:
            # Query rollup table - use distinct_chat_count (max per day) and sum message_count
            # Note: distinct_chat_count is per day, so we need to take max or sum depending on interpretation
            # For popularity, we want total unique chats, so we'll sum distinct_chat_count (which represents unique chats per day)
            # Actually, distinct_chat_count is already the count of distinct chats for that day/model combo
            # We should use MAX to get the maximum distinct chats across days, or sum if we want cumulative
            # For popularity ranking, let's use MAX to get the peak usage
            query = (
                db.query(
                    MetricsDailyRollup.model_id,
                    func.max(MetricsDailyRollup.distinct_chat_count).label("chat_count"),
                    func.sum(MetricsDailyRollup.message_count).label("message_count"),
                )
                .filter(
                    MetricsDailyRollup.user_id == user.id,
                    MetricsDailyRollup.date >= start_date_obj,
                    MetricsDailyRollup.date <= end_date_obj,
                    MetricsDailyRollup.model_id.isnot(None),
                )
                .group_by(MetricsDailyRollup.model_id)
                .order_by(func.max(MetricsDailyRollup.distinct_chat_count).desc())
            )
            
            query = filter_by_model_type(query, model_ownership_map, model_type, MetricsDailyRollup.model_id)
            
            results = query.limit(limit).all()
        db_query_time = (time.time() - db_query_start) * 1000
        log.debug(f"[PERF] /models/popularity: database query took {db_query_time:.2f}ms, returned {len(results)} rows")
        
        response = []
        for row in results:
            response.append(
                ModelPopularityResponse(
                    model_id=row.model_id,
                    model_name=model_id_to_name.get(row.model_id) or row.model_id,
                    chat_count=int(row.chat_count or 0),
                    message_count=int(row.message_count or 0),
                )
            )
        
        total_time = (time.time() - endpoint_start) * 1000
        log.debug(f"[PERF] /models/popularity: total endpoint time {total_time:.2f}ms (ownership: {model_ownership_time:.2f}ms, names: {model_names_time:.2f}ms, db: {db_query_time:.2f}ms)")
        
        return response
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/cost/token/daily", response_model=List[CostPerTokenDailyResponse])
async def get_cost_per_token_daily(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    model_type: str = Query("both", regex="^(local|external|both)$"),
    user: UserModel = Depends(get_verified_user),
):
    """Get cost per token trend"""
    endpoint_start = time.time()
    try:
        start_date_obj, end_date_obj = get_date_range_objects(start_date, end_date)
        
        model_ownership_start = time.time()
        model_ownership_map = await get_model_ownership_map(request, user)
        model_ownership_time = (time.time() - model_ownership_start) * 1000
        log.debug(f"[PERF] /cost/token/daily: get_model_ownership_map took {model_ownership_time:.2f}ms")
        
        db_query_start = time.time()
        with get_db() as db:
            # Query rollup table directly
            query = (
                db.query(
                    MetricsDailyRollup.date,
                    func.sum(MetricsDailyRollup.total_cost).label("total_cost"),
                    func.sum(MetricsDailyRollup.total_input_tokens + MetricsDailyRollup.total_output_tokens).label("total_tokens"),
                )
                .filter(
                    MetricsDailyRollup.user_id == user.id,
                    MetricsDailyRollup.date >= start_date_obj,
                    MetricsDailyRollup.date <= end_date_obj,
                    MetricsDailyRollup.model_id.isnot(None),  # Only include model-specific rows
                )
                .group_by(MetricsDailyRollup.date)
                .order_by(MetricsDailyRollup.date)
            )
            
            query = filter_by_model_type(query, model_ownership_map, model_type, MetricsDailyRollup.model_id)
            
            results = query.all()
        db_query_time = (time.time() - db_query_start) * 1000
        log.debug(f"[PERF] /cost/token/daily: database query took {db_query_time:.2f}ms, returned {len(results)} rows")
        
        response = []
        for row in results:
            date_str = str(row.date)
            total_cost = float(row.total_cost or 0)
            total_tokens = int(row.total_tokens or 0)
            # Calculate cost per 1M tokens (multiply by 1,000,000)
            avg_cost_per_token = (total_cost / total_tokens * 1000000) if total_tokens > 0 else 0.0
            
            response.append(
                CostPerTokenDailyResponse(
                    date=date_str,
                    avg_cost_per_token=avg_cost_per_token,
                    total_tokens=total_tokens,
                    total_cost=total_cost,
                )
            )
        
        total_time = (time.time() - endpoint_start) * 1000
        log.debug(f"[PERF] /cost/token/daily: total endpoint time {total_time:.2f}ms (ownership: {model_ownership_time:.2f}ms, db: {db_query_time:.2f}ms)")
        
        return response
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/tasks/types/daily", response_model=List[TaskGenerationTypesDailyResponse])
async def get_task_generation_types_daily(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    model_type: str = Query("both", regex="^(local|external|both)$"),
    include_embeddings: bool = Query(False, description="Include embedding types in task types chart"),
    user: UserModel = Depends(get_verified_user),
):
    """Get task generation types per day (and optionally embedding types)"""
    endpoint_start = time.time()
    try:
        start_date_obj, end_date_obj = get_date_range_objects(start_date, end_date)
        
        db_query_start = time.time()
        with get_db() as db:
            # Query task types
            query = (
                db.query(
                    TaskMetricsDailyRollup.date,
                    TaskMetricsDailyRollup.task_type,
                    func.sum(TaskMetricsDailyRollup.task_count).label("task_count"),
                )
                .filter(
                    TaskMetricsDailyRollup.user_id == user.id,
                    TaskMetricsDailyRollup.date >= start_date_obj,
                    TaskMetricsDailyRollup.date <= end_date_obj,
                )
                .group_by(TaskMetricsDailyRollup.date, TaskMetricsDailyRollup.task_type)
                .order_by(TaskMetricsDailyRollup.date, TaskMetricsDailyRollup.task_type)
            )
            
            # Filter by model type based on task_model_type
            if model_type == "local":
                query = query.filter(TaskMetricsDailyRollup.task_model_type == "internal")
            elif model_type == "external":
                query = query.filter(TaskMetricsDailyRollup.task_model_type == "external")
            # else "both" - no filter
            
            task_results = query.all()
            
            # Query embedding types if include_embeddings is True
            embedding_results = []
            if include_embeddings:
                embedding_query = (
                    db.query(
                        EmbeddingMetricsDailyRollup.date,
                        EmbeddingMetricsDailyRollup.embedding_type.label("task_type"),  # Use embedding_type as task_type
                        func.sum(EmbeddingMetricsDailyRollup.task_count).label("task_count"),
                    )
                    .filter(
                        EmbeddingMetricsDailyRollup.user_id == user.id,
                        EmbeddingMetricsDailyRollup.date >= start_date_obj,
                        EmbeddingMetricsDailyRollup.date <= end_date_obj,
                    )
                    .group_by(EmbeddingMetricsDailyRollup.date, EmbeddingMetricsDailyRollup.embedding_type)
                    .order_by(EmbeddingMetricsDailyRollup.date, EmbeddingMetricsDailyRollup.embedding_type)
                )
                
                # Filter by model type based on embedding_model_type
                if model_type == "local":
                    embedding_query = embedding_query.filter(EmbeddingMetricsDailyRollup.embedding_model_type == "internal")
                elif model_type == "external":
                    embedding_query = embedding_query.filter(EmbeddingMetricsDailyRollup.embedding_model_type == "external")
                # else "both" - no filter
                
                embedding_results = embedding_query.all()
            
        db_query_time = (time.time() - db_query_start) * 1000
        log.debug(f"[PERF] /tasks/types/daily: database query took {db_query_time:.2f}ms, returned {len(task_results)} task rows and {len(embedding_results)} embedding rows")
        
        # Merge results by date and type
        type_metrics = {}
        for row in task_results:
            date_str = str(row.date)
            key = (date_str, row.task_type)
            if key not in type_metrics:
                type_metrics[key] = {
                    "date": date_str,
                    "task_type": row.task_type,
                    "task_count": 0,
                }
            type_metrics[key]["task_count"] += int(row.task_count or 0)
        
        # Add embedding types
        for row in embedding_results:
            date_str = str(row.date)
            key = (date_str, row.task_type)  # task_type is actually embedding_type here
            if key not in type_metrics:
                type_metrics[key] = {
                    "date": date_str,
                    "task_type": row.task_type,
                    "task_count": 0,
                }
            type_metrics[key]["task_count"] += int(row.task_count or 0)
        
        # Convert to list and sort by date, then type
        response = sorted(type_metrics.values(), key=lambda x: (x["date"], x["task_type"]))
        
        total_time = (time.time() - endpoint_start) * 1000
        log.debug(f"[PERF] /tasks/types/daily: total endpoint time {total_time:.2f}ms (db: {db_query_time:.2f}ms)")
        
        return response
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/index/growth/daily", response_model=List[IndexGrowthDailyResponse])
async def get_index_growth_daily(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: UserModel = Depends(get_verified_user),
):
    """Get index growth over time (cumulative vector count per day)
    
    This uses embedding generations as a proxy for vector count, since each embedding
    generation typically corresponds to vectors being added to the index.
    """
    endpoint_start = time.time()
    try:
        start_date_obj, end_date_obj = get_date_range_objects(start_date, end_date)
        
        db_query_start = time.time()
        with get_db() as db:
            # Query embedding rollup table to get cumulative counts
            # We'll sum task_count (which represents embedding generations) up to each date
            query = (
                db.query(
                    EmbeddingMetricsDailyRollup.date,
                    func.sum(EmbeddingMetricsDailyRollup.task_count).label("daily_count"),
                )
                .filter(
                    EmbeddingMetricsDailyRollup.user_id == user.id,
                    EmbeddingMetricsDailyRollup.date >= start_date_obj,
                    EmbeddingMetricsDailyRollup.date <= end_date_obj,
                )
                .group_by(EmbeddingMetricsDailyRollup.date)
                .order_by(EmbeddingMetricsDailyRollup.date)
            )
            
            daily_results = query.all()
            
            # Calculate cumulative counts
            cumulative_count = 0
            response = []
            
            # First, get the count before the start date to establish baseline
            baseline_query = (
                db.query(
                    func.sum(EmbeddingMetricsDailyRollup.task_count).label("total_count"),
                )
                .filter(
                    EmbeddingMetricsDailyRollup.user_id == user.id,
                    EmbeddingMetricsDailyRollup.date < start_date_obj,
                )
            )
            baseline_result = baseline_query.first()
            if baseline_result and baseline_result.total_count:
                cumulative_count = int(baseline_result.total_count or 0)
            
            # Now add daily counts to get cumulative
            for row in daily_results:
                date_str = str(row.date)
                daily_count = int(row.daily_count or 0)
                cumulative_count += daily_count
                
                response.append(
                    IndexGrowthDailyResponse(
                        date=date_str,
                        vector_count=cumulative_count,
                    )
                )
            
        db_query_time = (time.time() - db_query_start) * 1000
        log.debug(f"[PERF] /index/growth/daily: database query took {db_query_time:.2f}ms, returned {len(response)} rows")
        
        total_time = (time.time() - endpoint_start) * 1000
        log.debug(f"[PERF] /index/growth/daily: total endpoint time {total_time:.2f}ms (db: {db_query_time:.2f}ms)")
        
        return response
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/embeddings/visualize", response_model=EmbeddingVisualizationResponse)
async def get_embeddings_visualization(
    request: Request,
    user: UserModel = Depends(get_verified_user),
):
    """Get embeddings visualization data (3D t-SNE projection)
    
    Fetches all embeddings from user's knowledge bases, runs t-SNE to reduce to 3D,
    and returns coordinates for 3D visualization.
    
    Note: Currently only supports ChromaDB. Other vector DBs may need additional implementation.
    """
    endpoint_start = time.time()
    try:
        # Check if sklearn is available
        try:
            from sklearn.manifold import TSNE
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="scikit-learn is required for embeddings visualization. Please install it: pip install scikit-learn"
            )
        
        # Check if we're using ChromaDB (for now, this is the only supported DB)
        if VECTOR_DB != "chroma":
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"Embeddings visualization is currently only supported for ChromaDB. Current vector DB: {VECTOR_DB}"
            )
        
        log.info(f"Starting embeddings visualization for user {user.id}")
        
        # Get all knowledge bases for the user
        knowledge_bases = Knowledges.get_knowledge_bases_by_user_id(user.id, "read")
        collection_names = [kb.id for kb in knowledge_bases if kb.id]
        
        if not collection_names:
            # Return empty response if no collections
            return EmbeddingVisualizationResponse(
                x=[],
                y=[],
                z=[],
                labels=[],
                collection_names=[]
            )
        
        log.info(f"Found {len(collection_names)} collections for user {user.id}")
        
        # Fetch all embeddings from collections
        all_embeddings = []
        all_labels = []
        all_collection_names = []
        
        # Use ChromaDB client directly to get embeddings
        if hasattr(VECTOR_DB_CLIENT, 'client'):
            chroma_client = VECTOR_DB_CLIENT.client
            
            # Get all actual collections from ChromaDB
            try:
                actual_collections = chroma_client.list_collections()
                actual_collection_names = [col.name for col in actual_collections] if actual_collections else []
                log.debug(f"ChromaDB has {len(actual_collection_names)} actual collections: {actual_collection_names}")
            except Exception as e:
                log.warning(f"Error listing ChromaDB collections: {e}")
                actual_collection_names = []
            
            for collection_name in collection_names:
                try:
                    # Check both has_collection and if it's in the actual list
                    if collection_name not in actual_collection_names:
                        log.debug(f"Collection {collection_name} does not exist in ChromaDB, skipping")
                        continue
                    
                    if not VECTOR_DB_CLIENT.has_collection(collection_name):
                        log.debug(f"Collection {collection_name} failed has_collection check, but exists in list, trying anyway...")
                    
                    collection = chroma_client.get_collection(name=collection_name)
                    # Get all items with embeddings included
                    # ChromaDB's get() method accepts include parameter as a list
                    result = collection.get(include=['embeddings', 'documents', 'metadatas'])  # type: ignore
                    
                    # Check if result exists and has embeddings (handle numpy arrays properly)
                    if result and 'embeddings' in result:
                        embeddings = result['embeddings']
                        # Check if embeddings exists and has items (avoid numpy boolean ambiguity)
                        # Must check is not None first, then length, to avoid evaluating numpy array as boolean
                        if embeddings is not None:
                            try:
                                embedding_count = len(embeddings)
                            except (TypeError, AttributeError):
                                embedding_count = 0
                            
                            if embedding_count > 0:
                                ids = result.get('ids', [])
                                metadatas = result.get('metadatas') or []
                                documents = result.get('documents', [])
                                
                                log.debug(f"Collection {collection_name}: {embedding_count} embeddings")
                                
                                # Handle both numpy arrays and lists
                                # If it's a numpy array, convert to list of lists
                                if isinstance(embeddings, np.ndarray):
                                    embeddings_list = embeddings.tolist()
                                elif isinstance(embeddings, list):
                                    embeddings_list = embeddings
                                else:
                                    embeddings_list = []
                                
                                for idx, embedding in enumerate(embeddings_list):
                                    # Check if embedding exists and is not None/empty
                                    if embedding is not None and isinstance(embedding, (list, np.ndarray)) and len(embedding) > 0:
                                        # Convert to list if it's a numpy array
                                        if isinstance(embedding, np.ndarray):
                                            embedding = embedding.tolist()
                                        all_embeddings.append(embedding)
                                        
                                        # Get label from metadata (file name) or document ID
                                        metadata = metadatas[idx] if metadatas and idx < len(metadatas) else {}
                                        label = ''
                                        if isinstance(metadata, dict):
                                            label = metadata.get('name', '') or metadata.get('file_id', '')
                                        if not label and ids and idx < len(ids):
                                            label = ids[idx]
                                        if not label:
                                            label = f"doc_{idx}"
                                        all_labels.append(str(label))
                                        all_collection_names.append(collection_name)
                    
                except Exception as e:
                    log.warning(f"Error fetching embeddings from collection {collection_name}: {e}", exc_info=True)
                    continue
        
        if not all_embeddings:
            log.warning(f"No embeddings found for user {user.id}")
            return EmbeddingVisualizationResponse(
                x=[],
                y=[],
                z=[],
                labels=[],
                collection_names=[]
            )
        
        log.info(f"Total embeddings to process: {len(all_embeddings)}")
        
        # Convert to numpy array for t-SNE
        embeddings_array = np.array(all_embeddings)
        
        # Run t-SNE to reduce to 3D
        log.info(f"Running t-SNE on {len(embeddings_array)} embeddings (dimension: {embeddings_array.shape[1]})...")
        tsne_start = time.time()
        
        # Use a reasonable perplexity based on sample size
        perplexity = min(30, max(5, len(embeddings_array) - 1))
        
        tsne = TSNE(
            n_components=3,
            random_state=42,
            perplexity=perplexity,
            max_iter=1000,
            verbose=1 if log.level <= logging.DEBUG else 0
        )
        projections = tsne.fit_transform(embeddings_array)
        
        tsne_time = time.time() - tsne_start
        log.info(f"t-SNE completed in {tsne_time:.2f}s")
        
        # Extract x, y, z coordinates
        x_coords = projections[:, 0].tolist()
        y_coords = projections[:, 1].tolist()
        z_coords = projections[:, 2].tolist()
        
        total_time = (time.time() - endpoint_start) * 1000
        log.info(f"[PERF] /embeddings/visualize: total time {total_time:.2f}ms (t-SNE: {tsne_time*1000:.2f}ms)")
        
        return EmbeddingVisualizationResponse(
            x=x_coords,
            y=y_coords,
            z=z_coords,
            labels=all_labels,
            collection_names=all_collection_names
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating embeddings visualization: {str(e)}"
        )

