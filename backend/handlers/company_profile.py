"""Company profile: editing by the owner, subscribers, the company's own subscriptions, my companies."""
import datetime
import json
import urllib.parse

from backend.companies import (
    SUBSCRIPTION_TARGETS,
    company_material_counts,
    is_company_owner,
    list_company_subscriptions,
    parse_directions,
    validate_company_fields,
)
from backend.config import MAX_JSON_BODY_BYTES
from backend.content import TOPICS_TITLE_MAP
from backend.media_library import focal_dict


class CompanyProfileHandlers:
    def _company_or_404(self, conn, company_id):
        row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        if not row:
            self.send_json_response(404, {"success": False, "error": "Компания не найдена"})
        return row

    def handle_get_company_profile(self, company_id):
        """GET /api/companies/<id>/profile: everything the company page needs in one response."""
        user = self.get_current_user()
        conn = self.get_db()
        try:
            row = self._company_or_404(conn, company_id)
            if not row:
                return
            counts = company_material_counts(conn, company_id)
            subscribers = conn.execute(
                "SELECT COUNT(*) FROM user_subscriptions WHERE target_type = 'company' AND target_id = ?",
                (company_id,)).fetchone()[0]
            members = conn.execute("SELECT COUNT(*) FROM company_members WHERE company_id = ?",
                                   (company_id,)).fetchone()[0]
            following = conn.execute("SELECT COUNT(*) FROM company_subscriptions WHERE company_id = ?",
                                     (company_id,)).fetchone()[0]
            rating = conn.execute("""
                SELECT COALESCE(SUM(v.value), 0) FROM article_votes v
                JOIN moderation_submissions ms ON ms.id = v.article_id OR ms.draft_id = v.article_id
                WHERE ms.status = 'approved' AND json_extract(ms.publication_settings, '$.companyId') = ?
            """, (company_id,)).fetchone()[0]
            owner = conn.execute("""
                SELECT u.id, COALESCE(NULLIF(TRIM(p.name), ''), u.login) AS name, p.avatar
                FROM users u LEFT JOIN user_profiles p ON p.user_id = u.id WHERE u.id = ?
            """, (row["owner_id"],)).fetchone()
            is_subscribed = False
            can_publish = False
            if user:
                is_subscribed = conn.execute("""
                    SELECT 1 FROM user_subscriptions WHERE user_id = ? AND target_type = 'company' AND target_id = ?
                """, (user["id"], company_id)).fetchone() is not None
                can_publish = user.get("role") == "admin" or row["owner_id"] == user["id"] or conn.execute(
                    "SELECT 1 FROM company_members WHERE company_id = ? AND user_id = ?",
                    (company_id, user["id"])).fetchone() is not None
            is_owner = bool(user) and row["owner_id"] == user["id"]
        finally:
            conn.close()

        self.send_json_response(200, {"success": True, "company": {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "about": row["about"] or "",
            "specialization": row["specialization"],
            "website": row["website"] or "",
            "logo": row["logo"],
            "cover": row["cover"] if "cover" in row.keys() else None,
            "coverFocal": focal_dict(row["cover_focal"]) if "cover_focal" in row.keys() else None,
            "directions": parse_directions(row["directions"]),
            "isVerified": bool(row["is_verified"]),
            "owner": {"id": owner["id"], "name": owner["name"], "avatar": owner["avatar"]} if owner else None,
            "stats": {
                "publications": counts["publications"],
                "questions": counts["questions"],
                "subscribers": subscribers,
                "members": members,
                "following": following,
                "rating": rating,
            },
            "isSubscribed": is_subscribed,
            "isOwner": is_owner,
            "canEdit": is_owner,
            "canPublish": can_publish,
            "createdAt": row["created_at"],
        }})

    def handle_update_company(self, company_id):
        """PUT /api/companies/<id>: the owner edits the profile."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация", "requireAuth": True})
            return
        data = self.read_json_body(MAX_JSON_BODY_BYTES)
        if data is None:
            return
        conn = self.get_db()
        try:
            if not self._company_or_404(conn, company_id):
                return
            if not is_company_owner(conn, company_id, user):
                self.send_json_response(403, {"success": False, "error": "Редактировать профиль может только владелец компании"})
                return
            clean, errors = validate_company_fields(data, partial=True)
            if errors:
                self.send_json_response(400, {"success": False, "error": next(iter(errors.values())), "fieldErrors": errors})
                return
            if not clean:
                self.send_json_response(400, {"success": False, "error": "Нет изменений"})
                return
            if "directions" in clean:
                clean["directions"] = json.dumps(clean["directions"], ensure_ascii=False)
            clean["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            assignments = ", ".join(f"{k} = ?" for k in clean)
            with conn:
                conn.execute(f"UPDATE companies SET {assignments} WHERE id = ?", list(clean.values()) + [company_id])
                if "name" in clean:
                    # Keep the stored titles of people's subscriptions in step with the new name
                    conn.execute("UPDATE user_subscriptions SET target_title = ? WHERE target_type = 'company' AND target_id = ?",
                                 (clean["name"], company_id))
        finally:
            conn.close()
        self.handle_get_company_profile(company_id)

    def handle_get_company_subscribers(self, company_id, parsed):
        """GET /api/companies/<id>/subscribers?limit=&offset="""
        query = urllib.parse.parse_qs(parsed.query)
        try:
            limit = max(1, min(int(query.get("limit", ["30"])[0]), 100))
            offset = max(0, int(query.get("offset", ["0"])[0]))
        except ValueError:
            limit, offset = 30, 0
        conn = self.get_db()
        try:
            if not self._company_or_404(conn, company_id):
                return
            rows = conn.execute("""
                SELECT s.user_id, s.created_at, u.login, u.status,
                       COALESCE(NULLIF(TRIM(p.name), ''), u.login, s.user_id) AS name, p.avatar, p.specialization
                FROM user_subscriptions s
                LEFT JOIN users u ON u.id = s.user_id
                LEFT JOIN user_profiles p ON p.user_id = s.user_id
                WHERE s.target_type = 'company' AND s.target_id = ?
                ORDER BY s.created_at DESC LIMIT ? OFFSET ?
            """, (company_id, limit + 1, offset)).fetchall()
        finally:
            conn.close()
        self.send_json_response(200, {
            "success": True,
            "items": [{
                "id": r["user_id"], "name": r["name"], "avatar": r["avatar"],
                "specialization": r["specialization"] or "", "since": r["created_at"],
            } for r in rows[:limit]],
            "hasMore": len(rows) > limit,
        })

    def handle_get_company_subscriptions(self, company_id):
        """GET /api/companies/<id>/subscriptions: who and what the company itself follows."""
        conn = self.get_db()
        try:
            if not self._company_or_404(conn, company_id):
                return
            items = list_company_subscriptions(conn, company_id)
        finally:
            conn.close()
        for item in items:
            if item["targetType"] == "topic":
                item["title"] = TOPICS_TITLE_MAP.get(item["targetId"], item["title"])
        self.send_json_response(200, {"success": True, "items": items})

    def handle_toggle_company_subscription(self, company_id):
        """
        POST /api/companies/<id>/subscriptions/toggle {targetType, targetId, action?}
        Only the owner manages the company's own subscriptions; they never touch the owner's personal ones.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация", "requireAuth": True})
            return
        data = self.read_json_body(MAX_JSON_BODY_BYTES)
        if data is None:
            return
        target_type = str(data.get("targetType") or "")
        target_id = str(data.get("targetId") or "").strip()
        action = str(data.get("action") or "toggle")
        if target_type not in SUBSCRIPTION_TARGETS or not target_id or action not in ("toggle", "subscribe", "unsubscribe"):
            self.send_json_response(400, {"success": False, "error": "Некорректная цель подписки"})
            return
        conn = self.get_db()
        try:
            if not self._company_or_404(conn, company_id):
                return
            if not is_company_owner(conn, company_id, user):
                self.send_json_response(403, {"success": False, "error": "Подписками компании управляет только владелец"})
                return
            if target_type == "company":
                if target_id == company_id:
                    self.send_json_response(400, {"success": False, "error": "Компания не может подписаться на себя"})
                    return
                target = conn.execute("SELECT name FROM companies WHERE id = ?", (target_id,)).fetchone()
                title = target["name"] if target else None
            elif target_type == "topic":
                title = TOPICS_TITLE_MAP.get(target_id)
            else:
                target = conn.execute("""
                    SELECT COALESCE(NULLIF(TRIM(p.name), ''), u.login) AS name FROM users u
                    LEFT JOIN user_profiles p ON p.user_id = u.id WHERE u.id = ? AND u.status != 'pending'
                """, (target_id,)).fetchone()
                title = target["name"] if target else None
            if not title:
                self.send_json_response(404, {"success": False, "error": "Цель подписки не найдена"})
                return
            existing = conn.execute("""
                SELECT id FROM company_subscriptions WHERE company_id = ? AND target_type = ? AND target_id = ?
            """, (company_id, target_type, target_id)).fetchone()
            subscribe = action == "subscribe" or (action == "toggle" and not existing)
            with conn:
                if subscribe:
                    conn.execute("""
                        INSERT OR IGNORE INTO company_subscriptions
                        (company_id, target_type, target_id, target_title, created_by, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (company_id, target_type, target_id, title, user["id"],
                          datetime.datetime.now(datetime.timezone.utc).isoformat()))
                else:
                    conn.execute("DELETE FROM company_subscriptions WHERE company_id = ? AND target_type = ? AND target_id = ?",
                                 (company_id, target_type, target_id))
        finally:
            conn.close()
        self.send_json_response(200, {"success": True, "subscribed": subscribe})

    def handle_get_my_companies(self):
        """GET /api/user/companies: companies the current user owns or belongs to."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация", "requireAuth": True})
            return
        conn = self.get_db()
        try:
            rows = conn.execute("""
                SELECT c.id, c.name, c.logo, c.specialization, c.owner_id,
                       CASE WHEN c.owner_id = ? THEN 'owner' ELSE COALESCE(m.role, 'member') END AS my_role
                FROM companies c
                LEFT JOIN company_members m ON m.company_id = c.id AND m.user_id = ?
                WHERE c.owner_id = ? OR m.user_id IS NOT NULL
                ORDER BY (c.owner_id = ?) DESC, c.name
            """, (user["id"], user["id"], user["id"], user["id"])).fetchall()
        finally:
            conn.close()
        self.send_json_response(200, {"success": True, "items": [{
            "id": r["id"], "name": r["name"], "logo": r["logo"], "specialization": r["specialization"],
            "role": r["my_role"], "canEdit": r["owner_id"] == user["id"],
        } for r in rows]})
