#!/usr/bin/env python3
"""
tests/test_issue6_sc003_html_sanitization.py

Comprehensive regression and security test suite for Issue #6 (SC-003):
«Серверная allowlist-санитизация HTML публикаций от сохраненного XSS».

Acceptance Criteria / Test Cases:
1. Тест 1: Удаление тегов <script> и их содержимого (<script>alert('xss')</script>).
2. Тест 2: Удаление обработчиков событий onerror, onload, onclick и любых on* из допустимых тегов (<img src="x" onerror="alert(1)"> -> <img src="x">).
3. Тест 3: Блокировка опасных схем href="javascript:alert(1)" и vbscript:.
4. Тест 4: Удаление <iframe>, <object>, <embed>.
5. Тест 5: Сохранение легитимного форматирования Quill (заголовки, списки, таблицы, блоки кода, форматирование текста, безопасные ссылки и изображения).
6. Тест 6: Сквозной тест через API POST /api/moderation/submit: отправка вредоносного HTML сохраняет в БД санитизированный вариант.
"""

import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

import server
from server import (
    ArticleHTMLSanitizer,
    HTMLSanitizer,
    compute_snapshot_hash,
    create_server,
    has_valid_article_text,
    init_db,
    sanitize_article_html,
    validate_submission_payload,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue6SC003HTMLSanitization(unittest.TestCase):
    """Test suite for server-side HTML allowlist sanitization against stored XSS."""

    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue6_sc003.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
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
        cls.server_thread.join(timeout=2)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _login(self, user_id: str, name: str = "Test User", role: str = "user"):
        payload = {"userId": user_id, "name": name, "role": role}
        status, data, cookie = self._post_json("/api/auth/login", payload)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("authenticated"))
        return data, cookie

    def _post_json(self, path: str, payload: dict, cookie: str = None):
        h = {"Content-Type": "application/json"}
        if cookie:
            h["Cookie"] = cookie
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=h,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data, resp.headers.get("Set-Cookie")
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode("utf-8"))
            except Exception:
                data = {"error": str(e)}
            e.close()
            return e.code, data, e.headers.get("Set-Cookie")

    # =========================================================================
    # Тест 1: Удаление тегов <script> и их содержимого
    # =========================================================================
    def test_01_script_tags_and_content_removed(self):
        """Тест 1: Полное удаление тегов <script> и исполняемого JS-кода внутри них."""
        # 1a. Базовый вектор <script>alert('xss')</script>
        html_input = "<script>alert('xss')</script>"
        result = sanitize_article_html(html_input)
        self.assertEqual(result, "")
        self.assertNotIn("script", result.lower())
        self.assertNotIn("alert", result)

        # 1b. Скрипт в верхнем регистре <SCRIPT>
        upper_script = "<SCRIPT type=\"text/javascript\">alert(document.cookie);</SCRIPT>"
        self.assertEqual(sanitize_article_html(upper_script), "")

        # 1c. Скрипт со внешним источником src
        ext_script = "<script src=\"https://evil.example.com/exploit.js\"></script>"
        self.assertEqual(sanitize_article_html(ext_script), "")

        # 1d. Вложенные скрипты
        nested_script = "<script><script>alert('nested')</script></script>"
        self.assertEqual(sanitize_article_html(nested_script), "")

        # 1e. Скрипт внутри легитимного текста
        mixed = "<p>Безопасный параграф.<script>alert('xss')</script> Продолжение текста.</p>"
        cleaned_mixed = sanitize_article_html(mixed)
        self.assertEqual(cleaned_mixed, "<p>Безопасный параграф. Продолжение текста.</p>")
        self.assertNotIn("alert", cleaned_mixed)

        # 1f. Незакрытый тег <script>
        unclosed = "<script>alert('unclosed')"
        self.assertEqual(sanitize_article_html(unclosed), "")

    # =========================================================================
    # Тест 2: Удаление обработчиков событий onerror, onload, onclick и любых on*
    # =========================================================================
    def test_02_event_handlers_removed(self):
        """Тест 2: Удаление обработчиков событий onerror, onload, onclick и любых on* из допустимых тегов."""
        # 2a. <img src="x" onerror="alert(1)"> -> <img src="x">
        img_onerror = '<img src="x" onerror="alert(1)">'
        self.assertEqual(sanitize_article_html(img_onerror), '<img src="x">')

        # 2b. Обработчик onclick у ссылки
        link_onclick = '<a href="https://smartcontractum.ru" onclick="alert(\'click\')">Ссылка</a>'
        self.assertEqual(
            sanitize_article_html(link_onclick),
            '<a href="https://smartcontractum.ru">Ссылка</a>'
        )

        # 2c. Обработчики событий на разных тегах
        tags_with_events = (
            '<p onmouseover="alert(\'hover\')">Параграф</p>'
            '<div onload="alert(\'div\')">Блок</div>'
            '<h1 ONCLICK="alert(\'title\')">Заголовок</h1>'
            '<span onfocus="alert(\'focus\')">Текст</span>'
        )
        cleaned = sanitize_article_html(tags_with_events)
        self.assertNotIn("onmouseover", cleaned.lower())
        self.assertNotIn("onload", cleaned.lower())
        self.assertNotIn("onclick", cleaned.lower())
        self.assertNotIn("onfocus", cleaned.lower())
        self.assertIn("<p>Параграф</p>", cleaned)
        self.assertIn("<div>Блок</div>", cleaned)
        self.assertIn("<h1>Заголовок</h1>", cleaned)
        self.assertIn("<span>Текст</span>", cleaned)

        # 2d. <svg onload=...>: тег <svg> не разрешен и удаляется вместе с атрибутом onload
        svg_vector = '<svg onload="alert(\'svg\')">Графика</svg>'
        cleaned_svg = sanitize_article_html(svg_vector)
        self.assertNotIn("onload", cleaned_svg.lower())
        self.assertNotIn("<svg", cleaned_svg.lower())
        self.assertEqual(cleaned_svg, "Графика")

    # =========================================================================
    # Тест 3: Блокировка опасных схем href="javascript:alert(1)" и vbscript:
    # =========================================================================
    def test_03_dangerous_schemes_blocked(self):
        """Тест 3: Блокировка опасных схем javascript:, vbscript:, data: в href и src."""
        # 3a. javascript: в href
        js_link = '<a href="javascript:alert(1)">Опасная ссылка</a>'
        self.assertEqual(sanitize_article_html(js_link), '<a>Опасная ссылка</a>')

        # 3b. vbscript: в href
        vbs_link = '<a href="vbscript:msgbox(1)">VB ссылка</a>'
        self.assertEqual(sanitize_article_html(vbs_link), '<a>VB ссылка</a>')

        # 3c. data:text/html в href
        data_link = '<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">Data ссылка</a>'
        self.assertEqual(sanitize_article_html(data_link), '<a>Data ссылка</a>')

        # 3d. Обфускация пробелами и спецсимволами (табы, переносы строк, сущности)
        obfuscated_links = [
            '<a href="  javascript:alert(1)  ">Пробелы</a>',
            '<a href="java\tscript:alert(1)">Табуляция</a>',
            '<a href="java\nscript:alert(1)">Перевод строки</a>',
            '<a href="jav&#x09;ascript:alert(1)">HTML-сущность таба</a>',
            '<a href="javascript&colon;alert(1)">Сущность двоеточия</a>',
            '<a href="JAVASCRIPT:alert(1)">Верхний регистр</a>',
        ]
        for obf in obfuscated_links:
            res = sanitize_article_html(obf)
            self.assertNotIn("javascript", res.lower(), f"Не удалось заблокировать обфусцированный href: {obf}")
            self.assertNotIn("href", res.lower(), f"href не был удален при обфускации: {obf}")

        # 3e. Опасные схемы в <img> src
        bad_img = '<img src="javascript:alert(\'img\')">'
        self.assertEqual(sanitize_article_html(bad_img), '<img>')

        # 3f. data:image/svg+xml (может содержать исполняемый SVG) блокируется в <img>
        svg_data_img = '<img src="data:image/svg+xml;base64,PHN2ZyBvbmxvYWQ9YWxlcnQoMSk+">'
        self.assertEqual(sanitize_article_html(svg_data_img), '<img>')

        # 3g. Легитимные схемы и пути разрешены
        safe_links = (
            '<a href="https://example.com/docs">HTTPS</a>'
            '<a href="http://example.com/api">HTTP</a>'
            '<a href="mailto:support@smartcontractum.ru">Mailto</a>'
            '<a href="/media/paper.pdf">Абсолютный путь</a>'
            '<a href="./article-123">Относительный путь</a>'
            '<a href="#section-top">Якорь</a>'
        )
        cleaned_safe = sanitize_article_html(safe_links)
        self.assertIn('href="https://example.com/docs"', cleaned_safe)
        self.assertIn('href="http://example.com/api"', cleaned_safe)
        self.assertIn('href="mailto:support@smartcontractum.ru"', cleaned_safe)
        self.assertIn('href="/media/paper.pdf"', cleaned_safe)
        self.assertIn('href="./article-123"', cleaned_safe)
        self.assertIn('href="#section-top"', cleaned_safe)

    # =========================================================================
    # Тест 4: Удаление <iframe>, <object>, <embed>
    # =========================================================================
    def test_04_dangerous_containers_removed(self):
        """Тест 4: Полное удаление опасных тегов-контейнеров <iframe>, <object>, <embed> и др."""
        # 4a. <iframe>
        iframe_payload = '<iframe src="https://phishing.example.com">Внутренний текст</iframe>'
        self.assertEqual(sanitize_article_html(iframe_payload), "")

        # 4b. <object>
        object_payload = '<object data="exploit.swf"><param name="allowScriptAccess" value="always"></object>'
        self.assertEqual(sanitize_article_html(object_payload), "")

        # 4c. <embed>
        embed_payload = '<embed src="exploit.swf" type="application/x-shockwave-flash">'
        self.assertEqual(sanitize_article_html(embed_payload), "")

        # 4d. Другие запрещенные теги: <style>, <form>, <input>, <applet>, <base>, <meta>
        other_forbidden = (
            '<style>body { display: none; }</style>'
            '<form action="https://evil.com"><input type="password" name="pwd"><button>Вход</button></form>'
            '<meta http-equiv="refresh" content="0;url=https://evil.com">'
            '<base href="https://evil.com/">'
        )
        self.assertEqual(sanitize_article_html(other_forbidden), "")

    # =========================================================================
    # Тест 5: Сохранение легитимного форматирования Quill
    # =========================================================================
    def test_05_quill_formatting_preserved(self):
        """Тест 5: Сохранение легитимной разметки Quill (заголовки, списки, таблицы, код, текст, ссылки, картинки)."""
        quill_html = (
            '<h1>Заголовок 1</h1>'
            '<h2>Заголовок 2</h2>'
            '<h3>Заголовок 3</h3>'
            '<p>Обычный параграф с <strong>жирным</strong>, <em>курсивом</em>, '
            '<u>подчеркиванием</u>, <s>зачеркиванием</s>, <sub>нижним</sub> и <sup>верхним</sup> индексами.</p>'
            '<blockquote>Цитата нормативного документа</blockquote>'
            '<ul><li>Элемент списка 1</li><li>Элемент списка 2</li></ul>'
            '<ol><li>Первый шаг</li><li>Второй шаг</li></ol>'
            '<pre class="ql-syntax"><code data-language="python">def verify_contract():\n    return True</code></pre>'
            '<table class="editor-table">'
            '<thead><tr><th colspan="2">Заголовок</th></tr></thead>'
            '<tbody><tr><td>Данные 1</td><td>Данные 2</td></tr></tbody>'
            '</table>'
            '<p><a href="https://smartcontractum.ru/rules" target="_blank" rel="noopener noreferrer" class="link-external" title="Правила">Правила</a></p>'
            '<p><img src="/media/diagram.png" alt="Схема" width="600" height="400" class="responsive-image" loading="lazy"></p>'
            '<p><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==" alt="Точка"></p>'
            '<hr>'
            '<p><br></p>'
        )

        cleaned = sanitize_article_html(quill_html)

        # Проверка сохранения основных структурных блоков
        self.assertIn('<h1>Заголовок 1</h1>', cleaned)
        self.assertIn('<h2>Заголовок 2</h2>', cleaned)
        self.assertIn('<h3>Заголовок 3</h3>', cleaned)
        self.assertIn('<strong>жирным</strong>', cleaned)
        self.assertIn('<em>курсивом</em>', cleaned)
        self.assertIn('<u>подчеркиванием</u>', cleaned)
        self.assertIn('<s>зачеркиванием</s>', cleaned)
        self.assertIn('<sub>нижним</sub>', cleaned)
        self.assertIn('<sup>верхним</sup>', cleaned)
        self.assertIn('<blockquote>Цитата нормативного документа</blockquote>', cleaned)
        self.assertIn('<ul><li>Элемент списка 1</li><li>Элемент списка 2</li></ul>', cleaned)
        self.assertIn('<ol><li>Первый шаг</li><li>Второй шаг</li></ol>', cleaned)
        self.assertIn('<pre class="ql-syntax"><code data-language="python">def verify_contract():\n    return True</code></pre>', cleaned)
        self.assertIn('<th colspan="2">Заголовок</th>', cleaned)
        self.assertIn('<td>Данные 1</td>', cleaned)
        self.assertIn('href="https://smartcontractum.ru/rules"', cleaned)
        self.assertIn('target="_blank"', cleaned)
        self.assertIn('rel="noopener noreferrer"', cleaned)
        self.assertIn('src="/media/diagram.png"', cleaned)
        self.assertIn('width="600"', cleaned)
        self.assertIn('height="400"', cleaned)
        self.assertIn('data:image/png;base64,', cleaned)
        self.assertIn('<hr>', cleaned)
        self.assertIn('<br>', cleaned)

        # Проверка валидности текста на санитизированном результате
        self.assertTrue(has_valid_article_text(cleaned))

    # =========================================================================
    # Тест 6: Сквозной тест через API POST /api/moderation/submit
    # =========================================================================
    def test_06_e2e_api_moderation_submit_stored_xss_sanitized(self):
        """Тест 6: Сквозной тест API: отправка вредоносного HTML сохраняет в БД санитизированный вариант."""
        # 1. Авторизация автора
        _, cookie = self._login("author_security_tester", "Тестировщик Безопасности", role="user")

        # 2. Формирование вредоносного payload со Stored XSS векторами
        malicious_html = (
            '<h2>Безопасный раздел публикации</h2>'
            '<p>Корректный текст о смарт-контрактах.</p>'
            '<script>alert("STORED_XSS_EXPLOIT")</script>'
            '<img src="/media/valid_chart.png" onerror="alert(\'XSS_ONERROR\')">'
            '<a href="javascript:alert(\'XSS_LINK\')">Вредоносная ссылка</a>'
            '<iframe src="https://attacker.example.com"></iframe>'
        )

        payload = {
            "draftId": "draft_xss_prevention_001",
            "title": "Статья с попыткой внедрения сохраненного XSS",
            "html": malicious_html,
            "publicationSettings": {
                "targetAudience": "developers",
                "topics": ["security"],
                "keywords": ["xss", "санитизация", "гост"],
                "description": "Тестирование серверной allowlist-санитизации входящего HTML публикаций на платформе Antigravity Writer.",
                "format": "article",
                "complexity": "hard"
            },
            "idempotencyKey": "idemp_xss_test_001"
        }

        # 3. Отправка запроса на публикацию
        status_code, response_data, _ = self._post_json("/api/moderation/submit", payload, cookie=cookie)
        self.assertEqual(status_code, 200)
        self.assertTrue(response_data.get("success"))
        self.assertEqual(response_data.get("status"), "pending_moderation")

        submission_id = response_data.get("submissionId")
        self.assertTrue(submission_id.startswith("sub_"))

        # 4. Проверка сохраненного снапшота в SQLite базе данных
        conn = server.get_db_connection(self.db_path)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM moderation_submissions WHERE id = ?", (submission_id,))
            row = cur.fetchone()
            self.assertIsNotNone(row)

            saved_html = row["article_html"]

            # Убеждаемся, что в базе НЕТ следов XSS-атак
            self.assertNotIn("<script", saved_html.lower())
            self.assertNotIn("stored_xss_exploit", saved_html.lower())
            self.assertNotIn("onerror", saved_html.lower())
            self.assertNotIn("xss_onerror", saved_html.lower())
            self.assertNotIn("javascript:", saved_html.lower())
            self.assertNotIn("xss_link", saved_html.lower())
            self.assertNotIn("<iframe", saved_html.lower())
            self.assertNotIn("attacker.example.com", saved_html.lower())

            # Убеждаемся, что легитимный контент сохранен
            self.assertIn("<h2>Безопасный раздел публикации</h2>", saved_html)
            self.assertIn("<p>Корректный текст о смарт-контрактах.</p>", saved_html)
            self.assertIn('<img src="/media/valid_chart.png">', saved_html)
            self.assertIn('<a>Вредоносная ссылка</a>', saved_html)

            # Проверяем, что snapshot_hash рассчитан строго от санитизированного HTML
            expected_hash = compute_snapshot_hash(
                payload["title"],
                saved_html,
                payload["publicationSettings"]
            )
            self.assertEqual(row["snapshot_hash"], expected_hash)
            self.assertEqual(response_data.get("snapshotHash"), expected_hash)
        conn.close()

        # 5. Попытка отправки черновика, состоящего ИСКЛЮЧИТЕЛЬНО из вредоносного скрипта
        script_only_payload = {
            "draftId": "draft_script_only_002",
            "title": "Статья только со скриптом",
            "html": "<script>alert('only script')</script>",
            "publicationSettings": payload["publicationSettings"],
            "idempotencyKey": "idemp_script_only_002"
        }
        status_bad, data_bad, _ = self._post_json("/api/moderation/submit", script_only_payload, cookie=cookie)
        self.assertEqual(status_bad, 400)
        self.assertFalse(data_bad.get("success"))
        self.assertIn("html", data_bad.get("fieldErrors", {}))


if __name__ == "__main__":
    unittest.main()
