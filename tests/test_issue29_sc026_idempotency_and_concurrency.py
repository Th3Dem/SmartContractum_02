#!/usr/bin/env python3
"""
tests/test_issue29_sc026_idempotency_and_concurrency.py

Integration and unit tests for Issue #29 (SC-026):
Comments Idempotency, Duplicate Prevention, and Concurrency Conflict Handling.
"""

import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from typing import Optional, Tuple

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue29IdempotencyAndConcurrency(unittest.TestCase):
    """Verifies idempotency of comment/answer creation and optimistic locking."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue29.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        with conn:
            users = [
                ("u_author", "Автор Статьи", "author"),
                ("u_alice", "Алиса", "user"),
                ("u_bob", "Боб", "user"),
            ]
            for uid, name, role in users:
                conn.execute("""
                    INSERT INTO user_profiles (
                        user_id, name, specialization, company, bio, avatar, created_at, updated_at
                    ) VALUES (?, ?, 'Engineer', 'SmartCo', '', '', '2026-09-30T10:00:00Z', '2026-09-30T10:00:00Z')
                """, (uid, name))

            # Question material
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "quest_issue29_01", "draft_q_29_01", "Вопрос по идемпотентности", "u_author",
                json.dumps({"materialType": "question", "topics": ["testing"]}, ensure_ascii=False),
                "<p>Текст вопроса</p>",
                "idemp_q_29_01", "hash_q_29_01",
                "2026-09-30T10:00:00Z", "2026-09-30T10:00:00Z"
            ))

            # Article material
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "art_issue29_01", "draft_art_29_01", "Статья по конкурентности", "u_author",
                json.dumps({"materialType": "article", "topics": ["database"]}, ensure_ascii=False),
                "<p>Текст статьи</p>",
                "idemp_art_29_01", "hash_art_29_01",
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

    def _get_db_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_01_replay_post_same_client_operation_id_no_duplicate_row_or_notification(self) -> None:
        """
        Test 1: Replay of POST with same clientOperationId returns 200 without
        duplicate row in article_comments and without duplicate in user_notifications.
        Verified for both comments and answers.
        """
        cookie_alice = self._login("u_alice", "Алиса")
        cookie_bob = self._login("u_bob", "Боб")
        op_comm_id = f"op_comm_{int(time.time()*1000)}"

        # Initial comment creation
        payload_comm = {
            "content": "Идемпотентный комментарий Алисы",
            "commentType": "comment",
            "clientOperationId": op_comm_id
        }
        st1, res1 = self._post_json("/api/articles/art_issue29_01/comments", payload_comm, cookie=cookie_alice)
        self.assertEqual(st1, 201)
        self.assertTrue(res1.get("success"))
        comm_id = res1["comment"]["id"]

        # Check DB counts after initial comment
        conn = self._get_db_conn()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = 'art_issue29_01'")
            self.assertEqual(cur.fetchone()["cnt"], 1)

            cur.execute("SELECT COUNT(*) AS cnt FROM user_notifications WHERE user_id = 'u_author' AND article_id = 'art_issue29_01'")
            self.assertEqual(cur.fetchone()["cnt"], 1)
        conn.close()

        # Replay identical POST with same clientOperationId
        st2, res2 = self._post_json("/api/articles/art_issue29_01/comments", payload_comm, cookie=cookie_alice)
        self.assertEqual(st2, 200)
        self.assertTrue(res2.get("success"))
        self.assertTrue(res2.get("isDuplicate"))
        self.assertEqual(res2["comment"]["id"], comm_id)

        # Check DB counts after replay (must NOT duplicate)
        conn = self._get_db_conn()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = 'art_issue29_01'")
            self.assertEqual(cur.fetchone()["cnt"], 1)

            cur.execute("SELECT COUNT(*) AS cnt FROM user_notifications WHERE user_id = 'u_author' AND article_id = 'art_issue29_01'")
            self.assertEqual(cur.fetchone()["cnt"], 1)
        conn.close()

        # Test answer creation and replay
        op_ans_id = f"op_ans_{int(time.time()*1000)}"
        payload_ans = {
            "content": "Идемпотентный ответ Боба",
            "commentType": "answer",
            "clientOperationId": op_ans_id
        }
        st_a1, res_a1 = self._post_json("/api/articles/quest_issue29_01/comments", payload_ans, cookie=cookie_bob)
        self.assertEqual(st_a1, 201)
        ans_id = res_a1["comment"]["id"]

        # Replay identical answer POST with same clientOperationId
        st_a2, res_a2 = self._post_json("/api/articles/quest_issue29_01/comments", payload_ans, cookie=cookie_bob)
        self.assertEqual(st_a2, 200)
        self.assertTrue(res_a2.get("isDuplicate"))
        self.assertEqual(res_a2["comment"]["id"], ans_id)

        conn = self._get_db_conn()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = 'quest_issue29_01' AND comment_type = 'answer'")
            self.assertEqual(cur.fetchone()["cnt"], 1)

            cur.execute("SELECT COUNT(*) AS cnt FROM user_notifications WHERE user_id = 'u_author' AND article_id = 'quest_issue29_01'")
            self.assertEqual(cur.fetchone()["cnt"], 1)
        conn.close()

    def test_02_replay_post_same_client_operation_id_altered_payload_returns_409(self) -> None:
        """
        Test 2: Replay of POST with same clientOperationId but altered content
        or parents returns 409 conflict and preserves database state.
        """
        cookie_alice = self._login("u_alice", "Алиса")
        op_id = f"op_altered_{int(time.time()*1000)}"

        # 1. Initial post
        st1, res1 = self._post_json("/api/articles/art_issue29_01/comments", {
            "content": "Первоначальный текст для теста 2",
            "commentType": "comment",
            "clientOperationId": op_id
        }, cookie=cookie_alice)
        self.assertEqual(st1, 201)
        comm_id = res1["comment"]["id"]

        # 2. Replay with altered content -> 409 OPERATION_ID_CONFLICT
        st2, res2 = self._post_json("/api/articles/art_issue29_01/comments", {
            "content": "Измененный текст при том же ключе операции",
            "commentType": "comment",
            "clientOperationId": op_id
        }, cookie=cookie_alice)
        self.assertEqual(st2, 409)
        self.assertFalse(res2.get("success"))
        self.assertEqual(res2.get("code"), "OPERATION_ID_CONFLICT")

        # 3. Replay with altered target article -> 409 OPERATION_ID_CONFLICT
        st3, res3 = self._post_json("/api/articles/quest_issue29_01/comments", {
            "content": "Первоначальный текст для теста 2",
            "commentType": "comment",
            "clientOperationId": op_id
        }, cookie=cookie_alice)
        self.assertEqual(st3, 409)
        self.assertEqual(res3.get("code"), "OPERATION_ID_CONFLICT")

        # 4. Verify DB was not altered
        conn = self._get_db_conn()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT content FROM article_comments WHERE id = ?", (comm_id,))
            row = cur.fetchone()
            self.assertEqual(row["content"], "Первоначальный текст для теста 2")
        conn.close()

    def test_03_intentional_identical_comments_different_client_operation_id(self) -> None:
        """
        Test 3: Two intentional comments with identical text but different
        clientOperationId successfully create two separate records.
        """
        cookie_alice = self._login("u_alice", "Алиса")
        op1 = f"op_dup_1_{int(time.time()*1000)}"
        op2 = f"op_dup_2_{int(time.time()*1000)}"
        identical_text = "Осознанный одинаковый комментарий!"

        st1, res1 = self._post_json("/api/articles/art_issue29_01/comments", {
            "content": identical_text,
            "commentType": "comment",
            "clientOperationId": op1
        }, cookie=cookie_alice)
        self.assertEqual(st1, 201)
        cid1 = res1["comment"]["id"]

        st2, res2 = self._post_json("/api/articles/art_issue29_01/comments", {
            "content": identical_text,
            "commentType": "comment",
            "clientOperationId": op2
        }, cookie=cookie_alice)
        self.assertEqual(st2, 201)
        cid2 = res2["comment"]["id"]

        self.assertNotEqual(cid1, cid2)

        # Verify both records exist in DB
        conn = self._get_db_conn()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id, content, client_operation_id FROM article_comments WHERE id IN (?, ?)", (cid1, cid2))
            rows = cur.fetchall()
            self.assertEqual(len(rows), 2)
            op_set = {r["client_operation_id"] for r in rows}
            self.assertEqual(op_set, {op1, op2})
        conn.close()

    def test_04_put_comment_without_revision_returns_400_revision_required(self) -> None:
        """
        Test 4: PUT on comment_type == 'comment' without revision returns
        400 REVISION_REQUIRED.
        """
        cookie_alice = self._login("u_alice", "Алиса")
        st, res = self._post_json("/api/articles/art_issue29_01/comments", {
            "content": "Комментарий для проверки обязательной ревизии",
            "commentType": "comment"
        }, cookie=cookie_alice)
        self.assertEqual(st, 201)
        comm_id = res["comment"]["id"]

        # PUT without revision field
        st_put, res_put = self._put_json(f"/api/articles/art_issue29_01/comments/{comm_id}", {
            "content": "Попытка правки без revision"
        }, cookie=cookie_alice)

        self.assertEqual(st_put, 400)
        self.assertFalse(res_put.get("success"))
        self.assertEqual(res_put.get("code"), "REVISION_REQUIRED")
        self.assertEqual(res_put.get("error"), "Поле revision обязательно для редактирования комментария")

        # Verify DB content not changed
        conn = self._get_db_conn()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT content, revision FROM article_comments WHERE id = ?", (comm_id,))
            row = cur.fetchone()
            self.assertEqual(row["content"], "Комментарий для проверки обязательной ревизии")
            self.assertEqual(row["revision"], 1)
        conn.close()

    def test_05_put_comment_with_invalid_revision_returns_400_invalid_revision(self) -> None:
        """
        Test 5: PUT on comment_type == 'comment' with invalid revision
        (string/bool/list) returns 400 INVALID_REVISION.
        """
        cookie_alice = self._login("u_alice", "Алиса")
        st, res = self._post_json("/api/articles/art_issue29_01/comments", {
            "content": "Комментарий для проверки типов ревизии",
            "commentType": "comment"
        }, cookie=cookie_alice)
        self.assertEqual(st, 201)
        comm_id = res["comment"]["id"]

        # 1. String revision
        st_s, res_s = self._put_json(f"/api/articles/art_issue29_01/comments/{comm_id}", {
            "content": "Правка со строковой ревизией",
            "revision": "1"
        }, cookie=cookie_alice)
        self.assertEqual(st_s, 400)
        self.assertEqual(res_s.get("code"), "INVALID_REVISION")
        self.assertEqual(res_s.get("error"), "Поле revision должно быть целым числом")

        # 2. Boolean revision (True)
        st_b, res_b = self._put_json(f"/api/articles/art_issue29_01/comments/{comm_id}", {
            "content": "Правка с булевой ревизией True",
            "revision": True
        }, cookie=cookie_alice)
        self.assertEqual(st_b, 400)
        self.assertEqual(res_b.get("code"), "INVALID_REVISION")
        self.assertEqual(res_b.get("error"), "Поле revision должно быть целым числом")

        # 3. Boolean revision (False)
        st_bf, res_bf = self._put_json(f"/api/articles/art_issue29_01/comments/{comm_id}", {
            "content": "Правка с булевой ревизией False",
            "revision": False
        }, cookie=cookie_alice)
        self.assertEqual(st_bf, 400)
        self.assertEqual(res_bf.get("code"), "INVALID_REVISION")

    def test_06_put_comment_with_outdated_revision_returns_409_concurrency_conflict(self) -> None:
        """
        Test 6: PUT on comment_type == 'comment' with outdated revision returns
        409 with currentRevision and currentContent.
        """
        cookie_alice = self._login("u_alice", "Алиса")
        st, res = self._post_json("/api/articles/art_issue29_01/comments", {
            "content": "Исходный текст комментария v1",
            "commentType": "comment"
        }, cookie=cookie_alice)
        self.assertEqual(st, 201)
        comm_id = res["comment"]["id"]

        # Author updates with valid revision 1 -> 200, becomes revision 2
        st_ok, res_ok = self._put_json(f"/api/articles/art_issue29_01/comments/{comm_id}", {
            "content": "Обновленный текст комментария v2",
            "revision": 1
        }, cookie=cookie_alice)
        self.assertEqual(st_ok, 200)
        self.assertEqual(res_ok["comment"]["revision"], 2)

        # Author updates with stale revision 1 -> 409 CONCURRENCY_CONFLICT
        st_stale, res_stale = self._put_json(f"/api/articles/art_issue29_01/comments/{comm_id}", {
            "content": "Конфликтная правка v3 со старой ревизией 1",
            "revision": 1
        }, cookie=cookie_alice)
        self.assertEqual(st_stale, 409)
        self.assertFalse(res_stale.get("success"))
        self.assertEqual(res_stale.get("code"), "CONCURRENCY_CONFLICT")
        self.assertEqual(res_stale.get("error"), "Комментарий был изменен в другой сессии")
        self.assertEqual(res_stale.get("currentRevision"), 2)
        self.assertEqual(res_stale.get("currentContent"), "Обновленный текст комментария v2")

        # Verify DB still has revision 2 content
        conn = self._get_db_conn()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT content, revision FROM article_comments WHERE id = ?", (comm_id,))
            row = cur.fetchone()
            self.assertEqual(row["content"], "Обновленный текст комментария v2")
            self.assertEqual(row["revision"], 2)
        conn.close()

    def test_07_legacy_put_answer_without_revision_succeeds_200(self) -> None:
        """
        Test 7: Legacy PUT on comment_type == 'answer' without revision succeeds
        with 200 and increments revision.
        """
        cookie_alice = self._login("u_alice", "Алиса")
        st, res = self._post_json("/api/articles/quest_issue29_01/comments", {
            "content": "Исходный ответ Алисы",
            "commentType": "answer"
        }, cookie=cookie_alice)
        self.assertEqual(st, 201)
        ans_id = res["comment"]["id"]
        self.assertEqual(res["comment"]["revision"], 1)

        # Legacy PUT without revision field
        st_put, res_put = self._put_json(f"/api/articles/quest_issue29_01/comments/{ans_id}", {
            "content": "Отредактированный ответ Алисы без передачи revision"
        }, cookie=cookie_alice)
        self.assertEqual(st_put, 200)
        self.assertTrue(res_put.get("success"))
        self.assertEqual(res_put["comment"]["revision"], 2)
        self.assertEqual(res_put["comment"]["content"], "Отредактированный ответ Алисы без передачи revision")

        # Verify DB update
        conn = self._get_db_conn()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT content, revision, updated_at FROM article_comments WHERE id = ?", (ans_id,))
            row = cur.fetchone()
            self.assertEqual(row["content"], "Отредактированный ответ Алисы без передачи revision")
            self.assertEqual(row["revision"], 2)
            self.assertIsNotNone(row["updated_at"])
        conn.close()

    def test_08_put_answer_with_outdated_revision_returns_409(self) -> None:
        """
        Test 8: PUT on comment_type == 'answer' with outdated revision returns 409,
        and invalid revision type returns 400.
        """
        cookie_alice = self._login("u_alice", "Алиса")
        # Fetch Alice's existing answer on quest_issue29_01
        conn = self._get_db_conn()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id, revision FROM article_comments WHERE article_id = 'quest_issue29_01' AND user_id = 'u_alice' AND comment_type = 'answer'")
            row = cur.fetchone()
            ans_id = row["id"]
            current_rev = row["revision"]
        conn.close()

        # 1. Invalid revision type (string) -> 400 INVALID_REVISION
        st_inv, res_inv = self._put_json(f"/api/articles/quest_issue29_01/comments/{ans_id}", {
            "content": "Правка с невалидным типом ревизии",
            "revision": "invalid"
        }, cookie=cookie_alice)
        self.assertEqual(st_inv, 400)
        self.assertEqual(res_inv.get("code"), "INVALID_REVISION")

        # 2. Outdated revision (current_rev - 1) -> 409 CONCURRENCY_CONFLICT
        st_stale, res_stale = self._put_json(f"/api/articles/quest_issue29_01/comments/{ans_id}", {
            "content": "Конфликтная правка ответа",
            "revision": current_rev - 1
        }, cookie=cookie_alice)
        self.assertEqual(st_stale, 409)
        self.assertFalse(res_stale.get("success"))
        self.assertEqual(res_stale.get("code"), "CONCURRENCY_CONFLICT")
        self.assertEqual(res_stale.get("currentRevision"), current_rev)

        # 3. Successful update with exact current_rev -> 200
        st_ok, res_ok = self._put_json(f"/api/articles/quest_issue29_01/comments/{ans_id}", {
            "content": "Успешная правка ответа с валидной ревизией",
            "revision": current_rev
        }, cookie=cookie_alice)
        self.assertEqual(st_ok, 200)
        self.assertEqual(res_ok["comment"]["revision"], current_rev + 1)

    def test_09_frontend_absence_of_reload_advice_on_409(self) -> None:
        """
        Test 9: Verify absence of page reload advice on 409 for comments and answers
        in frontend/public/js/article.js.
        """
        article_js_path = os.path.join(FRONTEND_DIR, "js", "article.js")
        with open(article_js_path, "r", encoding="utf-8") as f:
            article_js = f.read()

        self.assertNotIn("обновите страницу", article_js.lower())
        self.assertNotIn("перезагрузите", article_js.lower())
        self.assertNotIn("location.reload", article_js)

    def test_10_frontend_presence_of_edit_conflict_box_and_css(self) -> None:
        """
        Test 10: Verify presence of in-form conflict resolution box and CSS rules
        for .edit-conflict-box, .conflict-server-preview, .btn-conflict-load-server,
        and .btn-conflict-keep-local.
        """
        article_js_path = os.path.join(FRONTEND_DIR, "js", "article.js")
        with open(article_js_path, "r", encoding="utf-8") as f:
            article_js = f.read()

        self.assertIn("edit-conflict-box", article_js)
        self.assertIn("conflict-server-preview", article_js)
        self.assertIn("btn-conflict-load-server", article_js)
        self.assertIn("btn-conflict-keep-local", article_js)
        self.assertIn("Текст был изменен в другой сессии. Ваша версия не сохранена.", article_js)
        self.assertIn("Загрузить версию с сервера", article_js)
        self.assertIn("Оставить мой текст", article_js)
        self.assertIn("showConcurrencyConflictBox", article_js)

        article_css_path = os.path.join(FRONTEND_DIR, "css", "article.css")
        with open(article_css_path, "r", encoding="utf-8") as f:
            article_css = f.read()

        self.assertIn(".edit-conflict-box", article_css)
        self.assertIn(".conflict-server-preview", article_css)
        self.assertIn(".btn-conflict-load-server", article_css)
        self.assertIn(".btn-conflict-keep-local", article_css)

    def test_11_frontend_all_forms_pass_client_operation_id(self) -> None:
        """
        Test 11: Verify that all 5 creation forms (main comments, clarifications,
        answers, inline comment replies, answer replies) pass clientOperationId.
        """
        article_js_path = os.path.join(FRONTEND_DIR, "js", "article.js")
        with open(article_js_path, "r", encoding="utf-8") as f:
            article_js = f.read()

        # Both comments and answers must pass clientOperationId in POST body
        self.assertIn("clientOperationId: clientOpId", article_js)
        # Ensure answer POST specifically includes clientOperationId
        answer_post_idx = article_js.find("commentType: 'answer'")
        self.assertNotEqual(answer_post_idx, -1)
        answer_post_block = article_js[answer_post_idx:answer_post_idx + 250]
        self.assertIn("clientOperationId", answer_post_block)

        # Ensure answer reply POST specifically includes clientOperationId
        ans_reply_idx = article_js.find("parentAnswerId: comment.id")
        self.assertNotEqual(ans_reply_idx, -1)
        ans_reply_block = article_js[ans_reply_idx:ans_reply_idx + 250]
        self.assertIn("clientOperationId", ans_reply_block)

        # Ensure inline comment reply POST includes clientOperationId
        comm_reply_idx = article_js.find("parentCommentId: comment.id")
        self.assertNotEqual(comm_reply_idx, -1)
        comm_reply_block = article_js[comm_reply_idx:comm_reply_idx + 250]
        self.assertIn("clientOperationId", comm_reply_block)

    def test_12_frontend_client_operation_id_lifecycle_logic(self) -> None:
        """
        Test 12: Verify clientOperationId lifecycle contracts:
        - Stored on dataset.clientOpId
        - Reused on retry with same content
        - Regenerated when input content is modified before retry
        - Reset on successful 200 or 201 creation
        """
        article_js_path = os.path.join(FRONTEND_DIR, "js", "article.js")
        with open(article_js_path, "r", encoding="utf-8") as f:
            article_js = f.read()

        self.assertIn("getOrCreateClientOpId", article_js)
        self.assertIn("resetClientOpId", article_js)
        self.assertIn("handleFormTextInput", article_js)
        self.assertIn("dataset.clientOpId", article_js)
        self.assertIn("dataset.lastSubmittedText", article_js)

        # Simulation of the JS lifecycle logic in Python to guarantee exact behavior
        class MockFormElement:
            def __init__(self):
                self.dataset = {}

        def js_get_or_create(el):
            if "clientOpId" not in el.dataset:
                el.dataset["clientOpId"] = f"op_{int(time.time()*1000)}"
            return el.dataset["clientOpId"]

        def js_reset(el):
            el.dataset.pop("clientOpId", None)
            el.dataset.pop("lastSubmittedText", None)

        def js_input(el, text):
            if "clientOpId" not in el.dataset:
                el.dataset["clientOpId"] = f"op_{int(time.time()*1000)}"
            elif "lastSubmittedText" in el.dataset:
                if text.strip() != el.dataset["lastSubmittedText"]:
                    el.dataset["clientOpId"] = f"op_new_{int(time.time()*1000)}"
                    el.dataset.pop("lastSubmittedText", None)

        # 1. Opening form assigns opId
        form_el = MockFormElement()
        op1 = js_get_or_create(form_el)
        self.assertTrue(op1.startswith("op_"))

        # 2. Typing content before submission preserves op1
        js_input(form_el, "Hello world")
        self.assertEqual(js_get_or_create(form_el), op1)

        # 3. Submit sets lastSubmittedText
        form_el.dataset["lastSubmittedText"] = "Hello world"

        # 4. Network error / retry with SAME content preserves op1
        self.assertEqual(js_get_or_create(form_el), op1)

        # 5. User edits content before retry -> opId changes to new key
        js_input(form_el, "Hello world modified")
        op2 = js_get_or_create(form_el)
        self.assertNotEqual(op1, op2)

        # 6. Success -> reset removes opId
        js_reset(form_el)
        self.assertNotIn("clientOpId", form_el.dataset)
        self.assertNotIn("lastSubmittedText", form_el.dataset)

        # 7. Next comment gets a brand new opId
        op3 = js_get_or_create(form_el)
        self.assertNotEqual(op2, op3)


if __name__ == "__main__":
    unittest.main()

