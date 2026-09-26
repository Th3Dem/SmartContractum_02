# Task: task-21-rebuild-unified-header-menu — Создание новой единой шапки меню с нуля с кнопкой «Сообщество»

- **Цель**:
  1. Написать с нуля чистый, современный код шапки меню (`#appHeader`), полностью исключив старые легаси-наработки и фрагменты.
  2. Сделать шапку на 100% идентичной по верстке, геометрии, шрифту Onest, размерам и стилям на всех трех страницах: `index.html`, `feed.html`, `editor.html`.
  3. В навигационном меню `#headerNav` реализовать 3 кнопки:
     - «Главная» (`#navIndex` -> `index.html`)
     - «Сообщество» (`#navCommunity` -> `feed.html`)
     - «Редактор» (`#navEditor` -> `editor.html`)
  4. Обеспечить корректное активное состояние (`nav-link active is-active`) строго для текущей страницы:
     - на `index.html` активна «Главная»;
     - на `feed.html` активно «Сообщество»;
     - на `editor.html` активен «Редактор».
  5. Централизовать стили шапки в `theme.css` с использованием стабильной 3-колоночной сетки (`grid-template-columns: 260px 1fr 260px;`), гарантирующей математически точное центрирование навигации и полное отсутствие дерганья/сдвигов.
  6. Синхронизировать тестовый набор `tests/test_feed_page_and_palette.py` и подтвердить 100% PASS всех тестов проекта.

- **Границы изменений**:
  - Разрешено изменять:
    - `frontend/public/index.html`
    - `frontend/public/feed.html`
    - `frontend/public/editor.html`
    - `frontend/public/css/theme.css`
    - `frontend/public/css/editor.css`
    - `frontend/public/css/feed.css`
    - `tests/test_feed_page_and_palette.py`
    - `tasks/task-21-rebuild-unified-header-menu/*`
    - `WORKLOG.md`
  - Запрещено изменять:
    - `frontend/public/vendor/*`
    - `data/*`
    - `server.py`

- **Критерии приемки**:
  1. Шапка в `index.html`, `feed.html` и `editor.html` написана заново в едином стиле и является на 100% идентичной по разметке, классам, шрифту Onest, размерам кнопок и поведению.
  2. В навигации присутствуют все 3 пункта: «Главная», «Сообщество», «Редактор», каждый из которых ведет на соответствующую страницу (`index.html`, `feed.html`, `editor.html`).
  3. На каждой странице подсвечивается только соответствующий активный пункт.
  4. При переходе между страницами шапка не прыгает, не дергается и не изменяет размеры.
  5. Все автоматические тесты проходят успешно (100% PASS, 0 failures, 0 errors).

- **Текущий статус**: QA_APPROVED
- **Ответственный исполнитель**: git_bot
- **Рабочая ветка / копия**: feat/task-21-rebuild-unified-header-menu
- **Блокер**: нет
- **Следующий шаг**: Фиксация коммита git_bot на этапе FINALIZE
- **Ссылки на отчеты**:
  - DEV: `tasks/task-21-rebuild-unified-header-menu/DEV_HANDOVER.md`
  - QA: `tasks/task-21-rebuild-unified-header-menu/QA_REVIEW.md`
  - GIT: `tasks/task-21-rebuild-unified-header-menu/GIT_HANDOVER.md`
- **История попыток решения**:
  - [Попытка 1]: Инициализация задачи создания новой единой шапки меню с нуля | В процессе
  - Счетчик попыток данного подхода: 0/2
