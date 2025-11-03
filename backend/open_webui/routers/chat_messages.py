import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
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

        out = [MessageOut(**m.model_dump(), attachments=attachments_map.get(m.id, [])) for m in base_msgs]
        return {"messages": out}
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{chat_id}/messages", response_model=ChatMessageModel)
async def create_chat_message(
    chat_id: str, form: MessageCreateForm, user=Depends(get_verified_user)
):
    try:
        return ChatMessages.insert_message(chat_id, form)
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


