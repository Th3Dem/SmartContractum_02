#!/usr/bin/env python3
"""
tests/test_issue19_sc019_validate_root_json_type.py

Comprehensive regression test suite for Issue #19 (SC-019):
"Обработка невалидных JSON-типов без обрыва соединения".

Verifies:
1. Helper method read_json_body in ModerationRequestHandler:
   - Rejects non-dict JSON (lists, primitives, null) with HTTP 400.
   - Rejects malformed JSON syntax with HTTP 400.
   - Handles empty body according to allow_empty flag.
   - Returns valid dict payloads correctly.
2. All POST handlers safely validate root JSON type (dict check):
   - /api/auth/login
   - /api/user/feed-settings
   - /api/clubs
   - /api/companies
   - /api/likes/toggle and /api/articles/<id>/like
   - /api/articles/<id>/comments/<cid>/solution, /api/comments/<cid>/solution, /api/articles/<id>/solution
   - /api/articles/<id>/comments and /api/comments
   - /api/notifications/read
   - /api/user/profile
   - /api/exceptions/toggle
   - /api/subscriptions/toggle
   - /api/moderation/submit (retains fieldErrors: {})
   - /api/media/upload (application/json)
   Each endpoint returns HTTP 400 and success: False for non-dict JSON without 500 or crash.
3. do_PUT safely drains request body and returns HTTP 405 Method Not Allowed.
4. Keep-alive connection resilience across malformed and valid requests.
"""

import datetime
import http.client
import json
import os
import shutil
import socket
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from typing import Optional, Tuple

