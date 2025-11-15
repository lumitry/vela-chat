"""migrate RAG files from chat.chat to chat_message.meta

Revision ID: ad303355
Revises: add_task_model_tracking
Create Date: 2025-11-11 20:49:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String, Text, JSON, BigInteger

import json
import uuid
import time


revision = 'ad303355'
down_revision = 'add_task_model_tracking'
branch_labels = None
depends_on = None


def strip_collection_files(file_item):
    """Strip files array and data.file_ids from collection objects"""
    if not isinstance(file_item, dict):
        return file_item

    if file_item.get("type") == "collection":
        # Create a copy without files and data.file_ids
        stripped = {k: v for k, v in file_item.items() if k != "files"}
        if "data" in stripped and isinstance(stripped["data"], dict):
            data_copy = {k: v for k,
                         v in stripped["data"].items() if k != "file_ids"}
            if data_copy:
                stripped["data"] = data_copy
            else:
                stripped.pop("data", None)
        return stripped
    return file_item


def upgrade() -> None:
    """
    Migrate RAG files from chat.chat.history.messages[].files to chat_message.meta["files"]
    and create chat_message_attachment records.

    This migration:
    1. Reads all chats from chat.chat column
    2. For each message in history.messages, extracts non-image files (RAG files)
    3. Adds them to chat_message.meta["files"] after stripping collections
    4. Creates chat_message_attachment records for them
    """
    conn = op.get_bind()

    chat_table = table(
        'chat',
        column('id', String),
        column('chat', JSON),
    )

    chat_message_table = table(
        'chat_message',
        column('id', String),
        column('chat_id', String),
        column('meta', JSON),
        column('role', Text),
    )

    chat_message_attachment_table = table(
        'chat_message_attachment',
        column('id', String),
        column('message_id', String),
        column('type', Text),
        column('file_id', String),
        column('url', Text),
        column('mime_type', Text),
        column('size_bytes', BigInteger),
        column('meta', JSON),
        column('created_at', BigInteger),
    )

    # Process chats in batches to avoid memory issues with large JSON blobs
    batch_size = 50
    migrated_count = 0
    files_migrated = 0
    sources_migrated = 0

    # Get all chat IDs first (lightweight query)
    all_chat_ids_result = conn.execute(sa.select(chat_table.c.id)).fetchall()
    all_chat_ids = [row[0] for row in all_chat_ids_result]
    total_chats = len(all_chat_ids)
    print(f"Processing {total_chats} chats in batches of {batch_size}...")

    # Process chats in batches
    for batch_start in range(0, len(all_chat_ids), batch_size):
        batch_ids = all_chat_ids[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (len(all_chat_ids) + batch_size - 1) // batch_size
        print(
            f"Processing batch {batch_num}/{total_batches} ({len(batch_ids)} chats)...")

        # Fetch only this batch of chats
        batch_rows = conn.execute(
            sa.select(chat_table.c.id, chat_table.c.chat)
            .where(chat_table.c.id.in_(batch_ids))
        ).fetchall()

        for row in batch_rows:
            chat_id = row.id
            chat_json = row.chat

            if not chat_json:
                continue

            # Normalize chat_json type
            if isinstance(chat_json, str):
                try:
                    chat_json = json.loads(chat_json)
                except Exception:
                    continue

            history = (chat_json or {}).get('history') or {}
            history_messages = history.get('messages') or {}

            if isinstance(history_messages, list):
                # Unexpected older shape; skip list-style
                continue

            # Process each message
            for mid, msg in history_messages.items():
                message_id = msg.get('id') or mid
                if not message_id:
                    continue

                # Check if message exists in normalized table
                msg_row = conn.execute(
                    sa.select(chat_message_table.c.id,
                              chat_message_table.c.meta,
                              chat_message_table.c.role)
                    .where(chat_message_table.c.id == message_id)
                ).first()

                if not msg_row:
                    # Message doesn't exist in normalized table, skip
                    continue

                # Migrate sources for assistant messages
                sources = msg.get('sources')
                if sources and isinstance(sources, list) and len(sources) > 0:
                    # Only migrate sources for assistant messages
                    if msg_row.role == 'assistant':
                        # Get existing meta
                        existing_meta = msg_row.meta
                        if isinstance(existing_meta, str):
                            try:
                                existing_meta = json.loads(existing_meta)
                            except Exception:
                                existing_meta = {}
                        elif not isinstance(existing_meta, dict):
                            existing_meta = {}

                        # Check if sources already exist in meta (avoid duplicate migration)
                        if "sources" not in existing_meta:
                            # Strip collections from sources to reduce payload size
                            stripped_sources = []
                            for source in sources:
                                if isinstance(source, dict) and "source" in source:
                                    source_copy = dict(source)
                                    if isinstance(source_copy["source"], dict) and source_copy["source"].get("type") == "collection":
                                        source_copy["source"] = strip_collection_files(
                                            source_copy["source"])
                                    stripped_sources.append(source_copy)
                                else:
                                    stripped_sources.append(source)

                            # Add stripped sources to meta
                            existing_meta["sources"] = stripped_sources
                            # Update chat_message.meta
                            conn.execute(
                                sa.update(chat_message_table)
                                .where(chat_message_table.c.id == message_id)
                                .values(meta=existing_meta)
                            )
                            sources_migrated += 1

                # Get files from legacy message (if any)
                files = msg.get('files') or []

                # Filter out image files (already handled by previous migration)
                # and process RAG files (collections, files, docs)
                rag_files = []
                for f in files:
                    ftype = f.get('type') or 'file'
                    # Skip images (already migrated in 9f0b_backfill_chat_messages)
                    if ftype == 'image':
                        continue
                    # Process RAG files: collection, file, doc, web_search
                    if ftype in ['collection', 'file', 'doc', 'web_search']:
                        rag_files.append(f)

                if not rag_files:
                    continue

                # Get existing meta or create new
                existing_meta = msg_row.meta
                if isinstance(existing_meta, str):
                    try:
                        existing_meta = json.loads(existing_meta)
                    except Exception:
                        existing_meta = {}
                elif not isinstance(existing_meta, dict):
                    existing_meta = {}

                # Check if files already exist in meta (avoid duplicate migration)
                existing_files = existing_meta.get('files', [])
                if existing_files:
                    # Files already migrated, skip
                    continue

                # Strip collections and prepare files for meta
                meta_files = []
                for f in rag_files:
                    stripped = strip_collection_files(f)
                    meta_files.append(stripped)

                # Update message meta with files
                existing_meta['files'] = meta_files

                # Update chat_message.meta
                # SQLAlchemy handles JSON columns automatically, so pass the dict directly
                conn.execute(
                    sa.update(chat_message_table)
                    .where(chat_message_table.c.id == message_id)
                    .values(meta=existing_meta)
                )

                # Create chat_message_attachment records
                created_at = int(msg.get('timestamp') or time.time())
                for f in rag_files:
                    ftype = f.get('type') or 'file'
                    file_id = f.get('id') if ftype not in [
                        'collection', 'web_search'] else None
                    url = f.get('url') if ftype not in [
                        'collection', 'web_search'] else None
                    mime_type = f.get('mime_type')
                    size_bytes = f.get('size_bytes')

                    # Build attachment metadata (strip collections)
                    attachment_meta = {}
                    if "meta" in f and isinstance(f.get("meta"), dict):
                        attachment_meta.update(f["meta"])
                    if "metadata" in f:
                        attachment_meta.update(f["metadata"])

                    # Copy top-level fields
                    fields_to_copy = ["name", "description", "status",
                                      "collection", "collection_name", "collection_names"]
                    if ftype == "collection":
                        fields_to_copy.extend(
                            ["id", "user_id", "user", "access_control", "created_at", "updated_at"])
                        # Copy data but exclude file_ids
                        if "data" in f and isinstance(f["data"], dict):
                            data_copy = {k: v for k,
                                         v in f["data"].items() if k != "file_ids"}
                            if data_copy:
                                attachment_meta["data"] = data_copy

                    for key in fields_to_copy:
                        if key in f:
                            attachment_meta[key] = f[key]

                    attachment_id = str(uuid.uuid4())

                    # Check if attachment already exists (avoid duplicates)
                    existing_att = conn.execute(
                        sa.select(chat_message_attachment_table.c.id)
                        .where(chat_message_attachment_table.c.message_id == message_id)
                        .where(chat_message_attachment_table.c.type == ftype)
                        .where(chat_message_attachment_table.c.file_id == file_id)
                    ).first()

                    if not existing_att:
                        # SQLAlchemy handles JSON columns automatically, so pass the dict directly
                        conn.execute(
                            sa.insert(chat_message_attachment_table).values(
                                id=attachment_id,
                                message_id=message_id,
                                type=ftype,
                                file_id=file_id,
                                url=url,
                                mime_type=mime_type,
                                size_bytes=size_bytes,
                                meta=attachment_meta if attachment_meta else None,
                                created_at=created_at,
                            )
                        )
                        files_migrated += 1

                migrated_count += 1

    # Also strip collections from chat-level files (chat.chat.files)
    print("Stripping collections from chat-level files...")
    chat_files_migrated = 0
    # Process chats in batches (reuse the same batch approach)
    for batch_start in range(0, len(all_chat_ids), batch_size):
        batch_ids = all_chat_ids[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (len(all_chat_ids) + batch_size - 1) // batch_size
        print(
            f"Stripping collections from batch {batch_num}/{total_batches} ({len(batch_ids)} chats)...")

        # Fetch only this batch of chats
        batch_rows = conn.execute(
            sa.select(chat_table.c.id, chat_table.c.chat)
            .where(chat_table.c.id.in_(batch_ids))
        ).fetchall()

        for row in batch_rows:
            chat_id = row.id
            chat_json = row.chat

            if not chat_json:
                continue

            # Normalize chat_json type
            if isinstance(chat_json, str):
                try:
                    chat_json = json.loads(chat_json)
                except Exception:
                    continue

            # Check if chat has files
            if not isinstance(chat_json, dict) or "files" not in chat_json:
                continue

            files_list = chat_json.get("files", [])
            if not isinstance(files_list, list):
                continue

            # Check if any collections need stripping (have files or data.file_ids)
            needs_stripping = False
            for f in files_list:
                if isinstance(f, dict) and f.get("type") == "collection":
                    if "files" in f or (isinstance(f.get("data"), dict) and "file_ids" in f.get("data", {})):
                        needs_stripping = True
                        break

            if not needs_stripping:
                continue

            # Strip collections
            stripped_files = [strip_collection_files(f) for f in files_list]
            chat_json["files"] = stripped_files

            # Update chat - SQLAlchemy handles JSON columns automatically
            conn.execute(
                sa.update(chat_table)
                .where(chat_table.c.id == chat_id)
                .values(chat=chat_json)
            )
            chat_files_migrated += 1

    print(
        f"Migration complete: {migrated_count} messages migrated, {files_migrated} files migrated, {sources_migrated} sources migrated, {chat_files_migrated} chats with stripped collections")


def downgrade() -> None:
    """
    Downgrade: Remove files from chat_message.meta and delete corresponding attachments.
    Note: This does not restore files to chat.chat as that data may have been modified.
    """
    conn = op.get_bind()

    chat_message_table = table(
        'chat_message',
        column('id', String),
        column('meta', JSON),
    )

    chat_message_attachment_table = table(
        'chat_message_attachment',
        column('id', String),
        column('message_id', String),
        column('type', Text),
    )

    # Get all messages with files in meta
    rows = conn.execute(
        sa.select(chat_message_table.c.id, chat_message_table.c.meta)
    ).fetchall()

    for row in rows:
        message_id = row.id
        meta = row.meta

        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                continue
        elif not isinstance(meta, dict):
            continue

        if 'files' not in meta:
            continue

        # Remove files from meta
        meta.pop('files', None)

        # Update message
        # SQLAlchemy handles JSON columns automatically, so pass the dict directly
        conn.execute(
            sa.update(chat_message_table)
            .where(chat_message_table.c.id == message_id)
            .values(meta=meta if meta else None)
        )

        # Delete attachments that are RAG files (not images)
        conn.execute(
            sa.delete(chat_message_attachment_table)
            .where(chat_message_attachment_table.c.message_id == message_id)
            .where(chat_message_attachment_table.c.type.in_(['collection', 'file', 'doc', 'web_search']))
        )

    print("Downgrade complete: Removed files from chat_message.meta and deleted RAG attachments")
