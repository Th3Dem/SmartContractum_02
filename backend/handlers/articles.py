"""Public feed and single material endpoints."""
import datetime
import json
import urllib.parse

from backend.content import (
    TOPICS_TITLE_MAP,
    calculate_reading_time,
    extract_article_text,
    format_date_ru,
    normalize_keyword,
)
from backend.submissions import resolve_cover_position


def author_profile_names(cur, author_ids):
    """
    Current display names of material authors. The name stored inside old demo materials is only a
    fallback: a real author's materials follow their profile, including after a rename.
    """
    ids = sorted({a for a in author_ids if a})
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    cur.execute(f"SELECT user_id, name FROM user_profiles WHERE user_id IN ({placeholders})", ids)
    return {r["user_id"]: r["name"].strip() for r in cur.fetchall() if r["name"] and r["name"].strip()}


class ArticlesHandlers:
    def handle_articles_api(self, parsed_url):
        """
        Dispatches GET /api/articles or /api/questions requests to single article view or feed list view.
        """
        path = parsed_url.path
        prefix = "/api/articles/" if path.startswith("/api/articles/") else ("/api/questions/" if path.startswith("/api/questions/") else None)
        if prefix:
            article_id = path[len(prefix):].strip()
            if article_id.endswith("/comments"):
                self.handle_get_article_comments(article_id[:-len("/comments")].strip("/"))
                return
            if article_id:
                self.handle_get_article(article_id)
                return

        query = urllib.parse.parse_qs(parsed_url.query)
        if "id" in query and query["id"][0].strip():
            self.handle_get_article(query["id"][0].strip())
            return

        self.handle_get_articles_list(parsed_url)

    def handle_get_article(self, article_id: str):
        """
        GET /api/articles/<id> or GET /api/articles?id=<id>
        Returns full details of an approved publication.
        Returns 404 for drafts, pending/rejected submissions, or non-existent IDs.
        """
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM moderation_submissions WHERE (id = ? OR draft_id = ?) AND status = 'approved' LIMIT 1",
                (article_id, article_id)
            )
            row = cur.fetchone()
            profile_names = author_profile_names(cur, [row["author_id"]]) if row else {}

        if not row:
            self.send_json_response(404, {
                "success": False,
                "error": "Статья не найдена или еще не опубликована"
            })
            return

        try:
            settings = json.loads(row["publication_settings"]) if row["publication_settings"] else {}
        except Exception:
            settings = {}

        try:
            delta = json.loads(row["article_delta"]) if row["article_delta"] else None
        except Exception:
            delta = None

        article_html = row["article_html"] or ""
        reading_time, reading_minutes = calculate_reading_time(article_html)

        author_name = profile_names.get(row["author_id"]) or settings.get("author") or (
            "Пользователь #" + row["author_id"][:6] if row["author_id"] else "Автор SmartContractum"
        )
        author_initials = settings.get("authorInitials") or (
            "".join([part[0].upper() for part in author_name.split()[:2]]) if author_name else "SC"
        )
        author_role = settings.get("authorRole") or ""

        topics = settings.get("topics") or []

        user = self.get_current_user()
        likes_count = 0
        saves_count = 0
        comments_count = 0
        answers_count = 0
        discussion_count = 0
        has_solution = False
        has_liked = False
        has_saved = False
        has_reported = False
        score = 0
        my_vote = 0
        can_vote = False
        is_author = False
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM article_likes WHERE article_id = ?", (row["id"],))
            likes_count = cur.fetchone()["cnt"]
            cur.execute("SELECT COUNT(*) AS cnt FROM article_saves WHERE article_id = ?", (row["id"],))
            saves_count = cur.fetchone()["cnt"]
            target_ids = [row["id"]]
            draft_id = row["draft_id"] if ("draft_id" in row.keys() and row["draft_id"]) else None
            if draft_id and draft_id != row["id"]:
                target_ids.append(draft_id)
            placeholders = ",".join("?" for _ in target_ids)
            cur.execute(f"SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id IN ({placeholders}) AND status = 'published' AND comment_type = 'comment'", tuple(target_ids))
            comments_count = cur.fetchone()["cnt"]
            cur.execute(f"SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id IN ({placeholders}) AND status = 'published' AND comment_type = 'answer'", tuple(target_ids))
            answers_count = cur.fetchone()["cnt"]
            discussion_count = comments_count + answers_count
            cur.execute(f"SELECT 1 FROM article_comments WHERE article_id IN ({placeholders}) AND status = 'published' AND is_solution = 1 LIMIT 1", tuple(target_ids))
            has_solution = cur.fetchone() is not None
            cur.execute("SELECT COALESCE(SUM(value), 0) AS score FROM article_votes WHERE article_id = ?", (row["id"],))
            score_row = cur.fetchone()
            score = score_row["score"] if score_row else 0
            if user:
                cur.execute("SELECT 1 FROM article_likes WHERE article_id = ? AND user_id = ?", (row["id"], user["id"]))
                has_liked = cur.fetchone() is not None
                cur.execute("SELECT 1 FROM article_saves WHERE article_id = ? AND user_id = ?", (row["id"], user["id"]))
                has_saved = cur.fetchone() is not None
                cur.execute(f"SELECT 1 FROM article_reports WHERE article_id IN ({placeholders}) AND user_id = ? LIMIT 1", (*target_ids, user["id"]))
                has_reported = cur.fetchone() is not None
                cur.execute("SELECT value FROM article_votes WHERE article_id = ? AND user_id = ?", (row["id"], user["id"]))
                vote_row = cur.fetchone()
                if vote_row:
                    my_vote = vote_row["value"]
                is_author = bool(row["author_id"] == user["id"])
                can_vote = bool(row["status"] == "approved" and not is_author)

        raw_mat = (settings.get("materialType") or settings.get("type") or "publication").strip().lower()
        if raw_mat in ("article", "post", "news"):
            mat_type = "publication"
        else:
            mat_type = raw_mat

        article_data = {
            "id": row["id"],
            "draftId": row["draft_id"],
            "title": row["title"],
            "authorId": row["author_id"],
            "author_id": row["author_id"],
            "author": author_name,
            "authorInitials": author_initials,
            "authorRole": author_role,
            "date": format_date_ru(row["created_at"]),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "description": settings.get("description") or "",
            "coverImage": settings.get("coverImage") or None,
            "coverPosition": resolve_cover_position(settings),
            "focalPoint": resolve_cover_position(settings),
            "objectPosition": resolve_cover_position(settings),
            "isDemo": bool(settings.get("isDemo") or row["id"].startswith("art-0")),
            "topics": topics,
            "topic": topics[0] if topics else "",
            "targetAudience": settings.get("targetAudience") or None,
            "format": settings.get("format") or None,
            "complexity": settings.get("complexity") or None,
            "keywords": settings.get("keywords") or [],
            "readingTime": reading_time,
            "readingMinutes": reading_minutes,
            "likesCount": likes_count,
            "hasLiked": has_liked,
            "savesCount": saves_count,
            "hasSaved": has_saved,
            "isSaved": has_saved,
            "hasReported": has_reported,
            "isReported": has_reported,
            "score": score,
            "myVote": my_vote,
            "canVote": can_vote,
            "isAuthor": is_author,
            "commentsCount": comments_count,
            "answersCount": answers_count,
            "discussionCount": discussion_count,
            "hasSolution": has_solution,
            "materialType": mat_type,
            "type": mat_type,
            "html": article_html,
            "delta": delta
        }

        self.send_json_response(200, {
            "success": True,
            "article": article_data,
            "savesCount": saves_count,
            "hasSaved": has_saved,
            "isSaved": has_saved,
            "hasReported": has_reported,
            "isReported": has_reported,
            "commentsCount": comments_count,
            "answersCount": answers_count,
            "discussionCount": discussion_count,
            "score": score,
            "myVote": my_vote,
            "canVote": can_vote,
            "isAuthor": is_author
        })

    def handle_get_articles_list(self, parsed_url):
        """
        GET /api/articles
        Query parameters:
          tab: 'focus' (default), 'top', 'new', 'subscriptions'/'my', 'saved', 'all'
          period: 'day', 'week', 'month', 'all' (for tab=top, default 'week')
          search: search string across title, description, keywords, and body
          topic / topics / direction: filter by topic ID
          club / clubId: filter by club ID
          company / companyId: filter by company ID
          audience: filter by target audience ID
          format: filter by format ID
          complexity / complexities: filter by complexity ID(s)
          type / types: filter by material type(s)
          sort: 'popular', 'discussed', 'newest', 'oldest'
          ids: comma-separated list of article IDs (for bookmarks retrieval)
          limit: items per page (default 10)
          offset: offset for pagination (default 0)
        Returns approved articles matching criteria.
        """
        query = urllib.parse.parse_qs(parsed_url.query)
        tab_param = query.get("tab", [None])[0]
        types_raw = (query.get("types", [""])[0] or query.get("type", [""])[0] or query.get("materialType", [""])[0] or "").strip().lower()
        if tab_param is None and types_raw in ("question", "questions"):
            tab_raw = "questions"
        else:
            tab_raw = (tab_param or "all").strip().lower()
        tab = "subscriptions" if tab_raw == "my" else tab_raw
        search_query = (query.get("search", [""])[0] or query.get("q", [""])[0] or "").strip().lower()
        question_status = (query.get("questionStatus", ["all"])[0] or query.get("question_status", ["all"])[0] or query.get("status", ["all"])[0]).strip().lower()

        direction_param = (query.get("direction", [""])[0] or "").strip()
        topics_filter = (query.get("topics", [""])[0] or query.get("topic", [""])[0] or direction_param).strip()
        club_filter = (query.get("club", [""])[0] or query.get("clubId", [""])[0] or "").strip()
        company_filter = (query.get("company", [""])[0] or query.get("companyId", [""])[0] or "").strip()
        is_company_param = (query.get("isCompany", [""])[0] or query.get("is_company", [""])[0] or "").strip().lower()
        is_company_filter = is_company_param in ("1", "true", "yes")

        # Audience filter (supports single or multiple, comma-separated or repeated)
        audiences_raw = query.get("audiences", []) + query.get("audience", [])
        allowed_audiences = set()
        for item in audiences_raw:
            for a in item.split(","):
                a_clean = a.strip()
                if a_clean and a_clean != "all":
                    allowed_audiences.add(a_clean)
        if not allowed_audiences:
            allowed_audiences = None

        # Format filter (supports single or multiple, comma-separated or repeated)
        formats_raw = query.get("formats", []) + query.get("format", [])
        allowed_formats = set()
        for item in formats_raw:
            for f in item.split(","):
                f_clean = f.strip()
                if f_clean and f_clean != "all":
                    allowed_formats.add(f_clean)
        if not allowed_formats:
            allowed_formats = None

        complexity_filter = (query.get("complexities", [""])[0] or query.get("complexity", [""])[0] or "").strip()
        types_filter = types_raw
        sort_by = (query.get("sort", ["newest"])[0] or "newest").strip().lower()
        has_explicit_sort = "sort" in query

        # Period filtering: for tab=top defaults to week; otherwise defaults to all
        default_period = "week" if tab == "top" else "all"
        period_filter = (query.get("period", [default_period])[0] or default_period).strip().lower()
        date_from_str = (query.get("dateFrom", [""])[0] or query.get("date_from", [""])[0] or "").strip()
        date_to_str = (query.get("dateTo", [""])[0] or query.get("date_to", [""])[0] or "").strip()
        ids_filter = (query.get("ids", [""])[0] or "").strip()

        try:
            limit = max(1, min(100, int(query.get("limit", [10])[0])))
        except ValueError:
            limit = 10

        try:
            offset = max(0, int(query.get("offset", [0])[0]))
        except ValueError:
            offset = 0

        allowed_ids = set([x.strip() for x in ids_filter.split(",") if x.strip()]) if ids_filter else None
        if tab == "saved" and allowed_ids is None:
            active_u = self.get_current_user()
            if active_u:
                conn_tmp = self.get_db()
                with conn_tmp:
                    cur_tmp = conn_tmp.cursor()
                    cur_tmp.execute("SELECT article_id FROM article_saves WHERE user_id = ?", (active_u["id"],))
                    allowed_ids = {r["article_id"] for r in cur_tmp.fetchall()}
            else:
                allowed_ids = set()

        if topics_filter and topics_filter != "all":
            req_topics = set([t.strip() for t in topics_filter.split(",") if t.strip()])
        else:
            req_topics = None
        if req_topics and "all" in req_topics:
            req_topics = None

        sub_authors = set()
        sub_topics = set()
        sub_tags = set()
        sub_clubs = set()
        sub_companies = set()
        sub_topics_titles = {}
        sub_tags_titles = {}
        sub_clubs_titles = {}
        sub_companies_titles = {}

        user_types = None
        user_complexities = None

        if tab in ("subscriptions", "my"):
            user = self.get_current_user()
            if not user:
                self.send_json_response(401, {
                    "success": False,
                    "error": "Для просмотра персональной ленты необходимо войти",
                    "requireAuth": True
                })
                return

            conn = self.get_db()
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT target_type, target_id, target_title FROM user_subscriptions WHERE user_id = ?",
                    (user["id"],)
                )
                sub_rows = cur.fetchall()

                cur.execute(
                    "SELECT material_types, complexity_levels FROM user_feed_settings WHERE user_id = ?",
                    (user["id"],)
                )
                fs_row = cur.fetchone()
                if fs_row:
                    try:
                        user_types = json.loads(fs_row["material_types"])
                    except Exception:
                        user_types = None
                    try:
                        user_complexities = json.loads(fs_row["complexity_levels"])
                    except Exception:
                        user_complexities = None

            if not sub_rows:
                self.send_json_response(200, {
                    "success": True,
                    "articles": [],
                    "total": 0,
                    "limit": limit,
                    "offset": offset,
                    "hasMore": False,
                    "topicCounts": {},
                    "tab": tab_raw,
                    "noSubscriptions": True
                })
                return

            for sr in sub_rows:
                stype = sr["target_type"]
                sid = sr["target_id"]
                stitle = sr["target_title"]
                if stype == "author":
                    sub_authors.add(sid)
                elif stype == "topic":
                    sub_topics.add(sid)
                    sub_topics_titles[sid] = stitle
                elif stype == "tag":
                    norm_t = normalize_keyword(sid).lstrip('#').strip().lower()
                    sub_tags.add(norm_t)
                    sub_tags_titles[norm_t] = stitle
                elif stype == "club":
                    sub_clubs.add(sid)
                    sub_clubs_titles[sid] = stitle
                elif stype == "company":
                    sub_companies.add(sid)
                    sub_companies_titles[sid] = stitle

        is_publications_tab = tab in ("all", "publications", "pubs", "articles", "focus", "top", "new")
        is_questions_tab = (tab == "questions")

        # Determine effective types filter
        if is_questions_tab:
            allowed_types = {"question"}
        elif is_publications_tab:
            if types_filter and types_filter != "all":
                requested = set([t.strip().lower() for t in types_filter.split(",") if t.strip()])
                allowed_types = {t for t in requested if t not in ("question", "questions")}
                if not allowed_types:
                    allowed_types = {"__none__"}
            else:
                allowed_types = {"publication", "article", "post", "news"}
        elif types_filter and types_filter != "all":
            allowed_types = set([t.strip().lower() for t in types_filter.split(",") if t.strip()])
        elif tab in ("subscriptions", "my") and user_types:
            allowed_types = set([t.strip().lower() for t in user_types if t.strip()])
        else:
            allowed_types = None

        if allowed_types and "all" in allowed_types and not is_publications_tab and not is_questions_tab:
            allowed_types = None

        # Determine effective complexity filter
        if complexity_filter and complexity_filter != "all":
            allowed_complexities = set([c.strip().lower() for c in complexity_filter.split(",") if c.strip()])
        elif tab in ("subscriptions", "my") and user_complexities:
            allowed_complexities = set([c.strip().lower() for c in user_complexities if c.strip()])
        else:
            allowed_complexities = None

        if allowed_complexities and "all" in allowed_complexities:
            allowed_complexities = None

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        cutoff_72h_dt = now_utc - datetime.timedelta(hours=72)
        cutoff_72h_str = cutoff_72h_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                query_sql = "SELECT * FROM moderation_submissions WHERE status = 'approved'"
                query_params = []
                if company_filter:
                    query_sql += " AND json_extract(publication_settings, '$.companyId') = ?"
                    query_params.append(company_filter)
                elif is_company_filter:
                    query_sql += " AND json_extract(publication_settings, '$.companyId') IS NOT NULL AND json_extract(publication_settings, '$.companyId') != ''"
                query_sql += " ORDER BY created_at DESC"
                cur.execute(query_sql, tuple(query_params))
                rows = cur.fetchall()
                profile_names = author_profile_names(cur, [r["author_id"] for r in rows])

                # Pre-fetch counts for likes, saves and comments
                cur.execute("SELECT article_id, COUNT(*) AS cnt FROM article_likes GROUP BY article_id")
                likes_counts = {r["article_id"]: r["cnt"] for r in cur.fetchall()}

                cur.execute("SELECT article_id, COUNT(*) AS cnt FROM article_saves GROUP BY article_id")
                saves_counts = {r["article_id"]: r["cnt"] for r in cur.fetchall()}

                cur.execute("SELECT article_id, COALESCE(SUM(value), 0) AS score FROM article_votes GROUP BY article_id")
                article_scores = {r["article_id"]: r["score"] for r in cur.fetchall()}

                cur.execute("SELECT article_id, COUNT(*) AS cnt FROM article_comments WHERE status = 'published' AND comment_type = 'comment' GROUP BY article_id")
                comments_counts = {r["article_id"]: r["cnt"] for r in cur.fetchall()}

                cur.execute("SELECT article_id, COUNT(*) AS cnt FROM article_comments WHERE status = 'published' AND comment_type = 'answer' GROUP BY article_id")
                answers_counts = {r["article_id"]: r["cnt"] for r in cur.fetchall()}

                cur.execute("SELECT DISTINCT article_id FROM article_comments WHERE status = 'published' AND is_solution = 1")
                solved_article_ids = {r["article_id"] for r in cur.fetchall()}

                comment_search_map = {}
                if search_query:
                    cur.execute("SELECT article_id, content FROM article_comments WHERE status = 'published' AND comment_type = 'answer'")
                    for cr in cur.fetchall():
                        aid = cr["article_id"]
                        if aid not in comment_search_map:
                            comment_search_map[aid] = []
                        comment_search_map[aid].append(cr["content"])

                # 72h window counts for focus gravity score
                cur.execute("SELECT article_id, COUNT(*) AS cnt FROM article_likes WHERE created_at >= ? GROUP BY article_id", (cutoff_72h_str,))
                likes_72h_counts = {r["article_id"]: r["cnt"] for r in cur.fetchall()}

                cur.execute("SELECT article_id, COUNT(*) AS cnt FROM article_comments WHERE status = 'published' AND created_at >= ? GROUP BY article_id", (cutoff_72h_str,))
                comments_72h_counts = {r["article_id"]: r["cnt"] for r in cur.fetchall()}

                current_user = self.get_current_user()
                user_likes = set()
                user_saves = set()
                user_reports = set()
                user_votes = {}
                exc_authors = set()
                exc_topics = set()
                exc_tags = set()
                exc_clubs = set()
                exc_companies = set()
                if current_user:
                    cur.execute("SELECT article_id FROM article_likes WHERE user_id = ?", (current_user["id"],))
                    user_likes = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id FROM article_saves WHERE user_id = ?", (current_user["id"],))
                    user_saves = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id FROM article_reports WHERE user_id = ?", (current_user["id"],))
                    user_reports = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id, value FROM article_votes WHERE user_id = ?", (current_user["id"],))
                    user_votes = {r["article_id"]: r["value"] for r in cur.fetchall()}
                    cur.execute("SELECT target_type, target_id FROM user_feed_exceptions WHERE user_id = ?", (current_user["id"],))
                    for r in cur.fetchall():
                        ttype = r["target_type"]
                        tid = r["target_id"]
                        if ttype == "author":
                            exc_authors.add(tid)
                        elif ttype == "topic":
                            exc_topics.add(tid)
                        elif ttype == "tag":
                            exc_tags.add(normalize_keyword(tid).lstrip('#').strip().lower())
                        elif ttype == "club":
                            exc_clubs.add(tid)
                        elif ttype == "company":
                            exc_companies.add(tid)
        finally:
            conn.close()

        topic_counts = {}
        filtered_articles = []
        seen_article_ids = set()

        for row in rows:
            art_id = row["id"]
            if art_id in seen_article_ids:
                continue

            try:
                settings = json.loads(row["publication_settings"]) if row["publication_settings"] else {}
            except Exception:
                settings = {}

            draft_id = row["draft_id"]
            raw_art_type = (settings.get("materialType") or settings.get("type") or "publication").strip().lower()
            if raw_art_type in ("article", "post", "news", "pubs"):
                art_type = "publication"
            else:
                art_type = raw_art_type

            if is_questions_tab and art_type != "question":
                continue
            if is_publications_tab and art_type == "question":
                continue

            topics = settings.get("topics") or []
            for t in topics:
                topic_counts[t] = topic_counts.get(t, 0) + 1

            # Author metadata
            raw_author = settings.get("author")
            if isinstance(raw_author, dict):
                raw_author = raw_author.get("name")
            author_name = profile_names.get(row["author_id"]) or raw_author or (
                "Пользователь #" + row["author_id"][:6] if row["author_id"] else "Автор SmartContractum"
            )
            author_initials = settings.get("authorInitials") or (
                "".join([part[0].upper() for part in str(author_name).split()[:2]]) if author_name else "SC"
            )
            author_role = settings.get("authorRole") or ""
            keywords = settings.get("keywords") or []
            norm_kws = [normalize_keyword(k).lstrip('#').strip().lower() for k in keywords]

            art_club_id = settings.get("clubId")
            art_company_id = settings.get("companyId")

            # Club filter
            if club_filter and art_club_id != club_filter:
                continue

            # Company filter
            if is_company_filter and not art_company_id:
                continue
            if company_filter and art_company_id != company_filter:
                continue

            # Priority of exceptions:
            # Publication is hidden if author, topic, keyword, club, or company is in user exceptions.
            # Applies to all feed modes and searches. Does NOT hide when tab=saved or bookmarks (allowed_ids).
            is_excluded = (
                (row["author_id"] in exc_authors) or
                (author_name in exc_authors) or
                any(t in exc_topics for t in topics) or
                any(nk in exc_tags for nk in norm_kws) or
                (art_club_id and art_club_id in exc_clubs) or
                (art_company_id and art_company_id in exc_companies)
            )
            if is_excluded and tab != "saved" and allowed_ids is None:
                continue

            # Period filtering
            created_at_dt = None
            try:
                created_at_dt = datetime.datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            except Exception:
                pass

            if (period_filter == "day" or (tab == "top" and period_filter == "day")) and created_at_dt:
                if (now_utc - created_at_dt).total_seconds() > 86400:
                    continue
            elif (period_filter == "week" or (tab == "top" and period_filter == "week")) and created_at_dt:
                if (now_utc - created_at_dt).total_seconds() > 7 * 86400:
                    continue
            elif (period_filter == "month" or (tab == "top" and period_filter == "month")) and created_at_dt:
                if (now_utc - created_at_dt).total_seconds() > 30 * 86400:
                    continue
            elif period_filter == "year" and created_at_dt:
                if (now_utc - created_at_dt).total_seconds() > 365 * 86400:
                    continue
            elif (period_filter == "custom" or date_from_str or date_to_str) and created_at_dt:
                if date_from_str:
                    try:
                        df = datetime.date.fromisoformat(date_from_str)
                        df_dt = datetime.datetime(df.year, df.month, df.day, 0, 0, 0, tzinfo=datetime.timezone.utc)
                        if created_at_dt < df_dt:
                            continue
                    except Exception:
                        pass
                if date_to_str:
                    try:
                        dt = datetime.date.fromisoformat(date_to_str)
                        dt_dt = datetime.datetime(dt.year, dt.month, dt.day, 23, 59, 59, 999999, tzinfo=datetime.timezone.utc)
                        if created_at_dt > dt_dt:
                            continue
                    except Exception:
                        pass

            # IDs filtering (e.g. bookmarks)
            if allowed_ids is not None:
                if art_id not in allowed_ids and draft_id not in allowed_ids:
                    continue

            # Material type filtering (Issue #61, #162: publication or question)
            if is_questions_tab:
                if art_type != "question":
                    continue
                a_cnt = answers_counts.get(art_id, 0)
                is_sol = (art_id in solved_article_ids)
                if question_status == "unanswered" and a_cnt > 0:
                    continue
                if question_status == "solved" and not is_sol:
                    continue
            elif is_publications_tab:
                if art_type == "question":
                    continue
                if allowed_types is not None:
                    norm_allowed = []
                    for at in allowed_types:
                        at_norm = at.strip().lower()
                        if at_norm in ("article", "post", "news", "publication", "publications", "pubs"):
                            at_norm = "publication"
                        norm_allowed.append(at_norm)
                    if art_type not in norm_allowed:
                        continue
            elif allowed_types is not None:
                norm_allowed = []
                for at in allowed_types:
                    at_norm = at.strip().lower()
                    if at_norm in ("article", "post", "news", "publication", "publications", "pubs"):
                        at_norm = "publication"
                    elif at_norm in ("question", "questions"):
                        at_norm = "question"
                    norm_allowed.append(at_norm)
                if art_type not in norm_allowed:
                    continue

            # Complexity filtering
            compl = (settings.get("complexity") or "").strip().lower()
            if allowed_complexities is not None:
                is_unspecified = compl in ("", "none", "unspecified")
                if is_unspecified:
                    if "unspecified" not in allowed_complexities and "none" not in allowed_complexities:
                        continue
                else:
                    if compl not in allowed_complexities:
                        continue

            # Topic filtering
            if req_topics is not None:
                if not any(t in req_topics for t in topics):
                    continue

            # Audience filtering (multi-selection support)
            target_audience = settings.get("targetAudience") or ""
            if allowed_audiences is not None:
                if target_audience not in allowed_audiences:
                    continue

            # Format filtering (multi-selection support)
            fmt = settings.get("format") or ""
            if allowed_formats is not None:
                if fmt not in allowed_formats:
                    continue

            # Search query filtering across title, author, role, description, keywords, club, company, body, and comments/answers
            title = row["title"] or ""
            desc = settings.get("description") or ""
            club_title = settings.get("clubTitle") or ""
            company_name = settings.get("companyName") or ""
            article_text = extract_article_text(row["article_html"] or "")

            matched_answer_snippet = None
            if search_query:
                search_haystack = f"{title} {author_name} {author_role} {club_title} {company_name} {desc} {' '.join(keywords)} {article_text}".lower()
                words = search_query.split()
                matches_main = all(w in search_haystack for w in words)
                matches_comment = False

                if not matches_main and is_questions_tab:
                    # Check comments/answers
                    for c_text in comment_search_map.get(art_id, []):
                        c_lower = c_text.lower()
                        if all(w in c_lower for w in words):
                            matches_comment = True
                            first_w = words[0]
                            pos = c_lower.find(first_w)
                            sp = max(0, pos - 40)
                            ep = min(len(c_text), pos + len(first_w) + 60)
                            matched_answer_snippet = ("..." if sp > 0 else "") + c_text[sp:ep].strip() + ("..." if ep < len(c_text) else "")
                            break

                if not matches_main and not matches_comment:
                    continue

            # Check subscription filter for "subscriptions" / "my" feed
            subscription_reason = None
            if tab in ("subscriptions", "my"):
                if row["author_id"] in sub_authors or author_name in sub_authors:
                    subscription_reason = f"Вы подписаны на автора {author_name}"
                elif art_club_id and art_club_id in sub_clubs:
                    c_title = sub_clubs_titles.get(art_club_id) or club_title or art_club_id
                    subscription_reason = f"Вы подписаны на клуб «{c_title}»"
                elif art_company_id and art_company_id in sub_companies:
                    cp_name = sub_companies_titles.get(art_company_id) or company_name or art_company_id
                    subscription_reason = f"Вы подписаны на компанию «{cp_name}»"
                else:
                    matched_topic = next((t for t in topics if t in sub_topics), None)
                    if matched_topic:
                        topic_title = sub_topics_titles.get(matched_topic) or TOPICS_TITLE_MAP.get(matched_topic, matched_topic)
                        subscription_reason = f"Вы подписаны на тему «{topic_title}»"
                    else:
                        matched_tag = next((nk for nk in norm_kws if nk in sub_tags), None)
                        if matched_tag:
                            tag_title = sub_tags_titles.get(matched_tag) or matched_tag
                            subscription_reason = f"Вы подписаны на #{tag_title}"

                if not subscription_reason:
                    continue

            reading_time, reading_minutes = calculate_reading_time(row["article_html"] or "")

            # Focus gravity formula: (likes_72h * 2 + comments_72h * 3) / ((age_hours + 2.0) ** 1.5)
            age_hours = max(0.0, (now_utc - created_at_dt).total_seconds() / 3600.0) if created_at_dt else 100.0
            l_72 = likes_72h_counts.get(art_id, 0)
            c_72 = comments_72h_counts.get(art_id, 0)
            focus_score = (l_72 * 2.0 + c_72 * 3.0) / ((age_hours + 2.0) ** 1.5)

            seen_article_ids.add(art_id)
            filtered_articles.append({
                "id": row["id"],
                "draftId": row["draft_id"],
                "title": row["title"],
                "authorId": row["author_id"],
                "author_id": row["author_id"],
                "author": author_name,
                "authorInitials": author_initials,
                "authorRole": author_role,
                "date": format_date_ru(row["created_at"]),
                "createdAt": row["created_at"],
                "description": desc,
                "coverImage": settings.get("coverImage") or None,
                "coverPosition": resolve_cover_position(settings),
                "focalPoint": resolve_cover_position(settings),
                "objectPosition": resolve_cover_position(settings),
                "isDemo": bool(settings.get("isDemo") or row["id"].startswith("art-0")),
                "topics": topics,
                "topic": topics[0] if topics else "",
                "targetAudience": target_audience,
                "format": fmt,
                "complexity": compl,
                "keywords": keywords,
                "readingTime": reading_time,
                "readingMinutes": reading_minutes,
                "subscriptionReason": subscription_reason,
                "likesCount": likes_counts.get(art_id, 0),
                "hasLiked": art_id in user_likes,
                "savesCount": saves_counts.get(art_id, 0),
                "hasSaved": art_id in user_saves,
                "isSaved": art_id in user_saves,
                "hasReported": (art_id in user_reports or (draft_id and draft_id in user_reports)),
                "isReported": (art_id in user_reports or (draft_id and draft_id in user_reports)),
                "score": article_scores.get(art_id, 0),
                "myVote": user_votes.get(art_id, 0),
                "canVote": bool(current_user and row["status"] == "approved" and row["author_id"] != current_user["id"]),
                "isAuthor": bool(current_user and row["author_id"] == current_user["id"]),
                "commentsCount": comments_counts.get(art_id, 0),
                "answersCount": answers_counts.get(art_id, 0),
                "discussionCount": comments_counts.get(art_id, 0) + answers_counts.get(art_id, 0),
                "hasSolution": art_id in solved_article_ids,
                "matchedAnswerSnippet": matched_answer_snippet,
                "materialType": art_type,
                "material_type": art_type,
                "type": art_type,
                "companyId": art_company_id,
                "companyName": company_name or None,
                "clubId": art_club_id,
                "clubTitle": club_title or None,
                "focusScore": round(focus_score, 4)
            })

        # Apply sorting logic
        if has_explicit_sort:
            if sort_by == "rating":
                filtered_articles.sort(key=lambda a: (a.get("score", 0), a.get("createdAt", ""), a.get("id", "")), reverse=True)
            elif sort_by == "popular":
                filtered_articles.sort(key=lambda a: (a.get("likesCount", 0), a.get("createdAt", ""), a.get("id", "")), reverse=True)
            elif sort_by == "discussed":
                filtered_articles.sort(key=lambda a: (a.get("discussionCount", a.get("commentsCount", 0)), a.get("createdAt", "")), reverse=True)
            elif sort_by in ("oldest", "asc"):
                filtered_articles.reverse()
            elif sort_by in ("newest", "desc"):
                filtered_articles.sort(key=lambda a: (a.get("createdAt", ""), a.get("id", "")), reverse=True)
        else:
            if tab == "focus":
                # Default "В фокусе": gravity popularity with fallback to createdAt
                filtered_articles.sort(key=lambda a: (a.get("focusScore", 0.0), a.get("createdAt", ""), a.get("id", "")), reverse=True)
            elif tab == "top":
                # "Топ": sort by (score, commentsCount, createdAt, id) DESC strictly
                filtered_articles.sort(key=lambda a: (a.get("score", 0), a.get("commentsCount", 0), a.get("createdAt", ""), a.get("id", "")), reverse=True)
            elif tab == "new":
                # "Новое": strict chronological DESC
                filtered_articles.sort(key=lambda a: (a.get("createdAt", ""), a.get("id", "")), reverse=True)
            elif tab in ("subscriptions", "my"):
                # "Подписки": chronological DESC
                filtered_articles.sort(key=lambda a: (a.get("createdAt", ""), a.get("id", "")), reverse=True)
            else:
                # "Все публикации", "Вопросы": newest by default
                filtered_articles.sort(key=lambda a: (a.get("createdAt", ""), a.get("id", "")), reverse=True)

        total = len(filtered_articles)
        paged_articles = filtered_articles[offset : offset + limit]
        has_more = (offset + limit) < total

        self.send_json_response(200, {
            "success": True,
            "articles": paged_articles,
            "items": paged_articles,
            "total": total,
            "limit": limit,
            "offset": offset,
            "hasMore": has_more,
            "topicCounts": topic_counts,
            "tab": tab_raw,
            "noSubscriptions": False
        })

    def handle_get_unanswered_questions(self):
        """
        GET /api/questions/unanswered
        Returns up to 3 approved questions that have 0 published answers.
        """
        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT ms.id, ms.draft_id, ms.title, ms.publication_settings, ms.created_at,
                           (SELECT COUNT(*) FROM article_comments ac WHERE ac.article_id = ms.id AND ac.status = 'published' AND ac.comment_type = 'answer') AS ans_cnt
                    FROM moderation_submissions ms
                    WHERE ms.status = 'approved'
                      AND (
                        json_extract(ms.publication_settings, '$.materialType') = 'question'
                        OR json_extract(ms.publication_settings, '$.type') = 'question'
                      )
                      AND ans_cnt = 0
                    ORDER BY ms.created_at DESC
                    LIMIT 3
                """)
                rows = cur.fetchall()

            questions = []
            for r in rows:
                try:
                    st = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                except Exception:
                    st = {}
                questions.append({
                    "id": r["id"],
                    "title": r["title"],
                    "createdAt": r["created_at"],
                    "date": format_date_ru(r["created_at"]),
                    "topic": (st.get("topics") or [""])[0] if st.get("topics") else "",
                    "answersCount": 0,
                    "material_type": "question",
                    "materialType": "question"
                })

            self.send_json_response(200, {
                "success": True,
                "questions": questions,
                "items": questions
            })
        finally:
            conn.close()
