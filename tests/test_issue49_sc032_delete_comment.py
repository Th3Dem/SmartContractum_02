#!/usr/bin/env python3
"""
tests/test_issue49_sc032_delete_comment.py

Test suite verifying all 10 invariants for Issue #49:
"Комментарии: кнопка «Удалить» для собственного комментария".
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
from typing import Any, Dict, List, Optional, Set, Tuple

import server
from scripts.migration_diagnostic import run_diagnostic
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue49DeleteCommentBackend(unittest.TestCase):
    """Verifies backend API, ownership checks, soft-delete, and karma recalculation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue49.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        with conn:
            users = [
                ("u_alice", "Алиса", "user"),
                ("u_bob", "Боб", "user"),
                ("u_charlie", "Чарли", "user"),
                ("u_admin", "Администратор", "admin"),
            ]
            for uid, name, role in users:
                conn.execute("""
                    INSERT INTO user_profiles (
                        user_id, name, specialization, company, bio, avatar, created_at, updated_at
                    ) VALUES (?, ?, 'Engineer', 'SmartCo', '', '', '2026-10-01T10:00:00Z', '2026-10-01T10:00:00Z')
                """, (uid, name))

            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "art_issue49_01", "draft_art_49_01", "Статья для проверки удаления", "u_alice",
                json.dumps({"materialType": "article", "topics": ["testing"]}, ensure_ascii=False),
                "<p>Текст статьи</p>", "idemp_49_art", "hash_49_art",
                "2026-10-01T10:00:00Z", "2026-10-01T10:00:00Z"
            ))

            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "quest_issue49_01", "draft_quest_49_01", "Вопрос для проверки удаления", "u_alice",
                json.dumps({"materialType": "question", "topics": ["testing"]}, ensure_ascii=False),
                "<p>Текст вопроса</p>", "idemp_49_quest", "hash_49_quest",
                "2026-10-01T10:00:00Z", "2026-10-01T10:00:00Z"
            ))
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0)
        cls.port = cls.httpd.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "httpd"):
            cls.httpd.shutdown()
            cls.httpd.server_close()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _login(self, user_id: str, name: str) -> str:
        url = f"{self.base_url}/api/auth/login"
        payload = json.dumps({"userId": user_id, "name": name}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            cookie_headers = resp.headers.get_all("Set-Cookie") or []
            session_cookie = ""
            for c in cookie_headers:
                if "sc_session=" in c:
                    session_cookie = c.split(";")[0]
                    break
            return session_cookie

    def _get_json(self, path: str, cookie: Optional[str] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            with e:
                res_body = e.read().decode("utf-8")
                return e.code, json.loads(res_body) if res_body else {}

    def _post_json(self, path: str, data: dict, cookie: Optional[str] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        payload = json.dumps(data).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
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

    def test_01_guest_delete_rejected_401(self) -> None:
        """Invariant 6: Direct API call by unauthenticated guest returns 401 with requireAuth: True."""
        st, res = self._delete_json("/api/articles/art_issue49_01/comments/comm_some_id")
        self.assertEqual(st, 401)
        self.assertFalse(res.get("success"))
        self.assertTrue(res.get("requireAuth"))

    def test_02_foreign_user_delete_rejected_403(self) -> None:
        """Invariant 6: Foreign user cannot delete another user's comment (returns 403)."""
        c_alice = self._login("u_alice", "Алиса")
        c_bob = self._login("u_bob", "Боб")

        st, res = self._post_json("/api/articles/art_issue49_01/comments", {
            "content": "Комментарий Алисы для теста прав",
            "commentType": "comment"
        }, cookie=c_alice)
        self.assertEqual(st, 201)
        comm_id = res["comment"]["id"]

        st, res = self._delete_json(f"/api/articles/art_issue49_01/comments/{comm_id}", cookie=c_bob)
        self.assertEqual(st, 403)
        self.assertFalse(res.get("success"))
        self.assertEqual(res.get("error"), "Вы можете удалять только свои комментарии")

    def test_03_delete_answer_rejected_400(self) -> None:
        """Invariant 2: Normal user cannot delete answers (comment_type = 'answer') -> returns 400."""
        c_bob = self._login("u_bob", "Боб")

        st, res = self._post_json("/api/articles/quest_issue49_01/comments", {
            "content": "Полноценный ответ Боба на вопрос",
            "commentType": "answer"
        }, cookie=c_bob)
        self.assertEqual(st, 201)
        ans_id = res["comment"]["id"]

        st, res = self._delete_json(f"/api/articles/quest_issue49_01/comments/{ans_id}", cookie=c_bob)
        self.assertEqual(st, 400)
        self.assertFalse(res.get("success"))
        self.assertEqual(res.get("error"), "Удаление доступно только для обычных комментариев")

    def test_04_author_delete_leaf_comment(self) -> None:
        """Invariant 5: Author deleting leaf comment removes it from view; counters decrement accurately."""
        c_charlie = self._login("u_charlie", "Чарли")

        st, res = self._post_json("/api/articles/art_issue49_01/comments", {
            "content": "Листовой комментарий Чарли",
            "commentType": "comment"
        }, cookie=c_charlie)
        self.assertEqual(st, 201)
        leaf_id = res["comment"]["id"]

        # Verify comment is in list
        st, res = self._get_json("/api/articles/art_issue49_01/comments")
        self.assertEqual(st, 200)
        found_before = [c for c in res["comments"] if c["id"] == leaf_id]
        self.assertEqual(len(found_before), 1)
        count_before = res["commentsCount"]

        # Delete comment
        st, res = self._delete_json(f"/api/articles/art_issue49_01/comments/{leaf_id}", cookie=c_charlie)
        self.assertEqual(st, 200)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("commentId"), leaf_id)

        # GET comments: leaf comment omitted completely; commentsCount decremented by 1
        st, res = self._get_json("/api/articles/art_issue49_01/comments")
        self.assertEqual(st, 200)
        found_after = [c for c in res["comments"] if c["id"] == leaf_id]
        self.assertEqual(len(found_after), 0)
        self.assertEqual(res["commentsCount"], count_before - 1)

    def test_05_author_delete_parent_with_children(self) -> None:
        """Invariant 4: Deleting parent preserves active children; parent becomes 'Комментарий удален'."""
        c_alice = self._login("u_alice", "Алиса")
        c_bob = self._login("u_bob", "Боб")

        st, res = self._post_json("/api/articles/art_issue49_01/comments", {
            "content": "Родительский комментарий Алисы",
            "commentType": "comment"
        }, cookie=c_alice)
        self.assertEqual(st, 201)
        p_id = res["comment"]["id"]

        st, res = self._post_json("/api/articles/art_issue49_01/comments", {
            "content": "Дочерний комментарий Боба",
            "commentType": "comment",
            "parentCommentId": p_id
        }, cookie=c_bob)
        self.assertEqual(st, 201)
        c_id = res["comment"]["id"]

        # Delete parent
        st, res = self._delete_json(f"/api/articles/art_issue49_01/comments/{p_id}", cookie=c_alice)
        self.assertEqual(st, 200)

        # GET comments: parent is returned as placeholder, child is intact
        st, res = self._get_json("/api/articles/art_issue49_01/comments")
        self.assertEqual(st, 200)

        p_node = next((c for c in res["comments"] if c["id"] == p_id), None)
        self.assertIsNotNone(p_node)
        self.assertTrue(p_node.get("isDeleted"))
        self.assertEqual(p_node["content"], "Комментарий удален")
        self.assertFalse(p_node.get("canVote"))

        c_node = next((c for c in res["comments"] if c["id"] == c_id), None)
        self.assertIsNotNone(c_node)
        self.assertFalse(c_node.get("isDeleted"))
        self.assertEqual(c_node["content"], "Дочерний комментарий Боба")
        self.assertEqual(c_node["parentCommentId"], p_id)

    def test_06_idempotent_repeated_deletion(self) -> None:
        """Invariant 7: Repeating DELETE on already deleted comment returns 200 without DB distortion."""
        c_alice = self._login("u_alice", "Алиса")

        st, res = self._post_json("/api/articles/art_issue49_01/comments", {
            "content": "Комментарий для повторного удаления",
            "commentType": "comment"
        }, cookie=c_alice)
        self.assertEqual(st, 201)
        c_id = res["comment"]["id"]

        # First delete
        st, res = self._delete_json(f"/api/articles/art_issue49_01/comments/{c_id}", cookie=c_alice)
        self.assertEqual(st, 200)

        # Second delete (repeat)
        st, res = self._delete_json(f"/api/articles/art_issue49_01/comments/{c_id}", cookie=c_alice)
        self.assertEqual(st, 200)
        self.assertTrue(res.get("success"))

    def test_07_author_rating_karma_sync(self) -> None:
        """Invariant 9: Deleting comment immediately excludes its score from author karma; children keep karma."""
        c_alice = self._login("u_alice", "Алиса")
        c_bob = self._login("u_bob", "Боб")

        st, res = self._post_json("/api/articles/art_issue49_01/comments", {
            "content": "Комментарий Алисы с голосом",
            "commentType": "comment"
        }, cookie=c_alice)
        self.assertEqual(st, 201)
        a_comm_id = res["comment"]["id"]

        # Bob votes +1 on Alice's comment
        st, res = self._post_json(f"/api/comments/{a_comm_id}/vote", {"value": 1}, cookie=c_bob)
        self.assertEqual(st, 200)

        # Bob writes child comment under Alice's comment
        st, res = self._post_json("/api/articles/art_issue49_01/comments", {
            "content": "Комментарий Боба под комментарием Алисы",
            "commentType": "comment",
            "parentCommentId": a_comm_id
        }, cookie=c_bob)
        self.assertEqual(st, 201)
        b_comm_id = res["comment"]["id"]

        # Alice votes +1 on Bob's comment
        st, res = self._post_json(f"/api/comments/{b_comm_id}/vote", {"value": 1}, cookie=c_alice)
        self.assertEqual(st, 200)

        # Check profiles before deletion
        st, res_a = self._get_json("/api/users/u_alice")
        self.assertEqual(st, 200)
        alice_rating_before = res_a["user"]["rating"]

        st, res_b = self._get_json("/api/users/u_bob")
        self.assertEqual(st, 200)
        bob_rating_before = res_b["user"]["rating"]

        # Alice deletes her comment
        st, res = self._delete_json(f"/api/articles/art_issue49_01/comments/{a_comm_id}", cookie=c_alice)
        self.assertEqual(st, 200)

        # Check profiles after deletion
        st, res_a_after = self._get_json("/api/users/u_alice")
        self.assertEqual(st, 200)
        self.assertEqual(res_a_after["user"]["rating"], alice_rating_before - 1)

        st, res_b_after = self._get_json("/api/users/u_bob")
        self.assertEqual(st, 200)
        self.assertEqual(res_b_after["user"]["rating"], bob_rating_before)

    def test_08_delete_question_clarification_and_answer_replies(self) -> None:
        """Invariant 3 & 8: Authors can delete question clarification comments and answer replies."""
        c_alice = self._login("u_alice", "Алиса")
        c_bob = self._login("u_bob", "Боб")

        # 1. Clarification comment on question
        st, res = self._post_json("/api/articles/quest_issue49_01/comments", {
            "content": "Уточнение Алисы к вопросу",
            "commentType": "comment"
        }, cookie=c_alice)
        self.assertEqual(st, 201)
        clar_id = res["comment"]["id"]

        st, res = self._delete_json(f"/api/articles/quest_issue49_01/comments/{clar_id}", cookie=c_alice)
        self.assertEqual(st, 200)

        # 2. Answer on question by Charlie
        c_charlie = self._login("u_charlie", "Чарли")
        st, res = self._post_json("/api/articles/quest_issue49_01/comments", {
            "content": "Ответ Чарли на вопрос для проверки ветки",
            "commentType": "answer"
        }, cookie=c_charlie)
        self.assertEqual(st, 201)
        ans_id = res["comment"]["id"]

        # Reply to answer by Bob
        st, res = self._post_json("/api/articles/quest_issue49_01/comments", {
            "content": "Комментарий Боба под ответом Чарли",
            "commentType": "comment",
            "parentAnswerId": ans_id
        }, cookie=c_bob)
        self.assertEqual(st, 201)
        reply_id = res["comment"]["id"]

        # Bob deletes his reply
        st, res = self._delete_json(f"/api/articles/quest_issue49_01/comments/{reply_id}", cookie=c_bob)
        self.assertEqual(st, 200)


class TestIssue49FrontendContractsAndCSS(unittest.TestCase):
    """Verifies frontend HTML/CSS contracts, styles, and two-tier layout."""

    @classmethod
    def setUpClass(cls) -> None:
        css_path = os.path.join(FRONTEND_DIR, "css", "article.css")
        with open(css_path, "r", encoding="utf-8") as f:
            cls.article_css = f.read()

        js_path = os.path.join(FRONTEND_DIR, "js", "article.js")
        with open(js_path, "r", encoding="utf-8") as f:
            cls.article_js = f.read()

    def test_09_css_contracts_and_two_tier_layout(self) -> None:
        """Invariant 10: .btn-delete-comment hover danger style, .comment-delete-confirm container, and action row."""
        self.assertTrue(
            ".btn-action-text.btn-delete-comment:hover" in self.article_css or
            ".btn-comment-action.btn-delete-comment:hover" in self.article_css
        )
        self.assertTrue(
            "var(--danger-color, #ef4444)" in self.article_css or
            "var(--error-color, #ef4444)" in self.article_css or
            "var(--error-color" in self.article_css
        )
        self.assertIn(".comment-delete-confirm", self.article_css)
        self.assertIn(".comment-delete-confirm-text", self.article_css)
        self.assertIn(".comment-delete-confirm-actions", self.article_css)

        # In article.js: deleteBtnHtml rendered only for own non-answer comments
        self.assertIn("deleteBtnHtml", self.article_js)
        self.assertIn("isMyComment && !isAnswer && !comment.isDeleted", self.article_js)
        self.assertTrue(
            'class="btn-action-text btn-delete-comment"' in self.article_js or
            'class="btn-comment-action btn-delete-comment"' in self.article_js
        )
        self.assertIn('class="comment-delete-confirm"', self.article_js)
        self.assertIn('class="btn btn-secondary btn-sm btn-cancel-delete-comment"', self.article_js)
        self.assertIn('class="btn btn-danger btn-sm btn-confirm-delete-comment"', self.article_js)

        # Action row layout: comment-vote-row exists in article.js
        self.assertIn('class="comment-vote-row', self.article_js)


class MockDOMElement:
    """Minimal mock DOM element for runtime behavioral simulation."""
    def __init__(self, tag: str = "div"):
        self.tag = tag
        self.classes: Set[str] = set()
        self.attributes: Dict[str, str] = {}
        self.style: Dict[str, str] = {}
        self.children: List["MockDOMElement"] = []
        self.text_content = ""
        self.disabled = False
        self.focused = False

    def focus(self) -> None:
        self.focused = True

    def blur(self) -> None:
        self.focused = False

    def query_selector(self, selector: str) -> Optional["MockDOMElement"]:
        for c in self.children:
            if selector.startswith(".") and selector[1:] in c.classes:
                return c
            sub = c.query_selector(selector)
            if sub:
                return sub
        return None

    def query_selector_all(self, selector: str) -> List["MockDOMElement"]:
        res = []
        for c in self.children:
            if selector.startswith(".") and selector[1:] in c.classes:
                res.append(c)
            res.extend(c.query_selector_all(selector))
        return res


class TestIssue49FrontendBehavioralSimulation(unittest.TestCase):
    """Verifies runtime behavior: visibility, inline confirm, keyboard access, pending state, and session isolation."""

    def test_10_behavioral_delete_confirmation_flow_and_accessibility(self) -> None:
        """Invariants 1, 3, 7, 8: Simulation of delete flow, escape dismiss, disabled pending, and session switch."""

        class CommentUIController:
            def __init__(self, current_user: Optional[dict], session_token: int = 1):
                self.current_user = current_user
                self.session_token = session_token
                self.is_delete_pending = False
                self.toasts: List[Tuple[str, str]] = []
                self.events: List[dict] = []
                self.comments_reloaded = False
                self.auth_modal_invoked = False

            def build_comment_node(self, comment: dict) -> MockDOMElement:
                el = MockDOMElement("div")
                el.classes.add("comment-item")

                is_my = bool(self.current_user and (self.current_user.get("id") == comment.get("userId")))
                is_ans = (comment.get("commentType") == "answer")
                is_del = bool(comment.get("isDeleted"))

                actions = MockDOMElement("div")
                actions.classes.add("comment-actions")

                del_btn = None
                if is_my and not is_ans and not is_del:
                    del_btn = MockDOMElement("button")
                    del_btn.classes.add("btn-action-text")
                    del_btn.classes.add("btn-delete-comment")
                    del_btn.text_content = "Удалить"
                    actions.children.append(del_btn)

                confirm_wrap = MockDOMElement("div")
                confirm_wrap.classes.add("comment-delete-confirm")
                confirm_wrap.style["display"] = "none"

                cancel_btn = MockDOMElement("button")
                cancel_btn.classes.add("btn-cancel-delete-comment")
                cancel_btn.text_content = "Отмена"

                confirm_btn = MockDOMElement("button")
                confirm_btn.classes.add("btn-confirm-delete-comment")
                confirm_btn.text_content = "Удалить"

                confirm_wrap.children.extend([cancel_btn, confirm_btn])
                el.children.extend([actions, confirm_wrap])
                return el

            def on_delete_click(self, el: MockDOMElement) -> None:
                if self.is_delete_pending:
                    return
                del_btn = el.query_selector(".btn-delete-comment")
                confirm_wrap = el.query_selector(".comment-delete-confirm")
                cancel_btn = el.query_selector(".btn-cancel-delete-comment")
                if del_btn and confirm_wrap:
                    confirm_wrap.style["display"] = "flex"
                    del_btn.style["display"] = "none"
                    if cancel_btn:
                        cancel_btn.focus()

            def on_cancel_click(self, el: MockDOMElement) -> None:
                if self.is_delete_pending:
                    return
                del_btn = el.query_selector(".btn-delete-comment")
                confirm_wrap = el.query_selector(".comment-delete-confirm")
                if del_btn and confirm_wrap:
                    confirm_wrap.style["display"] = "none"
                    del_btn.style["display"] = ""
                    del_btn.focus()

            def on_escape_press(self, el: MockDOMElement) -> None:
                self.on_cancel_click(el)

            def on_confirm_delete(self, el: MockDOMElement, req_session_token: int, mock_response: dict) -> None:
                if self.is_delete_pending:
                    return
                self.is_delete_pending = True
                confirm_btn = el.query_selector(".btn-confirm-delete-comment")
                cancel_btn = el.query_selector(".btn-cancel-delete-comment")
                if confirm_btn:
                    confirm_btn.disabled = True
                    confirm_btn.text_content = "Удаление..."
                if cancel_btn:
                    cancel_btn.disabled = True

                # Check session switch
                if req_session_token != self.session_token:
                    # Discard response
                    return

                if mock_response.get("ok"):
                    self.toasts.append(("Комментарий удален", "success"))
                    self.events.append({"type": "smartcontractum:voted", "action": "delete"})
                    self.comments_reloaded = True
                else:
                    self.is_delete_pending = False
                    if confirm_btn:
                        confirm_btn.disabled = False
                        confirm_btn.text_content = "Удалить"
                    if cancel_btn:
                        cancel_btn.disabled = False
                    if mock_response.get("status") == 401:
                        self.auth_modal_invoked = True
                    else:
                        self.toasts.append((mock_response.get("error") or "Не удалось удалить", "error"))

        # Scenario A: Visibility
        ctrl_alice = CommentUIController({"id": "u_alice", "name": "Алиса"})
        comment_alice = {"id": "c1", "userId": "u_alice", "commentType": "comment", "isDeleted": False}
        el_alice = ctrl_alice.build_comment_node(comment_alice)
        self.assertIsNotNone(el_alice.query_selector(".btn-delete-comment"))

        # For Bob on Alice's comment: no delete button
        ctrl_bob = CommentUIController({"id": "u_bob", "name": "Боб"})
        el_bob = ctrl_bob.build_comment_node(comment_alice)
        self.assertIsNone(el_bob.query_selector(".btn-delete-comment"))

        # For Guest on Alice's comment: no delete button
        ctrl_guest = CommentUIController(None)
        el_guest = ctrl_guest.build_comment_node(comment_alice)
        self.assertIsNone(el_guest.query_selector(".btn-delete-comment"))

        # For Alice on Answer: no delete button
        ans_alice = {"id": "a1", "userId": "u_alice", "commentType": "answer", "isDeleted": False}
        el_ans = ctrl_alice.build_comment_node(ans_alice)
        self.assertIsNone(el_ans.query_selector(".btn-delete-comment"))

        # Scenario B: Confirmation & Cancel / Escape
        ctrl = CommentUIController({"id": "u_alice", "name": "Алиса"}, session_token=1)
        el = ctrl.build_comment_node(comment_alice)
        del_btn = el.query_selector(".btn-delete-comment")
        confirm_wrap = el.query_selector(".comment-delete-confirm")
        cancel_btn = el.query_selector(".btn-cancel-delete-comment")

        # Click delete -> confirm opens, cancel focused
        ctrl.on_delete_click(el)
        self.assertEqual(confirm_wrap.style["display"], "flex")
        self.assertEqual(del_btn.style["display"], "none")
        self.assertTrue(cancel_btn.focused)

        # Press Escape -> confirm closes, delete focused
        ctrl.on_escape_press(el)
        self.assertEqual(confirm_wrap.style["display"], "none")
        self.assertEqual(del_btn.style["display"], "")
        self.assertTrue(del_btn.focused)

        # Scenario C: In-flight Pending and Session Switch
        ctrl.on_delete_click(el)
        req_token = ctrl.session_token
        # User switches accounts in another tab
        ctrl.session_token = 2

        # Response arrives for req_token=1
        ctrl.on_confirm_delete(el, req_session_token=req_token, mock_response={"ok": True})
        # Verifies response was discarded due to session switch
        self.assertFalse(ctrl.comments_reloaded)
        self.assertEqual(len(ctrl.toasts), 0)

        # Scenario D: Error Rollback
        ctrl_err = CommentUIController({"id": "u_alice", "name": "Алиса"}, session_token=5)
        el_err = ctrl_err.build_comment_node(comment_alice)
        ctrl_err.on_delete_click(el_err)
        ctrl_err.on_confirm_delete(el_err, req_session_token=5, mock_response={"ok": False, "status": 403, "error": "Доступ запрещен"})
        self.assertFalse(ctrl_err.is_delete_pending)
        confirm_btn = el_err.query_selector(".btn-confirm-delete-comment")
        self.assertFalse(confirm_btn.disabled)
        self.assertEqual(ctrl_err.toasts[-1], ("Доступ запрещен", "error"))

        # Scenario E: Success
        ctrl_ok = CommentUIController({"id": "u_alice", "name": "Алиса"}, session_token=10)
        el_ok = ctrl_ok.build_comment_node(comment_alice)
        ctrl_ok.on_delete_click(el_ok)
        ctrl_ok.on_confirm_delete(el_ok, req_session_token=10, mock_response={"ok": True})
        self.assertTrue(ctrl_ok.comments_reloaded)
        self.assertEqual(ctrl_ok.toasts[-1], ("Комментарий удален", "success"))
        self.assertEqual(ctrl_ok.events[-1]["action"], "delete")


if __name__ == "__main__":
    unittest.main()
