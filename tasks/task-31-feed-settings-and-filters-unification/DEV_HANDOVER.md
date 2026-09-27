# Dev Handover: task-31-feed-settings-and-filters-unification

## Статус: READY_FOR_QA

- **Задача**: task-31-feed-settings-and-filters-unification — Доработка и визуально-поведенческая согласованность панелей «Настройка ленты» и «Фильтры», исключения и пагинация каталогов
- **Исполнители**: dev_bot (Frontend UI) & py_bot (Backend & Tests)
- **Рабочая ветка**: `feat/task-31-feed-settings-and-filters-unification`
- **Спецификация**: `tasks/task-31-feed-settings-and-filters-unification/TASK.md`
- **Логи проверок**:
  - Python Unit & Integration Tests: `tasks/task-31-feed-settings-and-filters-unification/logs/py_checks.log`

---

## 1. Реализованная серверная логика (py_bot)

### 1.1. База данных SQLite (`server.py`)
- В функции `init_db(db_path)` добавлена таблица исключений `user_feed_exceptions`:
  ```sql
  CREATE TABLE IF NOT EXISTS user_feed_exceptions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT NOT NULL,
      entity_type TEXT NOT NULL,
      entity_id TEXT NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE(user_id, entity_type, entity_id)
  )
  ```
- Созданы необходимые индексы:
  - `idx_exceptions_user_id`: по полю `user_id` для быстрой выборки всех исключений пользователя.
  - `idx_exceptions_lookup`: по составному ключу `(user_id, entity_type, entity_id)` для мгновенной проверки исключения конкретной сущности.
- Функция `init_db` идемпотентно инициализирует все 5 таблиц системы: `user_subscriptions`, `user_feed_exceptions`, `user_feed_settings`, `article_likes`, `article_comments`.

### 1.2. Эндпоинты исключений и взаимное исключение (`/api/exceptions` и `/api/exceptions/toggle`)
- `GET /api/exceptions`:
  - Возвращает структуру исключений текущего авторизованного пользователя:
    `{ success: True, exceptions: { authors: [...], topics: [...], tags: [...] }, total: int }`.
  - Для неавторизованных пользователей возвращает пустую структуру с `total: 0`.
- `POST /api/exceptions/toggle`:
  - Требует обязательной авторизации (для гостей возвращает `401 Unauthorized` с `requireAuth: True`).
  - Валидирует `type` (`author`, `topic`, `tag`) и `id`.
  - Переключает статус исключения: удаляет при повторном запросе (`isExcluded: False`) или добавляет при первом (`isExcluded: True`).
  - **Взаимное исключение**: при добавлении сущности в исключения (`isExcluded: True`) запись о подписке на эту же сущность автоматически удаляется из `user_subscriptions`.
- `POST /api/subscriptions/toggle`:
  - Дополнена логика взаимного исключения: при оформлении подписки (`isSubscribed: True`) запись об исключении этой же сущности автоматически удаляется из `user_feed_exceptions`.

### 1.3. Пагинация и поиск в каталоге сущностей (`GET /api/subscriptions/entities`)
- Поддержка параметров: `type` (`author`, `topic`, `tag`), `search` (поисковая строка без учета регистра), `limit` (по умолчанию 20), `offset` (по умолчанию 0).
- При указании параметра `type`:
  - Возвращает порцию элементов: `{ success: True, items: [...], total: int, limit: int, offset: int, hasMore: bool }`.
  - Элементы содержат поля: `id`, `title`, `count` (число опубликованных материалов), `isSubscribed` (bool), `isExcluded` (bool).
  - Для авторов возвращаются `role` и `avatar`.
  - Для типа `topic` гарантировано включение всех стандартных рубрик платформы (`STANDARD_TOPICS`), даже если по ним пока нет материалов (`count: 0`).
  - Поиск производит регистронезависимую фильтрацию по названию рубрики/тега или имени автора.
- Обратная совместимость: если параметр `type` не передан, эндпоинт отдает полную структуру со всеми тремя категориями `{ success: True, authors: [...], topics: [...], tags: [...] }`.

### 1.4. Фильтрация публикаций и наивысший приоритет исключений (`GET /api/articles`)
- **Приоритет исключений**:
  - Исключения обладают абсолютным приоритетом над подписками и параметрами ленты.
  - Публикация безусловно исключается из выдачи, если:
    1. Автор статьи исключен пользователем (`entity_type = 'author'`).
    2. Хотя бы одна из тем статьи исключена пользователем (`entity_type = 'topic'`).
    3. Хотя бы один из тегов/ключевых слов статьи исключен пользователем (`entity_type = 'tag'`).
  - Исключения действуют как в общей ленте (`tab=all`), так и в персональной «Моей ленте» (`tab=my`), а также при полнотекстовом поиске по ленте.
  - Исключения **не скрывают** публикацию при прямом обращении по ее ID (`GET /api/articles/<id>`) и в сохраненных закладках (`tab=saved` / параметр `ids`).
