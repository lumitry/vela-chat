"""
Conversion utilities between normalized chat_message tables and legacy JSON blob format.
This allows the old API endpoints to work transparently with the new normalized schema.
"""
import logging
import time
import re
import uuid
import base64
import hashlib
import os
from typing import Optional, Dict, List
from open_webui.models.chat_messages import ChatMessages
from open_webui.models.chats import Chats
from open_webui.internal.db import get_db
from open_webui.models.chat_messages import ChatMessage, ChatMessageAttachment
from open_webui.models.files import Files, FileForm
from open_webui.storage.provider import Storage
from collections import OrderedDict
from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS.get("MODELS", logging.INFO))


def normalized_to_legacy_format(chat_id: str, embed_files_as_base64: bool = False) -> Dict:
    """
    Convert normalized chat_message tables to legacy JSON blob format.
    Returns a dict in the old `chat.chat` format.
    
    This function works entirely from normalized tables - it does not depend on
    the legacy chat.chat blob for message content. All messages should have been migrated during the
    backfill migration, including fields like modelIdx, userContext, lastSentence
    stored in the meta column.
    """
    from open_webui.models.chats import Chat
    
    with get_db() as db:
        chat = db.query(Chat).filter_by(id=chat_id).first()
        if not chat:
            return {}
        
        # Get all messages for this chat, ordered by creation time
        messages_query = db.query(ChatMessage).filter_by(chat_id=chat_id).order_by(ChatMessage.created_at.asc())
        all_messages = messages_query.all()
        
        # Get all attachments
        message_ids = [m.id for m in all_messages]
        attachments_map: Dict[str, List[Dict]] = {}
        if message_ids:
            attachments = db.query(ChatMessageAttachment).filter(
                ChatMessageAttachment.message_id.in_(message_ids)
            ).all()
            for att in attachments:
                msg_id_str = str(att.message_id) if att.message_id else None
                if msg_id_str:
                    if msg_id_str not in attachments_map:
                        attachments_map[msg_id_str] = []
                    attachments_map[msg_id_str].append({
                        "type": str(att.type) if att.type else "file",
                        "file_id": str(att.file_id) if att.file_id else None,
                        "url": str(att.url) if att.url else None,
                        "mime_type": str(att.mime_type) if att.mime_type else None,
                        "size_bytes": int(att.size_bytes) if att.size_bytes else None,
                        "metadata": att.meta if att.meta else {}
                    })
        
        # Build message map (old format) - use OrderedDict to preserve creation order
        messages_dict: OrderedDict[str, Dict] = OrderedDict()
        
        # Helper to get model name from model_id
        def get_model_name(model_id: Optional[str]) -> Optional[str]:
            if not model_id:
                return None
            try:
                from open_webui.models.models import Models
                model = Models.get_model_by_id(model_id)
                if model and hasattr(model, 'name'):
                    return model.name or model_id
                return model_id
            except Exception:
                return model_id
        
        # Helper to extract lastSentence from content
        def get_last_sentence(content: str) -> Optional[str]:
            if not content:
                return None
            # Simple extraction: get last sentence (ending with . ! ?)
            sentences = re.split(r'([.!?]+)', content)
            if len(sentences) >= 2:
                # Get last complete sentence
                last = ''.join(sentences[-2:]).strip()
                return last if last else None
            return content.strip() if content.strip() else None
        
        # Build messages in creation order (ordered by created_at from query)
        # This matches the original order since messages were created sequentially
        for msg in all_messages:
            # Get message ID string first - needed for dict key and lookups
            msg_id_str = str(msg.id) if msg.id else None
            if not msg_id_str:
                continue  # Skip messages without valid IDs
            
            # Build childrenIds list
            # Order by position (for side-by-side) then creation time
            children = db.query(ChatMessage).filter_by(parent_id=msg.id).order_by(
                ChatMessage.position.asc(), 
                ChatMessage.created_at.asc()
            ).all()
            children_ids = [str(c.id) for c in children if c.id]
            
            # Map attachments to files array with base64 embedding
            files = []
            if msg_id_str in attachments_map:
                for att in attachments_map[msg_id_str]:
                    # Extract file_id from URL if not directly present
                    file_id = att.get("file_id")
                    if not file_id and att.get("url"):
                        # Try to extract file_id from URL format: /api/v1/files/{file_id}/content or http://host/api/v1/files/{file_id}/content
                        url = att.get("url")
                        if url and "/files/" in url:
                            parts = url.split("/files/")
                            if len(parts) > 1:
                                file_id = parts[1].split("/")[0]
                    
                    # Preserve attachment type (image, file, collection, web_search, etc.)
                    att_type = att.get("type", "file")
                    att_meta = att.get("meta") or att.get("metadata") or {}
                    
                    # For regular files, get full file record to reconstruct complete structure
                    if file_id and att_type in ["file", "image"]:
                        try:
                            from open_webui.models.files import Files
                            file_record = Files.get_file_by_id(file_id)
                            if file_record:
                                # Start with file record data
                                file_meta = dict(file_record.meta) if file_record.meta else {}
                                
                                # Merge attachment metadata (which may have collection info, etc.)
                                if att_meta:
                                    # Merge attachment meta into file meta, preserving file record data
                                    for key, value in att_meta.items():
                                        if key not in file_meta or value is not None:
                                            file_meta[key] = value
                                
                                # Reconstruct full file structure matching legacy format
                                # Start with all fields from file record and attachment metadata
                                file_obj = {
                                    "id": file_record.id,
                                    "type": att_type,
                                    "meta": file_meta,  # Already merged above
                                    "created_at": file_record.created_at,
                                    "updated_at": file_record.updated_at,
                                }
                                
                                # Add name - prefer attachment meta, then file meta, then filename
                                if "name" in att_meta:
                                    file_obj["name"] = att_meta["name"]
                                elif file_meta.get("name"):
                                    file_obj["name"] = file_meta["name"]
                                else:
                                    file_obj["name"] = file_record.filename
                                
                                # Add description if present (from attachment or file meta)
                                if "description" in att_meta:
                                    file_obj["description"] = att_meta["description"]
                                elif file_meta.get("description"):
                                    file_obj["description"] = file_meta["description"]
                                
                                # Add status - prefer attachment meta, then file meta, then default
                                if "status" in att_meta:
                                    file_obj["status"] = att_meta["status"]
                                elif file_meta.get("status"):
                                    file_obj["status"] = file_meta["status"]
                                else:
                                    file_obj["status"] = "processed"  # Default
                                
                                # Add collection info if present
                                collection_name = att_meta.get("collection_name") or file_meta.get("collection_name")
                                if collection_name:
                                    # Ensure collection_name is in meta
                                    if "collection_name" not in file_obj["meta"]:
                                        file_obj["meta"]["collection_name"] = collection_name
                                    
                                    # Try to get collection details from attachment meta or database
                                    if "collection" in att_meta:
                                        file_obj["collection"] = att_meta["collection"]
                                    else:
                                        try:
                                            from open_webui.models.knowledge import Knowledge
                                            with get_db() as db:
                                                knowledge = db.query(Knowledge).filter_by(id=collection_name).first()
                                                if knowledge:
                                                    file_obj["collection"] = {
                                                        "name": knowledge.name or "",
                                                        "description": knowledge.description or ""
                                                    }
                                        except Exception:
                                            pass  # Collection lookup failed, continue without it
                                
                                # Add URL for API responses (not for base64 exports)
                                if not embed_files_as_base64:
                                    file_obj["url"] = f"/api/v1/files/{file_id}/content"
                            else:
                                # File record not found, reconstruct from attachment metadata
                                file_obj = {
                                    "id": file_id,
                                    "type": att_type,
                                }
                                # Copy metadata from attachment
                                if att_meta:
                                    if "name" in att_meta:
                                        file_obj["name"] = att_meta["name"]
                                    if "description" in att_meta:
                                        file_obj["description"] = att_meta["description"]
                                    if "status" in att_meta:
                                        file_obj["status"] = att_meta["status"]
                                    if "collection" in att_meta:
                                        file_obj["collection"] = att_meta["collection"]
                                # Build meta dict from attachment metadata
                                if att_meta:
                                    file_obj["meta"] = {}
                                    # Include all relevant meta fields
                                    for key in ["name", "content_type", "size", "data", "collection_name"]:
                                        if key in att_meta:
                                            file_obj["meta"][key] = att_meta[key]
                                if not embed_files_as_base64:
                                    file_obj["url"] = f"/api/v1/files/{file_id}/content"
                        except Exception as e:
                            log.warning(f"normalized_to_legacy_format: Failed to get file record {file_id}: {e}, using attachment metadata")
                            # Fallback: reconstruct from attachment metadata
                            file_obj = {
                                "id": file_id,
                                "type": att_type,
                            }
                            if att_meta:
                                if "name" in att_meta:
                                    file_obj["name"] = att_meta["name"]
                                if "description" in att_meta:
                                    file_obj["description"] = att_meta["description"]
                                if "status" in att_meta:
                                    file_obj["status"] = att_meta["status"]
                                if "collection" in att_meta:
                                    file_obj["collection"] = att_meta["collection"]
                                # Build meta dict from attachment metadata
                                if att_meta:
                                    file_obj["meta"] = {}
                                    # Include all relevant meta fields
                                    for key in ["name", "content_type", "size", "data", "collection_name"]:
                                        if key in att_meta:
                                            file_obj["meta"][key] = att_meta[key]
                            if not embed_files_as_base64:
                                file_obj["url"] = f"/api/v1/files/{file_id}/content"
                    elif att_type == "collection" and att_meta:
                        # For collections, reconstruct from attachment meta
                        file_obj = {
                            "type": "collection",
                        }
                        # Copy all collection fields from meta
                        for key in ["id", "name", "description", "data", "files", "type", "status", "user", "collection_name", "collection_names"]:
                            if key in att_meta:
                                file_obj[key] = att_meta[key]
                    elif att_type == "web_search" and att_meta:
                        # For web_search, reconstruct from attachment meta
                        file_obj = {
                            "type": "web_search",
                        }
                        for key in ["collection_name", "name", "urls", "docs", "type"]:
                            if key in att_meta:
                                file_obj[key] = att_meta[key]
                    else:
                        # Fallback for other types
                        file_obj = {
                            "type": att_type,
                            "mime_type": att.get("mime_type"),
                            "size_bytes": att.get("size_bytes"),
                            "metadata": att_meta
                        }
                        if file_id:
                            file_obj["id"] = file_id
                            if not embed_files_as_base64:
                                file_obj["url"] = f"/api/v1/files/{file_id}/content"
                    
                    # Handle base64 embedding for regular files (if requested and not already handled)
                    if file_id and embed_files_as_base64 and att_type in ["file", "image"] and isinstance(file_obj, dict) and "url" not in file_obj:
                        # For exports, embed file content as base64 data URL
                        try:
                            from open_webui.models.files import Files
                            file_record = Files.get_file_by_id(file_id)
                            if file_record and file_record.path:
                                file_path = Storage.get_file(file_record.path)
                                if os.path.isfile(file_path):
                                    with open(file_path, "rb") as f:
                                        file_content = f.read()
                                    base64_data = base64.b64encode(file_content).decode("utf-8")
                                    
                                    # Use data URL format for compatibility with old exports
                                    # Format: data:{mime_type};base64,{base64_data}
                                    # Get mime_type from attachment, file record meta, or file record mime_type column
                                    mime_type = (att.get("mime_type") or 
                                               (file_record.meta.get("content_type") if file_record.meta else None) or
                                               (getattr(file_record, 'mime_type', None) if hasattr(file_record, 'mime_type') else None) or
                                               "application/octet-stream")
                                    file_obj["url"] = f"data:{mime_type};base64,{base64_data}"
                                    
                                else:
                                    # File doesn't exist on disk, use file URL as fallback
                                    file_obj["url"] = f"/api/v1/files/{file_id}/content"
                                    log.warning(f"normalized_to_legacy_format: File {file_id} not found at path {file_path}, using file URL")
                            else:
                                # File record not found, use file URL as fallback
                                file_obj["url"] = f"/api/v1/files/{file_id}/content"
                                log.warning(f"normalized_to_legacy_format: File record {file_id} not found, using file URL")
                        except Exception as e:
                            # On error, use file URL as fallback
                            file_obj["url"] = f"/api/v1/files/{file_id}/content"
                            log.warning(f"normalized_to_legacy_format: Failed to embed file {file_id} as base64: {e}, using file URL")
                    elif file_id and not embed_files_as_base64 and isinstance(file_obj, dict) and "url" not in file_obj:
                        # For API responses, use file URL (don't embed base64)
                        file_obj["url"] = f"/api/v1/files/{file_id}/content"
                    elif not file_id and att.get("url") and isinstance(file_obj, dict):
                        # No file_id, keep URL if present
                        file_obj["url"] = att.get("url")
                    
                    # Add file to list (collections and web_search don't need URLs)
                    if isinstance(file_obj, dict):
                        files.append(file_obj)
            
            # Also include any explicit files stored in message meta
            try:
                meta_files = []
                if msg.meta and isinstance(msg.meta, dict) and "files" in msg.meta:
                    if isinstance(msg.meta["files"], list):
                        meta_files = msg.meta["files"]
                if meta_files:
                    # Normalize meta files to legacy shape: ensure id/url/type set where possible
                    for mf in meta_files:
                        if not isinstance(mf, dict):
                            continue
                        out = dict(mf)
                        # If URL missing but id present, provide default URL
                        if out.get("id") and not out.get("url") and out.get("type") in ["file", "image"]:
                            out["url"] = f"/api/v1/files/{out['id']}/content"
                        files.append(out)
                    # Deduplicate by (type, id or collection_name)
                    # Prefer files from meta (more complete) over those reconstructed from attachments
                    seen_keys = set()
                    dedup = []
                    for f in files:
                        file_type = f.get("type")
                        file_id = f.get("id")
                        collection_name = f.get("collection_name")
                        
                        # Build deduplication key
                        key = (file_type, file_id or collection_name)
                        
                        if key not in seen_keys:
                            seen_keys.add(key)
                            dedup.append(f)
                        else:
                            # Key already exists - check if we should replace with a more complete version
                            existing_idx = next((i for i, existing in enumerate(dedup) if (existing.get("type"), existing.get("id") or existing.get("collection_name")) == key), None)
                            if existing_idx is not None:
                                existing = dedup[existing_idx]
                                # Prefer the one with an id field (more complete)
                                if not existing.get("id") and f.get("id"):
                                    dedup[existing_idx] = f
                                # If both have id, prefer the one with more fields (likely from meta, more complete)
                                elif existing.get("id") and f.get("id") and existing.get("id") == f.get("id"):
                                    if len(f) > len(existing):
                                        dedup[existing_idx] = f
                                # If neither has id but both have collection_name, prefer the one with more fields
                                elif not existing.get("id") and not f.get("id") and collection_name:
                                    if len(f) > len(existing):
                                        dedup[existing_idx] = f
                    files = dedup
            except Exception:
                pass
            
            # Build message in old format
            # Access SQLAlchemy model attributes (they're values, not Column objects at runtime)
            msg_id = str(msg.id) if msg.id else None
            msg_parent_id = str(msg.parent_id) if msg.parent_id else None
            msg_role = str(msg.role) if msg.role else ""
            msg_content_text = str(msg.content_json.get("text")) if (msg.content_json and isinstance(msg.content_json, dict) and "text" in msg.content_json) else (str(msg.content_text) if msg.content_text else "")
            msg_model_id = str(msg.model_id) if msg.model_id else None
            msg_created_at = int(msg.created_at) if msg.created_at else 0
            
            message_dict = {
                "id": msg_id,
                "parentId": msg_parent_id,
                "childrenIds": children_ids,
                "role": msg_role,
                "content": msg_content_text,
                "model": msg_model_id,
                "timestamp": msg_created_at,
            }
            
            # Debug: Log ID conversion to help track down ID mismatches
            if log.isEnabledFor(logging.DEBUG):
                log.debug(f"Converting message: db_id={msg.id}, db_parent_id={msg.parent_id}, "
                         f"converted_id={msg_id}, converted_parent_id={msg_parent_id}")
            
            # Add modelName for assistant messages (lookup from model_id)
            if msg_role == "assistant" and msg_model_id:
                model_name = get_model_name(msg_model_id)
                if model_name:
                    message_dict["modelName"] = model_name
            
            # Add optional fields
            if msg.content_json:
                message_dict["content_json"] = msg.content_json
            
            if msg.status:
                message_dict["status"] = msg.status
                if "statusHistory" in msg.status:
                    message_dict["statusHistory"] = msg.status["statusHistory"]
            
            if msg.usage:
                message_dict["usage"] = msg.usage
            
            # Add feedback/evaluation fields
            if msg.annotation:
                message_dict["annotation"] = msg.annotation
            if msg.feedback_id:
                message_dict["feedbackId"] = msg.feedback_id
            if msg.selected_model_id:
                message_dict["selectedModelId"] = msg.selected_model_id
            
            # Extract fields from meta (all unmigrated fields should be here)
            if msg.meta:
                # Preserve modelIdx for side-by-side chats
                if "modelIdx" in msg.meta:
                    message_dict["modelIdx"] = msg.meta["modelIdx"]
                if "models" in msg.meta:
                    message_dict["models"] = msg.meta["models"]
                # Preserve userContext if stored in meta
                if "userContext" in msg.meta:
                    message_dict["userContext"] = msg.meta["userContext"]
                # Preserve lastSentence if stored in meta
                if "lastSentence" in msg.meta:
                    message_dict["lastSentence"] = msg.meta["lastSentence"]
                # Preserve sources (web search, RAG citations) if stored in meta
                if "sources" in msg.meta:
                    message_dict["sources"] = msg.meta["sources"]
                # Preserve merged (MOA) metadata if stored in meta
                if "merged" in msg.meta:
                    message_dict["merged"] = msg.meta["merged"]
            
            # Compute lastSentence if still not present (for assistant messages)
            if msg_role == "assistant" and "lastSentence" not in message_dict and msg_content_text:
                last_sent = get_last_sentence(msg_content_text)
                if last_sent:
                    message_dict["lastSentence"] = last_sent
            
            # Set done flag for assistant messages (true if usage exists, indicating completion)
            if msg_role == "assistant" and "done" not in message_dict:
                message_dict["done"] = bool(msg.usage)
                # Also check status for done flag
                if msg.status and isinstance(msg.status, dict) and "done" in msg.status:
                    message_dict["done"] = msg.status["done"]
            
            # userContext defaults to null for assistant messages
            if msg_role == "assistant" and "userContext" not in message_dict:
                message_dict["userContext"] = None
            
            if files:
                message_dict["files"] = files
            
            messages_dict[msg_id_str] = message_dict
        
        # Build legacy chat structure
        chat_content = {}
        
        # Get models from first user message's meta (where it should be stored)
        # Do NOT read from chat.params - models should be at chat level, not in params
        first_user_msg = next((m for m in all_messages if m.role == "user"), None)
        if first_user_msg and first_user_msg.meta and "models" in first_user_msg.meta:
            chat_content["models"] = first_user_msg.meta["models"]
        else:
            # Fallback: if no models in meta, use empty array (frontend will handle defaults)
            chat_content["models"] = []
        
        # Get params
        if chat.params:
            chat_content["params"] = chat.params
        else:
            chat_content["params"] = {}
        
        # Get files (stored at chat level in old format)
        # Trust the frontend's canonical copy stored in chat.chat["files"]
        # If the frontend sends an empty array, respect that - don't reconstruct from attachments
        all_files = []
        if chat.chat and isinstance(chat.chat, dict) and "files" in chat.chat:
            stored_files = chat.chat.get("files", [])
            if isinstance(stored_files, list):
                all_files = stored_files
        
        if all_files:
            chat_content["files"] = all_files
        
        # Build history
        current_id = str(chat.active_message_id) if chat.active_message_id else None
        if not current_id and all_messages:
            # Find the deepest leaf message
            # Build a parent_id set for quick lookup
            parent_ids = {str(c.parent_id) for c in all_messages if c.parent_id}
            leaves = [m for m in all_messages if str(m.id) not in parent_ids]
            if leaves:
                # Sort by timestamp descending and take the most recent
                leaves.sort(key=lambda m: int(m.created_at) if m.created_at else 0, reverse=True)
                current_id = str(leaves[0].id) if leaves[0].id else None
        
        # Convert OrderedDict to regular dict while preserving order (Python 3.7+ preserves insertion order)
        # Ensure messages are in creation order (already sorted by created_at query)
        messages_dict_final = dict(messages_dict)
        
        chat_content["history"] = {
            "messages": messages_dict_final,
            "currentId": current_id,
            "timestamp": int(all_messages[0].created_at) if all_messages else int(time.time())
        }
        
        # Build messages list (flat list format, also used by frontend)
        # This is the linear branch to currentId
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
                msg_dict = messages_dict.get(msg_id_str, {}) if msg_id_str else {}
                
                # Build message entry for messages array - should match history.messages structure
                msg_entry = {
                    "id": msg_dict.get("id"),
                    "role": msg_dict.get("role"),
                    "content": msg_dict.get("content"),
                    "timestamp": msg_dict.get("timestamp"),
                }
                
                # Add all fields that are in history.messages
                if "parentId" in msg_dict:
                    msg_entry["parentId"] = msg_dict["parentId"]
                if "childrenIds" in msg_dict:
                    msg_entry["childrenIds"] = msg_dict["childrenIds"]
                if "model" in msg_dict:
                    msg_entry["model"] = msg_dict["model"]
                if "modelName" in msg_dict:
                    msg_entry["modelName"] = msg_dict["modelName"]
                if "modelIdx" in msg_dict:
                    msg_entry["modelIdx"] = msg_dict["modelIdx"]
                if "userContext" in msg_dict:
                    msg_entry["userContext"] = msg_dict["userContext"]
                if "done" in msg_dict:
                    msg_entry["done"] = msg_dict["done"]
                if "lastSentence" in msg_dict:
                    msg_entry["lastSentence"] = msg_dict["lastSentence"]
                if "models" in msg_dict:
                    msg_entry["models"] = msg_dict["models"]
                if "files" in msg_dict:
                    msg_entry["files"] = msg_dict["files"]
                
                # Usage goes into "usage" field
                if msg_dict.get("usage"):
                    msg_entry["usage"] = msg_dict["usage"]
                
                if msg_dict.get("sources"):
                    msg_entry["sources"] = msg_dict["sources"]
                if msg_dict.get("merged"):
                    msg_entry["merged"] = msg_dict["merged"]
                
                # Add feedback/evaluation fields
                if "annotation" in msg_dict:
                    msg_entry["annotation"] = msg_dict["annotation"]
                if "feedbackId" in msg_dict:
                    msg_entry["feedbackId"] = msg_dict["feedbackId"]
                if "selectedModelId" in msg_dict:
                    msg_entry["selectedModelId"] = msg_dict["selectedModelId"]
                
                messages_list.append(msg_entry)
        
        chat_content["messages"] = messages_list
        
        # Title
        chat_content["title"] = chat.title or "New Chat"
        
        return chat_content


