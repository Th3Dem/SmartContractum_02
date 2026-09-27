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
import base64
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
VALID_MATERIAL_TYPES = ("article", "post", "news", "question")


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


STANDARD_TOPICS = [
    ("pksc-architecture", "Архитектура и развитие ПКСК"),
    ("smart-contracts-development", "Разработка смарт-контрактов"),
    ("business-logic-deals", "Бизнес-логика и моделирование сделок"),
    ("testing-and-quality", "Тестирование и качество"),
    ("information-security", "Информационная безопасность"),
    ("audit-and-verification", "Аудит и проверка смарт-контрактов"),
    ("law-and-compliance", "Право и комплаенс"),
    ("digital-ruble-payments", "Цифровой рубль и платежи"),
    ("oracles-and-data", "Оракулы и поставка данных"),
    ("integrations-and-api", "Интеграции и API"),
    ("infrastructure-and-nodes", "Инфраструктура и узлы"),
    ("analytics-and-monitoring", "Аналитика и мониторинг"),
    ("standards-and-protocols", "Стандарты и протоколы"),
    ("business-cases-adoption", "Бизнес-сценарии и внедрение"),
]
TOPICS_TITLE_MAP = dict(STANDARD_TOPICS)


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
            CREATE TABLE IF NOT EXISTS article_comments (
                id TEXT PRIMARY KEY,
                article_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                author_name TEXT NOT NULL,
                author_avatar TEXT,
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'published',
                created_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_article_id ON article_comments(article_id);")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_feed_settings (
                user_id TEXT PRIMARY KEY,
                material_types TEXT NOT NULL,
                complexity_levels TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        seed_approved_articles(conn)
        seed_user_subscriptions(conn)
        seed_article_comments(conn)
    return conn


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

<p>где <span class="editor-inline-formula" data-latex="P_i">\\(P_i\\)</span> — вероятность реализации угрозы, а <span class="editor-inline-formula" data-latex="I_i">\\(I_i\\)</span> — тяжесть последствий инцидента.</p>

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
<p>Смарт-контракты исполняются в детерминированной виртуальной среде и не имеют прямого сетевого доступа к внешним HTTP/REST API. Для фиксации событий реального мира (котировки драгоценных металлов, статусы доставки грузов, курсы валют) требуются специализированные узлы — децентрализованные оракулы.</p>

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

        # 4g. materialType / type
        raw_mat = pub_settings.get("materialType") or pub_settings.get("type")
        if raw_mat is not None and raw_mat != "":
            if not isinstance(raw_mat, str) or raw_mat.strip().lower() not in VALID_MATERIAL_TYPES:
                field_errors["materialType"] = f"Недопустимый тип материала публикации. Допустимые типы: {', '.join(VALID_MATERIAL_TYPES)}"
            else:
                pub_settings["materialType"] = raw_mat.strip().lower()
                pub_settings["type"] = raw_mat.strip().lower()

        # 4h. coverImage
        cover_image = pub_settings.get("coverImage")
        if cover_image is not None and cover_image != "":
            cov_res = validate_cover_image(cover_image)
            is_cov_valid, cov_err = cov_res[0], cov_res[1]
            if not is_cov_valid:
                field_errors["coverImage"] = cov_err or "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ."
            elif cov_res.saved_url and cov_res.saved_url.startswith("/media/"):
                pub_settings["coverImage"] = cov_res.saved_url

    if field_errors:
        order = [
            "title", "html", "targetAudience", "topics", "keywords", "description",
            "format", "complexity", "materialType", "coverImage", "draftId", "publicationSettings"
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

    def get_current_user(self) -> Optional[Dict[str, str]]:
        """
        Extracts authenticated user from cookies, X-User-Id header, Authorization header, or query params.
        """
        cookie_header = self.headers.get("Cookie", "")
        if cookie_header:
            cookies = urllib.parse.parse_qsl(cookie_header.replace("; ", "&"))
            for k, v in cookies:
                if k == "sc_session" and v:
                    return {"id": v, "name": "Демо Пользователь" if v == "user_demo" else v}

        x_user = self.headers.get("X-User-Id", "").strip()
        if x_user:
            return {"id": x_user, "name": "Демо Пользователь" if x_user == "user_demo" else x_user}

        auth_header = self.headers.get("Authorization", "").strip()
        if auth_header:
            token = auth_header.replace("Bearer ", "").strip()
            if token:
                return {"id": token, "name": "Демо Пользователь" if token == "user_demo" else token}

        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        u_param = (qs.get("userId", [""])[0] or qs.get("authUser", [""])[0]).strip()
        if u_param:
            return {"id": u_param, "name": "Демо Пользователь" if u_param == "user_demo" else u_param}

        return None

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
        elif path == "/api/subscriptions":
            self.handle_get_subscriptions()
        elif path == "/api/subscriptions/entities":
            self.handle_get_subscription_entities()
        elif path == "/api/moderation/status":
            self.handle_moderation_status(parsed)
        elif path == "/api/moderation/list":
            self.handle_moderation_list()
        elif path.startswith("/api/articles/") and path.endswith("/comments"):
            art_id = path[len("/api/articles/"): -len("/comments")].strip("/")
            self.handle_get_article_comments(art_id)
        elif path == "/api/comments":
            query = urllib.parse.parse_qs(parsed.query)
            art_id = (query.get("articleId", [""])[0] or query.get("article_id", [""])[0] or query.get("id", [""])[0]).strip()
            self.handle_get_article_comments(art_id)
        elif path == "/api/articles" or path.startswith("/api/articles/"):
            self.handle_articles_api(parsed)
        elif path.startswith("/media/"):
            self.handle_serve_media(parsed)
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

        if path == "/api/auth/login":
            self.handle_auth_login()
        elif path == "/api/auth/logout":
            self.handle_auth_logout()
        elif path == "/api/user/feed-settings":
            self.handle_post_feed_settings()
        elif path == "/api/likes/toggle":
            try:
                cl = int(self.headers.get("Content-Length", 0))
                b = self.rfile.read(cl).decode("utf-8") if cl > 0 else "{}"
                p = json.loads(b) if b else {}
            except Exception:
                p = {}
            art_id = p.get("articleId") or p.get("article_id") or ""
            self.handle_article_like_toggle(art_id)
        elif path.startswith("/api/articles/") and path.endswith("/like"):
            art_id = path[len("/api/articles/"): -len("/like")].strip("/")
            self.handle_article_like_toggle(art_id)
        elif path.startswith("/api/articles/") and path.endswith("/comments"):
            art_id = path[len("/api/articles/"): -len("/comments")].strip("/")
            self.handle_post_article_comment(art_id)
        elif path == "/api/comments":
            self.handle_post_article_comment("")
        elif path == "/api/subscriptions/toggle":
            self.handle_subscriptions_toggle()
        elif path == "/api/moderation/submit":
            self.handle_moderation_submit()
        elif path == "/api/media/upload":
            self.handle_media_upload()
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

    def handle_auth_login(self):
        """POST /api/auth/login sets sc_session cookie and returns user."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        user_id = (data.get("userId") or "user_demo").strip()
        user_name = (data.get("name") or ("Демо Пользователь" if user_id == "user_demo" else user_id)).strip()
        user = {"id": user_id, "name": user_name}

        self.send_json_response(200, {
            "success": True,
            "authenticated": True,
            "user": user
        }, extra_headers=[("Set-Cookie", f"sc_session={user_id}; Path=/; SameSite=Lax")])

    def handle_auth_logout(self):
        """POST /api/auth/logout clears sc_session cookie."""
        self.send_json_response(200, {
            "success": True,
            "authenticated": False
        }, extra_headers=[("Set-Cookie", "sc_session=; Path=/; Max-Age=0; SameSite=Lax")])

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

        subs = {"authors": [], "topics": [], "tags": []}
        for r in rows:
            t = r["target_type"]
            entry = {"id": r["target_id"], "title": r["target_title"], "createdAt": r["created_at"]}
            if t == "author":
                subs["authors"].append(entry)
            elif t == "topic":
                subs["topics"].append(entry)
            elif t == "tag":
                subs["tags"].append(entry)

        self.send_json_response(200, {
            "success": True,
            "user": user,
            "subscriptions": subs
        })

    def handle_subscriptions_toggle(self):
        """POST /api/subscriptions/toggle toggles subscription state."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Unauthorized", "requireAuth": True})
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}
        except Exception as e:
            self.send_json_response(400, {"success": False, "error": f"Invalid JSON payload: {e}"})
            return

        target_type = (data.get("targetType") or "").strip().lower()
        raw_id = (data.get("targetId") or "").strip()
        raw_title = (data.get("targetTitle") or "").strip()

        if target_type not in ("author", "topic", "tag"):
            self.send_json_response(400, {"success": False, "error": "targetType must be 'author', 'topic', or 'tag'"})
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
                subscribed = True

        self.send_json_response(200, {
            "success": True,
            "subscribed": subscribed,
            "targetType": target_type,
            "targetId": normalized_id,
            "targetTitle": title
        })

    def handle_get_subscription_entities(self):
        """GET /api/subscriptions/entities returns catalog of entities available for subscription."""
        user = self.get_current_user()
        user_subs = set()
        conn = self.get_db()
        with conn:
            if user:
                cur = conn.cursor()
                cur.execute("SELECT target_type, target_id FROM user_subscriptions WHERE user_id = ?", (user["id"],))
                for r in cur.fetchall():
                    user_subs.add((r["target_type"], r["target_id"]))

            cur = conn.cursor()
            cur.execute("SELECT * FROM moderation_submissions WHERE status = 'approved' ORDER BY created_at DESC")
            rows = cur.fetchall()

        authors_map = {}
        tags_map = {}
        topics_counts = {}

        for row in rows:
            try:
                settings = json.loads(row["publication_settings"]) if row["publication_settings"] else {}
            except Exception:
                settings = {}

            author_id = row["author_id"]
            author_name = settings.get("author") or "Автор платформы"
            author_role = settings.get("authorRole") or ""
            if author_id not in authors_map:
                authors_map[author_id] = {
                    "id": author_id,
                    "title": author_name,
                    "role": author_role,
                    "count": 0,
                    "isSubscribed": ("author", author_id) in user_subs
                }
            authors_map[author_id]["count"] += 1

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
                            "isSubscribed": ("tag", norm_tag) in user_subs
                        }
                    tags_map[norm_tag]["count"] += 1

        topics_list = []
        for tid, tname in STANDARD_TOPICS:
            topics_list.append({
                "id": tid,
                "title": tname,
                "count": topics_counts.get(tid, 0),
                "isSubscribed": ("topic", tid) in user_subs
            })

        self.send_json_response(200, {
            "success": True,
            "authors": list(authors_map.values()),
            "topics": topics_list,
            "tags": sorted(list(tags_map.values()), key=lambda x: x["count"], reverse=True)
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
                    "complexityLevels": default_complexity_levels
                },
                "materialTypes": default_material_types,
                "complexityLevels": default_complexity_levels
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT material_types, complexity_levels FROM user_feed_settings WHERE user_id = ?",
                (user["id"],)
            )
            row = cur.fetchone()

        if row:
            try:
                m_types = json.loads(row["material_types"])
            except Exception:
                m_types = default_material_types
            try:
                c_levels = json.loads(row["complexity_levels"])
            except Exception:
                c_levels = default_complexity_levels
        else:
            m_types = default_material_types
            c_levels = default_complexity_levels

        self.send_json_response(200, {
            "success": True,
            "settings": {
                "materialTypes": m_types,
                "complexityLevels": c_levels
            },
            "materialTypes": m_types,
            "complexityLevels": c_levels
        })

    def handle_post_feed_settings(self):
        """
        POST /api/user/feed-settings
        Saves user feed settings for authenticated user.
        Body: { "materialTypes": [...], "complexityLevels": [...] }
        Returns 401 if unauthenticated.
        Returns 400 if materialTypes is empty ("Выберите хотя бы один тип материала").
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для сохранения настроек ленты необходимо войти",
                "requireAuth": True
            })
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            payload = json.loads(body) if body else {}
        except Exception as e:
            self.send_json_response(400, {
                "success": False,
                "error": f"Невалидный JSON: {str(e)}"
            })
            return

        settings_obj = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload

        material_types = settings_obj.get("materialTypes")
        if material_types is None:
            material_types = settings_obj.get("material_types")

        if material_types is None or not isinstance(material_types, list):
            self.send_json_response(400, {
                "success": False,
                "error": "Выберите хотя бы один тип материала"
            })
            return

        valid_types = []
        for t in material_types:
            if isinstance(t, str) and t.strip().lower() in VALID_MATERIAL_TYPES:
                norm_t = t.strip().lower()
                if norm_t not in valid_types:
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
            conn.execute("""
                INSERT INTO user_feed_settings (user_id, material_types, complexity_levels, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    material_types = excluded.material_types,
                    complexity_levels = excluded.complexity_levels,
                    updated_at = excluded.updated_at
            """, (
                user["id"],
                json.dumps(valid_types, ensure_ascii=False),
                json.dumps(clean_levels, ensure_ascii=False),
                now_iso
            ))

        self.send_json_response(200, {
            "success": True,
            "settings": {
                "materialTypes": valid_types,
                "complexityLevels": clean_levels
            },
            "materialTypes": valid_types,
            "complexityLevels": clean_levels
        })

    def handle_article_like_toggle(self, article_id: str):
        """
        POST /api/articles/<id>/like or POST /api/likes/toggle
        Toggles like for current user on the given article.
        Requires authentication (401 requireAuth).
        Returns { success: True, hasLiked: bool, likesCount: int }.
        """
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
            "likesCount": likes_count,
            "articleId": real_art_id
        })

    def handle_get_article_comments(self, article_id: str):
        """
        GET /api/articles/<id>/comments
        Returns list of published comments for the article. Accessible to guests.
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
            cur.execute("SELECT id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (article_id, article_id))
            art_row = cur.fetchone()
            real_id = art_row["id"] if art_row else article_id

            cur.execute("""
                SELECT id, article_id, user_id, author_name, author_avatar, content, created_at
                FROM article_comments
                WHERE article_id = ? AND status = 'published'
                ORDER BY created_at ASC
            """, (real_id,))
            rows = cur.fetchall()

        comments = []
        for r in rows:
            comments.append({
                "id": r["id"],
                "articleId": r["article_id"],
                "userId": r["user_id"],
                "authorName": r["author_name"],
                "authorAvatar": r["author_avatar"] or None,
                "content": r["content"],
                "createdAt": r["created_at"]
            })

        self.send_json_response(200, {
            "success": True,
            "comments": comments,
            "total": len(comments)
        })

    def handle_post_article_comment(self, article_id: str):
        """
        POST /api/articles/<id>/comments
        Adds a comment to the specified article.
        Requires authentication (401 requireAuth).
        Validates content: non-empty, stripped, max 5000 chars. Escapes HTML.
        Returns newly added comment and updated commentsCount.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для отправки комментария необходимо войти",
                "requireAuth": True
            })
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""
            payload = json.loads(body) if body else {}
        except Exception as e:
            self.send_json_response(400, {
                "success": False,
                "error": f"Невалидный JSON: {str(e)}"
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

        sanitized_content = html.escape(stripped_content)

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

            real_id = art_row["id"]
            user_id = user["id"]
            author_name = user.get("name") or (f"Пользователь #{user_id[:6]}" if user_id else "Читатель")
            author_avatar = user.get("avatar") or None

            comment_id = f"comm_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

            cur.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar, content, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', ?)
            """, (
                comment_id, real_id, user_id, author_name, author_avatar,
                sanitized_content, now_iso
            ))

            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = ? AND status = 'published'", (real_id,))
            comments_count = cur.fetchone()["cnt"]

        comment_data = {
            "id": comment_id,
            "articleId": real_id,
            "userId": user_id,
            "authorName": author_name,
            "authorAvatar": author_avatar,
            "content": sanitized_content,
            "createdAt": now_iso
        }

        self.send_json_response(201, {
            "success": True,
            "comment": comment_data,
            "commentsCount": comments_count
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

    def handle_articles_api(self, parsed_url):
        """
        Dispatches GET /api/articles requests to single article view or feed list view.
        """
        path = parsed_url.path
        if path.startswith("/api/articles/"):
            article_id = path[len("/api/articles/"):].strip()
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
        comments_count = 0
        has_liked = False
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM article_likes WHERE article_id = ?", (row["id"],))
            likes_count = cur.fetchone()["cnt"]
            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = ? AND status = 'published'", (row["id"],))
            comments_count = cur.fetchone()["cnt"]
            if user:
                cur.execute("SELECT 1 FROM article_likes WHERE article_id = ? AND user_id = ?", (row["id"], user["id"]))
                has_liked = cur.fetchone() is not None

        mat_type = settings.get("materialType") or settings.get("type") or "article"

        article_data = {
            "id": row["id"],
            "draftId": row["draft_id"],
            "title": row["title"],
            "author": author_name,
            "authorInitials": author_initials,
            "authorRole": author_role,
            "date": format_date_ru(row["created_at"]),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "description": settings.get("description") or "",
            "coverImage": settings.get("coverImage") or None,
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
            "commentsCount": comments_count,
            "materialType": mat_type,
            "type": mat_type,
            "html": article_html,
            "delta": delta
        }

        self.send_json_response(200, {
            "success": True,
            "article": article_data
        })

    def handle_get_articles_list(self, parsed_url):
        """
        GET /api/articles
        Query parameters:
          search: search string across title, description, keywords, and body
          topic: filter by topic ID
          audience: filter by target audience ID
          format: filter by format ID
          complexity / complexities: filter by complexity ID(s)
          type / types: filter by material type(s)
          sort: 'newest' (default) or 'oldest'
          period: 'all' (default), 'month', 'week'
          ids: comma-separated list of article IDs (for bookmarks retrieval)
          limit: items per page (default 10)
          offset: offset for pagination (default 0)
        Returns only approved articles.
        """
        query = urllib.parse.parse_qs(parsed_url.query)
        tab = (query.get("tab", ["all"])[0] or "all").strip().lower()
        search_query = (query.get("search", [""])[0] or "").strip().lower()
        topic_filter = (query.get("topic", [""])[0] or "").strip()
        audience_filter = (query.get("audience", [""])[0] or "").strip()
        format_filter = (query.get("format", [""])[0] or "").strip()
        complexity_filter = (query.get("complexities", [""])[0] or query.get("complexity", [""])[0] or "").strip()
        types_filter = (query.get("types", [""])[0] or query.get("type", [""])[0] or "").strip()
        sort_by = (query.get("sort", ["newest"])[0] or "newest").strip().lower()
        period_filter = (query.get("period", ["all"])[0] or "all").strip().lower()
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

        sub_authors = set()
        sub_topics = set()
        sub_tags = set()
        sub_topics_titles = {}
        sub_tags_titles = {}

        user_types = None
        user_complexities = None

        if tab == "my":
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
                    "tab": "my",
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

        # Determine effective types filter
        if types_filter and types_filter != "all":
            allowed_types = set([t.strip().lower() for t in types_filter.split(",") if t.strip()])
        elif tab == "my" and user_types:
            allowed_types = set([t.strip().lower() for t in user_types if t.strip()])
        else:
            allowed_types = None

        if allowed_types and "all" in allowed_types:
            allowed_types = None

        # Determine effective complexity filter
        if complexity_filter and complexity_filter != "all":
            allowed_complexities = set([c.strip().lower() for c in complexity_filter.split(",") if c.strip()])
        elif tab == "my" and user_complexities:
            allowed_complexities = set([c.strip().lower() for c in user_complexities if c.strip()])
        else:
            allowed_complexities = None

        if allowed_complexities and "all" in allowed_complexities:
            allowed_complexities = None

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM moderation_submissions WHERE status = 'approved' ORDER BY created_at DESC")
            rows = cur.fetchall()

            # Pre-fetch counts for likes and comments
            cur.execute("SELECT article_id, COUNT(*) AS cnt FROM article_likes GROUP BY article_id")
            likes_counts = {r["article_id"]: r["cnt"] for r in cur.fetchall()}

            cur.execute("SELECT article_id, COUNT(*) AS cnt FROM article_comments WHERE status = 'published' GROUP BY article_id")
            comments_counts = {r["article_id"]: r["cnt"] for r in cur.fetchall()}

            current_user = self.get_current_user()
            user_likes = set()
            if current_user:
                cur.execute("SELECT article_id FROM article_likes WHERE user_id = ?", (current_user["id"],))
                user_likes = {r["article_id"] for r in cur.fetchall()}

        now_utc = datetime.datetime.now(datetime.timezone.utc)
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
            topics = settings.get("topics") or []
            for t in topics:
                topic_counts[t] = topic_counts.get(t, 0) + 1

            # Period filtering
            created_at_dt = None
            try:
                created_at_dt = datetime.datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            except Exception:
                pass

            if period_filter == "week" and created_at_dt:
                if (now_utc - created_at_dt).total_seconds() > 7 * 86400:
                    continue
            elif period_filter == "month" and created_at_dt:
                if (now_utc - created_at_dt).total_seconds() > 30 * 86400:
                    continue

            # IDs filtering (e.g. bookmarks)
            if allowed_ids is not None:
                if art_id not in allowed_ids and draft_id not in allowed_ids:
                    continue

            # Material type filtering
            art_type = (settings.get("materialType") or settings.get("type") or "article").strip().lower()
            if allowed_types is not None and art_type not in allowed_types:
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
            if topic_filter and topic_filter != "all":
                if topic_filter not in topics:
                    continue

            # Audience filtering
            target_audience = settings.get("targetAudience") or ""
            if audience_filter and audience_filter != "all":
                if target_audience != audience_filter:
                    continue

            # Format filtering
            fmt = settings.get("format") or ""
            if format_filter and format_filter != "all":
                if fmt != format_filter:
                    continue

            # Author metadata
            author_name = settings.get("author") or (
                "Пользователь #" + row["author_id"][:6] if row["author_id"] else "Автор SmartContractum"
            )
            author_initials = settings.get("authorInitials") or (
                "".join([part[0].upper() for part in author_name.split()[:2]]) if author_name else "SC"
            )
            author_role = settings.get("authorRole") or ""

            # Search query filtering across title, author, role, description, keywords and body
            title = row["title"] or ""
            desc = settings.get("description") or ""
            keywords = settings.get("keywords") or []
            article_text = extract_article_text(row["article_html"] or "")

            if search_query:
                search_haystack = f"{title} {author_name} {author_role} {desc} {' '.join(keywords)} {article_text}".lower()
                words = search_query.split()
                if not all(w in search_haystack for w in words):
                    continue

            # Check subscription filter for "my" feed
            subscription_reason = None
            if tab == "my":
                if row["author_id"] in sub_authors or author_name in sub_authors:
                    subscription_reason = f"Вы подписаны на автора {author_name}"
                else:
                    matched_topic = next((t for t in topics if t in sub_topics), None)
                    if matched_topic:
                        topic_title = sub_topics_titles.get(matched_topic) or TOPICS_TITLE_MAP.get(matched_topic, matched_topic)
                        subscription_reason = f"Вы подписаны на тему «{topic_title}»"
                    else:
                        norm_kws = [normalize_keyword(k).lstrip('#').strip().lower() for k in keywords]
                        matched_tag = next((nk for nk in norm_kws if nk in sub_tags), None)
                        if matched_tag:
                            tag_title = sub_tags_titles.get(matched_tag) or matched_tag
                            subscription_reason = f"Вы подписаны на #{tag_title}"

                if not subscription_reason:
                    continue

            reading_time, reading_minutes = calculate_reading_time(row["article_html"] or "")

            seen_article_ids.add(art_id)
            filtered_articles.append({
                "id": row["id"],
                "draftId": row["draft_id"],
                "title": row["title"],
                "author": author_name,
                "authorInitials": author_initials,
                "authorRole": author_role,
                "date": format_date_ru(row["created_at"]),
                "createdAt": row["created_at"],
                "description": desc,
                "coverImage": settings.get("coverImage") or None,
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
                "commentsCount": comments_counts.get(art_id, 0),
                "materialType": art_type,
                "type": art_type
            })

        if sort_by in ("oldest", "asc"):
            filtered_articles.reverse()

        total = len(filtered_articles)
        paged_articles = filtered_articles[offset : offset + limit]
        has_more = (offset + limit) < total

        self.send_json_response(200, {
            "success": True,
            "articles": paged_articles,
            "total": total,
            "limit": limit,
            "offset": offset,
            "hasMore": has_more,
            "topicCounts": topic_counts,
            "tab": tab,
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
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            content_length = 0

        if content_length <= 0:
            self.send_json_response(400, {"success": False, "error": "Пустое тело запроса"})
            return

        content_type = self.headers.get("Content-Type", "")
        raw_body = self.rfile.read(content_length)

        media_root = getattr(self.server, "media_dir", MEDIA_DIR)

        if "application/json" in content_type:
            try:
                payload = json.loads(raw_body.decode("utf-8"))
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
            except Exception as e:
                self.send_json_response(400, {"success": False, "error": f"Ошибка обработки JSON: {str(e)}"})
                return

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


def create_server(host: str = "0.0.0.0", port: int = 8000, db_path: Optional[str] = None, directory: Optional[str] = None, media_dir: Optional[str] = None) -> http.server.ThreadingHTTPServer:
    """
    Creates and returns a ThreadingHTTPServer instance with initialized database and media storage.
    """
    init_db(db_path)
    server_address = (host, port)
    httpd = http.server.ThreadingHTTPServer(server_address, ModerationRequestHandler)
    httpd.db_path = db_path or os.environ.get("MODERATION_DB_PATH", DEFAULT_DB_PATH)
    httpd.directory = directory or FRONTEND_PUBLIC_DIR
    httpd.media_dir = media_dir or os.environ.get("MEDIA_DIR", MEDIA_DIR)
    os.makedirs(httpd.media_dir, exist_ok=True)
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
