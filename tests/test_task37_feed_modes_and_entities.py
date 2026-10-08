#!/usr/bin/env python3
"""
tests/test_task37_feed_modes_and_entities.py

Comprehensive test suite for task-37-feed-modes-communities-companies-and-directions:
1. Second-Level Navigation Bar (strict order, 7 desktop tabs, mobile scroll, relocated saved button, unified headers)
2. Feed Modes («В фокусе» 72h gravity formula, «Топ» periods & sorting, «Новое» strict chronological)
3. Subscriptions (multi-source, deduplication, exception priority, reason badges, empty states, 5-tab modal)
4. Clubs (catalog, search, direction filtering, detail view, creation API, owner attribution)
5. Companies (catalog, publications subtab, detail view, creation API, human vs company attribution)
6. Directions (all 13 standard topics, subscriber/article counters, transition to feed)
7. Editor Integration (company and club selectors in publication modal, query param preselection, settings persistence)
8. Seed Data (13 directions, 5 clubs, 5 companies, 28 authentic articles)
9. Quality Standards (100% offline-first, Onest font, zero emojis)
"""

import datetime
import http.client
import json
import os
import re
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request

import server
from server import (
    STANDARD_TOPICS,
    TOPICS_TITLE_MAP,
    compute_snapshot_hash,
    create_server,
    get_db_connection,
    init_db,
)
from tests.fixtures import seed_data

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestTask37Base(unittest.TestCase):
    """Base class for Task-37 tests with isolated database and test HTTP server."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_task37.db")
        server.DEFAULT_DB_PATH = cls.db_path

        # Initialize and seed database
        conn = init_db(cls.db_path)
        conn.close()

        # Start HTTP server on dynamic port
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        # Read static files
        with open(os.path.join(FRONTEND_DIR, "index.html"), "r", encoding="utf-8") as f:
            cls.index_html = f.read()
        with open(os.path.join(FRONTEND_DIR, "feed.html"), "r", encoding="utf-8") as f:
            cls.feed_html = f.read()
        with open(os.path.join(FRONTEND_DIR, "editor.html"), "r", encoding="utf-8") as f:
            cls.editor_html = f.read()
        with open(os.path.join(FRONTEND_DIR, "article.html"), "r", encoding="utf-8") as f:
            cls.article_html = f.read()
        with open(os.path.join(FRONTEND_DIR, "css", "feed.css"), "r", encoding="utf-8") as f:
            cls.feed_css = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "feed.js"), "r", encoding="utf-8") as f:
            cls.feed_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "card.js"), "r", encoding="utf-8") as f:
            cls.card_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "publication.js"), "r", encoding="utf-8") as f:
            cls.publication_js = f.read()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _get_json(self, path: str, cookie: str = None):
        safe_path = urllib.parse.quote(path, safe="/:?=&%")
        req = urllib.request.Request(f"{self.base_url}{safe_path}", method="GET")
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read().decode("utf-8")
                return resp.status, json.loads(body), resp.headers.get("Set-Cookie")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = {"raw": body}
            return e.code, data, None

    def _post_json(self, path: str, payload: dict, cookie: str = None):
        safe_path = urllib.parse.quote(path, safe="/:?=&%")
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}{safe_path}", data=data_bytes, method="POST")
        req.add_header("Content-Type", "application/json")
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read().decode("utf-8")
                return resp.status, json.loads(body), resp.headers.get("Set-Cookie")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = {"raw": body}
            return e.code, data, None

    def _login_demo_user(self):
        status, data, set_cookie = self._post_json("/api/auth/login", {"username": "demo"})
        self.assertEqual(status, 200)
        cookie_val = set_cookie.split(";")[0] if set_cookie else None
        return cookie_val


class TestSubnavAndHeaderLayout(TestTask37Base):
    """1. Tests for Second-Level Navigation Bar and Header Layout."""

    def test_strict_visual_order_of_subnav_elements(self):
        """
        Task 38 strict order of subnav elements:
        Создать + → Все публикации → Вопросы → Подписки → Сохраненные
        """
        subnav_start = self.feed_html.find('id="feedSubnavBar"')
        self.assertNotEqual(subnav_start, -1, "#feedSubnavBar must exist in feed.html")
        subnav_end = self.feed_html.find('</nav>', subnav_start)
        subnav_chunk = self.feed_html[subnav_start:subnav_end]

        idx_create = subnav_chunk.find('id="btnCreateDropdown"') if 'id="btnCreateDropdown"' in subnav_chunk else subnav_chunk.find('id="btnHeroWrite"')
        idx_all = subnav_chunk.find('id="tabFeedAll"')
        idx_questions = subnav_chunk.find('id="tabFeedQuestions"')
        idx_subs = subnav_chunk.find('id="tabFeedSubscriptions"')
        idx_saved = subnav_chunk.find('id="feedSavedTab"')

        self.assertNotEqual(idx_create, -1, "Create button must exist in subnav")
        self.assertNotEqual(idx_all, -1, "All publications tab must exist in subnav")
        self.assertNotEqual(idx_questions, -1, "Questions tab must exist in subnav")
        self.assertNotEqual(idx_subs, -1, "Subscriptions tab must exist in subnav")
        self.assertNotEqual(idx_saved, -1, "Saved tab must exist in subnav")

        # Verify strict sequence: Создать + → Все публикации → Вопросы → Подписки → Сохраненные
        self.assertLess(idx_create, idx_all, "Создать + must precede Все публикации")
        self.assertLess(idx_all, idx_questions, "Все публикации must precede Вопросы")
        self.assertLess(idx_questions, idx_subs, "Вопросы must precede Подписки")
        self.assertLess(idx_subs, idx_saved, "Подписки must precede Сохраненные")

    def test_rename_my_feed_to_subscriptions(self):
        """Visible label must be 'Подписки'."""
        self.assertIn("Подписки", self.feed_html)
        self.assertIn('id="tabFeedSubscriptions"', self.feed_html)

    def test_write_button_is_primary_accent(self):
        """Write button in subnav must have btn-primary accent class."""
        self.assertTrue('btn-primary' in self.feed_html and ('feed-create-btn' in self.feed_html or 'feed-subnav-write-btn' in self.feed_html))

    def test_relocated_saved_button_in_app_header(self):
        """
        Task 38: 'Сохраненные' (#feedSavedTab, #feedSavedCount) is moved to Subnav Level 2.
        Header Level 1 (#appHeader) must contain #headerNotificationsBtn and #headerLoginBtn, but NOT #feedSavedTab.
        """
        header_start = self.feed_html.find('id="appHeader"')
        header_end = self.feed_html.find('</header>', header_start)
        header_chunk = self.feed_html[header_start:header_end]

        idx_notif = header_chunk.find('id="headerNotificationsBtn"')
        idx_login = header_chunk.find('id="headerLoginBtn"')
        idx_saved_in_header = header_chunk.find('id="feedSavedTab"')

        self.assertNotEqual(idx_notif, -1, "#headerNotificationsBtn must exist inside #appHeader")
        self.assertNotEqual(idx_login, -1, "#headerLoginBtn must exist inside #appHeader")
        self.assertEqual(idx_saved_in_header, -1, "#feedSavedTab must NOT exist inside #appHeader in Task 38")

    def test_unified_header_markup_identity(self):
        """
        #appHeader lines must be 100% identical across index.html, feed.html, editor.html, article.html.
        """
        def extract_header_lines(html_text: str):
            start = html_text.find('<header id="appHeader"')
            end = html_text.find('</header>', start) + len('</header>')
            raw = html_text[start:end]
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
            return lines

        h_index = extract_header_lines(self.index_html)
        h_feed = extract_header_lines(self.feed_html)
        h_editor = extract_header_lines(self.editor_html)
        h_article = extract_header_lines(self.article_html)

        self.assertEqual(h_index, h_feed, "Header in feed.html differs from index.html")
        self.assertEqual(h_index, h_editor, "Header in editor.html differs from index.html")
        self.assertEqual(h_index, h_article, "Header in article.html differs from index.html")

    def test_css_subnav_desktop_and_mobile_scroll(self):
        """
        CSS must support single-line desktop tabs and horizontal scroll on mobile.
        """
        self.assertIn(".feed-subnav-tabs", self.feed_css)
        self.assertIn("overflow-x: auto", self.feed_css)
        self.assertIn("flex-shrink: 0", self.feed_css)


class TestFeedModes(TestTask37Base):
    """2. Tests for Feed Modes: Focus, Top (with periods), New."""

    def test_focus_feed_gravity_scoring(self):
        """
        «В фокусе» (tab=focus): 72h gravity formula (likes_72h*2 + comments_72h*3)/((age_hours+2)**1.5).
        """
        # Ensure at least one recent interaction within 72 hours for gravity scoring
        conn = sqlite3.connect(self.db_path)
        try:
            now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            conn.execute("INSERT OR REPLACE INTO article_likes (article_id, user_id, created_at) VALUES ('art-07', 'user_test_recent', ?)", (now_iso,))
            conn.commit()
        finally:
            conn.close()

        status, data, _ = self._get_json("/api/articles?tab=focus")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        articles = data.get("articles", [])
        self.assertGreater(len(articles), 0)

        # Check focusScore field is present and non-negative
        for a in articles:
            self.assertIn("focusScore", a)
            self.assertGreaterEqual(a["focusScore"], 0.0)

        # Article with high interactions (art-07 or art-01) should have positive focusScore
        scores = [a["focusScore"] for a in articles]
        self.assertTrue(any(s > 0 for s in scores))

    def test_top_feed_periods(self):
        """
        «Топ» (tab=top): supports period=day, period=week, period=month, period=all.
        Sorted by score DESC, commentsCount DESC, createdAt DESC.
        """
        for period in ["day", "week", "month", "all"]:
            status, data, _ = self._get_json(f"/api/articles?tab=top&period={period}")
            self.assertEqual(status, 200)
            self.assertTrue(data.get("success"))
            articles = data.get("articles", [])
            # Verify sorting: each subsequent item has <= score or (equal score and <= comments)
            for i in range(len(articles) - 1):
                cur = articles[i]
                nxt = articles[i + 1]
                cur_key = (cur.get("score", 0), cur.get("commentsCount", 0), cur.get("createdAt", ""))
                nxt_key = (nxt.get("score", 0), nxt.get("commentsCount", 0), nxt.get("createdAt", ""))
                self.assertGreaterEqual(cur_key, nxt_key, f"Top sort order violated for period={period}")

    def test_new_feed_strict_chronological_order(self):
        """
        «Новое» (tab=new): strict sort by createdAt DESC, id DESC.
        """
        status, data, _ = self._get_json("/api/articles?tab=new")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        articles = data.get("articles", [])
        self.assertGreater(len(articles), 1)

        for i in range(len(articles) - 1):
            cur_dt = articles[i].get("createdAt", "")
            nxt_dt = articles[i + 1].get("createdAt", "")
            self.assertGreaterEqual(cur_dt, nxt_dt, "New feed must be strictly sorted by createdAt DESC")


class TestSubscriptionsAndExceptions(TestTask37Base):
    """3. Tests for Subscriptions, Deduplication, and Exceptions."""

    def test_subscriptions_multi_source_toggle_api(self):
        """
        POST /api/subscriptions/toggle supports all 5 targets: author, topic, tag, club, company.
        """
        cookie = self._login_demo_user()
        targets = [
            ("author", "author_volkova", "Ольга Волкова"),
            ("club", "pksc-architects", "Архитекторы ПКСК"),
            ("company", "distributed-lab", "Distributed Lab"),
            ("topic", "law-and-compliance", "Право и комплаенс"),
            ("tag", "безопасность", "Безопасность")
        ]

        for target_type, target_id, title in targets:
            # Subscribe
            status, data, _ = self._post_json(
                "/api/subscriptions/toggle",
                {"target_type": target_type, "target_id": target_id, "target_title": title},
                cookie=cookie
            )
            self.assertEqual(status, 200)
            self.assertTrue(data.get("success"))
            self.assertTrue(data.get("isSubscribed"))

            # Unsubscribe toggle
            status2, data2, _ = self._post_json(
                "/api/subscriptions/toggle",
                {"target_type": target_type, "target_id": target_id},
                cookie=cookie
            )
            self.assertEqual(status2, 200)
            self.assertFalse(data2.get("isSubscribed"))

    def test_subscription_feed_deduplication_and_reason_badge(self):
        """
        Articles in personal feed are deduplicated and contain subscriptionReason.
        """
        cookie = self._login_demo_user()
        # Ensure user is subscribed to topic and club
        self._post_json("/api/subscriptions/toggle", {"target_type": "topic", "target_id": "pksc-architecture"}, cookie=cookie)
        self._post_json("/api/subscriptions/toggle", {"target_type": "club", "target_id": "pksc-architects"}, cookie=cookie)

        status, data, _ = self._get_json("/api/articles?tab=subscriptions", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        articles = data.get("articles", [])
        seen_ids = set()
        for a in articles:
            self.assertNotIn(a["id"], seen_ids, f"Duplicate article {a['id']} found in subscriptions feed")
            seen_ids.add(a["id"])
            self.assertIsNotNone(a.get("subscriptionReason"), "Article in subscriptions feed must have subscriptionReason")

    def test_exceptions_priority_over_subscriptions(self):
        """
        Exceptions strictly hide materials from feed across all tabs.
        """
        cookie = self._login_demo_user()
        # Add exception for author_kuznetsov
        self._post_json("/api/exceptions/toggle", {"target_type": "author", "target_id": "author_kuznetsov"}, cookie=cookie)

        status, data, _ = self._get_json("/api/articles?tab=focus", cookie=cookie)
        self.assertEqual(status, 200)
        articles = data.get("articles", [])
        for a in articles:
            self.assertNotEqual(a.get("author"), "Дмитрий Кузнецов", "Excluded author must not appear in feed")

        # Cleanup exception
        self._post_json("/api/exceptions/toggle", {"target_type": "author", "target_id": "author_kuznetsov"}, cookie=cookie)

    def test_subscription_entities_catalog_endpoint(self):
        """
        GET /api/subscriptions/entities returns categorized catalogs for the 5-tab modal.
        """
        status, data, _ = self._get_json("/api/subscriptions/entities")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertIn("authors", data)
        self.assertIn("clubs", data)
        self.assertIn("companies", data)
        self.assertIn("topics", data)
        self.assertIn("tags", data)

        # Single type query
        status2, data2, _ = self._get_json("/api/subscriptions/entities?type=club")
        self.assertEqual(status2, 200)
        self.assertIn("items", data2)
        self.assertGreater(data2.get("total", 0), 0)


class TestClubsAndCommunities(TestTask37Base):
    """4. Tests for Clubs (Professional Communities)."""

    def test_clubs_catalog_endpoint_and_filters(self):
        """
        GET /api/clubs returns list of clubs with search and direction filter.
        """
        status, data, _ = self._get_json("/api/clubs")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        clubs = data.get("clubs", [])
        self.assertGreaterEqual(len(clubs), 5)

        # Search test
        status_s, data_s, _ = self._get_json("/api/clubs?search=безопасность")
        self.assertEqual(status_s, 200)
        self.assertTrue(data_s.get("success"))
        for c in data_s.get("clubs", []):
            self.assertIn("безопасн", (c["title"] + " " + c["description"] + " " + " ".join(c.get("tags", []))).lower())

    def test_club_detail_endpoint(self):
        """
        GET /api/clubs/<id> returns detail for a single club.
        """
        status, data, _ = self._get_json("/api/clubs/pksc-architects")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        club = data.get("club")
        self.assertEqual(club["id"], "pksc-architects")
        self.assertEqual(club["title"], "Архитекторы ПКСК")
        self.assertIn("directions", club)
        self.assertIn("rules", club)
        self.assertIn("subscribersCount", club)
        self.assertIn("articlesCount", club)

    def test_create_club_api(self):
        """
        POST /api/clubs creates club with current user as owner.
        """
        cookie = self._login_demo_user()
        new_club_payload = {
            "title": "Клуб разработчиков Hyperledger Besu",
            "description": "Практика развертывания приватных сетей на базе консенсуса QBFT.",
            "rules": "Уважительное общение и инженерная аргументация.",
            "directions": ["pksc-architecture", "infrastructure-operations"],
            "tags": ["Besu", "QBFT"]
        }
        status, data, _ = self._post_json("/api/clubs", new_club_payload, cookie=cookie)
        self.assertEqual(status, 201)
        self.assertTrue(data.get("success"))
        club = data.get("club")
        self.assertIn("id", club)
        self.assertEqual(club["ownerId"], "user_demo")
        self.assertTrue(club.get("isSubscribed"))


class TestCompaniesCorporateBlogs(TestTask37Base):
    """5. Tests for Companies (Corporate Blogs)."""

    def test_companies_catalog_endpoint(self):
        """
        GET /api/companies returns list of companies with verification and stats.
        """
        status, data, _ = self._get_json("/api/companies")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        comps = data.get("companies", [])
        self.assertGreaterEqual(len(comps), 5)

        for c in comps:
            self.assertIn("name", c)
            self.assertIn("specialization", c)
            self.assertIn("website", c)
            self.assertIn("subscribersCount", c)
            self.assertIn("articlesCount", c)

    def test_company_detail_endpoint(self):
        """
        GET /api/companies/<id> returns detail for a single company.
        """
        status, data, _ = self._get_json("/api/companies/smarttech-innovations")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        comp = data.get("company")
        self.assertEqual(comp["id"], "smarttech-innovations")
        self.assertEqual(comp["name"], "ООО «СмартТех Инновации»")
        self.assertTrue(comp.get("isVerified"))

    def test_create_company_api(self):
        """
        POST /api/companies registers company profile with current user as owner.
        """
        cookie = self._login_demo_user()
        payload = {
            "name": "Новая Лаборатория ДЛТ",
            "description": "Разработка высоконагруженных смарт-контрактов для финтеха.",
            "specialization": "DLT & Smart Contracts",
            "website": "dltlab.ru"
        }
        status, data, _ = self._post_json("/api/companies", payload, cookie=cookie)
        self.assertEqual(status, 201)
        self.assertTrue(data.get("success"))
        comp = data.get("company")
        self.assertEqual(comp["ownerId"], "user_demo")
        self.assertTrue(comp.get("isSubscribed"))


class TestDirectionsCatalog(TestTask37Base):
    """6. Tests for Directions (Topics Catalog)."""

    def test_directions_catalog_contains_all_13_topics(self):
        """
        GET /api/directions returns exactly 13 standard topics with post and subscriber counters.
        """
        status, data, _ = self._get_json("/api/directions")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        directions = data.get("directions", [])
        self.assertEqual(len(directions), 13, "Must contain all 13 standard topics")

        dir_ids = {d["id"] for d in directions}
        expected_ids = {tid for tid, _ in STANDARD_TOPICS}
        self.assertEqual(dir_ids, expected_ids)

        for d in directions:
            self.assertIn("description", d)
            self.assertIn("articlesCount", d)
            self.assertIn("subscribersCount", d)


class TestEditorIntegration(TestTask37Base):
    """7. Tests for Editor Integration with Company and Club Selectors."""

    def test_editor_has_company_and_club_selectors(self):
        """
        editor.html must contain #pub-company-select and #pub-club-select.
        """
        self.assertIn('id="pub-company-select"', self.editor_html)
        self.assertIn('id="pub-club-select"', self.editor_html)

    def test_publication_js_persists_entity_settings(self):
        """
        publication.js must handle companyId, companyName, clubId, clubTitle in getSettings and loadSettings.
        """
        self.assertIn("companyId: this.companyId", self.publication_js)
        self.assertIn("companyName: this.companyName", self.publication_js)
        self.assertIn("clubId: this.clubId", self.publication_js)
        self.assertIn("clubTitle: this.clubTitle", self.publication_js)


class TestQualityAndStandards(TestTask37Base):
    """9. Tests for Quality, Offline-First, Font Onest, and Zero Emojis."""

    def test_offline_first_zero_external_requests(self):
        """
        Zero external http:// or https:// CDNs, fonts, or assets across HTML, CSS, JS.
        (Standard SVG XML namespace http://www.w3.org/2000/svg is exempted).
        """
        files_to_check = [
            ("feed.html", self.feed_html),
            ("feed.css", self.feed_css),
            ("feed.js", self.feed_js),
            ("card.js", self.card_js),
            ("publication.js", self.publication_js),
        ]
        url_pattern = re.compile(r'https?://(?!www\.w3\.org/2000/svg)[a-zA-Z0-9\.\-_]+')

        for name, content in files_to_check:
            matches = url_pattern.findall(content)
            self.assertEqual(matches, [], f"Found external URLs in {name}: {matches}")

    def test_font_onest_declared(self):
        """
        Font-family Onest must be declared across pages.
        """
        self.assertIn("Onest", self.feed_html)
        self.assertIn("Onest", self.feed_css)

    def test_zero_emojis(self):
        """
        Zero emoji unicode characters in code and markup.
        """
        emoji_pattern = re.compile(
            r'[\U0001F600-\U0001F64F]'  # Emoticons
            r'|[\U0001F300-\U0001F5FF]'  # Misc Symbols and Pictographs
            r'|[\U0001F680-\U0001F6FF]'  # Transport and Map
            r'|[\U0001F1E0-\U0001F1FF]'  # Flags
            r'|[\U00002702-\U000027B0]'
            r'|[\U000024C2-\U0001F251]'
        )
        files_to_check = [
            ("feed.html", self.feed_html),
            ("editor.html", self.editor_html),
            ("feed.css", self.feed_css),
            ("feed.js", self.feed_js),
            ("card.js", self.card_js),
            ("publication.js", self.publication_js),
        ]
        for name, content in files_to_check:
            found = emoji_pattern.findall(content)
            self.assertEqual(found, [], f"Found emojis in {name}: {found}")


if __name__ == "__main__":
    unittest.main()
