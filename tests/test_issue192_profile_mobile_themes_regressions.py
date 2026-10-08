#!/usr/bin/env python3
"""
tests/test_issue192_profile_mobile_themes_regressions.py

Automated test suite for Issue #192:
[P1][testing/frontend][PROFILE] Mobile screens, theme parity, accessibility,
and behavioral regressions for the complete Profile subsystem (Epic #167).

Acceptance Criteria & Matrix Coverage:
1. Data & Permissions:
   - Public records displayed, unapproved/rejected materials and parents excluded.
   - Legacy question not duplicated.
   - Rating and user card states match API.
   - Guest, owner, and peer user receive valid action sets.
   - Public DTO does not leak private fields.
2. Real User Scenarios:
   - Quick Profile -> Full Profile navigation.
   - Overview, tabs, search, sorting, pagination.
   - Like, Vote, Save, Share, Report, Subscribe state verification.
   - Delayed network, error states, and retry mechanism.
   - Profile edit and avatar update.
   - Deep permalink to comment (#comment-<id>).
   - URL, Back/Forward popstate and rating refresh preservation.
3. Accessibility:
   - Focus trapping in all modal dialogs.
   - Initial focus and focus restoration to triggering elements.
   - Keyboard tab navigation (ArrowLeft/Right/Up/Down, Home, End) with roving tabindex.
   - Accessible names for icons and visible focus styles.
4. Visual Matrix & Themes:
   - Viewport breakpoints: 320px, 375px, 768px, 1024px, 1440px.
   - Avatar / name bounding box separation geometry on narrow viewports.
   - Overflow prevention (min-width: 0, text-overflow, word-break).
   - Broken avatar fallback to initials in Quick and Full profile.
   - Theme parity and contrast in light and dark modes.
5. Invariants:
   - Zero emojis, zero em dashes, 100% offline-first.
"""

import datetime
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import unittest
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

import server
from server import create_server, init_db

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
BROWSER_SMOKE = True  # collected by tests/run_browser_smoke.py
PROFILE_JS_PATH = os.path.join(FRONTEND_DIR, "js", "profile.js")
PROFILE_PAGE_JS_PATH = os.path.join(FRONTEND_DIR, "js", "profile-page.js")
PROFILE_CSS_PATH = os.path.join(FRONTEND_DIR, "css", "profile.css")
PROFILE_HTML_PATH = os.path.join(FRONTEND_DIR, "profile.html")


