# Task: task-13-header-mode-toggle-and-author-guide-polish — Удаление переключателя режимов из шапки и редизайн памятки автору

- **Цель**:
  1. Удалить переключатель режимов «Редактирование / Предпросмотр» (`#mode-toggle`) из шапки редактора (`.app-header .header-center`).
  2. В блоке «Памятка автору» (`#widget-author-guide`) удалить иконку книги из строки заголовка и выровнять заголовок «Памятка автору» по правому краю блока.
  3. В памятке автору вместо стандартных буллетов списка добавить соответствующие технологичные векторные SVG-иконки (stroke-width="2", 0 эмодзи) и выполнить аккуратный рерайт 3 пунктов рекомендаций.
  4. Синхронизировать тестовые наборы `tests/test_editor_v3.py`, `tests/test_design_system_and_icons.py`, `tests/test_editor_habr_features.py`.

- **Границы изменений**:
  - Разрешено изменять:
    - `frontend/public/editor.html`
    - `frontend/public/css/editor.css`
    - `frontend/public/js/main.js`
    - `tests/test_editor_v3.py`
    - `tests/test_design_system_and_icons.py`
    - `tests/test_editor_habr_features.py`
    - `tasks/task-13-header-mode-toggle-and-author-guide-polish/*`
    - `WORKLOG.md`
  - Запрещено изменять:
    - `server.py`
    - `data/*`
    - файлы ядра quill/библиотеки в `vendor/`
    - остальные модули и тесты

- **Критерии приемки**:
  1. В `frontend/public/editor.html` элемент `#mode-toggle` (кнопки `#btn-mode-edit`, `#btn-mode-preview`) полностью удален из шапки редактора.
  2. В `frontend/public/js/main.js` отсутствие `#btn-mode-edit` и `#btn-mode-preview` обрабатывается корректно без JavaScript-ошибок.
  3. В `#widget-author-guide` строка заголовка не содержит иконок (удалена голубая иконка книги), заголовок «Памятка автору» выровнен по правому краю блока.
  4. Вместо стандартных маркеров списка буллетов каждый из 3 пунктов памятки содержит аккуратную векторную SVG-иконку (2px stroke, строгий стиль Lucide/Flaticon, без эмодзи) и переработанный текст:
     - Пункт 1: правила и этика сообщества.
     - Пункт 2: структура и заботливое оформление статьи.
     - Пункт 3: лимиты изображений (до 8 МБ в тексте статьи и до 1 МБ для обложки).
  5. Все 151 автоматических теста проходят успешно (100% pass).
  6. Полное соответствие `GEMINI.md`: 100% offline-first, только шрифт Onest, строгие SVG-иконки, 0 эмодзи.

- **Текущий статус**: IN_GIT
- **Ответственный исполнитель**: git_bot
- **Рабочая ветка / копия**: feat/task-13-header-mode-toggle-and-author-guide-polish
- **Блокер**: нет
- **Следующий шаг**: Этап FINALIZE в git_bot (проверка QA-хеша, атомарный коммит).
- **Ссылки на отчеты**:
  - DEV: `tasks/task-13-header-mode-toggle-and-author-guide-polish/DEV_HANDOVER.md`
  - QA: `tasks/task-13-header-mode-toggle-and-author-guide-polish/QA_REVIEW.md`
  - GIT: `tasks/task-13-header-mode-toggle-and-author-guide-polish/GIT_HANDOVER.md`
- **История попыток решения**:
  - [Попытка 1]: Инициализация задачи | Создание спецификации | В процессе
  - Счетчик попыток данного подхода: 0/2
