/**
 * Antigravity WYSIWYG Editor - Floating Contextual Bubble Toolbar
 * Appears ONLY when non-empty text is selected in the editor (mouse or keyboard).
 * 11 Tools + 4 Alignment Buttons.
 * Sequential formatting without clearing selection, Escape to close, viewport bounds checking.
 */

(function (window) {
  'use strict';

  class BubbleToolbar {
    constructor(editor) {
      this.editor = editor;
      this.bubble = document.getElementById('bubble-toolbar');
      this.editorContainer = editor.container;

      if (!this.bubble) return;

      const editorCard = document.getElementById('editor-card');
      if (editorCard && this.bubble.parentNode !== editorCard) {
        editorCard.appendChild(this.bubble);
      }

      this.currentRange = null;
      this.bindEvents();
    }

    bindEvents() {
      // Selection change event from Quill (triggers on mouse and keyboard selection)
      this.editor.on('selection-change', (range, oldRange, source) => {
        if (range && range.length > 0) {
          this.currentRange = { index: range.index, length: range.length };
          this.show(range);
        } else {
          this.currentRange = null;
          this.hide();
        }
      });

      // Prevent mousedown on bubble buttons from clearing selection in editor
      this.bubble.addEventListener('mousedown', (e) => {
        // If clicking an input inside a sub-popup, allow default; otherwise prevent blur
        if (!e.target.closest('input, textarea')) {
          e.preventDefault();
        }
      });

      // Handle button clicks in bubble toolbar
      this.bubble.addEventListener('click', (e) => {
        // Handle standard bubble button
        const btn = e.target.closest('.bubble-btn');
        if (!btn) return;

        const format = btn.getAttribute('data-format');
        const value = btn.getAttribute('data-value');
        const action = btn.getAttribute('data-action');

        const range = this.editor.getSelection() || this.currentRange;
        if (!range || range.length === 0) return;

        // Alignment format
        if (format === 'align') {
          this.editor.format('align', value || false);
          this.updateActiveStates(range);
          return;
        }

        // 8. Clear formatting
        if (action === 'clear-format') {
          this.editor.removeFormat(range.index, range.length);
          this.updateActiveStates(range);
          return;
        }

        // 10. Link dialog
        if (action === 'link') {
          if (window.EditorApp && window.EditorApp.Toolbar) {
            window.EditorApp.Toolbar.openLinkModal(range);
          }
          return;
        }

        // 11. Formula dialog
        if (action === 'formula') {
          if (window.EditorApp && window.EditorApp.Toolbar) {
            window.EditorApp.Toolbar.openFormulaModal(range);
          }
          return;
        }

        // Inline spoiler format
        if (format === 'inline-spoiler') {
          const current = this.editor.getFormat(range);
          let isActive = !!current['inline-spoiler'];
          if (!isActive) {
            try {
              const [leaf] = this.editor.getLeaf(range.index);
              if (leaf && leaf.domNode) {
                const el = leaf.domNode.nodeType === 1 ? leaf.domNode : leaf.domNode.parentElement;
                if (el && el.closest('.editor-inline-spoiler')) {
                  isActive = true;
                }
              }
            } catch (err) {}
          }
          this.editor.format('inline-spoiler', !isActive);
          this.updateActiveStates(range);
          return;
        }

        // Standard formats (bold, italic, underline, strike, script, code)
        if (format) {
          const current = this.editor.getFormat(range);
          if (value !== null && value !== undefined) {
            const nextVal = (current[format] === value || current[format] === parseInt(value, 10)) ? false : value;
            this.editor.format(format, nextVal);
          } else {
            this.editor.format(format, !current[format]);
          }
          this.updateActiveStates(range);
        }
      });

      // Escape closes bubble toolbar
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          if (this.bubble.classList.contains('show')) {
            this.hide();
          }
        }
      });

      // Reposition on window scroll or resize
      window.addEventListener('scroll', () => {
        const range = this.editor.getSelection();
        if (range && range.length > 0) {
          this.reposition(range);
        } else {
          this.hide();
        }
      }, { passive: true });

      window.addEventListener('resize', () => {
        const range = this.editor.getSelection();
        if (range && range.length > 0) {
          this.reposition(range);
        }
      }, { passive: true });
    }

    show(range) {
      if (!range || range.length === 0) {
        this.hide();
        return;
      }
      this.reposition(range);
      this.updateActiveStates(range);
      this.bubble.classList.add('show');
    }

    hide() {
      if (this.bubble) {
        this.bubble.classList.remove('show');
      }
    }

    reposition(range) {
      if (!range) return;

      const bounds = this.editor.getBounds(range.index, range.length);
      if (!bounds) return;

      const editorCard = this.editorContainer.closest('.editor-card') || this.editorContainer;
      const cardRect = editorCard.getBoundingClientRect();
      const containerRect = this.editorContainer.getBoundingClientRect();

      // Horizontal center of selection relative to editor-card
      const left = (containerRect.left - cardRect.left) + bounds.left + (bounds.width / 2);
      // Vertical top strictly above the selection relative to editor-card
      const top = (containerRect.top - cardRect.top) + Math.max(10, bounds.top);

      this.bubble.style.top = `${top}px`;

      // Constrain horizontal position within editorCard bounds
      const minLeft = 140;
      const maxLeft = Math.max(140, cardRect.width - 140);
      const clampedLeft = Math.max(minLeft, Math.min(left, maxLeft));

      this.bubble.style.left = `${clampedLeft}px`;
    }

    updateActiveStates(range) {
      if (!range || !this.bubble) return;

      const formats = this.editor.getFormat(range);
      const buttons = this.bubble.querySelectorAll('.bubble-btn[data-format]');

      // Check if current format has 'inline-spoiler' or selection is within an .editor-inline-spoiler
      let isInsideInlineSpoiler = !!formats['inline-spoiler'];
      if (!isInsideInlineSpoiler) {
        try {
          const [leaf] = this.editor.getLeaf(range.index);
          if (leaf && leaf.domNode) {
            const el = leaf.domNode.nodeType === 1 ? leaf.domNode : leaf.domNode.parentElement;
            if (el && el.closest('.editor-inline-spoiler')) {
              isInsideInlineSpoiler = true;
            }
          }
        } catch (err) {}
      }

      buttons.forEach((btn) => {
        const fmt = btn.getAttribute('data-format');
        const val = btn.getAttribute('data-value');

        if (fmt === 'inline-spoiler') {
          btn.classList.toggle('is-active', isInsideInlineSpoiler);
          return;
        }

        if (fmt === 'align') {
          const currentAlign = formats.align || '';
          btn.classList.toggle('is-active', (val || '') === currentAlign);
          return;
        }

        if (val) {
          btn.classList.toggle('is-active', formats[fmt] === val || formats[fmt] === parseInt(val, 10));
        } else {
          btn.classList.toggle('is-active', !!formats[fmt]);
        }
      });
    }
  }

  window.BubbleToolbar = BubbleToolbar;

})(window);
