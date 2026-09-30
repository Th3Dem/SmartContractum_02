#!/usr/bin/env python3
"""
tests/test_issue22_sc023_browser_smoke.py

Browser smoke and CI pipeline test suite for Issue #22 (SC-023):
"Внедрить базовый GitHub Actions CI с реальными браузерными проверками".

Acceptance Criteria:
1. .github/workflows/ci.yml is configured with push & pull_request triggers on main,
   runs standard test suite, installs Playwright, and executes browser smoke tests.
2. TestBrowserSmoke runs headless Chromium checks when Playwright is available:
   - test_01_feed_page_loads_and_renders_articles: verifies feed rendering.
   - test_02_author_profile_modal_opens_on_click: verifies SC-007 modal opening in DOM.
   - test_03_comment_single_escaping_in_browser_dom: verifies SC-021 single escaping in DOM.
   - test_04_offline_badge_and_error_retry: verifies SC-020 error retry and offline badge.
3. Safe offline fallback: graceful skipUnless when Playwright is absent locally,
   preserving 100% PASS Compilation Gate in offline environments.
"""

import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.request
from typing import Any, Dict, Optional, Tuple

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

import server
from server import create_server, init_db

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
WORKFLOW_PATH = os.path.join(PROJECT_ROOT, ".github", "workflows", "ci.yml")


class TestCIWorkflowConfiguration(unittest.TestCase):
    """Validates GitHub Actions CI workflow specification and structure."""

    def test_01_workflow_file_exists(self) -> None:
        """Verify .github/workflows/ci.yml exists on disk."""
        self.assertTrue(
            os.path.isfile(WORKFLOW_PATH),
            f"CI workflow file not found at {WORKFLOW_PATH}"
        )

    def test_02_workflow_yaml_validity_and_name(self) -> None:
        """Verify workflow parses as valid YAML with correct name."""
        with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        if YAML_AVAILABLE:
            data = yaml.safe_load(content)
            self.assertIsInstance(data, dict, "Workflow root must be a YAML mapping")
            self.assertEqual(data.get("name"), "CI Pipeline")
        else:
            self.assertTrue(len(content.strip()) > 0, "Workflow file must not be empty")
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            self.assertIn("name: CI Pipeline", lines)
            self.assertTrue(any(line.startswith("jobs:") for line in lines))

    def test_03_workflow_triggers_on_main(self) -> None:
        """Verify push and pull_request triggers on branch main."""
        with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
            if YAML_AVAILABLE:
                data = yaml.safe_load(f)
                triggers = data.get("on") or data.get(True)
                self.assertIsNotNone(triggers, "Workflow must define triggers")
                self.assertIn("push", triggers, "push trigger must be configured")
                self.assertIn("pull_request", triggers, "pull_request trigger must be configured")

                push_branches = triggers["push"].get("branches", [])
                pr_branches = triggers["pull_request"].get("branches", [])
                self.assertIn("main", push_branches, "push must trigger on main")
                self.assertIn("main", pr_branches, "pull_request must trigger on main")
            else:
                content = f.read()
                self.assertIn("push:", content)
                self.assertIn("pull_request:", content)
                self.assertIn("main", content)

    def test_04_workflow_job_steps_contract(self) -> None:
        """Verify required jobs and steps in CI workflow."""
        with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
            if YAML_AVAILABLE:
                data = yaml.safe_load(f)
                jobs = data.get("jobs", {})
                self.assertIn("test", jobs, "Job 'test' must be defined")

                test_job = jobs["test"]
                self.assertEqual(test_job.get("runs-on"), "ubuntu-latest")

                steps = test_job.get("steps", [])
                step_runs = [s.get("run", "") for s in steps if "run" in s]
                step_uses = [s.get("uses", "") for s in steps if "uses" in s]
            else:
                content = f.read()
                self.assertIn("jobs:", content)
                self.assertIn("test:", content)
                self.assertIn("runs-on: ubuntu-latest", content)
                step_runs = [
                    line.strip().replace("run: ", "")
                    for line in content.splitlines()
                    if line.strip().startswith("run:")
                ]
                step_uses = [
                    line.strip().replace("uses: ", "")
                    for line in content.splitlines()
                    if line.strip().startswith("uses:")
                ]

        # 1. Checkout
        self.assertTrue(any("actions/checkout@v4" in u for u in step_uses))

        # 2. Setup python
        self.assertTrue(any("actions/setup-python@v5" in u for u in step_uses))

        # 3. Unit & integration test execution
        self.assertTrue(
            any("python3 -m unittest discover tests -v" in r for r in step_runs),
            "Step for running full unit and integration tests is missing"
        )

        # 4. Playwright install
        self.assertTrue(
            any("playwright install --with-deps chromium" in r for r in step_runs),
            "Step for installing Playwright and chromium is missing"
        )

        # 5. Browser smoke tests
        self.assertTrue(
            any("tests/test_issue22_sc023_browser_smoke.py" in r for r in step_runs),
            "Step for running browser smoke tests is missing"
        )

    def test_05_zero_emojis_in_workflow_and_suite(self) -> None:
        """Zero emojis in ci.yml and test_issue22_sc023_browser_smoke.py."""
        emoji_ranges = [
            (0x1F600, 0x1F64F),
            (0x1F300, 0x1F5FF),
            (0x1F680, 0x1F6FF),
            (0x2600, 0x26FF),
            (0x2700, 0x27BF),
        ]
        files_to_check = [
            WORKFLOW_PATH,
            os.path.abspath(__file__),
        ]
        for path in files_to_check:
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            for ch in text:
                cp = ord(ch)
                for start, end in emoji_ranges:
                    self.assertFalse(
                        start <= cp <= end,
                        f"Found emoji '{ch}' (U+{cp:X}) in {path}"
                    )


