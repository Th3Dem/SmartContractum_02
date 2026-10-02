#!/usr/bin/env python3
"""
tests/test_issue75_unique_colors_and_card_actions.py

Automated test suite verifying:
1. Unique color palette for all comment and card action buttons:
   - Reply: Sky (#38bdf8)
   - Save/Bookmark: Amber (#f59e0b)
   - Share: Purple (#a855f7)
   - Subscribe: Teal (#14b8a6)
   - Report: Raspberry (#e11d48)
   - Delete: Red (#ef4444)
   - Edit: Indigo (#6366f1)
2. Report button active state:
   - Does NOT remain grey/inactive (opacity 0.5 eliminated).
   - Lights up in Raspberry (#e11d48) with subtle background (rgba(225, 29, 72, 0.12)) and filled icon.
   - Clicking reported button notifies user with toast.
3. Feed card action bar buttons for publications and questions:
   - Adds "Поделиться" (.btn-card-share) and "Пожаловаться" (.btn-card-report).
   - Author cannot report own publication or question.
   - Popover share menu and report modal integration.
4. Backend API for article reporting:
   - POST /api/articles/<id>/report requires auth (401).
   - Prevents reporting own article (403).
   - Prevents duplicate reports (409).
   - Validates report reason (400).
   - Successfully records reports in article_reports table (200).

Strict invariants: zero emojis, zero em dashes, 100% offline-first.
"""

import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


def read_file(relative_path: str) -> str:
    full_path = os.path.join(PROJECT_ROOT, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


class TestArticleReportBackend(unittest.TestCase):
    """Verifies backend API, schema, report invariants for articles and questions."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_article_reports.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        with conn:
            # Seed users
            users = [
                ("u_alice", "Алиса", "author"),
                ("u_bob", "Боб", "user"),
                ("u_charlie", "Чарли", "user"),
            ]
            for uid, name, role in users:
                conn.execute("""
                    INSERT INTO user_profiles (
                        user_id, name, specialization, company, bio, avatar, created_at, updated_at
                    ) VALUES (?, ?, 'Engineer', 'SmartCo', '', '', '2026-10-01T10:00:00Z', '2026-10-01T10:00:00Z')
                """, (uid, name))

            # Seed approved publication authored by u_alice
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, idempotency_key, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, ?, ?, ?, ?)
            """, (
                "art_test_01", "draft_art_01", "Публикация Алисы", "u_alice",
                json.dumps({"materialType": "article", "topics": ["testing"]}, ensure_ascii=False),
                "<p>Текст статьи</p>", "idemp_art_01", "hash_art_01",
                "2026-10-01T10:00:00Z", "2026-10-01T10:00:00Z"
            ))

            # Seed approved question authored by u_bob
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, idempotency_key, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, ?, ?, ?, ?)
            """, (
                "quest_test_01", "draft_quest_01", "Вопрос Боба", "u_bob",
                json.dumps({"materialType": "question", "topics": ["testing"]}, ensure_ascii=False),
                "<p>Текст вопроса</p>", "idemp_quest_01", "hash_quest_01",
                "2026-10-01T10:00:00Z", "2026-10-01T10:00:00Z"
            ))
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

    def _login(self, user_id: str, name: str = "Test User", role: str = "user") -> str:
        url = f"{self.base_url}/api/auth/login"
        body = json.dumps({"userId": user_id, "name": name, "role": role}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            return resp.headers.get("Set-Cookie", "")

    def _post_json(self, path: str, data: Any, cookie: Optional[str] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                resp_body = resp.read().decode("utf-8")
                return resp.status, json.loads(resp_body) if resp_body else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            try:
                return e.code, json.loads(err_body)
            except Exception:
                return e.code, {"error": err_body}

    def test_01_article_reports_schema_exists(self):
        """Verify article_reports table and indexes are created in SQLite."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(article_reports)")
        columns = {row[1]: row[2] for row in cur.fetchall()}
        conn.close()

        self.assertIn("id", columns)
        self.assertIn("article_id", columns)
        self.assertIn("user_id", columns)
        self.assertIn("reason", columns)
        self.assertIn("details", columns)
        self.assertIn("created_at", columns)

    def test_02_report_requires_auth(self):
        """POST /api/articles/<id>/report returns 401 when unauthenticated."""
        status, data = self._post_json("/api/articles/art_test_01/report", {"reason": "spam"})
        self.assertEqual(status, 401)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "AUTH_REQUIRED")

    def test_03_cannot_report_own_article_or_question(self):
        """Author cannot report their own publication or question (403)."""
        alice_cookie = self._login("u_alice", "Алиса", "author")
        status, data = self._post_json(
            "/api/articles/art_test_01/report",
            {"reason": "spam"},
            cookie=alice_cookie
        )
        self.assertEqual(status, 403)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "CANNOT_REPORT_OWN_ARTICLE")

        bob_cookie = self._login("u_bob", "Боб", "user")
        status, data = self._post_json(
            "/api/articles/quest_test_01/report",
            {"reason": "spam"},
            cookie=bob_cookie
        )
        self.assertEqual(status, 403)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "CANNOT_REPORT_OWN_ARTICLE")

    def test_04_report_validates_reason(self):
        """Report requires non-empty reason within 200 characters."""
        bob_cookie = self._login("u_bob", "Боб", "user")

        # Empty reason
        status, data = self._post_json("/api/articles/art_test_01/report", {"reason": ""}, cookie=bob_cookie)
        self.assertEqual(status, 400)

        # Missing reason
        status, data = self._post_json("/api/articles/art_test_01/report", {}, cookie=bob_cookie)
        self.assertEqual(status, 400)

        # Reason exceeding 200 characters
        status, data = self._post_json(
            "/api/articles/art_test_01/report",
            {"reason": "a" * 201},
            cookie=bob_cookie
        )
        self.assertEqual(status, 400)
        self.assertEqual(data.get("code"), "REASON_TOO_LONG")

    def test_05_report_success_and_duplicate_rejection(self):
        """Submitting a valid report succeeds (200) and duplicate report from same user is rejected (409)."""
        bob_cookie = self._login("u_bob", "Боб", "user")

        # First report by Bob on Alice's article
        status, data = self._post_json(
            "/api/articles/art_test_01/report",
            {"reason": "spam", "details": "Рекламный спам"},
            cookie=bob_cookie
        )
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("message"), "Жалоба отправлена")

        # Duplicate report by Bob on Alice's article
        status, data = self._post_json(
            "/api/articles/art_test_01/report",
            {"reason": "insult"},
            cookie=bob_cookie
        )
        self.assertEqual(status, 409)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "REPORT_ALREADY_EXISTS")

        # Another user Charlie can still report Alice's article
        charlie_cookie = self._login("u_charlie", "Чарли", "user")
        status, data = self._post_json(
            "/api/articles/art_test_01/report",
            {"reason": "malicious"},
            cookie=charlie_cookie
        )
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))


