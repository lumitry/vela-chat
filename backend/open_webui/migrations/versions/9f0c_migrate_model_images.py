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
import os
import uuid
import time
import base64
import hashlib
import mimetypes
from pathlib import Path

# Import DATA_DIR from runtime to ensure consistency (especially in Docker)
# This ensures we use the same path resolution as the runtime code
try:
    from open_webui.env import DATA_DIR as RUNTIME_DATA_DIR
except ImportError:
    # Fallback if import fails (shouldn't happen in normal operation)
    RUNTIME_DATA_DIR = None


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
    # Strip whitespace from base64 string to ensure consistent hashing
    # Base64 strings may have whitespace (spaces, newlines) that need to be removed
    b64_clean = ''.join(b64.split())
    raw = base64.b64decode(b64_clean)
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
    # Priority order:
    # 1. DATA_DIR environment variable (explicit override - highest priority)
    # 2. Standard Docker volume mount path (/app/backend/data)
    # 3. Runtime DATA_DIR (from open_webui.env)
    # 4. Calculated from migration file location (last resort)
    # This ensures we use the correct path that matches volume mounts in Docker
    data_dir = None
    data_dir_source = None
    
    # 1. Check environment variable first (explicit override)
    env_data_dir = os.getenv('DATA_DIR')
    if env_data_dir:
        data_dir = Path(env_data_dir).resolve()
        data_dir_source = "environment variable"
    else:
        # 2. Check standard Docker volume mount location
        # This is where volumes are typically mounted: /app/backend/data
        docker_data_dir = Path('/app/backend/data')
        if docker_data_dir.exists() and docker_data_dir.is_dir():
            # Verify it's writable by checking parent
            try:
                test_file = docker_data_dir / '.migration_test_write'
                test_file.touch()
                test_file.unlink()
                data_dir = docker_data_dir
                data_dir_source = "Docker volume mount path"
            except Exception:
                pass  # Not writable, try next option
    
    # 3. Use runtime DATA_DIR if available and no better option found
    if data_dir is None and RUNTIME_DATA_DIR is not None:
        runtime_path = Path(RUNTIME_DATA_DIR).resolve()
        # Only use runtime path if it's not the problematic open_webui/data subdirectory
        # (which happens when FROM_INIT_PY is True)
        if 'open_webui/data' not in str(runtime_path):
            data_dir = runtime_path
            data_dir_source = "runtime DATA_DIR"
        else:
            # Runtime path is wrong, try to fix it
            # If runtime says /app/backend/open_webui/data, try /app/backend/data instead
            if '/app/backend/open_webui/data' in str(runtime_path):
                corrected_path = Path('/app/backend/data')
                if corrected_path.exists():
                    data_dir = corrected_path
                    data_dir_source = "corrected from runtime path"
    
    # 4. Last resort: calculate from migration file location
    if data_dir is None:
        data_dir = Path(__file__).resolve().parents[2] / 'data'
        data_dir_source = "calculated from file location"
    
    print(f"Migration: Using DATA_DIR from {data_dir_source}: {data_dir}")
    
    uploads_dir = data_dir / 'uploads' / 'model_images'
    uploads_dir.mkdir(parents=True, exist_ok=True)
    
    # Log the actual paths being used
    print(f"Migration: DATA_DIR = {data_dir}")
    print(f"Migration: uploads_dir = {uploads_dir}")
    print(f"Migration: uploads_dir absolute = {uploads_dir.resolve()}")
    print(f"Migration: uploads_dir exists = {uploads_dir.exists()}")
    print(f"Migration: uploads_dir is_dir = {uploads_dir.is_dir()}")
    
    # Verify the directory is writable
    test_file = uploads_dir / '.migration_test'
    try:
        test_file.touch()
        test_content = b"test"
        test_file.write_bytes(test_content)
        read_back = test_file.read_bytes()
        if read_back != test_content:
            raise Exception(f"Test file content mismatch")
        test_file.unlink()
        print(f"Migration: Verified uploads directory is writable: {uploads_dir}")
    except Exception as e:
        print(f"ERROR: Cannot write to uploads directory {uploads_dir}: {e}")
        import traceback
        traceback.print_exc()
        raise

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
            # Normalize the data URL string - ensure it's a clean string
            # JSON parsing might return different types or have encoding issues
            if not isinstance(profile_image_url, str):
                profile_image_url = str(profile_image_url)
            
            # Decode the base64 image
            raw_bytes, mime_type = decode_data_url(profile_image_url)
            
            # Calculate hash for deduplication
            file_hash = calculate_sha256_bytes(raw_bytes)
            
            # Debug: Log first few characters of hash and data URL for troubleshooting
            if migrated_count < 5:  # Only log first few to avoid spam
                print(f"Model {model_id}: hash={file_hash[:8]}, data_url_len={len(profile_image_url)}, data_url_preview={profile_image_url[:100]}...")
            
            # Initialize new_url - will be set in one of the branches below
            new_url = None
            
            # Check if we've already created a file for this hash in this migration
            if file_hash in hash_to_file_id:
                file_id = hash_to_file_id[file_hash]
                new_url = f"/api/v1/files/{file_id}/content"
                if migrated_count < 5:
                    print(f"  -> Reusing file from hash_to_file_id cache: {file_id}")
            else:
                # Check if a file with this hash already exists in the database
                # IMPORTANT: We need to flush/commit any pending inserts to make them visible
                # But Alembic handles transactions, so this should work within the same transaction
                existing_files = conn.execute(
                    sa.select(file_table.c.id, file_table.c.meta, file_table.c.path)
                    .where(file_table.c.hash == file_hash)
                ).fetchall()
                
                if migrated_count < 5 and existing_files:
                    print(f"  -> Found {len(existing_files)} existing file(s) with hash {file_hash[:8]}")
                
                # Check if any existing file has matching content type AND actual content
                # We verify the file content matches because hash mismatches can occur due to
                # encoding differences, whitespace, or other issues
                existing_file_id = None
                for existing_file in existing_files:
                    existing_meta = existing_file.meta if isinstance(existing_file.meta, dict) else (json.loads(existing_file.meta) if isinstance(existing_file.meta, str) else {})
                    if existing_meta and existing_meta.get('content_type') == mime_type:
                        # Verify the file actually exists and matches
                        existing_path = existing_file.path
                        if existing_path and Path(existing_path).exists():
                            try:
                                with open(existing_path, 'rb') as f:
                                    existing_bytes = f.read()
                                # Compare actual file content, not just hash
                                # This catches cases where hashes differ but content is the same
                                if existing_bytes == raw_bytes:
                                    existing_file_id = existing_file.id
                                    if migrated_count < 5:
                                        print(f"  -> Found matching file by content comparison (hash mismatch!): {existing_file_id}")
                                    break
                            except Exception as e:
                                # File read failed, skip this one
                                if migrated_count < 5:
                                    print(f"  -> Error reading existing file {existing_path}: {e}")
                                continue
                        else:
                            # File doesn't exist on disk, skip
                            continue
                
                if existing_file_id:
                    # We already verified the file exists and matches in the loop above
                    # Reuse existing file
                    file_id = existing_file_id
                    hash_to_file_id[file_hash] = file_id
                    new_url = f"/api/v1/files/{file_id}/content"
                    if migrated_count < 5:
                        print(f"  -> Reusing existing file: {file_id}")
                
                if not existing_file_id:
                    # Hash-based lookup didn't find a match, but the hash might be wrong
                    # Try a fallback: check files with same content type and size
                    # This catches cases where the same image has different hashes
                    if migrated_count < 5:
                        print(f"  -> No file found with hash {file_hash[:8]}, trying fallback search by content type and size")
                    
                    fallback_files = conn.execute(
                        sa.select(file_table.c.id, file_table.c.path, file_table.c.meta)
                        .where(
                            sa.and_(
                                file_table.c.meta.isnot(None),
                                # We can't easily filter by content_type in SQL, so we'll check in Python
                            )
                        )
                    ).fetchall()
                    
                    if migrated_count < 5:
                        print(f"  -> Fallback: Checking {len(fallback_files)} files for matches")
                    
                    # Check files with matching content type and size
                    fallback_checked = 0
                    for fallback_file in fallback_files:
                        fallback_meta = fallback_file.meta if isinstance(fallback_file.meta, dict) else (json.loads(fallback_file.meta) if isinstance(fallback_file.meta, str) else {})
                        if fallback_meta and fallback_meta.get('content_type') == mime_type:
                            fallback_size = fallback_meta.get('size') or (fallback_meta.get('data', {}).get('size') if isinstance(fallback_meta.get('data'), dict) else None)
                            if fallback_size == len(raw_bytes):
                                fallback_checked += 1
                                # Size matches, check actual content
                                fallback_path = fallback_file.path
                                if migrated_count < 5 and fallback_checked <= 3:
                                    print(f"  -> Fallback: Checking file {fallback_file.id}, path={fallback_path}, exists={Path(fallback_path).exists() if fallback_path else False}")
                                
                                if fallback_path and Path(fallback_path).exists():
                                    try:
                                        with open(fallback_path, 'rb') as f:
                                            fallback_bytes = f.read()
                                        if fallback_bytes == raw_bytes:
                                            existing_file_id = fallback_file.id
                                            if migrated_count < 5:
                                                print(f"  -> Found duplicate by content comparison (different hash!): {existing_file_id}")
                                            break
                                    except Exception as e:
                                        if migrated_count < 5:
                                            print(f"  -> Fallback: Error reading {fallback_path}: {e}")
                                        continue
                                elif fallback_path:
                                    # File path exists in DB but file doesn't exist on disk - skip it
                                    if migrated_count < 5:
                                        print(f"  -> Fallback: File {fallback_file.id} path {fallback_path} does not exist on disk, skipping")
                    
                    if migrated_count < 5:
                        print(f"  -> Fallback: Checked {fallback_checked} files with matching content_type and size")
                    
                    if existing_file_id:
                        # Found a match via fallback
                        file_id = existing_file_id
                        hash_to_file_id[file_hash] = file_id
                        new_url = f"/api/v1/files/{file_id}/content"
                        if migrated_count < 5:
                            print(f"  -> Reusing file found via fallback: {file_id}")
                    else:
                        if migrated_count < 5:
                            print(f"  -> Fallback: No matching file found, will create new file")
                
                if not existing_file_id:
                    # Create new file
                    ext = mimetypes.guess_extension(mime_type) or '.bin'
                    filename = f"{file_hash}{ext}"
                    file_path = uploads_dir / filename
                    
                    # Store path relative to UPLOAD_DIR for consistency with runtime code
                    # Runtime expects: UPLOAD_DIR / "model_images" / filename
                    # So we store: model_images/filename (relative path)
                    relative_path = f"model_images/{filename}"
                    
                    # Check if file already exists on filesystem (might have been created but DB record missing)
                    if file_path.exists():
                        # File exists but no DB record - verify it matches
                        with open(file_path, 'rb') as f:
                            existing_file_bytes = f.read()
                        if existing_file_bytes == raw_bytes:
                            # File matches, but we still need a DB record
                            # Check if there's a file record with this path (check both absolute and relative)
                            path_file = conn.execute(
                                sa.select(file_table.c.id)
                                .where(
                                    sa.or_(
                                        file_table.c.path == str(file_path),
                                        file_table.c.path == relative_path
                                    )
                                )
                            ).scalar_one_or_none()
                            if path_file:
                                file_id = path_file
                                hash_to_file_id[file_hash] = file_id
                                new_url = f"/api/v1/files/{file_id}/content"
                            else:
                                # Create DB record for existing file
                                file_id = str(uuid.uuid4())
                                ts = int(time.time())
                                conn.execute(
                                    sa.insert(file_table).values(
                                        id=file_id,
                                        user_id=user_id,
                                        hash=file_hash,
                                        filename=filename,
                                        path=str(file_path),  # Store absolute path (matches runtime)
                                        data={"size": len(raw_bytes)},
                                        meta={"content_type": mime_type, "size": len(raw_bytes), "model_image": True},
                                        created_at=ts,
                                        updated_at=ts,
                                    )
                                )
                                hash_to_file_id[file_hash] = file_id
                                new_url = f"/api/v1/files/{file_id}/content"
                        else:
                            # File exists but content doesn't match - this shouldn't happen with hash-based names
                            # Overwrite it (hash collision is extremely unlikely)
                            with open(file_path, 'wb') as f:
                                written = f.write(raw_bytes)
                                if written != len(raw_bytes):
                                    raise Exception(f"Only wrote {written} of {len(raw_bytes)} bytes")
                                f.flush()
                                os.fsync(f.fileno())  # Force write to disk
                            # Verify file was written
                            if not file_path.exists() or file_path.stat().st_size != len(raw_bytes):
                                raise Exception(f"Failed to write file {file_path}")
                            file_id = str(uuid.uuid4())
                            ts = int(time.time())
                            conn.execute(
                                sa.insert(file_table).values(
                                    id=file_id,
                                    user_id=user_id,
                                    hash=file_hash,
                                    filename=filename,
                                    path=str(file_path),  # Store absolute path
                                    data={"size": len(raw_bytes)},
                                    meta={"content_type": mime_type, "size": len(raw_bytes), "model_image": True},
                                    created_at=ts,
                                    updated_at=ts,
                                )
                            )
                            hash_to_file_id[file_hash] = file_id
                            new_url = f"/api/v1/files/{file_id}/content"
                    else:
                        # File doesn't exist - create it
                        # CRITICAL: Write file FIRST, then create DB record
                        # This ensures if file write fails, we don't create orphaned DB records
                        try:
                            # Ensure directory exists
                            file_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            # Log file write attempt
                            if migrated_count < 5:
                                print(f"  -> Attempting to write file: {file_path}")
                                print(f"     Absolute path: {file_path.resolve()}")
                                print(f"     Parent exists: {file_path.parent.exists()}")
                                print(f"     Parent is_dir: {file_path.parent.is_dir()}")
                                print(f"     File size: {len(raw_bytes)} bytes")
                            
                            # Write file with explicit error handling
                            with open(file_path, 'wb') as f:
                                written = f.write(raw_bytes)
                                f.flush()
                                os.fsync(f.fileno())  # Force write to disk
                            
                            if written != len(raw_bytes):
                                raise Exception(f"Only wrote {written} of {len(raw_bytes)} bytes")
                            
                            # Verify file was actually written and is readable
                            if not file_path.exists():
                                raise Exception(f"File {file_path} was not created after write")
                            
                            file_stat = file_path.stat()
                            if file_stat.st_size != len(raw_bytes):
                                raise Exception(f"File {file_path} size mismatch: expected {len(raw_bytes)}, got {file_stat.st_size}")
                            
                            # Verify we can read it back
                            with open(file_path, 'rb') as f:
                                read_back = f.read()
                            if read_back != raw_bytes:
                                raise Exception(f"File {file_path} content mismatch - file write may be corrupted")
                            
                            if migrated_count < 5:
                                print(f"  -> Successfully created and verified file: {file_path} (size: {len(raw_bytes)} bytes)")
                                print(f"     File exists check: {file_path.exists()}")
                                print(f"     File readable: {file_path.is_file()}")
                        except Exception as e:
                            error_msg = f"ERROR: Failed to write file {file_path}: {e}"
                            print(error_msg)
                            import traceback
                            traceback.print_exc()
                            # Don't create DB record if file write failed
                            raise Exception(error_msg) from e
                        
                        # Only create DB record AFTER file is successfully written and verified
                        file_id = str(uuid.uuid4())
                        ts = int(time.time())
                        try:
                            conn.execute(
                                sa.insert(file_table).values(
                                    id=file_id,
                                    user_id=user_id,  # Use model owner's user_id
                                    hash=file_hash,
                                    filename=filename,
                                    path=str(file_path),  # Store absolute path for now (matches runtime behavior)
                                    data={"size": len(raw_bytes)},
                                    meta={"content_type": mime_type, "size": len(raw_bytes), "model_image": True},
                                    created_at=ts,
                                    updated_at=ts,
                                )
                            )
                            
                            # Verify DB record was created
                            verify_file = conn.execute(
                                sa.select(file_table.c.id)
                                .where(file_table.c.id == file_id)
                            ).scalar_one_or_none()
                            if not verify_file:
                                raise Exception(f"DB record for {file_id} was not created")
                            
                            hash_to_file_id[file_hash] = file_id
                            new_url = f"/api/v1/files/{file_id}/content"
                            
                            if migrated_count < 5:
                                print(f"  -> Created file record: {file_id} with path: {file_path}")
                        except Exception as e:
                            # If DB insert fails, try to clean up the file we just created
                            try:
                                if file_path.exists():
                                    file_path.unlink()
                                    print(f"  -> Cleaned up orphaned file: {file_path}")
                            except:
                                pass
                            raise Exception(f"Failed to create DB record for file {file_path}: {e}") from e
            
            # Update model meta with new URL
            # new_url should always be set by this point, but check just in case
            if new_url is None:
                print(f"ERROR: new_url was not set for model {model_id}, skipping update")
                continue
                
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
    
    print(f"Migration complete: {migrated_count} models migrated, {skipped_count} skipped")


def downgrade() -> None:
    # Note: Downgrade would require storing the original base64 data, which we don't have
    # So we'll just leave the migrated URLs in place
    # If needed, we could restore from a backup or re-encode the files, but that's complex
    pass

