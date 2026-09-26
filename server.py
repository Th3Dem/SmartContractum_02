#!/usr/bin/env python3
"""
server.py — Antigravity Moderation Queue Server & Static File Server.

Provides:
- Standalone Python HTTP server using http.server.ThreadingHTTPServer and SimpleHTTPRequestHandler.
- Static file serving from frontend/public/ for web client.
- SQLite persistence in data/moderation.db (table moderation_submissions).
- REST API for article moderation queue:
    POST /api/moderation/submit  - Validate article and enqueue immutable snapshot
    GET  /api/moderation/status  - Status check for a given draftId
    GET  /api/moderation/list    - List submissions in moderation queue
    GET  /api/health             - Health check
"""

import argparse
import datetime
import hashlib
import html
import http.server
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

# Base paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND_PUBLIC_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "moderation.db")

# Allowed configuration values
VALID_COMPLEXITIES = {"none", "easy", "medium", "hard"}
VALID_STATUSES = {"draft", "pending_moderation", "approved", "rejected"}


def is_valid_id(value: Any) -> bool:
    """
    Checks if a string is a valid identifier (alphanumeric, underscores, hyphens, 1..64 chars).
    """
    if not isinstance(value, str):
        return False
    val = value.strip()
    if not val or len(val) > 64:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', val))


def extract_article_text(html_content: str) -> str:
    """
    Extracts text content from HTML by stripping all tags, unescaping HTML entities,
    and removing non-breaking and zero-width spaces.
    """
    if not html_content or not isinstance(html_content, str):
        return ""
    # Strip HTML tags
    cleaned = re.sub(r'<[^>]+>', ' ', html_content)
    # Unescape HTML entities (&nbsp;, &amp;, etc.)
    unescaped = html.unescape(cleaned)
    # Replace non-breaking spaces (\u00a0), zero-width spaces (\u200b, \ufeff, etc.)
    normalized = re.sub(r'[\u00a0\u200b\ufeff\s]+', ' ', unescaped)
    return normalized.strip()


def has_valid_article_text(html_content: str) -> bool:
    """
    Validates that article body contains at least one text character [a-zA-Zа-яА-Я0-9].
    Empty tags, &nbsp;, whitespace, dividers (<hr>), and images (<img...>) only
    are strictly rejected.
    """
    if not html_content or not isinstance(html_content, str):
        return False
    text = extract_article_text(html_content)
    return bool(re.search(r'[a-zA-Zа-яА-Я0-9]', text))


def normalize_keyword(keyword: str) -> str:
    """
    Normalizes a single keyword:
    - strips outer whitespace
    - collapses multiple consecutive whitespace characters inside to a single space
    """
    if not isinstance(keyword, str):
        return ""
    trimmed = keyword.strip()
    return re.sub(r'\s+', ' ', trimmed)


def parse_and_normalize_keywords(raw_input: Union[str, List[Any]]) -> List[str]:
    """
    Parses and normalizes keywords matching frontend requirements:
    - Comma splitting (if string or items contain commas)
    - Trimming outer whitespace
    - Whitespace preservation inside phrases
    - Collapsing multiple consecutive spaces
    - Case-insensitive deduplication (preserves first occurrence casing)
    - Filters out empty strings
    """
    if isinstance(raw_input, str):
        raw_items = raw_input.split(',')
    elif isinstance(raw_input, (list, tuple)):
        raw_items = []
        for item in raw_input:
            if isinstance(item, str):
                if ',' in item:
                    raw_items.extend(item.split(','))
                else:
                    raw_items.append(item)
            else:
                raw_items.append(str(item))
    else:
        return []

    result: List[str] = []
    seen_lower = set()

    for item in raw_items:
        norm = normalize_keyword(item)
        if not norm:
            continue
        key_lower = norm.lower()
        if key_lower not in seen_lower:
            seen_lower.add(key_lower)
            result.append(norm)

    return result


