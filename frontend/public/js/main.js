/**
 * Antigravity WYSIWYG Editor - Main Bootstrap
 * Orchestrates themes, modules, modals, live stats, preview mode, and shortcuts.
 * 100% offline-first.
 */

(function (window) {
  'use strict';

  class EditorApplication {
    constructor() {
      this.theme = 'light';
      this.mode = 'edit'; // 'edit' or 'preview'
      this.editor = null;
      this.titleInput = null;
      this.Toolbar = null;
      this.Bubble = null;
      this.Blocks = null;
      this.Table = null;
      this.Media = null;
      this.Drafts = null;
      this.Converter = null;
      this.Publication = null;

      this.init();
    }

    init() {
      this.initTheme();
      this.titleInput = document.getElementById('article-title');

      // Initialize Quill Editor
      const editorContainer = document.getElementById('editor');
      if (!editorContainer) {
        console.error('#editor container not found');
        return;
      }

      this.editor = window.EditorCore.initQuill(editorContainer);

      // Initialize feature managers
      this.Toolbar = new window.ToolbarManager(this.editor);
      this.Bubble = new window.BubbleToolbar(this.editor);
      this.Blocks = new window.BlockInserter(this.editor);
      this.Table = new window.TableManager(this.editor);
      this.Media = new window.MediaManager(this.editor);
      this.Converter = new window.Converter(this.editor, this.titleInput);
      this.Drafts = new window.DraftsManager(this.editor, this.titleInput);
      if (window.PublicationManager) {
        this.Publication = new window.PublicationManager(this.editor, this.titleInput);
        window.publicationManager = this.Publication;
      }
      if (window.NodeControlsManager) {
        this.NodeControls = new window.NodeControlsManager(this.editor);
      }
      if (window.ImageMenuManager) {
        this.ImageMenu = new window.ImageMenuManager(this.editor);
      }

      this.bindTitleEvents();
      this.bindStats();
      this.bindModals();
      this.bindModeToggle();
      this.bindExportImport();
      this.bindShortcuts();
      this.bindInlineSpoilerInteraction();
      this.bindTypograph();
      this.bindChecklist();
    }

    /* ==========================================================================
       Theme Management
       ========================================================================== */
    initTheme() {
      const savedTheme = localStorage.getItem('ag_theme');
      if (savedTheme) {
        this.theme = savedTheme;
      } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        this.theme = 'dark';
      } else {
        this.theme = 'light';
      }
      this.applyTheme(this.theme);

      const toggleBtn = document.getElementById('btn-theme-toggle');
      if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
          this.theme = this.theme === 'dark' ? 'light' : 'dark';
          this.applyTheme(this.theme);
        });
      }
    }

    applyTheme(theme) {
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('ag_theme', theme);

      // Switch Highlight.js theme
      const hljsThemeLink = document.getElementById('hljs-theme');
      if (hljsThemeLink) {
        hljsThemeLink.href = theme === 'dark' ? 'vendor/highlight/github-dark.min.css' : 'vendor/highlight/github.min.css';
      }
    }

    /* ==========================================================================
       Mode Switching (Edit / Preview)
       ========================================================================== */
    bindModeToggle() {
      const editBtn = document.getElementById('btn-mode-edit');
      const previewBtn = document.getElementById('btn-mode-preview');

      if (editBtn) {
        editBtn.addEventListener('click', () => this.setMode('edit'));
      }
      if (previewBtn) {
        previewBtn.addEventListener('click', () => this.setMode('preview'));
      }
    }

    setMode(mode) {
      this.mode = mode;
      const editBtn = document.getElementById('btn-mode-edit');
      const previewBtn = document.getElementById('btn-mode-preview');

      if (mode === 'preview') {
        document.body.classList.add('preview-mode');
        if (editBtn) editBtn.classList.remove('active');
        if (previewBtn) previewBtn.classList.add('active');

        this.editor.enable(false);
        if (this.titleInput) this.titleInput.setAttribute('readonly', 'true');
        if (this.Blocks) this.Blocks.hide();
        if (this.Bubble) this.Bubble.hide();
        if (this.NodeControls) this.NodeControls.hide();
        if (this.ImageMenu) this.ImageMenu.hide();
      } else {
        document.body.classList.remove('preview-mode');
        if (editBtn) editBtn.classList.add('active');
        if (previewBtn) previewBtn.classList.remove('active');

        this.editor.enable(true);
        if (this.titleInput) this.titleInput.removeAttribute('readonly');
      }
    }

    bindInlineSpoilerInteraction() {
      // Clicking an inline spoiler toggles reveal / hide in all modes (edit and preview)
      this.editor.root.addEventListener('click', (e) => {
        const spoiler = e.target.closest('.editor-inline-spoiler');
        if (spoiler) {
          const isRevealed = spoiler.classList.contains('is-revealed') || spoiler.getAttribute('data-revealed') === 'true';
          if (isRevealed) {
            spoiler.classList.remove('is-revealed');
            spoiler.removeAttribute('data-revealed');
          } else {
            spoiler.classList.add('is-revealed');
            spoiler.setAttribute('data-revealed', 'true');
          }
        }
      });
    }

    /* ==========================================================================
       Article Title Field
       ========================================================================== */
    bindTitleEvents() {
      if (!this.titleInput) return;

      this.titleInput.addEventListener('input', () => {
        this.adjustTitleHeight();
        this.updateDocumentTitle();
        if (this.Publication) {
          this.Publication.updateReadinessUI();
        }
      });

      this.titleInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          this.editor.focus();
        }
      });

      this.adjustTitleHeight();
    }

    adjustTitleHeight() {
      if (!this.titleInput) return;
      this.titleInput.style.height = 'auto';
      this.titleInput.style.height = `${Math.max(48, this.titleInput.scrollHeight)}px`;
    }

    updateDocumentTitle() {
      const title = this.titleInput ? this.titleInput.value.trim() : '';
      document.title = title ? `${title} — Antigravity Editor` : 'Создание статьи — Antigravity Editor';
    }

    /* ==========================================================================
       Document Statistics (Words, Chars, Reading Time) in Bottom Status Bar
       ========================================================================== */
    bindStats() {
      this.editor.on('text-change', () => {
        this.updateStats();
        if (this.Publication) {
          this.Publication.updateReadinessUI();
        }
      });
      this.updateStats();
    }

    updateStats() {
      const text = this.editor.getText().trim();
      const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
      const chars = text.length;
      const readingTime = Math.max(1, Math.ceil(words / 200));

      const wordsEl = document.getElementById('stat-words');
      const charsEl = document.getElementById('stat-chars');
      const readingTimeEl = document.getElementById('stat-reading-time');

      if (wordsEl) wordsEl.textContent = `${words} сл.`;
      if (charsEl) charsEl.textContent = `${chars} зн.`;
      if (readingTimeEl) readingTimeEl.textContent = `${readingTime} мин чтения`;
    }

    /* ==========================================================================
       Modals & Dialogs
       ========================================================================== */
    bindModals() {
      // Close modal on click on overlay or close button
      // Note: publication-modal backdrop click does NOT close modal (spec requirement)
      document.querySelectorAll('.modal-overlay').forEach(modal => {
        modal.addEventListener('click', (e) => {
          if (modal.id === 'publication-modal') {
            if (e.target.closest('.modal-close-btn') || e.target.closest('[data-modal-close]')) {
              if (this.Publication) {
                this.Publication.closeModal(true);
              } else {
                modal.classList.remove('show');
              }
            }
            return;
          }
          if (e.target === modal || e.target.closest('.modal-close-btn') || e.target.closest('[data-modal-close]')) {
            modal.classList.remove('show');
          }
        });
      });

      // Drafts modal button in header
      const draftsBtn = document.getElementById('btn-drafts-modal');
      if (draftsBtn) {
        draftsBtn.addEventListener('click', () => {
          if (this.Drafts) this.Drafts.openDraftsModal();
        });
      }
    }

    /* ==========================================================================
       Export & Import Functionality
       ========================================================================== */
    bindExportImport() {
      const exportModal = document.getElementById('export-modal');
      const exportCodeBox = document.getElementById('export-code-box');
      const exportCopyBtn = document.getElementById('export-copy-btn');
      const exportDownloadBtn = document.getElementById('export-download-btn');
      const exportWarningBanner = document.getElementById('export-warning-banner');

      let currentExportType = 'html';

      const updateExportPreview = () => {
        if (!exportCodeBox) return;
        let content = '';
        if (currentExportType === 'html') {
          content = this.Converter.exportToHTML(true);
        } else if (currentExportType === 'markdown') {
          content = this.Converter.exportToMarkdown();
        } else if (currentExportType === 'json') {
          content = this.Converter.exportToJSON();
        }
        exportCodeBox.textContent = content;

        // Display loss warnings if any
        const warnings = this.Converter.getLastWarnings();
        if (exportWarningBanner) {
          if (warnings && warnings.length > 0) {
            exportWarningBanner.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -3px; margin-right: 6px;"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg><strong>Предупреждение о совместимости:</strong><br>' + warnings.map(w => `• ${w}`).join('<br>');
            exportWarningBanner.style.display = 'block';
          } else {
            exportWarningBanner.style.display = 'none';
          }
        }
      };

      // Header Export menu triggers
      const menuExportHtml = document.getElementById('menu-export-html');
      const menuExportMd = document.getElementById('menu-export-markdown');
      const menuExportJson = document.getElementById('menu-export-json');
      const menuImportJson = document.getElementById('menu-import-json');

      const openExportWithTab = (tabName) => {
        currentExportType = tabName;
        document.querySelectorAll('[data-export-tab]').forEach(tab => {
          tab.classList.toggle('active', tab.getAttribute('data-export-tab') === tabName);
        });
        updateExportPreview();
        if (exportModal) exportModal.classList.add('show');
        const exportMenu = document.getElementById('export-dropdown-menu');
        if (exportMenu) exportMenu.classList.remove('show');
      };

      if (menuExportHtml) {
        menuExportHtml.addEventListener('click', () => openExportWithTab('html'));
      }
      if (menuExportMd) {
        menuExportMd.addEventListener('click', () => openExportWithTab('markdown'));
      }
      if (menuExportJson) {
        menuExportJson.addEventListener('click', () => openExportWithTab('json'));
      }

      // Export format tabs in modal
      const exportTabs = document.querySelectorAll('[data-export-tab]');
      exportTabs.forEach(tab => {
        tab.addEventListener('click', () => {
          exportTabs.forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          currentExportType = tab.getAttribute('data-export-tab');
          updateExportPreview();
        });
      });

      // Copy to clipboard
      if (exportCopyBtn) {
        exportCopyBtn.addEventListener('click', () => {
          const content = exportCodeBox ? exportCodeBox.textContent : '';
          this.Converter.copyToClipboard(content).then(() => {
            this.showToast('Скопировано в буфер обмена!', 'success');
          });
        });
      }

      // Download file
      if (exportDownloadBtn) {
        exportDownloadBtn.addEventListener('click', () => {
          const title = (this.titleInput ? this.titleInput.value.trim() : '') || 'article';
          const cleanTitle = title.toLowerCase().replace(/[^a-z0-9а-яё]/gi, '_').substring(0, 30);
          const content = exportCodeBox ? exportCodeBox.textContent : '';

          let filename = `${cleanTitle}.${currentExportType === 'markdown' ? 'md' : currentExportType}`;
          let mime = 'text/plain;charset=utf-8';
          if (currentExportType === 'html') mime = 'text/html;charset=utf-8';
          if (currentExportType === 'json') mime = 'application/json;charset=utf-8';

          this.Converter.downloadFile(filename, content, mime);
          this.showToast(`Файл ${filename} скачан`, 'success');
        });
      }

      // Import modal
      const importModal = document.getElementById('import-modal');
      const importTextarea = document.getElementById('import-json-textarea');
      const importSubmitBtn = document.getElementById('import-submit-btn');
      const importFileInput = document.getElementById('import-file-input');

      if (menuImportJson && importModal) {
        menuImportJson.addEventListener('click', () => {
          if (importTextarea) importTextarea.value = '';
          importModal.classList.add('show');
          const exportMenu = document.getElementById('export-dropdown-menu');
          if (exportMenu) exportMenu.classList.remove('show');
        });
      }

      if (importFileInput) {
        importFileInput.addEventListener('change', (e) => {
          const file = e.target.files && e.target.files[0];
          if (file) {
            const reader = new FileReader();
            reader.onload = (evt) => {
              if (importTextarea) importTextarea.value = evt.target.result;
            };
            reader.readAsText(file);
          }
        });
      }

      if (importSubmitBtn) {
        importSubmitBtn.addEventListener('click', () => {
          const jsonText = importTextarea ? importTextarea.value.trim() : '';
          if (!jsonText) {
            alert('Пожалуйста, вставьте JSON или выберите файл.');
            return;
          }
          const success = this.Converter.importFromJSON(jsonText);
          if (success && importModal) {
            importModal.classList.remove('show');
          }
        });
      }
    }

    /* ==========================================================================
       Shortcuts & UI helpers
       ========================================================================== */
    bindShortcuts() {
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          document.querySelectorAll('.modal-overlay.show').forEach(m => m.classList.remove('show'));
          document.querySelectorAll('.dropdown-menu.show').forEach(d => d.classList.remove('show'));
        }
      });
    }

    /* ==========================================================================
       Sidebar Widgets: Typograph & Live Checklist
       ========================================================================== */
    bindTypograph() {
      const typoBtn = document.getElementById('btn-typograph');
      if (!typoBtn) return;

      typoBtn.addEventListener('click', () => {
        if (window.Typograph) {
          window.Typograph.typographEditor(this.editor, this.titleInput);
          this.typographVerified = true;
          const statusEl = document.getElementById('typograph-status');
          if (statusEl) {
            statusEl.style.display = 'flex';
          }
          this.showToast('Текст статьи успешно оттипографилен', 'success');
          this.updateChecklist();
        }
      });
    }

    bindChecklist() {
      this.typographVerified = false;

      this.editor.on('text-change', () => {
        this.updateChecklist();
      });

      if (this.titleInput) {
        this.titleInput.addEventListener('input', () => {
          this.updateChecklist();
        });
      }

      this.updateChecklist();
    }

    updateChecklist() {
      const titleFilled = this.titleInput ? this.titleInput.value.trim().length > 0 : false;

      const text = this.editor.getText().trim();
      const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
      const wordsMet = words > 100;

      const hasHeaders = Boolean(this.editor.root.querySelector('h2, h3, h4'));

      const typoMet = Boolean(this.typographVerified);

      const chkTitle = document.getElementById('chk-title');
      const chkWords = document.getElementById('chk-words');
      const chkHeaders = document.getElementById('chk-headers');
      const chkTypo = document.getElementById('chk-typograph');

      const setItemState = (el, isChecked) => {
        if (!el) return;
        el.classList.toggle('checked', isChecked);
        const box = el.querySelector('.checklist-box');
        if (box) box.innerHTML = isChecked ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>' : '';
      };

      setItemState(chkTitle, titleFilled);
      setItemState(chkWords, wordsMet);
      setItemState(chkHeaders, hasHeaders);
      setItemState(chkTypo, typoMet);

      const completedCount = [titleFilled, wordsMet, hasHeaders, typoMet].filter(Boolean).length;
      const pct = Math.round((completedCount / 4) * 100);

      const progressFill = document.getElementById('checklist-progress-fill');
      if (progressFill) {
        progressFill.style.width = `${pct}%`;
      }

      const badge = document.getElementById('readiness-badge');
      if (badge) {
        if (completedCount === 4) {
          badge.className = 'readiness-badge badge-success';
          badge.textContent = 'Готово к публикации';
        } else if (completedCount > 0) {
          badge.className = 'readiness-badge badge-warning';
          badge.textContent = `Черновик (${completedCount}/4)`;
        } else {
          badge.className = 'readiness-badge badge-muted';
          badge.textContent = 'Черновик (0/4)';
        }
      }
    }

    showToast(message, type = 'info', duration = 3000) {
      const container = document.getElementById('toast-container');
      if (!container) return;

      const toast = document.createElement('div');
      toast.className = `toast toast-${type}`;

      let icon = '';
      if (type === 'success') {
        icon = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--success-color)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -3px; margin-right: 6px;"><polyline points="20 6 9 17 4 12"></polyline></svg>';
      } else if (type === 'danger') {
        icon = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--danger-color)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -3px; margin-right: 6px;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
      } else {
        icon = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-color)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -3px; margin-right: 6px;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>';
      }

      toast.innerHTML = `${icon}<span>${this.Converter.escapeHTML(message)}</span>`;
      container.appendChild(toast);

      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
      }, duration);
    }
  }

  // Bootstrap when DOM is ready
  document.addEventListener('DOMContentLoaded', () => {
    window.EditorApp = new EditorApplication();
  });

})(window);
