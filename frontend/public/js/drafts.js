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
      this.isDirty = false;
      this.savePromise = null;

      this.statusEl = document.getElementById('save-status');
      this.statusTextEl = document.getElementById('save-status-text');
      this.draftsModal = document.getElementById('drafts-modal');
      this.draftsListEl = document.getElementById('drafts-list');
      this.draftsBadgeEl = document.getElementById('drafts-badge');
      this.newDraftBtn = document.getElementById('btn-new-draft');

      this.initDB().then(async () => {
        this.bindEvents();
        await this.updateBadge();
        await this.autoRestore();
      }).catch(async (err) => {
        console.warn('IndexedDB unavailable, fallback to localStorage:', err);
        this.bindEvents();
        await this.updateBadge();
        await this.autoRestore();
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
      if (this.editor && typeof this.editor.on === 'function') {
        this.editor.on('text-change', (delta, oldDelta, source) => {
          if (source === 'user') {
            this.triggerAutosave();
          }
        });
      }

      // Autosave on Title input change
      if (this.titleInput) {
        this.titleInput.addEventListener('input', () => {
          this.triggerAutosave();
        });
      }

      // New Draft button
      if (this.newDraftBtn) {
        this.newDraftBtn.addEventListener('click', async () => {
          await this.createNewDraft();
        });
      }
    }

    triggerAutosave() {
      this.isDirty = true;
      this.setStatus('unsaved');
      if (this.saveDebounceTimer) {
        clearTimeout(this.saveDebounceTimer);
        this.saveDebounceTimer = null;
      }
      const targetDraftId = this.currentDraftId;
      this.saveDebounceTimer = setTimeout(async () => {
        this.saveDebounceTimer = null;
        if (this.currentDraftId !== targetDraftId) return;
        try {
          await this.saveCurrent({ isAuto: true });
        } catch (e) {
          console.warn('Autosave failed:', e);
        }
      }, this.debounceDelay);
    }

    async flush() {
      const hadPendingTimer = Boolean(this.saveDebounceTimer);
      if (this.saveDebounceTimer) {
        clearTimeout(this.saveDebounceTimer);
        this.saveDebounceTimer = null;
      }

      if (this.savePromise) {
        try {
          await this.savePromise;
        } catch (_) {}
      }

      if (!this.isDirty && !hadPendingTimer) {
        return;
      }

      const title = this.titleInput ? this.titleInput.value.trim() : '';
      const text = this.editor && typeof this.editor.getText === 'function' ? this.editor.getText().trim() : '';

      // Don't save empty blank drafts automatically
      if (!title && !text) {
        this.isDirty = false;
        this.setStatus('saved');
        return;
      }

      try {
        await this.saveCurrent({ isAuto: true });
        this.isDirty = false;
      } catch (err) {
        this.isDirty = true;
        this.setStatus('error');
        throw err;
      }
    }

    setStatus(state) {
      if (!this.statusEl || !this.statusTextEl) return;
      this.statusEl.classList.remove('status-unsaved', 'status-saving', 'status-saved', 'status-error', 'saving');
      switch (state) {
        case 'unsaved':
          this.statusEl.classList.add('status-unsaved');
          this.statusTextEl.textContent = 'Есть изменения';
          break;
        case 'saving':
          this.statusEl.classList.add('status-saving', 'saving');
          this.statusTextEl.textContent = 'Сохранение...';
          break;
        case 'error':
          this.statusEl.classList.add('status-error');
          this.statusTextEl.textContent = 'Ошибка сохранения';
          break;
        case 'saved':
        default:
          this.statusEl.classList.add('status-saved');
          this.statusTextEl.textContent = 'Все изменения сохранены';
          break;
      }
    }

    setSavingStatus(isSaving) {
      this.setStatus(isSaving ? 'saving' : 'saved');
    }

    /* ==========================================================================
       Draft Storage Operations
       ========================================================================== */
    async saveCurrent({ isAuto = false, isManual = false } = {}) {
      if (this.saveDebounceTimer) {
        clearTimeout(this.saveDebounceTimer);
        this.saveDebounceTimer = null;
      }

      if (this.savePromise) {
        try {
          await this.savePromise;
        } catch (_) {}
      }

      this.savePromise = this._doSaveCurrent({ isAuto, isManual });
      try {
        await this.savePromise;
      } finally {
        this.savePromise = null;
      }
    }

    async _doSaveCurrent({ isAuto = false, isManual = false } = {}) {
      const title = this.titleInput ? this.titleInput.value.trim() : '';
      const text = this.editor && typeof this.editor.getText === 'function' ? this.editor.getText().trim() : '';
      const delta = this.editor && typeof this.editor.getContents === 'function' ? this.editor.getContents() : null;
      const html = this.editor && this.editor.root ? this.editor.root.innerHTML : '';

      // Don't save empty blank drafts automatically
      if (!title && !text && isAuto) {
        this.setStatus('saved');
        this.isDirty = false;
        return;
      }

      this.setStatus('saving');

      const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
      const chars = text.length;
      const readingTime = Math.max(1, Math.ceil(words / 200));

      let publicationSettings = null;
      if (window.EditorApp && window.EditorApp.Publication && typeof window.EditorApp.Publication.getSettings === 'function') {
        publicationSettings = window.EditorApp.Publication.getSettings();
      } else if (window.publicationManager && typeof window.publicationManager.getSettings === 'function') {
        publicationSettings = window.publicationManager.getSettings();
      }

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
        publicationSettings: publicationSettings,
        updatedAt: Date.now()
      };

      try {
        if (this.db) {
          await this.putToDB(draft);
        } else {
          this.putToLocalStorage(draft);
        }

        localStorage.setItem('ag_active_draft_id', this.currentDraftId);
        this.setStatus('saved');
        this.isDirty = false;
        await this.updateBadge();

        if (isManual && window.EditorApp && window.EditorApp.showToast) {
          window.EditorApp.showToast('Черновик успешно сохранен!', 'success');
        }
      } catch (err) {
        console.error('Failed to save draft:', err);
        this.setStatus('error');
        this.isDirty = true;

        const isQuota = Boolean(
          err && (
            err.name === 'QuotaExceededError' ||
            err.name === 'NS_ERROR_DOM_QUOTA_REACHED' ||
            err.code === 22 ||
            err.code === 1014 ||
            (typeof err.message === 'string' && (
              err.message.includes('QuotaExceededError') ||
              err.message.includes('quota') ||
              err.message.includes('Quota')
            ))
          )
        );
        const errMsg = isQuota
          ? 'Ошибка: хранилище браузера переполнено'
          : 'Ошибка сохранения черновика';

        if (window.EditorApp && typeof window.EditorApp.showToast === 'function') {
          window.EditorApp.showToast(errMsg, 'error');
        }

        throw err;
      }
    }

    putToDB(draft) {
      return new Promise((resolve, reject) => {
        try {
          const tx = this.db.transaction([STORE_NAME], 'readwrite');
          const store = tx.objectStore(STORE_NAME);
          const req = store.put(draft);
          tx.oncomplete = () => resolve(req.result);
          tx.onerror = () => reject(tx.error || new Error('Transaction failed'));
          tx.onabort = () => reject(tx.error || new Error('Transaction aborted'));
          req.onerror = () => reject(req.error || new Error('Put request failed'));
        } catch (err) {
          reject(err);
        }
      });
    }

    putToLocalStorage(draft) {
      try {
        const drafts = JSON.parse(localStorage.getItem('ag_drafts_fallback') || '{}');
        drafts[draft.id] = draft;
        localStorage.setItem('ag_drafts_fallback', JSON.stringify(drafts));
      } catch (e) {
        console.warn('LocalStorage save failed:', e);
        throw e;
      }
    }

    async getAllDrafts() {
      if (this.db) {
        return new Promise((resolve) => {
          try {
            const tx = this.db.transaction([STORE_NAME], 'readonly');
            const store = tx.objectStore(STORE_NAME);
            const req = store.getAll();
            req.onsuccess = () => {
              const list = req.result || [];
              list.sort((a, b) => b.updatedAt - a.updatedAt);
              resolve(list);
            };
            req.onerror = () => resolve([]);
            tx.onerror = () => resolve([]);
          } catch (_) {
            resolve([]);
          }
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
          try {
            const tx = this.db.transaction([STORE_NAME], 'readonly');
            const store = tx.objectStore(STORE_NAME);
            const req = store.get(activeId);
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => resolve(null);
            tx.onerror = () => resolve(null);
          } catch (_) {
            resolve(null);
          }
        });
      } else {
        const drafts = JSON.parse(localStorage.getItem('ag_drafts_fallback') || '{}');
        draft = drafts[activeId] || null;
      }

      if (draft) {
        await this.loadDraft(draft, false);
      }
    }

    async loadDraft(draft, notify = true) {
      if (!draft || !draft.id) return;

      // Flush any pending changes of the active draft before loading another
      try {
        await this.flush();
      } catch (e) {
        console.warn('Failed to flush active draft before loading another draft:', e);
      }

      if (this.saveDebounceTimer) {
        clearTimeout(this.saveDebounceTimer);
        this.saveDebounceTimer = null;
      }

      this.currentDraftId = draft.id;
      localStorage.setItem('ag_active_draft_id', draft.id);
      this.isDirty = false;

      if (this.titleInput) {
        this.titleInput.value = draft.title === 'Без названия' ? '' : (draft.title || '');
        if (window.EditorApp && window.EditorApp.adjustTitleHeight) {
          window.EditorApp.adjustTitleHeight();
        }
      }

      if (draft.delta && draft.delta.ops && this.editor && typeof this.editor.setContents === 'function') {
        this.editor.setContents(draft.delta);
      } else if (draft.html && this.editor && this.editor.root) {
        this.editor.root.innerHTML = draft.html;
      } else if (this.editor && typeof this.editor.setText === 'function') {
        this.editor.setText('');
      }

      // Restore publication settings or reset if not present (backward compatibility)
      if (draft.publicationSettings) {
        if (window.EditorApp && window.EditorApp.Publication && typeof window.EditorApp.Publication.loadSettings === 'function') {
          window.EditorApp.Publication.loadSettings(draft.publicationSettings);
        } else if (window.publicationManager && typeof window.publicationManager.loadSettings === 'function') {
          window.publicationManager.loadSettings(draft.publicationSettings);
        }
      } else {
        if (window.EditorApp && window.EditorApp.Publication && typeof window.EditorApp.Publication.resetSettings === 'function') {
          window.EditorApp.Publication.resetSettings();
        } else if (window.publicationManager && typeof window.publicationManager.resetSettings === 'function') {
          window.publicationManager.resetSettings();
        }
      }

      this.isDirty = false;
      this.setSavingStatus(false);

      if (notify && window.EditorApp && window.EditorApp.showToast) {
        window.EditorApp.showToast(`Черновик «${draft.title || 'Без названия'}» восстановлен`, 'info');
      }
    }

    async createNewDraft() {
      // Flush any pending changes of the active draft before creating a new one
      try {
        await this.flush();
      } catch (e) {
        console.warn('Failed to flush active draft before creating new draft:', e);
      }

      if (this.saveDebounceTimer) {
        clearTimeout(this.saveDebounceTimer);
        this.saveDebounceTimer = null;
      }

      this.currentDraftId = 'draft_' + Date.now();
      localStorage.setItem('ag_active_draft_id', this.currentDraftId);
      this.isDirty = false;

      if (this.titleInput) {
        this.titleInput.value = '';
        if (window.EditorApp && window.EditorApp.adjustTitleHeight) {
          window.EditorApp.adjustTitleHeight();
        }
      }

      if (this.editor && typeof this.editor.setText === 'function') {
        this.editor.setText('');
      }

      // Reset publication settings for new draft
      if (window.EditorApp && window.EditorApp.Publication && typeof window.EditorApp.Publication.resetSettings === 'function') {
        window.EditorApp.Publication.resetSettings();
      } else if (window.publicationManager && typeof window.publicationManager.resetSettings === 'function') {
        window.publicationManager.resetSettings();
      }

      this.isDirty = false;
      this.setSavingStatus(false);

      if (this.draftsModal) {
        this.draftsModal.classList.remove('show');
      }

      if (window.EditorApp && window.EditorApp.showToast) {
        window.EditorApp.showToast('Создан новый чистый черновик', 'success');
      }
    }

    async deleteDraft(id) {
      if (this.currentDraftId === id) {
        if (this.saveDebounceTimer) {
          clearTimeout(this.saveDebounceTimer);
          this.saveDebounceTimer = null;
        }
        this.isDirty = false;
      }

      if (this.db) {
        await new Promise((resolve) => {
          try {
            const tx = this.db.transaction([STORE_NAME], 'readwrite');
            const store = tx.objectStore(STORE_NAME);
            const req = store.delete(id);
            tx.oncomplete = () => resolve();
            req.onsuccess = () => resolve();
            req.onerror = () => resolve();
            tx.onerror = () => resolve();
          } catch (_) {
            resolve();
          }
        });
      } else {
        const drafts = JSON.parse(localStorage.getItem('ag_drafts_fallback') || '{}');
        delete drafts[id];
        localStorage.setItem('ag_drafts_fallback', JSON.stringify(drafts));
      }

      if (this.currentDraftId === id) {
        await this.createNewDraft();
      }

      await this.updateBadge();
      await this.renderDraftsList();
    }

    async openDraftsModal() {
      await this.flush();
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

        item.querySelector('.btn-load').addEventListener('click', async (e) => {
          e.stopPropagation();
          await this.loadDraft(d, true);
          if (this.draftsModal) this.draftsModal.classList.remove('show');
        });

        item.querySelector('.btn-delete').addEventListener('click', async (e) => {
          e.stopPropagation();
          if (confirm(`Удалить черновик «${d.title}»?`)) {
            await this.deleteDraft(d.id);
          }
        });

        this.draftsListEl.appendChild(item);
      });
    }
  }

  window.DraftsManager = DraftsManager;

})(window);
