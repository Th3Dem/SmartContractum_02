/**
 * Antigravity WYSIWYG Editor - Local Drafts & Autosave Manager
 * Robust IndexedDB storage, auto-recovery, and status indicator
 */

(function (window) {
  'use strict';

  const DB_NAME = 'AntigravityEditorDB';
  const DB_VERSION = 1;
  const STORE_NAME = 'drafts';

  class DraftsManager {
    constructor(editor, titleInput) {
      this.editor = editor;
      this.titleInput = titleInput;

      this.db = null;
      this.currentDraftId = localStorage.getItem('ag_active_draft_id') || ('draft_' + Date.now());
      this.saveDebounceTimer = null;
      this.debounceDelay = 2000; // 2 seconds

      this.statusEl = document.getElementById('save-status');
      this.statusTextEl = document.getElementById('save-status-text');
      this.draftsModal = document.getElementById('drafts-modal');
      this.draftsListEl = document.getElementById('drafts-list');
      this.newDraftBtn = document.getElementById('btn-new-draft');

      this.initDB().then(() => {
        this.bindEvents();
        this.autoRestore();
      }).catch(err => {
        console.warn('IndexedDB unavailable, fallback to localStorage:', err);
        this.bindEvents();
        this.autoRestore();
      });
    }

    /* ==========================================================================
       IndexedDB Initialization
       ========================================================================== */
    initDB() {
      return new Promise((resolve, reject) => {
        if (!window.indexedDB) {
          reject(new Error('IndexedDB not supported'));
          return;
        }

        const request = window.indexedDB.open(DB_NAME, DB_VERSION);

        request.onupgradeneeded = (e) => {
          const db = e.target.result;
          if (!db.objectStoreNames.contains(STORE_NAME)) {
            const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
            store.createIndex('updatedAt', 'updatedAt', { unique: false });
          }
        };

        request.onsuccess = (e) => {
          this.db = e.target.result;
          resolve(this.db);
        };

        request.onerror = (e) => {
          reject(e.target.error);
        };
      });
    }

    bindEvents() {
      // Autosave on Quill text-change
      this.editor.on('text-change', (delta, oldDelta, source) => {
        if (source === 'user') {
          this.triggerAutosave();
        }
      });

      // Autosave on Title input change
      if (this.titleInput) {
        this.titleInput.addEventListener('input', () => {
          this.triggerAutosave();
        });
      }

      // New Draft button
      if (this.newDraftBtn) {
        this.newDraftBtn.addEventListener('click', () => {
          this.createNewDraft();
        });
      }
    }

    triggerAutosave() {
      this.setSavingStatus(true);
      if (this.saveDebounceTimer) {
        clearTimeout(this.saveDebounceTimer);
      }
      this.saveDebounceTimer = setTimeout(() => {
        this.saveCurrent({ isAuto: true });
      }, this.debounceDelay);
    }

    setSavingStatus(isSaving, customText) {
      if (!this.statusEl) return;

      if (isSaving) {
        this.statusEl.classList.add('saving');
        if (this.statusTextEl) this.statusTextEl.textContent = 'Сохранение...';
      } else {
        this.statusEl.classList.remove('saving');
        if (this.statusTextEl) {
          const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
          this.statusTextEl.textContent = customText || `Сохранено в ${time}`;
        }
      }
    }

    /* ==========================================================================
       Save / Load / Delete Operations
       ========================================================================== */
    saveCurrent(options = {}) {
      const title = this.titleInput ? this.titleInput.value.trim() : '';
      const delta = this.editor.getContents();
      const html = this.editor.root.innerHTML;
      const text = this.editor.getText().trim();

      // Count words & chars
      const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
      const chars = text.length;
      const readingTime = Math.max(1, Math.ceil(words / 200));

      const draft = {
        id: this.currentDraftId,
        title: title || 'Без названия',
        delta: delta,
        html: html,
        textSnippet: text.substring(0, 160),
        wordCount: words,
        charCount: chars,
        readingTime: readingTime,
        updatedAt: Date.now()
      };

      return new Promise((resolve) => {
        if (this.db) {
          const tx = this.db.transaction(STORE_NAME, 'readwrite');
          const store = tx.objectStore(STORE_NAME);
          store.put(draft);
          tx.oncomplete = () => {
            localStorage.setItem('ag_active_draft_id', this.currentDraftId);
            this.setSavingStatus(false);
            if (options.isManual && window.EditorApp && window.EditorApp.showToast) {
              window.EditorApp.showToast('Черновик успешно сохранен!', 'success');
            }
            resolve(draft);
          };
          tx.onerror = () => {
            this.fallbackSave(draft);
            this.setSavingStatus(false);
            resolve(draft);
          };
        } else {
          this.fallbackSave(draft);
          this.setSavingStatus(false);
          resolve(draft);
        }
      });
    }

    fallbackSave(draft) {
      try {
        localStorage.setItem('ag_active_draft_id', draft.id);
        const drafts = JSON.parse(localStorage.getItem('ag_drafts_fallback') || '{}');
        drafts[draft.id] = draft;
        localStorage.setItem('ag_drafts_fallback', JSON.stringify(drafts));
      } catch (e) {
        console.error('LocalStorage save error:', e);
      }
    }

    getAllDrafts() {
      return new Promise((resolve) => {
        if (this.db) {
          const tx = this.db.transaction(STORE_NAME, 'readonly');
          const store = tx.objectStore(STORE_NAME);
          const req = store.getAll();
          req.onsuccess = () => {
            const list = req.result || [];
            list.sort((a, b) => b.updatedAt - a.updatedAt);
            resolve(list);
          };
          req.onerror = () => {
            resolve(this.fallbackGetAll());
          };
        } else {
          resolve(this.fallbackGetAll());
        }
      });
    }

    fallbackGetAll() {
      try {
        const drafts = JSON.parse(localStorage.getItem('ag_drafts_fallback') || '{}');
        const list = Object.values(drafts);
        list.sort((a, b) => b.updatedAt - a.updatedAt);
        return list;
      } catch (e) {
        return [];
      }
    }

    restoreDraft(id) {
      return new Promise((resolve) => {
        if (this.db) {
          const tx = this.db.transaction(STORE_NAME, 'readonly');
          const store = tx.objectStore(STORE_NAME);
          const req = store.get(id);
          req.onsuccess = () => {
            const draft = req.result;
            if (draft) {
              this.applyDraft(draft);
            }
            resolve(draft);
          };
          req.onerror = () => {
            resolve(null);
          };
        } else {
          const drafts = this.fallbackGetAll();
          const draft = drafts.find(d => d.id === id);
          if (draft) {
            this.applyDraft(draft);
          }
          resolve(draft);
        }
      });
    }

    applyDraft(draft) {
      this.currentDraftId = draft.id;
      localStorage.setItem('ag_active_draft_id', draft.id);

      if (this.titleInput) {
        this.titleInput.value = draft.title === 'Без названия' ? '' : draft.title;
        if (window.EditorApp && window.EditorApp.adjustTitleHeight) {
          window.EditorApp.adjustTitleHeight();
        }
      }

      if (draft.delta) {
        this.editor.setContents(draft.delta, 'silent');
      } else if (draft.html) {
        this.editor.root.innerHTML = draft.html;
      }

      this.setSavingStatus(false, 'Черновик восстановлен');
      if (window.EditorApp && window.EditorApp.updateStats) {
        window.EditorApp.updateStats();
      }
    }

    deleteDraft(id) {
      return new Promise((resolve) => {
        if (this.db) {
          const tx = this.db.transaction(STORE_NAME, 'readwrite');
          const store = tx.objectStore(STORE_NAME);
          store.delete(id);
          tx.oncomplete = () => {
            if (this.currentDraftId === id) {
              this.createNewDraft();
            }
            resolve(true);
          };
        } else {
          try {
            const drafts = JSON.parse(localStorage.getItem('ag_drafts_fallback') || '{}');
            delete drafts[id];
            localStorage.setItem('ag_drafts_fallback', JSON.stringify(drafts));
            if (this.currentDraftId === id) {
              this.createNewDraft();
            }
          } catch (e) {}
          resolve(true);
        }
      });
    }

    createNewDraft() {
      this.currentDraftId = 'draft_' + Date.now();
      localStorage.setItem('ag_active_draft_id', this.currentDraftId);

      if (this.titleInput) {
        this.titleInput.value = '';
        if (window.EditorApp && window.EditorApp.adjustTitleHeight) {
          window.EditorApp.adjustTitleHeight();
        }
      }

      this.editor.setContents([], 'user');
      this.setSavingStatus(false, 'Новый черновик');
      this.closeDraftsModal();
      this.editor.focus();

      if (window.EditorApp && window.EditorApp.showToast) {
        window.EditorApp.showToast('Создан новый черновик', 'success');
      }
    }

    autoRestore() {
      this.getAllDrafts().then((drafts) => {
        if (drafts.length > 0) {
          const active = drafts.find(d => d.id === this.currentDraftId) || drafts[0];
          if (active) {
            this.applyDraft(active);
          }
        }
      });
    }

    /* ==========================================================================
       Drafts Modal UI
       ========================================================================== */
    openDraftsModal() {
      this.renderDraftsList();
      if (this.draftsModal) {
        this.draftsModal.classList.add('show');
      }
    }

    closeDraftsModal() {
      if (this.draftsModal) {
        this.draftsModal.classList.remove('show');
      }
    }

    renderDraftsList() {
      if (!this.draftsListEl) return;
      this.draftsListEl.innerHTML = '<div style="padding: 16px; text-align: center; color: var(--text-muted);">Загрузка черновиков...</div>';

      this.getAllDrafts().then((drafts) => {
        if (drafts.length === 0) {
          this.draftsListEl.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-muted);">Нет сохраненных черновиков</div>';
          return;
        }

        this.draftsListEl.innerHTML = '';
        drafts.forEach((draft) => {
          const card = document.createElement('div');
          card.className = 'draft-card';
          if (draft.id === this.currentDraftId) {
            card.style.borderColor = 'var(--accent-color)';
            card.style.backgroundColor = 'var(--accent-subtle)';
          }

          const dateStr = new Date(draft.updatedAt).toLocaleString([], {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit'
          });

          card.innerHTML = `
            <div class="draft-info">
              <div class="draft-title">${this.escapeHTML(draft.title || 'Без названия')} ${draft.id === this.currentDraftId ? '<span class="badge">Текущий</span>' : ''}</div>
              <div class="draft-meta">${dateStr} • ${draft.wordCount || 0} слов • ${draft.readingTime || 1} мин чтения</div>
            </div>
            <div style="display: flex; gap: 8px;">
              <button class="btn btn-sm" data-action="restore" data-id="${draft.id}">Открыть</button>
              <button class="btn btn-sm btn-icon" data-action="delete" data-id="${draft.id}" title="Удалить" style="color: var(--danger-color);">✕</button>
            </div>
          `;

          card.querySelector('[data-action="restore"]').addEventListener('click', () => {
            this.restoreDraft(draft.id).then(() => {
              this.closeDraftsModal();
              if (window.EditorApp && window.EditorApp.showToast) {
                window.EditorApp.showToast('Черновик открыт', 'success');
              }
            });
          });

          card.querySelector('[data-action="delete"]').addEventListener('click', (e) => {
            e.stopPropagation();
            if (confirm(`Удалить черновик "${draft.title}"?`)) {
              this.deleteDraft(draft.id).then(() => {
                this.renderDraftsList();
              });
            }
          });

          this.draftsListEl.appendChild(card);
        });
      });
    }

    escapeHTML(str) {
      return (str || '').replace(/[&<>"']/g, (m) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[m]));
    }
  }

  window.DraftsManager = DraftsManager;

})(window);
