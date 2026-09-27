# Dev Handover: task-28-feed-cover-sync-and-polish

## Статус: READY_FOR_QA

- **Задача**: task-28-feed-cover-sync-and-polish — Согласование загрузки обложки, предпросмотра и отображения в ленте
- **Исполнители**: dev_bot (Go & Frontend Developer) / py_bot (Python Backend & Tests Developer)
- **Рабочая ветка**: `feat/task-28-feed-cover-sync-and-polish`
- **Спецификация**: `tasks/task-28-feed-cover-sync-and-polish/TASK.md`
- **Логи проверок**:
  - Frontend: `tasks/task-28-feed-cover-sync-and-polish/logs/dev_checks.log`
  - Backend & Integration Tests: `tasks/task-28-feed-cover-sync-and-polish/logs/py_checks.log`

---

## 1. Реализованная фронтенд-функциональность (dev_bot)

В соответствии с регламентом `AGENTS.md` и спецификацией задачи полностью реализована фронтенд-часть по согласованию обложки, предпросмотра и отображения в ленте:

### 1.1. Единая конфигурация обложки (`frontend/public/js/config.js`)
- Добавлен объект конфигурации `COVER`:
  ```javascript
  COVER: {
    REQUIRED: false,
    ALLOWED_FORMATS: ['image/jpeg', 'image/png', 'image/webp', 'image/gif'],
    ALLOWED_EXTENSIONS: ['.jpg', '.jpeg', '.png', '.webp', '.gif'],
    MAX_FILE_BYTES: 10 * 1024 * 1024, // 10 МБ
    TARGET_WIDTH: 780,
    TARGET_HEIGHT: 440,
    ASPECT_RATIO_W: 39,
    ASPECT_RATIO_H: 22,
    ASPECT_RATIO_VALUE: 39 / 22, // ~1.7727
    ASPECT_RATIO_STR: '39 / 22',
    FEED_MAX_WIDTH_PX: 560,
    FEED_HEIGHT_AT_MAX_WIDTH: 316
  }
  ```
- Объект экспортирован в `window.PublicationConfig.COVER`.

### 1.2. Дизайн-токены обложки (`frontend/public/css/theme.css`)
- В `:root` добавлены централизованные токены:
  - `--card-cover-aspect-ratio: 39 / 22;`
  - `--card-cover-max-width: 560px;`

### 1.3. Настройки публикации и интерфейс загрузчика (`frontend/public/editor.html`)
- В секции `#pub-section-feed` обновлены пояснительные тексты:
  - Основное описание:
    «Обложка необязательна. Рекомендуемое разрешение — от 780 × 440 px. Область обложки — 39:22. JPG/JPEG, PNG, WebP или GIF, до 10 МБ. При необходимости можно выбрать кадр»
  - Подсказка:
    «В ленте обложка отображается в уменьшенном размере с сохранением выбранного кадра. Для GIF используется первый кадр без анимации».
- В блоке кадрирования установлен заголовок «Кадрирование обложки (39:22)».
- Блок живого предпросмотра `#pub-card-preview` перестроен в строгом соответствии с 7-ступенчатой структурой карточки ленты:
  1. Автор и дата (`.card-meta` -> `.author-info`)
  2. Заголовок статьи (`.card-title` / `.pub-feed-card-title`)
  3. Бейджи (`.card-meta-badges`: темы, формат, сложность)
  4. Обложка (`.card-cover-container` / `.pub-feed-card-cover`)
  5. Краткое описание (`.card-lead` / `.pub-feed-card-desc`)
  6. Ключевые слова (`.card-tags` / `.pub-feed-card-tags`)
  7. Время чтения и закладка (`.card-footer` / `.pub-feed-card-footer`)

### 1.4. Стили карточки предпросмотра (`frontend/public/css/editor.css`)
- Стилизован компонент `.pub-feed-card` и его внутренние элементы под карточки ленты:
  - `.pub-feed-card-cover`: ширина до `var(--card-cover-max-width, 560px)`, `aspect-ratio: var(--card-cover-aspect-ratio, 39 / 22)`, `align-self: flex-start`, скругление `var(--radius-md)`.
  - При отсутствии обложки зарезервировано строго 0px (`display: none !important; margin: 0 !important; height: 0 !important;`).
  - Обеспечена естественная адаптивность под модальное окно без ухудшающего читаемость общего `transform: scale()`.
  - Шрифт Onest соблюдается для всех текстовых элементов.

