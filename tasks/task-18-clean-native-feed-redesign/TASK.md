# Task: task-18-clean-native-feed-redesign — Разработка чистой нативной ленты публикаций (feed.html) на дизайн-системе Projects_02 и удаление легаси-файлов

- **Цель**:
  1. Полностью удалить тяжелый немодульный легаси-балласт из `Projects_01`: `forum_social.css` (76 КБ), `forum_social.js` (52 КБ), `landing_main.css` (24 КБ), `hero_constellation.css` (12 КБ), `landing_main.js` (3 КБ).
  2. Убрать импорт `css/forum_social.css` из `editor.html`, сохранив единый визуальный стиль шапки на нативных токенах `theme.css`.
  3. Разработать с нуля легкую, современную и чистую страницу `frontend/public/feed.html` и ее стили/скрипты (`frontend/public/css/feed.css`, `frontend/public/js/feed.js`), полностью базирующиеся на дизайн-токенах `Projects_02` (`theme.css`, шрифт Onest 100% offline-first, строгие SVG-иконки).
  4. Обеспечить 100% консистентность шапки между `feed.html` и `editor.html` (логотип SmartContractum, 3 пункта меню: «Главная», «Сообщество», «Редактор», переключатель темы без багов инверсии, кнопка входа).
  5. Внедрить современную карточную ленту публикаций с фильтрами («Все», «Разработка», «Безопасность», «Дизайн»), метаданными (автор, дата, время чтения, теги), кнопкой перехода к написанию («Написать» -> `editor.html`) и отображением статей (включая интеграцию с локальными опубликованными материалами / очередью модерации).
  6. Актуализировать тестовый набор `tests/test_feed_page_and_palette.py` под новую нативную архитектуру (100% PASS, 0 failures).

- **Границы изменений**:
  - Разрешено изменять/удалять/создавать:
    - `frontend/public/feed.html`
    - `frontend/public/css/feed.css`
    - `frontend/public/js/feed.js`
    - `frontend/public/css/theme.css`
    - `frontend/public/css/editor.css`
    - `frontend/public/editor.html`
    - `frontend/public/index.html`
    - Удаление: `frontend/public/css/forum_social.css`, `frontend/public/css/landing_main.css`, `frontend/public/css/hero_constellation.css`, `frontend/public/js/forum_social.js`, `frontend/public/js/landing_main.js`
    - `tests/test_feed_page_and_palette.py`
    - `tests/test_editor_v3.py`
    - `tasks/task-18-clean-native-feed-redesign/*`
    - `WORKLOG.md`
  - Запрещено изменять:
    - модули ядра Quill в `frontend/public/vendor/quill/`
    - модули шрифта `frontend/public/vendor/fonts/`
    - базу данных SQLite `data/*`
    - `server.py` без необходимости

- **Критерии приемки**:
  1. Все легаси-файлы (`forum_social.*`, `landing_main.*`, `hero_constellation.*`) полностью удалены из проекта, а импорт `forum_social.css` удален из `editor.html`.
  2. Страница `frontend/public/feed.html` создана с нуля на нативной архитектуре `Projects_02`, использует только `css/theme.css` и собственный модульный `css/feed.css`.
  3. Шапка на `feed.html` и `editor.html` идентична по верстке и стилям: 3 пункта навигации («Главная», «Сообщество», «Редактор»), логотип, переключатель темы (`#btnThemeToggle`), кнопка входа. Переход между страницами бесшовный.
  4. На странице `feed.html` строго соблюдены стандарты проекта: 100% offline-first, только шрифт Onest, строгие векторные SVG-иконки, отсутствие эмодзи в интерфейсе.
  5. Корректная поддержка светлой и темной темы (цвета страниц и карточек берутся строго из CSS-переменных `--bg-page`, `--bg-card`, `--text-primary`, `--border-color` и т.д., без нечитаемого текста).
  6. Все unit-тесты в `tests/` проходят успешно (100% PASS, 0 failures, 0 errors).

- **Текущий статус**: QA_APPROVED
- **Ответственный исполнитель**: git_bot
- **Рабочая ветка / копия**: feat/task-18-clean-native-feed-redesign
- **Блокер**: нет
- **Следующий шаг**: Фиксация изменений git_bot на этапе FINALIZE
- **Ссылки на отчеты**:
  - DEV: `tasks/task-18-clean-native-feed-redesign/DEV_HANDOVER.md`
  - QA: `tasks/task-18-clean-native-feed-redesign/QA_REVIEW.md`
  - GIT: `tasks/task-18-clean-native-feed-redesign/GIT_HANDOVER.md`
- **История попыток решения**:
  - [Попытка 1]: Инициализация задачи создания нативной ленты и очистки от легаси | В процессе
  - Счетчик попыток данного подхода: 0/2
