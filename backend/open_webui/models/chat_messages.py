import time
import uuid
from typing import Optional, List, Tuple

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, String, Text, JSON, Index, ForeignKey, Integer, func, Numeric, Date

from open_webui.internal.db import Base, get_db


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id = Column(String, primary_key=True)
    chat_id = Column(String, index=True)
    parent_id = Column(String, nullable=True, index=True)

    role = Column(Text)
    model_id = Column(Text, nullable=True)

    # Position for sibling ordering (for side-by-side chats)
    # When multiple messages share the same parent_id, position determines their order
    position = Column(Integer, nullable=True, default=0)

    content_text = Column(Text, nullable=True)
    content_json = Column(JSON, nullable=True)

    status = Column(JSON, nullable=True)
    usage = Column(JSON, nullable=True)
    cost = Column(Numeric(precision=10, scale=8), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    reasoning_tokens = Column(Integer, nullable=True)
    meta = Column(JSON, nullable=True)
    
    # Feedback/evaluation fields
    annotation = Column(JSON, nullable=True)  # Contains rating, tags, reason, comment, details
    feedback_id = Column(String, nullable=True)  # ID of the feedback record
    selected_model_id = Column(Text, nullable=True)  # Selected model for arena/competition mode

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)

    __table_args__ = (
        Index("ix_chat_message_chat_parent", "chat_id", "parent_id"),
        Index("ix_chat_message_chat_created", "chat_id", "created_at"),
        Index("ix_chat_message_chat_parent_position", "chat_id", "parent_id", "position"),
    )


class ChatMessageAttachment(Base):
    __tablename__ = "chat_message_attachment"

    id = Column(String, primary_key=True)
    message_id = Column(String, ForeignKey("chat_message.id", ondelete="CASCADE"), index=True)
    type = Column(Text)  # image, file, tool_output, web_search, etc.

    file_id = Column(String, nullable=True)
    url = Column(Text, nullable=True)
    mime_type = Column(Text, nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    meta = Column(JSON, nullable=True)

    created_at = Column(BigInteger)


class MetricsDailyRollup(Base):
    __tablename__ = "metrics_daily_rollup"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    model_id = Column(Text, nullable=True, index=True)
    message_count = Column(Integer, nullable=False, server_default='0')
    total_cost = Column(Numeric(precision=10, scale=8), nullable=False, server_default='0')
    total_input_tokens = Column(Integer, nullable=False, server_default='0')
    total_output_tokens = Column(Integer, nullable=False, server_default='0')
    total_reasoning_tokens = Column(Integer, nullable=False, server_default='0')
    distinct_chat_count = Column(Integer, nullable=False, server_default='0')
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        Index("ix_metrics_daily_rollup_user_date", "user_id", "date"),
        Index("ix_metrics_daily_rollup_user_model_date", "user_id", "model_id", "date"),
    )


class ChatMessageModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chat_id: str
    parent_id: Optional[str]
    role: str
    model_id: Optional[str] = None
    position: Optional[int] = 0
    content_text: Optional[str] = None
    content_json: Optional[dict] = None
    status: Optional[dict] = None
    usage: Optional[dict] = None
    cost: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    meta: Optional[dict] = None
    annotation: Optional[dict] = None
    feedback_id: Optional[str] = None
    selected_model_id: Optional[str] = None
    created_at: int
    updated_at: int


class ChatMessageAttachmentModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    message_id: str
    type: str
    file_id: Optional[str] = None
    url: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    meta: Optional[dict] = None
    created_at: int