import server
from server import MAX_JSON_BODY_BYTES, create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue19ValidateRootJsonType(unittest.TestCase):
    """Test suite for Issue #19 (SC-019) validating root JSON payload type."""

    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue19_sc019.db")
        cls.media_dir = os.path.join(cls.temp_dir, "media")
        os.makedirs(cls.media_dir, exist_ok=True)
        server.DEFAULT_DB_PATH = cls.db_path
        server.MEDIA_DIR = cls.media_dir

        conn = init_db(cls.db_path)
        conn.close()

        cls.httpd = create_server(
            host="127.0.0.1",
            port=0,
            db_path=cls.db_path,
            directory=FRONTEND_DIR,
            media_dir=cls.media_dir,
        )
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
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        # Create an article and a comment in DB for endpoint targets
        conn = sqlite3.connect(self.db_path)
        with conn:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, author_id, title, article_html, article_delta,
                    publication_settings, snapshot_hash, status, created_at, updated_at
                ) VALUES (
                    'art_test_19', 'draft_19', 'alice', 'Тестовая статья для Issue 19',
                    '<p>Контент</p>', '{}', '{"materialType": "question"}', 'hash19',
                    'approved', ?, ?
                )
            """, (now_iso, now_iso))
            conn.execute("""
                INSERT OR REPLACE INTO article_comments (
                    id, article_id, user_id, author_name, content,
                    created_at, comment_type, is_solution
                ) VALUES (
                    'comm_test_19', 'art_test_19', 'bob', 'Боб', 'Тестовый ответ',
                    ?, 'answer', 0
                )
            """, (now_iso,))
        conn.close()

        # Log in alice to obtain auth session cookie
        login_url = f"{self.base_url}/api/auth/login"
        payload = json.dumps({"userId": "alice", "name": "Алиса", "role": "user"}).encode("utf-8")
        req = urllib.request.Request(
            login_url,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            self.alice_cookie = resp.headers.get("Set-Cookie", "")

    def _post_raw_payload(self, path: str, raw_body: bytes, cookie: Optional[str] = None,
                          content_type: str = "application/json") -> Tuple[int, dict]:
        """Sends raw POST bytes to path and returns (status_code, parsed_json_dict)."""
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": content_type}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, data=raw_body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            res_body = e.read().decode("utf-8")
            try:
                return e.code, json.loads(res_body) if res_body else {}
            except Exception:
                return e.code, {"raw": res_body}
            finally:
                e.close()

    def _send_raw_socket(self, method: str, path: str, headers: dict, body: bytes = b"") -> Tuple[int, dict, bytes]:
        """Sends raw HTTP request via socket to verify low-level protocol behavior."""
        s = socket.create_connection(("127.0.0.1", self.port), timeout=5.0)
        try:
            req_lines = [f"{method} {path} HTTP/1.1", f"Host: 127.0.0.1:{self.port}"]
            for k, v in headers.items():
                req_lines.append(f"{k}: {v}")
            if "content-length" not in [k.lower() for k in headers.keys()]:
                req_lines.append(f"Content-Length: {len(body)}")
            req_lines.append("Connection: close")
            req_lines.append("")
            raw_req = "\r\n".join(req_lines).encode("latin-1") + b"\r\n" + body
            s.sendall(raw_req)

            resp_chunks = []
            while True:
                chunk = s.recv(8192)
                if not chunk:
                    break
                resp_chunks.append(chunk)
            raw_resp = b"".join(resp_chunks)
        finally:
            s.close()

        parts = raw_resp.split(b"\r\n\r\n", 1)
        header_text = parts[0].decode("latin-1", errors="replace")
        resp_body = parts[1] if len(parts) > 1 else b""

        status_line = header_text.split("\r\n")[0]
        status_code = int(status_line.split()[1]) if len(status_line.split()) > 1 else 0

        resp_headers = {}
        for line in header_text.split("\r\n")[1:]:
            if ":" in line:
                hk, hv = line.split(":", 1)
                resp_headers[hk.strip().lower()] = hv.strip()

        return status_code, resp_headers, resp_body

    # =========================================================================
    # 0. Direct unit tests for read_json_body helper method
    # =========================================================================
    def test_00_read_json_body_method_direct_unit_tests(self):
        """Unit test read_json_body behavior directly for all branch conditions."""
        class DummyHandler:
            def __init__(self, raw: Optional[bytes]):
                self._raw = raw
                self.sent_responses = []

            def read_request_body(self, max_bytes: int = MAX_JSON_BODY_BYTES):
                return self._raw

            def send_json_response(self, status: int, data: dict, extra_headers=None):
                self.sent_responses.append((status, data))

            read_json_body = server.ModerationRequestHandler.read_json_body

        # 1. read_request_body returns None (e.g. 413 error)
        h = DummyHandler(None)
        res = h.read_json_body()
        self.assertIsNone(res)
        self.assertEqual(len(h.sent_responses), 0)

        # 2. Empty body with allow_empty=False
        h = DummyHandler(b"")
        res = h.read_json_body(allow_empty=False)
        self.assertIsNone(res)
        self.assertEqual(h.sent_responses[0][0], 400)
        self.assertIn("пустым", h.sent_responses[0][1]["error"])

        # 3. Empty body with allow_empty=True, default None -> {}
        h = DummyHandler(b"   ")
        res = h.read_json_body(allow_empty=True)
        self.assertEqual(res, {})
        self.assertEqual(len(h.sent_responses), 0)

        # 4. Empty body with allow_empty=True, custom default
        h = DummyHandler(b"")
        res = h.read_json_body(allow_empty=True, default_empty={"custom": True})
        self.assertEqual(res, {"custom": True})

        # 5. Invalid JSON syntax
        h = DummyHandler(b"{invalid_json")
        res = h.read_json_body()
        self.assertIsNone(res)
        self.assertEqual(h.sent_responses[0][0], 400)
        self.assertIn("Невалидный JSON", h.sent_responses[0][1]["error"])

        # 6. Non-dict types: list, str, int, float, bool, None
        for non_dict_val in [b"[]", b"[1, 2]", b'"string"', b"123", b"1.23", b"true", b"false", b"null"]:
            h = DummyHandler(non_dict_val)
            res = h.read_json_body()
            self.assertIsNone(res)
            self.assertEqual(h.sent_responses[0][0], 400)
            self.assertIn("JSON-объектом", h.sent_responses[0][1]["error"])

        # 7. Valid dict
        h = DummyHandler(b'{"key": "value", "count": 1}')
        res = h.read_json_body()
        self.assertEqual(res, {"key": "value", "count": 1})
        self.assertEqual(len(h.sent_responses), 0)

    # =========================================================================
    # 1. Non-dict JSON payloads to all POST endpoints return HTTP 400 Bad Request
    # =========================================================================
    def test_01_all_post_endpoints_reject_non_dict_json_types(self):
        """
        Verify that sending non-dict JSON (array, string, int, bool, null)
        returns HTTP 400 Bad Request with success: False and Russian error message.
        """
        endpoints = [
            "/api/auth/login",
            "/api/user/feed-settings",
            "/api/clubs",
            "/api/companies",
            "/api/likes/toggle",
            "/api/articles/art_test_19/like",
            "/api/articles/art_test_19/comments/comm_test_19/solution",
            "/api/comments/comm_test_19/solution",
            "/api/articles/art_test_19/solution",
            "/api/articles/art_test_19/comments",
            "/api/comments",
            "/api/notifications/read",
            "/api/user/profile",
            "/api/exceptions/toggle",
            "/api/subscriptions/toggle",
            "/api/moderation/submit",
            "/api/media/upload",
        ]

        non_dict_payloads = [
            ("empty_list", b"[]"),
            ("populated_list", b'["item1", 2, true]'),
            ("string", b'"hello world"'),
            ("integer", b"12345"),
            ("float", b"123.45"),
            ("boolean_true", b"true"),
            ("boolean_false", b"false"),
            ("null_literal", b"null"),
        ]

        for ep in endpoints:
            for p_name, raw_body in non_dict_payloads:
                with self.subTest(endpoint=ep, payload_type=p_name):
                    status, data = self._post_raw_payload(ep, raw_body, cookie=self.alice_cookie)
                    self.assertEqual(
                        status, 400,
                        f"Expected HTTP 400 for {ep} with {p_name}, got {status}: {data}"
                    )
                    self.assertFalse(
                        data.get("success"),
                        f"Expected success: False for {ep} with {p_name}"
                    )
                    error_msg = data.get("error", "")
                    self.assertTrue(
                        "объектом" in error_msg.lower() or "невалидный" in error_msg.lower() or "json" in error_msg.lower(),
                        f"Expected descriptive error message for {ep}, got: {error_msg}"
                    )
                    if ep == "/api/moderation/submit":
                        self.assertIn("fieldErrors", data, "moderation/submit must preserve fieldErrors in response")

    # =========================================================================
    # 2. Syntax errors in JSON return HTTP 400 Bad Request
    # =========================================================================
    def test_02_all_post_endpoints_reject_malformed_json_syntax(self):
        """Verify that broken JSON syntax ({invalid or truncated) returns HTTP 400."""
        endpoints = [
            "/api/auth/login",
            "/api/user/feed-settings",
            "/api/clubs",
            "/api/companies",
            "/api/likes/toggle",
            "/api/articles/art_test_19/like",
            "/api/articles/art_test_19/comments",
            "/api/comments",
            "/api/notifications/read",
            "/api/user/profile",
            "/api/exceptions/toggle",
            "/api/subscriptions/toggle",
            "/api/moderation/submit",
            "/api/media/upload",
        ]

        broken_bodies = [
            b"{bad_json:",
            b'{"key": "unclosed string',
            b'{"key": [1, 2, }',
            b"{",
        ]

        for ep in endpoints:
            for raw_body in broken_bodies:
                with self.subTest(endpoint=ep, body=raw_body):
                    status, data = self._post_raw_payload(ep, raw_body, cookie=self.alice_cookie)
                    self.assertEqual(
                        status, 400,
                        f"Expected HTTP 400 for malformed JSON on {ep}, got {status}: {data}"
                    )
                    self.assertFalse(data.get("success"))

    # =========================================================================
    # 3. Empty body handling per endpoint specification
    # =========================================================================
    def test_03_empty_body_handling(self):
        """
        Verify allow_empty=True endpoints accept empty body or default to {}:
        - /api/auth/login -> 200 OK
        - /api/notifications/read -> 200 OK
        - /api/user/profile -> 200 OK
        - /api/clubs (allow_empty=False) -> 400 Bad Request
        - /api/companies (allow_empty=False) -> 400 Bad Request
        - /api/subscriptions/toggle (allow_empty=False) -> 400 Bad Request
        - /api/exceptions/toggle (allow_empty=False) -> 400 Bad Request
        - /api/moderation/submit (allow_empty=False) -> 400 Bad Request
        """
        # allow_empty=True endpoints
        status, data = self._post_raw_payload("/api/auth/login", b"", cookie=None)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        status, data = self._post_raw_payload("/api/notifications/read", b"", cookie=self.alice_cookie)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        status, data = self._post_raw_payload("/api/user/profile", b"", cookie=self.alice_cookie)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        # allow_empty=False endpoints
        for ep in ["/api/clubs", "/api/companies", "/api/subscriptions/toggle",
                   "/api/exceptions/toggle", "/api/moderation/submit"]:
            with self.subTest(empty_endpoint=ep):
                status, data = self._post_raw_payload(ep, b"", cookie=self.alice_cookie)
                self.assertEqual(
                    status, 400,
                    f"Endpoint {ep} with allow_empty=False should return 400 on empty body, got {status}"
                )
                self.assertFalse(data.get("success"))

    # =========================================================================
    # 4. Valid JSON dicts process normally
    # =========================================================================
    def test_04_valid_json_dict_processed_normally(self):
        """Verify that valid dict payloads are accepted and processed properly."""
        # /api/auth/login with valid dict
        status, data = self._post_raw_payload(
            "/api/auth/login",
            json.dumps({"userId": "charlie", "name": "Чарли"}).encode("utf-8")
        )
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data["user"]["id"], "charlie")

        # /api/likes/toggle with valid dict
        status, data = self._post_raw_payload(
            "/api/likes/toggle",
            json.dumps({"articleId": "art_test_19"}).encode("utf-8"),
            cookie=self.alice_cookie
        )
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        # /api/subscriptions/toggle with valid dict
        status, data = self._post_raw_payload(
            "/api/subscriptions/toggle",
            json.dumps({"targetType": "author", "targetId": "bob"}).encode("utf-8"),
            cookie=self.alice_cookie
        )
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("subscribed"))

        # /api/exceptions/toggle with valid dict
        status, data = self._post_raw_payload(
            "/api/exceptions/toggle",
            json.dumps({"targetType": "topic", "targetId": "Rust"}).encode("utf-8"),
            cookie=self.alice_cookie
        )
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("excluded"))

    # =========================================================================
    # 5. do_PUT method returns 405 Method Not Allowed without crash
    # =========================================================================
    def test_05_do_put_returns_405_safely(self):
        """
        Verify that sending PUT requests to any API or static path
        safely drains the body and returns HTTP 405 Method Not Allowed.
        """
        put_targets = [
            "/api/articles/art_test_19",
            "/api/moderation/submit",
            "/api/user/profile",
            "/index.html",
        ]

        put_bodies = [
            b"",
            b"[]",
            b'{"name": "test"}',
            b"some arbitrary raw bytes " * 100,
        ]

        for target in put_targets:
            for body in put_bodies:
                with self.subTest(target=target, body_len=len(body)):
                    status, headers, resp_body = self._send_raw_socket(
                        "PUT",
                        target,
                        {"Content-Type": "application/json"},
                        body=body
                    )
                    self.assertEqual(status, 405)
                    try:
                        resp_data = json.loads(resp_body.decode("utf-8"))
                        self.assertFalse(resp_data.get("success"))
                        self.assertIn("method not allowed", resp_data.get("error", "").lower())
                    except Exception as e:
                        self.fail(f"Expected valid JSON 405 response, got: {resp_body}, err: {e}")

    # =========================================================================
    # 6. Connection resilience over keep-alive HTTP/1.1
    # =========================================================================
    def test_06_keep_alive_connection_resilience_after_bad_request(self):
        """
        Verify that after sending a non-dict request, the HTTP keep-alive connection
        remains healthy and can process subsequent valid requests cleanly.
        """
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5.0)
        try:
            # Request 1: Malformed non-dict JSON []
            conn.request(
                "POST",
                "/api/auth/login",
                body=b"[]",
                headers={"Content-Type": "application/json", "Connection": "keep-alive"}
            )
            resp1 = conn.getresponse()
            body1 = resp1.read()
            self.assertEqual(resp1.status, 400)
            data1 = json.loads(body1.decode("utf-8"))
            self.assertFalse(data1.get("success"))

            # Request 2: Valid JSON on the same persistent connection
            conn.request(
                "POST",
                "/api/auth/login",
                body=json.dumps({"userId": "keep_alive_user"}).encode("utf-8"),
                headers={"Content-Type": "application/json", "Connection": "close"}
            )
            resp2 = conn.getresponse()
            body2 = resp2.read()
            self.assertEqual(resp2.status, 200)
            data2 = json.loads(body2.decode("utf-8"))
            self.assertTrue(data2.get("success"))
            self.assertEqual(data2["user"]["id"], "keep_alive_user")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
