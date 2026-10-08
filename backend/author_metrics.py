"""
Public metrics of a person's profile, shared by the full profile (GET /api/users/<id>) and the
compact summary of the author mini card (GET /api/users/<id>/summary), so both show the same
numbers and the same rating formula (Issue #273).
"""
import json


def profile_exists(cur, user_id):
    """A person exists when any trace of them is stored: profile, account, session, material or comment."""
    for sql in (
        "SELECT 1 FROM user_profiles WHERE user_id = ? LIMIT 1",
        "SELECT 1 FROM users WHERE id = ? LIMIT 1",
        "SELECT 1 FROM sessions WHERE user_id = ? LIMIT 1",
        "SELECT 1 FROM moderation_submissions WHERE author_id = ? LIMIT 1",
        "SELECT 1 FROM article_comments WHERE user_id = ? LIMIT 1",
    ):
        cur.execute(sql, (user_id,))
        if cur.fetchone():
            return True
    return False


def material_kind(publication_settings):
    """'question' or the stored material type of an approved material ('article' when unknown)."""
    try:
        settings = json.loads(publication_settings) if publication_settings else {}
    except Exception:
        settings = {}
    return settings.get("materialType") or settings.get("type") or "article"


def count_material_kinds(settings_values):
    """(publications_count, questions_count) of approved materials from their publication settings."""
    publications = questions = 0
    for value in settings_values:
        if material_kind(value) == "question":
            questions += 1
        else:
            publications += 1
    return publications, questions


def author_metrics(cur, user_id):
    """Rating and counters of a person's public activity."""
    cur.execute("""
        SELECT publication_settings FROM moderation_submissions
        WHERE author_id = ? AND status = 'approved'
    """, (user_id,))
    publications_count, questions_count = count_material_kinds(r["publication_settings"] for r in cur.fetchall())

    cur.execute("""
        SELECT COUNT(DISTINCT ac.id) AS total_comments
        FROM article_comments ac
        JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
        WHERE ac.user_id = ?
          AND ac.status = 'published'
          AND (ac.comment_type IS NULL OR ac.comment_type != 'answer')
          AND ms.status = 'approved'
    """, (user_id,))
    comm_stats = cur.fetchone()
    comments_count = int(comm_stats["total_comments"] or 0) if comm_stats else 0

    cur.execute("""
        SELECT COALESCE(SUM(v.value), 0) AS pub_score
        FROM article_votes v
        WHERE v.article_id IN (
            SELECT id FROM moderation_submissions WHERE author_id = ? AND status = 'approved'
            UNION
            SELECT draft_id FROM moderation_submissions WHERE author_id = ? AND status = 'approved' AND draft_id IS NOT NULL
        )
    """, (user_id, user_id))
    pub_score = int(cur.fetchone()["pub_score"] or 0)

    cur.execute("""
        SELECT COALESCE(SUM(v.value), 0) AS comm_score
        FROM comment_votes v
        WHERE v.comment_id IN (
            SELECT ac.id
            FROM article_comments ac
            JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
            WHERE ac.user_id = ?
              AND ac.status = 'published'
              AND ms.status = 'approved'
        )
    """, (user_id,))
    comm_score = int(cur.fetchone()["comm_score"] or 0)

    cur.execute("SELECT COUNT(*) AS cnt FROM user_subscriptions WHERE target_type = 'author' AND target_id = ?", (user_id,))
    followers_count = cur.fetchone()["cnt"] or 0
    cur.execute("SELECT COUNT(*) AS cnt FROM user_subscriptions WHERE user_id = ? AND target_type = 'author'", (user_id,))
    following_count = cur.fetchone()["cnt"] or 0

    return {
        "rating": pub_score + comm_score,
        "materialsRating": pub_score,
        "discussionsRating": comm_score,
        "publicationsCount": publications_count,
        "questionsCount": questions_count,
        "commentsCount": comments_count,
        "followersCount": followers_count,
        "followingCount": following_count,
    }
