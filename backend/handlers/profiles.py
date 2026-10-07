"""Public user profiles, identity resolution, profile editing, subscribers."""
import datetime
import json
import sqlite3
import urllib.parse
from typing import Any, Dict

from backend import config
from backend.config import MAX_JSON_BODY_BYTES
from backend.content import TOPICS_TITLE_MAP, format_date_ru, make_content_snippet
from backend.identity import sync_comment_snapshots
from backend.media_library import focal_dict, is_upload_owned_by, record_upload
from backend.submissions import validate_cover_image


class ProfilesHandlers:
    def resolve_user_identity(self, cur, user_id: str, p_row=None) -> Dict[str, Any]:
        """
        Consistent user identity resolution across user profiles, sessions, and comments.
        """
        if p_row is None:
            cur.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
            p_row = cur.fetchone()

        author_name = p_row["name"] if p_row and p_row["name"] else None
        if not author_name:
            cur.execute("SELECT user_name FROM sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
            sn_row = cur.fetchone()
            if sn_row and sn_row["user_name"]:
                author_name = sn_row["user_name"]
        if not author_name:
            cur.execute("SELECT author_name FROM article_comments WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
            cn_row = cur.fetchone()
            if cn_row and cn_row["author_name"]:
                author_name = cn_row["author_name"]
        if not author_name:
            author_name = f"Пользователь #{user_id[:6]}"

        author_avatar = p_row["avatar"] if p_row and p_row["avatar"] else None
        company = p_row["company"] if p_row and p_row["company"] else ""
        specialization = p_row["specialization"] if p_row and p_row["specialization"] else ""
        author_initials = "".join([part[0].upper() for part in str(author_name).split()[:2]]) if author_name else "SC"

        return {
            "name": author_name,
            "avatar": author_avatar,
            "company": company,
            "specialization": specialization,
            "initials": author_initials,
        }

    def handle_get_user_profile(self, user_id: str):
        """
        GET /api/users/<user_id>
        Returns profile info, stats, publications, and subscription status.
        """
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "Не указан user_id"})
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
                p_row = cur.fetchone()

                # User existence check: user_profiles, sessions, moderation_submissions, article_comments
                user_exists = (p_row is not None)
                if not user_exists:
                    cur.execute("SELECT 1 FROM users WHERE id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True

                if not user_exists:
                    cur.execute("SELECT 1 FROM sessions WHERE user_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True

                if not user_exists:
                    cur.execute("SELECT 1 FROM moderation_submissions WHERE author_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True

                if not user_exists:
                    cur.execute("SELECT 1 FROM article_comments WHERE user_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True

                if not user_exists:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Пользователь не найден",
                        "code": "USER_NOT_FOUND"
                    })
                    return

                cur.execute("""
                    SELECT id, draft_id, title, publication_settings, created_at
                    FROM moderation_submissions
                    WHERE author_id = ? AND status = 'approved'
                    ORDER BY created_at DESC, id DESC
                """, (user_id,))
                pub_rows = cur.fetchall()

                cur.execute("""
                    SELECT COUNT(DISTINCT ac.id) AS total_answers,
                           SUM(CASE WHEN ac.is_solution = 1 THEN 1 ELSE 0 END) AS total_solutions
                    FROM article_comments ac
                    JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                    WHERE ac.user_id = ?
                      AND ac.status = 'published'
                      AND ac.comment_type = 'answer'
                      AND ms.status = 'approved'
                      AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question'
                """, (user_id,))
                c_stats = cur.fetchone()

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
                pub_score = cur.fetchone()["pub_score"] or 0

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
                comm_score = cur.fetchone()["comm_score"] or 0

                total_rating = int(pub_score) + int(comm_score)

                # Followers & following counts
                cur.execute("""
                    SELECT COUNT(*) AS cnt FROM user_subscriptions
                    WHERE target_type = 'author' AND target_id = ?
                """, (user_id,))
                followers_count = cur.fetchone()["cnt"] or 0

                cur.execute("""
                    SELECT COUNT(*) AS cnt FROM user_subscriptions
                    WHERE user_id = ? AND target_type = 'author'
                """, (user_id,))
                following_count = cur.fetchone()["cnt"] or 0

                # Registration / creation date (stable, do not fabricate today's timestamp)
                created_at_val = None
                if p_row and p_row["created_at"]:
                    created_at_val = p_row["created_at"]
                else:
                    cur.execute("SELECT created_at FROM sessions WHERE user_id = ? ORDER BY created_at ASC LIMIT 1", (user_id,))
                    s_row = cur.fetchone()
                    if s_row and s_row["created_at"]:
                        created_at_val = s_row["created_at"]
                    else:
                        cur.execute("SELECT created_at FROM moderation_submissions WHERE author_id = ? ORDER BY created_at ASC LIMIT 1", (user_id,))
                        m_row = cur.fetchone()
                        if m_row and m_row["created_at"]:
                            created_at_val = m_row["created_at"]
                        else:
                            cur.execute("SELECT created_at FROM article_comments WHERE user_id = ? ORDER BY created_at ASC LIMIT 1", (user_id,))
                            c_row = cur.fetchone()
                            if c_row and c_row["created_at"]:
                                created_at_val = c_row["created_at"]

                # Author identity resolution
                ident = self.resolve_user_identity(cur, user_id, p_row)
                author_name = ident["name"]
                author_avatar = ident["avatar"]
                author_initials = ident["initials"]
                company = ident["company"]
                specialization = ident["specialization"]

                curr_user = self.get_current_user()
                is_sub = False
                if curr_user:
                    cur.execute(
                        "SELECT id FROM user_subscriptions WHERE user_id = ? AND target_type = 'author' AND target_id = ?",
                        (curr_user["id"], user_id)
                    )
                    is_sub = bool(cur.fetchone())

            specialization = p_row["specialization"].strip() if p_row and p_row["specialization"] else ""
            company = p_row["company"] if p_row and p_row["company"] else ""
            bio = p_row["bio"] if p_row and p_row["bio"] else ""
            avatar = p_row["avatar"] if p_row and p_row["avatar"] else None
            cover = p_row["cover"] if p_row and "cover" in p_row.keys() and p_row["cover"] else None
            cover_focal = focal_dict(p_row["cover_focal"]) if p_row and "cover_focal" in p_row.keys() else None
            website = ""
            if p_row:
                try:
                    website = p_row["website"] or ""
                except (IndexError, KeyError):
                    website = ""

            pubs = []
            questions_count = 0
            publications_count = 0
            for pr in pub_rows:
                try:
                    pst = json.loads(pr["publication_settings"]) if pr["publication_settings"] else {}
                except Exception:
                    pst = {}
                mtype = pst.get("materialType") or pst.get("type") or "article"
                if mtype == "question":
                    questions_count += 1
                else:
                    publications_count += 1

                if len(pubs) < 10:
                    pubs.append({
                        "id": pr["id"],
                        "title": pr["title"],
                        "materialType": mtype,
                        "createdAt": pr["created_at"],
                        "date": format_date_ru(pr["created_at"])
                    })

            # Top contributions: 2-3 items with highest rating across approved publications and solutions
            # Query at most 4 top rated publications and 4 top rated solutions to avoid N+1 and full archive scans
            cur.execute("""
                SELECT ms.id, ms.draft_id, ms.title, ms.publication_settings, ms.created_at,
                       (SELECT COALESCE(SUM(v.value), 0)
                        FROM article_votes v
                        WHERE v.article_id = ms.id OR (ms.draft_id IS NOT NULL AND v.article_id = ms.draft_id)
                       ) AS rating,
                       (SELECT COUNT(DISTINCT ac.id)
                        FROM article_comments ac
                        WHERE (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                          AND ac.status = 'published'
                       ) AS comments_count
                FROM moderation_submissions ms
                WHERE ms.author_id = ? AND ms.status = 'approved'
                ORDER BY rating DESC, ms.created_at DESC, ms.id DESC
                LIMIT 4
            """, (user_id,))
            top_pub_rows = cur.fetchall()

            cand_pub_ids = [r["id"] for r in top_pub_rows]
            html_by_id = {}
            if cand_pub_ids:
                placeholders = ",".join("?" * len(cand_pub_ids))
                cur.execute(f"SELECT id, article_html FROM moderation_submissions WHERE id IN ({placeholders})", tuple(cand_pub_ids))
                html_by_id = {row["id"]: (row["article_html"] or "") for row in cur.fetchall()}

            top_contributions = []
            for pr in top_pub_rows:
                try:
                    pst = json.loads(pr["publication_settings"]) if pr["publication_settings"] else {}
                except Exception:
                    pst = {}
                mtype = (pst.get("materialType") or pst.get("type") or "publication").strip().lower()
                is_q = (mtype == "question")
                p_rating = int(pr["rating"] or 0)
                c_cnt = int(pr["comments_count"] or 0)
                art_content = html_by_id.get(pr["id"], "")

                top_contributions.append({
                    "id": pr["id"],
                    "type": "question" if is_q else "publication",
                    "materialType": "question" if is_q else "publication",
                    "material_type": "question" if is_q else "publication",
                    "title": pr["title"],
                    "contentSnippet": make_content_snippet(art_content),
                    "rating": p_rating,
                    "score": p_rating,
                    "commentsCount": c_cnt if not is_q else 0,
                    "answersCount": c_cnt if is_q else 0,
                    "isSolution": False,
                    "createdAt": pr["created_at"],
                    "date": format_date_ru(pr["created_at"]),
                    "url": f"article.html?id={urllib.parse.quote(pr['id'])}"
                })

            cur.execute("""
                SELECT ac.id, ac.article_id, ac.content, ac.created_at, ms.title AS question_title,
                       (SELECT COALESCE(SUM(v.value), 0) FROM comment_votes v WHERE v.comment_id = ac.id) AS rating
                FROM article_comments ac
                JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                WHERE ac.user_id = ?
                  AND ac.status = 'published'
                  AND ac.comment_type = 'answer'
                  AND ac.is_solution = 1
                  AND ms.status = 'approved'
                  AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question'
                GROUP BY ac.id
                ORDER BY rating DESC, ac.created_at DESC, ac.id DESC
                LIMIT 4
            """, (user_id,))
            for sol in cur.fetchall():
                top_contributions.append({
                    "id": sol["id"],
                    "questionId": sol["article_id"],
                    "type": "solution",
                    "materialType": "solution",
                    "material_type": "solution",
                    "title": sol["question_title"] or "Решение вопроса",
                    "contentSnippet": make_content_snippet(sol["content"]),
                    "rating": int(sol["rating"] or 0),
                    "score": int(sol["rating"] or 0),
                    "commentsCount": 0,
                    "answersCount": 0,
                    "isSolution": True,
                    "createdAt": sol["created_at"],
                    "date": format_date_ru(sol["created_at"]),
                    "url": f"article.html?id={urllib.parse.quote(sol['article_id'])}#comment-{urllib.parse.quote(sol['id'])}"
                })

            top_contributions.sort(key=lambda x: (x.get("rating", 0), x.get("createdAt") or "", x.get("id") or ""), reverse=True)

            is_own_profile = bool(curr_user and curr_user["id"] == user_id)
            pinned_material = self.get_user_pinned_material(cur, user_id, is_owner=is_own_profile)
            if pinned_material and not pinned_material.get("isUnavailable"):
                # Exclude pinned material from top contributions to prevent duplicate display
                p_id = pinned_material.get("id") or pinned_material.get("targetId")
                top_contributions = [tc for tc in top_contributions if tc.get("id") != p_id]
            top_contributions = top_contributions[:3]

            # Aggregated topics from author's approved publications
            topic_counts = {}
            for pr in pub_rows:
                try:
                    pst = json.loads(pr["publication_settings"]) if pr["publication_settings"] else {}
                except Exception:
                    pst = {}
                ts = pst.get("topics") or []
                if isinstance(ts, str):
                    ts = [ts]
                for t in ts:
                    if t and isinstance(t, str):
                        t_clean = t.strip()
                        if t_clean:
                            topic_counts[t_clean] = topic_counts.get(t_clean, 0) + 1
            topics_list = [{"id": tid, "title": TOPICS_TITLE_MAP.get(tid, tid), "count": cnt} for tid, cnt in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:8]]

            rating_formula_text = "Рейтинг складывается из голосов за материалы и обсуждения. Лайки не учитываются"
            profile_data = {
                "id": user_id,
                "userId": user_id,
                "name": author_name,
                "specialization": specialization,
                "company": company,
                "bio": bio,
                "avatar": avatar,
                "cover": cover,
                "coverFocal": cover_focal,
                "website": website,
                "createdAt": created_at_val,
                "date": format_date_ru(created_at_val) if created_at_val else None,
                "isSubscribed": is_sub,
                "isOwnProfile": is_own_profile,
                "rating": total_rating,
                "score": total_rating,
                "totalRating": total_rating,
                "karma": total_rating,
                "materialsRating": int(pub_score),
                "discussionsRating": int(comm_score),
                "ratingFormula": rating_formula_text,
                "publicationsCount": publications_count,
                "questionsCount": questions_count,
                "commentsCount": comments_count,
                "comments_count": comments_count,
                "followersCount": followers_count,
                "followingCount": following_count,
                "topics": topics_list,
                "pinnedMaterial": pinned_material,
                "stats": {
                    "rating": total_rating,
                    "score": total_rating,
                    "totalRating": total_rating,
                    "karma": total_rating,
                    "materialsRating": int(pub_score),
                    "discussionsRating": int(comm_score),
                    "ratingFormula": rating_formula_text,
                    "publicationsCount": publications_count,
                    "articlesCount": publications_count,
                    "questionsCount": questions_count,
                    "commentsCount": comments_count,
                    "comments_count": comments_count,
                    "followersCount": followers_count,
                    "followingCount": following_count,
                    "answersCount": (c_stats["total_answers"] or 0) if c_stats else 0,
                    "solutionsCount": (c_stats["total_solutions"] or 0) if c_stats else 0
                },
                "publications": pubs,
                "topContributions": top_contributions
            }

            resp_payload = {
                "success": True,
                "profile": profile_data,
                "user": profile_data,
                **profile_data
            }
            self.send_json_response(200, resp_payload)
        finally:
            conn.close()

    def handle_get_user_subscribers(self, user_id: str, parsed_url=None):
        """
        GET /api/users/<user_id>/subscribers
        Returns paginated list of subscribers (followers) for the specified author.
        Query params: limit (default 20, max 100), offset (default 0).
        """
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "Не указан user_id"})
            return

        query = urllib.parse.parse_qs(parsed_url.query) if parsed_url else {}
        try:
            limit = max(1, min(100, int(query.get("limit", [20])[0])))
        except ValueError:
            limit = 20
        try:
            offset = max(0, int(query.get("offset", [0])[0]))
        except ValueError:
            offset = 0

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
                user_exists = (cur.fetchone() is not None)
                if not user_exists:
                    cur.execute("SELECT 1 FROM sessions WHERE user_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True
                if not user_exists:
                    cur.execute("SELECT 1 FROM moderation_submissions WHERE author_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True
                if not user_exists:
                    cur.execute("SELECT 1 FROM article_comments WHERE user_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True

                if not user_exists:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Пользователь не найден",
                        "code": "USER_NOT_FOUND"
                    })
                    return

                cur.execute("""
                    SELECT COUNT(*) AS total
                    FROM user_subscriptions
                    WHERE target_type = 'author' AND target_id = ?
                """, (user_id,))
                total = cur.fetchone()["total"] or 0

                cur.execute("""
                    SELECT us.user_id, us.created_at, up.name, up.avatar, up.specialization, up.company
                    FROM user_subscriptions us
                    LEFT JOIN user_profiles up ON us.user_id = up.user_id
                    WHERE us.target_type = 'author' AND us.target_id = ?
                    ORDER BY us.created_at DESC, us.id DESC
                    LIMIT ? OFFSET ?
                """, (user_id, limit, offset))
                rows = cur.fetchall()

                curr_user = self.get_current_user()

                items = []
                for r in rows:
                    sub_uid = r["user_id"]
                    sub_name = (r["name"] or "").strip()
                    if not sub_name:
                        cur.execute("SELECT user_name FROM sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (sub_uid,))
                        s_row = cur.fetchone()
                        if s_row and s_row["user_name"]:
                            sub_name = s_row["user_name"].strip()
                    if not sub_name:
                        sub_name = f"Пользователь {sub_uid[:8]}" if len(sub_uid) >= 8 else sub_uid

                    avatar = r["avatar"] or None
                    initials = "".join([part[0].upper() for part in sub_name.split()[:2]]) if sub_name else "SC"
                    spec = r["specialization"] or "Участник сообщества"

                    is_following = False
                    if curr_user:
                        cur.execute(
                            "SELECT 1 FROM user_subscriptions WHERE user_id = ? AND target_type = 'author' AND target_id = ? LIMIT 1",
                            (curr_user["id"], sub_uid)
                        )
                        is_following = bool(cur.fetchone())

                    items.append({
                        "id": sub_uid,
                        "userId": sub_uid,
                        "name": sub_name,
                        "avatar": avatar,
                        "initials": initials,
                        "specialization": spec,
                        "company": r["company"] or "",
                        "isFollowing": is_following,
                        "isOwn": bool(curr_user and curr_user["id"] == sub_uid),
                        "url": f"profile.html?id={urllib.parse.quote(sub_uid)}"
                    })

                has_more = (offset + limit) < total
                self.send_json_response(200, {
                    "success": True,
                    "items": items,
                    "subscribers": items,
                    "total": total,
                    "totalCount": total,
                    "limit": limit,
                    "offset": offset,
                    "hasMore": has_more
                })
        finally:
            conn.close()

    def handle_get_user_profile_subscriptions(self, user_id: str, parsed_url=None):
        """
        GET /api/users/<user_id>/subscriptions
        Returns subscriptions of author.
        For own profile: returns authors and blogs (clubs) with separation.
        For other users: respects privacy (returns isPrivate: true, items: []).
        """
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "Не указан user_id"})
            return

        curr_user = self.get_current_user()
        is_own = bool(curr_user and curr_user["id"] == user_id)

        if not is_own:
            self.send_json_response(200, {
                "success": True,
                "isPrivate": True,
                "authors": [],
                "blogs": [],
                "items": [],
                "total": 0,
                "message": "Подписки пользователя скрыты настройками приватности"
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT us.target_type, us.target_id, us.target_title, us.created_at,
                           up.name AS author_name, up.avatar AS author_avatar, up.specialization AS author_spec,
                           c.title AS club_title, c.avatar AS club_avatar, c.description AS club_desc
                    FROM user_subscriptions us
                    LEFT JOIN user_profiles up ON (us.target_type = 'author' AND us.target_id = up.user_id)
                    LEFT JOIN clubs c ON (us.target_type IN ('club', 'company') AND us.target_id = c.id)
                    WHERE us.user_id = ?
                    ORDER BY us.id DESC
                """, (user_id,))
                rows = cur.fetchall()

                authors = []
                blogs = []
                for r in rows:
                    tt = r["target_type"]
                    tid = r["target_id"]
                    t_title = r["target_title"] or ""
                    if tt == "author":
                        name = r["author_name"] or t_title or tid
                        authors.append({
                            "id": tid,
                            "userId": tid,
                            "type": "author",
                            "name": name,
                            "title": name,
                            "avatar": r["author_avatar"] or None,
                            "specialization": r["author_spec"] or "Автор",
                            "url": f"profile.html?id={urllib.parse.quote(tid)}"
                        })
                    elif tt in ("club", "company"):
                        c_title = r["club_title"] or t_title or tid
                        blogs.append({
                            "id": tid,
                            "type": "blog",
                            "title": c_title,
                            "name": c_title,
                            "avatar": r["club_avatar"] or None,
                            "description": r["club_desc"] or "",
                            "url": f"feed.html?tab={urllib.parse.quote(tid)}"
                        })

                total = len(authors) + len(blogs)
                self.send_json_response(200, {
                    "success": True,
                    "isPrivate": False,
                    "authors": authors,
                    "blogs": blogs,
                    "clubs": blogs,
                    "items": authors + blogs,
                    "total": total
                })
        finally:
            conn.close()

    def handle_get_current_user_profile(self, parsed_url):
        """GET /api/user/profile for authenticated user."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Пользователь не авторизован",
                "requireAuth": True
            })
            return
        self.handle_get_user_profile(user["id"])

    def handle_post_user_profile(self):
        """
        POST /api/user/profile
        Updates specialization, company, bio, name, website, and avatar for the authenticated user.
        """
        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        if not isinstance(payload, dict):
            self.send_json_response(400, {
                "success": False,
                "error": "Тело запроса должно быть JSON-объектом"
            })
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для редактирования профиля необходимо войти",
                "requireAuth": True
            })
            return

        # Validate input types before conversion
        for field in ("name", "specialization", "company", "bio", "website", "avatar"):
            if field in payload and payload[field] is not None and not isinstance(payload[field], str):
                self.send_json_response(400, {
                    "success": False,
                    "error": f"Поле {field} должно быть строкой"
                })
                return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                try:
                    cur.execute("SELECT name, specialization, company, bio, avatar, website, first_name, last_name, created_at FROM user_profiles WHERE user_id = ?", (user["id"],))
                    existing_profile = cur.fetchone()
                except sqlite3.OperationalError:
                    cur.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user["id"],))
                    existing_profile = cur.fetchone()

                # 1. Validate name: 1..100 characters. Return 400 if empty.
                if "name" in payload:
                    raw_name = payload["name"]
                    name = raw_name.strip() if raw_name is not None else ""
                else:
                    name = (existing_profile["name"] if existing_profile and existing_profile["name"] else user.get("name") or "").strip()

                if not name or len(name) > 100:
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Имя обязательно для заполнения и должно содержать от 1 до 100 символов"
                    })
                    return

                # 2. Validate specialization: max 120 characters
                if "specialization" in payload:
                    raw_spec = payload["specialization"]
                    specialization = raw_spec.strip() if raw_spec is not None else ""
                else:
                    specialization = (existing_profile["specialization"] if existing_profile and existing_profile["specialization"] else "").strip()

                if len(specialization) > 120:
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Специализация не должна превышать 120 символов"
                    })
                    return

                # 3. Validate company: max 120 characters
                if "company" in payload:
                    raw_comp = payload["company"]
                    company = raw_comp.strip() if raw_comp is not None else ""
                else:
                    company = (existing_profile["company"] if existing_profile and existing_profile["company"] else "").strip()

                if len(company) > 120:
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Название компании не должно превышать 120 символов"
                    })
                    return

                # 4. Validate bio: max 1000 characters
                if "bio" in payload:
                    raw_bio = payload["bio"]
                    bio = raw_bio.strip() if raw_bio is not None else ""
                else:
                    bio = (existing_profile["bio"] if existing_profile and existing_profile["bio"] else "").strip()

                if len(bio) > 1000:
                    self.send_json_response(400, {
                        "success": False,
                        "error": "О себе не должно превышать 1000 символов"
                    })
                    return

                # 5. Validate website: max 300 characters, strictly http or https
                if "website" in payload:
                    raw_site = payload["website"]
                    website = raw_site.strip() if raw_site is not None else ""
                else:
                    existing_website = ""
                    if existing_profile:
                        try:
                            existing_website = existing_profile["website"] or ""
                        except (IndexError, KeyError):
                            existing_website = ""
                    website = existing_website.strip()

                if website:
                    if len(website) > 300:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Адрес сайта не должен превышать 300 символов"
                        })
                        return

                    parsed_url = urllib.parse.urlparse(website)
                    if parsed_url.scheme.lower() not in ("http", "https") or not parsed_url.netloc:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Адрес сайта должен использовать протокол http или https"
                        })
                        return

                # First/last name handling
                if "firstName" in payload:
                    first_name = (payload["firstName"] or "").strip()
                elif "first_name" in payload:
                    first_name = (payload["first_name"] or "").strip()
                else:
                    first_name = ""
                    if existing_profile and "first_name" in existing_profile.keys():
                        first_name = existing_profile["first_name"] or ""
                        
                if "lastName" in payload:
                    last_name = (payload["lastName"] or "").strip()
                elif "last_name" in payload:
                    last_name = (payload["last_name"] or "").strip()
                else:
                    last_name = ""
                    if existing_profile and "last_name" in existing_profile.keys():
                        last_name = existing_profile["last_name"] or ""

                # 6. Avatar handling:
                # - Check if removeAvatar is true or avatar is empty string: set avatar to None in db.
                # - If avatar is provided in payload (non-empty string): validate image format/parameters and update avatar.
                # - If avatar is omitted/None and removeAvatar is not true: preserve the existing avatar from user_profiles.
                remove_avatar = payload.get("removeAvatar") in (True, "true", "True", 1)
                raw_avatar = payload.get("avatar")

                if remove_avatar:
                    avatar = None
                elif "avatar" in payload and raw_avatar is not None:
                    stripped_avatar = raw_avatar.strip()
                    if not stripped_avatar:
                        avatar = None
                    elif existing_profile and existing_profile["avatar"] and stripped_avatar == existing_profile["avatar"]:
                        avatar = existing_profile["avatar"]
                    else:
                        media_root = getattr(self.server, "media_dir", config.MEDIA_DIR)
                        res = validate_cover_image(stripped_avatar, target_media_dir=media_root, require_exists=True)
                        if not res.is_valid:
                            self.send_json_response(400, {
                                "success": False,
                                "error": res.error_msg or "Аватар должен быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ."
                            })
                            return
                        if stripped_avatar.startswith("/media/") and not is_upload_owned_by(conn, stripped_avatar, user["id"]):
                            # Knowing the URL of someone else's upload does not allow taking it as an avatar
                            self.send_json_response(403, {
                                "success": False,
                                "error": "Можно использовать только изображения, загруженные вами"
                            })
                            return
                        avatar = res.saved_url
                        if not stripped_avatar.startswith("/media/"):
                            record_upload(conn, avatar, user["id"], res.meta)
                else:
                    avatar = existing_profile["avatar"] if existing_profile and existing_profile["avatar"] else None

                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                created_at_val = existing_profile["created_at"] if existing_profile and "created_at" in existing_profile.keys() and existing_profile["created_at"] else now_iso

                try:
                    cur.execute("""
                        INSERT INTO user_profiles (user_id, name, specialization, company, bio, avatar, website, first_name, last_name, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET
                            name = excluded.name,
                            specialization = excluded.specialization,
                            company = excluded.company,
                            bio = excluded.bio,
                            avatar = excluded.avatar,
                            website = excluded.website,
                            first_name = excluded.first_name,
                            last_name = excluded.last_name,
                            updated_at = excluded.updated_at
                    """, (user["id"], name, specialization, company, bio, avatar, website, first_name, last_name, created_at_val, now_iso))
                except sqlite3.OperationalError:
                    try:
                        cur.execute("""
                            INSERT INTO user_profiles (user_id, name, specialization, company, bio, avatar, website, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(user_id) DO UPDATE SET
                                name = excluded.name,
                                specialization = excluded.specialization,
                                company = excluded.company,
                                bio = excluded.bio,
                                avatar = excluded.avatar,
                                website = excluded.website,
                                updated_at = excluded.updated_at
                        """, (user["id"], name, specialization, company, bio, avatar, website, created_at_val, now_iso))
                    except sqlite3.OperationalError:
                        cur.execute("""
                            INSERT INTO user_profiles (user_id, name, specialization, company, bio, avatar, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(user_id) DO UPDATE SET
                                name = excluded.name,
                                specialization = excluded.specialization,
                                company = excluded.company,
                                bio = excluded.bio,
                                avatar = excluded.avatar,
                                updated_at = excluded.updated_at
                        """, (user["id"], name, specialization, company, bio, avatar, created_at_val, now_iso))

                # Synchronize user_name in sessions table across all active sessions of this user
                cur.execute("UPDATE sessions SET user_name = ? WHERE user_id = ?", (name, user["id"]))
                cur.execute("UPDATE users SET name = ? WHERE id = ?", (name, user["id"]))
                cur.execute("UPDATE users SET avatar = ? WHERE id = ?", (avatar, user["id"]))
                # Earlier comments show the author as they are now
                sync_comment_snapshots(cur, user["id"])

            initials = "".join([part[0].upper() for part in str(name).split()[:2]]) if name else "SC"
            profile_dto = {
                "id": user["id"],
                "userId": user["id"],
                "name": name,
                "specialization": specialization,
                "company": company,
                "bio": bio,
                "website": website or "",
                "avatar": avatar,
                "initials": initials
            }
            self.send_json_response(200, {
                "success": True,
                "profile": profile_dto,
                "user": profile_dto,
                **profile_dto
            })
        finally:
            conn.close()
