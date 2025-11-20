"""migrate base64-encoded images from config and user tables to filesystem storage

Revision ID: 9f0d_migrate_base64_images
Revises: 9f0c_migrate_model_images
Create Date: 2025-11-07 16:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String, Text, JSON, BigInteger, Integer

import json
import uuid
import time
import base64
import hashlib
import mimetypes
from pathlib import Path


revision = '9f0d_migrate_base64_images'
down_revision = '9f0c_migrate_model_images'
branch_labels = None
depends_on = None


def is_data_url(url: str) -> bool:
    """Check if a URL is a data URL (base64 encoded)."""
    return isinstance(url, str) and url.startswith('data:') and ';base64,' in url


def is_asset_path(url: str) -> bool:
    """Check if a URL is an asset path (like /user.png, /favicon.png, etc.)."""
    if not isinstance(url, str):
        return False
    # Asset paths typically start with / and don't contain data: or http:// or https://
    return url.startswith('/') and not url.startswith('//') and 'data:' not in url and 'http' not in url.lower()


def decode_data_url(data_url: str):
    """Decode a data URL into raw bytes and MIME type."""
    header, b64 = data_url.split(',', 1)
    mime = header.split(';')[0].split(':', 1)[1] if ':' in header else 'image/png'
    raw = base64.b64decode(b64)
    return raw, mime


def calculate_sha256_bytes(data: bytes) -> str:
    """Calculate SHA-256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


def migrate_image_to_file(conn, file_table, data_url: str, user_id: str, uploads_dir: Path, hash_to_file_id: dict, file_type: str = "image"):
    """
    Migrate a base64 image to filesystem and return the new URL.
    Returns (new_url, file_id) or (None, None) if skipped.
    """
    if not data_url or not is_data_url(data_url):
        return None, None
    
    try:
        # Decode the base64 image
        raw_bytes, mime_type = decode_data_url(data_url)
        
        # Calculate hash for deduplication
        file_hash = calculate_sha256_bytes(raw_bytes)
        
        # Check if we've already created a file for this hash in this migration
        if file_hash in hash_to_file_id:
            file_id = hash_to_file_id[file_hash]
            new_url = f"/api/v1/files/{file_id}/content"
            return new_url, file_id
        
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
            return new_url, file_id
        
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
                user_id=user_id,
                hash=file_hash,
                filename=filename,
                path=str(file_path),
                data={"size": len(raw_bytes)},
                meta={"content_type": mime_type, "size": len(raw_bytes), file_type: True},
                created_at=ts,
                updated_at=ts,
            )
        )
        
        hash_to_file_id[file_hash] = file_id
        new_url = f"/api/v1/files/{file_id}/content"
        return new_url, file_id
        
    except Exception as e:
        print(f"Error migrating image: {e}")
        return None, None


