#!/usr/bin/env python3
"""
seed_data.py — Reproducible Seed Data for SmartContractum
Provides:
- 13 Standard Directions / Topics with descriptions and metadata
- 5 Clubs (professional communities)
- 5 Companies (corporate blogs)
- 28 Authentic publications across topics, clubs, companies, and authors
- Varied likes and comments for realistic ranking in «В фокусе», «Топ» and «Новое»
- Default user subscriptions for user_demo
100% offline-first, Onest font, zero emojis.
"""

import base64
import datetime
import hashlib
import html
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple


def make_svg_data_uri(svg_markup: str) -> str:
    """Returns valid offline-first base64 data URI for SVG markup."""
    b64 = base64.b64encode(svg_markup.strip().encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def split_title_lines(title: str, max_chars: int = 34) -> Tuple[str, str]:
    """Splits title into two lines without breaking words in the middle."""
    words = title.strip().split()
    if not words:
        return "", ""
    line1_words = []
    line2_words = []
    curr_len = 0
    for w in words:
        w_len = len(w)
        if not line2_words and (curr_len == 0 or curr_len + 1 + w_len <= max_chars):
            line1_words.append(w)
            curr_len += (1 if curr_len > 0 else 0) + w_len
        else:
            line2_words.append(w)
    
    l1 = " ".join(line1_words)
    l2 = " ".join(line2_words)
    if len(l2) > 38:
        l2 = l2[:35].rsplit(" ", 1)[0] + "..."
    return l1, l2


def generate_svg_cover(badge_text: str, line1: str, line2: str, subtext: str, color1: str = "#38bdf8", color2: str = "#6366f1") -> str:
    """Generates standard 780x440 (39:22) SVG base64 cover image adhering to design system."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 440" width="780" height="440">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#060c18"/><stop offset="100%" stop-color="#0e1e38"/></linearGradient>
  <linearGradient id="acc" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="{color1}"/><stop offset="100%" stop-color="{color2}"/></linearGradient>
</defs>
<rect width="780" height="440" fill="url(#bg)"/>
<circle cx="620" cy="180" r="160" fill="none" stroke="rgba(56,189,248,0.12)" stroke-width="2"/>
<circle cx="620" cy="180" r="110" fill="none" stroke="rgba(99,102,241,0.18)" stroke-width="1.5" stroke-dasharray="8 6"/>
<circle cx="620" cy="180" r="60" fill="rgba(56,189,248,0.06)"/>
<rect x="64" y="64" width="200" height="32" rx="16" fill="rgba(56,189,248,0.12)" stroke="rgba(56,189,248,0.3)"/>
<text x="80" y="85" fill="{color1}" font-family="Onest, sans-serif" font-size="12" font-weight="700" letter-spacing="1">{html.escape(badge_text.upper())}</text>
<text x="64" y="160" fill="#ffffff" font-family="Onest, sans-serif" font-size="30" font-weight="800">{html.escape(line1)}</text>
<text x="64" y="202" fill="#94a3b8" font-family="Onest, sans-serif" font-size="30" font-weight="800">{html.escape(line2)}</text>
<line x1="64" y1="236" x2="380" y2="236" stroke="url(#acc)" stroke-width="3" stroke-linecap="round"/>
<text x="64" y="274" fill="#cbd5e1" font-family="Onest, sans-serif" font-size="15">{html.escape(subtext)}</text>
</svg>"""
    return make_svg_data_uri(svg)


STANDARD_TOPICS: List[Tuple[str, str]] = [
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

TOPICS_TITLE_MAP: Dict[str, str] = dict(STANDARD_TOPICS)

TOPICS_DESCRIPTION_MAP: Dict[str, str] = {
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

CLUBS_DATA = [
    {
        "id": "pksc-architects",
        "title": "Архитекторы ПКСК",
        "description": "Профессиональное сообщество разработчиков ядра, консенсуса и распределенных архитектур корпоративных сетей.",
        "avatar": None,
        "rules": "Конструктивные обсуждения архитектуры, открытый обмен опытом, аргументированные решения.",
        "owner_id": "author_smirnov",
        "directions": ["pksc-architecture", "infrastructure-operations"],
        "tags": ["ПКСК", "Архитектура", "Консенсус"],
        "created_at": "2026-09-01T10:00:00Z"
    },
    {
        "id": "smart-contracts-practice",
        "title": "Практика смарт-контрактов",
        "description": "Разработка, паттерны проектирования, оптимизация газа и безопасный код смарт-контрактов.",
        "avatar": None,
        "rules": "Только проверенные паттерны, код со ссылками на спецификации, без спама.",
        "owner_id": "user_demo",
        "directions": ["smart-contracts-development", "lifecycle-versioning"],
        "tags": ["Смарт-контракты", "Solidity", "Разработка"],
        "created_at": "2026-09-02T11:00:00Z"
    },
    {
        "id": "audit-and-security",
        "title": "Аудит и безопасность",
        "description": "Поиск уязвимостей, формальная верификация, тест-кейсы и стандарты безопасности распределенных реестров.",
        "avatar": None,
        "rules": "Ответственное раскрытие уязвимостей, соблюдение стандартов ИБ, воспроизводимые PoC.",
        "owner_id": "author_smirnov",
        "directions": ["audit-and-verification", "information-security", "testing-and-quality"],
        "tags": ["Аудит", "Безопасность", "Верификация"],
        "created_at": "2026-09-03T12:00:00Z"
    },
    {
        "id": "programmable-settlements",
        "title": "Программируемые расчеты",
        "description": "Интеграция цифрового рубля, двухфазные коммиты (2PC), атомарные сделки и смарт-контракты в финтехе.",
        "avatar": None,
        "rules": "Фокус на финтех-решениях, соответствие нормативной базе РФ, архитектурная чистота.",
        "owner_id": "user_demo",
        "directions": ["digital-ruble-payments", "business-logic-deals", "law-and-compliance"],
        "tags": ["Цифровой рубль", "Финтех", "Расчеты"],
        "created_at": "2026-09-04T13:00:00Z"
    },
    {
        "id": "defi-and-enterprise",
        "title": "Корпоративные блокчейн-системы",
        "description": "Интеграция корпоративных реестров с внешними API, оракулами данных и банковскими шлюзами.",
        "avatar": None,
        "rules": "Обсуждение практических внедрений в корпоративном секторе, интеграционные сценарии.",
        "owner_id": "author_smirnov",
        "directions": ["integrations-and-api", "oracles-and-data", "business-cases-adoption"],
        "tags": ["Интеграции", "Оракулы", "Корпоративные системы"],
        "created_at": "2026-09-05T14:00:00Z"
    }
]

COMPANIES_DATA = [
    {
        "id": "smarttech-innovations",
        "name": "ООО «СмартТех Инновации»",
        "description": "Ведущий разработчик корпоративных решений на базе смарт-контрактов и распределенных реестров для финансового сектора.",
        "specialization": "Архитектура распределенных реестров, разработка смарт-контрактов",
        "website": "smarttech-example.ru",
        "logo": None,
        "directions": ["pksc-architecture", "smart-contracts-development"],
        "owner_id": "user_demo",
        "is_verified": 1,
        "created_at": "2026-09-01T09:00:00Z"
    },
    {
        "id": "cryptosolutions-lab",
        "name": "АО «КриптоРешения Лаб»",
        "description": "Научно-производственная лаборатория криптографических протоколов, ГОСТ-шифрования и шлюзов безопасности.",
        "specialization": "Криптографическая защита, соответствие ГОСТ, безопасность узлов",
        "website": "cryptosolutions-example.ru",
        "logo": None,
        "directions": ["information-security", "testing-and-quality"],
        "owner_id": "author_smirnov",
        "is_verified": 1,
        "created_at": "2026-09-02T10:00:00Z"
    },
    {
        "id": "cyberinfra-tech",
        "name": "ООО «КиберИнфра Тех»",
        "description": "Провайдер высоконадежной инфраструктуры, мониторинга валидаторов и развертывания сетей распределенного реестра.",
        "specialization": "Инфраструктура узлов, DevOps/SRE, мониторинг реестров",
        "website": "cyberinfra-example.ru",
        "logo": None,
        "directions": ["infrastructure-operations", "integrations-and-api"],
        "owner_id": "author_smirnov",
        "is_verified": 0,
        "created_at": "2026-09-03T11:00:00Z"
    },
    {
        "id": "fintech-ledgers",
        "name": "ООО «ФинТех Реестры»",
        "description": "Интегратор систем цифрового рубля, оператор программируемых расчетов и автоматизированных аккредитивов.",
        "specialization": "Цифровой рубль, программируемые расчеты, комплаенс ЦБ РФ",
        "website": "fintech-ledgers-example.ru",
        "logo": None,
        "directions": ["digital-ruble-payments", "business-logic-deals", "law-and-compliance"],
        "owner_id": "user_demo",
        "is_verified": 1,
        "created_at": "2026-09-04T12:00:00Z"
    },
    {
        "id": "blockchain-audit-lab",
        "name": "АО «Блокчейн Аудит Лаб»",
        "description": "Независимый центр аудита смарт-контрактов, формальной верификации байткода и стресс-тестирования систем.",
        "specialization": "Аудит смарт-контрактов, формальная верификация, аудит кода",
        "website": "auditlab-example.ru",
        "logo": None,
        "directions": ["audit-and-verification", "testing-and-quality"],
        "owner_id": "author_smirnov",
        "is_verified": 1,
        "created_at": "2026-09-05T13:00:00Z"
    }
]

# Raw seed articles: Exactly 28 rich publications
ARTICLES_DATA = [
    {
        "id": "art-01",
        "draft_id": "draft-01",
        "title": "Интеграция смарт-контрактов с платформой цифрового рубля Банка России",
        "author_id": "author_smirnov",
        "author": "Алексей Смирнов",
        "authorInitials": "АС",
        "authorRole": "Архитектор решений",
        "targetAudience": "architects-integrators",
        "topics": ["digital-ruble-payments", "pksc-architecture", "smart-contracts-development"],
        "keywords": ["Цифровой рубль", "Банк России", "ПКСК", "Смарт-контракты", "Атомарные расчеты"],
        "description": "Архитектурный анализ взаимодействия шлюзов ПКСК с платформой цифрового рубля: моделирование атомарных транзакций, двухфазный коммит и валидация криптографических подписей по ГОСТ Р 34.12-2015.",
        "format": "tutorial",
        "complexity": "hard",
        "materialType": "article",
        "clubId": "pksc-architects",
        "clubTitle": "Архитекторы ПКСК",
        "companyId": "smarttech-innovations",
        "companyName": "ООО «СмартТех Инновации»",
        "created_at": "2026-09-26T14:30:00Z",
        "likes_count": 22,
        "badge_text": "ЦИФРОВОЙ РУБЛЬ",
        "subtext": "Архитектура шлюза • Двухфазный коммит 2PC • ГОСТ Р 34.10-2012"
    },
    {
        "id": "art-02",
        "draft_id": "draft-02",
        "title": "Аудит безопасности смарт-контрактов по ГОСТ Р 57580: типичные уязвимости и превентивный анализ",
        "author_id": "author_romanova",
        "author": "Екатерина Романова",
        "authorInitials": "ЕР",
        "authorRole": "Ведущий аудитор безопасности",
        "targetAudience": "security-auditors",
        "topics": ["information-security", "audit-and-verification", "smart-contracts-development"],
        "keywords": ["Аудит ИБ", "ГОСТ Р 57580", "Уязвимости", "Reentrancy", "Формальная верификация"],
        "description": "Разбор критических векторов атак на корпоративные распределенные реестры: повторный вход (reentrancy), ошибки управления доступом и методы автоматизированного аудита исходного кода.",
        "format": "review",
        "complexity": "hard",
        "materialType": "article",
        "clubId": "audit-and-security",
        "clubTitle": "Аудит и безопасность",
        "companyId": "cryptosolutions-lab",
        "companyName": "АО «КриптоРешения Лаб»",
        "created_at": "2026-09-25T18:15:00Z",
        "likes_count": 0,
        "badge_text": "БЕЗОПАСНОСТЬ",
        "subtext": "Превентивный анализ • ReentrancyGuard • Формальная верификация"
    },
    {
        "id": "art-03",
        "draft_id": "draft-03",
        "title": "Архитектура децентрализованного шлюза оракулов для распределенных реестров",
        "author_id": "author_kuznetsov",
        "author": "Михаил Кузнецов",
        "authorInitials": "МК",
        "authorRole": "Инженер интеграций",
        "targetAudience": "data-oracles",
        "topics": ["oracles-and-data", "integrations-and-api", "pksc-architecture"],
        "keywords": ["Оракулы", "Интеграции", "Поставка данных", "Медианный консенсус", "REST API"],
        "description": "Пошаговый разбор построения отказоустойчивой сети поставщиков доверенных данных: сбор котировок, консенсус валидаторов и передача криптографически подписанных payload в смарт-контракт.",
        "format": "retrospective",
        "complexity": "hard",
        "materialType": "article",
        "clubId": "defi-and-enterprise",
        "clubTitle": "Корпоративные блокчейн-системы",
        "companyId": "fintech-ledgers",
        "companyName": "ООО «ФинТех Реестры»",
        "created_at": "2026-09-24T11:00:00Z",
        "likes_count": 14,
        "badge_text": "ОРАКУЛЫ ДАННЫХ",
        "subtext": "Медианный консенсус • TLS-верификация • API шлюзы"
    },
    {
        "id": "art-04",
        "draft_id": "draft-04",
        "title": "Формальная верификация смарт-контрактов в банковских экосистемах",
        "author_id": "author_volkova",
        "author": "Елена Волкова",
        "authorInitials": "ЕВ",
        "authorRole": "Эксперт по информационной безопасности",
        "targetAudience": "security-auditors",
        "topics": ["audit-and-verification", "testing-and-quality", "information-security"],
        "keywords": ["Формальная верификация", "Аудит", "Безопасность", "Инварианты", "Certora"],
        "description": "Методология математического доказательства корректности работы смарт-контрактов: формализация инвариантов, спецификации на CVL и автоматизированный поиск нарушений логики.",
        "format": "tutorial",
        "complexity": "hard",
        "materialType": "article",
        "clubId": "audit-and-security",
        "clubTitle": "Аудит и безопасность",
        "companyId": "blockchain-audit-lab",
        "companyName": "АО «Блокчейн Аудит Лаб»",
        "created_at": "2026-09-23T11:00:00Z",
        "likes_count": 18,
        "badge_text": "ФОРМАЛЬНАЯ ВЕРИФИКАЦИЯ",
        "subtext": "Математические инварианты • CVL • Аудит байткода"
    },
    {
        "id": "art-05",
        "draft_id": "draft-05",
        "title": "Оптимизация EVM-байткода и паттерны экономии газа в Solidity 0.8.28",
        "author_id": "author_petrov",
        "author": "Дмитрий Петров",
        "authorInitials": "ДП",
        "authorRole": "Ведущий разработчик смарт-контрактов",
        "targetAudience": "smart-contracts-dev",
        "topics": ["smart-contracts-development", "pksc-architecture"],
        "keywords": ["Solidity", "Оптимизация газа", "EVM", "Байткод", "Yul"],
        "description": "Разбор новейших методов оптимизации исполнения смарт-контрактов: ассемблерные вставки Yul, упаковка слотов памяти transient storage (TLOAD/TSTORE) и кастомные ошибки.",
        "format": "tutorial",
        "complexity": "hard",
        "materialType": "article",
        "clubId": "smart-contracts-practice",
        "clubTitle": "Практика смарт-контрактов",
        "companyId": "smarttech-innovations",
        "companyName": "ООО «СмартТех Инновации»",
        "created_at": "2026-09-28T09:15:00Z",  # Today, high focus activity!
        "likes_count": 12,
        "badge_text": "ОПТИМИЗАЦИЯ ГАЗА",
        "subtext": "Solidity 0.8.28 • Yul • Transient Storage"
    },
    {
        "id": "art-06",
        "draft_id": "draft-06",
        "title": "Разбор критической уязвимости Reentrancy в контрактах пула ликвидности",
        "author_id": "author_petrov",
        "author": "Дмитрий Петров",
        "authorInitials": "ДП",
        "authorRole": "Ведущий Solidity-разработчик",
        "targetAudience": "security-auditors",
        "topics": ["audit-and-verification", "information-security"],
        "keywords": ["Аудит", "Reentrancy", "Уязвимости", "Ликвидность", "Эксплойты"],
        "description": "Детальный анализ реального инцидента: как перекрестный вызов внешнего токена позволил злоумышленнику нарушить баланс пула и как исключить подобные сценарии.",
        "format": "case-study",
        "complexity": "hard",
        "materialType": "article",
        "clubId": "audit-and-security",
        "clubTitle": "Аудит и безопасность",
        "companyId": "blockchain-audit-lab",
        "companyName": "АО «Блокчейн Аудит Лаб»",
        "created_at": "2026-09-28T07:30:00Z",  # Today
        "likes_count": 9,
        "badge_text": "БЕЗОПАСНОСТЬ",
        "subtext": "Разбор эксплойта • Read-only Reentrancy • Защита"
    },
    {
        "id": "art-07",
        "draft_id": "draft-07",
        "title": "Атомарные расчеты в цифровых рублях: практика применения протокола 2PC",
        "author_id": "author_kuznetsov",
        "author": "Михаил Кузнецов",
        "authorInitials": "МК",
        "authorRole": "Инженер интеграций",
        "targetAudience": "architects-integrators",
        "topics": ["digital-ruble-payments", "business-logic-deals"],
        "keywords": ["Цифровой рубль", "Атомарность", "2PC", "Платежи", "Смарт-контракты"],
        "description": "Проектирование и стресс-тестирование модуля двухфазной фиксации сделок при сопряжении частного блокчейна предприятия с инфраструктурой Банка России.",
        "format": "tutorial",
        "complexity": "medium",
        "materialType": "article",
        "clubId": "programmable-settlements",
        "clubTitle": "Программируемые расчеты",
        "companyId": "fintech-ledgers",
        "companyName": "ООО «ФинТех Реестры»",
        "created_at": "2026-09-27T20:00:00Z",  # Yesterday
        "likes_count": 15,
        "badge_text": "ПРОГРАММИРУЕМЫЕ РАСЧЕТЫ",
        "subtext": "Двухфазный коммит • Атомарность • Платежные шлюзы"
    },
    {
        "id": "art-08",
        "draft_id": "draft-08",
        "title": "Запуск валидатора узла ПКСК: пошаговое руководство по мониторингу в Prometheus",
        "author_id": "author_fedorov",
        "author": "Сергей Федоров",
        "authorInitials": "СФ",
        "authorRole": "DevOps / Инфраструктурный инженер",
        "targetAudience": "devops-sre",
        "topics": ["infrastructure-operations", "integrations-and-api"],
        "keywords": ["DevOps", "Валидаторы", "Prometheus", "Grafana", "Узлы ПКСК"],
        "description": "Развертывание production-ready узла валидатора: экспорт метрик консенсуса, мониторинг времени раунда, алертинг по потерянным блокам и защита RPC-интерфейса.",
        "format": "tutorial",
        "complexity": "medium",
        "materialType": "article",
        "clubId": "pksc-architects",
        "clubTitle": "Архитекторы ПКСК",
        "companyId": "cyberinfra-tech",
        "companyName": "ООО «КиберИнфра Тех»",
        "created_at": "2024-12-25T16:00:00Z",
        "likes_count": 7,
        "badge_text": "ИНФРАСТРУКТУРА",
        "subtext": "Prometheus • Grafana • Надежность валидаторов"
    },
    {
        "id": "art-09",
        "draft_id": "draft-09",
        "title": "Правовой статус смарт-контрактов в РФ: судебная практика и Федеральный закон № 259-ФЗ",
        "author_id": "author_volkova",
        "author": "Елена Волкова",
        "authorInitials": "ЕВ",
        "authorRole": "Юрист по цифровым активам",
        "targetAudience": "legal-compliance",
        "topics": ["law-and-compliance", "business-cases-adoption"],
        "keywords": ["Право", "ЦФА", "Законодательство", "Комплаенс", "Судебная практика"],
        "description": "Комплексный юридический анализ квалификации смарт-контрактов в гражданском обороте РФ: условия признания волеизъявления сторон и прецеденты арбитражных судов.",
        "format": "opinion",
        "complexity": "easy",
        "materialType": "article",
        "clubId": "programmable-settlements",
        "clubTitle": "Программируемые расчеты",
        "companyId": "fintech-ledgers",
        "companyName": "ООО «ФинТех Реестры»",
        "created_at": "2024-12-24T18:00:00Z",
        "likes_count": 14,
        "badge_text": "ПРАВО И КОМПЛАЕНС",
        "subtext": "ФЗ № 259-ФЗ • Судебные прецеденты • ЦФА"
    },
    {
        "id": "art-10",
        "draft_id": "draft-10",
        "title": "Поставка доверенных внешних данных: проектирование оракулов с мультиподписью",
        "author_id": "author_nesterov",
        "author": "Виктор Нестеров",
        "authorInitials": "ВН",
        "authorRole": "Инженер распределенных систем",
        "targetAudience": "data-oracles",
        "topics": ["oracles-and-data", "integrations-and-api"],
        "keywords": ["Оракулы", "Мультиподпись", "Поставка данных", "Schnorr", "ECDSA"],
        "description": "Архитектура децентрализованного оракула с агрегацией подписей BLS/Schnorr: защита от компрометации отдельных поставщиков данных и гарантированная доставка котировок.",
        "format": "tutorial",
        "complexity": "hard",
        "materialType": "article",
        "clubId": "defi-and-enterprise",
        "clubTitle": "Корпоративные блокчейн-системы",
        "companyId": "smarttech-innovations",
        "companyName": "ООО «СмартТех Инновации»",
        "created_at": "2024-12-23T14:00:00Z",
        "likes_count": 19,
        "badge_text": "ОРАКУЛЫ",
        "subtext": "Мультиподпись • Агрегация котировок • BLS"
    },
    {
        "id": "art-11",
        "draft_id": "draft-11",
        "title": "Обновление логики контрактов: прокси-паттерны UUPS vs Transparent Proxy",
        "author_id": "author_petrov",
        "author": "Дмитрий Петров",
        "authorInitials": "ДП",
        "authorRole": "Ведущий Solidity-разработчик",
        "targetAudience": "smart-contracts-dev",
        "topics": ["lifecycle-versioning", "infrastructure-operations"],
        "keywords": ["UUPS", "Proxy", "Обновление", "Solidity", "ERC-1967"],
        "description": "Сравнительный анализ архитектур обновления смарт-контрактов: экономия газа при деплое, предотвращение коллизий селекторов и безопасные миграции данных хранилища.",
        "format": "tutorial",
        "complexity": "hard",
        "materialType": "article",
        "clubId": "smart-contracts-practice",
        "clubTitle": "Практика смарт-контрактов",
        "companyId": "blockchain-audit-lab",
        "companyName": "АО «Блокчейн Аудит Лаб»",
        "created_at": "2024-12-22T16:00:00Z",
        "likes_count": 16,
        "badge_text": "ВЕРСИОНИРОВАНИЕ",
        "subtext": "UUPS • ERC-1967 • Миграция состояний"
    },
    {
        "id": "art-12",
        "draft_id": "draft-12",
        "title": "Тестирование смарт-контрактов: фаззинг и инварианты с использованием Echidna и Foundry",
        "author_id": "author_kuznetsov",
        "author": "Михаил Кузнецов",
        "authorInitials": "МК",
        "authorRole": "Инженер качества",
        "targetAudience": "qa-engineers",
        "topics": ["testing-and-quality"],
        "keywords": ["Фаззинг", "Foundry", "Echidna", "Тестирование", "Инварианты"],
        "description": "Практика фаззинг-тестирования контрактов децентрализованных реестров: составление инвариантных утверждений, генерация граничных условий и ускорение тестов в CI/CD.",
        "format": "tutorial",
        "complexity": "medium",
        "materialType": "article",
        "clubId": "audit-and-security",
        "clubTitle": "Аудит и безопасность",
        "companyId": "cryptosolutions-lab",
        "companyName": "АО «КриптоРешения Лаб»",
        "created_at": "2024-12-21T12:00:00Z",
        "likes_count": 13,
        "badge_text": "ТЕСТИРОВАНИЕ",
        "subtext": "Foundry • Echidna • Свойство-ориентированные тесты"
    },
    {
        "id": "art-13",
        "draft_id": "draft-13",
        "title": "Внедрение распределенного реестра в логистике поставок: разбор кейса",
        "author_id": "author_volkova",
        "author": "Елена Волкова",
        "authorInitials": "ЕВ",
        "authorRole": "Бизнес-аналитик",
        "targetAudience": "business-users",
        "topics": ["business-cases-adoption", "business-logic-deals"],
        "keywords": ["Логистика", "Внедрение", "Бизнес-кейсы", "Трекинг", "Смарт-контракты"],
        "description": "Экономический эффект внедрения реестра SmartContractum в цепочке поставок промышленного оборудования: сокращение времени верификации документов с 5 дней до 4 минут.",
        "format": "case-study",
        "complexity": "easy",
        "materialType": "article",
        "clubId": "defi-and-enterprise",
        "clubTitle": "Корпоративные блокчейн-системы",
        "companyId": "smarttech-innovations",
        "companyName": "ООО «СмартТех Инновации»",
        "created_at": "2024-12-20T11:00:00Z",
        "likes_count": 11,
        "badge_text": "БИЗНЕС-КЕЙС",
        "subtext": "Логистика поставок • Экономический эффект • ROI"
    },
    {
        "id": "art-14",
        "draft_id": "draft-14",
        "title": "Консенсус Raft в приватных сетях: тонкости настройки тайм-аутов и кворума",
        "author_id": "author_fedorov",
        "author": "Сергей Федоров",
        "authorInitials": "СФ",
        "authorRole": "Инфраструктурный инженер",
        "targetAudience": "devops-sre",
        "topics": ["pksc-architecture", "infrastructure-operations"],
        "keywords": ["Raft", "Консенсус", "Кворум", "Тайм-ауты", "Отказоустойчивость"],
        "description": "Глубокая настройка консенсусного модуля Raft: расчет heartbeat интервалов при географически распределенных узлах и сценарии восстановления после split-brain.",
        "format": "tutorial",
        "complexity": "hard",
        "materialType": "article",
        "clubId": "pksc-architects",
        "clubTitle": "Архитекторы ПКСК",
        "companyId": "cyberinfra-tech",
        "companyName": "ООО «КиберИнфра Тех»",
        "created_at": "2024-12-19T09:30:00Z",
        "likes_count": 10,
        "badge_text": "АРХИТЕКТУРА ЯДРА",
        "subtext": "Raft консенсус • Распределенный кворум • Split-brain"
    },
    {
        "id": "art-15",
        "draft_id": "draft-15",
        "title": "Эволюция архитектуры смарт-контрактов: от простых escrow до автономных протоколов",
        "author_id": "author_kovalev",
        "author": "Артем Ковалев",
        "authorInitials": "АК",
        "authorRole": "Архитектор решений",
        "targetAudience": "architects-integrators",
        "topics": ["pksc-architecture", "business-logic-deals"],
        "keywords": ["Архитектура", "Escrow", "Ретроспектива", "Автономность", "Протоколы"],
        "description": "Пятилетняя ретроспектива проектирования смарт-контрактов: какие паттерны доказали свою жизнеспособность в корпоративном секторе, а какие стали источником постоянных сбоев.",
        "format": "retrospective",
        "complexity": "medium",
        "materialType": "article",
        "clubId": "smart-contracts-practice",
        "clubTitle": "Практика смарт-контрактов",
        "companyId": "smarttech-innovations",
        "companyName": "ООО «СмартТех Инновации»",
        "created_at": "2024-12-18T10:00:00Z",
        "likes_count": 35,
        "badge_text": "РЕТРОСПЕКТИВА",
        "subtext": "5 лет опыта • Надежные паттерны • Архитектурные уроки"
    },
    {
        "id": "art-16",
        "draft_id": "draft-16",
        "title": "Безопасность корпоративных узлов: предотвращение Eclipse и Sybil атак",
        "author_id": "author_petrov",
        "author": "Дмитрий Петров",
        "authorInitials": "ДП",
        "authorRole": "Специалист по информационной безопасности",
        "targetAudience": "security-auditors",
        "topics": ["information-security", "infrastructure-operations"],
        "keywords": ["Eclipse-атака", "Sybil", "Пиринговые сети", "Сетевая безопасность", "Узлы"],
        "description": "Анализ сетевых векторов атак на уровне P2P протокола: белые списки статических пиров, ротация таблиц Kademlia и фильтрация недоверенных подключений.",
        "format": "tutorial",
        "complexity": "hard",
        "materialType": "article",
        "clubId": "audit-and-security",
        "clubTitle": "Аудит и безопасность",
        "companyId": "cryptosolutions-lab",
        "companyName": "АО «КриптоРешения Лаб»",
        "created_at": "2024-12-17T14:00:00Z",
        "likes_count": 21,
        "badge_text": "СЕТЕВАЯ БЕЗОПАСНОСТЬ",
        "subtext": "P2P защита • Kademlia • Предотвращение Eclipse"
    },
    {
        "id": "art-17",
        "draft_id": "draft-17",
        "title": "Как автоматизировать выставление счетов через смарт-контракты в 1С",
        "author_id": "author_kuznetsov",
        "author": "Михаил Кузнецов",
        "authorInitials": "МК",
        "authorRole": "Инженер интеграций",
        "targetAudience": "analysts",
        "topics": ["integrations-and-api", "business-logic-deals"],
        "keywords": ["1C", "Интеграции", "Счета", "Автоматизация", "REST API"],
        "description": "Практический туториал по связке корпоративной конфигурации 1С:Предприятие со смарт-контрактами платформы: автоматическое создание счетов при событии сделки.",
        "format": "tutorial",
        "complexity": "easy",
        "materialType": "article",
        "clubId": "programmable-settlements",
        "clubTitle": "Программируемые расчеты",
        "companyId": "fintech-ledgers",
        "companyName": "ООО «ФинТех Реестры»",
        "created_at": "2024-12-16T16:00:00Z",
        "likes_count": 18,
        "badge_text": "ИНТЕГРАЦИЯ 1С",
        "subtext": "1С:Предприятие • Смарт-счета • Вебхуки событий"
    },
    {
        "id": "art-18",
        "draft_id": "draft-18",
        "title": "Интервью с ведущим аудитором смарт-контрактов: главные ошибки разработчиков",
        "author_id": "author_volkova",
        "author": "Елена Волкова",
        "authorInitials": "ЕВ",
        "authorRole": "Технический журналист",
        "targetAudience": "smart-contracts-dev",
        "topics": ["audit-and-verification", "testing-and-quality"],
        "keywords": ["Интервью", "Аудит", "Ошибки", "Опыт", "Практика"],
        "description": "Большое интервью о скрытых ловушках при написании контрактов: почему unit-тесты не спасают от логических ошибок и как строить культуру безопасного кода в команде.",
        "format": "interview",
        "complexity": "easy",
        "materialType": "article",
        "clubId": "audit-and-security",
        "clubTitle": "Аудит и безопасность",
        "companyId": "blockchain-audit-lab",
        "companyName": "АО «Блокчейн Аудит Лаб»",
        "created_at": "2024-12-15T11:00:00Z",
        "likes_count": 24,
        "badge_text": "ИНТЕРВЬЮ",
        "subtext": "Беседа с аудитором • Типичные баги • Культура ИБ"
    },
    {
        "id": "art-19",
        "draft_id": "draft-19",
        "title": "Пакетная обработка транзакций (Batch Transactions) в высоконагруженных сетях",
        "author_id": "author_fedorov",
        "author": "Сергей Федоров",
        "authorInitials": "СФ",
        "authorRole": "Инфраструктурный инженер",
        "targetAudience": "architects-integrators",
        "topics": ["pksc-architecture", "integrations-and-api"],
        "keywords": ["Batching", "Транзакции", "Пропускная способность", "Мемпул", "Оптимизация"],
        "description": "Архитектура пакетной упаковки сделок: достижение 4500 транзакций в секунду за счет многоуровневого мерклирования и предварительной агрегации подписей в памяти узла.",
        "format": "tutorial",
        "complexity": "hard",
        "materialType": "article",
        "clubId": "pksc-architects",
        "clubTitle": "Архитекторы ПКСК",
        "companyId": "cyberinfra-tech",
        "companyName": "ООО «КиберИнфра Тех»",
        "created_at": "2024-12-14T09:00:00Z",
        "likes_count": 17,
        "badge_text": "ПРОИЗВОДИТЕЛЬНОСТЬ",
        "subtext": "4500 TPS • Batch Transactions • Мерклирование"
    },
    {
        "id": "art-20",
        "draft_id": "draft-20",
        "title": "Регуляторные требования к операторам информационных систем ЦФА в 2026 году",
        "author_id": "author_volkova",
        "author": "Елена Волкова",
        "authorInitials": "ЕВ",
        "authorRole": "Юрист по цифровым активам",
        "targetAudience": "legal-compliance",
        "topics": ["law-and-compliance", "digital-ruble-payments"],
        "keywords": ["Регуляторика", "ЦФА", "ЦБ РФ", "Операторы систем", "Требования"],
        "description": "Обзор обновленных указаний регулятора: правила допуска выпусков цифровых финансовых активов, обязательный аудит смарт-контрактов и протоколы резервного копирования данных.",
        "format": "opinion",
        "complexity": "medium",
        "materialType": "article",
        "clubId": "programmable-settlements",
        "clubTitle": "Программируемые расчеты",
        "companyId": "fintech-ledgers",
        "companyName": "ООО «ФинТех Реестры»",
        "created_at": "2024-12-13T12:00:00Z",
        "likes_count": 19,
        "badge_text": "РЕГУЛЯТОРИКА 2026",
        "subtext": "Операторы ЦФА • Требования Банка России • Стандарты"
    },
    {
        "id": "art-21",
        "draft_id": "draft-21",
        "title": "Архитектура оракулов ценовых котировок с взвешенным медианным консенсусом",
        "author_id": "author_semenov",
        "author": "Виктор Семенов",
        "authorInitials": "ВС",
        "authorRole": "Архитектор решений",
        "targetAudience": "data-oracles",
        "topics": ["oracles-and-data", "business-logic-deals"],
        "keywords": ["Оракулы", "Котировки", "Консенсус", "Медиана", "Финтех"],
        "description": "Математическая модель защиты от манипуляций мгновенными займами (Flash Loans): расчет временновзвешенных средних цен TWAP и фильтрация аномальных выбросов поставщиков.",
        "format": "tutorial",
        "complexity": "hard",
        "materialType": "article",
        "clubId": "defi-and-enterprise",
        "clubTitle": "Корпоративные блокчейн-системы",
        "companyId": "smarttech-innovations",
        "companyName": "ООО «СмартТех Инновации»",
        "created_at": "2024-12-12T15:00:00Z",
        "likes_count": 22,
        "badge_text": "TWAP ОРАКУЛЫ",
        "subtext": "Защита от Flash Loans • Взвешенная медиана • Математика"
    },
    {
        "id": "art-22",
        "draft_id": "draft-22",
        "title": "Памятка разработчика: 10 правил безопасной работы с криптографическими ключами",
        "author_id": "author_petrov",
        "author": "Дмитрий Петров",
        "authorInitials": "ДП",
        "authorRole": "Ведущий разработчик",
        "targetAudience": "smart-contracts-dev",
        "topics": ["information-security"],
        "keywords": ["Ключи", "Безопасность", "HSM", "Памятка", "Криптография"],
        "description": "Краткая и емкая сводка правил обращения с приватными ключами в production-средах: отказ от .env файлов, аппаратные модули HSM и регламент экстренной ротации.",
        "format": "tutorial",
        "complexity": "easy",
        "materialType": "post",
        "clubId": None,
        "clubTitle": None,
        "companyId": None,
        "companyName": None,
        "created_at": "2024-12-11T10:00:00Z",
        "likes_count": 28,
        "badge_text": "ПАМЯТКА",
        "subtext": "10 правил ИБ • Приватные ключи • Ротация HSM"
    },
    {
        "id": "art-23",
        "draft_id": "draft-23",
        "title": "Почему важно разделять бизнес-логику и хранилище данных в смарт-контрактах",
        "author_id": "author_kuznetsov",
        "author": "Михаил Кузнецов",
        "authorInitials": "МК",
        "authorRole": "Инженер интеграций",
        "targetAudience": "smart-contracts-dev",
        "topics": ["business-logic-deals", "pksc-architecture"],
        "keywords": ["Паттерны", "Eternal Storage", "Архитектура", "Хранилище", "Разделение ответственности"],
        "description": "Размышления о долгосрочной поддержке контрактов: преимущества паттерна Eternal Storage перед монолитными контрактами при частых изменениях бизнес-правил.",
        "format": "opinion",
        "complexity": "medium",
        "materialType": "article",
        "clubId": None,
        "clubTitle": None,
        "companyId": None,
        "companyName": None,
        "created_at": "2024-12-10T14:00:00Z",
        "likes_count": 15,
        "badge_text": "МНЕНИЕ",
        "subtext": "Eternal Storage • Архитектурная чистота • Паттерны"
    },
    {
        "id": "art-24",
        "draft_id": "draft-24",
        "title": "Опрос сообщества: какие инструменты отладки смарт-контрактов вы используете?",
        "author_id": "author_petrov",
        "author": "Дмитрий Петров",
        "authorInitials": "ДП",
        "authorRole": "Ведущий разработчик смарт-контрактов",
        "targetAudience": "smart-contracts-dev",
        "topics": ["testing-and-quality"],
        "keywords": ["Опрос", "Инструменты", "Отладка", "Hardhat", "Foundry"],
        "description": "Коллеги, поделитесь опытом: перешли ли вы полностью на связку Foundry + Chisel, или продолжаете использовать классический стек Hardhat с console.log?",
        "format": "none",
        "complexity": "none",
        "materialType": "question",
        "clubId": None,
        "clubTitle": None,
        "companyId": None,
        "companyName": None,
        "created_at": "2024-12-09T11:00:00Z",
        "likes_count": 12,
        "badge_text": "ВОПРОС",
        "subtext": "Опрос инженеров • Hardhat vs Foundry • Инструменты отладки"
    },
    {
        "id": "art-25",
        "draft_id": "draft-25",
        "title": "Открытие лаборатории формальной верификации смарт-контрактов в Санкт-Петербурге",
        "author_id": "author_fedorov",
        "author": "Сергей Федоров",
        "authorInitials": "СФ",
        "authorRole": "Представитель компании",
        "targetAudience": "security-auditors",
        "topics": ["audit-and-verification", "business-cases-adoption"],
        "keywords": ["Пресс-релиз", "Лаборатория", "Аудит", "Верификация", "Санкт-Петербург"],
        "description": "АО «Блокчейн Аудит Лаб» объявляет об открытии специализированного исследовательского центра по математическому анализу безопасности смарт-контрактов.",
        "format": "article",
        "complexity": "easy",
        "materialType": "news",
        "clubId": None,
        "clubTitle": None,
        "companyId": "blockchain-audit-lab",
        "companyName": "АО «Блокчейн Аудит Лаб»",
        "created_at": "2024-12-08T12:00:00Z",
        "likes_count": 9,
        "badge_text": "НОВОСТИ КОМПАНИИ",
        "subtext": "Открытие лаборатории • Научные исследования • R&D"
    },
    {
        "id": "art-26",
        "draft_id": "draft-26",
        "title": "Релиз шлюза межсетевого взаимодействия CyberInfra Gateway 2.0",
        "author_id": "author_fedorov",
        "author": "Сергей Федоров",
        "authorInitials": "СФ",
        "authorRole": "Технический директор",
        "targetAudience": "infrastructure-operations",
        "topics": ["infrastructure-operations", "integrations-and-api"],
        "keywords": ["Релиз", "Gateway", "Межсетевые шлюзы", "CyberInfra", "Инфраструктура"],
        "description": "ООО «КиберИнфра Тех» выпустила обновленную версию шлюза валидаторов с поддержкой шифрования ГОСТ Р 34.12-2015 и автоматической балансировкой очередей RPC.",
        "format": "article",
        "complexity": "medium",
        "materialType": "news",
        "clubId": None,
        "clubTitle": None,
        "companyId": "cyberinfra-tech",
        "companyName": "ООО «КиберИнфра Тех»",
        "created_at": "2024-12-07T09:00:00Z",
        "likes_count": 11,
        "badge_text": "РЕЛИЗ ПРОДУКТА",
        "subtext": "CyberInfra Gateway 2.0 • ГОСТ TLS • Балансировка"
    },
    {
        "id": "art-27",
        "draft_id": "draft-27",
        "title": "Обсуждение черновика стандарта токенизации прав требований в корпоративных ПКСК",
        "author_id": "author_kuznetsov",
        "author": "Михаил Кузнецов",
        "authorInitials": "МК",
        "authorRole": "Архитектор решений",
        "targetAudience": "analysts",
        "topics": ["business-cases-adoption", "business-logic-deals"],
        "keywords": ["Стандарты", "Токенизация", "Права требований", "RFC", "Дискуссия"],
        "description": "В клубе «Архитекторы ПКСК» открыто обсуждение предложенной спецификации интерфейса IClaimsToken для автоматического удержания и факторинга в реестре.",
        "format": "opinion",
        "complexity": "hard",
        "materialType": "post",
        "clubId": "pksc-architects",
        "clubTitle": "Архитекторы ПКСК",
        "companyId": None,
        "companyName": None,
        "created_at": "2024-12-06T16:00:00Z",
        "likes_count": 16,
        "badge_text": "ОБСУЖДЕНИЕ RFC",
        "subtext": "Спецификация IClaimsToken • Факторинг • Стандарты ПКСК"
    },
    {
        "id": "art-28",
        "draft_id": "draft-28",
        "title": "Сравнение производительности EVM vs WASM в корпоративных блокчейн-сетях",
        "author_id": "author_pavlov",
        "author": "Григорий Павлов",
        "authorInitials": "ГП",
        "authorRole": "Инженер ядра",
        "targetAudience": "smart-contracts-dev",
        "topics": ["pksc-architecture", "infrastructure-operations"],
        "keywords": ["EVM", "WASM", "Производительность", "Бенчмарки", "Смарт-контракты"],
        "description": "Результаты комплексных нагрузочных тестов: математические вычисления в WebAssembly выполняются на 420% быстрее EVM, однако сложность интеграции состояний выше.",
        "format": "case-study",
        "complexity": "hard",
        "materialType": "article",
        "clubId": "smart-contracts-practice",
        "clubTitle": "Практика смарт-контрактов",
        "companyId": None,
        "companyName": None,
        "created_at": "2024-12-05T10:00:00Z",
        "likes_count": 31,
        "badge_text": "БЕНЧМАРКИ",
        "subtext": "EVM vs WASM • +420% скорости • Стресс-тестирование"
    },
    {
        "id": "art-29",
        "draft_id": "draft-29",
        "title": "Как реализовать атомарный своп между Hyperledger Fabric и Masterchain без централизованного шлюза?",
        "author_id": "author_volkov",
        "author": "Сергей Волков",
        "authorInitials": "СВ",
        "authorRole": "Senior Blockchain Engineer",
        "targetAudience": "smart-contracts-dev",
        "topics": ["integrations-and-api", "pksc-architecture"],
        "keywords": ["Атомарный своп", "Hyperledger", "Masterchain", "Хэш-локи", "HTLC"],
        "description": "Изучаем архитектуру безопасного обмена активами между приватной сетью Hyperledger Fabric и Masterchain. Возможно ли обойтись схемой HTLC на стороне chaincode и смарт-контракта без доверенных ретрансляторов?",
        "format": "none",
        "complexity": "hard",
        "materialType": "question",
        "clubId": None,
        "clubTitle": None,
        "companyId": None,
        "companyName": None,
        "created_at": "2024-12-06T14:00:00Z",
        "likes_count": 5,
        "badge_text": "ВОПРОС",
        "subtext": "Атомарный своп • Fabric vs Masterchain • HTLC"
    },
    {
        "id": "art-30",
        "draft_id": "draft-30",
        "title": "Ошибка Out of Gas при пакетной выплате дивидендов в смарт-контракте ЦФА",
        "author_id": "author_morozova",
        "author": "Елена Морозова",
        "authorInitials": "ЕМ",
        "authorRole": "Руководитель направления смарт-контрактов",
        "targetAudience": "smart-contracts-dev",
        "topics": ["smart-contracts-development", "digital-ruble-payments"],
        "keywords": ["ЦФА", "Дивиденды", "Out of Gas", "Пакетная обработка", "Оптимизация"],
        "description": "При начислении купонного дохода более чем на 300 держателей транзакция падает по лимиту газа в блоке. Как лучше реструктурировать вызовы — pull over push или меркл-дерево выплат?",
        "format": "none",
        "complexity": "medium",
        "materialType": "question",
        "clubId": None,
        "clubTitle": None,
        "companyId": None,
        "companyName": None,
        "created_at": "2024-12-07T12:00:00Z",
        "likes_count": 8,
        "badge_text": "РЕШЕННЫЙ ВОПРОС",
        "subtext": "ЦФА • Дивиденды • Лимит газа • Оптимизация"
    },
]


def compute_snapshot_hash(title: str, article_html: str, publication_settings: Any) -> str:
    """Computes a deterministic SHA-256 hash of (title + article_html + publication_settings)."""
    if isinstance(publication_settings, dict):
        settings_str = json.dumps(publication_settings, sort_keys=True, ensure_ascii=False)
    elif isinstance(publication_settings, str):
        settings_str = publication_settings
    else:
        settings_str = json.dumps(publication_settings, ensure_ascii=False)

    content = f"{title.strip()}{article_html}{settings_str}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def seed_articles(conn: sqlite3.Connection):
    """Seeds the comprehensive publications into moderation_submissions idempotently."""
    for art in ARTICLES_DATA:
        cur = conn.cursor()
        cur.execute("SELECT id, article_html, publication_settings FROM moderation_submissions WHERE id = ?", (art["id"],))
        existing = cur.fetchone()

        badge_text = art.get("badge_text") or "SMARTCONTRACTUM"
        t = art["title"]
        line1, line2 = split_title_lines(t)
        subtext = art.get("subtext") or "Материал платформы SmartContractum"
        is_question = (art.get("materialType") == "question")
        cover_image = None if is_question else generate_svg_cover(badge_text, line1, line2, subtext)

        pub_settings = {
            "author": art["author"],
            "authorInitials": art["authorInitials"],
            "authorRole": art["authorRole"],
            "targetAudience": art["targetAudience"],
            "topics": art["topics"],
            "keywords": art["keywords"],
            "description": art["description"],
            "format": art["format"],
            "complexity": art["complexity"],
            "materialType": art.get("materialType", "article"),
            "clubId": art.get("clubId"),
            "clubTitle": art.get("clubTitle"),
            "companyId": art.get("companyId"),
            "companyName": art.get("companyName"),
            "isDemo": True,
            "coverImage": cover_image
        }

        if existing:
            body_html = existing["article_html"]
            try:
                curr_s = json.loads(existing["publication_settings"]) if existing["publication_settings"] else {}
                if curr_s.get("coverImage"):
                    pub_settings["coverImage"] = curr_s["coverImage"]
            except Exception:
                pass
            settings_str = json.dumps(pub_settings, ensure_ascii=False)
            h = compute_snapshot_hash(art["title"], body_html, pub_settings)
            conn.execute("""
                UPDATE moderation_submissions SET
                    publication_settings = ?,
                    snapshot_hash = ?,
                    created_at = ?,
                    updated_at = ?
                WHERE id = ?
            """, (settings_str, h, art["created_at"], art["created_at"], art["id"]))
        else:
            body_html = f"""<h2>{html.escape(art['title'])}</h2>
<p>{html.escape(art['description'])}</p>
<p>В данном материале представлены практические подходы, архитектурные решения и анализ лучших практик разработки распределенных реестров и смарт-контрактов в корпоративной среде.</p>"""
            settings_str = json.dumps(pub_settings, ensure_ascii=False)
            h = compute_snapshot_hash(art["title"], body_html, pub_settings)
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                art["id"], art["draft_id"], art["title"], art["author_id"],
                settings_str, body_html, f"seed_{art['id']}",
                h, art["created_at"], art["created_at"]
            ))


def seed_clubs(conn: sqlite3.Connection):
    """Seeds the 5 professional clubs idempotently."""
    for c in CLUBS_DATA:
        conn.execute("""
            INSERT INTO clubs (id, title, description, avatar, rules, owner_id, directions, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                rules = excluded.rules,
                directions = excluded.directions,
                tags = excluded.tags
        """, (
            c["id"], c["title"], c["description"], c["avatar"], c["rules"],
            c["owner_id"], json.dumps(c["directions"], ensure_ascii=False),
            json.dumps(c["tags"], ensure_ascii=False), c["created_at"], c["created_at"]
        ))


def seed_companies(conn: sqlite3.Connection):
    """Seeds the 5 companies idempotently."""
    for comp in COMPANIES_DATA:
        conn.execute("""
            INSERT INTO companies (id, name, description, specialization, website, logo, directions, owner_id, is_verified, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                specialization = excluded.specialization,
                website = excluded.website,
                directions = excluded.directions,
                is_verified = excluded.is_verified
        """, (
            comp["id"], comp["name"], comp["description"], comp["specialization"],
            comp["website"], comp["logo"], json.dumps(comp["directions"], ensure_ascii=False),
            comp["owner_id"], comp["is_verified"], comp["created_at"], comp["created_at"]
        ))


def seed_user_subscriptions(conn: sqlite3.Connection):
    """Seeds rich subscriptions for user_demo across author, club, company, topic, and tag."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM user_subscriptions WHERE user_id = 'user_demo'")
    row = cur.fetchone()
    if row and row["cnt"] >= 5:
        return

    default_subs = [
        ("user_demo", "topic", "smart-contracts-development", "Разработка смарт-контрактов", "2026-09-26T12:00:00Z"),
        ("user_demo", "author", "author_smirnov", "Алексей Смирнов", "2026-09-26T12:00:00Z"),
        ("user_demo", "club", "pksc-architects", "Архитекторы ПКСК", "2026-09-26T12:00:00Z"),
        ("user_demo", "company", "smarttech-innovations", "ООО «СмартТех Инновации»", "2026-09-26T12:00:00Z"),
        ("user_demo", "tag", "цифровой рубль", "Цифровой рубль", "2026-09-26T12:00:00Z"),
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, default_subs)


def seed_article_likes(conn: sqlite3.Connection):
    """Seeds realistic likes across articles with timestamps to create distinct feed rankings."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM article_likes")
    if cur.fetchone()["cnt"] >= 10:
        return

    likes_map = {
        "art-07": 4,
        "art-01": 3,
        "art-06": 2,
        "art-05": 1,
        "art-03": 1,
        "art-04": 1,
    }
    users = ["user_demo", "author_petrov", "author_kuznetsov", "author_volkova", "author_fedorov"]
    likes_rows = []
    for art in ARTICLES_DATA:
        art_id = art["id"]
        target_likes = likes_map.get(art_id, 0)
        if target_likes == 0:
            continue
        created_dt = datetime.datetime.fromisoformat(art["created_at"].replace("Z", "+00:00"))
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        for i in range(min(target_likes, len(users))):
            uid = users[i]
            if art_id in ("art-07", "art-01"):
                like_dt = max(created_dt + datetime.timedelta(hours=i * 2 + 1), now_dt - datetime.timedelta(hours=(i + 1) * 3))
            else:
                like_dt = created_dt + datetime.timedelta(hours=i * 2 + 1)
            likes_rows.append((art_id, uid, like_dt.strftime("%Y-%m-%dT%H:%M:%SZ")))

    conn.executemany("""
        INSERT OR IGNORE INTO article_likes (article_id, user_id, created_at)
        VALUES (?, ?, ?)
    """, likes_rows)


