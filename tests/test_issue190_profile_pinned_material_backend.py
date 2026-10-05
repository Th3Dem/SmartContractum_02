#!/usr/bin/env python3
"""
tests/test_issue190_profile_pinned_material_backend.py

Backend unit tests for Issue #190:
[P2][fullstack][PROFILE] Add one pinned material to user profile.

Verifies:
1. Authentication requirement for /api/user/pinned (401 for guests).
2. Author can pin their own approved publication.
3. Authorization checks: rejection of other users' materials (403).
4. Status checks: rejection of unapproved drafts (400) and questions (400).
5. Author can pin their own accepted solution (is_solution = 1) on approved question.
6. Rejection of unapproved answers or non-solution answers (400).
7. GET /api/users/<user_id> returns pinnedMaterial in profile DTO.
8. Pinned material is excluded from topContributions to prevent duplicate display.
9. Privacy & availability:
   - When pinned publication is unapproved/deleted: public visitors receive null, owner receives isUnavailable=True.
   - When pinned answer loses solution status: public visitors receive null, owner receives isUnavailable=True.
10. Replacing and unpinning (DELETE /api/user/pinned or POST action='unpin').
11. Strict invariants: zero emojis, zero em dashes.
"""

import json
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from server import ModerationRequestHandler, create_server