def legacy_to_normalized_format(chat_id: str, legacy_chat: Dict, regenerate_ids: bool = False) -> None:
    """
    Convert legacy JSON blob format to normalized chat_message tables.
    This is used when the frontend sends updates in the old format.
    
    Note: This should only be called when we receive an update, not during read operations.
    The middleware already handles message creation/updates during streaming.
    """
    from open_webui.models.chat_messages import ChatMessages, MessageCreateForm
    
    # Handle double nesting: frontend sends chat.chat.history, so we need to unwrap if needed
    if "chat" in legacy_chat and isinstance(legacy_chat["chat"], dict):
        legacy_chat = legacy_chat["chat"]
    
    log.debug(f"legacy_to_normalized_format: Processing chat {chat_id}, legacy_chat keys: {list(legacy_chat.keys()) if isinstance(legacy_chat, dict) else 'not a dict'}")
    
    # Legacy format includes BOTH history.messages (dict) AND messages (flat list)
    # The history.messages dict contains ALL messages (including siblings)
    # The messages list contains ONLY the current branch
    # We should use history.messages if available, as it's the complete set
    history = legacy_chat.get("history", {})
    messages = history.get("messages", {})
    current_id = history.get("currentId")
    
    log.debug(f"legacy_to_normalized_format: history keys: {list(history.keys()) if isinstance(history, dict) else 'not a dict'}")
    log.debug(f"legacy_to_normalized_format: messages type: {type(messages)}, length: {len(messages) if isinstance(messages, (dict, list)) else 'N/A'}")
    log.debug(f"legacy_to_normalized_format: current_id: {current_id}")
    
    # If history.messages is empty or not a dict, check if there's a flat messages list
    # This handles edge cases where history.messages might be missing but messages list exists
    if not messages or not isinstance(messages, dict):
        if "messages" in legacy_chat and isinstance(legacy_chat["messages"], list) and len(legacy_chat["messages"]) > 0:
            log.debug(f"legacy_to_normalized_format: Converting messages list to dict format (found {len(legacy_chat['messages'])} messages in list)")
            # Convert flat messages list to history.messages dict format
            messages = {}
            for msg in legacy_chat["messages"]:
                if isinstance(msg, dict) and "id" in msg:
                    messages[str(msg["id"])] = msg
            # Use the last message's ID as current_id if not set
            if not current_id and legacy_chat["messages"]:
                last_msg = legacy_chat["messages"][-1]
                if isinstance(last_msg, dict) and "id" in last_msg:
                    current_id = str(last_msg["id"])
                    log.debug(f"legacy_to_normalized_format: Set current_id from messages list: {current_id}")
        else:
            log.warning(f"legacy_to_normalized_format: No messages found. history.messages: {type(messages)}, messages list exists: {'messages' in legacy_chat if isinstance(legacy_chat, dict) else False}")
    
    if not messages or not isinstance(messages, dict) or len(messages) == 0:
        log.error(f"legacy_to_normalized_format: No messages found in legacy_chat for chat {chat_id}. "
                 f"Keys: {list(legacy_chat.keys()) if isinstance(legacy_chat, dict) else 'not a dict'}, "
                 f"history keys: {list(history.keys()) if isinstance(history, dict) else 'not a dict'}")
        return
    
    # If regenerating IDs, prepare a deterministic mapping old_id -> new_id
    id_map: Dict[str, str] = {}
    if regenerate_ids:
        for old_id in messages.keys():
            old_id_str = str(old_id)
            if old_id_str not in id_map:
                id_map[old_id_str] = str(uuid.uuid4())
        # Map current_id as well
        if current_id:
            cur_str = str(current_id)
            if cur_str not in id_map:
                id_map[cur_str] = str(uuid.uuid4())
    
    log.debug(f"legacy_to_normalized_format: Processing {len(messages)} messages, current_id: {current_id}")
    
    # Sort messages to ensure parents are created before children
    # Process messages without parents first, then messages whose parents have been processed
    def sort_messages_for_import(messages_dict):
        """Sort messages so parents are processed before children."""
        sorted_msgs = []
        processed_ids = set()
        remaining = dict(messages_dict)
        
        # First pass: add messages without parents
        for msg_id, msg_data in list(remaining.items()):
            parent_id = msg_data.get("parentId")
            if not parent_id or parent_id not in messages_dict:
                sorted_msgs.append((msg_id, msg_data))
                processed_ids.add(str(msg_id))
                del remaining[msg_id]
        
        # Subsequent passes: add messages whose parents have been processed
        max_iterations = len(messages_dict)  # Safety limit
        iteration = 0
        while remaining and iteration < max_iterations:
            iteration += 1
            progress_made = False
            for msg_id, msg_data in list(remaining.items()):
                parent_id = msg_data.get("parentId")
                parent_id_str = str(parent_id) if parent_id else None
                if not parent_id_str or parent_id_str in processed_ids:
                    sorted_msgs.append((msg_id, msg_data))
                    processed_ids.add(str(msg_id))
                    del remaining[msg_id]
                    progress_made = True
            if not progress_made:
                # If no progress, add remaining messages anyway (might have circular refs or missing parents)
                for msg_id, msg_data in remaining.items():
                    sorted_msgs.append((msg_id, msg_data))
                break
        
        return sorted_msgs
    
    sorted_messages = sort_messages_for_import(messages)
    
    # Update/create messages from the legacy format
    # This handles both updates to existing messages (e.g., edits) and creation of new messages (e.g., Save as Copy)
    processed_count = 0
    error_count = 0
    for msg_id, msg_data in sorted_messages:
        # Convert msg_id to string for consistency
        original_id_str = str(msg_id) if msg_id else None
        # Determine the target id (regenerate or keep)
        msg_id_str = id_map.get(original_id_str, original_id_str) if original_id_str else None
        
        if not msg_id_str:
            log.warning(f"legacy_to_normalized_format: Skipping message with invalid ID: {msg_id}")
            error_count += 1
            continue
        
        if not isinstance(msg_data, dict):
            log.warning(f"legacy_to_normalized_format: Skipping message {msg_id_str} - msg_data is not a dict: {type(msg_data)}")
            error_count += 1
            continue
        
        # Check if message exists
        existing = None if regenerate_ids else ChatMessages.get_message_by_id(msg_id_str)
        
        log.debug(f"legacy_to_normalized_format: Processing message {msg_id_str}, role={msg_data.get('role')}, existing={existing is not None}, content_length={len(str(msg_data.get('content', '') or ''))}")
        
        # Extract attachments/files and handle base64 embedded files
        attachments = []
        files = msg_data.get("files", [])
        log.debug(f"legacy_to_normalized_format: Processing {len(files)} file attachments for message {msg_id_str}")
        for idx, file_item in enumerate(files):
            log.debug(f"legacy_to_normalized_format: Processing file attachment {idx+1}/{len(files)}: type={file_item.get('type')}, has_url={'url' in file_item}, has_base64={'base64' in file_item}")
            file_type = file_item.get("type", "file")
            
            # Build attachment dict with full metadata preservation
            att_dict = {
                "type": file_type,
                "mime_type": file_item.get("mime_type"),
                "size_bytes": file_item.get("size_bytes"),
            }
            
            # Preserve ALL metadata from the file_item
            # This includes meta, collection, name, description, status, etc.
            attachment_meta = {}
            
            # Copy all fields that should be in meta
            if "meta" in file_item and isinstance(file_item.get("meta"), dict):
                attachment_meta.update(file_item["meta"])
            if "metadata" in file_item:
                attachment_meta.update(file_item["metadata"])
            
            # Also preserve top-level fields that are part of the file structure
            for key in ["name", "description", "status", "collection", "collection_name", "data"]:
                if key in file_item and key not in attachment_meta:
                    attachment_meta[key] = file_item[key]
            
            # Store created_at/updated_at if present
            if "created_at" in file_item:
                attachment_meta["created_at"] = file_item["created_at"]
            if "updated_at" in file_item:
                attachment_meta["updated_at"] = file_item["updated_at"]
            
            att_dict["metadata"] = attachment_meta if attachment_meta else {}
            
            # Handle collections (knowledge bases) - skip file_id processing
            if file_type == "collection":
                att_dict["url"] = None  # Collections don't have URLs
                attachments.append(att_dict)
                log.debug(f"legacy_to_normalized_format: Added collection attachment: {file_item.get('name', file_item.get('id', 'unknown'))}")
                continue
            
            # Handle web_search files - skip file_id processing
            if file_type == "web_search":
                att_dict["url"] = None  # Web search doesn't have file URLs
                attachments.append(att_dict)
                log.debug(f"legacy_to_normalized_format: Added web_search attachment: {file_item.get('name', 'unknown')}")
                continue
            
            # Don't include URL in att_dict initially - we'll add file_id after processing
            
            # Handle data URL format (data:image/png;base64,...) or separate base64 field
            url = file_item.get("url", "")
            base64_data = None
            mime_type = file_item.get("mime_type")
            
            log.debug(f"legacy_to_normalized_format: Processing file attachment, url type: {type(url)}, url starts with data: {url.startswith('data:') if url else False}, has base64 field: {'base64' in file_item}")
            
            # Check for data URL format
            if url and url.startswith("data:"):
                try:
                    log.debug(f"legacy_to_normalized_format: Found data URL, length: {len(url)}, preview: {url[:100]}...")
                    # Parse data URL: data:{mime_type};base64,{data}
                    parts = url.split(",", 1)
                    if len(parts) == 2:
                        header = parts[0]
                        base64_data = parts[1]
                        log.debug(f"legacy_to_normalized_format: Extracted base64 data, length: {len(base64_data)}, header: {header}")
                        # Extract mime type from header
                        if ";" in header:
                            mime_type = header.split(";")[0].split(":")[1] if ":" in header else None
                            log.debug(f"legacy_to_normalized_format: Extracted mime_type from header: {mime_type}")
                        else:
                            # Try to extract mime type without semicolon
                            if ":" in header:
                                mime_type = header.split(":")[1]
                                log.debug(f"legacy_to_normalized_format: Extracted mime_type from header (no semicolon): {mime_type}")
                    else:
                        log.warning(f"legacy_to_normalized_format: Data URL doesn't have expected format (no comma), parts: {len(parts)}")
                except Exception as e:
                    log.warning(f"legacy_to_normalized_format: Failed to parse data URL: {e}", exc_info=True)
                    url = None
            
            # Fallback to separate base64 field (for backwards compatibility)
            if not base64_data and "base64" in file_item:
                base64_data = file_item["base64"]
                log.debug(f"legacy_to_normalized_format: Using separate base64 field, length: {len(base64_data) if base64_data else 0}")
            
            # Process base64 data if we have it
            if base64_data:
                log.debug(f"legacy_to_normalized_format: Processing base64 data, length: {len(base64_data)}, mime_type: {mime_type}")
                try:
                    log.debug(f"legacy_to_normalized_format: Decoding base64 data...")
                    file_content = base64.b64decode(base64_data)
                    log.debug(f"legacy_to_normalized_format: Decoded file content, size: {len(file_content)} bytes")
                    file_hash = file_item.get("hash")
                    
                    # Calculate hash if not provided
                    if not file_hash:
                        log.debug(f"legacy_to_normalized_format: Calculating hash for file...")
                        file_hash = hashlib.sha256(file_content).hexdigest()
                        log.debug(f"legacy_to_normalized_format: Calculated hash: {file_hash[:16]}...")
                    
                    # Check if file already exists by hash (deduplication)
                    file_id = None
                    log.debug(f"legacy_to_normalized_format: Checking for existing file with hash {file_hash[:16]}...")
                    with get_db() as db:
                        from open_webui.models.files import File
                        existing_file = db.query(File).filter_by(hash=file_hash).first()
                        if existing_file:
                            file_id = existing_file.id
                            log.debug(f"legacy_to_normalized_format: Found existing file by hash {file_hash[:8]}... -> {file_id}")
                        else:
                            log.debug(f"legacy_to_normalized_format: No existing file found with hash {file_hash[:16]}...")
                    
                    # Create new file if not found
                    if not file_id:
                        log.debug(f"legacy_to_normalized_format: Creating new file record...")
                        file_id = str(uuid.uuid4())
                        filename = file_item.get("filename", f"imported_{file_id}")
                        # Generate storage filename
                        storage_filename = f"{file_id}_{filename}"
                        
                        # Upload file to storage
                        from io import BytesIO
                        file_io = BytesIO(file_content)
                        contents, file_path = Storage.upload_file(file_io, storage_filename)
                        
                        # Create file record
                        file_form = FileForm(
                            id=file_id,
                            filename=filename,
                            path=file_path,
                            hash=file_hash,
                            meta={
                                "name": filename,
                                "content_type": mime_type or "application/octet-stream",
                                "size": len(file_content),
                            }
                        )
                        # Get user_id from chat
                        log.debug(f"legacy_to_normalized_format: Getting chat {chat_id} to find user_id...")
                        chat = Chats.get_chat_by_id(chat_id)
                        user_id = chat.user_id if chat else None
                        log.debug(f"legacy_to_normalized_format: Chat found: {chat is not None}, user_id: {user_id}")
                        if user_id:
                            log.debug(f"legacy_to_normalized_format: Inserting file record for user {user_id}...")
                            file_record = Files.insert_new_file(user_id, file_form)
                            if file_record:
                                file_id = file_record.id
                                log.info(f"legacy_to_normalized_format: Successfully created new file {file_id} from base64 (hash: {file_hash[:8]}..., size: {len(file_content)} bytes)")
                            else:
                                log.error(f"legacy_to_normalized_format: Files.insert_new_file returned None for base64 attachment")
                                file_id = None
                        else:
                            log.warning(f"legacy_to_normalized_format: Cannot create file - no user_id available for chat {chat_id}")
                            file_id = None
                    
                    if file_id:
                        att_dict["file_id"] = file_id
                        log.debug(f"legacy_to_normalized_format: Set attachment file_id to {file_id}")
                    else:
                        log.warning(f"legacy_to_normalized_format: No file_id available for attachment after processing base64")
                except Exception as e:
                    log.error(f"legacy_to_normalized_format: Failed to process base64 file: {e}", exc_info=True)
            # Extract file_id from URL if present (non-data URLs)
            elif url and "/files/" in url and not url.startswith("data:"):
                # URL format: /api/v1/files/{file_id}/content or http://host/api/v1/files/{file_id}/content
                parts = url.split("/files/")
                if len(parts) > 1:
                    file_id_part = parts[1].split("/")[0]
                    att_dict["file_id"] = file_id_part
            elif "file_id" in file_item:
                att_dict["file_id"] = file_item["file_id"]
            
            attachments.append(att_dict)
            log.debug(f"legacy_to_normalized_format: Added attachment: type={att_dict.get('type')}, file_id={att_dict.get('file_id')}, has_url={'url' in att_dict}")
        
        # Build meta dict - only update if there's new data
        meta_update = {}
        if "modelIdx" in msg_data:
            meta_update["modelIdx"] = msg_data["modelIdx"]
        if "models" in msg_data and msg_data.get("role") == "user":
            # Only update models for user messages (first user message stores chat-level models)
            meta_update["models"] = msg_data["models"]
        # Preserve sources (web search, RAG citations) if present
        if "sources" in msg_data:
            meta_update["sources"] = msg_data["sources"]
        # Preserve merged (MOA) metadata if present
        if "merged" in msg_data:
            meta_update["merged"] = msg_data["merged"]
        # Preserve userContext if present
        if "userContext" in msg_data:
            meta_update["userContext"] = msg_data["userContext"]
        # Preserve lastSentence if present
        if "lastSentence" in msg_data:
            meta_update["lastSentence"] = msg_data["lastSentence"]
        
        # Extract feedback/evaluation fields
        annotation = msg_data.get("annotation")
        feedback_id = msg_data.get("feedbackId")  # Note: frontend uses camelCase
        selected_model_id = msg_data.get("selectedModelId")  # Note: frontend uses camelCase
        
        if existing:
            # Update existing message - merge meta, don't overwrite
            existing_meta = existing.meta if existing.meta else {}
            merged_meta = {**existing_meta, **meta_update} if meta_update else existing_meta
            
            # Update parent_id if provided (for fixing parent-child relationships)
            # Convert to string to ensure consistent format
            parent_id = msg_data.get("parentId")
            if parent_id is not None:
                parent_old_str = str(parent_id)
                parent_id = id_map.get(parent_old_str, parent_old_str) if regenerate_ids else parent_old_str
            
            # Get content - check if content was provided in the update
            content_text = msg_data.get("content")
            content_provided = "content" in msg_data
            
            # Handle statusHistory - merge with existing status if needed
            status_update = msg_data.get("status")
            if "statusHistory" in msg_data and status_update:
                # If statusHistory is provided separately, merge it into status
                if not isinstance(status_update, dict):
                    status_update = {}
                status_update["statusHistory"] = msg_data["statusHistory"]
            elif "statusHistory" in msg_data:
                # statusHistory provided but no status dict - create one
                status_update = {"statusHistory": msg_data["statusHistory"]}
            
            # Update the message
            try:
                result = ChatMessages.update_message(
                    msg_id_str,
                    content_text=content_text if content_provided else None,
                    content_json=msg_data.get("content_json"),
                    model_id=msg_data.get("model"),
                    status=status_update,
                    usage=msg_data.get("usage"),
                    meta=merged_meta if merged_meta else None,
                    parent_id=parent_id,
                    annotation=annotation,
                    feedback_id=feedback_id,
                    selected_model_id=selected_model_id
                )
                
                if result is None:
                    log.error(f"legacy_to_normalized_format: Failed to update message {msg_id_str} - update_message returned None")
                    error_count += 1
                else:
                    log.debug(f"legacy_to_normalized_format: Successfully updated message {msg_id_str}, content_provided={content_provided}, content_length={len(content_text or '') if content_provided else 0}")
                    processed_count += 1
            except Exception as e:
                log.error(f"legacy_to_normalized_format: Exception updating message {msg_id_str}: {str(e)}", exc_info=True)
                error_count += 1
        else:
            # Create new message (e.g., during import or "Save as Copy")
            # Convert parentId to string to ensure consistent format
            parent_id = msg_data.get("parentId")
            if parent_id is not None:
                parent_old_str = str(parent_id)
                parent_id = id_map.get(parent_old_str, parent_old_str) if regenerate_ids else parent_old_str
            
            # msg_id_str already set to regenerated or original id
            
            # Handle statusHistory for new messages
            status_for_insert = msg_data.get("status")
            if "statusHistory" in msg_data and status_for_insert:
                # If statusHistory is provided separately, merge it into status
                if not isinstance(status_for_insert, dict):
                    status_for_insert = {}
                status_for_insert["statusHistory"] = msg_data["statusHistory"]
            elif "statusHistory" in msg_data:
                # statusHistory provided but no status dict - create one
                status_for_insert = {"statusHistory": msg_data["statusHistory"]}
            
            # Create the message - this handles both user and assistant messages during import
            try:
                inserted_msg = ChatMessages.insert_message(
                    chat_id,
                    MessageCreateForm(
                        parent_id=parent_id,
                        role=msg_data.get("role"),
                        content_text=msg_data.get("content"),
                        content_json=msg_data.get("content_json"),
                        model_id=msg_data.get("model"),
                        attachments=attachments if attachments else None,
                        meta=meta_update if meta_update else None,
                        annotation=annotation,
                        feedback_id=feedback_id,
                        selected_model_id=selected_model_id
                    ),
                    message_id=msg_id_str
                )
                
                # Update status with statusHistory if needed (insert_message doesn't accept status)
                if status_for_insert:
                    ChatMessages.update_message(msg_id_str, status=status_for_insert)
                log.debug(f"legacy_to_normalized_format: Successfully created message {msg_id_str}, role={msg_data.get('role')}")
                processed_count += 1
            except Exception as e:
                log.error(f"legacy_to_normalized_format: Exception creating message {msg_id_str}: {str(e)}", exc_info=True)
                error_count += 1
            
            # For "Save as Copy" scenarios, ensure cost is set to 0 for the duplicated message
            if msg_data.get("usage") or msg_data.get("status"):
                # Update the message with usage/status but explicitly set cost to 0
                # We need to update via direct DB access since update_message extracts cost from usage
                with get_db() as db:
                    from decimal import Decimal
                    new_message = db.get(ChatMessage, msg_id_str)
                    if new_message:
                        # Set usage and status if provided
                        if msg_data.get("usage"):
                            new_message.usage = msg_data.get("usage")
                        if msg_data.get("status"):
                            new_message.status = msg_data.get("status")
                        
                        # Explicitly set cost to 0 for copied messages
                        new_message.cost = Decimal('0')
                        
                        # Extract and store tokens from usage (but keep cost at 0)
                        if msg_data.get("usage"):
                            from open_webui.models.chat_messages import extract_tokens_from_usage
                            input_tokens, output_tokens, reasoning_tokens = extract_tokens_from_usage(msg_data.get("usage"))
                            new_message.input_tokens = input_tokens
                            new_message.output_tokens = output_tokens
                            new_message.reasoning_tokens = reasoning_tokens
                        
                        db.commit()
                        log.debug(f"legacy_to_normalized_format: Set cost to 0 for copied message {msg_id_str}")
    
    # Update chat's active_message_id
    # Convert to string to ensure consistent format
    if current_id:
        current_id_str = str(current_id) if current_id else None
        if regenerate_ids and current_id_str:
            current_id_str = id_map.get(current_id_str, current_id_str)
        if current_id_str:
            try:
                Chats.update_chat_active_and_root_message_ids(chat_id, active_message_id=current_id_str)
                log.debug(f"legacy_to_normalized_format: Set active_message_id to {current_id_str}")
            except Exception as e:
                log.error(f"legacy_to_normalized_format: Exception setting active_message_id: {str(e)}", exc_info=True)
    
    log.info(f"legacy_to_normalized_format: Completed import for chat {chat_id}. Processed: {processed_count}, Errors: {error_count}, Total messages: {len(messages)}")
    
    # Preserve chat-level files in the chat blob (frontend's canonical source)
    # This is critical for RAG to work correctly - the frontend sends chat.files and expects it to be preserved
    chat_blob_update = {}
    if "files" in legacy_chat:
        chat_blob_update["files"] = legacy_chat["files"]
        log.debug(f"legacy_to_normalized_format: Preserving {len(legacy_chat['files']) if isinstance(legacy_chat['files'], list) else 0} chat-level files in chat blob")
    
    # Update params (but NOT models - models should be in user message meta, not params)
    # NOTE: We use update_chat_by_id which now preserves the title if not in the dict
    if "params" in legacy_chat:
        # Ensure params doesn't contain models (clean it up if it does)
        params_clean = legacy_chat["params"].copy() if isinstance(legacy_chat["params"], dict) else {}
        if "models" in params_clean:
            del params_clean["models"]
        chat_blob_update["params"] = params_clean
    
    # Update chat blob with files and/or params if we have updates
    if chat_blob_update:
        # Get existing chat blob and merge updates
        from open_webui.models.chats import Chat
        with get_db() as db:
            chat_item = db.query(Chat).filter_by(id=chat_id).first()
            if chat_item:
                existing_chat = chat_item.chat if chat_item.chat else {}
                updated_chat = {**existing_chat, **chat_blob_update}
                chat_item.chat = updated_chat
                db.commit()
                log.debug(f"legacy_to_normalized_format: Updated chat blob with files and/or params")
    
    # Update models: store in first user message's meta (not in params)
    if "models" in legacy_chat:
        from open_webui.models.chat_messages import ChatMessages
        # Find the first user message and update its meta
        with get_db() as db:
            first_user_msg = db.query(ChatMessage).filter_by(
                chat_id=chat_id,
                role="user"
            ).order_by(ChatMessage.created_at.asc()).first()
            
            if first_user_msg:
                existing_meta = first_user_msg.meta if first_user_msg.meta else {}
                existing_meta["models"] = legacy_chat["models"]
                ChatMessages.update_message(first_user_msg.id, meta=existing_meta)

