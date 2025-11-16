import json
import logging
from typing import Optional


from open_webui.socket.main import get_event_emitter
from open_webui.models.chats import (
    ChatForm,
    ChatImportForm,
    ChatResponse,
    Chats,
    ChatTitleIdResponse,
)
from open_webui.models.tags import TagModel, Tags
from open_webui.models.folders import Folders

from open_webui.config import ENABLE_ADMIN_CHAT_ACCESS, ENABLE_ADMIN_EXPORT
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import SRC_LOG_LEVELS
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from pydantic import BaseModel


from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.access_control import has_permission
from open_webui.internal.db import get_db

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


############################
# Response Models
############################


class ChatMetadataResponse(BaseModel):
    """Lean response model with only essential fields for chat listing/selection"""
    id: str
    title: str
    updated_at: int
    created_at: int
    pinned: Optional[bool] = False
    folder_id: Optional[str] = None

############################
# GetChatList
############################


@router.get("/", response_model=list[ChatTitleIdResponse])
@router.get("/list", response_model=list[ChatTitleIdResponse])
async def get_session_user_chat_list(
    user=Depends(get_verified_user), page: Optional[int] = None
):
    if page is not None:
        limit = 60
        skip = (page - 1) * limit

        return Chats.get_chat_title_id_list_by_user_id(user.id, skip=skip, limit=limit)
    else:
        return Chats.get_chat_title_id_list_by_user_id(user.id)


############################
# DeleteAllChats
############################


