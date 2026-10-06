"""Account area: pinned material and account settings."""
import datetime
import json
import sqlite3
import urllib.parse

from backend.config import MAX_JSON_BODY_BYTES
from backend.content import TOPICS_TITLE_MAP, format_date_ru, make_content_snippet


class AccountHandlers:
    def get_user_pinned_material(self, cur, user_id: str, is_owner: bool = False):
        """
        Fetches the pinned publication or solution for user_id.
        Validates authorship, public status, and returns card DTO.
        For third-party visitors, invalid/unapproved pinned items are returned as None.
        For profile owners, unavailable items are returned with isUnavailable=True and explanation.
        """
        try:
            cur.execute(
                "SELECT target_type, target_id FROM user_pinned_materials WHERE user_id = ?",
                (user_id,)
            )
            row = cur.fetchone()
        except sqlite3.OperationalError:
            return None

        if not row:
            return None

        target_type = row["target_type"]
        target_id = row["target_id"]

        if target_type == "publication":
            cur.execute("""
                SELECT id, draft_id, title, publication_settings, created_at, status, author_id, article_html AS content
                FROM moderation_submissions
                WHERE (id = ? OR (draft_id IS NOT NULL AND draft_id = ?))
                LIMIT 1
            """, (target_id, target_id))
            pub = cur.fetchone()
            if not pub:
                if is_owner:
                    return {
                        "targetType": "publication",
                        "targetId": target_id,
                        "id": target_id,
                        "isUnavailable": True,
                        "reason": "Материал был удален"
                    }
                return None

            if pub["author_id"] != user_id or pub["status"] != "approved":
                if is_owner:
                    return {
                        "targetType": "publication",
                        "targetId": pub["id"],
                        "id": pub["id"],
                        "title": pub["title"],
                        "isUnavailable": True,
                        "reason": "Материал не опубликован или находится на модерации"
                    }
                return None

            try:
                pst = json.loads(pub["publication_settings"]) if pub["publication_settings"] else {}
            except Exception:
                pst = {}
            mtype = (pst.get("materialType") or pst.get("type") or "publication").strip().lower()
            if mtype == "question":
                if is_owner:
                    return {
                        "targetType": "publication",
                        "targetId": pub["id"],
                        "id": pub["id"],
                        "title": pub["title"],
                        "isUnavailable": True,
                        "reason": "Вопросы нельзя закреплять в профиле"
                    }
                return None

            cur.execute("""
                SELECT COALESCE(SUM(value), 0) AS val FROM article_votes
                WHERE article_id = ? OR (? IS NOT NULL AND article_id = ?)
            """, (pub["id"], pub["draft_id"], pub["draft_id"]))
            score = cur.fetchone()["val"] or 0

            cur.execute("""
                SELECT COUNT(DISTINCT id) AS cnt FROM article_comments
                WHERE (article_id = ? OR (? IS NOT NULL AND article_id = ?)) AND status = 'published'
            """, (pub["id"], pub["draft_id"], pub["draft_id"]))
            c_cnt = cur.fetchone()["cnt"] or 0

            topics = pst.get("topics") or []
            first_topic = topics[0] if (isinstance(topics, list) and topics) else (topics if isinstance(topics, str) else None)
            topic_title = TOPICS_TITLE_MAP.get(first_topic, first_topic) if first_topic else None

            snippet = make_content_snippet(pub["content"])

            return {
                "targetType": "publication",
                "targetId": pub["id"],
                "id": pub["id"],
                "title": pub["title"],
                "type": "publication",
                "materialType": "publication",
                "material_type": "publication",
                "topic": first_topic,
                "topicTitle": topic_title,
                "contentSnippet": snippet,
                "rating": int(score),
                "score": int(score),
                "commentsCount": int(c_cnt),
                "createdAt": pub["created_at"],
                "date": format_date_ru(pub["created_at"]),
                "url": f"article.html?id={urllib.parse.quote(pub['id'])}",
                "isUnavailable": False
            }

        elif target_type == "solution":
            cur.execute("""
                SELECT ac.id, ac.article_id, ac.user_id, ac.content, ac.created_at, ac.is_solution, ac.status,
                       ms.title AS question_title, ms.status AS question_status, ms.publication_settings
                FROM article_comments ac
                LEFT JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                WHERE ac.id = ?
            """, (target_id,))
            sol = cur.fetchone()
            if not sol:
                if is_owner:
                    return {
                        "targetType": "solution",
                        "targetId": target_id,
                        "id": target_id,
                        "isUnavailable": True,
                        "reason": "Решение было удалено"
                    }
                return None

            if (sol["user_id"] != user_id or
                sol["is_solution"] != 1 or
                sol["status"] != "published" or
                sol["question_status"] != "approved"):
                if is_owner:
                    return {
                        "targetType": "solution",
                        "targetId": sol["id"],
                        "id": sol["id"],
                        "title": sol["question_title"] or "Решение вопроса",
                        "isUnavailable": True,
                        "reason": "Ответ больше не является решением или вопрос не опубликован"
                    }
                return None

            cur.execute("""
                SELECT COALESCE(SUM(value), 0) AS val FROM comment_votes WHERE comment_id = ?
            """, (sol["id"],))
            score = cur.fetchone()["val"] or 0

            pst = {}
            try:
                pst = json.loads(sol["publication_settings"]) if sol["publication_settings"] else {}
            except Exception:
                pass
            topics = pst.get("topics") or []
            first_topic = topics[0] if (isinstance(topics, list) and topics) else (topics if isinstance(topics, str) else None)
            topic_title = TOPICS_TITLE_MAP.get(first_topic, first_topic) if first_topic else None

            snippet = make_content_snippet(sol["content"])

            return {
                "targetType": "solution",
                "targetId": sol["id"],
                "id": sol["id"],
                "questionId": sol["article_id"],
                "title": sol["question_title"] or "Решение вопроса",
                "type": "solution",
                "materialType": "solution",
                "material_type": "solution",
                "topic": first_topic,
                "topicTitle": topic_title,
                "contentSnippet": snippet,
                "rating": int(score),
                "score": int(score),
                "isSolution": True,
                "createdAt": sol["created_at"],
                "date": format_date_ru(sol["created_at"]),
                "url": f"article.html?id={urllib.parse.quote(sol['article_id'])}#comment-{urllib.parse.quote(sol['id'])}",
                "isUnavailable": False
            }

        return None

    def handle_get_user_pinned(self):
        """
        GET /api/user/pinned
        Returns the authenticated user's pinned material.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Необходимо войти",
                "requireAuth": True
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                pinned_dto = self.get_user_pinned_material(cur, user["id"], is_owner=True)
                self.send_json_response(200, {
                    "success": True,
                    "pinnedMaterial": pinned_dto
                })
        finally:
            conn.close()

    def handle_post_user_pinned(self):
        """
        POST /api/user/pinned
        Body: { targetType: 'publication'|'solution', targetId: '...' }
        or { action: 'unpin' }
        """
        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для закрепления материала необходимо войти",
                "requireAuth": True
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                action = payload.get("action")
                target_type = (payload.get("targetType") or payload.get("type") or "").strip().lower()
                target_id = (payload.get("targetId") or payload.get("id") or "").strip()

                if action == "unpin" or (not target_id and not target_type):
                    cur.execute("DELETE FROM user_pinned_materials WHERE user_id = ?", (user["id"],))
                    self.send_json_response(200, {
                        "success": True,
                        "message": "Материал откреплен",
                        "pinnedMaterial": None
                    })
                    return

                if target_type not in ("publication", "solution"):
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Недопустимый тип материала. Разрешены только publication или solution"
                    })
                    return

                if not target_id:
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Не указан targetId"
                    })
                    return

                canonical_id = target_id
                if target_type == "publication":
                    cur.execute("""
                        SELECT id, draft_id, author_id, status, publication_settings
                        FROM moderation_submissions
                        WHERE id = ? OR (draft_id IS NOT NULL AND draft_id = ?)
                        LIMIT 1
                    """, (target_id, target_id))
                    pub = cur.fetchone()
                    if not pub:
                        self.send_json_response(404, {
                            "success": False,
                            "error": "Публикация не найдена"
                        })
                        return

                    if pub["author_id"] != user["id"]:
                        self.send_json_response(403, {
                            "success": False,
                            "error": "Нельзя закрепить чужой материал"
                        })
                        return

                    if pub["status"] != "approved":
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Нельзя закрепить неопубликованный материал"
                        })
                        return

                    try:
                        pst = json.loads(pub["publication_settings"]) if pub["publication_settings"] else {}
                    except Exception:
                        pst = {}
                    mtype = (pst.get("materialType") or pst.get("type") or "publication").strip().lower()
                    if mtype == "question":
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Вопросы нельзя закреплять в профиле"
                        })
                        return

                    canonical_id = pub["id"]

                elif target_type == "solution":
                    cur.execute("""
                        SELECT ac.id, ac.user_id, ac.is_solution, ac.status, ms.status AS question_status
                        FROM article_comments ac
                        LEFT JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                        WHERE ac.id = ?
                    """, (target_id,))
                    sol = cur.fetchone()
                    if not sol:
                        self.send_json_response(404, {
                            "success": False,
                            "error": "Ответ не найден"
                        })
                        return

                    if sol["user_id"] != user["id"]:
                        self.send_json_response(403, {
                            "success": False,
                            "error": "Нельзя закрепить чужой ответ"
                        })
                        return

                    if sol["is_solution"] != 1:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Можно закреплять только ответы, принятые как решение"
                        })
                        return

                    if sol["status"] != "published":
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Ответ не опубликован"
                        })
                        return

                    if sol["question_status"] != "approved":
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Вопрос с решением не опубликован"
                        })
                        return

                    canonical_id = sol["id"]

                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cur.execute("""
                    INSERT INTO user_pinned_materials (user_id, target_type, target_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        target_type = excluded.target_type,
                        target_id = excluded.target_id,
                        updated_at = excluded.updated_at
                """, (user["id"], target_type, canonical_id, now_iso, now_iso))

                pinned_dto = self.get_user_pinned_material(cur, user["id"], is_owner=True)
                self.send_json_response(200, {
                    "success": True,
                    "message": "Материал успешно закреплен",
                    "pinnedMaterial": pinned_dto
                })
        finally:
            conn.close()

    def handle_delete_user_pinned(self):
        """
        DELETE /api/user/pinned
        Removes the user's pinned material.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для открепления материала необходимо войти",
                "requireAuth": True
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM user_pinned_materials WHERE user_id = ?", (user["id"],))
                self.send_json_response(200, {
                    "success": True,
                    "message": "Материал успешно откреплен",
                    "pinnedMaterial": None
                })
        finally:
            conn.close()

    def handle_get_user_settings(self):
        """GET /api/user/settings"""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация",
                "requireAuth": True
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                # user is already fetched by get_current_user, but we need email, etc. Wait, get_current_user might return some of these?
                # Let's just query what we need.
                cur.execute("""
                    SELECT u.id, u.login, u.email, u.email_verified_at,
                           p.name, p.first_name, p.last_name, p.bio,
                           p.specialization, p.company, p.website, p.avatar
                    FROM users u
                    LEFT JOIN user_profiles p ON u.id = p.user_id
                    WHERE u.id = ?
                """, (user["id"],))
                row = cur.fetchone()
                if not row:
                    self.send_json_response(404, {"success": False, "error": "Пользователь не найден"})
                    return
                
                settings = {
                    "id": row["id"],
                    "login": row["login"],
                    "email": row["email"],
                    "emailVerified": bool(row["email_verified_at"]),
                    "name": row["name"] or "",
                    "firstName": row["first_name"] or "",
                    "lastName": row["last_name"] or "",
                    "bio": row["bio"] or "",
                    "specialization": row["specialization"] or "",
                    "company": row["company"] or "",
                    "website": row["website"] or "",
                    "avatar": row["avatar"] or ""
                }
                self.send_json_response(200, {"success": True, "settings": settings})
        finally:
            conn.close()
