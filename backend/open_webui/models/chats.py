import logging
import json
import time
import uuid
from typing import Optional

from open_webui.internal.db import Base, get_db
from open_webui.models.tags import TagModel, Tag, Tags
from open_webui.env import SRC_LOG_LEVELS

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import BigInteger, Boolean, Column, String, Text, JSON
from sqlalchemy import or_, func, select, and_, text
from sqlalchemy.sql import exists

####################
# Chat DB Schema
####################

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


class Chat(Base):
    __tablename__ = "chat"

    id = Column(String, primary_key=True)
    user_id = Column(String)
    title = Column(Text)
    chat = Column(JSON)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)

    share_id = Column(Text, unique=True, nullable=True)
    archived = Column(Boolean, default=False)
    pinned = Column(Boolean, default=False, nullable=True)

    meta = Column(JSON, server_default="{}")
    folder_id = Column(Text, nullable=True)

    # New normalized/summary columns
    active_message_id = Column(Text, nullable=True)
    root_message_id = Column(Text, nullable=True)
    params = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)


class ChatModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    chat: dict

    created_at: int  # timestamp in epoch
    updated_at: int  # timestamp in epoch

    share_id: Optional[str] = None
    archived: bool = False
    pinned: Optional[bool] = False

    meta: dict = {}
    folder_id: Optional[str] = None

    # New fields
    active_message_id: Optional[str] = None
    root_message_id: Optional[str] = None
    params: Optional[dict] = None
    summary: Optional[str] = None

    # @field_validator("chat", "meta", mode="before")
    # @classmethod
    # def parse_json_strings(cls, v):
    #     if isinstance(v, str):
    #         try:
    #             return json.loads(v)
    #         except json.JSONDecodeError:
    #             return {}
    #     return v


####################
# Forms
####################


class ChatForm(BaseModel):
    chat: dict


class ChatImportForm(ChatForm):
    meta: Optional[dict] = {}
    pinned: Optional[bool] = False
    folder_id: Optional[str] = None


class ChatTitleMessagesForm(BaseModel):
    title: str
    messages: list[dict]


class ChatTitleForm(BaseModel):
    title: str


class ChatResponse(BaseModel):
    id: str
    user_id: str
    title: str
    chat: dict
    updated_at: int  # timestamp in epoch
    created_at: int  # timestamp in epoch
    share_id: Optional[str] = None  # id of the chat to be shared
    archived: bool
    pinned: Optional[bool] = False
    meta: dict = {}
    folder_id: Optional[str] = None


class ChatTitleIdResponse(BaseModel):
    id: str
    title: str
    updated_at: int
    created_at: int


