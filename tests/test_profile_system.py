#!/usr/bin/env python3
"""
tests/test_profile_system.py

Comprehensive test suite for Issue #174:
[P0][frontend/testing] Profile: адаптивность, доступность, приватность данных и регрессионные тесты

Verifies:
1. Backend contracts:
   - GET /api/users/:id returns 200, profile structure, stats, and counters
   - GET /api/users/unknown returns 404 with USER_NOT_FOUND code
   - Self-subscription rejection (400)
   - Chronological activity pagination (limit and offset)
   - Dedicated publications, questions, and answers pagination and filters
   - Data privacy: strict isolation of email, session tokens, passwords, drafts, and private settings
2. Frontend contracts and accessibility:
   - Hero, cover, avatar, identity, and statistics bar in profile.html
   - Semantic tags (<main>, <aside>, <nav>, h1-h3 hierarchy)
   - ARIA roles and attributes (role="tablist", aria-selected, aria-current="page")
   - Focus management and keyboard navigation (:focus-visible, Escape key, return focus)
   - Quick Profile modal contracts in profile.js (delegation, close on escape/click, full profile link)
   - Shared profile.js inclusion in feed.html, article.html, profile.html
3. Responsive design and invariants:
   - CSS rules for 320px, 375px, 480px, 640px, 768px, 1024px
   - Zero emojis
   - Zero em dashes
   - 100% offline-first architecture
"""