@router.delete("/", response_model=bool)
async def delete_all_user_chats(request: Request, user=Depends(get_verified_user)):

    if user.role == "user" and not has_permission(
        user.id, "chat.delete", request.app.state.config.USER_PERMISSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    result = Chats.delete_chats_by_user_id(user.id)
    return result


############################
# GetUserChatList
############################


@router.get("/list/user/{user_id}", response_model=list[ChatTitleIdResponse])
async def get_user_chat_list_by_user_id(
    user_id: str,
    user=Depends(get_admin_user),
    skip: int = 0,
    limit: int = 50,
):
    if not ENABLE_ADMIN_CHAT_ACCESS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    return Chats.get_chat_list_by_user_id(
        user_id, include_archived=True, skip=skip, limit=limit
    )


############################
# CreateNewChat
############################


@router.post("/new", response_model=Optional[ChatResponse])
async def create_new_chat(form_data: ChatForm, user=Depends(get_verified_user)):
    try:
        # Create chat with legacy format in chat.chat blob initially
        # Messages will be inserted via middleware during streaming
        chat = Chats.insert_new_chat(user.id, form_data)
        
        # If the chat form has initial messages/history, convert to normalized format
        # Legacy format includes BOTH history.messages (dict) AND messages (list)
        # We should check for history.messages first as it contains all messages
        has_messages = False
        if form_data.chat and isinstance(form_data.chat, dict):
            if "history" in form_data.chat:
                history = form_data.chat["history"]
                if isinstance(history, dict) and history.get("messages"):
                    has_messages = True
            # Also check for flat messages list as fallback
            if not has_messages and "messages" in form_data.chat and isinstance(form_data.chat["messages"], list) and len(form_data.chat["messages"]) > 0:
                has_messages = True
        
        if chat and chat.id and has_messages:
            from open_webui.models.chat_converter import legacy_to_normalized_format
            try:
                # Regenerate message IDs during import to avoid collisions
                legacy_to_normalized_format(chat.id, form_data.chat, regenerate_ids=True)
            except Exception as e:
                log.error(f"create_new_chat: Exception during legacy_to_normalized_format: {str(e)}", exc_info=True)
                raise
        
        return ChatResponse(**chat.model_dump())
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# ImportChat
############################


@router.post("/import", response_model=Optional[ChatResponse])
async def import_chat(form_data: ChatImportForm, user=Depends(get_verified_user)):
    try:
        chat = Chats.import_chat(user.id, form_data)
        if chat:
            tags = chat.meta.get("tags", [])
            for tag_id in tags:
                tag_id = tag_id.replace(" ", "_").lower()
                tag_name = " ".join([word.capitalize() for word in tag_id.split("_")])
                if (
                    tag_id != "none"
                    and Tags.get_tag_by_name_and_user_id(tag_name, user.id) is None
                ):
                    Tags.insert_new_tag(tag_name, user.id)
            
            # Convert legacy format to normalized format if chat has messages
            # Legacy format includes BOTH history.messages (dict) AND messages (list)
            # We should check for history.messages first as it contains all messages
            has_messages = False
            if form_data.chat and isinstance(form_data.chat, dict):
                if "history" in form_data.chat:
                    history = form_data.chat["history"]
                    if isinstance(history, dict) and history.get("messages"):
                        has_messages = True
                        log.debug(f"import_chat: Found messages in history.messages (dict format)")
                # Also check for flat messages list as fallback
                if not has_messages and "messages" in form_data.chat and isinstance(form_data.chat["messages"], list) and len(form_data.chat["messages"]) > 0:
                    has_messages = True
                    log.debug(f"import_chat: Found messages in messages list (flat format)")
            
            if chat.id and has_messages:
                log.debug(f"import_chat: Converting legacy format to normalized format for chat {chat.id}")
                from open_webui.models.chat_converter import legacy_to_normalized_format
                try:
                    # Regenerate message IDs during import to avoid collisions
                    legacy_to_normalized_format(chat.id, form_data.chat, regenerate_ids=True)
                except Exception as e:
                    log.error(f"import_chat: Exception during legacy_to_normalized_format: {str(e)}", exc_info=True)
                    raise
            elif chat.id:
                log.warning(f"import_chat: No messages found in imported chat {chat.id}. Chat keys: {list(form_data.chat.keys()) if isinstance(form_data.chat, dict) else 'not a dict'}")

        return ChatResponse(**chat.model_dump())
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# GetChats
############################


@router.get("/search", response_model=list[ChatTitleIdResponse])
async def search_user_chats(
    text: str, page: Optional[int] = None, user=Depends(get_verified_user)
):
    if page is None:
        page = 1

    limit = 60
    skip = (page - 1) * limit

    chat_list = [
        ChatTitleIdResponse(**chat.model_dump())
        for chat in Chats.get_chats_by_user_id_and_search_text(
            user.id, text, skip=skip, limit=limit
        )
    ]

    # Delete tag if no chat is found
    words = text.strip().split(" ")
    if page == 1 and len(words) == 1 and words[0].startswith("tag:"):
        tag_id = words[0].replace("tag:", "")
        if len(chat_list) == 0:
            if Tags.get_tag_by_name_and_user_id(tag_id, user.id):
                log.debug(f"deleting tag: {tag_id}")
                Tags.delete_tag_by_name_and_user_id(tag_id, user.id)

    return chat_list


############################
# GetChatsByFolderId
############################


@router.get("/folder/{folder_id}", response_model=list[ChatResponse])
async def get_chats_by_folder_id(folder_id: str, user=Depends(get_verified_user)):
    folder_ids = [folder_id]
    children_folders = Folders.get_children_folders_by_id_and_user_id(
        folder_id, user.id
    )
    if children_folders:
        folder_ids.extend([folder.id for folder in children_folders])

    return [
        ChatResponse(**chat.model_dump())
        for chat in Chats.get_chats_by_folder_ids_and_user_id(folder_ids, user.id)
    ]


############################
# GetPinnedChats
############################


@router.get("/pinned", response_model=list[ChatResponse])
async def get_user_pinned_chats(user=Depends(get_verified_user)):
    return [
        ChatResponse(**chat.model_dump())
        for chat in Chats.get_pinned_chats_by_user_id(user.id)
    ]


############################
# GetPinnedChatsMetadata
############################


@router.get("/pinned/metadata", response_model=list[ChatMetadataResponse])
async def get_user_pinned_chats_metadata(user=Depends(get_verified_user)):
    """
    Returns a lean list of pinned chats with only essential fields.
    Excludes full chat JSON and other heavy fields to reduce payload size.
    """
    pinned_chats = Chats.get_pinned_chats_by_user_id(user.id)
    
    return [
        ChatMetadataResponse(
            id=chat.id,
            title=chat.title,
            updated_at=chat.updated_at,
            created_at=chat.created_at,
            pinned=chat.pinned,
            folder_id=chat.folder_id,
        )
        for chat in pinned_chats
    ]


############################
# GetChats
############################


@router.get("/all", response_model=list[ChatResponse])
async def get_user_chats(user=Depends(get_verified_user), export: bool = Query(False)):
    from open_webui.models.chat_converter import normalized_to_legacy_format
    from open_webui.models.chat_messages import ChatMessage
    
    chats = Chats.get_chats_by_user_id(user.id)
    result = []
    
    for chat in chats:
        # Check if this chat uses normalized storage (has messages in chat_message table)
        with get_db() as db:
            has_normalized = db.query(ChatMessage).filter_by(chat_id=chat.id).first() is not None
        
        if has_normalized:
            # Convert from normalized tables to legacy format
            # If export=True, embed files as base64 for portability
            legacy_chat = normalized_to_legacy_format(chat.id, embed_files_as_base64=export)
            # Merge with chat metadata
            chat.chat = legacy_chat
        
        result.append(ChatResponse(**chat.model_dump()))
    
    return result


############################
# GetArchivedChats
############################


@router.get("/all/archived", response_model=list[ChatResponse])
async def get_user_archived_chats(user=Depends(get_verified_user), export: bool = Query(False)):
    from open_webui.models.chat_converter import normalized_to_legacy_format
    from open_webui.models.chat_messages import ChatMessage
    
    chats = Chats.get_archived_chats_by_user_id(user.id)
    result = []
    
    for chat in chats:
        # Check if this chat uses normalized storage (has messages in chat_message table)
        with get_db() as db:
            has_normalized = db.query(ChatMessage).filter_by(chat_id=chat.id).first() is not None
        
        if has_normalized:
            # Convert from normalized tables to legacy format
            # If export=True, embed files as base64 for portability
            legacy_chat = normalized_to_legacy_format(chat.id, embed_files_as_base64=export)
            # Merge with chat metadata
            chat.chat = legacy_chat
        
        result.append(ChatResponse(**chat.model_dump()))
    
    return result


############################
# GetAllTags
############################


@router.get("/all/tags", response_model=list[TagModel])
async def get_all_user_tags(user=Depends(get_verified_user)):
    try:
        tags = Tags.get_tags_by_user_id(user.id)
        return tags
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# GetAllChatsInDB
############################


@router.get("/all/db", response_model=list[ChatResponse])
async def get_all_user_chats_in_db(user=Depends(get_admin_user), export: bool = Query(False)):
    if not ENABLE_ADMIN_EXPORT:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    
    from open_webui.models.chat_converter import normalized_to_legacy_format
    from open_webui.models.chat_messages import ChatMessage
    
    chats = Chats.get_chats()
    result = []
    
    for chat in chats:
        # Check if this chat uses normalized storage (has messages in chat_message table)
        with get_db() as db:
            has_normalized = db.query(ChatMessage).filter_by(chat_id=chat.id).first() is not None
        
        if has_normalized:
            # Convert from normalized tables to legacy format
            legacy_chat = normalized_to_legacy_format(chat.id)
            # Merge with chat metadata
            chat.chat = legacy_chat
        
        result.append(ChatResponse(**chat.model_dump()))
    
    return result


############################
# GetArchivedChats
############################


@router.get("/archived", response_model=list[ChatTitleIdResponse])
async def get_archived_session_user_chat_list(
    user=Depends(get_verified_user), skip: int = 0, limit: int = 50
):
    return Chats.get_archived_chat_list_by_user_id(user.id, skip, limit)


############################
# ArchiveAllChats
############################


@router.post("/archive/all", response_model=bool)
async def archive_all_chats(user=Depends(get_verified_user)):
    return Chats.archive_all_chats_by_user_id(user.id)


############################
# GetSharedChatById
############################


@router.get("/share/{share_id}", response_model=Optional[ChatResponse])
async def get_shared_chat_by_id(share_id: str, user=Depends(get_verified_user)):
    if user.role == "pending":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if user.role == "user" or (user.role == "admin" and not ENABLE_ADMIN_CHAT_ACCESS):
        chat = Chats.get_chat_by_share_id(share_id)
    elif user.role == "admin" and ENABLE_ADMIN_CHAT_ACCESS:
        chat = Chats.get_chat_by_id(share_id)

    if chat:
        return ChatResponse(**chat.model_dump())

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.NOT_FOUND
        )


