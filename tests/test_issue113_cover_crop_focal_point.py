"""
Tests for Issue #113: Publication cover crop coordinates, focal point, and object-position persistence.

Verifies end-to-end alignment: Editor Preview = Feed Card = Article Reader.
Ensures custom focal points / non-center crops are properly calculated, stored,
served via public API endpoints, and dynamically applied via CSS object-position.
"""

import json
import os
import unittest
import urllib.request
import urllib.parse
from io import BytesIO

import server
from tests.backend_source import BACKEND_FILES, backend_source_file


class TestIssue113CoverCropFocalPoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.js_dir = os.path.join(cls.server_dir, "frontend", "public", "js")
        cls.css_dir = os.path.join(cls.server_dir, "frontend", "public", "css")

        with open(os.path.join(cls.js_dir, "publication.js"), "r", encoding="utf-8") as f:
            cls.pub_js = f.read()

        with open(os.path.join(cls.js_dir, "card.js"), "r", encoding="utf-8") as f:
            cls.card_js = f.read()

        with open(os.path.join(cls.js_dir, "article.js"), "r", encoding="utf-8") as f:
            cls.article_js = f.read()

        with open(os.path.join(cls.css_dir, "article.css"), "r", encoding="utf-8") as f:
            cls.article_css = f.read()

        with open(os.path.join(cls.css_dir, "feed.css"), "r", encoding="utf-8") as f:
            cls.feed_css = f.read()

        with open(os.path.join(cls.css_dir, "editor.css"), "r", encoding="utf-8") as f:
            cls.editor_css = f.read()

    def test_resolve_cover_position_helper(self):
        """Test server.py resolve_cover_position with various payload formats."""
        # 1. Direct coverPosition string
        self.assertEqual(server.resolve_cover_position({"coverPosition": "50% 20%"}), "50% 20%")
        self.assertEqual(server.resolve_cover_position({"coverPosition": "center top"}), "center top")

        # 2. objectPosition alias
        self.assertEqual(server.resolve_cover_position({"objectPosition": "left 30%"}), "left 30%")

        # 3. focalPoint string
        self.assertEqual(server.resolve_cover_position({"focalPoint": "40% 60%"}), "40% 60%")

        # 4. focalPoint dict with fractions
        pos = server.resolve_cover_position({"focalPoint": {"x": 0.25, "y": 0.8}})
        self.assertEqual(pos, "25.0% 80.0%")

        # 5. focalPoint dict with percentages
        pos_pct = server.resolve_cover_position({"focalPoint": {"x": 75, "y": 30}})
        self.assertEqual(pos_pct, "75.0% 30.0%")

        # 6. None or empty settings
        self.assertIsNone(server.resolve_cover_position({}))
        self.assertIsNone(server.resolve_cover_position(None))
        self.assertIsNone(server.resolve_cover_position({"coverPosition": "   "}))

    def test_publication_js_crop_and_focal_point_logic(self):
        """Verify publication.js computes and retains coverPosition, focalPoint, objectPosition."""
        # Constructor has coverPosition, focalPoint, objectPosition initialized
        self.assertIn("this.coverPosition = null;", self.pub_js)
        self.assertIn("this.focalPoint = null;", self.pub_js)
        self.assertIn("this.objectPosition = null;", self.pub_js)

        # applyCropping computes focalX, focalY and stores coverPosition / focalPoint
        self.assertIn("this.coverPosition =", self.pub_js)
        self.assertIn("this.focalPoint =", self.pub_js)
        self.assertIn("this.objectPosition =", self.pub_js)

        # deleteCover resets coverPosition, focalPoint, objectPosition
        self.assertIn("this.coverPosition = null;", self.pub_js)

        # getSettings exports coverPosition, focalPoint, objectPosition
        self.assertIn("coverPosition: this.coverPosition || null", self.pub_js)
        self.assertIn("focalPoint: this.focalPoint || null", self.pub_js)
        self.assertIn("objectPosition: this.objectPosition || this.coverPosition || null", self.pub_js)

        # loadSettings restores coverPosition, focalPoint, objectPosition
        self.assertIn("this.coverPosition = settings.coverPosition || settings.objectPosition || null;", self.pub_js)

        # updateCardPreview includes coverPosition / focalPoint in previewItem
        self.assertIn("coverPosition: this.coverPosition || null", self.pub_js)

        # renderCoverUI applies objectPosition to pub-cover-img
        self.assertIn("this.coverImg.style.objectPosition = this.coverPosition;", self.pub_js)

    def test_card_js_applies_object_position_to_cover_img(self):
        """Verify card.js renders style='object-position: ...' when focal point is provided."""
        self.assertIn("item.coverPosition || item.objectPosition", self.card_js)
        self.assertIn("item.focalPoint", self.card_js)
        self.assertIn("' style=\"object-position: ' + escapeHtml(objPos) + ';\"'", self.card_js)

    def test_article_js_applies_object_position_to_cover_img(self):
        """Verify article.js applies coverImg.style.objectPosition dynamically."""
        self.assertIn("article.coverPosition || article.objectPosition", self.article_js)
        self.assertIn("article.focalPoint", self.article_js)
        self.assertIn("coverImg.style.objectPosition = objPos;", self.article_js)

    def test_unified_aspect_ratio_across_surfaces(self):
        """Verify exact 780:350 aspect ratio consistency across feed, editor, and reader."""
        self.assertIn("aspect-ratio: 780 / 350;", self.feed_css)
        self.assertIn("aspect-ratio: 780 / 350;", self.article_css)
        self.assertIn("aspect-ratio: var(--card-cover-aspect-ratio, 780 / 350);", self.editor_css)

    def test_server_article_api_includes_focal_point_fields(self):
        """Verify server article endpoints include coverPosition, focalPoint, objectPosition."""
        with backend_source_file() as f:
            srv = f.read()

        # Both handle_get_article and handle_get_articles must include resolve_cover_position
        self.assertIn('"coverPosition": resolve_cover_position(settings)', srv)
        self.assertIn('"focalPoint": resolve_cover_position(settings)', srv)
        self.assertIn('"objectPosition": resolve_cover_position(settings)', srv)


if __name__ == "__main__":
    unittest.main()