### 1.5. Логика кадрирования, обработки и предпросмотра (`frontend/public/js/publication.js`)
- Использование `PublicationConfig.COVER` для лимитов и пропорций.
- Валидация формата (JPEG, PNG, WebP, GIF) и размера до 10 МБ.
- Автоматическое распознавание пропорций 39:22 (с допуском epsilon ~0.02): при совпадении пропорций изображение сохраняется целиком без навязывания модалки кадрирования.
- При отличии пропорций — запуск кадрирования с фиксированным соотношением 39:22, плавным масштабированием (zoom) и перемещением (drag/pan) с учетом экранного масштаба canvas.
- Для GIF: рендеринг первого кадра на canvas и вывод пояснения: «Для GIF используется первый кадр в качестве статичной обложки».
- Предупреждение о разрешении ниже 780×440 px без блокировки сохранения.
- Повторное кадрирование и замена:
  - Сохранение исходного изображения (`this.rawCoverImageSource`) и параметров кадрирования (`this.cropParams = { zoom, panX, panY }`).
  - При повторном открытии кадрирования восстанавливаются выбранный зум и позиция.
  - Отмена кадрирования или ошибка замены восстанавливают ранее сохраненную обложку без ее стирания (`restoreCoverBackup()`).
  - Удаление обложки явно очищает данные и восстанавливает пустое состояние (0px).
