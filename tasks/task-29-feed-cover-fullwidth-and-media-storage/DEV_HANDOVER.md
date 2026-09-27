# Dev Handover: task-29-feed-cover-fullwidth-and-media-storage

## Статус: READY_FOR_QA

- **Задача**: task-29-feed-cover-fullwidth-and-media-storage — Полноширинная обложка, общий компонент карточки, серверное хранилище медиа и глубокое декодирование изображений
- **Исполнители**: dev_bot (Frontend) / py_bot (Backend & Tests)
- **Рабочая ветка**: `feat/task-29-feed-cover-fullwidth-and-media-storage`
- **Базовый коммит**: `739e774`
- **Diff Snapshot Hash**: `aa73b71d56dd6dc4d94966ea57ecc82c2cf1d11b3b563847beb9ad5c215c9843`
- **Спецификация**: `tasks/task-29-feed-cover-fullwidth-and-media-storage/TASK.md`
- **Логи проверок**:
  - Hash: `tasks/task-29-feed-cover-fullwidth-and-media-storage/logs/hash.txt`
  - Unit & Integration Tests: `tasks/task-29-feed-cover-fullwidth-and-media-storage/logs/qa_checks.log`

---

## 1. Реализованная фронтенд-функциональность (dev_bot)

В строгом соответствии с требованиями пользователя и спецификацией задачи:

### 1.1. Полноширинная обложка в карточке (100% ширины контента)
- **Отмена ограничения 560 px**:
  - В `frontend/public/js/config.js` в `PublicationConfig.COVER` удалено ограничение `FEED_MAX_WIDTH_PX: 560`, установлены свойства `FEED_FULL_WIDTH: true` и `FEED_MAX_WIDTH: '100%'`.
  - В `frontend/public/css/theme.css` обновлен токен `--card-cover-max-width: 100%;` при сохранении соотношения `--card-cover-aspect-ratio: 39 / 22;`.
  - В `frontend/public/css/feed.css` контейнер `.card-cover-container` переведен на полноширинное отображение: `width: 100%; max-width: var(--card-cover-max-width, 100%); align-self: stretch; aspect-ratio: var(--card-cover-aspect-ratio, 39 / 22);`.
  - В `frontend/public/css/editor.css` карточка предпросмотра `.pub-feed-card` и контейнер `.pub-feed-card-cover` обновлены до `width: 100%; max-width: 100%; align-self: stretch;`.
- **Согласование краев**:
  - Левый и правый края обложки точно совпадают с краями текстового содержимого (заголовком, бейджами и описанием).
  - Стандартные внутренние отступы карточки (`padding: 18px 22px;` в десктопе, `padding: 18px 16px;` на мобильных экранах) сохранены без изменений.
  - Высота рассчитывается автоматически строго по пропорциям 39:22 (`aspect-ratio: 39 / 22; width: 100%; height: auto;`).
  - Описание расположено строго под изображением.
  - Изображение не искажается (`object-fit: cover; width: 100%; height: 100%;`).
  - На мобильных устройствах обложка естественно адаптируется к ширине карточки без горизонтального скролла.

### 1.2. Общий компонент формирования карточки (`frontend/public/js/card.js`)
- Создан модульный компонент `window.SmartContractumCard`, обеспечивающий:
  - Единый 7-ступенчатый порядок блоков:
    1. Автор и дата (`.card-meta`)
    2. Заголовок (`.card-title`)
    3. Бейджи (`.card-meta-badges`: тема, формат, сложность, демо)
    4. Обложка (`.card-cover-container` / `.pub-feed-card-cover`)
    5. Краткое описание (`.card-lead` / `.pub-feed-card-desc`)
    6. Ключевые слова (`.card-tags` / `.pub-feed-card-tags`)
    7. Футер (`.card-footer`: время чтения, закладка)
  - Поддержку параметров отображения и опции `isPreview: true` для формы публикации (с сохранением специфичных ID элементов `#preview-card-...` и отключенными интерактивными действиями).
  - Единые функции экранирования `escapeHtml`, очистки `cleanString` и генерации бейджей `getBadgesHtml`.
- Подключение:
  - Тег `<script src="js/card.js"></script>` добавлен в `frontend/public/feed.html` и `frontend/public/editor.html`.
  - В `frontend/public/js/feed.js`: генерация карточки делегирована в `SmartContractumCard.createCardElement(item, { isBookmarked })`.
  - В `frontend/public/js/publication.js`: живой предпросмотр `updateCardPreview()` использует `SmartContractumCard.renderCardInnerHtml(previewItem, { isPreview: true })`.

### 1.3. Чистота обложки (Zero Site Overlays)
- На обложку категорически не накладываются элементы сайта: заголовки, бейджи, водяные знаки, затемнения или оверлей-рамки.

### 1.4. Состояния отображения и ошибки
- Без обложки или при ошибке загрузки: строго 0px резервируемого места (`display: none !important; margin: 0 !important; height: 0 !important;`).
- При загрузке: сохранение пропорций 39:22 с шиммер-анимацией.
- При отмене кадрирования или сбое замены: сохранение ранее загруженной обложки.

---

## 2. Реализованная серверная логика и тесты (py_bot)

