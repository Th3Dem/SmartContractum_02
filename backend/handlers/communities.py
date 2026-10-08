"""Clubs, companies and directions endpoints."""
import datetime
import json
import urllib.parse
import uuid

from backend.companies import normalize_website
from backend.config import MAX_JSON_BODY_BYTES
from backend.content import STANDARD_TOPICS, slugify
from backend.db import can_user_publish_for_company


class CommunitiesHandlers:
    def handle_get_clubs(self, parsed_url):
        """GET /api/clubs returns catalog of professional communities."""
        query = urllib.parse.parse_qs(parsed_url.query)
        search_query = (query.get("search", [""])[0] or "").strip().lower()
        direction_filter = (query.get("direction", [""])[0] or query.get("topic", [""])[0] or "").strip()

        user = self.get_current_user()
        user_subs = set()
        user_exceptions = set()
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            if user:
                cur.execute("SELECT target_type, target_id FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                user_subs = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}
                cur.execute("SELECT target_type, target_id FROM user_feed_exceptions WHERE user_id = ?", (user["id"],))
                user_exceptions = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}

            cur.execute("SELECT * FROM clubs ORDER BY created_at ASC")
            club_rows = cur.fetchall()

            cur.execute("SELECT publication_settings FROM moderation_submissions WHERE status = 'approved'")
            article_counts = {}
            for r in cur.fetchall():
                try:
                    s = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                    cid = s.get("clubId")
                    if cid:
                        article_counts[cid] = article_counts.get(cid, 0) + 1
                except Exception:
                    pass

            cur.execute("SELECT target_id, COUNT(*) AS cnt FROM user_subscriptions WHERE target_type = 'club' GROUP BY target_id")
            sub_counts = {r["target_id"]: r["cnt"] for r in cur.fetchall()}

        clubs_list = []
        for r in club_rows:
            cid = r["id"]
            title = r["title"]
            desc = r["description"]
            rules = r["rules"]
            directions = json.loads(r["directions"]) if r["directions"] else []
            tags = json.loads(r["tags"]) if r["tags"] else []

            if direction_filter and direction_filter != "all":
                if direction_filter not in directions:
                    continue

            if search_query:
                haystack = f"{title} {desc} {rules or ''} {' '.join(tags)}".lower()
                if not all(w in haystack for w in search_query.split()):
                    continue

            clubs_list.append({
                "id": cid,
                "title": title,
                "description": desc,
                "avatar": r["avatar"],
                "rules": rules,
                "ownerId": r["owner_id"],
                "directions": directions,
                "tags": tags,
                "articlesCount": article_counts.get(cid, 0),
                "subscribersCount": sub_counts.get(cid, 0),
                "isSubscribed": ("club", cid) in user_subs,
                "isExcluded": ("club", cid) in user_exceptions,
                "createdAt": r["created_at"],
                "updatedAt": r["updated_at"]
            })

        self.send_json_response(200, {
            "success": True,
            "clubs": clubs_list,
            "total": len(clubs_list)
        })

    def handle_get_club_detail(self, club_id: str):
        """GET /api/clubs/<id> returns detail for a single club."""
        user = self.get_current_user()
        user_subs = set()
        user_exceptions = set()
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            if user:
                cur.execute("SELECT target_type, target_id FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                user_subs = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}
                cur.execute("SELECT target_type, target_id FROM user_feed_exceptions WHERE user_id = ?", (user["id"],))
                user_exceptions = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}

            cur.execute("SELECT * FROM clubs WHERE id = ?", (club_id,))
            row = cur.fetchone()
            if not row:
                self.send_json_response(404, {"success": False, "error": f"Клуб '{club_id}' не найден"})
                return

            cur.execute("SELECT COUNT(*) AS cnt FROM user_subscriptions WHERE target_type = 'club' AND target_id = ?", (club_id,))
            sub_count = cur.fetchone()["cnt"]

            cur.execute("SELECT publication_settings FROM moderation_submissions WHERE status = 'approved'")
            art_cnt = 0
            for r in cur.fetchall():
                try:
                    s = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                    if s.get("clubId") == club_id:
                        art_cnt += 1
                except Exception:
                    pass

        directions = json.loads(row["directions"]) if row["directions"] else []
        tags = json.loads(row["tags"]) if row["tags"] else []

        club_data = {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "avatar": row["avatar"],
            "rules": row["rules"],
            "ownerId": row["owner_id"],
            "directions": directions,
            "tags": tags,
            "articlesCount": art_cnt,
            "subscribersCount": sub_count,
            "isSubscribed": ("club", club_id) in user_subs,
            "isExcluded": ("club", club_id) in user_exceptions,
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"]
        }

        self.send_json_response(200, {
            "success": True,
            "club": club_data
        })

    def handle_post_club(self):
        """POST /api/clubs creates a new club with current user as owner."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if data is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Unauthorized", "requireAuth": True})
            return

        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()
        if not title:
            self.send_json_response(400, {"success": False, "error": "Название клуба обязательно"})
            return
        if not description:
            self.send_json_response(400, {"success": False, "error": "Описание клуба обязательно"})
            return

        rules = (data.get("rules") or "").strip()
        avatar = data.get("avatar")
        directions = data.get("directions") or []
        tags = data.get("tags") or []
        if isinstance(directions, str):
            directions = [d.strip() for d in directions.split(",") if d.strip()]
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        club_id = slugify(title)
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM clubs WHERE id = ?", (club_id,))
            if cur.fetchone():
                club_id = f"{club_id}-{uuid.uuid4().hex[:4]}"

            conn.execute("""
                INSERT INTO clubs (id, title, description, avatar, rules, owner_id, directions, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                club_id, title, description, avatar, rules, user["id"],
                json.dumps(directions, ensure_ascii=False),
                json.dumps(tags, ensure_ascii=False),
                now_str, now_str
            ))

            conn.execute("""
                INSERT OR IGNORE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                VALUES (?, 'club', ?, ?, ?)
            """, (user["id"], club_id, title, now_str))

        self.send_json_response(201, {
            "success": True,
            "club": {
                "id": club_id,
                "title": title,
                "description": description,
                "avatar": avatar,
                "rules": rules,
                "ownerId": user["id"],
                "directions": directions,
                "tags": tags,
                "articlesCount": 0,
                "subscribersCount": 1,
                "isSubscribed": True,
                "createdAt": now_str
            }
        })

    def handle_get_companies(self, parsed_url):
        """GET /api/companies returns catalog of corporate blogs."""
        query = urllib.parse.parse_qs(parsed_url.query)
        search_query = (query.get("search", [""])[0] or "").strip().lower()
        direction_filter = (query.get("direction", [""])[0] or query.get("topic", [""])[0] or "").strip()
        topics_filter_raw = (query.get("topics", [""])[0] or "").strip()
        topics_list = [t.strip() for t in topics_filter_raw.split(",") if t.strip()] if topics_filter_raw else []
        if direction_filter and direction_filter != "all" and direction_filter not in topics_list:
            topics_list.append(direction_filter)

        sort_param = (query.get("sort", ["popular"])[0] or "popular").strip().lower()
        manageable_param = (query.get("manageable", ["0"])[0] or "").strip().lower()
        mine_param = (query.get("mine", ["0"])[0] or "").strip().lower()
        only_manageable = manageable_param in ("1", "true", "yes") or mine_param in ("1", "true", "yes")

        user = self.get_current_user()
        user_subs = set()
        user_exceptions = set()
        comps_list = []
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            if user:
                cur.execute("SELECT target_type, target_id FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                user_subs = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}
                cur.execute("SELECT target_type, target_id FROM user_feed_exceptions WHERE user_id = ?", (user["id"],))
                user_exceptions = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}

            cur.execute("SELECT * FROM companies ORDER BY created_at ASC")
            comp_rows = cur.fetchall()

            cur.execute("SELECT id, draft_id, publication_settings FROM moderation_submissions WHERE status = 'approved'")
            comp_canonical_articles = {}
            article_counts = {}
            for r in cur.fetchall():
                try:
                    s = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                    cid = s.get("companyId")
                    if cid:
                        article_counts[cid] = article_counts.get(cid, 0) + 1
                        if cid not in comp_canonical_articles:
                            comp_canonical_articles[cid] = []
                        canonical_id = r["id"]
                        aliases = {canonical_id}
                        if r["draft_id"]:
                            aliases.add(r["draft_id"])
                        comp_canonical_articles[cid].append(aliases)
                except Exception:
                    pass

            cur.execute("SELECT article_id, COALESCE(SUM(value), 0) AS vote_sum FROM article_votes GROUP BY article_id")
            vote_map = {r["article_id"]: r["vote_sum"] for r in cur.fetchall()}

            cur.execute("SELECT article_id, COUNT(*) AS comment_cnt FROM article_comments WHERE status != 'deleted' GROUP BY article_id")
            comment_map = {r["article_id"]: r["comment_cnt"] for r in cur.fetchall()}

            cur.execute("SELECT target_id, COUNT(*) AS cnt FROM user_subscriptions WHERE target_type = 'company' GROUP BY target_id")
            sub_counts = {r["target_id"]: r["cnt"] for r in cur.fetchall()}

            for r in comp_rows:
                cid = r["id"]
                name = r["name"]
                desc = r["description"]
                spec = r["specialization"]
                website = r["website"]
                directions = json.loads(r["directions"]) if r["directions"] else []

                can_publish = False
                if user:
                    can_publish = can_user_publish_for_company(
                        conn, user["id"], cid, user_role=user.get("role", "user")
                    )

                if only_manageable and not can_publish:
                    continue

                if topics_list:
                    if not any(t in directions for t in topics_list):
                        continue

                if search_query:
                    haystack = f"{name} {desc} {spec} {website or ''}".lower()
                    if not all(w in haystack for w in search_query.split()):
                        continue

                c_rating = 0
                c_comments = 0
                for aliases in comp_canonical_articles.get(cid, []):
                    c_rating += sum(vote_map.get(aid, 0) for aid in aliases)
                    c_comments += sum(comment_map.get(aid, 0) for aid in aliases)

                comps_list.append({
                    "id": cid,
                    "name": name,
                    "description": desc,
                    "specialization": spec,
                    "website": website,
                    "logo": r["logo"],
                    "directions": directions,
                    "ownerId": r["owner_id"],
                    "isVerified": bool(r["is_verified"]),
                    "articlesCount": article_counts.get(cid, 0),
                    "subscribersCount": sub_counts.get(cid, 0),
                    "rating": c_rating,
                    "commentsCount": c_comments,
                    "isSubscribed": ("company", cid) in user_subs,
                    "isExcluded": ("company", cid) in user_exceptions,
                    "canPublish": can_publish,
                    "createdAt": r["created_at"],
                    "updatedAt": r["updated_at"]
                })

        if sort_param == "newest":
            comps_list.sort(key=lambda c: c["createdAt"], reverse=True)
        elif sort_param == "oldest":
            comps_list.sort(key=lambda c: c["createdAt"])
        elif sort_param == "rating":
            comps_list.sort(key=lambda c: (c["rating"], c["subscribersCount"], c["articlesCount"], c["createdAt"]), reverse=True)
        elif sort_param == "discussed":
            comps_list.sort(key=lambda c: (c["commentsCount"], c["subscribersCount"], c["articlesCount"], c["createdAt"]), reverse=True)
        else: # "popular" or default
            comps_list.sort(key=lambda c: (c["subscribersCount"], c["rating"], c["articlesCount"], c["createdAt"]), reverse=True)

        self.send_json_response(200, {
            "success": True,
            "companies": comps_list,
            "total": len(comps_list)
        })

    def handle_get_company_detail(self, company_id: str):
        """GET /api/companies/<id> returns detail for a single company."""
        user = self.get_current_user()
        user_subs = set()
        user_exceptions = set()
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            if user:
                cur.execute("SELECT target_type, target_id FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                user_subs = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}
                cur.execute("SELECT target_type, target_id FROM user_feed_exceptions WHERE user_id = ?", (user["id"],))
                user_exceptions = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}

            cur.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
            row = cur.fetchone()
            if not row:
                self.send_json_response(404, {"success": False, "error": f"Компания '{company_id}' не найдена"})
                return

            cur.execute("SELECT COUNT(*) AS cnt FROM user_subscriptions WHERE target_type = 'company' AND target_id = ?", (company_id,))
            sub_count = cur.fetchone()["cnt"]

            cur.execute("SELECT id, draft_id, publication_settings FROM moderation_submissions WHERE status = 'approved'")
            art_cnt = 0
            company_arts = set()
            for r in cur.fetchall():
                try:
                    s = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                    if s.get("companyId") == company_id:
                        art_cnt += 1
                        company_arts.add(r["id"])
                        if r["draft_id"]:
                            company_arts.add(r["draft_id"])
                except Exception:
                    pass

            c_rating = 0
            c_comments = 0
            if company_arts:
                placeholders = ",".join(["?"] * len(company_arts))
                cur.execute(f"SELECT COALESCE(SUM(value), 0) AS vote_sum FROM article_votes WHERE article_id IN ({placeholders})", list(company_arts))
                vrow = cur.fetchone()
                if vrow and vrow["vote_sum"] is not None:
                    c_rating = vrow["vote_sum"]
                cur.execute(f"SELECT COUNT(*) AS comment_cnt FROM article_comments WHERE status != 'deleted' AND article_id IN ({placeholders})", list(company_arts))
                crow = cur.fetchone()
                if crow and crow["comment_cnt"] is not None:
                    c_comments = crow["comment_cnt"]

            can_publish = False
            if user:
                can_publish = can_user_publish_for_company(
                    conn, user["id"], company_id, user_role=user.get("role", "user")
                )

        directions = json.loads(row["directions"]) if row["directions"] else []

        comp_data = {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "specialization": row["specialization"],
            "website": row["website"],
            "logo": row["logo"],
            "directions": directions,
            "ownerId": row["owner_id"],
            "isVerified": bool(row["is_verified"]),
            "articlesCount": art_cnt,
            "subscribersCount": sub_count,
            "rating": c_rating,
            "commentsCount": c_comments,
            "isSubscribed": ("company", company_id) in user_subs,
            "isExcluded": ("company", company_id) in user_exceptions,
            "canPublish": can_publish,
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"]
        }

        self.send_json_response(200, {
            "success": True,
            "company": comp_data
        })

    def handle_post_company(self):
        """POST /api/companies creates a new company profile with current user as owner."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if data is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Unauthorized", "requireAuth": True})
            return

        name = (data.get("name") or "").strip()
        description = (data.get("description") or "").strip()
        specialization = (data.get("specialization") or "").strip()
        if not name:
            self.send_json_response(400, {"success": False, "error": "Название компании обязательно"})
            return
        if not description:
            self.send_json_response(400, {"success": False, "error": "Описание компании обязательно"})
            return
        if not specialization:
            self.send_json_response(400, {"success": False, "error": "Специализация компании обязательна"})
            return

        website, website_error = normalize_website(data.get("website") if isinstance(data.get("website"), str) else "")
        if website_error:
            self.send_json_response(400, {"success": False, "error": website_error})
            return
        logo = data.get("logo")
        directions = data.get("directions") or []
        if isinstance(directions, str):
            directions = [d.strip() for d in directions.split(",") if d.strip()]

        company_id = slugify(name)
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM companies WHERE id = ?", (company_id,))
            if cur.fetchone():
                company_id = f"{company_id}-{uuid.uuid4().hex[:4]}"

            conn.execute("""
                INSERT INTO companies (id, name, description, specialization, website, logo, directions, owner_id, is_verified, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """, (
                company_id, name, description, specialization, website, logo,
                json.dumps(directions, ensure_ascii=False),
                user["id"], now_str, now_str
            ))

            conn.execute("""
                INSERT OR REPLACE INTO company_members (company_id, user_id, role, created_at)
                VALUES (?, ?, 'owner', ?)
            """, (company_id, user["id"], now_str))

            conn.execute("""
                INSERT OR IGNORE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                VALUES (?, 'company', ?, ?, ?)
            """, (user["id"], company_id, name, now_str))

        self.send_json_response(201, {
            "success": True,
            "company": {
                "id": company_id,
                "name": name,
                "description": description,
                "specialization": specialization,
                "website": website,
                "logo": logo,
                "directions": directions,
                "ownerId": user["id"],
                "isVerified": False,
                "articlesCount": 0,
                "subscribersCount": 1,
                "isSubscribed": True,
                "canPublish": True,
                "createdAt": now_str
            }
        })

    def handle_get_directions(self, parsed_url):
        """GET /api/directions returns catalog of all standard directions / topics."""
        query = urllib.parse.parse_qs(parsed_url.query)
        search_query = (query.get("search", [""])[0] or "").strip().lower()

        from backend.content import TOPICS_DESCRIPTION_MAP
        desc_map = TOPICS_DESCRIPTION_MAP

        user = self.get_current_user()
        user_subs = set()
        user_exceptions = set()
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            if user:
                cur.execute("SELECT target_type, target_id FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                user_subs = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}
                cur.execute("SELECT target_type, target_id FROM user_feed_exceptions WHERE user_id = ?", (user["id"],))
                user_exceptions = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}

            cur.execute("SELECT publication_settings FROM moderation_submissions WHERE status = 'approved'")
            topic_article_counts = {}
            for r in cur.fetchall():
                try:
                    s = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                    for t in s.get("topics") or []:
                        topic_article_counts[t] = topic_article_counts.get(t, 0) + 1
                except Exception:
                    pass

            cur.execute("SELECT target_id, COUNT(*) AS cnt FROM user_subscriptions WHERE target_type = 'topic' GROUP BY target_id")
            topic_sub_counts = {r["target_id"]: r["cnt"] for r in cur.fetchall()}

        directions_list = []
        for tid, ttitle in STANDARD_TOPICS:
            tdesc = desc_map.get(tid, f"Направление «{ttitle}» в экосистеме смарт-контрактов")
            if search_query:
                haystack = f"{tid} {ttitle} {tdesc}".lower()
                if not all(w in haystack for w in search_query.split()):
                    continue

            directions_list.append({
                "id": tid,
                "title": ttitle,
                "description": tdesc,
                "articlesCount": topic_article_counts.get(tid, 0),
                "count": topic_article_counts.get(tid, 0),
                "subscribersCount": topic_sub_counts.get(tid, 0),
                "isSubscribed": ("topic", tid) in user_subs,
                "isExcluded": ("topic", tid) in user_exceptions
            })

        self.send_json_response(200, {
            "success": True,
            "directions": directions_list,
            "total": len(directions_list)
        })
