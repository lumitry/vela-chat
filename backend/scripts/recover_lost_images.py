#!/usr/bin/env python3
"""
Recovery script for lost in-chat images after migration to normalized storage.

This script:
1. Reads a backup database dump (PostgreSQL custom format) or connects to a restored backup database
2. Extracts base64 images from chat JSON blobs in the backup
3. Matches them to the current database state (chat_message_attachment records)
4. Recreates the files in the correct location (persisted Docker volume)
5. Updates the file records in the current database

Usage:
    # Option 1: Restore backup to temporary database first
    PGPASSWORD="backup_password" pg_restore -d backup_db -F c backup.dump
    python scripts/recover_lost_images.py --backup-db-url "postgresql://user:pass@host:5432/backup_db"
    
    # Option 2: Use current database URL from environment
    DATABASE_URL="postgresql://user:pass@host:5432/current_db" python scripts/recover_lost_images.py --backup-db-url "postgresql://user:pass@host:5432/backup_db"
    
    # Option 3: Run inside Docker container
    docker exec -it open-webui python /app/backend/scripts/recover_lost_images.py --backup-db-url "postgresql://user:pass@host:5432/backup_db"
"""

import os
import sys
import json
import base64
import hashlib
import mimetypes
import argparse
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# Add backend to path so we can import open_webui modules
# Script is in backend/scripts/ (in container: /app/backend/scripts/)
script_path = Path(__file__).resolve()

# Try common locations
possible_backends = [
    script_path.parent,  # backend/scripts/ -> backend/
    script_path.parent.parent / "backend",  # scripts/ -> backend/ (if moved)
    Path("/app/backend"),  # Docker container location
]

for backend_dir in possible_backends:
    if backend_dir.exists() and (backend_dir / "open_webui").exists():
        sys.path.insert(0, str(backend_dir))
        break
else:
    # Fallback: try to import from current directory
    # This will work if running from backend/ directory
    pass

from sqlalchemy import create_engine, text, MetaData, Table, select
from sqlalchemy.orm import sessionmaker


