#!/usr/bin/env python3
"""
tests/test_issue8_sc005_streaming_body_limit.py

Comprehensive security and regression test suite for Issue #8 (SC-005):
«Потоковое ограничение размера тела запроса и защита от декомпрессии PNG».

Acceptance Criteria:
1. Запросы с Content-Length > лимита немедленно отклоняются с HTTP 413 без исчерпания памяти.
2. Чтение из сокета ограничено max_bytes с потоковым контролем.
3. Декомпрессия IDAT в PNG ограничена безопасным буфером, zip-бомбы гарантированно отклоняются с ImageDecodeError.
4. 100% тестов проекта проходят успешно (python3 -m unittest discover tests/).
5. Оформлен tasks/issue-8-sc005-streaming-body-limit-and-png-decompression/DEV_HANDOVER.md.
"""

import base64
import binascii
import json
import os
import shutil
import socket
import struct
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zlib

import image_decoder
from image_decoder import (
    ImageDecodeError,
    MAX_PNG_DECOMPRESSED_BYTES,
    decode_and_validate_image,
    _decode_png,
)
import server
from tests.auth_helpers import upload_auth_headers
from server import (
    MAX_JSON_BODY_BYTES,
    MAX_MEDIA_BODY_BYTES,
    create_server,
    init_db,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


def _build_png_bytes(width: int, height: int, raw_idat: bytes) -> bytes:
    """Helper to assemble a valid PNG byte stream with specified dimensions and IDAT payload."""
    def chunk(chunk_type: bytes, chunk_data: bytes) -> bytes:
        content = chunk_type + chunk_data
        crc = binascii.crc32(content) & 0xFFFFFFFF
        return struct.pack(">I", len(chunk_data)) + content + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    compressed_idat = zlib.compress(raw_idat)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", compressed_idat)
        + chunk(b"IEND", b"")
    )


