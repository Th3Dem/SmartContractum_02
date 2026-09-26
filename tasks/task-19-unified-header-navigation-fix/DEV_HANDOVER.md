# DEV Handover: task-19-unified-header-navigation-fix

- **Статус**: READY_FOR_QA
- **Ответственный исполнитель**: dev_bot (Frontend)
- **Рабочая ветка**: `feat/task-19-unified-header-navigation-fix`
- **Дата**: 2026-09-26
- **Логи проверок**: `tasks/task-19-unified-header-navigation-fix/logs/dev_checks.log`

---

## 1. Обзор выполненных работ

### 1.1. Исправление маршрутизации в шапке на всех страницах
- На всех 3 страницах проекта (`index.html`, `feed.html`, `editor.html`) зафиксирована единая, точная маршрутизация:
  - **Логотип `brand-logo`**: ссылка ведет строго на `index.html` с `title="На главную"` и `aria-label="SmartContractum Главная"`.
  - **Пункт «Главная» (`#navIndex`)**: ссылка ведет на `index.html`. Имеет класс активности `active is-active` **только** на `index.html` (на `feed.html` и `editor.html` класс активности снят).
  - **Пункт «Сообщество» (`#navCommunity`)**: ссылка ведет на `feed.html`. Имеет класс активности `active is-active` **только** на `feed.html` (на `index.html` и `editor.html` класс активности снят).
  - **Пункт «Редактор» (`#navEditor`)**: ссылка ведет на `editor.html`. Имеет класс активности `active is-active` **только** на `editor.html` (на `index.html` и `feed.html` класс активности снят).

### 1.2. Устранение горизонтальных скачков и дергания меню («колбасит»)
- **Стабилизация скроллбара**:
  В `frontend/public/css/theme.css` для селектора `html` установлено:
  ```css
  overflow-y: scroll;
  scrollbar-gutter: stable;
  ```
  Это гарантирует постоянное выделение пространства под вертикальный скроллбар браузера независимо от длины страницы, полностью устраняя горизонтальные скачки центрированного макета при переходах между короткими и длинными страницами.
- **Математически центрированная 3-колоночная сетка**:
  В `frontend/public/css/theme.css` контейнер `.header-container` переведен с `display: flex` на жесткую 3-колоночную сетку:
  ```css
  .header-container {
    max-width: var(--max-width, 1360px);
    height: 100%;
    margin: 0 auto;
    padding: 0 24px;
    display: grid;
    grid-template-columns: 260px 1fr 260px;
    align-items: center;
    gap: 20px;
  }
  .brand-logo { justify-self: start; }
  .header-nav { justify-self: center; }
  .header-right-group { justify-self: end; display: flex; align-items: center; gap: 14px; }
  ```
  Благодаря фиксированным крайним колонкам одинаковой ширины (260px) и выравниванию `justify-self: center`, навигационный блок строго спозиционирован в математическом геометрическом центре окна браузера и не смещается ни на один пиксель при смене активного пункта или текста кнопок.
- **Адаптивность**:
  Для экранов шириной `<= 900px` предусмотрен медиа-запрос, переключающий контейнер на `display: flex; justify-content: space-between;` со скрытием центрального блока `.header-nav`.

### 1.3. Полная идентичность разметки, иконок и элементов шапки
- Разметка блока `<header class="app-header" id="appHeader">` во всех трех файлах (`frontend/public/index.html`, `frontend/public/feed.html`, `frontend/public/editor.html`) приведена к 100% посимвольной идентичности (структура, SVG-векторы, порядок тегов):
  - **Кнопка профиля**: везде используется единая структура `<a href="#auth" class="header-login-action-btn" id="headerLoginBtn" title="Войти в личный кабинет">` с аватаром `.btn-user-avatar-wrap`, точкой статуса `#headerUserDot`, надписью «Войти / Регистрация» (`#headerUserLabel`) и стрелочкой `.btn-user-arrow`.
  - **Тумблер темы**: везде одинаковый переключатель `#btnThemeToggle` со свитчем `.theme-toggle-track`, круглой кнопкой `.theme-toggle-thumb`, SVG-луной (`theme-icon-moon`) и SVG-солнцем (`theme-icon-sun`).
  - **Все 3 пункта навигации**: одинаковые SVG-иконки (домик, пользователи, карандаш/документ), контейнеры `.nav-icon-box` и текст `.nav-text`.

### 1.4. Очистка дубликатов стилей и гармонизация шрифтов
- Из `frontend/public/css/editor.css` полностью удалены дублирующие и конфликтующие переопределения `.nav-link.is-active, .nav-link.active` (строки 121–136).
- Все стили шапки централизованы в `frontend/public/css/theme.css`.
- Для всех кнопок и ссылок шапки (`.nav-link`, `.nav-text`, `.header-login-action-btn`, `.btn-user-label`) гарантировано строгое применение шрифта `font-family: var(--font-sans)` (семейство Onest), `font-size: 0.92rem` и `font-weight: 600`.

### 1.5. Синхронизация тестовых наборов
- В `tests/test_feed_page_and_palette.py` синхронизированы тесты навигации и добавлен новый специализированный тестовый набор `TestTask19UnifiedHeaderNavigationAndLayout` (6 тестов), проверяющий:
  1. Корректность логотипа (`href="index.html"`, `title="На главную"`) на всех 3 страницах;
  2. Строгую маршрутизацию и независимость активных классов между страницами;
  3. Наличие CSS-правил `overflow-y: scroll`, `scrollbar-gutter: stable` и 3-колоночной сетки `260px 1fr 260px`;
  4. 100% идентичность внутренней разметки шапки между всеми тремя HTML-файлами;
  5. Отсутствие конфликтующих переопределений в `editor.css`;
  6. Единообразие типографики (Onest, 0.92rem, 600) и структуры кнопки профиля.

---

## 2. Результаты локальных проверок (Dev Checks)

- **Проверка посимвольной идентичности шапки**:
  Сравнение разметки `<header>` между `index.html`, `feed.html` и `editor.html` (за вычетом класса активного пункта): **0 различий (100% совпадение)**.
- **Проверка HTTP-сервера (`http://localhost:8000`)**:
  - `GET /index.html` -> HTTP 200 OK, шапка и маршруты верифицированы.
  - `GET /feed.html` -> HTTP 200 OK, шапка и маршруты верифицированы.
  - `GET /editor.html` -> HTTP 200 OK, шапка и маршруты верифицированы.
  - `GET /css/theme.css` -> HTTP 200 OK, `scrollbar-gutter: stable` и `grid-template-columns: 260px 1fr 260px` подтверждены.
- **Unit & Integration тесты проекта**:
  - `python3 -m unittest discover tests`
  - **ИТОГО: 185/185 PASS (100% успех, 0 падений, 0 ошибок)**.
  - Логи проверки сохранены: `tasks/task-19-unified-header-navigation-fix/logs/dev_checks.log`.

---

## 3. Передача задачи на QA-аудит

Все требования задачи `task-19-unified-header-navigation-fix` по маршрутизации шапки, устранению сдвигов меню и унификации кнопок полностью реализованы и верифицированы.

Статус: **`READY_FOR_QA`**.
