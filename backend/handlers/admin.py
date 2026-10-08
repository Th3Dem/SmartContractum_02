"""Moderation panel and user administration for moderators and administrators."""
import datetime
import json
import sqlite3
import sys
import urllib.parse
import uuid

from backend.config import MAX_JSON_BODY_BYTES, site_url
from backend.content import TOPICS_TITLE_MAP, extract_article_text, make_content_snippet
from backend.mail import EMAIL_SERVICE, render_notice_email
from backend.moderation import (
    REJECT_REASONS,
    STATUS_LABELS,
    author_stats,
    claim,
    decide,
    decision_notice,
    list_decision_log,
    material_type_of,
    release,
    validate_decision,
)

QUEUE_STATUSES = ("pending_moderation", "needs_revision", "rejected", "approved")


def _page_args(query, default_limit=20, max_limit=100):
    try:
        limit = max(1, min(int(query.get("limit", [default_limit])[0]), max_limit))
    except ValueError:
        limit = default_limit
    try:
        offset = max(0, int(query.get("offset", ["0"])[0]))
    except ValueError:
        offset = 0
    return limit, offset


class AdminHandlers:
    def require_staff(self, admin_only=False):
        """Returns the current moderator/administrator, or sends 401/403 and returns None."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация", "requireAuth": True})
            return None
        allowed = ("admin",) if admin_only else ("moderator", "admin")
        if user.get("role") not in allowed:
            self.send_json_response(403, {"success": False, "error": "Недостаточно прав"})
            return None
        return user

    def _submission_summary(self, row, me_id):
        settings = {}
        try:
            settings = json.loads(row["publication_settings"] or "{}")
        except ValueError:
            pass
        snippet = make_content_snippet(extract_article_text(row["article_html"] or ""))
        return {
            "id": row["id"],
            "draftId": row["draft_id"],
            "title": row["title"],
            "materialType": material_type_of(row["publication_settings"]),
            "status": row["status"],
            "statusLabel": STATUS_LABELS.get(row["status"], row["status"]),
            "snippet": snippet,
            "author": {"id": row["author_id"], "name": row["author_name"], "login": row["author_login"]},
            "company": {"id": settings.get("companyId"), "name": row["company_name"]} if settings.get("companyId") else None,
            "topics": [TOPICS_TITLE_MAP.get(t, t) for t in (settings.get("topics") or [])],
            "claimedBy": {"id": row["claimed_by"], "name": row["claimer_name"]} if row["claimed_by"] else None,
            "claimedByMe": bool(row["claimed_by"]) and row["claimed_by"] == me_id,
            "claimedAt": row["claimed_at"],
            "reviewDecision": row["review_decision"],
            "reviewComment": row["review_comment"],
            "reviewReasonLabel": REJECT_REASONS.get(row["review_reason_code"] or "", None),
            "reviewedAt": row["reviewed_at"],
            "createdAt": row["created_at"],
        }

    _SUBMISSION_SELECT = """
        SELECT ms.*,
               COALESCE(NULLIF(TRIM(ap.name), ''), au.login, ms.author_id) AS author_name,
               au.login AS author_login,
               COALESCE(NULLIF(TRIM(cp.name), ''), cu.login) AS claimer_name,
               co.name AS company_name
        FROM moderation_submissions ms
        LEFT JOIN users au ON au.id = ms.author_id
        LEFT JOIN user_profiles ap ON ap.user_id = ms.author_id
        LEFT JOIN users cu ON cu.id = ms.claimed_by
        LEFT JOIN user_profiles cp ON cp.user_id = ms.claimed_by
        LEFT JOIN companies co ON co.id = json_extract(ms.publication_settings, '$.companyId')
    """

    def handle_admin_queue(self, parsed):
        """GET /api/admin/moderation/queue?status=&type=&q=&limit=&offset="""
        user = self.require_staff()
        if not user:
            return
        query = urllib.parse.parse_qs(parsed.query)
        status = query.get("status", ["pending_moderation"])[0]
        if status not in QUEUE_STATUSES:
            status = "pending_moderation"
        material_type = query.get("type", [""])[0]
        search = query.get("q", [""])[0].strip().lower()
        limit, offset = _page_args(query)

        where = ["ms.status = ?"]
        params = [status]
        if material_type == "question":
            where.append("json_extract(ms.publication_settings, '$.materialType') = 'question'")
        elif material_type == "publication":
            where.append("COALESCE(json_extract(ms.publication_settings, '$.materialType'), 'publication') != 'question'")
        if search:
            where.append("(LOWER(ms.title) LIKE ? OR LOWER(COALESCE(ap.name, au.login, '')) LIKE ?)")
            params += [f"%{search}%", f"%{search}%"]
        order = "ms.created_at ASC" if status == "pending_moderation" else "COALESCE(ms.reviewed_at, ms.updated_at) DESC"

        conn = self.get_db()
        try:
            rows = conn.execute(
                self._SUBMISSION_SELECT + f" WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ? OFFSET ?",
                params + [limit + 1, offset]).fetchall()
            counts = {s: 0 for s in QUEUE_STATUSES}
            for r in conn.execute("SELECT status, COUNT(*) AS cnt FROM moderation_submissions GROUP BY status"):
                if r["status"] in counts:
                    counts[r["status"]] = r["cnt"]
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "items": [self._submission_summary(r, user["id"]) for r in rows[:limit]],
            "hasMore": len(rows) > limit,
            "counts": counts,
            "limit": limit,
            "offset": offset,
        })

    def handle_admin_submission(self, submission_id):
        """GET /api/admin/moderation/submissions/<id>: full material, author stats, history."""
        user = self.require_staff()
        if not user:
            return
        conn = self.get_db()
        try:
            row = conn.execute(self._SUBMISSION_SELECT + " WHERE ms.id = ?", (submission_id,)).fetchone()
            if not row:
                self.send_json_response(404, {"success": False, "error": "Материал не найден"})
                return
            item = self._submission_summary(row, user["id"])
            try:
                item["publicationSettings"] = json.loads(row["publication_settings"] or "{}")
            except ValueError:
                item["publicationSettings"] = {}
            item["html"] = row["article_html"]
            item["authorStats"] = author_stats(conn, row["author_id"])
            item["versions"] = [{
                "id": v["id"],
                "status": v["status"],
                "statusLabel": STATUS_LABELS.get(v["status"], v["status"]),
                "reviewComment": v["review_comment"],
                "reviewReasonLabel": REJECT_REASONS.get(v["review_reason_code"] or "", None),
                "createdAt": v["created_at"],
                "reviewedAt": v["reviewed_at"],
            } for v in conn.execute("""
                SELECT id, status, review_comment, review_reason_code, created_at, reviewed_at
                FROM moderation_submissions WHERE draft_id = ? AND author_id = ? AND id != ?
                ORDER BY created_at DESC
            """, (row["draft_id"], row["author_id"], submission_id))]
        finally:
            conn.close()
        self.send_json_response(200, {"success": True, "submission": item, "rejectReasons": REJECT_REASONS})

    def handle_admin_claim(self, submission_id, take=True):
        """POST /api/admin/moderation/submissions/<id>/claim and /release"""
        user = self.require_staff()
        if not user:
            return
        if self.read_request_body(MAX_JSON_BODY_BYTES) is None:
            return
        conn = self.get_db()
        try:
            if take:
                ok, err = claim(conn, submission_id, user["id"])
            else:
                ok, err = release(conn, submission_id, user["id"], user.get("role") == "admin"), "not_claimed_by_you"
        finally:
            conn.close()
        if ok:
            self.send_json_response(200, {"success": True})
            return
        messages = {
            "not_found": (404, "Материал не найден"),
            "already_reviewed": (409, "Материал уже рассмотрен"),
            "claimed_by_other": (409, "Материалом уже занимается другой модератор"),
            "not_claimed_by_you": (409, "Материал закреплен не за вами"),
        }
        status, message = messages.get(err, (409, "Действие недоступно"))
        self.send_json_response(status, {"success": False, "error": message, "code": err})

    def handle_admin_decision(self, submission_id):
        """POST /api/admin/moderation/submissions/<id>/decision {decision, reasonCode, comment}"""
        user = self.require_staff()
        if not user:
            return
        data = self.read_json_body(MAX_JSON_BODY_BYTES)
        if data is None:
            return
        decision = str(data.get("decision") or "")
        reason_code = data.get("reasonCode") or None
        comment = data.get("comment") or ""
        comment = comment.strip() if isinstance(comment, str) else ""
        error = validate_decision(decision, reason_code, comment)
        if error:
            self.send_json_response(400, {"success": False, "error": error})
            return

        conn = self.get_db()
        try:
            try:
                ok, err, row = decide(conn, submission_id, user, decision, reason_code, comment)
            except sqlite3.Error as e:
                # The decision and the reader notifications share one transaction (Issue #274): nothing was saved
                sys.stderr.write(f"[moderation] decision for {submission_id} rolled back: {e}\n")
                self.send_json_response(503, {"success": False, "code": "decision_not_saved",
                                              "error": "Решение не сохранено, повторите попытку"})
                return
            if not ok:
                messages = {
                    "not_found": (404, "Материал не найден"),
                    "already_reviewed": (409, "Решение по материалу уже принято"),
                    "claimed_by_other": (409, "Материалом занимается другой модератор"),
                    "company_forbidden": (409, "Автор больше не может публиковать от имени указанной компании"),
                }
                status, message = messages.get(err, (409, "Решение не принято"))
                self.send_json_response(status, {"success": False, "error": message, "code": err})
                return
            self._notify_author(conn, row, user, decision, reason_code, comment)
        finally:
            conn.close()
        self.send_json_response(200, {
            "success": True,
            "status": row["status"],
            "statusLabel": STATUS_LABELS.get(row["status"], row["status"]),
        })

    def _notify_author(self, conn, row, moderator, decision, reason_code, comment):
        """Site notification and email for the author. Failures are logged and never undo the decision."""
        notice = decision_notice(decision, row["title"], reason_code, comment)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO user_notifications
                    (id, user_id, actor_id, actor_name, article_id, comment_id, type, title, message, is_read, created_at)
                    VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, 0, ?)
                """, (f"notif_{uuid.uuid4().hex[:16]}", row["author_id"], moderator["id"], "Модерация",
                      row["id"], notice["type"], notice["title"], notice["message"][:500], now_iso))
        except Exception as e:
            sys.stderr.write(f"[moderation] notification for {row['id']} failed: {e}\n")

        author = conn.execute("SELECT email, email_verified_at, status FROM users WHERE id = ?",
                              (row["author_id"],)).fetchone()
        if not author or not author["email"] or not author["email_verified_at"]:
            return
        if decision == "approve":
            button = ("Открыть материал", f"{site_url()}/article.html?id={urllib.parse.quote(row['id'])}")
        else:
            button = ("Мои материалы", f"{site_url()}/my-materials.html")
        text, html_body = render_notice_email(
            notice["email_heading"], notice["email_intro"], notice["email_details"], button[0], button[1])
        try:
            self.mailer().send_email(conn, author["email"], notice["email_subject"], text, html_body=html_body)
        except Exception as e:
            sys.stderr.write(f"[moderation] email for {row['id']} failed: {e}\n")

    def handle_admin_log(self, parsed):
        """GET /api/admin/moderation/log?limit=&offset="""
        if not self.require_staff():
            return
        limit, offset = _page_args(urllib.parse.parse_qs(parsed.query), default_limit=50, max_limit=200)
        conn = self.get_db()
        try:
            items = list_decision_log(conn, limit + 1, offset)
        finally:
            conn.close()
        self.send_json_response(200, {"success": True, "items": items[:limit], "hasMore": len(items) > limit})

    def handle_admin_users(self, parsed):
        """GET /api/admin/users?q=&role=&limit=&offset= (administrators only)"""
        if not self.require_staff(admin_only=True):
            return
        query = urllib.parse.parse_qs(parsed.query)
        search = query.get("q", [""])[0].strip().lower()
        role = query.get("role", [""])[0]
        limit, offset = _page_args(query)
        where, params = ["1 = 1"], []
        if search:
            where.append("(u.login_normalized LIKE ? OR u.email_normalized LIKE ? OR LOWER(COALESCE(p.name, '')) LIKE ?)")
            params += [f"%{search}%"] * 3
        if role in ("user", "moderator", "admin"):
            where.append("u.role = ?")
            params.append(role)
        conn = self.get_db()
        try:
            rows = conn.execute(f"""
                SELECT u.id, u.login, u.email, u.role, u.status, u.created_at, p.name,
                       (SELECT COUNT(*) FROM moderation_submissions ms WHERE ms.author_id = u.id AND ms.status = 'approved') AS published
                FROM users u LEFT JOIN user_profiles p ON p.user_id = u.id
                WHERE {' AND '.join(where)}
                ORDER BY CASE u.role WHEN 'admin' THEN 0 WHEN 'moderator' THEN 1 ELSE 2 END, u.created_at DESC
                LIMIT ? OFFSET ?
            """, params + [limit + 1, offset]).fetchall()
        finally:
            conn.close()
        self.send_json_response(200, {
            "success": True,
            "items": [{
                "id": r["id"], "login": r["login"], "name": r["name"] or r["login"], "email": r["email"],
                "role": r["role"], "status": r["status"], "createdAt": r["created_at"], "published": r["published"],
            } for r in rows[:limit]],
            "hasMore": len(rows) > limit,
        })

    def handle_admin_user_update(self, user_id, field):
        """POST /api/admin/users/<id>/role {role} and /status {status} (administrators only)"""
        admin = self.require_staff(admin_only=True)
        if not admin:
            return
        data = self.read_json_body(MAX_JSON_BODY_BYTES)
        if data is None:
            return
        value = str(data.get(field) or "")
        allowed = {"role": ("user", "moderator"), "status": ("active", "disabled")}[field]
        if value not in allowed:
            self.send_json_response(400, {"success": False, "error": "Недопустимое значение"})
            return
        if user_id == admin["id"]:
            self.send_json_response(409, {"success": False, "error": "Нельзя изменить собственную учетную запись"})
            return
        conn = self.get_db()
        try:
            target = conn.execute("SELECT id, role, status FROM users WHERE id = ?", (user_id,)).fetchone()
            if not target:
                self.send_json_response(404, {"success": False, "error": "Пользователь не найден"})
                return
            if target["role"] == "admin":
                self.send_json_response(409, {"success": False, "error": "Учетные записи администраторов меняются только на сервере"})
                return
            if field == "status" and target["status"] == "pending" and value == "active":
                self.send_json_response(409, {"success": False, "error": "Пользователь еще не подтвердил email"})
                return
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            with conn:
                conn.execute(f"UPDATE users SET {field} = ?, updated_at = ? WHERE id = ?", (value, now_iso, user_id))
                if field == "status" and value == "disabled":
                    conn.execute("UPDATE sessions SET is_revoked = 1 WHERE user_id = ?", (user_id,))
                if field == "role":
                    # Sessions carry the role they were issued with; make the change effective now
                    conn.execute("UPDATE sessions SET user_role = ? WHERE user_id = ?", (value, user_id))
        finally:
            conn.close()
        self.send_json_response(200, {"success": True, field: value})