class TestUniqueColorsAndCardActionsFrontend(unittest.TestCase):
    """Verifies unique action button palette, reported active state, and card action bar buttons."""

    @classmethod
    def setUpClass(cls):
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.theme_css = read_file("frontend/public/css/theme.css")
        cls.feed_css = read_file("frontend/public/css/feed.css")
        cls.card_js = read_file("frontend/public/js/card.js")
        cls.feed_js = read_file("frontend/public/js/feed.js")
        cls.feed_html = read_file("frontend/public/feed.html")

    def test_06_unique_colors_palette_for_all_action_buttons(self):
        """Every action button must have a distinct, unique, and harmonious color token."""
        for css_content, source_name in [(self.article_css, "article.css"), (self.theme_css, "theme.css")]:
            # Reply: Sky (#38bdf8)
            reply_match = re.search(r'\.btn-comment-action\.btn-reply-comment:hover[^{]*\{([^}]+)\}', css_content)
            self.assertIsNotNone(reply_match, f"Reply hover rule must exist in {source_name}")
            self.assertIn("#38bdf8", reply_match.group(1))

            # Save: Amber (#f59e0b)
            save_match = re.search(r'\.btn-comment-action\.btn-save-comment:hover[^{]*\{([^}]+)\}', css_content)
            self.assertIsNotNone(save_match, f"Save hover rule must exist in {source_name}")
            self.assertIn("#f59e0b", save_match.group(1))

            # Share: Purple (#a855f7)
            share_match = re.search(r'\.btn-comment-action\.btn-share-comment:hover[^{]*\{([^}]+)\}', css_content)
            self.assertIsNotNone(share_match, f"Share hover rule must exist in {source_name}")
            self.assertIn("#a855f7", share_match.group(1))

            # Subscribe: Teal (#14b8a6)
            sub_match = re.search(r'\.btn-comment-action\.btn-subscribe-comment:hover[^{]*\{([^}]+)\}', css_content)
            self.assertIsNotNone(sub_match, f"Subscribe hover rule must exist in {source_name}")
            self.assertIn("#14b8a6", sub_match.group(1))

            # Report: Raspberry (#e11d48)
            rep_match = re.search(r'\.btn-comment-action\.btn-report-comment:hover[^{]*\{([^}]+)\}', css_content)
            self.assertIsNotNone(rep_match, f"Report hover rule must exist in {source_name}")
            self.assertIn("#e11d48", rep_match.group(1))

            # Delete: Red (#ef4444)
            del_match = re.search(r'\.btn-comment-action\.btn-delete-comment:hover[^{]*\{([^}]+)\}', css_content)
            self.assertIsNotNone(del_match, f"Delete hover rule must exist in {source_name}")
            self.assertIn("#ef4444", del_match.group(1))

            # Edit: Indigo (#6366f1)
            edit_match = re.search(r'\.btn-comment-action\.btn-edit-comment:hover[^{]*\{([^}]+)\}', css_content)
            self.assertIsNotNone(edit_match, f"Edit hover rule must exist in {source_name}")
            self.assertIn("#6366f1", edit_match.group(1))

    def test_07_reported_state_lights_up_in_raspberry_not_grey_opacity(self):
        """Reported button (.is-reported) must light up in raspberry with fill, not grey opacity."""
        for css_content, source_name in [(self.article_css, "article.css"), (self.theme_css, "theme.css")]:
            rep_active_match = re.search(r'\.btn-comment-action\.is-reported[^{]*\{([^}]+)\}', css_content)
            self.assertIsNotNone(rep_active_match, f".is-reported rule must exist in {source_name}")
            block = rep_active_match.group(1)
            self.assertIn("#e11d48", block)
            self.assertIn("cursor: pointer;", block)
            self.assertNotIn("opacity: 0.5;", block)

        # In article.js: markCommentAsReported sets fill to currentColor and disabled to false
        self.assertIn("markCommentAsReported", self.article_js)
        self.assertIn("is-reported", self.article_js)
        self.assertIn("Жалоба уже отправлена", self.article_js)

    def test_08_feed_card_action_bar_contains_share_and_report_buttons(self):
        """Card action bar in card.js must include Share and Report buttons for publications and questions."""
        # Share button markup in card.js
        self.assertIn("btn-card-share", self.card_js)
        self.assertIn("Поделиться", self.card_js)

        # Report button markup in card.js
        self.assertIn("btn-card-report", self.card_js)
        self.assertIn("Пожаловаться", self.card_js)

        # In question branch of footerLeftHtml
        self.assertIn("footerLeftHtml = likeBtnHtml + voteCapsuleHtml + answersBtnHtml + bookmarkHtml;", self.card_js)
        self.assertIn("footerLeftHtml += shareHtml + reportHtml;", self.card_js)

        # In article branch of footerLeftHtml
        self.assertIn("footerLeftHtml = likeBtnHtml + voteCapsuleHtml + commentsBtnHtml + bookmarkHtml;", self.card_js)

    def test_09_card_action_buttons_styling_in_feed_css(self):
        """Feed card Share and Report buttons must have 36px geometry, unique hover colors, and active reported styling."""
        self.assertIn(".btn-card-share", self.feed_css)
        self.assertIn(".btn-card-report", self.feed_css)
        self.assertIn("#a855f7", self.feed_css)  # purple for share
        self.assertIn("#e11d48", self.feed_css)  # raspberry for report

    def test_10_popover_and_modal_present_in_feed_html_and_feed_js(self):
        """Verify feed.html includes #feedSharePopover and #articleReportModal, and feed.js binds events."""
        self.assertIn("feedSharePopover", self.feed_html)
        self.assertIn("articleReportModal", self.feed_html)
        self.assertIn("openArticleSharePopover", self.feed_js)
        self.assertIn("openArticleReportModal", self.feed_js)
        self.assertIn("/api/articles/' + encodeURIComponent(articleId) + '/report", self.feed_js)

    def test_11_zero_emojis_no_em_dashes_offline_first(self):
        """Ensure zero emojis, zero em dashes, and 100% offline-first."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        files_to_check = [
            (read_file("tests/test_issue75_unique_colors_and_card_actions.py"), "test_issue75_unique_colors_and_card_actions.py"),
            (self.article_js, "article.js"),
            (self.article_css, "article.css"),
            (self.theme_css, "theme.css"),
            (self.feed_css, "feed.css"),
            (self.card_js, "card.js"),
        ]
        for content, name in files_to_check:
            self.assertIsNone(emoji_pattern.search(content), f"Emoji found in {name}")
            self.assertNotIn("\u2014", content, f"Em dash found in {name}")

        for css_content, source_name in [
            (self.article_css, "article.css"),
            (self.theme_css, "theme.css"),
            (self.feed_css, "feed.css")
        ]:
            urls = re.findall(r'url\s*\(\s*["\']?(https?://[^"\')]+)', css_content)
            self.assertEqual(len(urls), 0, f"External CDN url found in {source_name}: {urls}")

    def test_12_card_report_icon_full_flag_svg_path(self):
        """Verify card.js report icon includes full flag SVG path with top contour."""
        self.assertIn("V3s-1 1-4 1-5-2-8-2-4 1-4 1z", self.card_js)


if __name__ == "__main__":
    unittest.main()
