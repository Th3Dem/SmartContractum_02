"""HTML sanitizing and text helpers for publications, questions and comments."""
import datetime
import hashlib
import html
import html.parser
import json
import re
import urllib.parse
import uuid
from typing import Any, List, Optional, Tuple, Union


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
        # Editor blocks (Issue #280): image with caption and spoiler
        "figure", "figcaption", "details", "summary",
    }
    # LaTeX source of editor formulas, rendered by KaTeX with trust: false (Issues #263, #280)
    MAX_LATEX_LENGTH = 4000
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
            if name == 'data-latex' and tag in ('div', 'span'):
                # Plain text only; it is escaped on output and never interpreted as HTML
                return 0 < len(val) <= self.MAX_LATEX_LENGTH and '\x00' not in val
            if name == 'open' and tag == 'details':
                return val in ('', 'open')
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

# Short descriptions of directions for the catalog and subscriptions (moved from seed_data.py, Issue #284)
TOPICS_DESCRIPTION_MAP = {
    "pksc-architecture": "Архитектурные паттерны, консенсус и масштабирование корпоративных систем",
    "smart-contracts-development": "Написание безопасного кода, оптимизация исполнения и шаблоны контрактов",
    "business-logic-deals": "Автоматизация бизнес-процессов, алгоритмы сделок и транзакций",
    "testing-and-quality": "Модульное, интеграционное и нагрузочное тестирование контрактов и узлов",
    "information-security": "Защита узлов, предотвращение атак и безопасность ключей",
    "audit-and-verification": "Формальная верификация, статический анализ и аудит безопасности",
    "law-and-compliance": "Правовой статус смарт-контрактов и регуляторные требования РФ",
    "oracles-and-data": "Поставка доверенных внешних данных и верификация источников",
    "integrations-and-api": "Интеграция реестров с банковскими и корпоративными системами",
    "digital-ruble-payments": "Программируемые расчеты, интеграция цифрового рубля и платежи",
    "lifecycle-versioning": "Управление версиями контрактов и обновление логики",
    "infrastructure-operations": "Развертывание узлов, мониторинг и сопровождение сетей",
    "infrastructure-and-nodes": "Развертывание узлов, мониторинг и сопровождение сетей",
    "analytics-and-monitoring": "Аналитика распределенных реестров, телеметрия и мониторинг смарт-контрактов",
    "standards-and-protocols": "Отраслевые стандарты, форматы токенизации и протоколы взаимодействия",
    "business-cases-adoption": "Практические кейсы внедрения распределенных реестров",
}


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
