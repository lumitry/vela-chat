import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from open_webui.internal.db import get_db
from open_webui.models.chat_messages import ChatMessageAttachment, ChatMessage

from open_webui.env import SRC_LOG_LEVELS
from open_webui.models.chat_messages import (
    ChatMessages,
    MessageCreateForm,
    ChatMessageModel,
)
from open_webui.models.chats import Chats
from open_webui.utils.auth import get_verified_user
from open_webui.constants import ERROR_MESSAGES
from open_webui.services.embedding_metrics import associate_pending_embeddings_with_message
from open_webui.routers.retrieval import pending_embedding_metadata


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


class AttachmentOut(BaseModel):
    id: str
    type: str
    file_id: Optional[str] = None
    url: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    meta: Optional[dict] = None


class MessageOut(ChatMessageModel):
    attachments: list[AttachmentOut] = []


class MessagesResponse(BaseModel):
    messages: list[MessageOut]
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None


############################
# GetMessagesBatch (for differential sync)
############################


class MessageWithCacheKey(MessageOut):
    cache_key: str
    files: Optional[list[dict]] = None
    sources: Optional[list] = None


class MessageBatchResponse(BaseModel):
    messages: list[MessageWithCacheKey]


@router.post("/{chat_id}/messages/batch", response_model=MessageBatchResponse)
async def get_messages_batch(
    chat_id: str,
    request: Request,
    user=Depends(get_verified_user)
):
    """
    Fetch multiple messages by ID for differential sync.
    Returns full message objects (including content, sources, files) with cache_keys.
    """
    try:
        # Manually parse the request body to bypass FastAPI validation
        # (needed because FastAPI was matching this route to /{id}/messages/{message_id} in chats router)
        body = await request.json()
        
        # Extract message_ids from body
        if isinstance(body, dict) and "message_ids" in body:
            message_ids = body["message_ids"]
        elif isinstance(body, list):
            message_ids = body
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Request body must contain 'message_ids' array or be an array of message IDs"
            )
        
        # Validate message_ids
        if not isinstance(message_ids, list) or not all(isinstance(id, str) for id in message_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="message_ids must be a list of strings"
            )
        
        # Fetch messages by IDs and verify access efficiently
        with get_db() as db:
            # Fast access check using optimized function
            if not Chats.has_chat_access(chat_id, user.id, db=db):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
                )
            
            messages = db.query(ChatMessage).filter(
                ChatMessage.chat_id == chat_id,
                ChatMessage.id.in_(message_ids)
            ).all()
            
            # Verify all requested messages belong to this chat
            found_ids = {str(m.id) for m in messages}
            missing_ids = set(message_ids) - found_ids
            if missing_ids:
                log.warning(f"Some message IDs not found in chat {chat_id}: {missing_ids}")
            
            # Convert to models
            msg_models = [ChatMessageModel.model_validate(m) for m in messages]
            
            # Get attachments for these messages
            ids = [m.id for m in msg_models]
            attachments_map: dict[str, list[AttachmentOut]] = {i: [] for i in ids}
            if ids:
                rows = (
                    db.query(ChatMessageAttachment)
                    .filter(ChatMessageAttachment.message_id.in_(ids))
                    .all()
                )
                for r in rows:
                    attachments_map[r.message_id].append(
                        AttachmentOut(
                            id=r.id,
                            type=r.type,
                            file_id=r.file_id,
                            url=r.url,
                            mime_type=r.mime_type,
                            size_bytes=r.size_bytes,
                            meta=r.meta,
                        )
                    )
            
            # Build response with cache keys and attachments
            from open_webui.models.chat_messages import compute_cache_key
            
            result_messages = []
            for msg_model in msg_models:
                # Get the database message object to compute cache key
                db_msg = next((m for m in messages if str(m.id) == msg_model.id), None)
                if not db_msg:
                    continue
                
                cache_key = compute_cache_key(db_msg)
                
                # Build message with files and sources from meta/attachments
                msg_dict = msg_model.model_dump()
                msg_dict["attachments"] = attachments_map.get(msg_model.id, [])
                
                # Extract files and sources from meta if present
                files = []
                sources = None
                if msg_model.meta and isinstance(msg_model.meta, dict):
                    if "files" in msg_model.meta:
                        files = msg_model.meta["files"]
                    if "sources" in msg_model.meta:
                        sources = msg_model.meta["sources"]
                    # Extract root-level properties that are stored in meta
                    if "modelIdx" in msg_model.meta:
                        msg_dict["modelIdx"] = msg_model.meta["modelIdx"]
                    if "modelName" in msg_model.meta:
                        msg_dict["modelName"] = msg_model.meta["modelName"]
                    if "models" in msg_model.meta:
                        msg_dict["models"] = msg_model.meta["models"]
                
                # Reconstruct files from attachments
                attachment_files = []
                for att in attachments_map.get(msg_model.id, []):
                    if att.file_id:
                        attachment_files.append({
                            "id": att.file_id,
                            "type": att.type,
                            "url": att.url or f"/api/v1/files/{att.file_id}/content",
                            "mime_type": att.mime_type,
                            "meta": att.meta or {}
                        })
                
                # Merge files from meta and attachments (deduplicate by id)
                all_files = {f.get("id"): f for f in files}
                for f in attachment_files:
                    if f.get("id") and f["id"] not in all_files:
                        all_files[f["id"]] = f
                files = list(all_files.values())
                
                # Create message with cache_key, files, and sources
                result_msg = MessageWithCacheKey(
                    **msg_dict,
                    cache_key=cache_key,
                    files=files if files else None,
                    sources=sources
                )
                result_messages.append(result_msg)
            
            return MessageBatchResponse(messages=result_messages)
    except HTTPException:
        raise
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{chat_id}/messages", response_model=MessagesResponse)
async def get_chat_messages(
    chat_id: str,
    leaf_id: Optional[str] = Query(None, description="Leaf message id to retrieve branch"),
    parent_id: Optional[str] = Query(None, description="List children of parent id"),
    user=Depends(get_verified_user),
):
    try:
        if leaf_id:
            base_msgs = ChatMessages.get_branch_to_root(chat_id, leaf_id)
        else:
            base_msgs = ChatMessages.list_children(chat_id, parent_id)

        # collect attachments for these messages
        ids = [m.id for m in base_msgs]
        attachments_map: dict[str, list[AttachmentOut]] = {i: [] for i in ids}
        if ids:
            with get_db() as db:
                rows = (
                    db.query(ChatMessageAttachment)
                    .filter(ChatMessageAttachment.message_id.in_(ids))
                    .all()
                )
                for r in rows:
                    attachments_map[r.message_id].append(
                        AttachmentOut(
                            id=r.id,
                            type=r.type,
                            file_id=r.file_id,
                            url=r.url,
                            mime_type=r.mime_type,
                            size_bytes=r.size_bytes,
                            meta=r.meta,
                        )
                    )

        out = [MessageOut(
            **m.model_dump(), attachments=attachments_map.get(m.id, [])) for m in base_msgs]
        return {"messages": out}
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{chat_id}/messages", response_model=ChatMessageModel)
async def create_chat_message(
    chat_id: str, form: MessageCreateForm, user=Depends(get_verified_user)
):
    try:
        message = ChatMessages.insert_message(chat_id, form)

        # Associate pending embeddings with this message if it has file attachments
        if message and form.attachments:
            file_ids = [att.get("file_id") for att in form.attachments if att.get("file_id")]
            if file_ids:
                associate_pending_embeddings_with_message(
                    file_ids=file_ids,
                    chat_id=chat_id,
                    message_id=message.id,
                    pending_metadata=pending_embedding_metadata,
                )

        return message
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{chat_id}/messages/all", response_model=MessagesResponse)
async def get_all_chat_messages(chat_id: str, user=Depends(get_verified_user)):
    try:
        with get_db() as db:
            msgs = db.query(ChatMessage).filter_by(chat_id=chat_id).order_by(ChatMessage.created_at.asc()).all()
            msg_models = [ChatMessageModel.model_validate(m) for m in msgs]

            ids = [m.id for m in msg_models]
            attachments_map: dict[str, list[AttachmentOut]] = {i: [] for i in ids}
            if ids:
                rows = (
                    db.query(ChatMessageAttachment)
                    .filter(ChatMessageAttachment.message_id.in_(ids))
                    .all()
                )
                for r in rows:
                    attachments_map[r.message_id].append(
                        AttachmentOut(
                            id=r.id,
                            type=r.type,
                            file_id=r.file_id,
                            url=r.url,
                            mime_type=r.mime_type,
                            size_bytes=r.size_bytes,
                            meta=r.meta,
                        )
                    )

            out = [MessageOut(**m.model_dump(), attachments=attachments_map.get(m.id, [])) for m in msg_models]
            return {"messages": out}
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


