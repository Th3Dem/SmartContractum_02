#!/usr/bin/env python3
"""
Unit and Integration tests for task-11-publication-settings-and-moderation:
- Server database initialization and table schema
- /api/moderation/submit success flow (valid payload, immutable snapshot, SHA-256 hash)
- Validation failures:
  - empty title
  - empty body (whitespace, empty tags, &nbsp;, dividers, images only)
  - missing audience / invalid audience
  - empty topics, >5 topics, duplicate topics
  - 0 keywords, >10 keywords, keyword >60 chars, duplicate keywords
  - description <50 chars, description >500 chars
- Idempotency handling: duplicate requests with same idempotencyKey do not create duplicate rows
- Retrieval via /api/moderation/status and /api/moderation/list
- Keyword parsing and normalization logic (comma splitting, whitespace preservation inside, trimming, collapsing spaces, deduplication)
- Article text detection logic (empty tags, nbsp, dividers, images only rejected)
- Status transition checks (cannot transition once approved)
- Health check and static files serving
"""

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

import server
from server import (
    DEFAULT_DB_PATH,
    compute_snapshot_hash,
    create_server,
    extract_article_text,
    get_db_connection,
    has_valid_article_text,
    init_db,
    is_valid_id,
    normalize_keyword,
    parse_and_normalize_keywords,
    update_submission_status,
    validate_submission_payload,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend', 'public')


class TestDatabaseAndSchema(unittest.TestCase):
    """1. Tests for SQLite database initialization and table schema."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_moderation.db')

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_db_creates_table_and_indexes(self):
        """Ensure moderation_submissions table and indexes are created with proper columns and constraints."""
        conn = init_db(self.db_path)
        cur = conn.cursor()

        # Check table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='moderation_submissions';")
        self.assertIsNotNone(cur.fetchone(), "Table moderation_submissions must exist")

        # Check columns
        cur.execute("PRAGMA table_info(moderation_submissions);")
        columns = {row["name"]: row for row in cur.fetchall()}

        expected_columns = [
            "id", "draft_id", "title", "author_id", "status",
            "publication_settings", "article_html", "article_delta",
            "idempotency_key", "snapshot_hash", "created_at", "updated_at"
        ]
        for col in expected_columns:
            self.assertIn(col, columns, f"Column '{col}' must be present in moderation_submissions table")

        # id is primary key
        self.assertEqual(columns["id"]["pk"], 1)

        # Default values
        self.assertEqual(columns["author_id"]["dflt_value"], "'author_local'")
        self.assertEqual(columns["status"]["dflt_value"], "'pending_moderation'")

        # Check indexes exist
        cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='moderation_submissions';")
        indexes = {row["name"] for row in cur.fetchall()}
        self.assertIn("idx_moderation_draft_id", indexes)
        self.assertIn("idx_moderation_status", indexes)

        conn.close()

    def test_status_check_constraint(self):
        """Ensure check constraint rejects invalid statuses."""
        conn = init_db(self.db_path)
        with self.assertRaises(sqlite3.IntegrityError):
            with conn:
                conn.execute("""
                    INSERT INTO moderation_submissions (
                        id, draft_id, title, author_id, status, publication_settings,
                        article_html, snapshot_hash, created_at, updated_at
                    ) VALUES ('sub_test', 'draft_1', 'Title', 'author_local', 'invalid_status', '{}', 'Content', 'hash', '2026-09-26T00:00:00Z', '2026-09-26T00:00:00Z')
                """)
        conn.close()


class TestKeywordParsingAndNormalization(unittest.TestCase):
    """2. Tests for keyword parsing and normalization logic matching frontend requirements."""

    def test_comma_splitting(self):
        """Splitting comma-separated tags into distinct keyword items."""
        raw = "javascript, web development, quill editor"
        res = parse_and_normalize_keywords(raw)
        self.assertEqual(res, ["javascript", "web development", "quill editor"])

    def test_whitespace_preservation_inside_phrase(self):
        """Spaces inside multi-word phrases must be preserved."""
        raw = "безопасная сделка, оракулы, аудит кода"
        res = parse_and_normalize_keywords(raw)
        self.assertEqual(res, ["безопасная сделка", "оракулы", "аудит кода"])

    def test_outer_whitespace_trimming(self):
        """Leading and trailing spaces around tags must be trimmed."""
        raw = "   antigravity   ,   offline first   ,   wysiwyg   "
        res = parse_and_normalize_keywords(raw)
        self.assertEqual(res, ["antigravity", "offline first", "wysiwyg"])

    def test_collapsing_multiple_consecutive_spaces(self):
        """Multiple consecutive spaces inside tags must be collapsed to a single space."""
        raw = "machine    learning,   deep     neural   network"
        res = parse_and_normalize_keywords(raw)
        self.assertEqual(res, ["machine learning", "deep neural network"])

    def test_case_insensitive_deduplication(self):
        """Case-insensitive duplicates are ignored, keeping the first occurrence casing."""
        raw = "Python, python, PYTHON, Golang, goLang"
        res = parse_and_normalize_keywords(raw)
        self.assertEqual(res, ["Python", "Golang"])

    def test_filtering_empty_and_whitespace_only_tags(self):
        """Empty strings and commas without text are filtered out."""
        raw = ", ,  , tag1,  , , tag2,   ,"
        res = parse_and_normalize_keywords(raw)
        self.assertEqual(res, ["tag1", "tag2"])

    def test_list_input_support(self):
        """Input can be provided as a list with internal commas or single tags."""
        raw = ["tag1, tag2", "   tag3   ", "tag1", "tag4,   tag5  "]
        res = parse_and_normalize_keywords(raw)
        self.assertEqual(res, ["tag1", "tag2", "tag3", "tag4", "tag5"])


class TestArticleTextDetectionLogic(unittest.TestCase):
    """3. Tests for article text detection logic (rejecting empty tags, nbsp, dividers, and images only)."""

    def test_rejection_of_empty_and_whitespace_strings(self):
        """Empty or whitespace-only body is rejected."""
        self.assertFalse(has_valid_article_text(""))
        self.assertFalse(has_valid_article_text("     "))
        self.assertFalse(has_valid_article_text("\n\t  \r\n"))
        self.assertFalse(has_valid_article_text(None))

    def test_rejection_of_empty_html_tags(self):
        """Empty paragraphs, breaks, and spans are rejected."""
        self.assertFalse(has_valid_article_text("<p></p>"))
        self.assertFalse(has_valid_article_text("<p><br></p>"))
        self.assertFalse(has_valid_article_text("<div><span><p></p></span></div>"))

    def test_rejection_of_nbsp_and_invisible_characters(self):
        """Non-breaking spaces, zero-width spaces, and entities only are rejected."""
        self.assertFalse(has_valid_article_text("<p>&nbsp;</p>"))
        self.assertFalse(has_valid_article_text("<p>&nbsp;&nbsp;&nbsp;&#160;</p>"))
        self.assertFalse(has_valid_article_text("<p>\u00a0\u200b\ufeff</p>"))

    def test_rejection_of_dividers_only(self):
        """Dividers (<hr>) and divider containers without text are rejected."""
        self.assertFalse(has_valid_article_text("<hr>"))
        self.assertFalse(has_valid_article_text("<hr/><hr>"))
        self.assertFalse(has_valid_article_text("<div class='editor-divider'><hr></div>"))
        self.assertFalse(has_valid_article_text("<p>— — —</p>"))

    def test_rejection_of_images_only(self):
        """Images only, even with alt attributes, are rejected as article body text."""
        self.assertFalse(has_valid_article_text('<img src="data:image/png;base64,123" alt="Image">'))
        self.assertFalse(has_valid_article_text('<figure><img src="pic.jpg"></figure>'))
        self.assertFalse(has_valid_article_text('<p><img src="pic.jpg"></p><hr><p>&nbsp;</p>'))

    def test_acceptance_of_valid_text(self):
        """Text containing latin or cyrillic alphanumeric characters is accepted."""
        self.assertTrue(has_valid_article_text("<p>Hello world!</p>"))
        self.assertTrue(has_valid_article_text("<p>Привет, мир публикации!</p>"))
        self.assertTrue(has_valid_article_text("<h1>Раздел 1. Архитектура</h1>"))
        self.assertTrue(has_valid_article_text("<p><img src='cat.jpg'> Котик на фотографии</p>"))


class TestValidationFailures(unittest.TestCase):
    """4. Tests for validation failures on publication settings and article payload."""

    def setUp(self):
        self.valid_payload = {
            "draftId": "draft_001",
            "title": "Правильная статья с полными настройками",
            "html": "<p>Это полноценный текст статьи, содержащий больше чем достаточно полезной информации.</p>",
            "delta": {"ops": [{"insert": "Текст"}]},
            "publicationSettings": {
                "targetAudience": "developers",
                "topics": ["development", "qa"],
                "keywords": ["разработка", "тестирование"],
                "description": "Краткое описание статьи длиной более пятидесяти символов для ленты публикаций.",
                "format": "tutorial",
                "complexity": "medium"
            },
            "idempotencyKey": "key_valid_1",
            "authorId": "author_local"
        }

    def test_empty_title_failure(self):
        """Empty or whitespace title must fail validation."""
        p1 = dict(self.valid_payload, title="")
        ok, err, field_errors = validate_submission_payload(p1)
        self.assertFalse(ok)
        self.assertIn("title", field_errors)

        p2 = dict(self.valid_payload, title="    ")
        ok, err, field_errors = validate_submission_payload(p2)
        self.assertFalse(ok)
        self.assertIn("title", field_errors)

    def test_empty_body_failure(self):
        """Empty body, whitespace, empty tags or images only must fail validation."""
        cases = [
            "",
            "   ",
            "<p><br></p>",
            "<p>&nbsp;</p>",
            "<hr>",
            "<img src='photo.png' alt='Photo'>"
        ]
        for html_val in cases:
            p = dict(self.valid_payload, html=html_val)
            ok, err, field_errors = validate_submission_payload(p)
            self.assertFalse(ok, f"Expected failure for body: {html_val}")
            self.assertIn("html", field_errors)

    def test_missing_and_invalid_audience_failure(self):
        """Missing or invalid target audience must fail validation."""
        # Missing
        pub_settings = dict(self.valid_payload["publicationSettings"])
        del pub_settings["targetAudience"]
        p = dict(self.valid_payload, publicationSettings=pub_settings)
        ok, err, field_errors = validate_submission_payload(p)
        self.assertFalse(ok)
        self.assertIn("targetAudience", field_errors)

        # Invalid ID characters
        pub_settings["targetAudience"] = "invalid audience! <>"
        p = dict(self.valid_payload, publicationSettings=pub_settings)
        ok, err, field_errors = validate_submission_payload(p)
        self.assertFalse(ok)
        self.assertIn("targetAudience", field_errors)

    def test_empty_topics_failure(self):
        """Empty topics array must fail validation."""
        pub_settings = dict(self.valid_payload["publicationSettings"], topics=[])
        p = dict(self.valid_payload, publicationSettings=pub_settings)
        ok, err, field_errors = validate_submission_payload(p)
        self.assertFalse(ok)
        self.assertIn("topics", field_errors)

    def test_more_than_five_topics_failure(self):
        """>5 topics must fail validation."""
        pub_settings = dict(self.valid_payload["publicationSettings"], topics=["t1", "t2", "t3", "t4", "t5", "t6"])
        p = dict(self.valid_payload, publicationSettings=pub_settings)
        ok, err, field_errors = validate_submission_payload(p)
        self.assertFalse(ok)
        self.assertIn("topics", field_errors)

    def test_zero_keywords_failure(self):
        """0 keywords must fail validation."""
        pub_settings = dict(self.valid_payload["publicationSettings"], keywords=[])
        p = dict(self.valid_payload, publicationSettings=pub_settings)
        ok, err, field_errors = validate_submission_payload(p)
        self.assertFalse(ok)
        self.assertIn("keywords", field_errors)

    def test_more_than_ten_keywords_failure(self):
        """>10 keywords must fail validation."""
        kws = [f"kw_{i}" for i in range(11)]
        pub_settings = dict(self.valid_payload["publicationSettings"], keywords=kws)
        p = dict(self.valid_payload, publicationSettings=pub_settings)
        ok, err, field_errors = validate_submission_payload(p)
        self.assertFalse(ok)
        self.assertIn("keywords", field_errors)

    def test_keyword_longer_than_sixty_chars_failure(self):
        """Keyword exceeding 60 characters must fail validation."""
        kws = ["a" * 61]
        pub_settings = dict(self.valid_payload["publicationSettings"], keywords=kws)
        p = dict(self.valid_payload, publicationSettings=pub_settings)
        ok, err, field_errors = validate_submission_payload(p)
        self.assertFalse(ok)
        self.assertIn("keywords", field_errors)

    def test_description_length_bounds_failure(self):
        """Description < 50 chars or > 500 chars must fail validation."""
        # < 50 chars
        pub_settings_short = dict(self.valid_payload["publicationSettings"], description="Слишком короткое описание (менее 50 символов).")
        p_short = dict(self.valid_payload, publicationSettings=pub_settings_short)
        ok, err, field_errors = validate_submission_payload(p_short)
        self.assertFalse(ok)
        self.assertIn("description", field_errors)

        # > 500 chars
        pub_settings_long = dict(self.valid_payload["publicationSettings"], description="A" * 501)
        p_long = dict(self.valid_payload, publicationSettings=pub_settings_long)
        ok, err, field_errors = validate_submission_payload(p_long)
        self.assertFalse(ok)
        self.assertIn("description", field_errors)

    def test_duplicate_keywords_case_insensitive_failure(self):
        """Duplicate keywords (case-insensitive) must fail validation."""
        pub_settings = dict(self.valid_payload["publicationSettings"], keywords=["Python", "python"])
        p = dict(self.valid_payload, publicationSettings=pub_settings)
        ok, err, field_errors = validate_submission_payload(p)
        self.assertFalse(ok)
        self.assertIn("keywords", field_errors)


class TestModerationServerIntegration(unittest.TestCase):
    """5. End-to-end integration tests with live HTTP server and SQLite database."""

    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, 'integration_moderation.db')

        # Create server on random available port
        cls.server = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.05)  # brief startup wait

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _post_json(self, path: str, data: dict):
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                resp_body = resp.read().decode("utf-8")
                return resp.status, json.loads(resp_body)
        except urllib.error.HTTPError as e:
            resp_body = e.read().decode("utf-8")
            e.close()
            return e.code, json.loads(resp_body)

    def _get_json(self, path: str):
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                resp_body = resp.read().decode("utf-8")
                return resp.status, json.loads(resp_body)
        except urllib.error.HTTPError as e:
            resp_body = e.read().decode("utf-8")
            e.close()
            return e.code, json.loads(resp_body)

    def test_health_check_endpoint(self):
        """GET /api/health returns ok status."""
        status_code, data = self._get_json("/api/health")
        self.assertEqual(status_code, 200)
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("server"), "Antigravity Moderation Server")

    def test_submit_success_flow_and_snapshot_hash(self):
        """POST /api/moderation/submit creates immutable record with valid SHA-256 snapshot hash."""
        payload = {
            "draftId": "draft_success_001",
            "title": "Как устроена модерация в Antigravity Writer",
            "html": "<p>Подробный разбор архитектуры очереди модерации на базе SQLite и ThreadingHTTPServer.</p>",
            "delta": {"ops": [{"insert": "Подробный разбор архитектуры..."}]},
            "publicationSettings": {
                "targetAudience": "developers",
                "topics": ["development", "security"],
                "keywords": ["python", "sqlite", "модерация"],
                "description": "Подробный разбор архитектуры очереди модерации на базе SQLite и ThreadingHTTPServer для Antigravity Writer.",
                "format": "article",
                "complexity": "medium"
            },
            "idempotencyKey": "idemp_succ_001",
            "authorId": "author_ivan"
        }

        status_code, data = self._post_json("/api/moderation/submit", payload)
        self.assertEqual(status_code, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("status"), "pending_moderation")

        submission_id = data.get("submissionId")
        self.assertTrue(submission_id.startswith("sub_"))

        # Verify snapshot hash matches SHA-256 calculation
        expected_hash = compute_snapshot_hash(
            payload["title"],
            payload["html"],
            payload["publicationSettings"]
        )
        self.assertEqual(data.get("snapshotHash"), expected_hash)

        # Verify SQLite row
        conn = get_db_connection(self.db_path)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM moderation_submissions WHERE id = ?", (submission_id,))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["draft_id"], "draft_success_001")
            self.assertEqual(row["title"], "Как устроена модерация в Antigravity Writer")
            self.assertEqual(row["author_id"], "author_ivan")
            self.assertEqual(row["status"], "pending_moderation")
            self.assertEqual(row["idempotency_key"], "idemp_succ_001")
            self.assertEqual(row["snapshot_hash"], expected_hash)
            self.assertEqual(row["article_html"], payload["html"])

            saved_settings = json.loads(row["publication_settings"])
            self.assertEqual(saved_settings["targetAudience"], "developers")
        conn.close()

    def test_idempotency_handling_no_duplicates(self):
        """Submitting multiple requests with identical idempotencyKey does not create duplicate rows."""
        payload = {
            "draftId": "draft_idemp_002",
            "title": "Идемпотентная публикация статьи",
            "html": "<p>Проверка защиты от повторных кликов и дубликатов в очереди модерации.</p>",
            "delta": None,
            "publicationSettings": {
                "targetAudience": "qa",
                "topics": ["qa"],
                "keywords": ["idempotency", "test"],
                "description": "Проверка защиты от повторных кликов и дубликатов в очереди модерации Antigravity Writer.",
                "format": "case",
                "complexity": "easy"
            },
            "idempotencyKey": "unique_key_12345",
            "authorId": "author_qa"
        }

        # First request
        status1, data1 = self._post_json("/api/moderation/submit", payload)
        self.assertEqual(status1, 200)
        self.assertTrue(data1.get("success"))
        sub_id_1 = data1.get("submissionId")
        self.assertFalse(data1.get("isDuplicate", False))

        # Second request with same idempotencyKey
        status2, data2 = self._post_json("/api/moderation/submit", payload)
        self.assertEqual(status2, 200)
        self.assertTrue(data2.get("success"))
        self.assertEqual(data2.get("submissionId"), sub_id_1)
        self.assertTrue(data2.get("isDuplicate"))

        # Verify DB has only 1 row with this key
        conn = get_db_connection(self.db_path)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM moderation_submissions WHERE idempotency_key = ?", ("unique_key_12345",))
            count = cur.fetchone()["cnt"]
            self.assertEqual(count, 1, "There must be exactly one row for a unique idempotency key")
        conn.close()

    def test_status_retrieval_endpoint(self):
        """GET /api/moderation/status?draftId=... returns submission status."""
        draft_id = "draft_status_isolated_001"
        payload = {
            "draftId": draft_id,
            "title": "Тестовая статья для проверки статуса",
            "html": "<p>Содержимое тестовой статьи для проверки статуса модерации в Antigravity.</p>",
            "publicationSettings": {
                "targetAudience": "developers",
                "topics": ["development"],
                "keywords": ["status", "check"],
                "description": "Содержимое тестовой статьи для проверки статуса модерации в Antigravity длиной более 50 символов.",
            },
            "idempotencyKey": "status_isolated_key_001",
            "authorId": "author_isolated"
        }
        post_status, post_data = self._post_json("/api/moderation/submit", payload)
        self.assertEqual(post_status, 200)

        # 1. Existing draft
        status_code, data = self._get_json(f"/api/moderation/status?draftId={draft_id}")
        self.assertEqual(status_code, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("status"), "pending_moderation")
        self.assertEqual(data.get("submissionId"), post_data["submissionId"])

        # 2. Non-existent draft
        status_code_404, data_404 = self._get_json("/api/moderation/status?draftId=non_existent_draft_999")
        self.assertEqual(status_code_404, 404)
        self.assertEqual(data_404.get("status"), "draft")
        self.assertIsNone(data_404.get("submissionId"))

        # 3. Missing draftId param
        status_code_400, data_400 = self._get_json("/api/moderation/status")
        self.assertEqual(status_code_400, 400)
        self.assertFalse(data_400.get("success"))

    def test_list_retrieval_endpoint(self):
        """GET /api/moderation/list returns submissions queue."""
        draft_id = "draft_list_isolated_002"
        payload = {
            "draftId": draft_id,
            "title": "Тестовая статья для списка модерации",
            "html": "<p>Содержимое тестовой статьи для проверки очереди модерации в Antigravity.</p>",
            "publicationSettings": {
                "targetAudience": "qa",
                "topics": ["qa"],
                "keywords": ["queue", "list"],
                "description": "Содержимое тестовой статьи для проверки очереди модерации в Antigravity длиной более 50 символов.",
            },
            "idempotencyKey": "list_isolated_key_002",
        }
        self._post_json("/api/moderation/submit", payload)

        status_code, data = self._get_json("/api/moderation/list")
        self.assertEqual(status_code, 200)
        self.assertTrue(data.get("success"))
        self.assertIsInstance(data.get("submissions"), list)
        self.assertGreaterEqual(len(data.get("submissions")), 1)

        # Check item structure
        first = data["submissions"][0]
        self.assertIn("id", first)
        self.assertIn("draftId", first)
        self.assertIn("title", first)
        self.assertIn("status", first)
        self.assertIn("publicationSettings", first)
        self.assertIn("snapshotHash", first)
        self.assertIsInstance(first["publicationSettings"], dict)

    def test_status_transition_rejection_after_approval(self):
        """Cannot submit draft to moderation if it is already approved."""
        draft_id = "draft_transition_check"
        payload = {
            "draftId": draft_id,
            "title": "Статья перед одобрением",
            "html": "<p>Текст для проверки невозможности повторной отправки после одобрения модератором.</p>",
            "publicationSettings": {
                "targetAudience": "all",
                "topics": ["career"],
                "keywords": ["transition", "status"],
                "description": "Текст для проверки невозможности повторной отправки после одобрения модератором.",
            },
            "idempotencyKey": "trans_key_1",
            "authorId": "author_test"
        }

        # 1. Initial submission
        status1, data1 = self._post_json("/api/moderation/submit", payload)
        self.assertEqual(status1, 200)
        sub_id = data1["submissionId"]

        # 2. Moderator approves submission in DB
        updated = update_submission_status(sub_id, "approved", self.db_path)
        self.assertTrue(updated)

        # 3. Attempt to submit again with different idempotency key
        payload2 = dict(payload, idempotencyKey="trans_key_2")
        status2, data2 = self._post_json("/api/moderation/submit", payload2)
        self.assertEqual(status2, 400)
        self.assertFalse(data2["success"])
        self.assertIn("уже одобрен", data2["error"])

    def test_static_file_serving(self):
        """Static files from frontend/public are served correctly via GET."""
        # 1. editor.html
        url_editor = f"{self.base_url}/editor.html"
        req = urllib.request.Request(url_editor, method="GET")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("Antigravity Writer", content)

        # 2. index.html
        url_index = f"{self.base_url}/index.html"
        req = urllib.request.Request(url_index, method="GET")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("<!DOCTYPE html>", content)

        # 3. Non-existent static file -> 404
        url_not_found = f"{self.base_url}/non_existent_file_abc123.xyz"
        req = urllib.request.Request(url_not_found, method="GET")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 404)
        ctx.exception.close()

    def test_options_cors_preflight(self):
        """OPTIONS request receives 204 with CORS headers."""
        url = f"{self.base_url}/api/moderation/submit"
        req = urllib.request.Request(url, method="OPTIONS")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 204)
            self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")
            self.assertIn("POST", resp.headers.get("Access-Control-Allow-Methods", ""))


if __name__ == "__main__":
    unittest.main()
