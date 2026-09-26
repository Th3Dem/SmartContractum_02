# Task: task-23-create-header-menu-dom-lenta — Создание меню в шапке с кнопками «Дом», «Лента» и «Вход»

- **Цель**:
  1. Создать единую верхнюю шапку меню (`<header class="app-header" id="appHeader">`) на страницах проекта (`frontend/public/index.html`, `frontend/public/feed.html`, `frontend/public/editor.html`).
  2. Добавить в шапку навигационное меню из двух страниц с соответствующими тематическими векторными SVG-иконками (стиль Lucide / 2px stroke, без эмодзи):
     - Первая кнопка: «Дом» (ссылка на `index.html`) с тематической SVG-иконкой дома.
     - Вторая кнопка: «Лента» (ссылка на `feed.html`) с тематической SVG-иконкой новостной ленты/потока статей.
  3. В правом углу шапки разместить кнопку «Вход» (`#headerLoginBtn` или ссылка на авторизацию `#auth`) с аккуратной тематической SVG-иконкой пользователя/входа.
  4. В левой части шапки сохранить или восстановить логотип бренда SmartContractum в соответствии с дизайн-системой.
  5. Реализовать корректную изоляцию активных состояний:
     - На `index.html`: активна кнопка «Дом» (`active is-active`).
     - На `feed.html`: активна кнопка «Лента» (`active is-active`).
     - На `editor.html`: кнопки навигации не имеют активного класса.
  6. Настроить CSS-стили шапки в `frontend/public/css/theme.css`:
     - Задать переменную `--header-height: 60px;` (или 64px) и стили сетки шапки (логотип слева, навигация по центру, кнопка входа справа).
     - Использовать строго шрифт Onest (`font-family: 'Onest', sans-serif`).
     - Настроить отступы и привязку в `editor.css` (`.editor-document-bar { top: var(--header-height); }`, `.sidebar-sticky-wrapper`) и `feed.css` / `index.html`.
  7. Актуализировать unit-тесты в `tests/test_feed_page_and_palette.py` и `tests/test_design_system_and_icons.py` под новую структуру шапки меню (2 пункта навигации «Дом» и «Лента», кнопка «Вход», соответствующие SVG-иконки).
  8. Добиться 100% успешного прохождения всех unit-тестов проекта (186/186 PASS).

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
    - `tests/test_publication_settings_and_moderation.py`
    - `tasks/task-23-create-header-menu-dom-lenta/*`
    - `WORKLOG.md`
  - Запрещено изменять:
    - `frontend/public/vendor/*`
    - `data/*`
    - `server.py`

- **Критерии приемки**:
  1. Шапка меню `<header class="app-header" id="appHeader">` присутствует на всех страницах (`index.html`, `feed.html`, `editor.html`) с единой, 100% совпадающей по структуре разметкой.
  2. В навигации присутствуют ровно 2 кнопки страниц: «Дом» (ведет на `index.html`) и «Лента» (ведет на `feed.html`).
  3. Рядом с названием каждой кнопки размещена векторная SVG-иконка, строго соответствующая теме («Дом» — дом, «Лента» — лента статей/поток).
  4. В правом углу шапки расположена кнопка «Вход» с иконкой.
  5. Для страницы `index.html` кнопка «Дом» выделена активным стилем, для `feed.html` — кнопка «Лента».
  6. Все стили используют семейство Onest, 100% Offline-First, внешние CDN отсутствуют.
  7. Панель редактора `#editorDocumentBar` в `editor.html` прикреплена сразу под шапкой без наслоений.
  8. Все 186 unit-тестов проекта проходят со статусом 100% PASS (0 failures, 0 errors).

- **Текущий статус**: DONE
- **Ответственный исполнитель**: pm_bot
- **Рабочая ветка / копия**: main
- **Блокер**: нет
- **Следующий шаг**: Задача полностью завершена (Done-Done). Ветка влита в main. Публикация (git push) ожидает явного разрешения пользователя.
- **Ссылки на отчеты**:
  - DEV: `tasks/task-23-create-header-menu-dom-lenta/DEV_HANDOVER.md`
  - QA: `tasks/task-23-create-header-menu-dom-lenta/QA_REVIEW.md`
  - GIT: `tasks/task-23-create-header-menu-dom-lenta/GIT_HANDOVER.md`
- **История попыток решения**:
  - [Попытка 1]: Разработка шапки меню и синхронизация unit-тестов Python (186/186 PASS) завершены успешно | Успешно
  - Счетчик попыток данного подхода: 0/2
