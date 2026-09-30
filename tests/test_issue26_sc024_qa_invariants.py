#!/usr/bin/env python3
"""
tests/test_issue26_sc024_qa_invariants.py

Integration and invariant test suite for Issue #26 (SC-024.3):
"Миграционная диагностика, интеграционные проверки инвариантов и E2E сценарий Q&A в CI".

Covers:
1. Migration diagnostic dry-run verification (scripts/migration_diagnostic.py):
   - Clean database execution (exit code 0, clean report).
   - Duplicate active answers per user on questions.
   - Multiple accepted solutions per question.
   - Solution flags on non-answers.
   - Answers on non-question materials.
   - Orphaned discussion replies (missing parent, non-published, non-answer, cross-article).
   - Mismatched counters across publications and profiles.
   - CLI flags (--json, --verbose, non-existent DB handling, path masking).
2. Domain & transaction invariant verifications:
   - Atomic solution switching.
   - Counter isolation (comments vs answers).
   - Prevention of duplicate answers (409 ANSWER_ALREADY_EXISTS).
   - Optimistic concurrency locking during answer edits (409 CONCURRENCY_CONFLICT).
"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

import server
from scripts.migration_diagnostic import mask_path, run_diagnostic
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
DIAGNOSTIC_SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "migration_diagnostic.py")


class TestMigrationDiagnosticUnitAndCLI(unittest.TestCase):
    """Test suite for scripts/migration_diagnostic.py execution and collision detection."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_diagnostic.db")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_clean_qa_db(self) -> None:
        """Initializes a valid clean database with standard question, answers, and comments."""
        conn = init_db(self.db_path, seed=False)
        with conn:
            # 1. Author profile
            conn.execute("""
                INSERT INTO user_profiles (
                    user_id, name, specialization, company, bio, avatar, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "author_alice", "Алиса Экспертова", "Auditor", "SecurityCorp",
                "Bio", "", "2026-09-30T10:00:00Z", "2026-09-30T10:00:00Z"
            ))

            # 2. Approved question
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "quest_diag_01", "draft_diag_01", "Вопрос по оптимизации газа", "author_alice",
                json.dumps({
                    "materialType": "question",
                    "topics": ["solidity"],
                    "questionStatus": "unsolved"
                }, ensure_ascii=False),
                "<p>Как оптимизировать циклы?</p>",
                "idemp_diag_01", "hash_diag_01",
                "2026-09-30T10:00:00Z", "2026-09-30T10:00:00Z"
            ))

            # 3. Approved article
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "art_diag_01", "draft_diag_02", "Статья об инвариантах", "author_alice",
                json.dumps({
                    "materialType": "article",
                    "topics": ["security"]
                }, ensure_ascii=False),
                "<p>Тело статьи об инвариантах.</p>",
                "idemp_diag_02", "hash_diag_02",
                "2026-09-30T10:00:00Z", "2026-09-30T10:00:00Z"
            ))

            # 4. Clarification comment to question
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar, content, status,
                    comment_type, is_solution, parent_answer_id, updated_at, revision, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'comment', 0, NULL, NULL, 1, ?)
            """, (
                "comm_diag_01", "quest_diag_01", "user_bob", "Боб", "",
                "Уточнение к вопросу: под какую версию EVM?", "2026-09-30T10:10:00Z"
            ))

            # 5. Answer to question
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar, content, status,
                    comment_type, is_solution, parent_answer_id, updated_at, revision, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'answer', 0, NULL, NULL, 1, ?)
            """, (
                "ans_diag_01", "quest_diag_01", "user_carol", "Кэрол", "",
                "Используйте unchecked для инкремента счетчика в циклах.", "2026-09-30T10:20:00Z"
            ))

            # 6. Reply to answer
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar, content, status,
                    comment_type, is_solution, parent_answer_id, updated_at, revision, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'comment', 0, ?, NULL, 1, ?)
            """, (
                "reply_diag_01", "quest_diag_01", "user_dave", "Дейв", "",
                "Полностью согласен, это экономит газ.", "ans_diag_01", "2026-09-30T10:30:00Z"
            ))
        conn.close()

    def test_01_clean_database_returns_code_zero(self) -> None:
        """Verify diagnostic returns code 0 and clean summary on a valid database."""
        self._create_clean_qa_db()

        res = run_diagnostic(self.db_path, verbose=True)
        self.assertTrue(res["clean"])
        self.assertEqual(res["violations_count"], 0)
        for key, val in res["summary"].items():
            self.assertEqual(val, 0, f"Expected 0 violations for {key}, got {val}")

        # Test CLI execution
        cmd = [sys.executable, DIAGNOSTIC_SCRIPT, "--db", self.db_path]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"CLI stderr: {proc.stderr}")
        self.assertIn("Status: CLEAN", proc.stdout)
        self.assertIn("Total Violations: 0", proc.stdout)

    def test_02_detects_duplicate_active_answers(self) -> None:
        """Verify detection of multiple active answers per user on the same question."""
        self._create_clean_qa_db()
        conn = sqlite3.connect(self.db_path)
        with conn:
            # Drop partial unique index to simulate legacy database state prior to unique constraint
            conn.execute("DROP INDEX IF EXISTS idx_unique_active_user_answer;")
            # Insert second published answer from same user (user_carol)
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar, content, status,
                    comment_type, is_solution, parent_answer_id, updated_at, revision, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'answer', 0, NULL, NULL, 1, ?)
            """, (
                "ans_diag_dup_02", "quest_diag_01", "user_carol", "Кэрол", "",
                "Второй ответ от того же пользователя.", "2026-09-30T10:40:00Z"
            ))
        conn.close()

        res = run_diagnostic(self.db_path)
        self.assertFalse(res["clean"])
        self.assertGreaterEqual(res["summary"]["duplicate_answers"], 1)

        # CLI execution
        cmd = [sys.executable, DIAGNOSTIC_SCRIPT, "--db", self.db_path, "--verbose"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Status: VIOLATIONS DETECTED", proc.stdout)
        self.assertIn("duplicate_answers", proc.stdout)
        self.assertIn("quest_diag_01", proc.stdout)

    def test_03_detects_multiple_solutions_per_question(self) -> None:
        """Verify detection of more than one accepted solution per question."""
        self._create_clean_qa_db()
        conn = sqlite3.connect(self.db_path)
        with conn:
            # Mark existing answer as solution
            conn.execute("UPDATE article_comments SET is_solution = 1 WHERE id = 'ans_diag_01'")

            # Insert another answer also marked as solution
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar, content, status,
                    comment_type, is_solution, parent_answer_id, updated_at, revision, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'answer', 1, NULL, NULL, 1, ?)
            """, (
                "ans_diag_sol_02", "quest_diag_01", "user_other", "Другой", "",
                "Второй принятый ответ.", "2026-09-30T10:45:00Z"
            ))
        conn.close()

        res = run_diagnostic(self.db_path)
        self.assertFalse(res["clean"])
        self.assertGreaterEqual(res["summary"]["multiple_solutions"], 1)

        cmd = [sys.executable, DIAGNOSTIC_SCRIPT, "--db", self.db_path, "--json"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        parsed = json.loads(proc.stdout)
        self.assertFalse(parsed["clean"])
        self.assertGreaterEqual(parsed["summary"]["multiple_solutions"], 1)

    def test_04_detects_solution_flags_on_non_answers(self) -> None:
        """Verify detection of is_solution = 1 on comments or non-answers."""
        self._create_clean_qa_db()
        conn = sqlite3.connect(self.db_path)
        with conn:
            # Mark regular comment as solution
            conn.execute("UPDATE article_comments SET is_solution = 1 WHERE id = 'comm_diag_01'")
        conn.close()

        res = run_diagnostic(self.db_path)
        self.assertFalse(res["clean"])
        self.assertGreaterEqual(res["summary"]["invalid_solutions"], 1)

        cmd = [sys.executable, DIAGNOSTIC_SCRIPT, "--db", self.db_path]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Solution flags on non-answers: 1", proc.stdout)

    def test_05_detects_answers_on_non_question_materials(self) -> None:
        """Verify detection of comment_type = 'answer' attached to articles."""
        self._create_clean_qa_db()
        conn = sqlite3.connect(self.db_path)
        with conn:
            # Attach answer to standard article (art_diag_01)
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar, content, status,
                    comment_type, is_solution, parent_answer_id, updated_at, revision, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'answer', 0, NULL, NULL, 1, ?)
            """, (
                "ans_wrong_material", "art_diag_01", "user_eva", "Ева", "",
                "Ответ к обычной статье, а не к вопросу.", "2026-09-30T10:50:00Z"
            ))
        conn.close()

        res = run_diagnostic(self.db_path)
        self.assertFalse(res["clean"])
        self.assertGreaterEqual(res["summary"]["answers_on_non_questions"], 1)

        cmd = [sys.executable, DIAGNOSTIC_SCRIPT, "--db", self.db_path, "--verbose"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("answers_on_non_questions", proc.stdout)
        self.assertIn("art_diag_01", proc.stdout)

    def test_06_detects_orphaned_replies(self) -> None:
        """Verify detection of orphaned replies with missing, deleted, or cross-article parents."""
        self._create_clean_qa_db()
        conn = sqlite3.connect(self.db_path)
        with conn:
            # Case A: missing parent
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar, content, status,
                    comment_type, is_solution, parent_answer_id, updated_at, revision, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'comment', 0, 'ans_non_existent', NULL, 1, ?)
            """, (
                "orphan_missing_parent", "quest_diag_01", "user_frank", "Франк", "",
                "Реплика с несуществующим родителем.", "2026-09-30T10:55:00Z"
            ))

            # Case B: parent is not an answer (parent is a question clarification comment)
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar, content, status,
                    comment_type, is_solution, parent_answer_id, updated_at, revision, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'comment', 0, 'comm_diag_01', NULL, 1, ?)
            """, (
                "orphan_comment_parent", "quest_diag_01", "user_frank", "Франк", "",
                "Реплика на комментарий вместо ответа.", "2026-09-30T10:56:00Z"
            ))

            # Case C: parent belongs to another article
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar, content, status,
                    comment_type, is_solution, parent_answer_id, updated_at, revision, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'comment', 0, 'ans_diag_01', NULL, 1, ?)
            """, (
                "orphan_cross_article", "art_diag_01", "user_frank", "Франк", "",
                "Реплика на ответ из другого вопроса.", "2026-09-30T10:57:00Z"
            ))
        conn.close()

        res = run_diagnostic(self.db_path)
        self.assertFalse(res["clean"])
        self.assertGreaterEqual(res["summary"]["orphaned_replies"], 3)

        cmd = [sys.executable, DIAGNOSTIC_SCRIPT, "--db", self.db_path, "--json"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        parsed = json.loads(proc.stdout)
        self.assertGreaterEqual(parsed["summary"]["orphaned_replies"], 3)

    def test_07_detects_mismatched_counters(self) -> None:
        """Verify detection of inconsistencies between cached settings/counters and actual records."""
        self._create_clean_qa_db()
        conn = sqlite3.connect(self.db_path)
        with conn:
            # Set corrupted questionStatus = 'solved' when 0 solutions exist
            conn.execute("""
                UPDATE moderation_submissions
                SET publication_settings = ?
                WHERE id = 'quest_diag_01'
            """, (
                json.dumps({
                    "materialType": "question",
                    "topics": ["solidity"],
                    "questionStatus": "solved",
                    "answersCount": 99
                }, ensure_ascii=False),
            ))
        conn.close()

        res = run_diagnostic(self.db_path)
        self.assertFalse(res["clean"])
        self.assertGreaterEqual(res["summary"]["mismatched_counters"], 1)

    def test_08_cli_non_existent_db_and_path_masking(self) -> None:
        """Verify CLI handles non-existent file with code 1 and masks paths."""
        non_existent = os.path.join(self.temp_dir, "missing.db")
        cmd = [sys.executable, DIAGNOSTIC_SCRIPT, "--db", non_existent]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)

        # Verify no machine absolute path like /home/ appears in output
        self.assertNotIn("/home/", proc.stdout)
        self.assertIn("<DB_PATH>/missing.db", proc.stdout)