class TestIssue8SC005StreamingBodyLimitAndPNG(unittest.TestCase):
    """Target security test suite for Issue #8 (SC-005)."""

    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue8_sc005.db")
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

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _login(self, user_id="alice", name="Alice", role="user"):
        """Helper to log in and return session cookie."""
        login_url = f"{self.base_url}/api/auth/login"
        payload = json.dumps({"userId": user_id, "name": name, "role": role}).encode("utf-8")
        req = urllib.request.Request(
            login_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            cookie = resp.headers.get("Set-Cookie")
            data = json.loads(resp.read().decode("utf-8"))
            return data, cookie

    def _send_raw_http(self, method: str, path: str, headers: dict, body_prefix: bytes = b"") -> tuple:
        """Sends raw HTTP request via socket and returns (status_code, headers_dict, body_bytes)."""
        s = socket.create_connection(("127.0.0.1", self.port), timeout=4.0)
        try:
            req_lines = [f"{method} {path} HTTP/1.1", f"Host: 127.0.0.1:{self.port}"]
            for k, v in headers.items():
                req_lines.append(f"{k}: {v}")
            req_lines.append("Connection: close")
            req_lines.append("")
            raw_req = "\r\n".join(req_lines).encode("latin-1") + b"\r\n" + body_prefix
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

    # -------------------------------------------------------------------------
    # 1. Запрос с Content-Length > MAX_JSON_BODY_BYTES немедленно возвращает 413
    # -------------------------------------------------------------------------
    def test_01_json_post_exceeding_limit_immediately_returns_413(self):
        """1. Запрос к JSON-эндпоинтам с Content-Length > 5 МБ немедленно возвращает 413 Payload Too Large."""
        oversized_cl = MAX_JSON_BODY_BYTES + 2048

        for endpoint in ["/api/moderation/submit", "/api/auth/login", "/api/companies", "/api/user/feed-settings"]:
            status, headers, body = self._send_raw_http(
                "POST",
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(oversized_cl),
                },
                body_prefix=b"",  # Data is NOT sent; server must reject based on header alone
            )
            self.assertEqual(status, 413, f"Endpoint {endpoint} must return 413 on oversized Content-Length")
            data = json.loads(body.decode("utf-8"))
            self.assertFalse(data.get("success"))
            self.assertIn("Payload Too Large", data.get("error", ""))
            self.assertEqual(headers.get("connection"), "close")

    # -------------------------------------------------------------------------
    # 2. Проверка, что тело свыше лимита не вычитывается в память при превышении Content-Length
    # -------------------------------------------------------------------------
    def test_02_body_above_limit_not_read_into_memory(self):
        """2. Запрос с огромным Content-Length (100 МБ) отвергается мгновенно без блокировки или OOM."""
        huge_cl = 100 * 1024 * 1024  # 100 MB claimed
        start_t = time.time()
        status, headers, body = self._send_raw_http(
            "POST",
            "/api/moderation/submit",
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(huge_cl),
            },
            body_prefix=b"",
        )
        elapsed = time.time() - start_t

        self.assertEqual(status, 413)
        self.assertLess(elapsed, 0.5, "Rejection must happen instantly without reading 100 MB")
        data = json.loads(body.decode("utf-8"))
        self.assertIn("Payload Too Large", data.get("error", ""))

    # -------------------------------------------------------------------------
    # 3. Отклонение запроса на загрузку медиа при превышении лимита медиа (15 МБ)
    # -------------------------------------------------------------------------
    def test_03_media_upload_exceeding_limit_returns_413(self):
        """3. Запрос к POST /api/media/upload с телом > MAX_MEDIA_BODY_BYTES (15 МБ) возвращает 413."""
        oversized_media_cl = MAX_MEDIA_BODY_BYTES + 4096

        status, headers, body = self._send_raw_http(
            "POST",
            "/api/media/upload",
            headers={**upload_auth_headers(self.db_path),
                "Content-Type": "image/png",
                "Content-Length": str(oversized_media_cl),
            },
            body_prefix=b"",
        )
        self.assertEqual(status, 413)
        data = json.loads(body.decode("utf-8"))
        self.assertFalse(data.get("success"))
        self.assertIn("Payload Too Large", data.get("error", ""))
        self.assertEqual(headers.get("connection"), "close")

    # -------------------------------------------------------------------------
    # 4. Некорректный или отрицательный Content-Length возвращает 413
    # -------------------------------------------------------------------------
    def test_04_invalid_and_negative_content_length_returns_413(self):
        """4. Некорректный или отрицательный Content-Length отвергается с кодом 413."""
        # Non-integer header
        status, _, body = self._send_raw_http(
            "POST",
            "/api/auth/login",
            headers={"Content-Length": "not_a_number"},
        )
        self.assertEqual(status, 413)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("некорректный", data.get("error", "").lower())

        # Negative header
        status, _, body = self._send_raw_http(
            "POST",
            "/api/auth/login",
            headers={"Content-Length": "-500"},
        )
        self.assertEqual(status, 413)

    # -------------------------------------------------------------------------
    # 5. Пустые тела запросов (Content-Length: 0 или отсутствие заголовка)
    # -------------------------------------------------------------------------
    def test_05_empty_or_missing_content_length_handled_gracefully(self):
        """5. Запросы с Content-Length: 0 или отсутствующим заголовком не вызывают 413."""
        # Missing Content-Length on /api/likes/toggle with empty body
        status, _, body = self._send_raw_http(
            "POST",
            "/api/likes/toggle",
            headers={},
        )
        # Should return 401 Unauthorized (since user is not logged in), NOT 413
        self.assertEqual(status, 401)

        # Content-Length: 0 on /api/moderation/submit
        status, _, body = self._send_raw_http(
            "POST",
            "/api/moderation/submit",
            headers={"Content-Length": "0"},
        )
        # Guest request with empty body returns 401
        self.assertEqual(status, 401)

    # -------------------------------------------------------------------------
    # 6. Защита от zlib-бомб в PNG: генератор zlib-бомбы отсекается с ImageDecodeError
    # -------------------------------------------------------------------------
    def test_06_png_zlib_bomb_rejected_by_decoder_without_oom(self):
        """6. Декодер PNG отсекает zip/zlib-бомбу с ImageDecodeError без OOM и зависания."""
        # A 1x1 PNG whose IDAT decompresses to 5 MB of zeros
        # Compressed IDAT payload is ~5 KB, while decompressed exceeds 1 MB limit for a 1x1 image
        bomb_png = _build_png_bytes(1, 1, b"\x00" * (5 * 1024 * 1024))
        self.assertLess(len(bomb_png), 10 * 1024, "Zip bomb must be tightly compressed")

        start_t = time.time()
        # Direct decoder call must raise ImageDecodeError
        with self.assertRaises(ImageDecodeError) as ctx:
            _decode_png(bomb_png)
        elapsed = time.time() - start_t

        self.assertIn("Превышен лимит размера распакованных данных PNG (подозрение на zip-бомбу).", str(ctx.exception))
        self.assertLess(elapsed, 0.2, "Zip bomb check must terminate in milliseconds")

        # Calling decode_and_validate_image must return False and appropriate error
        ok, err_msg, meta = decode_and_validate_image(bomb_png)
        self.assertFalse(ok)
        self.assertIn("Превышен лимит размера распакованных данных PNG (подозрение на zip-бомбу).", err_msg)
        self.assertIsNone(meta)

    def test_06b_png_zlib_bomb_with_large_dimensions_capped_at_max_decompressed(self):
        """6b. PNG с крупными заявленными размерами строго ограничен MAX_PNG_DECOMPRESSED_BYTES (60 МБ)."""
        # If dimensions are 5000x5000, max allowed is strictly capped at 60 MB
        # We test that a stream exceeding 60 MB raises ImageDecodeError
        bomb_65mb = _build_png_bytes(5000, 5000, b"\x00" * (65 * 1024 * 1024))
        with self.assertRaises(ImageDecodeError) as ctx:
            _decode_png(bomb_65mb)
        self.assertIn("подозрение на zip-бомбу", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 7. Загрузка PNG zip-бомбы через POST /api/media/upload отсекается с 400
    # -------------------------------------------------------------------------
    def test_07_media_upload_png_bomb_rejected(self):
        """7. Отправка zip-бомбы PNG в POST /api/media/upload отклоняется сервером."""
        bomb_png = _build_png_bytes(1, 1, b"\x00" * (5 * 1024 * 1024))

        # 1. As raw binary
        req = urllib.request.Request(
            f"{self.base_url}/api/media/upload",
            data=bomb_png,
            headers={**upload_auth_headers(self.db_path), "Content-Type": "image/png"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req)
            self.fail("Expected HTTPError 400 for PNG zip-bomb")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            data = json.loads(e.read().decode("utf-8"))
            self.assertFalse(data.get("success"))
            self.assertIn("подозрение на zip-бомбу", data.get("error", ""))

        # 2. As JSON Data URI
        b64 = base64.b64encode(bomb_png).decode("ascii")
        data_uri = f"data:image/png;base64,{b64}"
        json_payload = json.dumps({"image": data_uri}).encode("utf-8")
        req_json = urllib.request.Request(
            f"{self.base_url}/api/media/upload",
            data=json_payload,
            headers={**upload_auth_headers(self.db_path), "Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req_json)
            self.fail("Expected HTTPError 400 for PNG zip-bomb via data URI")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            data = json.loads(e.read().decode("utf-8"))
            self.assertFalse(data.get("success"))
            self.assertIn("подозрение на zip-бомбу", data.get("error", ""))

    # -------------------------------------------------------------------------
    # 8. Легитимные запросы нормального размера (JSON и медиа) успешно принимаются
    # -------------------------------------------------------------------------
    def test_08_legitimate_json_and_media_requests_succeed(self):
        """8. Легитимные JSON-запросы и медиа допустимого размера успешно принимаются и обрабатываются."""
        # 1. Successful JSON login
        login_res, cookie = self._login("alice_legit", "Alice Legit", role="user")
        self.assertTrue(login_res.get("success"))
        self.assertIsNotNone(cookie)

        # 2. Successful legitimate media upload (1x1 PNG)
        # 1 filter byte + 4 RGBA bytes = 5 bytes uncompressed
        valid_png = _build_png_bytes(1, 1, b"\x00\xff\x00\x00\xff")
        req = urllib.request.Request(
            f"{self.base_url}/api/media/upload",
            data=valid_png,
            headers={**upload_auth_headers(self.db_path), "Content-Type": "image/png"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            upload_data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(upload_data.get("success"))
            self.assertTrue(upload_data.get("url").startswith("/media/"))
            self.assertEqual(upload_data.get("meta", {}).get("format"), "png")

        # 3. Successful legitimate moderation submit
        submit_payload = {
            "draftId": "draft_legit_001",
            "title": "Легитимная статья о безопасности",
            "html": "<p>Безопасный контент без превышения лимитов размера.</p>",
            "delta": {"ops": [{"insert": "Безопасный контент..."}]},
            "publicationSettings": {
                "author": "Alice Legit",
                "authorRole": "Разработчик",
                "targetAudience": "developers",
                "topics": ["security-architecture"],
                "keywords": ["streaming", "security"],
                "format": "article",
                "complexity": "medium",
                "description": "Описание статьи длиной более пятидесяти символов для корректного прохождения валидации публикации.",
                "coverImage": upload_data["url"],
            },
            "idempotencyKey": "idemp_legit_001",
        }
        submit_data = json.dumps(submit_payload).encode("utf-8")
        req_submit = urllib.request.Request(
            f"{self.base_url}/api/moderation/submit",
            data=submit_data,
            headers={"Content-Type": "application/json", "Cookie": cookie},
            method="POST",
        )
        with urllib.request.urlopen(req_submit) as resp:
            self.assertEqual(resp.status, 200)
            res_submit = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(res_submit.get("success"))
            self.assertEqual(res_submit.get("status"), "pending_moderation")
            self.assertTrue(res_submit.get("submissionId"))

    # -------------------------------------------------------------------------
    # 9. Проверка лимитов на всех зарегистрированных POST-эндпоинтах
    # -------------------------------------------------------------------------
    def test_09_all_post_endpoints_enforce_body_limit(self):
        """9. Все POST-эндпоинты гарантированно возвращают HTTP 413 при превышении лимита."""
        all_post_endpoints = [
            "/api/auth/login",
            "/api/auth/logout",
            "/api/companies",
            "/api/clubs",
            "/api/likes/toggle",
            "/api/articles/test_art_01/like",
            "/api/subscriptions/toggle",
            "/api/exceptions/toggle",
            "/api/notifications/read",
            "/api/articles/test_art_01/comments",
            "/api/comments",
            "/api/user/feed-settings",
            "/api/user/profile",
            "/api/moderation/submit",
        ]
        oversized = MAX_JSON_BODY_BYTES + 8192
        for ep in all_post_endpoints:
            status, headers, body = self._send_raw_http(
                "POST",
                ep,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(oversized),
                },
            )
            self.assertEqual(status, 413, f"Endpoint {ep} did not return 413 on oversized body")
            data = json.loads(body.decode("utf-8"))
            self.assertFalse(data.get("success"))
            self.assertIn("Payload Too Large", data.get("error", ""))

    # -------------------------------------------------------------------------
    # 10. Прямое тестирование потокового прерывания read_request_body
    # -------------------------------------------------------------------------
    def test_10_read_request_body_streaming_chunk_interruption(self):
        """10. Потоковое чтение чанками корректно прерывается при превышении лимита max_bytes."""
        import io

        class DummyHandler:
            def __init__(self, rfile, headers):
                self.rfile = rfile
                self.headers = headers
                self.closed = False
                self.last_status = None
                self.last_data = None

            def send_json_response(self, code, data, extra_headers=None):
                self.last_status = code
                self.last_data = data

            # Bind actual read_request_body from ModerationRequestHandler
            read_request_body = server.ModerationRequestHandler.read_request_body

        # Case A: stream 100 KB with max_bytes = 50 KB
        stream_data = b"X" * (100 * 1024)
        dummy = DummyHandler(
            rfile=io.BytesIO(stream_data),
            headers={"Content-Length": str(len(stream_data))}
        )
        res = dummy.read_request_body(max_bytes=50 * 1024)
        self.assertIsNone(res)
        self.assertEqual(dummy.last_status, 413)
        self.assertTrue(dummy.close_connection)

        # Case B: stream within max_bytes
        stream_data_ok = b"Y" * (30 * 1024)
        dummy_ok = DummyHandler(
            rfile=io.BytesIO(stream_data_ok),
            headers={"Content-Length": str(len(stream_data_ok))}
        )
        res_ok = dummy_ok.read_request_body(max_bytes=50 * 1024)
        self.assertEqual(res_ok, stream_data_ok)
        self.assertIsNone(dummy_ok.last_status)


if __name__ == "__main__":
    unittest.main()

