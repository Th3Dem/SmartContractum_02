#!/usr/bin/env python3
"""
server.py - Antigravity Moderation Queue Server & Static File Server.

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
import base64
import datetime
import hashlib
import html
import html.parser
import http.server
import json
import os
import re
import secrets
import sqlite3
import sys
import time
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

import image_decoder

# Base paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND_PUBLIC_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "moderation.db")
MEDIA_DIR = os.path.join(DATA_DIR, "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

# Allowed configuration values
VALID_COMPLEXITIES = {"none", "easy", "medium", "hard"}
VALID_STATUSES = {"draft", "pending_moderation", "approved", "rejected"}
VALID_MATERIAL_TYPES = ("publication", "question")
LEGACY_MATERIAL_TYPES = {"article": "publication", "post": "publication", "news": "publication"}

# Request body size limits (Issue #8 / SC-005)
MAX_JSON_BODY_BYTES = 5 * 1024 * 1024    # 5 МБ для стандартных JSON-запросов
MAX_MEDIA_BODY_BYTES = 15 * 1024 * 1024  # 15 МБ для загрузки медиа/обложек



class CoverValidationResult(tuple):
    """
    Validation result that unpacks as (is_valid, error_msg) for full backward compatibility,
    while also exposing .is_valid, .error_msg, .saved_url, .meta, .image_bytes.
    """
    def __new__(cls, is_valid: bool, error_msg: Optional[str] = None, saved_url: Optional[str] = None, meta: Optional[dict] = None, image_bytes: Optional[bytes] = None):
        return super().__new__(cls, (is_valid, error_msg))

    def __init__(self, is_valid: bool, error_msg: Optional[str] = None, saved_url: Optional[str] = None, meta: Optional[dict] = None, image_bytes: Optional[bytes] = None):
        self.is_valid = is_valid
        self.error_msg = error_msg
        self.saved_url = saved_url
        self.meta = meta or {}
        self.image_bytes = image_bytes


def save_media_file(data: bytes, ext: str, media_dir: Optional[str] = None) -> str:
    """
    Saves image data to disk in media_dir/<sha256>.<ext> and returns /media/<sha256>.<ext>.
    """
    target_dir = media_dir or MEDIA_DIR
    os.makedirs(target_dir, exist_ok=True)
    clean_ext = ext.lstrip(".").lower()
    if clean_ext == "jpeg":
        clean_ext = "jpg"
    file_hash = hashlib.sha256(data).hexdigest()[:32]
    filename = f"{file_hash}.{clean_ext}"
    filepath = os.path.join(target_dir, filename)
    if not os.path.exists(filepath):
        with open(filepath, "wb") as f:
            f.write(data)
    return f"/media/{filename}"


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


def slugify(text: str) -> str:
    """Creates URL-safe slug from Russian or Latin text."""
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    s = text.lower().strip()
    out = []
    for ch in s:
        if ch in translit_map:
            out.append(translit_map[ch])
        elif ch.isalnum() or ch in ('-', '_'):
            out.append(ch)
        elif ch.isspace():
            out.append('-')
    res = re.sub(r'-+', '-', ''.join(out)).strip('-')
    return res or f"item-{uuid.uuid4().hex[:8]}"



class ArticleHTMLSanitizer(html.parser.HTMLParser):
    """
    Offline-first HTML sanitizer based on html.parser.HTMLParser.
    Enforces a strict allowlist of Quill editor tags and attributes,
    strips dangerous elements (<script>, <iframe>, <object>, etc.) along with their content,
    removes all event handler attributes ('on*'), and validates link/image URIs against safe schemes.
    """
    ALLOWED_TAGS = {
        "p", "h1", "h2", "h3", "h4", "h5", "h6",
        "blockquote", "ul", "ol", "li", "pre", "code",
        "table", "thead", "tbody", "tr", "th", "td",
        "img", "a", "strong", "b", "em", "i", "u", "s",
        "del", "strike", "sub", "sup", "span", "div",
        "br", "hr",
    }
    DROP_CONTENT_TAGS = {
        "script", "style", "iframe", "object", "embed", "applet",
        "meta", "link", "base", "form", "input", "button",
        "textarea", "noscript",
    }
    VOID_TAGS = {"img", "br", "hr"}

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.output: List[str] = []
        self.open_tags: List[str] = []
        self.drop_depth = 0

    @staticmethod
    def is_safe_href(url: str) -> bool:
        if not url or not isinstance(url, str):
            return False
        cleaned = re.sub(r'[\s\x00-\x1f\x7f-\x9f]', '', url)
        if not cleaned:
            return False
        unquoted = urllib.parse.unquote(cleaned).lower()
        if unquoted.startswith(('javascript:', 'vbscript:', 'data:', 'file:', 'blob:')):
            return False
        lower_cleaned = cleaned.lower()
        if lower_cleaned.startswith(('javascript:', 'vbscript:', 'data:', 'file:', 'blob:')):
            return False
        colon_idx = cleaned.find(':')
        if colon_idx != -1:
            scheme = cleaned[:colon_idx].lower()
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*$', scheme):
                if scheme not in ('http', 'https', 'mailto'):
                    return False
        return True

    @staticmethod
    def is_safe_img_src(src: str) -> bool:
        if not src or not isinstance(src, str):
            return False
        cleaned = re.sub(r'[\s\x00-\x1f\x7f-\x9f]', '', src)
        if not cleaned:
            return False
        unquoted = urllib.parse.unquote(cleaned).lower()
        if unquoted.startswith(('javascript:', 'vbscript:', 'file:', 'blob:')):
            return False
        lower_cleaned = cleaned.lower()
        if lower_cleaned.startswith(('javascript:', 'vbscript:', 'file:', 'blob:')):
            return False
        if lower_cleaned.startswith(('http://', 'https://', '/media/')) or cleaned.startswith(('/', './', '../', '#')):
            return True
        if lower_cleaned.startswith('data:'):
            return bool(re.match(r'^data:image/(?:png|jpeg|jpg|webp|gif);base64,[a-zA-Z0-9+/=]+$', cleaned, re.IGNORECASE))
        colon_idx = cleaned.find(':')
        if colon_idx != -1:
            return False
        return True

    def is_valid_attr(self, tag: str, name: str, val: str) -> bool:
        if name.startswith('on'):
            return False
        if tag == 'a':
            if name == 'href':
                return self.is_safe_href(val)
            if name == 'target':
                return val in ('_blank', '_self')
            if name == 'rel':
                return bool(re.match(r'^[a-zA-Z0-9_\-\s]+$', val))
            if name == 'class':
                return bool(re.match(r'^[a-zA-Z0-9_\-\s]+$', val))
            if name == 'id':
                return bool(re.match(r'^[a-zA-Z0-9_\-:]+$', val))
            if name == 'title':
                return True
            return False
        elif tag == 'img':
            if name == 'src':
                return self.is_safe_img_src(val)
            if name in ('alt', 'title'):
                return True
            if name in ('width', 'height'):
                return bool(re.match(r'^[0-9]+%?$|^auto$', val))
            if name == 'loading':
                return val in ('lazy', 'eager', 'auto')
            if name == 'class':
                return bool(re.match(r'^[a-zA-Z0-9_\-\s]+$', val))
            if name == 'id':
                return bool(re.match(r'^[a-zA-Z0-9_\-:]+$', val))
            return False
        elif tag in ('th', 'td'):
            if name in ('colspan', 'rowspan'):
                return bool(re.match(r'^[0-9]+$', val))
            if name == 'scope' and tag == 'th':
                return val in ('col', 'row', 'colgroup', 'rowgroup')
            if name == 'class':
                return bool(re.match(r'^[a-zA-Z0-9_\-\s]+$', val))
            if name == 'id':
                return bool(re.match(r'^[a-zA-Z0-9_\-:]+$', val))
            if name == 'title':
                return True
            return False
        else:
            if name == 'class':
                return bool(re.match(r'^[a-zA-Z0-9_\-\s]+$', val))
            if name == 'id':
                return bool(re.match(r'^[a-zA-Z0-9_\-:]+$', val))
            if name == 'title':
                return True
            if name == 'data-language' and tag in ('pre', 'code'):
                return bool(re.match(r'^[a-zA-Z0-9_\-\.\+]+$', val))
            return False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        tag = tag.lower()
        if self.drop_depth > 0:
            return
        if tag in self.DROP_CONTENT_TAGS:
            self.drop_depth += 1
            return
        if tag not in self.ALLOWED_TAGS:
            return

        clean_attrs = []
        for name, val in attrs:
            name = name.lower()
            val_str = val if val is not None else ''
            if self.is_valid_attr(tag, name, val_str):
                clean_attrs.append((name, val_str))

        if clean_attrs:
            attrs_str = ' ' + ' '.join(
                f'{k}="{html.escape(v, quote=True)}"'
                for k, v in clean_attrs
            )
        else:
            attrs_str = ''

        # Handle HTML auto-closing elements
        if tag == 'p' and self.open_tags and self.open_tags[-1] == 'p':
            self.output.append('</p>')
            self.open_tags.pop()
        elif tag == 'li' and self.open_tags and self.open_tags[-1] == 'li':
            self.output.append('</li>')
            self.open_tags.pop()
        elif tag == 'tr' and self.open_tags and self.open_tags[-1] in ('tr', 'td', 'th'):
            while self.open_tags and self.open_tags[-1] in ('tr', 'td', 'th'):
                popped = self.open_tags.pop()
                self.output.append(f'</{popped}>')
        elif tag in ('td', 'th') and self.open_tags and self.open_tags[-1] in ('td', 'th'):
            popped = self.open_tags.pop()
            self.output.append(f'</{popped}>')

        self.output.append(f'<{tag}{attrs_str}>')
        if tag not in self.VOID_TAGS:
            self.open_tags.append(tag)

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in self.DROP_CONTENT_TAGS:
            if self.drop_depth > 0:
                self.drop_depth -= 1
            return
        if self.drop_depth > 0:
            return
        if tag in self.VOID_TAGS:
            return
        if tag not in self.ALLOWED_TAGS:
            return
        if tag in self.open_tags:
            while self.open_tags:
                popped = self.open_tags.pop()
                self.output.append(f'</{popped}>')
                if popped == tag:
                    break

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        tag = tag.lower()
        if tag in self.DROP_CONTENT_TAGS:
            return
        if tag in self.VOID_TAGS:
            self.handle_starttag(tag, attrs)
        else:
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

    def handle_data(self, data: str):
        if self.drop_depth == 0:
            self.output.append(html.escape(data, quote=False))

    def handle_entityref(self, name: str):
        if self.drop_depth == 0:
            self.output.append(f'&{name};')

    def handle_charref(self, name: str):
        if self.drop_depth == 0:
            self.output.append(f'&#{name};')

    def sanitize(self, raw_html: str) -> str:
        self.feed(raw_html)
        while self.open_tags:
            popped = self.open_tags.pop()
            self.output.append(f'</{popped}>')
        return ''.join(self.output)


HTMLSanitizer = ArticleHTMLSanitizer


def sanitize_article_html(raw_html: str) -> str:
    """
    Sanitizes article HTML against stored XSS using a strict allowlist
    of tags and attributes. Offline-first, standard library html.parser.
    """
    if not raw_html or not isinstance(raw_html, str):
        return ''
    sanitizer = ArticleHTMLSanitizer()
    return sanitizer.sanitize(raw_html)


def extract_article_text(html_content: str) -> str:
    """
    Extracts text content from HTML by stripping all tags, unescaping HTML entities,
    and removing non-breaking and zero-width spaces.
    """
    if not html_content or not isinstance(html_content, str):
        return ""
    # Strip script, style, and similar non-content elements
    cleaned = re.sub(r'<(?:script|style|iframe|object|embed|noscript)[^>]*>.*?</(?:script|style|iframe|object|embed|noscript)>', ' ', html_content, flags=re.IGNORECASE | re.DOTALL)
    # Strip HTML tags
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    # Unescape HTML entities (&nbsp;, &amp;, etc.)
    unescaped = html.unescape(cleaned)
    # Replace non-breaking spaces (\u00a0), zero-width spaces (\u200b, \ufeff, etc.)
    normalized = re.sub(r'[\u00a0\u200b\ufeff\s]+', ' ', unescaped)
    return normalized.strip()


def make_content_snippet(raw_text: str, max_length: int = 180) -> str:
    """
    Creates a clean, plain-text snippet of given length from raw content or HTML.
    """
    cleaned = extract_article_text(raw_text or "")
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[:max_length].rstrip() + "..."


def has_valid_article_text(html_content: str) -> bool:
    """
    Validates that article body contains at least one text character [a-zA-Zа-яА-Я0-9].
    Empty tags, &nbsp;, whitespace, dividers (<hr>), and images (<img...>) only
    are strictly rejected.
    """
    if not html_content or not isinstance(html_content, str):
        return False
    sanitized = sanitize_article_html(html_content)
    text = extract_article_text(sanitized)
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


STANDARD_TOPICS = [
    ("pksc-architecture", "Архитектура и развитие ПКСК"),
    ("smart-contracts-development", "Разработка смарт-контрактов"),
    ("business-logic-deals", "Бизнес-логика и моделирование сделок"),
    ("testing-and-quality", "Тестирование и качество"),
    ("information-security", "Информационная безопасность"),
    ("audit-and-verification", "Аудит и проверка смарт-контрактов"),
    ("law-and-compliance", "Право и комплаенс"),
    ("oracles-and-data", "Оракулы и доверенные внешние данные"),
    ("integrations-and-api", "Интеграции и API"),
    ("digital-ruble-payments", "Цифровой рубль и программируемые расчеты"),
    ("lifecycle-versioning", "Жизненный цикл и версии смарт-контрактов"),
    ("infrastructure-operations", "Инфраструктура и эксплуатация"),
    ("business-cases-adoption", "Бизнес-сценарии и внедрение"),
]
TOPICS_TITLE_MAP = dict(STANDARD_TOPICS)


def init_db(db_path: Optional[str] = None, seed: Optional[bool] = None) -> sqlite3.Connection:
    """
    Initializes the SQLite database and ensures schema and tables exist.
    Optionally seeds demo data if seed is True or environment/test defaults dictate.
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

    return conn


init_moderation_db = init_db


RU_MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def format_date_ru(iso_str: str) -> str:
    """Formats an ISO timestamp to Russian localized date string (e.g. 26 сентября 2026)."""
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        day = dt.day
        month = RU_MONTHS[dt.month - 1]
        year = dt.year
        return f"{day} {month} {year}"
    except Exception:
        return "Недавно"


def calculate_reading_time(html_content: str) -> Tuple[str, int]:
    """Calculates estimated reading time in minutes based on ~200 words per minute."""
    text = extract_article_text(html_content or "")
    words = len(text.split())
    minutes = max(1, round(words / 200))
    return f"{minutes} мин", minutes


