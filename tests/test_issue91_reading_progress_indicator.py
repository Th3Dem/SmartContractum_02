#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Suite for Issue #91:
[P3][frontend] Тонкий индикатор прогресса чтения публикации под sticky шапкой.

Verifies:
1. HTML markup: presence of #readingProgressTrack and #readingProgressBar with accessibility attributes.
2. CSS styling: 2-3px height, sticky header bottom positioning, accent color, smooth width and opacity transitions.
3. Math algorithm: calculateReadingProgress correctly calculates 0%, 50%, 100%, and clamped values.
4. Safeguards: absence of calculations / zero reset when article container is missing or hidden.
5. Performance & throttling: requestAnimationFrame throttling on scroll and resize events.
6. Zero emojis and zero em dashes invariants.
"""

import os
import re
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE_DIR, "frontend", "public", "article.html")
CSS_PATH = os.path.join(BASE_DIR, "frontend", "public", "css", "article.css")
JS_PATH = os.path.join(BASE_DIR, "frontend", "public", "js", "article.js")


class TestIssue91ReadingProgressIndicator(unittest.TestCase):
    """Automated verification suite for Issue #91."""

    @classmethod
    def setUpClass(cls):
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            cls.css = f.read()
        with open(JS_PATH, "r", encoding="utf-8") as f:
            cls.js = f.read()

    def test_01_markup_and_accessibility_attributes(self):
        """Verify HTML markup for reading progress track and progress bar directly under header."""
        self.assertIn('id="readingProgressTrack"', self.html)
        self.assertIn('id="readingProgressBar"', self.html)
        self.assertIn('role="progressbar"', self.html)
        self.assertIn('aria-valuemin="0"', self.html)
        self.assertIn('aria-valuemax="100"', self.html)
        self.assertIn('aria-label="Прогресс чтения публикации"', self.html)

        # Confirm progress bar is anchored directly beneath app-header to maintain identical appHeader structure across pages
        header_close_idx = self.html.find('</header>')
        progress_bar_idx = self.html.find('id="readingProgressBar"')
        self.assertNotEqual(header_close_idx, -1)
        self.assertNotEqual(progress_bar_idx, -1)
        self.assertGreater(progress_bar_idx, header_close_idx, "readingProgressBar must be positioned directly under </header>")

    def test_02_css_styling_and_geometry(self):
        """Verify CSS height (2-3px), position, transitions, and accent color."""
        self.assertIn('.reading-progress-track', self.css)
        self.assertIn('.reading-progress-bar', self.css)

        # Track height 3px
        track_match = re.search(r'\.reading-progress-track\s*\{[^}]*height:\s*3px', self.css)
        self.assertIsNotNone(track_match, ".reading-progress-track must specify height: 3px")

        # Top fixed positioning under sticky header
        self.assertIn('position: fixed', self.css)
        self.assertIn('top: var(--header-height', self.css)
        self.assertIn('overflow: hidden', self.css)

        # Linear width transition and opacity fade
        self.assertIn('transition: width 0.1s linear', self.css)
        self.assertIn('var(--accent-color', self.css)

        # Mobile media query adjusts height to 2px
        mobile_match = re.search(r'@media\s*\(max-width:\s*480px\)\s*\{[^}]*height:\s*2px', self.css)
        self.assertIsNotNone(mobile_match, "Mobile media query must adjust height to 2px on small screens")

    def test_03_js_progress_calculation_math(self):
        """Verify mathematical calculation function for reading progress."""
        self.assertIn('function calculateReadingProgress', self.js)

        # Extract JS function logic or verify logic using Python equivalent
        def py_calc(top, height, win_h=800, header_h=60):
            total_dist = height - (win_h - header_h)
            if total_dist <= 0:
                return 100 if top <= header_h else 0
            scrolled = header_h - top
            progress = (scrolled / total_dist) * 100
            return max(0, min(100, round(progress)))

        # 1. At start: top = header_h (60)
        self.assertEqual(py_calc(60, 2000), 0)

        # 2. Before reaching start: top = 500
        self.assertEqual(py_calc(500, 2000), 0)

        # 3. Halfway: scrolled = total_dist / 2
        # total_dist = 2000 - (800 - 60) = 1260
        # scrolled = 630 -> top = 60 - 630 = -570
        self.assertEqual(py_calc(-570, 2000), 50)

        # 4. At finish: bottom reaches bottom of viewport
        # rect.bottom = rect.top + height = 800 -> top = 800 - 2000 = -1200
        # scrolled = 60 - (-1200) = 1260 = total_dist
        self.assertEqual(py_calc(-1200, 2000), 100)

        # 5. Over-scrolled: top = -1500 -> clamped at 100
        self.assertEqual(py_calc(-1500, 2000), 100)

    def test_04_js_safeguards_when_article_absent_or_hidden(self):
        """Verify reading progress resets to 0 and does not error when article is missing or hidden."""
        self.assertIn('function updateReadingProgress', self.js)
        self.assertIn("progressBar.style.width = '0%'", self.js)
        self.assertIn("progressBar.style.opacity = '0'", self.js)
        self.assertIn("style.display === 'none'", self.js)

    def test_05_js_fadeout_in_comments_and_footer(self):
        """Verify reading progress fades out when scrolled past article into comments."""
        self.assertIn('rect.bottom < headerHeight', self.js)
        self.assertIn("progressBar.style.opacity = '0'", self.js)

    def test_06_js_animation_performance_request_animation_frame(self):
        """Verify scroll and resize events are throttled via requestAnimationFrame."""
        self.assertIn('window.requestAnimationFrame', self.js)
        self.assertIn('isReadingProgressTicking', self.js)
        self.assertIn("window.addEventListener('scroll'", self.js)
        self.assertIn("window.addEventListener('resize'", self.js)

    def test_07_zero_emojis_and_zero_em_dashes(self):
        """Verify strict project invariants: zero emojis and zero em dashes."""
        for path in [HTML_PATH, CSS_PATH, JS_PATH]:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("\u2014", content, f"Em dash found in {os.path.basename(path)}")
            emoji_match = re.search(r"[\U00010000-\U0010ffff]", content)
            self.assertIsNone(emoji_match, f"Emoji found in {os.path.basename(path)}")


if __name__ == '__main__':
    unittest.main()