def upgrade() -> None:
    conn = op.get_bind()

    config_table = table(
        'config',
        column('id', Integer),
        column('data', JSON),
    )

    user_table = table(
        'user',
        column('id', String),
        column('profile_image_url', Text),
        column('settings', JSON),
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

    # Directory for storing migrated images
    uploads_dir = Path(__file__).resolve().parents[2] / 'data' / 'uploads' / 'images'
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Track hash -> file_id mapping for deduplication
    hash_to_file_id = {}
    migrated_count = {
        'config_arena_models': 0,
        'user_profile_images': 0,
        'user_background_images': 0,
    }
    skipped_count = {
        'config_arena_models': 0,
        'user_profile_images': 0,
        'user_background_images': 0,
    }

    # ============================================
    # 1. Migrate config table: arena model images
    # ============================================
    config_rows = conn.execute(sa.select(config_table.c.id, config_table.c.data)).fetchall()
    
    for row in config_rows:
        config_id = row.id
        data = row.data if isinstance(row.data, dict) else (json.loads(row.data) if isinstance(row.data, str) else {})
        
        if not data:
            continue
        
        # Navigate to evaluation.arena.models
        arena_models = data.get('evaluation', {}).get('arena', {}).get('models', [])
        if not isinstance(arena_models, list):
            continue
        
        updated = False
        for model in arena_models:
            if not isinstance(model, dict):
                continue
            
            meta = model.get('meta', {})
            if not isinstance(meta, dict):
                continue
            
            profile_image_url = meta.get('profile_image_url')
            if not profile_image_url or not is_data_url(profile_image_url):
                skipped_count['config_arena_models'] += 1
                continue
            
            # Use a system user_id for config images (or None if needed)
            # Since config is global, we'll use a placeholder
            system_user_id = "system"
            new_url, file_id = migrate_image_to_file(
                conn, file_table, profile_image_url, system_user_id, uploads_dir, hash_to_file_id, "arena_model_image"
            )
            
            if new_url:
                meta['profile_image_url'] = new_url
                model['meta'] = meta
                updated = True
                migrated_count['config_arena_models'] += 1
        
        if updated:
            # Update the config data
            conn.execute(
                sa.update(config_table)
                .where(config_table.c.id == config_id)
                .values(data=data)
            )

    # ============================================
    # 2. Migrate user table: profile_image_url
    # ============================================
    user_rows = conn.execute(
        sa.select(user_table.c.id, user_table.c.profile_image_url)
    ).fetchall()
    
    for row in user_rows:
        user_id = row.id
        profile_image_url = row.profile_image_url
        
        if not profile_image_url:
            continue
        
        # Skip asset paths like /user.png
        if is_asset_path(profile_image_url):
            skipped_count['user_profile_images'] += 1
            continue
        
        if not is_data_url(profile_image_url):
            skipped_count['user_profile_images'] += 1
            continue
        
        new_url, file_id = migrate_image_to_file(
            conn, file_table, profile_image_url, user_id, uploads_dir, hash_to_file_id, "user_profile_image"
        )
        
        if new_url:
            conn.execute(
                sa.update(user_table)
                .where(user_table.c.id == user_id)
                .values(profile_image_url=new_url)
            )
            migrated_count['user_profile_images'] += 1

    # ============================================
    # 3. Migrate user table: settings.ui.backgroundImageUrl
    # ============================================
    user_settings_rows = conn.execute(
        sa.select(user_table.c.id, user_table.c.settings)
    ).fetchall()
    
    for row in user_settings_rows:
        user_id = row.id
        settings = row.settings if isinstance(row.settings, dict) else (json.loads(row.settings) if isinstance(row.settings, str) else {})
        
        if not settings or not isinstance(settings, dict):
            continue
        
        # Check nested structure: settings.ui.backgroundImageUrl
        ui = settings.get('ui', {})
        if not isinstance(ui, dict):
            skipped_count['user_background_images'] += 1
            continue
        
        background_image_url = ui.get('backgroundImageUrl')
        if not background_image_url or not is_data_url(background_image_url):
            skipped_count['user_background_images'] += 1
            continue
        
        new_url, file_id = migrate_image_to_file(
            conn, file_table, background_image_url, user_id, uploads_dir, hash_to_file_id, "user_background_image"
        )
        
        if new_url:
            ui['backgroundImageUrl'] = new_url
            settings['ui'] = ui
            conn.execute(
                sa.update(user_table)
                .where(user_table.c.id == user_id)
                .values(settings=settings)
            )
            migrated_count['user_background_images'] += 1
    
    print(f"Migration complete:")
    print(f"  Config arena models: {migrated_count['config_arena_models']} migrated, {skipped_count['config_arena_models']} skipped")
    print(f"  User profile images: {migrated_count['user_profile_images']} migrated, {skipped_count['user_profile_images']} skipped")
    print(f"  User background images: {migrated_count['user_background_images']} migrated, {skipped_count['user_background_images']} skipped")


def downgrade() -> None:
    # Note: Downgrade would require storing the original base64 data, which we don't have
    # So we'll just leave the migrated URLs in place
    # If needed, we could restore from a backup or re-encode the files, but that's complex
    pass

