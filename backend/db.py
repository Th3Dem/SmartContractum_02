"""SQLite connection, schema creation and migrations, submission status changes."""
import datetime
import json
import os
import sqlite3
import sys
from typing import Optional

from backend import config
from backend.config import VALID_STATUSES
from backend.content import extract_article_text
from backend.seeds import seed_database
from backend.companies import migrate_company_schema
from backend.media_library import migrate_media_schema
from backend.users import disable_legacy_admin_password, migrate_legacy_profiles


def init_db(db_path: Optional[str] = None, seed: Optional[bool] = None) -> sqlite3.Connection:
    """
    Initializes the SQLite database and ensures schema and tables exist.
    Optionally seeds demo data if seed is True or environment/test defaults dictate.
    """
    target_path = db_path or os.environ.get("MODERATION_DB_PATH", config.DEFAULT_DB_PATH)
    if target_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.create_function("lower", 1, lambda s: s.lower() if s is not None else None)
    except Exception:
        pass
    try:
        conn.create_function("extract_text", 1, lambda s: extract_article_text(s) if s is not None else "")
    except Exception:
        pass
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS moderation_submissions (
                id TEXT PRIMARY KEY,
                draft_id TEXT NOT NULL,
                title TEXT NOT NULL,
                author_id TEXT NOT NULL DEFAULT 'author_local',
                status TEXT NOT NULL DEFAULT 'pending_moderation' CHECK (status IN ('draft', 'pending_moderation', 'approved', 'rejected', 'needs_revision')),
                publication_settings TEXT NOT NULL,
                article_html TEXT NOT NULL,
                article_delta TEXT,
                idempotency_key TEXT UNIQUE,
                snapshot_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_moderation_draft_id ON moderation_submissions(draft_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_moderation_status ON moderation_submissions(status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_moderation_author ON moderation_submissions(author_id, status);")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                target_title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, target_type, target_id)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_subs_user ON user_subscriptions(user_id);")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_feed_exceptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                target_title TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, target_type, target_id)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_exceptions_user_id ON user_feed_exceptions(user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_exceptions_lookup ON user_feed_exceptions(user_id, target_type, target_id);")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS article_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(article_id, user_id)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_likes_article_user ON article_likes(article_id, user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_likes_article_id ON article_likes(article_id);")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS article_saves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(article_id, user_id)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_saves_article_user ON article_saves(article_id, user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_saves_article_id ON article_saves(article_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_saves_user_id ON article_saves(user_id);")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS comment_saves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(comment_id, user_id)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comment_saves_comment_user ON comment_saves(comment_id, user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comment_saves_comment_id ON comment_saves(comment_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comment_saves_user_id ON comment_saves(user_id);")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS article_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                value INTEGER NOT NULL CHECK(value IN (-1, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(article_id, user_id)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_article_votes_target ON article_votes(article_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_article_votes_user ON article_votes(user_id);")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS comment_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                value INTEGER NOT NULL CHECK(value IN (-1, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(comment_id, user_id)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comment_votes_target ON comment_votes(comment_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comment_votes_user ON comment_votes(user_id);")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS article_comments (
                id TEXT PRIMARY KEY,
                article_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                author_name TEXT NOT NULL,
                author_avatar TEXT,
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'published',
                comment_type TEXT NOT NULL DEFAULT 'comment',
                is_solution INTEGER NOT NULL DEFAULT 0,
                parent_answer_id TEXT NULL,
                parent_comment_id TEXT NULL,
                client_operation_id TEXT NULL,
                updated_at TEXT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
        """)
        # Safe migration if columns don't exist
        for col, col_def in [
            ("comment_type", "TEXT NOT NULL DEFAULT 'comment'"),
            ("is_solution", "INTEGER NOT NULL DEFAULT 0"),
            ("parent_answer_id", "TEXT NULL"),
            ("parent_comment_id", "TEXT NULL"),
            ("client_operation_id", "TEXT NULL"),
            ("updated_at", "TEXT NULL"),
            ("revision", "INTEGER NOT NULL DEFAULT 1")
        ]:
            try:
                conn.execute(f"ALTER TABLE article_comments ADD COLUMN {col} {col_def};")
            except Exception:
                pass
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_article_id ON article_comments(article_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_solution ON article_comments(article_id, is_solution);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_parent_answer ON article_comments(parent_answer_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_parent_comment ON article_comments(parent_comment_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_user_status ON article_comments(user_id, status);")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_user_answer ON article_comments(article_id, user_id) WHERE comment_type = 'answer' AND status = 'published';")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_client_operation ON article_comments(user_id, client_operation_id) WHERE client_operation_id IS NOT NULL;")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS comment_reports (
                id TEXT PRIMARY KEY,
                comment_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comment_reports_comment ON comment_reports(comment_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comment_reports_user ON comment_reports(user_id);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS article_reports (
                id TEXT PRIMARY KEY,
                article_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_article_reports_article ON article_reports(article_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_article_reports_user ON article_reports(user_id);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS comment_subscriptions (
                id TEXT PRIMARY KEY,
                comment_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(comment_id, user_id)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comment_subscriptions_user ON comment_subscriptions(user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comment_subscriptions_comment ON comment_subscriptions(comment_id);")

        conn.execute("""
            UPDATE article_comments
            SET article_id = (
                SELECT ms.id FROM moderation_submissions ms
                WHERE ms.draft_id = article_comments.article_id AND ms.status = 'approved'
                LIMIT 1
            )
            WHERE article_id IN (
                SELECT draft_id FROM moderation_submissions WHERE draft_id IS NOT NULL AND status = 'approved'
            )
            AND EXISTS (
                SELECT 1 FROM moderation_submissions ms
                WHERE ms.draft_id = article_comments.article_id AND ms.status = 'approved'
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_notifications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                actor_name TEXT NOT NULL,
                article_id TEXT NOT NULL,
                comment_id TEXT,
                type TEXT NOT NULL CHECK(type IN ('new_answer', 'new_reply', 'solution_accepted')),
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON user_notifications(user_id);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                specialization TEXT,
                company TEXT,
                bio TEXT,
                avatar TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_feed_settings (
                user_id TEXT PRIMARY KEY,
                material_types TEXT NOT NULL,
                complexity_levels TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        try:
            conn.execute("ALTER TABLE user_feed_settings ADD COLUMN welcome_dismissed INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE user_profiles ADD COLUMN website TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE user_profiles ADD COLUMN first_name TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE user_profiles ADD COLUMN last_name TEXT;")
        except Exception:
            pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_pinned_materials (
                user_id TEXT PRIMARY KEY,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clubs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                avatar TEXT,
                rules TEXT,
                owner_id TEXT NOT NULL,
                directions TEXT,
                tags TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clubs_owner ON clubs(owner_id);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                specialization TEXT NOT NULL,
                website TEXT,
                logo TEXT,
                directions TEXT,
                owner_id TEXT NOT NULL,
                is_verified INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_companies_owner ON companies(owner_id);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS company_members (
                company_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                created_at TEXT NOT NULL,
                PRIMARY KEY (company_id, user_id)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_company_members_user ON company_members(user_id);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                user_role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                is_revoked INTEGER DEFAULT 0
            );
        """)
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN user_role TEXT NOT NULL DEFAULT 'user';")
        except Exception:
            pass
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                login TEXT NOT NULL,
                login_normalized TEXT NOT NULL UNIQUE,
                name TEXT,
                avatar TEXT,
                email TEXT,
                email_normalized TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('pending', 'active', 'disabled')),
                role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'moderator', 'admin')),
                email_verified_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_login_normalized ON users(login_normalized);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email_normalized ON users(email_normalized);")
        try:
            conn.execute("ALTER TABLE users ADD COLUMN name TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN avatar TEXT;")
        except sqlite3.OperationalError:
            pass
        try:
            # SHA-256 of the secret handed to the browser that registered; email verification must present it
            conn.execute("ALTER TABLE users ADD COLUMN registration_token_hash TEXT;")
        except sqlite3.OperationalError:
            pass


        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_verifications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                email TEXT NOT NULL,
                purpose TEXT NOT NULL DEFAULT 'email_verification',
                code_hash TEXT NOT NULL,
                attempts_left INTEGER NOT NULL DEFAULT 5,
                expires_at TEXT NOT NULL,
                resend_available_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'consumed', 'invalidated')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_email_verif_user_purpose ON email_verifications(user_id, purpose, status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_email_verif_email ON email_verifications(email, purpose, status);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_outbox (
                id TEXT PRIMARY KEY,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                body_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'sent' CHECK(status IN ('pending', 'sent', 'failed')),
                error_message TEXT,
                created_at TEXT NOT NULL,
                sent_at TEXT
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_email_outbox_recipient ON email_outbox(recipient, created_at);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_drafts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                material_type TEXT NOT NULL CHECK (material_type IN ('publication', 'question')),
                title TEXT,
                content TEXT,
                publication_settings TEXT,
                company_id TEXT,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_drafts_user_type ON user_drafts(user_id, material_type, updated_at);")

    if seed is None:
        if os.environ.get("SEED_ON_INIT") == "1":
            seed = True
        elif os.environ.get("SEED_ON_INIT") == "0":
            seed = False
        elif "unittest" in sys.modules:
            seed = True
        else:
            seed = False

    if seed:
        seed_database(conn)

    migrate_legacy_profiles(conn)
    disable_legacy_admin_password(conn)
    migrate_company_schema(conn)
    migrate_media_schema(conn)
    # Imported here: backend.moderation depends on this module
    from backend.moderation import migrate_moderation_schema
    migrate_moderation_schema(conn)

    return conn


init_moderation_db = init_db


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Returns a new SQLite connection for the specified database path.
    """
    target_path = db_path or os.environ.get("MODERATION_DB_PATH", config.DEFAULT_DB_PATH)
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.create_function("lower", 1, lambda s: s.lower() if s is not None else None)
    except Exception:
        pass
    try:
        conn.create_function("extract_text", 1, lambda s: extract_article_text(s) if s is not None else "")
    except Exception:
        pass
    return conn


def can_user_publish_for_company(
    conn: sqlite3.Connection,
    user_id: Optional[str],
    company_id: Optional[str],
    user_role: str = "user"
) -> bool:
    """
    Checks if a user is authorized to publish on behalf of a company.
    Rules:
    - If user_role == 'admin': return True
    - If not company_id: return False
    - Check if company exists in companies table. If not: return False
    - If not user_id: return False
    - If company['owner_id'] == user_id: return True
    - Check company_members table: if (company_id, user_id) exists with role in
      ('owner', 'admin', 'editor', 'author', 'member'): return True
    - Otherwise return False
    """
    if user_role == "admin":
        return True
    if not company_id:
        return False
    cur = conn.cursor()
    cur.execute("SELECT owner_id FROM companies WHERE id = ?", (company_id,))
    comp = cur.fetchone()
    if not comp:
        return False
    if not user_id:
        return False
    if comp["owner_id"] == user_id:
        return True
    cur.execute(
        "SELECT role FROM company_members WHERE company_id = ? AND user_id = ?",
        (company_id, user_id)
    )
    member = cur.fetchone()
    if member and member["role"] in ("owner", "admin", "editor", "author", "member"):
        return True
    return False


def update_submission_status(submission_id: str, new_status: str, db_path: Optional[str] = None) -> bool:
    """
    Helper to update submission status (e.g. for testing moderation decisions).
    If new_status == 'approved':
    Inspect submission's publication_settings. If companyId is specified, verify
    that the submission's author_id has permission via can_user_publish_for_company.
    If not, reject update (return False).
    """
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {VALID_STATUSES}")
    conn = get_db_connection(db_path)
    try:
        if new_status == "approved":
            cur = conn.cursor()
            cur.execute(
                "SELECT author_id, publication_settings FROM moderation_submissions WHERE id = ?",
                (submission_id,)
            )
            sub_row = cur.fetchone()
            if not sub_row:
                return False
            pub_settings_raw = sub_row["publication_settings"]
            try:
                pub_settings = json.loads(pub_settings_raw) if pub_settings_raw else {}
            except Exception:
                pub_settings = {}
            comp_id = pub_settings.get("companyId") or pub_settings.get("company_id")
            if comp_id:
                # Check company exists
                cur.execute("SELECT id FROM companies WHERE id = ?", (comp_id,))
                if not cur.fetchone():
                    return False

                author_id = sub_row["author_id"]
                author_role = "user"
                try:
                    cur.execute(
                        "SELECT user_role FROM sessions WHERE user_id = ? AND is_revoked = 0 ORDER BY created_at DESC LIMIT 1",
                        (author_id,)
                    )
                    sess_row = cur.fetchone()
                    if sess_row and "user_role" in sess_row.keys() and sess_row["user_role"]:
                        author_role = sess_row["user_role"]
                except Exception:
                    pass

                if not can_user_publish_for_company(conn, author_id, comp_id, user_role=author_role):
                    return False

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with conn:
            cur = conn.execute(
                "UPDATE moderation_submissions SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, now_iso, submission_id)
            )
            return cur.rowcount > 0
    finally:
        conn.close()
