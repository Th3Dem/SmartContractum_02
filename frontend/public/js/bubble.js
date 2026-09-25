/**
 * Antigravity WYSIWYG Editor - Floating Contextual Bubble Toolbar
 * Appears when text is selected inside the editor for quick formatting
 */

(function (window) {
  'use strict';

  class BubbleToolbar {
    constructor(editor) {
      this.editor = editor;
      this.bubble = document.getElementById('bubble-toolbar');
      this.editorContainer = editor.container;

      if (!this.bubble) return;

      this.bindEvents();
    }

    bindEvents() {
      // Selection change event from Quill
      this.editor.on('selection-change', (range, oldRange, source) => {
        if (range && range.length > 0) {
          this.show(range);
        } else {
          this.hide();
        }
      });

      // Handle button clicks in bubble toolbar
      this.bubble.addEventListener('click', (e) => {
        const btn = e.target.closest('.bubble-btn');
        if (!btn) return;

        const format = btn.getAttribute('data-format');
        const value = btn.getAttribute('data-value');
        const action = btn.getAttribute('data-action');

        const range = this.editor.getSelection();
        if (!range || range.length === 0) return;

        if (action === 'clear-format') {
          this.editor.removeFormat(range.index, range.length);
          this.updateActiveStates(range);
          return;
        }

        if (action === 'link') {
          if (window.EditorApp && window.EditorApp.Toolbar) {
            window.EditorApp.Toolbar.openLinkModal();
          }
          return;
        }

        if (format) {
          const current = this.editor.getFormat(range);
          if (value !== null && value !== undefined) {
            const nextVal = (current[format] === parseInt(value, 10) || current[format] === value) ? false : value;
            this.editor.format(format, nextVal);
          } else {
            this.editor.format(format, !current[format]);
          }
          this.updateActiveStates(range);
        }
      });

      // Hide bubble on window scroll or resize
      window.addEventListener('scroll', () => {
        const range = this.editor.getSelection();
        if (range && range.length > 0) {
          this.reposition(range);
        } else {
          this.hide();
        }
      }, { passive: true });
    }

    show(range) {
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

      const containerRect = this.editorContainer.getBoundingClientRect();
      const editorWrapper = this.editorContainer.closest('.editor-wrapper') || this.editorContainer;
      const wrapperRect = editorWrapper.getBoundingClientRect();

      // Horizontal center of selection relative to editorWrapper
      const left = (containerRect.left - wrapperRect.left) + bounds.left + (bounds.width / 2);
      // Vertical top of selection relative to editorWrapper
      const top = (containerRect.top - wrapperRect.top) + bounds.top;

      this.bubble.style.left = `${Math.max(120, Math.min(left, wrapperRect.width - 120))}px`;
      this.bubble.style.top = `${top}px`;
    }

    updateActiveStates(range) {
      if (!range || !this.bubble) return;

      const formats = this.editor.getFormat(range);
      const buttons = this.bubble.querySelectorAll('.bubble-btn[data-format]');

      buttons.forEach((btn) => {
        const fmt = btn.getAttribute('data-format');
        const val = btn.getAttribute('data-value');

        if (val) {
          btn.classList.toggle('is-active', formats[fmt] === parseInt(val, 10) || formats[fmt] === val);
        } else {
          btn.classList.toggle('is-active', !!formats[fmt]);
        }
      });
    }
  }

  window.BubbleToolbar = BubbleToolbar;

})(window);
