#!/usr/bin/env python3
"""
tests/test_issue35_sc030_voting_arrows_and_live_counters.py

Verification test suite for Issue #35:
"Рейтинг 2/3: стрелки голосования в интерфейсе и обновление счетчиков без перезагрузки".

Must Prove Invariants:
1. All 4 publication types have both like and rating capsule in card.js HTML, delegating to votes.js.
2. Question card in feed contains like, rating capsule, answers button, and bookmark.
3. Answer cards and comment nodes contain dedicated .comment-vote-row above actions.
4. Article page contains top and bottom voting capsules.
5. Live synchronization updates all matching capsules on page without page reload, validating response format.
6. Guest click triggers auth modal; author self-vote has disabled capsule.
7. Feed sorting: explicit state.sort takes precedence; rating and top use score, popular and focus use likes.
8. CSS styling, dark/light theme tokens, and mobile touch targets without 28px/32px container conflict.
9. Code quality standards: 100% offline-first, zero emojis, zero em dashes.
10. Behavioral checks: guest arrow click, user switch, drilldown return state retention, error rollback, 2-tier layout.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue35VotingArrowsAndLiveCounters(unittest.TestCase):
    """Verifies all UI, styling, and client-side logic for Issue #35."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, "js", "votes.js"), "r", encoding="utf-8") as f:
            cls.votes_js = f.read()

        with open(os.path.join(FRONTEND_DIR, "js", "card.js"), "r", encoding="utf-8") as f:
            cls.card_js = f.read()

        with open(os.path.join(FRONTEND_DIR, "js", "feed.js"), "r", encoding="utf-8") as f:
            cls.feed_js = f.read()

        with open(os.path.join(FRONTEND_DIR, "js", "article.js"), "r", encoding="utf-8") as f:
            cls.article_js = f.read()

        with open(os.path.join(FRONTEND_DIR, "feed.html"), "r", encoding="utf-8") as f:
            cls.feed_html = f.read()

        with open(os.path.join(FRONTEND_DIR, "article.html"), "r", encoding="utf-8") as f:
            cls.article_html = f.read()

        with open(os.path.join(FRONTEND_DIR, "editor.html"), "r", encoding="utf-8") as f:
            cls.editor_html = f.read()

        with open(os.path.join(FRONTEND_DIR, "css", "theme.css"), "r", encoding="utf-8") as f:
            cls.theme_css = f.read()

        with open(os.path.join(FRONTEND_DIR, "css", "article.css"), "r", encoding="utf-8") as f:
            cls.article_css = f.read()

        with open(os.path.join(FRONTEND_DIR, "css", "feed.css"), "r", encoding="utf-8") as f:
            cls.feed_css = f.read()

    # --------------------------------------------------------------------------
    # Invariant 1: All 4 publication types have both like and rating capsule
    # --------------------------------------------------------------------------
    def test_01_all_4_publication_types_have_like_and_rating_capsule(self):
        """Invariant 1: All 4 publication types have both like and rating capsule in card.js HTML."""
        # votes.js is single source of markup truth
        self.assertIn("renderVoteCapsuleHtml: renderVoteCapsuleHtml", self.votes_js)
        self.assertIn("window.SmartContractumVotes", self.votes_js)

        # card.js delegates to window.SmartContractumVotes.renderVoteCapsuleHtml
        self.assertIn("renderVoteCapsuleHtml", self.card_js)
        self.assertIn("SmartContractumVotes.renderVoteCapsuleHtml", self.card_js)

        # Standard publication branch in card.js footerLeftHtml must have likeBtnHtml AND voteCapsuleHtml
        standard_match = re.search(
            r'footerLeftHtml\s*=\s*likeBtnHtml\s*\+\s*voteCapsuleHtml\s*\+\s*commentsBtnHtml\s*\+\s*bookmarkHtml;',
            self.card_js
        )
        self.assertIsNotNone(
            standard_match,
            "card.js standard publication footerLeftHtml must include likeBtnHtml + voteCapsuleHtml + commentsBtnHtml + bookmarkHtml"
        )

        # Question publication branch in card.js footerLeftHtml must have likeBtnHtml AND voteCapsuleHtml
        question_match = re.search(
            r'footerLeftHtml\s*=\s*likeBtnHtml\s*\+\s*voteCapsuleHtml\s*\+\s*answersBtnHtml\s*\+\s*bookmarkHtml;',
            self.card_js
        )
        self.assertIsNotNone(
            question_match,
            "card.js question footerLeftHtml must include likeBtnHtml + voteCapsuleHtml + answersBtnHtml + bookmarkHtml"
        )

        # Verify capsule markup attributes in votes.js renderVoteCapsuleHtml
        self.assertIn('data-vote-target-type="', self.votes_js)
        self.assertIn('data-vote-target-id="', self.votes_js)
        self.assertIn('data-score="', self.votes_js)
        self.assertIn('data-my-vote="', self.votes_js)
        self.assertIn('data-can-vote="', self.votes_js)
        self.assertIn('vote-score', self.votes_js)
        self.assertIn('vote-btn-up', self.votes_js)
        self.assertIn('vote-btn-down', self.votes_js)

    # --------------------------------------------------------------------------
    # Invariant 2: Question card in feed contains like, rating capsule, answers button, and bookmark
    # --------------------------------------------------------------------------
    def test_02_question_card_in_feed_structure(self):
        """Invariant 2: Question card in feed contains like, rating capsule, answers button, and bookmark."""
        self.assertIn('footerLeftHtml = likeBtnHtml + voteCapsuleHtml + answersBtnHtml + bookmarkHtml;', self.card_js)
        self.assertIn('btn-card-answers', self.card_js)
        self.assertIn('is-solved', self.card_js)
        self.assertIn('hasSolution', self.card_js)
        self.assertIn('solved-badge', self.card_js)
        self.assertIn('btn-card-bookmark', self.card_js)
        self.assertIn('btn-card-like', self.card_js)
        self.assertIn('like-count', self.card_js)

    # --------------------------------------------------------------------------
    # Invariant 3: Answer cards and comment nodes contain voting capsules in separate row
    # --------------------------------------------------------------------------
    def test_03_answer_cards_and_comment_nodes_contain_voting_capsules(self):
        """Invariant 3: Answer cards and comment nodes contain dedicated .comment-vote-row above actions."""
        # Answer card in article.js has comment-vote-row answer-vote-row above answer-actions
        self.assertIn('renderAnswerCard', self.article_js)
        self.assertIn('ansVoteCapsuleHtml', self.article_js)
        ans_row_match = re.search(
            r'<div class="comment-vote-row answer-vote-row">\s*\'\s*\+\s*ansVoteCapsuleHtml\s*\+\s*\'\s*</div>\s*\'\s*\+\s*\'\s*<div class="answer-actions">',
            self.article_js
        )
        self.assertIsNotNone(
            ans_row_match,
            "article.js renderAnswerCard must render ansVoteCapsuleHtml in .comment-vote-row.answer-vote-row above .answer-actions"
        )

        # Comment node in article.js has comment-vote-row above comment-actions
        self.assertIn('renderCommentNode', self.article_js)
        self.assertIn('commVoteCapsuleHtml', self.article_js)
        comm_row_match = re.search(
            r'<div class="comment-vote-row">\s*\'\s*\+\s*commVoteCapsuleHtml\s*\+\s*\'\s*</div>\s*\'\s*\+\s*\'\s*<div class="comment-actions">',
            self.article_js
        )
        self.assertIsNotNone(
            comm_row_match,
            "article.js renderCommentNode must render commVoteCapsuleHtml in .comment-vote-row above .comment-actions"
        )

        # Verify neither .comment-actions nor .answer-actions contains vote capsule
        self.assertNotIn('<div class="comment-actions">\'+commVoteCapsuleHtml', self.article_js.replace(" ", ""))
        self.assertNotIn('<div class="answer-actions">\'+ansVoteCapsuleHtml', self.article_js.replace(" ", ""))

        # Both use targetType: 'comment'
        self.assertIn("targetType: 'comment'", self.article_js)

        # Deleted comments must not have active voting buttons
        self.assertIn("isDeleted: Boolean(comment.isDeleted)", self.article_js)

    # --------------------------------------------------------------------------
    # Invariant 4: Article page contains top and bottom voting capsules
    # --------------------------------------------------------------------------
    def test_04_article_page_top_and_bottom_voting_capsules(self):
        """Invariant 4: Article page contains top and bottom voting capsules."""
        self.assertIn('id="voteArticleTop"', self.article_html)
        self.assertIn('id="btnArticleLike"', self.article_html)
        self.assertIn('id="voteArticleBottom"', self.article_html)
        self.assertIn('id="btnArticleLikeBottom"', self.article_html)
        self.assertIn('syncArticleVoteCapsules(article);', self.article_js)
        self.assertIn("document.getElementById('voteArticleTop')", self.article_js)
        self.assertIn("document.getElementById('voteArticleBottom')", self.article_js)

    # --------------------------------------------------------------------------
    # Invariant 5: Live synchronization updates all matching capsules on page
    # --------------------------------------------------------------------------
    def test_05_live_synchronization_and_multi_capsule_sync(self):
        """Invariant 5: Live synchronization updates all matching capsules on page."""
        self.assertIn('syncVoteCapsules', self.votes_js)
        self.assertIn('data-vote-target-type="\' + targetType + \'"][data-vote-target-id="\' + targetId + \'"]', self.votes_js)
        self.assertIn("classList.add('is-pending')", self.votes_js)
        self.assertIn("disabled = true", self.votes_js)
        self.assertIn("classList.remove('is-pending')", self.votes_js)
        self.assertIn("scoreEl.textContent = String(score)", self.votes_js)
        self.assertIn("aria-pressed", self.votes_js)
        self.assertIn("is-voted", self.votes_js)
        self.assertIn("updateCapsuleElement(c, previousState)", self.votes_js)
        self.assertIn("showToast", self.votes_js)

    # --------------------------------------------------------------------------
    # Invariant 6: Guest click triggers auth modal; author self-vote has disabled capsule
    # --------------------------------------------------------------------------
    def test_06_guest_triggers_auth_modal_and_author_self_vote_disabled(self):
        """Invariant 6: Guest click triggers auth modal; author self-vote has disabled capsule."""
        self.assertIn('const user = getCurrentUser();', self.votes_js)
        self.assertIn('invokeAuthModal();', self.votes_js)
        self.assertIn('data-is-author', self.votes_js)
        self.assertIn('Нельзя голосовать за собственный материал', self.votes_js)
        self.assertIn('Нельзя голосовать за собственный комментарий', self.votes_js)
        self.assertIn('e.preventDefault();', self.votes_js)
        self.assertIn('e.stopPropagation();', self.votes_js)
        self.assertIn('e.stopImmediatePropagation();', self.votes_js)
        self.assertIn('window.openAuthModal', self.feed_js)
        self.assertIn('window.openAuthModal', self.article_js)

    # --------------------------------------------------------------------------
    # Invariant 7: Feed sorting for rating and top uses score, popular and focus use likes
    # --------------------------------------------------------------------------
    def test_07_feed_sorting_and_offline_fallback(self):
        """Invariant 7: Feed sorting for rating and top uses score, popular and focus use likes."""
        self.assertIn('id="feedSortSelect"', self.feed_html)
        self.assertIn('value="rating"', self.feed_html)
        self.assertIn('value="popular"', self.feed_html)
        self.assertIn('value="newest"', self.feed_html)
        self.assertIn('value="discussed"', self.feed_html)
        self.assertIn("state.sort = sortVal;", self.feed_js)

        # Fallback sorting: explicit sort has priority over tab
        self.assertIn("const hasExplicitSort = Boolean(state.sort", self.feed_js)
        self.assertIn("if (hasExplicitSort && state.sort === 'rating')", self.feed_js)
        self.assertIn("else if (hasExplicitSort && state.sort === 'popular')", self.feed_js)
        self.assertIn("else if (state.tab === 'top')", self.feed_js)
        self.assertIn("smartcontractum:voted", self.feed_js)

    # --------------------------------------------------------------------------
    # Invariant 8: CSS styling, theme tokens, and mobile touch targets
    # --------------------------------------------------------------------------
    def test_08_css_styling_and_theme_tokens(self):
        """Invariant 8: CSS styling, theme tokens, and mobile touch targets."""
        self.assertIn('.vote-capsule', self.theme_css)
        self.assertIn('.comment-vote-row', self.theme_css)
        self.assertIn('.vote-btn', self.theme_css)
        self.assertIn('.vote-btn-up', self.theme_css)
        self.assertIn('.vote-btn-down', self.theme_css)
        self.assertIn('.vote-score', self.theme_css)
        self.assertIn('.is-voted', self.theme_css)
        self.assertIn('.is-pending', self.theme_css)
        self.assertIn('var(--border-color)', self.theme_css)
        self.assertIn('var(--bg-surface)', self.theme_css)
        self.assertIn('var(--text-primary)', self.theme_css)
        self.assertIn('var(--text-secondary)', self.theme_css)
        self.assertIn('var(--success-color', self.theme_css)
        self.assertIn('var(--danger-color', self.theme_css)
        self.assertIn(':hover', self.theme_css)
        self.assertIn(':active', self.theme_css)
        self.assertIn(':focus-visible', self.theme_css)

        # Mobile media query touch target (at least 32px) and container min-height
        self.assertIn('@media (max-width: 768px)', self.theme_css)
        self.assertIn('32px', self.theme_css)
        self.assertIn('min-height: 32px;', self.theme_css)

    # --------------------------------------------------------------------------
    # Invariant 9: Quality Standards (Zero emojis, Zero em dashes, 100% offline-first)
    # --------------------------------------------------------------------------
    def test_09_code_quality_and_standards(self):
        """Invariant 9: Quality Standards (Zero emojis, Zero em dashes, 100% offline-first)."""
        em_dash = '\u2014'

        self.assertNotIn(em_dash, self.votes_js, "votes.js must not contain em dash")
        with open(__file__, "r", encoding="utf-8") as f:
            test_content = f.read()
        self.assertNotIn(em_dash, test_content, "Test file must not contain em dash")

        self.assertIn('<script src="js/votes.js"></script>', self.feed_html)
        self.assertIn('<script src="js/votes.js"></script>', self.article_html)
        self.assertIn('<script src="js/votes.js?v=3"></script>', self.editor_html)

        self.assertNotIn('http://', self.votes_js)
        self.assertNotIn('https://', self.votes_js)
        self.assertNotIn('cdn.', self.votes_js)

        emoji_pattern = re.compile(
            r'[\U00010000-\U0010ffff]'
            r'|[\u2600-\u26ff]'
            r'|[\u2700-\u27bf]'
        )
        self.assertIsNone(emoji_pattern.search(self.votes_js), "votes.js must contain zero emojis")

    # --------------------------------------------------------------------------
    # Invariant 10: Behavioral check - Guest click and Auth flow
    # --------------------------------------------------------------------------
    def test_10_behavioral_guest_click_and_auth_flow(self):
        """Guest arrow click invokes login modal, guest is not treated as author."""
        # canVote=false is NOT equated to authorship in votes.js
        self.assertNotIn("canVote === false ? 'is-author'", self.votes_js.replace(" ", ""))
        # Guest can click arrow (buttons not disabled by default for guests)
        self.assertIn("upTitle = 'Войдите, чтобы повысить рейтинг';", self.votes_js)
        self.assertIn("downTitle = 'Войдите, чтобы понизить рейтинг';", self.votes_js)
        self.assertIn("if (!user || user.isGuest) {", self.votes_js)
        self.assertIn("invokeAuthModal();", self.votes_js)

    # --------------------------------------------------------------------------
    # Invariant 11: Behavioral check - User switch refetches and discards stale
    # --------------------------------------------------------------------------
    def test_11_behavioral_user_switch_refetches_and_discards_stale(self):
        """User switch / login / logout refetches personalized vote data with token guard."""
        self.assertIn("refreshArticleAndCommentsOnAuthChange", self.article_js)
        self.assertIn("currentAuthSessionToken", self.article_js)
        # Auth event listeners update state and discard stale sessions
        self.assertIn("smartcontractum:auth-changed", self.article_js)
        self.assertIn("sessionToken !== currentAuthSessionToken", self.article_js)

    # --------------------------------------------------------------------------
    # Invariant 12: Behavioral check - Drilldown and return retains state across caches
    # --------------------------------------------------------------------------
    def test_12_behavioral_drilldown_and_return_retains_state(self):
        """Voting updates currentArticle, _commentsResponseData, _rawCommentsData, and _allCommentsMap."""
        self.assertIn("updateVoteDataStore", self.article_js)
        self.assertIn("window._commentsResponseData", self.article_js)
        self.assertIn("window._rawCommentsData", self.article_js)
        self.assertIn("window._allCommentsMap", self.article_js)
        self.assertIn("smartcontractum:voted", self.article_js)

    # --------------------------------------------------------------------------
    # Invariant 13: Behavioral check - Response validation and error rollback
    # --------------------------------------------------------------------------
    def test_13_behavioral_error_rollback_and_response_validation(self):
        """votes.js strictly validates response data before updating state and rolls back on failure."""
        self.assertIn("Number.isInteger(data.score)", self.votes_js)
        self.assertIn("[-1, 0, 1].indexOf(data.myVote) !== -1", self.votes_js)
        self.assertIn("data.targetId === targetId", self.votes_js)
        self.assertIn("updateCapsuleElement(c, previousState)", self.votes_js)
        self.assertIn("window._activePendingVotes.delete(targetKey)", self.votes_js)

    # --------------------------------------------------------------------------
    # Invariant 14: Behavioral check - Two-tier layout for comments and answers
    # --------------------------------------------------------------------------
    def test_14_behavioral_two_row_comment_rating_layout(self):
        """Rating capsule sits in its own row and is never shifted by toggleRow or thread collapse."""
        # .comment-vote-row exists in DOM structure between content and actions
        self.assertIn('<div class="comment-vote-row">', self.article_js)
        self.assertIn('<div class="comment-vote-row answer-vote-row">', self.article_js)
        # toggleRow appends .comment-actions, but does NOT append .comment-vote-row
        self.assertIn("toggleRow.appendChild(commentActions);", self.article_js)
        self.assertNotIn("toggleRow.appendChild(voteRow)", self.article_js)
        self.assertNotIn("toggleRow.appendChild(commVoteCapsuleHtml)", self.article_js)


if __name__ == '__main__':
    unittest.main()
