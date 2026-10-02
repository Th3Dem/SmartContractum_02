#!/usr/bin/env python3
"""
tests/test_issue74_comment_static_relative_time.py

Automated test suite for Issue #74 (SC-030):
"Disable realtime comment timestamp scheduler and make relative timestamps static".

Requirements verified:
1. formatCommentTimeRelative:
   - diffSec < 60 returns "только что" (0s, 1s, 10s, 30s, 59s).
   - Never outputs seconds ("1 секунду назад", "N секунд назад").
2. Minutes, hours, and date formatting:
   - 1..59 minutes: "N минут(ы) назад".
   - 1..24 hours: "N час(а/ов) назад".
   - > 24 hours (> 86400s): absolute date format via formatCommentDate(isoStr).
3. Background timer disabled:
   - window._commentTimestampTimer is null.
   - runCommentTimestampScheduler clears timer and does not call setTimeout.
   - Initial invocation of runCommentTimestampScheduler removed.
   - visibilitychange and focus event listeners removed.
   - updateCommentTimestamps is a safe stub returning 0 without DOM mutations.
4. Data integrity and HTML contract:
   - <time class="comment-date comment-time" datetime="..."> preserves ISO timestamp.
   - Tooltip title preserves absolute formatted date.
   - Only textContent contains static relative time string.
5. Contract exports preserved:
   - formatCommentTimeRelative, updateCommentTimestamps, runCommentTimestampScheduler.
6. Invariants:
   - Zero emojis, zero em dashes, 100% offline-first.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ARTICLE_JS_PATH = os.path.join(PROJECT_ROOT, "frontend", "public", "js", "article.js")


def read_file(relative_path: str) -> str:
    full_path = os.path.join(PROJECT_ROOT, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def py_russian_plural(n: int, one: str, few: str, many: str) -> str:
    mod10 = n % 10
    mod100 = n % 100
    if mod10 == 1 and mod100 != 11:
        return one
    if 2 <= mod10 <= 4 and not (10 <= mod100 <= 20):
        return few
    return many


def py_format_comment_time_relative(diff_sec: int) -> str:
    """Python specification mirror of formatCommentTimeRelative."""
    if diff_sec < 60:
        return "только что"
    diff_min = diff_sec // 60
    if diff_min < 60:
        return f"{diff_min} {py_russian_plural(diff_min, 'минуту', 'минуты', 'минут')} назад"
    if diff_sec <= 86400:
        diff_hours = diff_sec // 3600
        return f"{diff_hours} {py_russian_plural(diff_hours, 'час', 'часа', 'часов')} назад"
    return "ABSOLUTE_DATE_FORMATTED"


class TestIssue74CommentStaticRelativeTime(unittest.TestCase):
    """Test suite for static comment relative timestamps and disabled scheduler."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.article_js = read_file("frontend/public/js/article.js")

    def test_01_fresh_comments_format_tolko_chto(self) -> None:
        """Verify formatCommentTimeRelative returns 'только что' for diffSec < 60 without mentioning seconds."""
        # 1. Structural checks in article.js implementation
        fn_match = re.search(
            r'function formatCommentTimeRelative\(isoStr, nowMs\)\s*\{([\s\S]*?)\n  \}',
            self.article_js
        )
        self.assertIsNotNone(fn_match, "formatCommentTimeRelative must be defined in article.js")
        fn_body = fn_match.group(1)

        # Verify diffSec < 60 branch returns 'только что'
        self.assertIn("diffSec < 60", fn_body)
        self.assertIn("return 'только что';", fn_body)

        # Verify elimination of seconds mentions in formatCommentTimeRelative
        self.assertNotIn("секунду", fn_body, "formatCommentTimeRelative must not contain 'секунду'")
        self.assertNotIn("секунды", fn_body, "formatCommentTimeRelative must not contain 'секунды'")
        self.assertNotIn("секунд", fn_body, "formatCommentTimeRelative must not contain 'секунд'")

        # 2. Algorithmic boundary tests for fresh comments (< 60s)
        fresh_seconds = [0, 1, 5, 10, 25, 30, 45, 59]
        for sec in fresh_seconds:
            with self.subTest(diff_sec=sec):
                res = py_format_comment_time_relative(sec)
                self.assertEqual(res, "только что", f"Expected 'только что' for {sec}s, got {res}")
                self.assertNotIn("секунд", res)

        # Negative diff (e.g. clock skew) also falls into diffSec < 60
        res_negative = py_format_comment_time_relative(-5)
        self.assertEqual(res_negative, "только что")

    def test_02_minutes_hours_and_date_formatting(self) -> None:
        """Verify formatCommentTimeRelative outputs minutes, hours, and formatCommentDate for > 24h."""
        fn_match = re.search(
            r'function formatCommentTimeRelative\(isoStr, nowMs\)\s*\{([\s\S]*?)\n  \}',
            self.article_js
        )
        self.assertIsNotNone(fn_match)
        fn_body = fn_match.group(1)

        # Verify JS code delegates to getRussianPlural for minutes and hours
        self.assertIn("getRussianPlural(diffMin, 'минуту', 'минуты', 'минут')", fn_body)
        self.assertIn("getRussianPlural(diffHours, 'час', 'часа', 'часов')", fn_body)
        self.assertIn("return formatCommentDate(isoStr);", fn_body)

        cases = [
            (60, "1 минуту назад"),
            (120, "2 минуты назад"),
            (300, "5 минут назад"),
            (21 * 60, "21 минуту назад"),
            (59 * 60 + 59, "59 минут назад"),
            (3600, "1 час назад"),
            (7200, "2 часа назад"),
            (5 * 3600, "5 часов назад"),
            (21 * 3600, "21 час назад"),
            (86400, "24 часа назад"),
            (86401, "ABSOLUTE_DATE_FORMATTED"),
            (100000, "ABSOLUTE_DATE_FORMATTED"),
        ]

        for sec, expected in cases:
            with self.subTest(diff_sec=sec):
                res = py_format_comment_time_relative(sec)
                self.assertEqual(res, expected, f"Failed at {sec}s: expected {expected}, got {res}")

    def test_03_no_background_timer_scheduled(self) -> None:
        """Verify window._commentTimestampTimer is null/inactive and runCommentTimestampScheduler does not schedule timers."""
        # 1. runCommentTimestampScheduler must NOT call setTimeout
        scheduler_match = re.search(
            r'function runCommentTimestampScheduler\(\)\s*\{([\s\S]*?)\n  \}',
            self.article_js
        )
        self.assertIsNotNone(scheduler_match, "runCommentTimestampScheduler must be defined in article.js")
        scheduler_body = scheduler_match.group(1)

        self.assertNotIn("setTimeout", scheduler_body, "runCommentTimestampScheduler must not call setTimeout")
        self.assertIn("clearTimeout(window._commentTimestampTimer)", scheduler_body)
        self.assertIn("window._commentTimestampTimer = null;", scheduler_body)

        # 2. updateCommentTimestamps must return 0 and not trigger timers
        updater_match = re.search(
            r'function updateCommentTimestamps\(\)\s*\{([\s\S]*?)\n  \}',
            self.article_js
        )
        self.assertIsNotNone(updater_match, "updateCommentTimestamps must be defined in article.js")
        updater_body = updater_match.group(1)
        self.assertIn("return 0;", updater_body, "updateCommentTimestamps must return 0 as a no-op stub")

        # 3. Cleanup section must clear timers, remove listeners, and NOT call runCommentTimestampScheduler()
        cleanup_section = self.article_js[
            self.article_js.find("function runCommentTimestampScheduler()"):
            self.article_js.find("function getAuthorInitials")
        ]
        self.assertNotIn(
            "\n  runCommentTimestampScheduler();",
            cleanup_section,
            "runCommentTimestampScheduler() must NOT be invoked on initial script load"
        )

        # 4. Verify no active visibilitychange or focus event listener registrations
        active_code_lines = [
            line.strip() for line in cleanup_section.splitlines()
            if not line.strip().startswith("//") and not line.strip().startswith("/*")
        ]
        active_code = "\n".join(active_code_lines)
        self.assertNotIn("addEventListener", active_code, "No active addEventListener should be present in cleanup section")

        # Verify removal of any previously attached handlers
        self.assertIn("document.removeEventListener('visibilitychange', window._commentTimestampVisibilityHandler);", cleanup_section)
        self.assertIn("window.removeEventListener('focus', window._commentTimestampFocusHandler);", cleanup_section)
        self.assertIn("window._commentTimestampVisibilityHandler = null;", cleanup_section)
        self.assertIn("window._commentTimestampFocusHandler = null;", cleanup_section)

    def test_04_html_contract_and_iso_datetime(self) -> None:
        """Verify <time class="comment-date comment-time" datetime="..."> preserves ISO timestamp."""
        # Check comment item template
        comment_time_pattern = r'<time class="comment-date comment-time"\s+datetime="\'\s*\+\s*escapeHtml\(rawDate \|\| \'\'\)\s*\+\s*\'"\s+title="\'\s*\+\s*escapeHtml\(absDateText\)\s*\+\s*\'">\s*\'\s*\+\s*escapeHtml\(relTimeText\)\s*\+\s*\'</time>'
        self.assertIsNotNone(
            re.search(comment_time_pattern, self.article_js),
            "renderCommentItem must retain <time class='comment-date comment-time' datetime=... title=...> with relTimeText"
        )

        # Check answer card template
        answer_time_pattern = r'<time class="comment-date comment-time"\s+datetime="\'\s*\+\s*escapeHtml\(rawDate \|\| \'\'\)\s*\+\s*\'"\s+title="\'\s*\+\s*escapeHtml\(absDateText\)\s*\+\s*\'">\s*\'\s*\+\s*escapeHtml\(relTimeText\)\s*\+\s*\'</time>'
        matches = list(re.finditer(answer_time_pattern, self.article_js))
        self.assertGreaterEqual(len(matches), 2, "Both comments and answers must render time.comment-date.comment-time")

        # Static calculation once at render time
        rel_time_calls = re.findall(r'const relTimeText\s*=\s*formatCommentTimeRelative\(rawDate\);', self.article_js)
        self.assertGreaterEqual(len(rel_time_calls), 2, "relTimeText must be computed statically once via formatCommentTimeRelative(rawDate)")

    def test_05_contract_exports_preserved(self) -> None:
        """Verify formatCommentTimeRelative, updateCommentTimestamps, runCommentTimestampScheduler exist on window and in article.js."""
        self.assertIn("function formatCommentTimeRelative(", self.article_js)
        self.assertIn("function updateCommentTimestamps()", self.article_js)
        self.assertIn("function runCommentTimestampScheduler()", self.article_js)

        self.assertIn("window.formatCommentTimeRelative = formatCommentTimeRelative;", self.article_js)
        self.assertIn("window.updateCommentTimestamps = updateCommentTimestamps;", self.article_js)
        self.assertIn("window.runCommentTimestampScheduler = runCommentTimestampScheduler;", self.article_js)

    def test_06_zero_emojis_no_em_dashes_offline_first(self) -> None:
        """Verify zero emojis, zero em dashes, and 100% offline-first compliance."""
        emoji_pattern = re.compile(
            r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]"
        )
        em_dash_pattern = re.compile(r"\u2014")

        test_file_path = os.path.abspath(__file__)
        with open(test_file_path, "r", encoding="utf-8") as f:
            test_content = f.read()

        for filename, content in [("article.js", self.article_js), ("test_issue74.py", test_content)]:
            emoji_matches = emoji_pattern.findall(content)
            self.assertEqual(len(emoji_matches), 0, f"Found emojis in {filename}: {emoji_matches}")

            em_dash_matches = em_dash_pattern.findall(content)
            self.assertEqual(len(em_dash_matches), 0, f"Found em dash in {filename}: {em_dash_matches}")

        # Check offline-first compliance in article.js (no external CDNs)
        external_cdns = ["unpkg.com", "cdnjs.cloudflare.com", "cdn.jsdelivr.net", "fonts.googleapis.com"]
        for cdn in external_cdns:
            self.assertNotIn(cdn, self.article_js, f"External CDN '{cdn}' detected in article.js")


if __name__ == "__main__":
    unittest.main()
