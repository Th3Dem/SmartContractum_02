"""Moderation rules: schema migration, claiming, decisions, decision log and author notices."""
import datetime
import json
import sqlite3
import uuid
from typing import Any, Dict, List, Optional, Tuple

from backend.author_delivery import AUTHOR_NOTIFICATION_TYPES, deliver_author_material
from backend.author_delivery import ensure_schema as ensure_author_delivery_schema
from backend.db import can_user_publish_for_company

# Decision -> resulting submission status
DECISIONS = {
    "approve": "approved",
    "revise": "needs_revision",
    "reject": "rejected",
}

# Reasons offered when rejecting; "other" requires a free-text comment
REJECT_REASONS = {
    "spam": "Реклама или спам",
    "off_topic": "Не по теме сообщества",
    "plagiarism": "Плагиат или заимствование без указания источника",
    "rules": "Нарушение правил сообщества",
    "low_quality": "Недостаточное качество материала",
    "other": "Другая причина",
}

MIN_REVISION_COMMENT = 10
MAX_COMMENT = 4000
# A claim older than this is considered abandoned and can be taken by another moderator
CLAIM_TTL_MINUTES = 30

STATUS_LABELS = {
    "pending_moderation": "На модерации",
    "needs_revision": "Нужна доработка",
    "rejected": "Отклонено",
    "approved": "Опубликовано",
    "draft": "Заменено новой версией",
}

# Earlier CHECK lists of user_notifications.type, oldest first; each is migrated to NOTIFICATION_TYPES
_LEGACY_NOTIFICATION_TYPES = (
    ("new_answer", "new_reply", "solution_accepted"),
    ("new_answer", "new_reply", "solution_accepted",
     "moderation_approved", "moderation_revision", "moderation_rejected"),
)
NOTIFICATION_TYPES = _LEGACY_NOTIFICATION_TYPES[-1] + AUTHOR_NOTIFICATION_TYPES


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _rebuild_check(conn: sqlite3.Connection, table: str, old_fragment: str, new_fragment: str) -> bool:
    """
    SQLite cannot alter a CHECK constraint; rebuild the table with the new constraint,
    keeping every column and row. Returns True when a rebuild happened.
    """
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    if not row or new_fragment in row[0]:
        return False
    if old_fragment not in row[0]:
        raise RuntimeError(f"Unexpected schema of {table}; cannot extend its CHECK constraint")
    indexes = [r[0] for r in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL", (table,))]
    new_sql = row[0].replace(old_fragment, new_fragment)
    tmp = f"{table}__old"
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        with conn:
            conn.execute(f"ALTER TABLE {table} RENAME TO {tmp}")
            conn.execute(new_sql)
            cols = ", ".join(r[1] for r in conn.execute(f"PRAGMA table_info({tmp})"))
            conn.execute(f"INSERT INTO {table} ({cols}) SELECT {cols} FROM {tmp}")
            conn.execute(f"DROP TABLE {tmp}")
            for sql in indexes:
                conn.execute(sql.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1)
                             if "IF NOT EXISTS" not in sql else sql)
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    return True