############################
# GetChatsByTags
############################


class TagForm(BaseModel):
    name: str


class TagFilterForm(TagForm):
    skip: Optional[int] = 0
    limit: Optional[int] = 50


@router.post("/tags", response_model=list[ChatTitleIdResponse])
async def get_user_chat_list_by_tag_name(
    form_data: TagFilterForm, user=Depends(get_verified_user)
):
    chats = Chats.get_chat_list_by_user_id_and_tag_name(
        user.id, form_data.name, form_data.skip, form_data.limit
    )
    if len(chats) == 0:
        Tags.delete_tag_by_name_and_user_id(form_data.name, user.id)

    return chats


############################
# GetChatById
############################


@router.get("/{id}", response_model=Optional[ChatResponse])
async def get_chat_by_id(id: str, user=Depends(get_verified_user), export: bool = Query(False)):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.NOT_FOUND
        )
    
    # Check if this chat uses normalized storage (has messages in chat_message table)
    from open_webui.models.chat_messages import ChatMessages
    from open_webui.models.chat_converter import normalized_to_legacy_format
    
    # Check if chat has normalized messages
    with get_db() as db:
        from open_webui.models.chat_messages import ChatMessage
        has_normalized = db.query(ChatMessage).filter_by(chat_id=id).first() is not None
    
    if has_normalized:
        # Convert from normalized tables to legacy format
        # If export=True, embed files as base64 for portability
        legacy_chat = normalized_to_legacy_format(id, embed_files_as_base64=export)
        # Merge with chat metadata
        chat.chat = legacy_chat
    else:
        # Legacy chat, use existing chat.chat blob
        pass
    
    return ChatResponse(**chat.model_dump())


############################
# GetChatMeta (lightweight)
############################


class ChatMetaResponse(BaseModel):
    id: str
    title: str
    created_at: int
    updated_at: int
    share_id: Optional[str] = None
    archived: bool
    pinned: Optional[bool] = False
    folder_id: Optional[str] = None
    active_message_id: Optional[str] = None
    # minimal chat-level fields commonly used by the UI
    models: list[str] | None = None
    params: dict | None = None
    files: list[dict] | None = None


