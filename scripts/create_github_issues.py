#!/usr/bin/env python3
"""
scripts/create_github_issues.py

Creates GitHub Issues for SmartContractum_02 based on the Code Review from 2026-09-29.
Can use GitHub CLI (gh) or GitHub REST API directly via GH_TOKEN / GITHUB_TOKEN.
"""

import os
import sys
import json
import urllib.request
import urllib.error
import subprocess

REPO = "Th3Dem/SmartContractum_02"
GITHUB_API = "https://api.github.com"

SPRINT_ISSUES = [
    # --- СПРИНТ 1: Быстрые фиксы критического UX и подготовка ---
    {
        "title": "[P1][backend/frontend] SC-006: Вернуть authorId в DTO статей для возможности принятия ответа автором",
        "labels": ["priority:P1", "area:backend", "area:frontend", "sprint:1", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-006**.
Затронутые файлы: `server.py:3247–3277`, `server.py:3740–3780`, `frontend/public/js/article.js:410–415`, `frontend/public/js/card.js:146–155`.

### Проблема и последствие
Серверные методы `handle_get_articles_list` и `handle_get_article_by_id` возвращают имя автора (`author`), но не возвращают идентификатор автора (`authorId` / `author_id`).
При этом интерфейс статьи в `article.js` проверяет `user.id === article.authorId`, чтобы отобразить автору вопроса действие «Принять как решение». Из-за отсутствия поля автор вопроса не видит кнопку решения через штатный UI.

### Критерии приемки
1. Эндпоинты `GET /api/articles` и `GET /api/articles/<id>` возвращают стабильное поле `authorId` в объекте статьи.
2. Карточка и страница статьи используют `authorId` для сверки прав автора.
3. Автор вопроса видит и может нажать «Принять решение» в браузере; сторонний пользователь кнопку не видит.
"""
    },
    {
        "title": "[P1][frontend] SC-007: Синхронизировать data-author-id в карточке и обработчике профиля автора",
        "labels": ["priority:P1", "area:frontend", "sprint:1", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-007**.
Затронутые файлы: `frontend/public/js/card.js:146–155`, `frontend/public/js/feed.js:5884–5893`.

### Проблема и последствие
В `card.js` кнопка автора рендерится с атрибутом `data-user-id`, в то время как делегированный обработчик в `feed.js` пытается прочитать `target.dataset.authorId`.
В результате клик по имени автора в карточке не открывает модальное окно профиля автора.

### Критерии приемки
1. Использовать единое имя атрибута `data-author-id` (или fallback `target.dataset.authorId || target.dataset.userId`).
2. Клик и переход с клавиатуры (Enter) по автору в любой карточке ленты открывают соответствующий профиль автора.
"""
    },
    {
        "title": "[P1][backend] SC-013: Отключить автоматическую верификацию компаний при саморегистрации",
        "labels": ["priority:P1", "area:backend", "sprint:1", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-013**.
Затронутые файлы: `server.py:385`, `server.py:2292–2299`, `server.py:2315–2320`, `frontend/public/js/feed.js:4792–4797`.

### Проблема и последствие
При создании компании через API в базу принудительно записывается `is_verified = 1`, а в ответе возвращается `isVerified: True`. Любая созданная пользователем компания автоматически получает бейдж «Верифицированная компания», что вводит в заблуждение пользователей сообщества.

### Критерии приемки
1. По умолчанию при создании компании `is_verified = 0`.
2. Бейдж «Верифицированная компания» отображается только у компаний, прошедших верификацию модератором.
3. Проверить демо-данные: явная маркировка проверенных компаний.
"""
    },

    # --- СПРИНТ 2: Устранение P0-уязвимостей безопасности ---
    {
        "title": "[P0][security/backend] SC-001: Заменить подмену identity на безопасную серверную аутентификацию",
        "labels": ["priority:P0", "area:security", "area:backend", "sprint:2", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-001** (БЛОКЕР РЕЛИЗА).
Затронутые файлы: `server.py:1291–1318`, `server.py:1463–1487`.

### Проблема и последствие
Метод `get_current_user()` принимает произвольный `userId` из cookie `sc_session`, заголовка `X-User-Id`, `Bearer` или query-параметра `?userId=...` без проверки секрета, цифровой подписи или срока действия.
Посетитель может представиться любым пользователем и получить доступ к чужим приватным данным, уведомлениям, настройкам и действиям автора.

### Критерии приемки
1. Внедрить генерацию случайных непрозрачных сессионных токенов на сервере с фиксацией в SQLite (`sessions` table).
2. Cookie сессии должны иметь флаги `HttpOnly`, `SameSite=Lax`, `Secure` (в HTTPS окружении).
3. Произвольный заголовок `X-User-Id` или `?userId=...` не авторизует пользователя.
4. `POST /api/auth/logout` отзывает сессию на сервере.
"""
    },
    {
        "title": "[P0][security/backend] SC-002: Закрыть доступ к очереди модерации и исключить подмену авторства",
        "labels": ["priority:P0", "area:security", "area:backend", "sprint:2", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-002** (БЛОКЕР РЕЛИЗА).
Затронутые файлы: `server.py:2919–3016`, `server.py:3071–3156`.

### Проблема и последствие
1. Эндпоинт `GET /api/moderation/list` не проверяет права администратора/модератора и отдает неопубликованные материалы всем гостям.
2. При вызове `POST /api/moderation/submit` поле `authorId` из payload может переопределять реального пользователя, позволяя публиковать статьи от чужого имени.
3. `GET /api/moderation/status` позволяет узнавать статус чужого `draftId`.

### Критерии приемки
1. `GET /api/moderation/list` и принятие решений требуют роли `moderator` / `admin` (401 для гостей, 403 для обычных пользователей).
2. Автор заявки берется исключительно из подтвержденной сессии текущего пользователя.
3. Обычный пользователь видит статус только своих собственных заявок.
"""
    },
    {
        "title": "[P0][security/backend] SC-003: Серверная allowlist-санитизация HTML публикаций от сохраненного XSS",
        "labels": ["priority:P0", "area:security", "area:backend", "sprint:2", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-003** (БЛОКЕР РЕЛИЗА).
Затронутые файлы: `server.py:1099–1247`, `server.py:2990–3040`, `frontend/public/js/article.js:1018–1023`.

### Проблема и последствие
Сервер сохраняет входящий `article_html` без валидации тегов и атрибутов, а `article.js` выводит его через `innerHTML`. Клиентская очистка легко обходится прямым запросом к API, создавая уязвимость Stored XSS.

### Критерии приемки
1. Реализовать строгую серверную allowlist-очистку HTML (разрешены только теги Quill: `p`, `h1-h3`, `blockquote`, `ul`, `ol`, `li`, `pre`, `code`, `table`, `thead`, `tbody`, `tr`, `th`, `td`, `img`, `a`, `strong`, `em`, `u`, `s`).
2. Удаление всех `script`, `iframe`, `object`, обработчиков событий `on*` (`onload`, `onerror`, `onclick`).
3. Ссылки `href` и `src` валидируются по схемам (`http`, `https`, `/media/`, `mailto:`); схемы `javascript:`, `data:` (кроме изображений) блокируются.
"""
    },
    {
        "title": "[P0][security/ops] SC-004: Изоляция загрузок SVG и запрет исполнения активного содержимого в origin сайта",
        "labels": ["priority:P0", "area:security", "area:ops", "sprint:2", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-004** (БЛОКЕР РЕЛИЗА).
Затронутые файлы: `image_decoder.py:352–381`, `server.py:3823–3865`, `server.py:3868–3924`.

### Проблема и последствие
Загруженный пользовательский SVG отдается как `image/svg+xml` из origin сайта без строгих заголовков CSP. При прямом открытии файла браузер исполняет содержащийся в SVG Javascript в контексте origin сайта.

### Критерии приемки
1. Пользовательские SVG при загрузке санитизируются (полное удаление `<script>`, обработчиков событий, внешних сущностей XML) либо пользовательские загрузки SVG запрещаются в пользу растровых форматов (PNG/WebP/JPEG).
2. При отдаче статических файлов из `/media/` выставлять заголовки безопасности: `Content-Disposition: inline`, `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'`.
"""
    },
    {
        "title": "[P1][security/backend] SC-005: Потоковое ограничение размера тела запроса и защита от декомпрессии PNG",
        "labels": ["priority:P1", "area:security", "area:backend", "sprint:2", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-005**.
Затронутые файлы: `server.py:2945–2950`, `server.py:3878–3891`, `image_decoder.py:85–100`, `image_decoder.py:391–435`.

### Проблема и последствие
1. Тело запроса вычитывается в память целиком до валидации размера.
2. Декодер PNG вызывает `zlib.decompress()` без ограничения распакованного объема (уязвимость к zip-бомбам).

### Критерии приемки
1. Проверка `Content-Length` до чтения тела: запросы свыше лимита немедленно отклоняются с кодом `413 Payload Too Large`.
2. Ограничение чтения из сокета до максимального размера тела (`max_bytes`).
3. Безопасное распаковывание PNG с лимитом буфера декомпрессии.
"""
    },

    # --- СПРИНТ 3: Надежность редактора и черновиков ---
    {
        "title": "[P1][frontend] SC-008: Устранить гонку автосохранения и потерю текста при переключении черновиков",
        "labels": ["priority:P1", "area:frontend", "sprint:3", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-008**.
Затронутые файлы: `frontend/public/js/drafts.js:98–107`, `frontend/public/js/drafts.js:272–345`, `frontend/public/js/drafts.js:409–414`.

### Проблема и последствие
Autosave отложен на 2 секунды. При создании нового черновика или переключении на другой черновик редактор немедленно очищается/подменяется, а отложенный таймер старого черновика теряет последние правки или сохраняет новое содержимое под старым ID.

### Критерии приемки
1. При переключении или создании черновика выполняется принудительный синхронный flush (сохранение текущего снимка) с ожиданием завершения транзакции.
2. Таймер autosave отменяется и привязывается строго к ID конкретного черновика.
3. Быстрое переключение черновиков не приводит к потере текста.
"""
    },
    {
        "title": "[P1][frontend] SC-009: Обеспечить честные статусы ошибок записи в IndexedDB / localStorage",
        "labels": ["priority:P1", "area:frontend", "sprint:3", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-009**.
Затронутые файлы: `frontend/public/js/drafts.js:144–147`, `frontend/public/js/drafts.js:177–214`.

### Проблема и последствие
В `drafts.js` fallback на localStorage подавляет исключения переполнения квоты, после чего UI все равно сообщает об успехе («Все изменения сохранены»). Promise IndexedDB резолвится по `request.onsuccess`, а не по `transaction.oncomplete`.

### Критерии приемки
1. Promise сохранения черновика ожидает `transaction.oncomplete`.
2. Ошибки квоты и сбои хранилища явно пробрасываются в UI с отображением ошибки пользователю вместо ложного сообщения об успешном сохранении.
"""
    },
    {
        "title": "[P1][frontend] SC-010: Исключить гонки запросов в ленте через AbortController и генерации запросов",
        "labels": ["priority:P1", "area:frontend", "sprint:3", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-010**.
Затронутые файлы: `frontend/public/js/feed.js:1026–1089`, `frontend/public/js/feed.js:3479–3487`, `frontend/public/js/feed.js:3567–3609`.

### Проблема и последствие
Конструкция `if (state.isLoading) return` блокирует новый запрос при смене вкладки или фильтра, если предыдущий запрос еще выполняется. Когда предыдущий медленный запрос завершается, его ответ перезаписывает состояние уже переключенной вкладки.

### Критерии приемки
1. Использовать `AbortController` для отмены устаревших сетевых запросов при смене вкладки/поиска.
2. Ввести счетчик поколений (`requestGeneration`): ответ рендерится только в том случае, если его поколение совпадает с текущим.
"""
    },
    {
        "title": "[P1][frontend] SC-011: Изолировать действие «Задать вопрос» от автовосстановления статей",
        "labels": ["priority:P1", "area:frontend", "sprint:3", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-011**.
Затронутые файлы: `frontend/public/js/main.js:48–52`, `frontend/public/js/publication.js:80–87`, `frontend/public/js/drafts.js:30–39`, `frontend/public/js/drafts.js:249–307`.

### Проблема и последствие
При переходе по ссылке `editor.html?type=question` асинхронный `autoRestore()` восстанавливает активный черновик статьи, перезатирая тип `question` на `article` и подставляя старый текст статьи.

### Критерии приемки
1. При наличии параметра `type=question` создается новый независимый черновик вопроса без подгрузки старой статьи.
2. Старый черновик сохраняется в списке черновиков и доступен для восстановления через панель «Черновики».
"""
    },
    {
        "title": "[P2][fullstack] SC-014: Привязать идемпотентность отправки публикации к ревизии черновика",
        "labels": ["priority:P2", "area:fullstack", "sprint:3", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-014**.
Затронутые файлы: `frontend/public/js/publication.js:1786–1804`, `server.py:2958–2986`.

### Проблема и последствие
Ключ `idempotencyKey` генерируется заново при каждом нажатии кнопки «Отправить». При сетевом сбое и повторной отправке на сервере создается дубликат заявки вместо возврата существующей.

### Критерии приемки
1. `idempotencyKey` связывается с конкретной неизмененной ревизией черновика.
2. Повторная отправка с тем же ключом возвращает существующую заявку без дублирования записи в модерации.
"""
    },

    # --- СПРИНТ 4: Доменная согласованность и качество ---
    {
        "title": "[P1][backend] SC-012: Проверка полномочий пользователя на публикацию от имени компании",
        "labels": ["priority:P1", "area:backend", "sprint:4", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-012**.
Затронутые файлы: `server.py:1222–1234`, `server.py:2990–3000`, `frontend/public/js/publication.js:409–450`.

### Проблема и последствие
Сервер не проверяет, имеет ли автор право публиковать материалы от имени выбранной компании (`companyId`). Любой пользователь может привязать публикацию к любой существующей компании.

### Критерии приемки
1. Проверка членства/роли автора в компании перед одобрением публикации от ее имени.
2. Попытка указать чужую компанию отклоняется с ошибкой 403 Forbidden.
"""
    },
    {
        "title": "[P2][fullstack] SC-015: Серверная фильтрация публикаций компаний до пагинации",
        "labels": ["priority:P2", "area:fullstack", "sprint:4", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-015**.
Затронутые файлы: `frontend/public/js/feed.js:4693–4710`, `server.py:3283–3360`.

### Проблема и последствие
Клиент запрашивает общие публикации, а затем фильтрует их на клиенте по признаку компании (`isCompany`). Если среди первых 10 статей компании нет, выдача ошибочно показывает пустое состояние.

### Критерии приемки
1. Сервер поддерживает фильтр `companyId` / `isCompany` на уровне SQL запроса до применения `LIMIT` и `OFFSET`.
2. Пагинация выдачи компании работает корректно без пропусков и ложных пустых экранов.
"""
    },
    {
        "title": "[P2][backend] SC-016: Унифицировать подсчет и инварианты сущностей «ответ», «комментарий» и «решение»",
        "labels": ["priority:P2", "area:backend", "sprint:4", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-016**.
Затронутые файлы: `server.py:2858–2872`, `server.py:3488–3494`, `server.py:3926–4008`.

### Проблема и последствие
Счетчик «без ответа» учитывает любые комментарии, включая уточнения. Вопрос с 1 комментарием и 0 ответов ошибочно пропадает из виджета «Вопросы без ответа». Статус решения можно установить обычному комментарию статьи.

### Критерии приемки
1. Ответ (`answer`) возможен только для публикаций с `materialType = 'question'`.
2. Статус решения (`is_solution = 1`) может быть установлен только ответу (`comment_type = 'answer'`).
3. Виджет «Вопросы без ответа» считает строго ответы (`comment_type = 'answer'`).
"""
    },
    {
        "title": "[P2][frontend] SC-017: Сохранять фильтр статуса вопросов (questionStatus) в URL и истории",
        "labels": ["priority:P2", "area:frontend", "sprint:4", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-017**.
Затронутые файлы: `frontend/public/js/feed.js:278`, `frontend/public/js/feed.js:349–406`.

### Проблема и последствие
Параметр `questionStatus` считывается из URL при загрузке, но метод `syncURL()` не сохраняет его обратно в адресную строку при переключении фильтров. Перезагрузка страницы сбрасывает выбранный статус.

### Критерии приемки
1. `syncURL()` корректно сериализует `questionStatus` в `searchParams`.
2. Состояние кнопок фильтра синхронизируется при переходах «Назад / Вперед» в браузере (`popstate`).
"""
    },
    {
        "title": "[P2][backend] SC-018: Разделить запуск сервера и демонстрационный seed данных",
        "labels": ["priority:P2", "area:backend", "sprint:4", "type:architecture"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-018**.
Затронутые файлы: `server.py:393–409`, `server.py:886–931`, `seed_data.py`.

### Проблема и последствие
Функция `init_db()` при каждом старте сервера принудительно перезаписывает демо-данные через UPSERT, что может повредить рабочую БД или изменить пользовательские настройки.

### Критерии приемки
1. Запуск приложения по умолчанию применяет только схему миграций (`CREATE TABLE IF NOT EXISTS`).
2. Наполнение демо-данными выносится в отдельную команду/скрипт (`scripts/seed.py` или флаг `--seed`).
"""
    },
    {
        "title": "[P2][backend] SC-019: Обработка невалидных JSON-типов без обрыва соединения",
        "labels": ["priority:P2", "area:backend", "sprint:4", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-019**.
Затронутые файлы: `server.py:1465–1474`, `server.py:2255–2266`, `server.py:2945–2959`.

### Проблема и последствие
В ряде эндпоинтов после `json.loads` вызываются методы словаря `.get()` и `.strip()` без проверки того, является ли корневой JSON объектом (`dict`). Передача массива `[]` или примитива приводит к необработанному `AttributeError` и 500 ошибке.

### Критерии приемки
1. Валидация типа корневого JSON объекта на входе во все POST/PUT обработчики.
2. Невалидные типы возвращают контролируемый `400 Bad Request` с понятным сообщением об ошибке.
"""
    },
    {
        "title": "[P2][frontend] SC-020: Устранить подмену серверных ошибок ленты демонстрационными статьями",
        "labels": ["priority:P2", "area:frontend", "sprint:4", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-020**.
Затронутые файлы: `frontend/public/js/feed.js:3567–3610`, `frontend/public/js/feed.js:3612–3671`.

### Проблема и последствие
При любой сетевой или серверной ошибке (500, 502) лента переходит в блок `catch` и отображает `FALLBACK_ARTICLES`, маскируя реальный сбой под успешную загрузку.

### Критерии приемки
1. Серверные ошибки (5xx) отображают блок ошибки с кнопкой «Повторить попытку» (`Retry`).
2. Оффлайн-фоллбэк отображается только при реальном отсутствии сети (`navigator.onLine === false`) с явным бейджем автономного режима.
"""
    },
    {
        "title": "[P2][fullstack] SC-021: Устранить двойное экранирование plain-text полей",
        "labels": ["priority:P2", "area:fullstack", "sprint:4", "type:bug"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-021**.
Затронутые файлы: `server.py:2833–2839`, `frontend/public/js/article.js:434`, `frontend/public/js/feed.js:5857`.

### Проблема и последствие
Тексты комментариев и профилей сохраняются на сервере после `html.escape`, а затем повторно экранируются фронтендом при вставке в DOM. Символы `&`, `<`, `>` отображаются пользователю как `&amp;amp;`, `&amp;lt;`.

### Критерии приемки
1. Plain-text сохраняется в исходном виде и экранируется один раз на границе вывода в DOM.
2. Ввод символов `& < > ""` отображается корректно.
"""
    },
    {
        "title": "[P2][qa/ci] SC-023: Внедрить базовый GitHub Actions CI с реальными браузерными проверками",
        "labels": ["priority:P2", "area:qa", "area:ci", "sprint:4", "type:task"],
        "body": """### Источник
Код-ревью от 29.09.2026, пункт **SC-023**.
Затронутые файлы: `.github/workflows/ci.yml`, сьюты тестов `tests/`.

### Проблема и последствие
В репозитории отсутствует автоматический CI запуск тестов. Многие существующие тесты полагаются на проверку подстрок в HTML/CSS/JS файлах, пропуская реальные баги браузерного взаимодействия (например, SC-006 и SC-007).

### Критерии приемки
1. Создать `.github/workflows/ci.yml` с запуском полного набора тестов на каждый push и pull request.
2. Добавить headless-браузерные смоук-тесты (Playwright / Selenium) для проверки ключевых пользовательских сценариев.
"""
    }
]

def get_existing_issue_titles():
    try:
        res = subprocess.run(
            ["gh", "issue", "list", "--repo", REPO, "--json", "title", "--limit", "200"],
            capture_output=True, text=True
        )
        if res.returncode == 0:
            data = json.loads(res.stdout)
            return {item.get("title", "").strip() for item in data}
    except Exception:
        pass
    return set()

def create_issue_gh(issue):
    cmd = [
        "gh", "issue", "create",
        "--repo", REPO,
        "--title", issue["title"],
        "--body", issue["body"]
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"OK: {issue['title']} -> {res.stdout.strip()}")
        return True
    else:
        print(f"ERR: {issue['title']} -> {res.stderr.strip()}")
        return False

def create_issue_api(issue, token):
    url = f"{GITHUB_API}/repos/{REPO}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "SmartContractum-PMBot"
    }
    payload = {
        "title": issue["title"],
        "body": issue["body"]
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"OK: #{data.get('number')} {issue['title']} -> {data.get('html_url')}")
            return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"HTTP ERR {e.code}: {err_body}")
        return False
    except Exception as e:
        print(f"ERR: {str(e)}")
        return False

def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    
    # Check if gh CLI is authenticated
    gh_auth = False
    try:
        check = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        gh_auth = (check.returncode == 0)
    except Exception:
        pass

    if not token and not gh_auth:
        print("Внимание: Не обнаружен токен авторизации GitHub (GH_TOKEN / GITHUB_TOKEN) и gh CLI не авторизован.")
        print("Для автоматического создания issues выполните:")
        print("  export GITHUB_TOKEN=<ваш_персональный_токен>")
        print("  python3 scripts/create_github_issues.py")
        print("\nЛибо авторизуйтесь через gh CLI: gh auth login")
        print(f"\nВсего подготовлено {len(SPRINT_ISSUES)} детальных issues по 4 спринтам.")
        sys.exit(1)

    existing_titles = get_existing_issue_titles() if gh_auth else set()
    print(f"Создание {len(SPRINT_ISSUES)} issues в {REPO} (уже существует: {len(existing_titles)})...")
    success_count = 0
    for issue in SPRINT_ISSUES:
        if issue["title"].strip() in existing_titles:
            print(f"SKIP (уже существует): {issue['title']}")
            success_count += 1
            continue

        if gh_auth:
            if create_issue_gh(issue):
                success_count += 1
        elif token:
            if create_issue_api(issue, token):
                success_count += 1
    print(f"\nЗавершено! Успешно обработано {success_count} из {len(SPRINT_ISSUES)} issues.")

if __name__ == "__main__":
    main()