class TestSmokeServerSeedAndContracts(unittest.TestCase):
    """Verifies server startup, seeding, and API contracts for smoke tests offline."""

    temp_dir: str
    db_path: str
    media_dir: str
    httpd: Any
    server_thread: threading.Thread
    port: int
    base_url: str

    @classmethod
    def setUpClass(cls) -> None:
        """Initializes server and database with smoke test seeds."""
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_sc023_contracts.db")
        cls.media_dir = os.path.join(cls.temp_dir, "media")
        os.makedirs(cls.media_dir, exist_ok=True)

        server.DEFAULT_DB_PATH = cls.db_path
        server.MEDIA_DIR = cls.media_dir

        conn = init_db(cls.db_path, seed=False)
        with conn:
            conn.execute("""
                INSERT INTO user_profiles (
                    user_id, name, specialization, company, bio, avatar, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "expert_alex_01",
                "Алексей Экспертов",
                "Senior Smart Contract Engineer",
                "Antigravity Labs",
                "Аудит смарт-контрактов и децентрализованные протоколы",
                "",
                "2026-09-29T10:00:00Z",
                "2026-09-29T10:00:00Z"
            ))

            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "art_smoke_01",
                "draft_smoke_01",
                "Архитектура безопасных смарт-контрактов",
                "expert_alex_01",
                json.dumps({
                    "materialType": "article",
                    "topics": ["security", "solidity"],
                    "format": "guide",
                    "complexity": "medium",
                    "description": "Практическое руководство по архитектуре смарт-контрактов."
                }, ensure_ascii=False),
                "<h2>Безопасность кода</h2><p>Содержимое тестовой статьи для проверки браузера.</p>",
                "idemp_art_smoke_01",
                "hash_art_smoke_01",
                "2026-09-29T10:00:00Z",
                "2026-09-29T10:00:00Z"
            ))

            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "quest_smoke_01",
                "draft_quest_01",
                "Как избежать уязвимостей reentrancy в Solidity?",
                "expert_alex_01",
                json.dumps({
                    "materialType": "question",
                    "topics": ["security"],
                    "format": "qa",
                    "complexity": "easy",
                    "description": "Вопрос об эффективных паттернах защиты от reentrancy.",
                    "questionStatus": "unsolved"
                }, ensure_ascii=False),
                "<p>Какие модификаторы или проверки лучше использовать?</p>",
                "idemp_quest_smoke_01",
                "hash_quest_smoke_01",
                "2026-09-29T11:00:00Z",
                "2026-09-29T11:00:00Z"
            ))

            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar,
                    content, status, comment_type, is_solution, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'comment', 0, ?)
            """, (
                "comm_smoke_01",
                "art_smoke_01",
                "reader_bob_02",
                "Боб Читатель",
                "",
                'Тест спецсимволов: Rock & Roll <script>alert("xss")</script> & "Цитата" \'',
                "2026-09-29T12:00:00Z"
            ))
        conn.close()

        cls.httpd = create_server(
            host="127.0.0.1",
            port=0,
            db_path=cls.db_path,
            directory=FRONTEND_DIR,
            media_dir=cls.media_dir
        )
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        """Cleans up HTTP server and temporary database."""
        if hasattr(cls, "httpd") and cls.httpd:
            try:
                cls.httpd.shutdown()
                cls.httpd.server_close()
            except Exception:
                pass
        if hasattr(cls, "server_thread") and cls.server_thread:
            cls.server_thread.join(timeout=2)
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _get_json(self, path: str) -> Tuple[int, Dict[str, Any]]:
        req = urllib.request.Request(f"{self.base_url}{path}")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data

    def test_01_static_pages_served_200(self) -> None:
        """Verify feed.html and article.html are served with 200 OK."""
        for page_name in ["feed.html", "article.html"]:
            req = urllib.request.Request(f"{self.base_url}/{page_name}")
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200, f"{page_name} must return 200")
                content = resp.read().decode("utf-8")
                self.assertGreater(len(content), 100)

    def test_02_articles_api_returns_seeded_data(self) -> None:
        """Verify /api/articles returns seeded article and question."""
        status, data = self._get_json("/api/articles?tab=all")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        articles = data.get("articles", [])
        self.assertGreaterEqual(len(articles), 2)
        titles = [a["title"] for a in articles]
        self.assertIn("Архитектура безопасных смарт-контрактов", titles)
        self.assertIn("Как избежать уязвимостей reentrancy в Solidity?", titles)

    def test_03_user_profile_api_returns_author_info(self) -> None:
        """Verify /api/users/expert_alex_01 returns author profile (SC-007)."""
        status, data = self._get_json("/api/users/expert_alex_01")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        user = data.get("user") or {}
        self.assertEqual(user.get("name"), "Алексей Экспертов")
        self.assertEqual(user.get("company"), "Antigravity Labs")

    def test_04_comments_api_returns_raw_plain_text(self) -> None:
        """Verify comments API returns raw characters without double escaping (SC-021)."""
        status, data = self._get_json("/api/articles/art_smoke_01/comments")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        comments = data.get("comments", [])
        self.assertGreaterEqual(len(comments), 1)
        comment_content = comments[0]["content"]
        self.assertIn("&", comment_content)
        self.assertIn("<script>", comment_content)
        self.assertIn('"Цитата"', comment_content)
        self.assertNotIn("&amp;amp;", comment_content)

    def test_05_client_escaping_produces_single_escaped_entities(self) -> None:
        """Verify client escapeHtml simulation does not double-escape."""
        raw = 'Rock & Roll <script>alert("xss")</script> & "Цитата" \''
        escaped = (
            raw.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#039;")
        )
        self.assertNotIn("&amp;amp;", escaped)
        self.assertIn("&amp;", escaped)
        self.assertIn("&lt;script&gt;", escaped)


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, "Playwright is not installed in the local environment")
class TestBrowserSmoke(unittest.TestCase):
    """End-to-end headless browser smoke tests using Playwright."""

    temp_dir: str
    db_path: str
    media_dir: str
    httpd: Any
    server_thread: threading.Thread
    port: int
    base_url: str
    playwright: Any
    browser: Any

    @classmethod
    def setUpClass(cls) -> None:
        """Spins up test HTTP server and launches Playwright Chromium browser."""
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_sc023.db")
        cls.media_dir = os.path.join(cls.temp_dir, "media")
        os.makedirs(cls.media_dir, exist_ok=True)

        server.DEFAULT_DB_PATH = cls.db_path
        server.MEDIA_DIR = cls.media_dir

        conn = init_db(cls.db_path, seed=False)
        with conn:
            # Seed author profile
            conn.execute("""
                INSERT INTO user_profiles (
                    user_id, name, specialization, company, bio, avatar, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "expert_alex_01",
                "Алексей Экспертов",
                "Senior Smart Contract Engineer",
                "Antigravity Labs",
                "Аудит смарт-контрактов и децентрализованные протоколы",
                "",
                "2026-09-29T10:00:00Z",
                "2026-09-29T10:00:00Z"
            ))

            # Seed article
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "art_smoke_01",
                "draft_smoke_01",
                "Архитектура безопасных смарт-контрактов",
                "expert_alex_01",
                json.dumps({
                    "materialType": "article",
                    "topics": ["security", "solidity"],
                    "format": "guide",
                    "complexity": "medium",
                    "description": "Практическое руководство по архитектуре смарт-контрактов."
                }, ensure_ascii=False),
                "<h2>Безопасность кода</h2><p>Содержимое тестовой статьи для проверки браузера.</p>",
                "idemp_art_smoke_01",
                "hash_art_smoke_01",
                "2026-09-29T10:00:00Z",
                "2026-09-29T10:00:00Z"
            ))

            # Seed question
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "quest_smoke_01",
                "draft_quest_01",
                "Как избежать уязвимостей reentrancy в Solidity?",
                "expert_alex_01",
                json.dumps({
                    "materialType": "question",
                    "topics": ["security"],
                    "format": "qa",
                    "complexity": "easy",
                    "description": "Вопрос об эффективных паттернах защиты от reentrancy.",
                    "questionStatus": "unsolved"
                }, ensure_ascii=False),
                "<p>Какие модификаторы или проверки лучше использовать?</p>",
                "idemp_quest_smoke_01",
                "hash_quest_smoke_01",
                "2026-09-29T11:00:00Z",
                "2026-09-29T11:00:00Z"
            ))

            # Seed comment with special characters for SC-021 verification
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar,
                    content, status, comment_type, is_solution, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'comment', 0, ?)
            """, (
                "comm_smoke_01",
                "art_smoke_01",
                "reader_bob_02",
                "Боб Читатель",
                "",
                'Тест спецсимволов: Rock & Roll <script>alert("xss")</script> & "Цитата" \'',
                "2026-09-29T12:00:00Z"
            ))
        conn.close()

        cls.httpd = create_server(
            host="127.0.0.1",
            port=0,
            db_path=cls.db_path,
            directory=FRONTEND_DIR,
            media_dir=cls.media_dir
        )
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        # Launch Playwright Chromium
        try:
            cls.playwright = sync_playwright().start()
            cls.browser = cls.playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
        except Exception as err:
            cls.tearDownClass()
            raise unittest.SkipTest(f"Playwright chromium launch failed: {err}")

    @classmethod
    def tearDownClass(cls) -> None:
        """Shuts down browser and terminates HTTP server."""
        if hasattr(cls, "browser") and cls.browser:
            try:
                cls.browser.close()
            except Exception:
                pass
        if hasattr(cls, "playwright") and cls.playwright:
            try:
                cls.playwright.stop()
            except Exception:
                pass
        if hasattr(cls, "httpd") and cls.httpd:
            try:
                cls.httpd.shutdown()
                cls.httpd.server_close()
            except Exception:
                pass
        if hasattr(cls, "server_thread") and cls.server_thread:
            cls.server_thread.join(timeout=2)
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_feed_page_loads_and_renders_articles(self) -> None:
        """Opens /feed.html, waits for .feed-card, asserts articles are rendered."""
        page = self.browser.new_page()
        try:
            page.goto(f"{self.base_url}/feed.html", wait_until="domcontentloaded")
            page.wait_for_selector(".feed-card", timeout=10000)

            cards = page.locator(".feed-card")
            card_count = cards.count()
            self.assertGreaterEqual(card_count, 1, "At least one .feed-card must be present in DOM")

            titles = page.locator(".feed-card .card-title").all_text_contents()
            has_seeded_article = any(
                "Архитектура безопасных смарт-контрактов" in t for t in titles
            )
            self.assertTrue(
                has_seeded_article,
                f"Expected seeded article in feed card titles: {titles}"
            )
        finally:
            page.close()

    def test_02_author_profile_modal_opens_on_click(self) -> None:
        """Clicks .btn-author-profile, verifies #userProfileModal becomes visible (SC-007)."""
        page = self.browser.new_page()
        try:
            page.goto(f"{self.base_url}/feed.html", wait_until="domcontentloaded")
            page.wait_for_selector(".btn-author-profile", timeout=10000)

            author_btn = page.locator(".btn-author-profile").first
            self.assertTrue(author_btn.is_visible(), "Author button must be visible in DOM")

            # SC-007 contract check: data-author-id populated
            data_author_id = author_btn.get_attribute("data-author-id")
            self.assertEqual(
                data_author_id,
                "expert_alex_01",
                "Author profile trigger must contain expected data-author-id"
            )

            # Click author profile button
            author_btn.click()

            # Modal becomes visible
            modal = page.locator("#userProfileModal")
            modal.wait_for(state="visible", timeout=5000)
            self.assertTrue(
                modal.is_visible(),
                "#userProfileModal must become visible after clicking author button"
            )

            # Modal body loads author details
            modal_body = page.locator("#userProfileModalBody")
            page.wait_for_function(
                "document.getElementById('userProfileModalBody') && "
                "!document.getElementById('userProfileModalBody').innerText.includes('Загрузка профиля')",
                timeout=5000
            )
            body_text = modal_body.text_content() or ""
            self.assertIn("Алексей Экспертов", body_text)
            self.assertIn("Antigravity Labs", body_text)
        finally:
            page.close()

    def test_03_comment_single_escaping_in_browser_dom(self) -> None:
        """Verifies DOM .comment-text has single-escaped entities without &amp;amp; (SC-021)."""
        page = self.browser.new_page()
        try:
            page.goto(f"{self.base_url}/article.html?id=art_smoke_01", wait_until="domcontentloaded")
            page.wait_for_selector(".comment-text", timeout=10000)

            comments = page.locator(".comment-text")
            self.assertGreaterEqual(comments.count(), 1, "At least one comment must be rendered")

            comment_el = comments.first
            inner_html = comment_el.inner_html()
            text_content = comment_el.text_content() or ""

            # SC-021 Invariant 1: Absence of double-escaped entities in HTML
            self.assertNotIn(
                "&amp;amp;",
                inner_html,
                "DOM innerHTML must not contain double-escaped &amp;amp;"
            )
            self.assertNotIn(
                "&amp;lt;",
                inner_html,
                "DOM innerHTML must not contain double-escaped &amp;lt;"
            )
            self.assertNotIn(
                "&amp;gt;",
                inner_html,
                "DOM innerHTML must not contain double-escaped &amp;gt;"
            )
            self.assertNotIn(
                "&amp;quot;",
                inner_html,
                "DOM innerHTML must not contain double-escaped &amp;quot;"
            )

            # SC-021 Invariant 2: Presence of valid single-escaped entities
            self.assertIn(
                "&lt;script&gt;",
                inner_html,
                "DOM innerHTML must contain single-escaped &lt;script&gt;"
            )
            self.assertIn("&amp;", inner_html, "DOM innerHTML must contain single-escaped &amp;")
            self.assertIn(
                '"Цитата"',
                inner_html,
                "DOM innerHTML must contain raw quotes for text nodes"
            )

            # SC-021 Invariant 3: Rendered text in browser DOM equals expected raw content
            expected_raw_content = (
                'Тест спецсимволов: Rock & Roll <script>alert("xss")</script> & "Цитата" \''
            )
            self.assertEqual(text_content, expected_raw_content)
        finally:
            page.close()

    def test_04_offline_badge_and_error_retry(self) -> None:
        """Verifies #feedRetryBtn and #feedOfflineBadge behavior in browser DOM (SC-020)."""
        page = self.browser.new_page()
        try:
            page.goto(f"{self.base_url}/feed.html", wait_until="domcontentloaded")
            page.wait_for_selector(".feed-card", timeout=10000)

            # 1. Offline badge behavior
            page.evaluate("window.showOfflineBadge && window.showOfflineBadge()")
            badge = page.locator("#feedOfflineBadge")
            badge.wait_for(state="visible", timeout=5000)
            self.assertTrue(badge.is_visible(), "#feedOfflineBadge must be visible in offline mode")
            self.assertIn("Автономный режим", badge.text_content() or "")

            page.evaluate("window.hideOfflineBadge && window.hideOfflineBadge()")
            badge.wait_for(state="hidden", timeout=5000)
            self.assertFalse(badge.is_visible(), "#feedOfflineBadge must be hidden when offline disabled")

            # 2. Server error retry button behavior (SC-020)
            page.route(
                "**/api/articles*",
                lambda route: route.fulfill(
                    status=500,
                    headers={"Content-Type": "application/json"},
                    body='{"success": false, "error": "Internal Server Error"}'
                )
            )

            page.evaluate(
                "window.FeedApp && window.FeedApp.loadArticles && window.FeedApp.loadArticles(true)"
            )

            retry_btn = page.locator("#feedRetryBtn")
            retry_btn.wait_for(state="visible", timeout=5000)
            self.assertTrue(retry_btn.is_visible(), "#feedRetryBtn must be visible on 500 error")
            self.assertIn("Повторить попытку", retry_btn.text_content() or "")

            # Unroute error and click retry
            page.unroute("**/api/articles*")
            retry_btn.click()

            # Articles restored and retry button removed
            page.wait_for_selector(".feed-card", timeout=5000)
            self.assertGreaterEqual(page.locator(".feed-card").count(), 1)
            self.assertEqual(page.locator("#feedRetryBtn").count(), 0)
        finally:
            page.close()

    def test_05_qa_full_lifecycle_and_invariants(self) -> None:
        """
        Comprehensive multi-user Q&A lifecycle and invariants test (Issue #26):
        1. User A posts question clarification (commentType = 'comment').
        2. User B posts answer (commentType = 'answer').
        3. User C posts reply to User B's answer (parentAnswerId = answer_b_id).
        4. User B edits their answer.
        5. User B attempts second answer: blocked with 409 ANSWER_ALREADY_EXISTS.
        6. Question author marks answer B as solution (User C has no permission/button).
        7. Verifies DOM: solution badge, updated badge, count badges, and deep link.
        """
        page = self.browser.new_page()
        try:
            def switch_user(user_id: str, name: str) -> None:
                page.goto(f"{self.base_url}/feed.html", wait_until="domcontentloaded")
                page.evaluate("""async ([uid, uname]) => {
                    await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({userId: uid, name: uname, role: 'user'})
                    });
                }""", [user_id, name])

            # 1. User A logs in and posts question clarification
            switch_user("user_a_qa", "Анна Уточнитель")
            page.goto(f"{self.base_url}/article.html?id=quest_smoke_01", wait_until="domcontentloaded")
            page.wait_for_selector("#questionCommentsWrapper", timeout=10000)

            # Open question clarification form
            clarification_btn = page.locator("#btnAddQuestionClarification")
            clarification_btn.click()
            page.wait_for_selector("#questionClarificationForm", state="visible", timeout=5000)

            page.fill("#questionClarificationInput", "Какая версия Solidity используется в проекте?")
            page.click("#btnSubmitClarification")

            # Wait for clarification to appear
            page.wait_for_selector(".question-comment-item", timeout=5000)
            self.assertGreaterEqual(page.locator(".question-comment-item").count(), 1)
            self.assertEqual(page.locator("#questionCommentsCountBadge").text_content(), "1")
            self.assertEqual(page.locator("#answersCountBadge").text_content(), "0")

            # 2. User B logs in and posts an answer
            switch_user("user_b_qa", "Борис Ответчик")
            page.goto(f"{self.base_url}/article.html?id=quest_smoke_01", wait_until="domcontentloaded")
            page.wait_for_selector("#questionAnswerForm", state="visible", timeout=10000)

            page.fill("#answerTextInput", "Используйте Checks-Effects-Interactions и ReentrancyGuard.")
            page.click("#btnSubmitAnswer")

            # Wait for answer card to appear
            page.wait_for_selector(".answer-card", timeout=5000)
            answer_card = page.locator(".answer-card").first
            answer_b_id = answer_card.get_attribute("data-id")
            self.assertTrue(answer_b_id, "Answer card must have data-id attribute")
            self.assertEqual(page.locator("#answersCountBadge").text_content(), "1")

            # My answer banner is shown, answer submission form wrap is hidden
            page.wait_for_selector("#myAnswerBanner", state="visible", timeout=5000)
            self.assertFalse(page.locator("#myAnswerFormWrap").is_visible())

            # 3. User C logs in and replies to User B's answer
            switch_user("user_c_qa", "Владимир Репликатор")
            page.goto(f"{self.base_url}/article.html?id=quest_smoke_01", wait_until="domcontentloaded")
            page.wait_for_selector(".answer-card", timeout=10000)

            # Verify User C does NOT have solution action button
            self.assertEqual(
                page.locator(".btn-toggle-solution").count(),
                0,
                "Non-author user must not see solution button"
            )

            # Click reply on answer B
            reply_btn = page.locator(".btn-reply-answer").first
            reply_btn.click()
            page.wait_for_selector(".answer-reply-form", state="visible", timeout=5000)

            page.fill(".answer-reply-textarea", "Согласен, ReentrancyGuard решает проблему надежно.")
            page.click(".btn-submit-reply")

            # Wait for reply item to appear
            page.wait_for_selector(".answer-reply-item", timeout=5000)
            self.assertGreaterEqual(page.locator(".answer-reply-item").count(), 1)
            self.assertIn("ReentrancyGuard", page.locator(".answer-reply-item").first.text_content() or "")

            # 4. User B logs in and edits answer
            switch_user("user_b_qa", "Борис Ответчик")
            page.goto(f"{self.base_url}/article.html?id=quest_smoke_01", wait_until="domcontentloaded")
            page.wait_for_selector(".answer-card", timeout=10000)

            # Verify answer banner is present for User B
            self.assertTrue(page.locator("#myAnswerBanner").is_visible())

            # Edit answer
            edit_btn = page.locator(".btn-edit-answer").first
            edit_btn.click()
            page.wait_for_selector(".answer-edit-form-wrap", state="visible", timeout=5000)

            page.fill(".answer-edit-textarea", "Используйте Checks-Effects-Interactions и transient storage TSTORE.")
            page.click(".btn-save-answer-edit")

            # Verify updated text and badge
            page.wait_for_selector(".comment-updated-badge", timeout=5000)
            self.assertIn("TSTORE", page.locator(".answer-text").first.text_content() or "")
            self.assertIn("Изменено", page.locator(".comment-updated-badge").first.text_content() or "")

            # 5. User B attempts duplicate answer (409 Conflict)
            dup_result = page.evaluate("""async (artId) => {
                const res = await fetch('/api/articles/' + encodeURIComponent(artId) + '/comments', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        content: 'Второй ответ от того же пользователя.',
                        commentType: 'answer'
                    })
                });
                const data = await res.json();
                return {status: res.status, data: data};
            }""", "quest_smoke_01")
            self.assertEqual(dup_result["status"], 409)
            self.assertEqual(dup_result["data"].get("code"), "ANSWER_ALREADY_EXISTS")

            # 6. Question Author (expert_alex_01) marks answer B as solution
            switch_user("expert_alex_01", "Алексей Экспертов")
            page.goto(f"{self.base_url}/article.html?id=quest_smoke_01", wait_until="domcontentloaded")
            page.wait_for_selector(".answer-card", timeout=10000)

            # Author sees solution button
            solution_btn = page.locator(".btn-toggle-solution").first
            self.assertTrue(solution_btn.is_visible())
            solution_btn.click()

            # Wait for solution badge and styling
            page.wait_for_selector(".solution-badge", timeout=5000)
            self.assertIn("Решение принято автором", page.locator(".solution-badge").first.text_content() or "")
            self.assertIn("is-solution-answer", page.locator(".answer-card").first.get_attribute("class") or "")
            self.assertIn("Снять отметку решения", solution_btn.text_content() or "")

            # 7. Deep link navigation to answer
            page.goto(f"{self.base_url}/article.html?id=quest_smoke_01#comm_{answer_b_id}", wait_until="domcontentloaded")
            page.wait_for_selector(f"#comm_{answer_b_id}", timeout=5000)
            target_answer = page.locator(f"#comm_{answer_b_id}")
            self.assertTrue(target_answer.is_visible())
        finally:
            page.close()

    def test_06_threaded_comments_ui_interactions(self) -> None:
        """
        Verifies Reddit geometry connectors, single collapse toggle, parent jump,
        drilldown windowing, and mobile viewport zero horizontal scroll (Issue #27).
        """
        page = self.browser.new_page()
        try:
            # 1. Login user to create deep comments chain
            page.goto(f"{self.base_url}/feed.html", wait_until="domcontentloaded")
            page.evaluate("""async () => {
                await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({userId: 'user_tree_tester', name: 'Дерево Тестер', role: 'user'})
                });
            }""")

            # Build a 6-level comment chain via API
            chain_ids = page.evaluate("""async () => {
                const ids = [];
                let parentId = null;
                for (let lvl = 0; lvl <= 6; lvl++) {
                    const payload = {
                        content: 'Уровень вложенности ' + lvl,
                        commentType: 'comment'
                    };
                    if (parentId) {
                        payload.parentCommentId = parentId;
                    }
                    const res = await fetch('/api/articles/art_smoke_01/comments', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(payload)
                    });
                    const data = await res.json();
                    if (data && data.comment) {
                        ids.push(data.comment.id);
                        parentId = data.comment.id;
                    }
                }
                return ids;
            }""")
            self.assertEqual(len(chain_ids), 7, "Failed to seed 7-level comment chain")

            # 2. Open article page
            page.goto(f"{self.base_url}/article.html?id=art_smoke_01", wait_until="domcontentloaded")
            page.wait_for_selector(".comment-item", timeout=10000)

            # 3. Verify Single collapse button (.btn-toggle-thread) with +/- on root comment
            toggle_btns = page.locator(".btn-toggle-thread")
            self.assertGreaterEqual(toggle_btns.count(), 1, "Expected .btn-toggle-thread in DOM")
            first_toggle = toggle_btns.first
            toggle_icon = first_toggle.locator(".thread-toggle-icon")
            self.assertTrue(toggle_icon.is_visible(), "Expected .thread-toggle-icon in collapse button")
            self.assertEqual((toggle_icon.text_content() or "").strip(), "+")

            # Click to expand first level and verify switch to '-'
            first_toggle.click()
            page.wait_for_selector(".comment-child-node", state="visible", timeout=5000)
            self.assertEqual((toggle_icon.text_content() or "").strip(), "-")

            # 4. Verify absence of .btn-jump-to-parent and .comment-in-reply-to
            self.assertEqual(
                page.locator(".btn-jump-to-parent").count(),
                0,
                "Button .btn-jump-to-parent must be completely removed"
            )
            self.assertEqual(
                page.locator(".comment-in-reply-to").count(),
                0,
                "Label .comment-in-reply-to must not be present"
            )

            # 5. Verify Reddit continuous geometry: .comment-branch-elbow, .comment-stem-upper, .thread-toggle-icon
            elbows = page.locator(".comment-branch-elbow")
            self.assertGreaterEqual(elbows.count(), 1, "Expected .comment-branch-elbow on child nodes")
            self.assertTrue(elbows.first.is_visible(), "Expected .comment-branch-elbow to be visible")

            stem_uppers = page.locator(".comment-stem-upper")
            self.assertGreaterEqual(stem_uppers.count(), 1, "Expected .comment-stem-upper on parent node with children")

            # Verify centering of toggle icon on avatar axis (x = 15px)
            is_toggle_centered = page.evaluate("""() => {
                const icon = document.querySelector('.thread-toggle-icon');
                if (!icon) return false;
                const style = window.getComputedStyle(icon);
                return style.marginLeft === '7px' && style.marginRight === '17px';
            }""")
            self.assertTrue(is_toggle_centered, "Toggle icon must be centered on x=15px avatar axis")

            # Verify full path highlight (.is-tree-path-active) on elbow hover
            elbows.first.hover()
            page.wait_for_timeout(100)
            active_paths_count = page.locator(".is-tree-path-active").count()
            self.assertGreaterEqual(active_paths_count, 1, "Expected .is-tree-path-active elements on hover")
            page.mouse.move(0, 0)

            # 6. Sequentially expand intermediate levels down to depth >= 5 for drilldown windowing
            for _ in range(6):
                continue_btn = page.locator(".btn-continue-thread").first
                if continue_btn.count() > 0 and continue_btn.is_visible():
                    break
                unexpanded_toggles = page.locator(".btn-toggle-thread[aria-expanded='false']")
                clicked = False
                for i in range(unexpanded_toggles.count()):
                    cand = unexpanded_toggles.nth(i)
                    if cand.is_visible():
                        cand.click()
                        page.wait_for_timeout(200)
                        clicked = True
                        break
                if not clicked:
                    break

            continue_btns = page.locator(".btn-continue-thread")
            self.assertGreaterEqual(continue_btns.count(), 1, "Expected .btn-continue-thread at depth >= 5")
            self.assertTrue(continue_btns.first.is_visible(), "Expected .btn-continue-thread to be visible")
            continue_text = continue_btns.first.text_content() or ""
            self.assertIn("Продолжить ветку", continue_text)

            # Click continue thread to enter drilldown window
            continue_btns.first.click()
            page.wait_for_selector(".thread-drilldown-bar", timeout=5000)
            drilldown_bar = page.locator(".thread-drilldown-bar")
            self.assertTrue(drilldown_bar.is_visible(), "Expected .thread-drilldown-bar to appear on drilldown")

            back_btn = page.locator(".btn-drilldown-back")
            self.assertTrue(back_btn.is_visible(), "Expected .btn-drilldown-back in drilldown bar")
            self.assertIn("Назад", back_btn.text_content() or "")

            # Click back to return to main tree
            back_btn.click()
            page.wait_for_function(
                "document.querySelectorAll('.thread-drilldown-bar').length === 0",
                timeout=5000
            )

            # 7. Mobile responsive viewport (360px) and zero horizontal scroll
            page.set_viewport_size({"width": 360, "height": 640})
            page.wait_for_timeout(300)
            is_no_horizontal_scroll = page.evaluate("""() => {
                const docScrollOk = document.documentElement.scrollWidth <= window.innerWidth + 2;
                const commentsList = document.getElementById('commentsList');
                const listScrollOk = !commentsList || (commentsList.scrollWidth <= document.documentElement.clientWidth + 2);
                let childrenScrollOk = true;
                document.querySelectorAll('.comment-thread-children').forEach(el => {
                    if (el.scrollWidth > document.documentElement.clientWidth + 2) {
                        childrenScrollOk = false;
                    }
                });
                return docScrollOk && listScrollOk && childrenScrollOk;
            }""")
            self.assertTrue(
                is_no_horizontal_scroll,
                "Horizontal scroll detected on 360px viewport"
            )
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
