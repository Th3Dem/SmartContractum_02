"""Likes, saves, votes and reports on publications, questions and comments."""
import datetime
import json
import urllib.parse
import uuid

from backend.config import MAX_JSON_BODY_BYTES
from backend.content import format_date_ru
from backend.identity import author_identities


class EngagementHandlers:
    def handle_article_like_toggle(self, article_id: str = "", _body_already_read: bool = False):
        """
        POST /api/articles/<id>/like or POST /api/likes/toggle
        Toggles like for current user on the given article.
        Requires authentication (401 requireAuth).
        Returns { success: True, hasLiked: bool, likesCount: int }.
        """
        action = "toggle"
        if not _body_already_read:
            payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
            if payload is None:
                return
            if not article_id:
                article_id = payload.get("articleId") or payload.get("article_id") or ""
            action = payload.get("action", "toggle")

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для отметки «Нравится» необходимо войти",
                "requireAuth": True
            })
            return

        if not article_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор статьи"
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (article_id, article_id))
            art_row = cur.fetchone()
            if not art_row:
                self.send_json_response(404, {
                    "success": False,
                    "error": "Статья не найдена"
                })
                return

            real_art_id = art_row["id"]
            user_id = user["id"]

            cur.execute("SELECT id FROM article_likes WHERE article_id = ? AND user_id = ?", (real_art_id, user_id))
            existing_like = cur.fetchone()

            if action == "like":
                if existing_like:
                    has_liked = True
                else:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute(
                        "INSERT OR IGNORE INTO article_likes (article_id, user_id, created_at) VALUES (?, ?, ?)",
                        (real_art_id, user_id, now_iso)
                    )
                    has_liked = True
            elif action == "unlike":
                if existing_like:
                    cur.execute("DELETE FROM article_likes WHERE article_id = ? AND user_id = ?", (real_art_id, user_id))
                has_liked = False
            else:
                if existing_like:
                    cur.execute("DELETE FROM article_likes WHERE article_id = ? AND user_id = ?", (real_art_id, user_id))
                    has_liked = False
                else:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute(
                        "INSERT OR IGNORE INTO article_likes (article_id, user_id, created_at) VALUES (?, ?, ?)",
                        (real_art_id, user_id, now_iso)
                    )
                    has_liked = True

            cur.execute("SELECT COUNT(*) AS cnt FROM article_likes WHERE article_id = ?", (real_art_id,))
            likes_count = cur.fetchone()["cnt"]

        self.send_json_response(200, {
            "success": True,
            "hasLiked": has_liked,
            "isLiked": has_liked,
            "likesCount": likes_count,
            "articleId": real_art_id
        })

    def handle_article_save_toggle(self, article_id: str = "", action: str = "toggle", _body_already_read: bool = False):
        """
        POST /api/articles/<id>/save, POST /api/articles/<id>/unsave, POST /api/articles/<id>/bookmark, POST /api/saves/toggle
        Saves or unsaves an article for the current authenticated user.
        action can be 'save', 'unsave', or 'toggle'.
        Requires authentication (returns 401 with requireAuth: True if not logged in).
        Returns { success: True, isSaved: bool, hasSaved: bool, savesCount: int, articleId: str }.
        """
        if not _body_already_read:
            payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
            if payload is None:
                return
            if not article_id:
                article_id = payload.get("articleId") or payload.get("article_id") or ""
            if "action" in payload and payload["action"] in ("save", "unsave", "toggle"):
                action = payload["action"]

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для сохранения публикации необходимо войти",
                "requireAuth": True,
                "code": "AUTH_REQUIRED"
            })
            return

        if not article_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор статьи",
                "code": "INVALID_ARTICLE_ID"
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (article_id, article_id))
            art_row = cur.fetchone()
            if not art_row:
                self.send_json_response(404, {
                    "success": False,
                    "error": "Статья не найдена",
                    "code": "ARTICLE_NOT_FOUND"
                })
                return

            real_art_id = art_row["id"]
            user_id = user["id"]

            cur.execute("SELECT id FROM article_saves WHERE article_id = ? AND user_id = ?", (real_art_id, user_id))
            existing_save = cur.fetchone()

            if action == "save":
                if not existing_save:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute(
                        "INSERT OR IGNORE INTO article_saves (article_id, user_id, created_at) VALUES (?, ?, ?)",
                        (real_art_id, user_id, now_iso)
                    )
                is_saved = True
            elif action == "unsave":
                if existing_save:
                    cur.execute("DELETE FROM article_saves WHERE article_id = ? AND user_id = ?", (real_art_id, user_id))
                is_saved = False
            else:  # toggle
                if existing_save:
                    cur.execute("DELETE FROM article_saves WHERE article_id = ? AND user_id = ?", (real_art_id, user_id))
                    is_saved = False
                else:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute(
                        "INSERT OR IGNORE INTO article_saves (article_id, user_id, created_at) VALUES (?, ?, ?)",
                        (real_art_id, user_id, now_iso)
                    )
                    is_saved = True

            cur.execute("SELECT COUNT(*) AS cnt FROM article_saves WHERE article_id = ?", (real_art_id,))
            saves_count = cur.fetchone()["cnt"]

        self.send_json_response(200, {
            "success": True,
            "isSaved": is_saved,
            "hasSaved": is_saved,
            "savesCount": saves_count,
            "articleId": real_art_id
        })

    def handle_sync_saves(self):
        """
        POST /api/articles/sync-saves
        Idempotently migrates client bookmarks (from localStorage sc_bookmarks) to server.
        Requires authentication.
        Expects { "articleIds": ["art-1", "art-2", ...] } or list of strings.
        Returns { "success": True, "syncedCount": int, "totalSaved": int }.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для синхронизации закладок необходимо войти",
                "requireAuth": True,
                "code": "AUTH_REQUIRED"
            })
            return

        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        raw_ids = []
        if isinstance(payload, list):
            raw_ids = payload
        elif isinstance(payload, dict):
            raw_ids = payload.get("articleIds") or payload.get("ids") or payload.get("bookmarks") or []

        if not isinstance(raw_ids, list):
            self.send_json_response(400, {
                "success": False,
                "error": "Неверный формат списка статей",
                "code": "INVALID_ARTICLE_IDS"
            })
            return

        user_id = user["id"]
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        synced = 0

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            for raw_id in raw_ids:
                if not isinstance(raw_id, str) or not raw_id.strip():
                    continue
                aid = raw_id.strip()
                cur.execute("SELECT id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (aid, aid))
                row = cur.fetchone()
                if row:
                    real_id = row["id"]
                    cur.execute(
                        "INSERT OR IGNORE INTO article_saves (article_id, user_id, created_at) VALUES (?, ?, ?)",
                        (real_id, user_id, now_iso)
                    )
                    if cur.rowcount > 0:
                        synced += 1

            cur.execute("SELECT COUNT(*) AS cnt FROM article_saves WHERE user_id = ?", (user_id,))
            total_saved = cur.fetchone()["cnt"]

        self.send_json_response(200, {
            "success": True,
            "syncedCount": synced,
            "totalSaved": total_saved
        })

    def handle_comment_save_toggle(self, comment_id: str = "", action: str = "toggle", _body_already_read: bool = False):
        """
        POST /api/comments/<id>/save, POST /api/comments/<id>/unsave, POST /api/comments/<id>/bookmark
        Toggles, saves or unsaves a comment for the current authenticated user.
        """
        if not _body_already_read:
            payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
            if payload is None:
                return
            if not comment_id:
                comment_id = payload.get("commentId") or payload.get("comment_id") or ""
            if "action" in payload and payload["action"] in ("save", "unsave", "toggle"):
                action = payload["action"]

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для сохранения комментария необходимо войти",
                "requireAuth": True,
                "code": "AUTH_REQUIRED"
            })
            return

        if not comment_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор комментария",
                "code": "INVALID_COMMENT_ID"
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id, article_id FROM article_comments WHERE id = ? LIMIT 1", (comment_id,))
            comm_row = cur.fetchone()
            if not comm_row:
                self.send_json_response(404, {
                    "success": False,
                    "error": "Комментарий не найден",
                    "code": "COMMENT_NOT_FOUND"
                })
                return

            real_comm_id = comm_row["id"]
            user_id = user["id"]

            cur.execute("SELECT id FROM comment_saves WHERE comment_id = ? AND user_id = ?", (real_comm_id, user_id))
            existing_save = cur.fetchone()

            if action == "save":
                if not existing_save:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute(
                        "INSERT OR IGNORE INTO comment_saves (comment_id, user_id, created_at) VALUES (?, ?, ?)",
                        (real_comm_id, user_id, now_iso)
                    )
                is_saved = True
            elif action == "unsave":
                if existing_save:
                    cur.execute("DELETE FROM comment_saves WHERE comment_id = ? AND user_id = ?", (real_comm_id, user_id))
                is_saved = False
            else:
                if existing_save:
                    cur.execute("DELETE FROM comment_saves WHERE comment_id = ? AND user_id = ?", (real_comm_id, user_id))
                    is_saved = False
                else:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute(
                        "INSERT OR IGNORE INTO comment_saves (comment_id, user_id, created_at) VALUES (?, ?, ?)",
                        (real_comm_id, user_id, now_iso)
                    )
                    is_saved = True

            cur.execute("SELECT COUNT(*) AS cnt FROM comment_saves WHERE comment_id = ?", (real_comm_id,))
            saves_count = cur.fetchone()["cnt"]

        self.send_json_response(200, {
            "success": True,
            "commentId": real_comm_id,
            "isSaved": is_saved,
            "hasSaved": is_saved,
            "savesCount": saves_count
        })

    def handle_comment_saves_sync(self):
        """
        POST /api/comments/sync-saves
        Migrates client-side bookmark IDs into server comment_saves table for authenticated user.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для синхронизации закладок необходимо войти",
                "requireAuth": True
            })
            return

        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        comment_ids = payload.get("commentIds") or payload.get("ids") or []
        if not isinstance(comment_ids, list):
            self.send_json_response(400, {"success": False, "error": "commentIds must be a list"})
            return

        user_id = user["id"]
        synced = 0
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            for cid in comment_ids:
                if not isinstance(cid, str) or not cid.strip():
                    continue
                cid = cid.strip()
                cur.execute("SELECT id FROM article_comments WHERE id = ? LIMIT 1", (cid,))
                if cur.fetchone():
                    cur.execute(
                        "INSERT OR IGNORE INTO comment_saves (comment_id, user_id, created_at) VALUES (?, ?, ?)",
                        (cid, user_id, now_iso)
                    )
                    if cur.rowcount > 0:
                        synced += 1

            cur.execute("SELECT COUNT(*) AS cnt FROM comment_saves WHERE user_id = ?", (user_id,))
            total_saved = cur.fetchone()["cnt"]

        self.send_json_response(200, {
            "success": True,
            "syncedCount": synced,
            "totalSaved": total_saved
        })

    def handle_get_saved_comments(self):
        """
        GET /api/comments/saved
        Returns list of saved comments for current user.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(200, {"success": True, "items": [], "total": 0})
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT cs.comment_id, cs.created_at AS saved_at,
                       c.id, c.article_id, c.user_id AS author_id, c.author_name, c.author_avatar,
                       c.content AS text, c.created_at, c.comment_type,
                       m.title AS article_title,
                       (SELECT COUNT(*) FROM comment_saves cs2 WHERE cs2.comment_id = c.id) AS saves_count
                FROM comment_saves cs
                JOIN article_comments c ON cs.comment_id = c.id
                LEFT JOIN moderation_submissions m ON (c.article_id = m.id OR c.article_id = m.draft_id)
                WHERE cs.user_id = ? AND c.status = 'published'
                ORDER BY cs.created_at DESC
            """, (user["id"],))
            rows = cur.fetchall()

        items = []
        for r in rows:
            art_id = r["article_id"] or ""
            comm_id = r["id"] or ""
            items.append({
                "id": comm_id,
                "articleId": art_id,
                "articleTitle": r["article_title"] or "Материал сообщества",
                "permalink": f"article.html?id={art_id}#comment-{comm_id}",
                "authorId": r["author_id"],
                "authorName": r["author_name"],
                "authorAvatar": r["author_avatar"],
                "text": r["text"],
                "createdAt": r["created_at"],
                "commentType": r["comment_type"] or "comment",
                "isSaved": True,
                "hasSaved": True,
                "savesCount": r["saves_count"] or 1
            })

        self.send_json_response(200, {
            "success": True,
            "items": items,
            "total": len(items)
        })

    def handle_get_saved_counts(self):
        """
        GET /api/saved/counts
        Returns aggregated counts for Saved Hub without N+1 queries.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(200, {
                "success": True,
                "total": 0,
                "publications": 0,
                "questions": 0,
                "comments": 0
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                  (SELECT COUNT(DISTINCT s.article_id)
                   FROM article_saves s
                   JOIN moderation_submissions m ON (s.article_id = m.id OR s.article_id = m.draft_id)
                   WHERE s.user_id = ?
                     AND COALESCE(json_extract(m.publication_settings, '$.materialType'), json_extract(m.publication_settings, '$.type'), 'publication') != 'question'
                  ) as pubs_count,
                  (SELECT COUNT(DISTINCT s.article_id)
                   FROM article_saves s
                   JOIN moderation_submissions m ON (s.article_id = m.id OR s.article_id = m.draft_id)
                   WHERE s.user_id = ?
                     AND COALESCE(json_extract(m.publication_settings, '$.materialType'), json_extract(m.publication_settings, '$.type'), 'publication') = 'question'
                  ) as questions_count,
                  (SELECT COUNT(*) FROM comment_saves WHERE user_id = ?) as comments_count
            """, (user["id"], user["id"], user["id"]))
            row = cur.fetchone()
            pubs = row["pubs_count"] or 0
            questions = row["questions_count"] or 0
            comments = row["comments_count"] or 0
            total = pubs + questions + comments

        self.send_json_response(200, {
            "success": True,
            "total": total,
            "publications": pubs,
            "questions": questions,
            "comments": comments
        })

    def handle_get_saved(self, parsed_url):
        """
        GET /api/saved
        Unified Saved Hub endpoint returning saved materials and comments for current user.
        Query params:
          type: 'all' (default), 'publications', 'questions', 'comments'
          search: search string across title, description, content, author
          limit: int (default 20, max 100)
          offset: int (default 0)
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для просмотра сохраненных материалов необходимо войти",
                "requireAuth": True,
                "code": "AUTH_REQUIRED"
            })
            return

        query = urllib.parse.parse_qs(parsed_url.query)
        stype = (query.get("type", ["all"])[0] or "all").strip().lower()
        search_q = (query.get("search", [""])[0] or query.get("q", [""])[0] or "").strip().lower()
        try:
            limit = max(1, min(100, int(query.get("limit", [20])[0])))
        except ValueError:
            limit = 20
        try:
            offset = max(0, int(query.get("offset", [0])[0]))
        except ValueError:
            offset = 0

        user_id = user["id"]
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            # 1. Aggregated counts
            cur.execute("""
                SELECT
                  (SELECT COUNT(DISTINCT s.article_id)
                   FROM article_saves s
                   JOIN moderation_submissions m ON (s.article_id = m.id OR s.article_id = m.draft_id)
                   WHERE s.user_id = ?
                     AND COALESCE(json_extract(m.publication_settings, '$.materialType'), json_extract(m.publication_settings, '$.type'), 'publication') != 'question'
                  ) as pubs_count,
                  (SELECT COUNT(DISTINCT s.article_id)
                   FROM article_saves s
                   JOIN moderation_submissions m ON (s.article_id = m.id OR s.article_id = m.draft_id)
                   WHERE s.user_id = ?
                     AND COALESCE(json_extract(m.publication_settings, '$.materialType'), json_extract(m.publication_settings, '$.type'), 'publication') = 'question'
                  ) as questions_count,
                  (SELECT COUNT(*) FROM comment_saves WHERE user_id = ?) as comments_count
            """, (user_id, user_id, user_id))
            crow = cur.fetchone()
            pubs_cnt = crow["pubs_count"] or 0
            questions_cnt = crow["questions_count"] or 0
            comments_cnt = crow["comments_count"] or 0
            total_cnt = pubs_cnt + questions_cnt + comments_cnt
            counts = {
                "total": total_cnt,
                "publications": pubs_cnt,
                "questions": questions_cnt,
                "comments": comments_cnt
            }

            items = []
            # 2. Fetch comments if requested
            if stype in ("comments", "comment", "all"):
                cur.execute("""
                    SELECT cs.comment_id, cs.created_at AS saved_at,
                           c.id, c.article_id, c.user_id AS author_id, c.author_name, c.author_avatar,
                           c.content AS text, c.created_at, c.comment_type,
                           m.title AS article_title,
                           (SELECT COUNT(*) FROM comment_saves cs2 WHERE cs2.comment_id = c.id) AS saves_count
                    FROM comment_saves cs
                    JOIN article_comments c ON cs.comment_id = c.id
                    LEFT JOIN moderation_submissions m ON (c.article_id = m.id OR c.article_id = m.draft_id)
                    WHERE cs.user_id = ? AND c.status = 'published'
                    ORDER BY cs.created_at DESC
                """, (user_id,))
                crows = cur.fetchall()
                for cr in crows:
                    cid = cr["id"] or ""
                    aid = cr["article_id"] or ""
                    art_title = cr["article_title"] or "Материал сообщества"
                    text = cr["text"] or ""
                    aname = cr["author_name"] or "Пользователь"
                    if search_q:
                        if search_q not in text.lower() and search_q not in art_title.lower() and search_q not in aname.lower():
                            continue
                    items.append({
                        "id": cid,
                        "entityType": "comment",
                        "articleId": aid,
                        "articleTitle": art_title,
                        "permalink": f"article.html?id={aid}#comment-{cid}",
                        "authorId": cr["author_id"],
                        "authorName": aname,
                        "authorAvatar": cr["author_avatar"],
                        "text": text,
                        "createdAt": cr["created_at"],
                        "date": format_date_ru(cr["created_at"]),
                        "savedAt": cr["saved_at"],
                        "commentType": cr["comment_type"] or "comment",
                        "isSaved": True,
                        "hasSaved": True,
                        "savesCount": cr["saves_count"] or 1
                    })

            # 3. Fetch articles if requested
            if stype in ("publications", "publication", "questions", "question", "all"):
                cur.execute("""
                    SELECT s.article_id, s.created_at AS saved_at,
                           m.id, m.draft_id, m.title, m.author_id,
                           m.created_at, m.publication_settings,
                           (SELECT COUNT(*) FROM article_saves s2 WHERE s2.article_id = m.id OR s2.article_id = m.draft_id) AS saves_count
                    FROM article_saves s
                    JOIN moderation_submissions m ON (s.article_id = m.id OR s.article_id = m.draft_id)
                    WHERE s.user_id = ? AND m.status IN ('approved', 'published')
                    ORDER BY s.created_at DESC
                """, (user_id,))
                arows = cur.fetchall()
                for ar in arows:
                    aid = ar["id"] or ""
                    settings = {}
                    if ar["publication_settings"]:
                        try:
                            settings = json.loads(ar["publication_settings"])
                        except Exception:
                            settings = {}
                    raw_mat_type = (settings.get("materialType") or settings.get("type") or "publication").strip().lower()
                    if raw_mat_type in ("article", "post", "news", "pubs"):
                        mat_type = "publication"
                    else:
                        mat_type = raw_mat_type
                    is_question = (mat_type == "question")
                    if stype in ("questions", "question") and not is_question:
                        continue
                    if stype in ("publications", "publication") and is_question:
                        continue

                    title = ar["title"] or ""
                    desc = settings.get("description") or ""
                    raw_author = settings.get("author") or settings.get("authorName")
                    if isinstance(raw_author, dict):
                        author_name = raw_author.get("name") or "Пользователь"
                        author_avatar = raw_author.get("avatar") or settings.get("authorAvatar")
                    else:
                        author_name = raw_author or "Пользователь"
                        author_avatar = settings.get("authorAvatar")
                    live = author_identities(cur, [ar["author_id"]]).get(ar["author_id"]) or {}
                    author_name = live.get("name") or author_name
                    author_avatar = live.get("avatar") or author_avatar
                    cover_image = settings.get("coverImage")
                    if search_q:
                        if search_q not in title.lower() and search_q not in desc.lower() and search_q not in author_name.lower():
                            continue

                    topics = settings.get("topics") or ([settings["topic"]] if settings.get("topic") else [])
                    tags = settings.get("keywords") or settings.get("tags") or []
                    items.append({
                        "id": aid,
                        "entityType": "question" if is_question else "publication",
                        "title": title,
                        "description": desc,
                        "author": author_name,
                        "authorId": ar["author_id"],
                        "authorAvatar": author_avatar,
                        "cover": cover_image,
                        "date": format_date_ru(ar["created_at"]),
                        "createdAt": ar["created_at"],
                        "savedAt": ar["saved_at"],
                        "topics": topics,
                        "keywords": tags,
                        "tags": tags,
                        "format": settings.get("format") or ("question" if is_question else "article"),
                        "type": "question" if is_question else "article",
                        "materialType": "question" if is_question else "publication",
                        "complexity": settings.get("complexity") or "none",
                        "isSaved": True,
                        "hasSaved": True,
                        "savesCount": ar["saves_count"] or 1
                    })

            # Sort items by savedAt DESC
            items.sort(key=lambda x: x.get("savedAt") or "", reverse=True)
            total_items = len(items)
            paged_items = items[offset: offset + limit]

        self.send_json_response(200, {
            "success": True,
            "items": paged_items,
            "total": total_items,
            "counts": counts,
            "limit": limit,
            "offset": offset,
            "hasMore": (offset + limit) < total_items
        })

    def handle_article_vote(self, raw_id: str):
        """
        POST /api/articles/<id>/vote
        Registers or cancels vote (-1, 0, 1) for the specified article.
        Requires authenticated session (401 AUTH_REQUIRED).
        Prevents self-voting by the author (403 SELF_VOTE_FORBIDDEN).
        Resolves canonical article ID from id or draft_id.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация",
                "code": "AUTH_REQUIRED",
                "requireAuth": True
            })
            return

        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if payload is None:
            return

        if not isinstance(payload, dict) or "value" not in payload:
            self.send_json_response(400, {
                "success": False,
                "error": "Значение голоса должно быть -1, 0 или 1",
                "code": "INVALID_VOTE_VALUE"
            })
            return

        val = payload.get("value")
        if type(val) is not int or isinstance(val, bool) or val not in (-1, 0, 1):
            self.send_json_response(400, {
                "success": False,
                "error": "Значение голоса должно быть -1, 0 или 1",
                "code": "INVALID_VOTE_VALUE"
            })
            return

        if not raw_id:
            self.send_json_response(404, {
                "success": False,
                "error": "Публикация не найдена",
                "code": "NOT_FOUND"
            })
            return

        conn = self.get_db()
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, draft_id, author_id, status FROM moderation_submissions WHERE (id = ? OR draft_id = ?) LIMIT 1",
                    (raw_id, raw_id)
                )
                art_row = cur.fetchone()
                if not art_row or art_row["status"] != "approved":
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Публикация не найдена",
                        "code": "NOT_FOUND"
                    })
                    return

                canonical_id = art_row["id"]
                if art_row["author_id"] == user["id"]:
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Нельзя голосовать за собственную публикацию",
                        "code": "SELF_VOTE_FORBIDDEN"
                    })
                    return

                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                if val in (-1, 1):
                    cur.execute("""
                        INSERT INTO article_votes (article_id, user_id, value, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(article_id, user_id) DO UPDATE SET
                            value = excluded.value,
                            updated_at = excluded.updated_at
                    """, (canonical_id, user["id"], val, now_iso, now_iso))
                elif val == 0:
                    cur.execute(
                        "DELETE FROM article_votes WHERE article_id = ? AND user_id = ?",
                        (canonical_id, user["id"])
                    )

                cur.execute("SELECT COALESCE(SUM(value), 0) AS score FROM article_votes WHERE article_id = ?", (canonical_id,))
                score_row = cur.fetchone()
                score = score_row["score"] if score_row else 0
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "targetType": "article",
            "targetId": canonical_id,
            "score": score,
            "myVote": val,
            "canVote": True
        })

    def handle_comment_vote(self, comment_id: str):
        """
        POST /api/comments/<id>/vote
        Registers or cancels vote (-1, 0, 1) for the specified comment.
        Requires authenticated session (401 AUTH_REQUIRED).
        Prevents self-voting by the author (403 SELF_VOTE_FORBIDDEN).
        Validates comment existence, published status, and parent publication approval.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация",
                "code": "AUTH_REQUIRED",
                "requireAuth": True
            })
            return

        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if payload is None:
            return

        if not isinstance(payload, dict) or "value" not in payload:
            self.send_json_response(400, {
                "success": False,
                "error": "Значение голоса должно быть -1, 0 или 1",
                "code": "INVALID_VOTE_VALUE"
            })
            return

        val = payload.get("value")
        if type(val) is not int or isinstance(val, bool) or val not in (-1, 0, 1):
            self.send_json_response(400, {
                "success": False,
                "error": "Значение голоса должно быть -1, 0 или 1",
                "code": "INVALID_VOTE_VALUE"
            })
            return

        if not comment_id:
            comment_id = payload.get("commentId") or payload.get("comment_id") or ""

        if not comment_id:
            self.send_json_response(404, {
                "success": False,
                "error": "Комментарий не найден",
                "code": "NOT_FOUND"
            })
            return

        conn = self.get_db()
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                cur = conn.cursor()
                cur.execute("SELECT id, article_id, user_id, status FROM article_comments WHERE id = ?", (comment_id,))
                comment = cur.fetchone()
                if not comment:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Комментарий не найден",
                        "code": "NOT_FOUND"
                    })
                    return

                if comment["status"] == "deleted":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Нельзя голосовать за удаленный комментарий",
                        "code": "COMMENT_DELETED"
                    })
                    return

                if comment["status"] != "published":
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Комментарий не найден",
                        "code": "NOT_FOUND"
                    })
                    return

                parent_art_id = comment["article_id"]
                cur.execute(
                    "SELECT id, status FROM moderation_submissions WHERE (id = ? OR draft_id = ?) LIMIT 1",
                    (parent_art_id, parent_art_id)
                )
                art_row = cur.fetchone()
                if not art_row or art_row["status"] != "approved":
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Публикация не найдена",
                        "code": "NOT_FOUND"
                    })
                    return

                if comment["user_id"] == user["id"]:
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Нельзя голосовать за собственный комментарий",
                        "code": "SELF_VOTE_FORBIDDEN"
                    })
                    return

                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                if val in (-1, 1):
                    cur.execute("""
                        INSERT INTO comment_votes (comment_id, user_id, value, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(comment_id, user_id) DO UPDATE SET
                            value = excluded.value,
                            updated_at = excluded.updated_at
                    """, (comment_id, user["id"], val, now_iso, now_iso))
                elif val == 0:
                    cur.execute(
                        "DELETE FROM comment_votes WHERE comment_id = ? AND user_id = ?",
                        (comment_id, user["id"])
                    )

                cur.execute("SELECT COALESCE(SUM(value), 0) AS score FROM comment_votes WHERE comment_id = ?", (comment_id,))
                score_row = cur.fetchone()
                score = score_row["score"] if score_row else 0
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "targetType": "comment",
            "targetId": comment_id,
            "score": score,
            "myVote": val,
            "canVote": True
        })

    def handle_comment_report(self, comment_id: str):
        """
        POST /api/comments/<id>/report
        Submits a report against a comment or answer.
        Requires authentication (returns 401 if unauthorized).
        Validates reason (non-empty string, max length 200).
        Prevents author from reporting own comment (returns 403 CANNOT_REPORT_OWN_COMMENT).
        Prevents duplicate report from same user on same comment (returns 409 REPORT_ALREADY_EXISTS).
        Inserts into comment_reports and returns {"success": true, "message": "Жалоба отправлена"}.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация",
                "code": "AUTH_REQUIRED",
                "requireAuth": True
            })
            return

        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if payload is None:
            return

        if not isinstance(payload, dict):
            self.send_json_response(400, {
                "success": False,
                "error": "Неверный формат данных",
                "code": "INVALID_PAYLOAD"
            })
            return

        if not comment_id:
            comment_id = str(payload.get("commentId") or payload.get("comment_id") or "").strip()

        if not comment_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Идентификатор комментария обязателен",
                "code": "INVALID_COMMENT_ID"
            })
            return

        raw_reason = payload.get("reason")
        if not isinstance(raw_reason, str) or not raw_reason.strip():
            self.send_json_response(400, {
                "success": False,
                "error": "Причина жалобы обязательна",
                "code": "INVALID_REASON"
            })
            return

        reason = raw_reason.strip()
        if len(reason) > 200:
            self.send_json_response(400, {
                "success": False,
                "error": "Причина жалобы не должна превышать 200 символов",
                "code": "REASON_TOO_LONG"
            })
            return

        raw_details = payload.get("details", "")
        details = str(raw_details).strip() if raw_details is not None else ""
        if len(details) > 2000:
            details = details[:2000]

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT id, user_id, status FROM article_comments WHERE id = ?", (comment_id,))
                comment = cur.fetchone()
                if not comment:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Комментарий не найден",
                        "code": "NOT_FOUND"
                    })
                    return

                if comment["user_id"] == user["id"]:
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Нельзя пожаловаться на собственный комментарий",
                        "code": "CANNOT_REPORT_OWN_COMMENT"
                    })
                    return

                cur.execute(
                    "SELECT id FROM comment_reports WHERE comment_id = ? AND user_id = ?",
                    (comment_id, user["id"])
                )
                if cur.fetchone():
                    self.send_json_response(409, {
                        "success": False,
                        "error": "Вы уже отправили жалобу на этот комментарий",
                        "code": "REPORT_ALREADY_EXISTS"
                    })
                    return

                report_id = f"rep_{uuid.uuid4().hex[:12]}"
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cur.execute("""
                    INSERT INTO comment_reports (id, comment_id, user_id, reason, details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (report_id, comment_id, user["id"], reason, details, now_iso))
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "message": "Жалоба отправлена",
            "hasReported": True,
            "isReported": True
        })

    def handle_article_report(self, article_id: str):
        """
        POST /api/articles/<id>/report
        Submits a report against a publication or question.
        Requires authentication (returns 401 if unauthorized).
        Validates reason (non-empty string, max length 200).
        Prevents author from reporting own publication/question (returns 403 CANNOT_REPORT_OWN_ARTICLE).
        Prevents duplicate report from same user on same article (returns 409 REPORT_ALREADY_EXISTS).
        Inserts into article_reports and returns {"success": true, "message": "Жалоба отправлена"}.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация",
                "code": "AUTH_REQUIRED",
                "requireAuth": True
            })
            return

        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if payload is None:
            return

        if not isinstance(payload, dict):
            self.send_json_response(400, {
                "success": False,
                "error": "Неверный формат данных",
                "code": "INVALID_PAYLOAD"
            })
            return

        if not article_id:
            article_id = str(payload.get("articleId") or payload.get("article_id") or "").strip()

        if not article_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Идентификатор публикации обязателен",
                "code": "INVALID_ARTICLE_ID"
            })
            return

        raw_reason = payload.get("reason")
        if not isinstance(raw_reason, str) or not raw_reason.strip():
            self.send_json_response(400, {
                "success": False,
                "error": "Причина жалобы обязательна",
                "code": "INVALID_REASON"
            })
            return

        reason = raw_reason.strip()
        if len(reason) > 200:
            self.send_json_response(400, {
                "success": False,
                "error": "Причина жалобы не должна превышать 200 символов",
                "code": "REASON_TOO_LONG"
            })
            return

        raw_details = payload.get("details", "")
        details = str(raw_details).strip() if raw_details is not None else ""
        if len(details) > 2000:
            details = details[:2000]

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, draft_id, author_id, status FROM moderation_submissions WHERE (id = ? OR draft_id = ?) AND status = 'approved' LIMIT 1",
                    (article_id, article_id)
                )
                article = cur.fetchone()
                if not article:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Публикация не найдена",
                        "code": "NOT_FOUND"
                    })
                    return

                canonical_id = article["id"]

                if article["author_id"] == user["id"]:
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Нельзя пожаловаться на собственный материал",
                        "code": "CANNOT_REPORT_OWN_ARTICLE"
                    })
                    return

                cur.execute(
                    "SELECT id FROM article_reports WHERE article_id = ? AND user_id = ?",
                    (canonical_id, user["id"])
                )
                if cur.fetchone():
                    self.send_json_response(409, {
                        "success": False,
                        "error": "Вы уже отправили жалобу на этот материал",
                        "code": "REPORT_ALREADY_EXISTS"
                    })
                    return

                report_id = f"artrep_{uuid.uuid4().hex[:12]}"
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cur.execute("""
                    INSERT INTO article_reports (id, article_id, user_id, reason, details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (report_id, canonical_id, user["id"], reason, details, now_iso))
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "message": "Жалоба отправлена",
            "hasReported": True,
            "isReported": True
        })