@router.get("/{id}/meta", response_model=Optional[ChatMetaResponse])
async def get_chat_meta_by_id(id: str, user=Depends(get_verified_user)):
    # TODO make this quicker. idk how but it takes WAY too long right now
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    # Extract minimal fields without returning the full chat JSON
    chat_content = chat.chat or {}
    
    # Check if this chat uses normalized storage (has messages in chat_message table)
    from open_webui.models.chat_messages import ChatMessage
    models = None
    params = chat_content.get("params")
    
    with get_db() as db:
        has_normalized = db.query(ChatMessage).filter_by(chat_id=id).first() is not None
    
    if has_normalized:
        # For normalized chats, extract models from first user message's meta
        # (models are stored in user message meta, not in chat.chat.models)
        with get_db() as db:
            first_user_msg = db.query(ChatMessage).filter_by(
                chat_id=id,
                role="user"
            ).order_by(ChatMessage.created_at.asc()).first()
            
            if first_user_msg is not None:
                msg_meta = getattr(first_user_msg, 'meta', None)
                if msg_meta and isinstance(msg_meta, dict) and "models" in msg_meta:
                    models = msg_meta["models"]
        
        # For normalized chats, params are stored in chat.params column, not chat.chat.params
        if chat.params:
            params = chat.params
    else:
        # Legacy chat, use existing chat.chat blob
        models = chat_content.get("models")
        if not params:
            params = chat_content.get("params")
    
    return ChatMetaResponse(
        **{
            "id": chat.id,
            "title": chat.title,
            "created_at": chat.created_at,
            "updated_at": chat.updated_at,
            "share_id": chat.share_id,
            "archived": chat.archived,
            "pinned": chat.pinned,
            "folder_id": chat.folder_id,
            "active_message_id": getattr(chat, 'active_message_id', None),
            "models": models,
            "params": params,
            "files": chat_content.get("files"),
        }
    )


############################
# GetChatSync (lightweight with cache keys for differential sync)
############################


class MessageMetadata(BaseModel):
    """Lightweight message metadata with cache key (no content/sources/files)"""
    id: str
    cache_key: str
    parent_id: Optional[str] = None
    role: str
    model_id: Optional[str] = None
    position: Optional[int] = None
    created_at: int
    updated_at: int
    children_ids: list[str] = []


class ChatSyncResponse(BaseModel):
    id: str
    title: str
    models: list[str] | None = None
    params: dict | None = None
    files: list[dict] | None = None
    history: dict  # { messages: { id: MessageMetadata }, currentId: str }
    messages: list[dict]  # Array of message IDs with cache_keys (current branch, no content/sources/files)


