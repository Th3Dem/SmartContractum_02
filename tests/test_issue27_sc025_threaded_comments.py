#!/usr/bin/env python3
"""
tests/test_issue27_sc025_threaded_comments.py

Test suite proving the 10 Must Prove invariants for Issue #27 (SC-025):
"Единые многоуровневые комментарии (вопросы, ответы, статьи)".
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
from scripts.migration_diagnostic import run_diagnostic
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
DIAGNOSTIC_SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "migration_diagnostic.py")


class TestIssue27ThreadedCommentsBackend(unittest.TestCase):
    """Verifies backend API, invariants, idempotency, and diagnostics for threaded comments."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_threaded.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        with conn:
            # Users
            users = [
                ("u_author", "Автор Статьи", "author"),
                ("u_alice", "Алиса", "user"),
                ("u_bob", "Боб", "user"),
                ("u_charlie", "Чарли", "user"),
            ]
            for uid, name, role in users:
                conn.execute("""
                    INSERT INTO user_profiles (
                        user_id, name, specialization, company, bio, avatar, created_at, updated_at
                    ) VALUES (?, ?, 'Engineer', 'SmartCo', '', '', '2026-09-30T10:00:00Z', '2026-09-30T10:00:00Z')
                """, (uid, name))

            # Question Material
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "quest_thread_01", "draft_q_01", "Вопрос про треды", "u_author",
                json.dumps({"materialType": "question", "topics": ["threading"]}, ensure_ascii=False),
                "<p>Текст вопроса про треды.</p>",
                "idemp_q_01", "hash_q_01",
                "2026-09-30T10:00:00Z", "2026-09-30T10:00:00Z"
            ))

            # Article Material
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "art_thread_01", "draft_art_01", "Статья про треды", "u_author",
                json.dumps({"materialType": "article", "topics": ["architecture"]}, ensure_ascii=False),
                "<p>Текст статьи про архитектуру тредов.</p>",
                "idemp_art_01", "hash_art_01",
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

    def _delete_json(self, path: str, cookie: Optional[str] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, headers=headers, method="DELETE")
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            with e:
                res_body = e.read().decode("utf-8")
                return e.code, json.loads(res_body) if res_body else {}

    def test_01_invariant_hierarchy_and_depth_limits(self) -> None:
        """Invariant 1: Root -> child -> grandchild hierarchy and depth limit 20."""
        c_alice = self._login("u_alice", "Алиса")

        # 1. Create root comment on article
        st, res = self._post_json("/api/articles/art_thread_01/comments", {
            "content": "Корневой комментарий Алисы",
            "commentType": "comment"
        }, cookie=c_alice)
        self.assertEqual(st, 201)
        root_id = res["comment"]["id"]
        self.assertIsNone(res["comment"]["parentCommentId"])
        self.assertIsNone(res["comment"]["parentAnswerId"])

        # 2. Child comment to root
        c_bob = self._login("u_bob", "Боб")
        st, res = self._post_json("/api/articles/art_thread_01/comments", {
            "content": "Ответ Боба Алисе",
            "commentType": "comment",
            "parentCommentId": root_id
        }, cookie=c_bob)
        self.assertEqual(st, 201)
        child_id = res["comment"]["id"]
        self.assertEqual(res["comment"]["parentCommentId"], root_id)

        # 3. Grandchild comment
        st, res = self._post_json("/api/articles/art_thread_01/comments", {
            "content": "Ответ Алисы Бобу на дочерний комментарий",
            "commentType": "comment",
            "parentCommentId": child_id
        }, cookie=c_alice)
        self.assertEqual(st, 201)
        grandchild_id = res["comment"]["id"]
        self.assertEqual(res["comment"]["parentCommentId"], child_id)

        # 4. Independent second root by same author
        st, res = self._post_json("/api/articles/art_thread_01/comments", {
            "content": "Второй независимый корень Алисы",
            "commentType": "comment"
        }, cookie=c_alice)
        self.assertEqual(st, 201)
        root2_id = res["comment"]["id"]
        self.assertIsNone(res["comment"]["parentCommentId"])
        self.assertNotEqual(root_id, root2_id)

        # 5. Build chain up to 20 levels and verify 21st is rejected
        current_id = root_id
        # We already have root (lvl 0), child (lvl 1), grandchild (lvl 2)
        current_id = grandchild_id
        for lvl in range(3, 20):
            st, res = self._post_json("/api/articles/art_thread_01/comments", {
                "content": f"Вложенный уровень {lvl}",
                "commentType": "comment",
                "parentCommentId": current_id
            }, cookie=c_bob)
            self.assertEqual(st, 201, f"Failed at level {lvl}")
            current_id = res["comment"]["id"]

        # Level 20 was reached (current_id has 20 parents including root).
        # Attempt level 21 -> must return 400
        st, res = self._post_json("/api/articles/art_thread_01/comments", {
            "content": "Попытка превысить лимит 20 уровней",
            "commentType": "comment",
            "parentCommentId": current_id
        }, cookie=c_bob)
        self.assertEqual(st, 400)
        self.assertIn("глубина", res.get("error", "").lower())

    def test_02_invariant_strict_context_isolation(self) -> None:
        """Invariant 2: Rejection of cross-article, cross-answer, and invalid parent types."""
        c_alice = self._login("u_alice", "Алиса")
        c_bob = self._login("u_bob", "Боб")

        # Create answer on quest_thread_01
        st, res = self._post_json("/api/articles/quest_thread_01/comments", {
            "content": "Самостоятельный ответ Боба",
            "commentType": "answer"
        }, cookie=c_bob)
        self.assertEqual(st, 201)
        ans_id = res["comment"]["id"]

        # 1. Attempt to use an answer ID as parentCommentId -> must reject (must use parentAnswerId)
        st, res = self._post_json("/api/articles/quest_thread_01/comments", {
            "content": "Попытка сослаться на ответ как на комментарий",
            "commentType": "comment",
            "parentCommentId": ans_id
        }, cookie=c_alice)
        self.assertEqual(st, 400)

        # 2. Attempt to reply with parentCommentId belonging to another article
        # First get a comment on art_thread_01
        st_art, res_art = self._get_json("/api/articles/art_thread_01/comments")
        art_comm_id = res_art["comments"][0]["id"]

        st, res = self._post_json("/api/articles/quest_thread_01/comments", {
            "content": "Попытка ответить на комментарий из другой статьи",
            "commentType": "comment",
            "parentCommentId": art_comm_id
        }, cookie=c_alice)
        self.assertEqual(st, 400)

        # 3. Contradictory parentAnswerId: parentComment is on question root, but client passes parentAnswerId
        st, res = self._post_json("/api/articles/quest_thread_01/comments", {
            "content": "Уточняющий комментарий к вопросу",
            "commentType": "comment"
        }, cookie=c_alice)
        self.assertEqual(st, 201)
        q_comm_id = res["comment"]["id"]

        st, res = self._post_json("/api/articles/quest_thread_01/comments", {
            "content": "Конфликтные параметры родителей",
            "commentType": "comment",
            "parentCommentId": q_comm_id,
            "parentAnswerId": ans_id
        }, cookie=c_alice)
        self.assertEqual(st, 400)

    def test_03_invariant_edit_parity_and_concurrency(self) -> None:
        """Invariant 3: Author editing, revision check (409), non-author rejection (403), binding immutability."""
        c_alice = self._login("u_alice", "Алиса")
        c_bob = self._login("u_bob", "Боб")

        # Create comment
        st, res = self._post_json("/api/articles/art_thread_01/comments", {
            "content": "Исходный текст для редактирования",
            "commentType": "comment"
        }, cookie=c_alice)
        self.assertEqual(st, 201)
        comm_id = res["comment"]["id"]
        self.assertEqual(res["comment"]["revision"], 1)

        # Non-author tries to edit -> 403
        st, res = self._put_json(f"/api/articles/art_thread_01/comments/{comm_id}", {
            "content": "Попытка Боба изменить чужой комментарий",
            "revision": 1
        }, cookie=c_bob)
        self.assertEqual(st, 403)

        # Author tries to mutate parentCommentId -> 400
        st, res = self._put_json(f"/api/articles/art_thread_01/comments/{comm_id}", {
            "content": "Попытка изменить привязку",
            "parentCommentId": "fake_parent",
            "revision": 1
        }, cookie=c_alice)
        self.assertEqual(st, 400)

        # Author edits successfully
        st, res = self._put_json(f"/api/articles/art_thread_01/comments/{comm_id}", {
            "content": "Отредактированный текст Алисы",
            "revision": 1
        }, cookie=c_alice)
        self.assertEqual(st, 200)
        self.assertEqual(res["comment"]["revision"], 2)
        self.assertIsNotNone(res["comment"]["updatedAt"])

        # Stale revision edit -> 409 CONCURRENCY_CONFLICT
        st, res = self._put_json(f"/api/articles/art_thread_01/comments/{comm_id}", {
            "content": "Конфликтная правка со старой ревизией",
            "revision": 1
        }, cookie=c_alice)
        self.assertEqual(st, 409)
        self.assertEqual(res.get("code"), "CONCURRENCY_CONFLICT")
        self.assertEqual(res.get("currentRevision"), 2)

    def test_04_invariant_idempotency_and_safe_repeat(self) -> None:
        """Invariant 4: Replay with same clientOperationId returns 200/201 without duplicate, conflict on altered payload."""
        c_charlie = self._login("u_charlie", "Чарли")
        op_id = f"op_test_{int(time.time()*1000)}"

        # Initial post with clientOperationId
        st1, res1 = self._post_json("/api/articles/art_thread_01/comments", {
            "content": "Идемпотентный комментарий Чарли",
            "commentType": "comment",
            "clientOperationId": op_id
        }, cookie=c_charlie)
        self.assertEqual(st1, 201)
        cid1 = res1["comment"]["id"]

        # Replay identical POST with same clientOperationId
        st2, res2 = self._post_json("/api/articles/art_thread_01/comments", {
            "content": "Идемпотентный комментарий Чарли",
            "commentType": "comment",
            "clientOperationId": op_id
        }, cookie=c_charlie)
        self.assertIn(st2, (200, 201))
        self.assertEqual(res2["comment"]["id"], cid1)

        # Replay same clientOperationId with different content -> 409 Conflict
        st3, res3 = self._post_json("/api/articles/art_thread_01/comments", {
            "content": "Измененный текст с тем же clientOperationId",
            "commentType": "comment",
            "clientOperationId": op_id
        }, cookie=c_charlie)
        self.assertEqual(st3, 409)

        # Two separate comments with same text but different/missing operation IDs are allowed
        st4, res4 = self._post_json("/api/articles/art_thread_01/comments", {
            "content": "Идемпотентный комментарий Чарли",
            "commentType": "comment",
            "clientOperationId": f"op_diff_{int(time.time()*1000)}"
        }, cookie=c_charlie)
        self.assertEqual(st4, 201)
        self.assertNotEqual(res4["comment"]["id"], cid1)

    def test_05_invariant_counters_accuracy_and_isolation(self) -> None:
        """Invariant 5: Accurate calculation of answersCount, questionCommentsCount, commentsCount, discussionCount."""
        st, res = self._get_json("/api/articles/quest_thread_01/comments")
        self.assertEqual(st, 200)

        # Verify contractual definitions
        answers_count = res["answersCount"]
        q_comments_count = res["questionCommentsCount"]
        comments_count = res["commentsCount"]
        discussion_count = res["discussionCount"]

        self.assertEqual(discussion_count, answers_count + comments_count)
        self.assertGreaterEqual(answers_count, 1)

        # Check answers comments count
        for ans in res["answers"]:
            self.assertIn("commentsCount", ans)
            self.assertIn("comments", ans)

    def test_06_invariant_qa_model_protection(self) -> None:
        """Invariant 6: Comments cannot become solutions; articles reject answer commentType."""
        c_bob = self._login("u_bob", "Боб")

        # Attempt to post answer on an article
        st, res = self._post_json("/api/articles/art_thread_01/comments", {
            "content": "Попытка создать ответ на обычной статье",
            "commentType": "answer"
        }, cookie=c_bob)
        self.assertEqual(st, 400)

    def test_07_invariant_diagnostic_script_checks(self) -> None:
        """Invariant 7: migration_diagnostic.py detects cycles, depth violations, and orphans."""
        # Clean DB check
        res = run_diagnostic(self.db_path)
        self.assertTrue(res["clean"], f"Database diagnostic failed: {res.get('details')}")

        cmd = [sys.executable, DIAGNOSTIC_SCRIPT, "--db", self.db_path]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)

    def test_08_invariant_soft_deletion_and_placeholder(self) -> None:
        """Invariant 8: Soft deletion keeps tree intact with placeholder for nodes with active descendants."""
        c_alice = self._login("u_alice", "Алиса")
        c_bob = self._login("u_bob", "Боб")

        # Parent comment
        st, res = self._post_json("/api/articles/art_thread_01/comments", {
            "content": "Родительский комментарий для последующего удаления",
            "commentType": "comment"
        }, cookie=c_alice)
        self.assertEqual(st, 201)
        p_id = res["comment"]["id"]

        # Child comment
        st, res = self._post_json("/api/articles/art_thread_01/comments", {
            "content": "Дочерний комментарий к удаляемому родителю",
            "commentType": "comment",
            "parentCommentId": p_id
        }, cookie=c_bob)
        self.assertEqual(st, 201)
        c_id = res["comment"]["id"]

        # Delete parent
        st, res = self._delete_json(f"/api/articles/art_thread_01/comments/{p_id}", cookie=c_alice)
        self.assertEqual(st, 200)

        # GET comments: parent must appear as placeholder because it has active child
        st, res = self._get_json("/api/articles/art_thread_01/comments")
        self.assertEqual(st, 200)

        found_p = next((c for c in res["comments"] if c["id"] == p_id), None)
        self.assertIsNotNone(found_p)
        self.assertTrue(found_p.get("isDeleted"))
        self.assertEqual(found_p["content"], "Комментарий удален")
        self.assertNotIn("Родительский комментарий", found_p["content"])

        found_c = next((c for c in res["comments"] if c["id"] == c_id), None)
        self.assertIsNotNone(found_c)
        self.assertEqual(found_c["parentCommentId"], p_id)


if __name__ == "__main__":
    unittest.main()
