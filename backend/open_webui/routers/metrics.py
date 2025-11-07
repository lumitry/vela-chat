import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, and_, or_, case, text
from sqlalchemy.orm import aliased

from open_webui.internal.db import get_db
from open_webui.models.chat_messages import ChatMessage
from open_webui.models.chats import Chat
from open_webui.utils.auth import get_verified_user
from open_webui.utils.models import get_all_models
from open_webui.env import SRC_LOG_LEVELS
from open_webui.models.users import UserModel

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


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
    """Get mapping of model_id to owned_by (ollama/openai/arena)"""
    models = await get_all_models(request, user=user)
    return {model["id"]: model.get("owned_by", "unknown") for model in models}


# Helper function to convert timestamp to date string (ISO format)
def timestamp_to_date_str(timestamp: int) -> str:
    """Convert Unix timestamp to ISO date string (YYYY-MM-DD)"""
    return datetime.fromtimestamp(timestamp).date().isoformat()


# Helper function to get date range from query params
def get_date_range(start_date: Optional[str], end_date: Optional[str]) -> tuple[int, int]:
    """Convert date strings to timestamps. Defaults to last 30 days if not provided."""
    if end_date:
        end_ts = int(datetime.fromisoformat(end_date).timestamp())
    else:
        end_ts = int(datetime.now().timestamp())
    
    if start_date:
        start_ts = int(datetime.fromisoformat(start_date).timestamp())
    else:
        # Default to 30 days ago
        start_ts = int((datetime.now() - timedelta(days=30)).timestamp())
    
    return start_ts, end_ts


