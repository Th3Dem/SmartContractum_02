"""
Per-author notification bell and the compact author summary (Issue #273).

The bell is independent of the subscription: the subscription adds an author to "My feed",
the bell asks for in-site notifications about the author's new public materials. All four
combinations are valid. A row in user_author_notifications means "on"; no row means "off".

Endpoints:
  PUT /api/authors/<author_id>/notifications   body {"enabled": true|false}
  GET /api/user/author-notifications           ?q=&limit=&offset=   (private list of the current user)
  GET /api/users/<user_id>/summary             compact profile for the author mini card
"""
import datetime
import urllib.parse

from backend.author_metrics import author_metrics, profile_exists
from backend.config import MAX_JSON_BODY_BYTES

BIO_SUMMARY_LIMIT = 200
LIST_DEFAULT_LIMIT = 20
LIST_MAX_LIMIT = 100


def notifications_enabled(cur, user_id, author_id):
    if not user_id or not author_id:
        return False
    cur.execute("SELECT 1 FROM user_author_notifications WHERE user_id = ? AND author_id = ?", (user_id, author_id))
    return cur.fetchone() is not None


def clear_author_notifications(cur, user_id, author_ids):
    """Excluding an author from the feed turns their bell off (re-including does not turn it on)."""
    ids = [a for a in author_ids if a]
    if not user_id or not ids:
        return
    cur.executemany("DELETE FROM user_author_notifications WHERE user_id = ? AND author_id = ?",
                    [(user_id, a) for a in ids])


def _is_subscribed(cur, user_id, author_id):
    cur.execute("SELECT 1 FROM user_subscriptions WHERE user_id = ? AND target_type = 'author' AND target_id = ?",
                (user_id, author_id))
    return cur.fetchone() is not None


def _is_excluded(cur, user_id, author_id):
    cur.execute("SELECT 1 FROM user_feed_exceptions WHERE user_id = ? AND target_type = 'author' AND target_id = ?",
                (user_id, author_id))
    return cur.fetchone() is not None


def _active_author(cur, author_id):
    """The bell can be turned on only for an existing, active account."""
    cur.execute("SELECT status FROM users WHERE id = ?", (author_id,))
    row = cur.fetchone()
    return bool(row and row["status"] == "active")


def _enabled_count(cur, user_id):
    cur.execute("SELECT COUNT(*) AS cnt FROM user_author_notifications WHERE user_id = ?", (user_id,))
    return cur.fetchone()["cnt"] or 0


