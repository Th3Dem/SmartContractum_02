"""
Current identity of authors: display name, photo and specialization.

Materials keep a snapshot of the author in their settings and comments store the name and photo
at the moment of writing. Readers must see the author as they are now, so materials take the
identity from user_profiles at read time and comments are brought up to date whenever the
profile changes.
"""


def author_identities(cur, user_ids):
    """{user_id: {"name", "avatar", "specialization"}} from user profiles; empty values are None."""
    ids = sorted({a for a in user_ids if a})
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    cur.execute(f"SELECT user_id, name, avatar, specialization FROM user_profiles WHERE user_id IN ({placeholders})", ids)
    return {
        r["user_id"]: {
            "name": (r["name"] or "").strip() or None,
            "avatar": r["avatar"] or None,
            "specialization": (r["specialization"] or "").strip() or None,
        }
        for r in cur.fetchall()
    }


def initials_of(name):
    return "".join(part[0].upper() for part in str(name).split()[:2]) if name else "SC"


def sync_comment_snapshots(cur, user_id):
    """Copies the current name and photo of a user into all of their comments."""
    row = cur.execute("SELECT name, avatar FROM user_profiles WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return
    cur.execute("""
        UPDATE article_comments
        SET author_name = COALESCE(NULLIF(TRIM(?), ''), author_name), author_avatar = ?
        WHERE user_id = ?
    """, (row["name"] or "", row["avatar"] or None, user_id))
