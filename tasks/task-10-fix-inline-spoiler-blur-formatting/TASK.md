# TASK-10: Исправление применения инлайн-спойлера (блюр текста по выделению)

## 1. Контекст проблемы и первопричина
Пользователь сообщил, что кнопка «Скрытый текст (спойлер)» в меню при выделении текста не работает — при нажатии текст не блюрится.

### Первопричина дефекта:
1. **Отсутствие методов `static formats()` и `formats()` в классе `InlineSpoilerBlot` (`core.js`)**:
   - В Quill 2.0 / Parchment при применении любого `Inline` блота движок сразу же вызывает `optimize()`.
   - Внутри `optimize()` вызывается `const n = this.formats()`. Если `formats()` возвращает пустой объект `{}`, Parchment считает, что у узла нет форматов, и немедленно вызывает `this.unwrap()`.
   - Из-за того, что `InlineSpoilerBlot` наследовался от базового `Inline` (`<span>`), но не объявлял `static formats(domNode) { return true; }`, Parchment возвращал `undefined` и мгновенно удалял только что созданный `<span class="editor-inline-spoiler">` в том же тике оптимизации!
2. **Использование `editor.format()` вместо `editor.formatText()` при клике на всплывающую панель (`bubble.js`)**:
   - Метод `editor.format(name, value)` в Quill жестко опирается на `this.getSelection(!0)`. Если при клике по всплывающей кнопке фокус сместился и Quill вернул `null`, `editor.format()` просто молча выходит и ничего не форматирует.
   - Надежное форматирование по сохраненному диапазону выделения требует вызова `editor.formatText(range.index, range.length, 'inline-spoiler', !isActive, 'user')`.
3. **`user-select: none` в CSS**:
   - Свойство `user-select: none` при наложении на выделенный диапазон заставляло браузер сбрасывать выделение и мешало кликам мыши.

---

## 2. Критерии приемки (Definition of Done)

### 2.1. Исправление Blot в `core.js`
- [ ] В `InlineSpoilerBlot` реализован `static formats(domNode) { return true; }`.
- [ ] Реализован метод экземпляра `formats()`, гарантирующий наличие ключа `['inline-spoiler']: true`.
- [ ] Реализован метод `format(name, value)`, вызывающий `this.unwrap()` при передаче `value = false`.
- [ ] Блот зарегистрирован как в общем реестре Quill, так и по пути `'formats/inline-spoiler'`.

### 2.2. Надежное форматирование в `bubble.js`
- [ ] При нажатии кнопки `inline-spoiler` вызывается `editor.formatText(range.index, range.length, 'inline-spoiler', !isActive, 'user')`.
- [ ] Восстанавливается выделение через `editor.setSelection(range.index, range.length, 'silent')`.
- [ ] Кнопка в панели подсвечивается классом `.is-active` при наличии формата или предка `.editor-inline-spoiler`.

### 2.3. Визуальный блюр и раскрытие по клику (`editor.css` и `main.js`)
- [ ] Класс `.editor-inline-spoiler` имеет надежный визуальный блюр: `filter: blur(5px); -webkit-filter: blur(5px);`.
- [ ] Удален `user-select: none`, чтобы не конфликтовать с браузерным выделением и событиями клика.
- [ ] При клике мышью по спойлеру переключается класс `.is-revealed` (и `data-revealed="true"`): блюр пропадает (`filter: none !important; -webkit-filter: none !important;`).
- [ ] Клик работает в любых режимах (редактирование и предпросмотр).

### 2.4. Тестирование и регресс
- [ ] Написаны и обновлены тесты, верифицирующие наличие `static formats`, вызов `formatText`, CSS фильтры блюра и логику переключения.
- [ ] Все тесты проекта проходят на 100%: `python3 -m unittest discover -s tests -p 'test_*.py'`.
- [ ] 0 внешних CDN-запросов (100% offline-first).
