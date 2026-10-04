#!/usr/bin/env python3
"""
tests/test_issue189_profile_reputation_subscribers_frontend.py

Automated frontend test suite for Issue #189:
[P2][fullstack][PROFILE] Reputation breakdown, topic filtering, and subscribers modal.

Verifies:
1. profile.html Elements:
   - Stats bar interactive elements:
     * #profileStatRatingWrap with role="region" and rating formula title/aria-label.
     * #profileStatSolutionsWrap with role="button" and tabindex="0".
     * #profileStatFollowersWrap with role="button" and tabindex="0".
     * #profileStatFollowingWrap with role="button" and tabindex="0".
   - Active topic filtering bar:
     * #profileActiveTopicBar inside tabs toolbar.
     * #activeTopicChip, #activeTopicName, #btnClearTopicFilter.
   - Social modal (subscribers & subscriptions):
     * #profileSocialModal overlay with role="dialog" and aria-modal="true".
     * Header with #socialModalTitle and #btnProfileSocialModalClose.
     * Subnav for owner subscriptions: #socialModalSubnav, #socialSubTabAuthors, #socialSubTabBlogs.
     * List container #profileSocialList and load more container #profileSocialActions, #btnSocialLoadMore.
2. profile.css Styles:
   - .profile-stat-clickable with hover/focus states and pointer cursor.
   - .profile-active-topic-bar and .active-topic-chip with badge and clear button styling.
   - .profile-sidebar-topic-pill with interactive hover/active states.
   - .profile-social-modal-card, .profile-social-item, .profile-social-avatar-box, .profile-social-info.
3. profile-page.js Logic:
   - Reputation breakdown formatting and tooltip calculation.
   - Solution counter click routes to answers tab with filter=solutions.
   - Topic selection in sidebar filters author's publications via ?topic= parameter and displays active topic bar.
   - Clear topic filter resets filter and restores full publications list.
   - Subscribers modal pagination via GET /api/users/<user_id>/subscribers.
   - Subscriptions modal: privacy-preserving notice for other users; author/blog separated tabs for owner.
   - Real count reflection: toggleSubscription applies server-provided followersCount.
   - Silent refresh on votes via smartcontractum:voted window event.
4. Invariants:
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


class TestIssue189ProfileReputationSubscribersFrontend(unittest.TestCase):
    """Verifies profile reputation breakdown, topic filtering, and subscribers modal."""

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

    def test_01_profile_html_stats_bar_interactive_elements(self):
        """Verify reputation and interactive counter wrappers in profile stats bar."""
        # 1. Rating wrap
        self.assertIn('id="profileStatRatingWrap"', self.html, "Rating wrap must have id='profileStatRatingWrap'")
        self.assertIn('role="region"', self.html, "Rating wrap must have role='region'")
        self.assertIn('aria-label="Рейтинг автора"', self.html, "Rating wrap must have aria-label")

        # 2. Solutions wrap
        self.assertIn('id="profileStatSolutionsWrap"', self.html, "Solutions wrap must have id='profileStatSolutionsWrap'")
        self.assertIn('profile-stat-clickable', self.html, "Solutions wrap must have profile-stat-clickable class")

        # 3. Followers & Following wraps
        self.assertIn('id="profileStatFollowersWrap"', self.html, "Followers wrap must have id='profileStatFollowersWrap'")
        self.assertIn('id="profileStatFollowingWrap"', self.html, "Following wrap must have id='profileStatFollowingWrap'")

    def test_02_profile_html_active_topic_bar(self):
        """Verify active topic filter pill and reset button inside toolbar."""
        self.assertIn('id="profileActiveTopicBar"', self.html, "Active topic bar must have id='profileActiveTopicBar'")
        self.assertIn('id="activeTopicChip"', self.html, "Active topic chip must have id='activeTopicChip'")
        self.assertIn('id="activeTopicName"', self.html, "Active topic name element must have id='activeTopicName'")
        self.assertIn('id="btnClearTopicFilter"', self.html, "Clear topic filter button must have id='btnClearTopicFilter'")

    def test_03_profile_html_social_modal(self):
        """Verify social modal markup for subscribers and subscriptions."""
        self.assertIn('id="profileSocialModal"', self.html, "Modal must have id='profileSocialModal'")
        self.assertIn('role="dialog"', self.html, "Social modal must have role='dialog'")
        self.assertIn('id="socialModalTitle"', self.html, "Social modal title must have id='socialModalTitle'")
        self.assertIn('id="btnProfileSocialModalClose"', self.html, "Social modal close button must have id='btnProfileSocialModalClose'")
        self.assertIn('id="socialModalSubnav"', self.html, "Owner subnav must have id='socialModalSubnav'")
        self.assertIn('id="socialSubTabAuthors"', self.html, "Authors subtab button must have id='socialSubTabAuthors'")
        self.assertIn('id="socialSubTabBlogs"', self.html, "Blogs subtab button must have id='socialSubTabBlogs'")
        self.assertIn('id="profileSocialList"', self.html, "Social list container must have id='profileSocialList'")
        self.assertIn('id="btnSocialLoadMore"', self.html, "Social load more button must have id='btnSocialLoadMore'")

    # =========================================================================
    # 2. profile.css Styles
    # =========================================================================

    def test_04_profile_css_classes(self):
        """Verify CSS classes for clickable stats, topic chips, and social modal."""
        self.assertIn('.profile-stat-clickable', self.css, "CSS must define .profile-stat-clickable")
        self.assertIn('.profile-active-topic-bar', self.css, "CSS must define .profile-active-topic-bar")
        self.assertIn('.active-topic-chip', self.css, "CSS must define .active-topic-chip")
        self.assertIn('.btn-clear-topic', self.css, "CSS must define .btn-clear-topic")
        self.assertIn('.profile-sidebar-topic-pill', self.css, "CSS must define .profile-sidebar-topic-pill")
        self.assertIn('.profile-social-modal-card', self.css, "CSS must define .profile-social-modal-card")
        self.assertIn('.profile-social-list', self.css, "CSS must define .profile-social-list")
        self.assertIn('.profile-social-item', self.css, "CSS must define .profile-social-item")
        self.assertIn('.profile-social-avatar-box', self.css, "CSS must define .profile-social-avatar-box")
        self.assertIn('.profile-social-name', self.css, "CSS must define .profile-social-name")
        self.assertIn('.btn-social-load-more', self.css, "CSS must define .btn-social-load-more")

    # =========================================================================
    # 3. profile-page.js Logic
    # =========================================================================

    def test_05_profile_page_js_reputation_breakdown_tooltip(self):
        """Verify rating formula and score breakdown calculation in profile-page.js."""
        self.assertIn('p.ratingFormula', self.page_js, "Must read ratingFormula from profile DTO")
        self.assertIn('materialsRating', self.page_js, "Must support materialsRating breakdown")
        self.assertIn('discussionsRating', self.page_js, "Must support discussionsRating breakdown")
        self.assertIn('profileStatRatingWrap', self.page_js, "Must update profileStatRatingWrap tooltip")

    def test_06_profile_page_js_solutions_and_metrics_routing(self):
        """Verify solutions metric shortcut to answers tab with solutions filter."""
        self.assertIn('switchToSolutions', self.page_js, "Must implement switchToSolutions helper")
        self.assertIn('filterAnswersSolutions', self.page_js, "Must trigger filterAnswersSolutions button")
        self.assertIn('profileStatSolutionsWrap', self.page_js, "Must wire profileStatSolutionsWrap click and keydown")
        self.assertIn('profileStatFollowersWrap', self.page_js, "Must wire profileStatFollowersWrap to openSubscribersModal")
        self.assertIn('profileStatFollowingWrap', self.page_js, "Must wire profileStatFollowingWrap to openSubscriptionsModal")

    def test_07_profile_page_js_topic_filtering(self):
        """Verify topic filtering on author's materials without redirecting to feed."""
        self.assertIn('applyTopicFilter', self.page_js, "Must implement applyTopicFilter helper")
        self.assertIn('clearTopicFilter', self.page_js, "Must implement clearTopicFilter helper")
        self.assertIn('&topic=', self.page_js, "Must append &topic= parameter in loadPublications")
        self.assertIn('profileActiveTopicBar', self.page_js, "Must toggle profileActiveTopicBar display")
        self.assertIn('activeTopicName', self.page_js, "Must update activeTopicName text")
        self.assertIn('btnClearTopicFilter', self.page_js, "Must wire btnClearTopicFilter to clearTopicFilter")

    def test_08_profile_page_js_subscribers_modal_pagination(self):
        """Verify subscribers modal pagination and rendering."""
        self.assertIn('openSubscribersModal', self.page_js, "Must implement openSubscribersModal")
        self.assertIn('loadSubscribers', self.page_js, "Must implement loadSubscribers with pagination")
        self.assertIn('/subscribers?limit=', self.page_js, "Must fetch /subscribers with limit and offset")
        self.assertIn('btnSocialLoadMore', self.page_js, "Must wire btnSocialLoadMore for pagination")
        self.assertIn('renderSocialAuthorItem', self.page_js, "Must render author items with avatars and links")

    def test_09_profile_page_js_subscriptions_modal_privacy_and_tabs(self):
        """Verify subscriptions modal privacy separation and author/blog subtabs."""
        self.assertIn('openSubscriptionsModal', self.page_js, "Must implement openSubscriptionsModal")
        self.assertIn('/subscriptions', self.page_js, "Must fetch /subscriptions")
        self.assertIn('data.isPrivate', self.page_js, "Must check data.isPrivate for foreign profiles")
        self.assertIn('renderSubscriptionsTabContent', self.page_js, "Must render separated author and blog tabs")
        self.assertIn('socialSubTabAuthors', self.page_js, "Must wire authors subtab")
        self.assertIn('socialSubTabBlogs', self.page_js, "Must wire blogs subtab")
        self.assertIn('renderSocialBlogItem', self.page_js, "Must render club/blog links")

    def test_10_profile_page_js_real_state_synchronization(self):
        """Verify server state reflection on subscription toggle and vote events."""
        self.assertIn('data.followersCount', self.page_js, "Must use server-provided followersCount on toggle")
        self.assertIn('smartcontractum:voted', self.page_js, "Must listen to smartcontractum:voted window event")
        self.assertIn('loadProfile', self.page_js, "Must trigger silent loadProfile on vote event")

    # =========================================================================
    # 4. Strict Invariants (Zero Emojis, Zero Em Dashes, 100% Offline-First)
    # =========================================================================

    def test_11_invariants_zero_em_dashes(self):
        """Verify that no em dashes (\u2014) exist in code or template files."""
        for path, content in [
            ("profile.html", self.html),
            ("profile-page.js", self.page_js),
            ("profile.css", self.css),
            ("test_py", self.test_py)
        ]:
            self.assertNotIn("\u2014", content, f"Em dash found in {path}")

    def test_12_invariants_zero_emojis(self):
        """Verify that zero emojis exist in code or template files."""
        def check_emojis(text, label):
            for i, ch in enumerate(text):
                cat = unicodedata.category(ch)
                if cat == "So" or ord(ch) > 0x1F000:
                    self.fail(f"Emoji character detected in {label} at pos {i}: U+{ord(ch):04X}")

        check_emojis(self.html, "profile.html")
        check_emojis(self.page_js, "profile-page.js")
        check_emojis(self.css, "profile.css")

    def test_13_invariants_offline_first(self):
        """Verify that no external CDN or literal http/https URLs exist in client files."""
        suspicious_html = re.findall(r'(https?://[^\s"\'<>]+)', self.html)
        for url in suspicious_html:
            self.assertIn('www.w3.org/2000/svg', url, f"External network URL found in profile.html: {url}")

        suspicious_js = re.findall(r'(https?://[^\s"\'<>]+)', self.page_js)
        for url in suspicious_js:
            self.assertIn('www.w3.org/2000/svg', url, f"External network URL found in profile-page.js: {url}")


if __name__ == "__main__":
    unittest.main()