class ChatTable:
    def insert_new_chat(self, user_id: str, form_data: ChatForm) -> Optional[ChatModel]:
        with get_db() as db:
            id = str(uuid.uuid4())
            # Extract title from chat dict
            title = (
                form_data.chat["title"]
                if "title" in form_data.chat
                else "New Chat"
            )

            chat = ChatModel(
                **{
                    "id": id,
                    "user_id": user_id,
                    "title": title,
                    "chat": form_data.chat,
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                }
            )

            result = Chat(**chat.model_dump())
            db.add(result)
            db.commit()
            db.refresh(result)
            return ChatModel.model_validate(result) if result else None

    def import_chat(
        self, user_id: str, form_data: ChatImportForm
    ) -> Optional[ChatModel]:
        with get_db() as db:
            id = str(uuid.uuid4())
            # Extract title from chat dict
            title = (
                form_data.chat["title"]
                if "title" in form_data.chat
                else "New Chat"
            )

            # Extract created_at from import data (check both created_at and timestamp)
            # Use timestamp from import file if available, otherwise use current time
            # IMPORTANT: Detect and convert milliseconds to seconds (timestamps > year 2100 are likely milliseconds)
            import_time = int(time.time())
            chat_created_at = import_time
            if isinstance(form_data.chat, dict):
                if "created_at" in form_data.chat and form_data.chat["created_at"]:
                    try:
                        chat_created_at = int(form_data.chat["created_at"])
                        # Convert milliseconds to seconds if timestamp is too large (year 2100 = 4102444800)
                        if chat_created_at > 4102444800:
                            chat_created_at = chat_created_at // 1000
                            log.debug(
                                f"import_chat: Converted created_at from milliseconds to seconds")
                    except (ValueError, TypeError):
                        log.warning(
                            f"import_chat: Invalid created_at value, using current time")
                elif "timestamp" in form_data.chat and form_data.chat["timestamp"]:
                    try:
                        chat_created_at = int(form_data.chat["timestamp"])
                        # Convert milliseconds to seconds if timestamp is too large (year 2100 = 4102444800)
                        if chat_created_at > 4102444800:
                            chat_created_at = chat_created_at // 1000
                            log.debug(
                                f"import_chat: Converted timestamp from milliseconds to seconds")
                    except (ValueError, TypeError):
                        log.warning(
                            f"import_chat: Invalid timestamp value, using current time")

            # Mark this chat as imported in meta so it can be excluded from metrics
            import_meta = form_data.meta.copy() if form_data.meta else {}
            import_meta["imported"] = True
            import_meta["imported_at"] = import_time

            chat = ChatModel(
                **{
                    "id": id,
                    "user_id": user_id,
                    "title": title,
                    "chat": form_data.chat,
                    "meta": import_meta,
                    "pinned": form_data.pinned,
                    "folder_id": form_data.folder_id,
                    "created_at": chat_created_at,
                    "updated_at": import_time,  # Set updated_at to import time
                }
            )

            result = Chat(**chat.model_dump())
            db.add(result)
            db.commit()
            db.refresh(result)
            return ChatModel.model_validate(result) if result else None

    def update_chat_by_id(self, id: str, chat: dict) -> Optional[ChatModel]:
        try:
            with get_db() as db:
                chat_item = db.get(Chat, id)
                if not chat_item:
                    log.warning(f"update_chat_by_id: Chat {id} not found")
                    return None

                chat_item.chat = chat
                # Only update title if it's explicitly provided in the chat dict
                # Otherwise preserve the existing title
                if "title" in chat:
                    chat_item.title = chat["title"]

                chat_item.updated_at = int(time.time())
                db.commit()
                db.refresh(chat_item)

                return ChatModel.model_validate(chat_item)
        except Exception as e:
            log.error(
                f"update_chat_by_id: Exception updating chat {id}: {e}", exc_info=True)
            return None

    def update_chat_title_by_id(self, id: str, title: str) -> Optional[ChatModel]:
        chat = self.get_chat_by_id(id)
        if chat is None:
            return None

        chat = chat.chat
        chat["title"] = title

        return self.update_chat_by_id(id, chat)

    def update_chat_active_and_root_message_ids(self, id: str, active_message_id: Optional[str] = None, root_message_id: Optional[str] = None) -> Optional[ChatModel]:
        """Update active_message_id and/or root_message_id on the chat."""
        with get_db() as db:
            chat_item = db.get(Chat, id)
            if chat_item is None:
                return None

            if active_message_id is not None:
                chat_item.active_message_id = active_message_id
            if root_message_id is not None:
                chat_item.root_message_id = root_message_id

            chat_item.updated_at = int(time.time())
            db.commit()
            db.refresh(chat_item)
            return ChatModel.model_validate(chat_item)

    def update_chat_tags_by_id(
        self, id: str, tags: list[str], user
    ) -> Optional[ChatModel]:
        chat = self.get_chat_by_id(id)
        if chat is None:
            return None

        self.delete_all_tags_by_id_and_user_id(id, user.id)

        for tag in chat.meta.get("tags", []):
            if self.count_chats_by_tag_name_and_user_id(tag, user.id) == 0:
                Tags.delete_tag_by_name_and_user_id(tag, user.id)

        for tag_name in tags:
            if tag_name.lower() == "none":
                continue

            self.add_chat_tag_by_id_and_user_id_and_tag_name(
                id, user.id, tag_name)
        return self.get_chat_by_id(id)

    def get_chat_title_by_id(self, id: str) -> Optional[str]:
        chat = self.get_chat_by_id(id)
        if chat is None:
            return None

        return chat.chat.get("title", "New Chat")

    def get_messages_by_chat_id(self, id: str) -> Optional[dict]:
        chat = self.get_chat_by_id(id)
        if chat is None:
            return None

        # Check if this chat uses normalized storage (has messages in chat_message table)
        from open_webui.internal.db import get_db
        from open_webui.models.chat_messages import ChatMessage
        from open_webui.models.chat_converter import normalized_to_legacy_format

        with get_db() as db:
            has_normalized = db.query(ChatMessage).filter_by(
                chat_id=id).first() is not None

        if has_normalized:
            # For normalized chats, convert to legacy format to get messages dict
            legacy_chat = normalized_to_legacy_format(id)
            return legacy_chat.get("history", {}).get("messages", {}) or {}
        else:
            # Legacy chat, use existing chat.chat blob
            if chat.chat is None:
                return {}

            return chat.chat.get("history", {}).get("messages", {}) or {}

    def get_message_by_id_and_message_id(
        self, id: str, message_id: str
    ) -> Optional[dict]:
        chat = self.get_chat_by_id(id)
        if chat is None:
            return None

        if chat.chat is None:
            return {}

        return chat.chat.get("history", {}).get("messages", {}).get(message_id, {})

    def upsert_message_to_chat_by_id_and_message_id(
        self, id: str, message_id: str, message: dict
    ) -> Optional[ChatModel]:
        chat = self.get_chat_by_id(id)
        if chat is None:
            return None

        chat = chat.chat
        if chat is None:
            chat = {}

        history = chat.get("history", {})
        if "messages" not in history:
            history["messages"] = {}

        if message_id in history["messages"]:
            history["messages"][message_id] = {
                **history["messages"][message_id],
                **message,
            }
        else:
            history["messages"][message_id] = message

        history["currentId"] = message_id

        chat["history"] = history
        return self.update_chat_by_id(id, chat)

    def add_message_status_to_chat_by_id_and_message_id(
        self, id: str, message_id: str, status: dict
    ) -> Optional[ChatModel]:
        chat = self.get_chat_by_id(id)
        if chat is None:
            return None

        chat = chat.chat
        history = chat.get("history", {})

        if message_id in history.get("messages", {}):
            status_history = history["messages"][message_id].get(
                "statusHistory", [])
            status_history.append(status)
            history["messages"][message_id]["statusHistory"] = status_history

        chat["history"] = history
        return self.update_chat_by_id(id, chat)

    def insert_shared_chat_by_chat_id(self, chat_id: str) -> Optional[ChatModel]:
        with get_db() as db:
            # Get the existing chat to share
            chat = db.get(Chat, chat_id)
            # Check if the chat is already shared
            if chat.share_id:
                return self.get_chat_by_id_and_user_id(chat.share_id, "shared")
            # Create a new chat with the same data, but with a new ID
            shared_chat = ChatModel(
                **{
                    "id": str(uuid.uuid4()),
                    "user_id": f"shared-{chat_id}",
                    "title": chat.title,
                    "chat": chat.chat,
                    "created_at": chat.created_at,
                    "updated_at": int(time.time()),
                }
            )
            shared_result = Chat(**shared_chat.model_dump())
            db.add(shared_result)
            db.commit()
            db.refresh(shared_result)

            # Update the original chat with the share_id
            result = (
                db.query(Chat)
                .filter_by(id=chat_id)
                .update({"share_id": shared_chat.id})
            )
            db.commit()
            return shared_chat if (shared_result and result) else None

    def update_shared_chat_by_chat_id(self, chat_id: str) -> Optional[ChatModel]:
        try:
            with get_db() as db:
                chat = db.get(Chat, chat_id)
                shared_chat = (
                    db.query(Chat).filter_by(
                        user_id=f"shared-{chat_id}").first()
                )

                if shared_chat is None:
                    return self.insert_shared_chat_by_chat_id(chat_id)

                shared_chat.title = chat.title
                shared_chat.chat = chat.chat

                shared_chat.updated_at = int(time.time())
                db.commit()
                db.refresh(shared_chat)

                return ChatModel.model_validate(shared_chat)
        except Exception:
            return None

    def delete_shared_chat_by_chat_id(self, chat_id: str) -> bool:
        try:
            with get_db() as db:
                # Get the shared chat ID before deleting
                from open_webui.models.chat_messages import ChatMessage
                shared_chat = db.query(Chat).filter_by(
                    user_id=f"shared-{chat_id}").first()
                if shared_chat:
                    # Delete all messages for the shared chat (and their attachments via CASCADE)
                    db.query(ChatMessage).filter_by(
                        chat_id=shared_chat.id).delete()

                # Delete the shared chat
                db.query(Chat).filter_by(user_id=f"shared-{chat_id}").delete()
                db.commit()

                return True
        except Exception:
            return False

    def update_chat_share_id_by_id(
        self, id: str, share_id: Optional[str]
    ) -> Optional[ChatModel]:
        try:
            with get_db() as db:
                chat = db.get(Chat, id)
                chat.share_id = share_id
                db.commit()
                db.refresh(chat)
                return ChatModel.model_validate(chat)
        except Exception:
            return None

    def toggle_chat_pinned_by_id(self, id: str) -> Optional[ChatModel]:
        try:
            with get_db() as db:
                chat = db.get(Chat, id)
                chat.pinned = not chat.pinned
                chat.updated_at = int(time.time())
                db.commit()
                db.refresh(chat)
                return ChatModel.model_validate(chat)
        except Exception:
            return None

    def toggle_chat_archive_by_id(self, id: str) -> Optional[ChatModel]:
        try:
            with get_db() as db:
                chat = db.get(Chat, id)
                chat.archived = not chat.archived
                chat.updated_at = int(time.time())
                db.commit()
                db.refresh(chat)
                return ChatModel.model_validate(chat)
        except Exception:
            return None

    def archive_all_chats_by_user_id(self, user_id: str) -> bool:
        try:
            with get_db() as db:
                db.query(Chat).filter_by(
                    user_id=user_id).update({"archived": True})
                db.commit()
                return True
        except Exception:
            return False

    def get_archived_chat_list_by_user_id(
        self, user_id: str, skip: int = 0, limit: int = 50
    ) -> list[ChatModel]:
        with get_db() as db:
            all_chats = (
                db.query(Chat)
                .filter_by(user_id=user_id, archived=True)
                .order_by(Chat.updated_at.desc())
                # .limit(limit).offset(skip)
                .all()
            )
            return [ChatModel.model_validate(chat) for chat in all_chats]

    def get_chat_list_by_user_id(
        self,
        user_id: str,
        include_archived: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ChatModel]:
        with get_db() as db:
            query = db.query(Chat).filter_by(user_id=user_id)
            if not include_archived:
                query = query.filter_by(archived=False)

            query = query.order_by(Chat.updated_at.desc())

            if skip:
                query = query.offset(skip)
            if limit:
                query = query.limit(limit)

            all_chats = query.all()
            return [ChatModel.model_validate(chat) for chat in all_chats]

    def get_chat_title_id_list_by_user_id(
        self,
        user_id: str,
        include_archived: bool = False,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[ChatTitleIdResponse]:
        with get_db() as db:
            query = db.query(Chat).filter_by(
                user_id=user_id).filter_by(folder_id=None)
            query = query.filter(
                or_(Chat.pinned == False, Chat.pinned == None))

            if not include_archived:
                query = query.filter_by(archived=False)

            query = query.order_by(Chat.updated_at.desc()).with_entities(
                Chat.id, Chat.title, Chat.updated_at, Chat.created_at
            )

            if skip:
                query = query.offset(skip)
            if limit:
                query = query.limit(limit)

            all_chats = query.all()

            # result has to be destrctured from sqlalchemy `row` and mapped to a dict since the `ChatModel`is not the returned dataclass.
            return [
                ChatTitleIdResponse.model_validate(
                    {
                        "id": chat[0],
                        "title": chat[1],
                        "updated_at": chat[2],
                        "created_at": chat[3],
                    }
                )
                for chat in all_chats
            ]

    def get_chat_list_by_chat_ids(
        self, chat_ids: list[str], skip: int = 0, limit: int = 50
    ) -> list[ChatModel]:
        with get_db() as db:
            all_chats = (
                db.query(Chat)
                .filter(Chat.id.in_(chat_ids))
                .filter_by(archived=False)
                .order_by(Chat.updated_at.desc())
                .all()
            )
            return [ChatModel.model_validate(chat) for chat in all_chats]

    def get_chat_by_id(self, id: str) -> Optional[ChatModel]:
        try:
            with get_db() as db:
                chat = db.get(Chat, id)
                return ChatModel.model_validate(chat)
        except Exception:
            return None

    def get_chat_by_share_id(self, id: str) -> Optional[ChatModel]:
        try:
            with get_db() as db:
                # it is possible that the shared link was deleted. hence,
                # we check if the chat is still shared by checking if a chat with the share_id exists
                chat = db.query(Chat).filter_by(share_id=id).first()

                if chat:
                    return self.get_chat_by_id(id)
                else:
                    return None
        except Exception:
            return None

    def get_chat_by_id_and_user_id(self, id: str, user_id: str) -> Optional[ChatModel]:
        try:
            with get_db() as db:
                chat = db.query(Chat).filter_by(id=id, user_id=user_id).first()
                return ChatModel.model_validate(chat)
        except Exception:
            return None

    def get_chats(self, skip: int = 0, limit: int = 50) -> list[ChatModel]:
        with get_db() as db:
            all_chats = (
                db.query(Chat)
                # .limit(limit).offset(skip)
                .order_by(Chat.updated_at.desc())
            )
            return [ChatModel.model_validate(chat) for chat in all_chats]

    def get_chats_by_user_id(self, user_id: str) -> list[ChatModel]:
        with get_db() as db:
            all_chats = (
                db.query(Chat)
                .filter_by(user_id=user_id)
                .order_by(Chat.updated_at.desc())
            )
            return [ChatModel.model_validate(chat) for chat in all_chats]

    def get_pinned_chats_by_user_id(self, user_id: str) -> list[ChatModel]:
        with get_db() as db:
            all_chats = (
                db.query(Chat)
                .filter_by(user_id=user_id, pinned=True, archived=False)
                .order_by(Chat.updated_at.desc())
            )
            return [ChatModel.model_validate(chat) for chat in all_chats]

    def get_archived_chats_by_user_id(self, user_id: str) -> list[ChatModel]:
        with get_db() as db:
            all_chats = (
                db.query(Chat)
                .filter_by(user_id=user_id, archived=True)
                .order_by(Chat.updated_at.desc())
            )
            return [ChatModel.model_validate(chat) for chat in all_chats]

    def get_chats_by_user_id_and_search_text(
        self,
        user_id: str,
        search_text: str,
        include_archived: bool = False,
        skip: int = 0,
        limit: int = 60,
    ) -> list[ChatModel]:
        """
        Filters chats based on a search query using Python, allowing pagination using skip and limit.
        """
        import time
        perf_start = time.time()

        search_text = search_text.lower().strip()

        if not search_text:
            return self.get_chat_list_by_user_id(user_id, include_archived, skip, limit)

        search_text_words = search_text.split(" ")

        # search_text might contain 'tag:tag_name' format so we need to extract the tag_name, split the search_text and remove the tags
        tag_ids = [
            word.replace("tag:", "").replace(" ", "_").lower()
            for word in search_text_words
            if word.startswith("tag:")
        ]

        search_text_words = [
            word for word in search_text_words if not word.startswith("tag:")
        ]

        search_text = " ".join(search_text_words)

        perf_after_prep = time.time()
        log.debug(
            f"Search prep took {(perf_after_prep - perf_start) * 1000:.2f}ms")

        with get_db() as db:
            query = db.query(Chat).filter(Chat.user_id == user_id)

            if not include_archived:
                query = query.filter(Chat.archived == False)

            query = query.order_by(Chat.updated_at.desc())

            # Import ChatMessage for normalized search
            from open_webui.models.chat_messages import ChatMessage

            # Check if the database dialect is either 'sqlite' or 'postgresql'
            dialect_name = db.bind.dialect.name
            has_fulltext_search = False  # Initialize for all dialects

            if dialect_name == "sqlite":
                # SQLite case: search in normalized chat_message table
                # Search in title OR normalized messages
                query = query.filter(
                    (
                        Chat.title.ilike(
                            f"%{search_text}%"
                        )  # Case-insensitive search in title
                        | exists(
                            select(1).where(
                                and_(
                                    ChatMessage.chat_id == Chat.id,
                                    ChatMessage.content_text.isnot(None),
                                    ChatMessage.content_text.ilike(
                                        f"%{search_text}%")
                                )
                            )
                        )
                    ).params(search_text=search_text)
                )

                # Check if there are any tags to filter, it should have all the tags
                if "none" in tag_ids:
                    query = query.filter(
                        text(
                            """
                            NOT EXISTS (
                                SELECT 1
                                FROM json_each(Chat.meta, '$.tags') AS tag
                            )
                            """
                        )
                    )
                elif tag_ids:
                    query = query.filter(
                        and_(
                            *[
                                text(
                                    f"""
                                    EXISTS (
                                        SELECT 1
                                        FROM json_each(Chat.meta, '$.tags') AS tag
                                        WHERE tag.value = :tag_id_{tag_idx}
                                    )
                                    """
                                ).params(**{f"tag_id_{tag_idx}": tag_id})
                                for tag_idx, tag_id in enumerate(tag_ids)
                            ]
                        )
                    )

            elif dialect_name == "postgresql":
                # Check if full-text search columns exist (migration may not have run yet)
                # Query information_schema to check for the columns
                has_fulltext_search = False
                try:
                    result = db.execute(
                        text("""
                            SELECT COUNT(*) 
                            FROM information_schema.columns 
                            WHERE table_schema = 'public' 
                            AND table_name = 'chat' 
                            AND column_name = 'title_search'
                        """)
                    ).scalar()
                    has_fulltext_search = result > 0
                except Exception:
                    # If check fails, assume columns don't exist and fall back to ILIKE
                    has_fulltext_search = False

                if has_fulltext_search:
                    # PostgreSQL case: use full-text search with tsvector and GIN indexes
                    # Avoid OR condition which prevents index usage - use UNION approach instead
                    # This allows PostgreSQL to use both GIN indexes efficiently

                    perf_before_union = time.time()

                    # Get chat IDs matching in title (uses title_search GIN index)
                    title_match_ids = db.query(Chat.id).filter(
                        Chat.user_id == user_id,
                        text(
                            "chat.title_search @@ plainto_tsquery('english', :search_text)")
                    )
                    if not include_archived:
                        title_match_ids = title_match_ids.filter(
                            Chat.archived == False)

                    # Get chat IDs matching in messages (uses content_text_search GIN index)
                    message_match_ids = db.query(ChatMessage.chat_id).join(
                        Chat, ChatMessage.chat_id == Chat.id
                    ).filter(
                        Chat.user_id == user_id,
                        ChatMessage.content_text.isnot(None),
                        text(
                            "chat_message.content_text_search @@ plainto_tsquery('english', :search_text)")
                    )
                    if not include_archived:
                        message_match_ids = message_match_ids.filter(
                            Chat.archived == False)

                    # Union both result sets and filter main query by matching IDs
                    # This avoids OR and allows both indexes to be used
                    all_match_ids = title_match_ids.union(message_match_ids)

                    # Execute the union query to get matching IDs
                    perf_before_exec = time.time()
                    matching_ids_list = [row[0] for row in all_match_ids.params(
                        search_text=search_text).all()]
                    perf_after_exec = time.time()
                    log.debug(
                        f"Union query execution took {(perf_after_exec - perf_before_exec) * 1000:.2f}ms, found {len(matching_ids_list)} matching chats")

                    if matching_ids_list:
                        query = query.filter(Chat.id.in_(matching_ids_list))
                    else:
                        # No matches, return empty result early
                        perf_total = time.time()
                        log.info(
                            f"Total search took {(perf_total - perf_start) * 1000:.2f}ms, found 0 chats (no matches)")
                        return []

                    perf_after_union = time.time()
                    log.debug(
                        f"Full-text search setup took {(perf_after_union - perf_before_union) * 1000:.2f}ms")
                else:
                    # Fallback to ILIKE if full-text search columns don't exist yet
                    # This allows the code to work before the migration is run
                    query = query.filter(
                        or_(
                            Chat.title.ilike(f"%{search_text}%"),
                            exists(
                                select(1).where(
                                    and_(
                                        ChatMessage.chat_id == Chat.id,
                                        ChatMessage.content_text.isnot(None),
                                        ChatMessage.content_text.ilike(
                                            f"%{search_text}%")
                                    )
                                )
                            )
                        )
                    )

                # Check if there are any tags to filter, it should have all the tags
                if "none" in tag_ids:
                    query = query.filter(
                        text(
                            """
                            NOT EXISTS (
                                SELECT 1
                                FROM json_array_elements_text(Chat.meta->'tags') AS tag
                            )
                            """
                        )
                    )
                elif tag_ids:
                    query = query.filter(
                        and_(
                            *[
                                text(
                                    f"""
                                    EXISTS (
                                        SELECT 1
                                        FROM json_array_elements_text(Chat.meta->'tags') AS tag
                                        WHERE tag = :tag_id_{tag_idx}
                                    )
                                    """
                                ).params(**{f"tag_id_{tag_idx}": tag_id})
                                for tag_idx, tag_id in enumerate(tag_ids)
                            ]
                        )
                    )
            else:
                raise NotImplementedError(
                    f"Unsupported dialect: {db.bind.dialect.name}"
                )

            # Perform pagination at the SQL level
            # Optimize: Only select columns needed for search results to avoid loading large JSON blobs
            # The search endpoint only needs id, title, updated_at, created_at (ChatTitleIdResponse)
            # For PostgreSQL, always use this optimization since we're using normalized chat_message table
            # For SQLite, we still load full objects for backward compatibility
            perf_before_query = time.time()
            if dialect_name == "postgresql":
                # For PostgreSQL search results, we don't need the full chat JSON blob
                # Select only the columns needed for ChatTitleIdResponse
                all_chats = query.with_entities(
                    Chat.id, Chat.title, Chat.updated_at, Chat.created_at
                ).offset(skip).limit(limit).all()

                # Convert tuple results to ChatModel-like objects
                perf_after_query = time.time()
                log.debug(
                    f"Main query execution took {(perf_after_query - perf_before_query) * 1000:.2f}ms")

                perf_before_validate = time.time()
                # Create minimal ChatModel objects with only the fields we have
                result = []
                for chat_row in all_chats:
                    # chat_row is a tuple: (id, title, updated_at, created_at)
                    # Create a minimal ChatModel - we'll need to fetch full data if needed elsewhere
                    # For now, create a dict and validate it
                    chat_dict = {
                        "id": chat_row[0],
                        "user_id": user_id,  # We know this from the filter
                        "title": chat_row[1],
                        "chat": {},  # Empty - not needed for search results
                        "created_at": int(chat_row[3]) if chat_row[3] else 0,
                        "updated_at": int(chat_row[2]) if chat_row[2] else 0,
                        "share_id": None,
                        "archived": False,
                        "pinned": False,
                        "meta": {},
                        "folder_id": None,
                        "active_message_id": None,
                        "root_message_id": None,
                        "params": None,
                        "summary": None,
                    }
                    result.append(ChatModel.model_validate(chat_dict))
            else:
                # For SQLite or non-fulltext, load full objects (legacy behavior)
                all_chats = query.offset(skip).limit(limit).all()
                perf_after_query = time.time()
                log.debug(
                    f"Main query execution took {(perf_after_query - perf_before_query) * 1000:.2f}ms")

                perf_before_validate = time.time()
                result = [ChatModel.model_validate(chat) for chat in all_chats]

            perf_after_validate = time.time()
            log.debug(
                f"Model validation took {(perf_after_validate - perf_before_validate) * 1000:.2f}ms")

            perf_total = time.time()
            log.info(
                f"Total search took {(perf_total - perf_start) * 1000:.2f}ms, found {len(result)} chats")

            # Validate and return chats
            return result

    def get_all_folder_chats_by_user_id(
        self, user_id: str, folder_ids: list[str] = None
    ) -> dict[str, list[dict]]:
        """
        Efficiently fetch chats for multiple folders in a single query.
        Returns a dictionary mapping folder_ids to lists of chat objects (with title and id).
        If folder_ids is None, fetches chats for all folders belonging to the user.
        """
        with get_db() as db:
            query = db.query(Chat).filter_by(user_id=user_id)

            # Only get chats that belong to folders
            query = query.filter(Chat.folder_id.isnot(None))

            # If specific folder IDs are provided, filter by them
            if folder_ids:
                query = query.filter(Chat.folder_id.in_(folder_ids))

            query = query.filter(
                or_(Chat.pinned == False, Chat.pinned == None))
            query = query.filter_by(archived=False)
            query = query.order_by(Chat.updated_at.desc())

            # Select only the necessary fields for performance
            # Include updated_at and created_at so the client can sort reliably
            query = query.with_entities(
                Chat.id, Chat.title, Chat.folder_id, Chat.updated_at, Chat.created_at
            )

            all_chats = query.all()

            # Group the chats by folder_id
            result = {}
            for chat_id, chat_title, folder_id, updated_at, created_at in all_chats:
                if folder_id not in result:
                    result[folder_id] = []
                result[folder_id].append(
                    {
                        "id": chat_id,
                        "title": chat_title,
                        "updated_at": int(updated_at) if updated_at is not None else None,
                        "created_at": int(created_at) if created_at is not None else None,
                    }
                )

            return result

    def get_chats_by_folder_ids_and_user_id(
        self, folder_ids: list[str], user_id: str
    ) -> list[ChatModel]:
        """
        Retrieves all chats associated with a list of folder IDs for a specific user.
        This function is optimized to perform a single database query.
        """
        with get_db() as db:
            query = db.query(Chat).filter(
                Chat.folder_id.in_(folder_ids), Chat.user_id == user_id
            )
            query = query.filter(
                or_(Chat.pinned == False, Chat.pinned == None))
            query = query.filter_by(archived=False)
            query = query.order_by(Chat.updated_at.desc())

            all_chats = query.all()
            return [ChatModel.model_validate(chat) for chat in all_chats]

    def update_chat_folder_id_by_id_and_user_id(
        self, id: str, user_id: str, folder_id: str
    ) -> Optional[ChatModel]:
        try:
            with get_db() as db:
                chat = db.get(Chat, id)
                chat.folder_id = folder_id
                chat.updated_at = int(time.time())
                chat.pinned = False
                db.commit()
                db.refresh(chat)
                return ChatModel.model_validate(chat)
        except Exception:
            return None

    def get_chat_tags_by_id_and_user_id(self, id: str, user_id: str) -> list[TagModel]:
        with get_db() as db:
            chat = db.get(Chat, id)
            tags = chat.meta.get("tags", [])
            return [Tags.get_tag_by_name_and_user_id(tag, user_id) for tag in tags]

    def get_chat_list_by_user_id_and_tag_name(
        self, user_id: str, tag_name: str, skip: int = 0, limit: int = 50
    ) -> list[ChatModel]:
        with get_db() as db:
            query = db.query(Chat).filter_by(user_id=user_id)
            tag_id = tag_name.replace(" ", "_").lower()

            log.info(f"DB dialect name: {db.bind.dialect.name}")
            if db.bind.dialect.name == "sqlite":
                # SQLite JSON1 querying for tags within the meta JSON field
                query = query.filter(
                    text(
                        f"EXISTS (SELECT 1 FROM json_each(Chat.meta, '$.tags') WHERE json_each.value = :tag_id)"
                    )
                ).params(tag_id=tag_id)
            elif db.bind.dialect.name == "postgresql":
                # PostgreSQL JSON query for tags within the meta JSON field (for `json` type)
                query = query.filter(
                    text(
                        "EXISTS (SELECT 1 FROM json_array_elements_text(Chat.meta->'tags') elem WHERE elem = :tag_id)"
                    )
                ).params(tag_id=tag_id)
            else:
                raise NotImplementedError(
                    f"Unsupported dialect: {db.bind.dialect.name}"
                )

            all_chats = query.all()
            log.debug(f"all_chats: {all_chats}")
            return [ChatModel.model_validate(chat) for chat in all_chats]

    def add_chat_tag_by_id_and_user_id_and_tag_name(
        self, id: str, user_id: str, tag_name: str
    ) -> Optional[ChatModel]:
        tag = Tags.get_tag_by_name_and_user_id(tag_name, user_id)
        if tag is None:
            tag = Tags.insert_new_tag(tag_name, user_id)
        try:
            with get_db() as db:
                chat = db.get(Chat, id)

                tag_id = tag.id
                if tag_id not in chat.meta.get("tags", []):
                    chat.meta = {
                        **chat.meta,
                        "tags": list(set(chat.meta.get("tags", []) + [tag_id])),
                    }

                db.commit()
                db.refresh(chat)
                return ChatModel.model_validate(chat)
        except Exception:
            return None

    def count_chats_by_tag_name_and_user_id(self, tag_name: str, user_id: str) -> int:
        with get_db() as db:  # Assuming `get_db()` returns a session object
            query = db.query(Chat).filter_by(user_id=user_id, archived=False)

            # Normalize the tag_name for consistency
            tag_id = tag_name.replace(" ", "_").lower()

            if db.bind.dialect.name == "sqlite":
                # SQLite JSON1 support for querying the tags inside the `meta` JSON field
                query = query.filter(
                    text(
                        f"EXISTS (SELECT 1 FROM json_each(Chat.meta, '$.tags') WHERE json_each.value = :tag_id)"
                    )
                ).params(tag_id=tag_id)

            elif db.bind.dialect.name == "postgresql":
                # PostgreSQL JSONB support for querying the tags inside the `meta` JSON field
                query = query.filter(
                    text(
                        "EXISTS (SELECT 1 FROM json_array_elements_text(Chat.meta->'tags') elem WHERE elem = :tag_id)"
                    )
                ).params(tag_id=tag_id)

            else:
                raise NotImplementedError(
                    f"Unsupported dialect: {db.bind.dialect.name}"
                )

            # Get the count of matching records
            count = query.count()

            # Debugging output for inspection
            log.info(f"Count of chats for tag '{tag_name}': {count}")

            return count

    def delete_tag_by_id_and_user_id_and_tag_name(
        self, id: str, user_id: str, tag_name: str
    ) -> bool:
        try:
            with get_db() as db:
                chat = db.get(Chat, id)
                tags = chat.meta.get("tags", [])
                tag_id = tag_name.replace(" ", "_").lower()

                tags = [tag for tag in tags if tag != tag_id]
                chat.meta = {
                    **chat.meta,
                    "tags": list(set(tags)),
                }
                db.commit()
                return True
        except Exception:
            return False

    def delete_all_tags_by_id_and_user_id(self, id: str, user_id: str) -> bool:
        try:
            with get_db() as db:
                chat = db.get(Chat, id)
                chat.meta = {
                    **chat.meta,
                    "tags": [],
                }
                db.commit()

                return True
        except Exception:
            return False

    def delete_chat_by_id(self, id: str) -> bool:
        try:
            with get_db() as db:
                # Delete all messages for this chat (and their attachments via CASCADE)
                from open_webui.models.chat_messages import ChatMessage
                db.query(ChatMessage).filter_by(chat_id=id).delete()

                # Delete the chat
                db.query(Chat).filter_by(id=id).delete()
                db.commit()

                return True and self.delete_shared_chat_by_chat_id(id)
        except Exception:
            return False

    def delete_chat_by_id_and_user_id(self, id: str, user_id: str) -> bool:
        try:
            with get_db() as db:
                # Delete all messages for this chat (and their attachments via CASCADE)
                from open_webui.models.chat_messages import ChatMessage
                db.query(ChatMessage).filter_by(chat_id=id).delete()

                # Delete the chat
                db.query(Chat).filter_by(id=id, user_id=user_id).delete()
                db.commit()

                return True and self.delete_shared_chat_by_chat_id(id)
        except Exception:
            return False

    def delete_chats_by_user_id(self, user_id: str) -> bool:
        try:
            with get_db() as db:
                self.delete_shared_chats_by_user_id(user_id)

                # Get all chat IDs for this user before deleting
                from open_webui.models.chat_messages import ChatMessage
                chat_ids = [chat.id for chat in db.query(
                    Chat).filter_by(user_id=user_id).all()]

                # Delete all messages for all chats belonging to this user
                # (attachments will be deleted via CASCADE when messages are deleted)
                if chat_ids:
                    db.query(ChatMessage).filter(
                        ChatMessage.chat_id.in_(chat_ids)).delete()

                # Delete the chats
                db.query(Chat).filter_by(user_id=user_id).delete()
                db.commit()

                return True
        except Exception:
            return False

    def delete_chats_by_user_id_and_folder_id(
        self, user_id: str, folder_id: str
    ) -> bool:
        try:
            with get_db() as db:
                # Get all chat IDs for this user and folder before deleting
                from open_webui.models.chat_messages import ChatMessage
                chat_ids = [chat.id for chat in db.query(Chat).filter_by(
                    user_id=user_id, folder_id=folder_id).all()]

                # Delete all messages for all chats in this folder
                # (attachments will be deleted via CASCADE when messages are deleted)
                if chat_ids:
                    db.query(ChatMessage).filter(
                        ChatMessage.chat_id.in_(chat_ids)).delete()

                # Delete the chats
                db.query(Chat).filter_by(user_id=user_id,
                                         folder_id=folder_id).delete()
                db.commit()

                return True
        except Exception:
            return False

    def delete_shared_chats_by_user_id(self, user_id: str) -> bool:
        try:
            with get_db() as db:
                chats_by_user = db.query(Chat).filter_by(user_id=user_id).all()
                shared_chat_ids = [
                    f"shared-{chat.id}" for chat in chats_by_user]

                # Get the actual shared chat IDs (not just the user_id pattern)
                from open_webui.models.chat_messages import ChatMessage
                shared_chats = db.query(Chat).filter(
                    Chat.user_id.in_(shared_chat_ids)).all()
                shared_chat_actual_ids = [chat.id for chat in shared_chats]

                # Delete all messages for all shared chats (attachments will be deleted via CASCADE)
                if shared_chat_actual_ids:
                    db.query(ChatMessage).filter(
                        ChatMessage.chat_id.in_(shared_chat_actual_ids)).delete()

                # Delete the shared chats
                db.query(Chat).filter(
                    Chat.user_id.in_(shared_chat_ids)).delete()
                db.commit()

                return True
        except Exception:
            return False

    def clone_chat(self, source_chat_id: str, user_id: str, new_title: Optional[str] = None) -> Optional[ChatModel]:
        """
        Clone a chat and all its messages.
        Creates a new chat entry with a new ID and duplicates all messages.
        Returns the new cloned chat.
        """
        from open_webui.models.chat_messages import ChatMessages, ChatMessage

        # Get source chat
        source_chat = self.get_chat_by_id(source_chat_id)
        if not source_chat:
            return None

        # Check if source chat has normalized messages
        with get_db() as db:
            has_normalized = db.query(ChatMessage).filter_by(
                chat_id=source_chat_id).first() is not None

        # Create new chat entry
        new_chat_id = str(uuid.uuid4())
        ts = int(time.time())

        # Determine title
        title = new_title if new_title else f"Clone of {source_chat.title}"

        # Create new chat with updated metadata
        new_chat = ChatModel(
            **{
                "id": new_chat_id,
                "user_id": user_id,
                "title": title,
                "chat": {},  # Will be populated by normalized_to_legacy_format when needed
                "created_at": ts,
                "updated_at": ts,
                "share_id": None,  # Cloned chats don't inherit share_id
                "archived": False,
                "pinned": False,
                "meta": source_chat.meta.copy() if source_chat.meta else {},
                "folder_id": source_chat.folder_id,
                "active_message_id": None,  # Will be set after cloning messages
                "root_message_id": None,  # Will be set after cloning messages
                "params": source_chat.params.copy() if source_chat.params else None,
                "summary": source_chat.summary,
            }
        )

        # Add meta to track original chat
        if not new_chat.meta:
            new_chat.meta = {}
        new_chat.meta["originalChatId"] = source_chat_id

        with get_db() as db:
            result = Chat(**new_chat.model_dump())
            db.add(result)
            db.flush()

            # Clone messages if the source chat has normalized messages
            if has_normalized:
                id_mapping = ChatMessages.clone_messages_to_chat(
                    source_chat_id, new_chat_id)

                # Update active_message_id and root_message_id to new message IDs
                new_active_message_id = None
                new_root_message_id = None

                if source_chat.active_message_id:
                    old_active_id = str(source_chat.active_message_id)
                    new_active_message_id = id_mapping.get(old_active_id)

                if source_chat.root_message_id:
                    old_root_id = str(source_chat.root_message_id)
                    new_root_message_id = id_mapping.get(old_root_id)

                # Update the chat with new message IDs
                result.active_message_id = new_active_message_id
                result.root_message_id = new_root_message_id

                # Also add branchPointMessageId to meta for legacy compatibility
                if new_active_message_id:
                    result.meta = {
                        **(result.meta or {}),
                        "branchPointMessageId": new_active_message_id,
                    }
            else:
                # Legacy chat - clone the chat JSON blob
                # This is the old format where messages were stored in chat.chat JSON
                if source_chat.chat:
                    legacy_chat = source_chat.chat.copy()
                    legacy_chat["originalChatId"] = source_chat_id
                    # Get branchPointMessageId from legacy format
                    history = legacy_chat.get("history", {})
                    current_id = history.get("currentId")
                    if current_id:
                        legacy_chat["branchPointMessageId"] = current_id
                        result.meta = {
                            **(result.meta or {}),
                            "branchPointMessageId": current_id,
                        }
                    result.chat = legacy_chat

            db.commit()
            db.refresh(result)

            return ChatModel.model_validate(result)


Chats = ChatTable()
