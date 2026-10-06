"""Content-addressed storage of uploaded media files."""
import hashlib
import os
from typing import Optional

from backend import config


def save_media_file(data: bytes, ext: str, media_dir: Optional[str] = None) -> str:
    """
    Saves image data to disk in media_dir/<sha256>.<ext> and returns /media/<sha256>.<ext>.
    """
    target_dir = media_dir or config.MEDIA_DIR
    os.makedirs(target_dir, exist_ok=True)
    clean_ext = ext.lstrip(".").lower()
    if clean_ext == "jpeg":
        clean_ext = "jpg"
    file_hash = hashlib.sha256(data).hexdigest()[:32]
    filename = f"{file_hash}.{clean_ext}"
    filepath = os.path.join(target_dir, filename)
    if not os.path.exists(filepath):
        with open(filepath, "wb") as f:
            f.write(data)
    return f"/media/{filename}"