- **Расширенные фильтры ленты**:
  - Множественный выбор тем: параметры `topics` (через запятую) и `topic` с логикой «ИЛИ» внутри группы (статья включается, если относится хотя бы к одной из запрошенных тем).
  - Временные периоды (`period`):
    * `week`: публикации за последние 7 суток.
    * `month`: публикации за последние 30 суток.
    * `year`: публикации за последние 365 суток.
    * `custom`: произвольный диапазон с валидацией границ `dateFrom` и `dateTo`.
  - Режимы сортировки (`sort`):
    * `newest`: по дате публикации (`createdAt` DESC).
    * `popular`: по популярности (`likesCount` DESC, затем `createdAt` DESC).
    * `discussed`: по числу комментариев (`commentsCount` DESC, затем `createdAt` DESC).
  - Поддержка параметров формата (`format`) и целевой аудитории (`audience`).

### 1.5. Настройки ленты пользователя (`POST /api/user/feed-settings`)
- Валидация типов материалов: массив `materialTypes` обязателен и не может быть пустым. Попытка передать пустой список возвращает `400 Bad Request` с сообщением: «Выберите хотя бы один тип материала».
- Пакетное сохранение: эндпоинт поддерживает опциональные поля `subscriptions` и `exceptions` для пакетного применения списков интересов с контролем взаимного исключения.

---

## 2. Автоматизированные тесты (`tests/test_feed_page_and_palette.py`)

Реализован специализированный тестовый класс `TestTask31FeedSettingsAndFiltersUnification`:
1. `test_01_db_initialization_exceptions_table_and_indexes`: проверка создания таблицы `user_feed_exceptions`, ее колонок, уникального ограничения и индексов `idx_exceptions_user_id` и `idx_exceptions_lookup`.
2. `test_02_exceptions_toggle_and_mutual_exclusion_with_subscriptions`: проверка авторизации (401), тоггла статуса исключения и соблюдения инварианта взаимного исключения с таблицей `user_subscriptions`.
3. `test_03_subscription_entities_pagination_search_and_compat`: проверка постраничной выборки каталога (limit=20, offset, hasMore), регистронезависимого поиска, обязательного присутствия `STANDARD_TOPICS` и обратной совместимости при вызове без параметра `type`.
4. `test_04_feed_exception_priority_hiding_articles`: проверка приоритета исключений (автор, тема, тег) в режимах `tab=all` и `tab=my`, скрытия материалов даже при наличии подписки на автора.
5. `test_05_direct_article_access_and_saved_not_hidden_by_exceptions`: проверка доступности исключенных материалов при прямом переходе по ID публикации и в закладках пользователя (`tab=saved`).
6. `test_06_feed_filters_topics_or_logic_period_and_sort`: проверка объединения тем по логике «ИЛИ», фильтрации по периодам (`week`, `month`, `year`, `custom`) и сортировки (`newest`, `popular`, `discussed`).
7. `test_07_batch_feed_settings_with_subscriptions_and_exceptions`: проверка валидации `materialTypes` (400) и пакетного сохранения настроек, подписок и исключений.

### Актуализация существующих проверок
- Тесты разметки адаптированы под новую структуру выдвижной панели фильтров `#feedFiltersPanel` взамен устаревшего модального окна `#feedFiltersModal`.
- Добавлено корректное URL-кодирование (`urllib.parse.quote`) в тестовом HTTP-клиенте для безопасной передачи кириллических поисковых строк.

### Результаты прогона полного набора тестов:
- **Команда**: `python3 -m unittest discover tests -v`
- **Итог**: **259 / 259 тестов успешно пройдены (100% PASS, 0 FAILURES, 0 ERRORS)**.
- **Время выполнения**: ~5.2 сек.
- **Полный лог**: `tasks/task-31-feed-settings-and-filters-unification/logs/py_checks.log`.

---

## 3. Реализованный клиентский интерфейс (dev_bot)

### 3.1. Измененные файлы в рамках фронтенда
1. `frontend/public/feed.html`:
   - Полностью удалена модалка `#feedFiltersModal` и оверлей `.feed-modal-overlay`.
   - Обновлена кнопка `#btnFeedFiltersToggle` (`aria-controls="feedFiltersPanel"`).
   - Интегрирована выдвижная панель настроек `#feedSettingsPanel` с секциями типов материалов (4 тумблера), уровня сложности (5 кнопок со встроенными SVG-галочками), подписок/исключений (сегментированный переключатель, вкладки авторов/тем/тегов со счетчиками, персональный список и встроенный каталог поиска), футером с индикатором несохраненных изменений, кнопками «Отмена» и «Сохранить настройки».
   - Интегрирована выдвижная панель фильтров `#feedFiltersPanel` с мультивыбором типов, мультивыбором сложности, периодами (включая кастомные даты `dateFrom`/`dateTo`), сортировкой, мультивыбором тем со строкой поиска и съемными чипами выбранных тем, спойлером дополнительных параметров (формат, аудитория), действиями «Сбросить» и «Применить фильтры».
