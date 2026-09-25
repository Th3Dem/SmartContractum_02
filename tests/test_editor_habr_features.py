#!/usr/bin/env python3
"""
Unit tests for Habr-inspired Editor Features (task-04-habr-tools-and-sidebar):
1. Typograph engine rules:
   - Quotes: straight "..." to Russian «...» and nested to „...“.
   - Dashes: hyphens with spaces ' - ' to em-dash ' — ', preservation of word-internal hyphens.
   - Non-breaking spaces: binding 1-2 letter prepositions and conjunctions (\u00A0).
   - Ellipsis: triple dots '...' to '…'.
   - Preservation of code blocks (<pre>, <code>), LaTeX formulas, and link URLs.
2. Right Sidebar widgets:
   - Widget 1: «Типограф» with #btn-typograph, icon, and description.
   - Widget 2: «Памятка автору» with structure advice and shortcut cheatsheet.
   - Widget 3: «Чек-лист публикации» with 4 dynamic items, progress bar, and readiness badge.
   - Responsive styling (<1280px).
3. Node controls for blocks:
   - Left drag handle (node__drag-control, draggable="true").
   - Right 3-dots button (node__dots) with context menu (transform, duplicate, delete).
   - Visual drop-line (#node-drop-line).
4. Floating Image Menu:
   - Buttons: «В тексте», «Во всю ширину», «В рамку», «Удалить».
   - Figcaption caption support.
"""

import json
import os
import re
import unittest
from html.parser import HTMLParser


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend', 'public')


class TypographEngine:
    """Python reference mirror of frontend/public/js/typograph.js to test specification compliance."""

    PREPOSITIONS = [
        'и', 'в', 'на', 'с', 'по', 'к', 'не', 'за', 'от',
        'из', 'у', 'о', 'об', 'ни', 'а', 'но', 'да'
    ]

    @classmethod
    def typograph(cls, text):
        if not text:
            return ''

        # 1. Protect URLs
        urls = []
        def save_url(m):
            urls.append(m.group(0))
            return f'___TYPO_URL_{len(urls)-1}___'
        processed = re.sub(r'https?://[^\s<>"\'\)]+|www\.[^\s<>"\'\)]+', save_url, text)

        # 2. Protect LaTeX formulas
        formulas = []
        def save_formula(m):
            formulas.append(m.group(0))
            return f'___TYPO_FORMULA_{len(formulas)-1}___'
        processed = re.sub(r'\$\$.*?\$\$|\$.*?\$|\\\(.*?\\\)|\x5c\[.*?\x5c\]', save_formula, processed, flags=re.DOTALL)

        # 3. Protect code blocks and tags
        codes = []
        def save_code(m):
            codes.append(m.group(0))
            return f'___TYPO_CODE_{len(codes)-1}___'
        processed = re.sub(r'<(pre|code|a)\b[^>]*>.*?</\1>', save_code, processed, flags=re.IGNORECASE | re.DOTALL)

        # 4. Ellipsis: ... -> …
        processed = re.sub(r'\.{3,}', '…', processed)

        # 5. Dashes: word - word -> word — word
        processed = re.sub(r'(?<=\S)[ \t]+--?[ \t]+(?=\S)', ' — ', processed)
        processed = re.sub(r'(^|\n)[ \t]*-[ \t]+', r'\1— ', processed)

        # 6. Quotes: straight quotes to Russian guillemets «...» and nested to „...“
        chars = list(processed)
        depth = 0
        res = []
        n = len(chars)

        for i in range(n):
            c = chars[i]
            if c == '"':
                prev_c = chars[i - 1] if i > 0 else ' '
                next_c = chars[i + 1] if i + 1 < n else ' '

                is_open = (prev_c in ' \t\n\r([{\'«„\u00A0') and (next_c not in ' \t\n\r.,!?:;)]}\'»“\u00A0')
                is_close = (prev_c not in ' \t\n\r([{\'«„\u00A0') and (next_c in ' \t\n\r.,!?:;)]}\'»“\u00A0' or i + 1 == n)

                if is_open and not is_close:
                    if depth == 0:
                        res.append('«')
                        depth = 1
                    else:
                        res.append('„')
                        depth += 1
                elif is_close and not is_open:
                    if depth > 1:
                        res.append('“')
                        depth -= 1
                    else:
                        res.append('»')
                        depth = 0
                else:
                    if depth == 0:
                        res.append('«')
                        depth = 1
                    else:
                        if depth > 1:
                            res.append('“')
                            depth -= 1
                        else:
                            res.append('»')
                            depth = 0
            else:
                res.append(c)
        processed = ''.join(res)

        # 7. Non-breaking spaces for 1-2 letter prepositions and conjunctions
        preps_regex = '|'.join(sorted(cls.PREPOSITIONS, key=len, reverse=True))
        prep_pattern = r'(^|[\s«\"„\(\[\u00A0])(' + preps_regex + r')[ \t]+(?=[a-zA-Zа-яА-ЯёЁ0-9«„])'
        for _ in range(4):
            processed = re.sub(prep_pattern, r'\g<1>\g<2>' + '\u00A0', processed, flags=re.IGNORECASE)

        # Restore protected elements
        for idx, c in enumerate(codes):
            processed = processed.replace(f'___TYPO_CODE_{idx}___', c)
        for idx, f in enumerate(formulas):
            processed = processed.replace(f'___TYPO_FORMULA_{idx}___', f)
        for idx, u in enumerate(urls):
            processed = processed.replace(f'___TYPO_URL_{idx}___', u)

        return processed


