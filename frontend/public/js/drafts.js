/**
 * Antigravity WYSIWYG Editor - Local Drafts & Autosave Manager
 * IndexedDB storage with schema versioning (v2), auto-recovery, drafts badge count,
 * and autosave status indicator. 100% offline-first.
 * Supports materialType: 'publication' (default) and 'question' with strict isolation.
 */

(function (window) {
  'use strict';

  const DB_NAME = 'AntigravityEditorDB';
  const DB_VERSION = 2;
  const STORE_NAME = 'drafts';

  class DraftsManager {
    constructor(editor, titleInput, options = {}) {
      if (typeof titleInput === 'string') {
        this.titleInput = document.querySelector(titleInput) || document.getElementById(titleInput);
      } else {
        this.titleInput = titleInput || document.getElementById('questionTitleInput') || document.getElementById('question-title') || document.getElementById('article-title');
      }
      this.editor = editor;
      this.options = options || {};

      this.materialType = this.options.materialType || 'publication';
      this.baseActiveDraftKey = this.options.activeDraftKey || (this.materialType === 'question' ? 'ag_active_question_draft_id' : 'ag_active_draft_id');
      this.userId = window.SCAuth && window.SCAuth.currentUser ? window.SCAuth.currentUser.id : null;
      this.activeDraftKey = this.userId ? `${this.baseActiveDraftKey}_${this.userId}` : this.baseActiveDraftKey;
      this.tagsGetter = this.options.tagsGetter || this.options.getTags || null;
      this.tagsSetter = this.options.tagsSetter || this.options.setTags || null;
      this.onDraftLoaded = this.options.onDraftLoaded || null;
      this.onDraftReset = this.options.onDraftReset || null;
      this.onDraftSaved = this.options.onDraftSaved || null;
      this.debounceDelay = typeof this.options.debounceDelay === 'number' ? this.options.debounceDelay : 2000;

      this.db = null;
      this.currentDraftId = localStorage.getItem(this.activeDraftKey) || ((this.materialType === 'question' ? 'draft_q_' : 'draft_') + Date.now());
      this.currentRevision = 1;
      this.lastSavedFingerprint = null;
      this.currentDraft = null;
      this.saveDebounceTimer = null;
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

      // Drafts modal button in document bar / header
      const draftsBtn = document.getElementById('btn-drafts-modal');
      if (draftsBtn) {
        draftsBtn.addEventListener('click', async () => {
          await this.openDraftsModal();
        });
      }

      // Drafts modal close buttons and backdrop
      if (this.draftsModal) {
        this.draftsModal.querySelectorAll('[data-modal-close], #btn-close-drafts, .modal-close-btn').forEach(btn => {
          btn.addEventListener('click', () => {
            this.draftsModal.classList.remove('show');
          });
        });
        this.draftsModal.addEventListener('click', (e) => {
          if (e.target === this.draftsModal) {
            this.draftsModal.classList.remove('show');
          }
        });
      }

      window.addEventListener('auth:change', async (e) => {
        const { authenticated, user } = e.detail;
        if (!authenticated) {
          if (this.saveDebounceTimer) clearTimeout(this.saveDebounceTimer);
          this.userId = null;
          this.activeDraftKey = this.baseActiveDraftKey;
          this.currentDraftId = 'draft_' + Date.now();
          this.currentDraft = null;
          await this.createNewDraft();
        } else if (user) {
          this.userId = user.id;
          this.activeDraftKey = `${this.baseActiveDraftKey}_${this.userId}`;
          await this.importGuestDrafts(user.id);
          await this.autoRestore();
          await this.updateBadge();
        }
      });
    }

    async importGuestDrafts(userId) {
      const guestKey = this.baseActiveDraftKey;
      let guestDrafts = [];
      if (this.db) {
        guestDrafts = await new Promise((resolve) => {
          const tx = this.db.transaction([STORE_NAME], 'readonly');
          const store = tx.objectStore(STORE_NAME);
          const req = store.getAll();
          req.onsuccess = () => resolve((req.result || []).filter(d => !d.userId));
          req.onerror = () => resolve([]);
        });
      } else {
        const drafts = JSON.parse(localStorage.getItem('ag_drafts_fallback') || '{}');
        guestDrafts = Object.values(drafts).filter(d => !d.userId);
      }
      
      if (guestDrafts.length > 0) {
        const doImport = confirm('У вас есть локальные черновики. Хотите импортировать их в свой аккаунт?');
        if (doImport) {
          for (const d of guestDrafts) {
            d.userId = userId;
            d.id = d.id + '_' + userId;
            if (this.db) {
              await this.putToDB(d);
            } else {
              this.putToLocalStorage(d);
            }
          }
        }
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
      const tags = (this.tagsGetter && typeof this.tagsGetter === 'function') ? (this.tagsGetter() || []) : [];

      // Don't save empty blank drafts automatically
      if (!title && !text && tags.length === 0) {
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

    // Status text and tooltip change together: on phones the text is visually hidden
    // and the tooltip explains the colored dot (Issue #244)
    setStatusText(text) {
      if (this.statusTextEl) this.statusTextEl.textContent = text;
      if (this.statusEl) this.statusEl.title = text;
    }

    // Final state of a save attempt: drop the "saving" classes so the dot stops pulsing
    finishStatus(stateClass, text) {
      if (!this.statusEl) return;
      this.statusEl.classList.remove('status-unsaved', 'status-saving', 'status-saved', 'status-error', 'saving');
      this.statusEl.classList.add(stateClass);
      this.setStatusText(text);
    }

    setStatus(state) {
      if (!this.statusEl) {
        this.statusEl = document.getElementById('save-status');
      }
      if (!this.statusTextEl) {
        this.statusTextEl = document.getElementById('save-status-text');
      }
      if (!this.statusEl || !this.statusTextEl) return;
      this.statusEl.classList.remove('status-unsaved', 'status-saving', 'status-saved', 'status-error', 'saving');
      switch (state) {
        case 'unsaved':
          this.statusEl.classList.add('status-unsaved');
          this.setStatusText('Есть изменения');
          break;
        case 'saving':
          this.statusEl.classList.add('status-saving', 'saving');
          this.setStatusText('Сохранение...');
          break;
        case 'error':
          this.statusEl.classList.add('status-error');
          this.setStatusText('Ошибка сохранения');
          break;
        case 'saved':
        default:
          this.statusEl.classList.add('status-saved');
          this.setStatusText('Все изменения сохранены');
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
      const tags = (this.tagsGetter && typeof this.tagsGetter === 'function')
        ? (this.tagsGetter() || [])
        : ((this.currentDraft && this.currentDraft.tags) || []);

      // Don't save empty blank drafts automatically
      if (!title && !text && tags.length === 0 && isAuto) {
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

      const currentFingerprint = this._computeFingerprint(title, delta, html, publicationSettings, tags);

      let newRevision = this.currentRevision || 1;
      if (this.lastSavedFingerprint === null) {
        newRevision = (typeof this.currentRevision === 'number' && this.currentRevision > 0) ? this.currentRevision : 1;
      } else if (this.lastSavedFingerprint !== currentFingerprint || this.isDirty) {
        newRevision = (this.currentRevision || 1) + 1;
      }

      const snippet = text.substring(0, 150) || title;
      const draft = {
        id: this.currentDraftId,
        materialType: this.materialType,
        schema: 'antigravity-editor-v2',
        title: title || 'Без названия',
        tags: tags,
        revision: newRevision,
        delta: delta,
        html: html,
        snippet: snippet,
        textSnippet: snippet,
        wordCount: words,
        charCount: chars,
        readingTime: readingTime,
        publicationSettings: publicationSettings || (this.materialType === 'question' ? {
          materialType: 'question',
          type: 'question',
          keywords: tags,
          targetAudience: 'developers',
          topics: ['smart-contracts-development'],
          description: snippet
        } : null),
        updatedAt: Date.now(),
        userId: this.userId || null
      };

      try {
        if (this.db) {
          await this.putToDB(draft);
        } else {
          this.putToLocalStorage(draft);
        }

        let syncConflict = false;
        if (this.userId && navigator.onLine) {
          try {
            const method = this.currentRevision > 1 ? 'PUT' : 'POST';
            const url = this.currentRevision > 1 ? `/api/drafts/${this.currentDraftId}` : '/api/drafts';
            const res = await fetch(url, {
              method,
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                id: this.currentDraftId,
                materialType: this.materialType,
                title: title,
                content: text,
                revision: this.currentRevision,
                publicationSettings: draft.publicationSettings
              })
            });
            if (res.ok) {
              const data = await res.json();
              if (data.draft && data.draft.revision) {
                newRevision = data.draft.revision;
                draft.revision = newRevision;
              }
              this.finishStatus('status-saved', 'Сохранено в аккаунте');
            } else if (res.status === 409) {
              syncConflict = true;
              this.finishStatus('status-error', 'Конфликт синхронизации');
              const saveCopy = confirm('Конфликт синхронизации. Сохранить как копию?');
              if (saveCopy) {
                this.currentDraftId = 'draft_' + Date.now();
                draft.id = this.currentDraftId;
                draft.revision = 1;
                if (this.db) await this.putToDB(draft);
                else this.putToLocalStorage(draft);
              }
            } else {
              this.finishStatus('status-saved', 'Сохранено на устройстве');
            }
          } catch (e) {
            this.finishStatus('status-saved', 'Сохранено на устройстве');
          }
        } else {
          // Guest or offline: the draft is saved locally, there is nothing to sync
          this.finishStatus('status-saved', 'Сохранено на устройстве');
        }

        this.currentRevision = newRevision;
        this.lastSavedFingerprint = currentFingerprint;
        this.currentDraft = draft;
        localStorage.setItem(this.activeDraftKey, this.currentDraftId);
        if (!syncConflict) {
          this.isDirty = false;
        }
        await this.updateBadge();

        if (this.onDraftSaved && typeof this.onDraftSaved === 'function') {
          this.onDraftSaved(draft);
        }

        if (isManual) {
          const toastFn = (this.options && this.options.showToast) ||
                          (window.QuestionEditor && window.QuestionEditor.showToast) ||
                          (window.EditorApp && window.EditorApp.showToast) ||
                          (typeof window.showToast === 'function' ? window.showToast : null);
          if (toastFn) {
            const toastMsg = this.materialType === 'question' ? 'Вопрос успешно сохранен!' : 'Черновик успешно сохранен!';
            toastFn(toastMsg, 'success');
          }
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
        } else if (window.QuestionEditor && typeof window.QuestionEditor.showToast === 'function') {
          window.QuestionEditor.showToast(errMsg, 'danger');
        } else if (this.options && typeof this.options.showToast === 'function') {
          this.options.showToast(errMsg, 'danger');
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
      let list = [];
      if (this.db) {
        list = await new Promise((resolve) => {
          try {
            const tx = this.db.transaction([STORE_NAME], 'readonly');
            const store = tx.objectStore(STORE_NAME);
            const req = store.getAll();
            req.onsuccess = () => {
              resolve(req.result || []);
            };
            req.onerror = () => resolve([]);
            tx.onerror = () => resolve([]);
          } catch (_) {
            resolve([]);
          }
        });
      } else {
        const drafts = JSON.parse(localStorage.getItem('ag_drafts_fallback') || '{}');
        list = Object.values(drafts);
      }

      if (this.materialType === 'question') {
        list = list.filter(d => {
          if (!d) return false;
          if (d.materialType === 'question') return true;
          if (d.publicationSettings && (d.publicationSettings.materialType === 'question' || d.publicationSettings.type === 'question')) return true;
          if (typeof d.id === 'string' && d.id.startsWith('draft_q_')) return true;
          return false;
        });
      } else {
        list = list.filter(d => {
          if (!d) return false;
          if (d.materialType === 'question') return false;
          if (d.publicationSettings && (d.publicationSettings.materialType === 'question' || d.publicationSettings.type === 'question')) return false;
          if (typeof d.id === 'string' && d.id.startsWith('draft_q_')) return false;
          return true;
        });
      }

      list = list.filter(d => (d.userId || null) === this.userId);
      
      if (this.userId && navigator.onLine) {
        try {
          const res = await fetch(`/api/drafts?material_type=${this.materialType}`);
          if (res.ok) {
            const data = await res.json();
            if (data.drafts) {
              const serverDrafts = data.drafts;
              serverDrafts.forEach(sd => {
                const existing = list.find(ld => ld.id === sd.id);
                if (!existing || sd.revision > existing.revision) {
                  const merged = { ...existing, ...sd, userId: this.userId };
                  if (!existing) list.push(merged);
                  else Object.assign(existing, merged);
                  if (this.db) this.putToDB(merged);
                  else this.putToLocalStorage(merged);
                }
              });
            }
          }
        } catch (e) {}
      }
      
      list.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
      return list;
    }

    async getDraftsList() {
      return this.getAllDrafts();
    }

    async updateBadge() {
      if (!this.draftsBadgeEl) {
        this.draftsBadgeEl = document.getElementById('drafts-badge');
      }
      if (!this.draftsBadgeEl) return;
      try {
        const drafts = await this.getAllDrafts();
        this.draftsBadgeEl.textContent = String(drafts.length);
      } catch (e) {
        this.draftsBadgeEl.textContent = '0';
      }
    }

    async migrateLegacyQuestionDraft() {
      try {
        const legacyStr = localStorage.getItem('smartcontractum_question_draft');
        if (!legacyStr) return;

        const legacy = JSON.parse(legacyStr);
        if (legacy && typeof legacy === 'object') {
          const title = (legacy.title || '').trim();
          const tags = Array.isArray(legacy.tags) ? legacy.tags : [];
          const html = legacy.html || '';
          const text = html.replace(/<[^>]*>/g, '').trim();

          if (title || text || tags.length > 0) {
            const migrationId = 'draft_q_migrated_' + Date.now();
            const snippet = text.substring(0, 150) || title;
            const draft = {
              id: migrationId,
              materialType: 'question',
              schema: 'antigravity-editor-v2',
              title: title || 'Без названия',
              tags: tags,
              revision: 1,
              delta: legacy.delta || null,
              html: html,
              snippet: snippet,
              textSnippet: snippet,
              wordCount: text ? text.split(/\s+/).filter(Boolean).length : 0,
              charCount: text.length,
              readingTime: 1,
              publicationSettings: {
                materialType: 'question',
                type: 'question',
                keywords: tags,
                targetAudience: 'developers',
                topics: ['smart-contracts-development'],
                description: snippet
              },
              updatedAt: Date.now()
            };

            if (this.db) {
              await this.putToDB(draft);
            } else {
              this.putToLocalStorage(draft);
            }

            this.currentDraftId = migrationId;
            localStorage.setItem(this.activeDraftKey, migrationId);
          }
        }
      } catch (err) {
        console.warn('Migration of legacy question draft failed:', err);
      } finally {
        try {
          localStorage.removeItem('smartcontractum_question_draft');
        } catch (_) {}
      }
    }

    async restoreQuestionDraft() {
      await this.migrateLegacyQuestionDraft();

      const activeId = localStorage.getItem(this.activeDraftKey);
      let draft = null;

      if (activeId) {
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
      }

      const isQuestion = draft && (
        draft.materialType === 'question' ||
        (draft.publicationSettings && (draft.publicationSettings.materialType === 'question' || draft.publicationSettings.type === 'question')) ||
        (typeof draft.id === 'string' && draft.id.startsWith('draft_q_'))
      );

      if (draft && isQuestion) {
        await this.loadDraft(draft, false);
      } else {
        const questionDrafts = await this.getAllDrafts();
        if (questionDrafts.length > 0) {
          await this.loadDraft(questionDrafts[0], false);
        } else {
          await this.createNewDraft();
        }
      }
    }

    async autoRestore() {
      if (this.materialType === 'question') {
        await this.restoreQuestionDraft();
        return;
      }

      let requestedType = null;
      try {
        if (typeof window !== 'undefined' && window.location && window.location.search) {
          const urlParams = new URLSearchParams(window.location.search);
          requestedType = urlParams.get('type');
        }
      } catch (_) {}

      const activeId = localStorage.getItem('ag_active_draft_id');
      if (!activeId) {
        if (requestedType === 'question') {
          const pub = (window.EditorApp && window.EditorApp.Publication) || window.publicationManager;
          if (pub && typeof pub.setMaterialType === 'function') {
            pub.setMaterialType('question');
          }
        }
        return;
      }

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

      if (requestedType === 'question') {
        const activeMaterialType = draft && draft.publicationSettings
          ? (draft.publicationSettings.materialType || draft.publicationSettings.type)
          : null;

        if (draft && activeMaterialType === 'question') {
          await this.loadDraft(draft, false);
          const pub = (window.EditorApp && window.EditorApp.Publication) || window.publicationManager;
          if (pub && typeof pub.setMaterialType === 'function') {
            pub.setMaterialType('question');
          }
        } else {
          // If active draft is not a question (e.g. article) or draft does not exist:
          // Do NOT restore it. Initialize fresh clean question draft.
          await this.createNewDraft();
          const pub = (window.EditorApp && window.EditorApp.Publication) || window.publicationManager;
          if (pub && typeof pub.setMaterialType === 'function') {
            pub.setMaterialType('question');
          }
        }
        return;
      }

      if (draft) {
        const isQuestion = (draft.materialType === 'question') ||
          (draft.publicationSettings && (draft.publicationSettings.materialType === 'question' || draft.publicationSettings.type === 'question'));
        if (isQuestion) {
          await this.createNewDraft();
        } else {
          await this.loadDraft(draft, false);
        }
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
      localStorage.setItem(this.activeDraftKey, draft.id);
      this.currentRevision = (draft && typeof draft.revision === 'number' && draft.revision > 0) ? draft.revision : 1;
      this.currentDraft = draft;

      const tags = Array.isArray(draft.tags)
        ? draft.tags
        : (draft.publicationSettings && Array.isArray(draft.publicationSettings.keywords) ? draft.publicationSettings.keywords : []);

      this.lastSavedFingerprint = this._computeFingerprint(
        draft.title === 'Без названия' ? '' : (draft.title || ''),
        draft.delta,
        draft.html,
        draft.publicationSettings,
        tags
      );
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

      if (this.tagsSetter && typeof this.tagsSetter === 'function') {
        this.tagsSetter(tags);
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

      if (this.onDraftLoaded && typeof this.onDraftLoaded === 'function') {
        this.onDraftLoaded(draft);
      }

      this.isDirty = false;
      this.setSavingStatus(false);

      if (notify) {
        const toastFn = (this.options && this.options.showToast) ||
                        (window.QuestionEditor && window.QuestionEditor.showToast) ||
                        (window.EditorApp && window.EditorApp.showToast) ||
                        (typeof window.showToast === 'function' ? window.showToast : null);
        if (toastFn) {
          toastFn(`Черновик «${draft.title || 'Без названия'}» восстановлен`, 'info');
        }
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

      this.currentDraftId = (this.materialType === 'question' ? 'draft_q_' : 'draft_') + Date.now();
      localStorage.setItem(this.activeDraftKey, this.currentDraftId);
      this.currentRevision = 1;
      this.lastSavedFingerprint = null;
      this.currentDraft = null;
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

      if (this.tagsSetter && typeof this.tagsSetter === 'function') {
        this.tagsSetter([]);
      }

      // Reset publication settings for new draft
      if (window.EditorApp && window.EditorApp.Publication && typeof window.EditorApp.Publication.resetSettings === 'function') {
        window.EditorApp.Publication.resetSettings();
      } else if (window.publicationManager && typeof window.publicationManager.resetSettings === 'function') {
        window.publicationManager.resetSettings();
      }

      if (this.onDraftReset && typeof this.onDraftReset === 'function') {
        this.onDraftReset();
      }

      this.isDirty = false;
      this.setSavingStatus(false);

      if (this.draftsModal) {
        this.draftsModal.classList.remove('show');
      }

      await this.updateBadge();

      const toastFn = (this.options && this.options.showToast) ||
                      (window.QuestionEditor && window.QuestionEditor.showToast) ||
                      (window.EditorApp && window.EditorApp.showToast) ||
                      (typeof window.showToast === 'function' ? window.showToast : null);
      if (toastFn) {
        toastFn(this.materialType === 'question' ? 'Создан новый вопрос' : 'Создан новый чистый черновик', 'success');
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

      if (this.userId && navigator.onLine) {
        try {
          await fetch(`/api/drafts/${id}`, { method: 'DELETE' });
        } catch (e) {}
      }

      if (this.currentDraftId === id) {
        const remaining = await this.getAllDrafts();
        if (remaining.length > 0) {
          await this.loadDraft(remaining[0], false);
        } else {
          await this.createNewDraft();
        }
      }

      await this.updateBadge();
      await this.renderDraftsList();
    }

    async clearActiveDraft() {
      return this.deleteCurrentDraft();
    }

    async deleteCurrentDraft() {
      const draftIdToDelete = this.currentDraftId;
      if (this.saveDebounceTimer) {
        clearTimeout(this.saveDebounceTimer);
        this.saveDebounceTimer = null;
      }
      this.isDirty = false;

      if (this.db) {
        await new Promise((resolve) => {
          try {
            const tx = this.db.transaction([STORE_NAME], 'readwrite');
            const store = tx.objectStore(STORE_NAME);
            const req = store.delete(draftIdToDelete);
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
        delete drafts[draftIdToDelete];
        localStorage.setItem('ag_drafts_fallback', JSON.stringify(drafts));
      }

      await this.createNewDraft();
      await this.updateBadge();
    }

    async openDraftsModal() {
      await this.flush();
      await this.renderDraftsList();
      if (!this.draftsModal) {
        this.draftsModal = document.getElementById('drafts-modal');
      }
      if (this.draftsModal) {
        this.draftsModal.classList.add('show');
      }
    }

    async renderDraftsList() {
      if (!this.draftsListEl) {
        this.draftsListEl = document.getElementById('drafts-list');
      }
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

        const snippetText = d.snippet || d.textSnippet || '';
        const snippetHtml = snippetText
          ? `<div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${snippetText}</div>`
          : '';

        const tagsHtml = (Array.isArray(d.tags) && d.tags.length > 0)
          ? `<div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px;">` +
            d.tags.map(t => `<span style="display: inline-block; font-size: 0.75rem; padding: 1px 6px; border-radius: 4px; background: rgba(255, 255, 255, 0.08); color: var(--text-muted);">${t}</span>`).join('') +
            `</div>`
          : '';

        item.innerHTML = `
          <div style="flex: 1; overflow: hidden; padding-right: 12px;">
            <div style="font-weight: 600; font-size: 0.95rem; margin-bottom: 2px; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
              ${d.title || 'Без названия'}
            </div>
            ${snippetHtml}
            <div style="font-size: 0.8rem; color: var(--text-muted); display: flex; align-items: center; gap: 12px; margin-top: 4px;">
              <span style="display:inline-flex; align-items:center; gap:4px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg> ${dateStr}</span>
              <span style="display:inline-flex; align-items:center; gap:4px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg> ${d.wordCount || 0} сл.</span>
              <span style="display:inline-flex; align-items:center; gap:4px;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg> ${d.readingTime || 1} мин</span>
            </div>
            ${tagsHtml}
          </div>
          <div style="display: flex; gap: 6px; align-items: center;">
            <button class="btn btn-sm btn-load" type="button" title="Восстановить">Открыть</button>
            <button class="btn btn-sm btn-delete text-danger" type="button" title="Удалить"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button>
          </div>
        `;

        item.querySelector('.btn-load').addEventListener('click', async (e) => {
          e.stopPropagation();
          await this.loadDraft(d, true);
          if (this.draftsModal) this.draftsModal.classList.remove('show');
        });

        item.querySelector('.btn-delete').addEventListener('click', async (e) => {
          e.stopPropagation();
          const entityName = this.materialType === 'question' ? 'вопрос' : 'черновик';
          if (confirm(`Удалить ${entityName} «${d.title || 'Без названия'}»?`)) {
            await this.deleteDraft(d.id);
          }
        });

        this.draftsListEl.appendChild(item);
      });
    }

    getSubmissionIdempotencyKey() {
      const rev = this.currentRevision || (this.currentDraft && (this.currentDraft.revision || this.currentDraft.updatedAt)) || 1;
      return (this.materialType === 'question')
        ? ('q_' + this.currentDraftId + '_rev_' + rev)
        : ('pub_' + this.currentDraftId + '_rev_' + rev);
    }

    _computeFingerprint(title, delta, html, publicationSettings, tags) {
      let filteredSettings = null;
      if (publicationSettings && typeof publicationSettings === 'object') {
        filteredSettings = {};
        for (const key of Object.keys(publicationSettings).sort()) {
          if (key !== 'status') {
            filteredSettings[key] = publicationSettings[key];
          }
        }
      }
      return JSON.stringify({
        title: (title || '').trim(),
        delta: delta || null,
        html: (html || '').trim(),
        tags: Array.isArray(tags) ? tags.slice().sort() : [],
        settings: filteredSettings
      });
    }
  }

  window.DraftsManager = DraftsManager;

})(window);