@router.get("/{id}/sync", response_model=Optional[ChatSyncResponse])
async def get_chat_sync(id: str, user=Depends(get_verified_user)):
    """
    Get lightweight chat metadata with message cache keys for differential sync.
    Returns message metadata (no content/sources/files) so client can determine what needs to be fetched.
    """
    from open_webui.models.chat_messages import ChatMessage, compute_cache_key
    from open_webui.models.chats import Chat
    
    # Optimized: Only load minimal Chat fields (id, title, params, active_message_id) - skip huge chat.chat JSON blob
    # All chats are normalized now, so we don't need the legacy fallback
    # Use with_entities to select only specific columns (avoids loading chat.chat JSON blob)
    with get_db() as db:
        chat_row = db.query(
            Chat.id,
            Chat.title,
            Chat.params,
            Chat.user_id,
            Chat.active_message_id
        ).filter_by(id=id, user_id=user.id).first()
        
        if not chat_row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
            )
        
        # Extract only what we need (chat_row is a tuple-like Row object)
        chat_id = str(chat_row.id) if chat_row.id else id
        chat_title = str(chat_row.title) if chat_row.title else "New Chat"
        chat_params = chat_row.params if chat_row.params and isinstance(chat_row.params, dict) else {}
        chat_active_message_id = str(chat_row.active_message_id) if chat_row.active_message_id else None
    
    # Get all messages for this chat - only load columns we actually need!
    # Use SQL LENGTH() function to get content length without loading the full content_text
    # This avoids loading large JSON fields (meta, status, etc.) and huge TEXT fields
    with get_db() as db:
        from sqlalchemy import func
        # Query with content_length computed in SQL to avoid loading huge content_text
        messages_with_length = db.query(
            ChatMessage.id,
            ChatMessage.parent_id,
            ChatMessage.role,
            ChatMessage.model_id,
            ChatMessage.position,
            ChatMessage.created_at,
            ChatMessage.updated_at,
            func.coalesce(func.length(ChatMessage.content_text), 0).label('content_length')
        ).filter_by(chat_id=id).order_by(ChatMessage.created_at.asc()).all()
        
        # Convert to a format we can work with
        class MessageData:
            def __init__(self, row):
                self.id = row.id
                self.parent_id = row.parent_id
                self.role = row.role
                self.model_id = row.model_id
                self.position = row.position
                self.created_at = row.created_at
                self.updated_at = row.updated_at
                self.content_length = row.content_length
        
        all_messages = [MessageData(row) for row in messages_with_length]
    
    # Batch fetch all children relationships at once (much faster than per-message queries)
    # Only load id and parent_id columns
    message_ids = [str(m.id) for m in all_messages if m.id]
    children_map: dict[str, list[str]] = {}
    if message_ids:
        with get_db() as db:
            all_children = db.query(
                ChatMessage.id,
                ChatMessage.parent_id,
                ChatMessage.position,
                ChatMessage.created_at
            ).filter(
                ChatMessage.parent_id.in_([m.id for m in all_messages if m.id])
            ).order_by(
                ChatMessage.position.asc(),
                ChatMessage.created_at.asc()
            ).all()
            # Group children by parent_id (all_children is now Row objects with .id, .parent_id, etc.)
            for child in all_children:
                if child.parent_id:
                    parent_id_str = str(child.parent_id)
                    if parent_id_str not in children_map:
                        children_map[parent_id_str] = []
                    if child.id:
                        children_map[parent_id_str].append(str(child.id))
    
    # Compute cache keys in parallel for better performance
    from concurrent.futures import ThreadPoolExecutor
    
    def compute_cache_key_sync(msg) -> tuple[str, str]:
        """Compute cache key for a message (synchronous version for ThreadPoolExecutor)"""
        msg_id_str = str(msg.id) if msg.id else None
        cache_key = compute_cache_key(msg)
        return msg_id_str, cache_key
    
    # Use ThreadPoolExecutor to compute cache keys in parallel
    cache_keys_map: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=min(10, len(all_messages))) as executor:
        futures = [executor.submit(compute_cache_key_sync, msg) for msg in all_messages if msg.id]
        for future in futures:
            msg_id_str, cache_key = future.result()
            if msg_id_str:
                cache_keys_map[msg_id_str] = cache_key
    
    # Build history.messages dict with metadata only (no content/sources/files)
    messages_metadata: dict[str, MessageMetadata] = {}
    for msg in all_messages:
        msg_id_str = str(msg.id) if msg.id else None
        if not msg_id_str:
            continue
        
        # Get children IDs from pre-computed map
        children_ids = children_map.get(msg_id_str, [])
        
        # Get cache key from pre-computed map
        cache_key = cache_keys_map.get(msg_id_str, "")
        
        messages_metadata[msg_id_str] = MessageMetadata(
            id=msg_id_str,
            cache_key=cache_key,
            parent_id=str(msg.parent_id) if msg.parent_id else None,
            role=msg.role or "",
            model_id=msg.model_id,
            position=msg.position,
            created_at=int(msg.created_at) if msg.created_at else 0,
            updated_at=int(msg.updated_at) if msg.updated_at else 0,
            children_ids=children_ids
        )
    
    # Build messages array (current branch) with only IDs and cache_keys
    current_id = chat_active_message_id
    if not current_id and all_messages:
        # Find the deepest leaf message
        parent_ids = {str(c.parent_id) for c in all_messages if c.parent_id}
        leaves = [m for m in all_messages if str(m.id) not in parent_ids]
        if leaves:
            leaves.sort(key=lambda m: int(m.created_at) if m.created_at else 0, reverse=True)
            current_id = str(leaves[0].id) if leaves[0].id else None
    
    messages_list = []
    if current_id:
        # Walk back from currentId to build the branch
        msg_map = {str(m.id): m for m in all_messages if m.id}
        cur = msg_map.get(str(current_id))
        branch = []
        while cur:
            branch.append(cur)
            if cur.parent_id:
                cur = msg_map.get(str(cur.parent_id))
            else:
                break
        branch.reverse()
        
        for msg in branch:
            msg_id_str = str(msg.id) if msg.id else None
            if msg_id_str and msg_id_str in messages_metadata:
                # Reuse cache key from messages_metadata instead of recomputing
                cache_key = messages_metadata[msg_id_str].cache_key
                messages_list.append({
                    "id": msg_id_str,
                    "cache_key": cache_key
                })
    
    # Get models from first user message's meta
    # Note: We need to query this separately since we didn't load meta in the main query
    models = None
    first_user_msg = next((m for m in all_messages if m.role == "user"), None)
    if first_user_msg:
        # Load meta only for the first user message
        with get_db() as db:
            first_user_msg_with_meta = db.query(ChatMessage.meta).filter_by(id=first_user_msg.id).first()
            if first_user_msg_with_meta and first_user_msg_with_meta.meta and isinstance(first_user_msg_with_meta.meta, dict) and "models" in first_user_msg_with_meta.meta:
                models = first_user_msg_with_meta.meta["models"]
    
    # Get params (already loaded above)
    params = chat_params
    
    # Get files - for normalized chats, files are stored in chat.chat.files
    # But we don't want to load the entire chat.chat JSON blob just for files
    # For now, we'll skip files in sync endpoint (they're not needed for differential sync)
    # If files are needed, we can add a separate lightweight query or store them elsewhere
    files = None
    
    # Convert messages_metadata to dict format for response
    history_messages_dict = {k: v.model_dump() for k, v in messages_metadata.items()}
    
    # Build response
    return ChatSyncResponse(
        id=chat_id,
        title=chat_title,
        models=models,
        params=params,
        files=files,  # None for now - files not needed for sync
        history={
            "messages": history_messages_dict,
            "currentId": current_id
        },
        messages=messages_list
    )


