"""Demo content used by --seed and by tests."""
import base64
import json
import sqlite3
import sys

from backend.content import compute_snapshot_hash


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
            from tests.fixtures import seed_data
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