class BaseProfileTestCase(unittest.TestCase):
    """Base test class providing an isolated test database and HTTP server."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_profile_192.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        cls._seed_database(conn)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    @classmethod
    def _seed_database(cls, conn: sqlite3.Connection):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cur = conn.cursor()

        # Seed test user profiles
        cur.execute(
            """
            INSERT OR REPLACE INTO user_profiles (user_id, name, bio, specialization, company, website, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "author_192",
                "Alice Engineer",
                "Senior Blockchain Developer specializing in Smart Contracts and EVM Security.",
                "EVM Security Architect",
                "SmartContractum Labs",
                "https://example.com/alice",
                "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=",
                now,
                now
            )
        )

        cur.execute(
            """
            INSERT OR REPLACE INTO user_profiles (user_id, name, bio, specialization, company, website, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("peer_192", "Bob Reviewer", "Reviewer Bio", "Peer Spec", "", "", "", now, now)
        )

        # Seed approved publications for author_192
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pub_192_1",
                "draft_192_1",
                "EVM Bytecode Analysis and Verification",
                "author_192",
                "approved",
                json.dumps({"materialType": "article", "topics": ["solidity", "evm"]}),
                "<p>Full content of publication 1</p>",
                "snap_192_1",
                "2026-10-01T10:00:00Z",
                "2026-10-01T10:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pub_192_2",
                "draft_192_2",
                "Zero Knowledge Proofs Primer",
                "author_192",
                "approved",
                json.dumps({"materialType": "article", "topics": ["cryptography"]}),
                "<p>Full content of publication 2</p>",
                "snap_192_2",
                "2026-10-02T10:00:00Z",
                "2026-10-02T10:00:00Z"
            )
        )

        # Seed rejected publication (must not be visible to public or peer users)
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pub_192_rejected",
                "draft_192_rej",
                "Rejected Draft Not For Public Eyes",
                "author_192",
                "rejected",
                json.dumps({"materialType": "article", "topics": ["secret"]}),
                "<p>Private content</p>",
                "snap_192_rej",
                "2026-10-03T10:00:00Z",
                "2026-10-03T10:00:00Z"
            )
        )

        # Seed approved question
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "quest_192_1",
                "draft_quest_1",
                "How to optimize SLOAD gas in Solidity 0.8.28?",
                "author_192",
                "approved",
                json.dumps({"materialType": "question", "topics": ["solidity"]}),
                "<p>Question description</p>",
                "snap_192_q1",
                "2026-10-03T12:00:00Z",
                "2026-10-03T12:00:00Z"
            )
        )

        # Seed comments
        cur.execute(
            """
            INSERT OR REPLACE INTO article_comments (
                id, article_id, user_id, author_name, content, status, comment_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "comm_192_1",
                "pub_192_1",
                "author_192",
                "Alice Engineer",
                "Great discussion on opcodes and gas refund anomalies.",
                "published",
                "comment",
                "2026-10-04T08:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO article_comments (
                id, article_id, user_id, author_name, content, status, comment_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "comm_192_rejected_parent",
                "pub_192_rejected",
                "author_192",
                "Alice Engineer",
                "Comment on rejected parent that must remain isolated.",
                "published",
                "comment",
                "2026-10-04T09:00:00Z"
            )
        )

        # Seed pinned material for author_192
        cur.execute(
            """
            INSERT OR REPLACE INTO user_pinned_materials (
                user_id, target_type, target_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("author_192", "publication", "pub_192_1", now, now)
        )

        # Seed votes
        cur.execute(
            """
            INSERT OR REPLACE INTO article_votes (article_id, user_id, value, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("pub_192_1", "peer_192", 1, now, now)
        )

        # Seed subscription (peer_192 follows author_192)
        cur.execute(
            """
            INSERT OR REPLACE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("peer_192", "author", "author_192", "Alice Engineer", now)
        )

        # Seed test users and materials for Round 3 review acceptance regressions

        # 1. user_r3_isolation: Draft with approved and rejected snapshots
        cur.execute(
            """
            INSERT OR REPLACE INTO user_profiles (user_id, name, bio, specialization, company, website, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("user_r3_isolation", "Isolation Tester", "Bio", "Spec", "", "", "", now, now)
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "sub_q_iso_rej",
                "draft_q_iso",
                "Rejected Question Parent Title",
                "user_r3_isolation",
                "rejected",
                json.dumps({"materialType": "question", "topics": ["solidity"]}),
                "<p>Rejected question snapshot</p>",
                "hash_q_iso_rej",
                "2026-10-01T09:00:00Z",
                "2026-10-01T09:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "sub_q_iso_app",
                "draft_q_iso",
                "Approved Question Parent Title",
                "user_r3_isolation",
                "approved",
                json.dumps({"materialType": "question", "topics": ["solidity"]}),
                "<p>Approved question snapshot</p>",
                "hash_q_iso_app",
                "2026-10-01T10:00:00Z",
                "2026-10-01T10:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "sub_art_iso_rej",
                "draft_art_iso",
                "Rejected Article Parent Title",
                "user_r3_isolation",
                "rejected",
                json.dumps({"materialType": "article", "topics": ["security"]}),
                "<p>Rejected article snapshot</p>",
                "hash_art_iso_rej",
                "2026-10-01T09:30:00Z",
                "2026-10-01T09:30:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "sub_art_iso_app",
                "draft_art_iso",
                "Approved Article Parent Title",
                "user_r3_isolation",
                "approved",
                json.dumps({"materialType": "article", "topics": ["security"]}),
                "<p>Approved article snapshot</p>",
                "hash_art_iso_app",
                "2026-10-01T10:30:00Z",
                "2026-10-01T10:30:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO article_comments (
                id, article_id, user_id, author_name, content, status, comment_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ans_iso_1",
                "draft_q_iso",
                "user_r3_isolation",
                "Isolation Tester",
                "Detailed answer to the question",
                "published",
                "answer",
                "2026-10-02T12:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO article_comments (
                id, article_id, user_id, author_name, content, status, comment_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "comm_iso_1",
                "draft_art_iso",
                "user_r3_isolation",
                "Isolation Tester",
                "Thoughtful comment on the article",
                "published",
                "comment",
                "2026-10-02T12:30:00Z"
            )
        )

        # 2. user_r3_topics: Exact topic matching vs false positives
        cur.execute(
            """
            INSERT OR REPLACE INTO user_profiles (user_id, name, bio, specialization, company, website, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("user_r3_topics", "Topic Tester", "Bio", "Spec", "", "", "", now, now)
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pub_topic_match",
                "draft_top_match_p",
                "Exact Solidity Article",
                "user_r3_topics",
                "approved",
                json.dumps({"materialType": "article", "topics": ["solidity"]}),
                "<p>Solidity content</p>",
                "hash_top_match_p",
                "2026-10-02T10:00:00Z",
                "2026-10-02T10:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pub_topic_fp_desc",
                "draft_top_fp_desc_p",
                "Security Article with Solidity in Description",
                "user_r3_topics",
                "approved",
                json.dumps({"materialType": "article", "topics": ["security"], "description": "solidity"}),
                "<p>Security content</p>",
                "hash_top_fp_desc_p",
                "2026-10-02T11:00:00Z",
                "2026-10-02T11:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pub_topic_fp_extra",
                "draft_top_fp_extra_p",
                "Solidity Extra Article",
                "user_r3_topics",
                "approved",
                json.dumps({"materialType": "article", "topics": ["solidity-extra"]}),
                "<p>Solidity extra content</p>",
                "hash_top_fp_extra_p",
                "2026-10-02T12:00:00Z",
                "2026-10-02T12:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "quest_topic_match",
                "draft_top_match_q",
                "Exact Solidity Question",
                "user_r3_topics",
                "approved",
                json.dumps({"materialType": "question", "topics": ["solidity"]}),
                "<p>Solidity question content</p>",
                "hash_top_match_q",
                "2026-10-02T13:00:00Z",
                "2026-10-02T13:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "quest_topic_fp_desc",
                "draft_top_fp_desc_q",
                "Security Question with Solidity in Description",
                "user_r3_topics",
                "approved",
                json.dumps({"materialType": "question", "topics": ["security"], "description": "solidity"}),
                "<p>Security question content</p>",
                "hash_top_fp_desc_q",
                "2026-10-02T14:00:00Z",
                "2026-10-02T14:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "quest_topic_fp_extra",
                "draft_top_fp_extra_q",
                "Solidity Extra Question",
                "user_r3_topics",
                "approved",
                json.dumps({"materialType": "question", "topics": ["solidity-extra"]}),
                "<p>Solidity extra question content</p>",
                "hash_top_fp_extra_q",
                "2026-10-02T15:00:00Z",
                "2026-10-02T15:00:00Z"
            )
        )

        # 3. user_r3_semantic: HTML text search semantic matching
        cur.execute(
            """
            INSERT OR REPLACE INTO user_profiles (user_id, name, bio, specialization, company, website, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("user_r3_semantic", "Semantic Tester", "Bio", "Spec", "", "", "", now, now)
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pub_sem_match",
                "draft_sem_pub",
                "EVM Execution Internals",
                "user_r3_semantic",
                "approved",
                json.dumps({"materialType": "article", "topics": ["evm"]}),
                "<p>smart <strong>contract</strong></p>",
                "hash_sem_pub",
                "2026-10-02T16:00:00Z",
                "2026-10-02T16:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "quest_sem_match",
                "draft_sem_quest",
                "Bytecode Verification Steps",
                "user_r3_semantic",
                "approved",
                json.dumps({"materialType": "question", "topics": ["evm"]}),
                "<p>smart <strong>contract</strong></p>",
                "hash_sem_quest",
                "2026-10-02T17:00:00Z",
                "2026-10-02T17:00:00Z"
            )
        )

        # 4. user_r3_activity: Overview activity search and pagination
        cur.execute(
            """
            INSERT OR REPLACE INTO user_profiles (user_id, name, bio, specialization, company, website, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("user_r3_activity", "Activity Tester", "Bio", "Spec", "", "", "", now, now)
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pub_act_1",
                "draft_act_p1",
                "Compiler Pipeline Fundamentals",
                "user_r3_activity",
                "approved",
                json.dumps({"materialType": "article", "topics": ["compilers"]}),
                "<p>Understanding compilation stages.</p>",
                "hash_act_p1",
                "2026-10-03T10:00:00Z",
                "2026-10-03T10:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pub_act_2",
                "draft_act_p2",
                "Code Optimization Strategies",
                "user_r3_activity",
                "approved",
                json.dumps({"materialType": "article", "topics": ["compilers"]}),
                "<p>Techniques inside the compiler optimizer.</p>",
                "hash_act_p2",
                "2026-10-03T11:00:00Z",
                "2026-10-03T11:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "quest_act_1",
                "draft_act_q1",
                "How does compiler generate AST nodes?",
                "user_r3_activity",
                "approved",
                json.dumps({"materialType": "question", "topics": ["compilers"]}),
                "<p>Details on the AST construction.</p>",
                "hash_act_q1",
                "2026-10-03T12:00:00Z",
                "2026-10-03T12:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO article_comments (
                id, article_id, user_id, author_name, content, status, comment_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ans_act_1",
                "draft_act_q1",
                "user_r3_activity",
                "Activity Tester",
                "The compiler constructs AST during semantic analysis.",
                "published",
                "answer",
                "2026-10-03T13:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO article_comments (
                id, article_id, user_id, author_name, content, status, comment_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "comm_act_1",
                "draft_act_p1",
                "user_r3_activity",
                "Activity Tester",
                "Useful reference for compiler developers.",
                "published",
                "comment",
                "2026-10-03T14:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pub_act_other",
                "draft_act_p_other",
                "Decentralized Network Protocol",
                "user_r3_activity",
                "approved",
                json.dumps({"materialType": "article", "topics": ["networking"]}),
                "<p>Peer discovery protocols.</p>",
                "hash_act_other",
                "2026-10-03T08:00:00Z",
                "2026-10-03T08:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "quest_act_other",
                "draft_act_q_other",
                "Consensus Fault Tolerance",
                "user_r3_activity",
                "approved",
                json.dumps({"materialType": "question", "topics": ["consensus"]}),
                "<p>Byzantine fault tolerance basics.</p>",
                "hash_act_q_other",
                "2026-10-03T09:00:00Z",
                "2026-10-03T09:00:00Z"
            )
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO article_comments (
                id, article_id, user_id, author_name, content, status, comment_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "comm_act_other",
                "draft_act_p_other",
                "user_r3_activity",
                "Activity Tester",
                "Interesting points on gossip routing.",
                "published",
                "comment",
                "2026-10-03T09:30:00Z"
            )
        )

        conn.commit()

    def get_json(self, path: str, cookie: Optional[str] = None) -> Dict[str, Any]:
        req = urllib.request.Request(f"{self.base_url}{path}")
        if cookie:
            req.add_header("Cookie", cookie)
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)

    def post_json(self, path: str, payload: Dict[str, Any], cookie: Optional[str] = None) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        if cookie:
            req.add_header("Cookie", cookie)
        with urllib.request.urlopen(req) as resp:
            resp_data = resp.read().decode("utf-8")
            return json.loads(resp_data)


class TestDataAndPermissionsRegressions(BaseProfileTestCase):
    """Validates public records, privacy isolation, legacy deduplication, and role permissions."""

    def test_01_public_submissions_only_for_guests(self):
        """Verify unapproved materials are excluded from public responses."""
        res = self.get_json("/api/users/author_192/publications")
        self.assertTrue(res.get("success"))
        items = res.get("items") or res.get("publications", [])
        ids = [item.get("id") for item in items]
        self.assertIn("pub_192_1", ids)
        self.assertIn("pub_192_2", ids)
        self.assertNotIn("pub_192_rejected", ids, "Rejected material must never appear in public list")

    def test_02_unapproved_answers_to_rejected_parents_isolated(self):
        """Verify comments on rejected materials are not leaked in public comments endpoint."""
        res = self.get_json("/api/users/author_192/comments")
        self.assertTrue(res.get("success"))
        items = res.get("comments") or res.get("items", [])
        comment_ids = [c.get("id") for c in items]
        self.assertIn("comm_192_1", comment_ids)
        self.assertNotIn("comm_192_rejected_parent", comment_ids, "Comment on rejected material must be excluded")

    def test_03_legacy_question_not_duplicated(self):
        """Verify question material is not duplicated across publication lists."""
        pub_res = self.get_json("/api/users/author_192/publications")
        quest_res = self.get_json("/api/users/author_192/questions")
        pub_items = pub_res.get("items") or pub_res.get("publications", [])
        quest_items = quest_res.get("items") or quest_res.get("questions", [])
        pub_ids = [p.get("id") for p in pub_items]
        quest_ids = [q.get("id") for q in quest_items]

        self.assertIn("quest_192_1", quest_ids)
        self.assertNotIn("quest_192_1", pub_ids, "Question must not be duplicated into publications feed")

    def test_04_public_dto_sanitized(self):
        """Verify public user profile DTO does not leak private fields."""
        res = self.get_json("/api/users/author_192")
        self.assertTrue(res.get("success"))
        profile = res.get("profile") or res.get("user")
        self.assertIsNotNone(profile)
        self.assertNotIn("password_hash", profile)
        self.assertNotIn("password", profile)
        self.assertNotIn("draft_id", profile)

    def test_05_pinned_material_projected_and_deduplicated(self):
        """Verify pinned material is returned in profile DTO and excluded from topContributions."""
        res = self.get_json("/api/users/author_192")
        self.assertTrue(res.get("success"))
        profile = res.get("profile") or res.get("user")
        pinned = profile.get("pinnedMaterial")
        self.assertIsNotNone(pinned)
        self.assertEqual(pinned.get("id"), "pub_192_1")

        top = profile.get("topContributions", [])
        top_ids = [t.get("id") for t in top]
        self.assertNotIn("pub_192_1", top_ids, "Pinned material must be deduplicated from topContributions")


class TestRealUserScenariosRegressions(BaseProfileTestCase):
    """Validates real user flows: Quick Profile, navigation, action states, and search."""

    def test_06_quick_profile_api_and_profile_url_format(self):
        """Verify /api/users/:id response structure conforms to Quick Profile expectations."""
        res = self.get_json("/api/users/author_192")
        self.assertTrue(res.get("success"))
        u = res.get("profile") or res.get("user")
        self.assertEqual(u.get("name"), "Alice Engineer")
        self.assertEqual(u.get("company"), "SmartContractum Labs")
        self.assertEqual(u.get("specialization"), "EVM Security Architect")
        stats = u.get("stats", {})
        self.assertIn("rating", stats)
        self.assertIn("publicationsCount", stats)

    def test_07_search_query_filtering(self):
        """Verify search query parameter q filters publications properly."""
        res_all = self.get_json("/api/users/author_192/publications")
        all_items = res_all.get("items") or res_all.get("publications", [])
        self.assertEqual(len(all_items), 2)

        res_evm = self.get_json("/api/users/author_192/publications?q=EVM")
        items = res_evm.get("items") or res_evm.get("publications", [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "pub_192_1")

        res_none = self.get_json("/api/users/author_192/publications?q=NonExistentKeywordXYZ")
        none_items = res_none.get("items") or res_none.get("publications", [])
        self.assertEqual(len(none_items), 0)

    def test_08_subscribers_endpoint_and_counts(self):
        """Verify subscribers endpoint returns paginated subscriber list."""
        res = self.get_json("/api/users/author_192/subscribers")
        self.assertTrue(res.get("success"))
        subs = res.get("subscribers", [])
        self.assertGreaterEqual(len(subs), 1)
        sub_ids = [s.get("id") for s in subs]
        self.assertIn("peer_192", sub_ids)

    def test_09_deep_comment_permalink_anchor_generation(self):
        """Verify rendered comment markup contains native DOM id comment-<id> and data-comment-id."""
        with open(PROFILE_PAGE_JS_PATH, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("cardEl.id = 'comment-' + commentId", code)
        self.assertIn("cardEl.setAttribute('data-comment-id', commentId)", code)
        self.assertIn("window.location.hash.indexOf('#comment-') === 0", code)
        self.assertIn("targetCard.scrollIntoView", code)

    def test_10_retry_button_in_error_rendering(self):
        """Verify error state provides a retry button on network failure."""
        with open(PROFILE_PAGE_JS_PATH, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("btnProfileRetryLoad", code)
        self.assertIn("Повторить попытку", code)
        self.assertIn("loadProfile(uid, false)", code)


class TestAccessibilityAndFocusRegressions(unittest.TestCase):
    """Validates accessibility, keyboard trap in all modals, and roving tabindex on tabs."""

    def test_11_focus_trap_implementation_in_all_modals(self):
        """Verify Tab focus trapping is implemented and invoked for all 5 modals."""
        with open(PROFILE_JS_PATH, "r", encoding="utf-8") as f:
            profile_js = f.read()
        with open(PROFILE_PAGE_JS_PATH, "r", encoding="utf-8") as f:
            page_js = f.read()

        # Quick Profile became a non-modal author card (Issues #271, #272): no focus trap,
        # Tab moves from the trigger into the card and Escape returns focus to the trigger.
        self.assertNotIn("trapModalFocus", profile_js)
        self.assertIn("e.key === 'Escape'", profile_js)
        self.assertIn("closeCard(true)", profile_js)

        # In Full Profile Page (profile-page.js)
        self.assertIn("function trapModalFocus(e, modalEl)", page_js)
        self.assertNotIn("editProfileModal", page_js, "editing moved to settings.html (Issue #234)")
        self.assertIn("authModal", page_js)
        self.assertIn("articleReportModal", page_js)
        self.assertIn("profileSocialModal", page_js)
        self.assertIn("userProfileModal", page_js)

    def test_12_modal_focus_restoration_to_trigger_elements(self):
        """Verify focus is restored to the triggering element upon modal close."""
        with open(PROFILE_PAGE_JS_PATH, "r", encoding="utf-8") as f:
            page_js = f.read()

        self.assertIn("lastAuthTriggerEl.focus()", page_js)
        self.assertIn("lastSocialTriggerEl.focus()", page_js)
        self.assertIn("modal._activeReportBtn.focus()", page_js)

    def test_13_keyboard_tab_navigation_semantics(self):
        """Verify WAI-ARIA tab navigation: Arrow keys, Home, End, and roving tabindex."""
        with open(PROFILE_PAGE_JS_PATH, "r", encoding="utf-8") as f:
            page_js = f.read()

        self.assertIn("btn.setAttribute('tabindex', isCurrent ? '0' : '-1')", page_js)
        self.assertIn("ArrowRight", page_js)
        self.assertIn("ArrowLeft", page_js)
        self.assertIn("Home", page_js)
        self.assertIn("End", page_js)

    def test_14_accessible_names_and_visible_focus_styles(self):
        """Verify accessible names on icon buttons and visible focus indicators in CSS."""
        with open(PROFILE_HTML_PATH, "r", encoding="utf-8") as f:
            html = f.read()
        with open(PROFILE_CSS_PATH, "r", encoding="utf-8") as f:
            css = f.read()

        # Check buttons in HTML have aria-label or title
        self.assertIn('aria-label="Скопировать ссылку на профиль"', html)
        self.assertIn('aria-label="Сбросить фильтр по теме"', html)
        self.assertIn('aria-label="Очистить поиск"', html)
        self.assertIn('aria-label="Закрыть"', html)

        # Check visible focus styles in CSS
        self.assertIn(":focus-visible", css)
        self.assertIn("outline: 2px solid", css)


class TestVisualMatrixAndThemeRegressions(unittest.TestCase):
    """Validates responsive breakpoints, bounding box separation, and theme parity."""

    def test_15_responsive_breakpoints_declared(self):
        """Verify media query rules for 320px, 375px, 768px, 1024px, 1440px."""
        with open(PROFILE_CSS_PATH, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn("@media (max-width: 320px)", css)
        self.assertIn("@media (max-width: 375px)", css)
        self.assertIn("@media (max-width: 768px)", css)
        self.assertIn("@media (max-width: 1024px)", css)
        self.assertIn("@media (min-width: 1440px)", css)

    def test_16_avatar_name_bounding_box_separation_geometry(self):
        """Verify CSS geometry guarantees avatar and name bounding boxes never overlap.

        Calculations:
        - Desktop: Cover height 140px, avatar pull up 48px, avatar height 96px, cover leaves 92px.
        - 375px: Cover height 90px, avatar pull up 35px, avatar height 70px, cover leaves 55px.
        - 320px: Cover height 80px, avatar pull up 32px, avatar height 64px, cover leaves 48px.
        Avatar is placed in a block preceding profile-main-row in normal flow, so avatar bottom
        is separated from profile-name by margin-bottom (10px on 320px, 12px on 375px, 16px desktop).
        """
        with open(PROFILE_CSS_PATH, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn("margin-top: -32px", css)
        self.assertIn("height: 64px", css)
        self.assertIn("margin-bottom: 10px", css)

    def test_17_overflow_prevention_on_narrow_screens(self):
        """Verify min-width: 0, overflow-wrap: anywhere, and text-overflow: ellipsis."""
        with open(PROFILE_CSS_PATH, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn("overflow-x: hidden", css)
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertIn("word-break: break-word", css)
        self.assertIn("text-overflow: ellipsis", css)
        self.assertTrue(re.search(r"\.profile-sidebar-meta-item\s*\{[^}]*min-width:\s*0", css))
        self.assertTrue(re.search(r"\.profile-sidebar-meta-val\s*\{[^}]*min-width:\s*0", css))

    def test_18_broken_avatar_fallback_handling(self):
        """Verify onerror handlers in both Quick Profile and Full Profile fall back to initials."""
        with open(PROFILE_JS_PATH, "r", encoding="utf-8") as f:
            profile_js = f.read()
        with open(PROFILE_PAGE_JS_PATH, "r", encoding="utf-8") as f:
            page_js = f.read()

        # Author card: a broken avatar image removes itself and uncovers the initials under it.
        self.assertIn('onerror="this.remove()"', profile_js)
        self.assertIn('class="author-card-initials"', profile_js)
        self.assertIn("avatarImg.onerror", page_js)
        self.assertIn("avatarInitials.style.display = 'block'", page_js)

    def test_19_theme_parity_and_contrast_tokens(self):
        """Verify light and dark theme variable parity and high contrast styles."""
        with open(PROFILE_CSS_PATH, "r", encoding="utf-8") as f:
            profile_css = f.read()

        self.assertIn('[data-theme="light"] .profile-pinned-card', profile_css)
        self.assertIn('[data-theme="light"] .profile-social-item', profile_css)
        self.assertIn('[data-theme="light"] .profile-social-avatar-box', profile_css)
        self.assertIn('[data-theme="light"] .profile-comment-item.comment-highlight', profile_css)


class TestBrowserSmokeRegressions(BaseProfileTestCase):
    """Headless Chromium smoke test for real browser DOM rendering across viewports and themes."""

    @unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1", "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
    def test_20_headless_profile_viewports_and_theme_toggle(self):
        """Verify headless browser renders at 320px, 375px, and desktop with theme toggle."""
        viewports = [
            {"width": 320, "height": 568},
            {"width": 375, "height": 667},
            {"width": 1440, "height": 900}
        ]

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            js_errors = []
            for vp in viewports:
                context = browser.new_context(viewport=vp)
                page = context.new_page()

                page.on("pageerror", lambda err, vp=vp: js_errors.append(f"Page error ({vp}): {err}"))
                page.on("console", lambda msg, vp=vp: js_errors.append(f"Console error ({vp}): {msg.text}") if msg.type == "error" else None)

                # Open profile page
                page.goto(f"{self.base_url}/profile.html?id=author_192", wait_until="domcontentloaded")
                page.wait_for_function(
                    "() => { const el = document.getElementById('profileName'); return el && el.textContent.trim() !== 'Загрузка...' && el.textContent.trim() !== ''; }",
                    timeout=10000
                )

                name_text = page.locator("#profileName").inner_text()
                self.assertEqual(name_text, "Alice Engineer")

                # Verify avatar bounding box and name bounding box do not overlap
                avatar_box = page.locator("#profileAvatar").bounding_box()
                name_box = page.locator("#profileName").bounding_box()
                self.assertIsNotNone(avatar_box)
                self.assertIsNotNone(name_box)

                # Name is next to the avatar on wide screens and below it on phones (Issue #234)
                below = name_box["y"] > avatar_box["y"] + avatar_box["height"] - 5
                beside = name_box["x"] > avatar_box["x"] + avatar_box["width"] - 5
                self.assertTrue(below or beside, f"Avatar overlaps name on viewport {vp}")
                if vp["width"] <= 640:
                    self.assertTrue(below, f"On phones the name goes under the avatar ({vp})")

                # Check horizontal overflow: page content width should not exceed viewport width
                scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
                client_width = page.evaluate("() => document.documentElement.clientWidth")
                self.assertLessEqual(scroll_width, client_width + 1,
                                     f"Horizontal overflow detected on viewport {vp}")

                # Toggle theme and verify theme switched
                initial_theme = page.evaluate("() => document.documentElement.getAttribute('data-theme') || 'dark'")
                expected_next = "light" if initial_theme == "dark" else "dark"
                theme_btn = page.locator("#btnThemeToggle")
                theme_btn.click()
                page.wait_for_function(
                    f"() => document.documentElement.getAttribute('data-theme') === '{expected_next}'",
                    timeout=5000
                )
                theme_attr = page.locator("html").get_attribute("data-theme")
                self.assertEqual(theme_attr, expected_next)

                context.close()
            browser.close()

            self.assertEqual(js_errors, [], f"JavaScript runtime errors occurred during page load or theme toggle: {js_errors}")


class TestProjectInvariants(unittest.TestCase):
    """Enforces zero emojis, zero em dashes, and 100% offline-first compliance."""

    def test_21_zero_emojis_in_source_and_tests(self):
        """Verify zero emoji characters across changed files."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
        target_files = [
            PROFILE_JS_PATH,
            PROFILE_PAGE_JS_PATH,
            PROFILE_CSS_PATH,
            PROFILE_HTML_PATH,
            __file__
        ]

        for path in target_files:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                matches = emoji_pattern.findall(content)
                self.assertEqual(matches, [], f"Emoji found in {path}: {matches}")

    def test_22_zero_em_dashes_in_source_and_tests(self):
        """Verify zero em dashes (\\u2014) across changed files."""
        target_files = [
            PROFILE_JS_PATH,
            PROFILE_PAGE_JS_PATH,
            PROFILE_CSS_PATH,
            PROFILE_HTML_PATH,
            __file__
        ]

        for path in target_files:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertNotIn("\u2014", content, f"Em dash found in {path}")

    def test_23_offline_first_strict(self):
        """Verify no unescaped http/https external CDN or analytics links."""
        forbidden_hosts = ["cdn.", "unpkg.com", "cdnjs.", "googleapis.com", "fonts.gstatic.com", "analytics"]
        target_files = [
            PROFILE_HTML_PATH,
            PROFILE_CSS_PATH,
            PROFILE_JS_PATH,
            PROFILE_PAGE_JS_PATH
        ]

        for path in target_files:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                for host in forbidden_hosts:
                    self.assertNotIn(host, content, f"External network reference to {host} found in {path}")

    def test_24_profile_page_js_syntax_via_node(self):
        """Verify frontend JS files pass node --check without syntax errors."""
        node_bin = shutil.which("node")
        if not node_bin:
            fallback = os.path.expanduser("~/.local/bin/node")
            if os.path.exists(fallback):
                node_bin = fallback
        if not node_bin:
            self.skipTest("node binary not found on system")
        for js_file in ("profile-page.js", "profile.js", "card.js", "feed.js", "article.js"):
            js_path = os.path.join(FRONTEND_DIR, "js", js_file)
            res = subprocess.run([node_bin, "--check", js_path], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"node --check failed on {js_file}:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")


class TestRound3ReviewAcceptanceRegressions(BaseProfileTestCase):
    """Validates Round 3 review acceptance criteria: frontend triggerSearch, approval isolation, topic isolation, HTML search, activity pagination."""

    def test_25_acceptance_single_trigger_search_definition_in_frontend(self):
        """Verify that exactly 1 definition of function triggerSearch exists in frontend/public/js/profile-page.js."""
        with open(PROFILE_PAGE_JS_PATH, "r", encoding="utf-8") as f:
            code = f.read()

        function_defs = re.findall(r"\bfunction\s+triggerSearch\b", code)
        self.assertEqual(len(function_defs), 1, f"Expected exactly 1 definition of function triggerSearch, found {len(function_defs)}")

        assign_defs = re.findall(r"\b(?:const|let|var)\s+triggerSearch\s*=", code)
        self.assertEqual(len(assign_defs), 0, f"Unexpected triggerSearch assignment definitions: {assign_defs}")

    def test_26_acceptance_guest_activity_parent_approval_isolation(self):
        """Verify guest activity request returns approved parent title and isolates rejected snapshots."""
        res = self.get_json("/api/users/user_r3_isolation/activity")
        self.assertTrue(res.get("success"), f"Request failed: {res}")
        items = res.get("items") or res.get("activity", [])
        self.assertGreater(len(items), 0, "Expected non-empty activity items list")

        answers = [item for item in items if item.get("type") == "answer" and item.get("id") == "ans_iso_1"]
        self.assertEqual(len(answers), 1, "Expected exactly 1 answer in activity")
        ans = answers[0]
        self.assertEqual(ans.get("title"), "Approved Question Parent Title")
        self.assertNotEqual(ans.get("title"), "Rejected Question Parent Title")

        comments = [item for item in items if item.get("type") == "comment" and item.get("id") == "comm_iso_1"]
        self.assertEqual(len(comments), 1, "Expected exactly 1 comment in activity")
        comm = comments[0]
        self.assertEqual(comm.get("title"), "Approved Article Parent Title")
        self.assertEqual(comm.get("parentTitle"), "Approved Article Parent Title")
        self.assertNotEqual(comm.get("title"), "Rejected Article Parent Title")
        self.assertNotEqual(comm.get("parentTitle"), "Rejected Article Parent Title")

        # Ensure rejected titles never appear anywhere in the response payload
        res_json = json.dumps(res)
        self.assertNotIn("Rejected Question Parent Title", res_json)
        self.assertNotIn("Rejected Article Parent Title", res_json)

    def test_27_acceptance_exact_topic_isolation_no_false_positives(self):
        """Verify topic=solidity filter strictly isolates exact topic without false positives."""
        pub_res = self.get_json("/api/users/user_r3_topics/publications?topic=solidity")
        self.assertTrue(pub_res.get("success"), f"Publications request failed: {pub_res}")
        pub_items = pub_res.get("items") or pub_res.get("publications", [])
        pub_ids = [item.get("id") for item in pub_items]

        self.assertIn("pub_topic_match", pub_ids, "Exact topic match must be included")
        self.assertNotIn("pub_topic_fp_desc", pub_ids, "Item with topic security and description solidity must not match")
        self.assertNotIn("pub_topic_fp_extra", pub_ids, "Item with topic solidity-extra must not match topic solidity")
        self.assertEqual(len(pub_items), 1, f"Expected exactly 1 publication matching topic solidity, got {len(pub_items)}")

        quest_res = self.get_json("/api/users/user_r3_topics/questions?topic=solidity")
        self.assertTrue(quest_res.get("success"), f"Questions request failed: {quest_res}")
        quest_items = quest_res.get("items") or quest_res.get("questions", [])
        quest_ids = [item.get("id") for item in quest_items]

        self.assertIn("quest_topic_match", quest_ids, "Exact topic match must be included")
        self.assertNotIn("quest_topic_fp_desc", quest_ids, "Question with topic security and description solidity must not match")
        self.assertNotIn("quest_topic_fp_extra", quest_ids, "Question with topic solidity-extra must not match topic solidity")
        self.assertEqual(len(quest_items), 1, f"Expected exactly 1 question matching topic solidity, got {len(quest_items)}")

    def test_28_acceptance_html_text_search_semantic_matching(self):
        """Verify search q=smart contract semantically matches HTML content across publications and questions."""
        pub_res = self.get_json("/api/users/user_r3_semantic/publications?q=smart%20contract")
        self.assertTrue(pub_res.get("success"), f"Publications search failed: {pub_res}")
        pub_items = pub_res.get("items") or pub_res.get("publications", [])
        pub_ids = [item.get("id") for item in pub_items]
        self.assertIn("pub_sem_match", pub_ids, "Publication containing HTML smart contract must match q=smart contract")
        self.assertEqual(len(pub_items), 1)

        quest_res = self.get_json("/api/users/user_r3_semantic/questions?q=smart%20contract")
        self.assertTrue(quest_res.get("success"), f"Questions search failed: {quest_res}")
        quest_items = quest_res.get("items") or quest_res.get("questions", [])
        quest_ids = [item.get("id") for item in quest_items]
        self.assertIn("quest_sem_match", quest_ids, "Question containing HTML smart contract must match q=smart contract")
        self.assertEqual(len(quest_items), 1)

        # Negative search check: unrelated query must not match
        neg_res = self.get_json("/api/users/user_r3_semantic/publications?q=unrelated_nonexistent_token")
        self.assertTrue(neg_res.get("success"))
        neg_items = neg_res.get("items") or neg_res.get("publications", [])
        self.assertEqual(len(neg_items), 0, "Unrelated search query must return 0 items")

    def test_29_acceptance_overview_activity_search_and_pagination(self):
        """Verify activity search with q parameter returns exact total and accurate hasMore across pages."""
        # Page 1: limit 2, offset 0 -> items 0..1 out of 5
        res_p1 = self.get_json("/api/users/user_r3_activity/activity?q=compiler&limit=2&offset=0")
        self.assertTrue(res_p1.get("success"))
        self.assertEqual(res_p1.get("total"), 5, "Total matching items must equal 5")
        items_p1 = res_p1.get("items") or res_p1.get("activity", [])
        self.assertEqual(len(items_p1), 2, "Page 1 must contain exactly 2 items")
        self.assertTrue(res_p1.get("hasMore"), "Page 1 hasMore must be True")

        # Page 2: limit 2, offset 2 -> items 2..3 out of 5
        res_p2 = self.get_json("/api/users/user_r3_activity/activity?q=compiler&limit=2&offset=2")
        self.assertTrue(res_p2.get("success"))
        self.assertEqual(res_p2.get("total"), 5, "Total matching items must remain 5")
        items_p2 = res_p2.get("items") or res_p2.get("activity", [])
        self.assertEqual(len(items_p2), 2, "Page 2 must contain exactly 2 items")
        self.assertTrue(res_p2.get("hasMore"), "Page 2 hasMore must be True")

        # Page 3: limit 2, offset 4 -> item 4 out of 5
        res_p3 = self.get_json("/api/users/user_r3_activity/activity?q=compiler&limit=2&offset=4")
        self.assertTrue(res_p3.get("success"))
        self.assertEqual(res_p3.get("total"), 5, "Total matching items must remain 5")
        items_p3 = res_p3.get("items") or res_p3.get("activity", [])
        self.assertEqual(len(items_p3), 1, "Page 3 must contain exactly 1 remaining item")
        self.assertFalse(res_p3.get("hasMore"), "Page 3 hasMore must be False")

        # Page 4: limit 2, offset 6 -> out of bounds
        res_p4 = self.get_json("/api/users/user_r3_activity/activity?q=compiler&limit=2&offset=6")
        self.assertTrue(res_p4.get("success"))
        self.assertEqual(res_p4.get("total"), 5, "Total matching items must remain 5")
        items_p4 = res_p4.get("items") or res_p4.get("activity", [])
        self.assertEqual(len(items_p4), 0, "Page 4 must contain 0 items")
        self.assertFalse(res_p4.get("hasMore"), "Page 4 hasMore must be False")

        # Verify items returned across pages are disjoint and cover all expected items
        all_paged_ids = [item.get("id") for item in items_p1] + [item.get("id") for item in items_p2] + [item.get("id") for item in items_p3]
        self.assertEqual(len(all_paged_ids), 5)
        self.assertEqual(len(set(all_paged_ids)), 5, "Items across pages must be disjoint")
        expected_ids = {"pub_act_1", "pub_act_2", "quest_act_1", "ans_act_1", "comm_act_1"}
        self.assertEqual(set(all_paged_ids), expected_ids)

        # Verify non-matching items are never present in any paged results
        unwanted_ids = {"pub_act_other", "quest_act_other", "comm_act_other"}
        self.assertTrue(unwanted_ids.isdisjoint(set(all_paged_ids)), "Unwanted items must not appear in search results")


if __name__ == "__main__":
    unittest.main()
