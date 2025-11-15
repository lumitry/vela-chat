import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, String, Text, JSON, Index, Integer, Numeric, Date, UniqueConstraint

from open_webui.internal.db import Base


class EmbeddingGeneration(Base):
    __tablename__ = "embedding_generation"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    chat_id = Column(String, nullable=True, index=True)
    message_id = Column(String, nullable=True, index=True)
    knowledge_base_id = Column(String, nullable=True, index=True)
    
    embedding_type = Column(Text, nullable=False, index=True)
    embedding_model_type = Column(Text, nullable=False)  # internal|external
    model_id = Column(Text, nullable=False, index=True)
    embedding_engine = Column(Text, nullable=False)  # sentencetransformers|ollama|openai
    
    total_input_tokens = Column(Integer, nullable=True)
    cost = Column(Numeric(precision=10, scale=8), nullable=True)
    usage = Column(JSON, nullable=True)
    
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        Index("ix_embedding_generation_user_created", "user_id", "created_at"),
        Index("ix_embedding_generation_chat_message", "chat_id", "message_id"),
        Index("ix_embedding_generation_type_created", "embedding_type", "created_at"),
    )


class EmbeddingMetricsDailyRollup(Base):
    __tablename__ = "embedding_metrics_daily_rollup"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    embedding_type = Column(Text, nullable=False, index=True)
    embedding_model_type = Column(Text, nullable=False)  # internal|external
    model_id = Column(Text, nullable=False, index=True)
    
    task_count = Column(Integer, nullable=False, server_default='0')
    total_cost = Column(Numeric(precision=10, scale=8), nullable=False, server_default='0')
    total_input_tokens = Column(Integer, nullable=False, server_default='0')
    distinct_chat_count = Column(Integer, nullable=False, server_default='0')
    
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "date", "embedding_type", "model_id", "embedding_model_type", name="uq_embedding_metrics_rollup_unique"),
        Index("ix_embedding_metrics_rollup_user_date", "user_id", "date"),
        Index("ix_embedding_metrics_rollup_user_model_date", "user_id", "model_id", "date"),
    )


class EmbeddingGenerationModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    chat_id: Optional[str] = None
    message_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    embedding_type: str
    embedding_model_type: str
    model_id: str
    embedding_engine: str
    total_input_tokens: Optional[int] = None
    cost: Optional[float] = None
    usage: Optional[dict] = None
    created_at: int
    updated_at: int


class EmbeddingMetricsDailyRollupModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    date: str  # ISO date string
    embedding_type: str
    embedding_model_type: str
    model_id: str
    task_count: int
    total_cost: float
    total_input_tokens: int
    distinct_chat_count: int
    created_at: int
    updated_at: int


