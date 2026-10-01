# -*- coding: utf-8 -*-
"""
Tests for Mobile Phone Emulator on localhost.
Verifies that /mobile, /emulator, and /mobile.html work properly,
device presets are present, navigation and scaling controls exist,
header shortcuts are in place, and code hygiene rules are respected.
"""

import http.client
import os
import unittest
import urllib.parse
from server import create_server, DEFAULT_DB_PATH


class TestMobileEmulator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=DEFAULT_DB_PATH)
        cls.port = cls.httpd.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        import threading
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass

    def _get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", path)
        res = conn.getresponse()
        data = res.read().decode("utf-8", errors="replace")
        headers = dict(res.getheaders())
        conn.close()
        return res.status, headers, data

    def _head(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("HEAD", path)
        res = conn.getresponse()
        headers = dict(res.getheaders())
        conn.close()
        return res.status, headers

    def test_01_redirects_for_mobile_and_emulator(self):
        """Verifies that /mobile and /emulator redirect to /mobile.html."""
        for path in ("/mobile", "/emulator", "/mobile/", "/emulator/"):
            st, hd, _ = self._get(path)
            self.assertEqual(st, 302, f"Expected 302 on {path}, got {st}")
            self.assertEqual(hd.get("Location") or hd.get("location"), "/mobile.html")

            # Also check HEAD requests
            st_head, hd_head = self._head(path)
            self.assertEqual(st_head, 302, f"Expected 302 on HEAD {path}, got {st_head}")
            self.assertEqual(hd_head.get("Location") or hd_head.get("location"), "/mobile.html")

    def test_02_mobile_html_served_200(self):
        """Verifies that /mobile.html returns 200 OK and contains expected markup."""
        st, hd, body = self._get("/mobile.html")
        self.assertEqual(st, 200)
        ct = next((v for k, v in hd.items() if k.lower() == "content-type"), "")
        self.assertIn("text/html", ct)
        self.assertIn("SmartContractum", body)
        self.assertIn("Mobile Lab", body)
        self.assertIn('id="smartphoneFrame"', body)
        self.assertIn('id="phoneFrame"', body)
        self.assertIn('id="dynamicIsland"', body)
        self.assertIn('id="btnRotate"', body)
        self.assertIn('id="btnFit"', body)
        self.assertIn('id="btnHardwarePower"', body)
        self.assertIn('id="urlInput"', body)

    def test_03_assets_served_200(self):
        """Verifies that CSS and JS assets for emulator are properly served."""
        st, hd, css = self._get("/css/mobile-emulator.css")
        self.assertEqual(st, 200)
        ct_css = next((v for k, v in hd.items() if k.lower() == "content-type"), "")
        self.assertIn("text/css", ct_css)
        self.assertIn(".smartphone-frame", css)
        self.assertIn(".dynamic-island", css)

        st, hd, js = self._get("/js/mobile-emulator.js")
        self.assertEqual(st, 200)
        ct_js = next((v for k, v in hd.items() if k.lower() == "content-type"), "")
        self.assertTrue("javascript" in ct_js or "text/plain" in ct_js)
        self.assertIn("DEVICE_PRESETS", js)
        self.assertIn("iphone15pro", js)
        self.assertIn("autoScale", js)

    def test_04_device_presets_present(self):
        """Verifies that key device presets are defined in HTML and JS."""
        st, _, body = self._get("/mobile.html")
        self.assertEqual(st, 200)
        self.assertIn('value="iphone15pro"', body)
        self.assertIn('value="iphone14"', body)
        self.assertIn('value="iphonese"', body)
        self.assertIn('value="galaxys23"', body)
        self.assertIn('value="pixel7"', body)
        self.assertIn('value="ipadmini"', body)

    def test_05_header_shortcuts_in_feed_and_article(self):
        """Verifies that feed.html and article.html contain the mobile emulator shortcut button."""
        st, _, feed = self._get("/feed.html")
        self.assertEqual(st, 200)
        self.assertIn('id="btnMobileEmulator"', feed)
        self.assertIn('href="mobile.html?page=feed.html"', feed)

        st, _, art = self._get("/article.html")
        self.assertEqual(st, 200)
        self.assertIn('id="btnMobileEmulator"', art)
        self.assertIn('href="mobile.html?page=article.html"', art)

    def test_06_code_hygiene_zero_emojis(self):
        """Verifies zero emojis and clean code hygiene in created files."""
        files = [
            "frontend/public/mobile.html",
            "frontend/public/css/mobile-emulator.css",
            "frontend/public/js/mobile-emulator.js"
        ]
        for fpath in files:
            self.assertTrue(os.path.exists(fpath), f"File {fpath} must exist")
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                for line_no, line in enumerate(content.splitlines(), 1):
                    for ch in line:
                        self.assertLessEqual(ord(ch), 0x1F000, f"Emoji found in {fpath}:{line_no}: {ch}")


if __name__ == "__main__":
    unittest.main()
