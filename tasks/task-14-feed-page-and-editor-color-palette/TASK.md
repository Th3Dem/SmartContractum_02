# Task: task-14-feed-page-and-editor-color-palette — Клонирование страницы ленты (feed) из Projects_01, внедрение шрифта Onest и применение дизайнерской цветовой гаммы в редакторе

- **Цель**:
  1. Скопировать и адаптировать страницу ленты публикаций (`feed.html`) из `Projects_01` в `Projects_02` (`frontend/public/feed.html`) с сопутствующими стилями и скриптами.
  2. Сделать полноценную шапку меню в самом верху страницы ленты публикаций (логотип SmartContractum, навигация: Главная, Сообщество, Эксперты, База знаний, Редактор, переключатель темы, вход).
  3. Обеспечить сквозную навигацию между лентой (`feed.html`) и редактором (`editor.html`).
  4. Применить на странице `feed.html` шрифт **Onest** (100% offline-first, удалив все внешние зависимости от Google Fonts).
  5. Применить на странице `editor.html` дизайнерскую цветовую гамму ленты (CoinMarketCap Midnight Navy `#0b1426`, темные карточки `#171924`, границы `#222531`, акценты `#3861fb`, `#38bdf8`, `#16c784`, радиальные градиенты фона).
  6. Синхронизировать тестовые наборы и добавить проверку страницы ленты и палитры.

- **Границы изменений**:
  - Разрешено изменять/создавать:
    - `frontend/public/feed.html`
    - `frontend/public/css/landing_main.css`
    - `frontend/public/css/hero_constellation.css`
    - `frontend/public/css/forum_social.css`
    - `frontend/public/js/landing_main.js`
    - `frontend/public/js/forum_social.js`
    - `frontend/public/css/theme.css`
    - `frontend/public/css/editor.css`
    - `frontend/public/editor.html`
    - `frontend/public/index.html`
    - `tests/test_feed_page_and_palette.py`
    - `tests/test_editor_v3.py`
    - `tests/test_design_system_and_icons.py`
    - `tasks/task-14-feed-page-and-editor-color-palette/*`
    - `WORKLOG.md`
  - Запрещено изменять:
    - модули ядра Quill в `frontend/public/vendor/quill/`
    - данные SQLite `data/*`

- **Критерии приемки**:
  1. Страница `frontend/public/feed.html` создана и доступна по адресу `/feed.html`.
  2. Шапка меню вверху `feed.html` полностью соответствует референсу из `Projects_01`: логотип, навигация, переключатель тем, кнопка входа.
  3. Кнопка «Редактор» в навигации шапки и кнопка «Написать» в панели управления ведут на `editor.html`.
  4. В шапке `editor.html` логотип/ссылка ведет на `feed.html`.
  5. На странице `feed.html` полностью исключены внешние запросы к Google Fonts (100% offline-first), везде применен шрифт **Onest**.
  6. На странице `editor.html` применена дизайнерская цветовая гамма со страницы ленты: глубокий фон `#0b1426` с мягкими свечениями, карточки и боковые блоки `#171924`, границы `#222531`, технологичные сине-голубые акценты `#3861fb` / `#38bdf8` и мятный `#16c784`. По умолчанию редактор открывается в этой фирменной темной гамме (`data-theme="dark"`).
  7. Все автоматические тесты проходят успешно (100% PASS, 0 failures, 0 errors).

- **Текущий статус**: QA_APPROVED
- **Ответственный исполнитель**: git_bot
- **Рабочая ветка / копия**: feat/task-14-feed-page-and-editor-color-palette
- **Блокер**: нет
- **Следующий шаг**: Фиксация коммита на этапе FINALIZE в git_bot и слияние ветки.
- **Ссылки на отчеты**:
  - DEV: `tasks/task-14-feed-page-and-editor-color-palette/DEV_HANDOVER.md`
  - QA: `tasks/task-14-feed-page-and-editor-color-palette/QA_REVIEW.md`
  - GIT: `tasks/task-14-feed-page-and-editor-color-palette/GIT_HANDOVER.md`
- **История попыток решения**:
  - [Попытка 1]: Инициализация задачи | Разработка и аудит завершены, вердикт APPROVED | Успешно
  - Счетчик попыток данного подхода: 0/2
