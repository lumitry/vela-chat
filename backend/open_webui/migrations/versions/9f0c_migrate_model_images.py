"""migrate model profile images from base64 to filesystem storage

Revision ID: 9f0c_migrate_model_images
Revises: 9f0b_backfill_chat_messages
Create Date: 2025-01-15 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String, Text, JSON, BigInteger

import json
import uuid
import time
import base64
import hashlib
import mimetypes
from pathlib import Path


revision = '9f0c_migrate_model_images'
down_revision = 'add_tokens_to_chat_message'
branch_labels = None
depends_on = None


def is_data_url(url: str) -> bool:
    """Check if a URL is a data URL (base64 encoded)."""
    return isinstance(url, str) and url.startswith('data:') and ';base64,' in url


def decode_data_url(data_url: str):
    """Decode a data URL into raw bytes and MIME type."""
    header, b64 = data_url.split(',', 1)
    mime = header.split(';')[0].split(':', 1)[1] if ':' in header else 'image/png'
    raw = base64.b64decode(b64)
    return raw, mime


def calculate_sha256_bytes(data: bytes) -> str:
    """Calculate SHA-256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


def upgrade() -> None:
    conn = op.get_bind()

    model_table = table(
        'model',
        column('id', String),
        column('user_id', String),
        column('meta', JSON),
    )

    file_table = table(
        'file',
        column('id', String),
        column('user_id', String),
        column('hash', Text),
        column('filename', Text),
        column('path', Text),
        column('data', JSON),
        column('meta', JSON),
        column('created_at', BigInteger),
        column('updated_at', BigInteger),
    )

    # Fetch all models
    rows = conn.execute(sa.select(model_table.c.id, model_table.c.user_id, model_table.c.meta)).fetchall()

    # Directory for storing model images
    # backend/open_webui/migrations/versions/../../data/uploads/model_images
    uploads_dir = Path(__file__).resolve().parents[2] / 'data' / 'uploads' / 'model_images'
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Track hash -> file_id mapping for deduplication
    hash_to_file_id = {}
    migrated_count = 0
    skipped_count = 0

    for row in rows:
        model_id = row.id
        user_id = row.user_id
        meta = row.meta if isinstance(row.meta, dict) else (json.loads(row.meta) if isinstance(row.meta, str) else {})

        if not meta:
            continue

        profile_image_url = meta.get('profile_image_url')
        if not profile_image_url or not is_data_url(profile_image_url):
            # Skip if not a data URL (might be /static/favicon.png or already migrated)
            skipped_count += 1
            continue

        try:
            # Decode the base64 image
            raw_bytes, mime_type = decode_data_url(profile_image_url)
            
            # Calculate hash for deduplication
            file_hash = calculate_sha256_bytes(raw_bytes)
            
            # Check if we've already created a file for this hash in this migration
            if file_hash in hash_to_file_id:
                file_id = hash_to_file_id[file_hash]
                new_url = f"/api/v1/files/{file_id}/content"
            else:
                # Check if a file with this hash already exists in the database
                existing_files = conn.execute(
                    sa.select(file_table.c.id, file_table.c.meta)
                    .where(file_table.c.hash == file_hash)
                ).fetchall()
                
                # Check if any existing file has matching content type
                existing_file_id = None
                for existing_file in existing_files:
                    existing_meta = existing_file.meta if isinstance(existing_file.meta, dict) else (json.loads(existing_file.meta) if isinstance(existing_file.meta, str) else {})
                    if existing_meta and existing_meta.get('content_type') == mime_type:
                        existing_file_id = existing_file.id
                        break
                
                if existing_file_id:
                    # Reuse existing file
                    file_id = existing_file_id
                    hash_to_file_id[file_hash] = file_id
                    new_url = f"/api/v1/files/{file_id}/content"
                else:
                    # Create new file
                    ext = mimetypes.guess_extension(mime_type) or '.bin'
                    filename = f"{file_hash}{ext}"
                    file_path = uploads_dir / filename
                    
                    # Write to filesystem
                    with open(file_path, 'wb') as f:
                        f.write(raw_bytes)
                    
                    # Create file record
                    file_id = str(uuid.uuid4())
                    ts = int(time.time())
                    conn.execute(
                        sa.insert(file_table).values(
                            id=file_id,
                            user_id=user_id,  # Use model owner's user_id
                            hash=file_hash,
                            filename=filename,
                            path=str(file_path),
                            data={"size": len(raw_bytes)},
                            meta={"content_type": mime_type, "size": len(raw_bytes), "model_image": True},
                            created_at=ts,
                            updated_at=ts,
                        )
                    )
                    
                    hash_to_file_id[file_hash] = file_id
                    new_url = f"/api/v1/files/{file_id}/content"
            
            # Update model meta with new URL
            meta['profile_image_url'] = new_url
            # SQLAlchemy JSON column handles serialization automatically
            conn.execute(
                sa.update(model_table)
                .where(model_table.c.id == model_id)
                .values(meta=meta)
            )
            
            migrated_count += 1
            
        except Exception as e:
            # Log error but continue with other models
            print(f"Error migrating model {model_id}: {e}")
            continue

    # Commit all changes
    conn.commit()
    
    print(f"Migration complete: {migrated_count} models migrated, {skipped_count} skipped")


def downgrade() -> None:
    # Note: Downgrade would require storing the original base64 data, which we don't have
    # So we'll just leave the migrated URLs in place
    # If needed, we could restore from a backup or re-encode the files, but that's complex
    pass

