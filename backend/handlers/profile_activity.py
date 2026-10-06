"""Profile activity tabs: activity feed, publications, questions, answers, comments."""
import json
import urllib.parse

from backend.content import (
    TOPICS_TITLE_MAP,
    calculate_reading_time,
    extract_article_text,
    format_date_ru,
    make_content_snippet,
)
from backend.submissions import resolve_cover_position


class ProfileActivityHandlers:
    def handle_get_user_activity(self, user_id: str, parsed_url=None):
        """
        GET /api/users/<user_id>/activity
        Returns unified chronological feed of author's activity (publications, questions, answers).
        Supports limit and offset pagination.
        """
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "Не указан user_id"})
            return

        query = urllib.parse.parse_qs(parsed_url.query) if parsed_url else {}
        search_q = (query.get("q", [""])[0] or query.get("search", [""])[0] or "").strip().lower()
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

                # Phase 1: Fast indexed total calculation
                # Complexity note: O(1) refers to bounded data transfer, payload size, and server memory per page via LIMIT ? OFFSET ?, while database filtering performs indexed/author scanning.
                if not search_q:
                    count_sql = """
                        SELECT (
                            (SELECT COUNT(*) FROM moderation_submissions ms
                             WHERE ms.author_id = ? AND ms.status = 'approved'
                               AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') != 'question')
                            +
                            (SELECT COUNT(*) FROM moderation_submissions ms
                             WHERE ms.author_id = ? AND ms.status = 'approved'
                               AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question')
                            +
                            (SELECT COUNT(DISTINCT ac.id) FROM article_comments ac
                             JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                             WHERE ac.user_id = ? AND ac.status = 'published' AND ac.comment_type = 'answer' AND ms.status = 'approved'
                               AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question')
                            +
                            (SELECT COUNT(DISTINCT ac.id) FROM article_comments ac
                             JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                             WHERE ac.user_id = ? AND ac.status = 'published' AND (ac.comment_type IS NULL OR ac.comment_type != 'answer') AND ms.status = 'approved')
                        ) AS total
                    """
                    cur.execute(count_sql, (user_id, user_id, user_id, user_id))
                else:
                    q_like = f"%{search_q}%"
                    count_sql = """
                        SELECT (
                            (SELECT COUNT(*) FROM moderation_submissions ms
                             WHERE ms.author_id = ? AND ms.status = 'approved'
                               AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') != 'question'
                               AND (LOWER(ms.title) LIKE ? OR LOWER(extract_text(ms.article_html)) LIKE ?))
                            +
                            (SELECT COUNT(*) FROM moderation_submissions ms
                             WHERE ms.author_id = ? AND ms.status = 'approved'
                               AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question'
                               AND (LOWER(ms.title) LIKE ? OR LOWER(extract_text(ms.article_html)) LIKE ?))
                            +
                            (SELECT COUNT(DISTINCT ac.id) FROM article_comments ac
                             JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                             WHERE ac.user_id = ? AND ac.status = 'published' AND ac.comment_type = 'answer' AND ms.status = 'approved'
                               AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question'
                               AND (LOWER(ac.content) LIKE ? OR LOWER(extract_text(ac.content)) LIKE ? OR LOWER(ms.title) LIKE ?))
                            +
                            (SELECT COUNT(DISTINCT ac.id) FROM article_comments ac
                             JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                             WHERE ac.user_id = ? AND ac.status = 'published' AND (ac.comment_type IS NULL OR ac.comment_type != 'answer') AND ms.status = 'approved'
                               AND (LOWER(ac.content) LIKE ? OR LOWER(extract_text(ac.content)) LIKE ? OR LOWER(ms.title) LIKE ?))
                        ) AS total
                    """
                    cur.execute(count_sql, (user_id, q_like, q_like, user_id, q_like, q_like, user_id, q_like, q_like, q_like, user_id, q_like, q_like, q_like))
                total = cur.fetchone()["total"] or 0

                # Phase 2: Retrieve ordered IDs and types for the requested page using SQLite UNION ALL
                if not search_q:
                    union_sql = """
                        SELECT item_type, item_id, act_time, tie_breaker, parent_ms_id FROM (
                            SELECT 'publication' AS item_type, ms.id AS item_id, ms.created_at AS act_time, ms.id AS tie_breaker, NULL AS parent_ms_id
                            FROM moderation_submissions ms
                            WHERE ms.author_id = ? AND ms.status = 'approved'
                              AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') != 'question'
                            UNION ALL
                            SELECT 'question' AS item_type, ms.id AS item_id, ms.created_at AS act_time, ms.id AS tie_breaker, NULL AS parent_ms_id
                            FROM moderation_submissions ms
                            WHERE ms.author_id = ? AND ms.status = 'approved'
                              AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question'
                            UNION ALL
                            SELECT 'answer' AS item_type, ac.id AS item_id, ac.created_at AS act_time, ac.id AS tie_breaker, ms.id AS parent_ms_id
                            FROM article_comments ac
                            JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                            WHERE ac.user_id = ?
                              AND ac.status = 'published'
                              AND ac.comment_type = 'answer'
                              AND ms.status = 'approved'
                              AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question'
                            GROUP BY ac.id
                            UNION ALL
                            SELECT 'comment' AS item_type, ac.id AS item_id, ac.created_at AS act_time, ac.id AS tie_breaker, ms.id AS parent_ms_id
                            FROM article_comments ac
                            JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                            WHERE ac.user_id = ?
                              AND ac.status = 'published'
                              AND (ac.comment_type IS NULL OR ac.comment_type != 'answer')
                              AND ms.status = 'approved'
                            GROUP BY ac.id
                        )
                        ORDER BY act_time DESC, tie_breaker DESC
                        LIMIT ? OFFSET ?
                    """
                    cur.execute(union_sql, (user_id, user_id, user_id, user_id, limit, offset))
                else:
                    q_like = f"%{search_q}%"
                    union_sql = """
                        SELECT item_type, item_id, act_time, tie_breaker, parent_ms_id FROM (
                            SELECT 'publication' AS item_type, ms.id AS item_id, ms.created_at AS act_time, ms.id AS tie_breaker, NULL AS parent_ms_id
                            FROM moderation_submissions ms
                            WHERE ms.author_id = ? AND ms.status = 'approved'
                              AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') != 'question'
                              AND (LOWER(ms.title) LIKE ? OR LOWER(extract_text(ms.article_html)) LIKE ?)
                            UNION ALL
                            SELECT 'question' AS item_type, ms.id AS item_id, ms.created_at AS act_time, ms.id AS tie_breaker, NULL AS parent_ms_id
                            FROM moderation_submissions ms
                            WHERE ms.author_id = ? AND ms.status = 'approved'
                              AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question'
                              AND (LOWER(ms.title) LIKE ? OR LOWER(extract_text(ms.article_html)) LIKE ?)
                            UNION ALL
                            SELECT 'answer' AS item_type, ac.id AS item_id, ac.created_at AS act_time, ac.id AS tie_breaker, ms.id AS parent_ms_id
                            FROM article_comments ac
                            JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                            WHERE ac.user_id = ?
                              AND ac.status = 'published'
                              AND ac.comment_type = 'answer'
                              AND ms.status = 'approved'
                              AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question'
                              AND (LOWER(ac.content) LIKE ? OR LOWER(extract_text(ac.content)) LIKE ? OR LOWER(ms.title) LIKE ?)
                            GROUP BY ac.id
                            UNION ALL
                            SELECT 'comment' AS item_type, ac.id AS item_id, ac.created_at AS act_time, ac.id AS tie_breaker, ms.id AS parent_ms_id
                            FROM article_comments ac
                            JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                            WHERE ac.user_id = ?
                              AND ac.status = 'published'
                              AND (ac.comment_type IS NULL OR ac.comment_type != 'answer')
                              AND ms.status = 'approved'
                              AND (LOWER(ac.content) LIKE ? OR LOWER(extract_text(ac.content)) LIKE ? OR LOWER(ms.title) LIKE ?)
                            GROUP BY ac.id
                        )
                        ORDER BY act_time DESC, tie_breaker DESC
                        LIMIT ? OFFSET ?
                    """
                    cur.execute(union_sql, (user_id, q_like, q_like, user_id, q_like, q_like, user_id, q_like, q_like, q_like, user_id, q_like, q_like, q_like, limit, offset))
                paged_refs = cur.fetchall()

                # Phase 3: Fetch content/details and compute snippets ONLY for items on the requested page
                paged_activity = []
                if paged_refs:
                    pub_ids = [r["item_id"] for r in paged_refs if r["item_type"] == "publication"]
                    quest_ids = [r["item_id"] for r in paged_refs if r["item_type"] == "question"]
                    ans_ids = [r["item_id"] for r in paged_refs if r["item_type"] == "answer"]
                    comm_ids = [r["item_id"] for r in paged_refs if r["item_type"] == "comment"]
                    ans_parent_map = {r["item_id"]: r["parent_ms_id"] for r in paged_refs if r["item_type"] == "answer"}
                    comm_parent_map = {r["item_id"]: r["parent_ms_id"] for r in paged_refs if r["item_type"] == "comment"}

                    pub_map = {}
                    if pub_ids:
                        qmarks = ",".join("?" for _ in pub_ids)
                        cur.execute(f"""
                            SELECT ms.id, ms.draft_id, ms.title, ms.article_html AS content, ms.created_at, ms.publication_settings,
                                   (SELECT COALESCE(SUM(v.value), 0) FROM article_votes v WHERE v.article_id = ms.id OR (ms.draft_id IS NOT NULL AND v.article_id = ms.draft_id)) AS rating,
                                   (SELECT COUNT(DISTINCT ac.id) FROM article_comments ac WHERE (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id)) AND ac.status = 'published') AS comments_count
                            FROM moderation_submissions ms
                            WHERE ms.id IN ({qmarks})
                        """, tuple(pub_ids))
                        for row in cur.fetchall():
                            pub_map[row["id"]] = row

                    quest_map = {}
                    if quest_ids:
                        qmarks = ",".join("?" for _ in quest_ids)
                        cur.execute(f"""
                            SELECT ms.id, ms.draft_id, ms.title, ms.article_html AS content, ms.created_at, ms.publication_settings,
                                   (SELECT COALESCE(SUM(v.value), 0) FROM article_votes v WHERE v.article_id = ms.id OR (ms.draft_id IS NOT NULL AND v.article_id = ms.draft_id)) AS rating,
                                   (SELECT COUNT(DISTINCT ac.id) FROM article_comments ac WHERE (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id)) AND ac.status = 'published' AND ac.comment_type = 'answer') AS answers_count
                            FROM moderation_submissions ms
                            WHERE ms.id IN ({qmarks})
                        """, tuple(quest_ids))
                        for row in cur.fetchall():
                            quest_map[row["id"]] = row

                    ans_map = {}
                    if ans_ids:
                        qmarks = ",".join("?" for _ in ans_ids)
                        cur.execute(f"""
                            SELECT ac.id, ac.article_id, ac.content, ac.is_solution, ac.created_at,
                                   (SELECT COALESCE(SUM(v.value), 0) FROM comment_votes v WHERE v.comment_id = ac.id) AS rating
                            FROM article_comments ac
                            WHERE ac.id IN ({qmarks})
                        """, tuple(ans_ids))
                        for row in cur.fetchall():
                            ans_map[row["id"]] = dict(row)

                        parent_ms_ids = list({ans_parent_map[aid] for aid in ans_ids if ans_parent_map.get(aid)})
                        if parent_ms_ids:
                            p_qmarks = ",".join("?" for _ in parent_ms_ids)
                            cur.execute(f"""
                                SELECT ms.id, ms.title
                                FROM moderation_submissions ms
                                WHERE ms.id IN ({p_qmarks}) AND ms.status = 'approved'
                            """, tuple(parent_ms_ids))
                            p_titles = {row["id"]: row["title"] for row in cur.fetchall()}
                            for aid, row_dict in ans_map.items():
                                p_id = ans_parent_map.get(aid)
                                row_dict["question_title"] = p_titles.get(p_id)
                        else:
                            for row_dict in ans_map.values():
                                row_dict["question_title"] = None

                    comm_map = {}
                    if comm_ids:
                        qmarks = ",".join("?" for _ in comm_ids)
                        cur.execute(f"""
                            SELECT ac.id, ac.article_id, ac.content, ac.created_at,
                                   (SELECT COALESCE(SUM(v.value), 0) FROM comment_votes v WHERE v.comment_id = ac.id) AS rating
                            FROM article_comments ac
                            WHERE ac.id IN ({qmarks})
                        """, tuple(comm_ids))
                        for row in cur.fetchall():
                            comm_map[row["id"]] = dict(row)

                        parent_ms_ids = list({comm_parent_map[cid] for cid in comm_ids if comm_parent_map.get(cid)})
                        if parent_ms_ids:
                            p_qmarks = ",".join("?" for _ in parent_ms_ids)
                            cur.execute(f"""
                                SELECT ms.id, ms.title
                                FROM moderation_submissions ms
                                WHERE ms.id IN ({p_qmarks}) AND ms.status = 'approved'
                            """, tuple(parent_ms_ids))
                            p_titles = {row["id"]: row["title"] for row in cur.fetchall()}
                            for cid, row_dict in comm_map.items():
                                p_id = comm_parent_map.get(cid)
                                row_dict["parent_title"] = p_titles.get(p_id)
                        else:
                            for row_dict in comm_map.values():
                                row_dict["parent_title"] = None

                    for ref in paged_refs:
                        itype = ref["item_type"]
                        iid = ref["item_id"]
                        if itype == "publication" and iid in pub_map:
                            r = pub_map[iid]
                            paged_activity.append({
                                "type": "publication",
                                "materialType": "article",
                                "material_type": "article",
                                "id": r["id"],
                                "title": r["title"],
                                "contentSnippet": make_content_snippet(r["content"]),
                                "rating": int(r["rating"] or 0),
                                "score": int(r["rating"] or 0),
                                "commentsCount": int(r["comments_count"] or 0),
                                "answersCount": 0,
                                "isSolution": False,
                                "createdAt": r["created_at"],
                                "date": format_date_ru(r["created_at"]),
                                "url": f"article.html?id={urllib.parse.quote(r['id'])}"
                            })
                        elif itype == "question" and iid in quest_map:
                            r = quest_map[iid]
                            paged_activity.append({
                                "type": "question",
                                "materialType": "question",
                                "material_type": "question",
                                "id": r["id"],
                                "title": r["title"],
                                "contentSnippet": make_content_snippet(r["content"]),
                                "rating": int(r["rating"] or 0),
                                "score": int(r["rating"] or 0),
                                "commentsCount": 0,
                                "answersCount": int(r["answers_count"] or 0),
                                "isSolution": False,
                                "createdAt": r["created_at"],
                                "date": format_date_ru(r["created_at"]),
                                "url": f"article.html?id={urllib.parse.quote(r['id'])}"
                            })
                        elif itype == "answer" and iid in ans_map:
                            r = ans_map[iid]
                            paged_activity.append({
                                "type": "answer",
                                "materialType": "solution" if bool(r["is_solution"] == 1) else "answer",
                                "material_type": "solution" if bool(r["is_solution"] == 1) else "answer",
                                "id": r["id"],
                                "questionId": r["article_id"],
                                "title": r["question_title"] or "Ответ на вопрос",
                                "contentSnippet": make_content_snippet(r["content"]),
                                "rating": int(r["rating"] or 0),
                                "score": int(r["rating"] or 0),
                                "commentsCount": 0,
                                "answersCount": 0,
                                "isSolution": bool(r["is_solution"] == 1),
                                "createdAt": r["created_at"],
                                "date": format_date_ru(r["created_at"]),
                                "url": f"article.html?id={urllib.parse.quote(r['article_id'])}#comment-{urllib.parse.quote(r['id'])}"
                            })
                        elif itype == "comment" and iid in comm_map:
                            r = comm_map[iid]
                            p_title = r["parent_title"] or "Материал сообщества"
                            paged_activity.append({
                                "type": "comment",
                                "materialType": "comment",
                                "material_type": "comment",
                                "id": r["id"],
                                "commentId": r["id"],
                                "articleId": r["article_id"],
                                "parentTitle": p_title,
                                "title": p_title,
                                "contentSnippet": make_content_snippet(r["content"]),
                                "snippet": make_content_snippet(r["content"]),
                                "rating": int(r["rating"] or 0),
                                "score": int(r["rating"] or 0),
                                "commentsCount": 0,
                                "answersCount": 0,
                                "isSolution": False,
                                "createdAt": r["created_at"],
                                "date": format_date_ru(r["created_at"]),
                                "url": f"article.html?id={urllib.parse.quote(r['article_id'])}#comment-{urllib.parse.quote(r['id'])}"
                            })

                has_more = (offset + limit) < total

                self.send_json_response(200, {
                    "success": True,
                    "activity": paged_activity,
                    "items": paged_activity,
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "hasMore": has_more
                })
        finally:
            conn.close()

    def handle_get_user_publications(self, user_id: str, parsed_url=None):
        """
        GET /api/users/<user_id>/publications
        Returns author's approved publications (articles, posts, news, etc. where materialType != 'question').
        Query params: sort ('newest'|'popular'), limit, offset.
        """
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "Не указан user_id"})
            return

        query = urllib.parse.parse_qs(parsed_url.query) if parsed_url else {}
        sort_by = (query.get("sort", ["newest"])[0] or "newest").strip().lower()
        search_q = (query.get("q", [""])[0] or query.get("search", [""])[0] or "").strip().lower()
        topic_filter = (query.get("topic", [""])[0] or "").strip().lower()
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
                p_row = cur.fetchone()
                user_exists = (p_row is not None)
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

                ident = self.resolve_user_identity(cur, user_id, p_row)
                author_name = ident["name"]
                author_avatar = ident["avatar"]
                author_initials = ident["initials"]
                company = ident["company"]
                specialization = ident["specialization"]

                curr_user = self.get_current_user()
                user_likes = set()
                user_saves = set()
                user_reports = set()
                user_votes = {}
                if curr_user:
                    cur.execute("SELECT article_id FROM article_likes WHERE user_id = ?", (curr_user["id"],))
                    user_likes = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id FROM article_saves WHERE user_id = ?", (curr_user["id"],))
                    user_saves = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id FROM article_reports WHERE user_id = ?", (curr_user["id"],))
                    user_reports = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id, value FROM article_votes WHERE user_id = ?", (curr_user["id"],))
                    user_votes = {r["article_id"]: r["value"] for r in cur.fetchall()}

                conditions = [
                    "ms.author_id = ?",
                    "ms.status = 'approved'",
                    "COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') != 'question'"
                ]
                params = [user_id]

                # Complexity note: O(1) refers to bounded data transfer, payload size, and server memory per page via LIMIT ? OFFSET ?, while database filtering performs indexed/author scanning.
                if search_q:
                    conditions.append("(LOWER(ms.title) LIKE ? OR LOWER(extract_text(ms.article_html)) LIKE ?)")
                    params.extend([f"%{search_q}%", f"%{search_q}%"])

                if topic_filter:
                    topic_candidates = [topic_filter]
                    for slug, title in TOPICS_TITLE_MAP.items():
                        if topic_filter == slug.lower() and title.lower() not in topic_candidates:
                            topic_candidates.append(title.lower())
                        elif topic_filter == title.lower() and slug.lower() not in topic_candidates:
                            topic_candidates.append(slug.lower())

                    topic_clauses = []
                    topic_params = []
                    for cand in topic_candidates:
                        topic_clauses.append("""(
                            json_valid(ms.publication_settings) = 1 AND (
                                LOWER(json_extract(ms.publication_settings, '$.topic')) = ?
                                OR (json_type(ms.publication_settings, '$.topics') = 'text' AND LOWER(json_extract(ms.publication_settings, '$.topics')) = ?)
                                OR (json_type(ms.publication_settings, '$.topics') = 'array' AND EXISTS (SELECT 1 FROM json_each(ms.publication_settings, '$.topics') WHERE LOWER(value) = ?))
                            )
                        )""")
                        topic_params.extend([cand, cand, cand])
                    conditions.append(f"({' OR '.join(topic_clauses)})")
                    params.extend(topic_params)

                where_sql = " AND ".join(conditions)

                cur.execute(f"""
                    SELECT COUNT(*) AS total
                    FROM moderation_submissions ms
                    WHERE {where_sql}
                """, tuple(params))
                total = cur.fetchone()["total"] or 0

                order_sql = "rating DESC, ms.created_at DESC, ms.id DESC" if sort_by == "popular" else "ms.created_at DESC, ms.id DESC"
                select_params = list(params) + [limit, offset]
                cur.execute(f"""
                    SELECT ms.id, ms.draft_id, ms.title, ms.article_html, ms.created_at, ms.publication_settings,
                           (SELECT COALESCE(SUM(v.value), 0) FROM article_votes v WHERE v.article_id = ms.id OR (ms.draft_id IS NOT NULL AND v.article_id = ms.draft_id)) AS rating,
                           (SELECT COUNT(DISTINCT ac.id) FROM article_comments ac WHERE (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id)) AND ac.status = 'published') AS comments_count,
                           (SELECT COUNT(DISTINCT al.id) FROM article_likes al WHERE al.article_id = ms.id OR (ms.draft_id IS NOT NULL AND al.article_id = ms.draft_id)) AS likes_count,
                           (SELECT COUNT(DISTINCT asv.id) FROM article_saves asv WHERE asv.article_id = ms.id OR (ms.draft_id IS NOT NULL AND asv.article_id = ms.draft_id)) AS saves_count
                    FROM moderation_submissions ms
                    WHERE {where_sql}
                    ORDER BY {order_sql}
                    LIMIT ? OFFSET ?
                """, tuple(select_params))
                rows = cur.fetchall()

            items = []
            for r in rows:
                art_id = r["id"]
                draft_id = r["draft_id"]
                try:
                    pst = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                except Exception:
                    pst = {}
                focal_pos = resolve_cover_position(pst)
                topics = pst.get("topics") or []
                if isinstance(topics, str):
                    topics = [topics]
                cover_image = pst.get("coverImage") or None
                snippet = make_content_snippet(r["article_html"])
                reading_time, reading_minutes = calculate_reading_time(r["article_html"] or "")
                date_str = format_date_ru(r["created_at"])
                rating_val = int(r["rating"] or 0)
                comments_val = int(r["comments_count"] or 0)
                likes_val = int(r["likes_count"] or 0)
                saves_val = int(r["saves_count"] or 0)
                has_liked = bool(art_id in user_likes or (draft_id and draft_id in user_likes))
                has_saved = bool(art_id in user_saves or (draft_id and draft_id in user_saves))
                has_reported = bool(art_id in user_reports or (draft_id and draft_id in user_reports))
                my_vote = int(user_votes.get(art_id, 0) or (user_votes.get(draft_id, 0) if draft_id else 0))
                can_vote = bool(curr_user and user_id != curr_user["id"])
                is_author = bool(curr_user and user_id == curr_user["id"])

                items.append({
                    "id": art_id,
                    "draftId": draft_id,
                    "title": r["title"],
                    "authorId": user_id,
                    "author": author_name,
                    "authorInitials": author_initials,
                    "authorAvatar": author_avatar,
                    "company": company,
                    "specialization": specialization,
                    "date": date_str,
                    "createdAt": r["created_at"],
                    "description": snippet,
                    "snippet": snippet,
                    "contentSnippet": snippet,
                    "coverImage": cover_image,
                    "coverPosition": focal_pos,
                    "focalPoint": focal_pos,
                    "objectPosition": focal_pos,
                    "topics": topics,
                    "topic": topics[0] if topics else "",
                    "materialType": "article",
                    "material_type": "article",
                    "type": "article",
                    "format": pst.get("format") or "",
                    "rating": rating_val,
                    "score": rating_val,
                    "commentsCount": comments_val,
                    "answersCount": 0,
                    "discussionCount": comments_val,
                    "likesCount": likes_val,
                    "hasLiked": has_liked,
                    "isLiked": has_liked,
                    "savesCount": saves_val,
                    "hasSaved": has_saved,
                    "isSaved": has_saved,
                    "hasReported": has_reported,
                    "isReported": has_reported,
                    "myVote": my_vote,
                    "canVote": can_vote,
                    "isAuthor": is_author,
                    "readingTime": reading_time,
                    "readingMinutes": reading_minutes,
                    "url": f"article.html?id={urllib.parse.quote(art_id)}"
                })

            paged_items = items
            has_more = (offset + limit) < total

            self.send_json_response(200, {
                "success": True,
                "items": paged_items,
                "total": total,
                "limit": limit,
                "offset": offset,
                "hasMore": has_more
            })
        finally:
            conn.close()

    def handle_get_user_questions(self, user_id: str, parsed_url=None):
        """
        GET /api/users/<user_id>/questions
        Returns author's approved questions.
        Query params: sort ('newest'|'popular'), status ('all'|'solved'|'unsolved'), limit, offset.
        """
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "Не указан user_id"})
            return

        query = urllib.parse.parse_qs(parsed_url.query) if parsed_url else {}
        sort_by = (query.get("sort", ["newest"])[0] or "newest").strip().lower()
        status_filter = (query.get("status", ["all"])[0] or "all").strip().lower()
        search_q = (query.get("q", [""])[0] or query.get("search", [""])[0] or "").strip().lower()
        topic_filter = (query.get("topic", [""])[0] or "").strip().lower()
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
                p_row = cur.fetchone()
                user_exists = (p_row is not None)
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

                ident = self.resolve_user_identity(cur, user_id, p_row)
                author_name = ident["name"]
                author_avatar = ident["avatar"]
                author_initials = ident["initials"]
                company = ident["company"]
                specialization = ident["specialization"]

                curr_user = self.get_current_user()
                user_likes = set()
                user_saves = set()
                user_reports = set()
                user_votes = {}
                if curr_user:
                    cur.execute("SELECT article_id FROM article_likes WHERE user_id = ?", (curr_user["id"],))
                    user_likes = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id FROM article_saves WHERE user_id = ?", (curr_user["id"],))
                    user_saves = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id FROM article_reports WHERE user_id = ?", (curr_user["id"],))
                    user_reports = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id, value FROM article_votes WHERE user_id = ?", (curr_user["id"],))
                    user_votes = {r["article_id"]: r["value"] for r in cur.fetchall()}

                conditions = [
                    "ms.author_id = ?",
                    "ms.status = 'approved'",
                    "COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question'"
                ]
                params = [user_id]

                # Complexity note: O(1) refers to bounded data transfer, payload size, and server memory per page via LIMIT ? OFFSET ?, while database filtering performs indexed/author scanning.
                if search_q:
                    conditions.append("(LOWER(ms.title) LIKE ? OR LOWER(extract_text(ms.article_html)) LIKE ?)")
                    params.extend([f"%{search_q}%", f"%{search_q}%"])

                if topic_filter:
                    topic_candidates = [topic_filter]
                    for slug, title in TOPICS_TITLE_MAP.items():
                        if topic_filter == slug.lower() and title.lower() not in topic_candidates:
                            topic_candidates.append(title.lower())
                        elif topic_filter == title.lower() and slug.lower() not in topic_candidates:
                            topic_candidates.append(slug.lower())

                    topic_clauses = []
                    topic_params = []
                    for cand in topic_candidates:
                        topic_clauses.append("""(
                            json_valid(ms.publication_settings) = 1 AND (
                                LOWER(json_extract(ms.publication_settings, '$.topic')) = ?
                                OR (json_type(ms.publication_settings, '$.topics') = 'text' AND LOWER(json_extract(ms.publication_settings, '$.topics')) = ?)
                                OR (json_type(ms.publication_settings, '$.topics') = 'array' AND EXISTS (SELECT 1 FROM json_each(ms.publication_settings, '$.topics') WHERE LOWER(value) = ?))
                            )
                        )""")
                        topic_params.extend([cand, cand, cand])
                    conditions.append(f"({' OR '.join(topic_clauses)})")
                    params.extend(topic_params)

                if status_filter == "solved":
                    conditions.append("EXISTS (SELECT 1 FROM article_comments ac WHERE (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id)) AND ac.status = 'published' AND ac.comment_type = 'answer' AND ac.is_solution = 1)")
                elif status_filter == "unsolved":
                    conditions.append("NOT EXISTS (SELECT 1 FROM article_comments ac WHERE (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id)) AND ac.status = 'published' AND ac.comment_type = 'answer' AND ac.is_solution = 1)")

                where_sql = " AND ".join(conditions)

                cur.execute(f"""
                    SELECT COUNT(*) AS total
                    FROM moderation_submissions ms
                    WHERE {where_sql}
                """, tuple(params))
                total = cur.fetchone()["total"] or 0

                order_sql = "rating DESC, ms.created_at DESC, ms.id DESC" if sort_by == "popular" else "ms.created_at DESC, ms.id DESC"
                select_params = list(params) + [limit, offset]
                cur.execute(f"""
                    SELECT ms.id, ms.draft_id, ms.title, ms.article_html, ms.created_at, ms.publication_settings,
                           (SELECT COALESCE(SUM(v.value), 0) FROM article_votes v WHERE v.article_id = ms.id OR (ms.draft_id IS NOT NULL AND v.article_id = ms.draft_id)) AS rating,
                           (SELECT COUNT(DISTINCT ac.id) FROM article_comments ac WHERE (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id)) AND ac.status = 'published' AND ac.comment_type = 'answer') AS answers_count,
                           (SELECT COUNT(DISTINCT ac.id) FROM article_comments ac WHERE (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id)) AND ac.status = 'published' AND ac.comment_type = 'answer' AND ac.is_solution = 1) AS solutions_count,
                           (SELECT COUNT(DISTINCT al.id) FROM article_likes al WHERE al.article_id = ms.id OR (ms.draft_id IS NOT NULL AND al.article_id = ms.draft_id)) AS likes_count,
                           (SELECT COUNT(DISTINCT asv.id) FROM article_saves asv WHERE asv.article_id = ms.id OR (ms.draft_id IS NOT NULL AND asv.article_id = ms.draft_id)) AS saves_count
                    FROM moderation_submissions ms
                    WHERE {where_sql}
                    ORDER BY {order_sql}
                    LIMIT ? OFFSET ?
                """, tuple(select_params))
                rows = cur.fetchall()

            items = []
            for r in rows:
                art_id = r["id"]
                draft_id = r["draft_id"]
                sol_cnt = int(r["solutions_count"] or 0)
                is_solved = (sol_cnt > 0)
                try:
                    pst = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                except Exception:
                    pst = {}
                focal_pos = resolve_cover_position(pst)
                topics = pst.get("topics") or []
                if isinstance(topics, str):
                    topics = [topics]
                cover_image = pst.get("coverImage") or None
                snippet = make_content_snippet(r["article_html"])
                date_str = format_date_ru(r["created_at"])
                rating_val = int(r["rating"] or 0)
                answers_val = int(r["answers_count"] or 0)
                likes_val = int(r["likes_count"] or 0)
                saves_val = int(r["saves_count"] or 0)
                has_liked = bool(art_id in user_likes or (draft_id and draft_id in user_likes))
                has_saved = bool(art_id in user_saves or (draft_id and draft_id in user_saves))
                has_reported = bool(art_id in user_reports or (draft_id and draft_id in user_reports))
                my_vote = int(user_votes.get(art_id, 0) or (user_votes.get(draft_id, 0) if draft_id else 0))
                can_vote = bool(curr_user and user_id != curr_user["id"])
                is_author = bool(curr_user and user_id == curr_user["id"])

                items.append({
                    "id": art_id,
                    "draftId": draft_id,
                    "title": r["title"],
                    "authorId": user_id,
                    "author": author_name,
                    "authorInitials": author_initials,
                    "authorAvatar": author_avatar,
                    "company": company,
                    "specialization": specialization,
                    "date": date_str,
                    "createdAt": r["created_at"],
                    "description": snippet,
                    "snippet": snippet,
                    "contentSnippet": snippet,
                    "coverImage": cover_image,
                    "coverPosition": focal_pos,
                    "focalPoint": focal_pos,
                    "objectPosition": focal_pos,
                    "topics": topics,
                    "topic": topics[0] if topics else "",
                    "materialType": "question",
                    "material_type": "question",
                    "type": "question",
                    "rating": rating_val,
                    "score": rating_val,
                    "answersCount": answers_val,
                    "commentsCount": 0,
                    "discussionCount": answers_val,
                    "likesCount": likes_val,
                    "hasLiked": has_liked,
                    "isLiked": has_liked,
                    "savesCount": saves_val,
                    "hasSaved": has_saved,
                    "isSaved": has_saved,
                    "hasReported": has_reported,
                    "isReported": has_reported,
                    "myVote": my_vote,
                    "canVote": can_vote,
                    "isAuthor": is_author,
                    "solutionsCount": sol_cnt,
                    "isSolved": is_solved,
                    "hasSolution": is_solved,
                    "url": f"article.html?id={urllib.parse.quote(art_id)}"
                })

            paged_items = items
            has_more = (offset + limit) < total

            self.send_json_response(200, {
                "success": True,
                "items": paged_items,
                "total": total,
                "limit": limit,
                "offset": offset,
                "hasMore": has_more
            })
        finally:
            conn.close()

    def handle_get_user_answers(self, user_id: str, parsed_url=None):
        """
        GET /api/users/<user_id>/answers
        Returns author's published answers from article_comments with question title context.
        Query params: filter ('all'|'solutions'), sort ('new'|'rating'|'popular'|'top'), limit, offset.
        """
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "Не указан user_id"})
            return

        query = urllib.parse.parse_qs(parsed_url.query) if parsed_url else {}
        sort_by = (query.get("sort", ["new"])[0] or "new").strip().lower()
        filter_type = (query.get("filter", ["all"])[0] or "all").strip().lower()
        search_q = (query.get("q", [""])[0] or query.get("search", [""])[0] or "").strip().lower()
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

                total_count = None
                sol_condition = " AND ac.is_solution = 1" if filter_type in ("solutions", "solution") else ""
                if not search_q:
                    cur.execute(f"""
                        SELECT COUNT(DISTINCT ac.id) AS total
                        FROM article_comments ac
                        JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                        WHERE ac.user_id = ?
                          AND ac.status = 'published'
                          AND ac.comment_type = 'answer'
                          AND ms.status = 'approved'
                          AND (
                              json_extract(ms.publication_settings, '$.materialType') = 'question'
                              OR json_extract(ms.publication_settings, '$.type') = 'question'
                          )
                          {sol_condition}
                    """, (user_id,))
                    total_count = cur.fetchone()["total"] or 0

                    ans_order_sql = "rating DESC, ac.created_at DESC, ac.id DESC" if sort_by in ("rating", "popular", "top") else "ac.created_at DESC, ac.id DESC"
                    cur.execute(f"""
                        SELECT ac.id, ac.article_id, ac.content, ac.is_solution, ac.created_at,
                                ms.title AS question_title,
                                (SELECT COALESCE(SUM(v.value), 0) FROM comment_votes v WHERE v.comment_id = ac.id) AS rating
                        FROM article_comments ac
                        JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                        WHERE ac.user_id = ?
                          AND ac.status = 'published'
                          AND ac.comment_type = 'answer'
                          AND ms.status = 'approved'
                          AND (
                              json_extract(ms.publication_settings, '$.materialType') = 'question'
                              OR json_extract(ms.publication_settings, '$.type') = 'question'
                          )
                          {sol_condition}
                        GROUP BY ac.id
                        ORDER BY {ans_order_sql}
                        LIMIT ? OFFSET ?
                    """, (user_id, limit, offset))
                    rows = cur.fetchall()
                else:
                    ans_order_sql = "rating DESC, ac.created_at DESC, ac.id DESC" if sort_by in ("rating", "popular", "top") else "ac.created_at DESC, ac.id DESC"
                    cur.execute(f"""
                        SELECT ac.id, ac.article_id, ac.content, ac.is_solution, ac.created_at,
                                ms.title AS question_title,
                                (SELECT COALESCE(SUM(v.value), 0) FROM comment_votes v WHERE v.comment_id = ac.id) AS rating
                        FROM article_comments ac
                        JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                        WHERE ac.user_id = ?
                          AND ac.status = 'published'
                          AND ac.comment_type = 'answer'
                          AND ms.status = 'approved'
                          AND (
                              json_extract(ms.publication_settings, '$.materialType') = 'question'
                              OR json_extract(ms.publication_settings, '$.type') = 'question'
                          )
                          {sol_condition}
                        GROUP BY ac.id
                        ORDER BY {ans_order_sql}
                    """, (user_id,))
                    rows = cur.fetchall()

            items = []
            for r in rows:
                is_sol = bool(r["is_solution"] == 1)
                if filter_type in ("solutions", "solution") and not is_sol:
                    continue

                q_title = r["question_title"] or ""
                content_val = r["content"] or ""
                if search_q:
                    text_val = extract_article_text(content_val)
                    if search_q not in q_title.lower() and search_q not in content_val.lower() and search_q not in text_val.lower():
                        continue

                items.append({
                    "id": r["id"],
                    "questionId": r["article_id"],
                    "questionTitle": r["question_title"] or "Ответ на вопрос",
                    "title": r["question_title"] or "Ответ на вопрос",
                    "contentSnippet": make_content_snippet(r["content"]),
                    "rating": int(r["rating"] or 0),
                    "isSolution": is_sol,
                    "createdAt": r["created_at"],
                    "date": format_date_ru(r["created_at"]),
                    "url": f"article.html?id={urllib.parse.quote(r['article_id'])}#comment-{urllib.parse.quote(r['id'])}"
                })

            if total_count is not None:
                total = total_count
                paged_items = items
                has_more = (offset + limit) < total
            else:
                if sort_by in ("rating", "popular", "top"):
                    items.sort(key=lambda x: (x.get("rating", 0), x.get("createdAt") or ""), reverse=True)
                else:
                    items.sort(key=lambda x: x.get("createdAt") or "", reverse=True)
                total = len(items)
                paged_items = items[offset : offset + limit]
                has_more = (offset + limit) < total

            self.send_json_response(200, {
                "success": True,
                "items": paged_items,
                "total": total,
                "totalCount": total,
                "limit": limit,
                "offset": offset,
                "hasMore": has_more
            })
        finally:
            conn.close()

    def handle_get_user_comments(self, user_id: str, parsed_url=None):
        """
        GET /api/users/<user_id>/comments
        Returns author's published ordinary comments on approved materials.
        Query params: sort ('new'|'newest'|'rating'|'popular'|'top'), q (search query), limit, offset.
        """
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "Не указан user_id"})
            return

        query = urllib.parse.parse_qs(parsed_url.query) if parsed_url else {}
        sort_by = (query.get("sort", ["new"])[0] or "new").strip().lower()
        search_q = (query.get("q", [""])[0] or query.get("search", [""])[0] or "").strip()
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

                try:
                    conn.create_function("lower", 1, lambda s: s.lower() if s is not None else None)
                except Exception:
                    pass
                try:
                    conn.create_function("extract_text", 1, lambda s: extract_article_text(s) if s is not None else "")
                except Exception:
                    pass

                total_count = None
                order_sql = "rating DESC, ac.created_at DESC, ac.id DESC" if sort_by in ("rating", "popular", "top") else "ac.created_at DESC, ac.id DESC"
                if not search_q:
                    count_sql = """
                        SELECT COUNT(DISTINCT ac.id) AS total
                        FROM article_comments ac
                        JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                        WHERE ac.user_id = ?
                          AND ac.status = 'published'
                          AND (ac.comment_type IS NULL OR ac.comment_type != 'answer')
                          AND ms.status = 'approved'
                    """
                    cur.execute(count_sql, (user_id,))
                    total_count = cur.fetchone()["total"] or 0

                    sql = f"""
                        SELECT ac.id, ac.article_id, ac.content, ac.created_at, ac.comment_type,
                               ms.id AS material_id, ms.title AS parent_title,
                               (SELECT COALESCE(SUM(v.value), 0) FROM comment_votes v WHERE v.comment_id = ac.id) AS rating
                        FROM article_comments ac
                        JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                        WHERE ac.user_id = ?
                          AND ac.status = 'published'
                          AND (ac.comment_type IS NULL OR ac.comment_type != 'answer')
                          AND ms.status = 'approved'
                        GROUP BY ac.id
                        ORDER BY {order_sql}
                        LIMIT ? OFFSET ?
                    """
                    cur.execute(sql, (user_id, limit, offset))
                    rows = cur.fetchall()
                else:
                    sql = f"""
                        SELECT ac.id, ac.article_id, ac.content, ac.created_at, ac.comment_type,
                               ms.id AS material_id, ms.title AS parent_title,
                               (SELECT COALESCE(SUM(v.value), 0) FROM comment_votes v WHERE v.comment_id = ac.id) AS rating
                        FROM article_comments ac
                        JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                        WHERE ac.user_id = ?
                          AND ac.status = 'published'
                          AND (ac.comment_type IS NULL OR ac.comment_type != 'answer')
                          AND ms.status = 'approved'
                          AND (lower(ac.content) LIKE lower(?) OR lower(ms.title) LIKE lower(?))
                        GROUP BY ac.id
                        ORDER BY {order_sql}
                    """
                    q_like = f"%{search_q}%"
                    cur.execute(sql, (user_id, q_like, q_like))
                    rows = cur.fetchall()

            items = []
            q_lower = search_q.lower() if search_q else ""
            for r in rows:
                content = r["content"] or ""
                p_title = r["parent_title"] or "Материал сообщества"
                if q_lower:
                    if q_lower not in content.lower() and q_lower not in p_title.lower():
                        continue

                cid = r["id"]
                aid = r["article_id"]
                rating_val = int(r["rating"] or 0)
                snippet = make_content_snippet(content)
                date_str = format_date_ru(r["created_at"])
                permalink = f"article.html?id={urllib.parse.quote(aid)}#comment-{urllib.parse.quote(cid)}"

                items.append({
                    "id": cid,
                    "commentId": cid,
                    "articleId": aid,
                    "materialId": r["material_id"] or aid,
                    "parentTitle": p_title,
                    "title": p_title,
                    "content": content,
                    "text": content,
                    "contentSnippet": snippet,
                    "snippet": snippet,
                    "rating": rating_val,
                    "score": rating_val,
                    "createdAt": r["created_at"],
                    "date": date_str,
                    "commentType": r["comment_type"] or "comment",
                    "type": "comment",
                    "materialType": "comment",
                    "url": permalink,
                    "permalink": permalink
                })

            if total_count is not None:
                total_count_val = total_count
                paged_items = items
                has_more = (offset + limit) < total_count_val
            else:
                if sort_by in ("rating", "popular", "top"):
                    items.sort(key=lambda x: (x.get("rating", 0), x.get("createdAt") or "", x.get("id") or ""), reverse=True)
                else:
                    items.sort(key=lambda x: (x.get("createdAt") or "", x.get("id") or ""), reverse=True)
                total_count_val = len(items)
                paged_items = items[offset : offset + limit]
                has_more = (offset + limit) < total_count_val

            self.send_json_response(200, {
                "success": True,
                "items": paged_items,
                "comments": paged_items,
                "totalCount": total_count_val,
                "total": total_count_val,
                "limit": limit,
                "offset": offset,
                "hasMore": has_more
            })
        finally:
            conn.close()