def compute_snapshot_hash(title: str, article_html: str, publication_settings: Any) -> str:
    """
    Computes a deterministic SHA-256 hash of (title + article_html + publication_settings).
    """
    if isinstance(publication_settings, dict):
        settings_str = json.dumps(publication_settings, sort_keys=True, ensure_ascii=False)
    elif isinstance(publication_settings, str):
        settings_str = publication_settings
    else:
        settings_str = json.dumps(publication_settings, ensure_ascii=False)

    content = f"{title.strip()}{article_html}{settings_str}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def init_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Initializes the SQLite database and ensures the moderation_submissions table exists.
    """
    target_path = db_path or os.environ.get("MODERATION_DB_PATH", DEFAULT_DB_PATH)
    if target_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS moderation_submissions (
                id TEXT PRIMARY KEY,
                draft_id TEXT NOT NULL,
                title TEXT NOT NULL,
                author_id TEXT NOT NULL DEFAULT 'author_local',
                status TEXT NOT NULL DEFAULT 'pending_moderation' CHECK (status IN ('draft', 'pending_moderation', 'approved', 'rejected')),
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
    return conn


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Returns a new SQLite connection for the specified database path.
    """
    target_path = db_path or os.environ.get("MODERATION_DB_PATH", DEFAULT_DB_PATH)
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    return conn


def update_submission_status(submission_id: str, new_status: str, db_path: Optional[str] = None) -> bool:
    """
    Helper to update submission status (e.g. for testing moderation decisions).
    """
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {VALID_STATUSES}")
    conn = get_db_connection(db_path)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with conn:
        cur = conn.execute(
            "UPDATE moderation_submissions SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now_iso, submission_id)
        )
        return cur.rowcount > 0


def validate_submission_payload(payload: Any) -> Tuple[bool, Optional[str], Dict[str, str]]:
    """
    Validates submission payload according to product requirements:
    - title: non-empty trimmed string (min 1 char)
    - html: contains text characters [a-zA-Zа-яА-Я0-9] (no empty tags, &nbsp;, dividers, images only)
    - publicationSettings:
        - targetAudience: non-empty string, valid ID
        - topics: array of 1 to 5 non-empty string IDs
        - keywords: array of 1 to 10 strings, each 1..60 chars, no case-insensitive duplicates
        - description: string 50..500 chars
        - format: valid format ID or null/empty
        - complexity: valid complexity ID or null/empty
    """
    field_errors: Dict[str, str] = {}

    if not isinstance(payload, dict):
        return False, "Тело запроса должно быть JSON-объектом", {"payload": "Invalid JSON object"}

    # 1. draftId
    draft_id = payload.get("draftId") or payload.get("draft_id")
    if not draft_id or not isinstance(draft_id, str) or not draft_id.strip():
        field_errors["draftId"] = "Идентификатор черновика (draftId) обязателен."

    # 2. title
    title = payload.get("title")
    if title is None or not isinstance(title, str) or not title.strip():
        field_errors["title"] = "Заголовок статьи не может быть пустым."

    # 3. html
    article_html = payload.get("html") or payload.get("article_html") or payload.get("content")
    if article_html is None or not isinstance(article_html, str) or not has_valid_article_text(article_html):
        field_errors["html"] = "Тело статьи должно содержать текст (буквы или цифры). Пустые блоки, пробелы и только изображения недопустимы."

    # 4. publicationSettings
    pub_settings = payload.get("publicationSettings") or payload.get("publication_settings")
    if pub_settings is None or not isinstance(pub_settings, dict):
        field_errors["publicationSettings"] = "Настройки публикации обязательны и должны быть объектом."
    else:
        # 4a. targetAudience
        target_audience = pub_settings.get("targetAudience") or pub_settings.get("target_audience")
        if not target_audience or not isinstance(target_audience, str) or not target_audience.strip():
            field_errors["targetAudience"] = "Целевая аудитория обязательна и должна быть выбрана."
        elif not is_valid_id(target_audience):
            field_errors["targetAudience"] = "Указан недопустимый идентификатор целевой аудитории."

        # 4b. topics
        topics = pub_settings.get("topics")
        if topics is None or not isinstance(topics, list):
            field_errors["topics"] = "Темы публикации должны быть массивом идентификаторов."
        elif len(topics) < 1 or len(topics) > 5:
            field_errors["topics"] = "Необходимо выбрать от 1 до 5 тем публикации."
        elif not all(isinstance(t, str) and is_valid_id(t) for t in topics):
            field_errors["topics"] = "Темы публикации содержат невалидные идентификаторы."
        elif len(set(topics)) != len(topics):
            field_errors["topics"] = "Темы публикации не должны дублироваться."

        # 4c. keywords
        keywords = pub_settings.get("keywords")
        if keywords is None or not isinstance(keywords, list):
            field_errors["keywords"] = "Ключевые слова должны быть массивом строк."
        elif len(keywords) < 1:
            field_errors["keywords"] = "Необходимо указать хотя бы одно ключевое слово."
        elif len(keywords) > 10:
            field_errors["keywords"] = "Нельзя указать более 10 ключевых слов."
        else:
            seen_kw = set()
            invalid_kw_len = False
            has_dup = False
            for kw in keywords:
                if not isinstance(kw, str):
                    invalid_kw_len = True
                    break
                stripped = kw.strip()
                if len(stripped) < 1 or len(stripped) > 60:
                    invalid_kw_len = True
                    break
                norm = re.sub(r'\s+', ' ', stripped).lower()
                if norm in seen_kw:
                    has_dup = True
                    break
                seen_kw.add(norm)

            if invalid_kw_len:
                field_errors["keywords"] = "Каждое ключевое слово должно содержать от 1 до 60 символов."
            elif has_dup:
                field_errors["keywords"] = "Ключевые слова не должны дублироваться без учета регистра."

        # 4d. description
        desc = pub_settings.get("description")
        if desc is None or not isinstance(desc, str):
            field_errors["description"] = "Краткое описание обязательно."
        elif len(desc.strip()) < 50 or len(desc.strip()) > 500:
            field_errors["description"] = "Краткое описание должно содержать от 50 до 500 символов."

        # 4e. format
        fmt = pub_settings.get("format")
        if fmt is not None and fmt != "":
            if not isinstance(fmt, str) or not is_valid_id(fmt):
                field_errors["format"] = "Недопустимый формат публикации."

        # 4f. complexity
        compl = pub_settings.get("complexity")
        if compl is not None and compl != "":
            if not isinstance(compl, str) or compl not in VALID_COMPLEXITIES:
                field_errors["complexity"] = "Недопустимый уровень сложности публикации."

    if field_errors:
        order = ["title", "html", "targetAudience", "topics", "keywords", "description", "format", "complexity", "draftId", "publicationSettings"]
        first_key = next((k for k in order if k in field_errors), next(iter(field_errors.keys())))
        error_msg = field_errors[first_key]
        return False, error_msg, field_errors

    return True, None, {}


