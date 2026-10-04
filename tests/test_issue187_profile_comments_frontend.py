#!/usr/bin/env python3
"""
tests/test_issue187_profile_comments_frontend.py

Automated frontend test suite for Issue #187:
[P1][fullstack][PROFILE] Comments and search across author content.

Verifies:
1. Comments tab and count elements in profile.html:
   - Tab button id="tabProfileComments", data-tab="comments".
   - Count span id="profileTabCountComments".
   - Panel container id="profileTabComments" with sorting controls (sort=new / sort=rating),
     list id="profileCommentsList", actions id="profileCommentsActions",
     and load more button id="btnProfileLoadMoreComments".
   - Profile tabs toolbar with search input id="profileSearchInput" (.profile-search-input).
2. CSS styling in profile.css:
   - .profile-comment-item, .profile-comment-context, .profile-comment-snippet.
   - .profile-search-input, .profile-tabs-toolbar, .activity-badge-comment.
3. profile-page.js comments tab wiring and rendering:
   - setActiveTab handles 'comments'.
   - loadComments with race condition protection (commReqSeq, commAbortCtrl) and safe pagination.
   - renderCommentsTab displays comment card with parent context, snippet, rating, date, permalink.
   - Tab count badges updated with comments count from p.commentsCount / p.comments_count.
4. Activity feed renders comment items:
   - item.type === 'comment' displays context label, parent title, date, rating, permalink.
5. Search input triggers server query with q:
   - Input listener triggers server-side q parameter across active tab endpoints.
6. Invariants:
   - Zero emojis, zero em dashes, 100% offline-first.
"""

import os
import re
import unittest
import unicodedata

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
HTML_PATH = os.path.join(FRONTEND_DIR, "profile.html")
PAGE_JS_PATH = os.path.join(FRONTEND_DIR, "js", "profile-page.js")
CSS_PATH = os.path.join(FRONTEND_DIR, "css", "profile.css")