############################
# UpdateChatById
############################


@router.post("/{id}", response_model=Optional[ChatResponse])
async def update_chat_by_id(
    id: str, form_data: ChatForm, user=Depends(get_verified_user)
):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    
    # Check if this chat uses normalized storage
    from open_webui.models.chat_messages import ChatMessage
    from open_webui.models.chat_converter import legacy_to_normalized_format, normalized_to_legacy_format
    from open_webui.models.chats import Chat
    
    with get_db() as db:
        has_normalized = db.query(ChatMessage).filter_by(chat_id=id).first() is not None
    
    if has_normalized:
        # Convert legacy format to normalized tables
        legacy_to_normalized_format(id, form_data.chat)
        
        # Update chat metadata (title, params, etc.)
        if "title" in form_data.chat:
            Chats.update_chat_title_by_id(id, form_data.chat["title"])
        if "params" in form_data.chat:
            # Clean params - remove models if present (models should be in user message meta, not params)
            params_clean = form_data.chat["params"].copy() if isinstance(form_data.chat["params"], dict) else {}
            if "models" in params_clean:
                del params_clean["models"]
            with get_db() as db:
                chat_item = db.query(Chat).filter_by(id=id).first()
                if chat_item:
                    # Type ignore: SQLAlchemy Column assignment works at runtime
                    chat_item.params = params_clean  # type: ignore
                    db.commit()
        # Update models: store in first user message's meta (NOT in params)
        if "models" in form_data.chat:
            from open_webui.models.chat_messages import ChatMessages, ChatMessage
            with get_db() as db:
                # Find the first user message and update its meta
                first_user_msg = db.query(ChatMessage).filter_by(
                    chat_id=id,
                    role="user"
                ).order_by(ChatMessage.created_at.asc()).first()
                
                if first_user_msg:
                    existing_meta = first_user_msg.meta if first_user_msg.meta else {}
                    existing_meta["models"] = form_data.chat["models"]
                    ChatMessages.update_message(first_user_msg.id, meta=existing_meta)
        
        # Update active_message_id if history.currentId is present
        # This handles both full history updates and lightweight updates that only send currentId
        if "history" in form_data.chat and isinstance(form_data.chat["history"], dict):
            history_current_id = form_data.chat["history"].get("currentId")
            if history_current_id:
                Chats.update_chat_active_and_root_message_ids(id, active_message_id=history_current_id)
        
        # Generate legacy response for the API response (includes full message history)
        legacy_chat_response = normalized_to_legacy_format(id)
        
        # Persist only minimal chat metadata (no message history) to the database
        # Read current chat blob and merge only metadata fields
        with get_db() as db:
            from open_webui.models.chats import Chat
            chat_item = db.query(Chat).filter_by(id=id).first()
            if chat_item:
                existing_chat = chat_item.chat if chat_item.chat else {}
                # Update only metadata fields, preserve anything else that might be there
                minimal_chat = dict(existing_chat)
                # Strip collections from chat-level files to remove files array and data.file_ids
                files_list = legacy_chat_response.get("files", [])
                if isinstance(files_list, list):
                    from open_webui.models.chat_converter import strip_collection_files
                    minimal_chat["files"] = [strip_collection_files(f) for f in files_list]
                else:
                    minimal_chat["files"] = files_list
                minimal_chat["params"] = legacy_chat_response.get("params", {})
                minimal_chat["models"] = legacy_chat_response.get("models", [])
                if "title" in legacy_chat_response:
                    minimal_chat["title"] = legacy_chat_response["title"]
                # Explicitly remove history and messages if present
                if "history" in minimal_chat:
                    del minimal_chat["history"]
                if "messages" in minimal_chat:
                    del minimal_chat["messages"]
                chat_item.chat = minimal_chat
                db.commit()

        # Reload chat model for response with full legacy payload
        chat = Chats.get_chat_by_id_and_user_id(id, user.id)
        if chat:
            chat_data = chat.model_dump()
            chat_data["chat"] = legacy_chat_response
            return ChatResponse(**chat_data)
    else:
        # Legacy chat, update the JSON blob
        updated_chat = {**chat.chat, **form_data.chat}
        chat = Chats.update_chat_by_id(id, updated_chat)
    
    return ChatResponse(**chat.model_dump())


############################
# UpdateChatMessageById
############################
class MessageForm(BaseModel):
    content: str