class TestQADomainAndTransactionInvariants(unittest.TestCase):
    """Verifies transactional domain invariants: solution switching, isolation, concurrency."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_invariants.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        with conn:
            # Question Author
            conn.execute("""
                INSERT INTO user_profiles (
                    user_id, name, specialization, company, bio, avatar, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "q_author", "Автор Вопроса", "Lead", "Lab", "", "",
                "2026-09-30T10:00:00Z", "2026-09-30T10:00:00Z"
            ))

            # Responders
            for uid, name in [("user_ans_1", "Отвечающий 1"), ("user_ans_2", "Отвечающий 2")]:
                conn.execute("""
                    INSERT INTO user_profiles (
                        user_id, name, specialization, company, bio, avatar, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (uid, name, "Dev", "Co", "", "", "2026-09-30T10:00:00Z", "2026-09-30T10:00:00Z"))

            # Seed question
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "quest_inv_01", "draft_inv_01", "Инварианты Q&A", "q_author",
                json.dumps({"materialType": "question", "topics": ["testing"]}, ensure_ascii=False),
                "<p>Проверка инвариантов системы.</p>",
                "idemp_inv_01", "hash_inv_01",
                "2026-09-30T10:00:00Z", "2026-09-30T10:00:00Z"
            ))
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass
        if hasattr(cls, "server_thread") and cls.server_thread:
            cls.server_thread.join(timeout=2)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _login(self, user_id: str, name: str = "User") -> str:
        url = f"{self.base_url}/api/auth/login"
        body = json.dumps({"userId": user_id, "name": name, "role": "user"}).encode("utf-8")
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            return resp.headers.get("Set-Cookie", "")

    def _post_json(self, path: str, data: dict, cookie: Optional[str] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            with e:
                res_body = e.read().decode("utf-8")
                return e.code, json.loads(res_body) if res_body else {}

    def _put_json(self, path: str, data: dict, cookie: Optional[str] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, data=body, headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            with e:
                res_body = e.read().decode("utf-8")
                return e.code, json.loads(res_body) if res_body else {}

    def _get_json(self, path: str, cookie: Optional[str] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            with e:
                res_body = e.read().decode("utf-8")
                return e.code, json.loads(res_body) if res_body else {}

    def test_01_atomic_solution_switching(self) -> None:
        """Verify atomic switching of solutions ensures strictly <= 1 solution per question."""
        cookie_author = self._login("q_author", "Автор Вопроса")
        cookie_ans1 = self._login("user_ans_1", "Отвечающий 1")
        cookie_ans2 = self._login("user_ans_2", "Отвечающий 2")

        # User 1 posts answer 1
        st1, d1 = self._post_json(
            "/api/articles/quest_inv_01/comments",
            {"content": "Первое решение проблемы через библиотеку SafeMath.", "commentType": "answer"},
            cookie=cookie_ans1
        )
        self.assertEqual(st1, 201)
        ans1_id = d1["comment"]["id"]

        # User 2 posts answer 2
        st2, d2 = self._post_json(
            "/api/articles/quest_inv_01/comments",
            {"content": "Второе решение проблемы через встроенный overflow check 0.8.", "commentType": "answer"},
            cookie=cookie_ans2
        )
        self.assertEqual(st2, 201)
        ans2_id = d2["comment"]["id"]

        # Author marks answer 1 as solution
        st_sol1, d_sol1 = self._post_json(
            f"/api/articles/quest_inv_01/comments/{ans1_id}/solution",
            {"isSolution": True},
            cookie=cookie_author
        )
        self.assertEqual(st_sol1, 200)
        self.assertTrue(d_sol1.get("isSolution"))

        # Verify in DB: ans1 is solution, ans2 is not
        st_get1, d_get1 = self._get_json("/api/articles/quest_inv_01/comments")
        self.assertEqual(st_get1, 200)
        self.assertTrue(d_get1["hasSolution"])
        self.assertEqual(d_get1["solutionCommentId"], ans1_id)

        # Author marks answer 2 as solution: answer 1 must atomically become 0
        st_sol2, d_sol2 = self._post_json(
            f"/api/articles/quest_inv_01/comments/{ans2_id}/solution",
            {"isSolution": True},
            cookie=cookie_author
        )
        self.assertEqual(st_sol2, 200)
        self.assertTrue(d_sol2.get("isSolution"))

        # Verify DB directly: exactly one solution exists
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT id, is_solution FROM article_comments WHERE article_id = 'quest_inv_01' AND is_solution = 1")
        active_solutions = cur.fetchall()
        conn.close()

        self.assertEqual(len(active_solutions), 1)
        self.assertEqual(active_solutions[0][0], ans2_id)

        # Run diagnostic to ensure clean invariant state
        diag = run_diagnostic(self.db_path)
        self.assertEqual(diag["summary"]["multiple_solutions"], 0)

    def test_02_counter_isolation_clarifications_vs_answers(self) -> None:
        """Verify clarifications (comments) do not increment answersCount."""
        cookie = self._login("user_guest", "Гость")

        # Initial answersCount
        _, initial_data = self._get_json("/api/articles/quest_inv_01/comments")
        initial_answers = initial_data["answersCount"]
        initial_clarifications = initial_data["questionCommentsCount"]

        # Post question clarification
        st, _ = self._post_json(
            "/api/articles/quest_inv_01/comments",
            {"content": "Уточните компилятор solc.", "commentType": "comment"},
            cookie=cookie
        )
        self.assertEqual(st, 201)

        # After clarification: questionCommentsCount incremented, answersCount untouched
        _, post_data = self._get_json("/api/articles/quest_inv_01/comments")
        self.assertEqual(post_data["answersCount"], initial_answers)
        self.assertEqual(post_data["questionCommentsCount"], initial_clarifications + 1)

    def test_03_duplicate_answer_prevention_409(self) -> None:
        """Verify 1 answer per user per question invariant with 409 Conflict."""
        cookie_ans1 = self._login("user_ans_1", "Отвечающий 1")

        # Second answer attempt by same user
        st, data = self._post_json(
            "/api/articles/quest_inv_01/comments",
            {"content": "Попытка отправить второй ответ от того же пользователя.", "commentType": "answer"},
            cookie=cookie_ans1
        )
        self.assertEqual(st, 409)
        self.assertEqual(data.get("code"), "ANSWER_ALREADY_EXISTS")
        self.assertTrue(data.get("myAnswerId"))

    def test_04_optimistic_concurrency_locking(self) -> None:
        """Verify revision conflict during concurrent answer editing returns 409 CONCURRENCY_CONFLICT."""
        cookie_ans1 = self._login("user_ans_1", "Отвечающий 1")

        # Fetch existing answer ID
        _, get_data = self._get_json("/api/articles/quest_inv_01/comments", cookie=cookie_ans1)
        my_ans_id = get_data["myAnswerId"]

        # 1. Successful update from revision 1 -> revision becomes 2
        st_up1, d_up1 = self._put_json(
            f"/api/articles/quest_inv_01/comments/{my_ans_id}",
            {"content": "Обновленное содержимое ответа первой сессией.", "revision": 1},
            cookie=cookie_ans1
        )
        self.assertEqual(st_up1, 200)
        self.assertEqual(d_up1["comment"]["revision"], 2)

        # 2. Conflicting update with stale revision 1 -> 409 Conflict
        st_up2, d_up2 = self._put_json(
            f"/api/articles/quest_inv_01/comments/{my_ans_id}",
            {"content": "Конфликтующее обновление из второй сессии.", "revision": 1},
            cookie=cookie_ans1
        )
        self.assertEqual(st_up2, 409)
        self.assertEqual(d_up2.get("code"), "CONCURRENCY_CONFLICT")
        self.assertEqual(d_up2.get("currentRevision"), 2)


if __name__ == "__main__":
    unittest.main()
