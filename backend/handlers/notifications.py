"""Notifications of the current user."""

from backend.author_delivery import AUTHOR_NOTIFICATION_TYPES, present_author_notification
from backend.config import MAX_JSON_BODY_BYTES


class NotificationsHandlers:
    def handle_get_notifications(self):
        """
        GET /api/notifications
        Returns list of in-app notifications for the logged in user, plus unreadCount.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(200, {
                "success": True,
                "notifications": [],
                "unreadCount": 0
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, user_id, actor_id, actor_name, article_id, comment_id, type, title, message, is_read, created_at
                    FROM user_notifications
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 50
                """, (user["id"],))
                rows = cur.fetchall()

                cur.execute("""
                    SELECT COUNT(*) AS unread_cnt
                    FROM user_notifications
                    WHERE user_id = ? AND is_read = 0
                """, (user["id"],))
                unread_cnt = cur.fetchone()["unread_cnt"]

                notifs = []
                for r in rows:
                    item = {
                        "id": r["id"],
                        "userId": r["user_id"],
                        "actorId": r["actor_id"],
                        "actorName": r["actor_name"],
                        "articleId": r["article_id"],
                        "commentId": r["comment_id"],
                        "type": r["type"],
                        "title": r["title"],
                        "message": r["message"],
                        "isRead": bool(r["is_read"]),
                        "createdAt": r["created_at"]
                    }
                    if r["type"] in AUTHOR_NOTIFICATION_TYPES:
                        # Publicity is rechecked on every read (Issue #274); unread rows stay counted
                        present_author_notification(cur, item)
                    notifs.append(item)

            self.send_json_response(200, {
                "success": True,
                "notifications": notifs,
                "unreadCount": unread_cnt
            })
        finally:
            conn.close()

    def handle_post_notifications_read(self):
        """
        POST /api/notifications/read
        Marks one or all notifications as read.
        """
        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для управления уведомлениями необходимо войти",
                "requireAuth": True
            })
            return

        notif_id = payload.get("notificationId") or payload.get("id")
        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                if notif_id:
                    cur.execute("SELECT id, user_id FROM user_notifications WHERE id = ?", (notif_id,))
                    row = cur.fetchone()
                    if not row:
                        self.send_json_response(404, {"success": False, "error": "Уведомление не найдено"})
                        return
                    if row["user_id"] != user["id"]:
                        self.send_json_response(403, {"success": False, "error": "Отказано в доступе"})
                        return
                    cur.execute("UPDATE user_notifications SET is_read = 1 WHERE user_id = ? AND id = ?", (user["id"], notif_id))
                else:
                    cur.execute("UPDATE user_notifications SET is_read = 1 WHERE user_id = ?", (user["id"],))

                cur.execute("SELECT COUNT(*) AS unread_cnt FROM user_notifications WHERE user_id = ? AND is_read = 0", (user["id"],))
                unread_cnt = cur.fetchone()["unread_cnt"]

            self.send_json_response(200, {
                "success": True,
                "unreadCount": unread_cnt
            })
        finally:
            conn.close()
