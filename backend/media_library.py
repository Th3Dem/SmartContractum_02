"""Ownership of uploaded media and profile images (avatar, cover, company logo and cover)."""
import datetime
import json
import sqlite3
from typing import Any, Dict, Optional, Tuple

PROFILE_MEDIA_KINDS = ("avatar", "cover")
COMPANY_MEDIA_KINDS = ("logo", "cover")


def migrate_media_schema(conn: sqlite3.Connection) -> None:
    """Idempotent: upload ownership and the profile image columns of people and companies."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS media_uploads (
            url TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            mime TEXT,
            width INTEGER,
            height INTEGER,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_media_uploads_owner ON media_uploads(owner_id)")
    for table, columns in (("user_profiles", ("cover", "cover_focal")), ("companies", ("cover", "cover_focal"))):
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for column in columns:
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
    conn.commit()


def record_upload(conn: sqlite3.Connection, url: str, owner_id: str, meta: Optional[Dict[str, Any]] = None) -> None:
    """
    Remembers who uploaded a file. Files are content-addressed, so the same bytes uploaded by
    two people share one URL: the first uploader is kept as owner and the second one is added
    as a co-owner row under a suffixed key, which is enough for ownership checks.
    """
    meta = meta or {}
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with conn:
        row = conn.execute("SELECT owner_id FROM media_uploads WHERE url = ?", (url,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO media_uploads (url, owner_id, mime, width, height, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                         (url, owner_id, meta.get("mime"), meta.get("width"), meta.get("height"), now))
        elif row[0] != owner_id:
            conn.execute("INSERT OR IGNORE INTO media_uploads (url, owner_id, mime, width, height, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                         (f"{url}#{owner_id}", owner_id, meta.get("mime"), meta.get("width"), meta.get("height"), now))


def is_upload_owned_by(conn: sqlite3.Connection, url: str, user_id: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM media_uploads WHERE (url = ? AND owner_id = ?) OR url = ?",
        (url, user_id, f"{url}#{user_id}")).fetchone() is not None


def parse_focal(value: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Focal point of a cover as {"x": 0..1, "y": 0..1}: the part kept visible when a wide cover is cut
    on narrow screens. Returns (json_or_None, error).
    """
    if value in (None, ""):
        return None, None
    if not isinstance(value, dict):
        return None, "Точка фокуса передается объектом {x, y}"
    try:
        x = float(value.get("x"))
        y = float(value.get("y"))
    except (TypeError, ValueError):
        return None, "Точка фокуса должна содержать числа x и y"
    if not (0 <= x <= 1 and 0 <= y <= 1):
        return None, "Координаты точки фокуса должны быть от 0 до 1"
    return json.dumps({"x": round(x, 4), "y": round(y, 4)}), None


def focal_dict(raw: Optional[str]) -> Optional[Dict[str, float]]:
    try:
        value = json.loads(raw) if raw else None
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None