class ModerationRequestHandler(http.server.SimpleHTTPRequestHandler):
    """
    HTTP Request Handler serving both the static frontend and the Moderation REST API.
    """
    directory = FRONTEND_PUBLIC_DIR

    def __init__(self, *args, directory=None, **kwargs):
        if directory is None:
            if len(args) >= 3 and hasattr(args[2], "directory"):
                directory = args[2].directory
            else:
                directory = FRONTEND_PUBLIC_DIR
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        """Optionally suppress verbose logging in quiet test environments."""
        if not os.environ.get("SERVER_QUIET"):
            sys.stderr.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {format % args}\n")

    def get_db(self) -> sqlite3.Connection:
        db_path = getattr(self.server, "db_path", DEFAULT_DB_PATH)
        return get_db_connection(db_path)

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, Idempotency-Key")

    def send_json_response(self, status_code: int, data: dict):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        """Handle GET requests for static files and REST API."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            self.send_json_response(200, {
                "status": "ok",
                "server": "Antigravity Moderation Server"
            })
        elif path == "/api/moderation/status":
            self.handle_moderation_status(parsed)
        elif path == "/api/moderation/list":
            self.handle_moderation_list()
        elif path.startswith("/api/"):
            self.send_json_response(404, {
                "success": False,
                "error": f"API endpoint not found: {path}"
            })
        else:
            # Delegate to SimpleHTTPRequestHandler for static files
            super().do_GET()

    def do_POST(self):
        """Handle POST requests for REST API."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/moderation/submit":
            self.handle_moderation_submit()
        elif path.startswith("/api/"):
            self.send_json_response(404, {
                "success": False,
                "error": f"API endpoint not found: {path}"
            })
        else:
            self.send_json_response(405, {
                "success": False,
                "error": "Method Not Allowed"
            })

    def handle_moderation_submit(self):
        """
        POST /api/moderation/submit
        Receives { draftId, title, html, delta, publicationSettings, idempotencyKey, authorId }.
        Validates payload, enforces idempotency, checks status transition,
        calculates SHA-256 snapshot hash, and stores immutable snapshot in SQLite.
        """
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            content_length = 0

        if content_length <= 0:
            self.send_json_response(400, {
                "success": False,
                "error": "Пустое тело запроса (Content-Length must be > 0)",
                "fieldErrors": {}
            })
            return

        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self.send_json_response(400, {
                "success": False,
                "error": f"Невалидный JSON: {str(e)}",
                "fieldErrors": {}
            })
            return

        idempotency_key = payload.get("idempotencyKey") or payload.get("idempotency_key")
        if isinstance(idempotency_key, str):
            idempotency_key = idempotency_key.strip() or None
        else:
            idempotency_key = None

        conn = self.get_db()

        # Idempotency check: if already processed, return existing submission immediately
        if idempotency_key:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT * FROM moderation_submissions WHERE idempotency_key = ? LIMIT 1",
                    (idempotency_key,)
                )
                existing = cur.fetchone()
                if existing:
                    self.send_json_response(200, {
                        "success": True,
                        "status": existing["status"],
                        "submissionId": existing["id"],
                        "snapshotHash": existing["snapshot_hash"],
                        "createdAt": existing["created_at"],
                        "isDuplicate": True
                    })
                    return

        # Validation check
        is_valid, err_msg, field_errors = validate_submission_payload(payload)
        if not is_valid:
            self.send_json_response(400, {
                "success": False,
                "error": err_msg,
                "fieldErrors": field_errors
            })
            return

        draft_id = payload.get("draftId") or payload.get("draft_id")
        title = payload.get("title").strip()
        article_html = payload.get("html") or payload.get("article_html") or payload.get("content")
        delta = payload.get("delta") or payload.get("article_delta")
        pub_settings = payload.get("publicationSettings") or payload.get("publication_settings")
        author_id = payload.get("authorId") or payload.get("author_id") or "author_local"

        # Status transition check: cannot transition if already approved or in terminal invalid state
        with conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, status FROM moderation_submissions WHERE draft_id = ? ORDER BY created_at DESC LIMIT 1",
                (draft_id,)
            )
            last_sub = cur.fetchone()
            if last_sub and last_sub["status"] == "approved":
                self.send_json_response(400, {
                    "success": False,
                    "error": "Черновик уже одобрен модератором и не может быть отправлен повторно.",
                    "fieldErrors": {
                        "status": "Статья уже имеет статус 'approved'."
                    }
                })
                return

        # Compute deterministic SHA-256 snapshot hash
        snapshot_hash = compute_snapshot_hash(title, article_html, pub_settings)

        submission_id = f"sub_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        pub_settings_json = json.dumps(pub_settings, ensure_ascii=False)
        article_delta_json = json.dumps(delta, ensure_ascii=False) if delta is not None else None

        # Insert immutable snapshot row
        try:
            with conn:
                conn.execute("""
                    INSERT INTO moderation_submissions (
                        id, draft_id, title, author_id, status, publication_settings,
                        article_html, article_delta, idempotency_key, snapshot_hash,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'pending_moderation', ?, ?, ?, ?, ?, ?, ?)
                """, (
                    submission_id, draft_id, title, author_id, pub_settings_json,
                    article_html, article_delta_json, idempotency_key, snapshot_hash,
                    now_iso, now_iso
                ))
        except sqlite3.IntegrityError:
            # Race condition with identical idempotency_key
            if idempotency_key:
                cur = conn.cursor()
                cur.execute(
                    "SELECT * FROM moderation_submissions WHERE idempotency_key = ? LIMIT 1",
                    (idempotency_key,)
                )
                dup_row = cur.fetchone()
                if dup_row:
                    self.send_json_response(200, {
                        "success": True,
                        "status": dup_row["status"],
                        "submissionId": dup_row["id"],
                        "snapshotHash": dup_row["snapshot_hash"],
                        "createdAt": dup_row["created_at"],
                        "isDuplicate": True
                    })
                    return

            self.send_json_response(500, {
                "success": False,
                "error": "Ошибка сохранения заявки в базу данных (Integrity Error)",
                "fieldErrors": {}
            })
            return

        self.send_json_response(200, {
            "success": True,
            "status": "pending_moderation",
            "submissionId": submission_id,
            "snapshotHash": snapshot_hash,
            "createdAt": now_iso
        })

    def handle_moderation_status(self, parsed_url):
        """
        GET /api/moderation/status?draftId=...
        Returns status of the latest submission for the draft.
        """
        query = urllib.parse.parse_qs(parsed_url.query)
        draft_id = query.get("draftId", [None])[0] or query.get("draft_id", [None])[0]

        if not draft_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Параметр draftId обязателен",
                "fieldErrors": {"draftId": "Параметр draftId обязателен"}
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM moderation_submissions WHERE draft_id = ? ORDER BY created_at DESC LIMIT 1",
                (draft_id,)
            )
            row = cur.fetchone()

        if not row:
            self.send_json_response(404, {
                "success": False,
                "status": "draft",
                "submissionId": None,
                "error": "Заявка на модерацию для данного черновика не найдена"
            })
            return

        self.send_json_response(200, {
            "success": True,
            "status": row["status"],
            "submissionId": row["id"],
            "snapshotHash": row["snapshot_hash"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"]
        })

    def handle_moderation_list(self):
        """
        GET /api/moderation/list
        Returns array of submissions in queue (for moderator access).
        """
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM moderation_submissions ORDER BY created_at DESC")
            rows = cur.fetchall()

        submissions = []
        for row in rows:
            try:
                settings = json.loads(row["publication_settings"]) if row["publication_settings"] else {}
            except Exception:
                settings = {}

            try:
                delta = json.loads(row["article_delta"]) if row["article_delta"] else None
            except Exception:
                delta = None

            submissions.append({
                "id": row["id"],
                "draftId": row["draft_id"],
                "title": row["title"],
                "authorId": row["author_id"],
                "status": row["status"],
                "publicationSettings": settings,
                "articleHtml": row["article_html"],
                "articleDelta": delta,
                "idempotencyKey": row["idempotency_key"],
                "snapshotHash": row["snapshot_hash"],
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"]
            })

        self.send_json_response(200, {
            "success": True,
            "submissions": submissions,
            "count": len(submissions)
        })


def create_server(host: str = "0.0.0.0", port: int = 8000, db_path: Optional[str] = None, directory: Optional[str] = None) -> http.server.ThreadingHTTPServer:
    """
    Creates and returns a ThreadingHTTPServer instance with initialized database.
    """
    init_db(db_path)
    server_address = (host, port)
    httpd = http.server.ThreadingHTTPServer(server_address, ModerationRequestHandler)
    httpd.db_path = db_path or os.environ.get("MODERATION_DB_PATH", DEFAULT_DB_PATH)
    httpd.directory = directory or FRONTEND_PUBLIC_DIR
    return httpd


def run_server(host: str = "0.0.0.0", port: int = 8000, db_path: Optional[str] = None):
    """
    Starts the server loop listening on host:port.
    """
    httpd = create_server(host=host, port=port, db_path=db_path)
    print(f"Antigravity Moderation Server running at http://{host}:{port}/")
    print(f"Serving static files from {httpd.directory}")
    print(f"SQLite database at {httpd.db_path}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Antigravity Moderation Server")
    parser.add_argument("port_pos", nargs="?", type=int, default=None, help="Port to listen on (positional)")
    parser.add_argument("--port", type=int, default=None, help="Port to listen on (default 8000)")
    parser.add_argument("--host", type=str, default=os.environ.get("HOST", "0.0.0.0"), help="Host to bind to (default 0.0.0.0)")
    parser.add_argument("--db", type=str, default=None, help="Path to SQLite database")
    args = parser.parse_args()
    port = args.port or args.port_pos or int(os.environ.get("PORT", 8000))
    run_server(host=args.host, port=port, db_path=args.db)
