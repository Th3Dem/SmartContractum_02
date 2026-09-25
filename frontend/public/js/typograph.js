/**
 * Antigravity WYSIWYG Editor - Russian Typograph Engine
 * Implements Habr-inspired typography rules:
 * 1. Straight quotes "..." to Russian guillemets «...» and nested to „...“.
 * 2. Hyphen between words ' - ' to em-dash ' — '.
 * 3. 1-2 letter prepositions and conjunctions (и, в, на, с, по, к, не, за, от, из, у, о, об, ни, а, но, да)
 *    bound to next word using non-breaking space '\u00A0'.
 * 4. Triple dots '...' to ellipsis '…'.
 * 5. Preservation of code blocks (<pre>, <code>), LaTeX formulas, and link URLs.
 * 6. Integration with Quill Delta and Undo stack.
 * 100% offline-first.
 */

(function (window) {
  'use strict';

  const PREPOSITIONS = [
    'и', 'в', 'на', 'с', 'по', 'к', 'не', 'за', 'от',
    'из', 'у', 'о', 'об', 'ни', 'а', 'но', 'да'
  ];

  class Typograph {
    /**
     * Formats plain text according to Russian typography standards.
     * @param {string} text
     * @returns {string}
     */
    static typographText(text) {
      if (!text || typeof text !== 'string') return '';

      // 1. Protect URLs (http, https, ftp, www)
      const urls = [];
      let processed = text.replace(/https?:\/\/[^\s<>"')]+|www\.[^\s<>"')]+/gi, (match) => {
        urls.push(match);
        return `___TYPO_URL_${urls.length - 1}___`;
      });

      // 2. Protect LaTeX formulas ($$...$$, $...$, \(...\), \[...\])
      const formulas = [];
      processed = processed.replace(/\$\$.*?\$\$|\$.*?\$|\\\(.*?\\\)|\x5c\[.*?\x5c\]/gs, (match) => {
        formulas.push(match);
        return `___TYPO_FORMULA_${formulas.length - 1}___`;
      });

      // 3. Protect inline/block code tags if present
      const codeBlocks = [];
      processed = processed.replace(/<(pre|code|a)\b[^>]*>.*?<\/\1>/gis, (match) => {
        codeBlocks.push(match);
        return `___TYPO_CODE_${codeBlocks.length - 1}___`;
      });

      // 4. Triple dots '...' to ellipsis '…'
      processed = processed.replace(/\.{3,}/g, '…');

      // 5. Hyphen to em-dash ' — '
      // Word to word or space to space with hyphens: ' - ' or ' -- '
      processed = processed.replace(/(?<=\S)[ \t]+--?[ \t]+(?=\S)/g, ' — ');
      // Start of line or quote direct speech: '- ' -> '— '
      processed = processed.replace(/(^|\n)[ \t]*-[ \t]+/g, '$1— ');

      // 6. Convert straight quotes "..." to Russian «...» and nested to „...“
      const chars = Array.from(processed);
      let depth = 0;
      const res = [];
      const n = chars.length;

      for (let i = 0; i < n; i++) {
        const c = chars[i];
        if (c === '"') {
          const prevC = i > 0 ? chars[i - 1] : ' ';
          const nextC = i + 1 < n ? chars[i + 1] : ' ';

          const isOpen = ' \t\n\r([{\'«„\u00A0'.includes(prevC) && !' \t\n\r.,!?:;)]}\'»“\u00A0'.includes(nextC);
          const isClose = !' \t\n\r([{\'«„\u00A0'.includes(prevC) && (' \t\n\r.,!?:;)]}\'»“\u00A0'.includes(nextC) || i + 1 === n);

          if (isOpen && !isClose) {
            if (depth === 0) {
              res.push('«');
              depth = 1;
            } else {
              res.push('„');
              depth++;
            }
          } else if (isClose && !isOpen) {
            if (depth > 1) {
              res.push('“');
              depth--;
            } else {
              res.push('»');
              depth = 0;
            }
          } else {
            // Context-based fallback
            if (depth === 0) {
              res.push('«');
              depth = 1;
            } else {
              if (depth > 1) {
                res.push('“');
                depth--;
              } else {
                res.push('»');
                depth = 0;
              }
            }
          }
        } else {
          res.push(c);
        }
      }
      processed = res.join('');

      // 7. Bind 1-2 letter prepositions and conjunctions with non-breaking space \u00A0
      const prepsRegex = PREPOSITIONS.slice().sort((a, b) => b.length - a.length).join('|');
      const prepPattern = new RegExp(`(^|[\\s«"„(\\[\u00A0])(${prepsRegex})[ \\t]+(?=[a-zA-Zа-яА-ЯёЁ0-9«„])`, 'gi');

      // Multiple passes to catch chained prepositions (e.g., "и в город")
      for (let p = 0; p < 4; p++) {
        processed = processed.replace(prepPattern, '$1$2\u00A0');
      }

      // Restore protected code blocks
      for (let k = 0; k < codeBlocks.length; k++) {
        processed = processed.replace(`___TYPO_CODE_${k}___`, codeBlocks[k]);
      }

      // Restore protected LaTeX formulas
      for (let f = 0; f < formulas.length; f++) {
        processed = processed.replace(`___TYPO_FORMULA_${f}___`, formulas[f]);
      }

      // Restore protected URLs
      for (let u = 0; u < urls.length; u++) {
        processed = processed.replace(`___TYPO_URL_${u}___`, urls[u]);
      }

      return processed;
    }

    /**
     * Formats an HTML snippet while preserving <pre>, <code>, <a>, and formula containers.
     * @param {string} html
     * @returns {string}
     */
    static typographHTML(html) {
      if (!html || typeof html !== 'string') return '';

      const doc = new DOMParser().parseFromString(html, 'text/html');

      const walkTextNodes = (node) => {
        if (!node) return;

        // Skip code, pre, formulas, and link elements
        if (node.nodeType === Node.ELEMENT_NODE) {
          const tagName = node.tagName.toLowerCase();
          if (['pre', 'code', 'a'].includes(tagName)) return;
          if (node.classList && (
            node.classList.contains('ql-syntax') ||
            node.classList.contains('editor-code-block') ||
            node.classList.contains('editor-block-formula') ||
            node.classList.contains('editor-inline-formula') ||
            node.classList.contains('formula-rendered') ||
            node.hasAttribute('data-latex')
          )) {
            return;
          }
        }

        if (node.nodeType === Node.TEXT_NODE) {
          if (node.nodeValue && node.nodeValue.trim()) {
            node.nodeValue = Typograph.typographText(node.nodeValue);
          }
          return;
        }

        let child = node.firstChild;
        while (child) {
          const next = child.nextSibling;
          walkTextNodes(child);
          child = next;
        }
      };

      walkTextNodes(doc.body);
      return doc.body.innerHTML;
    }

    /**
     * Applies typography to the Quill editor and title field with Undo stack integration.
     * @param {Quill} editor
     * @param {HTMLInputElement|HTMLTextAreaElement} [titleInput]
     * @returns {boolean} Whether changes were made
     */
    static typographEditor(editor, titleInput = null) {
      if (!editor) return false;

      let changed = false;

      // 1. Process Title Input if provided
      if (titleInput && titleInput.value) {
        const oldTitle = titleInput.value;
        const newTitle = Typograph.typographText(oldTitle);
        if (oldTitle !== newTitle) {
          titleInput.value = newTitle;
          changed = true;
          if (window.EditorApp && window.EditorApp.updateDocumentTitle) {
            window.EditorApp.updateDocumentTitle();
          }
        }
      }

      // 2. Process Quill editor contents via Delta with history integration
      const currentDelta = editor.getContents();
      if (!currentDelta || !currentDelta.ops) return changed;

      const Delta = editor.constructor.import ? editor.constructor.import('delta') : (window.Quill ? window.Quill.import('delta') : null);

      const newOps = currentDelta.ops.map(op => {
        // If text operation
        if (typeof op.insert === 'string') {
          // Never touch code blocks, inline code, or formulas
          const attrs = op.attributes || {};
          if (attrs.code || attrs['code-block'] || attrs.formula) {
            return op;
          }
          const formattedText = Typograph.typographText(op.insert);
          if (formattedText !== op.insert) {
            changed = true;
          }
          return {
            insert: formattedText,
            attributes: op.attributes ? { ...op.attributes } : undefined
          };
        }
        // Embed blot (image, media, formula, etc.)
        return op;
      });

      if (Delta) {
        const newDelta = new Delta(newOps);
        const diff = currentDelta.diff(newDelta);
        if (diff && diff.ops && diff.ops.length > 0) {
          editor.updateContents(diff, 'user');
          changed = true;
        }
      } else {
        // Fallback: direct setContents with 'user' source
        editor.setContents({ ops: newOps }, 'user');
      }

      return changed;
    }
  }

  // Bind to window
  window.Typograph = Typograph;

})(window);
