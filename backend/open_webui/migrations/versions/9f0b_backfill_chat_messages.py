"""backfill chat messages and migrate base64 images

Revision ID: 9f0b_backfill_chat_messages
Revises: 9f0a_chat_messages_init
Create Date: 2025-11-01 00:10:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String, Text, JSON, BigInteger

import json
import uuid
import time
import base64
import re
import io
import mimetypes

import os
from pathlib import Path


revision = '9f0b_backfill_chat_messages'
down_revision = '9f0a_chat_messages_init'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add columns to chat table
    op.add_column('chat', sa.Column('active_message_id', sa.Text(), nullable=True))
    op.add_column('chat', sa.Column('root_message_id', sa.Text(), nullable=True))
    op.add_column('chat', sa.Column('params', sa.JSON(), nullable=True))
    op.add_column('chat', sa.Column('summary', sa.Text(), nullable=True))

    conn = op.get_bind()

    chat_table = table(
        'chat',
        column('id', String),
        column('user_id', String),
        column('title', Text),
        column('chat', JSON),
        column('meta', JSON),
        column('active_message_id', Text),
        column('root_message_id', Text),
        column('params', JSON),
    )

    file_table = table(
        'file',
        column('id', String),
        column('user_id', String),
        column('filename', Text),
        column('path', Text),
        column('data', JSON),
        column('meta', JSON),
        column('created_at', BigInteger),
        column('updated_at', BigInteger),
    )

    # Fetch chats
    rows = conn.execute(sa.select(chat_table.c.id, chat_table.c.user_id, chat_table.c.chat, chat_table.c.meta)).fetchall()

    def is_data_url(url: str) -> bool:
        return isinstance(url, str) and url.startswith('data:') and ';base64,' in url

    def decode_data_url(data_url: str):
        header, b64 = data_url.split(',', 1)
        mime = header.split(';')[0].split(':', 1)[1] if ':' in header else 'image/png'
        raw = base64.b64decode(b64)
        return raw, mime

    def upload_and_record(user_id: str, raw: bytes, mime: str):
        # Write to local uploads dir to avoid importing app storage during migration
        ext = mimetypes.guess_extension(mime) or '.bin'
        fid = str(uuid.uuid4())
        filename = f"{fid}{ext}"
        # backend/open_webui/migrations/versions/../../data/uploads
        uploads_dir = Path(__file__).resolve().parents[2] / 'data' / 'uploads'
        uploads_dir.mkdir(parents=True, exist_ok=True)
        file_path = uploads_dir / filename
        with open(file_path, 'wb') as f:
            f.write(raw)
        ts = int(time.time())
        conn.execute(
            sa.insert(file_table).values(
                id=fid,
                user_id=user_id,
                filename=filename,
                path=str(file_path),
                data={"size": len(raw)},
                meta={"content_type": mime, "size": len(raw)},
                created_at=ts,
                updated_at=ts,
            )
        )
        return fid

    # Insert helpers for messages/attachments using SQL
    def insert_message(mid, chat_id, parent_id, role, model_id, content_text, content_json, status, usage, meta, created_at, annotation=None, feedback_id=None, selected_model_id=None):
        conn.execute(
            sa.text(
                """
                INSERT INTO chat_message (id, chat_id, parent_id, role, model_id, content_text, content_json, status, usage, meta, annotation, feedback_id, selected_model_id, created_at, updated_at)
                VALUES (:id, :chat_id, :parent_id, :role, :model_id, :content_text, :content_json, :status, :usage, :meta, :annotation, :feedback_id, :selected_model_id, :created_at, :updated_at)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                'id': mid,
                'chat_id': chat_id,
                'parent_id': parent_id,
                'role': role,
                'model_id': model_id,
                'content_text': content_text,
                'content_json': json.dumps(content_json) if content_json is not None else None,
                'status': json.dumps(status) if status is not None else None,
                'usage': json.dumps(usage) if usage is not None else None,
                'meta': json.dumps(meta) if meta is not None else None,
                'annotation': json.dumps(annotation) if annotation is not None else None,
                'feedback_id': feedback_id,
                'selected_model_id': selected_model_id,
                'created_at': created_at,
                'updated_at': created_at,
            },
        )

    def insert_attachment(aid, message_id, typ, file_id, url, mime, size, meta):
        conn.execute(
            sa.text(
                """
                INSERT INTO chat_message_attachment (id, message_id, type, file_id, url, mime_type, size_bytes, meta, created_at)
                VALUES (:id, :message_id, :type, :file_id, :url, :mime_type, :size_bytes, :meta, :created_at)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                'id': aid,
                'message_id': message_id,
                'type': typ,
                'file_id': file_id,
                'url': url,
                'mime_type': mime,
                'size_bytes': size,
                'meta': json.dumps(meta) if meta is not None else None,
                'created_at': int(time.time()),
            },
        )

    for row in rows:
        chat_id = row.id
        user_id = row.user_id
        chat_json = row.chat
        chat_meta = row.meta if isinstance(row.meta, dict) else {}
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
            history_messages = {}

        # Backfill messages
        root_id = None
        ts_now = int(time.time())
        for mid, msg in history_messages.items():
            # Prefer the embedded id if present
            message_id = msg.get('id') or mid
            parent_id = msg.get('parentId')
            if parent_id is None and root_id is None:
                root_id = message_id

            role = msg.get('role') or ('assistant' if msg.get('model') else 'user')
            model_id = msg.get('model')
            content_text = msg.get('content')
            content_json = None
            status = {'statusHistory': msg.get('statusHistory')} if msg.get('statusHistory') else None
            usage = msg.get('usage')
            
            # Preserve unmigrated fields in meta
            message_meta = {}
            if msg.get('modelIdx') is not None:
                message_meta['modelIdx'] = msg.get('modelIdx')
            if msg.get('models'):
                message_meta['models'] = msg.get('models')
            if msg.get('userContext') is not None:
                message_meta['userContext'] = msg.get('userContext')
            if msg.get('lastSentence'):
                message_meta['lastSentence'] = msg.get('lastSentence')
            message_meta = message_meta if message_meta else None
            
            # Extract feedback/evaluation fields
            annotation = msg.get('annotation')
            feedback_id = msg.get('feedbackId')  # Note: frontend uses camelCase
            selected_model_id = msg.get('selectedModelId')  # Note: frontend uses camelCase
            
            created_at = int(msg.get('timestamp') or ts_now)

            insert_message(
                message_id, chat_id, parent_id, role, model_id,
                content_text, content_json, status, usage, message_meta, created_at,
                annotation=annotation, feedback_id=feedback_id, selected_model_id=selected_model_id
            )

            # Attachments
            files = msg.get('files') or []
            for f in files:
                ftype = f.get('type') or 'file'
                furl = f.get('url')
                file_id = None
                mime_guess = None
                size_guess = None
                if ftype == 'image' and furl:
                    if is_data_url(furl):
                        raw, mime = decode_data_url(furl)
                        file_id = upload_and_record(user_id, raw, mime)
                        mime_guess = mime
                        size_guess = len(raw)
                        new_url = f"/api/v1/files/{file_id}/content"
                        # mutate chat_json to drop base64
                        f['url'] = new_url
                        furl = new_url
                    else:
                        # possibly server URL already
                        pass
                aid = str(uuid.uuid4())
                insert_attachment(aid, message_id, ftype, file_id, furl, mime_guess, size_guess, None)

        # Update chat row with active/root ids and params, and mutated chat JSON (urls)
        active_id = history.get('currentId')
        params = (chat_json or {}).get('params')
        if not isinstance(chat_meta, dict):
            chat_meta = {}
        chat_meta['storage_version'] = 2
        conn.execute(
            sa.update(chat_table)
            .where(chat_table.c.id == chat_id)
            .values(
                active_message_id=active_id,
                root_message_id=root_id,
                params=params,
                meta=chat_meta,
                chat=chat_json,
            )
        )


def downgrade() -> None:
    # Do not delete any data; only drop columns added in upgrade.
    with op.batch_alter_table('chat') as batch:
        batch.drop_column('summary')
        batch.drop_column('params')
        batch.drop_column('root_message_id')
        batch.drop_column('active_message_id')


