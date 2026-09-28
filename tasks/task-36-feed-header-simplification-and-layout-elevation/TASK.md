# Task: task-36-feed-header-simplification-and-layout-elevation — Удаление кнопки «Настройка ленты» из шапки, перемещение кнопки «Фильтры» вправо от поиска, удаление компактного заголовка и тулбара, подъем ленты публикаций

- **Цель**:
  1. [x] Удалить из второго уровня шапки меню (`.feed-subnav-bar`) кнопку «Настройка ленты» (`#btnFeedSettingsToggle`). Теперь в шапке остается только кнопка «Фильтры» (`#btnFeedFiltersToggle`), где содержатся все настройки и параметры.
  2. [x] Переместить кнопку «Фильтры» (`#btnFeedFiltersToggle`) в правый блок меню (`.feed-subnav-right`) до конца вправо, справа от строки поиска (`#feedSearchGroup`).
  3. [x] Удалить блок и текст с фразой «Лента публикаций, разработка, безопасность и практика применения коммерческих смарт-контрактов» (`.feed-compact-header`).
  4. [x] Удалить блок тулбара над лентой (`#feedDirectToolbar`), где отображается количество публикаций (`#feedResultsCount`) и выпадающий список сортировки («Сначала новые», «Сначала старые», «Обсуждаемые», «Популярные»).
  5. [x] Поднять саму ленту публикаций выше на место удаленных блоков (непосредственно под второй уровень шапки).
  6. [x] Обеспечить 100% прохождение всех unit-тестов проекта (`python3 -m unittest discover tests -v`, 305/305 PASS).

- **Границы изменений**:
  - Разрешено изменять:
    - `frontend/public/feed.html`
    - `frontend/public/css/feed.css`
    - `frontend/public/js/feed.js`
    - `tests/*`
    - `tasks/task-36-feed-header-simplification-and-layout-elevation/*`
    - `WORKLOG.md`
  - Запрещено изменять:
    - `frontend/public/vendor/*`

- **Текущий статус**: DONE
- **Ответственный исполнитель**: pm_bot (упрощенный режим / Fast-Track)
- **Рабочая ветка / копия**: main
- **Diff Snapshot Hash**: `bc078fd3afc5887f1965d79ac255f819cfd72056b1ad167a08cef0342268b667`
- **Блокер**: нет
- **Следующий шаг**: Задача завершена (Done-Done)
- **Ссылки на отчеты**:
  - DEV: `tasks/task-36-feed-header-simplification-and-layout-elevation/DEV_HANDOVER.md`
  - QA: `tasks/task-36-feed-header-simplification-and-layout-elevation/QA_REVIEW.md`
