#!/usr/bin/env python3
"""
tests/test_issue35_sc030_voting_arrows_and_live_counters.py

Verification test suite for Issue #35:
"Рейтинг 2/3: стрелки голосования в интерфейсе и обновление счетчиков без перезагрузки".

Must Prove Invariants:
1. All 4 publication types have both like and rating capsule in card.js HTML.
2. Question card in feed contains like, rating capsule, answers button, and bookmark.
3. Answer cards and comment nodes contain voting capsules.
4. Article page contains top and bottom voting capsules.
5. Live synchronization updates all matching capsules on page without page reload.
6. Guest click triggers auth modal; author self-vote has disabled capsule.
7. Feed sorting for rating and top uses score, popular and focus use likes.
8. CSS styling, dark/light theme tokens, and mobile touch targets.
9. Code quality standards: 100% offline-first, zero emojis, zero em dashes.
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
        # card.js must export renderVoteCapsuleHtml on window.SmartContractumCard
        self.assertIn("renderVoteCapsuleHtml: renderVoteCapsuleHtml", self.card_js)
        self.assertIn("window.SmartContractumCard", self.card_js)

        # votes.js must export renderVoteCapsuleHtml on window.SmartContractumVotes
        self.assertIn("renderVoteCapsuleHtml: renderVoteCapsuleHtml", self.votes_js)
        self.assertIn("window.SmartContractumVotes", self.votes_js)

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

        # Verify capsule markup attributes in card.js renderVoteCapsuleHtml
        self.assertIn('class="\' + capsuleClass + \'"', self.card_js)
        self.assertIn('data-vote-target-type="\' + escapeHtml(targetType) + \'"', self.card_js)
        self.assertIn('data-vote-target-id="\' + escapeHtml(targetId) + \'"', self.card_js)
        self.assertIn('data-score="\' + score + \'"', self.card_js)
        self.assertIn('data-my-vote="\' + myVote + \'"', self.card_js)
        self.assertIn('data-can-vote="\' + (canVote ? \'true\' : \'false\') + \'"', self.card_js)
        self.assertIn('vote-score', self.card_js)
        self.assertIn('vote-btn-up', self.card_js)
        self.assertIn('vote-btn-down', self.card_js)

    # --------------------------------------------------------------------------
    # Invariant 2: Question card in feed contains like, rating capsule, answers button, and bookmark
    # --------------------------------------------------------------------------
    def test_02_question_card_in_feed_structure(self):
        """Invariant 2: Question card in feed contains like, rating capsule, answers button, and bookmark."""
        # Check that footerLeftHtml for questions explicitly includes all 4 components in correct sequence
        self.assertIn('footerLeftHtml = likeBtnHtml + voteCapsuleHtml + answersBtnHtml + bookmarkHtml;', self.card_js)

        # Ensure answers button has distinct styling classes and solved state support
        self.assertIn('btn-card-answers', self.card_js)
        self.assertIn('is-solved', self.card_js)
        self.assertIn('hasSolution', self.card_js)
        self.assertIn('solved-badge', self.card_js)

        # Ensure bookmark button is retained
        self.assertIn('btn-card-bookmark', self.card_js)

        # Ensure like button is present and binds like-count
        self.assertIn('btn-card-like', self.card_js)
        self.assertIn('like-count', self.card_js)

    # --------------------------------------------------------------------------
    # Invariant 3: Answer cards and comment nodes contain voting capsules
    # --------------------------------------------------------------------------
    def test_03_answer_cards_and_comment_nodes_contain_voting_capsules(self):
        """Invariant 3: Answer cards and comment nodes contain voting capsules."""
        # Answer card in article.js
        self.assertIn('renderAnswerCard', self.article_js)
        self.assertIn('ansVoteCapsuleHtml', self.article_js)
        ans_action_match = re.search(
            r'<div class="answer-actions">\s*\'\s*\+\s*ansVoteCapsuleHtml\s*\+\s*editBtnHtml',
            self.article_js
        )
        self.assertIsNotNone(
            ans_action_match,
            "article.js renderAnswerCard must include ansVoteCapsuleHtml in .answer-actions"
        )

        # Comment node in article.js
        self.assertIn('renderCommentNode', self.article_js)
        self.assertIn('commVoteCapsuleHtml', self.article_js)
        comm_action_match = re.search(
            r'<div class="comment-actions">\s*\'\s*\+\s*commVoteCapsuleHtml\s*\+\s*editBtnHtml',
            self.article_js
        )
        self.assertIsNotNone(
            comm_action_match,
            "article.js renderCommentNode must include commVoteCapsuleHtml in .comment-actions"
        )

        # Both use targetType: 'comment'
        self.assertIn("targetType: 'comment'", self.article_js)

        # Deleted comments must not have active voting buttons
        self.assertIn("isDeleted: Boolean(comment.isDeleted)", self.article_js)

    # --------------------------------------------------------------------------
    # Invariant 4: Article page contains top and bottom voting capsules
    # --------------------------------------------------------------------------
    def test_04_article_page_top_and_bottom_voting_capsules(self):
        """Invariant 4: Article page contains top and bottom voting capsules."""
        # article.html top action bar
        self.assertIn('id="voteArticleTop"', self.article_html)
        self.assertIn('id="btnArticleLike"', self.article_html)

        # article.html bottom action bar
        self.assertIn('id="voteArticleBottom"', self.article_html)
        self.assertIn('id="btnArticleLikeBottom"', self.article_html)

        # article.js populateArticle calls syncArticleVoteCapsules
        self.assertIn('syncArticleVoteCapsules(article);', self.article_js)

        # syncArticleVoteCapsules updates both top and bottom containers
        self.assertIn("document.getElementById('voteArticleTop')", self.article_js)
        self.assertIn("document.getElementById('voteArticleBottom')", self.article_js)

    # --------------------------------------------------------------------------
    # Invariant 5: Live synchronization updates all matching capsules on page
    # --------------------------------------------------------------------------
    def test_05_live_synchronization_and_multi_capsule_sync(self):
        """Invariant 5: Live synchronization updates all matching capsules on page."""
        # votes.js defines syncVoteCapsules
        self.assertIn('syncVoteCapsules', self.votes_js)

        # Selector queries all matching capsules on the page by targetType and targetId
        self.assertIn('data-vote-target-type="\' + targetType + \'"][data-vote-target-id="\' + targetId + \'"]', self.votes_js)

        # Pending state locks matching capsules during request
        self.assertIn("classList.add('is-pending')", self.votes_js)
        self.assertIn(".disabled = true", self.votes_js)

        # On success (status === 200), updates score, myVote, aria-pressed, titles, and removes is-pending
        self.assertIn("classList.remove('is-pending')", self.votes_js)
        self.assertIn("scoreEl.textContent = String(state.score)", self.votes_js)
        self.assertIn("aria-pressed", self.votes_js)
        self.assertIn("is-voted", self.votes_js)

        # On network failure or error, rolls back previousState and removes is-pending
        self.assertIn("updateCapsuleElement(c, previousState)", self.votes_js)
        self.assertIn("showToast", self.votes_js)

    # --------------------------------------------------------------------------
    # Invariant 6: Guest click triggers auth modal; author self-vote has disabled capsule
    # --------------------------------------------------------------------------
    def test_06_guest_triggers_auth_modal_and_author_self_vote_disabled(self):
        """Invariant 6: Guest click triggers auth modal; author self-vote has disabled capsule."""
        # Guest check in votes.js
        self.assertIn('const user = getCurrentUser();', self.votes_js)
        self.assertIn('invokeAuthModal();', self.votes_js)

        # Author check and disabled attributes
        self.assertIn('data-is-author', self.votes_js)
        self.assertIn('Нельзя голосовать за собственный материал', self.votes_js)
        self.assertIn('Нельзя голосовать за собственный комментарий', self.votes_js)

        # Event isolation (stops page navigation and comment toggles)
        self.assertIn('e.preventDefault();', self.votes_js)
        self.assertIn('e.stopPropagation();', self.votes_js)
        self.assertIn('e.stopImmediatePropagation();', self.votes_js)

        # Window hooks
        self.assertIn('window.openAuthModal', self.feed_js)
        self.assertIn('window.openAuthModal', self.article_js)

    # --------------------------------------------------------------------------
    # Invariant 7: Feed sorting for rating and top uses score, popular and focus use likes
    # --------------------------------------------------------------------------
    def test_07_feed_sorting_and_offline_fallback(self):
        """Invariant 7: Feed sorting for rating and top uses score, popular and focus use likes."""
        # feed.html toolbar select has rating option
        self.assertIn('id="feedSortSelect"', self.feed_html)
        self.assertIn('value="rating"', self.feed_html)
        self.assertIn('value="popular"', self.feed_html)
        self.assertIn('value="newest"', self.feed_html)
        self.assertIn('value="discussed"', self.feed_html)

        # feed.js parseURLParams supports sort
        self.assertIn("state.sort = sortVal;", self.feed_js)

        # Offline fallback sorting logic in feed.js
        # sort === 'rating' sorts by score DESC
        self.assertIn("if (state.sort === 'rating')", self.feed_js)
        self.assertIn("sb - sa", self.feed_js)

        # tab === 'top' sorts by score DESC then commentsCount DESC
        self.assertIn("else if (state.tab === 'top')", self.feed_js)
        self.assertIn("cb - ca", self.feed_js)

        # sort === 'popular' or tab === 'focus' sorts by likes
        self.assertIn("state.sort === 'popular' || state.tab === 'focus'", self.feed_js)
        self.assertIn("lb - la", self.feed_js)

        # smartcontractum:voted listener updates article in feed memory without moving branches
        self.assertIn("smartcontractum:voted", self.feed_js)

    # --------------------------------------------------------------------------
    # Invariant 8: CSS styling, theme tokens, and mobile touch targets
    # --------------------------------------------------------------------------
    def test_08_css_styling_and_theme_tokens(self):
        """Invariant 8: CSS styling, theme tokens, and mobile touch targets."""
        # Theme CSS contains vote capsule styles
        self.assertIn('.vote-capsule', self.theme_css)
        self.assertIn('.vote-btn', self.theme_css)
        self.assertIn('.vote-btn-up', self.theme_css)
        self.assertIn('.vote-btn-down', self.theme_css)
        self.assertIn('.vote-score', self.theme_css)
        self.assertIn('.is-voted', self.theme_css)
        self.assertIn('.is-pending', self.theme_css)

        # Tokens usage
        self.assertIn('var(--border-color)', self.theme_css)
        self.assertIn('var(--bg-surface)', self.theme_css)
        self.assertIn('var(--text-primary)', self.theme_css)
        self.assertIn('var(--text-secondary)', self.theme_css)
        self.assertIn('var(--success-color', self.theme_css)
        self.assertIn('var(--danger-color', self.theme_css)

        # Hover, active, focus-visible
        self.assertIn(':hover', self.theme_css)
        self.assertIn(':active', self.theme_css)
        self.assertIn(':focus-visible', self.theme_css)

        # Mobile media query touch target (at least 32px)
        self.assertIn('@media (max-width: 768px)', self.theme_css)
        self.assertIn('32px', self.theme_css)

    # --------------------------------------------------------------------------
    # Invariant 9: Quality Standards (Zero emojis, Zero em dashes, 100% offline-first)
    # --------------------------------------------------------------------------
    def test_09_code_quality_and_standards(self):
        """Invariant 9: Quality Standards (Zero emojis, Zero em dashes, 100% offline-first)."""
        em_dash = '\u2014'

        files_to_check = [
            ("votes.js", self.votes_js),
            ("card.js", self.card_js),
            ("feed.js", self.feed_js),
            ("article.js", self.article_js),
            ("feed.html", self.feed_html),
            ("article.html", self.article_html),
            ("editor.html", self.editor_html),
            ("theme.css", self.theme_css),
            ("article.css", self.article_css),
            ("feed.css", self.feed_css)
        ]

        # 1. Zero em dashes in our newly created votes.js and test file
        self.assertNotIn(em_dash, self.votes_js, "votes.js must not contain em dash")
        with open(__file__, "r", encoding="utf-8") as f:
            test_content = f.read()
        self.assertNotIn(em_dash, test_content, "Test file must not contain em dash")

        # 2. Script inclusion order: votes.js is included in feed.html, article.html, editor.html
        self.assertIn('<script src="js/votes.js"></script>', self.feed_html)
        self.assertIn('<script src="js/votes.js"></script>', self.article_html)
        self.assertIn('<script src="js/votes.js?v=3"></script>', self.editor_html)

        # 3. 100% offline-first: no external CDN urls in votes.js
        self.assertNotIn('http://', self.votes_js)
        self.assertNotIn('https://', self.votes_js)
        self.assertNotIn('cdn.', self.votes_js)

        # 4. Zero emojis in votes.js
        emoji_pattern = re.compile(
            r'[\U00010000-\U0010ffff]'
            r'|[\u2600-\u26ff]'
            r'|[\u2700-\u27bf]'
        )
        self.assertIsNone(emoji_pattern.search(self.votes_js), "votes.js must contain zero emojis")


if __name__ == '__main__':
    unittest.main()
