# Task: task-16-fix-editor-visual-and-theme-issues — Устранение дефектов отображения текста, темы оформления, унификация шапки и шрифта Onest в редакторе (editor.html)

- **Цель**:
  1. **Устранить проблему белого текста на белом фоне**:
     - В `theme.css` и `landing_main.css` переменная `--text-primary` перебивалась на `#ffffff`, что в светлой теме приводило к белому тексту в редакторе и заголовке на белом фоне карточки.
     - Добавить явные высококонтрастные правила для `[data-theme="light"]` (`--text-primary: #0f172a;`, `--bg-page: #f8fafc;`, `--bg-editor: #ffffff;`, `--bg-card: #ffffff;`, границы `#e2e8f0;`) и `[data-theme="dark"]` (`--text-primary: #ffffff;`, `--bg-page: #0b1426;`, `--bg-editor: #171924;`).
     - Гарантировать 100% контрастность и видимость всего текста (заголовок, текст статьи Quill, счетчики, плейсхолдеры, виджеты, модальные окна) в обеих темах.
  2. **Исправить и синхронизировать переключение тем (тёмная / светлая)**:
     - Обеспечить идеальную работу тумблера темы `#btnThemeToggle` в шапке и пункта в меню действий `#btn-theme-toggle`.
     - Корректно переключать атрибут `data-theme` на `<html>`, синхронизировать ключи `ag_theme` и `sc_theme` в `localStorage`, обновлять анимацию солнца/луны на тумблере и тему подсветки Highlight.js.
     - Подключить необходимые стили светлой темы из `forum_social.css` в `editor.html`.
  3. **Сделать шапку меню на самом верху точной копией шапки со страницы feed.html**:
     - Полный фирменный векторный SVG-логотип SmartContractum с градиентом `scDocGradFeedUnified` и печатью.
     - Оригинальный текстовый блок `<span class="logo-title"><span class="logo-smart">Smart</span><span class="logo-contractum">Contractum</span></span>`.
     - Все 5 навигационных пунктов («Главная», «Сообщество», «Эксперты», «База знаний», «Редактор») с **векторными SVG-иконками** в `.nav-icon-box` в точности как на `feed.html`.
     - Пункт «Редактор» активен (`class="nav-link active" id="navEditor"`).
     - Полноразмерный блок авторизации `#headerLoginBtn` с аватаркой, точкой статуса и стрелкой.
  4. **Унифицировать типографику Onest**:
     - Проверить и применить шрифт **Onest** повсеместно во всех элементах `editor.html` и `editor.css` с одинаковыми параметрами сглаживания (`-webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; text-rendering: optimizeLegibility;`), исключив любые шрифтовые расхождения между `feed.html` и `editor.html`.
  5. **Синхронизировать все автоматические тесты**:
     - Обеспечить 100% прохождение всех тестов (0 failures, 0 errors).

- **Границы изменений**:
  - Разрешено изменять/создавать:
    - `frontend/public/editor.html`
    - `frontend/public/css/editor.css`
    - `frontend/public/css/theme.css`
    - `frontend/public/css/landing_main.css`
    - `frontend/public/js/main.js`
    - `tests/test_feed_page_and_palette.py`
    - `tests/test_editor_v3.py`
    - `tasks/task-16-fix-editor-visual-and-theme-issues/*`
    - `WORKLOG.md`
  - Запрещено изменять:
    - модули ядра Quill в `frontend/public/vendor/quill/`
    - данные SQLite `data/*`

- **Критерии приемки**:
  1. В светлой теме (`data-theme="light"`) весь текст редактора (заголовок `#article-title`, параграфы, заголовки H2-H4, списки, цитаты, тулбары, виджеты и модальные окна) контрастный и тёмный (`#0f172a`), белый текст на белом фоне полностью отсутствует.
  2. В тёмной теме (`data-theme="dark"`) текст чёткий и светлый (`#ffffff` / `#a1a7bb`) на тёмном фоне `#171924` / `#0b1426`.
  3. Переключение тем через тумблер `#btnThemeToggle` и через выпадающее меню работает мгновенно, без визуальных артефактов и сохраняется при перезагрузке страницы.
  4. Шапка навигации `#appHeader` в `editor.html` идентична шапке `feed.html` (SVG-логотип, иконки для каждого пункта меню, единые отступы, размытие, анимации).
  5. Шрифт Onest применён единообразно на обеих страницах.
  6. Все автоматические тесты проходят успешно (100% PASS, 0 failures, 0 errors).

- **Текущий статус**: QA_APPROVED
- **Ответственный исполнитель**: git_bot
- **Рабочая ветка / копия**: feat/task-16-fix-editor-visual-and-theme-issues
- **Блокер**: нет
- **Следующий шаг**: Фиксация коммита на этапе FINALIZE в git_bot и слияние ветки.
- **Ссылки на отчеты**:
  - DEV: `tasks/task-16-fix-editor-visual-and-theme-issues/DEV_HANDOVER.md`
  - QA: `tasks/task-16-fix-editor-visual-and-theme-issues/QA_REVIEW.md`
  - GIT: `tasks/task-16-fix-editor-visual-and-theme-issues/GIT_HANDOVER.md`
- **История попыток решения**:
  - [Попытка 1]: Инициализация задачи | Разработка и независимый аудит QA завершены, вердикт APPROVED | Успешно
  - Счетчик попыток данного подхода: 0/2
