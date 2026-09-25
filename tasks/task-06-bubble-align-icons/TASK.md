# Task: task-06-bubble-align-icons — Перенос выравнивания текста в основную панель Bubble Toolbar в виде иконок и удаление кнопки «Еще»

- **Цель**: Модернизировать контекстную панель форматирования выделенного текста (`#bubble-toolbar`):
  1. Убрать кнопку «Еще» (`#bubble-more-btn`) и выпадающее меню (`#bubble-more-menu`).
  2. Вынести 4 функции выравнивания текста (по левому краю, по центру, по правому краю, по ширине) непосредственно в основную полосу панели Bubble Toolbar.
  3. Оформить кнопки выравнивания в виде лаконичных векторных SVG-иконок в общем стиле редактора с корректной подсветкой активного состояния (`is-active`).

- **Границы изменений**:
  - Разрешено изменять/создавать:
    - `frontend/public/editor.html`
    - `frontend/public/js/bubble.js`
    - `frontend/public/css/editor.css`
    - `tasks/task-06-bubble-align-icons/**`
    - `tests/**` (обновление и добавление тестов)
    - `WORKLOG.md`
  - Запрещено изменять:
    - `.agents/**`
    - `AGENTS.md`

- **Критерии приемки (DoD)**:
  1. Кнопка «Еще» и выпадающее меню `#bubble-more-menu` полностью удалены из `#bubble-toolbar`.
  2. В панели `#bubble-toolbar` присутствуют 4 кнопки выравнивания текста:
     - Слева (`data-format="align"`, `data-value=""`)
     - По центру (`data-format="align"`, `data-value="center"`)
     - Справа (`data-format="align"`, `data-value="right"`)
     - По ширине (`data-format="align"`, `data-value="justify"`)
  3. Кнопки оформлены SVG-иконками единого стиля (15x15px), с русскими подсказками (title/aria-label).
  4. Клик по иконке выравнивания мгновенно применяет форматирование выравнивания через Quill (`editor.format('align', value)`), не сбрасывая выделения.
  5. Активное выравнивание подсвечивается классом `is-active`.
  6. Все существующие и новые автоматические тесты проходят на 100%.

- **Текущий статус**: DONE
- **Ответственный исполнитель**: pm_bot
- **Рабочая ветка / копия**: feat/task-06-bubble-align-icons
- **Блокер**: нет
- **Следующий шаг**: слияние ветки feat/task-06-bubble-align-icons в main
- **Ссылки на отчеты**:
  - DEV: `tasks/task-06-bubble-align-icons/DEV_HANDOVER.md`
  - QA: `tasks/task-06-bubble-align-icons/QA_REVIEW.md`
  - GIT: `tasks/task-06-bubble-align-icons/GIT_HANDOVER.md`
  - OPS: `tasks/task-06-bubble-align-icons/OPS_HANDOVER.md`
- **История попыток решения**:
  - [Попытка 1]: Инициализация задачи переноса кнопок выравнивания в Bubble Toolbar
  - Счетчик попыток данного подхода: 1/2
