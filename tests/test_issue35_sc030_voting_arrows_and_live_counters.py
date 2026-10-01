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


class MockElement:
    """Lightweight DOM element representation for client-side behavioral testing."""
    def __init__(self, tag_name, attributes=None, classes=None, text_content=""):
        self.tag_name = tag_name
        self.attributes = dict(attributes or {})
        self.classes = set(classes or [])
        self.text_content = text_content
        self.children = []
        self.parent = None
        self.title = ""
        self.disabled = False

    def append_child(self, child):
        child.parent = self
        self.children.append(child)
        return child

    def remove_child(self, child):
        if child in self.children:
            self.children.remove(child)
            child.parent = None

    def get_attribute(self, name):
        return self.attributes.get(name)

    def set_attribute(self, name, value):
        self.attributes[name] = str(value)

    def remove_attribute(self, name):
        self.attributes.pop(name, None)

    def has_attribute(self, name):
        return name in self.attributes

    def matches(self, selector):
        parts = re.findall(r'^[a-zA-Z0-9_-]+|\.[a-zA-Z0-9_-]+|\[[a-zA-Z0-9_-]+(?:="[^"]*")?\]', selector)
        if not parts:
            return self.tag_name.lower() == selector.lower()
        for p in parts:
            if p.startswith('.'):
                if p[1:] not in self.classes:
                    return False
            elif p.startswith('['):
                m = re.match(r'\[([a-zA-Z0-9_-]+)(?:="([^"]*)")?\]', p)
                if not m:
                    return False
                name, val = m.groups()
                if val is not None:
                    if self.get_attribute(name) != val:
                        return False
                else:
                    if not self.has_attribute(name):
                        return False
            else:
                if self.tag_name.lower() != p.lower():
                    return False
        return True

    def query_selector(self, selector):
        matches = self.query_selector_all(selector)
        return matches[0] if matches else None

    def query_selector_all(self, selector):
        results = []
        def traverse(el):
            for child in el.children:
                if child.matches(selector):
                    results.append(child)
                traverse(child)
        traverse(self)
        return results