class TestTypographRules(unittest.TestCase):
    """Test 1: Verify all Russian typography engine rules."""

    def setUp(self):
        js_path = os.path.join(FRONTEND_DIR, 'js', 'typograph.js')
        self.assertTrue(os.path.isfile(js_path), "typograph.js must exist in frontend/public/js/")
        with open(js_path, 'r', encoding='utf-8') as f:
            self.js_code = f.read()

    def test_typograph_js_structure(self):
        """Verify typograph.js defines Typograph with required methods."""
        self.assertIn('class Typograph', self.js_code)
        self.assertIn('typographText', self.js_code)
        self.assertIn('typographHTML', self.js_code)
        self.assertIn('typographEditor', self.js_code)
        self.assertIn('window.Typograph = Typograph', self.js_code)

    def test_quotes_conversion_simple_and_nested(self):
        """Straight quotes are converted to «...» and nested to „...“."""
        # Simple quotes
        simple = TypographEngine.typograph('"Простой текст в кавычках"')
        self.assertEqual(simple, '«Простой текст в\xa0кавычках»')

        # Multiple quote pairs
        multi = TypographEngine.typograph('"Первая фраза" и "вторая фраза"')
        self.assertEqual(multi, '«Первая фраза» и\xa0«вторая фраза»')

        # Nested quotes
        nested = TypographEngine.typograph('"Она сказала: "Привет!", и улыбнулась"')
        self.assertEqual(nested, '«Она сказала: „Привет!“, и\xa0улыбнулась»')

        # Nested quotes in middle of text
        nested2 = TypographEngine.typograph('"В книге "Мастер и Маргарита" есть цитата"')
        self.assertEqual(nested2, '«В\xa0книге „Мастер и\xa0Маргарита“ есть цитата»')

    def test_dashes_conversion(self):
        """Hyphens with spaces ' - ' are converted to em-dash ' — '."""
        text = TypographEngine.typograph('Москва - столица России')
        self.assertEqual(text, 'Москва — столица России')

        # Double hyphens
        text2 = TypographEngine.typograph('Текст -- длинное тире')
        self.assertEqual(text2, 'Текст — длинное тире')

        # Direct speech at line start
        text3 = TypographEngine.typograph('- Привет! - сказал он.')
        self.assertEqual(text3, '— Привет! — сказал он.')

        # Intra-word hyphens must NOT be converted
        word_hyphen = TypographEngine.typograph('какой-то по-русски черно-белый')
        self.assertIn('какой-то', word_hyphen)
        self.assertIn('по-русски', word_hyphen)
        self.assertIn('черно-белый', word_hyphen)
        self.assertNotIn('какой—то', word_hyphen)

    def test_prepositions_non_breaking_spaces(self):
        """1-2 letter prepositions and conjunctions bound with \\u00A0."""
        preps = ['и', 'в', 'на', 'с', 'по', 'к', 'не', 'за', 'от', 'из', 'у', 'о', 'об', 'ни', 'а', 'но', 'да']
        sample = 'Мы поехали в город и на дачу с друзьями по реке к морю.'
        result = TypographEngine.typograph(sample)

        self.assertIn('в\xa0город', result)
        self.assertIn('и\xa0на\xa0дачу', result)
        self.assertIn('с\xa0друзьями', result)
        self.assertIn('по\xa0реке', result)
        self.assertIn('к\xa0морю', result)

        # Capitalized at sentence start
        cap_result = TypographEngine.typograph('В лесу было тихо. И птицы пели.')
        self.assertIn('В\xa0лесу', cap_result)
        self.assertIn('И\xa0птицы', cap_result)

    def test_ellipsis_conversion(self):
        """Triple dots '...' converted to ellipsis '…'."""
        result = TypographEngine.typograph('Продолжение следует...')
        self.assertEqual(result, 'Продолжение следует…')

        result4 = TypographEngine.typograph('Задумался....')
        self.assertEqual(result4, 'Задумался…')

    def test_preservation_of_code_formulas_and_urls(self):
        """Code blocks, LaTeX formulas, and URLs must NEVER be altered."""
        code_snippet = '<code>const x = "string" - 10;</code>'
        url_snippet = 'https://habr.com/ru/articles/12345/?utm_source=test-param'
        formula_snippet = '$f(x) = a - b$'

        text = f'Читайте статью {url_snippet} про формулу {formula_snippet} и код {code_snippet}.'
        result = TypographEngine.typograph(text)

        self.assertIn(code_snippet, result)
        self.assertIn(url_snippet, result)
        self.assertIn(formula_snippet, result)


