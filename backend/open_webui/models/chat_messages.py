import time
import uuid
from typing import Optional, List

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, String, Text, JSON, Index, ForeignKey, Integer, func

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
    meta = Column(JSON, nullable=True)

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
    meta: Optional[dict] = None
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


class MessageCreateForm(BaseModel):
    parent_id: Optional[str] = None
    role: str
    content_text: Optional[str] = None
    content_json: Optional[dict] = None
    model_id: Optional[str] = None
    attachments: Optional[List[dict]] = None
    meta: Optional[dict] = None
    position: Optional[int] = None  # If provided, use it; otherwise calculate from siblings


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
                      meta: Optional[dict] = None, position: Optional[int] = None) -> Optional[ChatMessageModel]:
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
            if content_json is not None:
                message.content_json = content_json
            if model_id is not None:
                message.model_id = model_id
            if status is not None:
                message.status = status
            if usage is not None:
                message.usage = usage
            if position is not None:
                message.position = position
            if meta is not None:
                # Merge with existing meta if it exists
                existing_meta = message.meta or {}
                message.meta = {**existing_meta, **meta}
                # If modelIdx is in meta and position doesn't match, update position
                if "modelIdx" in message.meta and message.position != message.meta.get("modelIdx"):
                    message.position = message.meta.get("modelIdx")
            
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


ChatMessages = ChatMessagesTable()