@router.post("/{id}/messages/{message_id}", response_model=Optional[ChatResponse])
async def update_chat_message_by_id(
    id: str, message_id: str, form_data: MessageForm, user=Depends(get_verified_user)
):
    chat = Chats.get_chat_by_id(id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    if chat.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    chat = Chats.upsert_message_to_chat_by_id_and_message_id(
        id,
        message_id,
        {
            "content": form_data.content,
        },
    )

    event_emitter = get_event_emitter(
        {
            "user_id": user.id,
            "chat_id": id,
            "message_id": message_id,
        },
        False,
    )

    if event_emitter:
        await event_emitter(
            {
                "type": "chat:message",
                "data": {
                    "chat_id": id,
                    "message_id": message_id,
                    "content": form_data.content,
                },
            }
        )

    return ChatResponse(**chat.model_dump())


############################
# SendChatMessageEventById
############################
class EventForm(BaseModel):
    type: str
    data: dict


@router.post("/{id}/messages/{message_id}/event", response_model=Optional[bool])
async def send_chat_message_event_by_id(
    id: str, message_id: str, form_data: EventForm, user=Depends(get_verified_user)
):
    chat = Chats.get_chat_by_id(id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    if chat.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    event_emitter = get_event_emitter(
        {
            "user_id": user.id,
            "chat_id": id,
            "message_id": message_id,
        }
    )

    try:
        if event_emitter:
            await event_emitter(form_data.model_dump())
        else:
            return False
        return True
    except:
        return False


############################
# DeleteChatById
############################


@router.delete("/{id}", response_model=bool)
async def delete_chat_by_id(request: Request, id: str, user=Depends(get_verified_user)):
    if user.role == "admin":
        chat = Chats.get_chat_by_id(id)
        for tag in chat.meta.get("tags", []):
            if Chats.count_chats_by_tag_name_and_user_id(tag, user.id) == 1:
                Tags.delete_tag_by_name_and_user_id(tag, user.id)

        result = Chats.delete_chat_by_id(id)

        return result
    else:
        if not has_permission(
            user.id, "chat.delete", request.app.state.config.USER_PERMISSIONS
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
            )

        chat = Chats.get_chat_by_id(id)
        for tag in chat.meta.get("tags", []):
            if Chats.count_chats_by_tag_name_and_user_id(tag, user.id) == 1:
                Tags.delete_tag_by_name_and_user_id(tag, user.id)

        result = Chats.delete_chat_by_id_and_user_id(id, user.id)
        return result


############################
# GetPinnedStatusById
############################


@router.get("/{id}/pinned", response_model=Optional[bool])
async def get_pinned_status_by_id(id: str, user=Depends(get_verified_user)):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        return chat.pinned
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# PinChatById
############################


@router.post("/{id}/pin", response_model=Optional[ChatResponse])
async def pin_chat_by_id(id: str, user=Depends(get_verified_user)):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        chat = Chats.toggle_chat_pinned_by_id(id)
        return chat
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# CloneChat
############################


class CloneForm(BaseModel):
    title: Optional[str] = None


@router.post("/{id}/clone", response_model=Optional[ChatResponse])
async def clone_chat_by_id(
    form_data: CloneForm, id: str, user=Depends(get_verified_user)
):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        # Use the new clone_chat method which handles normalized messages properly
        new_title = form_data.title if form_data.title else None
        cloned_chat = Chats.clone_chat(id, user.id, new_title)
        
        if cloned_chat:
            # Convert to legacy format for response if needed
            from open_webui.models.chat_converter import normalized_to_legacy_format
            from open_webui.models.chat_messages import ChatMessage
            from open_webui.internal.db import get_db
            
            with get_db() as db:
                has_normalized = db.query(ChatMessage).filter_by(chat_id=cloned_chat.id).first() is not None
            
            if has_normalized:
                # Convert from normalized tables to legacy format for response
                legacy_chat = normalized_to_legacy_format(cloned_chat.id)
                cloned_chat.chat = legacy_chat
            
            return ChatResponse(**cloned_chat.model_dump())
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="Failed to clone chat"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# CloneSharedChatById
############################


@router.post("/{id}/clone/shared", response_model=Optional[ChatResponse])
async def clone_shared_chat_by_id(id: str, user=Depends(get_verified_user)):

    if user.role == "admin":
        chat = Chats.get_chat_by_id(id)
    else:
        chat = Chats.get_chat_by_share_id(id)

    if chat:
        # Use the new clone_chat method which handles normalized messages properly
        cloned_chat = Chats.clone_chat(chat.id, user.id, None)
        
        if cloned_chat:
            # Convert to legacy format for response if needed
            from open_webui.models.chat_converter import normalized_to_legacy_format
            from open_webui.models.chat_messages import ChatMessage
            from open_webui.internal.db import get_db
            
            with get_db() as db:
                has_normalized = db.query(ChatMessage).filter_by(chat_id=cloned_chat.id).first() is not None
            
            if has_normalized:
                # Convert from normalized tables to legacy format for response
                legacy_chat = normalized_to_legacy_format(cloned_chat.id)
                cloned_chat.chat = legacy_chat
            
            return ChatResponse(**cloned_chat.model_dump())
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="Failed to clone chat"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# ArchiveChat
############################


@router.post("/{id}/archive", response_model=Optional[ChatResponse])
async def archive_chat_by_id(id: str, user=Depends(get_verified_user)):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        chat = Chats.toggle_chat_archive_by_id(id)

        # Delete tags if chat is archived
        if chat.archived:
            for tag_id in chat.meta.get("tags", []):
                if Chats.count_chats_by_tag_name_and_user_id(tag_id, user.id) == 0:
                    log.debug(f"deleting tag: {tag_id}")
                    Tags.delete_tag_by_name_and_user_id(tag_id, user.id)
        else:
            for tag_id in chat.meta.get("tags", []):
                tag = Tags.get_tag_by_name_and_user_id(tag_id, user.id)
                if tag is None:
                    log.debug(f"inserting tag: {tag_id}")
                    tag = Tags.insert_new_tag(tag_id, user.id)

        return ChatResponse(**chat.model_dump())
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# ShareChatById
############################


@router.post("/{id}/share", response_model=Optional[ChatResponse])
async def share_chat_by_id(id: str, user=Depends(get_verified_user)):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        if chat.share_id:
            shared_chat = Chats.update_shared_chat_by_chat_id(chat.id)
            return ChatResponse(**shared_chat.model_dump())

        shared_chat = Chats.insert_shared_chat_by_chat_id(chat.id)
        if not shared_chat:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ERROR_MESSAGES.DEFAULT(),
            )
        return ChatResponse(**shared_chat.model_dump())

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )


############################
# DeletedSharedChatById
############################


@router.delete("/{id}/share", response_model=Optional[bool])
async def delete_shared_chat_by_id(id: str, user=Depends(get_verified_user)):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        if not chat.share_id:
            return False

        result = Chats.delete_shared_chat_by_chat_id(id)
        update_result = Chats.update_chat_share_id_by_id(id, None)

        return result and update_result != None
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )


############################
# UpdateChatFolderIdById
############################


class ChatFolderIdForm(BaseModel):
    folder_id: Optional[str] = None


@router.post("/{id}/folder", response_model=Optional[ChatResponse])
async def update_chat_folder_id_by_id(
    id: str, form_data: ChatFolderIdForm, user=Depends(get_verified_user)
):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        chat = Chats.update_chat_folder_id_by_id_and_user_id(
            id, user.id, form_data.folder_id
        )
        return ChatResponse(**chat.model_dump())
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# GetChatTagsById
############################


@router.get("/{id}/tags", response_model=list[TagModel])
async def get_chat_tags_by_id(id: str, user=Depends(get_verified_user)):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        tags = chat.meta.get("tags", [])
        return Tags.get_tags_by_ids_and_user_id(tags, user.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.NOT_FOUND
        )


############################
# AddChatTagById
############################


@router.post("/{id}/tags", response_model=list[TagModel])
async def add_tag_by_id_and_tag_name(
    id: str, form_data: TagForm, user=Depends(get_verified_user)
):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        tags = chat.meta.get("tags", [])
        tag_id = form_data.name.replace(" ", "_").lower()

        if tag_id == "none":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Tag name cannot be 'None'"),
            )

        if tag_id not in tags:
            Chats.add_chat_tag_by_id_and_user_id_and_tag_name(
                id, user.id, form_data.name
            )

        chat = Chats.get_chat_by_id_and_user_id(id, user.id)
        tags = chat.meta.get("tags", [])
        return Tags.get_tags_by_ids_and_user_id(tags, user.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# DeleteChatTagById
############################


@router.delete("/{id}/tags", response_model=list[TagModel])
async def delete_tag_by_id_and_tag_name(
    id: str, form_data: TagForm, user=Depends(get_verified_user)
):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        Chats.delete_tag_by_id_and_user_id_and_tag_name(id, user.id, form_data.name)

        if Chats.count_chats_by_tag_name_and_user_id(form_data.name, user.id) == 0:
            Tags.delete_tag_by_name_and_user_id(form_data.name, user.id)

        chat = Chats.get_chat_by_id_and_user_id(id, user.id)
        tags = chat.meta.get("tags", [])
        return Tags.get_tags_by_ids_and_user_id(tags, user.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.NOT_FOUND
        )


############################
# DeleteAllTagsById
############################


@router.delete("/{id}/tags/all", response_model=Optional[bool])
async def delete_all_tags_by_id(id: str, user=Depends(get_verified_user)):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        Chats.delete_all_tags_by_id_and_user_id(id, user.id)

        for tag in chat.meta.get("tags", []):
            if Chats.count_chats_by_tag_name_and_user_id(tag, user.id) == 0:
                Tags.delete_tag_by_name_and_user_id(tag, user.id)

        return True
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.NOT_FOUND
        )