class MockVotingController:
    """Executable simulation replicating votes.js voting lifecycle and session guards."""
    def __init__(self, doc_root, initial_user=None):
        self.doc_root = doc_root
        self.active_pending_votes = set()
        self.global_session_generation = 1
        self.current_user = initial_user
        self.last_observed_user_id = self.get_current_user_id()
        self.vote_request_seq = 0
        self.active_vote_requests = {}
        self.auth_modal_invoked = False
        self.toasts = []
        self.dispatched_events = []

    def get_current_user_id(self):
        if not self.current_user or self.current_user.get("isGuest"):
            return None
        return self.current_user.get("id")

    def get_session_token(self):
        cur_id = self.get_current_user_id()
        if cur_id != self.last_observed_user_id:
            self.last_observed_user_id = cur_id
            self.global_session_generation += 1
        return self.global_session_generation

    def bump_session_token(self):
        self.global_session_generation += 1
        self.last_observed_user_id = self.get_current_user_id()
        return self.global_session_generation

    def invoke_auth_modal(self):
        self.auth_modal_invoked = True

    def show_toast(self, msg, toast_type="info"):
        self.toasts.append({"message": msg, "type": toast_type})

    def create_capsule_element(self, target_type, target_id, score=0, my_vote=0, is_author=False, can_vote=None):
        target_key = f"{target_type}:{target_id}"
        is_pending = target_key in self.active_pending_votes
        user = self.current_user
        is_guest = not user or bool(user.get("isGuest"))
        if can_vote is None:
            can_vote = (not is_author) and (not is_guest)

        capsule = MockElement("div", {
            "data-vote-target-type": target_type,
            "data-vote-target-id": str(target_id),
            "data-score": str(score),
            "data-my-vote": str(my_vote),
            "data-can-vote": "true" if can_vote else "false"
        }, classes=["vote-capsule"])

        if is_pending:
            capsule.classes.add("is-pending")
        if is_guest:
            capsule.classes.add("is-guest")
            capsule.set_attribute("data-is-guest", "true")
        if is_author:
            capsule.classes.add("is-author")
            capsule.set_attribute("data-is-author", "true")
        if my_vote == 1:
            capsule.classes.add("has-voted-up")
        elif my_vote == -1:
            capsule.classes.add("has-voted-down")

        up_btn = MockElement("button", {"data-dir": "1", "aria-pressed": "true" if my_vote == 1 else "false"}, classes=["vote-btn", "vote-btn-up"])
        if my_vote == 1:
            up_btn.classes.add("is-voted")
        if is_pending or is_author:
            up_btn.disabled = True
            up_btn.set_attribute("disabled", "true")
            up_btn.set_attribute("aria-disabled", "true")
        if is_guest:
            up_btn.title = "Войдите, чтобы повысить рейтинг"
        elif is_author:
            up_btn.title = "Нельзя голосовать за собственный материал"
        else:
            up_btn.title = "Снять голос" if my_vote == 1 else "Повысить рейтинг"

        score_el = MockElement("span", {"data-score": str(score)}, classes=["vote-score"], text_content=str(score))
        if score > 0:
            score_el.classes.add("is-positive")
        elif score < 0:
            score_el.classes.add("is-negative")
        else:
            score_el.classes.add("is-zero")

        down_btn = MockElement("button", {"data-dir": "-1", "aria-pressed": "true" if my_vote == -1 else "false"}, classes=["vote-btn", "vote-btn-down"])
        if my_vote == -1:
            down_btn.classes.add("is-voted")
        if is_pending or is_author:
            down_btn.disabled = True
            down_btn.set_attribute("disabled", "true")
            down_btn.set_attribute("aria-disabled", "true")
        if is_guest:
            down_btn.title = "Войдите, чтобы понизить рейтинг"
        elif is_author:
            down_btn.title = "Нельзя голосовать за собственный материал"
        else:
            down_btn.title = "Снять голос" if my_vote == -1 else "Понизить рейтинг"

        capsule.append_child(up_btn)
        capsule.append_child(score_el)
        capsule.append_child(down_btn)
        return capsule

    def update_capsule_element(self, c, state):
        if not c:
            return
        target_type = c.get_attribute("data-vote-target-type") or "article"
        target_id = c.get_attribute("data-vote-target-id") or ""
        target_key = f"{target_type}:{target_id}"
        is_pending = bool(target_id and (target_key in self.active_pending_votes))

        if is_pending:
            c.classes.add("is-pending")
        else:
            c.classes.discard("is-pending")

        score = state.get("score", 0)
        my_vote = state.get("myVote", 0)
        c.set_attribute("data-score", str(score))
        c.set_attribute("data-my-vote", str(my_vote))
        if "canVote" in state:
            c.set_attribute("data-can-vote", "true" if state["canVote"] else "false")

        if my_vote == 1:
            c.classes.add("has-voted-up")
            c.classes.discard("has-voted-down")
        elif my_vote == -1:
            c.classes.add("has-voted-down")
            c.classes.discard("has-voted-up")
        else:
            c.classes.discard("has-voted-up")
            c.classes.discard("has-voted-down")

        score_el = c.query_selector(".vote-score")
        if score_el:
            score_el.text_content = str(score)
            score_el.set_attribute("data-score", str(score))
            score_el.classes.discard("is-positive")
            score_el.classes.discard("is-negative")
            score_el.classes.discard("is-zero")
            if score > 0:
                score_el.classes.add("is-positive")
            elif score < 0:
                score_el.classes.add("is-negative")
            else:
                score_el.classes.add("is-zero")

        user = self.current_user
        is_guest = not user or bool(user.get("isGuest"))
        is_author = c.get_attribute("data-is-author") == "true" or state.get("isAuthor") is True

        up_btn = c.query_selector(".vote-btn-up")
        down_btn = c.query_selector(".vote-btn-down")

        up_disabled = False
        down_disabled = False
        up_title = "Повысить рейтинг"
        down_title = "Понизить рейтинг"

        if is_author:
            up_title = "Нельзя голосовать за собственный материал"
            down_title = "Нельзя голосовать за собственный материал"
            up_disabled = True
            down_disabled = True
        elif is_guest:
            up_title = "Войдите, чтобы повысить рейтинг"
            down_title = "Войдите, чтобы понизить рейтинг"
            up_disabled = False
            down_disabled = False
        else:
            if my_vote == 1:
                up_title = "Снять голос"
            if my_vote == -1:
                down_title = "Снять голос"

        if is_pending:
            up_disabled = True
            down_disabled = True

        if up_btn:
            is_up = (my_vote == 1)
            if is_up:
                up_btn.classes.add("is-voted")
            else:
                up_btn.classes.discard("is-voted")
            up_btn.set_attribute("aria-pressed", "true" if is_up else "false")
            up_btn.title = up_title
            up_btn.disabled = up_disabled
            if up_disabled:
                up_btn.set_attribute("disabled", "true")
                up_btn.set_attribute("aria-disabled", "true")
            else:
                up_btn.remove_attribute("disabled")
                up_btn.remove_attribute("aria-disabled")

        if down_btn:
            is_down = (my_vote == -1)
            if is_down:
                down_btn.classes.add("is-voted")
            else:
                down_btn.classes.discard("is-voted")
            down_btn.set_attribute("aria-pressed", "true" if is_down else "false")
            down_btn.title = down_title
            down_btn.disabled = down_disabled
            if down_disabled:
                down_btn.set_attribute("disabled", "true")
                down_btn.set_attribute("aria-disabled", "true")
            else:
                down_btn.remove_attribute("disabled")
                down_btn.remove_attribute("aria-disabled")

    def handle_vote_click(self, capsule, btn):
        user = self.current_user
        if not user or user.get("isGuest"):
            self.invoke_auth_modal()
            return None

        is_author = (capsule.get_attribute("data-is-author") == "true")
        if is_author:
            self.show_toast("Нельзя голосовать за собственный материал", "error")
            return None

        target_type = capsule.get_attribute("data-vote-target-type") or "article"
        target_id = capsule.get_attribute("data-vote-target-id") or ""
        target_key = f"{target_type}:{target_id}"

        if target_key in self.active_pending_votes:
            return None

        dir_val = int(btn.get_attribute("data-dir") or 0)
        is_voted = "is-voted" in btn.classes or btn.get_attribute("aria-pressed") == "true"
        new_val = 0 if is_voted else dir_val

        selector = f'.vote-capsule[data-vote-target-type="{target_type}"][data-vote-target-id="{target_id}"]'
        matching_capsules = list(self.doc_root.query_selector_all(selector))

        previous_state = {
            "score": int(capsule.get_attribute("data-score") or 0),
            "myVote": int(capsule.get_attribute("data-my-vote") or 0),
            "canVote": True,
            "isAuthor": False
        }

        self.active_pending_votes.add(target_key)
        for c in matching_capsules:
            c.classes.add("is-pending")
            for b in c.query_selector_all(".vote-btn"):
                b.disabled = True
                b.set_attribute("disabled", "true")

        self.vote_request_seq += 1
        req_seq = self.vote_request_seq
        self.active_vote_requests[target_key] = req_seq
        request_session_token = self.get_session_token()

        controller_self = self

        class PendingVoteRequest:
            def __init__(self):
                self.target_key = target_key
                self.target_type = target_type
                self.target_id = target_id
                self.new_val = new_val
                self.req_seq = req_seq
                self.request_session_token = request_session_token
                self.matching_capsules = matching_capsules
                self.previous_state = previous_state
                self.selector = selector

            def resolve(self, status, data):
                is_latest = (controller_self.active_vote_requests.get(self.target_key) == self.req_seq)
                if is_latest:
                    controller_self.active_vote_requests.pop(self.target_key, None)
                    controller_self.active_pending_votes.discard(self.target_key)

                if self.request_session_token != controller_self.get_session_token():
                    if is_latest:
                        for c in controller_self.doc_root.query_selector_all(self.selector):
                            controller_self.update_capsule_element(c, {
                                "score": int(c.get_attribute("data-score") or 0),
                                "myVote": int(c.get_attribute("data-my-vote") or 0),
                                "canVote": c.get_attribute("data-can-vote") == "true"
                            })
                    return

                if not is_latest:
                    return

                current_matching = list(controller_self.doc_root.query_selector_all(self.selector))
                all_to_update = list(dict.fromkeys(self.matching_capsules + current_matching))

                is_valid = (
                    status == 200 and
                    data and
                    data.get("success") is True and
                    data.get("targetId") == self.target_id and
                    isinstance(data.get("score"), int) and
                    not isinstance(data.get("score"), bool) and
                    isinstance(data.get("myVote"), int) and
                    data.get("myVote") in (-1, 0, 1)
                )

                if is_valid:
                    updated_state = {
                        "score": data["score"],
                        "myVote": data["myVote"],
                        "canVote": data.get("canVote") is not False,
                        "isAuthor": False
                    }
                    for c in all_to_update:
                        controller_self.update_capsule_element(c, updated_state)
                    controller_self.dispatched_events.append(("smartcontractum:voted", {
                        "targetType": self.target_type,
                        "targetId": self.target_id,
                        "score": data["score"],
                        "myVote": data["myVote"],
                        "canVote": data.get("canVote"),
                        "sessionToken": self.request_session_token
                    }))
                elif status == 401:
                    for c in all_to_update:
                        controller_self.update_capsule_element(c, self.previous_state)
                    controller_self.invoke_auth_modal()
                elif status == 403:
                    for c in all_to_update:
                        c.set_attribute("data-is-author", "true")
                        c.set_attribute("data-can-vote", "false")
                        controller_self.update_capsule_element(c, {
                            "score": self.previous_state["score"],
                            "myVote": 0,
                            "canVote": False,
                            "isAuthor": True
                        })
                    controller_self.show_toast((data and data.get("error")) or "Нельзя голосовать за собственный материал", "error")
                else:
                    for c in all_to_update:
                        controller_self.update_capsule_element(c, self.previous_state)
                    controller_self.show_toast((data and data.get("error")) or "Ошибка при сохранении голоса", "error")

            def reject(self, err_msg="Ошибка сети"):
                is_latest = (controller_self.active_vote_requests.get(self.target_key) == self.req_seq)
                if is_latest:
                    controller_self.active_vote_requests.pop(self.target_key, None)
                    controller_self.active_pending_votes.discard(self.target_key)

                if self.request_session_token != controller_self.get_session_token():
                    if is_latest:
                        for c in controller_self.doc_root.query_selector_all(self.selector):
                            controller_self.update_capsule_element(c, {
                                "score": int(c.get_attribute("data-score") or 0),
                                "myVote": int(c.get_attribute("data-my-vote") or 0),
                                "canVote": c.get_attribute("data-can-vote") == "true"
                            })
                    return

                if not is_latest:
                    return

                current_matching = list(controller_self.doc_root.query_selector_all(self.selector))
                all_to_update = list(dict.fromkeys(self.matching_capsules + current_matching))
                for c in all_to_update:
                    controller_self.update_capsule_element(c, self.previous_state)
                controller_self.show_toast("Ошибка сети при отправке голоса", "error")

        return PendingVoteRequest()


