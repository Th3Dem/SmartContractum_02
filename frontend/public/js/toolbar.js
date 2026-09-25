/**
 * Antigravity WYSIWYG Editor - Sticky Top Toolbar
 * Format buttons, dropdowns, color pickers, and state synchronization
 */

(function (window) {
  'use strict';

  class ToolbarManager {
    constructor(editor) {
      this.editor = editor;
      this.activeLinkRange = null;

      this.initElements();
      this.bindEvents();
      this.initColorPickers();
    }

    initElements() {
      this.toolbar = document.getElementById('editor-toolbar');
      this.headingSelect = document.getElementById('tb-heading');
      this.linkModal = document.getElementById('link-modal');
      this.linkUrlInput = document.getElementById('link-url-input');
      this.linkTextInput = document.getElementById('link-text-input');
      this.linkTargetInput = document.getElementById('link-target-input');
      this.linkSaveBtn = document.getElementById('link-save-btn');
      this.linkRemoveBtn = document.getElementById('link-remove-btn');
    }

    bindEvents() {
      if (!this.toolbar) return;

      // Handle click on toolbar buttons with data-format
      this.toolbar.addEventListener('click', (e) => {
        const btn = e.target.closest('.tb-btn');
        if (!btn) return;

        const format = btn.getAttribute('data-format');
        const value = btn.getAttribute('data-value');
        const action = btn.getAttribute('data-action');

        if (action) {
          this.handleAction(action);
          return;
        }

        if (format) {
          this.toggleFormat(format, value);
        }
      });

      // Heading selector change
      if (this.headingSelect) {
        this.headingSelect.addEventListener('change', (e) => {
          const val = e.target.value;
          if (val === 'p') {
            this.editor.format('header', false);
          } else {
            this.editor.format('header', parseInt(val, 10));
          }
        });
      }

      // Sync active state on selection change
      this.editor.on('selection-change', (range) => {
        this.updateActiveStates(range);
      });

      // Link Modal events
      if (this.linkSaveBtn) {
        this.linkSaveBtn.addEventListener('click', () => this.saveLink());
      }
      if (this.linkRemoveBtn) {
        this.linkRemoveBtn.addEventListener('click', () => this.removeLink());
      }
    }

    handleAction(action) {
      switch (action) {
        case 'undo':
          this.editor.history.undo();
          break;
        case 'redo':
          this.editor.history.redo();
          break;
        case 'clear-format': {
          const range = this.editor.getSelection();
          if (range) {
            this.editor.removeFormat(range.index, range.length);
          }
          break;
        }
        case 'link':
          this.openLinkModal();
          break;
        case 'divider':
          this.insertDivider();
          break;
        case 'spoiler':
          this.insertSpoiler();
          break;
        case 'table':
          if (window.EditorApp && window.EditorApp.Table) {
            window.EditorApp.Table.openInsertModal();
          }
          break;
        case 'image':
          if (window.EditorApp && window.EditorApp.Media) {
            window.EditorApp.Media.openModal();
          }
          break;
        case 'code-block':
          this.toggleCodeBlock();
          break;
        case 'checklist':
          this.toggleFormat('list', 'check');
          break;
        case 'ordered-list':
          this.toggleFormat('list', 'ordered');
          break;
        case 'bullet-list':
          this.toggleFormat('list', 'bullet');
          break;
        case 'indent':
          this.editor.format('indent', '+1');
          break;
        case 'outdent':
          this.editor.format('indent', '-1');
          break;
        default:
          break;
      }
    }

    toggleFormat(format, value) {
      const current = this.editor.getFormat();
      if (value !== null && value !== undefined) {
        this.editor.format(format, current[format] === value ? false : value);
      } else {
        this.editor.format(format, !current[format]);
      }
    }

    toggleCodeBlock() {
      const current = this.editor.getFormat();
      this.editor.format('code-block', !current['code-block']);
    }

    insertDivider() {
      const range = this.editor.getSelection(true);
      const index = range ? range.index : this.editor.getLength();
      this.editor.insertEmbed(index, 'divider', true, 'user');
      this.editor.insertText(index + 1, '\n', 'user');
      this.editor.setSelection(index + 2, 'silent');
    }

    insertSpoiler(title = 'Спойлер (нажмите, чтобы открыть)', body = 'Скрытый текст спойлера...') {
      const range = this.editor.getSelection(true);
      const index = range ? range.index : this.editor.getLength();
      this.editor.insertEmbed(index, 'spoiler', { title, body }, 'user');
      this.editor.insertText(index + 1, '\n', 'user');
      this.editor.setSelection(index + 2, 'silent');
    }

    /* ==========================================================================
       Color Pickers (Text Color & Highlight Background)
       ========================================================================== */
    initColorPickers() {
      const textColors = ['#000000', '#475569', '#2563eb', '#059669', '#d97706', '#dc2626', '#7c3aed', '#db2777'];
      const bgColors = ['#fef08a', '#bbf7d0', '#fed7aa', '#bae6fd', '#fbcfe8', '#e2e8f0', '#ddd6fe', '#fecdd3'];

      this.setupPalette('btn-text-color', 'popover-text-color', textColors, (color) => {
        this.editor.format('color', color);
      }, () => {
        this.editor.format('color', false);
      });

      this.setupPalette('btn-bg-color', 'popover-bg-color', bgColors, (color) => {
        this.editor.format('background', color);
      }, () => {
        this.editor.format('background', false);
      });
    }

    setupPalette(btnId, popoverId, colors, onSelect, onReset) {
      const btn = document.getElementById(btnId);
      const popover = document.getElementById(popoverId);
      if (!btn || !popover) return;

      const paletteEl = popover.querySelector('.color-palette');
      const resetBtn = popover.querySelector('.color-reset-btn');

      if (paletteEl) {
        paletteEl.innerHTML = '';
        colors.forEach((color) => {
          const swatch = document.createElement('div');
          swatch.className = 'color-swatch';
          swatch.style.backgroundColor = color;
          swatch.addEventListener('click', (e) => {
            e.stopPropagation();
            onSelect(color);
            popover.classList.remove('show');
          });
          paletteEl.appendChild(swatch);
        });
      }

      if (resetBtn) {
        resetBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          onReset();
          popover.classList.remove('show');
        });
      }

      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        // Close any other open popovers
        document.querySelectorAll('.color-picker-popover').forEach(p => {
          if (p !== popover) p.classList.remove('show');
        });
        popover.classList.toggle('show');
      });

      document.addEventListener('click', (e) => {
        if (!popover.contains(e.target) && e.target !== btn) {
          popover.classList.remove('show');
        }
      });
    }

    /* ==========================================================================
       Link Modal Handling
       ========================================================================== */
    openLinkModal() {
      const range = this.editor.getSelection();
      this.activeLinkRange = range;

      let currentLink = '';
      let selectedText = '';

      if (range) {
        const formats = this.editor.getFormat(range);
        currentLink = formats.link || '';
        selectedText = this.editor.getText(range.index, range.length);
      }

      if (this.linkUrlInput) this.linkUrlInput.value = currentLink;
      if (this.linkTextInput) this.linkTextInput.value = selectedText;
      if (this.linkRemoveBtn) {
        this.linkRemoveBtn.style.display = currentLink ? 'inline-flex' : 'none';
      }

      if (this.linkModal) {
        this.linkModal.classList.add('show');
        setTimeout(() => this.linkUrlInput && this.linkUrlInput.focus(), 50);
      }
    }

    saveLink() {
      let url = this.linkUrlInput ? this.linkUrlInput.value.trim() : '';
      const text = this.linkTextInput ? this.linkTextInput.value.trim() : '';

      if (!url) {
        this.closeLinkModal();
        return;
      }

      // Automatically add https:// if scheme is missing
      if (!/^https?:\/\//i.test(url) && !url.startsWith('/') && !url.startsWith('#') && !url.startsWith('mailto:')) {
        url = 'https://' + url;
      }

      if (this.activeLinkRange && this.activeLinkRange.length > 0) {
        if (text && text !== this.editor.getText(this.activeLinkRange.index, this.activeLinkRange.length)) {
          this.editor.deleteText(this.activeLinkRange.index, this.activeLinkRange.length);
          this.editor.insertText(this.activeLinkRange.index, text, { link: url });
        } else {
          this.editor.formatText(this.activeLinkRange.index, this.activeLinkRange.length, 'link', url);
        }
      } else {
        const index = this.activeLinkRange ? this.activeLinkRange.index : this.editor.getLength();
        this.editor.insertText(index, text || url, { link: url });
      }

      this.closeLinkModal();
    }

    removeLink() {
      if (this.activeLinkRange) {
        this.editor.formatText(this.activeLinkRange.index, this.activeLinkRange.length || 1, 'link', false);
      }
      this.closeLinkModal();
    }

    closeLinkModal() {
      if (this.linkModal) {
        this.linkModal.classList.remove('show');
      }
      this.activeLinkRange = null;
    }

    /* ==========================================================================
       Synchronize Toolbar States
       ========================================================================== */
    updateActiveStates(range) {
      if (!range) return;

      const formats = this.editor.getFormat(range);

      // Update button active states
      const buttons = this.toolbar.querySelectorAll('.tb-btn[data-format]');
      buttons.forEach((btn) => {
        const fmt = btn.getAttribute('data-format');
        const val = btn.getAttribute('data-value');
        if (val) {
          btn.classList.toggle('is-active', formats[fmt] === val);
        } else {
          btn.classList.toggle('is-active', !!formats[fmt]);
        }
      });

      // Update action-based active states (e.g. lists, blockquote)
      const actionButtons = this.toolbar.querySelectorAll('.tb-btn[data-action]');
      actionButtons.forEach((btn) => {
        const act = btn.getAttribute('data-action');
        if (act === 'blockquote') {
          btn.classList.toggle('is-active', !!formats['blockquote']);
        } else if (act === 'checklist') {
          btn.classList.toggle('is-active', formats['list'] === 'check');
        } else if (act === 'ordered-list') {
          btn.classList.toggle('is-active', formats['list'] === 'ordered');
        } else if (act === 'bullet-list') {
          btn.classList.toggle('is-active', formats['list'] === 'bullet');
        } else if (act === 'code-block') {
          btn.classList.toggle('is-active', !!formats['code-block']);
        }
      });

      // Update Heading dropdown
      if (this.headingSelect) {
        const headerLevel = formats['header'];
        this.headingSelect.value = headerLevel ? String(headerLevel) : 'p';
      }
    }
  }

  window.ToolbarManager = ToolbarManager;

})(window);