def make_svg_data_uri(svg_markup: str) -> str:
    """Returns valid offline-first base64 data URI for SVG markup."""
    b64 = base64.b64encode(svg_markup.strip().encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


APPROVED_SEED_ARTICLES = [
    {
        "id": "art-01",
        "draft_id": "draft-01",
        "title": "Интеграция смарт-контрактов с платформой цифрового рубля Банка России",
        "author_id": "author_smirnov",
        "status": "approved",
        "publication_settings": {
            "author": "Алексей Смирнов",
            "authorInitials": "АС",
            "authorRole": "Архитектор решений",
            "targetAudience": "architects-integrators",
            "topics": ["digital-ruble-payments", "pksc-architecture", "smart-contracts-development"],
            "keywords": ["Цифровой рубль", "Банк России", "ПКСК", "Смарт-контракты", "Атомарные расчеты"],
            "description": "Архитектурный анализ взаимодействия шлюзов ПКСК с платформой цифрового рубля: моделирование атомарных транзакций, двухфазный коммит и валидация криптографических подписей по ГОСТ Р 34.12-2015.",
            "format": "tutorial",
            "complexity": "hard",
            "isDemo": True,
            "coverImage": make_svg_data_uri('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 440" width="780" height="440"><defs><linearGradient id="bg1" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#060c18"/><stop offset="100%" stop-color="#0e1e38"/></linearGradient><linearGradient id="acc1" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#38bdf8"/><stop offset="100%" stop-color="#6366f1"/></linearGradient></defs><rect width="780" height="440" fill="url(#bg1)"/><circle cx="620" cy="180" r="160" fill="none" stroke="rgba(56,189,248,0.15)" stroke-width="2"/><circle cx="620" cy="180" r="110" fill="none" stroke="rgba(99,102,241,0.2)" stroke-width="1.5" stroke-dasharray="8 6"/><circle cx="620" cy="180" r="60" fill="rgba(56,189,248,0.08)"/><rect x="64" y="64" width="160" height="32" rx="16" fill="rgba(56,189,248,0.12)" stroke="rgba(56,189,248,0.3)"/><text x="84" y="85" fill="#38bdf8" font-family="Onest, sans-serif" font-size="13" font-weight="700" letter-spacing="1">ЦИФРОВОЙ РУБЛЬ</text><text x="64" y="160" fill="#ffffff" font-family="Onest, sans-serif" font-size="34" font-weight="800">Интеграция смарт-контрактов</text><text x="64" y="202" fill="#94a3b8" font-family="Onest, sans-serif" font-size="34" font-weight="800">с платформой Банка России</text><line x1="64" y1="236" x2="380" y2="236" stroke="url(#acc1)" stroke-width="3" stroke-linecap="round"/><text x="64" y="274" fill="#cbd5e1" font-family="Onest, sans-serif" font-size="16">Архитектура шлюза • Двухфазный коммит 2PC • ГОСТ Р 34.10-2012</text></svg>')
        },
        "article_html": """<h2>Нормативный контекст и архитектурный контур</h2>
<p>В рамках реализации положений Федерального закона № 259-ФЗ «О цифровых финансовых активах» и пилотного проекта Банка России по внедрению платформы цифрового рубля возникает практическая необходимость взаимодействия смарт-контрактов децентрализованных сетей (ПКСК) с централизованным контуром регулятора.</p>
<p>Ключевой вызов заключается в обеспечении атомарности расчетов (Atomicity) между двумя разнородными средами: распределенным реестром участников сделки и единым реестром цифрового рубля ЦБ РФ.</p>

<h2>Архитектура интеграционного шлюза</h2>
<p>Для бесшовного взаимодействия разворачивается двунаправленный шлюз Gateway-Node с аппаратным модулем безопасности (HSM) для криптографического подписания транзакций ключами по ГОСТ Р 34.10-2012.</p>

<blockquote class="editor-quote">
«Интеграционный шлюз должен гарантировать финализацию транзакции в реестре только после безотзывного подтверждения списания/зачисления токенов цифрового рубля в процессинговом центре Банка России».
</blockquote>

<details class="editor-spoiler">
  <summary class="editor-spoiler-title">Требования к защите каналов по ГОСТ Р 57580</summary>
  <div class="editor-spoiler-body">
    <p>Для подключения узлов шлюза к контуру платформы цифрового рубля требуется реализация взаимной аутентификации узлов с использованием криптографических протоколов TLS с алгоритмами шифрования ГОСТ Р 34.12-2015 («Кузнечик» / «Магма») и ГОСТ Р 34.10-2012. Время непрерывной сессии ограничено 4 часами.</p>
  </div>
</details>

<p>Архитектурная схема компонентов взаимодействия представлена в таблице ниже:</p>

<div class="table-responsive-wrapper">
<table class="editor-table">
  <thead>
    <tr>
      <th>Компонент</th>
      <th>Протокол</th>
      <th>Назначение</th>
      <th>SLA отклика</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Gate-Inbound</td>
      <td>gRPC / TLS ГОСТ</td>
      <td>Прием транзакций из корпоративного контура ПКСК</td>
      <td>&lt; 50 ms</td>
    </tr>
    <tr>
      <td>Signer HSM</td>
      <td>PKCS#11</td>
      <td>Аппаратная подпись сообщений ключами ГОСТ Р 34.10-2012</td>
      <td>&lt; 15 ms</td>
    </tr>
    <tr>
      <td>Settlement-Core</td>
      <td>IPC / Shared Mem</td>
      <td>Двухфазная фиксация (2PC) состояния транзакций</td>
      <td>&lt; 30 ms</td>
    </tr>
    <tr>
      <td>Ledger-Sync</td>
      <td>Kafka / Raft</td>
      <td>Репликация журналов распределенного реестра</td>
      <td>&lt; 100 ms</td>
    </tr>
  </tbody>
</table>
</div>

<h2>Модель двухфазной фиксации расчетов (2PC)</h2>
<p>Временное окно фиксации сделки рассчитывается по формуле:</p>

<div class="editor-block-formula" data-latex="T_{\\text{settlement}} = \\min\\left(T_{\\text{timeout}}, \\; T_{\\text{commit}} + \\Delta t\\right)">
  <div class="formula-rendered">$$T_{\\text{settlement}} = \\min\\left(T_{\\text{timeout}}, \\; T_{\\text{commit}} + \\Delta t\\right)$$</div>
</div>

<p>где допустимая дельта синхронизации узлов составляет <span class="editor-inline-formula" data-latex="\\Delta t \\le 1200\\text{ ms}">\\(\\Delta t \\le 1200\\text{ ms}\\)</span> при условии отсутствия сетевых коллизий.</p>

<p>Ниже приведен фрагмент контракта шлюза расчетов:</p>

<pre class="ql-syntax" spellcheck="false">// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title DigitalRubleSettlementGateway
 * @notice Прототип шлюза двухфазных расчетов с платформой ЦБ РФ
 */
contract DigitalRubleSettlementGateway {
    enum DealState { Created, Reserved, Settled, Cancelled }

    struct SettlementDeal {
        bytes32 dealId;
        address buyer;
        address seller;
        uint256 rubleAmount;
        uint256 expiryTimestamp;
        DealState state;
    }

    mapping(bytes32 => SettlementDeal) public deals;

    event DealReserved(bytes32 indexed dealId, uint256 amount);
    event DealSettled(bytes32 indexed dealId, uint256 timestamp);

    function reserve(bytes32 dealId, uint256 amount, uint256 validUntil) external {
        require(deals[dealId].state == DealState.Created, "Deal already exists");
        deals[dealId] = SettlementDeal(dealId, msg.sender, address(0), amount, validUntil, DealState.Reserved);
        emit DealReserved(dealId, amount);
    }
}</pre>

<p>Обратите внимание: параметр <span class="editor-inline-spoiler" title="Нажмите для просмотра">секретный мастер-ключ шлюза HSM</span> никогда не покидает защищенный криптографический модуль.</p>

<h2>Заключение</h2>
<p>Предложенная архитектура шлюза позволяет масштабировать корпоративные смарт-контракты в российских финансовых институтах с соблюдением требований регулятора и гарантией безотзывности расчетов.</p>""",
        "created_at": "2026-09-26T14:30:00Z",
        "updated_at": "2026-09-26T14:30:00Z"
    },
    {
        "id": "art-02",
        "draft_id": "draft-02",
        "title": "Аудит безопасности смарт-контрактов по ГОСТ Р 57580: типичные уязвимости и превентивный анализ",
        "author_id": "author_romanova",
        "status": "approved",
        "publication_settings": {
            "author": "Екатерина Романова",
            "authorInitials": "ЕР",
            "authorRole": "Ведущий аудитор безопасности",
            "targetAudience": "security-auditors",
            "topics": ["information-security", "audit-and-verification", "smart-contracts-development"],
            "keywords": ["Аудит ИБ", "ГОСТ Р 57580", "Уязвимости", "Reentrancy", "Формальная верификация"],
            "description": "Разбор критических векторов атак на корпоративные распределенные реестры: повторный вход (reentrancy), ошибки управления доступом и методы автоматизированного аудита исходного кода.",
            "format": "review",
            "complexity": "hard",
            "isDemo": True,
            "coverImage": make_svg_data_uri('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 440" width="780" height="440"><defs><linearGradient id="bg2" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#060f14"/><stop offset="100%" stop-color="#0d2220"/></linearGradient><linearGradient id="acc2" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#10b981"/><stop offset="100%" stop-color="#38bdf8"/></linearGradient></defs><rect width="780" height="440" fill="url(#bg2)"/><path d="M600 90 L710 140 L710 270 L600 350 L490 270 L490 140 Z" fill="rgba(16,185,129,0.06)" stroke="rgba(16,185,129,0.3)" stroke-width="2"/><path d="M600 130 L670 165 L670 245 L600 295 L530 245 L530 165 Z" fill="none" stroke="rgba(56,189,248,0.25)" stroke-width="1.5" stroke-dasharray="6 4"/><rect x="64" y="64" width="140" height="32" rx="16" fill="rgba(16,185,129,0.12)" stroke="rgba(16,185,129,0.3)"/><text x="84" y="85" fill="#10b981" font-family="Onest, sans-serif" font-size="13" font-weight="700" letter-spacing="1">БЕЗОПАСНОСТЬ</text><text x="64" y="160" fill="#ffffff" font-family="Onest, sans-serif" font-size="34" font-weight="800">Аудит смарт-контрактов</text><text x="64" y="202" fill="#94a3b8" font-family="Onest, sans-serif" font-size="34" font-weight="800">по стандарту ГОСТ Р 57580</text><line x1="64" y1="236" x2="380" y2="236" stroke="url(#acc2)" stroke-width="3" stroke-linecap="round"/><text x="64" y="274" fill="#cbd5e1" font-family="Onest, sans-serif" font-size="16">Превентивный анализ • ReentrancyGuard • Формальная верификация</text></svg>')
        },
        "article_html": """<h2>Нормативные требования ГОСТ Р 57580 к смарт-контрактам</h2>
<p>Стандарт ГОСТ Р 57580.1-2017 устанавливает базовый состав организационных и технических мер защиты информации в финансовых организациях РФ. При развертывании смарт-контрактов в распределенных реестрах критически важно обеспечить контроль целостности программной логики и неизменяемость аудиторского следа.</p>

<h2>Классификация критических уязвимостей</h2>
<p>В таблице ниже обобщены основные риски, выявляемые в ходе аудита смарт-контрактов распределенных реестров:</p>

<div class="table-responsive-wrapper">
<table class="editor-table">
  <thead>
    <tr>
      <th>Уязвимость</th>
      <th>Уровень риска</th>
      <th>CWE ID</th>
      <th>Метод выявления</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Повторный вход (Reentrancy)</td>
      <td>Критический (Critical)</td>
      <td>CWE-841</td>
      <td>Статический анализ + Фаззинг</td>
    </tr>
    <tr>
      <td>Ошибки управления доступом</td>
      <td>Высокий (High)</td>
      <td>CWE-284</td>
      <td>Ручной аудит + Role ACL</td>
    </tr>
    <tr>
      <td>Некорректная обработка исключений</td>
      <td>Средний (Medium)</td>
      <td>CWE-754</td>
      <td>Модульное тестирование</td>
    </tr>
    <tr>
      <td>Манипуляция внешними оракулами</td>
      <td>Высокий (High)</td>
      <td>CWE-345</td>
      <td>Стресс-тестирование TWAP</td>
    </tr>
  </tbody>
</table>
</div>

<h2>Анализ уязвимости Reentrancy и безопасные шаблоны</h2>
<p>Классическая уязвимость Reentrancy возникает, когда контракт передает управление внешнему вызывающему коду до того, как обновил свое внутреннее состояние.</p>

<details class="editor-spoiler">
  <summary class="editor-spoiler-title">Чек-лист экспресс-аудита перед компиляцией</summary>
  <div class="editor-spoiler-body">
    <p>1. Использование актуальной версии компилятора Solidity (>= 0.8.20).<br>2. Явная спецификация модификаторов доступа (AccessControl).<br>3. Паттерн Checks-Effects-Interactions для всех функций с передачей активов.<br>4. Обязательное использование ReentrancyGuard при вызове низкоуровневых операций.</p>
  </div>
</details>

<p>Пример безопасной реализации вывода средств:</p>

<pre class="ql-syntax" spellcheck="false">// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

contract SecureVault is ReentrancyGuard {
    mapping(address => uint256) private _balances;

    event Withdrawn(address indexed recipient, uint256 amount);

    function withdraw(uint256 amount) external nonReentrant {
        require(_balances[msg.sender] >= amount, "Insufficient balance");

        // 1. Effects: изменение состояния до внешнего вызова
        _balances[msg.sender] -= amount;

        // 2. Interactions: отправка средств
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer execution failed");

        emit Withdrawn(msg.sender, amount);
    }
}</pre>

<p>Для количественной оценки безопасности проекта применяется интегральный индекс риска:</p>

<div class="editor-block-formula" data-latex="\\text{RiskIndex} = \\frac{1}{N} \\sum_{i=1}^{N} \\left( P_i \\times I_i \\right) \\cdot w_i">
  <div class="formula-rendered">$$\\text{RiskIndex} = \\frac{1}{N} \\sum_{i=1}^{N} \\left( P_i \\times I_i \\right) \\cdot w_i$$</div>
</div>

<p>где <span class="editor-inline-formula" data-latex="P_i">\\(P_i\\)</span> - вероятность реализации угрозы, а <span class="editor-inline-formula" data-latex="I_i">\\(I_i\\)</span> - тяжесть последствий инцидента.</p>

<p>Для поиска скрытых дефектов используется <span class="editor-inline-spoiler" title="Нажмите для просмотра">автоматизированный символьный фаззинг Echidna и Slither</span> на этапах CI/CD.</p>

<h2>Заключение и выводы аудита</h2>
<p>Соблюдение профиля защиты ГОСТ Р 57580 и применение паттерна Checks-Effects-Interactions гарантирует устойчивость смарт-контрактов к наиболее разрушительным атакам в распределенных реестрах.</p>""",
        "created_at": "2026-09-25T18:15:00Z",
        "updated_at": "2026-09-25T18:15:00Z"
    },
    {
        "id": "art-03",
        "draft_id": "draft-03",
        "title": "Правовая квалификация смарт-контрактов и комплаенс сделок в российском праве",
        "author_id": "author_melnikov",
        "status": "approved",
        "publication_settings": {
            "author": "Илья Мельников",
            "authorInitials": "ИМ",
            "authorRole": "Советник по LegalTech и комплаенсу",
            "targetAudience": "legal-compliance",
            "topics": ["law-and-compliance", "business-logic-deals"],
            "keywords": ["Право", "Комплаенс", "ГК РФ", "Цифровые права", "ЦФА"],
            "description": "Практика применения статьи 309 ГК РФ к автоматизированному исполнению обязательств: самоисполняемые сделки, цифровые права (ЦФА) и особенности арбитражного доказывания.",
            "format": "analytics",
            "complexity": "medium",
            "isDemo": True,
            "coverImage": make_svg_data_uri('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 440" width="780" height="440"><defs><linearGradient id="bg3" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#100c1e"/><stop offset="100%" stop-color="#1a1532"/></linearGradient><linearGradient id="acc3" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#a855f7"/><stop offset="100%" stop-color="#6366f1"/></linearGradient></defs><rect width="780" height="440" fill="url(#bg3)"/><path d="M550 120 L670 120 L610 200 Z" fill="none" stroke="rgba(168,85,247,0.3)" stroke-width="2"/><line x1="610" y1="80" x2="610" y2="300" stroke="rgba(168,85,247,0.2)" stroke-width="3"/><rect x="64" y="64" width="180" height="32" rx="16" fill="rgba(168,85,247,0.12)" stroke="rgba(168,85,247,0.3)"/><text x="84" y="85" fill="#c084fc" font-family="Onest, sans-serif" font-size="13" font-weight="700" letter-spacing="1">ПРАВО И КОМПЛАЕНС</text><text x="64" y="160" fill="#ffffff" font-family="Onest, sans-serif" font-size="34" font-weight="800">Правовая квалификация</text><text x="64" y="202" fill="#94a3b8" font-family="Onest, sans-serif" font-size="34" font-weight="800">смарт-контрактов в РФ</text><line x1="64" y1="236" x2="380" y2="236" stroke="url(#acc3)" stroke-width="3" stroke-linecap="round"/><text x="64" y="274" fill="#cbd5e1" font-family="Onest, sans-serif" font-size="16">Статья 309 ГК РФ • ЦФА (259-ФЗ) • Арбитражная практика</text></svg>')
        },
        "article_html": """<h2>Правовая природа самоисполняемых обязательств</h2>
<p>С принятием Федерального закона № 34-ФЗ в Гражданский кодекс РФ была внесена норма части второй статьи 309 ГК РФ, прямо закрепляющая возможность автоматизированного исполнения сделок с использованием информационных технологий.</p>
<p>Смарт-контракт в российской юриспруденции рассматривается не как отдельный самостоятельный вид договора, а как программно-технический способ исполнения обязательств, согласованных сторонами сделки.</p>

<h2>Сравнительный анализ традиционных договоров и смарт-контрактов</h2>

<div class="table-responsive-wrapper">
<table class="editor-table">
  <thead>
    <tr>
      <th>Критерий</th>
      <th>Традиционный договор</th>
      <th>Смарт-контракт в ПКСК</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Форма фиксации</td>
      <td>Письменная / Бумажная или PDF с КЭП</td>
      <td>Исходный код + Хэш транзакции в реестре</td>
    </tr>
    <tr>
      <td>Исполнение условий</td>
      <td>Добровольное сторонами или принудительное приставами</td>
      <td>Автоматическое при наступлении триггеров</td>
    </tr>
    <tr>
      <td>Арбитражное доказывание</td>
      <td>Оригинал документа, протокол проверки КЭП</td>
      <td>Нотариальный протокол осмотра узла + Timestamp</td>
    </tr>
    <tr>
      <td>Изменение условий</td>
      <td>Дополнительное соглашение сторон</td>
      <td>Версионирование контракта / Multisig-кворум</td>
    </tr>
  </tbody>
</table>
</div>

<details class="editor-spoiler">
  <summary class="editor-spoiler-title">Судебный прецедент: нотариальный протокол распределенного реестра</summary>
  <div class="editor-spoiler-body">
    <p>В определении арбитражного суда Московского округа установлено: электронная выгрузка журналов транзакций из узла распределенного реестра, заверенная нотариусом с фиксацией меток времени RFC 3161, признается допустимым и достоверным письменным доказательством по смыслу ст. 75 АПК РФ.</p>
  </div>
</details>

<h2>Формализация комплаенс-индекса сделки</h2>
<p>Для подтверждения легитимности сделки в автоматизированных системах формируется индекс соответствия регуляторным нормам:</p>

<div class="editor-block-formula" data-latex="C_{\\text{deal}} = \\prod_{k=1}^{m} \\mathbf{1}\\left(\\text{Clause}_k \\in \\mathcal{L}_{\\text{RF}}\\right)">
  <div class="formula-rendered">$$C_{\\text{deal}} = \\prod_{k=1}^{m} \\mathbf{1}\\left(\\text{Clause}_k \\in \\mathcal{L}_{\\text{RF}}\\right)$$</div>
</div>

<p>где каждое условие <span class="editor-inline-formula" data-latex="\\text{Clause}_k">\\(\\text{Clause}_k\\)</span> проверяется на непротиворечие публичному порядку и нормам 115-ФЗ.</p>

<blockquote class="editor-quote">
«При разработке архитектуры смарт-контрактов для российского бизнеса критически важно предусматривать возможность приостановки исполнения контракта по судебному акту (circuit breaker pattern)».
</blockquote>

<h2>Практические комплаенс-рекомендации для интеграторов</h2>
<p>1. Всегда связывать идентификаторы учетных записей в смарт-контракте с реальными субъектами права через идентификацию по ЕСИА или квалифицированную электронную подпись.<br>2. Вести локальный архив исходных текстов условий и версий компилятора для обеспечения воспроизводимости кода в суде.</p>""",
        "created_at": "2026-09-24T11:00:00Z",
        "updated_at": "2026-09-24T11:00:00Z"
    },
    {
        "id": "art-04",
        "draft_id": "draft-04",
        "title": "Поставка доверенных внешних данных: проектирование децентрализованных оракулов",
        "author_id": "author_nesterov",
        "status": "approved",
        "publication_settings": {
            "author": "Виктор Нестеров",
            "authorInitials": "ВН",
            "authorRole": "Инженер распределенных систем",
            "targetAudience": "data-oracles",
            "topics": ["oracles-and-data", "integrations-and-api"],
            "keywords": ["Оракулы", "Внешние данные", "API", "Консенсус", "ЦФА"],
            "description": "Пошаговое проектирование отказоустойчивой сети поставщиков котировок и внешних юридически значимых событий для корпоративных смарт-контрактов без единой точки отказа.",
            "format": "case-study",
            "complexity": "medium",
            "isDemo": True,
            "coverImage": make_svg_data_uri('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 440" width="780" height="440"><defs><linearGradient id="bg4" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#0c141e"/><stop offset="100%" stop-color="#13273a"/></linearGradient><linearGradient id="acc4" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#f59e0b"/><stop offset="100%" stop-color="#38bdf8"/></linearGradient></defs><rect width="780" height="440" fill="url(#bg4)"/><circle cx="620" cy="180" r="130" fill="none" stroke="rgba(245,158,11,0.2)" stroke-width="1.5"/><circle cx="560" cy="150" r="14" fill="#f59e0b"/><circle cx="670" cy="130" r="10" fill="#38bdf8"/><circle cx="640" cy="240" r="12" fill="#10b981"/><line x1="560" y1="150" x2="670" y2="130" stroke="rgba(255,255,255,0.2)" stroke-width="1.5"/><line x1="670" y1="130" x2="640" y2="240" stroke="rgba(255,255,255,0.2)" stroke-width="1.5"/><line x1="640" y1="240" x2="560" y2="150" stroke="rgba(255,255,255,0.2)" stroke-width="1.5"/><rect x="64" y="64" width="160" height="32" rx="16" fill="rgba(245,158,11,0.12)" stroke="rgba(245,158,11,0.3)"/><text x="84" y="85" fill="#fbbf24" font-family="Onest, sans-serif" font-size="13" font-weight="700" letter-spacing="1">ОРАКУЛЫ И ДАННЫЕ</text><text x="64" y="160" fill="#ffffff" font-family="Onest, sans-serif" font-size="34" font-weight="800">Поставка внешних данных</text><text x="64" y="202" fill="#94a3b8" font-family="Onest, sans-serif" font-size="34" font-weight="800">для корпоративных реестров</text><line x1="64" y1="236" x2="380" y2="236" stroke="url(#acc4)" stroke-width="3" stroke-linecap="round"/><text x="64" y="274" fill="#cbd5e1" font-family="Onest, sans-serif" font-size="16">BFT-кворум • Агрегация медианы • Защита от сговора</text></svg>')
        },
        "article_html": """<h2>Проблема оракулов в изолированных реестрах</h2>
<p>Смарт-контракты исполняются в детерминированной виртуальной среде и не имеют прямого сетевого доступа к внешним HTTP/REST API. Для фиксации событий реального мира (котировки драгоценных металлов, статусы доставки грузов, курсы валют) требуются специализированные узлы - децентрализованные оракулы.</p>

<h2>Архитектура кворума поставщиков данных</h2>
<p>Одиночный оракул представляет собой критическую единую точку отказа (Single Point of Failure). Для обеспечения надежности проектируется сеть из независимых провайдеров с BFT-консенсусом.</p>

<div class="table-responsive-wrapper">
<table class="editor-table">
  <thead>
    <tr>
      <th>Уровень</th>
      <th>Технология</th>
      <th>Задача</th>
      <th>Механизм защиты</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Сбор данных</td>
      <td>Websocket / TLS 1.3</td>
      <td>Получение котировок с биржевых шлюзов</td>
      <td>Сертификаты X.509 ГОСТ</td>
    </tr>
    <tr>
      <td>Фильтрация выбросов</td>
      <td>Statistical Outlier Filter</td>
      <td>Отсечение ошибочных и аномальных значений</td>
      <td>Правило 3-сигма</td>
    </tr>
    <tr>
      <td>Агрегация консенсуса</td>
      <td>Off-chain BFT Aggregator</td>
      <td>Формирование медианного значения цены</td>
      <td>Мультиподпись BLS / ГОСТ</td>
    </tr>
    <tr>
      <td>Публикация в реестр</td>
      <td>On-chain Oracle Router</td>
      <td>Запись верифицированного значения в смарт-контракт</td>
      <td>Проверка порога кворума M of N</td>
    </tr>
  </tbody>
</table>
</div>

<details class="editor-spoiler">
  <summary class="editor-spoiler-title">Защита от сговора провайдеров (Sybil Resistance)</summary>
  <div class="editor-spoiler-body">
    <p>Применяется схема репутационного взвешивания узлов: поставщик с отклонением цены более чем на 3 сигмы теряет часть залога, который распределяется между добросовестными валидаторами кворума.</p>
  </div>
</details>

<h2>Алгоритм медианной агрегации котировок</h2>
<p>Формирование доверенной цены в распределенном кворуме определяется как:</p>

<div class="editor-block-formula" data-latex="P_{\\text{consensus}} = \\text{Median}\\left(p_1, p_2, \\dots, p_n\\right), \\quad \\left|p_i - P_{\\text{consensus}}\\right| \\le 3\\sigma">
  <div class="formula-rendered">$$P_{\\text{consensus}} = \\text{Median}\\left(p_1, p_2, \\dots, p_n\\right), \\quad \\left|p_i - P_{\\text{consensus}}\\right| \\le 3\\sigma$$</div>
</div>

<p>Фрагмент контракта агрегатора данных оракула:</p>

<pre class="ql-syntax" spellcheck="false">// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract OracleDataAggregator {
    struct PriceReport {
        uint256 price;
        uint256 timestamp;
        bytes signature;
    }

    uint256 public constant MIN_ORACLES = 5;
    uint256 public latestConsensusPrice;
    uint256 public lastUpdateTimestamp;

    event PriceUpdated(uint256 indexed price, uint256 timestamp);

    function submitReports(PriceReport[] calldata reports) external {
        require(reports.length >= MIN_ORACLES, "Quorum not reached");
        // Медианный расчет и верификация подписей
        uint256 medianPrice = _calculateMedian(reports);
        latestConsensusPrice = medianPrice;
        lastUpdateTimestamp = block.timestamp;
        emit PriceUpdated(medianPrice, block.timestamp);
    }

    function _calculateMedian(PriceReport[] calldata reports) internal pure returns (uint256) {
        // Логика сортировки и выбора медианы
        return reports[reports.length / 2].price;
    }
}</pre>

<h2>Результаты промышленного тестирования</h2>
<p>Тестирование сети из 9 узлов показало среднюю задержку поставки котировки в 1.8 секунды при 100% устойчивости к отключению до 2 узлов одновременно.</p>""",
        "created_at": "2026-09-22T09:45:00Z",
        "updated_at": "2026-09-22T09:45:00Z"
    }
]


def seed_approved_articles(conn: sqlite3.Connection):
    """
    Seeds approved articles into moderation_submissions or updates seed articles
    to ensure valid offline-first base64 cover images and clean demo metadata.
    """
    for item in APPROVED_SEED_ARTICLES:
        settings_str = json.dumps(item["publication_settings"], ensure_ascii=False)
        hash_val = compute_snapshot_hash(item["title"], item["article_html"], item["publication_settings"])
        conn.execute("""
            INSERT INTO moderation_submissions (
                id, draft_id, title, author_id, status, publication_settings,
                article_html, article_delta, idempotency_key, snapshot_hash,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                publication_settings = excluded.publication_settings,
                article_html = excluded.article_html,
                snapshot_hash = excluded.snapshot_hash
        """, (
            item["id"], item["draft_id"], item["title"], item["author_id"],
            settings_str, item["article_html"], f"seed_{item['id']}",
            hash_val, item["created_at"], item["updated_at"]
        ))


def seed_user_subscriptions(conn: sqlite3.Connection):
    """
    Seeds default subscriptions for user_demo if none exist.
    """
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM user_subscriptions WHERE user_id = 'user_demo'")
    row = cur.fetchone()
    if row and row["cnt"] > 0:
        return

    default_subs = [
        ("user_demo", "topic", "smart-contracts-development", "Разработка смарт-контрактов", "2026-09-26T12:00:00Z"),
        ("user_demo", "author", "author_smirnov", "Алексей Смирнов", "2026-09-26T12:00:00Z"),
        ("user_demo", "tag", "цифровой рубль", "Цифровой рубль", "2026-09-26T12:00:00Z"),
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, default_subs)


def seed_article_comments(conn: sqlite3.Connection):
    """
    Seeds 3 demo comments for 'art-01' publication idempotently.
    """
    demo_comments = [
        (
            "comm-seed-01",
            "art-01",
            "reader_01",
            "Тестовый читатель 1",
            None,
            "Было бы полезно увидеть пример обработки ошибки во время исполнения контракта.",
            "published",
            "2026-09-26T14:15:00Z"
        ),
        (
            "comm-seed-02",
            "art-01",
            "reader_02",
            "Тестовый читатель 2",
            None,
            "Планируется ли отдельный материал о проверке данных оракула?",
            "published",
            "2026-09-26T15:30:00Z"
        ),
        (
            "comm-seed-03",
            "art-01",
            "reader_03",
            "Тестовый читатель 3",
            None,
            "Спасибо за разбор. Особенно интересен раздел о тестировании.",
            "published",
            "2026-09-26T16:45:00Z"
        )
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO article_comments (
            id, article_id, user_id, author_name, author_avatar, content, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, demo_comments)


def seed_database(conn: sqlite3.Connection) -> None:
    """
    Seeds initial demo data (articles, subscriptions, comments, clubs, companies, profiles).
    """
    with conn:
        seed_approved_articles(conn)
        seed_user_subscriptions(conn)
        seed_article_comments(conn)
        try:
            import seed_data
            seed_data.seed_clubs(conn)
            seed_data.seed_companies(conn)
            conn.execute("""
                INSERT OR IGNORE INTO company_members (company_id, user_id, role, created_at)
                SELECT id, owner_id, 'owner', created_at FROM companies WHERE owner_id IS NOT NULL AND owner_id != '';
            """)
            seed_data.seed_articles(conn)
            seed_data.seed_user_subscriptions(conn)
            seed_data.seed_article_likes(conn)
            if hasattr(seed_data, "seed_article_votes"):
                seed_data.seed_article_votes(conn)
            seed_data.seed_article_comments(conn)
            if hasattr(seed_data, "seed_user_profiles"):
                seed_data.seed_user_profiles(conn)
        except Exception as e:
            print(f"Warning: error seeding extended data: {e}", file=sys.stderr)


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Returns a new SQLite connection for the specified database path.
    """
    target_path = db_path or os.environ.get("MODERATION_DB_PATH", DEFAULT_DB_PATH)
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
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


MAX_COVER_DECODED_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_COVER_BASE64_CHARS = 14 * 1024 * 1024 + 1024  # ~14 MB

COVER_DATA_URI_PATTERN = re.compile(
    r"^data:image/(jpeg|jpg|png|webp|gif|svg\+xml);base64,(.+)$",
    re.IGNORECASE | re.DOTALL
)


def validate_cover_image(cover_image: Any, target_media_dir: Optional[str] = None) -> CoverValidationResult:
    """
    Validates publication cover image:
    - Field is optional (None, empty string or whitespace-only is valid).
    - If provided: must be string.
    - Size: maximum 10 MB decoded data (~14 MB base64).
    - Schemes supported:
        * Relative path: /media/...
        * Data URI: data:image/(jpeg|jpg|png|webp|gif|svg+xml);base64,...
    - Deep validation via image_decoder.decode_and_validate_image:
        * PNG: signature, IHDR, IDAT, IEND, zlib decompression.
        * JPEG: SOI, SOF, APP1 EXIF orientation, EOI end marker.
        * GIF: GIF87a/GIF89a, screen descriptor, static first frame check, trailer.
        * WebP: RIFF, WEBP, VP8/VP8L/VP8X, static frame check.
        * SVG: <svg tag and viewBox.
        * Pixel bomb protection: rejects images exceeding 25 million pixels.
    - Storage:
        * Decoded binary image is automatically stored to data/media/<sha256>.<ext>.
        * Returns CoverValidationResult (unpacks as (is_valid, error_msg)).
    """
    if cover_image is None or cover_image == "":
        return CoverValidationResult(True, None, saved_url=None)

    if not isinstance(cover_image, str):
        return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")

    stripped = cover_image.strip()
    if not stripped:
        return CoverValidationResult(True, None, saved_url=None)

    if stripped.startswith("/media/"):
        if ".." in stripped or len(stripped) > 500:
            return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")
        if not re.match(r"^/media/[a-zA-Z0-9_\-\./]+$", stripped):
            return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")

        media_root = target_media_dir or MEDIA_DIR
        rel_path = stripped[len("/media/"):].lstrip("/")
        full_path = os.path.abspath(os.path.join(media_root, rel_path))
        if not full_path.startswith(os.path.abspath(media_root)):
            return CoverValidationResult(False, "Недопустимый путь к медиафайлу.")

        if os.path.isfile(full_path):
            try:
                with open(full_path, "rb") as f:
                    file_bytes = f.read()
                ok, err, meta = image_decoder.decode_and_validate_image(file_bytes)
                if not ok:
                    return CoverValidationResult(False, err or "Обложка повреждена или не может быть декодирована.")
                return CoverValidationResult(True, None, saved_url=stripped, meta=meta, image_bytes=file_bytes)
            except Exception as e:
                return CoverValidationResult(False, f"Ошибка чтения медиафайла: {str(e)}")

        return CoverValidationResult(True, None, saved_url=stripped)

    if stripped.startswith("data:image/"):
        if len(stripped) > MAX_COVER_BASE64_CHARS:
            return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")

        match = COVER_DATA_URI_PATTERN.match(stripped)
        if not match:
            return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")

        mime_sub = match.group(1).lower()
        b64_str = match.group(2).strip()

        try:
            decoded = base64.b64decode(b64_str, validate=True)
        except Exception:
            return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")

        if len(decoded) == 0 or len(decoded) > MAX_COVER_DECODED_BYTES:
            return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")

        # Deep decoding and verification via image_decoder
        ok, err, meta = image_decoder.decode_and_validate_image(decoded)
        if not ok:
            return CoverValidationResult(False, err or "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")

        ext = meta.get("format", "jpg")
        media_root = target_media_dir or MEDIA_DIR
        saved_url = save_media_file(decoded, ext, media_dir=media_root)

        return CoverValidationResult(True, None, saved_url=saved_url, meta=meta, image_bytes=decoded)

    return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")


def resolve_cover_position(settings: Any) -> Optional[str]:
    """
    Extracts or computes CSS object-position for article/card cover image.
    Supports coverPosition, objectPosition, or focalPoint (dict or string).
    """
    if not isinstance(settings, dict):
        return None
    cov_pos = settings.get("coverPosition") or settings.get("objectPosition")
    if cov_pos and isinstance(cov_pos, str) and cov_pos.strip():
        return cov_pos.strip()
    focal = settings.get("focalPoint")
    if isinstance(focal, str) and focal.strip():
        return focal.strip()
    if isinstance(focal, dict):
        x = focal.get("x")
        y = focal.get("y")
        if x is not None and y is not None:
            try:
                xf = float(x)
                yf = float(y)
                if 0 <= xf <= 1 and 0 <= yf <= 1 and (xf < 1 or yf < 1):
                    return f"{round(xf * 100, 2)}% {round(yf * 100, 2)}%"
                return f"{round(xf, 2)}% {round(yf, 2)}%"
            except (ValueError, TypeError):
                pass
    return None


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
        - coverImage: optional valid image up to 10 MB (data URI / relative /media/ path)
    """
    field_errors: Dict[str, str] = {}

    if not isinstance(payload, dict):
        return False, "Тело запроса должно быть JSON-объектом", {"payload": "Invalid JSON object"}

    pub_settings = payload.get("publicationSettings") or payload.get("publication_settings")
    if pub_settings is None and (payload.get("materialType") == "question" or payload.get("type") == "question"):
        pub_settings = {}
        payload["publicationSettings"] = pub_settings

    # Resolve materialType early to apply material-specific rules (e.g. questions)
    raw_mat = None
    if isinstance(pub_settings, dict):
        raw_mat = pub_settings.get("materialType") or pub_settings.get("type")
    if not raw_mat:
        raw_mat = payload.get("materialType") or payload.get("type")

    is_question = False
    if raw_mat is not None and isinstance(raw_mat, str):
        norm_mat = raw_mat.strip().lower()
        if norm_mat in LEGACY_MATERIAL_TYPES:
            norm_mat = LEGACY_MATERIAL_TYPES[norm_mat]
        if norm_mat in VALID_MATERIAL_TYPES:
            raw_mat = norm_mat
            is_question = (norm_mat == "question")
            if isinstance(pub_settings, dict):
                pub_settings["materialType"] = norm_mat
                pub_settings["type"] = norm_mat
            payload["materialType"] = norm_mat

    # 1. draftId
    draft_id = payload.get("draftId") or payload.get("draft_id")
    if not draft_id or not isinstance(draft_id, str) or not draft_id.strip():
        if is_question:
            draft_id = f"draft_q_{int(time.time()*1000)}"
            payload["draftId"] = draft_id
        else:
            field_errors["draftId"] = "Идентификатор черновика (draftId) обязателен."

    # 2. title
    title = payload.get("title")
    if title is None or not isinstance(title, str) or not title.strip():
        field_errors["title"] = "Заголовок статьи не может быть пустым."

    # 3. html
    article_html = payload.get("html") or payload.get("article_html") or payload.get("content")
    if article_html is None or not isinstance(article_html, str):
        field_errors["html"] = "Тело статьи должно содержать текст (буквы или цифры). Пустые блоки, пробелы и только изображения недопустимы."
    else:
        sanitized_html = sanitize_article_html(article_html)
        if not has_valid_article_text(sanitized_html):
            field_errors["html"] = "Тело статьи должно содержать текст (буквы или цифры). Пустые блоки, пробелы и только изображения недопустимы."
        else:
            if "html" in payload and isinstance(payload["html"], str):
                payload["html"] = sanitized_html
            elif "article_html" in payload and isinstance(payload["article_html"], str):
                payload["article_html"] = sanitized_html
            elif "content" in payload and isinstance(payload["content"], str):
                payload["content"] = sanitized_html

    # 4. publicationSettings
    if pub_settings is None or not isinstance(pub_settings, dict):
        field_errors["publicationSettings"] = "Настройки публикации обязательны и должны быть объектом."
    else:
        # 4a. targetAudience
        target_audience = pub_settings.get("targetAudience") or pub_settings.get("target_audience")
        if not target_audience or not isinstance(target_audience, str) or not target_audience.strip():
            if is_question:
                target_audience = "developers"
                pub_settings["targetAudience"] = "developers"
            else:
                field_errors["targetAudience"] = "Целевая аудитория обязательна и должна быть выбрана."
        elif not is_valid_id(target_audience):
            field_errors["targetAudience"] = "Указан недопустимый идентификатор целевой аудитории."

        # 4b. topics
        topics = pub_settings.get("topics")
        if topics is None or not isinstance(topics, list) or len(topics) == 0:
            if is_question:
                pub_settings["topics"] = ["smart-contracts-development"]
                topics = pub_settings["topics"]
            else:
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
            if is_question:
                pub_settings["keywords"] = []
                keywords = []
            else:
                field_errors["keywords"] = "Ключевые слова должны быть массивом строк."
        elif len(keywords) < 1:
            if not is_question:
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
        if is_question:
            if not desc or not isinstance(desc, str) or not desc.strip():
                clean_title = (title or "Вопрос сообществу").strip()
                pub_settings["description"] = clean_title[:500]
            elif len(desc.strip()) > 500:
                field_errors["description"] = "Краткое описание должно содержать от 50 до 500 символов."
        else:
            if desc is None or not isinstance(desc, str):
                field_errors["description"] = "Краткое описание обязательно."
            elif len(desc.strip()) < 50 or len(desc.strip()) > 500:
                field_errors["description"] = "Краткое описание должно содержать от 50 до 500 символов."

        # 4e. format
        fmt = pub_settings.get("format")
        if fmt is not None and fmt != "":
            if not isinstance(fmt, str) or not is_valid_id(fmt):
                field_errors["format"] = "Недопустимый формат публикации."

        # 4f. complexity (deprecated per Issue #61: optional, not enforced)
        compl = pub_settings.get("complexity")
        if compl is not None and compl != "":
            if not isinstance(compl, str) or compl not in VALID_COMPLEXITIES:
                pass

        # 4g. materialType / type (Issue #61: publication or question)
        mat_check = pub_settings.get("materialType") or pub_settings.get("type") or payload.get("materialType")
        if mat_check is not None and mat_check != "":
            if not isinstance(mat_check, str):
                field_errors["materialType"] = f"Недопустимый тип материала публикации. Допустимые типы: {', '.join(VALID_MATERIAL_TYPES)}"
            else:
                norm_mat = mat_check.strip().lower()
                if norm_mat in LEGACY_MATERIAL_TYPES:
                    norm_mat = LEGACY_MATERIAL_TYPES[norm_mat]
                if norm_mat not in VALID_MATERIAL_TYPES:
                    field_errors["materialType"] = f"Недопустимый тип материала публикации. Допустимые типы: {', '.join(VALID_MATERIAL_TYPES)}"
                else:
                    pub_settings["materialType"] = norm_mat
                    pub_settings["type"] = norm_mat
                    payload["materialType"] = norm_mat

        # 4h. coverImage
        cover_image = pub_settings.get("coverImage")
        if cover_image is not None and cover_image != "":
            cov_res = validate_cover_image(cover_image)
            is_cov_valid, cov_err = cov_res[0], cov_res[1]
            if not is_cov_valid:
                field_errors["coverImage"] = cov_err or "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ."
            elif cov_res.saved_url and cov_res.saved_url.startswith("/media/"):
                pub_settings["coverImage"] = cov_res.saved_url

        # 4i. companyId (optional)
        comp_id = pub_settings.get("companyId") or pub_settings.get("company_id")
        if comp_id is not None and comp_id != "":
            if not isinstance(comp_id, str) or not is_valid_id(comp_id):
                field_errors["companyId"] = "Недопустимый идентификатор компании."

        # 4j. clubId (optional)
        club_id = pub_settings.get("clubId") or pub_settings.get("club_id")
        if club_id is not None and club_id != "":
            if not isinstance(club_id, str) or not is_valid_id(club_id):
                field_errors["clubId"] = "Недопустимый идентификатор клуба."

    if field_errors:
        order = [
            "title", "html", "targetAudience", "topics", "keywords", "description",
            "format", "complexity", "materialType", "coverImage", "companyId", "clubId",
            "draftId", "publicationSettings"
        ]
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
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, Idempotency-Key, X-User-Id")
        self.send_header("Access-Control-Allow-Credentials", "true")

    def send_json_response(self, status_code: int, data: dict, extra_headers: Optional[List[Tuple[str, str]]] = None):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        if extra_headers:
            for hk, hv in extra_headers:
                self.send_header(hk, hv)
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def read_request_body(self, max_bytes: int = MAX_JSON_BODY_BYTES) -> Optional[bytes]:
        """
        Safely reads the request body from self.rfile with size limits and streaming chunks.
        Validates Content-Length:
        - If missing or 0, returns b"" without error.
        - If invalid, negative, or > max_bytes, returns HTTP 413 Payload Too Large and None.
        - Streams from self.rfile in 64 KB chunks, continuously monitoring total bytes read.
        - If total bytes read exceeds max_bytes, interrupts and returns HTTP 413 Payload Too Large and None.
        """
        cl_header = self.headers.get("Content-Length")
        if cl_header is None:
            return b""

        cl_str = cl_header.strip()
        if not cl_str:
            return b""

        try:
            content_length = int(cl_str)
        except (ValueError, TypeError):
            self.close_connection = True
            self.send_json_response(413, {
                "success": False,
                "error": "Payload Too Large: некорректный заголовок Content-Length"
            }, extra_headers=[("Connection", "close")])
            return None

        if content_length < 0:
            self.close_connection = True
            self.send_json_response(413, {
                "success": False,
                "error": "Payload Too Large: некорректный заголовок Content-Length"
            }, extra_headers=[("Connection", "close")])
            return None

        if content_length == 0:
            return b""

        if content_length > max_bytes:
            self.close_connection = True
            self.send_json_response(413, {
                "success": False,
                "error": f"Payload Too Large: размер тела запроса ({content_length} байт) превышает допустимый лимит ({max_bytes} байт)"
            }, extra_headers=[("Connection", "close")])
            return None

        chunks = []
        total_read = 0
        remaining = content_length
        chunk_size = 64 * 1024

        while remaining > 0:
            to_read = min(remaining, chunk_size)
            chunk = self.rfile.read(to_read)
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > max_bytes:
                self.close_connection = True
                self.send_json_response(413, {
                    "success": False,
                    "error": f"Payload Too Large: размер тела запроса превышает допустимый лимит ({max_bytes} байт)"
                }, extra_headers=[("Connection", "close")])
                return None
            chunks.append(chunk)
            remaining -= len(chunk)

        return b"".join(chunks)

    def read_json_body(
        self,
        max_bytes: int = MAX_JSON_BODY_BYTES,
        allow_empty: bool = False,
        default_empty: Optional[dict] = None
    ) -> Optional[dict]:
        raw_body = self.read_request_body(max_bytes)
        if raw_body is None:
            return None

        if not raw_body or not raw_body.strip():
            if allow_empty:
                return default_empty if default_empty is not None else {}
            self.send_json_response(400, {
                "success": False,
                "error": "Тело запроса не может быть пустым."
            })
            return None

        try:
            data = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.send_json_response(400, {
                "success": False,
                "error": f"Невалидный JSON: {str(e)}"
            })
            return None
        except Exception as e:
            self.send_json_response(400, {
                "success": False,
                "error": f"Ошибка декодирования запроса: {str(e)}"
            })
            return None

        if not isinstance(data, dict):
            self.send_json_response(400, {
                "success": False,
                "error": "Тело запроса должно быть JSON-объектом."
            })
            return None

        return data

    def is_secure_request(self) -> bool:
        """Determines if the request was made over HTTPS or behind an HTTPS reverse proxy."""
        if self.headers.get("X-Forwarded-Proto", "").strip().lower() == "https":
            return True
        if hasattr(self, "connection") and hasattr(self.connection, "getpeercert"):
            try:
                if self.connection.getpeercert() is not None:
                    return True
            except Exception:
                pass
        return False

    def get_session_token(self) -> Optional[str]:
        """
        Extracts session token from Cookie 'sc_session' or Authorization 'Bearer <token>'.
        """
        cookie_header = self.headers.get("Cookie", "")
        if cookie_header:
            for part in cookie_header.split(";"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    if k.strip() == "sc_session" and v.strip():
                        return v.strip()

        auth_header = self.headers.get("Authorization", "").strip()
        if auth_header:
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:].strip()
                if token:
                    return token

        return None

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Extracts authenticated user by validating session token from Cookie or Authorization header against the sessions table.
        Rejects revoked or expired sessions. Ignores X-User-Id and query parameters.
        """
        token = self.get_session_token()
        if not token:
            return None

        conn = None
        try:
            conn = self.get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT user_id, user_name, user_role, expires_at, is_revoked
                FROM sessions
                WHERE token = ?
            """, (token,))
            row = cur.fetchone()
        except Exception:
            return None
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

        if not row:
            return None

        if row["is_revoked"] != 0:
            return None

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        try:
            exp_str = str(row["expires_at"]).replace("Z", "+00:00")
            exp_dt = datetime.datetime.fromisoformat(exp_str)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
            if exp_dt <= now_dt:
                return None
        except Exception:
            return None

        return {
            "id": row["user_id"],
            "name": row["user_name"],
            "role": row["user_role"] if "user_role" in row.keys() else "user"
        }

    def is_moderator_or_admin(self, user: Optional[Dict[str, Any]]) -> bool:
        if not user:
            return False
        return user.get("role") in ("moderator", "admin") or bool(user.get("isAdmin"))

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
        elif path == "/api/auth/status":
            user = self.get_current_user()
            if user:
                self.send_json_response(200, {"success": True, "authenticated": True, "user": user})
            else:
                self.send_json_response(200, {"success": True, "authenticated": False, "user": None})
        elif path == "/api/user/feed-settings":
            self.handle_get_feed_settings()
        elif path == "/api/exceptions":
            self.handle_get_exceptions()
        elif path == "/api/subscriptions":
            self.handle_get_subscriptions()
        elif path == "/api/subscriptions/entities":
            self.handle_get_subscription_entities(parsed)
        elif path == "/api/moderation/status":
            self.handle_moderation_status(parsed)
        elif path == "/api/moderation/list":
            self.handle_moderation_list()
        elif (path.startswith("/api/articles/") or path.startswith("/api/questions/")) and path.endswith("/comments"):
            prefix = "/api/articles/" if path.startswith("/api/articles/") else "/api/questions/"
            art_id = path[len(prefix): -len("/comments")].strip("/")
            self.handle_get_article_comments(art_id)
        elif path.rstrip("/") == "/api/comments/subscriptions":
            self.handle_get_comment_subscriptions()
        elif path.rstrip("/") == "/api/comments/saved":
            self.handle_get_saved_comments()
        elif path.rstrip("/") in ("/api/saved/counts", "/api/user/saved-stats"):
            self.handle_get_saved_counts()
        elif path.rstrip("/") == "/api/saved":
            self.handle_get_saved(parsed)
        elif path == "/api/comments":
            query = urllib.parse.parse_qs(parsed.query)
            art_id = (query.get("articleId", [""])[0] or query.get("article_id", [""])[0] or query.get("id", [""])[0]).strip()
            self.handle_get_article_comments(art_id)
        elif path == "/api/questions/unanswered":
            self.handle_get_unanswered_questions()
        elif path in ("/api/articles", "/api/questions") or path.startswith("/api/articles/") or path.startswith("/api/questions/"):
            self.handle_articles_api(parsed)
        elif path.startswith("/media/"):
            self.handle_serve_media(parsed)
        elif path == "/api/clubs" or path.startswith("/api/clubs/"):
            if path == "/api/clubs":
                self.handle_get_clubs(parsed)
            else:
                club_id = path[len("/api/clubs/"):].strip("/")
                self.handle_get_club_detail(club_id)
        elif path == "/api/companies" or path.startswith("/api/companies/"):
            if path == "/api/companies":
                self.handle_get_companies(parsed)
            else:
                company_id = path[len("/api/companies/"):].strip("/")
                self.handle_get_company_detail(company_id)
        elif path == "/api/directions":
            self.handle_get_directions(parsed)
        elif path == "/api/notifications":
            self.handle_get_notifications()
        elif path.startswith("/api/users/"):
            rest = path[len("/api/users/"):].strip("/")
            if rest.endswith("/activity"):
                user_id = rest[:-len("/activity")].strip("/")
                self.handle_get_user_activity(user_id, parsed)
            elif rest.endswith("/publications"):
                user_id = rest[:-len("/publications")].strip("/")
                self.handle_get_user_publications(user_id, parsed)
            elif rest.endswith("/questions"):
                user_id = rest[:-len("/questions")].strip("/")
                self.handle_get_user_questions(user_id, parsed)
            elif rest.endswith("/answers"):
                user_id = rest[:-len("/answers")].strip("/")
                self.handle_get_user_answers(user_id, parsed)
            else:
                user_id = rest
                if user_id.endswith("/profile"):
                    user_id = user_id[:-len("/profile")].strip("/")
                self.handle_get_user_profile(user_id)
        elif path == "/api/user/profile":
            self.handle_get_current_user_profile(parsed)
        elif path.startswith("/user/"):
            uid = path[len("/user/"):].strip("/")
            if uid:
                self.send_response(302)
                self.send_header("Location", f"/profile.html?id={urllib.parse.quote(uid)}")
                self.end_headers()
                return
        elif path in ("/mobile", "/emulator", "/mobile/", "/emulator/"):
            self.send_response(302)
            self.send_header("Location", "/mobile.html")
            self.end_headers()
            return
        elif path.startswith("/api/"):
            self.send_json_response(404, {
                "success": False,
                "error": f"API endpoint not found: {path}"
            })
        else:
            # Delegate to SimpleHTTPRequestHandler for static files
            super().do_GET()

    def do_HEAD(self):
        """Handle HEAD requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/user/"):
            uid = path[len("/user/"):].strip("/")
            if uid:
                self.send_response(302)
                self.send_header("Location", f"/profile.html?id={urllib.parse.quote(uid)}")
                self.end_headers()
                return
        if path in ("/mobile", "/emulator", "/mobile/", "/emulator/"):
            self.send_response(302)
            self.send_header("Location", "/mobile.html")
            self.end_headers()
            return
        super().do_HEAD()

    def do_POST(self):
        """Handle POST requests for REST API."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/auth/login":
            self.handle_auth_login()
        elif path == "/api/auth/logout":
            self.handle_auth_logout()
        elif path == "/api/user/feed-settings":
            self.handle_post_feed_settings()
        elif path == "/api/clubs":
            self.handle_post_club()
        elif path == "/api/companies":
            self.handle_post_company()
        elif path == "/api/likes/toggle":
            p = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
            if p is None:
                return
            art_id = p.get("articleId") or p.get("article_id") or ""
            self.handle_article_like_toggle(art_id, _body_already_read=True)
        elif path.startswith("/api/articles/") and path.endswith("/like"):
            art_id = path[len("/api/articles/"): -len("/like")].strip("/")
            self.handle_article_like_toggle(art_id, _body_already_read=False)
        elif path in ("/api/saves/toggle", "/api/bookmarks/toggle"):
            p = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
            if p is None:
                return
            art_id = p.get("articleId") or p.get("article_id") or ""
            self.handle_article_save_toggle(art_id, action="toggle", _body_already_read=True)
        elif (path.startswith("/api/articles/") or path.startswith("/api/questions/")) and path.endswith("/save"):
            prefix = "/api/articles/" if path.startswith("/api/articles/") else "/api/questions/"
            art_id = path[len(prefix): -len("/save")].strip("/")
            self.handle_article_save_toggle(art_id, action="save", _body_already_read=False)
        elif (path.startswith("/api/articles/") or path.startswith("/api/questions/")) and path.endswith("/unsave"):
            prefix = "/api/articles/" if path.startswith("/api/articles/") else "/api/questions/"
            art_id = path[len(prefix): -len("/unsave")].strip("/")
            self.handle_article_save_toggle(art_id, action="unsave", _body_already_read=False)
        elif (path.startswith("/api/articles/") or path.startswith("/api/questions/")) and path.endswith("/bookmark"):
            prefix = "/api/articles/" if path.startswith("/api/articles/") else "/api/questions/"
            art_id = path[len(prefix): -len("/bookmark")].strip("/")
            self.handle_article_save_toggle(art_id, action="toggle", _body_already_read=False)
        elif path in ("/api/articles/sync-saves", "/api/saves/sync"):
            self.handle_sync_saves()
        elif path.startswith("/api/articles/") and "/comments/" in path and path.endswith("/solution"):
            parts = path.strip("/").split("/")
            art_id = parts[2] if len(parts) >= 6 else ""
            comm_id = parts[4] if len(parts) >= 6 else ""
            self.handle_comment_solution_toggle(art_id, comm_id)
        elif path.startswith("/api/articles/") and path.endswith("/solution"):
            art_id = path[len("/api/articles/"): -len("/solution")].strip("/")
            self.handle_comment_solution_toggle(art_id, "")
        elif path.startswith("/api/comments/") and path.endswith("/solution"):
            parts = path.strip("/").split("/")
            comm_id = parts[2] if len(parts) >= 4 else ""
            self.handle_comment_solution_toggle("", comm_id)
        elif path.startswith("/api/articles/") and "/comments/" in path and path.endswith("/vote"):
            parts = path.strip("/").split("/")
            comm_id = parts[4] if len(parts) >= 6 else ""
            self.handle_comment_vote(comm_id)
        elif path.startswith("/api/comments/") and path.endswith("/vote"):
            comm_id = path[len("/api/comments/"): -len("/vote")].strip("/")
            self.handle_comment_vote(comm_id)
        elif path.startswith("/api/articles/") and "/comments/" in path and path.rstrip("/").endswith("/report"):
            parts = path.strip("/").split("/")
            comm_id = parts[4] if len(parts) >= 6 else ""
            self.handle_comment_report(comm_id)
        elif path.rstrip("/").startswith("/api/comments/") and path.rstrip("/").endswith("/report"):
            comm_id = path.rstrip("/")[len("/api/comments/"): -len("/report")].strip("/")
            self.handle_comment_report(comm_id)
        elif path.startswith("/api/articles/") and "/comments/" in path and path.rstrip("/").endswith("/subscribe"):
            parts = path.strip("/").split("/")
            comm_id = parts[4] if len(parts) >= 6 else ""
            self.handle_comment_subscribe_toggle(comm_id)
        elif path.rstrip("/").startswith("/api/comments/") and path.rstrip("/").endswith("/subscribe"):
            comm_id = path.rstrip("/")[len("/api/comments/"): -len("/subscribe")].strip("/")
            self.handle_comment_subscribe_toggle(comm_id)
        elif path.rstrip("/").startswith("/api/comments/") and (path.rstrip("/").endswith("/save") or path.rstrip("/").endswith("/bookmark") or path.rstrip("/").endswith("/unsave")):
            action = "unsave" if path.rstrip("/").endswith("/unsave") else "toggle"
            suffix = "/unsave" if action == "unsave" else ("/bookmark" if path.rstrip("/").endswith("/bookmark") else "/save")
            comm_id = path.rstrip("/")[len("/api/comments/"): -len(suffix)].strip("/")
            self.handle_comment_save_toggle(comm_id, action=action)
        elif path.startswith("/api/articles/") and "/comments/" in path and (path.rstrip("/").endswith("/save") or path.rstrip("/").endswith("/bookmark") or path.rstrip("/").endswith("/unsave")):
            parts = path.strip("/").split("/")
            comm_id = parts[4] if len(parts) >= 6 else ""
            action = "unsave" if path.rstrip("/").endswith("/unsave") else "toggle"
            self.handle_comment_save_toggle(comm_id, action=action)
        elif path.rstrip("/") in ("/api/comments/save", "/api/comments/toggle-save"):
            self.handle_comment_save_toggle("", action="toggle")
        elif path.rstrip("/") in ("/api/comments/sync-saves", "/api/comments/sync"):
            self.handle_comment_saves_sync()
        elif (path.startswith("/api/articles/") or path.startswith("/api/questions/")) and not "/comments/" in path and path.rstrip("/").endswith("/report"):
            prefix = "/api/articles/" if path.startswith("/api/articles/") else "/api/questions/"
            art_id = path.rstrip("/")[len(prefix): -len("/report")].strip("/")
            self.handle_article_report(art_id)
        elif (path.startswith("/api/articles/") or path.startswith("/api/questions/")) and path.endswith("/vote"):
            prefix = "/api/articles/" if path.startswith("/api/articles/") else "/api/questions/"
            art_id = path[len(prefix): -len("/vote")].strip("/")
            self.handle_article_vote(art_id)
        elif (path.startswith("/api/articles/") or path.startswith("/api/questions/")) and path.endswith("/comments"):
            prefix = "/api/articles/" if path.startswith("/api/articles/") else "/api/questions/"
            art_id = path[len(prefix): -len("/comments")].strip("/")
            self.handle_post_article_comment(art_id)
        elif path == "/api/comments":
            self.handle_post_article_comment("")
        elif path == "/api/notifications/read":
            self.handle_post_notifications_read()
        elif path == "/api/user/profile":
            self.handle_post_user_profile()
        elif path == "/api/exceptions/toggle":
            self.handle_exceptions_toggle()
        elif path == "/api/subscriptions/toggle":
            self.handle_subscriptions_toggle()
        elif path == "/api/moderation/submit":
            self.handle_moderation_submit()
        elif path == "/api/media/upload" or path == "/api/upload/image":
            self.handle_media_upload()
        elif path.startswith("/api/"):
            raw_body = self.read_request_body(MAX_JSON_BODY_BYTES)
            if raw_body is None:
                return
            self.send_json_response(404, {
                "success": False,
                "error": f"API endpoint not found: {path}"
            })
        else:
            raw_body = self.read_request_body(MAX_JSON_BODY_BYTES)
            if raw_body is None:
                return
            self.send_json_response(405, {
                "success": False,
                "error": "Method Not Allowed"
            })

    def do_PUT(self):
        """Handle PUT requests for comments update and API fallback."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/articles/") and "/comments/" in path:
            parts = path.strip("/").split("/")
            if len(parts) >= 5:
                art_id = parts[2]
                comm_id = parts[4]
                self.handle_update_article_comment(art_id, comm_id)
                return
        elif path.startswith("/api/comments/"):
            parts = path.strip("/").split("/")
            if len(parts) >= 3:
                comm_id = parts[2]
                self.handle_update_article_comment("", comm_id)
                return

        raw_body = self.read_request_body(MAX_JSON_BODY_BYTES)
        if raw_body is None:
            return
        if path.startswith("/api/"):
            self.send_json_response(405, {
                "success": False,
                "error": f"Method Not Allowed: PUT {path}"
            })
        else:
            self.send_json_response(405, {
                "success": False,
                "error": "Method Not Allowed"
            })

    def do_DELETE(self):
        """Handle DELETE requests for comments and API fallback."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/articles/") and "/comments/" in path:
            parts = path.strip("/").split("/")
            if len(parts) >= 5:
                art_id = parts[2]
                comm_id = parts[4]
                self.handle_delete_article_comment(art_id, comm_id)
                return
        elif path.startswith("/api/comments/"):
            parts = path.strip("/").split("/")
            if len(parts) >= 3:
                comm_id = parts[2]
                self.handle_delete_article_comment("", comm_id)
                return

        if path.startswith("/api/"):
            self.send_json_response(405, {
                "success": False,
                "error": f"Method Not Allowed: DELETE {path}"
            })
        else:
            self.send_json_response(405, {
                "success": False,
                "error": "Method Not Allowed"
            })

    def handle_auth_login(self):
        """POST /api/auth/login generates secure session token, saves to sessions table, sets sc_session cookie."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if data is None:
            return

        user_id = (data.get("userId") or data.get("user_id") or data.get("authorId") or data.get("author_id") or "user_demo").strip()
        user_name = (data.get("name") or ("Демо Пользователь" if user_id == "user_demo" else user_id)).strip()
        role = data.get("role") or ("admin" if user_id in ("admin", "user_admin") else "moderator" if user_id in ("moderator", "user_moderator") else "user")
        user = {"id": user_id, "name": user_name, "role": role}

        token = secrets.token_hex(32)
        now = datetime.datetime.now(datetime.timezone.utc)
        created_at = now.isoformat()
        expires_at = (now + datetime.timedelta(days=7)).isoformat()

        conn = None
        try:
            conn = self.get_db()
            with conn:
                conn.execute("""
                    INSERT INTO sessions (token, user_id, user_name, user_role, created_at, expires_at, is_revoked)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                """, (token, user_id, user_name, role, created_at, expires_at))
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

        secure_flag = "; Secure" if self.is_secure_request() else ""
        cookie_header = f"sc_session={token}; Path=/; HttpOnly; SameSite=Lax{secure_flag}"

        self.send_json_response(200, {
            "success": True,
            "authenticated": True,
            "user": user,
            "sessionToken": token
        }, extra_headers=[("Set-Cookie", cookie_header)])

    def handle_auth_logout(self):
        """POST /api/auth/logout revokes session in DB and clears sc_session cookie."""
        raw_body = self.read_request_body(MAX_JSON_BODY_BYTES)
        if raw_body is None:
            return
        token = self.get_session_token()
        if token:
            conn = None
            try:
                conn = self.get_db()
                with conn:
                    conn.execute("UPDATE sessions SET is_revoked = 1 WHERE token = ?", (token,))
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        secure_flag = "; Secure" if self.is_secure_request() else ""
        cookie_header = f"sc_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax{secure_flag}"

        self.send_json_response(200, {
            "success": True,
            "authenticated": False
        }, extra_headers=[("Set-Cookie", cookie_header)])

    def handle_get_subscriptions(self):
        """GET /api/subscriptions returns user's active subscriptions."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Unauthorized", "requireAuth": True})
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT target_type, target_id, target_title, created_at 
                FROM user_subscriptions WHERE user_id = ? ORDER BY id ASC
            """, (user["id"],))
            rows = cur.fetchall()

        subs = {"authors": [], "topics": [], "tags": [], "clubs": [], "companies": []}
        for r in rows:
            t = r["target_type"]
            entry = {"id": r["target_id"], "title": r["target_title"], "createdAt": r["created_at"]}
            if t == "author":
                subs["authors"].append(entry)
            elif t == "topic":
                subs["topics"].append(entry)
            elif t == "tag":
                subs["tags"].append(entry)
            elif t == "club":
                subs["clubs"].append(entry)
            elif t == "company":
                subs["companies"].append(entry)

        self.send_json_response(200, {
            "success": True,
            "user": user,
            "subscriptions": subs
        })

    def handle_get_exceptions(self):
        """GET /api/exceptions returns user's active feed exceptions."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(200, {
                "success": True,
                "exceptions": {"authors": [], "topics": [], "tags": [], "clubs": [], "companies": []},
                "total": 0
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT target_type, target_id, target_title, created_at 
                FROM user_feed_exceptions WHERE user_id = ? ORDER BY id ASC
            """, (user["id"],))
            rows = cur.fetchall()

        exceptions = {"authors": [], "topics": [], "tags": [], "clubs": [], "companies": []}
        for r in rows:
            t = r["target_type"]
            entry = {"id": r["target_id"], "title": r["target_title"], "createdAt": r["created_at"]}
            if t == "author":
                exceptions["authors"].append(entry)
            elif t == "topic":
                exceptions["topics"].append(entry)
            elif t == "tag":
                exceptions["tags"].append(entry)
            elif t == "club":
                exceptions["clubs"].append(entry)
            elif t == "company":
                exceptions["companies"].append(entry)

        total = len(exceptions["authors"]) + len(exceptions["topics"]) + len(exceptions["tags"]) + len(exceptions["clubs"]) + len(exceptions["companies"])
        self.send_json_response(200, {
            "success": True,
            "user": user,
            "exceptions": exceptions,
            "total": total
        })

    def handle_subscriptions_toggle(self):
        """POST /api/subscriptions/toggle toggles subscription state."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if data is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Unauthorized", "requireAuth": True})
            return

        target_type = (data.get("targetType") or data.get("target_type") or "").strip().lower()
        raw_id = (data.get("targetId") or data.get("target_id") or "").strip()
        raw_title = (data.get("targetTitle") or data.get("target_title") or "").strip()

        if target_type not in ("author", "topic", "tag", "club", "company"):
            self.send_json_response(400, {"success": False, "error": "targetType must be 'author', 'topic', 'tag', 'club', or 'company'"})
            return

        if not raw_id:
            self.send_json_response(400, {"success": False, "error": "targetId is required"})
            return

        # Normalize tag ID (lowercase, trim extra spaces, remove #)
        if target_type == "tag":
            normalized_id = normalize_keyword(raw_id).lstrip('#').strip().lower()
            title = normalize_keyword(raw_title or raw_id).lstrip('#').strip()
        else:
            normalized_id = raw_id
            title = raw_title or raw_id

        if target_type == "author" and (normalized_id or "").strip() == (user["id"] or "").strip():
            self.send_json_response(400, {
                "success": False,
                "error": "Нельзя подписаться на самого себя",
                "code": "SELF_SUBSCRIPTION_FORBIDDEN"
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id FROM user_subscriptions 
                WHERE user_id = ? AND target_type = ? AND target_id = ?
            """, (user["id"], target_type, normalized_id))
            row = cur.fetchone()

            if row:
                cur.execute("DELETE FROM user_subscriptions WHERE id = ?", (row["id"],))
                subscribed = False
            else:
                now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cur.execute("""
                    INSERT INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (user["id"], target_type, normalized_id, title, now_str))
                # Remove from exceptions if present (mutual exclusion)
                cur.execute("""
                    DELETE FROM user_feed_exceptions
                    WHERE user_id = ? AND target_type = ? AND target_id = ?
                """, (user["id"], target_type, normalized_id))
                subscribed = True

        self.send_json_response(200, {
            "success": True,
            "subscribed": subscribed,
            "isSubscribed": subscribed,
            "is_subscribed": subscribed,
            "targetType": target_type,
            "targetId": normalized_id,
            "targetTitle": title
        })

    def handle_exceptions_toggle(self):
        """POST /api/exceptions/toggle toggles exception state."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if data is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Unauthorized", "requireAuth": True})
            return

        target_type = (data.get("targetType") or data.get("target_type") or "").strip().lower()
        raw_id = (data.get("targetId") or data.get("target_id") or "").strip()
        raw_title = (data.get("targetTitle") or data.get("target_title") or "").strip()

        if target_type not in ("author", "topic", "tag", "club", "company"):
            self.send_json_response(400, {"success": False, "error": "targetType must be 'author', 'topic', 'tag', 'club', or 'company'"})
            return

        if not raw_id:
            self.send_json_response(400, {"success": False, "error": "targetId is required"})
            return

        # Normalize tag ID (lowercase, trim extra spaces, remove #)
        if target_type == "tag":
            normalized_id = normalize_keyword(raw_id).lstrip('#').strip().lower()
            title = normalize_keyword(raw_title or raw_id).lstrip('#').strip()
        else:
            normalized_id = raw_id
            title = raw_title or raw_id

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id FROM user_feed_exceptions 
                WHERE user_id = ? AND target_type = ? AND target_id = ?
            """, (user["id"], target_type, normalized_id))
            row = cur.fetchone()

            if row:
                cur.execute("DELETE FROM user_feed_exceptions WHERE id = ?", (row["id"],))
                excluded = False
            else:
                now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cur.execute("""
                    INSERT INTO user_feed_exceptions (user_id, target_type, target_id, target_title, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (user["id"], target_type, normalized_id, title, now_str))
                # Remove from subscriptions if present (mutual exclusion)
                cur.execute("""
                    DELETE FROM user_subscriptions
                    WHERE user_id = ? AND target_type = ? AND target_id = ?
                """, (user["id"], target_type, normalized_id))
                excluded = True

        self.send_json_response(200, {
            "success": True,
            "excluded": excluded,
            "isExcluded": excluded,
            "is_excluded": excluded,
            "targetType": target_type,
            "targetId": normalized_id,
            "targetTitle": title
        })

    def handle_get_subscription_entities(self, parsed_url=None):
        """GET /api/subscriptions/entities returns catalog of entities available for subscription/exclusion."""
        if parsed_url is None:
            parsed_url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_url.query)
        entity_type = (query.get("type", [""])[0] or "").strip().lower()
        search_query = (query.get("search", [""])[0] or "").strip().lower()

        try:
            limit = max(1, min(100, int(query.get("limit", [20])[0])))
        except ValueError:
            limit = 20

        try:
            offset = max(0, int(query.get("offset", [0])[0]))
        except ValueError:
            offset = 0

        user = self.get_current_user()
        user_subs = set()
        user_exceptions = set()
        conn = self.get_db()
        with conn:
            if user:
                cur = conn.cursor()
                cur.execute("SELECT target_type, target_id FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                for r in cur.fetchall():
                    user_subs.add((r["target_type"], r["target_id"]))
                cur.execute("SELECT target_type, target_id FROM user_feed_exceptions WHERE user_id = ?", (user["id"],))
                for r in cur.fetchall():
                    user_exceptions.add((r["target_type"], r["target_id"]))

            cur = conn.cursor()
            cur.execute("SELECT * FROM moderation_submissions WHERE status = 'approved' ORDER BY created_at DESC")
            rows = cur.fetchall()

            cur.execute("SELECT * FROM clubs ORDER BY created_at ASC")
            club_rows = cur.fetchall()

            cur.execute("SELECT * FROM companies ORDER BY created_at ASC")
            comp_rows = cur.fetchall()

        authors_map = {}
        tags_map = {}
        topics_counts = {}
        club_counts = {}
        comp_counts = {}

        for row in rows:
            try:
                settings = json.loads(row["publication_settings"]) if row["publication_settings"] else {}
            except Exception:
                settings = {}

            author_id = row["author_id"]
            author_name = settings.get("author") or "Автор платформы"
            author_role = settings.get("authorRole") or ""
            author_avatar = settings.get("authorAvatar") or settings.get("avatar") or None
            if author_id not in authors_map:
                authors_map[author_id] = {
                    "id": author_id,
                    "title": author_name,
                    "role": author_role,
                    "avatar": author_avatar,
                    "count": 0,
                    "isSubscribed": ("author", author_id) in user_subs,
                    "isExcluded": ("author", author_id) in user_exceptions
                }
            authors_map[author_id]["count"] += 1
            if author_avatar and not authors_map[author_id].get("avatar"):
                authors_map[author_id]["avatar"] = author_avatar

            for t in settings.get("topics") or []:
                topics_counts[t] = topics_counts.get(t, 0) + 1

            for k in settings.get("keywords") or []:
                norm_tag = normalize_keyword(k).lstrip('#').strip().lower()
                display_tag = normalize_keyword(k).lstrip('#').strip()
                if norm_tag:
                    if norm_tag not in tags_map:
                        tags_map[norm_tag] = {
                            "id": norm_tag,
                            "title": display_tag,
                            "count": 0,
                            "isSubscribed": ("tag", norm_tag) in user_subs,
                            "isExcluded": ("tag", norm_tag) in user_exceptions
                        }
                    tags_map[norm_tag]["count"] += 1

            cid = settings.get("clubId")
            if cid:
                club_counts[cid] = club_counts.get(cid, 0) + 1

            cmp_id = settings.get("companyId")
            if cmp_id:
                comp_counts[cmp_id] = comp_counts.get(cmp_id, 0) + 1

        import seed_data
        desc_map = seed_data.TOPICS_DESCRIPTION_MAP

        topics_list = []
        for tid, tname in STANDARD_TOPICS:
            topics_list.append({
                "id": tid,
                "title": tname,
                "description": desc_map.get(tid, ""),
                "count": topics_counts.get(tid, 0),
                "isSubscribed": ("topic", tid) in user_subs,
                "isExcluded": ("topic", tid) in user_exceptions
            })

        authors_list = sorted(list(authors_map.values()), key=lambda x: (-x["count"], x["title"]))
        tags_list = sorted(list(tags_map.values()), key=lambda x: (-x["count"], x["title"]))

        clubs_list = []
        for cr in club_rows:
            cid = cr["id"]
            clubs_list.append({
                "id": cid,
                "title": cr["title"],
                "description": cr["description"],
                "count": club_counts.get(cid, 0),
                "isSubscribed": ("club", cid) in user_subs,
                "isExcluded": ("club", cid) in user_exceptions
            })

        companies_list = []
        for cpr in comp_rows:
            cid = cpr["id"]
            companies_list.append({
                "id": cid,
                "title": cpr["name"],
                "name": cpr["name"],
                "description": cpr["description"],
                "specialization": cpr["specialization"],
                "count": comp_counts.get(cid, 0),
                "isSubscribed": ("company", cid) in user_subs,
                "isExcluded": ("company", cid) in user_exceptions
            })

        def match_search(item: dict) -> bool:
            if not search_query:
                return True
            title_match = search_query in (item.get("title") or item.get("name") or "").lower()
            id_match = search_query in (item.get("id") or "").lower()
            role_match = search_query in (item.get("role") or item.get("specialization") or "").lower()
            desc_match = search_query in (item.get("description") or "").lower()
            return title_match or id_match or role_match or desc_match

        if entity_type:
            if entity_type in ("author", "authors"):
                source = authors_list
            elif entity_type in ("topic", "topics"):
                source = topics_list
            elif entity_type in ("tag", "tags"):
                source = tags_list
            elif entity_type in ("club", "clubs"):
                source = clubs_list
            elif entity_type in ("company", "companies"):
                source = companies_list
            else:
                source = []

            filtered_items = [it for it in source if match_search(it)]
            total = len(filtered_items)
            paged_items = filtered_items[offset : offset + limit]
            has_more = (offset + limit) < total

            self.send_json_response(200, {
                "success": True,
                "items": paged_items,
                "total": total,
                "limit": limit,
                "offset": offset,
                "hasMore": has_more
            })
            return

        # Full catalog when entity_type is not specified
        filtered_authors = [it for it in authors_list if match_search(it)]
        filtered_topics = [it for it in topics_list if match_search(it)]
        filtered_tags = [it for it in tags_list if match_search(it)]
        filtered_clubs = [it for it in clubs_list if match_search(it)]
        filtered_companies = [it for it in companies_list if match_search(it)]

        self.send_json_response(200, {
            "success": True,
            "authors": filtered_authors,
            "topics": filtered_topics,
            "tags": filtered_tags,
            "clubs": filtered_clubs,
            "companies": filtered_companies
        })

    def handle_get_clubs(self, parsed_url):
        """GET /api/clubs returns catalog of professional communities."""
        query = urllib.parse.parse_qs(parsed_url.query)
        search_query = (query.get("search", [""])[0] or "").strip().lower()
        direction_filter = (query.get("direction", [""])[0] or query.get("topic", [""])[0] or "").strip()

        user = self.get_current_user()
        user_subs = set()
        user_exceptions = set()
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            if user:
                cur.execute("SELECT target_type, target_id FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                user_subs = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}
                cur.execute("SELECT target_type, target_id FROM user_feed_exceptions WHERE user_id = ?", (user["id"],))
                user_exceptions = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}

            cur.execute("SELECT * FROM clubs ORDER BY created_at ASC")
            club_rows = cur.fetchall()

            cur.execute("SELECT publication_settings FROM moderation_submissions WHERE status = 'approved'")
            article_counts = {}
            for r in cur.fetchall():
                try:
                    s = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                    cid = s.get("clubId")
                    if cid:
                        article_counts[cid] = article_counts.get(cid, 0) + 1
                except Exception:
                    pass

            cur.execute("SELECT target_id, COUNT(*) AS cnt FROM user_subscriptions WHERE target_type = 'club' GROUP BY target_id")
            sub_counts = {r["target_id"]: r["cnt"] for r in cur.fetchall()}

        clubs_list = []
        for r in club_rows:
            cid = r["id"]
            title = r["title"]
            desc = r["description"]
            rules = r["rules"]
            directions = json.loads(r["directions"]) if r["directions"] else []
            tags = json.loads(r["tags"]) if r["tags"] else []

            if direction_filter and direction_filter != "all":
                if direction_filter not in directions:
                    continue

            if search_query:
                haystack = f"{title} {desc} {rules or ''} {' '.join(tags)}".lower()
                if not all(w in haystack for w in search_query.split()):
                    continue

            clubs_list.append({
                "id": cid,
                "title": title,
                "description": desc,
                "avatar": r["avatar"],
                "rules": rules,
                "ownerId": r["owner_id"],
                "directions": directions,
                "tags": tags,
                "articlesCount": article_counts.get(cid, 0),
                "subscribersCount": sub_counts.get(cid, 0),
                "isSubscribed": ("club", cid) in user_subs,
                "isExcluded": ("club", cid) in user_exceptions,
                "createdAt": r["created_at"],
                "updatedAt": r["updated_at"]
            })

        self.send_json_response(200, {
            "success": True,
            "clubs": clubs_list,
            "total": len(clubs_list)
        })

    def handle_get_club_detail(self, club_id: str):
        """GET /api/clubs/<id> returns detail for a single club."""
        user = self.get_current_user()
        user_subs = set()
        user_exceptions = set()
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            if user:
                cur.execute("SELECT target_type, target_id FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                user_subs = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}
                cur.execute("SELECT target_type, target_id FROM user_feed_exceptions WHERE user_id = ?", (user["id"],))
                user_exceptions = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}

            cur.execute("SELECT * FROM clubs WHERE id = ?", (club_id,))
            row = cur.fetchone()
            if not row:
                self.send_json_response(404, {"success": False, "error": f"Клуб '{club_id}' не найден"})
                return

            cur.execute("SELECT COUNT(*) AS cnt FROM user_subscriptions WHERE target_type = 'club' AND target_id = ?", (club_id,))
            sub_count = cur.fetchone()["cnt"]

            cur.execute("SELECT publication_settings FROM moderation_submissions WHERE status = 'approved'")
            art_cnt = 0
            for r in cur.fetchall():
                try:
                    s = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                    if s.get("clubId") == club_id:
                        art_cnt += 1
                except Exception:
                    pass

        directions = json.loads(row["directions"]) if row["directions"] else []
        tags = json.loads(row["tags"]) if row["tags"] else []

        club_data = {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "avatar": row["avatar"],
            "rules": row["rules"],
            "ownerId": row["owner_id"],
            "directions": directions,
            "tags": tags,
            "articlesCount": art_cnt,
            "subscribersCount": sub_count,
            "isSubscribed": ("club", club_id) in user_subs,
            "isExcluded": ("club", club_id) in user_exceptions,
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"]
        }

        self.send_json_response(200, {
            "success": True,
            "club": club_data
        })

    def handle_post_club(self):
        """POST /api/clubs creates a new club with current user as owner."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if data is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Unauthorized", "requireAuth": True})
            return

        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()
        if not title:
            self.send_json_response(400, {"success": False, "error": "Название клуба обязательно"})
            return
        if not description:
            self.send_json_response(400, {"success": False, "error": "Описание клуба обязательно"})
            return

        rules = (data.get("rules") or "").strip()
        avatar = data.get("avatar")
        directions = data.get("directions") or []
        tags = data.get("tags") or []
        if isinstance(directions, str):
            directions = [d.strip() for d in directions.split(",") if d.strip()]
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        club_id = slugify(title)
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM clubs WHERE id = ?", (club_id,))
            if cur.fetchone():
                club_id = f"{club_id}-{uuid.uuid4().hex[:4]}"

            conn.execute("""
                INSERT INTO clubs (id, title, description, avatar, rules, owner_id, directions, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                club_id, title, description, avatar, rules, user["id"],
                json.dumps(directions, ensure_ascii=False),
                json.dumps(tags, ensure_ascii=False),
                now_str, now_str
            ))

            conn.execute("""
                INSERT OR IGNORE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                VALUES (?, 'club', ?, ?, ?)
            """, (user["id"], club_id, title, now_str))

        self.send_json_response(201, {
            "success": True,
            "club": {
                "id": club_id,
                "title": title,
                "description": description,
                "avatar": avatar,
                "rules": rules,
                "ownerId": user["id"],
                "directions": directions,
                "tags": tags,
                "articlesCount": 0,
                "subscribersCount": 1,
                "isSubscribed": True,
                "createdAt": now_str
            }
        })

    def handle_get_companies(self, parsed_url):
        """GET /api/companies returns catalog of corporate blogs."""
        query = urllib.parse.parse_qs(parsed_url.query)
        search_query = (query.get("search", [""])[0] or "").strip().lower()
        direction_filter = (query.get("direction", [""])[0] or query.get("topic", [""])[0] or "").strip()
        topics_filter_raw = (query.get("topics", [""])[0] or "").strip()
        topics_list = [t.strip() for t in topics_filter_raw.split(",") if t.strip()] if topics_filter_raw else []
        if direction_filter and direction_filter != "all" and direction_filter not in topics_list:
            topics_list.append(direction_filter)

        sort_param = (query.get("sort", ["popular"])[0] or "popular").strip().lower()
        manageable_param = (query.get("manageable", ["0"])[0] or "").strip().lower()
        mine_param = (query.get("mine", ["0"])[0] or "").strip().lower()
        only_manageable = manageable_param in ("1", "true", "yes") or mine_param in ("1", "true", "yes")

        user = self.get_current_user()
        user_subs = set()
        user_exceptions = set()
        comps_list = []
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            if user:
                cur.execute("SELECT target_type, target_id FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                user_subs = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}
                cur.execute("SELECT target_type, target_id FROM user_feed_exceptions WHERE user_id = ?", (user["id"],))
                user_exceptions = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}

            cur.execute("SELECT * FROM companies ORDER BY created_at ASC")
            comp_rows = cur.fetchall()

            cur.execute("SELECT id, draft_id, publication_settings FROM moderation_submissions WHERE status = 'approved'")
            comp_canonical_articles = {}
            article_counts = {}
            for r in cur.fetchall():
                try:
                    s = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                    cid = s.get("companyId")
                    if cid:
                        article_counts[cid] = article_counts.get(cid, 0) + 1
                        if cid not in comp_canonical_articles:
                            comp_canonical_articles[cid] = []
                        canonical_id = r["id"]
                        aliases = {canonical_id}
                        if r["draft_id"]:
                            aliases.add(r["draft_id"])
                        comp_canonical_articles[cid].append(aliases)
                except Exception:
                    pass

            cur.execute("SELECT article_id, COALESCE(SUM(value), 0) AS vote_sum FROM article_votes GROUP BY article_id")
            vote_map = {r["article_id"]: r["vote_sum"] for r in cur.fetchall()}

            cur.execute("SELECT article_id, COUNT(*) AS comment_cnt FROM article_comments WHERE status != 'deleted' GROUP BY article_id")
            comment_map = {r["article_id"]: r["comment_cnt"] for r in cur.fetchall()}

            cur.execute("SELECT target_id, COUNT(*) AS cnt FROM user_subscriptions WHERE target_type = 'company' GROUP BY target_id")
            sub_counts = {r["target_id"]: r["cnt"] for r in cur.fetchall()}

            for r in comp_rows:
                cid = r["id"]
                name = r["name"]
                desc = r["description"]
                spec = r["specialization"]
                website = r["website"]
                directions = json.loads(r["directions"]) if r["directions"] else []

                can_publish = False
                if user:
                    can_publish = can_user_publish_for_company(
                        conn, user["id"], cid, user_role=user.get("role", "user")
                    )

                if only_manageable and not can_publish:
                    continue

                if topics_list:
                    if not any(t in directions for t in topics_list):
                        continue

                if search_query:
                    haystack = f"{name} {desc} {spec} {website or ''}".lower()
                    if not all(w in haystack for w in search_query.split()):
                        continue

                c_rating = 0
                c_comments = 0
                for aliases in comp_canonical_articles.get(cid, []):
                    c_rating += sum(vote_map.get(aid, 0) for aid in aliases)
                    c_comments += sum(comment_map.get(aid, 0) for aid in aliases)

                comps_list.append({
                    "id": cid,
                    "name": name,
                    "description": desc,
                    "specialization": spec,
                    "website": website,
                    "logo": r["logo"],
                    "directions": directions,
                    "ownerId": r["owner_id"],
                    "isVerified": bool(r["is_verified"]),
                    "articlesCount": article_counts.get(cid, 0),
                    "subscribersCount": sub_counts.get(cid, 0),
                    "rating": c_rating,
                    "commentsCount": c_comments,
                    "isSubscribed": ("company", cid) in user_subs,
                    "isExcluded": ("company", cid) in user_exceptions,
                    "canPublish": can_publish,
                    "createdAt": r["created_at"],
                    "updatedAt": r["updated_at"]
                })

        if sort_param == "newest":
            comps_list.sort(key=lambda c: c["createdAt"], reverse=True)
        elif sort_param == "oldest":
            comps_list.sort(key=lambda c: c["createdAt"])
        elif sort_param == "rating":
            comps_list.sort(key=lambda c: (c["rating"], c["subscribersCount"], c["articlesCount"], c["createdAt"]), reverse=True)
        elif sort_param == "discussed":
            comps_list.sort(key=lambda c: (c["commentsCount"], c["subscribersCount"], c["articlesCount"], c["createdAt"]), reverse=True)
        else: # "popular" or default
            comps_list.sort(key=lambda c: (c["subscribersCount"], c["rating"], c["articlesCount"], c["createdAt"]), reverse=True)

        self.send_json_response(200, {
            "success": True,
            "companies": comps_list,
            "total": len(comps_list)
        })

    def handle_get_company_detail(self, company_id: str):
        """GET /api/companies/<id> returns detail for a single company."""
        user = self.get_current_user()
        user_subs = set()
        user_exceptions = set()
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            if user:
                cur.execute("SELECT target_type, target_id FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                user_subs = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}
                cur.execute("SELECT target_type, target_id FROM user_feed_exceptions WHERE user_id = ?", (user["id"],))
                user_exceptions = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}

            cur.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
            row = cur.fetchone()
            if not row:
                self.send_json_response(404, {"success": False, "error": f"Компания '{company_id}' не найдена"})
                return

            cur.execute("SELECT COUNT(*) AS cnt FROM user_subscriptions WHERE target_type = 'company' AND target_id = ?", (company_id,))
            sub_count = cur.fetchone()["cnt"]

            cur.execute("SELECT id, draft_id, publication_settings FROM moderation_submissions WHERE status = 'approved'")
            art_cnt = 0
            company_arts = set()
            for r in cur.fetchall():
                try:
                    s = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                    if s.get("companyId") == company_id:
                        art_cnt += 1
                        company_arts.add(r["id"])
                        if r["draft_id"]:
                            company_arts.add(r["draft_id"])
                except Exception:
                    pass

            c_rating = 0
            c_comments = 0
            if company_arts:
                placeholders = ",".join(["?"] * len(company_arts))
                cur.execute(f"SELECT COALESCE(SUM(value), 0) AS vote_sum FROM article_votes WHERE article_id IN ({placeholders})", list(company_arts))
                vrow = cur.fetchone()
                if vrow and vrow["vote_sum"] is not None:
                    c_rating = vrow["vote_sum"]
                cur.execute(f"SELECT COUNT(*) AS comment_cnt FROM article_comments WHERE status != 'deleted' AND article_id IN ({placeholders})", list(company_arts))
                crow = cur.fetchone()
                if crow and crow["comment_cnt"] is not None:
                    c_comments = crow["comment_cnt"]

            can_publish = False
            if user:
                can_publish = can_user_publish_for_company(
                    conn, user["id"], company_id, user_role=user.get("role", "user")
                )

        directions = json.loads(row["directions"]) if row["directions"] else []

        comp_data = {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "specialization": row["specialization"],
            "website": row["website"],
            "logo": row["logo"],
            "directions": directions,
            "ownerId": row["owner_id"],
            "isVerified": bool(row["is_verified"]),
            "articlesCount": art_cnt,
            "subscribersCount": sub_count,
            "rating": c_rating,
            "commentsCount": c_comments,
            "isSubscribed": ("company", company_id) in user_subs,
            "isExcluded": ("company", company_id) in user_exceptions,
            "canPublish": can_publish,
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"]
        }

        self.send_json_response(200, {
            "success": True,
            "company": comp_data
        })

    def handle_post_company(self):
        """POST /api/companies creates a new company profile with current user as owner."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if data is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Unauthorized", "requireAuth": True})
            return

        name = (data.get("name") or "").strip()
        description = (data.get("description") or "").strip()
        specialization = (data.get("specialization") or "").strip()
        if not name:
            self.send_json_response(400, {"success": False, "error": "Название компании обязательно"})
            return
        if not description:
            self.send_json_response(400, {"success": False, "error": "Описание компании обязательно"})
            return
        if not specialization:
            self.send_json_response(400, {"success": False, "error": "Специализация компании обязательна"})
            return

        website = (data.get("website") or "").strip()
        logo = data.get("logo")
        directions = data.get("directions") or []
        if isinstance(directions, str):
            directions = [d.strip() for d in directions.split(",") if d.strip()]

        company_id = slugify(name)
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM companies WHERE id = ?", (company_id,))
            if cur.fetchone():
                company_id = f"{company_id}-{uuid.uuid4().hex[:4]}"

            conn.execute("""
                INSERT INTO companies (id, name, description, specialization, website, logo, directions, owner_id, is_verified, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """, (
                company_id, name, description, specialization, website, logo,
                json.dumps(directions, ensure_ascii=False),
                user["id"], now_str, now_str
            ))

            conn.execute("""
                INSERT OR REPLACE INTO company_members (company_id, user_id, role, created_at)
                VALUES (?, ?, 'owner', ?)
            """, (company_id, user["id"], now_str))

            conn.execute("""
                INSERT OR IGNORE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                VALUES (?, 'company', ?, ?, ?)
            """, (user["id"], company_id, name, now_str))

        self.send_json_response(201, {
            "success": True,
            "company": {
                "id": company_id,
                "name": name,
                "description": description,
                "specialization": specialization,
                "website": website,
                "logo": logo,
                "directions": directions,
                "ownerId": user["id"],
                "isVerified": False,
                "articlesCount": 0,
                "subscribersCount": 1,
                "isSubscribed": True,
                "canPublish": True,
                "createdAt": now_str
            }
        })

    handle_create_company = handle_post_company

    def handle_get_directions(self, parsed_url):
        """GET /api/directions returns catalog of all standard directions / topics."""
        query = urllib.parse.parse_qs(parsed_url.query)
        search_query = (query.get("search", [""])[0] or "").strip().lower()

        import seed_data
        desc_map = seed_data.TOPICS_DESCRIPTION_MAP

        user = self.get_current_user()
        user_subs = set()
        user_exceptions = set()
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            if user:
                cur.execute("SELECT target_type, target_id FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                user_subs = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}
                cur.execute("SELECT target_type, target_id FROM user_feed_exceptions WHERE user_id = ?", (user["id"],))
                user_exceptions = {(r["target_type"], r["target_id"]) for r in cur.fetchall()}

            cur.execute("SELECT publication_settings FROM moderation_submissions WHERE status = 'approved'")
            topic_article_counts = {}
            for r in cur.fetchall():
                try:
                    s = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                    for t in s.get("topics") or []:
                        topic_article_counts[t] = topic_article_counts.get(t, 0) + 1
                except Exception:
                    pass

            cur.execute("SELECT target_id, COUNT(*) AS cnt FROM user_subscriptions WHERE target_type = 'topic' GROUP BY target_id")
            topic_sub_counts = {r["target_id"]: r["cnt"] for r in cur.fetchall()}

        directions_list = []
        for tid, ttitle in STANDARD_TOPICS:
            tdesc = desc_map.get(tid, f"Направление «{ttitle}» в экосистеме смарт-контрактов")
            if search_query:
                haystack = f"{tid} {ttitle} {tdesc}".lower()
                if not all(w in haystack for w in search_query.split()):
                    continue

            directions_list.append({
                "id": tid,
                "title": ttitle,
                "description": tdesc,
                "articlesCount": topic_article_counts.get(tid, 0),
                "count": topic_article_counts.get(tid, 0),
                "subscribersCount": topic_sub_counts.get(tid, 0),
                "isSubscribed": ("topic", tid) in user_subs,
                "isExcluded": ("topic", tid) in user_exceptions
            })

        self.send_json_response(200, {
            "success": True,
            "directions": directions_list,
            "total": len(directions_list)
        })

    def handle_get_feed_settings(self):
        """
        GET /api/user/feed-settings
        Returns feed settings for authenticated user, or default settings for guests.
        """
        user = self.get_current_user()
        default_material_types = ["article", "post", "news", "question"]
        default_complexity_levels = ["all"]

        if not user:
            self.send_json_response(200, {
                "success": True,
                "settings": {
                    "materialTypes": default_material_types,
                    "complexityLevels": default_complexity_levels,
                    "welcomeDismissed": False
                },
                "materialTypes": default_material_types,
                "complexityLevels": default_complexity_levels,
                "welcomeDismissed": False
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT material_types, complexity_levels, welcome_dismissed FROM user_feed_settings WHERE user_id = ?",
                (user["id"],)
            )
            row = cur.fetchone()

        is_welcome_dismissed = False
        if row:
            try:
                m_types = json.loads(row["material_types"])
            except Exception:
                m_types = default_material_types
            try:
                c_levels = json.loads(row["complexity_levels"])
            except Exception:
                c_levels = default_complexity_levels
            if "welcome_dismissed" in row.keys() and row["welcome_dismissed"]:
                is_welcome_dismissed = bool(row["welcome_dismissed"])
        else:
            m_types = default_material_types
            c_levels = default_complexity_levels

        self.send_json_response(200, {
            "success": True,
            "settings": {
                "materialTypes": m_types,
                "complexityLevels": c_levels,
                "welcomeDismissed": is_welcome_dismissed
            },
            "materialTypes": m_types,
            "complexityLevels": c_levels,
            "welcomeDismissed": is_welcome_dismissed
        })

    def handle_post_feed_settings(self):
        """
        POST /api/user/feed-settings
        Saves user feed settings for authenticated user.
        Body: { "materialTypes": [...], "complexityLevels": [...], "welcomeDismissed": bool }
        Returns 401 if unauthenticated.
        Returns 400 if materialTypes is empty ("Выберите хотя бы один тип материала").
        """
        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для сохранения настроек ленты необходимо войти",
                "requireAuth": True
            })
            return

        settings_obj = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload

        # Check for welcome dismissal toggle
        welcome_dismissed = None
        if "welcomeDismissed" in settings_obj:
            welcome_dismissed = 1 if settings_obj["welcomeDismissed"] else 0
        elif "welcome_dismissed" in settings_obj:
            welcome_dismissed = 1 if settings_obj["welcome_dismissed"] else 0

        material_types = settings_obj.get("materialTypes")
        if material_types is None:
            material_types = settings_obj.get("material_types")

        # If this is ONLY a welcomeDismissed toggle without materialTypes:
        if material_types is None and welcome_dismissed is not None:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn = self.get_db()
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT material_types, complexity_levels FROM user_feed_settings WHERE user_id = ?", (user["id"],))
                existing = cur.fetchone()
                if existing:
                    cur.execute("UPDATE user_feed_settings SET welcome_dismissed = ?, updated_at = ? WHERE user_id = ?", (welcome_dismissed, now_iso, user["id"]))
                else:
                    cur.execute(
                        "INSERT INTO user_feed_settings (user_id, material_types, complexity_levels, welcome_dismissed, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (user["id"], json.dumps(["article", "post", "news", "question"]), json.dumps(["all"]), welcome_dismissed, now_iso)
                    )
            self.send_json_response(200, {
                "success": True,
                "welcomeDismissed": bool(welcome_dismissed)
            })
            return

        if material_types is None or not isinstance(material_types, list):
            self.send_json_response(400, {
                "success": False,
                "error": "Выберите хотя бы один тип материала"
            })
            return

        valid_types = []
        for t in material_types:
            if isinstance(t, str):
                norm_t = t.strip().lower()
                if norm_t in LEGACY_MATERIAL_TYPES:
                    norm_t = LEGACY_MATERIAL_TYPES[norm_t]
                if norm_t in VALID_MATERIAL_TYPES and norm_t not in valid_types:
                    valid_types.append(norm_t)

        if not valid_types:
            self.send_json_response(400, {
                "success": False,
                "error": "Выберите хотя бы один тип материала"
            })
            return

        complexity_levels = settings_obj.get("complexityLevels")
        if complexity_levels is None:
            complexity_levels = settings_obj.get("complexity_levels")

        if complexity_levels is None or not isinstance(complexity_levels, list) or len(complexity_levels) == 0:
            clean_levels = ["all"]
        else:
            clean_levels = []
            for c in complexity_levels:
                if isinstance(c, str) and c.strip():
                    clean_levels.append(c.strip().lower())
            if not clean_levels:
                clean_levels = ["all"]

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT welcome_dismissed FROM user_feed_settings WHERE user_id = ?", (user["id"],))
            ex_row = cur.fetchone()
            curr_wel = ex_row["welcome_dismissed"] if (ex_row and "welcome_dismissed" in ex_row.keys()) else 0
            if welcome_dismissed is not None:
                curr_wel = welcome_dismissed

            conn.execute("""
                INSERT INTO user_feed_settings (user_id, material_types, complexity_levels, welcome_dismissed, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    material_types = excluded.material_types,
                    complexity_levels = excluded.complexity_levels,
                    welcome_dismissed = excluded.welcome_dismissed,
                    updated_at = excluded.updated_at
            """, (
                user["id"],
                json.dumps(valid_types, ensure_ascii=False),
                json.dumps(clean_levels, ensure_ascii=False),
                curr_wel,
                now_iso
            ))

        # Optional batch update for subscriptions
        if "subscriptions" in settings_obj:
            batch_subs = settings_obj["subscriptions"]
            now_iso_sub = datetime.datetime.now(datetime.timezone.utc).isoformat()
            items_to_add = []
            if isinstance(batch_subs, dict):
                for stype in ("author", "topic", "tag"):
                    sub_list = batch_subs.get(f"{stype}s") or batch_subs.get(stype) or []
                    if isinstance(sub_list, list):
                        for s in sub_list:
                            sid = s.get("id") if isinstance(s, dict) else str(s)
                            stitle = (s.get("title") or sid) if isinstance(s, dict) else sid
                            if stype == "tag":
                                sid = normalize_keyword(sid).lstrip('#').strip().lower()
                                stitle = normalize_keyword(stitle).lstrip('#').strip()
                            if sid:
                                items_to_add.append((user["id"], stype, sid, stitle, now_iso_sub))
            elif isinstance(batch_subs, list):
                for s in batch_subs:
                    if isinstance(s, dict):
                        stype = (s.get("targetType") or s.get("type") or "").strip().lower()
                        sid = (s.get("targetId") or s.get("id") or "").strip()
                        stitle = (s.get("targetTitle") or s.get("title") or sid).strip()
                        if stype in ("author", "topic", "tag") and sid:
                            if stype == "tag":
                                sid = normalize_keyword(sid).lstrip('#').strip().lower()
                                stitle = normalize_keyword(stitle).lstrip('#').strip()
                            items_to_add.append((user["id"], stype, sid, stitle, now_iso_sub))

            with conn:
                conn.execute("DELETE FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                if items_to_add:
                    conn.executemany("""
                        INSERT OR REPLACE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, items_to_add)
                    for item in items_to_add:
                        conn.execute("DELETE FROM user_feed_exceptions WHERE user_id = ? AND target_type = ? AND target_id = ?",
                                     (item[0], item[1], item[2]))

        # Optional batch update for exceptions
        if "exceptions" in settings_obj:
            batch_exc = settings_obj["exceptions"]
            now_iso_exc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            exc_to_add = []
            if isinstance(batch_exc, dict):
                for etype in ("author", "topic", "tag"):
                    exc_list = batch_exc.get(f"{etype}s") or batch_exc.get(etype) or []
                    if isinstance(exc_list, list):
                        for e in exc_list:
                            eid = e.get("id") if isinstance(e, dict) else str(e)
                            etitle = (e.get("title") or eid) if isinstance(e, dict) else eid
                            if etype == "tag":
                                eid = normalize_keyword(eid).lstrip('#').strip().lower()
                                etitle = normalize_keyword(etitle).lstrip('#').strip()
                            if eid:
                                exc_to_add.append((user["id"], etype, eid, etitle, now_iso_exc))
            elif isinstance(batch_exc, list):
                for e in batch_exc:
                    if isinstance(e, dict):
                        etype = (e.get("targetType") or e.get("type") or "").strip().lower()
                        eid = (e.get("targetId") or e.get("id") or "").strip()
                        etitle = (e.get("targetTitle") or e.get("title") or eid).strip()
                        if etype in ("author", "topic", "tag") and eid:
                            if etype == "tag":
                                eid = normalize_keyword(eid).lstrip('#').strip().lower()
                                etitle = normalize_keyword(etitle).lstrip('#').strip()
                            exc_to_add.append((user["id"], etype, eid, etitle, now_iso_exc))

            with conn:
                conn.execute("DELETE FROM user_feed_exceptions WHERE user_id = ?", (user["id"],))
                if exc_to_add:
                    conn.executemany("""
                        INSERT OR REPLACE INTO user_feed_exceptions (user_id, target_type, target_id, target_title, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, exc_to_add)
                    for item in exc_to_add:
                        conn.execute("DELETE FROM user_subscriptions WHERE user_id = ? AND target_type = ? AND target_id = ?",
                                     (item[0], item[1], item[2]))

        self.send_json_response(200, {
            "success": True,
            "settings": {
                "materialTypes": valid_types,
                "complexityLevels": clean_levels
            },
            "materialTypes": valid_types,
            "complexityLevels": clean_levels
        })

    def handle_article_like_toggle(self, article_id: str = "", _body_already_read: bool = False):
        """
        POST /api/articles/<id>/like or POST /api/likes/toggle
        Toggles like for current user on the given article.
        Requires authentication (401 requireAuth).
        Returns { success: True, hasLiked: bool, likesCount: int }.
        """
        if not _body_already_read:
            payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
            if payload is None:
                return
            if not article_id:
                article_id = payload.get("articleId") or payload.get("article_id") or ""

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для отметки «Нравится» необходимо войти",
                "requireAuth": True
            })
            return

        if not article_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор статьи"
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (article_id, article_id))
            art_row = cur.fetchone()
            if not art_row:
                self.send_json_response(404, {
                    "success": False,
                    "error": "Статья не найдена"
                })
                return

            real_art_id = art_row["id"]
            user_id = user["id"]

            cur.execute("SELECT id FROM article_likes WHERE article_id = ? AND user_id = ?", (real_art_id, user_id))
            existing_like = cur.fetchone()

            if existing_like:
                cur.execute("DELETE FROM article_likes WHERE article_id = ? AND user_id = ?", (real_art_id, user_id))
                has_liked = False
            else:
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cur.execute(
                    "INSERT INTO article_likes (article_id, user_id, created_at) VALUES (?, ?, ?)",
                    (real_art_id, user_id, now_iso)
                )
                has_liked = True

            cur.execute("SELECT COUNT(*) AS cnt FROM article_likes WHERE article_id = ?", (real_art_id,))
            likes_count = cur.fetchone()["cnt"]

        self.send_json_response(200, {
            "success": True,
            "hasLiked": has_liked,
            "isLiked": has_liked,
            "likesCount": likes_count,
            "articleId": real_art_id
        })

    def handle_article_save_toggle(self, article_id: str = "", action: str = "toggle", _body_already_read: bool = False):
        """
        POST /api/articles/<id>/save, POST /api/articles/<id>/unsave, POST /api/articles/<id>/bookmark, POST /api/saves/toggle
        Saves or unsaves an article for the current authenticated user.
        action can be 'save', 'unsave', or 'toggle'.
        Requires authentication (returns 401 with requireAuth: True if not logged in).
        Returns { success: True, isSaved: bool, hasSaved: bool, savesCount: int, articleId: str }.
        """
        if not _body_already_read:
            payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
            if payload is None:
                return
            if not article_id:
                article_id = payload.get("articleId") or payload.get("article_id") or ""
            if "action" in payload and payload["action"] in ("save", "unsave", "toggle"):
                action = payload["action"]

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для сохранения публикации необходимо войти",
                "requireAuth": True,
                "code": "AUTH_REQUIRED"
            })
            return

        if not article_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор статьи",
                "code": "INVALID_ARTICLE_ID"
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (article_id, article_id))
            art_row = cur.fetchone()
            if not art_row:
                self.send_json_response(404, {
                    "success": False,
                    "error": "Статья не найдена",
                    "code": "ARTICLE_NOT_FOUND"
                })
                return

            real_art_id = art_row["id"]
            user_id = user["id"]

            cur.execute("SELECT id FROM article_saves WHERE article_id = ? AND user_id = ?", (real_art_id, user_id))
            existing_save = cur.fetchone()

            if action == "save":
                if not existing_save:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute(
                        "INSERT OR IGNORE INTO article_saves (article_id, user_id, created_at) VALUES (?, ?, ?)",
                        (real_art_id, user_id, now_iso)
                    )
                is_saved = True
            elif action == "unsave":
                if existing_save:
                    cur.execute("DELETE FROM article_saves WHERE article_id = ? AND user_id = ?", (real_art_id, user_id))
                is_saved = False
            else:  # toggle
                if existing_save:
                    cur.execute("DELETE FROM article_saves WHERE article_id = ? AND user_id = ?", (real_art_id, user_id))
                    is_saved = False
                else:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute(
                        "INSERT OR IGNORE INTO article_saves (article_id, user_id, created_at) VALUES (?, ?, ?)",
                        (real_art_id, user_id, now_iso)
                    )
                    is_saved = True

            cur.execute("SELECT COUNT(*) AS cnt FROM article_saves WHERE article_id = ?", (real_art_id,))
            saves_count = cur.fetchone()["cnt"]

        self.send_json_response(200, {
            "success": True,
            "isSaved": is_saved,
            "hasSaved": is_saved,
            "savesCount": saves_count,
            "articleId": real_art_id
        })

    def handle_sync_saves(self):
        """
        POST /api/articles/sync-saves
        Idempotently migrates client bookmarks (from localStorage sc_bookmarks) to server.
        Requires authentication.
        Expects { "articleIds": ["art-1", "art-2", ...] } or list of strings.
        Returns { "success": True, "syncedCount": int, "totalSaved": int }.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для синхронизации закладок необходимо войти",
                "requireAuth": True,
                "code": "AUTH_REQUIRED"
            })
            return

        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        raw_ids = []
        if isinstance(payload, list):
            raw_ids = payload
        elif isinstance(payload, dict):
            raw_ids = payload.get("articleIds") or payload.get("ids") or payload.get("bookmarks") or []

        if not isinstance(raw_ids, list):
            self.send_json_response(400, {
                "success": False,
                "error": "Неверный формат списка статей",
                "code": "INVALID_ARTICLE_IDS"
            })
            return

        user_id = user["id"]
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        synced = 0

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            for raw_id in raw_ids:
                if not isinstance(raw_id, str) or not raw_id.strip():
                    continue
                aid = raw_id.strip()
                cur.execute("SELECT id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (aid, aid))
                row = cur.fetchone()
                if row:
                    real_id = row["id"]
                    cur.execute(
                        "INSERT OR IGNORE INTO article_saves (article_id, user_id, created_at) VALUES (?, ?, ?)",
                        (real_id, user_id, now_iso)
                    )
                    if cur.rowcount > 0:
                        synced += 1

            cur.execute("SELECT COUNT(*) AS cnt FROM article_saves WHERE user_id = ?", (user_id,))
            total_saved = cur.fetchone()["cnt"]

        self.send_json_response(200, {
            "success": True,
            "syncedCount": synced,
            "totalSaved": total_saved
        })

    def handle_comment_save_toggle(self, comment_id: str = "", action: str = "toggle", _body_already_read: bool = False):
        """
        POST /api/comments/<id>/save, POST /api/comments/<id>/unsave, POST /api/comments/<id>/bookmark
        Toggles, saves or unsaves a comment for the current authenticated user.
        """
        if not _body_already_read:
            payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
            if payload is None:
                return
            if not comment_id:
                comment_id = payload.get("commentId") or payload.get("comment_id") or ""
            if "action" in payload and payload["action"] in ("save", "unsave", "toggle"):
                action = payload["action"]

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для сохранения комментария необходимо войти",
                "requireAuth": True,
                "code": "AUTH_REQUIRED"
            })
            return

        if not comment_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор комментария",
                "code": "INVALID_COMMENT_ID"
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id, article_id FROM article_comments WHERE id = ? LIMIT 1", (comment_id,))
            comm_row = cur.fetchone()
            if not comm_row:
                self.send_json_response(404, {
                    "success": False,
                    "error": "Комментарий не найден",
                    "code": "COMMENT_NOT_FOUND"
                })
                return

            real_comm_id = comm_row["id"]
            user_id = user["id"]

            cur.execute("SELECT id FROM comment_saves WHERE comment_id = ? AND user_id = ?", (real_comm_id, user_id))
            existing_save = cur.fetchone()

            if action == "save":
                if not existing_save:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute(
                        "INSERT OR IGNORE INTO comment_saves (comment_id, user_id, created_at) VALUES (?, ?, ?)",
                        (real_comm_id, user_id, now_iso)
                    )
                is_saved = True
            elif action == "unsave":
                if existing_save:
                    cur.execute("DELETE FROM comment_saves WHERE comment_id = ? AND user_id = ?", (real_comm_id, user_id))
                is_saved = False
            else:
                if existing_save:
                    cur.execute("DELETE FROM comment_saves WHERE comment_id = ? AND user_id = ?", (real_comm_id, user_id))
                    is_saved = False
                else:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute(
                        "INSERT OR IGNORE INTO comment_saves (comment_id, user_id, created_at) VALUES (?, ?, ?)",
                        (real_comm_id, user_id, now_iso)
                    )
                    is_saved = True

            cur.execute("SELECT COUNT(*) AS cnt FROM comment_saves WHERE comment_id = ?", (real_comm_id,))
            saves_count = cur.fetchone()["cnt"]

        self.send_json_response(200, {
            "success": True,
            "commentId": real_comm_id,
            "isSaved": is_saved,
            "hasSaved": is_saved,
            "savesCount": saves_count
        })

    def handle_comment_saves_sync(self):
        """
        POST /api/comments/sync-saves
        Migrates client-side bookmark IDs into server comment_saves table for authenticated user.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для синхронизации закладок необходимо войти",
                "requireAuth": True
            })
            return

        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        comment_ids = payload.get("commentIds") or payload.get("ids") or []
        if not isinstance(comment_ids, list):
            self.send_json_response(400, {"success": False, "error": "commentIds must be a list"})
            return

        user_id = user["id"]
        synced = 0
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            for cid in comment_ids:
                if not isinstance(cid, str) or not cid.strip():
                    continue
                cid = cid.strip()
                cur.execute("SELECT id FROM article_comments WHERE id = ? LIMIT 1", (cid,))
                if cur.fetchone():
                    cur.execute(
                        "INSERT OR IGNORE INTO comment_saves (comment_id, user_id, created_at) VALUES (?, ?, ?)",
                        (cid, user_id, now_iso)
                    )
                    if cur.rowcount > 0:
                        synced += 1

            cur.execute("SELECT COUNT(*) AS cnt FROM comment_saves WHERE user_id = ?", (user_id,))
            total_saved = cur.fetchone()["cnt"]

        self.send_json_response(200, {
            "success": True,
            "syncedCount": synced,
            "totalSaved": total_saved
        })

    def handle_get_saved_comments(self):
        """
        GET /api/comments/saved
        Returns list of saved comments for current user.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(200, {"success": True, "items": [], "total": 0})
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT cs.comment_id, cs.created_at AS saved_at,
                       c.id, c.article_id, c.user_id AS author_id, c.author_name, c.author_avatar,
                       c.content AS text, c.created_at, c.comment_type,
                       m.title AS article_title,
                       (SELECT COUNT(*) FROM comment_saves cs2 WHERE cs2.comment_id = c.id) AS saves_count
                FROM comment_saves cs
                JOIN article_comments c ON cs.comment_id = c.id
                LEFT JOIN moderation_submissions m ON (c.article_id = m.id OR c.article_id = m.draft_id)
                WHERE cs.user_id = ? AND c.status = 'published'
                ORDER BY cs.created_at DESC
            """, (user["id"],))
            rows = cur.fetchall()

        items = []
        for r in rows:
            art_id = r["article_id"] or ""
            comm_id = r["id"] or ""
            items.append({
                "id": comm_id,
                "articleId": art_id,
                "articleTitle": r["article_title"] or "Материал сообщества",
                "permalink": f"article.html?id={art_id}#comment-{comm_id}",
                "authorId": r["author_id"],
                "authorName": r["author_name"],
                "authorAvatar": r["author_avatar"],
                "text": r["text"],
                "createdAt": r["created_at"],
                "commentType": r["comment_type"] or "comment",
                "isSaved": True,
                "hasSaved": True,
                "savesCount": r["saves_count"] or 1
            })

        self.send_json_response(200, {
            "success": True,
            "items": items,
            "total": len(items)
        })

    def handle_get_saved_counts(self):
        """
        GET /api/saved/counts
        Returns aggregated counts for Saved Hub without N+1 queries.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(200, {
                "success": True,
                "total": 0,
                "publications": 0,
                "questions": 0,
                "comments": 0
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                  (SELECT COUNT(DISTINCT s.article_id)
                   FROM article_saves s
                   JOIN moderation_submissions m ON (s.article_id = m.id OR s.article_id = m.draft_id)
                   WHERE s.user_id = ?
                     AND COALESCE(json_extract(m.publication_settings, '$.materialType'), json_extract(m.publication_settings, '$.type'), 'publication') != 'question'
                  ) as pubs_count,
                  (SELECT COUNT(DISTINCT s.article_id)
                   FROM article_saves s
                   JOIN moderation_submissions m ON (s.article_id = m.id OR s.article_id = m.draft_id)
                   WHERE s.user_id = ?
                     AND COALESCE(json_extract(m.publication_settings, '$.materialType'), json_extract(m.publication_settings, '$.type'), 'publication') = 'question'
                  ) as questions_count,
                  (SELECT COUNT(*) FROM comment_saves WHERE user_id = ?) as comments_count
            """, (user["id"], user["id"], user["id"]))
            row = cur.fetchone()
            pubs = row["pubs_count"] or 0
            questions = row["questions_count"] or 0
            comments = row["comments_count"] or 0
            total = pubs + questions + comments

        self.send_json_response(200, {
            "success": True,
            "total": total,
            "publications": pubs,
            "questions": questions,
            "comments": comments
        })

    def handle_get_saved(self, parsed_url):
        """
        GET /api/saved
        Unified Saved Hub endpoint returning saved materials and comments for current user.
        Query params:
          type: 'all' (default), 'publications', 'questions', 'comments'
          search: search string across title, description, content, author
          limit: int (default 20, max 100)
          offset: int (default 0)
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для просмотра сохраненных материалов необходимо войти",
                "requireAuth": True,
                "code": "AUTH_REQUIRED"
            })
            return

        query = urllib.parse.parse_qs(parsed_url.query)
        stype = (query.get("type", ["all"])[0] or "all").strip().lower()
        search_q = (query.get("search", [""])[0] or query.get("q", [""])[0] or "").strip().lower()
        try:
            limit = max(1, min(100, int(query.get("limit", [20])[0])))
        except ValueError:
            limit = 20
        try:
            offset = max(0, int(query.get("offset", [0])[0]))
        except ValueError:
            offset = 0

        user_id = user["id"]
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            # 1. Aggregated counts
            cur.execute("""
                SELECT
                  (SELECT COUNT(DISTINCT s.article_id)
                   FROM article_saves s
                   JOIN moderation_submissions m ON (s.article_id = m.id OR s.article_id = m.draft_id)
                   WHERE s.user_id = ?
                     AND COALESCE(json_extract(m.publication_settings, '$.materialType'), json_extract(m.publication_settings, '$.type'), 'publication') != 'question'
                  ) as pubs_count,
                  (SELECT COUNT(DISTINCT s.article_id)
                   FROM article_saves s
                   JOIN moderation_submissions m ON (s.article_id = m.id OR s.article_id = m.draft_id)
                   WHERE s.user_id = ?
                     AND COALESCE(json_extract(m.publication_settings, '$.materialType'), json_extract(m.publication_settings, '$.type'), 'publication') = 'question'
                  ) as questions_count,
                  (SELECT COUNT(*) FROM comment_saves WHERE user_id = ?) as comments_count
            """, (user_id, user_id, user_id))
            crow = cur.fetchone()
            pubs_cnt = crow["pubs_count"] or 0
            questions_cnt = crow["questions_count"] or 0
            comments_cnt = crow["comments_count"] or 0
            total_cnt = pubs_cnt + questions_cnt + comments_cnt
            counts = {
                "total": total_cnt,
                "publications": pubs_cnt,
                "questions": questions_cnt,
                "comments": comments_cnt
            }

            items = []
            # 2. Fetch comments if requested
            if stype in ("comments", "comment", "all"):
                cur.execute("""
                    SELECT cs.comment_id, cs.created_at AS saved_at,
                           c.id, c.article_id, c.user_id AS author_id, c.author_name, c.author_avatar,
                           c.content AS text, c.created_at, c.comment_type,
                           m.title AS article_title,
                           (SELECT COUNT(*) FROM comment_saves cs2 WHERE cs2.comment_id = c.id) AS saves_count
                    FROM comment_saves cs
                    JOIN article_comments c ON cs.comment_id = c.id
                    LEFT JOIN moderation_submissions m ON (c.article_id = m.id OR c.article_id = m.draft_id)
                    WHERE cs.user_id = ? AND c.status = 'published'
                    ORDER BY cs.created_at DESC
                """, (user_id,))
                crows = cur.fetchall()
                for cr in crows:
                    cid = cr["id"] or ""
                    aid = cr["article_id"] or ""
                    art_title = cr["article_title"] or "Материал сообщества"
                    text = cr["text"] or ""
                    aname = cr["author_name"] or "Пользователь"
                    if search_q:
                        if search_q not in text.lower() and search_q not in art_title.lower() and search_q not in aname.lower():
                            continue
                    items.append({
                        "id": cid,
                        "entityType": "comment",
                        "articleId": aid,
                        "articleTitle": art_title,
                        "permalink": f"article.html?id={aid}#comment-{cid}",
                        "authorId": cr["author_id"],
                        "authorName": aname,
                        "authorAvatar": cr["author_avatar"],
                        "text": text,
                        "createdAt": cr["created_at"],
                        "date": format_date_ru(cr["created_at"]),
                        "savedAt": cr["saved_at"],
                        "commentType": cr["comment_type"] or "comment",
                        "isSaved": True,
                        "hasSaved": True,
                        "savesCount": cr["saves_count"] or 1
                    })

            # 3. Fetch articles if requested
            if stype in ("publications", "publication", "questions", "question", "all"):
                cur.execute("""
                    SELECT s.article_id, s.created_at AS saved_at,
                           m.id, m.draft_id, m.title, m.author_id,
                           m.created_at, m.publication_settings,
                           (SELECT COUNT(*) FROM article_saves s2 WHERE s2.article_id = m.id OR s2.article_id = m.draft_id) AS saves_count
                    FROM article_saves s
                    JOIN moderation_submissions m ON (s.article_id = m.id OR s.article_id = m.draft_id)
                    WHERE s.user_id = ? AND m.status IN ('approved', 'published')
                    ORDER BY s.created_at DESC
                """, (user_id,))
                arows = cur.fetchall()
                for ar in arows:
                    aid = ar["id"] or ""
                    settings = {}
                    if ar["publication_settings"]:
                        try:
                            settings = json.loads(ar["publication_settings"])
                        except Exception:
                            settings = {}
                    raw_mat_type = (settings.get("materialType") or settings.get("type") or "publication").strip().lower()
                    if raw_mat_type in ("article", "post", "news", "pubs"):
                        mat_type = "publication"
                    else:
                        mat_type = raw_mat_type
                    is_question = (mat_type == "question")
                    if stype in ("questions", "question") and not is_question:
                        continue
                    if stype in ("publications", "publication") and is_question:
                        continue

                    title = ar["title"] or ""
                    desc = settings.get("description") or ""
                    raw_author = settings.get("author") or settings.get("authorName")
                    if isinstance(raw_author, dict):
                        author_name = raw_author.get("name") or "Пользователь"
                        author_avatar = raw_author.get("avatar") or settings.get("authorAvatar")
                    else:
                        author_name = raw_author or "Пользователь"
                        author_avatar = settings.get("authorAvatar")
                    cover_image = settings.get("coverImage")
                    if search_q:
                        if search_q not in title.lower() and search_q not in desc.lower() and search_q not in author_name.lower():
                            continue

                    topics = settings.get("topics") or ([settings["topic"]] if settings.get("topic") else [])
                    tags = settings.get("keywords") or settings.get("tags") or []
                    items.append({
                        "id": aid,
                        "entityType": "question" if is_question else "publication",
                        "title": title,
                        "description": desc,
                        "author": author_name,
                        "authorId": ar["author_id"],
                        "authorAvatar": author_avatar,
                        "cover": cover_image,
                        "date": format_date_ru(ar["created_at"]),
                        "createdAt": ar["created_at"],
                        "savedAt": ar["saved_at"],
                        "topics": topics,
                        "keywords": tags,
                        "tags": tags,
                        "format": settings.get("format") or ("question" if is_question else "article"),
                        "type": "question" if is_question else "article",
                        "materialType": "question" if is_question else "publication",
                        "complexity": settings.get("complexity") or "none",
                        "isSaved": True,
                        "hasSaved": True,
                        "savesCount": ar["saves_count"] or 1
                    })

            # Sort items by savedAt DESC
            items.sort(key=lambda x: x.get("savedAt") or "", reverse=True)
            total_items = len(items)
            paged_items = items[offset: offset + limit]

        self.send_json_response(200, {
            "success": True,
            "items": paged_items,
            "total": total_items,
            "counts": counts,
            "limit": limit,
            "offset": offset,
            "hasMore": (offset + limit) < total_items
        })

    def handle_article_vote(self, raw_id: str):
        """
        POST /api/articles/<id>/vote
        Registers or cancels vote (-1, 0, 1) for the specified article.
        Requires authenticated session (401 AUTH_REQUIRED).
        Prevents self-voting by the author (403 SELF_VOTE_FORBIDDEN).
        Resolves canonical article ID from id or draft_id.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация",
                "code": "AUTH_REQUIRED",
                "requireAuth": True
            })
            return

        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if payload is None:
            return

        if not isinstance(payload, dict) or "value" not in payload:
            self.send_json_response(400, {
                "success": False,
                "error": "Значение голоса должно быть -1, 0 или 1",
                "code": "INVALID_VOTE_VALUE"
            })
            return

        val = payload.get("value")
        if type(val) is not int or isinstance(val, bool) or val not in (-1, 0, 1):
            self.send_json_response(400, {
                "success": False,
                "error": "Значение голоса должно быть -1, 0 или 1",
                "code": "INVALID_VOTE_VALUE"
            })
            return

        if not raw_id:
            self.send_json_response(404, {
                "success": False,
                "error": "Публикация не найдена",
                "code": "NOT_FOUND"
            })
            return

        conn = self.get_db()
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, draft_id, author_id, status FROM moderation_submissions WHERE (id = ? OR draft_id = ?) LIMIT 1",
                    (raw_id, raw_id)
                )
                art_row = cur.fetchone()
                if not art_row or art_row["status"] != "approved":
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Публикация не найдена",
                        "code": "NOT_FOUND"
                    })
                    return

                canonical_id = art_row["id"]
                if art_row["author_id"] == user["id"]:
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Нельзя голосовать за собственную публикацию",
                        "code": "SELF_VOTE_FORBIDDEN"
                    })
                    return

                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                if val in (-1, 1):
                    cur.execute("""
                        INSERT INTO article_votes (article_id, user_id, value, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(article_id, user_id) DO UPDATE SET
                            value = excluded.value,
                            updated_at = excluded.updated_at
                    """, (canonical_id, user["id"], val, now_iso, now_iso))
                elif val == 0:
                    cur.execute(
                        "DELETE FROM article_votes WHERE article_id = ? AND user_id = ?",
                        (canonical_id, user["id"])
                    )

                cur.execute("SELECT COALESCE(SUM(value), 0) AS score FROM article_votes WHERE article_id = ?", (canonical_id,))
                score_row = cur.fetchone()
                score = score_row["score"] if score_row else 0
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "targetType": "article",
            "targetId": canonical_id,
            "score": score,
            "myVote": val,
            "canVote": True
        })

    def handle_comment_vote(self, comment_id: str):
        """
        POST /api/comments/<id>/vote
        Registers or cancels vote (-1, 0, 1) for the specified comment.
        Requires authenticated session (401 AUTH_REQUIRED).
        Prevents self-voting by the author (403 SELF_VOTE_FORBIDDEN).
        Validates comment existence, published status, and parent publication approval.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация",
                "code": "AUTH_REQUIRED",
                "requireAuth": True
            })
            return

        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if payload is None:
            return

        if not isinstance(payload, dict) or "value" not in payload:
            self.send_json_response(400, {
                "success": False,
                "error": "Значение голоса должно быть -1, 0 или 1",
                "code": "INVALID_VOTE_VALUE"
            })
            return

        val = payload.get("value")
        if type(val) is not int or isinstance(val, bool) or val not in (-1, 0, 1):
            self.send_json_response(400, {
                "success": False,
                "error": "Значение голоса должно быть -1, 0 или 1",
                "code": "INVALID_VOTE_VALUE"
            })
            return

        if not comment_id:
            comment_id = payload.get("commentId") or payload.get("comment_id") or ""

        if not comment_id:
            self.send_json_response(404, {
                "success": False,
                "error": "Комментарий не найден",
                "code": "NOT_FOUND"
            })
            return

        conn = self.get_db()
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                cur = conn.cursor()
                cur.execute("SELECT id, article_id, user_id, status FROM article_comments WHERE id = ?", (comment_id,))
                comment = cur.fetchone()
                if not comment:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Комментарий не найден",
                        "code": "NOT_FOUND"
                    })
                    return

                if comment["status"] == "deleted":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Нельзя голосовать за удаленный комментарий",
                        "code": "COMMENT_DELETED"
                    })
                    return

                if comment["status"] != "published":
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Комментарий не найден",
                        "code": "NOT_FOUND"
                    })
                    return

                parent_art_id = comment["article_id"]
                cur.execute(
                    "SELECT id, status FROM moderation_submissions WHERE (id = ? OR draft_id = ?) LIMIT 1",
                    (parent_art_id, parent_art_id)
                )
                art_row = cur.fetchone()
                if not art_row or art_row["status"] != "approved":
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Публикация не найдена",
                        "code": "NOT_FOUND"
                    })
                    return

                if comment["user_id"] == user["id"]:
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Нельзя голосовать за собственный комментарий",
                        "code": "SELF_VOTE_FORBIDDEN"
                    })
                    return

                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                if val in (-1, 1):
                    cur.execute("""
                        INSERT INTO comment_votes (comment_id, user_id, value, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(comment_id, user_id) DO UPDATE SET
                            value = excluded.value,
                            updated_at = excluded.updated_at
                    """, (comment_id, user["id"], val, now_iso, now_iso))
                elif val == 0:
                    cur.execute(
                        "DELETE FROM comment_votes WHERE comment_id = ? AND user_id = ?",
                        (comment_id, user["id"])
                    )

                cur.execute("SELECT COALESCE(SUM(value), 0) AS score FROM comment_votes WHERE comment_id = ?", (comment_id,))
                score_row = cur.fetchone()
                score = score_row["score"] if score_row else 0
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "targetType": "comment",
            "targetId": comment_id,
            "score": score,
            "myVote": val,
            "canVote": True
        })

    def handle_comment_report(self, comment_id: str):
        """
        POST /api/comments/<id>/report
        Submits a report against a comment or answer.
        Requires authentication (returns 401 if unauthorized).
        Validates reason (non-empty string, max length 200).
        Prevents author from reporting own comment (returns 403 CANNOT_REPORT_OWN_COMMENT).
        Prevents duplicate report from same user on same comment (returns 409 REPORT_ALREADY_EXISTS).
        Inserts into comment_reports and returns {"success": true, "message": "Жалоба отправлена"}.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация",
                "code": "AUTH_REQUIRED",
                "requireAuth": True
            })
            return

        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if payload is None:
            return

        if not isinstance(payload, dict):
            self.send_json_response(400, {
                "success": False,
                "error": "Неверный формат данных",
                "code": "INVALID_PAYLOAD"
            })
            return

        if not comment_id:
            comment_id = str(payload.get("commentId") or payload.get("comment_id") or "").strip()

        if not comment_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Идентификатор комментария обязателен",
                "code": "INVALID_COMMENT_ID"
            })
            return

        raw_reason = payload.get("reason")
        if not isinstance(raw_reason, str) or not raw_reason.strip():
            self.send_json_response(400, {
                "success": False,
                "error": "Причина жалобы обязательна",
                "code": "INVALID_REASON"
            })
            return

        reason = raw_reason.strip()
        if len(reason) > 200:
            self.send_json_response(400, {
                "success": False,
                "error": "Причина жалобы не должна превышать 200 символов",
                "code": "REASON_TOO_LONG"
            })
            return

        raw_details = payload.get("details", "")
        details = str(raw_details).strip() if raw_details is not None else ""
        if len(details) > 2000:
            details = details[:2000]

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT id, user_id, status FROM article_comments WHERE id = ?", (comment_id,))
                comment = cur.fetchone()
                if not comment:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Комментарий не найден",
                        "code": "NOT_FOUND"
                    })
                    return

                if comment["user_id"] == user["id"]:
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Нельзя пожаловаться на собственный комментарий",
                        "code": "CANNOT_REPORT_OWN_COMMENT"
                    })
                    return

                cur.execute(
                    "SELECT id FROM comment_reports WHERE comment_id = ? AND user_id = ?",
                    (comment_id, user["id"])
                )
                if cur.fetchone():
                    self.send_json_response(409, {
                        "success": False,
                        "error": "Вы уже отправили жалобу на этот комментарий",
                        "code": "REPORT_ALREADY_EXISTS"
                    })
                    return

                report_id = f"rep_{uuid.uuid4().hex[:12]}"
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cur.execute("""
                    INSERT INTO comment_reports (id, comment_id, user_id, reason, details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (report_id, comment_id, user["id"], reason, details, now_iso))
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "message": "Жалоба отправлена",
            "hasReported": True,
            "isReported": True
        })

    def handle_article_report(self, article_id: str):
        """
        POST /api/articles/<id>/report
        Submits a report against a publication or question.
        Requires authentication (returns 401 if unauthorized).
        Validates reason (non-empty string, max length 200).
        Prevents author from reporting own publication/question (returns 403 CANNOT_REPORT_OWN_ARTICLE).
        Prevents duplicate report from same user on same article (returns 409 REPORT_ALREADY_EXISTS).
        Inserts into article_reports and returns {"success": true, "message": "Жалоба отправлена"}.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация",
                "code": "AUTH_REQUIRED",
                "requireAuth": True
            })
            return

        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if payload is None:
            return

        if not isinstance(payload, dict):
            self.send_json_response(400, {
                "success": False,
                "error": "Неверный формат данных",
                "code": "INVALID_PAYLOAD"
            })
            return

        if not article_id:
            article_id = str(payload.get("articleId") or payload.get("article_id") or "").strip()

        if not article_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Идентификатор публикации обязателен",
                "code": "INVALID_ARTICLE_ID"
            })
            return

        raw_reason = payload.get("reason")
        if not isinstance(raw_reason, str) or not raw_reason.strip():
            self.send_json_response(400, {
                "success": False,
                "error": "Причина жалобы обязательна",
                "code": "INVALID_REASON"
            })
            return

        reason = raw_reason.strip()
        if len(reason) > 200:
            self.send_json_response(400, {
                "success": False,
                "error": "Причина жалобы не должна превышать 200 символов",
                "code": "REASON_TOO_LONG"
            })
            return

        raw_details = payload.get("details", "")
        details = str(raw_details).strip() if raw_details is not None else ""
        if len(details) > 2000:
            details = details[:2000]

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, draft_id, author_id, status FROM moderation_submissions WHERE (id = ? OR draft_id = ?) AND status = 'approved' LIMIT 1",
                    (article_id, article_id)
                )
                article = cur.fetchone()
                if not article:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Публикация не найдена",
                        "code": "NOT_FOUND"
                    })
                    return

                canonical_id = article["id"]

                if article["author_id"] == user["id"]:
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Нельзя пожаловаться на собственный материал",
                        "code": "CANNOT_REPORT_OWN_ARTICLE"
                    })
                    return

                cur.execute(
                    "SELECT id FROM article_reports WHERE article_id = ? AND user_id = ?",
                    (canonical_id, user["id"])
                )
                if cur.fetchone():
                    self.send_json_response(409, {
                        "success": False,
                        "error": "Вы уже отправили жалобу на этот материал",
                        "code": "REPORT_ALREADY_EXISTS"
                    })
                    return

                report_id = f"artrep_{uuid.uuid4().hex[:12]}"
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cur.execute("""
                    INSERT INTO article_reports (id, article_id, user_id, reason, details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (report_id, canonical_id, user["id"], reason, details, now_iso))
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "message": "Жалоба отправлена",
            "hasReported": True,
            "isReported": True
        })

    def handle_comment_subscribe_toggle(self, comment_id: str):
        """
        POST /api/comments/<id>/subscribe
        Toggles subscription to replies on a comment or answer.
        Requires authentication (returns 401 if unauthorized).
        Toggles subscription: if exists, delete and return {"success": true, "subscribed": false};
        if not exists, insert and return {"success": true, "subscribed": true}.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация",
                "code": "AUTH_REQUIRED",
                "requireAuth": True
            })
            return

        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        if not comment_id and isinstance(payload, dict):
            comment_id = str(payload.get("commentId") or payload.get("comment_id") or "").strip()

        if not comment_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Идентификатор комментария обязателен",
                "code": "INVALID_COMMENT_ID"
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM article_comments WHERE id = ?", (comment_id,))
                comment = cur.fetchone()
                if not comment:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Комментарий не найден",
                        "code": "NOT_FOUND"
                    })
                    return

                cur.execute(
                    "SELECT id FROM comment_subscriptions WHERE comment_id = ? AND user_id = ?",
                    (comment_id, user["id"])
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute("DELETE FROM comment_subscriptions WHERE id = ?", (existing["id"],))
                    subscribed = False
                else:
                    sub_id = f"csub_{uuid.uuid4().hex[:12]}"
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute("""
                        INSERT INTO comment_subscriptions (id, comment_id, user_id, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (sub_id, comment_id, user["id"], now_iso))
                    subscribed = True
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "subscribed": subscribed
        })

    def handle_get_comment_subscriptions(self):
        """
        GET /api/comments/subscriptions
        Returns list of comment IDs the current user is subscribed to:
        {"success": true, "subscriptions": [...]}
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация",
                "code": "AUTH_REQUIRED",
                "requireAuth": True
            })
            return

        conn = self.get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT comment_id FROM comment_subscriptions WHERE user_id = ? ORDER BY created_at ASC",
                (user["id"],)
            )
            rows = cur.fetchall()
            sub_ids = [r["comment_id"] for r in rows]
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "subscriptions": sub_ids
        })

    def handle_get_article_comments(self, article_id: str):
        """
        GET /api/articles/<id>/comments
        Returns structured comments and discussions for the article/question. Accessible to guests.
        Includes answers with nested comments, questionComments, myAnswerId, counters, and flat comments array.
        Enforces:
        - parentCommentId included in DTO
        - Accurate counters: answersCount, questionCommentsCount, commentsCount, discussionCount
        - Deletion placeholders for deleted nodes with active published descendants
        - Strict isolation: orphaned child comments excluded from questionComments
        """
        if not article_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор статьи"
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id, draft_id, status FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (article_id, article_id))
            art_row = cur.fetchone()
            real_id = art_row["id"] if art_row else article_id
            draft_id = art_row["draft_id"] if art_row else None
            parent_is_approved = bool(art_row and art_row["status"] == "approved")

            target_article_ids = [real_id]
            if draft_id and draft_id != real_id:
                target_article_ids.append(draft_id)
            placeholders = ",".join("?" for _ in target_article_ids)

            cur.execute(f"""
                SELECT id, article_id, user_id, author_name, author_avatar, content,
                       status, comment_type, is_solution, parent_answer_id, parent_comment_id,
                       client_operation_id, updated_at, revision, created_at
                FROM article_comments
                WHERE article_id IN ({placeholders}) AND status IN ('published', 'deleted')
                ORDER BY is_solution DESC, created_at ASC
            """, tuple(target_article_ids))
            rows = cur.fetchall()

            cur.execute(f"SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id IN ({placeholders}) AND status = 'published' AND comment_type = 'comment'", tuple(target_article_ids))
            cur.execute(f"SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id IN ({placeholders}) AND status = 'published' AND comment_type = 'answer'", tuple(target_article_ids))

            curr_user = self.get_current_user()
            curr_user_id = curr_user["id"] if curr_user else None

            all_comm_ids = [r["id"] for r in rows]
            comment_scores = {}
            user_comment_votes = {}
            user_comment_reports = set()
            user_comment_saves = set()
            comment_save_counts = {}
            if all_comm_ids:
                for i in range(0, len(all_comm_ids), 500):
                    chunk = all_comm_ids[i:i+500]
                    placeholders = ",".join("?" for _ in chunk)
                    cur.execute(
                        f"SELECT comment_id, COALESCE(SUM(value), 0) AS score FROM comment_votes WHERE comment_id IN ({placeholders}) GROUP BY comment_id",
                        tuple(chunk)
                    )
                    for cr in cur.fetchall():
                        comment_scores[cr["comment_id"]] = cr["score"]

                    cur.execute(
                        f"SELECT comment_id, COUNT(*) AS cnt FROM comment_saves WHERE comment_id IN ({placeholders}) GROUP BY comment_id",
                        tuple(chunk)
                    )
                    for cr in cur.fetchall():
                        comment_save_counts[cr["comment_id"]] = cr["cnt"]

                    if curr_user_id:
                        cur.execute(
                            f"SELECT comment_id, value FROM comment_votes WHERE user_id = ? AND comment_id IN ({placeholders})",
                            (curr_user_id, *chunk)
                        )
                        for cr in cur.fetchall():
                            user_comment_votes[cr["comment_id"]] = cr["value"]

                        cur.execute(
                            f"SELECT comment_id FROM comment_reports WHERE user_id = ? AND comment_id IN ({placeholders})",
                            (curr_user_id, *chunk)
                        )
                        for cr in cur.fetchall():
                            user_comment_reports.add(cr["comment_id"])

                        cur.execute(
                            f"SELECT comment_id FROM comment_saves WHERE user_id = ? AND comment_id IN ({placeholders})",
                            (curr_user_id, *chunk)
                        )
                        for cr in cur.fetchall():
                            user_comment_saves.add(cr["comment_id"])

        row_map = {r["id"]: r for r in rows}
        published_rows = [r for r in rows if r["status"] == "published"]

        # Track ancestor IDs that are required to display published descendants
        needed_ancestors = set()
        for r in published_rows:
            curr_pid = r["parent_comment_id"] if "parent_comment_id" in r.keys() else None
            visited = set()
            while curr_pid and curr_pid in row_map and curr_pid not in visited:
                visited.add(curr_pid)
                needed_ancestors.add(curr_pid)
                p_row = row_map[curr_pid]
                curr_pid = p_row["parent_comment_id"] if "parent_comment_id" in p_row.keys() else None

            p_ans = r["parent_answer_id"] if "parent_answer_id" in r.keys() else None
            if p_ans and p_ans in row_map:
                needed_ancestors.add(p_ans)

        comments = []
        answers_map = {}
        child_comments = []
        question_comments = []
        my_answer_id = None
        has_solution = False
        solution_comment_id = None

        for r in rows:
            is_del = (r["status"] == "deleted")
            # If deleted and not an ancestor of any published descendant, omit completely
            if is_del and r["id"] not in needed_ancestors:
                continue

            ctype = (r["comment_type"] if "comment_type" in r.keys() else None) or "comment"
            is_sol = bool(r["is_solution"]) if "is_solution" in r.keys() and r["is_solution"] is not None else False
            rev = r["revision"] if "revision" in r.keys() and r["revision"] is not None else 1
            upd_at = r["updated_at"] if "updated_at" in r.keys() else None
            p_ans_id = r["parent_answer_id"] if "parent_answer_id" in r.keys() else None
            p_comm_id = r["parent_comment_id"] if "parent_comment_id" in r.keys() else None
            client_op_id = r["client_operation_id"] if "client_operation_id" in r.keys() else None
            comm_score = comment_scores.get(r["id"], 0)
            comm_my_vote = user_comment_votes.get(r["id"], 0)
            comm_is_author = bool(curr_user and r["user_id"] == curr_user_id)
            comm_can_vote = bool(curr_user and parent_is_approved and not is_del and r["status"] == "published" and not comm_is_author)

            if not is_del and is_sol and ctype == "answer":
                has_solution = True
                solution_comment_id = r["id"]

            if is_del:
                dto = {
                    "id": r["id"],
                    "articleId": r["article_id"],
                    "userId": r["user_id"],
                    "authorName": "Удаленный комментарий",
                    "authorAvatar": None,
                    "content": "Комментарий удален",
                    "commentType": ctype,
                    "isSolution": False,
                    "parentAnswerId": p_ans_id,
                    "parentCommentId": p_comm_id,
                    "clientOperationId": client_op_id,
                    "isDeleted": True,
                    "updatedAt": upd_at,
                    "revision": rev,
                    "createdAt": r["created_at"],
                    "score": comm_score,
                    "myVote": comm_my_vote,
                    "canVote": False,
                    "isAuthor": False,
                    "hasReported": (r["id"] in user_comment_reports),
                    "isReported": (r["id"] in user_comment_reports),
                    "isSaved": (r["id"] in user_comment_saves),
                    "hasSaved": (r["id"] in user_comment_saves),
                    "savesCount": comment_save_counts.get(r["id"], 0)
                }
            else:
                dto = {
                    "id": r["id"],
                    "articleId": r["article_id"],
                    "userId": r["user_id"],
                    "authorName": r["author_name"],
                    "authorAvatar": r["author_avatar"] or None,
                    "content": r["content"],
                    "commentType": ctype,
                    "isSolution": is_sol,
                    "parentAnswerId": p_ans_id,
                    "parentCommentId": p_comm_id,
                    "clientOperationId": client_op_id,
                    "isDeleted": False,
                    "updatedAt": upd_at,
                    "revision": rev,
                    "createdAt": r["created_at"],
                    "score": comm_score,
                    "myVote": comm_my_vote,
                    "canVote": comm_can_vote,
                    "isAuthor": comm_is_author,
                    "hasReported": (r["id"] in user_comment_reports),
                    "isReported": (r["id"] in user_comment_reports),
                    "isSaved": (r["id"] in user_comment_saves),
                    "hasSaved": (r["id"] in user_comment_saves),
                    "savesCount": comment_save_counts.get(r["id"], 0)
                }

            if ctype == "answer":
                ans_obj = dict(dto)
                ans_obj["comments"] = []
                ans_obj["commentsCount"] = 0
                answers_map[r["id"]] = ans_obj
                if not is_del and curr_user_id and r["user_id"] == curr_user_id and my_answer_id is None:
                    my_answer_id = r["id"]
                comments.append(dto)
            else:
                if p_ans_id:
                    child_comments.append(dto)
                else:
                    if p_comm_id is not None and p_comm_id not in row_map:
                        # Orphaned comment without valid parent comment
                        continue
                    question_comments.append(dto)
                    comments.append(dto)

        for child in child_comments:
            pid = child["parentAnswerId"]
            if pid in answers_map:
                answers_map[pid]["comments"].append(child)
                if not child.get("isDeleted"):
                    answers_map[pid]["commentsCount"] += 1
                comments.append(child)
            else:
                # Invariant: do NOT dump orphaned child comments into questionComments
                pass

        answers_list = list(answers_map.values())
        answers_count = sum(1 for a in answers_list if not a.get("isDeleted"))
        question_comments_count = sum(1 for q in question_comments if not q.get("isDeleted") and q.get("parentAnswerId") is None)
        comments_count = sum(1 for c in comments if c.get("commentType") == "comment" and not c.get("isDeleted"))
        discussion_count = answers_count + comments_count

        self.send_json_response(200, {
            "success": True,
            "comments": comments,
            "answers": answers_list,
            "questionComments": question_comments,
            "myAnswerId": my_answer_id,
            "answersCount": answers_count,
            "questionCommentsCount": question_comments_count,
            "commentsCount": comments_count,
            "discussionCount": discussion_count,
            "total": len(comments),
            "hasSolution": has_solution,
            "solutionCommentId": solution_comment_id
        })

    def handle_post_article_comment(self, article_id: str):
        """
        POST /api/articles/<id>/comments or POST /api/comments
        Adds an answer or comment to the specified article/question.
        Requires authentication (401 requireAuth).
        Validates content: non-empty, stripped, max 5000 chars. Stores plain-text.
        Strictly validates commentType: must be 'comment' or 'answer' (400).
        Supports parentCommentId and clientOperationId.
        Enforces invariants:
          - Only questions can receive answers (400).
          - Single active published answer per user per question (409 ANSWER_ALREADY_EXISTS).
          - Validates parentCommentId (must be published comment on same publication, comment_type == 'comment').
          - Automatically derives parentAnswerId from parent comment. Reject contradictory parentAnswerId (400).
          - Cycle detection and depth check (depth limit 20 levels; 21st rejected with 400).
          - Idempotency with clientOperationId: replay with same payload returns 200/201 without duplicate,
            replay with conflicting payload returns 409 OPERATION_ID_CONFLICT.
          - Atomic notifications in the same transaction (targeted to immediate parent author, no self-notifications).
        """
        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if payload is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для отправки комментария необходимо войти",
                "requireAuth": True
            })
            return

        if not article_id:
            article_id = payload.get("articleId") or payload.get("article_id") or ""

        if not article_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор статьи"
            })
            return

        raw_comment_type = payload.get("commentType") if "commentType" in payload else payload.get("comment_type")
        if not isinstance(raw_comment_type, str) or raw_comment_type.strip().lower() not in ("comment", "answer"):
            self.send_json_response(400, {
                "success": False,
                "error": "Некорректный или отсутствующий commentType. Допустимые значения: 'comment', 'answer'."
            })
            return
        comment_type = raw_comment_type.strip().lower()

        content = payload.get("content")
        if content is None or not isinstance(content, str) or not content.strip():
            self.send_json_response(400, {
                "success": False,
                "error": "Комментарий не может быть пустым"
            })
            return

        stripped_content = content.strip()
        if len(stripped_content) > 5000:
            self.send_json_response(400, {
                "success": False,
                "error": "Комментарий не должен превышать 5000 символов"
            })
            return

        raw_parent_comm = payload.get("parentCommentId") if "parentCommentId" in payload else payload.get("parent_comment_id")
        raw_parent_ans = payload.get("parentAnswerId") if "parentAnswerId" in payload else payload.get("parent_answer_id")
        raw_client_op = payload.get("clientOperationId") if "clientOperationId" in payload else payload.get("client_operation_id")

        target_parent_comm_id = raw_parent_comm.strip() if isinstance(raw_parent_comm, str) and raw_parent_comm.strip() else None
        target_parent_ans_id = raw_parent_ans.strip() if isinstance(raw_parent_ans, str) and raw_parent_ans.strip() else None
        client_op_id = raw_client_op.strip() if isinstance(raw_client_op, str) and raw_client_op.strip() else None

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id, title, author_id, publication_settings FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (article_id, article_id))
            art_row = cur.fetchone()
            if not art_row:
                self.send_json_response(404, {
                    "success": False,
                    "error": "Статья не найдена"
                })
                return

            real_id = art_row["id"]
            user_id = user["id"]
            author_name = user.get("name") or (f"Пользователь #{user_id[:6]}" if user_id else "Читатель")
            author_avatar = user.get("avatar") or None

            material_type = "article"
            try:
                art_settings = json.loads(art_row["publication_settings"]) if art_row["publication_settings"] else {}
                material_type = (art_settings.get("materialType") or art_settings.get("type") or "article").strip().lower()
            except Exception:
                pass

            art_title = art_row["title"] or "Публикация"
            art_author_id = art_row["author_id"]

            if comment_type == "answer":
                if material_type != "question":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Ответ (answer) возможен только для публикаций с типом 'Вопрос' (materialType = 'question')."
                    })
                    return

                if target_parent_comm_id is not None or target_parent_ans_id is not None:
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Ответ не может иметь родительский комментарий или ответ."
                    })
                    return

                notification_recipient_id = art_author_id
                notification_type = "new_answer"
                notification_title = "Новый ответ на ваш вопрос"
                notification_message = f"Пользователь {author_name} ответил на ваш вопрос «{art_title[:60]}»"
            else:
                # comment_type == 'comment'
                if target_parent_comm_id is not None:
                    cur.execute("""
                        SELECT id, user_id, article_id, comment_type, status, parent_answer_id, parent_comment_id
                        FROM article_comments
                        WHERE id = ? LIMIT 1
                    """, (target_parent_comm_id,))
                    p_comm_row = cur.fetchone()
                    if not p_comm_row or p_comm_row["status"] != "published":
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Указанный родительский комментарий не найден или не опубликован."
                        })
                        return

                    if p_comm_row["article_id"] != real_id:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Родительский комментарий принадлежит другой публикации."
                        })
                        return

                    if p_comm_row["comment_type"] != "comment":
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Родительский комментарий не может быть ответом. Для ответа на ответ используйте parentAnswerId."
                        })
                        return

                    # Automatically derive parent_answer_id from parent comment
                    derived_ans_id = p_comm_row["parent_answer_id"]
                    if target_parent_ans_id is not None and target_parent_ans_id != derived_ans_id:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Указанный parentAnswerId противоречит родительскому комментарию."
                        })
                        return
                    target_parent_ans_id = derived_ans_id

                    # Cycle detection and depth check: walk up parent_comment_id chain
                    depth = 1
                    curr_anc_id = p_comm_row["parent_comment_id"]
                    visited_anc = {target_parent_comm_id}
                    while curr_anc_id is not None:
                        depth += 1
                        if curr_anc_id in visited_anc:
                            self.send_json_response(400, {
                                "success": False,
                                "error": "Обнаружен цикл в иерархии комментариев."
                            })
                            return
                        visited_anc.add(curr_anc_id)
                        if depth >= 20:
                            self.send_json_response(400, {
                                "success": False,
                                "error": "Превышена максимальная глубина вложенности комментариев (максимум 20 уровней)."
                            })
                            return
                        cur.execute("SELECT parent_comment_id FROM article_comments WHERE id = ? LIMIT 1", (curr_anc_id,))
                        anc_r = cur.fetchone()
                        if not anc_r:
                            break
                        curr_anc_id = anc_r["parent_comment_id"]

                    notification_recipient_id = p_comm_row["user_id"]
                    notification_type = "new_reply"
                    notification_title = "Новый ответ в обсуждении"
                    notification_message = f"Пользователь {author_name} ответил на ваш комментарий к «{art_title[:60]}»"
                elif target_parent_ans_id is not None:
                    # Direct comment on answer
                    cur.execute("""
                        SELECT id, user_id, article_id, comment_type, status
                        FROM article_comments
                        WHERE id = ? LIMIT 1
                    """, (target_parent_ans_id,))
                    p_ans_row = cur.fetchone()
                    if not p_ans_row or p_ans_row["comment_type"] != "answer" or p_ans_row["status"] != "published" or p_ans_row["article_id"] != real_id:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Указанный ответ не найден или не принадлежит данному вопросу."
                        })
                        return

                    notification_recipient_id = p_ans_row["user_id"]
                    notification_type = "new_reply"
                    notification_title = "Новый ответ в обсуждении"
                    notification_message = f"Пользователь {author_name} ответил на ваш ответ к «{art_title[:60]}»"
                else:
                    # Root comment on article or question
                    notification_recipient_id = art_author_id
                    notification_type = "new_reply"
                    notification_title = "Новый комментарий"
                    notification_message = f"Пользователь {author_name} оставил комментарий к «{art_title[:60]}»"

            # Idempotency check with clientOperationId
            if client_op_id:
                cur.execute("""
                    SELECT * FROM article_comments
                    WHERE user_id = ? AND client_operation_id = ?
                    LIMIT 1
                """, (user_id, client_op_id))
                existing_op = cur.fetchone()
                if existing_op:
                    same_art = (existing_op["article_id"] == real_id)
                    same_content = (existing_op["content"] == stripped_content)
                    same_type = (existing_op["comment_type"] == comment_type)
                    same_p_comm = ((existing_op["parent_comment_id"] or None) == target_parent_comm_id)
                    same_p_ans = ((existing_op["parent_answer_id"] or None) == target_parent_ans_id)

                    if same_art and same_content and same_type and same_p_comm and same_p_ans:
                        cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = ? AND status = 'published' AND comment_type = 'comment'", (real_id,))
                        comments_count = cur.fetchone()["cnt"]
                        cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = ? AND status = 'published' AND comment_type = 'answer'", (real_id,))
                        answers_count = cur.fetchone()["cnt"]
                        discussion_count = comments_count + answers_count
                        self.send_json_response(200, {
                            "success": True,
                            "comment": {
                                "id": existing_op["id"],
                                "articleId": existing_op["article_id"],
                                "userId": existing_op["user_id"],
                                "authorName": existing_op["author_name"],
                                "authorAvatar": existing_op["author_avatar"] or None,
                                "content": existing_op["content"],
                                "commentType": existing_op["comment_type"],
                                "isSolution": bool(existing_op["is_solution"]),
                                "parentAnswerId": existing_op["parent_answer_id"],
                                "parentCommentId": existing_op["parent_comment_id"],
                                "clientOperationId": existing_op["client_operation_id"],
                                "updatedAt": existing_op["updated_at"],
                                "revision": existing_op["revision"] if "revision" in existing_op.keys() and existing_op["revision"] is not None else 1,
                                "createdAt": existing_op["created_at"]
                            },
                            "commentsCount": comments_count,
                            "answersCount": answers_count,
                            "discussionCount": discussion_count,
                            "isDuplicate": True
                        })
                        return
                    else:
                        self.send_json_response(409, {
                            "success": False,
                            "error": "Запрос с данным clientOperationId уже обработан с другими параметрами.",
                            "code": "OPERATION_ID_CONFLICT"
                        })
                        return

            if comment_type == "answer":
                cur.execute("""
                    SELECT id FROM article_comments
                    WHERE article_id = ? AND user_id = ? AND comment_type = 'answer' AND status = 'published'
                    LIMIT 1
                """, (real_id, user_id))
                existing_answer = cur.fetchone()
                if existing_answer:
                    self.send_json_response(409, {
                        "success": False,
                        "error": "Вы уже опубликовали ответ на этот вопрос",
                        "code": "ANSWER_ALREADY_EXISTS",
                        "myAnswerId": existing_answer["id"]
                    })
                    return

            comment_id = f"comm_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

            try:
                cur.execute("""
                    INSERT INTO article_comments (
                        id, article_id, user_id, author_name, author_avatar, content, status,
                        comment_type, is_solution, parent_answer_id, parent_comment_id, client_operation_id,
                        updated_at, revision, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'published', ?, 0, ?, ?, ?, NULL, 1, ?)
                """, (
                    comment_id, real_id, user_id, author_name, author_avatar,
                    stripped_content, comment_type, target_parent_ans_id,
                    target_parent_comm_id, client_op_id, now_iso
                ))
            except sqlite3.IntegrityError:
                if client_op_id:
                    cur.execute("""
                        SELECT * FROM article_comments
                        WHERE user_id = ? AND client_operation_id = ?
                        LIMIT 1
                    """, (user_id, client_op_id))
                    race_row = cur.fetchone()
                    if race_row:
                        same_art = (race_row["article_id"] == real_id)
                        same_content = (race_row["content"] == stripped_content)
                        same_type = (race_row["comment_type"] == comment_type)
                        same_p_comm = ((race_row["parent_comment_id"] or None) == target_parent_comm_id)
                        same_p_ans = ((race_row["parent_answer_id"] or None) == target_parent_ans_id)
                        if same_art and same_content and same_type and same_p_comm and same_p_ans:
                            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = ? AND status = 'published' AND comment_type = 'comment'", (real_id,))
                            comments_count = cur.fetchone()["cnt"]
                            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = ? AND status = 'published' AND comment_type = 'answer'", (real_id,))
                            answers_count = cur.fetchone()["cnt"]
                            discussion_count = comments_count + answers_count
                            self.send_json_response(200, {
                                "success": True,
                                "comment": {
                                    "id": race_row["id"],
                                    "articleId": race_row["article_id"],
                                    "userId": race_row["user_id"],
                                    "authorName": race_row["author_name"],
                                    "authorAvatar": race_row["author_avatar"] or None,
                                    "content": race_row["content"],
                                    "commentType": race_row["comment_type"],
                                    "isSolution": bool(race_row["is_solution"]),
                                    "parentAnswerId": race_row["parent_answer_id"],
                                    "parentCommentId": race_row["parent_comment_id"],
                                    "clientOperationId": race_row["client_operation_id"],
                                    "updatedAt": race_row["updated_at"],
                                    "revision": race_row["revision"] if "revision" in race_row.keys() and race_row["revision"] is not None else 1,
                                    "createdAt": race_row["created_at"]
                                },
                                "commentsCount": comments_count,
                                "answersCount": answers_count,
                                "discussionCount": discussion_count,
                                "isDuplicate": True
                            })
                            return
                        else:
                            self.send_json_response(409, {
                                "success": False,
                                "error": "Запрос с данным clientOperationId уже обработан с другими параметрами.",
                                "code": "OPERATION_ID_CONFLICT"
                            })
                            return
                if comment_type == "answer":
                    cur.execute("""
                        SELECT id FROM article_comments
                        WHERE article_id = ? AND user_id = ? AND comment_type = 'answer' AND status = 'published'
                        LIMIT 1
                    """, (real_id, user_id))
                    existing_ans = cur.fetchone()
                    my_id = existing_ans["id"] if existing_ans else ""
                    self.send_json_response(409, {
                        "success": False,
                        "error": "Вы уже опубликовали ответ на этот вопрос",
                        "code": "ANSWER_ALREADY_EXISTS",
                        "myAnswerId": my_id
                    })
                    return
                raise

            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = ? AND status = 'published' AND comment_type = 'comment'", (real_id,))
            comments_count = cur.fetchone()["cnt"]
            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = ? AND status = 'published' AND comment_type = 'answer'", (real_id,))
            answers_count = cur.fetchone()["cnt"]
            discussion_count = comments_count + answers_count

            # Notification is sent only if recipient exists and is not the actor
            if notification_recipient_id and notification_recipient_id != user_id:
                notif_id = f"notif_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
                cur.execute("""
                    INSERT INTO user_notifications (
                        id, user_id, actor_id, actor_name, article_id, comment_id, type, title, message, is_read, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """, (
                    notif_id, notification_recipient_id, user_id, author_name, real_id, comment_id,
                    notification_type, notification_title, notification_message, now_iso
                ))

        comment_data = {
            "id": comment_id,
            "articleId": real_id,
            "userId": user_id,
            "authorName": author_name,
            "authorAvatar": author_avatar,
            "content": stripped_content,
            "commentType": comment_type,
            "isSolution": False,
            "parentAnswerId": target_parent_ans_id,
            "parentCommentId": target_parent_comm_id,
            "clientOperationId": client_op_id,
            "updatedAt": None,
            "revision": 1,
            "createdAt": now_iso
        }

        self.send_json_response(201, {
            "success": True,
            "comment": comment_data,
            "commentsCount": comments_count,
            "answersCount": answers_count,
            "discussionCount": discussion_count
        })

    def handle_update_article_comment(self, art_id: str, comm_id: str):
        """
        PUT /api/articles/<art_id>/comments/<comm_id> or PUT /api/comments/<comm_id>
        Allows the author of an answer or comment to edit its content.
        Enforces authentication (401), content validation (1..5000 chars),
        published status check, author ownership (403), URL article matching (400),
        immutability of relational bindings (400),
        and optimistic concurrency locking via revision (409 CONCURRENCY_CONFLICT).
        """
        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if payload is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для редактирования необходимо войти",
                "requireAuth": True
            })
            return

        if not comm_id:
            comm_id = payload.get("commentId") or payload.get("comment_id") or ""
        if not comm_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор комментария"
            })
            return

        content = payload.get("content")
        if content is None or not isinstance(content, str) or not content.strip():
            self.send_json_response(400, {
                "success": False,
                "error": "Комментарий не может быть пустым"
            })
            return

        stripped_content = content.strip()
        if len(stripped_content) > 5000:
            self.send_json_response(400, {
                "success": False,
                "error": "Комментарий не должен превышать 5000 символов"
            })
            return

        revision_param = payload.get("revision")

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM article_comments WHERE id = ?", (comm_id,))
                comment = cur.fetchone()
                if not comment:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Комментарий не найден"
                    })
                    return

                comm_type = (comment["comment_type"] if "comment_type" in comment.keys() else "").strip().lower()
                comm_status = (comment["status"] if "status" in comment.keys() else "").strip().lower()
                if comm_type not in ("answer", "comment") or comm_status != "published":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Редактирование доступно только для опубликованных комментариев и ответов"
                    })
                    return

                if art_id:
                    cur.execute("SELECT id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (art_id, art_id))
                    art_row = cur.fetchone()
                    canonical_art_id = art_row["id"] if art_row else art_id
                    if canonical_art_id != comment["article_id"]:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Идентификатор публикации не совпадает с комментарием"
                        })
                        return

                if user["id"] != comment["user_id"]:
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Вы можете редактировать только свой комментарий или ответ"
                    })
                    return

                # Enforce 48-hour editing window (Issue #73)
                created_at_raw = comment["created_at"] if "created_at" in comment.keys() else None
                if created_at_raw:
                    try:
                        created_dt = datetime.datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
                        if created_dt.tzinfo is None:
                            created_dt = created_dt.replace(tzinfo=datetime.timezone.utc)
                        now_utc = datetime.datetime.now(datetime.timezone.utc)
                        diff_seconds = (now_utc - created_dt).total_seconds()
                        if diff_seconds >= 48 * 3600:
                            self.send_json_response(403, {
                                "success": False,
                                "error": "Срок редактирования комментария истек (максимум 48 часов с момента публикации)",
                                "code": "EDIT_WINDOW_EXPIRED"
                            })
                            return
                    except Exception:
                        pass

                # Invariant: reject attempts to modify immutable bindings
                if "articleId" in payload or "article_id" in payload:
                    p_art = payload.get("articleId") or payload.get("article_id")
                    cur.execute("SELECT id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (p_art, p_art))
                    p_art_row = cur.fetchone()
                    p_art_canonical = p_art_row["id"] if p_art_row else p_art
                    if p_art_canonical != comment["article_id"]:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Запрещено изменять публикацию комментария"
                        })
                        return

                if "commentType" in payload or "comment_type" in payload:
                    p_ctype = payload.get("commentType") or payload.get("comment_type")
                    if p_ctype != comment["comment_type"]:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Запрещено изменять тип комментария"
                        })
                        return

                if "parentAnswerId" in payload or "parent_answer_id" in payload:
                    p_ans = payload.get("parentAnswerId") if "parentAnswerId" in payload else payload.get("parent_answer_id")
                    if isinstance(p_ans, str) and not p_ans.strip():
                        p_ans = None
                    c_ans = comment["parent_answer_id"] if "parent_answer_id" in comment.keys() else None
                    if p_ans != c_ans:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Запрещено изменять родительский ответ комментария"
                        })
                        return

                if "parentCommentId" in payload or "parent_comment_id" in payload:
                    p_comm = payload.get("parentCommentId") if "parentCommentId" in payload else payload.get("parent_comment_id")
                    if isinstance(p_comm, str) and not p_comm.strip():
                        p_comm = None
                    c_comm = comment["parent_comment_id"] if "parent_comment_id" in comment.keys() else None
                    if p_comm != c_comm:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Запрещено изменять родительский комментарий"
                        })
                        return

                if "isSolution" in payload or "is_solution" in payload:
                    p_sol = payload.get("isSolution") if "isSolution" in payload else payload.get("is_solution")
                    if p_sol is not None:
                        c_sol = bool(comment["is_solution"]) if "is_solution" in comment.keys() and comment["is_solution"] is not None else False
                        if bool(p_sol) != c_sol:
                            self.send_json_response(400, {
                                "success": False,
                                "error": "Запрещено изменять статус решения через редактирование комментария"
                            })
                            return

                current_revision = comment["revision"] if "revision" in comment.keys() and comment["revision"] is not None else 1

                if comm_type == "comment":
                    if revision_param is None:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Поле revision обязательно для редактирования комментария",
                            "code": "REVISION_REQUIRED"
                        })
                        return
                    if not isinstance(revision_param, int) or isinstance(revision_param, bool):
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Поле revision должно быть целым числом",
                            "code": "INVALID_REVISION"
                        })
                        return
                    if revision_param != current_revision:
                        self.send_json_response(409, {
                            "success": False,
                            "error": "Комментарий был изменен в другой сессии",
                            "code": "CONCURRENCY_CONFLICT",
                            "currentRevision": current_revision,
                            "currentContent": comment["content"]
                        })
                        return
                    expected_rev = revision_param
                elif comm_type == "answer":
                    if revision_param is not None:
                        if not isinstance(revision_param, int) or isinstance(revision_param, bool):
                            self.send_json_response(400, {
                                "success": False,
                                "error": "Поле revision должно быть целым числом",
                                "code": "INVALID_REVISION"
                            })
                            return
                        if revision_param != current_revision:
                            self.send_json_response(409, {
                                "success": False,
                                "error": "Комментарий был изменен в другой сессии",
                                "code": "CONCURRENCY_CONFLICT",
                                "currentRevision": current_revision,
                                "currentContent": comment["content"]
                            })
                            return
                        expected_rev = revision_param
                    else:
                        expected_rev = current_revision
                else:
                    expected_rev = current_revision

                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cur.execute("""
                    UPDATE article_comments
                    SET content = ?, updated_at = ?, revision = revision + 1
                    WHERE id = ? AND revision = ?
                """, (stripped_content, now_iso, comm_id, expected_rev))

                if cur.rowcount == 0:
                    cur.execute("SELECT * FROM article_comments WHERE id = ?", (comm_id,))
                    latest = cur.fetchone()
                    latest_rev = latest["revision"] if latest and "revision" in latest.keys() else current_revision
                    latest_cnt = latest["content"] if latest else comment["content"]
                    self.send_json_response(409, {
                        "success": False,
                        "error": "Комментарий был изменен в другой сессии",
                        "code": "CONCURRENCY_CONFLICT",
                        "currentRevision": latest_rev,
                        "currentContent": latest_cnt
                    })
                    return

            new_revision = expected_rev + 1
            self.send_json_response(200, {
                "success": True,
                "comment": {
                    "id": comment["id"],
                    "articleId": comment["article_id"],
                    "userId": comment["user_id"],
                    "authorName": comment["author_name"],
                    "authorAvatar": comment["author_avatar"] or None,
                    "content": stripped_content,
                    "commentType": comment["comment_type"],
                    "isSolution": bool(comment["is_solution"]),
                    "parentAnswerId": comment["parent_answer_id"] if "parent_answer_id" in comment.keys() else None,
                    "parentCommentId": comment["parent_comment_id"] if "parent_comment_id" in comment.keys() else None,
                    "clientOperationId": comment["client_operation_id"] if "client_operation_id" in comment.keys() else None,
                    "revision": new_revision,
                    "updatedAt": now_iso,
                    "createdAt": comment["created_at"]
                }
            })
        finally:
            conn.close()

    def handle_delete_article_comment(self, art_id: str, comm_id: str):
        """
        DELETE /api/articles/<art_id>/comments/<comm_id> or DELETE /api/comments/<comm_id>
        Soft-deletes a comment or answer by setting status = 'deleted'.
        Requires authentication and ownership (or admin role).
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для удаления необходимо войти",
                "requireAuth": True
            })
            return

        if not comm_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор комментария"
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM article_comments WHERE id = ?", (comm_id,))
                comment = cur.fetchone()
                if not comment:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Комментарий не найден"
                    })
                    return

                if art_id:
                    cur.execute("SELECT id, draft_id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (art_id, art_id))
                    art_row = cur.fetchone()
                    canonical_art_id = art_row["id"] if art_row else art_id
                    draft_art_id = art_row["draft_id"] if art_row else None
                    valid_art_ids = {canonical_art_id}
                    if draft_art_id:
                        valid_art_ids.add(draft_art_id)
                    if comment["article_id"] not in valid_art_ids:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Идентификатор публикации не совпадает с комментарием"
                        })
                        return

                user_id = user["id"]
                user_role = user.get("role", "user")
                if user_id != comment["user_id"] and user_role != "admin":
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Вы можете удалять только свои комментарии"
                    })
                    return

                comm_type = (comment["comment_type"] if "comment_type" in comment.keys() else None) or "comment"
                if comm_type != "comment" and user_role != "admin":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Удаление доступно только для обычных комментариев"
                    })
                    return

                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cur.execute("UPDATE article_comments SET status = 'deleted', is_solution = 0, updated_at = ? WHERE id = ?", (now_iso, comm_id))

            self.send_json_response(200, {
                "success": True,
                "commentId": comm_id
            })
        finally:
            conn.close()

    def handle_moderation_submit(self):
        """
        POST /api/moderation/submit
        Receives { draftId, title, html, delta, publicationSettings, idempotencyKey }.
        Validates payload, enforces idempotency, checks status transition,
        calculates SHA-256 snapshot hash, and stores immutable snapshot in SQLite.
        Requires authenticated user. author_id is strictly bound to curr_user.
        """
        raw_body = self.read_request_body(MAX_JSON_BODY_BYTES)
        if raw_body is None:
            return

        curr_user = self.get_current_user()
        if not curr_user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация для отправки материалов",
                "requireAuth": True
            })
            return

        if not raw_body:
            self.send_json_response(400, {
                "success": False,
                "error": "Пустое тело запроса (Content-Length must be > 0)",
                "fieldErrors": {}
            })
            return

        try:
            body = raw_body.decode("utf-8")
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.send_json_response(400, {
                "success": False,
                "error": f"Невалидный JSON: {str(e)}",
                "fieldErrors": {}
            })
            return
        except Exception as e:
            self.send_json_response(400, {
                "success": False,
                "error": f"Ошибка декодирования запроса: {str(e)}",
                "fieldErrors": {}
            })
            return

        if not isinstance(payload, dict):
            self.send_json_response(400, {
                "success": False,
                "error": "Тело запроса должно быть JSON-объектом.",
                "fieldErrors": {}
            })
            return

        idempotency_key = payload.get("idempotencyKey") or payload.get("idempotency_key")
        if isinstance(idempotency_key, str):
            idempotency_key = idempotency_key.strip() or None
        else:
            idempotency_key = None

        conn = self.get_db()
        try:
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
            raw_html = payload.get("html") or payload.get("article_html") or payload.get("content") or ""
            article_html = sanitize_article_html(raw_html)
            delta = payload.get("delta") or payload.get("article_delta")
            pub_settings = payload.get("publicationSettings") or payload.get("publication_settings")
            author_id = curr_user["id"]

            # Company publication authorization check
            comp_id = pub_settings.get("companyId") or pub_settings.get("company_id")
            if comp_id:
                with conn:
                    cur = conn.cursor()
                    cur.execute("SELECT id FROM companies WHERE id = ?", (comp_id,))
                    comp_row = cur.fetchone()
                if not comp_row:
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Указанная компания не найдена.",
                        "fieldErrors": {
                            "companyId": "Указанная компания не существует."
                        }
                    })
                    return

                user_role = curr_user.get("role", "user")
                if not can_user_publish_for_company(conn, author_id, comp_id, user_role=user_role):
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Отказано в доступе: у вас нет прав на публикацию от имени выбранной компании.",
                        "fieldErrors": {
                            "companyId": "Вы не являетесь владельцем или участником этой компании."
                        }
                    })
                    return
                pub_settings["companyId"] = comp_id

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
                            "id": dup_row["id"],
                            "url": f"/article.html?id={dup_row['id']}",
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
                "id": submission_id,
                "url": f"/article.html?id={submission_id}",
                "snapshotHash": snapshot_hash,
                "createdAt": now_iso
            })
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def handle_moderation_status(self, parsed_url):
        """
        GET /api/moderation/status?draftId=...
        Returns status of the latest submission for the draft.
        Requires authentication. Allowed only for the submission author or moderator/admin.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация для проверки статуса модерации",
                "requireAuth": True
            })
            return

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
        try:
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

            if not self.is_moderator_or_admin(user) and row["author_id"] != user["id"]:
                self.send_json_response(403, {
                    "success": False,
                    "error": "Доступ запрещен: вы можете просматривать статус только своих заявок"
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
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def handle_moderation_list(self):
        """
        GET /api/moderation/list
        Returns array of submissions in queue (for moderator or admin access only).
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация для доступа к очереди модерации",
                "requireAuth": True
            })
            return

        if not self.is_moderator_or_admin(user):
            self.send_json_response(403, {
                "success": False,
                "error": "Доступ запрещен: требуется роль модератора или администратора"
            })
            return

        conn = self.get_db()
        try:
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
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def handle_articles_api(self, parsed_url):
        """
        Dispatches GET /api/articles or /api/questions requests to single article view or feed list view.
        """
        path = parsed_url.path
        prefix = "/api/articles/" if path.startswith("/api/articles/") else ("/api/questions/" if path.startswith("/api/questions/") else None)
        if prefix:
            article_id = path[len(prefix):].strip()
            if article_id.endswith("/comments"):
                self.handle_get_article_comments(article_id[:-len("/comments")].strip("/"))
                return
            if article_id:
                self.handle_get_article(article_id)
                return

        query = urllib.parse.parse_qs(parsed_url.query)
        if "id" in query and query["id"][0].strip():
            self.handle_get_article(query["id"][0].strip())
            return

        self.handle_get_articles_list(parsed_url)

    def handle_get_article(self, article_id: str):
        """
        GET /api/articles/<id> or GET /api/articles?id=<id>
        Returns full details of an approved publication.
        Returns 404 for drafts, pending/rejected submissions, or non-existent IDs.
        """
        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM moderation_submissions WHERE (id = ? OR draft_id = ?) AND status = 'approved' LIMIT 1",
                (article_id, article_id)
            )
            row = cur.fetchone()

        if not row:
            self.send_json_response(404, {
                "success": False,
                "error": "Статья не найдена или еще не опубликована"
            })
            return

        try:
            settings = json.loads(row["publication_settings"]) if row["publication_settings"] else {}
        except Exception:
            settings = {}

        try:
            delta = json.loads(row["article_delta"]) if row["article_delta"] else None
        except Exception:
            delta = None

        article_html = row["article_html"] or ""
        reading_time, reading_minutes = calculate_reading_time(article_html)

        author_name = settings.get("author") or (
            "Пользователь #" + row["author_id"][:6] if row["author_id"] else "Автор SmartContractum"
        )
        author_initials = settings.get("authorInitials") or (
            "".join([part[0].upper() for part in author_name.split()[:2]]) if author_name else "SC"
        )
        author_role = settings.get("authorRole") or ""

        topics = settings.get("topics") or []

        user = self.get_current_user()
        likes_count = 0
        saves_count = 0
        comments_count = 0
        answers_count = 0
        discussion_count = 0
        has_solution = False
        has_liked = False
        has_saved = False
        has_reported = False
        score = 0
        my_vote = 0
        can_vote = False
        is_author = False
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM article_likes WHERE article_id = ?", (row["id"],))
            likes_count = cur.fetchone()["cnt"]
            cur.execute("SELECT COUNT(*) AS cnt FROM article_saves WHERE article_id = ?", (row["id"],))
            saves_count = cur.fetchone()["cnt"]
            target_ids = [row["id"]]
            draft_id = row["draft_id"] if ("draft_id" in row.keys() and row["draft_id"]) else None
            if draft_id and draft_id != row["id"]:
                target_ids.append(draft_id)
            placeholders = ",".join("?" for _ in target_ids)
            cur.execute(f"SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id IN ({placeholders}) AND status = 'published' AND comment_type = 'comment'", tuple(target_ids))
            comments_count = cur.fetchone()["cnt"]
            cur.execute(f"SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id IN ({placeholders}) AND status = 'published' AND comment_type = 'answer'", tuple(target_ids))
            answers_count = cur.fetchone()["cnt"]
            discussion_count = comments_count + answers_count
            cur.execute(f"SELECT 1 FROM article_comments WHERE article_id IN ({placeholders}) AND status = 'published' AND is_solution = 1 LIMIT 1", tuple(target_ids))
            has_solution = cur.fetchone() is not None
            cur.execute("SELECT COALESCE(SUM(value), 0) AS score FROM article_votes WHERE article_id = ?", (row["id"],))
            score_row = cur.fetchone()
            score = score_row["score"] if score_row else 0
            if user:
                cur.execute("SELECT 1 FROM article_likes WHERE article_id = ? AND user_id = ?", (row["id"], user["id"]))
                has_liked = cur.fetchone() is not None
                cur.execute("SELECT 1 FROM article_saves WHERE article_id = ? AND user_id = ?", (row["id"], user["id"]))
                has_saved = cur.fetchone() is not None
                cur.execute(f"SELECT 1 FROM article_reports WHERE article_id IN ({placeholders}) AND user_id = ? LIMIT 1", (*target_ids, user["id"]))
                has_reported = cur.fetchone() is not None
                cur.execute("SELECT value FROM article_votes WHERE article_id = ? AND user_id = ?", (row["id"], user["id"]))
                vote_row = cur.fetchone()
                if vote_row:
                    my_vote = vote_row["value"]
                is_author = bool(row["author_id"] == user["id"])
                can_vote = bool(row["status"] == "approved" and not is_author)

        raw_mat = (settings.get("materialType") or settings.get("type") or "publication").strip().lower()
        if raw_mat in ("article", "post", "news"):
            mat_type = "publication"
        else:
            mat_type = raw_mat

        article_data = {
            "id": row["id"],
            "draftId": row["draft_id"],
            "title": row["title"],
            "authorId": row["author_id"],
            "author_id": row["author_id"],
            "author": author_name,
            "authorInitials": author_initials,
            "authorRole": author_role,
            "date": format_date_ru(row["created_at"]),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "description": settings.get("description") or "",
            "coverImage": settings.get("coverImage") or None,
            "coverPosition": resolve_cover_position(settings),
            "focalPoint": resolve_cover_position(settings),
            "objectPosition": resolve_cover_position(settings),
            "isDemo": bool(settings.get("isDemo") or row["id"].startswith("art-0")),
            "topics": topics,
            "topic": topics[0] if topics else "",
            "targetAudience": settings.get("targetAudience") or None,
            "format": settings.get("format") or None,
            "complexity": settings.get("complexity") or None,
            "keywords": settings.get("keywords") or [],
            "readingTime": reading_time,
            "readingMinutes": reading_minutes,
            "likesCount": likes_count,
            "hasLiked": has_liked,
            "savesCount": saves_count,
            "hasSaved": has_saved,
            "isSaved": has_saved,
            "hasReported": has_reported,
            "isReported": has_reported,
            "score": score,
            "myVote": my_vote,
            "canVote": can_vote,
            "isAuthor": is_author,
            "commentsCount": comments_count,
            "answersCount": answers_count,
            "discussionCount": discussion_count,
            "hasSolution": has_solution,
            "materialType": mat_type,
            "type": mat_type,
            "html": article_html,
            "delta": delta
        }

        self.send_json_response(200, {
            "success": True,
            "article": article_data,
            "savesCount": saves_count,
            "hasSaved": has_saved,
            "isSaved": has_saved,
            "hasReported": has_reported,
            "isReported": has_reported,
            "commentsCount": comments_count,
            "answersCount": answers_count,
            "discussionCount": discussion_count,
            "score": score,
            "myVote": my_vote,
            "canVote": can_vote,
            "isAuthor": is_author
        })

    handle_get_article_by_id = handle_get_article

    def handle_get_articles_list(self, parsed_url):
        """
        GET /api/articles
        Query parameters:
          tab: 'focus' (default), 'top', 'new', 'subscriptions'/'my', 'saved', 'all'
          period: 'day', 'week', 'month', 'all' (for tab=top, default 'week')
          search: search string across title, description, keywords, and body
          topic / topics / direction: filter by topic ID
          club / clubId: filter by club ID
          company / companyId: filter by company ID
          audience: filter by target audience ID
          format: filter by format ID
          complexity / complexities: filter by complexity ID(s)
          type / types: filter by material type(s)
          sort: 'popular', 'discussed', 'newest', 'oldest'
          ids: comma-separated list of article IDs (for bookmarks retrieval)
          limit: items per page (default 10)
          offset: offset for pagination (default 0)
        Returns approved articles matching criteria.
        """
        query = urllib.parse.parse_qs(parsed_url.query)
        tab_param = query.get("tab", [None])[0]
        types_raw = (query.get("types", [""])[0] or query.get("type", [""])[0] or query.get("materialType", [""])[0] or "").strip().lower()
        if tab_param is None and types_raw in ("question", "questions"):
            tab_raw = "questions"
        else:
            tab_raw = (tab_param or "all").strip().lower()
        tab = "subscriptions" if tab_raw == "my" else tab_raw
        search_query = (query.get("search", [""])[0] or query.get("q", [""])[0] or "").strip().lower()
        question_status = (query.get("questionStatus", ["all"])[0] or query.get("question_status", ["all"])[0] or query.get("status", ["all"])[0]).strip().lower()

        direction_param = (query.get("direction", [""])[0] or "").strip()
        topics_filter = (query.get("topics", [""])[0] or query.get("topic", [""])[0] or direction_param).strip()
        club_filter = (query.get("club", [""])[0] or query.get("clubId", [""])[0] or "").strip()
        company_filter = (query.get("company", [""])[0] or query.get("companyId", [""])[0] or "").strip()
        is_company_param = (query.get("isCompany", [""])[0] or query.get("is_company", [""])[0] or "").strip().lower()
        is_company_filter = is_company_param in ("1", "true", "yes")

        # Audience filter (supports single or multiple, comma-separated or repeated)
        audiences_raw = query.get("audiences", []) + query.get("audience", [])
        allowed_audiences = set()
        for item in audiences_raw:
            for a in item.split(","):
                a_clean = a.strip()
                if a_clean and a_clean != "all":
                    allowed_audiences.add(a_clean)
        if not allowed_audiences:
            allowed_audiences = None

        # Format filter (supports single or multiple, comma-separated or repeated)
        formats_raw = query.get("formats", []) + query.get("format", [])
        allowed_formats = set()
        for item in formats_raw:
            for f in item.split(","):
                f_clean = f.strip()
                if f_clean and f_clean != "all":
                    allowed_formats.add(f_clean)
        if not allowed_formats:
            allowed_formats = None

        complexity_filter = (query.get("complexities", [""])[0] or query.get("complexity", [""])[0] or "").strip()
        types_filter = types_raw
        sort_by = (query.get("sort", ["newest"])[0] or "newest").strip().lower()
        has_explicit_sort = "sort" in query

        # Period filtering: for tab=top defaults to week; otherwise defaults to all
        default_period = "week" if tab == "top" else "all"
        period_filter = (query.get("period", [default_period])[0] or default_period).strip().lower()
        date_from_str = (query.get("dateFrom", [""])[0] or query.get("date_from", [""])[0] or "").strip()
        date_to_str = (query.get("dateTo", [""])[0] or query.get("date_to", [""])[0] or "").strip()
        ids_filter = (query.get("ids", [""])[0] or "").strip()

        try:
            limit = max(1, min(100, int(query.get("limit", [10])[0])))
        except ValueError:
            limit = 10

        try:
            offset = max(0, int(query.get("offset", [0])[0]))
        except ValueError:
            offset = 0

        allowed_ids = set([x.strip() for x in ids_filter.split(",") if x.strip()]) if ids_filter else None
        if tab == "saved" and allowed_ids is None:
            active_u = self.get_current_user()
            if active_u:
                conn_tmp = self.get_db()
                with conn_tmp:
                    cur_tmp = conn_tmp.cursor()
                    cur_tmp.execute("SELECT article_id FROM article_saves WHERE user_id = ?", (active_u["id"],))
                    allowed_ids = {r["article_id"] for r in cur_tmp.fetchall()}
            else:
                allowed_ids = set()

        if topics_filter and topics_filter != "all":
            req_topics = set([t.strip() for t in topics_filter.split(",") if t.strip()])
        else:
            req_topics = None
        if req_topics and "all" in req_topics:
            req_topics = None

        sub_authors = set()
        sub_topics = set()
        sub_tags = set()
        sub_clubs = set()
        sub_companies = set()
        sub_topics_titles = {}
        sub_tags_titles = {}
        sub_clubs_titles = {}
        sub_companies_titles = {}

        user_types = None
        user_complexities = None

        if tab in ("subscriptions", "my"):
            user = self.get_current_user()
            if not user:
                self.send_json_response(401, {
                    "success": False,
                    "error": "Для просмотра персональной ленты необходимо войти",
                    "requireAuth": True
                })
                return

            conn = self.get_db()
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT target_type, target_id, target_title FROM user_subscriptions WHERE user_id = ?",
                    (user["id"],)
                )
                sub_rows = cur.fetchall()

                cur.execute(
                    "SELECT material_types, complexity_levels FROM user_feed_settings WHERE user_id = ?",
                    (user["id"],)
                )
                fs_row = cur.fetchone()
                if fs_row:
                    try:
                        user_types = json.loads(fs_row["material_types"])
                    except Exception:
                        user_types = None
                    try:
                        user_complexities = json.loads(fs_row["complexity_levels"])
                    except Exception:
                        user_complexities = None

            if not sub_rows:
                self.send_json_response(200, {
                    "success": True,
                    "articles": [],
                    "total": 0,
                    "limit": limit,
                    "offset": offset,
                    "hasMore": False,
                    "topicCounts": {},
                    "tab": tab_raw,
                    "noSubscriptions": True
                })
                return

            for sr in sub_rows:
                stype = sr["target_type"]
                sid = sr["target_id"]
                stitle = sr["target_title"]
                if stype == "author":
                    sub_authors.add(sid)
                elif stype == "topic":
                    sub_topics.add(sid)
                    sub_topics_titles[sid] = stitle
                elif stype == "tag":
                    norm_t = normalize_keyword(sid).lstrip('#').strip().lower()
                    sub_tags.add(norm_t)
                    sub_tags_titles[norm_t] = stitle
                elif stype == "club":
                    sub_clubs.add(sid)
                    sub_clubs_titles[sid] = stitle
                elif stype == "company":
                    sub_companies.add(sid)
                    sub_companies_titles[sid] = stitle

        is_publications_tab = tab in ("all", "publications", "pubs", "articles", "focus", "top", "new")
        is_questions_tab = (tab == "questions")

        # Determine effective types filter
        if is_questions_tab:
            allowed_types = {"question"}
        elif is_publications_tab:
            if types_filter and types_filter != "all":
                requested = set([t.strip().lower() for t in types_filter.split(",") if t.strip()])
                allowed_types = {t for t in requested if t not in ("question", "questions")}
                if not allowed_types:
                    allowed_types = {"__none__"}
            else:
                allowed_types = {"publication", "article", "post", "news"}
        elif types_filter and types_filter != "all":
            allowed_types = set([t.strip().lower() for t in types_filter.split(",") if t.strip()])
        elif tab in ("subscriptions", "my") and user_types:
            allowed_types = set([t.strip().lower() for t in user_types if t.strip()])
        else:
            allowed_types = None

        if allowed_types and "all" in allowed_types and not is_publications_tab and not is_questions_tab:
            allowed_types = None

        # Determine effective complexity filter
        if complexity_filter and complexity_filter != "all":
            allowed_complexities = set([c.strip().lower() for c in complexity_filter.split(",") if c.strip()])
        elif tab in ("subscriptions", "my") and user_complexities:
            allowed_complexities = set([c.strip().lower() for c in user_complexities if c.strip()])
        else:
            allowed_complexities = None

        if allowed_complexities and "all" in allowed_complexities:
            allowed_complexities = None

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        cutoff_72h_dt = now_utc - datetime.timedelta(hours=72)
        cutoff_72h_str = cutoff_72h_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                query_sql = "SELECT * FROM moderation_submissions WHERE status = 'approved'"
                query_params = []
                if company_filter:
                    query_sql += " AND json_extract(publication_settings, '$.companyId') = ?"
                    query_params.append(company_filter)
                elif is_company_filter:
                    query_sql += " AND json_extract(publication_settings, '$.companyId') IS NOT NULL AND json_extract(publication_settings, '$.companyId') != ''"
                query_sql += " ORDER BY created_at DESC"
                cur.execute(query_sql, tuple(query_params))
                rows = cur.fetchall()

                # Pre-fetch counts for likes, saves and comments
                cur.execute("SELECT article_id, COUNT(*) AS cnt FROM article_likes GROUP BY article_id")
                likes_counts = {r["article_id"]: r["cnt"] for r in cur.fetchall()}

                cur.execute("SELECT article_id, COUNT(*) AS cnt FROM article_saves GROUP BY article_id")
                saves_counts = {r["article_id"]: r["cnt"] for r in cur.fetchall()}

                cur.execute("SELECT article_id, COALESCE(SUM(value), 0) AS score FROM article_votes GROUP BY article_id")
                article_scores = {r["article_id"]: r["score"] for r in cur.fetchall()}

                cur.execute("SELECT article_id, COUNT(*) AS cnt FROM article_comments WHERE status = 'published' AND comment_type = 'comment' GROUP BY article_id")
                comments_counts = {r["article_id"]: r["cnt"] for r in cur.fetchall()}

                cur.execute("SELECT article_id, COUNT(*) AS cnt FROM article_comments WHERE status = 'published' AND comment_type = 'answer' GROUP BY article_id")
                answers_counts = {r["article_id"]: r["cnt"] for r in cur.fetchall()}

                cur.execute("SELECT DISTINCT article_id FROM article_comments WHERE status = 'published' AND is_solution = 1")
                solved_article_ids = {r["article_id"] for r in cur.fetchall()}

                comment_search_map = {}
                if search_query:
                    cur.execute("SELECT article_id, content FROM article_comments WHERE status = 'published' AND comment_type = 'answer'")
                    for cr in cur.fetchall():
                        aid = cr["article_id"]
                        if aid not in comment_search_map:
                            comment_search_map[aid] = []
                        comment_search_map[aid].append(cr["content"])

                # 72h window counts for focus gravity score
                cur.execute("SELECT article_id, COUNT(*) AS cnt FROM article_likes WHERE created_at >= ? GROUP BY article_id", (cutoff_72h_str,))
                likes_72h_counts = {r["article_id"]: r["cnt"] for r in cur.fetchall()}

                cur.execute("SELECT article_id, COUNT(*) AS cnt FROM article_comments WHERE status = 'published' AND created_at >= ? GROUP BY article_id", (cutoff_72h_str,))
                comments_72h_counts = {r["article_id"]: r["cnt"] for r in cur.fetchall()}

                current_user = self.get_current_user()
                user_likes = set()
                user_saves = set()
                user_reports = set()
                user_votes = {}
                exc_authors = set()
                exc_topics = set()
                exc_tags = set()
                exc_clubs = set()
                exc_companies = set()
                if current_user:
                    cur.execute("SELECT article_id FROM article_likes WHERE user_id = ?", (current_user["id"],))
                    user_likes = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id FROM article_saves WHERE user_id = ?", (current_user["id"],))
                    user_saves = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id FROM article_reports WHERE user_id = ?", (current_user["id"],))
                    user_reports = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id, value FROM article_votes WHERE user_id = ?", (current_user["id"],))
                    user_votes = {r["article_id"]: r["value"] for r in cur.fetchall()}
                    cur.execute("SELECT target_type, target_id FROM user_feed_exceptions WHERE user_id = ?", (current_user["id"],))
                    for r in cur.fetchall():
                        ttype = r["target_type"]
                        tid = r["target_id"]
                        if ttype == "author":
                            exc_authors.add(tid)
                        elif ttype == "topic":
                            exc_topics.add(tid)
                        elif ttype == "tag":
                            exc_tags.add(normalize_keyword(tid).lstrip('#').strip().lower())
                        elif ttype == "club":
                            exc_clubs.add(tid)
                        elif ttype == "company":
                            exc_companies.add(tid)
        finally:
            conn.close()

        topic_counts = {}
        filtered_articles = []
        seen_article_ids = set()

        for row in rows:
            art_id = row["id"]
            if art_id in seen_article_ids:
                continue

            try:
                settings = json.loads(row["publication_settings"]) if row["publication_settings"] else {}
            except Exception:
                settings = {}

            draft_id = row["draft_id"]
            raw_art_type = (settings.get("materialType") or settings.get("type") or "publication").strip().lower()
            if raw_art_type in ("article", "post", "news", "pubs"):
                art_type = "publication"
            else:
                art_type = raw_art_type

            if is_questions_tab and art_type != "question":
                continue
            if is_publications_tab and art_type == "question":
                continue

            topics = settings.get("topics") or []
            for t in topics:
                topic_counts[t] = topic_counts.get(t, 0) + 1

            # Author metadata
            raw_author = settings.get("author")
            if isinstance(raw_author, dict):
                author_name = raw_author.get("name") or (
                    "Пользователь #" + row["author_id"][:6] if row["author_id"] else "Автор SmartContractum"
                )
            else:
                author_name = raw_author or (
                    "Пользователь #" + row["author_id"][:6] if row["author_id"] else "Автор SmartContractum"
                )
            author_initials = settings.get("authorInitials") or (
                "".join([part[0].upper() for part in str(author_name).split()[:2]]) if author_name else "SC"
            )
            author_role = settings.get("authorRole") or ""
            keywords = settings.get("keywords") or []
            norm_kws = [normalize_keyword(k).lstrip('#').strip().lower() for k in keywords]

            art_club_id = settings.get("clubId")
            art_company_id = settings.get("companyId")

            # Club filter
            if club_filter and art_club_id != club_filter:
                continue

            # Company filter
            if is_company_filter and not art_company_id:
                continue
            if company_filter and art_company_id != company_filter:
                continue

            # Priority of exceptions:
            # Publication is hidden if author, topic, keyword, club, or company is in user exceptions.
            # Applies to all feed modes and searches. Does NOT hide when tab=saved or bookmarks (allowed_ids).
            is_excluded = (
                (row["author_id"] in exc_authors) or
                (author_name in exc_authors) or
                any(t in exc_topics for t in topics) or
                any(nk in exc_tags for nk in norm_kws) or
                (art_club_id and art_club_id in exc_clubs) or
                (art_company_id and art_company_id in exc_companies)
            )
            if is_excluded and tab != "saved" and allowed_ids is None:
                continue

            # Period filtering
            created_at_dt = None
            try:
                created_at_dt = datetime.datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            except Exception:
                pass

            if (period_filter == "day" or (tab == "top" and period_filter == "day")) and created_at_dt:
                if (now_utc - created_at_dt).total_seconds() > 86400:
                    continue
            elif (period_filter == "week" or (tab == "top" and period_filter == "week")) and created_at_dt:
                if (now_utc - created_at_dt).total_seconds() > 7 * 86400:
                    continue
            elif (period_filter == "month" or (tab == "top" and period_filter == "month")) and created_at_dt:
                if (now_utc - created_at_dt).total_seconds() > 30 * 86400:
                    continue
            elif period_filter == "year" and created_at_dt:
                if (now_utc - created_at_dt).total_seconds() > 365 * 86400:
                    continue
            elif (period_filter == "custom" or date_from_str or date_to_str) and created_at_dt:
                if date_from_str:
                    try:
                        df = datetime.date.fromisoformat(date_from_str)
                        df_dt = datetime.datetime(df.year, df.month, df.day, 0, 0, 0, tzinfo=datetime.timezone.utc)
                        if created_at_dt < df_dt:
                            continue
                    except Exception:
                        pass
                if date_to_str:
                    try:
                        dt = datetime.date.fromisoformat(date_to_str)
                        dt_dt = datetime.datetime(dt.year, dt.month, dt.day, 23, 59, 59, 999999, tzinfo=datetime.timezone.utc)
                        if created_at_dt > dt_dt:
                            continue
                    except Exception:
                        pass

            # IDs filtering (e.g. bookmarks)
            if allowed_ids is not None:
                if art_id not in allowed_ids and draft_id not in allowed_ids:
                    continue

            # Material type filtering (Issue #61, #162: publication or question)
            if is_questions_tab:
                if art_type != "question":
                    continue
                a_cnt = answers_counts.get(art_id, 0)
                is_sol = (art_id in solved_article_ids)
                if question_status == "unanswered" and a_cnt > 0:
                    continue
                if question_status == "solved" and not is_sol:
                    continue
            elif is_publications_tab:
                if art_type == "question":
                    continue
                if allowed_types is not None:
                    norm_allowed = []
                    for at in allowed_types:
                        at_norm = at.strip().lower()
                        if at_norm in ("article", "post", "news", "publication", "publications", "pubs"):
                            at_norm = "publication"
                        norm_allowed.append(at_norm)
                    if art_type not in norm_allowed:
                        continue
            elif allowed_types is not None:
                norm_allowed = []
                for at in allowed_types:
                    at_norm = at.strip().lower()
                    if at_norm in ("article", "post", "news", "publication", "publications", "pubs"):
                        at_norm = "publication"
                    elif at_norm in ("question", "questions"):
                        at_norm = "question"
                    norm_allowed.append(at_norm)
                if art_type not in norm_allowed:
                    continue

            # Complexity filtering
            compl = (settings.get("complexity") or "").strip().lower()
            if allowed_complexities is not None:
                is_unspecified = compl in ("", "none", "unspecified")
                if is_unspecified:
                    if "unspecified" not in allowed_complexities and "none" not in allowed_complexities:
                        continue
                else:
                    if compl not in allowed_complexities:
                        continue

            # Topic filtering
            if req_topics is not None:
                if not any(t in req_topics for t in topics):
                    continue

            # Audience filtering (multi-selection support)
            target_audience = settings.get("targetAudience") or ""
            if allowed_audiences is not None:
                if target_audience not in allowed_audiences:
                    continue

            # Format filtering (multi-selection support)
            fmt = settings.get("format") or ""
            if allowed_formats is not None:
                if fmt not in allowed_formats:
                    continue

            # Search query filtering across title, author, role, description, keywords, club, company, body, and comments/answers
            title = row["title"] or ""
            desc = settings.get("description") or ""
            club_title = settings.get("clubTitle") or ""
            company_name = settings.get("companyName") or ""
            article_text = extract_article_text(row["article_html"] or "")

            matched_answer_snippet = None
            if search_query:
                search_haystack = f"{title} {author_name} {author_role} {club_title} {company_name} {desc} {' '.join(keywords)} {article_text}".lower()
                words = search_query.split()
                matches_main = all(w in search_haystack for w in words)
                matches_comment = False

                if not matches_main and is_questions_tab:
                    # Check comments/answers
                    for c_text in comment_search_map.get(art_id, []):
                        c_lower = c_text.lower()
                        if all(w in c_lower for w in words):
                            matches_comment = True
                            first_w = words[0]
                            pos = c_lower.find(first_w)
                            sp = max(0, pos - 40)
                            ep = min(len(c_text), pos + len(first_w) + 60)
                            matched_answer_snippet = ("..." if sp > 0 else "") + c_text[sp:ep].strip() + ("..." if ep < len(c_text) else "")
                            break

                if not matches_main and not matches_comment:
                    continue

            # Check subscription filter for "subscriptions" / "my" feed
            subscription_reason = None
            if tab in ("subscriptions", "my"):
                if row["author_id"] in sub_authors or author_name in sub_authors:
                    subscription_reason = f"Вы подписаны на автора {author_name}"
                elif art_club_id and art_club_id in sub_clubs:
                    c_title = sub_clubs_titles.get(art_club_id) or club_title or art_club_id
                    subscription_reason = f"Вы подписаны на клуб «{c_title}»"
                elif art_company_id and art_company_id in sub_companies:
                    cp_name = sub_companies_titles.get(art_company_id) or company_name or art_company_id
                    subscription_reason = f"Вы подписаны на компанию «{cp_name}»"
                else:
                    matched_topic = next((t for t in topics if t in sub_topics), None)
                    if matched_topic:
                        topic_title = sub_topics_titles.get(matched_topic) or TOPICS_TITLE_MAP.get(matched_topic, matched_topic)
                        subscription_reason = f"Вы подписаны на тему «{topic_title}»"
                    else:
                        matched_tag = next((nk for nk in norm_kws if nk in sub_tags), None)
                        if matched_tag:
                            tag_title = sub_tags_titles.get(matched_tag) or matched_tag
                            subscription_reason = f"Вы подписаны на #{tag_title}"

                if not subscription_reason:
                    continue

            reading_time, reading_minutes = calculate_reading_time(row["article_html"] or "")

            # Focus gravity formula: (likes_72h * 2 + comments_72h * 3) / ((age_hours + 2.0) ** 1.5)
            age_hours = max(0.0, (now_utc - created_at_dt).total_seconds() / 3600.0) if created_at_dt else 100.0
            l_72 = likes_72h_counts.get(art_id, 0)
            c_72 = comments_72h_counts.get(art_id, 0)
            focus_score = (l_72 * 2.0 + c_72 * 3.0) / ((age_hours + 2.0) ** 1.5)

            seen_article_ids.add(art_id)
            filtered_articles.append({
                "id": row["id"],
                "draftId": row["draft_id"],
                "title": row["title"],
                "authorId": row["author_id"],
                "author_id": row["author_id"],
                "author": author_name,
                "authorInitials": author_initials,
                "authorRole": author_role,
                "date": format_date_ru(row["created_at"]),
                "createdAt": row["created_at"],
                "description": desc,
                "coverImage": settings.get("coverImage") or None,
                "coverPosition": resolve_cover_position(settings),
                "focalPoint": resolve_cover_position(settings),
                "objectPosition": resolve_cover_position(settings),
                "isDemo": bool(settings.get("isDemo") or row["id"].startswith("art-0")),
                "topics": topics,
                "topic": topics[0] if topics else "",
                "targetAudience": target_audience,
                "format": fmt,
                "complexity": compl,
                "keywords": keywords,
                "readingTime": reading_time,
                "readingMinutes": reading_minutes,
                "subscriptionReason": subscription_reason,
                "likesCount": likes_counts.get(art_id, 0),
                "hasLiked": art_id in user_likes,
                "savesCount": saves_counts.get(art_id, 0),
                "hasSaved": art_id in user_saves,
                "isSaved": art_id in user_saves,
                "hasReported": (art_id in user_reports or (draft_id and draft_id in user_reports)),
                "isReported": (art_id in user_reports or (draft_id and draft_id in user_reports)),
                "score": article_scores.get(art_id, 0),
                "myVote": user_votes.get(art_id, 0),
                "canVote": bool(current_user and row["status"] == "approved" and row["author_id"] != current_user["id"]),
                "isAuthor": bool(current_user and row["author_id"] == current_user["id"]),
                "commentsCount": comments_counts.get(art_id, 0),
                "answersCount": answers_counts.get(art_id, 0),
                "discussionCount": comments_counts.get(art_id, 0) + answers_counts.get(art_id, 0),
                "hasSolution": art_id in solved_article_ids,
                "matchedAnswerSnippet": matched_answer_snippet,
                "materialType": art_type,
                "material_type": art_type,
                "type": art_type,
                "companyId": art_company_id,
                "companyName": company_name or None,
                "clubId": art_club_id,
                "clubTitle": club_title or None,
                "focusScore": round(focus_score, 4)
            })

        # Apply sorting logic
        if has_explicit_sort:
            if sort_by == "rating":
                filtered_articles.sort(key=lambda a: (a.get("score", 0), a.get("createdAt", ""), a.get("id", "")), reverse=True)
            elif sort_by == "popular":
                filtered_articles.sort(key=lambda a: (a.get("likesCount", 0), a.get("createdAt", ""), a.get("id", "")), reverse=True)
            elif sort_by == "discussed":
                filtered_articles.sort(key=lambda a: (a.get("discussionCount", a.get("commentsCount", 0)), a.get("createdAt", "")), reverse=True)
            elif sort_by in ("oldest", "asc"):
                filtered_articles.reverse()
            elif sort_by in ("newest", "desc"):
                filtered_articles.sort(key=lambda a: (a.get("createdAt", ""), a.get("id", "")), reverse=True)
        else:
            if tab == "focus":
                # Default "В фокусе": gravity popularity with fallback to createdAt
                filtered_articles.sort(key=lambda a: (a.get("focusScore", 0.0), a.get("createdAt", ""), a.get("id", "")), reverse=True)
            elif tab == "top":
                # "Топ": sort by (score, commentsCount, createdAt, id) DESC strictly
                filtered_articles.sort(key=lambda a: (a.get("score", 0), a.get("commentsCount", 0), a.get("createdAt", ""), a.get("id", "")), reverse=True)
            elif tab == "new":
                # "Новое": strict chronological DESC
                filtered_articles.sort(key=lambda a: (a.get("createdAt", ""), a.get("id", "")), reverse=True)
            elif tab in ("subscriptions", "my"):
                # "Подписки": chronological DESC
                filtered_articles.sort(key=lambda a: (a.get("createdAt", ""), a.get("id", "")), reverse=True)
            else:
                # "Все публикации", "Вопросы": newest by default
                filtered_articles.sort(key=lambda a: (a.get("createdAt", ""), a.get("id", "")), reverse=True)

        total = len(filtered_articles)
        paged_articles = filtered_articles[offset : offset + limit]
        has_more = (offset + limit) < total

        self.send_json_response(200, {
            "success": True,
            "articles": paged_articles,
            "items": paged_articles,
            "total": total,
            "limit": limit,
            "offset": offset,
            "hasMore": has_more,
            "topicCounts": topic_counts,
            "tab": tab_raw,
            "noSubscriptions": False
        })

    def handle_serve_media(self, parsed_url):
        """
        GET /media/<filename>
        Serves stored media files with strict path-traversal prevention,
        proper Content-Type header, and long-term caching headers.
        """
        media_root = getattr(self.server, "media_dir", MEDIA_DIR)
        rel_path = parsed_url.path[len("/media/"):].lstrip("/")
        if not rel_path or ".." in rel_path:
            self.send_json_response(400, {"success": False, "error": "Invalid media path"})
            return

        full_path = os.path.abspath(os.path.join(media_root, rel_path))
        if not full_path.startswith(os.path.abspath(media_root)):
            self.send_json_response(403, {"success": False, "error": "Access denied"})
            return

        if not os.path.isfile(full_path):
            self.send_json_response(404, {"success": False, "error": "Media not found"})
            return

        ext = os.path.splitext(full_path)[1].lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".svg": "image/svg+xml"
        }
        content_type = mime_types.get(ext, "application/octet-stream")

        try:
            with open(full_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Disposition", "inline")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_json_response(500, {"success": False, "error": f"Failed to read media: {str(e)}"})

    def handle_media_upload(self):
        """
        POST /api/media/upload
        Accepts:
          - JSON: { "image": "data:image/..." } or { "coverImage": "..." }
          - Raw binary image bytes
        Validates via image_decoder and saves to data/media/<hash>.<ext>.
        Returns { success: True, url: "/media/...", meta: { ... } }
        """
        raw_body = self.read_request_body(MAX_MEDIA_BODY_BYTES)
        if raw_body is None:
            return

        if len(raw_body) == 0:
            self.send_json_response(400, {"success": False, "error": "Пустое тело запроса"})
            return

        content_type = self.headers.get("Content-Type", "")
        media_root = getattr(self.server, "media_dir", MEDIA_DIR)

        if "application/json" in content_type:
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                self.send_json_response(400, {"success": False, "error": f"Невалидный JSON: {str(e)}"})
                return
            except Exception as e:
                self.send_json_response(400, {"success": False, "error": f"Ошибка обработки JSON: {str(e)}"})
                return

            if not isinstance(payload, dict):
                self.send_json_response(400, {"success": False, "error": "Тело запроса должно быть JSON-объектом."})
                return

            image_val = payload.get("image") or payload.get("coverImage") or payload.get("file")
            if not image_val or not isinstance(image_val, str):
                self.send_json_response(400, {"success": False, "error": "Поле image должно содержать Data URI или base64"})
                return
            res = validate_cover_image(image_val, target_media_dir=media_root)
            if not res.is_valid:
                self.send_json_response(400, {"success": False, "error": res.error_msg})
                return
            self.send_json_response(200, {
                "success": True,
                "url": res.saved_url,
                "meta": res.meta
            })
            return

        if "multipart/form-data" in content_type:
            boundary_match = re.search(r'boundary=([^\s;]+)', content_type)
            if boundary_match:
                boundary = boundary_match.group(1).strip('"\'').encode('ascii')
                parts = raw_body.split(b'--' + boundary)
                file_bytes = None
                for part in parts:
                    if b'filename=' in part:
                        header_end = part.find(b'\r\n\r\n')
                        if header_end != -1:
                            file_bytes = part[header_end + 4:].rstrip(b'\r\n-')
                            break
                        header_end = part.find(b'\n\n')
                        if header_end != -1:
                            file_bytes = part[header_end + 2:].rstrip(b'\r\n-')
                            break
                if file_bytes:
                    raw_body = file_bytes

        # Direct binary image upload
        ok, err, meta = image_decoder.decode_and_validate_image(raw_body)
        if not ok:
            self.send_json_response(400, {"success": False, "error": err or "Невалидный формат изображения"})
            return

        ext = meta.get("format", "jpg")
        saved_url = save_media_file(raw_body, ext, media_dir=media_root)
        self.send_json_response(200, {
            "success": True,
            "url": saved_url,
            "meta": meta
        })

    def handle_comment_solution_toggle(self, art_id: str, comm_id: str):
        """
        POST /api/articles/<art_id>/comments/<comm_id>/solution or POST /api/comments/<comm_id>/solution
        Allows the question author to mark or unmark an answer as the accepted solution.
        Requires authentication. Enforces 403 if user is not author of the question (admin bypass removed).
        """
        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для отметки решения необходимо авторизоваться",
                "requireAuth": True
            })
            return

        if not comm_id:
            comm_id = payload.get("commentId") or payload.get("comment_id") or ""

        if not comm_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор комментария"
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM article_comments WHERE id = ?", (comm_id,))
                comment = cur.fetchone()
                if not comment:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Ответ не найден"
                    })
                    return

                actual_art_id = comment["article_id"]
                cur.execute("SELECT * FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (actual_art_id, actual_art_id))
                art_row = cur.fetchone()
                if not art_row:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Вопрос не найден"
                    })
                    return

                if art_id:
                    cur.execute("SELECT id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (art_id, art_id))
                    url_art_row = cur.fetchone()
                    canonical_url_id = url_art_row["id"] if url_art_row else art_id
                    if canonical_url_id != actual_art_id:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Идентификатор публикации не совпадает с ответом"
                        })
                        return

                material_type = "article"
                try:
                    art_settings = json.loads(art_row["publication_settings"]) if art_row["publication_settings"] else {}
                    material_type = (art_settings.get("materialType") or art_settings.get("type") or "article").strip().lower()
                except Exception:
                    pass

                if material_type != "question":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Статус решения может быть установлен только для вопросов (materialType = 'question')."
                    })
                    return

                is_author = (user.get("id") == art_row["author_id"])
                if not is_author:
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Только автор вопроса может отмечать решение"
                    })
                    return

                comm_type = (comment["comment_type"] if "comment_type" in comment.keys() else "").strip().lower()
                comm_status = (comment["status"] if "status" in comment.keys() else "").strip().lower()
                if comm_type != "answer" or comm_status != "published":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Статус решения может быть установлен только ответу (comment_type = 'answer')."
                    })
                    return

                is_sol_val = payload.get("isSolution") if "isSolution" in payload else payload.get("is_solution")
                current_is_sol = int(comment["is_solution"] or 0)
                if is_sol_val is not None:
                    target_is_sol = bool(is_sol_val)
                else:
                    target_is_sol = (current_is_sol == 0)

                if target_is_sol:
                    if current_is_sol != 1:
                        cur.execute("UPDATE article_comments SET is_solution = 0 WHERE article_id = ? AND is_solution = 1", (actual_art_id,))
                        cur.execute("UPDATE article_comments SET is_solution = 1 WHERE id = ?", (comm_id,))

                        ans_author_id = comment["user_id"]
                        if ans_author_id and ans_author_id != user.get("id"):
                            notif_id = f"notif_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
                            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            art_title = art_row["title"] or "Вопрос"
                            cur.execute("""
                                INSERT INTO user_notifications (
                                    id, user_id, actor_id, actor_name, article_id, comment_id, type, title, message, is_read, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, 'solution_accepted', ?, ?, 0, ?)
                            """, (
                                notif_id,
                                ans_author_id,
                                user.get("id"),
                                user.get("name") or "Автор вопроса",
                                actual_art_id,
                                comm_id,
                                "Ваш ответ отмечен как решение",
                                f"Автор вопроса «{art_title[:60]}» отметил ваш ответ как решение",
                                now_iso
                            ))
                else:
                    if current_is_sol == 1:
                        cur.execute("UPDATE article_comments SET is_solution = 0 WHERE id = ?", (comm_id,))

            self.send_json_response(200, {
                "success": True,
                "isSolution": target_is_sol,
                "is_solution": target_is_sol,
                "commentId": comm_id,
                "articleId": actual_art_id
            })
        finally:
            conn.close()

    handle_post_article_solution = handle_comment_solution_toggle

    def handle_get_notifications(self):
        """
        GET /api/notifications
        Returns list of in-app notifications for the logged in user, plus unreadCount.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(200, {
                "success": True,
                "notifications": [],
                "unreadCount": 0
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, user_id, actor_id, actor_name, article_id, comment_id, type, title, message, is_read, created_at
                    FROM user_notifications
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 50
                """, (user["id"],))
                rows = cur.fetchall()

                cur.execute("""
                    SELECT COUNT(*) AS unread_cnt
                    FROM user_notifications
                    WHERE user_id = ? AND is_read = 0
                """, (user["id"],))
                unread_cnt = cur.fetchone()["unread_cnt"]

            notifs = []
            for r in rows:
                notifs.append({
                    "id": r["id"],
                    "userId": r["user_id"],
                    "actorId": r["actor_id"],
                    "actorName": r["actor_name"],
                    "articleId": r["article_id"],
                    "commentId": r["comment_id"],
                    "type": r["type"],
                    "title": r["title"],
                    "message": r["message"],
                    "isRead": bool(r["is_read"]),
                    "createdAt": r["created_at"]
                })

            self.send_json_response(200, {
                "success": True,
                "notifications": notifs,
                "unreadCount": unread_cnt
            })
        finally:
            conn.close()

    def handle_post_notifications_read(self):
        """
        POST /api/notifications/read
        Marks one or all notifications as read.
        """
        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для управления уведомлениями необходимо войти",
                "requireAuth": True
            })
            return

        notif_id = payload.get("notificationId") or payload.get("id")
        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                if notif_id:
                    cur.execute("UPDATE user_notifications SET is_read = 1 WHERE user_id = ? AND id = ?", (user["id"], notif_id))
                else:
                    cur.execute("UPDATE user_notifications SET is_read = 1 WHERE user_id = ?", (user["id"],))

                cur.execute("SELECT COUNT(*) AS unread_cnt FROM user_notifications WHERE user_id = ? AND is_read = 0", (user["id"],))
                unread_cnt = cur.fetchone()["unread_cnt"]

            self.send_json_response(200, {
                "success": True,
                "unreadCount": unread_cnt
            })
        finally:
            conn.close()

    def handle_get_unanswered_questions(self):
        """
        GET /api/questions/unanswered
        Returns up to 3 approved questions that have 0 published answers.
        """
        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT ms.id, ms.draft_id, ms.title, ms.publication_settings, ms.created_at,
                           (SELECT COUNT(*) FROM article_comments ac WHERE ac.article_id = ms.id AND ac.status = 'published' AND ac.comment_type = 'answer') AS ans_cnt
                    FROM moderation_submissions ms
                    WHERE ms.status = 'approved'
                      AND (
                        json_extract(ms.publication_settings, '$.materialType') = 'question'
                        OR json_extract(ms.publication_settings, '$.type') = 'question'
                      )
                      AND ans_cnt = 0
                    ORDER BY ms.created_at DESC
                    LIMIT 3
                """)
                rows = cur.fetchall()

            questions = []
            for r in rows:
                try:
                    st = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                except Exception:
                    st = {}
                questions.append({
                    "id": r["id"],
                    "title": r["title"],
                    "createdAt": r["created_at"],
                    "date": format_date_ru(r["created_at"]),
                    "topic": (st.get("topics") or [""])[0] if st.get("topics") else "",
                    "answersCount": 0,
                    "material_type": "question",
                    "materialType": "question"
                })

            self.send_json_response(200, {
                "success": True,
                "questions": questions,
                "items": questions
            })
        finally:
            conn.close()

    def resolve_user_identity(self, cur, user_id: str, p_row=None) -> Dict[str, Any]:
        """
        Consistent user identity resolution across user profiles, sessions, and comments.
        """
        if p_row is None:
            cur.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
            p_row = cur.fetchone()

        author_name = p_row["name"] if p_row and p_row["name"] else None
        if not author_name:
            cur.execute("SELECT user_name FROM sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
            sn_row = cur.fetchone()
            if sn_row and sn_row["user_name"]:
                author_name = sn_row["user_name"]
        if not author_name:
            cur.execute("SELECT author_name FROM article_comments WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
            cn_row = cur.fetchone()
            if cn_row and cn_row["author_name"]:
                author_name = cn_row["author_name"]
        if not author_name:
            author_name = f"Пользователь #{user_id[:6]}"

        author_avatar = p_row["avatar"] if p_row and p_row["avatar"] else None
        company = p_row["company"] if p_row and p_row["company"] else ""
        specialization = p_row["specialization"] if p_row and p_row["specialization"] else ""
        author_initials = "".join([part[0].upper() for part in str(author_name).split()[:2]]) if author_name else "SC"

        return {
            "name": author_name,
            "avatar": author_avatar,
            "company": company,
            "specialization": specialization,
            "initials": author_initials,
        }

    def handle_get_user_profile(self, user_id: str):
        """
        GET /api/users/<user_id>
        Returns profile info, stats, publications, and subscription status.
        """
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "Не указан user_id"})
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
                p_row = cur.fetchone()

                # User existence check: user_profiles, sessions, moderation_submissions, article_comments
                user_exists = (p_row is not None)
                if not user_exists:
                    cur.execute("SELECT 1 FROM sessions WHERE user_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True

                if not user_exists:
                    cur.execute("SELECT 1 FROM moderation_submissions WHERE author_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True

                if not user_exists:
                    cur.execute("SELECT 1 FROM article_comments WHERE user_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True

                if not user_exists:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Пользователь не найден",
                        "code": "USER_NOT_FOUND"
                    })
                    return

                cur.execute("""
                    SELECT id, draft_id, title, publication_settings, created_at, article_html AS content
                    FROM moderation_submissions
                    WHERE author_id = ? AND status = 'approved'
                    ORDER BY created_at DESC
                """, (user_id,))
                pub_rows = cur.fetchall()

                cur.execute("""
                    SELECT COUNT(DISTINCT ac.id) AS total_answers,
                           SUM(CASE WHEN ac.is_solution = 1 THEN 1 ELSE 0 END) AS total_solutions
                    FROM article_comments ac
                    JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                    WHERE ac.user_id = ?
                      AND ac.status = 'published'
                      AND ac.comment_type = 'answer'
                      AND ms.status = 'approved'
                      AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question'
                """, (user_id,))
                c_stats = cur.fetchone()

                cur.execute("""
                    SELECT COALESCE(SUM(v.value), 0) AS pub_score
                    FROM article_votes v
                    WHERE v.article_id IN (
                        SELECT id FROM moderation_submissions WHERE author_id = ? AND status = 'approved'
                        UNION
                        SELECT draft_id FROM moderation_submissions WHERE author_id = ? AND status = 'approved' AND draft_id IS NOT NULL
                    )
                """, (user_id, user_id))
                pub_score = cur.fetchone()["pub_score"] or 0

                cur.execute("""
                    SELECT COALESCE(SUM(v.value), 0) AS comm_score
                    FROM comment_votes v
                    WHERE v.comment_id IN (
                        SELECT ac.id
                        FROM article_comments ac
                        JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                        WHERE ac.user_id = ?
                          AND ac.status = 'published'
                          AND ms.status = 'approved'
                    )
                """, (user_id,))
                comm_score = cur.fetchone()["comm_score"] or 0

                total_rating = int(pub_score) + int(comm_score)

                # Followers & following counts
                cur.execute("""
                    SELECT COUNT(*) AS cnt FROM user_subscriptions
                    WHERE target_type = 'author' AND target_id = ?
                """, (user_id,))
                followers_count = cur.fetchone()["cnt"] or 0

                cur.execute("""
                    SELECT COUNT(*) AS cnt FROM user_subscriptions
                    WHERE user_id = ? AND target_type = 'author'
                """, (user_id,))
                following_count = cur.fetchone()["cnt"] or 0

                # Registration / creation date (stable, do not fabricate today's timestamp)
                created_at_val = None
                if p_row and p_row["created_at"]:
                    created_at_val = p_row["created_at"]
                else:
                    cur.execute("SELECT created_at FROM sessions WHERE user_id = ? ORDER BY created_at ASC LIMIT 1", (user_id,))
                    s_row = cur.fetchone()
                    if s_row and s_row["created_at"]:
                        created_at_val = s_row["created_at"]
                    else:
                        cur.execute("SELECT created_at FROM moderation_submissions WHERE author_id = ? ORDER BY created_at ASC LIMIT 1", (user_id,))
                        m_row = cur.fetchone()
                        if m_row and m_row["created_at"]:
                            created_at_val = m_row["created_at"]
                        else:
                            cur.execute("SELECT created_at FROM article_comments WHERE user_id = ? ORDER BY created_at ASC LIMIT 1", (user_id,))
                            c_row = cur.fetchone()
                            if c_row and c_row["created_at"]:
                                created_at_val = c_row["created_at"]

                # Author identity resolution
                ident = self.resolve_user_identity(cur, user_id, p_row)
                author_name = ident["name"]
                author_avatar = ident["avatar"]
                author_initials = ident["initials"]
                company = ident["company"]
                specialization = ident["specialization"]

                curr_user = self.get_current_user()
                is_sub = False
                if curr_user:
                    cur.execute(
                        "SELECT id FROM user_subscriptions WHERE user_id = ? AND target_type = 'author' AND target_id = ?",
                        (curr_user["id"], user_id)
                    )
                    is_sub = bool(cur.fetchone())

            specialization = p_row["specialization"].strip() if p_row and p_row["specialization"] else ""
            company = p_row["company"] if p_row and p_row["company"] else ""
            bio = p_row["bio"] if p_row and p_row["bio"] else ""
            avatar = p_row["avatar"] if p_row and p_row["avatar"] else None
            website = ""
            if p_row:
                try:
                    website = p_row["website"] or ""
                except (IndexError, KeyError):
                    website = ""

            pubs = []
            questions_count = 0
            publications_count = 0
            for pr in pub_rows:
                try:
                    pst = json.loads(pr["publication_settings"]) if pr["publication_settings"] else {}
                except Exception:
                    pst = {}
                mtype = pst.get("materialType") or pst.get("type") or "article"
                if mtype == "question":
                    questions_count += 1
                else:
                    publications_count += 1

                if len(pubs) < 10:
                    pubs.append({
                        "id": pr["id"],
                        "title": pr["title"],
                        "materialType": mtype,
                        "createdAt": pr["created_at"],
                        "date": format_date_ru(pr["created_at"])
                    })

            # Top contributions: 2-3 items with highest rating across approved publications and solutions
            top_contributions = []
            for pr in pub_rows:
                try:
                    pst = json.loads(pr["publication_settings"]) if pr["publication_settings"] else {}
                except Exception:
                    pst = {}
                mtype = (pst.get("materialType") or pst.get("type") or "publication").strip().lower()
                is_q = (mtype == "question")

                cur.execute("""
                    SELECT COALESCE(SUM(value), 0) AS val FROM article_votes
                    WHERE article_id = ? OR (? IS NOT NULL AND article_id = ?)
                """, (pr["id"], pr["draft_id"], pr["draft_id"]))
                p_rating = cur.fetchone()["val"] or 0

                cur.execute("""
                    SELECT COUNT(DISTINCT id) AS cnt FROM article_comments
                    WHERE (article_id = ? OR (? IS NOT NULL AND article_id = ?)) AND status = 'published'
                """, (pr["id"], pr["draft_id"], pr["draft_id"]))
                c_cnt = cur.fetchone()["cnt"] or 0

                top_contributions.append({
                    "id": pr["id"],
                    "type": "question" if is_q else "publication",
                    "materialType": "question" if is_q else "publication",
                    "material_type": "question" if is_q else "publication",
                    "title": pr["title"],
                    "contentSnippet": make_content_snippet(pr["content"]),
                    "rating": int(p_rating),
                    "score": int(p_rating),
                    "commentsCount": int(c_cnt) if not is_q else 0,
                    "answersCount": int(c_cnt) if is_q else 0,
                    "isSolution": False,
                    "createdAt": pr["created_at"],
                    "date": format_date_ru(pr["created_at"]),
                    "url": f"article.html?id={urllib.parse.quote(pr['id'])}"
                })

            cur.execute("""
                SELECT ac.id, ac.article_id, ac.content, ac.created_at, ms.title AS question_title,
                       (SELECT COALESCE(SUM(v.value), 0) FROM comment_votes v WHERE v.comment_id = ac.id) AS rating
                FROM article_comments ac
                JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                WHERE ac.user_id = ?
                  AND ac.status = 'published'
                  AND ac.comment_type = 'answer'
                  AND ac.is_solution = 1
                  AND ms.status = 'approved'
                  AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question'
                GROUP BY ac.id
            """, (user_id,))
            for sol in cur.fetchall():
                top_contributions.append({
                    "id": sol["id"],
                    "questionId": sol["article_id"],
                    "type": "solution",
                    "materialType": "solution",
                    "material_type": "solution",
                    "title": sol["question_title"] or "Решение вопроса",
                    "contentSnippet": make_content_snippet(sol["content"]),
                    "rating": int(sol["rating"] or 0),
                    "score": int(sol["rating"] or 0),
                    "commentsCount": 0,
                    "answersCount": 0,
                    "isSolution": True,
                    "createdAt": sol["created_at"],
                    "date": format_date_ru(sol["created_at"]),
                    "url": f"article.html?id={urllib.parse.quote(sol['article_id'])}#comment-{urllib.parse.quote(sol['id'])}"
                })

            top_contributions.sort(key=lambda x: (x.get("rating", 0), x.get("createdAt") or ""), reverse=True)
            top_contributions = top_contributions[:3]

            # Aggregated topics from author's approved publications
            topic_counts = {}
            for pr in pub_rows:
                try:
                    pst = json.loads(pr["publication_settings"]) if pr["publication_settings"] else {}
                except Exception:
                    pst = {}
                ts = pst.get("topics") or []
                if isinstance(ts, str):
                    ts = [ts]
                for t in ts:
                    if t and isinstance(t, str):
                        t_clean = t.strip()
                        if t_clean:
                            topic_counts[t_clean] = topic_counts.get(t_clean, 0) + 1
            topics_list = [{"id": tid, "title": tid, "count": cnt} for tid, cnt in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:8]]

            profile_data = {
                "id": user_id,
                "userId": user_id,
                "name": author_name,
                "specialization": specialization,
                "company": company,
                "bio": bio,
                "avatar": avatar,
                "website": website,
                "createdAt": created_at_val,
                "date": format_date_ru(created_at_val) if created_at_val else None,
                "isSubscribed": is_sub,
                "isOwnProfile": bool(curr_user and curr_user["id"] == user_id),
                "rating": total_rating,
                "score": total_rating,
                "totalRating": total_rating,
                "karma": total_rating,
                "publicationsCount": publications_count,
                "questionsCount": questions_count,
                "followersCount": followers_count,
                "followingCount": following_count,
                "topics": topics_list,
                "stats": {
                    "rating": total_rating,
                    "score": total_rating,
                    "totalRating": total_rating,
                    "karma": total_rating,
                    "publicationsCount": publications_count,
                    "articlesCount": publications_count,
                    "questionsCount": questions_count,
                    "followersCount": followers_count,
                    "followingCount": following_count,
                    "answersCount": (c_stats["total_answers"] or 0) if c_stats else 0,
                    "solutionsCount": (c_stats["total_solutions"] or 0) if c_stats else 0
                },
                "publications": pubs,
                "topContributions": top_contributions
            }

            resp_payload = {
                "success": True,
                "profile": profile_data,
                "user": profile_data,
                **profile_data
            }
            self.send_json_response(200, resp_payload)
        finally:
            conn.close()

    def handle_get_user_activity(self, user_id: str, parsed_url=None):
        """
        GET /api/users/<user_id>/activity
        Returns unified chronological feed of author's activity (publications, questions, answers).
        Supports limit and offset pagination.
        """
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "Не указан user_id"})
            return

        query = urllib.parse.parse_qs(parsed_url.query) if parsed_url else {}
        try:
            limit = max(1, min(100, int(query.get("limit", [20])[0])))
        except ValueError:
            limit = 20

        try:
            offset = max(0, int(query.get("offset", [0])[0]))
        except ValueError:
            offset = 0

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
                user_exists = (cur.fetchone() is not None)
                if not user_exists:
                    cur.execute("SELECT 1 FROM sessions WHERE user_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True
                if not user_exists:
                    cur.execute("SELECT 1 FROM moderation_submissions WHERE author_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True
                if not user_exists:
                    cur.execute("SELECT 1 FROM article_comments WHERE user_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True

                if not user_exists:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Пользователь не найден",
                        "code": "USER_NOT_FOUND"
                    })
                    return

                # 1. Approved publications (articles)
                cur.execute("""
                    SELECT ms.id, ms.draft_id, ms.title, ms.article_html AS content, ms.created_at, ms.publication_settings,
                           (SELECT COALESCE(SUM(v.value), 0) FROM article_votes v WHERE v.article_id = ms.id OR (ms.draft_id IS NOT NULL AND v.article_id = ms.draft_id)) AS rating,
                           (SELECT COUNT(DISTINCT ac.id) FROM article_comments ac WHERE (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id)) AND ac.status = 'published') AS comments_count
                    FROM moderation_submissions ms
                    WHERE ms.author_id = ? AND ms.status = 'approved'
                      AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') != 'question'
                """, (user_id,))
                pub_rows = cur.fetchall()

                # 2. Approved questions
                cur.execute("""
                    SELECT ms.id, ms.draft_id, ms.title, ms.article_html AS content, ms.created_at, ms.publication_settings,
                           (SELECT COALESCE(SUM(v.value), 0) FROM article_votes v WHERE v.article_id = ms.id OR (ms.draft_id IS NOT NULL AND v.article_id = ms.draft_id)) AS rating,
                           (SELECT COUNT(DISTINCT ac.id) FROM article_comments ac WHERE (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id)) AND ac.status = 'published' AND ac.comment_type = 'answer') AS answers_count
                    FROM moderation_submissions ms
                    WHERE ms.author_id = ? AND ms.status = 'approved'
                      AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question'
                """, (user_id,))
                question_rows = cur.fetchall()

                # 3. Published answers
                cur.execute("""
                    SELECT ac.id, ac.article_id, ac.content, ac.is_solution, ac.created_at,
                           ms.title AS question_title,
                           (SELECT COALESCE(SUM(v.value), 0) FROM comment_votes v WHERE v.comment_id = ac.id) AS rating
                    FROM article_comments ac
                    JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                    WHERE ac.user_id = ?
                      AND ac.status = 'published'
                      AND ac.comment_type = 'answer'
                      AND ms.status = 'approved'
                      AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question'
                    GROUP BY ac.id
                """, (user_id,))
                answer_rows = cur.fetchall()

            activity = []
            for r in pub_rows:
                activity.append({
                    "type": "publication",
                    "materialType": "article",
                    "material_type": "article",
                    "id": r["id"],
                    "title": r["title"],
                    "contentSnippet": make_content_snippet(r["content"]),
                    "rating": int(r["rating"] or 0),
                    "score": int(r["rating"] or 0),
                    "commentsCount": int(r["comments_count"] or 0),
                    "answersCount": 0,
                    "isSolution": False,
                    "createdAt": r["created_at"],
                    "date": format_date_ru(r["created_at"]),
                    "url": f"article.html?id={urllib.parse.quote(r['id'])}"
                })

            for r in question_rows:
                activity.append({
                    "type": "question",
                    "materialType": "question",
                    "material_type": "question",
                    "id": r["id"],
                    "title": r["title"],
                    "contentSnippet": make_content_snippet(r["content"]),
                    "rating": int(r["rating"] or 0),
                    "score": int(r["rating"] or 0),
                    "commentsCount": 0,
                    "answersCount": int(r["answers_count"] or 0),
                    "isSolution": False,
                    "createdAt": r["created_at"],
                    "date": format_date_ru(r["created_at"]),
                    "url": f"article.html?id={urllib.parse.quote(r['id'])}"
                })

            for r in answer_rows:
                activity.append({
                    "type": "answer",
                    "materialType": "solution" if bool(r["is_solution"] == 1) else "answer",
                    "material_type": "solution" if bool(r["is_solution"] == 1) else "answer",
                    "id": r["id"],
                    "questionId": r["article_id"],
                    "title": r["question_title"] or "Ответ на вопрос",
                    "contentSnippet": make_content_snippet(r["content"]),
                    "rating": int(r["rating"] or 0),
                    "score": int(r["rating"] or 0),
                    "commentsCount": 0,
                    "answersCount": 0,
                    "isSolution": bool(r["is_solution"] == 1),
                    "createdAt": r["created_at"],
                    "date": format_date_ru(r["created_at"]),
                    "url": f"article.html?id={urllib.parse.quote(r['article_id'])}#comment-{urllib.parse.quote(r['id'])}"
                })

            activity.sort(key=lambda x: x.get("createdAt") or "", reverse=True)
            total = len(activity)
            paged_activity = activity[offset : offset + limit]
            has_more = (offset + limit) < total

            self.send_json_response(200, {
                "success": True,
                "activity": paged_activity,
                "items": paged_activity,
                "total": total,
                "limit": limit,
                "offset": offset,
                "hasMore": has_more
            })
        finally:
            conn.close()

    def handle_get_user_publications(self, user_id: str, parsed_url=None):
        """
        GET /api/users/<user_id>/publications
        Returns author's approved publications (articles, posts, news, etc. where materialType != 'question').
        Query params: sort ('newest'|'popular'), limit, offset.
        """
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "Не указан user_id"})
            return

        query = urllib.parse.parse_qs(parsed_url.query) if parsed_url else {}
        sort_by = (query.get("sort", ["newest"])[0] or "newest").strip().lower()
        try:
            limit = max(1, min(100, int(query.get("limit", [20])[0])))
        except ValueError:
            limit = 20
        try:
            offset = max(0, int(query.get("offset", [0])[0]))
        except ValueError:
            offset = 0

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
                p_row = cur.fetchone()
                user_exists = (p_row is not None)
                if not user_exists:
                    cur.execute("SELECT 1 FROM sessions WHERE user_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True
                if not user_exists:
                    cur.execute("SELECT 1 FROM moderation_submissions WHERE author_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True
                if not user_exists:
                    cur.execute("SELECT 1 FROM article_comments WHERE user_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True

                if not user_exists:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Пользователь не найден",
                        "code": "USER_NOT_FOUND"
                    })
                    return

                ident = self.resolve_user_identity(cur, user_id, p_row)
                author_name = ident["name"]
                author_avatar = ident["avatar"]
                author_initials = ident["initials"]
                company = ident["company"]
                specialization = ident["specialization"]

                curr_user = self.get_current_user()
                user_likes = set()
                user_saves = set()
                user_reports = set()
                user_votes = {}
                if curr_user:
                    cur.execute("SELECT article_id FROM article_likes WHERE user_id = ?", (curr_user["id"],))
                    user_likes = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id FROM article_saves WHERE user_id = ?", (curr_user["id"],))
                    user_saves = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id FROM article_reports WHERE user_id = ?", (curr_user["id"],))
                    user_reports = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id, value FROM article_votes WHERE user_id = ?", (curr_user["id"],))
                    user_votes = {r["article_id"]: r["value"] for r in cur.fetchall()}

                cur.execute("""
                    SELECT ms.id, ms.draft_id, ms.title, ms.article_html, ms.created_at, ms.publication_settings,
                           (SELECT COALESCE(SUM(v.value), 0) FROM article_votes v WHERE v.article_id = ms.id OR (ms.draft_id IS NOT NULL AND v.article_id = ms.draft_id)) AS rating,
                           (SELECT COUNT(DISTINCT ac.id) FROM article_comments ac WHERE (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id)) AND ac.status = 'published') AS comments_count,
                           (SELECT COUNT(DISTINCT al.id) FROM article_likes al WHERE al.article_id = ms.id OR (ms.draft_id IS NOT NULL AND al.article_id = ms.draft_id)) AS likes_count,
                           (SELECT COUNT(DISTINCT asv.id) FROM article_saves asv WHERE asv.article_id = ms.id OR (ms.draft_id IS NOT NULL AND asv.article_id = ms.draft_id)) AS saves_count
                    FROM moderation_submissions ms
                    WHERE ms.author_id = ? AND ms.status = 'approved'
                      AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') != 'question'
                """, (user_id,))
                rows = cur.fetchall()

            items = []
            for r in rows:
                art_id = r["id"]
                draft_id = r["draft_id"]
                try:
                    pst = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                except Exception:
                    pst = {}
                focal_pos = resolve_cover_position(pst)
                topics = pst.get("topics") or []
                cover_image = pst.get("coverImage") or None
                snippet = make_content_snippet(r["article_html"])
                reading_time, reading_minutes = calculate_reading_time(r["article_html"] or "")
                date_str = format_date_ru(r["created_at"])
                rating_val = int(r["rating"] or 0)
                comments_val = int(r["comments_count"] or 0)
                likes_val = int(r["likes_count"] or 0)
                saves_val = int(r["saves_count"] or 0)
                has_liked = bool(art_id in user_likes or (draft_id and draft_id in user_likes))
                has_saved = bool(art_id in user_saves or (draft_id and draft_id in user_saves))
                has_reported = bool(art_id in user_reports or (draft_id and draft_id in user_reports))
                my_vote = int(user_votes.get(art_id, 0) or (user_votes.get(draft_id, 0) if draft_id else 0))
                can_vote = bool(curr_user and user_id != curr_user["id"])
                is_author = bool(curr_user and user_id == curr_user["id"])

                items.append({
                    "id": art_id,
                    "draftId": draft_id,
                    "title": r["title"],
                    "authorId": user_id,
                    "author": author_name,
                    "authorInitials": author_initials,
                    "authorAvatar": author_avatar,
                    "company": company,
                    "specialization": specialization,
                    "date": date_str,
                    "createdAt": r["created_at"],
                    "description": snippet,
                    "snippet": snippet,
                    "contentSnippet": snippet,
                    "coverImage": cover_image,
                    "coverPosition": focal_pos,
                    "focalPoint": focal_pos,
                    "objectPosition": focal_pos,
                    "topics": topics,
                    "topic": topics[0] if topics else "",
                    "materialType": "article",
                    "material_type": "article",
                    "type": "article",
                    "format": pst.get("format") or "",
                    "rating": rating_val,
                    "score": rating_val,
                    "commentsCount": comments_val,
                    "answersCount": 0,
                    "discussionCount": comments_val,
                    "likesCount": likes_val,
                    "hasLiked": has_liked,
                    "isLiked": has_liked,
                    "savesCount": saves_val,
                    "hasSaved": has_saved,
                    "isSaved": has_saved,
                    "hasReported": has_reported,
                    "isReported": has_reported,
                    "myVote": my_vote,
                    "canVote": can_vote,
                    "isAuthor": is_author,
                    "readingTime": reading_time,
                    "readingMinutes": reading_minutes,
                    "url": f"article.html?id={urllib.parse.quote(art_id)}"
                })

            if sort_by == "popular":
                items.sort(key=lambda x: (x.get("rating", 0), x.get("createdAt") or ""), reverse=True)
            else:
                items.sort(key=lambda x: x.get("createdAt") or "", reverse=True)

            total = len(items)
            paged_items = items[offset : offset + limit]
            has_more = (offset + limit) < total

            self.send_json_response(200, {
                "success": True,
                "items": paged_items,
                "total": total,
                "limit": limit,
                "offset": offset,
                "hasMore": has_more
            })
        finally:
            conn.close()

    def handle_get_user_questions(self, user_id: str, parsed_url=None):
        """
        GET /api/users/<user_id>/questions
        Returns author's approved questions.
        Query params: sort ('newest'|'popular'), status ('all'|'solved'|'unsolved'), limit, offset.
        """
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "Не указан user_id"})
            return

        query = urllib.parse.parse_qs(parsed_url.query) if parsed_url else {}
        sort_by = (query.get("sort", ["newest"])[0] or "newest").strip().lower()
        status_filter = (query.get("status", ["all"])[0] or "all").strip().lower()
        try:
            limit = max(1, min(100, int(query.get("limit", [20])[0])))
        except ValueError:
            limit = 20
        try:
            offset = max(0, int(query.get("offset", [0])[0]))
        except ValueError:
            offset = 0

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
                p_row = cur.fetchone()
                user_exists = (p_row is not None)
                if not user_exists:
                    cur.execute("SELECT 1 FROM sessions WHERE user_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True
                if not user_exists:
                    cur.execute("SELECT 1 FROM moderation_submissions WHERE author_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True
                if not user_exists:
                    cur.execute("SELECT 1 FROM article_comments WHERE user_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True

                if not user_exists:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Пользователь не найден",
                        "code": "USER_NOT_FOUND"
                    })
                    return

                ident = self.resolve_user_identity(cur, user_id, p_row)
                author_name = ident["name"]
                author_avatar = ident["avatar"]
                author_initials = ident["initials"]
                company = ident["company"]
                specialization = ident["specialization"]

                curr_user = self.get_current_user()
                user_likes = set()
                user_saves = set()
                user_reports = set()
                user_votes = {}
                if curr_user:
                    cur.execute("SELECT article_id FROM article_likes WHERE user_id = ?", (curr_user["id"],))
                    user_likes = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id FROM article_saves WHERE user_id = ?", (curr_user["id"],))
                    user_saves = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id FROM article_reports WHERE user_id = ?", (curr_user["id"],))
                    user_reports = {r["article_id"] for r in cur.fetchall()}
                    cur.execute("SELECT article_id, value FROM article_votes WHERE user_id = ?", (curr_user["id"],))
                    user_votes = {r["article_id"]: r["value"] for r in cur.fetchall()}

                cur.execute("""
                    SELECT ms.id, ms.draft_id, ms.title, ms.article_html, ms.created_at, ms.publication_settings,
                           (SELECT COALESCE(SUM(v.value), 0) FROM article_votes v WHERE v.article_id = ms.id OR (ms.draft_id IS NOT NULL AND v.article_id = ms.draft_id)) AS rating,
                           (SELECT COUNT(DISTINCT ac.id) FROM article_comments ac WHERE (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id)) AND ac.status = 'published' AND ac.comment_type = 'answer') AS answers_count,
                           (SELECT COUNT(DISTINCT ac.id) FROM article_comments ac WHERE (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id)) AND ac.status = 'published' AND ac.comment_type = 'answer' AND ac.is_solution = 1) AS solutions_count,
                           (SELECT COUNT(DISTINCT al.id) FROM article_likes al WHERE al.article_id = ms.id OR (ms.draft_id IS NOT NULL AND al.article_id = ms.draft_id)) AS likes_count,
                           (SELECT COUNT(DISTINCT asv.id) FROM article_saves asv WHERE asv.article_id = ms.id OR (ms.draft_id IS NOT NULL AND asv.article_id = ms.draft_id)) AS saves_count
                    FROM moderation_submissions ms
                    WHERE ms.author_id = ? AND ms.status = 'approved'
                      AND COALESCE(json_extract(ms.publication_settings, '$.materialType'), json_extract(ms.publication_settings, '$.type'), 'publication') = 'question'
                """, (user_id,))
                rows = cur.fetchall()

            items = []
            for r in rows:
                art_id = r["id"]
                draft_id = r["draft_id"]
                sol_cnt = int(r["solutions_count"] or 0)
                is_solved = (sol_cnt > 0)
                if status_filter == "solved" and not is_solved:
                    continue
                if status_filter == "unsolved" and is_solved:
                    continue

                try:
                    pst = json.loads(r["publication_settings"]) if r["publication_settings"] else {}
                except Exception:
                    pst = {}
                focal_pos = resolve_cover_position(pst)
                topics = pst.get("topics") or []
                cover_image = pst.get("coverImage") or None
                snippet = make_content_snippet(r["article_html"])
                date_str = format_date_ru(r["created_at"])
                rating_val = int(r["rating"] or 0)
                answers_val = int(r["answers_count"] or 0)
                likes_val = int(r["likes_count"] or 0)
                saves_val = int(r["saves_count"] or 0)
                has_liked = bool(art_id in user_likes or (draft_id and draft_id in user_likes))
                has_saved = bool(art_id in user_saves or (draft_id and draft_id in user_saves))
                has_reported = bool(art_id in user_reports or (draft_id and draft_id in user_reports))
                my_vote = int(user_votes.get(art_id, 0) or (user_votes.get(draft_id, 0) if draft_id else 0))
                can_vote = bool(curr_user and user_id != curr_user["id"])
                is_author = bool(curr_user and user_id == curr_user["id"])

                items.append({
                    "id": art_id,
                    "draftId": draft_id,
                    "title": r["title"],
                    "authorId": user_id,
                    "author": author_name,
                    "authorInitials": author_initials,
                    "authorAvatar": author_avatar,
                    "company": company,
                    "specialization": specialization,
                    "date": date_str,
                    "createdAt": r["created_at"],
                    "description": snippet,
                    "snippet": snippet,
                    "contentSnippet": snippet,
                    "coverImage": cover_image,
                    "coverPosition": focal_pos,
                    "focalPoint": focal_pos,
                    "objectPosition": focal_pos,
                    "topics": topics,
                    "topic": topics[0] if topics else "",
                    "materialType": "question",
                    "material_type": "question",
                    "type": "question",
                    "rating": rating_val,
                    "score": rating_val,
                    "answersCount": answers_val,
                    "commentsCount": 0,
                    "discussionCount": answers_val,
                    "likesCount": likes_val,
                    "hasLiked": has_liked,
                    "isLiked": has_liked,
                    "savesCount": saves_val,
                    "hasSaved": has_saved,
                    "isSaved": has_saved,
                    "hasReported": has_reported,
                    "isReported": has_reported,
                    "myVote": my_vote,
                    "canVote": can_vote,
                    "isAuthor": is_author,
                    "solutionsCount": sol_cnt,
                    "isSolved": is_solved,
                    "hasSolution": is_solved,
                    "url": f"article.html?id={urllib.parse.quote(art_id)}"
                })

            if sort_by == "popular":
                items.sort(key=lambda x: (x.get("rating", 0), x.get("createdAt") or ""), reverse=True)
            else:
                items.sort(key=lambda x: x.get("createdAt") or "", reverse=True)

            total = len(items)
            paged_items = items[offset : offset + limit]
            has_more = (offset + limit) < total

            self.send_json_response(200, {
                "success": True,
                "items": paged_items,
                "total": total,
                "limit": limit,
                "offset": offset,
                "hasMore": has_more
            })
        finally:
            conn.close()

    def handle_get_user_answers(self, user_id: str, parsed_url=None):
        """
        GET /api/users/<user_id>/answers
        Returns author's published answers from article_comments with question title context.
        Query params: filter ('all'|'solutions'), limit, offset.
        """
        if not user_id:
            self.send_json_response(400, {"success": False, "error": "Не указан user_id"})
            return

        query = urllib.parse.parse_qs(parsed_url.query) if parsed_url else {}
        filter_type = (query.get("filter", ["all"])[0] or "all").strip().lower()
        try:
            limit = max(1, min(100, int(query.get("limit", [20])[0])))
        except ValueError:
            limit = 20
        try:
            offset = max(0, int(query.get("offset", [0])[0]))
        except ValueError:
            offset = 0

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
                user_exists = (cur.fetchone() is not None)
                if not user_exists:
                    cur.execute("SELECT 1 FROM sessions WHERE user_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True
                if not user_exists:
                    cur.execute("SELECT 1 FROM moderation_submissions WHERE author_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True
                if not user_exists:
                    cur.execute("SELECT 1 FROM article_comments WHERE user_id = ? LIMIT 1", (user_id,))
                    if cur.fetchone():
                        user_exists = True

                if not user_exists:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Пользователь не найден",
                        "code": "USER_NOT_FOUND"
                    })
                    return

                cur.execute("""
                    SELECT ac.id, ac.article_id, ac.content, ac.is_solution, ac.created_at,
                           ms.title AS question_title,
                           (SELECT COALESCE(SUM(v.value), 0) FROM comment_votes v WHERE v.comment_id = ac.id) AS rating
                    FROM article_comments ac
                    JOIN moderation_submissions ms ON (ac.article_id = ms.id OR (ms.draft_id IS NOT NULL AND ac.article_id = ms.draft_id))
                    WHERE ac.user_id = ?
                      AND ac.status = 'published'
                      AND ac.comment_type = 'answer'
                      AND ms.status = 'approved'
                      AND (
                          json_extract(ms.publication_settings, '$.materialType') = 'question'
                          OR json_extract(ms.publication_settings, '$.type') = 'question'
                      )
                    GROUP BY ac.id
                    ORDER BY ac.created_at DESC
                """, (user_id,))
                rows = cur.fetchall()

            items = []
            for r in rows:
                is_sol = bool(r["is_solution"] == 1)
                if filter_type in ("solutions", "solution") and not is_sol:
                    continue

                items.append({
                    "id": r["id"],
                    "questionId": r["article_id"],
                    "questionTitle": r["question_title"] or "Ответ на вопрос",
                    "title": r["question_title"] or "Ответ на вопрос",
                    "contentSnippet": make_content_snippet(r["content"]),
                    "rating": int(r["rating"] or 0),
                    "isSolution": is_sol,
                    "createdAt": r["created_at"],
                    "date": format_date_ru(r["created_at"]),
                    "url": f"article.html?id={urllib.parse.quote(r['article_id'])}#comment-{urllib.parse.quote(r['id'])}"
                })

            total = len(items)
            paged_items = items[offset : offset + limit]
            has_more = (offset + limit) < total

            self.send_json_response(200, {
                "success": True,
                "items": paged_items,
                "total": total,
                "limit": limit,
                "offset": offset,
                "hasMore": has_more
            })
        finally:
            conn.close()

    def handle_get_current_user_profile(self, parsed_url):
        """GET /api/user/profile for authenticated user."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Пользователь не авторизован",
                "requireAuth": True
            })
            return
        self.handle_get_user_profile(user["id"])

    def handle_post_user_profile(self):
        """
        POST /api/user/profile
        Updates specialization, company, bio, name for the authenticated user.
        """
        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для редактирования профиля необходимо войти",
                "requireAuth": True
            })
            return

        name = (payload.get("name") or user.get("name") or "").strip()
        specialization = (payload.get("specialization") or "").strip()
        company = (payload.get("company") or "").strip()
        bio = (payload.get("bio") or "").strip()
        website = (payload.get("website") or "").strip() if payload.get("website") is not None else None
        avatar = payload.get("avatar") or user.get("avatar")
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                try:
                    cur.execute("""
                        INSERT INTO user_profiles (user_id, name, specialization, company, bio, avatar, website, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET
                            name = excluded.name,
                            specialization = excluded.specialization,
                            company = excluded.company,
                            bio = excluded.bio,
                            avatar = excluded.avatar,
                            website = COALESCE(excluded.website, user_profiles.website),
                            updated_at = excluded.updated_at
                    """, (user["id"], name, specialization, company, bio, avatar, website, now_iso, now_iso))
                except sqlite3.OperationalError:
                    cur.execute("""
                        INSERT INTO user_profiles (user_id, name, specialization, company, bio, avatar, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET
                            name = excluded.name,
                            specialization = excluded.specialization,
                            company = excluded.company,
                            bio = excluded.bio,
                            avatar = excluded.avatar,
                            updated_at = excluded.updated_at
                    """, (user["id"], name, specialization, company, bio, avatar, now_iso, now_iso))

            self.send_json_response(200, {
                "success": True,
                "profile": {
                    "userId": user["id"],
                    "name": name,
                    "specialization": specialization,
                    "company": company,
                    "bio": bio,
                    "website": website or "",
                    "avatar": avatar
                }
            })
        finally:
            conn.close()



def create_server(host: str = "0.0.0.0", port: int = 8000, db_path: Optional[str] = None, directory: Optional[str] = None, media_dir: Optional[str] = None, seed: Optional[bool] = None) -> http.server.ThreadingHTTPServer:
    """
    Creates and returns a ThreadingHTTPServer instance with initialized database and media storage.
    """
    init_db(db_path, seed=seed)
    server_address = (host, port)
    httpd = http.server.ThreadingHTTPServer(server_address, ModerationRequestHandler)
    httpd.db_path = db_path or os.environ.get("MODERATION_DB_PATH", DEFAULT_DB_PATH)
    httpd.directory = directory or FRONTEND_PUBLIC_DIR
    httpd.media_dir = media_dir or os.environ.get("MEDIA_DIR", MEDIA_DIR)
    os.makedirs(httpd.media_dir, exist_ok=True)
    return httpd


def run_server(host: str = "0.0.0.0", port: int = 8000, db_path: Optional[str] = None, seed: bool = False):
    """
    Starts the server loop listening on host:port.
    """
    httpd = create_server(host=host, port=port, db_path=db_path, seed=seed)
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
    parser.add_argument("--seed", action="store_true", help="Seed database with demo data on startup")
    args = parser.parse_args()
    port = args.port or args.port_pos or int(os.environ.get("PORT", 8000))
    run_server(host=args.host, port=port, db_path=args.db, seed=args.seed)
