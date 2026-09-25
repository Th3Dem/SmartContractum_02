/**
 * Antigravity WYSIWYG Editor - Floating Block Inserter (+) & Menu
 * Notion/Habr-inspired block inserter for quick media and structure insertion
 */

(function (window) {
  'use strict';

  class BlockInserter {
    constructor(editor) {
      this.editor = editor;
      this.inserter = document.getElementById('block-inserter');
      this.inserterBtn = document.getElementById('block-inserter-btn');
      this.blockMenu = document.getElementById('block-menu');
      this.editorWrapper = document.querySelector('.editor-wrapper');

      if (!this.inserter || !this.inserterBtn || !this.blockMenu) return;

      this.currentLineIndex = 0;
      this.bindEvents();
    }

    bindEvents() {
      // Track selection or cursor movement
      this.editor.on('selection-change', (range) => {
        if (!range) {
          this.hide();
          return;
        }

        // Only show if selection is collapsed (a single caret position)
        if (range.length === 0) {
          this.updatePosition(range.index);
        } else {
          this.hide();
        }
      });

      // Toggle menu on "+" button click
      this.inserterBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleMenu();
      });

      // Handle item click in block menu
      this.blockMenu.addEventListener('click', (e) => {
        const item = e.target.closest('.block-menu-item');
        if (!item) return;

        const blockType = item.getAttribute('data-block');
        this.insertBlock(blockType);
        this.closeMenu();
      });

      // Close menu when clicking outside
      document.addEventListener('click', (e) => {
        if (!this.blockMenu.contains(e.target) && e.target !== this.inserterBtn) {
          this.closeMenu();
        }
      });

      // Close on Escape
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.blockMenu.classList.contains('show')) {
          this.closeMenu();
        }
      });
    }

    updatePosition(index) {
      this.currentLineIndex = index;

      const bounds = this.editor.getBounds(index);
      if (!bounds) {
        this.hide();
        return;
      }

      // Calculate vertical offset relative to editor container
      const containerRect = this.editor.container.getBoundingClientRect();
      const wrapperRect = this.editorWrapper.getBoundingClientRect();

      const topOffset = (containerRect.top - wrapperRect.top) + bounds.top;

      this.inserter.style.top = `${topOffset}px`;
      this.inserter.classList.add('visible');
    }

    hide() {
      if (this.inserter) {
        this.inserter.classList.remove('visible');
      }
      this.closeMenu();
    }

    toggleMenu() {
      const isOpen = this.blockMenu.classList.contains('show');
      if (isOpen) {
        this.closeMenu();
      } else {
        this.openMenu();
      }
    }

    openMenu() {
      this.blockMenu.classList.add('show');
      this.inserterBtn.classList.add('active');
    }

    closeMenu() {
      this.blockMenu.classList.remove('show');
      this.inserterBtn.classList.remove('active');
    }

    insertBlock(type) {
      const index = this.currentLineIndex;
      this.editor.focus();

      switch (type) {
        case 'image':
          if (window.EditorApp && window.EditorApp.Media) {
            window.EditorApp.Media.openModal();
          }
          break;

        case 'code-block':
          this.editor.formatLine(index, 1, 'code-block', true);
          break;

        case 'table':
          if (window.EditorApp && window.EditorApp.Table) {
            window.EditorApp.Table.insertDefaultTable(index);
          }
          break;

        case 'blockquote':
          this.editor.formatLine(index, 1, 'blockquote', true);
          break;

        case 'spoiler':
          this.editor.insertEmbed(index, 'spoiler', {
            title: 'Спойлер (нажмите, чтобы открыть)',
            body: 'Скрытый текст спойлера...'
          }, 'user');
          this.editor.insertText(index + 1, '\n', 'user');
          this.editor.setSelection(index + 2, 'user');
          break;

        case 'divider':
          this.editor.insertEmbed(index, 'divider', true, 'user');
          this.editor.insertText(index + 1, '\n', 'user');
          this.editor.setSelection(index + 2, 'user');
          break;

        case 'checklist':
          this.editor.formatLine(index, 1, 'list', 'check');
          break;

        case 'ordered-list':
          this.editor.formatLine(index, 1, 'list', 'ordered');
          break;

        case 'bullet-list':
          this.editor.formatLine(index, 1, 'list', 'bullet');
          break;

        default:
          break;
      }
    }
  }

  window.BlockInserter = BlockInserter;

})(window);