class AuthorNotificationsHandlers:
    def handle_put_author_notifications(self, author_id):
        """PUT /api/authors/<author_id>/notifications with the desired state; idempotent."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if data is None:
            return
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация", "requireAuth": True})
            return
        enabled = data.get("enabled")
        if not isinstance(enabled, bool):
            self.send_json_response(400, {"success": False, "error": "enabled должен быть true или false", "code": "INVALID_ENABLED"})
            return
        author_id = (author_id or "").strip()
        if not author_id:
            self.send_json_response(400, {"success": False, "error": "Не указан автор", "code": "AUTHOR_REQUIRED"})
            return
        if author_id == user["id"]:
            self.send_json_response(400, {"success": False, "error": "Нельзя включить уведомления о себе",
                                          "code": "SELF_NOTIFICATIONS_FORBIDDEN"})
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                if enabled:
                    if not _active_author(cur, author_id):
                        self.send_json_response(404, {"success": False, "error": "Автор не найден", "code": "AUTHOR_NOT_FOUND"})
                        return
                    if _is_excluded(cur, user["id"], author_id):
                        self.send_json_response(409, {
                            "success": False, "code": "AUTHOR_EXCLUDED",
                            "error": "Автор скрыт из вашей ленты. Сначала уберите его из исключений.",
                        })
                        return
                    cur.execute("""
                        INSERT OR IGNORE INTO user_author_notifications (user_id, author_id, created_at)
                        VALUES (?, ?, ?)
                    """, (user["id"], author_id, datetime.datetime.now(datetime.timezone.utc).isoformat()))
                else:
                    # Turning off is allowed for any id, so a removed author can be cleaned from the list
                    cur.execute("DELETE FROM user_author_notifications WHERE user_id = ? AND author_id = ?",
                                (user["id"], author_id))
                state = notifications_enabled(cur, user["id"], author_id)
                subscribed = _is_subscribed(cur, user["id"], author_id)
                count = _enabled_count(cur, user["id"])
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "authorId": author_id,
            "enabled": state,
            "authorNotificationsEnabled": state,
            "isSubscribed": subscribed,
            "count": count,
        })

    def handle_get_author_notifications_list(self, parsed):
        """GET /api/user/author-notifications: private list of authors with the bell on."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация", "requireAuth": True})
            return
        query = urllib.parse.parse_qs(parsed.query if parsed else "")
        q = (query.get("q", [""])[0] or "").strip().casefold()
        try:
            limit = int(query.get("limit", [str(LIST_DEFAULT_LIMIT)])[0])
        except ValueError:
            limit = LIST_DEFAULT_LIMIT
        limit = max(1, min(limit, LIST_MAX_LIMIT))
        try:
            offset = max(0, int(query.get("offset", ["0"])[0]))
        except ValueError:
            offset = 0

        conn = self.get_db()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT an.author_id, an.created_at, u.login, u.status,
                       EXISTS(SELECT 1 FROM user_subscriptions s
                              WHERE s.user_id = an.user_id AND s.target_type = 'author' AND s.target_id = an.author_id) AS subscribed
                FROM user_author_notifications an
                LEFT JOIN users u ON u.id = an.author_id
                WHERE an.user_id = ?
                ORDER BY an.created_at DESC, an.author_id ASC
            """, (user["id"],))
            rows = cur.fetchall()
            items = []
            for r in rows:
                ident = self.resolve_user_identity(cur, r["author_id"])
                login = r["login"] or ""
                if q and q not in ident["name"].casefold() and q not in login.casefold():
                    continue
                items.append({
                    "authorId": r["author_id"],
                    "name": ident["name"],
                    "login": login or None,
                    "avatar": ident["avatar"],
                    "initials": ident["initials"],
                    "isSubscribed": bool(r["subscribed"]),
                    "enabled": True,
                    "available": r["status"] == "active",
                    "profileUrl": "profile.html?id=" + urllib.parse.quote(r["author_id"]),
                })
        finally:
            conn.close()

        total = len(items)
        page = items[offset:offset + limit]
        self.send_json_response(200, {
            "success": True,
            "items": page,
            "total": total,
            "count": len(rows),
            "limit": limit,
            "offset": offset,
            "hasMore": offset + len(page) < total,
        })

    def handle_get_user_summary(self, user_id):
        """GET /api/users/<user_id>/summary: what the author mini card needs, without the material lists."""
        user_id = (user_id or "").strip()
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "Не указан user_id"})
            return
        conn = self.get_db()
        try:
            cur = conn.cursor()
            if not profile_exists(cur, user_id):
                self.send_json_response(404, {"success": False, "error": "Пользователь не найден", "code": "USER_NOT_FOUND"})
                return
            cur.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
            p_row = cur.fetchone()
            ident = self.resolve_user_identity(cur, user_id, p_row)
            metrics = author_metrics(cur, user_id)
            bio = (p_row["bio"] or "").strip() if p_row and p_row["bio"] else ""
            if len(bio) > BIO_SUMMARY_LIMIT:
                bio = bio[:BIO_SUMMARY_LIMIT - 1].rstrip() + "…"

            viewer = self.get_current_user()
            is_own = bool(viewer and viewer["id"] == user_id)
            personal = bool(viewer and not is_own)
            summary = {
                "id": user_id,
                "userId": user_id,
                "name": ident["name"],
                "avatar": ident["avatar"],
                "initials": ident["initials"],
                "bio": bio,
                "rating": metrics["rating"],
                "publicationsCount": metrics["publicationsCount"],
                "questionsCount": metrics["questionsCount"],
                "commentsCount": metrics["commentsCount"],
                "followersCount": metrics["followersCount"],
                "profileUrl": "profile.html?id=" + urllib.parse.quote(user_id),
                "isOwnProfile": is_own,
                # Personal state of the current viewer only; guests and the author themselves get false
                "isSubscribed": personal and _is_subscribed(cur, viewer["id"], user_id),
                "authorNotificationsEnabled": personal and notifications_enabled(cur, viewer["id"], user_id),
                "isExcluded": personal and _is_excluded(cur, viewer["id"], user_id),
                "canNotify": personal and _active_author(cur, user_id),
            }
        finally:
            conn.close()
        self.send_json_response(200, {"success": True, "summary": summary})