def calculate_sha256_bytes(data: bytes) -> str:
    """Calculate SHA-256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


def is_data_url(url: str) -> bool:
    """Check if a URL is a data URL (base64 encoded)."""
    return isinstance(url, str) and url.startswith('data:') and ';base64,' in url


def decode_data_url(data_url: str) -> Tuple[bytes, str]:
    """Decode a data URL into raw bytes and MIME type."""
    header, b64 = data_url.split(',', 1)
    mime = header.split(';')[0].split(':', 1)[1] if ':' in header else 'image/png'
    # Strip whitespace from base64 string
    b64_clean = ''.join(b64.split())
    raw = base64.b64decode(b64_clean)
    return raw, mime


def get_data_dir() -> Path:
    """Get the DATA_DIR path using the same logic as migrations."""
    # Priority order:
    # 1. DATA_DIR environment variable (explicit override - highest priority)
    # 2. Standard Docker volume mount path (/app/backend/data)
    # 3. Calculated from script location (last resort)
    
    env_data_dir = os.getenv('DATA_DIR')
    if env_data_dir:
        return Path(env_data_dir).resolve()
    
    # Check standard Docker volume mount location
    docker_data_dir = Path('/app/backend/data')
    if docker_data_dir.exists() and docker_data_dir.is_dir():
        try:
            test_file = docker_data_dir / '.recovery_test_write'
            test_file.touch()
            test_file.unlink()
            return docker_data_dir
        except Exception:
            pass
    
    # Last resort: calculate from script location
    return Path(__file__).resolve().parents[2] / 'backend' / 'data'


def extract_images_from_chat_json(chat_json: dict) -> List[Dict]:
    """
    Extract all base64 images from a chat JSON blob.
    Returns list of dicts with: message_id, file_url (base64), file_type, and other metadata.
    """
    images = []
    
    if not chat_json or not isinstance(chat_json, dict):
        return images
    
    history = chat_json.get('history', {})
    if not isinstance(history, dict):
        return images
    
    messages = history.get('messages', {})
    if not isinstance(messages, dict):
        return images
    
    for mid, msg in messages.items():
        message_id = msg.get('id') or mid
        files = msg.get('files', [])
        
        for f in files:
            if not isinstance(f, dict):
                continue
            
            ftype = f.get('type') or 'file'
            furl = f.get('url')
            
            if ftype == 'image' and furl and is_data_url(furl):
                images.append({
                    'message_id': message_id,
                    'file_url': furl,
                    'file_type': ftype,
                    'original_file': f,
                })
    
    return images


def find_matching_attachment(current_db, chat_id: str, message_id: str, image_hash: str) -> Optional[Dict]:
    """
    Find a chat_message_attachment record that might match this image.
    We match by:
    1. chat_id and message_id (if available)
    2. file_id that points to a file with a missing path or broken URL
    """
    # Try to find attachment by message_id
    query = text("""
        SELECT cma.id, cma.message_id, cma.file_id, cma.url, cma.mime_type, cma.size_bytes
        FROM chat_message_attachment cma
        JOIN chat_message cm ON cm.id = cma.message_id
        WHERE cm.chat_id = :chat_id
          AND cma.message_id = :message_id
          AND cma.type = 'image'
        LIMIT 1
    """)
    
    result = current_db.execute(query, {'chat_id': chat_id, 'message_id': message_id})
    row = result.fetchone()
    
    if row:
        return {
            'id': row[0],
            'message_id': row[1],
            'file_id': row[2],
            'url': row[3],
            'mime_type': row[4],
            'size_bytes': row[5],
        }
    
    return None


def check_file_exists(current_db, file_id: str) -> Optional[Dict]:
    """Check if a file record exists and return its details."""
    query = text("""
        SELECT id, user_id, hash, filename, path, data, meta
        FROM file
        WHERE id = :file_id
    """)
    
    result = current_db.execute(query, {'file_id': file_id})
    row = result.fetchone()
    
    if row:
        return {
            'id': row[0],
            'user_id': row[1],
            'hash': row[2],
            'filename': row[3],
            'path': row[4],
            'data': row[5],
            'meta': row[6],
        }
    
    return None


def create_or_update_file(current_db, user_id: str, raw_bytes: bytes, mime_type: str, 
                          file_hash: str, existing_file_id: Optional[str] = None) -> str:
    """
    Create a new file record or update an existing one.
    Returns the file_id.
    """
    data_dir = get_data_dir()
    uploads_dir = data_dir / 'uploads'
    uploads_dir.mkdir(parents=True, exist_ok=True)
    
    ext = mimetypes.guess_extension(mime_type) or '.bin'
    filename = f"{file_hash}{ext}"
    file_path = uploads_dir / filename
    
    # Write file to filesystem
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'wb') as f:
            written = f.write(raw_bytes)
            f.flush()
            os.fsync(f.fileno())
        
        if written != len(raw_bytes):
            raise Exception(f"Only wrote {written} of {len(raw_bytes)} bytes")
        
        # Verify file was written
        if not file_path.exists() or file_path.stat().st_size != len(raw_bytes):
            raise Exception(f"Failed to write file {file_path}")
    except Exception as e:
        raise Exception(f"Error writing file {file_path}: {e}") from e
    
    if existing_file_id:
        # Update existing file record
        query = text("""
            UPDATE file
            SET path = :path,
                hash = :hash,
                filename = :filename,
                data = :data,
                meta = :meta,
                updated_at = :updated_at
            WHERE id = :file_id
        """)
        
        current_db.execute(query, {
            'file_id': existing_file_id,
            'path': str(file_path),
            'hash': file_hash,
            'filename': filename,
            'data': json.dumps({"size": len(raw_bytes)}),
            'meta': json.dumps({"content_type": mime_type, "size": len(raw_bytes), "image": True}),
            'updated_at': int(time.time()),
        })
        current_db.commit()
        return existing_file_id
    else:
        # Create new file record
        file_id = str(uuid.uuid4())
        ts = int(time.time())
        
        query = text("""
            INSERT INTO file (id, user_id, hash, filename, path, data, meta, created_at, updated_at)
            VALUES (:id, :user_id, :hash, :filename, :path, :data, :meta, :created_at, :updated_at)
        """)
        
        current_db.execute(query, {
            'id': file_id,
            'user_id': user_id,
            'hash': file_hash,
            'filename': filename,
            'path': str(file_path),
            'data': json.dumps({"size": len(raw_bytes)}),
            'meta': json.dumps({"content_type": mime_type, "size": len(raw_bytes), "image": True}),
            'created_at': ts,
            'updated_at': ts,
        })
        current_db.commit()
        return file_id


def recover_images(backup_db_url: str, current_db_url: Optional[str] = None, dry_run: bool = False):
    """
    Main recovery function.
    
    Args:
        backup_db_url: PostgreSQL connection URL for the backup database
        current_db_url: PostgreSQL connection URL for the current database (defaults to DATABASE_URL env var)
        dry_run: If True, don't actually write files or update database
    """
    if current_db_url is None:
        current_db_url = os.environ.get('DATABASE_URL')
        if not current_db_url:
            raise ValueError("DATABASE_URL environment variable not set and --current-db-url not provided")
    
    # Replace postgres:// with postgresql:// if needed
    if "postgres://" in backup_db_url:
        backup_db_url = backup_db_url.replace("postgres://", "postgresql://")
    if "postgres://" in current_db_url:
        current_db_url = current_db_url.replace("postgres://", "postgresql://")
    
    print(f"Connecting to backup database...")
    backup_engine = create_engine(backup_db_url)
    backup_db = backup_engine.connect()
    
    print(f"Connecting to current database...")
    current_engine = create_engine(current_db_url)
    current_db = current_engine.connect()
    
    try:
        # Get all chats from backup database
        print("Fetching chats from backup database...")
        backup_query = text("SELECT id, user_id, chat FROM chat WHERE chat IS NOT NULL")
        backup_chats = backup_db.execute(backup_query).fetchall()
        
        print(f"Found {len(backup_chats)} chats in backup database")
        
        total_images_found = 0
        total_images_recovered = 0
        total_images_skipped = 0
        total_errors = 0
        
        data_dir = get_data_dir()
        print(f"Using DATA_DIR: {data_dir}")
        print(f"Files will be written to: {data_dir / 'uploads'}")
        
        if dry_run:
            print("\n*** DRY RUN MODE - No files will be written, no database updates will be made ***\n")
        
        for chat_row in backup_chats:
            chat_id = chat_row[0]
            user_id = chat_row[1]
            chat_json_raw = chat_row[2]
            
            # Parse chat JSON
            if isinstance(chat_json_raw, str):
                try:
                    chat_json = json.loads(chat_json_raw)
                except json.JSONDecodeError:
                    continue
            else:
                chat_json = chat_json_raw
            
            if not chat_json:
                continue
            
            # Extract images from this chat
            images = extract_images_from_chat_json(chat_json)
            
            if not images:
                continue
            
            total_images_found += len(images)
            print(f"\nChat {chat_id}: Found {len(images)} base64 image(s)")
            
            for img in images:
                try:
                    message_id = img['message_id']
                    data_url = img['file_url']
                    
                    # Decode the base64 image
                    raw_bytes, mime_type = decode_data_url(data_url)
                    file_hash = calculate_sha256_bytes(raw_bytes)
                    
                    print(f"  Image in message {message_id}: {len(raw_bytes)} bytes, {mime_type}, hash={file_hash[:8]}...")
                    
                    # Try to find matching attachment in current database
                    attachment = find_matching_attachment(current_db, chat_id, message_id, file_hash)
                    
                    if not attachment:
                        print(f"    ⚠️  No matching attachment found - skipping")
                        total_images_skipped += 1
                        continue
                    
                    print(f"    ✓ Found matching attachment: {attachment['id']}")
                    
                    # Check if file record exists
                    file_id = attachment.get('file_id')
                    if not file_id:
                        print(f"    ⚠️  Attachment has no file_id - skipping")
                        total_images_skipped += 1
                        continue
                    
                    file_record = check_file_exists(current_db, file_id)
                    if not file_record:
                        print(f"    ⚠️  File record {file_id} not found - will create new file record")
                        # We'll create a new file record below
                    else:
                        # Check if file exists on filesystem
                        file_path = Path(file_record['path'])
                        if file_path.exists():
                            # Verify it matches
                            with open(file_path, 'rb') as f:
                                existing_bytes = f.read()
                            if existing_bytes == raw_bytes:
                                print(f"    ✓ File already exists and matches - no action needed")
                                total_images_skipped += 1
                                continue
                            else:
                                print(f"    ⚠️  File exists but content doesn't match - will update")
                        else:
                            print(f"    ⚠️  File record exists but file missing on disk - will recreate")
                    
                    if dry_run:
                        file_ext = mimetypes.guess_extension(mime_type) or '.bin'
                        file_name = f"{file_hash}{file_ext}"
                        file_location = data_dir / 'uploads' / file_name
                        print(f"    [DRY RUN] Would create/update file {file_id} at {file_location}")
                        total_images_recovered += 1
                    else:F
                        # Create or update file
                        updated_file_id = create_or_update_file(
                            current_db, user_id, raw_bytes, mime_type, file_hash, file_id
                        )
                        print(f"    ✓ Created/updated file {updated_file_id}")
                        total_images_recovered += 1
                
                except Exception as e:
                    print(f"    ✗ Error processing image: {e}")
                    import traceback
                    traceback.print_exc()
                    total_errors += 1
        
        print(f"\n{'='*60}")
        print(f"Recovery Summary:")
        print(f"  Total images found in backup: {total_images_found}")
        print(f"  Images recovered: {total_images_recovered}")
        print(f"  Images skipped: {total_images_skipped}")
        print(f"  Errors: {total_errors}")
        print(f"{'='*60}")
        
        if dry_run:
            print("\nThis was a DRY RUN. Run without --dry-run to actually recover images.")
    
    finally:
        backup_db.close()
        current_db.close()


def main():
    parser = argparse.ArgumentParser(
        description='Recover lost in-chat images from backup database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--backup-db-url',
        required=True,
        help='PostgreSQL connection URL for the backup database (e.g., postgresql://user:pass@host:5432/backup_db)'
    )
    parser.add_argument(
        '--current-db-url',
        help='PostgreSQL connection URL for the current database (defaults to DATABASE_URL env var)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Perform a dry run without writing files or updating database'
    )
    
    args = parser.parse_args()
    
    try:
        recover_images(
            backup_db_url=args.backup_db_url,
            current_db_url=args.current_db_url,
            dry_run=args.dry_run
        )
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

