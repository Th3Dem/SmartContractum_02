# Task: task-22-remove-top-header-menu — Полное удаление шапки меню из проекта со всеми кнопками

- **Цель**:
  1. Полностью удалить верхнюю шапку меню (`<header class="app-header" id="appHeader">...</header>`) и все входящие в неё кнопки (логотип, пункты навигации «Главная», «Сообщество», «Редактор», переключатель темы, кнопка входа/профиля) со всех страниц проекта: `frontend/public/index.html`, `frontend/public/feed.html`, `frontend/public/editor.html`.
  2. Очистить и оптимизировать стили шапки в `frontend/public/css/theme.css` (а также сопутствующие правила в `editor.css` / `feed.css`), устранив неиспользуемые правила и гарантируя аккуратные верхние отступы контента страниц.
  3. Сохранить в неизменном виде функционал страницы редактора (панель документа `#editorDocumentBar`, рабочая область, сайдбар) и страницы ленты/главной.
  4. Актуализировать тесты в `tests/test_design_system_and_icons.py` и `tests/test_feed_page_and_palette.py`, зафиксировав требование полного отсутствия `#appHeader` на всех страницах.
  5. Подтвердить 100% успешное прохождение всех тестов проекта.

- **Границы изменений**:
  - Разрешено изменять:
    - `frontend/public/index.html`
    - `frontend/public/feed.html`
    - `frontend/public/editor.html`
    - `frontend/public/css/theme.css`
    - `frontend/public/css/editor.css`
    - `frontend/public/css/feed.css`
    - `tests/test_design_system_and_icons.py`
    - `tests/test_feed_page_and_palette.py`
    - `tasks/task-22-remove-top-header-menu/*`
    - `WORKLOG.md`
  - Запрещено изменять:
    - `frontend/public/vendor/*`
    - `data/*`
    - `server.py`

- **Критерии приемки**:
  1. Элемент `<header class="app-header" id="appHeader">` и все его дочерние элементы полностью удалены из `index.html`, `feed.html` и `editor.html`.
  2. Верстка страниц аккуратная, контент не наезжает на верхний край и не имеет лишних артефактов.
  3. Все автоматические тесты проходят успешно (100% PASS, 0 failures, 0 errors).

- **Текущий статус**: QA_APPROVED
- **Ответственный исполнитель**: git_bot
- **Рабочая ветка / копия**: feat/task-22-remove-top-header-menu
- **Блокер**: нет
- **Следующий шаг**: Вызов git_bot для выполнения этапа FINALIZE (фиксация атомарного коммита со снимком 8e3df8eb3c00587b56fa5eeb72adf69463d6ac2cc7da62097570d6086f581048 и локальное слияние в main).
- **Ссылки на отчеты**:
  - DEV: `tasks/task-22-remove-top-header-menu/DEV_HANDOVER.md`
  - QA: `tasks/task-22-remove-top-header-menu/QA_REVIEW.md`
  - GIT: `tasks/task-22-remove-top-header-menu/GIT_HANDOVER.md`
- **История попыток решения**:
  - [Попытка 1]: Полное удаление шапки меню со всеми кнопками и 100% синхронизация unit-тестов | Успешно
  - Счетчик попыток данного подхода: 0/2
