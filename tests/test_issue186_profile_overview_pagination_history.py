#!/usr/bin/env python3
"""
tests/test_issue186_profile_overview_pagination_history.py

Automated test suite for Issue #186:
[P1][frontend][PROFILE] Исправить пустой обзор, гонки запросов, пагинацию и историю.

Verifies:
1. Safe pagination:
   - Offset is never incremented before fetch in loadActivity, loadPublications, loadQuestions, loadAnswers.
   - Offset is incremented strictly on successful response (offset += items.length).
   - Load more click handlers do not increment offset prematurely.
2. Race condition & Sequence token protection:
   - Request sequence counters (actReqSeq, pubReqSeq, questReqSeq, ansReqSeq) and AbortControllers.
   - Rapid filter/sort changes supersede pending requests without blocking UI.
   - Outdated in-flight responses are ignored.
3. Error states with retry:
   - Distinct error states for Activity, Publications, Questions, and Answers feeds.
   - Retry buttons present on error and wired to re-fetch with identical offset.
   - Load more errors preserve offset for subsequent retry.
4. History and tab navigation:
   - pushState on explicit tab clicks.
   - popstate handler (addEventListener) activates tab without duplicating history.
5. In-place stats update:
   - updateProfileStats updates stats, tab counts, and sidebar in-place.
   - Silent refresh does not wipe loaded tabs, reset scroll, or re-trigger feed loaders.
6. Top contributions fallback:
   - Derives top 2-3 items from publications (sorted by rating DESC, then date DESC) when topContributions is empty.
   - Displays #profileTopContributionsSection when items are derived.
7. Strict invariants:
   - Zero emojis across all files.
   - Zero em dashes across all files.
   - 100% offline-first.
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


class TestIssue186ProfileOverviewPaginationHistory(unittest.TestCase):
    """Automated test suite verifying Issue #186 implementation and invariants."""

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
    # 1. Safe Pagination Invariants
    # =========================================================================

    def test_safe_pagination_offset_updated_only_on_success(self):
        """Verify loadActivity, loadPublications, loadQuestions, loadAnswers update offset strictly on success."""
        # 1. loadActivity
        act_match = re.search(r"function loadActivity\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(act_match, "loadActivity function must exist")
        act_body = act_match.group(1)
        self.assertNotIn("activityOffset +=", act_body.split("fetch(")[0], "activityOffset must not be incremented before fetch")
        self.assertIn("activityOffset += newItems.length", act_body, "activityOffset must be incremented on successful fetch")

        # 2. loadPublications
        pub_match = re.search(r"function loadPublications\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(pub_match, "loadPublications function must exist")
        pub_body = pub_match.group(1)
        self.assertNotIn("pubOffset +=", pub_body.split("fetch(")[0], "pubOffset must not be incremented before fetch")
        self.assertIn("pubOffset += incoming.length", pub_body, "pubOffset must be incremented on successful fetch")

        # 3. loadQuestions
        quest_match = re.search(r"function loadQuestions\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(quest_match, "loadQuestions function must exist")
        quest_body = quest_match.group(1)
        self.assertNotIn("questOffset +=", quest_body.split("fetch(")[0], "questOffset must not be incremented before fetch")
        self.assertIn("questOffset += incoming.length", quest_body, "questOffset must be incremented on successful fetch")

        # 4. loadAnswers
        ans_match = re.search(r"function loadAnswers\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(ans_match, "loadAnswers function must exist")
        ans_body = ans_match.group(1)
        self.assertNotIn("ansOffset +=", ans_body.split("fetch(")[0], "ansOffset must not be incremented before fetch")
        self.assertIn("ansOffset += incoming.length", ans_body, "ansOffset must be incremented on successful fetch")

    def test_load_more_handlers_do_not_increment_offset_before_fetch(self):
        """Verify load more button click handlers removed premature offset += limit operations."""
        # Check btnProfileLoadMore
        self.assertNotIn(
            "activityOffset += activityLimit",
            self.page_js,
            "Premature activityOffset += activityLimit must be removed from click listener"
        )

        # Check btnProfileLoadMorePublications
        self.assertNotIn(
            "pubOffset += pubLimit",
            self.page_js,
            "Premature pubOffset += pubLimit must be removed from click listener"
        )

        # Check btnProfileLoadMoreQuestions
        self.assertNotIn(
            "questOffset += questLimit",
            self.page_js,
            "Premature questOffset += questLimit must be removed from click listener"
        )

        # Check btnProfileLoadMoreAnswers
        self.assertNotIn(
            "ansOffset += ansLimit",
            self.page_js,
            "Premature ansOffset += ansLimit must be removed from click listener"
        )

    # =========================================================================
    # 2. Race Condition & Sequence Token Protection
    # =========================================================================

    def test_sequence_counters_and_abort_controllers_defined(self):
        """Verify sequence tokens and abort controller variables exist for each feed."""
        tokens = [
            "actReqSeq",
            "pubReqSeq",
            "questReqSeq",
            "ansReqSeq",
            "actAbortCtrl",
            "pubAbortCtrl",
            "questAbortCtrl",
            "ansAbortCtrl"
        ]
        for token in tokens:
            self.assertRegex(
                self.page_js,
                rf"\b{token}\b",
                f"State variable {token} must be defined in profile-page.js"
            )

    def test_loaders_increment_sequence_and_ignore_outdated_responses(self):
        """Verify loaders increment sequence token before fetch and ignore superseded responses."""
        loaders = [
            ("loadActivity", "actReqSeq"),
            ("loadPublications", "pubReqSeq"),
            ("loadQuestions", "questReqSeq"),
            ("loadAnswers", "ansReqSeq")
        ]
        for fn_name, seq_name in loaders:
            pattern = rf"function {fn_name}\s*\([^\)]*\)\s*\{{([\s\S]*?)\n  \}}"
            match = re.search(pattern, self.page_js)
            self.assertIsNotNone(match, f"{fn_name} must be defined")
            body = match.group(1)

            # Pre-fetch sequence increment
            self.assertIn(f"++{seq_name}", body, f"{fn_name} must increment {seq_name} before request")

            # Superseded check in promise resolution
            self.assertRegex(
                body,
                rf"if\s*\([^)]*!==\s*{seq_name}\)\s*return;",
                f"{fn_name} must check and ignore superseded request responses"
            )

    def test_changing_filters_does_not_block_when_pending(self):
        """Verify that when append is false (filter/sort change), pending requests do not block new fetch."""
        loaders = [
            ("loadActivity", "isLoadingActivity"),
            ("loadPublications", "isLoadingPub"),
            ("loadQuestions", "isLoadingQuest"),
            ("loadAnswers", "isLoadingAns")
        ]
        for fn_name, flag_name in loaders:
            pattern = rf"function {fn_name}\s*\([^\)]*\)\s*\{{([\s\S]*?)\n  \}}"
            match = re.search(pattern, self.page_js)
            self.assertIsNotNone(match)
            body = match.group(1)

            # Block condition must check (append && isLoading...)
            self.assertRegex(
                body,
                rf"if\s*\(\s*append\s*&&\s*{flag_name}\s*\)\s*return;",
                f"{fn_name} must only block concurrent append requests, allowing filter changes to supersede"
            )

    # =========================================================================
    # 3. Distinct Error States and Retry Buttons
    # =========================================================================

    def test_distinct_error_states_and_retry_buttons_in_loaders(self):
        """Verify distinct error states with working retry buttons for all 4 feeds."""
        loaders_and_retry_ids = [
            ("loadActivity", "btnRetryActivity", "Ошибка загрузки ленты активности"),
            ("loadPublications", "btnRetryPublications", "Ошибка загрузки публикаций"),
            ("loadQuestions", "btnRetryQuestions", "Ошибка загрузки вопросов"),
            ("loadAnswers", "btnRetryAnswers", "Ошибка загрузки ответов")
        ]
        for fn_name, retry_id, err_text in loaders_and_retry_ids:
            pattern = rf"function {fn_name}\s*\([^\)]*\)\s*\{{([\s\S]*?)\n  \}}"
            match = re.search(pattern, self.page_js)
            self.assertIsNotNone(match)
            body = match.group(1)

            self.assertIn("profile-error-state", body, f"{fn_name} must render profile-error-state container")
            self.assertIn(retry_id, body, f"{fn_name} must render retry button #{retry_id}")
            self.assertIn(err_text, body, f"{fn_name} must render error message: {err_text}")
            self.assertIn(f"{fn_name}(userId, false)", body, f"Retry button must invoke {fn_name} on click")

    def test_error_state_css_classes_defined(self):
        """Verify CSS definitions for .profile-error-state, .profile-error-text, and .btn-profile-retry."""
        self.assertIn(".profile-error-state", self.css)
        self.assertIn(".profile-error-text", self.css)
        self.assertIn(".btn-profile-retry", self.css)
        self.assertIn(".btn-profile-retry:hover", self.css)

    # =========================================================================
    # 4. History and Tab Navigation
    # =========================================================================

    def test_tab_switching_uses_push_state(self):
        """Verify setActiveTab uses history.pushState when tab is changed by user."""
        set_tab_match = re.search(r"function setActiveTab\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(set_tab_match, "setActiveTab must exist")
        body = set_tab_match.group(1)

        self.assertIn("window.history.pushState", body, "setActiveTab must support window.history.pushState")
        self.assertIn("window.history.replaceState", body, "setActiveTab must preserve replaceState support")

    def test_popstate_handler_handles_navigation_without_duplication(self):
        """Verify popstate handler activates tab without pushing duplicate history entries."""
        self.assertIn("function handlePopState", self.page_js, "handlePopState must be defined")
        self.assertIn("window.addEventListener('popstate', handlePopState)", self.page_js, "popstate event listener must be registered")

        # Verify handlePopState invokes setActiveTab(tab, false)
        popstate_match = re.search(r"function handlePopState\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(popstate_match)
        pop_body = popstate_match.group(1)
        self.assertIn("setActiveTab(tab, false)", pop_body, "handlePopState must call setActiveTab with updateUrl=false")

    # =========================================================================
    # 5. In-Place Stats Update
    # =========================================================================

    def test_update_profile_stats_function_defined_and_exported(self):
        """Verify updateProfileStats is defined, handles all stats, and is exported."""
        self.assertRegex(self.page_js, r"function updateProfileStats\s*\(", "updateProfileStats function must be defined")
        self.assertIn("updateProfileStats: updateProfileStats", self.page_js, "updateProfileStats must be exported")

        match = re.search(r"function updateProfileStats\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match)
        body = match.group(1)

        # Check in-place updating of key elements
        self.assertIn("profileStatRating", body)
        self.assertIn("profileStatFollowers", body)
        self.assertIn("profileStatPublications", body)
        self.assertIn("profileStatQuestions", body)
        self.assertIn("profileStatAnswers", body)
        self.assertIn("profileStatSolutions", body)
        self.assertIn("tabCountPublications", body)
        self.assertIn("tabCountQuestions", body)
        self.assertIn("tabCountAnswers", body)

    def test_load_profile_silent_refresh_does_not_wipe_tabs(self):
        """Verify loadProfile with isSilentRefresh updates stats only without re-rendering or wiping tabs."""
        match = re.search(r"function loadProfile\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match)
        body = match.group(1)

        self.assertIn("if (isSilentRefresh && currentProfile)", body)
        self.assertIn("updateProfileStats(", body)
        self.assertIn("return;", body, "Silent refresh must return immediately after updating stats")

    # =========================================================================
    # 6. Top Contributions Fallback
    # =========================================================================

    def test_top_contributions_fallback_logic(self):
        """Verify renderTopContributions derives top 2-3 items from publications when topContributions is empty."""
        match = re.search(r"function renderTopContributions\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match, "renderTopContributions must exist")
        body = match.group(1)

        # Fallback inspection
        self.assertIn("fallbackPubs", body, "renderTopContributions must accept fallbackPubs")
        self.assertIn("candidates.sort", body, "Fallback items must be sorted")
        self.assertIn("candidates.slice(0, 3)", body, "Must pick top 2-3 items from fallback publications")
        self.assertIn("sec.style.display = 'block'", body)
        self.assertIn("sec.style.display = 'none'", body)

    def test_render_profile_supplies_fallback_publications_to_top_contributions(self):
        """Verify renderProfile passes fallback publications to renderTopContributions."""
        match = re.search(r"function renderProfile\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match)
        body = match.group(1)

        self.assertRegex(
            body,
            r"renderTopContributions\(\s*p\.topContributions\s*\|\|\s*\[\]\s*,\s*p\.publications",
            "renderProfile must pass publications as fallback to renderTopContributions"
        )

    # =========================================================================
    # 7. Module Exports and Global API
    # =========================================================================

    def test_global_exports_include_issue_186_enhancements(self):
        """Verify window.SmartContractumProfilePage exports all required methods."""
        export_match = re.search(r"window\.SmartContractumProfilePage\s*=\s*\{([\s\S]*?)\n  \};", self.page_js)
        self.assertIsNotNone(export_match)
        exports = export_match.group(1)

        required = [
            "loadActivity",
            "loadPublications",
            "loadQuestions",
            "loadAnswers",
            "updateProfileStats",
            "handlePopState",
            "renderTopContributions",
            "getOffsets",
            "getSeqTokens",
            "getActiveTab"
        ]
        for r in required:
            self.assertIn(r, exports, f"Export {r} must be present in window.SmartContractumProfilePage")

    # =========================================================================
    # 8. Strict Invariants: Zero Emojis, Zero Em Dashes, Offline-First
    # =========================================================================

    def test_zero_emojis(self):
        """Verify zero emojis in all modified files."""
        for path, content in [
            ("profile.html", self.html),
            ("profile-page.js", self.page_js),
            ("profile.css", self.css),
            (__file__, self.test_py)
        ]:
            emojis = [c for c in content if "EMOJI" in unicodedata.name(c, "")]
            self.assertEqual(len(emojis), 0, f"Found emojis in {path}: {emojis}")

    def test_zero_em_dashes(self):
        """Verify zero em dashes in all modified files."""
        em_dash = chr(8212)
        for path, content in [
            ("profile.html", self.html),
            ("profile-page.js", self.page_js),
            ("profile.css", self.css),
            (__file__, self.test_py)
        ]:
            self.assertNotIn(em_dash, content, f"Found em dash in {path}")

    def test_offline_first_integrity(self):
        """Verify 100% offline-first architecture with no external CDNs or remote URLs."""
        for path, content in [
            ("profile.html", self.html),
            ("profile-page.js", self.page_js),
            ("profile.css", self.css)
        ]:
            # Disallow external CDNs
            for cdn in ["cdnjs", "unpkg", "jsdelivr", "googleapis.com", "gstatic.com"]:
                self.assertNotIn(cdn, content, f"External CDN {cdn} detected in {path}")


if __name__ == "__main__":
    unittest.main()
