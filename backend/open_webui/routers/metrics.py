import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, and_, or_, case, text
from sqlalchemy.orm import aliased

from open_webui.internal.db import get_db
from open_webui.models.chat_messages import ChatMessage, MetricsDailyRollup
from open_webui.models.chats import Chat
from open_webui.utils.auth import get_verified_user
from open_webui.utils.models import get_all_models
from open_webui.env import SRC_LOG_LEVELS
from open_webui.models.users import UserModel

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
            # Query rollup table directly - aggregate across date range
            query = (
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
            query = filter_by_model_type(query, model_ownership_map, model_type, MetricsDailyRollup.model_id)
            
            # Use having clause to filter out zero-token models and order by total tokens
            results = (
                query.having(
                    (func.sum(MetricsDailyRollup.total_input_tokens) + func.sum(MetricsDailyRollup.total_output_tokens)) > 0
                )
                .order_by(
                    (func.sum(MetricsDailyRollup.total_input_tokens) + func.sum(MetricsDailyRollup.total_output_tokens)).desc()
                )
                .limit(limit)
                .all()
            )
        db_query_time = (time.time() - db_query_start) * 1000
        log.debug(f"[PERF] /models: database query took {db_query_time:.2f}ms, returned {len(results)} rows")
        
        # Map model IDs to names (cached)
        model_names_start = time.time()
        model_id_to_name = await get_model_names_map(request, user)
        model_names_time = (time.time() - model_names_start) * 1000
        log.debug(f"[PERF] /models: get_model_names_map took {model_names_time:.2f}ms")
        
        response = []
        for row in results:
            model_id = row.model_id
            total_input = int(row.total_input_tokens or 0)
            total_output = int(row.total_output_tokens or 0)
            total_tokens = total_input + total_output
            
            response.append(
                ModelMetricsResponse(
                    model_id=model_id,
                    model_name=model_id_to_name.get(model_id) or model_id,
                    spend=float(row.total_cost or 0),
                    input_tokens=total_input,
                    output_tokens=total_output,
                    total_tokens=total_tokens,
                    message_count=int(row.message_count or 0),
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
            # Query rollup table directly
            query = (
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
                .order_by(MetricsDailyRollup.date)
            )
            
            # Filter by model type
            query = filter_by_model_type(query, model_ownership_map, model_type, MetricsDailyRollup.model_id)
            
            results = query.all()
        db_query_time = (time.time() - db_query_start) * 1000
        log.debug(f"[PERF] /tokens/daily: database query took {db_query_time:.2f}ms, returned {len(results)} rows")
        
        response = []
        for row in results:
            date_str = str(row.date)
            input_tokens = int(row.input_tokens or 0)
            output_tokens = int(row.output_tokens or 0)
            
            response.append(
                DailyTokenUsageResponse(
                    date=date_str,
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
            # Query rollup table directly
            query = (
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
                .order_by(MetricsDailyRollup.date)
            )
            
            query = filter_by_model_type(query, model_ownership_map, model_type, MetricsDailyRollup.model_id)
            
            results = query.all()
        db_query_time = (time.time() - db_query_start) * 1000
        log.debug(f"[PERF] /spend/daily: database query took {db_query_time:.2f}ms, returned {len(results)} rows")
        
        response = []
        for row in results:
            date_str = str(row.date)
            
            response.append(
                DailySpendResponse(
                    date=date_str,
                    cost=float(row.total_cost or 0),
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