# Helper function to filter by model type
def filter_by_model_type(
    query, model_ownership_map: Dict[str, str], model_type: str, model_id_column
):
    """Filter query by model type (local/external/both)"""
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
    try:
        start_ts, end_ts = get_date_range(start_date, end_date)
        model_ownership_map = await get_model_ownership_map(request, user)
        
        with get_db() as db:
            # Join chat_message with chat to filter by user_id
            # Exclude content_text for performance
            query = (
                db.query(
                    ChatMessage.model_id,
                    func.sum(ChatMessage.cost).label("total_cost"),
                    func.sum(ChatMessage.input_tokens).label("total_input_tokens"),
                    func.sum(ChatMessage.output_tokens).label("total_output_tokens"),
                    func.count(ChatMessage.id).label("message_count"),
                )
                .join(Chat, ChatMessage.chat_id == Chat.id)
                .filter(
                    Chat.user_id == user.id,
                    ChatMessage.created_at >= start_ts,
                    ChatMessage.created_at <= end_ts,
                    ChatMessage.model_id.isnot(None),
                )
                .group_by(ChatMessage.model_id)
            )
            
            # Filter by model type
            query = filter_by_model_type(query, model_ownership_map, model_type, ChatMessage.model_id)
            
            # Order by total tokens (input + output)
            results = (
                query.order_by(
                    (func.sum(ChatMessage.input_tokens) + func.sum(ChatMessage.output_tokens)).desc()
                )
                .limit(limit)
                .all()
            )
        
        # Map model IDs to names
        model_id_to_name = {model["id"]: model.get("name", model["id"]) for model in await get_all_models(request, user=user)}
        
        response = []
        for row in results:
            model_id = row.model_id
            total_input = int(row.total_input_tokens or 0)
            total_output = int(row.total_output_tokens or 0)
            total_tokens = total_input + total_output
            
            response.append(
                ModelMetricsResponse(
                    model_id=model_id,
                    model_name=model_id_to_name.get(model_id, model_id),
                    spend=float(row.total_cost or 0),
                    input_tokens=total_input,
                    output_tokens=total_output,
                    total_tokens=total_tokens,
                    message_count=int(row.message_count or 0),
                )
            )
        
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
    try:
        start_ts, end_ts = get_date_range(start_date, end_date)
        model_ownership_map = await get_model_ownership_map(request, user)
        
        with get_db() as db:
            # Get database dialect for date conversion
            dialect_name = db.bind.dialect.name
            
            if dialect_name == "sqlite":
                # SQLite: Use datetime function with unixepoch
                # SQLite's datetime() function converts unix timestamp to datetime, then date() extracts date
                date_expr = func.date(func.datetime(ChatMessage.created_at, 'unixepoch'))
            elif dialect_name == "postgresql":
                # PostgreSQL: Use to_timestamp and date extraction
                date_expr = func.date(func.to_timestamp(ChatMessage.created_at))
            else:
                # Fallback: convert in Python (will need post-processing)
                date_expr = ChatMessage.created_at
            
            query = (
                db.query(
                    date_expr.label("date"),
                    func.sum(ChatMessage.input_tokens).label("input_tokens"),
                    func.sum(ChatMessage.output_tokens).label("output_tokens"),
                )
                .join(Chat, ChatMessage.chat_id == Chat.id)
                .filter(
                    Chat.user_id == user.id,
                    ChatMessage.created_at >= start_ts,
                    ChatMessage.created_at <= end_ts,
                )
                .group_by(date_expr)
                .order_by(date_expr)
            )
            
            # Filter by model type
            query = filter_by_model_type(query, model_ownership_map, model_type, ChatMessage.model_id)
            
            results = query.all()
        
        response = []
        for row in results:
            if dialect_name in ("sqlite", "postgresql"):
                date_str = str(row.date)
            else:
                # Fallback: convert timestamp to date
                date_str = timestamp_to_date_str(int(row.date))
            
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
    try:
        start_ts, end_ts = get_date_range(start_date, end_date)
        model_ownership_map = await get_model_ownership_map(request, user)
        
        with get_db() as db:
            dialect_name = db.bind.dialect.name
            
            if dialect_name == "sqlite":
                date_expr = func.date(func.datetime(ChatMessage.created_at, 'unixepoch'))
            elif dialect_name == "postgresql":
                date_expr = func.date(func.to_timestamp(ChatMessage.created_at))
            else:
                date_expr = ChatMessage.created_at
            
            query = (
                db.query(
                    date_expr.label("date"),
                    func.sum(ChatMessage.cost).label("total_cost"),
                )
                .join(Chat, ChatMessage.chat_id == Chat.id)
                .filter(
                    Chat.user_id == user.id,
                    ChatMessage.created_at >= start_ts,
                    ChatMessage.created_at <= end_ts,
                    ChatMessage.cost.isnot(None),
                )
                .group_by(date_expr)
                .order_by(date_expr)
            )
            
            query = filter_by_model_type(query, model_ownership_map, model_type, ChatMessage.model_id)
            
            results = query.all()
        
        response = []
        for row in results:
            if dialect_name in ("sqlite", "postgresql"):
                date_str = str(row.date)
            else:
                date_str = timestamp_to_date_str(int(row.date))
            
            response.append(
                DailySpendResponse(
                    date=date_str,
                    cost=float(row.total_cost or 0),
                )
            )
        
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
    try:
        start_ts, end_ts = get_date_range(start_date, end_date)
        model_ownership_map = await get_model_ownership_map(request, user)
        all_models = await get_all_models(request, user=user)
        model_id_to_name = {model["id"]: model.get("name", model["id"]) for model in all_models}
        
        with get_db() as db:
            dialect_name = db.bind.dialect.name
            
            if dialect_name == "sqlite":
                date_expr = func.date(func.datetime(ChatMessage.created_at, 'unixepoch'))
            elif dialect_name == "postgresql":
                date_expr = func.date(func.to_timestamp(ChatMessage.created_at))
            else:
                date_expr = ChatMessage.created_at
            
            # First, get top N models by total tokens
            top_models_query = (
                db.query(
                    ChatMessage.model_id,
                    func.sum(ChatMessage.input_tokens + ChatMessage.output_tokens).label("total_tokens"),
                )
                .join(Chat, ChatMessage.chat_id == Chat.id)
                .filter(
                    Chat.user_id == user.id,
                    ChatMessage.created_at >= start_ts,
                    ChatMessage.created_at <= end_ts,
                    ChatMessage.model_id.isnot(None),
                )
                .group_by(ChatMessage.model_id)
                .order_by(func.sum(ChatMessage.input_tokens + ChatMessage.output_tokens).desc())
                .limit(limit)
            )
            
            top_models_query = filter_by_model_type(top_models_query, model_ownership_map, model_type, ChatMessage.model_id)
            top_model_ids = [row.model_id for row in top_models_query.all()]
            
            if not top_model_ids:
                return []
            
            # Now get daily breakdown for these models
            query = (
                db.query(
                    date_expr.label("date"),
                    ChatMessage.model_id,
                    func.sum(ChatMessage.input_tokens).label("input_tokens"),
                    func.sum(ChatMessage.output_tokens).label("output_tokens"),
                )
                .join(Chat, ChatMessage.chat_id == Chat.id)
                .filter(
                    Chat.user_id == user.id,
                    ChatMessage.created_at >= start_ts,
                    ChatMessage.created_at <= end_ts,
                    ChatMessage.model_id.in_(top_model_ids),
                )
                .group_by(date_expr, ChatMessage.model_id)
                .order_by(date_expr, ChatMessage.model_id)
            )
            
            results = query.all()
        
        response = []
        for row in results:
            if dialect_name in ("sqlite", "postgresql"):
                date_str = str(row.date)
            else:
                date_str = timestamp_to_date_str(int(row.date))
            
            input_tokens = int(row.input_tokens or 0)
            output_tokens = int(row.output_tokens or 0)
            
            response.append(
                ModelDailyTokensResponse(
                    date=date_str,
                    model_id=row.model_id,
                    model_name=model_id_to_name.get(row.model_id, row.model_id),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                )
            )
        
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
    try:
        start_ts, end_ts = get_date_range(start_date, end_date)
        model_ownership_map = await get_model_ownership_map(request, user)
        
        with get_db() as db:
            dialect_name = db.bind.dialect.name
            
            if dialect_name == "sqlite":
                date_expr = func.date(func.datetime(ChatMessage.created_at, 'unixepoch'))
            elif dialect_name == "postgresql":
                date_expr = func.date(func.to_timestamp(ChatMessage.created_at))
            else:
                date_expr = ChatMessage.created_at
            
            query = (
                db.query(
                    date_expr.label("date"),
                    func.avg(ChatMessage.cost).label("avg_cost"),
                    func.count(ChatMessage.id).label("message_count"),
                    func.sum(ChatMessage.cost).label("total_cost"),
                )
                .join(Chat, ChatMessage.chat_id == Chat.id)
                .filter(
                    Chat.user_id == user.id,
                    ChatMessage.created_at >= start_ts,
                    ChatMessage.created_at <= end_ts,
                    ChatMessage.cost.isnot(None),
                )
                .group_by(date_expr)
                .order_by(date_expr)
            )
            
            query = filter_by_model_type(query, model_ownership_map, model_type, ChatMessage.model_id)
            
            results = query.all()
        
        response = []
        for row in results:
            if dialect_name in ("sqlite", "postgresql"):
                date_str = str(row.date)
            else:
                date_str = timestamp_to_date_str(int(row.date))
            
            response.append(
                CostPerMessageDailyResponse(
                    date=date_str,
                    avg_cost=float(row.avg_cost or 0),
                    message_count=int(row.message_count or 0),
                    total_cost=float(row.total_cost or 0),
                )
            )
        
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
    try:
        start_ts, end_ts = get_date_range(start_date, end_date)
        
        with get_db() as db:
            dialect_name = db.bind.dialect.name
            
            if dialect_name == "sqlite":
                date_expr = func.date(func.datetime(ChatMessage.created_at, 'unixepoch'))
            elif dialect_name == "postgresql":
                date_expr = func.date(func.to_timestamp(ChatMessage.created_at))
            else:
                date_expr = ChatMessage.created_at
            
            results = (
                db.query(
                    date_expr.label("date"),
                    func.count(ChatMessage.id).label("count"),
                )
                .join(Chat, ChatMessage.chat_id == Chat.id)
                .filter(
                    Chat.user_id == user.id,
                    ChatMessage.created_at >= start_ts,
                    ChatMessage.created_at <= end_ts,
                )
                .group_by(date_expr)
                .order_by(date_expr)
                .all()
            )
        
        response = []
        for row in results:
            if dialect_name in ("sqlite", "postgresql"):
                date_str = str(row.date)
            else:
                date_str = timestamp_to_date_str(int(row.date))
            
            response.append(
                MessageCountDailyResponse(
                    date=date_str,
                    count=int(row.count or 0),
                )
            )
        
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
    try:
        start_ts, end_ts = get_date_range(start_date, end_date)
        model_ownership_map = await get_model_ownership_map(request, user)
        all_models = await get_all_models(request, user=user)
        model_id_to_name = {model["id"]: model.get("name", model["id"]) for model in all_models}
        
        with get_db() as db:
            # Count distinct chats per model
            query = (
                db.query(
                    ChatMessage.model_id,
                    func.count(func.distinct(ChatMessage.chat_id)).label("chat_count"),
                    func.count(ChatMessage.id).label("message_count"),
                )
                .join(Chat, ChatMessage.chat_id == Chat.id)
                .filter(
                    Chat.user_id == user.id,
                    ChatMessage.created_at >= start_ts,
                    ChatMessage.created_at <= end_ts,
                    ChatMessage.model_id.isnot(None),
                )
                .group_by(ChatMessage.model_id)
                .order_by(func.count(func.distinct(ChatMessage.chat_id)).desc())
            )
            
            query = filter_by_model_type(query, model_ownership_map, model_type, ChatMessage.model_id)
            
            results = query.limit(limit).all()
        
        response = []
        for row in results:
            response.append(
                ModelPopularityResponse(
                    model_id=row.model_id,
                    model_name=model_id_to_name.get(row.model_id, row.model_id),
                    chat_count=int(row.chat_count or 0),
                    message_count=int(row.message_count or 0),
                )
            )
        
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
    try:
        start_ts, end_ts = get_date_range(start_date, end_date)
        model_ownership_map = await get_model_ownership_map(request, user)
        
        with get_db() as db:
            dialect_name = db.bind.dialect.name
            
            if dialect_name == "sqlite":
                date_expr = func.date(func.datetime(ChatMessage.created_at, 'unixepoch'))
            elif dialect_name == "postgresql":
                date_expr = func.date(func.to_timestamp(ChatMessage.created_at))
            else:
                date_expr = ChatMessage.created_at
            
            query = (
                db.query(
                    date_expr.label("date"),
                    func.sum(ChatMessage.cost).label("total_cost"),
                    func.sum(ChatMessage.input_tokens + ChatMessage.output_tokens).label("total_tokens"),
                )
                .join(Chat, ChatMessage.chat_id == Chat.id)
                .filter(
                    Chat.user_id == user.id,
                    ChatMessage.created_at >= start_ts,
                    ChatMessage.created_at <= end_ts,
                    ChatMessage.cost.isnot(None),
                )
                .group_by(date_expr)
                .order_by(date_expr)
            )
            
            query = filter_by_model_type(query, model_ownership_map, model_type, ChatMessage.model_id)
            
            results = query.all()
        
        response = []
        for row in results:
            if dialect_name in ("sqlite", "postgresql"):
                date_str = str(row.date)
            else:
                date_str = timestamp_to_date_str(int(row.date))
            
            total_cost = float(row.total_cost or 0)
            total_tokens = int(row.total_tokens or 0)
            avg_cost_per_token = total_cost / total_tokens if total_tokens > 0 else 0.0
            
            response.append(
                CostPerTokenDailyResponse(
                    date=date_str,
                    avg_cost_per_token=avg_cost_per_token,
                    total_tokens=total_tokens,
                    total_cost=total_cost,
                )
            )
        
        return response
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