2. `frontend/public/css/feed.css`:
   - Добавлены стили `.feed-slide-panel` и `.feed-slide-panel-container` (max-width: 1360px, padding: 24px 28px, border-radius: 8px, анимация плавного появления сверху).
   - Стилизованы тумблеры материалов `.feed-tumbler-row`, кнопки множественного выбора `.feed-choice-btn` с SVG-галочками, сегментированный переключатель `.feed-segmented-control`, каталог `.feed-catalog-pane`, адаптивные пустые состояния `.feed-subs-empty-state`, индикатор несохраненных изменений `.feed-settings-unsaved-indicator`.
   - Стилизована сетка фильтров `.feed-filters-primary-grid`, съемные чипы тем `.filter-selected-chip`, раскрывающийся блок `.feed-filters-advanced`, чипы активных фильтров `.feed-active-chips-bar` и бейдж счетчика `.filter-count-badge`.
   - Добавлены медиа-запросы для планшетов (<= 1024px) и мобильных устройств (<= 768px).
3. `frontend/public/js/config.js`:
   - Обогащены описания (`description`) для всех 13 стандартных тем в `PublicationConfig.TOPICS` для информативного отображения в каталоге интересов.
4. `frontend/public/js/feed.js`:
   - Реализована русская плюрализация: `pluralize`, `pluralizePublications`, `pluralizeAuthors`, `pluralizeTopics`, `pluralizeTags`.
   - Реализовано управление черновиком настроек (`savedSettingsState`, `draftSettingsState`, `hasUnsavedSettingsChanges`, `validateMaterialTypes`, `updateSettingsDraftUI`).
   - Реализовано взаимное исключение панелей: открытие одной закрывает другую без оверлеев и без уничтожения черновика настроек в памяти.
   - Закрытие настроек по «Отмена», крестику, Escape или повторному клику сбрасывает несохраненный черновик к сохраненному состоянию.
   - Реализован пагинированный поиск по каталогу (порции по 20 элементов, кнопка «Показать ещё», debounce 250 мс, защита от race conditions через seq-счетчик).
   - Реализовано взаимное исключение подписок и исключений с информативными toast-уведомлениями.
   - Реализована клиентская фильтрация `filterArticleList()` с наивысшим приоритетом исключений (скрытие из общей и персональной ленты при совпадении автора, темы или тега).
   - Реализована панель активных чипов `#feedActiveChipsBar` со сбросом каждого фильтра по отдельности и кнопкой «Сбросить все».
   - Реализован счетчик групп ограничений на бейдже `#feedFiltersCountBadge` (поиск и сортировка исключены из подсчета).
   - Синхронизация параметров фильтрации в URL.
   - 100% Offline-First, Zero Emojis (чистые SVG), строгий шрифт Onest.

---

## 4. Инструкция для независимого аудита (QA)

1. **Запуск тестового набора**:
   ```bash
   python3 -m unittest discover tests -v
   ```
   Убедиться в прохождении всех 259 тестов (100% PASS).

2. **Запуск специализированных тестов задачи**:
   ```bash
   python3 -m unittest tests.test_feed_page_and_palette.TestTask31FeedSettingsAndFiltersUnification -v
   ```

3. **Проверка логов**:
   Ознакомиться с `tasks/task-31-feed-settings-and-filters-unification/logs/py_checks.log`.

4. **Критерии приемки**:
   - [x] Удаление модального окна фильтров с затемнением; обе панели — выпадающие под шапкой в 1360px контейнере.
   - [x] Взаимное исключение панелей настроек и фильтров.
   - [x] 3 раздела настроек: типы (4 тумблера, запрет пустого), сложность, подписки и исключения.
   - [x] Режимы «Подписки» и «Исключения» с вкладками авторов, тем, тегов и счетчиками пользователя.
   - [x] Пагинированный каталог (по 20) и поиск без сторонних модалок.
   - [x] Наивысший приоритет исключений в лентах `tab=all` и `tab=my`.
   - [x] Взаимное исключение подписки и исключения для одной сущности.
   - [x] Черновик настроек, отмена, сохранение в аккаунт.
   - [x] Мультивыбор фильтров (ИЛИ внутри группы, И между группами), периоды, сортировка.
   - [x] Активные чипы над лентой, счетчик на кнопке фильтров, синхронизация URL.
   - [x] Серверные таблицы, индексы, эндпоинты `/api/exceptions*` и `/api/subscriptions/entities`.
   - [x] 100% PASS тестов на Python.
   - [x] Onest, 100% Offline-First, Zero Emojis.