class TestIssue187ProfileCommentsFrontend(unittest.TestCase):
    """Verifies profile comments tab, search toolbar, and client rendering logic."""

    @classmethod
    def setUpClass(cls):
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()
        with open(PAGE_JS_PATH, "r", encoding="utf-8") as f:
            cls.page_js = f.read()
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            cls.css = f.read()
        with open(__file__, "r", encoding="utf-8") as f:
            cls.test_py = f.read()

    # =========================================================================
    # 1. profile.html Elements
    # =========================================================================

    def test_01_profile_html_comments_tab_and_counts(self):
        """Verify comments tab button, badge, panel, sorting and actions in profile.html."""
        # 1. Tab button id="tabProfileComments" and data-tab="comments"
        self.assertIn('id="tabProfileComments"', self.html, "Comments tab button id must be tabProfileComments")
        self.assertIn('data-tab="comments"', self.html, "Comments tab button must have data-tab='comments'")
        self.assertIn('aria-controls="profileTabComments"', self.html, "Tab button must control profileTabComments panel")

        # 2. Count span id="profileTabCountComments"
        self.assertIn('id="profileTabCountComments"', self.html, "Comments count badge must have id='profileTabCountComments'")

        # 3. Tab pane container id="profileTabComments"
        self.assertIn('id="profileTabComments"', self.html, "Comments tab panel must have id='profileTabComments'")
        self.assertIn('role="tabpanel"', self.html, "Tab panels must have role='tabpanel'")

        # 4. Sorting controls for comments (sort=new / sort=rating)
        self.assertIn('data-comm-sort="new"', self.html, "Comments sorting must include sort=new control")
        self.assertIn('data-comm-sort="rating"', self.html, "Comments sorting must include sort=rating control")

        # 5. Comments list container
        self.assertIn('id="profileCommentsList"', self.html, "Comments list container must have id='profileCommentsList'")

        # 6. Comments actions and load more button
        self.assertIn('id="profileCommentsActions"', self.html, "Comments actions wrapper must have id='profileCommentsActions'")
        self.assertIn('id="btnProfileLoadMoreComments"', self.html, "Load more comments button must have id='btnProfileLoadMoreComments'")

    def test_02_profile_html_search_toolbar(self):
        """Verify profile tabs toolbar with search input in profile.html."""
        self.assertIn('class="profile-tabs-toolbar"', self.html, "Toolbar container must have class profile-tabs-toolbar")
        self.assertIn('id="profileSearchInput"', self.html, "Search input must have id='profileSearchInput'")
        self.assertIn('class="profile-search-input"', self.html, "Search input must have class 'profile-search-input'")
        self.assertIn('id="btnProfileSearchClear"', self.html, "Clear search button must exist")

    # =========================================================================
    # 2. CSS Styling
    # =========================================================================

    def test_03_profile_css_styles_exist(self):
        """Verify styling for comment card and search toolbar elements in profile.css."""
        # Comment card classes
        self.assertIn(".profile-comment-item", self.css, "CSS must style .profile-comment-item")
        self.assertIn(".profile-comment-context", self.css, "CSS must style .profile-comment-context")
        self.assertIn(".profile-comment-snippet", self.css, "CSS must style .profile-comment-snippet")
        self.assertIn(".profile-comment-badge", self.css, "CSS must style .profile-comment-badge")
        self.assertIn(".profile-comment-parent-title", self.css, "CSS must style .profile-comment-parent-title")
        self.assertIn(".profile-comment-rating", self.css, "CSS must style .profile-comment-rating")
        self.assertIn(".profile-comment-link", self.css, "CSS must style .profile-comment-link")

        # Search toolbar classes
        self.assertIn(".profile-search-input", self.css, "CSS must style .profile-search-input")
        self.assertIn(".profile-tabs-toolbar", self.css, "CSS must style .profile-tabs-toolbar")
        self.assertIn(".profile-tabs-nav-wrap", self.css, "CSS must style .profile-tabs-nav-wrap")
        self.assertIn(".profile-search-wrap", self.css, "CSS must style .profile-search-wrap")

        # Activity feed comment badge
        self.assertIn(".activity-badge-comment", self.css, "CSS must style .activity-badge-comment")

    # =========================================================================
    # 3. profile-page.js Tab Handling & Comments Loading
    # =========================================================================

    def test_04_profile_page_js_wires_comments_tab(self):
        """Verify profile-page.js wires tab switching and count badges for comments."""
        # Tab names include comments
        self.assertIn("'comments'", self.page_js, "validTabs list must include 'comments'")
        self.assertIn("tabProfileComments", self.page_js, "tabProfileComments button element must be referenced")
        self.assertIn("profileTabComments", self.page_js, "profileTabComments panel element must be referenced")

        # Tab counts update
        self.assertIn("profileTabCountComments", self.page_js, "renderTabCounts must update profileTabCountComments")
        self.assertIn("commentsCount", self.page_js, "updateProfileStats must handle commentsCount")

    def test_05_profile_page_js_load_comments_and_race_protection(self):
        """Verify loadComments implements race protection and safe pagination."""
        match = re.search(r"function loadComments\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match, "loadComments function must be defined in profile-page.js")
        body = match.group(1)

        # Endpoint URL
        self.assertIn("/api/users/", body, "Must fetch from /api/users/<userId>/comments")
        self.assertIn("/comments", body, "Must query /comments endpoint")

        # Race protection with commReqSeq and commAbortCtrl
        self.assertIn("commReqSeq", body, "Must track request sequence via commReqSeq")
        self.assertIn("commAbortCtrl", body, "Must support cancellation via commAbortCtrl")
        self.assertIn("commAbortCtrl.abort()", body, "Must abort stale pending request")

        # Safe pagination
        self.assertNotIn("commOffset +=", body.split("fetch(")[0], "commOffset must not be incremented before fetch")
        self.assertIn("commOffset += incoming.length", body, "commOffset must be updated on successful fetch")
        self.assertIn("commHasMore = Boolean(data.hasMore)", body, "commHasMore must be assigned from response data")

        # Error state with retry
        self.assertIn("btnRetryComments", body, "Must provide retry button on comments error")

        # Sort and search query passed
        self.assertIn("commSort", body, "Must pass sort parameter commSort")
        self.assertIn("currentSearchQuery", body, "Must pass search query parameter if present")

    def test_06_profile_page_js_render_comments_tab(self):
        """Verify renderCommentsTab displays comment cards with parent context, snippet, rating, permalink."""
        match = re.search(r"function renderCommentsTab\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match, "renderCommentsTab function must be defined in profile-page.js")
        body = match.group(1)

        # Context link and label
        self.assertIn("profile-comment-context", body, "Must render .profile-comment-context")
        self.assertIn("profile-comment-parent-title", body, "Must render parent title link")
        self.assertIn("К материалу:", body, "Must display context label 'К материалу:'")

        # Snippet
        self.assertIn("profile-comment-snippet", body, "Must render comment snippet")

        # Rating and date
        self.assertIn("profile-comment-rating", body, "Must render comment rating")
        self.assertIn("profile-comment-date", body, "Must render comment date")

        # Permalink
        self.assertIn("profile-comment-link", body, "Must render comment permalink")
        self.assertIn("#comment-", body, "Permalink must target comment anchor #comment-<id>")

        # Actions toggle on hasMore
        self.assertIn("hasMore ? 'block' : 'none'", body, "Actions visibility must reflect hasMore")

    # =========================================================================
    # 4. Activity Feed Comments Rendering
    # =========================================================================

    def test_07_activity_feed_renders_comment_items(self):
        """Verify renderActivityFeed handles item.type === 'comment'."""
        match = re.search(r"function renderActivityFeed\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match, "renderActivityFeed function must be defined in profile-page.js")
        body = match.group(1)

        self.assertIn("item.type === 'comment'", body, "renderActivityFeed must check for item.type === 'comment'")
        self.assertIn("activity-badge-comment", body, "Comment activity must render .activity-badge-comment")
        self.assertIn("К материалу:", body, "Comment activity must render 'К материалу:' context label")
        self.assertIn("parentTitle", body, "Comment activity must display parentTitle")
        self.assertIn("activity-comment-permalink", body, "Comment activity must provide direct permalink link")

    # =========================================================================
    # 5. Search Input Triggers Server Query with ?q=
    # =========================================================================

    def test_08_search_input_triggers_server_query_q(self):
        """Verify profile tabs toolbar search input triggers server-side query with q."""
        # 1. Event listener for search input
        self.assertIn("profileSearchInput", self.page_js, "profileSearchInput listener must be wired")
        self.assertIn("triggerSearch", self.page_js, "triggerSearch handler must be defined")

        # 2. Debouncing and clear button
        self.assertIn("searchDebounceTimer", self.page_js, "Search must be debounced")
        self.assertIn("btnProfileSearchClear", self.page_js, "Clear search button must be wired")

        # 3. Server-side q parameter across endpoints
        self.assertIn("&q=", self.page_js, "Requests must append &q= parameter to server URLs")

        # 4. Exported search functions
        self.assertIn("triggerSearch: triggerSearch", self.page_js, "triggerSearch must be exported on SmartContractumProfilePage")
        self.assertIn("loadComments: loadComments", self.page_js, "loadComments must be exported on SmartContractumProfilePage")
        self.assertIn("renderCommentsTab: renderCommentsTab", self.page_js, "renderCommentsTab must be exported on SmartContractumProfilePage")

    # =========================================================================
    # 6. Strict Invariants
    # =========================================================================

    def test_09_strict_invariants(self):
        """Verify zero emojis, zero em dashes, and offline-first compliance across all modified files."""
        files = {
            "profile.html": self.html,
            "profile.css": self.css,
            "profile-page.js": self.page_js,
            "test_file": self.test_py,
        }

        for fname, content in files.items():
            # 1. Zero em dashes
            self.assertNotIn("\u2014", content, f"Em dash forbidden in {fname}")

            # 2. Zero emojis
            for ch in content:
                cp = ord(ch)
                if cp > 127:
                    cat = unicodedata.category(ch)
                    if cat in ("So", "Sk") or (0x1F000 <= cp <= 0x1FFFF):
                        self.fail(f"Emoji '{ch}' (U+{cp:04X}) forbidden in {fname}")

            # 3. 100% offline-first: no external CDN scripts, styles or fonts
            if fname in ("profile.html", "profile.css", "profile-page.js"):
                external_matches = re.findall(r'https?://[^\s\'"<>]+', content)
                for ext in external_matches:
                    # Allow internal/local documentation references, share links, or mock protocols
                    if any(allowed in ext for allowed in ["t.me/", "vk.com/", "connect.ok.ru/", "schema.org"]):
                        continue
                    # Ensure no CDN resource links are imported
                    self.assertNotIn(
                        "cdn", ext.lower(), f"External CDN link forbidden in {fname}: {ext}"
                    )
                    self.assertNotIn(
                        "unpkg", ext.lower(), f"External unpkg link forbidden in {fname}: {ext}"
                    )
                    self.assertNotIn(
                        "cdnjs", ext.lower(), f"External cdnjs link forbidden in {fname}: {ext}"
                    )


if __name__ == "__main__":
    unittest.main()
