"""
Utility functions for handling model profile images with hash-based deduplication.
Converts base64-encoded images to filesystem storage.
"""
import base64
import hashlib
import logging
import mimetypes
from pathlib import Path
from typing import Optional, Tuple

from fastapi import Request
from open_webui.config import UPLOAD_DIR
from open_webui.models.files import Files, FileForm

log = logging.getLogger(__name__)

# Directory for storing model images
MODEL_IMAGES_DIR = UPLOAD_DIR / "model_images"
MODEL_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def is_data_url(url: str) -> bool:
    """Check if a URL is a data URL (base64 encoded)."""
    return isinstance(url, str) and url.startswith("data:") and ";base64," in url


def decode_data_url(data_url: str) -> Tuple[bytes, str]:
    """Decode a data URL into raw bytes and MIME type."""
    header, b64 = data_url.split(",", 1)
    mime = header.split(";")[0].split(":", 1)[1] if ":" in header else "image/png"
    raw = base64.b64decode(b64)
    return raw, mime


def calculate_sha256_bytes(data: bytes) -> str:
    """Calculate SHA-256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


def convert_file_url_to_absolute(request: Request, url: str) -> str:
    """
    Convert a relative file URL to an absolute URL using the request's base URL.
    If the URL is already absolute or is a static file path, return as-is.
    """
    if not url or url.startswith("http://") or url.startswith("https://") or url.startswith("/static/"):
        return url
    
    if url.startswith("/api/v1/files/"):
        # Extract file ID from URL like /api/v1/files/{id}/content
        import re
        match = re.search(r"/files/([A-Za-z0-9\-]+)", url)
        if match:
            file_id = match.group(1)
            # Convert relative path to absolute URL using base_url to preserve port
            base_url = str(request.base_url).rstrip('/')
            return f"{base_url}/api/v1/files/{file_id}/content"
    
    return url


def get_or_create_model_image_file(
    request: Request, user_id: str, image_data_url: str
) -> Optional[str]:
    """
    Convert a base64 data URL to a filesystem file with hash-based deduplication.
    
    Args:
        request: FastAPI request object (for generating file URLs)
        user_id: User ID for the file record
        image_data_url: Base64 data URL (data:image/png;base64,...) or existing file URL
        
    Returns:
        File URL (e.g., /api/v1/files/{id}/content) or the original URL if not a data URL
    """
    # If it's not a data URL, return as-is (might be /static/favicon.png or existing file URL)
    if not is_data_url(image_data_url):
        return image_data_url

    try:
        # Decode the base64 image
        raw_bytes, mime_type = decode_data_url(image_data_url)
        
        # Calculate hash for deduplication
        file_hash = calculate_sha256_bytes(raw_bytes)
        
        # Check if a file with this hash already exists
        from open_webui.internal.db import get_db
        from open_webui.models.files import File
        
        with get_db() as db:
            # Query for existing file with same hash and content type
            existing_files = db.query(File).filter(File.hash == file_hash).all()
            
            # Check if any existing file has matching content type
            for existing_file in existing_files:
                if existing_file.meta and existing_file.meta.get("content_type") == mime_type:
                    # File already exists, return relative URL (will be converted to absolute in endpoint)
                    log.debug(f"Reusing existing model image file with hash {file_hash}")
                    return f"/api/v1/files/{existing_file.id}/content"
        
        # File doesn't exist, create it
        # Use hash-based filename for easy deduplication
        ext = mimetypes.guess_extension(mime_type) or ".bin"
        filename = f"{file_hash}{ext}"
        file_path = MODEL_IMAGES_DIR / filename
        
        # Write to filesystem
        with open(file_path, "wb") as f:
            f.write(raw_bytes)
        
        # Create file record in database
        import uuid
        file_id = str(uuid.uuid4())
        
        file_form = FileForm(
            id=file_id,
            hash=file_hash,
            filename=filename,
            path=str(file_path),
            data={"size": len(raw_bytes)},
            meta={"content_type": mime_type, "size": len(raw_bytes), "model_image": True},
        )
        
        file_model = Files.insert_new_file(user_id, file_form)
        
        if file_model:
            log.debug(f"Created new model image file with hash {file_hash}")
            # Return relative URL (will be converted to absolute in endpoint)
            return f"/api/v1/files/{file_model.id}/content"
        else:
            log.error(f"Failed to create file record for model image with hash {file_hash}")
            return image_data_url  # Fallback to original
            
    except Exception as e:
        log.exception(f"Error processing model image: {e}")
        return image_data_url  # Fallback to original on error