def migrate_moderation_schema(conn: sqlite3.Connection) -> None:
    """Idempotent: adds the needs_revision status, review columns, the decision log and notification types."""
    _rebuild_check(
        conn, "moderation_submissions",
        "'approved', 'rejected')",
        "'approved', 'rejected', 'needs_revision')",
    )
    existing = {r[1] for r in conn.execute("PRAGMA table_info(moderation_submissions)")}
    for column in ("claimed_by", "claimed_at", "reviewed_by", "reviewed_at",
                   "review_decision", "review_reason_code", "review_comment"):
        if column not in existing:
            conn.execute(f"ALTER TABLE moderation_submissions ADD COLUMN {column} TEXT")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS moderation_decisions (
            id TEXT PRIMARY KEY,
            submission_id TEXT NOT NULL,
            draft_id TEXT NOT NULL,
            author_id TEXT NOT NULL,
            moderator_id TEXT NOT NULL,
            decision TEXT NOT NULL CHECK (decision IN ('approve', 'revise', 'reject')),
            reason_code TEXT,
            comment TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_moderation_decisions_submission ON moderation_decisions(submission_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_moderation_decisions_created ON moderation_decisions(created_at)")
    _migrate_notifications(conn)
    conn.commit()


def _type_check(types) -> str:
    return "CHECK(type IN (" + ", ".join(f"'{t}'" for t in types) + "))"


def _migrate_notifications(conn: sqlite3.Connection) -> None:
    """Extends the type CHECK and adds the material key of author notifications with its uniqueness (Issue #274)."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'user_notifications'").fetchone()
    new_check = _type_check(NOTIFICATION_TYPES)
    if row and new_check not in row[0]:
        old = next((_type_check(t) for t in reversed(_LEGACY_NOTIFICATION_TYPES) if _type_check(t) in row[0]), None)
        if old is None:
            raise RuntimeError("Unexpected schema of user_notifications; cannot extend its CHECK constraint")
        _rebuild_check(conn, "user_notifications", old, new_check)
    columns = {r[1] for r in conn.execute("PRAGMA table_info(user_notifications)")}
    if "material_id" not in columns:
        conn.execute("ALTER TABLE user_notifications ADD COLUMN material_id TEXT")
    ensure_author_delivery_schema(conn)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_notifications_material
        ON user_notifications(user_id, type, material_id) WHERE material_id IS NOT NULL
    """)


def material_type_of(settings_json: Optional[str]) -> str:
    try:
        settings = json.loads(settings_json or "{}")
    except (TypeError, ValueError):
        settings = {}
    value = settings.get("materialType") or settings.get("material_type") or "publication"
    return "question" if value == "question" else "publication"


def claim(conn: sqlite3.Connection, submission_id: str, moderator_id: str) -> Tuple[bool, Optional[str]]:
    """Takes a pending submission into work. Returns (ok, error)."""
    now = _now()
    stale = (now - datetime.timedelta(minutes=CLAIM_TTL_MINUTES)).isoformat()
    with conn:
        updated = conn.execute("""
            UPDATE moderation_submissions SET claimed_by = ?, claimed_at = ?
            WHERE id = ? AND status = 'pending_moderation'
              AND (claimed_by IS NULL OR claimed_by = ? OR claimed_at < ?)
        """, (moderator_id, now.isoformat(), submission_id, moderator_id, stale)).rowcount
    if updated:
        return True, None
    row = conn.execute("SELECT status FROM moderation_submissions WHERE id = ?", (submission_id,)).fetchone()
    if not row:
        return False, "not_found"
    if row["status"] != "pending_moderation":
        return False, "already_reviewed"
    return False, "claimed_by_other"


def release(conn: sqlite3.Connection, submission_id: str, moderator_id: str, is_admin: bool) -> bool:
    with conn:
        if is_admin:
            return conn.execute("UPDATE moderation_submissions SET claimed_by = NULL, claimed_at = NULL WHERE id = ?",
                                (submission_id,)).rowcount > 0
        return conn.execute("""
            UPDATE moderation_submissions SET claimed_by = NULL, claimed_at = NULL
            WHERE id = ? AND claimed_by = ?
        """, (submission_id, moderator_id)).rowcount > 0


def validate_decision(decision: str, reason_code: Optional[str], comment: str) -> Optional[str]:
    """Returns an error message, or None when the decision payload is acceptable."""
    if decision not in DECISIONS:
        return "Неизвестное решение"
    if len(comment) > MAX_COMMENT:
        return f"Комментарий не должен превышать {MAX_COMMENT} символов"
    if decision == "revise" and len(comment) < MIN_REVISION_COMMENT:
        return "Опишите, что нужно доработать (не короче 10 символов)"
    if decision == "reject":
        if reason_code not in REJECT_REASONS:
            return "Выберите причину отклонения"
        if reason_code == "other" and len(comment) < MIN_REVISION_COMMENT:
            return "Опишите причину отклонения (не короче 10 символов)"
    return None


def decide(
    conn: sqlite3.Connection,
    submission_id: str,
    moderator: Dict[str, Any],
    decision: str,
    reason_code: Optional[str],
    comment: str,
) -> Tuple[bool, Optional[str], Optional[sqlite3.Row]]:
    """
    Applies a decision exactly once. Only a pending submission can be decided, and a submission
    claimed by another moderator (and not stale) cannot be decided by someone else.
    Returns (ok, error_code, submission_row_after).
    """
    row = conn.execute("SELECT * FROM moderation_submissions WHERE id = ?", (submission_id,)).fetchone()
    if not row:
        return False, "not_found", None
    if row["status"] != "pending_moderation":
        return False, "already_reviewed", row

    if decision == "approve":
        try:
            settings = json.loads(row["publication_settings"] or "{}")
        except ValueError:
            settings = {}
        company_id = settings.get("companyId") or settings.get("company_id")
        if company_id:
            author = conn.execute("SELECT role FROM users WHERE id = ?", (row["author_id"],)).fetchone()
            if not can_user_publish_for_company(conn, row["author_id"], company_id,
                                                user_role=author["role"] if author else "user"):
                return False, "company_forbidden", row

    now = _now()
    stale = (now - datetime.timedelta(minutes=CLAIM_TTL_MINUTES)).isoformat()
    status = DECISIONS[decision]
    stored_reason = reason_code if decision == "reject" else None
    with conn:
        updated = conn.execute("""
            UPDATE moderation_submissions
            SET status = ?, reviewed_by = ?, reviewed_at = ?, review_decision = ?,
                review_reason_code = ?, review_comment = ?, claimed_by = NULL, claimed_at = NULL,
                updated_at = ?
            WHERE id = ? AND status = 'pending_moderation'
              AND (claimed_by IS NULL OR claimed_by = ? OR claimed_at < ?)
        """, (status, moderator["id"], now.isoformat(), decision, stored_reason, comment or None,
              now.isoformat(), submission_id, moderator["id"], stale)).rowcount
        if updated != 1:
            current = conn.execute("SELECT status FROM moderation_submissions WHERE id = ?", (submission_id,)).fetchone()
            return False, ("already_reviewed" if current and current["status"] != "pending_moderation"
                           else "claimed_by_other"), row
        conn.execute("""
            INSERT INTO moderation_decisions
            (id, submission_id, draft_id, author_id, moderator_id, decision, reason_code, comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"dec_{uuid.uuid4().hex[:16]}", submission_id, row["draft_id"], row["author_id"], moderator["id"],
              decision, stored_reason, comment or None, now.isoformat()))
        if status == "approved":
            deliver_author_material(conn, submission_id, now.isoformat())
    after = conn.execute("SELECT * FROM moderation_submissions WHERE id = ?", (submission_id,)).fetchone()
    return True, None, after


def author_stats(conn: sqlite3.Connection, author_id: str) -> Dict[str, int]:
    stats = {"pending_moderation": 0, "approved": 0, "needs_revision": 0, "rejected": 0}
    for r in conn.execute("""
        SELECT status, COUNT(*) AS cnt FROM moderation_submissions
        WHERE author_id = ? AND status IN ('pending_moderation', 'approved', 'needs_revision', 'rejected')
        GROUP BY status
    """, (author_id,)):
        stats[r["status"]] = r["cnt"]
    return stats


def decision_notice(decision: str, title: str, reason_code: Optional[str], comment: str) -> Dict[str, str]:
    """Texts for the site notification and the email sent to the author."""
    if decision == "approve":
        return {
            "type": "moderation_approved",
            "title": "Материал опубликован",
            "message": f"«{title}» прошел модерацию и опубликован.",
            "email_subject": "Ваш материал опубликован на SmartContractum",
            "email_heading": "Материал опубликован",
            "email_intro": f"Ваш материал «{title}» прошел модерацию и теперь виден всем читателям.",
            "email_details": comment,
        }
    if decision == "revise":
        return {
            "type": "moderation_revision",
            "title": "Материал нужно доработать",
            "message": f"Модератор вернул «{title}» на доработку: {comment}",
            "email_subject": "Материал нужно доработать: замечания модератора",
            "email_heading": "Нужна доработка",
            "email_intro": f"Модератор вернул ваш материал «{title}» на доработку. Исправьте его по замечаниям "
                           f"и отправьте снова.",
            "email_details": comment,
        }
    reason = REJECT_REASONS.get(reason_code or "", "")
    details = reason + (f". {comment}" if comment else "")
    return {
        "type": "moderation_rejected",
        "title": "Материал отклонен",
        "message": f"«{title}» отклонен модератором. Причина: {details}",
        "email_subject": "Материал отклонен модератором SmartContractum",
        "email_heading": "Материал отклонен",
        "email_intro": f"Модератор отклонил ваш материал «{title}».",
        "email_details": f"Причина: {details}",
    }


def list_decision_log(conn: sqlite3.Connection, limit: int, offset: int) -> List[Dict[str, Any]]:
    rows = conn.execute("""
        SELECT d.*, ms.title,
               COALESCE(NULLIF(TRIM(mp.name), ''), mu.login, d.moderator_id) AS moderator_name,
               COALESCE(NULLIF(TRIM(ap.name), ''), au.login, d.author_id) AS author_name
        FROM moderation_decisions d
        LEFT JOIN moderation_submissions ms ON ms.id = d.submission_id
        LEFT JOIN users mu ON mu.id = d.moderator_id
        LEFT JOIN user_profiles mp ON mp.user_id = d.moderator_id
        LEFT JOIN users au ON au.id = d.author_id
        LEFT JOIN user_profiles ap ON ap.user_id = d.author_id
        ORDER BY d.created_at DESC
        LIMIT ? OFFSET ?
    """, (limit, offset)).fetchall()
    return [{
        "id": r["id"],
        "submissionId": r["submission_id"],
        "title": r["title"],
        "decision": r["decision"],
        "reasonCode": r["reason_code"],
        "reasonLabel": REJECT_REASONS.get(r["reason_code"] or "", None),
        "comment": r["comment"],
        "moderator": {"id": r["moderator_id"], "name": r["moderator_name"]},
        "author": {"id": r["author_id"], "name": r["author_name"]},
        "createdAt": r["created_at"],
    } for r in rows]
