import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, String, Text, JSON, Index, ForeignKey, Integer, Numeric, Date, Boolean, UniqueConstraint

from open_webui.internal.db import Base, get_db


class TaskPromptTemplate(Base):
    __tablename__ = "task_prompt_template"

    id = Column(String, primary_key=True)
    task_type = Column(Text, nullable=False, index=True)
    template = Column(Text, nullable=False)
    template_hash = Column(Text, nullable=False)
    source = Column(Text, nullable=False, server_default="default")  # default|config|user
    version = Column(Integer, nullable=False, server_default="1")
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("task_type", "template_hash", name="uq_task_prompt_template_task_hash"),
    )


class TaskGeneration(Base):
    __tablename__ = "task_generation"

    id = Column(String, primary_key=True)
    chat_id = Column(String, nullable=False, index=True)
    message_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    
    task_type = Column(Text, nullable=False, index=True)
    prompt_template_id = Column(String, ForeignKey("task_prompt_template.id"), nullable=False, index=True)
    
    model_id = Column(Text, nullable=False, index=True)
    task_model_type = Column(Text, nullable=False, index=True)  # internal|external
    
    response_text = Column(Text, nullable=True)
    usage = Column(JSON, nullable=True)
    cost = Column(Numeric(precision=10, scale=8), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    reasoning_tokens = Column(Integer, nullable=True)
    
    is_success = Column(Boolean, nullable=True)
    error = Column(JSON, nullable=True)
    
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        Index("ix_task_generation_user_created", "user_id", "created_at"),
        Index("ix_task_generation_user_task_created", "user_id", "task_type", "created_at"),
        Index("ix_task_generation_model_created", "model_id", "created_at"),
        Index("ix_task_generation_chat_message", "chat_id", "message_id"),
    )


class TaskMetricsDailyRollup(Base):
    __tablename__ = "task_metrics_daily_rollup"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    task_type = Column(Text, nullable=False, index=True)
    task_model_type = Column(Text, nullable=False, index=True)  # internal|external
    model_id = Column(Text, nullable=False, index=True)
    
    task_count = Column(Integer, nullable=False, server_default='0')
    total_cost = Column(Numeric(precision=10, scale=8), nullable=False, server_default='0')
    total_input_tokens = Column(Integer, nullable=False, server_default='0')
    total_output_tokens = Column(Integer, nullable=False, server_default='0')
    total_reasoning_tokens = Column(Integer, nullable=False, server_default='0')
    distinct_chat_count = Column(Integer, nullable=False, server_default='0')
    
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "date", "task_type", "model_id", "task_model_type", name="uq_task_metrics_rollup_unique"),
        Index("ix_task_metrics_rollup_user_date", "user_id", "date"),
        Index("ix_task_metrics_rollup_user_model_date", "user_id", "model_id", "date"),
    )


class TaskPromptTemplateModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_type: str
    template: str
    template_hash: str
    source: str
    version: int
    created_at: int
    updated_at: int


class TaskGenerationModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chat_id: str
    message_id: str
    user_id: str
    task_type: str
    prompt_template_id: str
    model_id: str
    task_model_type: str
    response_text: Optional[str] = None
    usage: Optional[dict] = None
    cost: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    is_success: Optional[bool] = None
    error: Optional[dict] = None
    created_at: int
    updated_at: int


class TaskMetricsDailyRollupModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    date: str  # ISO date string
    task_type: str
    task_model_type: str
    model_id: str
    task_count: int
    total_cost: float
    total_input_tokens: int
    total_output_tokens: int
    total_reasoning_tokens: int
    distinct_chat_count: int
    created_at: int
    updated_at: int