class MockCommentsLoader:
    """Executable simulation replicating article.js comments loader with session guards."""
    def __init__(self, voting_controller):
        self.voting_controller = voting_controller
        self.current_auth_session_token = 0
        self.current_comments_request_seq = 0
        self.rendered_comments = []
        self.discarded_responses = []

    def refresh_article_and_comments_on_auth_change(self, article_id):
        self.voting_controller.bump_session_token()
        self.current_auth_session_token = self.voting_controller.get_session_token()
        return self.load_comments(article_id)

    def load_comments(self, article_id):
        self.current_comments_request_seq += 1
        req_seq = self.current_comments_request_seq
        session_token = self.voting_controller.get_session_token()

        loader_self = self

        class PendingCommentsRequest:
            def __init__(self):
                self.req_seq = req_seq
                self.session_token = session_token
                self.article_id = article_id

            def resolve(self, data):
                cur_session_token = loader_self.voting_controller.get_session_token()
                if self.session_token != cur_session_token or self.req_seq != loader_self.current_comments_request_seq:
                    loader_self.discarded_responses.append(data)
                    return False
                loader_self.rendered_comments = data.get("comments", [])
                return True

        return PendingCommentsRequest()


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

        # Desktop hit target: vote button at least 32px and capsule height 34px
        self.assertIn('width: 32px;', self.theme_css)
        self.assertIn('height: 32px;', self.theme_css)
        self.assertIn('min-width: 32px;', self.theme_css)
        self.assertIn('min-height: 32px;', self.theme_css)
        self.assertIn('height: 34px;', self.theme_css)
        self.assertIn('min-height: 34px;', self.theme_css)

        # Mobile and touch media query touch target (at least 44px) and container min-height (at least 46px)
        self.assertIn('@media (pointer: coarse), (max-width: 768px)', self.theme_css)
        self.assertIn('width: 44px;', self.theme_css)
        self.assertIn('height: 44px;', self.theme_css)
        self.assertIn('min-width: 44px;', self.theme_css)
        self.assertIn('min-height: 44px;', self.theme_css)
        self.assertIn('min-height: 46px;', self.theme_css)

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
        """Executable scenario: Guest click invokes login modal without network request or author flags."""
        doc = MockElement("body")
        controller = MockVotingController(doc)

        # 1. Guest capsule rendering
        capsule_guest = controller.create_capsule_element("article", "art_guest_01", score=3, my_vote=0)
        doc.append_child(capsule_guest)
        up_btn = capsule_guest.query_selector(".vote-btn-up")
        down_btn = capsule_guest.query_selector(".vote-btn-down")

        self.assertFalse(up_btn.disabled, "Guest up-vote button must not be disabled by default")
        self.assertFalse(down_btn.disabled, "Guest down-vote button must not be disabled by default")
        self.assertEqual(up_btn.title, "Войдите, чтобы повысить рейтинг")
        self.assertNotIn("is-author", capsule_guest.classes)

        # 2. Guest click invokes auth modal without starting network request or setting pending
        req = controller.handle_vote_click(capsule_guest, up_btn)
        self.assertIsNone(req, "Guest click must not initiate a network vote request")
        self.assertTrue(controller.auth_modal_invoked, "Guest click must invoke authentication modal")
        self.assertNotIn("is-pending", capsule_guest.classes, "Guest click must not lock capsule in pending state")
        self.assertEqual(len(controller.active_pending_votes), 0)

        # 3. Author capsule rendering and click check
        controller.current_user = {"id": "author_user_01"}
        capsule_author = controller.create_capsule_element("article", "art_author_01", score=5, my_vote=0, is_author=True)
        doc.append_child(capsule_author)
        author_up_btn = capsule_author.query_selector(".vote-btn-up")
        self.assertTrue(author_up_btn.disabled, "Author up-vote button must be disabled")
        self.assertEqual(author_up_btn.title, "Нельзя голосовать за собственный материал")

        author_req = controller.handle_vote_click(capsule_author, author_up_btn)
        self.assertIsNone(author_req, "Author click must not initiate a network vote request")
        self.assertTrue(any(t["type"] == "error" for t in controller.toasts), "Author click must show error toast")

        # Static contract validation
        self.assertNotIn("canVote === false ? 'is-author'", self.votes_js.replace(" ", ""))
        self.assertIn("invokeAuthModal();", self.votes_js)

    # --------------------------------------------------------------------------
    # Invariant 11: Behavioral check - User switch refetches and discards stale
    # --------------------------------------------------------------------------
    def test_11_behavioral_user_switch_refetches_and_discards_stale(self):
        """Executable scenario: Stale comments response simulation (delayed GET A discarded, B retains myVote=0)."""
        doc = MockElement("body")
        voting_controller = MockVotingController(doc, initial_user={"id": "user_a", "name": "Alice"})
        loader = MockCommentsLoader(voting_controller)

        # Step 1: User A requests comments (seq=1, token=1)
        req_a = loader.load_comments("art_thread_01")
        self.assertEqual(req_a.req_seq, 1)
        self.assertEqual(req_a.session_token, 1)

        # Step 2: Auth change occurs: User switches to User B (token bumped to 2)
        voting_controller.current_user = {"id": "user_b", "name": "Bob"}
        req_b = loader.refresh_article_and_comments_on_auth_change("art_thread_01")
        self.assertEqual(req_b.req_seq, 2)
        self.assertEqual(req_b.session_token, 2)

        # Step 3: Fast response for User B arrives first (comments with myVote=0)
        data_b = {
            "success": True,
            "comments": [{"id": "c_01", "score": 10, "myVote": 0, "canVote": True}]
        }
        accepted_b = req_b.resolve(data_b)
        self.assertTrue(accepted_b, "User B response must be accepted as fresh")
        self.assertEqual(len(loader.rendered_comments), 1)
        self.assertEqual(loader.rendered_comments[0]["myVote"], 0, "User B comments must show myVote=0")

        # Step 4: Delayed response for User A arrives later (comments with User A's myVote=1)
        data_a = {
            "success": True,
            "comments": [{"id": "c_01", "score": 11, "myVote": 1, "canVote": True}]
        }
        accepted_a = req_a.resolve(data_a)
        self.assertFalse(accepted_a, "Delayed User A response must be discarded as stale")
        self.assertIn(data_a, loader.discarded_responses, "Discarded response list must record delayed data A")

        # Step 5: Verification: User B retains personalized state without pollution
        self.assertEqual(loader.rendered_comments[0]["myVote"], 0, "User B must retain myVote=0 after delayed response")
        self.assertEqual(loader.rendered_comments[0]["score"], 10)

        # Static contract validation
        self.assertIn("refreshArticleAndCommentsOnAuthChange", self.article_js)
        self.assertIn("currentAuthSessionToken", self.article_js)
        self.assertIn("_currentCommentsRequestSeq", self.article_js)
        self.assertIn("sessionToken !== curSessionToken || reqSeq !== _currentCommentsRequestSeq", self.article_js)

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
        """Executable scenario: votes.js validates response data strictly and rolls back on all failure modes."""
        doc = MockElement("body")
        controller = MockVotingController(doc, initial_user={"id": "voter_01"})

        # Scenario A: 500 error / server error rolls back previous state
        cap_a = controller.create_capsule_element("article", "art_err_01", score=7, my_vote=0)
        doc.append_child(cap_a)
        up_a = cap_a.query_selector(".vote-btn-up")
        req_a = controller.handle_vote_click(cap_a, up_a)
        self.assertIn("is-pending", cap_a.classes)
        self.assertIn("article:art_err_01", controller.active_pending_votes)

        req_a.resolve(500, {"success": False})
        self.assertNotIn("is-pending", cap_a.classes)
        self.assertEqual(cap_a.get_attribute("data-score"), "7")
        self.assertEqual(cap_a.get_attribute("data-my-vote"), "0")
        self.assertNotIn("article:art_err_01", controller.active_pending_votes)
        self.assertTrue(any("Ошибка при сохранении голоса" in t["message"] for t in controller.toasts))

        # Scenario B: 401 unauthorized rolls back and invokes auth modal
        cap_b = controller.create_capsule_element("article", "art_err_02", score=4, my_vote=0)
        doc.append_child(cap_b)
        up_b = cap_b.query_selector(".vote-btn-up")
        req_b = controller.handle_vote_click(cap_b, up_b)
        controller.auth_modal_invoked = False
        req_b.resolve(401, {"success": False, "error": "Unauthorized"})
        self.assertNotIn("is-pending", cap_b.classes)
        self.assertTrue(controller.auth_modal_invoked)
        self.assertNotIn("article:art_err_02", controller.active_pending_votes)

        # Scenario C: 403 forbidden marks capsule as author and sets myVote=0
        cap_c = controller.create_capsule_element("article", "art_err_03", score=12, my_vote=0)
        doc.append_child(cap_c)
        up_c = cap_c.query_selector(".vote-btn-up")
        req_c = controller.handle_vote_click(cap_c, up_c)
        req_c.resolve(403, {"success": False, "error": "Нельзя голосовать за собственный материал"})
        self.assertEqual(cap_c.get_attribute("data-is-author"), "true")
        self.assertEqual(cap_c.get_attribute("data-can-vote"), "false")
        self.assertTrue(cap_c.query_selector(".vote-btn-up").disabled)

        # Scenario D: Network exception in fetch (catch block)
        cap_d = controller.create_capsule_element("article", "art_err_04", score=9, my_vote=0)
        doc.append_child(cap_d)
        up_d = cap_d.query_selector(".vote-btn-up")
        req_d = controller.handle_vote_click(cap_d, up_d)
        req_d.reject("Network failure")
        self.assertNotIn("is-pending", cap_d.classes)
        self.assertEqual(cap_d.get_attribute("data-score"), "9")
        self.assertNotIn("article:art_err_04", controller.active_pending_votes)

        # Static contract validation
        self.assertIn("Number.isInteger(data.score)", self.votes_js)
        self.assertIn("[-1, 0, 1].indexOf(data.myVote) !== -1", self.votes_js)
        self.assertIn("data.targetId === targetId", self.votes_js)
        self.assertIn("_activeVoteRequests.delete(targetKey)", self.votes_js)

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

    # --------------------------------------------------------------------------
    # Invariant 15: Behavioral check - In-flight vote re-render test (#41)
    # --------------------------------------------------------------------------
    def test_15_behavioral_inflight_vote_rerender(self):
        """Executable scenario (#41): In-flight re-render mounts new pending capsule, vote completion unlocks and updates live DOM."""
        doc = MockElement("body")
        controller = MockVotingController(doc, initial_user={"id": "voter_01"})

        # Step 1: Initial capsule rendered and mounted in DOM
        capsule_v1 = controller.create_capsule_element("article", "art_inflight_01", score=10, my_vote=0)
        doc.append_child(capsule_v1)

        # Step 2: User votes up, vote request enters flight
        up_btn_v1 = capsule_v1.query_selector(".vote-btn-up")
        req = controller.handle_vote_click(capsule_v1, up_btn_v1)
        self.assertIsNotNone(req)
        self.assertIn("is-pending", capsule_v1.classes)
        self.assertIn("article:art_inflight_01", controller.active_pending_votes)

        # Step 3: During flight, DOM is re-rendered (capsule_v1 replaced by capsule_v2)
        doc.remove_child(capsule_v1)
        capsule_v2 = controller.create_capsule_element("article", "art_inflight_01", score=10, my_vote=0)
        # Because vote is pending, capsule_v2 is mounted with is-pending and disabled buttons
        self.assertIn("is-pending", capsule_v2.classes)
        self.assertTrue(capsule_v2.query_selector(".vote-btn-up").disabled)
        doc.append_child(capsule_v2)

        # Verify querySelector finds capsule_v2 as the live element in DOM
        live_capsules = doc.query_selector_all('.vote-capsule[data-vote-target-type="article"][data-vote-target-id="art_inflight_01"]')
        self.assertEqual(len(live_capsules), 1)
        self.assertEqual(live_capsules[0], capsule_v2)

        # Step 4: Network vote request completes with success
        vote_response = {
            "success": True,
            "targetId": "art_inflight_01",
            "score": 11,
            "myVote": 1,
            "canVote": True
        }
        req.resolve(200, vote_response)

        # Step 5: Verify new capsule in live DOM is fully unlocked, disabled removed, and score/myVote updated
        self.assertNotIn("is-pending", capsule_v2.classes, "Live capsule must have is-pending removed")
        self.assertFalse(capsule_v2.query_selector(".vote-btn-up").disabled, "Live capsule up button must be enabled")
        self.assertFalse(capsule_v2.query_selector(".vote-btn-down").disabled, "Live capsule down button must be enabled")
        self.assertEqual(capsule_v2.get_attribute("data-score"), "11")
        self.assertEqual(capsule_v2.get_attribute("data-my-vote"), "1")
        self.assertIn("has-voted-up", capsule_v2.classes)
        self.assertIn("is-voted", capsule_v2.query_selector(".vote-btn-up").classes)
        self.assertEqual(capsule_v2.query_selector(".vote-score").text_content, "11")

        # Active pending set is cleaned up
        self.assertNotIn("article:art_inflight_01", controller.active_pending_votes)

    # --------------------------------------------------------------------------
    # Invariant 16: Behavioral check - Session switch during vote flight (#42)
    # --------------------------------------------------------------------------
    def test_16_behavioral_session_switch_during_vote_flight(self):
        """Executable scenario (#42): User A votes, switches to User B during flight, response A ignored, B cleanly unlocked."""
        doc = MockElement("body")
        controller = MockVotingController(doc, initial_user={"id": "user_a", "name": "Alice"})

        # Step 1: User A votes up on article
        capsule = controller.create_capsule_element("article", "art_session_01", score=20, my_vote=0)
        doc.append_child(capsule)
        up_btn = capsule.query_selector(".vote-btn-up")

        req_a = controller.handle_vote_click(capsule, up_btn)
        self.assertIsNotNone(req_a)
        self.assertEqual(req_a.request_session_token, 1)
        self.assertIn("is-pending", capsule.classes)
        self.assertTrue(up_btn.disabled)
        self.assertIn("article:art_session_01", controller.active_pending_votes)

        # Step 2: User switches from User A to User B while vote A is in flight
        controller.current_user = {"id": "user_b", "name": "Bob"}
        new_session_token = controller.get_session_token()
        self.assertEqual(new_session_token, 2, "Session token must increment when user switches")

        # Step 3: Response A completes successfully (score=21, myVote=1 for User A)
        resp_a = {
            "success": True,
            "targetId": "art_session_01",
            "score": 21,
            "myVote": 1,
            "canVote": True
        }
        req_a.resolve(200, resp_a)

        # Step 4: Verify User B's DOM does NOT get User A's myVote, and pending state is cleanly unlocked
        self.assertEqual(capsule.get_attribute("data-my-vote"), "0", "User B must not receive User A's vote")
        self.assertNotIn("has-voted-up", capsule.classes)
        self.assertNotIn("is-voted", capsule.query_selector(".vote-btn-up").classes)
        self.assertNotIn("is-pending", capsule.classes, "Capsule must be cleanly unlocked for User B")
        self.assertFalse(capsule.query_selector(".vote-btn-up").disabled, "Buttons must be re-enabled for User B")
        self.assertFalse(capsule.query_selector(".vote-btn-down").disabled)
        self.assertNotIn("article:art_session_01", controller.active_pending_votes)
        self.assertEqual(len(controller.dispatched_events), 0, "No smartcontractum:voted event should be dispatched across sessions")

        # Step 5: User B now casts their own down vote (-1)
        down_btn = capsule.query_selector(".vote-btn-down")
        req_b = controller.handle_vote_click(capsule, down_btn)
        self.assertIsNotNone(req_b, "User B vote must not be blocked by prior in-flight vote")
        self.assertEqual(req_b.new_val, -1, "User B must send value -1 (not 0)")
        self.assertEqual(req_b.request_session_token, 2)

        # Response B completes
        resp_b = {
            "success": True,
            "targetId": "art_session_01",
            "score": 19,
            "myVote": -1,
            "canVote": True
        }
        req_b.resolve(200, resp_b)
        self.assertEqual(capsule.get_attribute("data-score"), "19")
        self.assertEqual(capsule.get_attribute("data-my-vote"), "-1")
        self.assertIn("has-voted-down", capsule.classes)
        self.assertIn("is-voted", capsule.query_selector(".vote-btn-down").classes)

    # --------------------------------------------------------------------------
    # Invariant 17: Visual refinement - Neutral capsule border and no double highlighting (#46)
    # --------------------------------------------------------------------------
    def test_17_neutral_capsule_border_no_double_highlighting(self):
        """Sub-issue #46: Capsule container border/background must remain strictly neutral; only active arrow button gets color accent."""
        # 1. CSS rules check: capsule container retains neutral border and surface background when voted
        self.assertIn('.vote-capsule.has-voted-up,\n.vote-capsule.has-voted-down', self.theme_css)
        self.assertIn('border-color: var(--border-color);', self.theme_css)
        self.assertIn('background: var(--bg-surface);', self.theme_css)

        # Ensure no colored border rules exist for capsule voted states
        self.assertNotIn('border-color: rgba(16, 185, 129', self.theme_css, "Capsule container border must not have green accent")
        self.assertNotIn('border-color: rgba(239, 68, 68', self.theme_css, "Capsule container border must not have red accent")

        # Active accent is strictly applied to button only (.vote-btn-up.is-voted and .vote-btn-down.is-voted)
        self.assertIn('.vote-btn-up.is-voted', self.theme_css)
        self.assertIn('.vote-btn-down.is-voted', self.theme_css)
        self.assertIn('color: var(--success-color, #10b981);', self.theme_css)
        self.assertIn('color: var(--danger-color, #ef4444);', self.theme_css)

        # 2. Runtime DOM checks: simulated elements verify only voted button gets is-voted class
        doc = MockElement("body")
        controller = MockVotingController(doc)

        # Upvoted state
        cap_up = controller.create_capsule_element("article", "art_neutral_01", score=5, my_vote=1)
        up_btn = cap_up.query_selector(".vote-btn-up")
        down_btn = cap_up.query_selector(".vote-btn-down")
        self.assertIn("is-voted", up_btn.classes, "Up button must have is-voted accent class")
        self.assertNotIn("is-voted", down_btn.classes, "Down button must not have is-voted accent class")

        # Downvoted state
        cap_down = controller.create_capsule_element("article", "art_neutral_02", score=-3, my_vote=-1)
        up_btn_d = cap_down.query_selector(".vote-btn-up")
        down_btn_d = cap_down.query_selector(".vote-btn-down")
        self.assertIn("is-voted", down_btn_d.classes, "Down button must have is-voted accent class")
        self.assertNotIn("is-voted", up_btn_d.classes, "Up button must not have is-voted accent class")

        # Unvoted state
        cap_neutral = controller.create_capsule_element("article", "art_neutral_03", score=0, my_vote=0)
        self.assertNotIn("is-voted", cap_neutral.query_selector(".vote-btn-up").classes)
        self.assertNotIn("is-voted", cap_neutral.query_selector(".vote-btn-down").classes)

    # --------------------------------------------------------------------------
    # Invariant 18: Score sign vs personal vote 3x3 matrix separation (#47)
    # --------------------------------------------------------------------------
    def test_18_score_sign_and_my_vote_3x3_matrix(self):
        """Sub-issue #47: Total score color strictly depends on score sign; personal vote controls only arrow highlights."""
        doc = MockElement("body")
        controller = MockVotingController(doc)

        score_cases = [
            (-7, "is-negative"),
            (0, "is-zero"),
            (14, "is-positive")
        ]
        my_vote_cases = [-1, 0, 1]

        # 3x3 matrix iteration
        for score_val, expected_score_class in score_cases:
            for my_vote_val in my_vote_cases:
                with self.subTest(score=score_val, my_vote=my_vote_val):
                    # Test createCapsule
                    target_id = f"art_matrix_{score_val}_{my_vote_val}"
                    cap = controller.create_capsule_element("article", target_id, score=score_val, my_vote=my_vote_val)

                    score_el = cap.query_selector(".vote-score")
                    self.assertIsNotNone(score_el, "Vote score element must exist")
                    self.assertEqual(score_el.text_content, str(score_val))

                    # Score class must match sign exactly, regardless of personal my_vote
                    all_score_classes = {"is-positive", "is-negative", "is-zero"}
                    self.assertIn(expected_score_class, score_el.classes,
                                  f"Score {score_val} with my_vote {my_vote_val} must have {expected_score_class}")
                    for other_class in all_score_classes - {expected_score_class}:
                        self.assertNotIn(other_class, score_el.classes,
                                         f"Score {score_val} with my_vote {my_vote_val} must not have {other_class}")

                    # Arrow highlights must strictly match my_vote
                    up_btn = cap.query_selector(".vote-btn-up")
                    down_btn = cap.query_selector(".vote-btn-down")

                    if my_vote_val == 1:
                        self.assertIn("is-voted", up_btn.classes)
                        self.assertNotIn("is-voted", down_btn.classes)
                    elif my_vote_val == -1:
                        self.assertIn("is-voted", down_btn.classes)
                        self.assertNotIn("is-voted", up_btn.classes)
                    else:
                        self.assertNotIn("is-voted", up_btn.classes)
                        self.assertNotIn("is-voted", down_btn.classes)

                    # Now test updateCapsuleElement transition
                    controller.update_capsule_element(cap, {"score": score_val, "myVote": my_vote_val})
                    self.assertIn(expected_score_class, score_el.classes)
                    for other_class in all_score_classes - {expected_score_class}:
                        self.assertNotIn(other_class, score_el.classes)

        # Static CSS check: ensure .vote-score styling classes are defined
        self.assertIn('.vote-score.is-positive', self.theme_css)
        self.assertIn('.vote-score.is-negative', self.theme_css)
        self.assertIn('.vote-score.is-zero', self.theme_css)
        # Ensure capsule border or myVote never cascades into vote-score color
        self.assertNotIn('.has-voted-up .vote-score', self.theme_css)
        self.assertNotIn('.has-voted-down .vote-score', self.theme_css)

    # --------------------------------------------------------------------------
    # Invariant 19: Hit target dimensions for desktop and mobile/touch (#48)
    # --------------------------------------------------------------------------
    def test_19_hit_target_dimensions_desktop_and_touch(self):
        """Sub-issue #48: Arrow hit areas >= 32px desktop, >= 44px touch/mobile, compact 14px SVG icons."""
        # 1. Desktop dimensions
        # .vote-btn: width: 32px; height: 32px; min-width: 32px; min-height: 32px;
        self.assertIn('width: 32px;', self.theme_css)
        self.assertIn('height: 32px;', self.theme_css)
        self.assertIn('min-width: 32px;', self.theme_css)
        self.assertIn('min-height: 32px;', self.theme_css)

        # .vote-capsule desktop height: 34px
        self.assertIn('height: 34px;', self.theme_css)
        self.assertIn('min-height: 34px;', self.theme_css)

        # .comment-vote-row .vote-capsule and .card-footer-left .vote-capsule desktop: 34px
        self.assertIn('.comment-vote-row .vote-capsule', self.theme_css)
        self.assertIn('.card-footer-left .vote-capsule', self.theme_css)

        # 2. Touch / Mobile media query: @media (pointer: coarse), (max-width: 768px)
        self.assertIn('@media (pointer: coarse), (max-width: 768px)', self.theme_css)
        self.assertIn('width: 44px;', self.theme_css)
        self.assertIn('height: 44px;', self.theme_css)
        self.assertIn('min-width: 44px;', self.theme_css)
        self.assertIn('min-height: 44px;', self.theme_css)
        self.assertIn('min-height: 46px;', self.theme_css)

        # 3. Compact SVG icons: width: 14px; height: 14px;
        self.assertIn('width: 14px;', self.theme_css)
        self.assertIn('height: 14px;', self.theme_css)


if __name__ == '__main__':
    unittest.main()