def extract_tokens_from_usage(usage: Optional[dict]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Extract token counts from usage JSON.
    Returns (input_tokens, output_tokens, reasoning_tokens) tuple.
    """
    if not usage or not isinstance(usage, dict):
        return (None, None, None)
    
    # Extract input tokens (prompt_tokens)
    input_tokens = None
    if 'prompt_tokens' in usage and usage['prompt_tokens'] is not None:
        try:
            input_tokens = int(usage['prompt_tokens'])
        except (ValueError, TypeError):
            pass
    
    # Extract total output tokens (completion_tokens)
    output_tokens = None
    if 'completion_tokens' in usage and usage['completion_tokens'] is not None:
        try:
            output_tokens = int(usage['completion_tokens'])
        except (ValueError, TypeError):
            pass
    
    # Extract reasoning tokens (completion_tokens_details.reasoning_tokens)
    reasoning_tokens = None
    if 'completion_tokens_details' in usage and isinstance(usage['completion_tokens_details'], dict):
        details = usage['completion_tokens_details']
        if 'reasoning_tokens' in details and details['reasoning_tokens'] is not None:
            try:
                reasoning_tokens = int(details['reasoning_tokens'])
            except (ValueError, TypeError):
                pass
    
    return (input_tokens, output_tokens, reasoning_tokens)


def extract_cost_from_usage(usage: Optional[dict]) -> Optional[float]:
    """
    Extract cost from usage JSON.
    Tries multiple possible fields:
    1. usage.cost (direct cost field)
    2. usage.estimates.total_cost (estimated total cost)
    3. usage.estimates.input_cost + usage.estimates.output_cost (sum of components)
    
    Returns None if no cost information is found.
    """
    if not usage or not isinstance(usage, dict):
        return None
    
    # Priority 1: Direct cost field
    if 'cost' in usage and usage['cost'] is not None:
        try:
            return float(usage['cost'])
        except (ValueError, TypeError):
            pass
    
    # Priority 2: Total cost from estimates
    if 'estimates' in usage and isinstance(usage['estimates'], dict):
        estimates = usage['estimates']
        if 'total_cost' in estimates and estimates['total_cost'] is not None:
            try:
                return float(estimates['total_cost'])
            except (ValueError, TypeError):
                pass
    
    # Priority 3: Sum of input and output costs
    if 'estimates' in usage and isinstance(usage['estimates'], dict):
        estimates = usage['estimates']
        input_cost = 0.0
        output_cost = 0.0
        
        if 'input_cost' in estimates and estimates['input_cost'] is not None:
            try:
                input_cost = float(estimates['input_cost'])
            except (ValueError, TypeError):
                pass
        
        if 'output_cost' in estimates and estimates['output_cost'] is not None:
            try:
                output_cost = float(estimates['output_cost'])
            except (ValueError, TypeError):
                pass
        
        if input_cost > 0 or output_cost > 0:
            return input_cost + output_cost
    
    return None


class MessageCreateForm(BaseModel):
    parent_id: Optional[str] = None
    role: str
    content_text: Optional[str] = None
    content_json: Optional[dict] = None
    model_id: Optional[str] = None
    attachments: Optional[List[dict]] = None
    meta: Optional[dict] = None
    position: Optional[int] = None  # If provided, use it; otherwise calculate from siblings
    annotation: Optional[dict] = None  # Feedback/evaluation annotation
    feedback_id: Optional[str] = None  # Feedback ID
    selected_model_id: Optional[str] = None  # Selected model for arena models


class ChatMessagesTable:
    def insert_message(self, chat_id: str, form: MessageCreateForm, message_id: Optional[str] = None) -> Optional[ChatMessageModel]:
        with get_db() as db:
            ts = int(time.time())
            mid = message_id if message_id else str(uuid.uuid4())
            
            # Calculate position for sibling ordering if not provided
            # Position determines the order of messages with the same parent_id (for side-by-side chats)
            position = form.position
            if position is None:
                # For side-by-side chats, use modelIdx from meta if available to ensure correct ordering
                # Otherwise, calculate position from existing siblings
                if form.meta and "modelIdx" in form.meta:
                    # If modelIdx is provided, use it as position (they should match for side-by-side)
                    position = form.meta.get("modelIdx", 0)
                else:
                    # Find the maximum position among siblings with the same parent_id
                    max_position_result = db.query(
                        func.max(ChatMessage.position)
                    ).filter_by(
                        chat_id=chat_id,
                        parent_id=form.parent_id
                    ).scalar()
                    position = (max_position_result or -1) + 1
            
            message = ChatMessage(
                **{
                    "id": mid,
                    "chat_id": chat_id,
                    "parent_id": form.parent_id,
                    "role": form.role,
                    "model_id": form.model_id,
                    "position": position,
                    "content_text": form.content_text,
                    "content_json": form.content_json,
                    "meta": form.meta,
                    "annotation": form.annotation,
                    "feedback_id": form.feedback_id,
                    "selected_model_id": form.selected_model_id,
                    "created_at": ts,
                    "updated_at": ts,
                }
            )
            db.add(message)
            db.flush()

            # attachments
            if form.attachments:
                for att in form.attachments:
                    db.add(
                        ChatMessageAttachment(
                            **{
                                "id": str(uuid.uuid4()),
                                "message_id": mid,
                                "type": att.get("type", "file"),
                                "file_id": att.get("file_id"),
                                "url": att.get("url"),
                                "mime_type": att.get("mime_type"),
                                "size_bytes": att.get("size_bytes"),
                                "meta": att.get("metadata") or att.get("meta"),
                                "created_at": ts,
                            }
                        )
                    )

            db.commit()
            db.refresh(message)
            return ChatMessageModel.model_validate(message)

    def get_message_by_id(self, id: str) -> Optional[ChatMessageModel]:
        with get_db() as db:
            m = db.get(ChatMessage, id)
            return ChatMessageModel.model_validate(m) if m else None

    def update_message(self, message_id: str, content_text: Optional[str] = None, 
                      content_json: Optional[dict] = None, model_id: Optional[str] = None,
                      status: Optional[dict] = None, usage: Optional[dict] = None,
                      meta: Optional[dict] = None, position: Optional[int] = None,
                      parent_id: Optional[str] = None, annotation: Optional[dict] = None,
                      feedback_id: Optional[str] = None, selected_model_id: Optional[str] = None) -> Optional[ChatMessageModel]:
        """Update an existing message with new content or metadata."""
        import logging
        log = logging.getLogger(__name__)
        
        with get_db() as db:
            message = db.get(ChatMessage, message_id)
            if not message:
                log.warning(f"ChatMessages.update_message: Message {message_id} not found")
                return None
            
            if content_text is not None:
                message.content_text = content_text
                log.debug(f"ChatMessages.update_message: Updated content_text for {message_id} (length: {len(content_text) if content_text else 0})")
                db.flush()
            if content_json is not None:
                message.content_json = content_json
            if model_id is not None:
                message.model_id = model_id
            if status is not None:
                message.status = status
            if usage is not None:
                message.usage = usage
                # Extract and store cost and tokens when usage is updated
                cost = extract_cost_from_usage(usage)
                input_tokens, output_tokens, reasoning_tokens = extract_tokens_from_usage(usage)
                
                if cost is not None:
                    from decimal import Decimal
                    message.cost = Decimal(str(cost))
                else:
                    message.cost = None
                
                message.input_tokens = input_tokens
                message.output_tokens = output_tokens
                message.reasoning_tokens = reasoning_tokens
            if position is not None:
                message.position = position
            if parent_id is not None:
                message.parent_id = parent_id
                log.debug(f"ChatMessages.update_message: Updated parent_id for {message_id} to {parent_id}")
            if meta is not None:
                # Merge with existing meta if it exists
                existing_meta = message.meta or {}
                message.meta = {**existing_meta, **meta}
                # If modelIdx is in meta and position doesn't match, update position
                if "modelIdx" in message.meta and message.position != message.meta.get("modelIdx"):
                    message.position = message.meta.get("modelIdx")
            if annotation is not None:
                message.annotation = annotation
            if feedback_id is not None:
                message.feedback_id = feedback_id
            if selected_model_id is not None:
                message.selected_model_id = selected_model_id
            
            message.updated_at = int(time.time())
            db.commit()
            db.refresh(message)
            log.debug(f"ChatMessages.update_message: Successfully updated message {message_id}")
            return ChatMessageModel.model_validate(message)

    def get_branch_to_root(self, chat_id: str, leaf_id: str) -> List[ChatMessageModel]:
        with get_db() as db:
            seq = []
            cur = db.get(ChatMessage, leaf_id)
            while cur and cur.chat_id == chat_id:
                seq.append(ChatMessageModel.model_validate(cur))
                if cur.parent_id:
                    cur = db.get(ChatMessage, cur.parent_id)
                else:
                    break
            return list(reversed(seq))

    def list_children(self, chat_id: str, parent_id: Optional[str]) -> List[ChatMessageModel]:
        with get_db() as db:
            # Order by position first (for side-by-side chats), then by created_at as fallback
            q = db.query(ChatMessage).filter_by(chat_id=chat_id, parent_id=parent_id).order_by(
                ChatMessage.position.asc(),
                ChatMessage.created_at.asc()
            )
            return [ChatMessageModel.model_validate(m) for m in q.all()]

    def get_all_messages_by_chat_id(self, chat_id: str) -> List[ChatMessageModel]:
        """Get all messages for a chat, ordered by creation time."""
        with get_db() as db:
            q = db.query(ChatMessage).filter_by(chat_id=chat_id).order_by(ChatMessage.created_at.asc())
            return [ChatMessageModel.model_validate(m) for m in q.all()]

    def clone_messages_to_chat(self, source_chat_id: str, target_chat_id: str) -> dict[str, str]:
        """
        Clone all messages from source_chat_id to target_chat_id.
        Returns a mapping from old message IDs to new message IDs.
        
        This ensures:
        - All messages get new unique IDs
        - Parent IDs are updated to point to the new parent message IDs
        - Chat IDs are updated to the target chat
        - Cost is set to 0 for all duplicated messages
        - Parent-child relationships are preserved correctly
        """
        with get_db() as db:
            # Get all messages from source chat
            source_messages = db.query(ChatMessage).filter_by(chat_id=source_chat_id).order_by(
                ChatMessage.created_at.asc()
            ).all()
            
            if not source_messages:
                return {}
            
            # Create ID mapping: old_id -> new_id
            id_mapping: dict[str, str] = {}
            for msg in source_messages:
                old_id = str(msg.id)
                new_id = str(uuid.uuid4())
                id_mapping[old_id] = new_id
            
            # Get all attachments from source messages
            source_message_ids = [str(m.id) for m in source_messages]
            source_attachments = []
            if source_message_ids:
                source_attachments = db.query(ChatMessageAttachment).filter(
                    ChatMessageAttachment.message_id.in_(source_message_ids)
                ).all()
            
            ts = int(time.time())
            
            # Clone messages in creation order to maintain parent-child relationships
            for msg in source_messages:
                old_id = str(msg.id)
                new_id = id_mapping[old_id]
                
                # Map parent_id to new parent_id
                new_parent_id = None
                if msg.parent_id:
                    old_parent_id = str(msg.parent_id)
                    new_parent_id = id_mapping.get(old_parent_id)
                
                # Create new message with updated IDs and cost set to 0
                new_message = ChatMessage(
                    id=new_id,
                    chat_id=target_chat_id,
                    parent_id=new_parent_id,
                    role=msg.role,
                    model_id=msg.model_id,
                    position=msg.position,
                    content_text=msg.content_text,
                    content_json=msg.content_json,
                    status=msg.status,
                    usage=msg.usage,
                    cost=0,  # Set cost to 0 for cloned messages
                    input_tokens=msg.input_tokens,
                    output_tokens=msg.output_tokens,
                    reasoning_tokens=msg.reasoning_tokens,
                    meta=msg.meta,
                    created_at=ts,  # Use current timestamp for cloned messages
                    updated_at=ts,
                )
                db.add(new_message)
            
            # Clone attachments
            for att in source_attachments:
                old_msg_id = str(att.message_id)
                new_msg_id = id_mapping.get(old_msg_id)
                if new_msg_id:
                    new_attachment = ChatMessageAttachment(
                        id=str(uuid.uuid4()),
                        message_id=new_msg_id,
                        type=att.type,
                        file_id=att.file_id,
                        url=att.url,
                        mime_type=att.mime_type,
                        size_bytes=att.size_bytes,
                        meta=att.meta,
                        created_at=ts,
                    )
                    db.add(new_attachment)
            
            db.commit()
            return id_mapping

    def append_status_history(self, message_id: str, status_entry: dict) -> Optional[ChatMessageModel]:
        """
        Append a status history entry to a message's statusHistory array.
        Status history is stored in the status JSON field as statusHistory array.
        """
        import logging
        log = logging.getLogger(__name__)
        
        with get_db() as db:
            message = db.get(ChatMessage, message_id)
            if not message:
                log.warning(f"ChatMessages.append_status_history: Message {message_id} not found")
                return None
            
            # Get existing status or initialize
            existing_status = message.status or {}
            
            # Get existing statusHistory or initialize
            status_history = existing_status.get("statusHistory", [])
            if not isinstance(status_history, list):
                status_history = []
            
            # Append the new status entry
            status_history = status_history + [status_entry]
            
            # Create new status dict with updated statusHistory
            message.status = {**existing_status, "statusHistory": status_history}
            
            message.updated_at = int(time.time())
            db.commit()
            db.refresh(message)
            log.debug(f"ChatMessages.append_status_history: Appended status entry to message {message_id}")
            return ChatMessageModel.model_validate(message)

    def set_sources(self, message_id: str, sources: List[dict]) -> Optional[ChatMessageModel]:
        """
        Set the sources array for a message (web search results, RAG citations, etc.).
        Sources are stored in the meta field as 'sources' array.
        """
        import logging
        log = logging.getLogger(__name__)
        
        with get_db() as db:
            message = db.get(ChatMessage, message_id)
            if not message:
                log.warning(f"ChatMessages.set_sources: Message {message_id} not found")
                return None
            
            # Get existing meta or initialize
            existing_meta = message.meta or {}
            
            # Create new meta dict with sources
            message.meta = {**existing_meta, "sources": sources}
            
            message.updated_at = int(time.time())
            db.commit()
            db.refresh(message)
            log.debug(f"ChatMessages.set_sources: Set sources for message {message_id} ({len(sources)} sources)")
            return ChatMessageModel.model_validate(message)

    def add_attachment(self, message_id: str, attachment: dict) -> Optional[ChatMessageAttachmentModel]:
        """
        Add an attachment to a message (images, files, knowledge bases, etc.).
        Returns the created attachment model.
        """
        import logging
        log = logging.getLogger(__name__)
        
        with get_db() as db:
            message = db.get(ChatMessage, message_id)
            if not message:
                log.warning(f"ChatMessages.add_attachment: Message {message_id} not found")
                return None
            
            ts = int(time.time())
            att = ChatMessageAttachment(
                id=str(uuid.uuid4()),
                message_id=message_id,
                type=attachment.get("type", "file"),
                file_id=attachment.get("file_id"),
                url=attachment.get("url"),
                mime_type=attachment.get("mime_type"),
                size_bytes=attachment.get("size_bytes"),
                meta=attachment.get("metadata") or attachment.get("meta"),
                created_at=ts,
            )
            db.add(att)
            db.commit()
            db.refresh(att)
            log.debug(f"ChatMessages.add_attachment: Added attachment {att.id} to message {message_id} (type: {att.type})")
            return ChatMessageAttachmentModel.model_validate(att)

    def set_merged_metadata(self, message_id: str, merged_content: str, merged_status: bool = True) -> Optional[ChatMessageModel]:
        """
        Set MOA (merged) metadata for a message.
        Merged metadata is stored in the meta field as 'merged' object.
        """
        import logging
        log = logging.getLogger(__name__)
        
        with get_db() as db:
            message = db.get(ChatMessage, message_id)
            if not message:
                log.warning(f"ChatMessages.set_merged_metadata: Message {message_id} not found")
                return None
            
            # Get existing meta or initialize
            existing_meta = message.meta or {}
            
            # Create new meta dict with merged metadata
            message.meta = {
                **existing_meta,
                "merged": {
                    "status": merged_status,
                    "content": merged_content
                }
            }
            
            message.updated_at = int(time.time())
            db.commit()
            db.refresh(message)
            log.debug(f"ChatMessages.set_merged_metadata: Set merged metadata for message {message_id}")
            return ChatMessageModel.model_validate(message)


ChatMessages = ChatMessagesTable()