def seed_article_comments(conn: sqlite3.Connection):
    """Seeds comments and answers for articles with timestamps for rich discussions."""
    comments_data = [
        ("comm-seed-04", "art-06", "reader_05", "Павел Белов", None, "Read-only reentrancy — одна из самых коварных ошибок, спасибо за подробный PoC.", "published", "comment", 0, "2026-09-28T08:15:00Z"),
        ("comm-seed-05", "art-06", "reader_06", "Татьяна Ильина", None, "Применяется ли подобная защита в продакшене?", "published", "comment", 0, "2026-09-28T08:45:00Z"),
        ("comm-seed-06", "art-05", "reader_04", "Ольга Васильева", None, "Очень вовремя! Как раз проектируем пул с высокой частотой вызовов.", "published", "comment", 0, "2026-09-28T10:15:00Z"),
        ("comm-seed-07", "art-07", "reader_07", "Артем Ковалев", None, "Двухфазный коммит отлично закрывает риски рассинхронизации.", "published", "comment", 0, "2026-09-27T21:00:00Z"),
        ("comm-seed-08", "art-24", "reader_01", "Иван Соколов", None, "Мы перешли на Foundry около 6 месяцев назад. Скорость прогона тестов выросла примерно в 7 раз по сравнению с hardhat/ts. Возможность писать тесты на Solidity и фаззинг из коробки — главное преимущество.", "published", "answer", 0, "2026-09-28T09:00:00Z"),
        ("comm-seed-09", "art-24", "reader_02", "Анна Куликова", None, "Уточните, как вы решаете задачу деплоймент-скриптов с интеграцией в корпоративный CI/CD на gitlab?", "published", "comment", 0, "2026-09-28T09:30:00Z"),
        ("comm-seed-10", "art-30", "author_fedorov", "Сергей Федоров", None, "Рекомендую перейти на pull-паттерн (Claiming) с использованием SafeMath и ReentrancyGuard: смарт-контракт фиксирует общую сумму и номер транша, а каждый держатель самостоятельно забирает причитающуюся сумму отдельной транзакцией, либо через генерацию Merkle proof. Это снижает сложность до O(1) на стороне эмитента и полностью исключает блокировку блока.", "published", "answer", 1, "2026-09-27T14:30:00Z"),
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO article_comments (id, article_id, user_id, author_name, author_avatar, content, status, comment_type, is_solution, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, comments_data)


def seed_user_profiles(conn: sqlite3.Connection):
    """Seeds initial user profiles."""
    profiles = [
        ("author_smirnov", "Алексей Смирнов", "Lead Blockchain Developer", "InnoTech", "Архитектура смарт-контрактов, EVM и корпоративные блокчейн-системы. Автор открытых библиотек для ЦФА.", None),
        ("author_morozova", "Елена Морозова", "Руководитель направления смарт-контрактов", "Fintech Lab", "Специализация на программируемых расчетах в цифровых рублях и токенизации прав требований.", None),
        ("author_fedorov", "Сергей Федоров", "Эксперт по безопасности смарт-контрактов", "АО «Блокчейн Аудит Лаб»", "Формальная верификация, безопасность кода смарт-контрактов и аудит протоколов.", None),
        ("author_kuznetsov", "Михаил Кузнецов", "Архитектор решений", "Клуб «Архитекторы ПКСК»", "Моделирование корпоративных смарт-контрактов и разработка стандартов взаимодействия.", None)
    ]
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for uid, name, spec, comp, bio, avatar in profiles:
        conn.execute("""
            INSERT OR IGNORE INTO user_profiles (user_id, name, specialization, company, bio, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, name, spec, comp, bio, avatar, now_iso, now_iso))

