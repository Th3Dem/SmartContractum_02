# Task: task-20-remove-community-nav-item — Удаление пункта «Сообщество» из меню навигации в шапке на всех страницах

- **Цель**:
  1. Удалить пункт «Сообщество» (`#navCommunity`) из навигационного меню в шапке (`#headerNav`) на всех страницах: `index.html`, `feed.html`, `editor.html`.
  2. Оставить в меню ровно 2 пункта навигации: «Главная» (`#navIndex` -> `index.html`) и «Редактор» (`#navEditor` -> `editor.html`).
  3. Сохранить математически точное центрирование меню в 3-колоночной сетке шапки (`.header-container`) и 100% идентичность стилей, шрифта Onest и кнопок.
  4. Актуализировать тесты в `tests/test_feed_page_and_palette.py` (проверка 2 пунктов навигации и отсутствия «Сообщество» в списке навигации шапки).
  5. Обеспечить 100% прохождение всех автоматических тестов проекта (0 failures, 0 errors).

- **Границы изменений**:
  - Разрешено изменять:
    - `frontend/public/index.html`
    - `frontend/public/feed.html`
    - `frontend/public/editor.html`
    - `frontend/public/css/theme.css`
    - `tests/test_feed_page_and_palette.py`
    - `tasks/task-20-remove-community-nav-item/*`
    - `WORKLOG.md`
  - Запрещено изменять:
    - `frontend/public/vendor/*`
    - `data/*`
    - `server.py`

- **Критерии приемки**:
  1. Во всех трех файлах (`index.html`, `feed.html`, `editor.html`) в навигационном меню `#headerNav` присутствуют только 2 пункта: «Главная» и «Редактор». Пункт «Сообщество» полностью удален из шапки.
  2. Разметка, отступы, шрифт Onest и центрирование меню в шапке на 100% идентичны между всеми страницами, горизонтальные сдвиги отсутствуют.
  3. Все автоматические тесты проходят успешно (100% PASS, 0 failures, 0 errors).

- **Текущий статус**: DONE
- **Ответственный исполнитель**: pm_bot
- **Рабочая ветка / копия**: main
- **Блокер**: нет
- **Следующий шаг**: Задача полностью завершена (Done-Done). Ветка влита в main.
- **Ссылки на отчеты**:
  - DEV: `tasks/task-20-remove-community-nav-item/DEV_HANDOVER.md`
  - QA: `tasks/task-20-remove-community-nav-item/QA_REVIEW.md`
  - GIT: `tasks/task-20-remove-community-nav-item/GIT_HANDOVER.md`
- **История попыток решения**:
  - [Попытка 1]: Инициализация задачи по удалению пункта «Сообщество» из меню шапки | В процессе
  - Счетчик попыток данного подхода: 0/2
