/**
 * Antigravity WYSIWYG Editor - Local Drafts & Autosave Manager
 * IndexedDB storage with schema versioning (v2), auto-recovery, drafts badge count,
 * and autosave status indicator. 100% offline-first.
 */

(function (window) {
  'use strict';

  const DB_NAME = 'AntigravityEditorDB';
  const DB_VERSION = 2;
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
      this.draftsBadgeEl = document.getElementById('drafts-badge');
      this.newDraftBtn = document.getElementById('btn-new-draft');

      this.initDB().then(() => {
        this.bindEvents();
        this.updateBadge();
        this.autoRestore();
      }).catch(err => {
        console.warn('IndexedDB unavailable, fallback to localStorage:', err);
        this.bindEvents();
        this.updateBadge();
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

    setSavingStatus(isSaving) {
      if (!this.statusEl || !this.statusTextEl) return;
      if (isSaving) {
        this.statusEl.classList.add('saving');
        this.statusTextEl.textContent = 'Сохранение...';
      } else {
        this.statusEl.classList.remove('saving');
        this.statusTextEl.textContent = 'Все изменения сохранены';
      }
    }

    /* ==========================================================================
       Draft Storage Operations
       ========================================================================== */
    async saveCurrent({ isAuto = false, isManual = false } = {}) {
      const title = this.titleInput ? this.titleInput.value.trim() : '';
      const text = this.editor.getText().trim();
      const delta = this.editor.getContents();
      const html = this.editor.root.innerHTML;

      // Don't save empty blank drafts automatically
      if (!title && !text && isAuto) {
        this.setSavingStatus(false);
        return;
      }

      const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
      const chars = text.length;
      const readingTime = Math.max(1, Math.ceil(words / 200));

      const draft = {
        id: this.currentDraftId,
        schema: 'antigravity-editor-v2',
        title: title || 'Без названия',
        delta: delta,
        html: html,
        textSnippet: text.substring(0, 120),
        wordCount: words,
        charCount: chars,
        readingTime: readingTime,
        updatedAt: Date.now()
      };

      try {
        if (this.db) {
          await this.putToDB(draft);
        } else {
          this.putToLocalStorage(draft);
        }

        localStorage.setItem('ag_active_draft_id', this.currentDraftId);
        this.setSavingStatus(false);
        this.updateBadge();

        if (isManual && window.EditorApp && window.EditorApp.showToast) {
          window.EditorApp.showToast('Черновик успешно сохранен!', 'success');
        }
      } catch (err) {
        console.error('Failed to save draft:', err);
        this.setSavingStatus(false);
      }
    }

    putToDB(draft) {
      return new Promise((resolve, reject) => {
        const tx = this.db.transaction([STORE_NAME], 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const req = store.put(draft);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      });
    }

    putToLocalStorage(draft) {
      try {
        const drafts = JSON.parse(localStorage.getItem('ag_drafts_fallback') || '{}');
        drafts[draft.id] = draft;
        localStorage.setItem('ag_drafts_fallback', JSON.stringify(drafts));
      } catch (e) {
        console.warn('LocalStorage save failed:', e);
      }
    }

    async getAllDrafts() {
      if (this.db) {
        return new Promise((resolve) => {
          const tx = this.db.transaction([STORE_NAME], 'readonly');
          const store = tx.objectStore(STORE_NAME);
          const req = store.getAll();
          req.onsuccess = () => {
            const list = req.result || [];
            list.sort((a, b) => b.updatedAt - a.updatedAt);
            resolve(list);
          };
          req.onerror = () => resolve([]);
        });
      } else {
        const drafts = JSON.parse(localStorage.getItem('ag_drafts_fallback') || '{}');
        const list = Object.values(drafts);
        list.sort((a, b) => b.updatedAt - a.updatedAt);
        return list;
      }
    }

    async updateBadge() {
      if (!this.draftsBadgeEl) return;
      try {
        const drafts = await this.getAllDrafts();
        this.draftsBadgeEl.textContent = drafts.length;
      } catch (e) {
        this.draftsBadgeEl.textContent = '0';
      }
    }

    async autoRestore() {
      const activeId = localStorage.getItem('ag_active_draft_id');
      if (!activeId) return;

      let draft = null;
      if (this.db) {
        draft = await new Promise((resolve) => {
          const tx = this.db.transaction([STORE_NAME], 'readonly');
          const store = tx.objectStore(STORE_NAME);
          const req = store.get(activeId);
          req.onsuccess = () => resolve(req.result);
          req.onerror = () => resolve(null);
        });
      } else {
        const drafts = JSON.parse(localStorage.getItem('ag_drafts_fallback') || '{}');
        draft = drafts[activeId] || null;
      }

      if (draft) {
        this.loadDraft(draft, false);
      }
    }

    loadDraft(draft, notify = true) {
      this.currentDraftId = draft.id;
      localStorage.setItem('ag_active_draft_id', draft.id);

      if (this.titleInput) {
        this.titleInput.value = draft.title === 'Без названия' ? '' : draft.title;
        if (window.EditorApp && window.EditorApp.adjustTitleHeight) {
          window.EditorApp.adjustTitleHeight();
        }
      }

      if (draft.delta && draft.delta.ops) {
        this.editor.setContents(draft.delta);
      } else if (draft.html) {
        this.editor.root.innerHTML = draft.html;
      }

      this.setSavingStatus(false);

      if (notify && window.EditorApp && window.EditorApp.showToast) {
        window.EditorApp.showToast(`Черновик «${draft.title}» восстановлен`, 'info');
      }
    }

    async createNewDraft() {
      this.currentDraftId = 'draft_' + Date.now();
      localStorage.setItem('ag_active_draft_id', this.currentDraftId);

      if (this.titleInput) {
        this.titleInput.value = '';
        if (window.EditorApp && window.EditorApp.adjustTitleHeight) {
          window.EditorApp.adjustTitleHeight();
        }
      }

      this.editor.setText('');
      this.setSavingStatus(false);

      if (this.draftsModal) {
        this.draftsModal.classList.remove('show');
      }

      if (window.EditorApp && window.EditorApp.showToast) {
        window.EditorApp.showToast('Создан новый чистый черновик', 'success');
      }
    }

    async deleteDraft(id) {
      if (this.db) {
        await new Promise((resolve) => {
          const tx = this.db.transaction([STORE_NAME], 'readwrite');
          const store = tx.objectStore(STORE_NAME);
          const req = store.delete(id);
          req.onsuccess = () => resolve();
          req.onerror = () => resolve();
        });
      } else {
        const drafts = JSON.parse(localStorage.getItem('ag_drafts_fallback') || '{}');
        delete drafts[id];
        localStorage.setItem('ag_drafts_fallback', JSON.stringify(drafts));
      }

      if (this.currentDraftId === id) {
        this.createNewDraft();
      }

      this.updateBadge();
      this.renderDraftsList();
    }

    async openDraftsModal() {
      await this.renderDraftsList();
      if (this.draftsModal) {
        this.draftsModal.classList.add('show');
      }
    }

    async renderDraftsList() {
      if (!this.draftsListEl) return;
      this.draftsListEl.innerHTML = '<div style="padding: 12px; text-align: center; color: var(--text-muted);">Загрузка...</div>';

      const drafts = await this.getAllDrafts();

      if (drafts.length === 0) {
        this.draftsListEl.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-muted);">Сохраненных черновиков пока нет</div>';
        return;
      }

      this.draftsListEl.innerHTML = '';
      drafts.forEach(d => {
        const item = document.createElement('div');
        item.className = `draft-item ${d.id === this.currentDraftId ? 'active' : ''}`;

        const dateStr = new Date(d.updatedAt).toLocaleString('ru-RU', {
          day: 'numeric',
          month: 'short',
          hour: '2-digit',
          minute: '2-digit'
        });

        item.innerHTML = `
          <div style="flex: 1; overflow: hidden; padding-right: 12px;">
            <div style="font-weight: 600; font-size: 0.95rem; margin-bottom: 3px; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
              ${d.title || 'Без названия'}
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted); display: flex; align-items: center; gap: 12px;">
              <span style="display:inline-flex; align-items:center; gap:4px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg> ${dateStr}</span>
              <span style="display:inline-flex; align-items:center; gap:4px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg> ${d.wordCount || 0} сл.</span>
              <span style="display:inline-flex; align-items:center; gap:4px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg> ${d.readingTime || 1} мин</span>
            </div>
          </div>
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-sm btn-load" title="Восстановить">Открыть</button>
            <button class="btn btn-sm btn-delete text-danger" title="Удалить"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button>
          </div>
        `;

        item.querySelector('.btn-load').addEventListener('click', (e) => {
          e.stopPropagation();
          this.loadDraft(d, true);
          if (this.draftsModal) this.draftsModal.classList.remove('show');
        });

        item.querySelector('.btn-delete').addEventListener('click', (e) => {
          e.stopPropagation();
          if (confirm(`Удалить черновик «${d.title}»?`)) {
            this.deleteDraft(d.id);
          }
        });

        this.draftsListEl.appendChild(item);
      });
    }
  }

  window.DraftsManager = DraftsManager;

})(window);
