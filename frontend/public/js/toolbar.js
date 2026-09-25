/**
 * Antigravity WYSIWYG Editor - Toolbar & Dialog Manager
 * Manages modal dialogs (Link, Video Media, LaTeX Formulas, Anchor, Person),
 * compact header dropdowns, and bottom status bar undo/redo actions.
 */

(function (window) {
  'use strict';

  class ToolbarManager {
    constructor(editor) {
      this.editor = editor;
      this.activeLinkRange = null;
      this.activeFormulaRange = null;
      this.activeInsertionIndex = null;

      this.initElements();
      this.bindEvents();
      this.bindHeaderDropdowns();
      this.bindModals();
    }

    initElements() {
      // Modals
      this.linkModal = document.getElementById('link-modal');
      this.linkUrlInput = document.getElementById('link-url-input');
      this.linkTextInput = document.getElementById('link-text-input');
      this.linkSaveBtn = document.getElementById('link-save-btn');
      this.linkRemoveBtn = document.getElementById('link-remove-btn');

      this.mediaModal = document.getElementById('media-modal');
      this.mediaUrlInput = document.getElementById('media-url-input');
      this.mediaCaptionInput = document.getElementById('media-caption-input');
      this.mediaInsertBtn = document.getElementById('media-insert-btn');

      this.formulaModal = document.getElementById('formula-modal');
      this.formulaInput = document.getElementById('formula-input');
      this.formulaPreview = document.getElementById('formula-live-preview');
      this.formulaApplyBtn = document.getElementById('formula-apply-btn');

      this.anchorModal = document.getElementById('anchor-modal');
      this.anchorIdInput = document.getElementById('anchor-id-input');
      this.anchorErrorMsg = document.getElementById('anchor-error-msg');
      this.anchorApplyBtn = document.getElementById('anchor-apply-btn');

      this.personModal = document.getElementById('person-modal');
      this.personNameInput = document.getElementById('person-name-input');
      this.personRoleInput = document.getElementById('person-role-input');
      this.personLinkInput = document.getElementById('person-link-input');
      this.personAvatarInput = document.getElementById('person-avatar-input');
      this.personAvatarFile = document.getElementById('person-avatar-file');
      this.personAvatarPreview = document.getElementById('person-avatar-preview');
      this.personApplyBtn = document.getElementById('person-apply-btn');

      this.shortcutsModal = document.getElementById('shortcuts-modal');

      // Undo / Redo
      this.undoBtn = document.getElementById('btn-undo');
      this.redoBtn = document.getElementById('btn-redo');
    }

    bindEvents() {
      // Undo / Redo buttons in bottom status bar
      if (this.undoBtn) {
        this.undoBtn.addEventListener('click', () => {
          this.editor.history.undo();
        });
      }
      if (this.redoBtn) {
        this.redoBtn.addEventListener('click', () => {
          this.editor.history.redo();
        });
      }

      // Re-edit block formula on edit button click
      this.editor.root.addEventListener('click', (e) => {
        const formulaAction = e.target.closest('.formula-edit-action');
        if (formulaAction) {
          const formulaBlock = formulaAction.closest('.editor-block-formula');
          if (formulaBlock) {
            const latex = formulaBlock.getAttribute('data-latex') || '';
            this.openFormulaModal(null, null, true, latex, formulaBlock);
          }
        }
      });
    }

    bindHeaderDropdowns() {
      // Export / Import dropdown
      const exportDropdownBtn = document.getElementById('btn-export-dropdown');
      const exportDropdownMenu = document.getElementById('export-dropdown-menu');

      if (exportDropdownBtn && exportDropdownMenu) {
        exportDropdownBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          exportDropdownMenu.classList.toggle('show');
          if (moreDropdownMenu) moreDropdownMenu.classList.remove('show');
        });
      }

      // More actions dropdown
      const moreActionsBtn = document.getElementById('btn-more-actions');
      const moreDropdownMenu = document.getElementById('more-dropdown-menu');

      if (moreActionsBtn && moreDropdownMenu) {
        moreActionsBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          moreDropdownMenu.classList.toggle('show');
          if (exportDropdownMenu) exportDropdownMenu.classList.remove('show');
        });
      }

      // Close dropdowns on outside click
      document.addEventListener('click', (e) => {
        if (exportDropdownMenu && !exportDropdownMenu.contains(e.target) && e.target !== exportDropdownBtn) {
          exportDropdownMenu.classList.remove('show');
        }
        if (moreDropdownMenu && !moreDropdownMenu.contains(e.target) && e.target !== moreActionsBtn) {
          moreDropdownMenu.classList.remove('show');
        }
      });

      // Clear document
      const clearBtn = document.getElementById('btn-clear-doc');
      if (clearBtn) {
        clearBtn.addEventListener('click', () => {
          if (confirm('Вы уверены, что хотите полностью очистить документ?')) {
            this.editor.setText('');
            const titleInput = document.getElementById('article-title');
            if (titleInput) titleInput.value = '';
            if (window.EditorApp) window.EditorApp.adjustTitleHeight();
            if (moreDropdownMenu) moreDropdownMenu.classList.remove('show');
          }
        });
      }

      // Shortcuts modal button
      const shortcutsBtn = document.getElementById('btn-shortcuts-modal');
      if (shortcutsBtn && this.shortcutsModal) {
        shortcutsBtn.addEventListener('click', () => {
          this.shortcutsModal.classList.add('show');
          if (moreDropdownMenu) moreDropdownMenu.classList.remove('show');
        });
      }
    }

    bindModals() {
      // 1. Link Modal
      if (this.linkSaveBtn) {
        this.linkSaveBtn.addEventListener('click', () => this.saveLink());
      }
      if (this.linkRemoveBtn) {
        this.linkRemoveBtn.addEventListener('click', () => this.removeLink());
      }

      // 2. Media Modal
      if (this.mediaInsertBtn) {
        this.mediaInsertBtn.addEventListener('click', () => this.saveMedia());
      }

      // 3. Formula Modal
      if (this.formulaInput && this.formulaPreview) {
        this.formulaInput.addEventListener('input', () => {
          const val = this.formulaInput.value.trim();
          this.formulaPreview.textContent = val ? `\\(${val}\\)` : '\\(...)';
        });
      }
      if (this.formulaApplyBtn) {
        this.formulaApplyBtn.addEventListener('click', () => this.saveFormula());
      }

      // 4. Anchor Modal
      if (this.anchorApplyBtn) {
        this.anchorApplyBtn.addEventListener('click', () => this.saveAnchor());
      }

      // 5. Person Modal
      if (this.personAvatarFile) {
        this.personAvatarFile.addEventListener('change', (e) => {
          const file = e.target.files && e.target.files[0];
          if (file) {
            const reader = new FileReader();
            reader.onload = (evt) => {
              this.currentPersonAvatarData = evt.target.result;
              if (this.personAvatarPreview) {
                this.personAvatarPreview.innerHTML = `<img src="${evt.target.result}" style="width:50px;height:50px;border-radius:50%;object-fit:cover;">`;
              }
            };
            reader.readAsDataURL(file);
          }
        });
      }
      if (this.personApplyBtn) {
        this.personApplyBtn.addEventListener('click', () => this.savePerson());
      }
    }

    /* ==========================================================================
       Link Modal
       ========================================================================== */
    openLinkModal(range = null) {
      this.activeLinkRange = range || this.editor.getSelection();

      let currentUrl = '';
      let selectedText = '';

      if (this.activeLinkRange) {
        const formats = this.editor.getFormat(this.activeLinkRange);
        currentUrl = formats.link || '';
        selectedText = this.editor.getText(this.activeLinkRange.index, this.activeLinkRange.length);
      }

      if (this.linkUrlInput) this.linkUrlInput.value = currentUrl;
      if (this.linkTextInput) this.linkTextInput.value = selectedText;

      if (this.linkRemoveBtn) {
        this.linkRemoveBtn.style.display = currentUrl ? 'inline-block' : 'none';
      }

      if (this.linkModal) {
        this.linkModal.classList.add('show');
        setTimeout(() => {
          if (this.linkUrlInput) this.linkUrlInput.focus();
        }, 50);
      }
    }

    saveLink() {
      let url = this.linkUrlInput ? this.linkUrlInput.value.trim() : '';
      const text = this.linkTextInput ? this.linkTextInput.value.trim() : '';

      if (!url) {
        this.removeLink();
        return;
      }

      // Prepend https:// if missing
      if (!/^https?:\/\//i.test(url) && !url.startsWith('#') && !url.startsWith('/')) {
        url = 'https://' + url;
      }

      const range = this.activeLinkRange;
      if (range) {
        if (text && text !== this.editor.getText(range.index, range.length)) {
          this.editor.deleteText(range.index, range.length);
          this.editor.insertText(range.index, text, { link: url });
          this.editor.setSelection(range.index + text.length, 0);
        } else {
          this.editor.formatText(range.index, range.length, 'link', url);
          this.editor.setSelection(range.index + range.length, 0);
        }
      }

      if (this.linkModal) this.linkModal.classList.remove('show');
      this.editor.focus();
    }

    removeLink() {
      const range = this.activeLinkRange;
      if (range) {
        this.editor.formatText(range.index, range.length, 'link', false);
      }
      if (this.linkModal) this.linkModal.classList.remove('show');
      this.editor.focus();
    }

    /* ==========================================================================
       Media (Video) Modal
       ========================================================================== */
    openMediaModal(index = null) {
      this.activeInsertionIndex = index;
      if (this.mediaUrlInput) this.mediaUrlInput.value = '';
      if (this.mediaCaptionInput) this.mediaCaptionInput.value = '';
      if (this.mediaModal) {
        this.mediaModal.classList.add('show');
        setTimeout(() => {
          if (this.mediaUrlInput) this.mediaUrlInput.focus();
        }, 50);
      }
    }

    saveMedia() {
      const url = this.mediaUrlInput ? this.mediaUrlInput.value.trim() : '';
      const caption = this.mediaCaptionInput ? this.mediaCaptionInput.value.trim() : '';

      if (!url) {
        alert('Пожалуйста, укажите URL видео (YouTube, Vimeo или VK Видео).');
        return;
      }

      const parsed = window.MediaManager ? window.MediaManager.parseVideoUrl(url) : null;
      if (!parsed) {
        alert('Не удалось распознать ссылку на видео. Поддерживаются: YouTube, Vimeo и VK Видео.');
        return;
      }

      let index = this.activeInsertionIndex;
      if (index === null || index === undefined) {
        const range = this.editor.getSelection(true);
        index = range ? range.index : this.editor.getLength();
      }

      this.editor.insertEmbed(index, 'mediaEmbed', {
        provider: parsed.provider,
        embedUrl: parsed.embedUrl,
        originalUrl: parsed.originalUrl,
        caption: caption
      }, 'user');

      this.editor.insertText(index + 1, '\n', 'user');
      this.editor.setSelection(index + 2, 'user');

      if (this.mediaModal) this.mediaModal.classList.remove('show');
      this.editor.focus();
    }

    /* ==========================================================================
       Formula Modal
       ========================================================================== */
    openFormulaModal(range = null, index = null, isBlock = false, initialLatex = '', targetBlockNode = null) {
      this.activeFormulaRange = range;
      this.activeInsertionIndex = index;
      this.editingFormulaNode = targetBlockNode;

      let formulaText = initialLatex;
      if (!formulaText && range && range.length > 0) {
        formulaText = this.editor.getText(range.index, range.length).trim();
      }

      if (this.formulaInput) this.formulaInput.value = formulaText;
      if (this.formulaPreview) {
        this.formulaPreview.textContent = formulaText ? `\\(${formulaText}\\)` : '\\(...)';
      }

      const blockRadio = document.getElementById('formula-type-block');
      const inlineRadio = document.getElementById('formula-type-inline');
      if (blockRadio && inlineRadio) {
        blockRadio.checked = isBlock;
        inlineRadio.checked = !isBlock;
      }

      if (this.formulaModal) {
        this.formulaModal.classList.add('show');
        setTimeout(() => {
          if (this.formulaInput) this.formulaInput.focus();
        }, 50);
      }
    }

    saveFormula() {
      const latex = this.formulaInput ? this.formulaInput.value.trim() : '';
      if (!latex) {
        alert('Пожалуйста, введите код формулы LaTeX.');
        return;
      }

      const isBlock = document.getElementById('formula-type-block')?.checked;

      // If re-editing an existing block formula
      if (this.editingFormulaNode) {
        this.editingFormulaNode.setAttribute('data-latex', latex);
        const renderEl = this.editingFormulaNode.querySelector('.formula-rendered');
        if (renderEl) renderEl.textContent = `$$\n${latex}\n$$`;
        this.editingFormulaNode = null;
        if (this.formulaModal) this.formulaModal.classList.remove('show');
        this.editor.focus();
        return;
      }

      if (isBlock) {
        let index = this.activeInsertionIndex;
        if (index === null || index === undefined) {
          const range = this.activeFormulaRange || this.editor.getSelection(true);
          index = range ? range.index : this.editor.getLength();
        }

        this.editor.insertEmbed(index, 'blockFormula', { latex: latex }, 'user');
        this.editor.insertText(index + 1, '\n', 'user');
        this.editor.setSelection(index + 2, 'user');
      } else {
        const range = this.activeFormulaRange || this.editor.getSelection(true);
        const index = range ? range.index : 0;
        const length = range ? range.length : 0;

        if (length > 0) {
          this.editor.deleteText(index, length);
        }
        this.editor.insertEmbed(index, 'inlineFormula', { latex: latex }, 'user');
        this.editor.setSelection(index + 1, 0);
      }

      if (this.formulaModal) this.formulaModal.classList.remove('show');
      this.editor.focus();
    }

    /* ==========================================================================
       Anchor Modal
       ========================================================================== */
    openAnchorModal(index = null) {
      this.activeInsertionIndex = index;
      if (this.anchorIdInput) this.anchorIdInput.value = '';
      if (this.anchorErrorMsg) {
        this.anchorErrorMsg.style.display = 'none';
        this.anchorErrorMsg.textContent = '';
      }

      if (this.anchorModal) {
        this.anchorModal.classList.add('show');
        setTimeout(() => {
          if (this.anchorIdInput) this.anchorIdInput.focus();
        }, 50);
      }
    }

    saveAnchor() {
      const rawId = this.anchorIdInput ? this.anchorIdInput.value.trim() : '';
      if (!rawId) {
        this.showAnchorError('Пожалуйста, укажите ID якоря.');
        return;
      }

      const cleanId = rawId.toLowerCase().replace(/[^a-z0-9а-яё_-]/gi, '-');

      // Unique ID check across document
      const existingAnchor = document.querySelector(`.editor-anchor-block[data-anchor-id="${cleanId}"]`);
      if (existingAnchor) {
        this.showAnchorError(`Якорь с ID "#${cleanId}" уже существует в статье. Укажите уникальный ID.`);
        return;
      }

      let index = this.activeInsertionIndex;
      if (index === null || index === undefined) {
        const range = this.editor.getSelection(true);
        index = range ? range.index : this.editor.getLength();
      }

      this.editor.insertEmbed(index, 'anchor', { id: cleanId }, 'user');
      this.editor.insertText(index + 1, '\n', 'user');
      this.editor.setSelection(index + 2, 'user');

      if (this.anchorModal) this.anchorModal.classList.remove('show');
      this.editor.focus();
    }

    showAnchorError(msg) {
      if (this.anchorErrorMsg) {
        this.anchorErrorMsg.textContent = msg;
        this.anchorErrorMsg.style.display = 'block';
      }
    }

    /* ==========================================================================
       Person Modal
       ========================================================================== */
    openPersonModal(index = null) {
      this.activeInsertionIndex = index;
      this.currentPersonAvatarData = null;

      if (this.personNameInput) this.personNameInput.value = '';
      if (this.personRoleInput) this.personRoleInput.value = '';
      if (this.personLinkInput) this.personLinkInput.value = '';
      if (this.personAvatarInput) this.personAvatarInput.value = '';
      if (this.personAvatarFile) this.personAvatarFile.value = '';
      if (this.personAvatarPreview) this.personAvatarPreview.innerHTML = '';

      if (this.personModal) {
        this.personModal.classList.add('show');
        setTimeout(() => {
          if (this.personNameInput) this.personNameInput.focus();
        }, 50);
      }
    }

    savePerson() {
      const name = this.personNameInput ? this.personNameInput.value.trim() : '';
      if (!name) {
        alert('Пожалуйста, укажите имя персоны.');
        return;
      }

      const role = this.personRoleInput ? this.personRoleInput.value.trim() : '';
      const link = this.personLinkInput ? this.personLinkInput.value.trim() : '';
      let avatar = this.currentPersonAvatarData || (this.personAvatarInput ? this.personAvatarInput.value.trim() : '');

      let index = this.activeInsertionIndex;
      if (index === null || index === undefined) {
        const range = this.editor.getSelection(true);
        index = range ? range.index : this.editor.getLength();
      }

      this.editor.insertEmbed(index, 'person', {
        name: name,
        role: role,
        link: link,
        avatar: avatar
      }, 'user');

      this.editor.insertText(index + 1, '\n', 'user');
      this.editor.setSelection(index + 2, 'user');

      if (this.personModal) this.personModal.classList.remove('show');
      this.editor.focus();
    }
  }

  window.ToolbarManager = ToolbarManager;

})(window);