### 2.1. Глубокое декодирование изображений (`image_decoder.py`)
- Разработан автономный модуль декодирования и валидации изображений на чистом Python (без внешних зависимостей, 100% Offline-First):
  - **PNG**: проверка 8-байтовой сигнатуры `\x89PNG\r\n\x1a\n`, заголовка `IHDR` (размеры), чанков `IDAT` с декомпрессией потока через `zlib.decompress`, завершающего чанка `IEND`. Отклонение усеченных файлов без `IEND`.
  - **JPEG**: проверка маркера начала `\xff\xd8`, разбор сегментов `SOF` (SOF0..SOF15), парсинг `APP1` EXIF с учетом ориентации (Orientation 1..8), обязательная проверка маркера конца `EOI` (`\xff\xd9`). Отклонение усеченных данных без `EOI`.
  - **GIF**: поддержка `GIF87a`/`GIF89a`, проверка логического дескриптора экрана, дескрипторов блоков, завершающего трейлера `0x3B`. Проверка статичности: анимированные многокадровые GIF отклоняются, допускается только статичный первый кадр.
  - **WebP**: проверка контейнера `RIFF....WEBP`, парсинг чанков `VP8 `, `VP8L`, `VP8X`, извлечение размеров, подтверждение статичности.
  - **SVG**: проверка тега `<svg` и извлечение `viewBox`.
  - **Лимиты безопасности**: отклонение «пиксельных бомб» свыше 25 млн пикселей (`MAX_IMAGE_PIXELS = 25_000_000`) и файлов свыше 10 МБ.
  - **Пропорции**: строгая проверка пропорций 39:22 при установленном флаге `require_aspect_ratio`.

### 2.2. Серверное хранилище медиафайлов (`server.py`)
- Создана директория постоянного хранения `data/media/` (`MEDIA_DIR`).
- Реализована функция `save_media_file(data, ext, media_dir=None)`, вычисляющая SHA-256 хэш контента и сохраняющая файл по пути `data/media/<sha256>.<ext>`, возвращая постоянный URL `/media/<sha256>.<ext>`.
- Реализован класс `CoverValidationResult(tuple)`: обеспечивает обратную совместимость распаковки кортежа `is_valid, err = validate_cover_image(...)` для существующих тестов, а также предоставляет атрибуты `.saved_url`, `.meta`, `.image_bytes`.
- В `POST /api/moderation/submit`:
  - Входные Data URL обложек валидируются глубоким декодером, автоматически сохраняются в постоянное хранилище `data/media/` и заменяются в `publicationSettings["coverImage"]` на постоянный адрес `/media/<sha256>.<ext>`.
  - Зафиксированный в базе модерации снимок неизменяем и независим от дальнейших правок в локальном черновике.
- В публичном API выдачи статей (`GET /api/articles`):
  - Поле `coverImage` возвращает адрес `/media/...`.
  - Исходные несжатые файлы (`rawCoverImageSource`) и параметры кадрирования (`cropParams`) в публичную выдачу ленты не включаются.
- В HTTP-сервере добавлены эндпоинты:
  - `GET /media/<filename>` (`handle_serve_media`): раздача файлов с защитой от path traversal (`..`), корректным `Content-Type` (`image/jpeg`, `image/png`, `image/webp`, `image/gif`, `image/svg+xml`), кеширующими заголовками `Cache-Control: public, max-age=31536000, immutable` и CORS.
  - `POST /api/media/upload` (`handle_media_upload`): прием и сохранение медиафайлов как через JSON (с base64), так и в бинарном виде.

### 2.3. Комплексный тестовый набор (`tests/test_feed_page_and_palette.py`)
- В тест-сьют добавлен класс `TestTask29FullwidthCoverAndMediaStorage`:
  1. `test_tokens_and_fullwidth_cover_css`: отмена 560px ограничения, полноширинные токены и классы, 39:22 aspect-ratio, 0px при скрытии.
  2. `test_unified_card_js_component`: единый компонент `card.js`, 7-ступенчатый порядок, подключение в `feed.html` и `editor.html`, вызов из `feed.js` и `publication.js`.
  3. `test_image_decoder_deep_validation`: валидация форматов PNG, JPEG, GIF, WebP, SVG, отклонение усеченных PNG/JPEG, отклонение анимированных GIF, проверка пропорций 39:22.
  4. `test_server_media_upload_and_serving`: выгрузка через `POST /api/media/upload`, отдача через `GET /media/<filename>`, проверка MIME и `Cache-Control`, защита от path-traversal и 404 для отсутствующих файлов.
  5. `test_moderation_submit_converts_data_url_to_media_and_isolates_draft`: автоматическая конвертация Data URL в `/media/`, изоляция снимка модерации от правок черновика, отсутствие утечки `rawCoverImageSource` и `cropParams` в публичном API.
  6. `test_zero_site_overlays_on_cover`: отсутствие наложенных на обложку элементов оформления со стороны сайта.
- Результат прогона тестов проекта: **244 / 244 PASS (0 FAILURES, 0 ERRORS)**.

---

## 3. Файлы, готовые к аудиту QA

1. `frontend/public/js/config.js` — удаление 560px, полноширинный флаг.
2. `frontend/public/js/card.js` — новый единый модуль карточки публикации.
3. `frontend/public/feed.html` — подключение `card.js`.
4. `frontend/public/editor.html` — подключение `card.js`.
5. `frontend/public/css/theme.css` — токен `--card-cover-max-width: 100%`.
6. `frontend/public/css/feed.css` — полноширинный `.card-cover-container` (100%, 39:22).
7. `frontend/public/css/editor.css` — полноширинный `.pub-feed-card-cover` (100%, 39:22).
8. `frontend/public/js/feed.js` — интеграция `SmartContractumCard.createCardElement`.
9. `frontend/public/js/publication.js` — интеграция `SmartContractumCard.renderCardInnerHtml`.
10. `image_decoder.py` — новый глубокий валидатор и декодер изображений.
11. `server.py` — хранилище `data/media/`, маршруты `/media/*` и `/api/media/upload`, конвертация Data URL в модерации.
12. `tests/test_feed_page_and_palette.py` — актуализация и добавление тестов Task 29 (всего 244 теста).