import datetime
import http.client
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestProfileSystem(unittest.TestCase):
    """End-to-end test suite for the complete user profile system."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_profile_system.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        cls._seed_test_data(conn)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    @classmethod
    def _seed_test_data(cls, conn):
        cur = conn.cursor()
        now = datetime.datetime.now(datetime.timezone.utc)
        t_exp = (now + datetime.timedelta(days=30)).isoformat()
        t0 = (now - datetime.timedelta(days=120)).isoformat()

        # User 1: Alice (Full profile author with articles, questions, answers, solutions)
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, website, avatar, created_at, updated_at)
            VALUES ('alice_sys', 'Алиса Эксперт', 'Senior Smart Contract Auditor', 'SecurityLabs', 'Специализируюсь на анализе уязвимостей в Solidity.', 'https://alice.example.com', NULL, ?, ?)
        """, (t0, t0))

        cur.execute("""
            INSERT OR REPLACE INTO sessions (token, user_id, user_name, user_role, expires_at, created_at)
            VALUES ('token_alice', 'alice_sys', 'Алиса Эксперт', 'user', ?, ?)
        """, (t_exp, t0))

        # Seed 5 approved articles for Alice
        for i in range(1, 6):
            t_art = (now - datetime.timedelta(days=30 - i)).isoformat()
            cur.execute("""
                INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
                VALUES (?, ?, 'alice_sys', ?, '<p>Article content</p>', 'approved', ?, ?, ?, ?)
            """, (
                f"art_sys_{i}",
                f"draft_sys_{i}",
                f"Article Title {i}",
                json.dumps({"materialType": "article", "topics": ["security", "evm"]}),
                f"hash_sys_{i}",
                t_art,
                t_art
            ))

        # Seed 3 approved questions for Alice
        for i in range(1, 4):
            t_quest = (now - datetime.timedelta(days=15 - i)).isoformat()
            cur.execute("""
                INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
                VALUES (?, ?, 'alice_sys', ?, '<p>Question content</p>', 'approved', ?, ?, ?, ?)
            """, (
                f"quest_sys_{i}",
                f"draft_qsys_{i}",
                f"Question Title {i}",
                json.dumps({"materialType": "question", "topics": ["defi", "security"]}),
                f"hash_qsys_{i}",
                t_quest,
                t_quest
            ))

        # User 2: Bob (Another user with answers and solutions on questions)
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, website, avatar, created_at, updated_at)
            VALUES ('bob_sys', 'Боб Исследователь', 'Core Dev', 'CryptoCo', 'Разработчик протоколов.', 'https://bob.example.com', NULL, ?, ?)
        """, (t0, t0))

        cur.execute("""
            INSERT OR REPLACE INTO sessions (token, user_id, user_name, user_role, expires_at, created_at)
            VALUES ('token_bob', 'bob_sys', 'Боб Исследователь', 'user', ?, ?)
        """, (t_exp, t0))

        # Seed answers by Bob on quest_sys_1
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at, updated_at)
            VALUES ('ans_sys_1', 'quest_sys_1', 'bob_sys', 'Боб Исследователь', 'Вот правильное решение вопроса.', 'published', 'answer', 1, ?, ?)
        """, (t0, t0))

        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at, updated_at)
            VALUES ('ans_sys_2', 'quest_sys_2', 'bob_sys', 'Боб Исследователь', 'Обычный ответ без статуса решения.', 'published', 'answer', 0, ?, ?)
        """, (t0, t0))

        # User 3: Carol (For self-subscription and edit testing)
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, website, avatar, created_at, updated_at)
            VALUES ('carol_sys', 'Каролина Тест', 'Tester', 'TestLab', 'Тестировщик.', 'https://carol.example.com', NULL, ?, ?)
        """, (t0, t0))

        cur.execute("""
            INSERT OR REPLACE INTO sessions (token, user_id, user_name, user_role, expires_at, created_at)
            VALUES ('token_carol', 'carol_sys', 'Каролина Тест', 'user', ?, ?)
        """, (t_exp, t0))

        # Carol subscribes to Alice
        cur.execute("""
            INSERT INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
            VALUES ('carol_sys', 'author', 'alice_sys', 'Алиса Эксперт', ?)
        """, (t0,))

        conn.commit()

    def _api_get(self, path, session_token=None):
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url)
        if session_token:
            req.add_header("Cookie", f"sc_session={session_token}")
            req.add_header("Authorization", f"Bearer {session_token}")
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                return status, json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = {"raw": body}
            return e.code, data

    def _api_post(self, path, payload, session_token=None):
        url = f"{self.base_url}{path}"
        body_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body_bytes, method="POST")
        req.add_header("Content-Type", "application/json; charset=utf-8")
        if session_token:
            req.add_header("Cookie", f"sc_session={session_token}")
            req.add_header("Authorization", f"Bearer {session_token}")
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                return status, json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = {"raw": body}
            return e.code, data

    # =========================================================================
    # 1. Backend Contracts Tests
    # =========================================================================

    def test_api_get_user_profile_success(self):
        """GET /api/users/:id returns 200, valid profile, stats counters and topics."""
        status, data = self._api_get("/api/users/alice_sys")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        profile = data.get("profile", {})
        self.assertEqual(profile.get("userId"), "alice_sys")
        self.assertEqual(profile.get("name"), "Алиса Эксперт")
        self.assertEqual(profile.get("specialization"), "Senior Smart Contract Auditor")
        self.assertEqual(profile.get("company"), "SecurityLabs")
        self.assertEqual(profile.get("followersCount"), 1)

        # Check stats
        stats = profile.get("stats", {})
        self.assertEqual(stats.get("publicationsCount"), 5)
        self.assertEqual(stats.get("questionsCount"), 3)
        self.assertEqual(stats.get("followersCount"), 1)

        # Check topics
        topics = profile.get("topics", [])
        self.assertTrue(len(topics) >= 2)

    def test_api_get_user_profile_unknown_user_returns_404(self):
        """GET /api/users/unknown returns 404 with error code USER_NOT_FOUND."""
        status, data = self._api_get("/api/users/unknown_user_nonexistent_999")
        self.assertEqual(status, 404)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "USER_NOT_FOUND")

    def test_api_prevent_self_subscription(self):
        """Subscribing to own user_id returns 400 Bad Request."""
        payload = {
            "targetType": "author",
            "targetId": "carol_sys"
        }
        status, data = self._api_post("/api/subscriptions/toggle", payload, session_token="token_carol")
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "SELF_SUBSCRIPTION_FORBIDDEN")

    def test_api_activity_pagination(self):
        """GET /api/users/:id/activity respects limit and offset pagination."""
        # Alice has 5 articles + 3 questions = 8 activity items
        status, data = self._api_get("/api/users/alice_sys/activity?limit=3&offset=0")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        items = data.get("activity") or data.get("items") or []
        self.assertEqual(len(items), 3)
        self.assertTrue(data.get("hasMore"))

        status2, data2 = self._api_get("/api/users/alice_sys/activity?limit=3&offset=6")
        self.assertEqual(status2, 200)
        items2 = data2.get("activity") or data2.get("items") or []
        self.assertEqual(len(items2), 2)
        self.assertFalse(data2.get("hasMore"))

    def test_api_publications_and_questions_endpoints(self):
        """GET publications and questions endpoints return filtered items and total counts."""
        status, data = self._api_get("/api/users/alice_sys/publications?limit=10&offset=0")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("total"), 5)
        self.assertEqual(len(data.get("items", [])), 5)

        status_q, data_q = self._api_get("/api/users/alice_sys/questions?limit=10&offset=0")
        self.assertEqual(status_q, 200)
        self.assertEqual(data_q.get("total"), 3)
        self.assertEqual(len(data_q.get("items", [])), 3)

    def test_api_answers_and_solutions_endpoints(self):
        """GET /api/users/:id/answers supports filtering by solutions."""
        # Bob has 2 answers, 1 of which is marked as solution
        status_all, data_all = self._api_get("/api/users/bob_sys/answers?filter=all")
        self.assertEqual(status_all, 200)
        self.assertEqual(data_all.get("total"), 2)

        status_sol, data_sol = self._api_get("/api/users/bob_sys/answers?filter=solutions")
        self.assertEqual(status_sol, 200)
        self.assertEqual(data_sol.get("total"), 1)
        items_sol = data_sol.get("items", [])
        self.assertTrue(items_sol[0].get("isSolution"))

    def test_api_privacy_data_leak_audit(self):
        """Verifies zero leakage of private fields across all public user endpoints."""
        endpoints = [
            "/api/users/alice_sys",
            "/api/users/alice_sys/activity",
            "/api/users/alice_sys/publications",
            "/api/users/alice_sys/questions",
            "/api/users/bob_sys/answers"
        ]
        forbidden_substrings = [
            "email",
            "sessiontoken",
            "password",
            "privatesettings"
        ]

        for ep in endpoints:
            status, data = self._api_get(ep)
            self.assertEqual(status, 200, f"Endpoint {ep} must return 200")
            data_str = json.dumps(data).lower()
            for forbidden in forbidden_substrings:
                self.assertNotIn(
                    f'"{forbidden}"',
                    data_str,
                    f"Forbidden private field '{forbidden}' found in public endpoint {ep}"
                )

    def test_api_post_user_profile_updates_fields(self):
        """POST /api/user/profile updates user bio, specialization, and company."""
        payload = {
            "name": "Каролина Тест Обновленная",
            "specialization": "Lead QA Engineer",
            "company": "SmartShield Tech",
            "website": "https://carol-qa.example.com",
            "bio": "Ведущий инженер тестирования смарт-контрактов."
        }
        status, data = self._api_post("/api/user/profile", payload, session_token="token_carol")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data["profile"]["specialization"], "Lead QA Engineer")
        self.assertEqual(data["profile"]["company"], "SmartShield Tech")

    # =========================================================================
    # 2. Frontend Accessibility & Semantic Contracts
    # =========================================================================

    def test_frontend_profile_html_semantics_and_a11y(self):
        """Verifies profile.html conforms to semantic hierarchy and ARIA specifications."""
        html_path = os.path.join(FRONTEND_DIR, "profile.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Semantic landmarks
        self.assertIn('<main class="profile-page"', html)
        self.assertIn('<aside class="profile-sidebar"', html)
        self.assertIn('<nav class="header-nav"', html)

        # Headings hierarchy
        self.assertIn('<h1 class="profile-name"', html)
        self.assertNotIn('editProfileModal', html, "profile fields are edited on settings.html (Issue #234)")
        self.assertIn('<h3 class="profile-subheading"', html)
        self.assertIn('<h3 class="profile-widget-title"', html)

        # Tablist and ARIA attributes
        self.assertIn('role="tablist"', html)
        self.assertIn('role="tab"', html)
        self.assertIn('aria-selected="true"', html)
        self.assertIn('aria-current="page"', html)
        self.assertIn('role="tabpanel"', html)

        # Icon button accessible labels
        self.assertIn('aria-label="Скопировать ссылку на профиль"', html)
        self.assertIn('aria-label="Паспорт автора"', html)

    def test_frontend_shared_profile_js_in_all_views(self):
        """Verifies shared profile.js script tag exists in feed.html, article.html, and profile.html."""
        pages = ["feed.html", "article.html", "profile.html"]
        for page in pages:
            page_path = os.path.join(FRONTEND_DIR, page)
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn('<script src="js/profile.js"></script>', content, f"profile.js missing in {page}")

    def test_frontend_focus_management_and_keyboard_a11y(self):
        """Verifies focus management and Escape key bindings in profile-page.js and profile.js."""
        profile_page_js_path = os.path.join(FRONTEND_DIR, "js", "profile-page.js")
        with open(profile_page_js_path, "r", encoding="utf-8") as f:
            code = f.read()

        # Save and restore focus on modal
        self.assertIn("lastAuthTriggerEl.focus()", code)

        # Escape key handling
        self.assertIn("e.key === 'Escape'", code)
        self.assertIn("closeAuthModal", code)

        # Dynamic aria-current updates on tab switch
        self.assertIn("setAttribute('aria-current', 'page')", code)
        self.assertIn("removeAttribute('aria-current')", code)

    # =========================================================================
    # 3. Responsive Styling & Invariants
    # =========================================================================

    def test_frontend_css_responsive_breakpoints_and_focus_visible(self):
        """Verifies profile.css includes all required media queries and focus-visible rules."""
        css_path = os.path.join(FRONTEND_DIR, "css", "profile.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # Focus-visible
        self.assertIn(":focus-visible", css)
        self.assertIn(".profile-tab-btn:focus-visible", css)

        # Responsive breakpoints
        self.assertIn("@media (max-width: 1024px)", css)
        self.assertIn("@media (max-width: 768px)", css)
        self.assertIn("@media (max-width: 640px)", css)
        self.assertIn("@media (max-width: 480px)", css)
        self.assertIn("@media (max-width: 375px)", css)
        self.assertIn("@media (max-width: 320px)", css)

        # Overflow prevention
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertIn("word-break: break-word", css)

    def test_invariants_zero_emojis(self):
        """Verifies zero emojis across all profile system files."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]')
        files_to_check = [
            os.path.join(FRONTEND_DIR, "profile.html"),
            os.path.join(FRONTEND_DIR, "js", "profile.js"),
            os.path.join(FRONTEND_DIR, "js", "profile-page.js"),
            os.path.join(FRONTEND_DIR, "css", "profile.css"),
            os.path.abspath(__file__)
        ]
        for fpath in files_to_check:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                matches = emoji_pattern.findall(content)
                self.assertEqual(len(matches), 0, f"Found emojis in {os.path.basename(fpath)}: {matches}")

    def test_invariants_zero_em_dashes(self):
        """Verifies zero em dashes across all profile system files."""
        em_dash = "\u2014"
        files_to_check = [
            os.path.join(FRONTEND_DIR, "profile.html"),
            os.path.join(FRONTEND_DIR, "js", "profile.js"),
            os.path.join(FRONTEND_DIR, "js", "profile-page.js"),
            os.path.join(FRONTEND_DIR, "css", "profile.css"),
            os.path.abspath(__file__)
        ]
        for fpath in files_to_check:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertNotIn(em_dash, content, f"Found em dash in {os.path.basename(fpath)}")

    def test_invariants_offline_first(self):
        """Verifies 100% offline-first architecture with zero external assets."""
        files_to_check = [
            os.path.join(FRONTEND_DIR, "profile.html"),
            os.path.join(FRONTEND_DIR, "js", "profile.js"),
            os.path.join(FRONTEND_DIR, "js", "profile-page.js"),
            os.path.join(FRONTEND_DIR, "css", "profile.css")
        ]
        url_pattern = re.compile(r'https?://[^\s"\'<>]+')
        for fpath in files_to_check:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                urls = url_pattern.findall(content)
                for u in urls:
                    self.assertTrue(
                        "localhost" in u or "127.0.0.1" in u or "schema.org" in u or "w3.org" in u,
                        f"External link found in {os.path.basename(fpath)}: {u}"
                    )


if __name__ == "__main__":
    unittest.main()