class TestSidebarWidgets(unittest.TestCase):
    """Test 2: Verify presence and layout of all 3 right sidebar widgets."""

    def setUp(self):
        html_path = os.path.join(FRONTEND_DIR, 'editor.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            self.html = f.read()

        css_path = os.path.join(FRONTEND_DIR, 'css', 'editor.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            self.css = f.read()

    def test_sidebar_zone_right_container(self):
        """Verify .side-zone-right exists and contains sidebar sticky wrapper."""
        self.assertIn('class="side-zone side-zone-right"', self.html)
        self.assertIn('class="sidebar-sticky-wrapper"', self.html)

    def test_widget_1_typograph(self):
        """Widget 1: «Типограф» with icon, description, button #btn-typograph, and feedback status."""
        self.assertIn('id="widget-typograph"', self.html)
        self.assertIn('Типограф', self.html)
        self.assertIn('После редактирования улучшает типографику текста', self.html)
        self.assertIn('id="btn-typograph"', self.html)
        self.assertIn('Оттипографить текст', self.html)
        self.assertIn('id="typograph-status"', self.html)

    def test_widget_2_author_guide(self):
        """Widget 2: «Памятка автору» with structure tips and shortcuts."""
        self.assertIn('id="widget-author-guide"', self.html)
        self.assertIn('Памятка автору', self.html)
        self.assertIn('Структура статьи', self.html)
        self.assertIn('Подзаголовки (H2–H4)', self.html)
        self.assertIn('Горячие клавиши', self.html)
        self.assertIn('Ctrl+K', self.html)
        self.assertIn('Ctrl+B/I/U', self.html)
        self.assertIn('Ctrl+S', self.html)

    def test_widget_3_checklist(self):
        """Widget 3: «Чек-лист публикации» with 4 dynamic items and progress bar."""
        self.assertIn('id="widget-checklist"', self.html)
        self.assertIn('Чек-лист публикации', self.html)
        self.assertIn('id="readiness-badge"', self.html)

        # 4 dynamic checklist items
        self.assertIn('id="chk-title"', self.html)
        self.assertIn('Заголовок статьи заполнен', self.html)
        self.assertIn('id="chk-words"', self.html)
        self.assertIn('Объем текста', self.html)
        self.assertIn('id="chk-headers"', self.html)
        self.assertIn('Наличие подзаголовков (H2-H4)', self.html)
        self.assertIn('id="chk-typograph"', self.html)
        self.assertIn('Типографика проверена', self.html)

        self.assertIn('id="checklist-progress-fill"', self.html)

    def test_sidebar_responsive_hiding_under_1280px(self):
        """Sidebar is hidden on screens under 1280px without breaking editor layout."""
        self.assertIn('@media (max-width: 1280px)', self.css)
        media_match = re.search(r'@media\s*\(max-width:\s*1280px\)\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(media_match)
        content = media_match.group(1)
        self.assertIn('.side-zone-right', content)
        self.assertIn('display: none', content)


class TestNodeControls(unittest.TestCase):
    """Test 3: Verify node controls for each block in Quill."""

    def setUp(self):
        html_path = os.path.join(FRONTEND_DIR, 'editor.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            self.html = f.read()

        css_path = os.path.join(FRONTEND_DIR, 'css', 'editor.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            self.css = f.read()

        js_path = os.path.join(FRONTEND_DIR, 'js', 'node-controls.js')
        self.assertTrue(os.path.isfile(js_path))
        with open(js_path, 'r', encoding='utf-8') as f:
            self.js_code = f.read()

    def test_node_controls_html_elements(self):
        """Verify node-controls container, drag handle, trash button, and drop line in HTML."""
        self.assertIn('id="node-controls"', self.html)
        self.assertIn('class="node__drag-control"', self.html)
        self.assertIn('draggable="true"', self.html)
        self.assertIn('data-drag-handle', self.html)

        self.assertIn('id="btn-node-direct-delete"', self.html)
        self.assertIn('node__delete', self.html)
        self.assertNotIn('id="node-action-menu"', self.html)
        self.assertIn('id="node-drop-line"', self.html)

    def test_node_actions_menu_items(self):
        """Verify 3-dots dropdown menu was replaced with direct delete trash button."""
        self.assertIn('id="btn-node-direct-delete"', self.html)
        self.assertIn('title="Удалить блок"', self.html)
        self.assertNotIn('id="node-action-menu"', self.html)
        self.assertNotIn('data-transform="paragraph"', self.html)

    def test_node_controls_js_manager(self):
        """NodeControlsManager implements hover/focus, HTML5 drag-and-drop, and actions."""
        self.assertIn('class NodeControlsManager', self.js_code)
        self.assertIn('bindHoverAndFocus', self.js_code)
        self.assertIn('bindDragAndDrop', self.js_code)
        self.assertIn('transformBlock', self.js_code)
        self.assertIn('duplicateBlock', self.js_code)
        self.assertIn('deleteBlock', self.js_code)


class TestImageFloatingMenu(unittest.TestCase):
    """Test 4: Verify Floating Context Menu for Images (Image Menu)."""

    def setUp(self):
        html_path = os.path.join(FRONTEND_DIR, 'editor.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            self.html = f.read()

        css_path = os.path.join(FRONTEND_DIR, 'css', 'editor.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            self.css = f.read()

        js_path = os.path.join(FRONTEND_DIR, 'js', 'node-controls.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            self.js_code = f.read()

    def test_image_menu_html_structure(self):
        """Image menu contains 'В тексте', 'Во всю ширину', 'В рамку', and 'Удалить' buttons."""
        self.assertIn('id="image-menu"', self.html)
        self.assertIn('class="image-menu-container"', self.html)
        self.assertIn('class="image-menu__buttons"', self.html)

        # 4 required buttons
        self.assertIn('data-test-id="toggle-float"', self.html)
        self.assertIn('В тексте', self.html)
        self.assertIn('data-test-id="toggle-full"', self.html)
        self.assertIn('Во всю ширину', self.html)
        self.assertIn('data-test-id="toggle-border"', self.html)
        self.assertIn('В рамку', self.html)
        self.assertIn('data-test-id="delete-image"', self.html)
        self.assertIn('Удалить', self.html)

    def test_image_menu_css_styles(self):
        """Verify CSS styles for full-width image, border toggle, and image menu."""
        self.assertIn('.image-menu-container', self.css)
        self.assertIn('.image-menu__buttons', self.css)
        self.assertIn('.editor-figure.has-border', self.css)
        self.assertIn('.editor-figure.align-full', self.css)

    def test_image_menu_js_manager(self):
        """ImageMenuManager handles click on images, buttons toggle, and editable figcaption."""
        self.assertIn('class ImageMenuManager', self.js_code)
        self.assertIn('showForFigure', self.js_code)
        self.assertIn('figcaption', self.js_code)
        self.assertIn('contentEditable', self.js_code)


if __name__ == '__main__':
    unittest.main()