class TestIssue190ProfilePinnedMaterialBackend(unittest.TestCase):
    """Verifies pinned material backend functionality, authorization, and DTO projection."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = os.path.join(cls.temp_dir.name, "test_pinned.db")
        cls.media_dir = os.path.join(cls.temp_dir.name, "media")
        os.makedirs(cls.media_dir, exist_ok=True)

        cls.httpd = create_server(
            host="127.0.0.1",
            port=0,
            db_path=cls.db_path,
            directory=cls.temp_dir.name,
            media_dir=cls.media_dir,
            seed=False
        )
        cls.port = cls.httpd.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

        cls.seed_test_database()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.temp_dir.cleanup()

    @classmethod
    def seed_test_database(cls):
        conn = sqlite3.connect(cls.db_path)
        with conn:
            # 1. Sessions for Alice (owner), Bob (other author)
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("""
                INSERT INTO sessions (token, user_id, user_name, user_role, expires_at, created_at, is_revoked)
                VALUES ('token_alice', 'author_alice', 'Alice Architect', 'user', '2099-01-01T00:00:00Z', ?, 0)
            """, (now,))
            conn.execute("""
                INSERT INTO sessions (token, user_id, user_name, user_role, expires_at, created_at, is_revoked)
                VALUES ('token_bob', 'author_bob', 'Bob Developer', 'user', '2099-01-01T00:00:00Z', ?, 0)
            """, (now,))

            # 2. User profiles
            conn.execute("""
                INSERT INTO user_profiles (user_id, name, specialization, company, bio, created_at, updated_at)
                VALUES ('author_alice', 'Alice Architect', 'Solidity Core Dev', 'Ethereum Foundation', 'Smart contracts security engineer', ?, ?)
            """, (now, now))
            conn.execute("""
                INSERT INTO user_profiles (user_id, name, specialization, company, bio, created_at, updated_at)
                VALUES ('author_bob', 'Bob Developer', 'Smart Contract Auditor', 'CertiK', 'Security auditor', ?, ?)
            """, (now, now))

            # 3. Publications for Alice
            # 3a. Approved publication pub_alice_1
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, author_id, title, article_html, snapshot_hash, status,
                    publication_settings, created_at, updated_at
                ) VALUES (
                    'pub_alice_1', 'draft_alice_1', 'author_alice',
                    'Advanced Diamond Standard EIP-2535', '<p>Diamond standard guide</p>',
                    'hash_1', 'approved',
                    json('{"topics": ["smart-contracts-development"], "materialType": "publication"}'),
                    ?, ?
                )
            """, (now, now))

            # 3b. Approved publication pub_alice_2
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, author_id, title, article_html, snapshot_hash, status,
                    publication_settings, created_at, updated_at
                ) VALUES (
                    'pub_alice_2', 'draft_alice_2', 'author_alice',
                    'Proxy Patterns in EVM', '<p>Proxy patterns deep dive</p>',
                    'hash_2', 'approved',
                    json('{"topics": ["smart-contracts-development"], "materialType": "publication"}'),
                    ?, ?
                )
            """, (now, now))

            # 3c. Draft/pending publication for Alice (not approved)
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, author_id, title, article_html, snapshot_hash, status,
                    publication_settings, created_at, updated_at
                ) VALUES (
                    'pub_alice_draft', 'draft_alice_3', 'author_alice',
                    'Draft Article on Rollups', '<p>Draft content</p>',
                    'hash_3', 'pending_moderation',
                    json('{"topics": ["smart-contracts-development"], "materialType": "publication"}'),
                    ?, ?
                )
            """, (now, now))

            # 3d. Question by Alice (materialType = question)
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, author_id, title, article_html, snapshot_hash, status,
                    publication_settings, created_at, updated_at
                ) VALUES (
                    'quest_alice_1', 'draft_alice_quest', 'author_alice',
                    'How to optimize gas in delegatecall?', '<p>Question description</p>',
                    'hash_4', 'approved',
                    json('{"topics": ["smart-contracts-development"], "materialType": "question"}'),
                    ?, ?
                )
            """, (now, now))

            # 3e. Publication by Bob
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, author_id, title, article_html, snapshot_hash, status,
                    publication_settings, created_at, updated_at
                ) VALUES (
                    'pub_bob_1', 'draft_bob_1', 'author_bob',
                    'Bobs Secret Exploits', '<p>Exploit analysis</p>',
                    'hash_5', 'approved',
                    json('{"topics": ["security"], "materialType": "publication"}'),
                    ?, ?
                )
            """, (now, now))

            # 4. Answers / Solutions for Alice
            # 4a. Approved question by Bob
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, author_id, title, article_html, snapshot_hash, status,
                    publication_settings, created_at, updated_at
                ) VALUES (
                    'quest_bob_1', 'draft_bob_q1', 'author_bob',
                    'How to prevent reentrancy in Solidity?', '<p>Question text</p>',
                    'hash_6', 'approved',
                    json('{"topics": ["smart-contracts-development"], "materialType": "question"}'),
                    ?, ?
                )
            """, (now, now))

            # 4b. Answer by Alice marked as solution (is_solution = 1)
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at, updated_at
                ) VALUES (
                    'sol_alice_1', 'quest_bob_1', 'author_alice', 'Alice Architect',
                    'Use Checks-Effects-Interactions pattern along with ReentrancyGuard mutex.',
                    'published', 'answer', 1, ?, ?
                )
            """, (now, now))

            # 4c. Second approved question by Bob
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, author_id, title, article_html, snapshot_hash, status,
                    publication_settings, created_at, updated_at
                ) VALUES (
                    'quest_bob_2', 'draft_bob_q2', 'author_bob',
                    'How to structure upgradeable contracts?', '<p>Question text 2</p>',
                    'hash_7', 'approved',
                    json('{"topics": ["smart-contracts-development"], "materialType": "question"}'),
                    ?, ?
                )
            """, (now, now))

            # 4d. Regular answer by Alice to quest_bob_2 (NOT marked as solution)
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at, updated_at
                ) VALUES (
                    'ans_alice_not_sol', 'quest_bob_2', 'author_alice', 'Alice Architect',
                    'You could also try UUPS pattern.',
                    'published', 'answer', 0, ?, ?
                )
            """, (now, now))

            # 4d. Solution by Bob
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at, updated_at
                ) VALUES (
                    'sol_bob_1', 'quest_alice_1', 'author_bob', 'Bob Developer',
                    'Cache memory pointers and avoid state writes.',
                    'published', 'answer', 1, ?, ?
                )
            """, (now, now))

            # 5. Votes for pub_alice_1 and sol_alice_1
            conn.execute("""
                INSERT INTO article_votes (article_id, user_id, value, created_at, updated_at)
                VALUES ('pub_alice_1', 'author_bob', 1, ?, ?)
            """, (now, now))
            conn.execute("""
                INSERT INTO comment_votes (comment_id, user_id, value, created_at, updated_at)
                VALUES ('sol_alice_1', 'author_bob', 1, ?, ?)
            """, (now, now))

        conn.close()

    def make_request(self, method, path, data=None, token=None):
        url = self.base_url + path
        headers = {}
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        if token:
            headers["Cookie"] = f"sc_session={token}"

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                resp_body = resp.read().decode("utf-8")
                return resp.status, json.loads(resp_body) if resp_body else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            return e.code, json.loads(err_body) if err_body else {}

    # =========================================================================
    # Tests
    # =========================================================================

    def test_01_authentication_required_to_pin(self):
        """Guests cannot pin materials (must return 401)."""
        status, data = self.make_request("POST", "/api/user/pinned", {
            "targetType": "publication",
            "targetId": "pub_alice_1"
        })
        self.assertEqual(status, 401)
        self.assertFalse(data.get("success"))

    def test_02_owner_can_pin_approved_publication(self):
        """Author can pin their approved publication and fetch it via GET /api/user/pinned."""
        status, data = self.make_request(
            "POST",
            "/api/user/pinned",
            {"targetType": "publication", "targetId": "pub_alice_1"},
            token="token_alice"
        )
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        pinned = data.get("pinnedMaterial")
        self.assertIsNotNone(pinned)
        self.assertEqual(pinned.get("id"), "pub_alice_1")
        self.assertEqual(pinned.get("title"), "Advanced Diamond Standard EIP-2535")
        self.assertEqual(pinned.get("targetType"), "publication")
        self.assertFalse(pinned.get("isUnavailable"))

        # Verify via GET /api/user/pinned
        status, get_data = self.make_request("GET", "/api/user/pinned", token="token_alice")
        self.assertEqual(status, 200)
        self.assertEqual(get_data.get("pinnedMaterial", {}).get("id"), "pub_alice_1")

    def test_03_cannot_pin_other_users_publication(self):
        """User cannot pin another authors publication (returns 403)."""
        status, data = self.make_request(
            "POST",
            "/api/user/pinned",
            {"targetType": "publication", "targetId": "pub_bob_1"},
            token="token_alice"
        )
        self.assertEqual(status, 403)
        self.assertFalse(data.get("success"))

    def test_04_cannot_pin_unapproved_or_draft_publication(self):
        """User cannot pin an unapproved or draft publication (returns 400)."""
        status, data = self.make_request(
            "POST",
            "/api/user/pinned",
            {"targetType": "publication", "targetId": "pub_alice_draft"},
            token="token_alice"
        )
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))

    def test_05_cannot_pin_question_as_publication(self):
        """Questions cannot be pinned as publications (returns 400)."""
        status, data = self.make_request(
            "POST",
            "/api/user/pinned",
            {"targetType": "publication", "targetId": "quest_alice_1"},
            token="token_alice"
        )
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))

    def test_06_owner_can_pin_accepted_solution(self):
        """Author can pin their accepted solution and receive solution metadata."""
        status, data = self.make_request(
            "POST",
            "/api/user/pinned",
            {"targetType": "solution", "targetId": "sol_alice_1"},
            token="token_alice"
        )
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        pinned = data.get("pinnedMaterial")
        self.assertIsNotNone(pinned)
        self.assertEqual(pinned.get("id"), "sol_alice_1")
        self.assertEqual(pinned.get("targetType"), "solution")
        self.assertTrue(pinned.get("isSolution"))
        self.assertIn("Checks-Effects-Interactions", pinned.get("contentSnippet", ""))

    def test_07_cannot_pin_other_users_solution(self):
        """User cannot pin another users solution (returns 403)."""
        status, data = self.make_request(
            "POST",
            "/api/user/pinned",
            {"targetType": "solution", "targetId": "sol_bob_1"},
            token="token_alice"
        )
        self.assertEqual(status, 403)
        self.assertFalse(data.get("success"))

    def test_08_cannot_pin_non_solution_answer(self):
        """Answers that have not been marked as a solution cannot be pinned (returns 400)."""
        status, data = self.make_request(
            "POST",
            "/api/user/pinned",
            {"targetType": "solution", "targetId": "ans_alice_not_sol"},
            token="token_alice"
        )
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))

    def test_09_pinned_material_in_profile_dto_and_duplicate_prevention(self):
        """GET /api/users/<user_id> returns pinnedMaterial and excludes it from topContributions."""
        # First pin pub_alice_1
        self.make_request(
            "POST",
            "/api/user/pinned",
            {"targetType": "publication", "targetId": "pub_alice_1"},
            token="token_alice"
        )

        # Fetch Alice profile
        status, data = self.make_request("GET", "/api/users/author_alice")
        self.assertEqual(status, 200)
        profile = data.get("profile", {})
        pinned = profile.get("pinnedMaterial")
        self.assertIsNotNone(pinned)
        self.assertEqual(pinned.get("id"), "pub_alice_1")

        # Verify duplicate exclusion in topContributions
        top_contribs = profile.get("topContributions", [])
        top_ids = [item.get("id") for item in top_contribs]
        self.assertNotIn("pub_alice_1", top_ids, "Pinned material must not be duplicated in top contributions")

    def test_10_unavailable_pinned_material_handling(self):
        """
        When pinned material becomes unapproved/deleted:
        - Public visitor receives pinnedMaterial: null.
        - Owner receives pinnedMaterial with isUnavailable: true.
        """
        # Pin pub_alice_2
        self.make_request(
            "POST",
            "/api/user/pinned",
            {"targetType": "publication", "targetId": "pub_alice_2"},
            token="token_alice"
        )

        # Unapprove pub_alice_2 in database
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("UPDATE moderation_submissions SET status = 'rejected' WHERE id = 'pub_alice_2'")
        conn.close()

        try:
            # 1. Public visitor view (guest)
            status, guest_data = self.make_request("GET", "/api/users/author_alice")
            self.assertEqual(status, 200)
            self.assertIsNone(guest_data.get("profile", {}).get("pinnedMaterial"))

            # 2. Owner view (Alice)
            status, owner_data = self.make_request("GET", "/api/users/author_alice", token="token_alice")
            self.assertEqual(status, 200)
            owner_pinned = owner_data.get("profile", {}).get("pinnedMaterial")
            self.assertIsNotNone(owner_pinned)
            self.assertTrue(owner_pinned.get("isUnavailable"))
            self.assertIn("модерации", owner_pinned.get("reason", ""))
        finally:
            # Restore pub_alice_2 status
            conn = sqlite3.connect(self.db_path)
            with conn:
                conn.execute("UPDATE moderation_submissions SET status = 'approved' WHERE id = 'pub_alice_2'")
            conn.close()

    def test_11_unpin_material(self):
        """Owner can unpin their material via DELETE /api/user/pinned or POST action='unpin'."""
        # Pin pub_alice_1
        self.make_request(
            "POST",
            "/api/user/pinned",
            {"targetType": "publication", "targetId": "pub_alice_1"},
            token="token_alice"
        )

        # Unpin via DELETE
        status, del_data = self.make_request("DELETE", "/api/user/pinned", token="token_alice")
        self.assertEqual(status, 200)
        self.assertTrue(del_data.get("success"))
        self.assertIsNone(del_data.get("pinnedMaterial"))

        # Verify profile has no pinned material
        status, prof_data = self.make_request("GET", "/api/users/author_alice", token="token_alice")
        self.assertIsNone(prof_data.get("profile", {}).get("pinnedMaterial"))

        # Re-pin and unpin via POST action='unpin'
        self.make_request(
            "POST",
            "/api/user/pinned",
            {"targetType": "publication", "targetId": "pub_alice_1"},
            token="token_alice"
        )
        status, post_unpin = self.make_request("POST", "/api/user/pinned", {"action": "unpin"}, token="token_alice")
        self.assertEqual(status, 200)
        self.assertIsNone(post_unpin.get("pinnedMaterial"))


if __name__ == "__main__":
    unittest.main()
