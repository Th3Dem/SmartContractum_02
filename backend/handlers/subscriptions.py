"""Subscriptions, feed exceptions and feed settings of the current user."""
import datetime
import json
import urllib.parse

from backend.config import LEGACY_MATERIAL_TYPES, MAX_JSON_BODY_BYTES, VALID_MATERIAL_TYPES
from backend.content import STANDARD_TOPICS, normalize_keyword
from backend.identity import author_identities
from backend.handlers.author_notifications import clear_author_notifications


class SubscriptionsHandlers:
    def handle_get_subscriptions(self):
        """GET /api/subscriptions returns user's active subscriptions."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Unauthorized", "requireAuth": True})
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT target_type, target_id, target_title, created_at 
                FROM user_subscriptions WHERE user_id = ? ORDER BY id ASC
            """, (user["id"],))
            rows = cur.fetchall()

        subs = {"authors": [], "topics": [], "tags": [], "clubs": [], "companies": []}
        for r in rows:
            t = r["target_type"]
            entry = {"id": r["target_id"], "title": r["target_title"], "createdAt": r["created_at"]}
            if t == "author":
                subs["authors"].append(entry)
            elif t == "topic":
                subs["topics"].append(entry)
            elif t == "tag":
                subs["tags"].append(entry)
            elif t == "club":
                subs["clubs"].append(entry)
            elif t == "company":
                subs["companies"].append(entry)

        self.send_json_response(200, {
            "success": True,
            "user": user,
            "subscriptions": subs
        })

    def handle_get_exceptions(self):
        """GET /api/exceptions returns user's active feed exceptions."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(200, {
                "success": True,
                "exceptions": {"authors": [], "topics": [], "tags": [], "clubs": [], "companies": []},
                "total": 0
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT target_type, target_id, target_title, created_at 
                FROM user_feed_exceptions WHERE user_id = ? ORDER BY id ASC
            """, (user["id"],))
            rows = cur.fetchall()

        exceptions = {"authors": [], "topics": [], "tags": [], "clubs": [], "companies": []}
        for r in rows:
            t = r["target_type"]
            entry = {"id": r["target_id"], "title": r["target_title"], "createdAt": r["created_at"]}
            if t == "author":
                exceptions["authors"].append(entry)
            elif t == "topic":
                exceptions["topics"].append(entry)
            elif t == "tag":
                exceptions["tags"].append(entry)
            elif t == "club":
                exceptions["clubs"].append(entry)
            elif t == "company":
                exceptions["companies"].append(entry)

        total = len(exceptions["authors"]) + len(exceptions["topics"]) + len(exceptions["tags"]) + len(exceptions["clubs"]) + len(exceptions["companies"])
        self.send_json_response(200, {
            "success": True,
            "user": user,
            "exceptions": exceptions,
            "total": total
        })

    def handle_subscriptions_toggle(self):
        """POST /api/subscriptions/toggle toggles subscription state."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if data is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Unauthorized", "requireAuth": True})
            return

        target_type = (data.get("targetType") or data.get("target_type") or "").strip().lower()
        raw_id = (data.get("targetId") or data.get("target_id") or "").strip()
        raw_title = (data.get("targetTitle") or data.get("target_title") or "").strip()
        action = data.get("action", "toggle")

        if target_type not in ("author", "topic", "tag", "club", "company"):
            self.send_json_response(400, {"success": False, "error": "targetType must be 'author', 'topic', 'tag', 'club', or 'company'"})
            return

        if not raw_id:
            self.send_json_response(400, {"success": False, "error": "targetId is required"})
            return

        # Normalize tag ID (lowercase, trim extra spaces, remove #)
        if target_type == "tag":
            normalized_id = normalize_keyword(raw_id).lstrip('#').strip().lower()
            title = normalize_keyword(raw_title or raw_id).lstrip('#').strip()
        else:
            normalized_id = raw_id
            title = raw_title or raw_id

        if target_type == "author" and (normalized_id or "").strip() == (user["id"] or "").strip():
            self.send_json_response(400, {
                "success": False,
                "error": "Нельзя подписаться на самого себя",
                "code": "SELF_SUBSCRIPTION_FORBIDDEN"
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id FROM user_subscriptions 
                WHERE user_id = ? AND target_type = ? AND target_id = ?
            """, (user["id"], target_type, normalized_id))
            row = cur.fetchone()

            if action == "subscribe":
                if row:
                    subscribed = True
                else:
                    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute("""
                        INSERT OR IGNORE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user["id"], target_type, normalized_id, title, now_str))
                    cur.execute("""
                        DELETE FROM user_feed_exceptions
                        WHERE user_id = ? AND target_type = ? AND target_id = ?
                    """, (user["id"], target_type, normalized_id))
                    subscribed = True
            elif action == "unsubscribe":
                if row:
                    cur.execute("DELETE FROM user_subscriptions WHERE id = ?", (row["id"],))
                subscribed = False
            else:
                if row:
                    cur.execute("DELETE FROM user_subscriptions WHERE id = ?", (row["id"],))
                    subscribed = False
                else:
                    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute("""
                        INSERT OR IGNORE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user["id"], target_type, normalized_id, title, now_str))
                    cur.execute("""
                        DELETE FROM user_feed_exceptions
                        WHERE user_id = ? AND target_type = ? AND target_id = ?
                    """, (user["id"], target_type, normalized_id))
                    subscribed = True

        followers_count = None
        if target_type == "author":
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) AS cnt FROM user_subscriptions WHERE target_type = 'author' AND target_id = ?", (normalized_id,))
                followers_count = cur.fetchone()["cnt"] or 0

        resp = {
            "success": True,
            "subscribed": subscribed,
            "isSubscribed": subscribed,
            "is_subscribed": subscribed,
            "targetType": target_type,
            "targetId": normalized_id,
            "targetTitle": title
        }
        if followers_count is not None:
            resp["followersCount"] = followers_count

        self.send_json_response(200, resp)

    def handle_exceptions_toggle(self):
        """POST /api/exceptions/toggle toggles exception state."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if data is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Unauthorized", "requireAuth": True})
            return

        target_type = (data.get("targetType") or data.get("target_type") or "").strip().lower()
        raw_id = (data.get("targetId") or data.get("target_id") or "").strip()
        raw_title = (data.get("targetTitle") or data.get("target_title") or "").strip()
        action = data.get("action", "toggle")

        if target_type not in ("author", "topic", "tag", "club", "company"):
            self.send_json_response(400, {"success": False, "error": "targetType must be 'author', 'topic', 'tag', 'club', or 'company'"})
            return

        if not raw_id:
            self.send_json_response(400, {"success": False, "error": "targetId is required"})
            return

        # Normalize tag ID (lowercase, trim extra spaces, remove #)
        if target_type == "tag":
            normalized_id = normalize_keyword(raw_id).lstrip('#').strip().lower()
            title = normalize_keyword(raw_title or raw_id).lstrip('#').strip()
        else:
            normalized_id = raw_id
            title = raw_title or raw_id

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id FROM user_feed_exceptions 
                WHERE user_id = ? AND target_type = ? AND target_id = ?
            """, (user["id"], target_type, normalized_id))
            row = cur.fetchone()

            if action == "exclude":
                if row:
                    excluded = True
                else:
                    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute("""
                        INSERT OR IGNORE INTO user_feed_exceptions (user_id, target_type, target_id, target_title, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user["id"], target_type, normalized_id, title, now_str))
                    cur.execute("""
                        DELETE FROM user_subscriptions
                        WHERE user_id = ? AND target_type = ? AND target_id = ?
                    """, (user["id"], target_type, normalized_id))
                    excluded = True
            elif action == "remove":
                if row:
                    cur.execute("DELETE FROM user_feed_exceptions WHERE id = ?", (row["id"],))
                excluded = False
            else:
                if row:
                    cur.execute("DELETE FROM user_feed_exceptions WHERE id = ?", (row["id"],))
                    excluded = False
                else:
                    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute("""
                        INSERT OR IGNORE INTO user_feed_exceptions (user_id, target_type, target_id, target_title, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user["id"], target_type, normalized_id, title, now_str))
                    # Remove from subscriptions if present (mutual exclusion)
                    cur.execute("""
                        DELETE FROM user_subscriptions
                        WHERE user_id = ? AND target_type = ? AND target_id = ?
                    """, (user["id"], target_type, normalized_id))
                    excluded = True

            # Issue #273: hiding an author also turns their bell off; removing the exclusion does not turn it on
            if excluded and target_type == "author":
                clear_author_notifications(cur, user["id"], [normalized_id])

        self.send_json_response(200, {
            "success": True,
            "excluded": excluded,
            "isExcluded": excluded,
            "is_excluded": excluded,
            "targetType": target_type,
            "targetId": normalized_id,
            "targetTitle": title
        })

    def handle_get_subscription_entities(self, parsed_url=None):
        """GET /api/subscriptions/entities returns catalog of entities available for subscription/exclusion."""
        if parsed_url is None:
            parsed_url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_url.query)
        entity_type = (query.get("type", [""])[0] or "").strip().lower()
        search_query = (query.get("search", [""])[0] or "").strip().lower()

        try:
            limit = max(1, min(100, int(query.get("limit", [20])[0])))
        except ValueError:
            limit = 20

        try:
            offset = max(0, int(query.get("offset", [0])[0]))
        except ValueError:
            offset = 0

        user = self.get_current_user()
        user_subs = set()
        user_exceptions = set()
        conn = self.get_db()
        with conn:
            if user:
                cur = conn.cursor()
                cur.execute("SELECT target_type, target_id FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                for r in cur.fetchall():
                    user_subs.add((r["target_type"], r["target_id"]))
                cur.execute("SELECT target_type, target_id FROM user_feed_exceptions WHERE user_id = ?", (user["id"],))
                for r in cur.fetchall():
                    user_exceptions.add((r["target_type"], r["target_id"]))

            cur = conn.cursor()
            cur.execute("SELECT * FROM moderation_submissions WHERE status = 'approved' ORDER BY created_at DESC")
            rows = cur.fetchall()

            cur.execute("SELECT * FROM clubs ORDER BY created_at ASC")
            club_rows = cur.fetchall()

            cur.execute("SELECT * FROM companies ORDER BY created_at ASC")
            comp_rows = cur.fetchall()
            identities = author_identities(cur, [r["author_id"] for r in rows])

        authors_map = {}
        tags_map = {}
        topics_counts = {}
        club_counts = {}
        comp_counts = {}

        for row in rows:
            try:
                settings = json.loads(row["publication_settings"]) if row["publication_settings"] else {}
            except Exception:
                settings = {}

            author_id = row["author_id"]
            live = identities.get(author_id) or {}
            author_name = live.get("name") or settings.get("author") or "Автор платформы"
            author_role = live.get("specialization") or settings.get("authorRole") or ""
            author_avatar = live.get("avatar") or settings.get("authorAvatar") or settings.get("avatar") or None
            if author_id not in authors_map:
                authors_map[author_id] = {
                    "id": author_id,
                    "title": author_name,
                    "role": author_role,
                    "avatar": author_avatar,
                    "count": 0,
                    "isSubscribed": ("author", author_id) in user_subs,
                    "isExcluded": ("author", author_id) in user_exceptions
                }
            authors_map[author_id]["count"] += 1
            if author_avatar and not authors_map[author_id].get("avatar"):
                authors_map[author_id]["avatar"] = author_avatar

            for t in settings.get("topics") or []:
                topics_counts[t] = topics_counts.get(t, 0) + 1

            for k in settings.get("keywords") or []:
                norm_tag = normalize_keyword(k).lstrip('#').strip().lower()
                display_tag = normalize_keyword(k).lstrip('#').strip()
                if norm_tag:
                    if norm_tag not in tags_map:
                        tags_map[norm_tag] = {
                            "id": norm_tag,
                            "title": display_tag,
                            "count": 0,
                            "isSubscribed": ("tag", norm_tag) in user_subs,
                            "isExcluded": ("tag", norm_tag) in user_exceptions
                        }
                    tags_map[norm_tag]["count"] += 1

            cid = settings.get("clubId")
            if cid:
                club_counts[cid] = club_counts.get(cid, 0) + 1

            cmp_id = settings.get("companyId")
            if cmp_id:
                comp_counts[cmp_id] = comp_counts.get(cmp_id, 0) + 1

        from backend.content import TOPICS_DESCRIPTION_MAP
        desc_map = TOPICS_DESCRIPTION_MAP

        topics_list = []
        for tid, tname in STANDARD_TOPICS:
            topics_list.append({
                "id": tid,
                "title": tname,
                "description": desc_map.get(tid, ""),
                "count": topics_counts.get(tid, 0),
                "isSubscribed": ("topic", tid) in user_subs,
                "isExcluded": ("topic", tid) in user_exceptions
            })

        authors_list = sorted(list(authors_map.values()), key=lambda x: (-x["count"], x["title"]))
        tags_list = sorted(list(tags_map.values()), key=lambda x: (-x["count"], x["title"]))

        clubs_list = []
        for cr in club_rows:
            cid = cr["id"]
            clubs_list.append({
                "id": cid,
                "title": cr["title"],
                "description": cr["description"],
                "count": club_counts.get(cid, 0),
                "isSubscribed": ("club", cid) in user_subs,
                "isExcluded": ("club", cid) in user_exceptions
            })

        companies_list = []
        for cpr in comp_rows:
            cid = cpr["id"]
            companies_list.append({
                "id": cid,
                "title": cpr["name"],
                "name": cpr["name"],
                "description": cpr["description"],
                "specialization": cpr["specialization"],
                "count": comp_counts.get(cid, 0),
                "isSubscribed": ("company", cid) in user_subs,
                "isExcluded": ("company", cid) in user_exceptions
            })

        def match_search(item: dict) -> bool:
            if not search_query:
                return True
            title_match = search_query in (item.get("title") or item.get("name") or "").lower()
            id_match = search_query in (item.get("id") or "").lower()
            role_match = search_query in (item.get("role") or item.get("specialization") or "").lower()
            desc_match = search_query in (item.get("description") or "").lower()
            return title_match or id_match or role_match or desc_match

        if entity_type:
            if entity_type in ("author", "authors"):
                source = authors_list
            elif entity_type in ("topic", "topics"):
                source = topics_list
            elif entity_type in ("tag", "tags"):
                source = tags_list
            elif entity_type in ("club", "clubs"):
                source = clubs_list
            elif entity_type in ("company", "companies"):
                source = companies_list
            else:
                source = []

            filtered_items = [it for it in source if match_search(it)]
            total = len(filtered_items)
            paged_items = filtered_items[offset : offset + limit]
            has_more = (offset + limit) < total

            self.send_json_response(200, {
                "success": True,
                "items": paged_items,
                "total": total,
                "limit": limit,
                "offset": offset,
                "hasMore": has_more
            })
            return

        # Full catalog when entity_type is not specified
        filtered_authors = [it for it in authors_list if match_search(it)]
        filtered_topics = [it for it in topics_list if match_search(it)]
        filtered_tags = [it for it in tags_list if match_search(it)]
        filtered_clubs = [it for it in clubs_list if match_search(it)]
        filtered_companies = [it for it in companies_list if match_search(it)]

        self.send_json_response(200, {
            "success": True,
            "authors": filtered_authors,
            "topics": filtered_topics,
            "tags": filtered_tags,
            "clubs": filtered_clubs,
            "companies": filtered_companies
        })

    def handle_get_feed_settings(self):
        """
        GET /api/user/feed-settings
        Returns feed settings for authenticated user, or default settings for guests.
        """
        user = self.get_current_user()
        default_material_types = ["article", "post", "news", "question"]
        default_complexity_levels = ["all"]

        if not user:
            self.send_json_response(200, {
                "success": True,
                "settings": {
                    "materialTypes": default_material_types,
                    "complexityLevels": default_complexity_levels,
                    "welcomeDismissed": False
                },
                "materialTypes": default_material_types,
                "complexityLevels": default_complexity_levels,
                "welcomeDismissed": False
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT material_types, complexity_levels, welcome_dismissed FROM user_feed_settings WHERE user_id = ?",
                (user["id"],)
            )
            row = cur.fetchone()

        is_welcome_dismissed = False
        if row:
            try:
                m_types = json.loads(row["material_types"])
            except Exception:
                m_types = default_material_types
            try:
                c_levels = json.loads(row["complexity_levels"])
            except Exception:
                c_levels = default_complexity_levels
            if "welcome_dismissed" in row.keys() and row["welcome_dismissed"]:
                is_welcome_dismissed = bool(row["welcome_dismissed"])
        else:
            m_types = default_material_types
            c_levels = default_complexity_levels

        self.send_json_response(200, {
            "success": True,
            "settings": {
                "materialTypes": m_types,
                "complexityLevels": c_levels,
                "welcomeDismissed": is_welcome_dismissed
            },
            "materialTypes": m_types,
            "complexityLevels": c_levels,
            "welcomeDismissed": is_welcome_dismissed
        })

    def handle_post_feed_settings(self):
        """
        POST /api/user/feed-settings
        Saves user feed settings for authenticated user.
        Body: { "materialTypes": [...], "complexityLevels": [...], "welcomeDismissed": bool }
        Returns 401 if unauthenticated.
        Returns 400 if materialTypes is empty ("Выберите хотя бы один тип материала").
        """
        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для сохранения настроек ленты необходимо войти",
                "requireAuth": True
            })
            return

        settings_obj = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload

        # Check for welcome dismissal toggle
        welcome_dismissed = None
        if "welcomeDismissed" in settings_obj:
            welcome_dismissed = 1 if settings_obj["welcomeDismissed"] else 0
        elif "welcome_dismissed" in settings_obj:
            welcome_dismissed = 1 if settings_obj["welcome_dismissed"] else 0

        material_types = settings_obj.get("materialTypes")
        if material_types is None:
            material_types = settings_obj.get("material_types")

        # If this is ONLY a welcomeDismissed toggle without materialTypes:
        if material_types is None and welcome_dismissed is not None:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn = self.get_db()
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT material_types, complexity_levels FROM user_feed_settings WHERE user_id = ?", (user["id"],))
                existing = cur.fetchone()
                if existing:
                    cur.execute("UPDATE user_feed_settings SET welcome_dismissed = ?, updated_at = ? WHERE user_id = ?", (welcome_dismissed, now_iso, user["id"]))
                else:
                    cur.execute(
                        "INSERT INTO user_feed_settings (user_id, material_types, complexity_levels, welcome_dismissed, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (user["id"], json.dumps(["article", "post", "news", "question"]), json.dumps(["all"]), welcome_dismissed, now_iso)
                    )
            self.send_json_response(200, {
                "success": True,
                "welcomeDismissed": bool(welcome_dismissed)
            })
            return

        if material_types is None or not isinstance(material_types, list):
            self.send_json_response(400, {
                "success": False,
                "error": "Выберите хотя бы один тип материала"
            })
            return

        valid_types = []
        for t in material_types:
            if isinstance(t, str):
                norm_t = t.strip().lower()
                if norm_t in LEGACY_MATERIAL_TYPES:
                    norm_t = LEGACY_MATERIAL_TYPES[norm_t]
                if norm_t in VALID_MATERIAL_TYPES and norm_t not in valid_types:
                    valid_types.append(norm_t)

        if not valid_types:
            self.send_json_response(400, {
                "success": False,
                "error": "Выберите хотя бы один тип материала"
            })
            return

        complexity_levels = settings_obj.get("complexityLevels")
        if complexity_levels is None:
            complexity_levels = settings_obj.get("complexity_levels")

        if complexity_levels is None or not isinstance(complexity_levels, list) or len(complexity_levels) == 0:
            clean_levels = ["all"]
        else:
            clean_levels = []
            for c in complexity_levels:
                if isinstance(c, str) and c.strip():
                    clean_levels.append(c.strip().lower())
            if not clean_levels:
                clean_levels = ["all"]

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT welcome_dismissed FROM user_feed_settings WHERE user_id = ?", (user["id"],))
            ex_row = cur.fetchone()
            curr_wel = ex_row["welcome_dismissed"] if (ex_row and "welcome_dismissed" in ex_row.keys()) else 0
            if welcome_dismissed is not None:
                curr_wel = welcome_dismissed

            conn.execute("""
                INSERT INTO user_feed_settings (user_id, material_types, complexity_levels, welcome_dismissed, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    material_types = excluded.material_types,
                    complexity_levels = excluded.complexity_levels,
                    welcome_dismissed = excluded.welcome_dismissed,
                    updated_at = excluded.updated_at
            """, (
                user["id"],
                json.dumps(valid_types, ensure_ascii=False),
                json.dumps(clean_levels, ensure_ascii=False),
                curr_wel,
                now_iso
            ))

        # Optional batch update for subscriptions
        if "subscriptions" in settings_obj:
            batch_subs = settings_obj["subscriptions"]
            now_iso_sub = datetime.datetime.now(datetime.timezone.utc).isoformat()
            items_to_add = []
            if isinstance(batch_subs, dict):
                for stype in ("author", "topic", "tag"):
                    sub_list = batch_subs.get(f"{stype}s") or batch_subs.get(stype) or []
                    if isinstance(sub_list, list):
                        for s in sub_list:
                            sid = s.get("id") if isinstance(s, dict) else str(s)
                            stitle = (s.get("title") or sid) if isinstance(s, dict) else sid
                            if stype == "tag":
                                sid = normalize_keyword(sid).lstrip('#').strip().lower()
                                stitle = normalize_keyword(stitle).lstrip('#').strip()
                            if sid:
                                items_to_add.append((user["id"], stype, sid, stitle, now_iso_sub))
            elif isinstance(batch_subs, list):
                for s in batch_subs:
                    if isinstance(s, dict):
                        stype = (s.get("targetType") or s.get("type") or "").strip().lower()
                        sid = (s.get("targetId") or s.get("id") or "").strip()
                        stitle = (s.get("targetTitle") or s.get("title") or sid).strip()
                        if stype in ("author", "topic", "tag") and sid:
                            if stype == "tag":
                                sid = normalize_keyword(sid).lstrip('#').strip().lower()
                                stitle = normalize_keyword(stitle).lstrip('#').strip()
                            items_to_add.append((user["id"], stype, sid, stitle, now_iso_sub))

            with conn:
                conn.execute("DELETE FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                if items_to_add:
                    conn.executemany("""
                        INSERT OR REPLACE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, items_to_add)
                    for item in items_to_add:
                        conn.execute("DELETE FROM user_feed_exceptions WHERE user_id = ? AND target_type = ? AND target_id = ?",
                                     (item[0], item[1], item[2]))

        # Optional batch update for exceptions
        if "exceptions" in settings_obj:
            batch_exc = settings_obj["exceptions"]
            now_iso_exc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            exc_to_add = []
            if isinstance(batch_exc, dict):
                for etype in ("author", "topic", "tag"):
                    exc_list = batch_exc.get(f"{etype}s") or batch_exc.get(etype) or []
                    if isinstance(exc_list, list):
                        for e in exc_list:
                            eid = e.get("id") if isinstance(e, dict) else str(e)
                            etitle = (e.get("title") or eid) if isinstance(e, dict) else eid
                            if etype == "tag":
                                eid = normalize_keyword(eid).lstrip('#').strip().lower()
                                etitle = normalize_keyword(etitle).lstrip('#').strip()
                            if eid:
                                exc_to_add.append((user["id"], etype, eid, etitle, now_iso_exc))
            elif isinstance(batch_exc, list):
                for e in batch_exc:
                    if isinstance(e, dict):
                        etype = (e.get("targetType") or e.get("type") or "").strip().lower()
                        eid = (e.get("targetId") or e.get("id") or "").strip()
                        etitle = (e.get("targetTitle") or e.get("title") or eid).strip()
                        if etype in ("author", "topic", "tag") and eid:
                            if etype == "tag":
                                eid = normalize_keyword(eid).lstrip('#').strip().lower()
                                etitle = normalize_keyword(etitle).lstrip('#').strip()
                            exc_to_add.append((user["id"], etype, eid, etitle, now_iso_exc))

            with conn:
                conn.execute("DELETE FROM user_feed_exceptions WHERE user_id = ?", (user["id"],))
                if exc_to_add:
                    conn.executemany("""
                        INSERT OR REPLACE INTO user_feed_exceptions (user_id, target_type, target_id, target_title, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, exc_to_add)
                    for item in exc_to_add:
                        conn.execute("DELETE FROM user_subscriptions WHERE user_id = ? AND target_type = ? AND target_id = ?",
                                     (item[0], item[1], item[2]))
                    clear_author_notifications(conn, user["id"], [item[2] for item in exc_to_add if item[1] == "author"])

        self.send_json_response(200, {
            "success": True,
            "settings": {
                "materialTypes": valid_types,
                "complexityLevels": clean_levels
            },
            "materialTypes": valid_types,
            "complexityLevels": clean_levels
        })
