"""
In-app notifications about new public materials of authors a user follows with the bell (Issue #274).

Delivery happens inside the transaction that makes a submission public, so the first publication and the
notification rows commit or roll back together. The first publication of a material is recorded once in
author_material_publications (primary key: material key); a later approval, a re-approval or a return to
'approved' finds that record and delivers nothing. Every notification row also carries the material key and
the database keeps (user_id, type, material_id) unique, so retries and concurrent approvals never duplicate.
"""
import json
import uuid

# Notification type per material kind (publication covers every non-question material type)
AUTHOR_MATERIAL_TYPES = {
    "publication": "author_publication",
    "question": "author_question",
}
AUTHOR_NOTIFICATION_TYPES = tuple(AUTHOR_MATERIAL_TYPES.values())

TYPE_TITLES = {
    "author_publication": "Новая публикация",
    "author_question": "Новый вопрос",
}
UNAVAILABLE_TITLE = "Материал недоступен"
UNAVAILABLE_MESSAGE = "Автор снял материал с публикации или он был удален."
MAX_TITLE = 200


def material_key(author_id, draft_id):
    """Stable id of one material across its submitted versions."""
    return f"{author_id}/{draft_id}"


def _settings(raw):
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _material_type(settings):
    value = settings.get("materialType") or settings.get("material_type") or "publication"
    return "question" if value == "question" else "publication"


def author_display_name(cur, author_id):
    cur.execute("""
        SELECT COALESCE(NULLIF(TRIM(p.name), ''), u.login, ?) AS name
        FROM (SELECT ? AS id) x
        LEFT JOIN users u ON u.id = x.id
        LEFT JOIN user_profiles p ON p.user_id = x.id
    """, (author_id, author_id))
    row = cur.fetchone()
    return (row["name"] if row else None) or author_id


def message_for(author_name, title):
    return f"{author_name}: «{(title or '').strip()[:MAX_TITLE]}»"


def deliver_author_material(conn, submission_id, now_iso):
    """
    Creates the notifications for the first public version of a material. Must run inside the transaction
    that set the submission to 'approved'; raises on database errors so that transaction rolls back.
    Returns the number of new rows.

    Skipped: a material that already had a public version, materials published under a company identity,
    the author themselves, recipients whose bell is off, disabled accounts and recipients who excluded the
    author from their feed.
    """
    cur = conn.cursor()
    cur.execute("SELECT id, draft_id, author_id, title, status, publication_settings FROM moderation_submissions WHERE id = ?",
                (submission_id,))
    row = cur.fetchone()
    if not row or row["status"] != "approved":
        return 0
    settings = _settings(row["publication_settings"])
    author_id = row["author_id"]
    key = material_key(author_id, row["draft_id"])
    cur.execute("""
        INSERT OR IGNORE INTO author_material_publications (material_id, author_id, submission_id, published_at)
        VALUES (?, ?, ?, ?)
    """, (key, author_id, row["id"], now_iso))
    if cur.rowcount != 1:
        return 0
    if settings.get("companyId") or settings.get("company_id"):
        return 0
    cur.execute("""
        SELECT an.user_id FROM user_author_notifications an
        JOIN users u ON u.id = an.user_id AND u.status = 'active'
        WHERE an.author_id = ? AND an.user_id != ?
          AND NOT EXISTS (SELECT 1 FROM user_feed_exceptions e
                          WHERE e.user_id = an.user_id AND e.target_type = 'author' AND e.target_id = an.author_id)
    """, (author_id, author_id))
    recipients = [r["user_id"] for r in cur.fetchall()]
    if not recipients:
        return 0

    ntype = AUTHOR_MATERIAL_TYPES[_material_type(settings)]
    author_name = author_display_name(cur, author_id)
    message = message_for(author_name, row["title"])
    created = 0
    for user_id in recipients:
        cur.execute("""
            INSERT OR IGNORE INTO user_notifications
            (id, user_id, actor_id, actor_name, article_id, comment_id, type, title, message, is_read, created_at,
             material_id)
            VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, 0, ?, ?)
        """, (f"notif_{uuid.uuid4().hex[:16]}", user_id, author_id, author_name, row["id"], ntype,
              TYPE_TITLES[ntype], message, now_iso, key))
        created += cur.rowcount
    return created


def present_author_notification(cur, item):
    """
    Rechecks an author notification at read time: the current author name and title for a public material,
    a neutral text without the title or link once the material is no longer public.
    """
    cur.execute("SELECT title, status FROM moderation_submissions WHERE id = ?", (item["articleId"],))
    sub = cur.fetchone()
    item["materialType"] = "question" if item["type"] == "author_question" else "publication"
    if not sub or sub["status"] != "approved":
        item.update({"available": False, "articleId": None, "title": UNAVAILABLE_TITLE,
                     "message": UNAVAILABLE_MESSAGE, "materialTitle": None})
        return item
    name = author_display_name(cur, item["actorId"])
    item.update({"available": True, "actorName": name, "authorName": name, "materialTitle": sub["title"],
                 "title": TYPE_TITLES.get(item["type"], item["title"]), "message": message_for(name, sub["title"])})
    return item


def ensure_schema(conn):
    """Idempotent: the first-publication record, backfilled with materials that are already public."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS author_material_publications (
            material_id TEXT PRIMARY KEY,
            author_id TEXT NOT NULL,
            submission_id TEXT NOT NULL,
            published_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        INSERT OR IGNORE INTO author_material_publications (material_id, author_id, submission_id, published_at)
        SELECT author_id || '/' || draft_id, author_id, id, COALESCE(reviewed_at, updated_at, created_at)
        FROM moderation_submissions WHERE status = 'approved'
    """)
