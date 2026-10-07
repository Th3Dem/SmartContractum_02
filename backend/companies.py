"""Company profiles: schema additions, field validation and ownership rules."""
import json
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

# What a company profile may contain; lengths are enforced on create and update
LIMITS = {"name": 120, "description": 300, "specialization": 120, "website": 300, "about": 8000}
MAX_DIRECTIONS = 12
SUBSCRIPTION_TARGETS = ("company", "topic", "user")


def migrate_company_schema(conn: sqlite3.Connection) -> None:
    """Idempotent: extended description and the company's own outgoing subscriptions."""
    columns = {r[1] for r in conn.execute("PRAGMA table_info(companies)")}
    if "about" not in columns:
        conn.execute("ALTER TABLE companies ADD COLUMN about TEXT")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS company_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT NOT NULL,
            target_type TEXT NOT NULL CHECK (target_type IN ('company', 'topic', 'user')),
            target_id TEXT NOT NULL,
            target_title TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (company_id, target_type, target_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_company_subscriptions_company ON company_subscriptions(company_id)")
    conn.commit()


def normalize_website(value: str) -> Tuple[Optional[str], Optional[str]]:
    """Returns (url, error). Only http and https links are accepted; a bare domain gets https://."""
    value = (value or "").strip()
    if not value:
        return "", None
    # Any explicit scheme other than http(s) is refused; "host:8080" is a port, not a scheme
    scheme = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):(?!\d)", value)
    if scheme and scheme.group(1).lower() not in ("http", "https"):
        return None, "Адрес сайта должен начинаться с http:// или https://"
    if not re.match(r"^https?://", value, re.IGNORECASE):
        value = "https://" + value
    if not re.match(r"^https?://[^\s/$.?#][^\s]*$", value, re.IGNORECASE):
        return None, "Адрес сайта должен начинаться с http:// или https://"
    return value, None


def validate_company_fields(data: Dict[str, Any], partial: bool) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Validates editable company fields. With partial=True only present fields are checked.
    Returns (clean_fields, field_errors). Text is stored as plain text; the client renders it escaped.
    """
    clean: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    required = {"name": "Название компании обязательно",
                "description": "Краткое описание обязательно",
                "specialization": "Специализация обязательна"}
    for field in ("name", "description", "specialization", "about"):
        if partial and field not in data:
            continue
        raw = data.get(field)
        value = raw.strip() if isinstance(raw, str) else ""
        if field in required and not value:
            errors[field] = required[field]
            continue
        if len(value) > LIMITS[field]:
            errors[field] = f"Не длиннее {LIMITS[field]} символов"
            continue
        clean[field] = value
    if not partial or "website" in data:
        url, err = normalize_website(data.get("website") if isinstance(data.get("website"), str) else "")
        if err:
            errors["website"] = err
        elif len(url) > LIMITS["website"]:
            errors["website"] = f"Не длиннее {LIMITS['website']} символов"
        else:
            clean["website"] = url
    if not partial or "directions" in data:
        directions = data.get("directions") or []
        if not isinstance(directions, list) or not all(isinstance(d, str) for d in directions):
            errors["directions"] = "Направления передаются списком строк"
        else:
            cleaned = []
            for d in directions:
                d = d.strip()
                if d and d not in cleaned:
                    cleaned.append(d[:60])
            if len(cleaned) > MAX_DIRECTIONS:
                errors["directions"] = f"Не больше {MAX_DIRECTIONS} направлений"
            else:
                clean["directions"] = cleaned
    return clean, errors


def is_company_owner(conn: sqlite3.Connection, company_id: str, user: Optional[Dict[str, Any]]) -> bool:
    """Only the owner edits the profile; members may publish but not edit (Issue #212)."""
    if not user:
        return False
    row = conn.execute("SELECT owner_id FROM companies WHERE id = ?", (company_id,)).fetchone()
    return bool(row) and row["owner_id"] == user["id"]


def company_material_counts(conn: sqlite3.Connection, company_id: str) -> Dict[str, int]:
    counts = {"publications": 0, "questions": 0}
    for r in conn.execute("""
        SELECT COALESCE(json_extract(publication_settings, '$.materialType'), 'publication') AS mt, COUNT(*) AS cnt
        FROM moderation_submissions
        WHERE status = 'approved' AND json_extract(publication_settings, '$.companyId') = ?
        GROUP BY mt
    """, (company_id,)):
        counts["questions" if r["mt"] == "question" else "publications"] += r["cnt"]
    return counts


def list_company_subscriptions(conn: sqlite3.Connection, company_id: str) -> List[Dict[str, Any]]:
    return [{
        "targetType": r["target_type"],
        "targetId": r["target_id"],
        "title": r["target_title"],
        "createdAt": r["created_at"],
    } for r in conn.execute("""
        SELECT target_type, target_id, target_title, created_at FROM company_subscriptions
        WHERE company_id = ? ORDER BY created_at DESC
    """, (company_id,))]


def parse_directions(raw: Optional[str]) -> List[str]:
    try:
        value = json.loads(raw) if raw else []
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []
