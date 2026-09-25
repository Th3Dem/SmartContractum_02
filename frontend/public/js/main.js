/**
 * Antigravity WYSIWYG Editor - Main Bootstrap
 * Orchestrates themes, modules, modals, stats, and shortcuts
 */

(function (window) {
  'use strict';

  class EditorApplication {
    constructor() {
      this.theme = 'light';
      this.editor = null;
      this.titleInput = null;
      this.Toolbar = null;
      this.Bubble = null;
      this.Blocks = null;
      this.Table = null;
      this.Media = null;
      this.Drafts = null;
      this.Converter = null;

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

      this.bindTitleEvents();
      this.bindStats();
      this.bindModals();
      this.bindExportImport();
      this.bindShortcuts();
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

      // Update toggle icon
      const toggleBtn = document.getElementById('btn-theme-toggle');
      if (toggleBtn) {
        toggleBtn.innerHTML = theme === 'dark'
          ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>'
          : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>';
        toggleBtn.setAttribute('title', theme === 'dark' ? 'Светлая тема' : 'Темная тема');
      }

      // Switch Highlight.js theme
      const hljsThemeLink = document.getElementById('hljs-theme');
      if (hljsThemeLink) {
        hljsThemeLink.href = theme === 'dark' ? 'vendor/highlight/github-dark.min.css' : 'vendor/highlight/github.min.css';
      }
    }

    /* ==========================================================================
       Article Title Field
       ========================================================================== */
    bindTitleEvents() {
      if (!this.titleInput) return;

      this.titleInput.addEventListener('input', () => {
        this.adjustTitleHeight();
        this.updateDocumentTitle();
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
       Document Statistics (Words, Chars, Reading Time)
       ========================================================================== */
    bindStats() {
      this.editor.on('text-change', () => {
        this.updateStats();
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
      document.querySelectorAll('.modal-overlay').forEach(modal => {
        modal.addEventListener('click', (e) => {
          if (e.target === modal || e.target.closest('.modal-close-btn') || e.target.closest('[data-modal-close]')) {
            modal.classList.remove('show');
          }
        });
      });

      // Drafts modal button
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
      const exportBtn = document.getElementById('btn-export-modal');
      const exportCodeBox = document.getElementById('export-code-box');
      const exportCopyBtn = document.getElementById('export-copy-btn');
      const exportDownloadBtn = document.getElementById('export-download-btn');

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
      };

      if (exportBtn && exportModal) {
        exportBtn.addEventListener('click', () => {
          updateExportPreview();
          exportModal.classList.add('show');
        });
      }

      // Export format tabs
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
      const importBtn = document.getElementById('btn-import-modal');
      const importTextarea = document.getElementById('import-json-textarea');
      const importSubmitBtn = document.getElementById('import-submit-btn');
      const importFileInput = document.getElementById('import-file-input');

      if (importBtn && importModal) {
        importBtn.addEventListener('click', () => {
          if (importTextarea) importTextarea.value = '';
          importModal.classList.add('show');
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
          document.querySelectorAll('.color-picker-popover.show').forEach(p => p.classList.remove('show'));
        }
      });
    }

    showToast(message, type = 'info', duration = 3000) {
      const container = document.getElementById('toast-container');
      if (!container) return;

      const toast = document.createElement('div');
      toast.className = `toast toast-${type}`;

      let icon = '';
      if (type === 'success') {
        icon = '<span style="color: var(--success-color); font-weight: bold;">✓</span>';
      } else if (type === 'danger') {
        icon = '<span style="color: var(--danger-color); font-weight: bold;">✕</span>';
      } else {
        icon = '<span style="color: var(--accent-color); font-weight: bold;">ℹ</span>';
      }

      toast.innerHTML = `${icon} <span>${this.Converter.escapeHTML(message)}</span>`;
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