- Сохранение в постоянный Data URL (без использования временных `blob:` URL).
- Метод `updateCardPreview()` наполняет карточку реальными данными черновика (автор платформы, дата «Недавно», реальный заголовок, бейджи выбранных тем, формата и сложности, обложка, реальные тэги #keywords, расчетное время чтения) без фиктивных дат и метрик.

### 1.6. Отображение карточек и обложек в ленте (`frontend/public/css/feed.css`, `frontend/public/js/feed.js`, `frontend/public/feed.html`)
- В `frontend/public/css/feed.css`:
  - `.card-cover-container`: `max-width: var(--card-cover-max-width, 560px); aspect-ratio: var(--card-cover-aspect-ratio, 39 / 22); align-self: flex-start; margin: 0 0 12px 0;`.
  - Описание `.card-lead` размещено строго под обложкой и ограничено 3 строками (`-webkit-line-clamp: 3; display: -webkit-box; -webkit-box-orient: vertical; overflow: hidden;`).
  - Уплотнены вертикальные отступы между ключевыми словами `.card-tags`, разделителем и нижней строкой `.card-footer`.
  - Нейтральные границы карточек по умолчанию, акцентные только при hover/focus.
  - Служебная строка выдачи над статьями (`.feed-toolbar-row`, `.feed-direct-toolbar`): убраны избыточные тени, оптимизированы отступы, обеспечено четкое позиционирование счетчика слева и сортировки справа с фильтрами снизу.
- В `frontend/public/js/feed.js`:
  - В `renderSidebarTopics`: в коротком списке сайдбара выводятся ТОЛЬКО темы с количеством публикаций > 0 (`count > 0`). Полный каталог (включая темы с 0) открывается по нажатию «Показать все».
  - В `createCardElement`: формат публикации выводится только если указан (значения `null`, `not_specified`, «Не указан» не рендерятся). Очищены заголовки от дублирующих префиксов `(демо)`, используется единый бейдж «Демонстрационный материал».
- В `frontend/public/feed.html`:
  - Строке панели инструментов над статьями присвоен единый класс `.feed-toolbar-row`.

---

## 2. Реализованная серверная логика и тесты (py_bot)

В соответствии с требованиями задачи и архитектурным регламентом:

### 2.1. Серверная валидация обложки (`server.py`)
- Добавлены константы лимитов размера:
  - `MAX_COVER_DECODED_BYTES = 10 * 1024 * 1024` (10 МБ декодированных данных).
  - `MAX_COVER_BASE64_CHARS = 14 * 1024 * 1024 + 1024` (~14 МБ base64 представления).
  - Регулярное выражение `COVER_DATA_URI_PATTERN` для валидации схемы Data URI с MIME-типами: `image/(jpeg|jpg|png|webp|gif|svg+xml);base64,...`.
- Реализована функция `validate_cover_image(cover_image: Any) -> Tuple[bool, Optional[str]]`:
  - Необязательность: `None`, пустая строка или строка из пробелов являются валидными (статья без обложки).
  - Тип: если передано непустое значение, оно обязано быть строкой.
  - Относительный путь: поддержка путей схемы `/media/...` с защитой от path traversal (`..`) и ограничением длины (до 500 символов).
  - Data URI: проверка структуры `data:image/...;base64,...`, валидности base64-кодирования и декодирования.
  - Проверка магических байтов:
    - JPEG (`image/jpeg`, `image/jpg`): заголовок `\xff\xd8\xff`.
    - PNG (`image/png`): сигнатура `\x89PNG`.
    - WebP (`image/webp`): заголовок `RIFF` с сигнатурой `WEBP` по смещению 8..12.
    - GIF (`image/gif`): сигнатуры `GIF87a` или `GIF89a`.
    - SVG (`image/svg+xml`): наличие тега `<svg` в структуре файла.
  - Проверка размера: ограничение до 10 МБ декодированных байтов.
  - Сообщения об ошибках: при невалидном формате, поврежденных данных или превышении размера формируется понятная ошибка: «Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.».
- Интеграция в `validate_submission_payload(payload)`:
  - Проверка `pub_settings.get("coverImage")` вынесена в цепочку валидации `field_errors["coverImage"]`.
  - Ключ `coverImage` включен в детерминированный список приоритета первого сообщения об ошибке `order`.
- Неизменяемость и выдача в API:
  - В `handle_moderation_submit`: валидированная обложка фиксируется в теле настроек публикации, защищается детерминированным хэшем снимка статьи `snapshot_hash` (SHA-256) и сохраняется в таблице `moderation_submissions`.
  - В `handle_get_article` и `handle_get_articles_list`: обложка выдается в ключе `coverImage`.

### 2.2. Комплексное тестовое покрытие (`tests/test_feed_page_and_palette.py`)
Создан тестовый класс `TestTask28CoverSyncAndFeedPolish`, содержащий 6 методов:
1. `test_unified_cover_config_and_tokens`:
   - Проверка `PublicationConfig.COVER` в `config.js` (780×440, 39:22, макс 10 МБ, форматы JPG/PNG/WebP/GIF).
   - Проверка дизайн-токенов `--card-cover-aspect-ratio: 39 / 22;` и `--card-cover-max-width: 560px;` в `theme.css`.
2. `test_editor_feed_section_texts_and_preview_markup`:
   - Проверка точных формулировок подсказок и описаний в `editor.html`.
   - Проверка 7-ступенчатой последовательности карточки предпросмотра `#pub-card-preview`:
     `автор -> заголовок -> бейджи -> обложка -> описание -> теги -> футер`.
3. `test_editor_css_preview_card_styles`:
   - Проверка стилей `.pub-feed-card-cover`: max-width 560px, aspect-ratio 39 / 22, выравнивание `align-self: flex-start`, 0px при скрытии обложки (`display: none !important; margin: 0 !important; height: 0 !important;`).
4. `test_feed_css_card_cover_and_compactness`:
   - Проверка контейнера обложки `.card-cover-container` в `feed.css`: max-width 560px, aspect-ratio 39 / 22, левое выравнивание.
   - Проверка ограничения `.card-lead` в 3 строки (`-webkit-line-clamp: 3; display: -webkit-box;`).
   - Проверка компактной строки панели инструментов `.feed-toolbar-row`.
5. `test_feed_sidebar_topics_only_with_positive_count`:
   - Проверка логики `renderSidebarTopics` в `feed.js`: отображение в коротком списке сайдбара только тем с опубликованными статьями (`count > 0`).
6. `test_server_cover_image_validation`:
   - Успешный прием валидного base64 изображения (JPEG, PNG, WebP, GIF, SVG, `/media/`).
   - Корректная обработка черновика без обложки (`None`, `""`, отсутствие ключа).
   - Отклонение невалидного base64 / поврежденных данных.
   - Отклонение невалидных магических байтов (поврежденный файл).
   - Отклонение неподдерживаемого MIME-типа (BMP, TIFF, etc.).
   - Отклонение изображения свыше 10 МБ.
   - Сквозная проверка через HTTP POST `/api/moderation/submit`: сохранение в БД и неизменяемость снимка.

---

## 3. Результаты локальных проверок

- **Unit-тесты проекта**: 238 из 238 успешно пройдены (100% PASS, 0 FAIL, 0 ERROR).
  ```bash
  python3 -m unittest discover tests -v
  # Ran 238 tests in 3.171s — OK
  ```
- **Лог проверок сохранен**: `tasks/task-28-feed-cover-sync-and-polish/logs/py_checks.log`.
- **Дизайн-система и типографика**:
  - Полное соответствие требованиям шрифта Onest (`font-family: 'Onest', sans-serif`).
  - 100% Offline-First (полное отсутствие CDN и внешних сетевых вызовов).
  - Векторные SVG-иконки в едином стиле, эмодзи не используются.

---

## 4. Передача на аудит `qa_bot`

Задача полностью реализована со стороны Frontend (`dev_bot`) и Backend & Tests (`py_bot`), локальные проверки успешно пройдены в полном объеме. Задача готова к независимому аудиту `qa_bot`.

> [!WARNING]
> **Напоминание о регламенте Git**: В соответствии с правилами `AGENTS.md`, `.agents/dev_bot.md` и `.agents/py_bot.md` команды `git commit` и `git push` разработчикам строго запрещены. Все коммиты и публикация в репозиторий осуществляются исключительно агентом `git_bot` после завершения разработки и согласования `qa_bot`.
