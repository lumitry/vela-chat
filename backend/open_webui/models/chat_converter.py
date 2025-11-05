"""
Conversion utilities between normalized chat_message tables and legacy JSON blob format.
This allows the old API endpoints to work transparently with the new normalized schema.
"""
import logging
import time
import re
from typing import Optional, Dict, List
from open_webui.models.chat_messages import ChatMessages
from open_webui.models.chats import Chats
from open_webui.internal.db import get_db
from open_webui.models.chat_messages import ChatMessage, ChatMessageAttachment
from collections import OrderedDict
from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS.get("MODELS", logging.INFO))


def normalized_to_legacy_format(chat_id: str) -> Dict:
    """
    Convert normalized chat_message tables to legacy JSON blob format.
    Returns a dict in the old `chat.chat` format.
    
    This function works entirely from normalized tables - it does not depend on
    the legacy chat.chat blob. All data should have been migrated during the
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
            
            # Map attachments to files array
            files = []
            if msg_id_str in attachments_map:
                for att in attachments_map[msg_id_str]:
                    file_obj = {
                        "type": att["type"] if att["type"] == "image" else "file",
                        "url": att.get("url") or (f"/api/v1/files/{att['file_id']}/content" if att.get("file_id") else None)
                    }
                    if file_obj["url"]:
                        files.append(file_obj)
            
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
        # In normalized, files are per-message attachments, but old format has them at chat level
        # We'll reconstruct from attachments
        all_files = []
        seen_file_ids = set()
        for msg_attachments in attachments_map.values():
            for att in msg_attachments:
                if att.get("file_id") and att["file_id"] not in seen_file_ids:
                    all_files.append({
                        "id": att["file_id"],
                        "type": att["type"],
                        "url": att.get("url")
                    })
                    seen_file_ids.add(att["file_id"])
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
                
                # Usage goes into both "usage" and "info" fields (legacy format)
                if msg_dict.get("usage"):
                    msg_entry["usage"] = msg_dict["usage"]
                    msg_entry["info"] = msg_dict["usage"]
                elif msg_dict.get("info"):
                    msg_entry["info"] = msg_dict["info"]
                else:
                    msg_entry["info"] = None
                
                if msg_dict.get("sources"):
                    msg_entry["sources"] = msg_dict["sources"]
                
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


def legacy_to_normalized_format(chat_id: str, legacy_chat: Dict) -> None:
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
    
    history = legacy_chat.get("history", {})
    messages = history.get("messages", {})
    current_id = history.get("currentId")
    
    if not messages:
        log.debug(f"legacy_to_normalized_format: No messages in history for chat {chat_id}")
        return
    
    # Update/create messages from the legacy format
    # This handles both updates to existing messages (e.g., edits) and creation of new messages (e.g., Save as Copy)
    for msg_id, msg_data in messages.items():
        # Convert msg_id to string for consistency
        msg_id_str = str(msg_id) if msg_id else None
        
        if not msg_id_str:
            log.warning(f"legacy_to_normalized_format: Skipping message with invalid ID: {msg_id}")
            continue
        
        # Check if message exists
        existing = ChatMessages.get_message_by_id(msg_id_str)
        
        log.debug(f"legacy_to_normalized_format: Processing message {msg_id_str}, role={msg_data.get('role')}, existing={existing is not None}, content_length={len(msg_data.get('content', '') or '')}")
        
        # Extract attachments/files
        attachments = []
        files = msg_data.get("files", [])
        for file_item in files:
            att_dict = {
                "type": file_item.get("type", "file"),
                "url": file_item.get("url"),
                "mime_type": file_item.get("mime_type"),
                "size_bytes": file_item.get("size_bytes"),
                "metadata": file_item.get("metadata") or {}
            }
            # Extract file_id from URL if present
            if "url" in file_item and "/files/" in file_item["url"]:
                # URL format: /api/v1/files/{file_id}/content
                parts = file_item["url"].split("/files/")
                if len(parts) > 1:
                    file_id_part = parts[1].split("/")[0]
                    att_dict["file_id"] = file_id_part
            elif "file_id" in file_item:
                att_dict["file_id"] = file_item["file_id"]
            attachments.append(att_dict)
        
        # Build meta dict - only update if there's new data
        meta_update = {}
        if "modelIdx" in msg_data:
            meta_update["modelIdx"] = msg_data["modelIdx"]
        if "models" in msg_data and msg_data.get("role") == "user":
            # Only update models for user messages (first user message stores chat-level models)
            meta_update["models"] = msg_data["models"]
        
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
                parent_id = str(parent_id)
            
            # Get content - check if content was provided in the update
            content_text = msg_data.get("content")
            content_provided = "content" in msg_data
            
            # Update the message
            try:
                result = ChatMessages.update_message(
                    msg_id_str,
                    content_text=content_text if content_provided else None,
                    content_json=msg_data.get("content_json"),
                    model_id=msg_data.get("model"),
                    status=msg_data.get("status"),
                    usage=msg_data.get("usage"),
                    meta=merged_meta if merged_meta else None,
                    parent_id=parent_id,
                    annotation=annotation,
                    feedback_id=feedback_id,
                    selected_model_id=selected_model_id
                )
                
                if result is None:
                    log.error(f"legacy_to_normalized_format: Failed to update message {msg_id_str} - update_message returned None")
                else:
                    log.debug(f"legacy_to_normalized_format: Successfully updated message {msg_id_str}, content_provided={content_provided}, content_length={len(content_text or '') if content_provided else 0}")
            except Exception as e:
                log.error(f"legacy_to_normalized_format: Exception updating message {msg_id_str}: {str(e)}", exc_info=True)
        else:
            # Create new message (e.g., "Save as Copy" creates new assistant messages)
            role = msg_data.get("role")
            if role == "user":
                # User messages should already exist from middleware - skip to avoid duplicates
                log.debug(f"legacy_to_normalized_format: Skipping user message {msg_id_str} (should be created by middleware)")
                continue
            
            # Create new message (mainly for assistant messages that might have been missed)
            # Convert parentId to string to ensure consistent format
            parent_id = msg_data.get("parentId")
            if parent_id is not None:
                parent_id = str(parent_id)
            
            # Convert msg_id to string to ensure consistent format
            msg_id_str = str(msg_id) if msg_id else None
            
            ChatMessages.insert_message(
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
        if current_id_str:
            Chats.update_chat_active_and_root_message_ids(chat_id, active_message_id=current_id_str)
    
    # Update params (but NOT models - models should be in user message meta, not params)
    if "params" in legacy_chat:
        # Ensure params doesn't contain models (clean it up if it does)
        params_clean = legacy_chat["params"].copy() if isinstance(legacy_chat["params"], dict) else {}
        if "models" in params_clean:
            del params_clean["models"]
        Chats.update_chat_by_id(chat_id, {"params": params_clean})
    
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

