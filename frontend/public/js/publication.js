/**
 * Antigravity WYSIWYG Editor - Publication Settings & Moderation Manager
 * Handles article readiness validation, publication settings modal,
 * searchable audience/topics, keywords tagging, format & complexity selection,
 * canvas cover cropping (780x440), live feed card preview, and submission to moderation queue.
 * 100% offline-first, Onest font family, strict 2px stroke SVG icons, 0 emojis.
 */

(function (window) {
  'use strict';

  class PublicationManager {
    constructor(editor, titleInput) {
      this.editor = editor;
      this.titleInput = titleInput;
      this.config = window.PublicationConfig || {
        AUDIENCES: [],
        TOPICS: [],
        FORMATS: [],
        COMPLEXITIES: [],
        LIMITS: {
          KEYWORDS_MIN: 1,
          KEYWORDS_MAX: 10,
          KEYWORD_MAX_LEN: 60,
          TOPICS_MIN: 1,
          TOPICS_MAX: 5,
          DESCRIPTION_MIN: 50,
          DESCRIPTION_MAX: 500,
          COVER_MAX_BYTES: 10 * 1024 * 1024,
          COVER_WIDTH: 780,
          COVER_HEIGHT: 440
        }
      };

      // Publication settings state
      this.audience = null; // string id
      this.topics = []; // array of topic ids (1-5)
      this.keywords = []; // array of keyword strings (1-10)
      this.format = 'not_specified'; // format id or 'not_specified'
      this.complexity = 'none'; // 'none' | 'easy' | 'medium' | 'hard'
      this.description = ''; // plain text 50-500 chars
      this.isDescriptionCustom = false;
      this.coverDataUrl = null; // cropped 780x440 data URL
      this.rawCoverImageSource = null; // original Data URL string
      this.cropParams = { zoom: 1, panX: 0, panY: 0 };
      this.previousCoverState = null; // backup for cancel/replace error recovery
      this.coverMeta = null; // metadata { originalName, originalWidth, originalHeight, isGif }
      this.status = 'draft'; // 'draft' | 'in_moderation'

      // Cropper state
      this.rawCoverImage = null; // HTMLImageElement
      this.cropZoom = 1;
      this.cropPanX = 0;
      this.cropPanY = 0;
      this.isDraggingCrop = false;
      this.dragStartX = 0;
      this.dragStartY = 0;

      // Modal state
      this.isOpen = false;
      this.previousActiveElement = null;
      this.isSubmitting = false;

      // Filter search queries
      this.audienceSearchQuery = '';
      this.topicsSearchQuery = '';

      this.initElements();
      this.bindEvents();
      this.updateReadinessUI();
    }

    /* ==========================================================================
       Initialization and DOM Elements
       ========================================================================== */
    initElements() {
      // Top bar button
      this.btnNextToSettings = document.getElementById('btn-next-to-settings');

      // Modal and overlay
      this.modalOverlay = document.getElementById('publication-modal');
      this.modalCloseBtn = document.getElementById('pub-modal-close-btn');
      this.btnPubBack = document.getElementById('btn-pub-back');
      this.btnPubSubmit = document.getElementById('btn-pub-submit');

      // Section 1: Audience
      this.audienceSearchInput = document.getElementById('pub-audience-search');
      this.audienceListEl = document.getElementById('pub-audience-list');
      this.audienceErrorEl = document.getElementById('pub-audience-error');

      // Section 2: Topics
      this.topicsSearchInput = document.getElementById('pub-topics-search');
      this.topicsSelectedEl = document.getElementById('pub-topics-selected');
      this.topicsAvailableEl = document.getElementById('pub-topics-available');
      this.topicsCountEl = document.getElementById('pub-topics-count');
      this.topicsErrorEl = document.getElementById('pub-topics-error');

      // Section 3: Keywords
      this.keywordsContainerEl = document.getElementById('pub-keywords-container');
      this.keywordsInput = document.getElementById('pub-keywords-input');
      this.keywordsCountEl = document.getElementById('pub-keywords-count');
      this.keywordsErrorEl = document.getElementById('pub-keywords-error');

      // Section 4: Format
      this.formatOptionsEl = document.getElementById('pub-format-options');

      // Section 5: Complexity
      this.complexityOptionsEl = document.getElementById('pub-complexity-options');
      this.complexityDescEl = document.getElementById('pub-complexity-desc');

      // Section 6: Feed Display & Cover
      this.coverDropzone = document.getElementById('pub-cover-dropzone');
      this.coverFileInput = document.getElementById('pub-cover-input');
      this.coverPreviewWrapper = document.getElementById('pub-cover-preview-wrapper');
      this.coverImg = document.getElementById('pub-cover-img');
      this.coverReplaceBtn = document.getElementById('pub-cover-replace-btn');
      this.coverCropBtn = document.getElementById('pub-cover-crop-btn');
      this.coverDeleteBtn = document.getElementById('pub-cover-delete-btn');
      this.coverNoticeEl = document.getElementById('pub-cover-notice');
      this.coverWarningEl = document.getElementById('pub-cover-warning');
      this.coverErrorEl = document.getElementById('pub-cover-error');

      // Cropper modal/inline controls
      this.cropperWrapper = document.getElementById('pub-cropper-wrapper');
      this.cropperCanvas = document.getElementById('pub-cropper-canvas');
      this.cropperZoomInput = document.getElementById('pub-cropper-zoom');
      this.cropperApplyBtn = document.getElementById('pub-cropper-apply-btn');
      this.cropperCancelBtn = document.getElementById('pub-cropper-cancel-btn');

      // Description
      this.descriptionInput = document.getElementById('pub-description');
      this.descriptionCountEl = document.getElementById('pub-desc-count');
      this.descriptionErrorEl = document.getElementById('pub-desc-error');

      // Card Preview (7-step uniform structure)
      this.cardPreview = document.getElementById('pub-card-preview');
      this.cardPreviewAvatar = document.getElementById('preview-card-avatar');
      this.cardPreviewAuthor = document.getElementById('preview-card-author');
      this.cardPreviewDate = document.getElementById('preview-card-date');
      this.cardPreviewDot = document.getElementById('preview-card-dot');
      this.cardPreviewRole = document.getElementById('preview-card-role');
      this.cardPreviewTitle = document.getElementById('preview-card-title');
      this.cardPreviewBadges = document.getElementById('preview-card-badges');
      this.cardPreviewBadgeTopic = document.getElementById('preview-card-badge-topic');
      this.cardPreviewBadgeFormat = document.getElementById('preview-card-badge-format');
      this.cardPreviewBadgeComplexity = document.getElementById('preview-card-badge-complexity');
      this.cardPreviewCover = document.getElementById('preview-card-cover');
      this.cardPreviewDesc = document.getElementById('preview-card-desc');
      this.cardPreviewTags = document.getElementById('preview-card-tags');
      this.cardPreviewTime = document.getElementById('preview-card-time');
      this.cardPreviewBookmark = document.getElementById('preview-card-bookmark');
    }

    bindEvents() {
      // Top bar button click
      if (this.btnNextToSettings) {
        this.btnNextToSettings.addEventListener('click', (e) => this.handleNextToSettingsClick(e));
      }

      // Title & Editor input events for dynamic readiness checking
      if (this.titleInput) {
        this.titleInput.addEventListener('input', () => {
          this.updateReadinessUI();
          this.updateCardPreview();
        });
      }

      if (this.editor) {
        this.editor.on('text-change', () => {
          this.updateReadinessUI();
          this.updateCardPreview();
        });
      }

      // Modal close handlers (Save on close, no backdrop close)
      if (this.modalCloseBtn) {
        this.modalCloseBtn.addEventListener('click', () => this.closeModal(true));
      }
      if (this.btnPubBack) {
        this.btnPubBack.addEventListener('click', () => this.closeModal(true));
      }

      // Submit to moderation button
      if (this.btnPubSubmit) {
        this.btnPubSubmit.addEventListener('click', () => this.submitToModeration());
      }

      // Keyboard trap & Escape
      document.addEventListener('keydown', (e) => this.handleKeyDown(e));

      // Section 1: Audience search
      if (this.audienceSearchInput) {
        this.audienceSearchInput.addEventListener('input', (e) => {
          this.audienceSearchQuery = e.target.value.toLowerCase().trim();
          this.renderAudienceList();
        });
      }

      // Section 2: Topics search
      if (this.topicsSearchInput) {
        this.topicsSearchInput.addEventListener('input', (e) => {
          this.topicsSearchQuery = e.target.value.toLowerCase().trim();
          this.renderTopicsAvailable();
        });
      }

      // Section 3: Keywords input
      if (this.keywordsInput) {
        this.keywordsInput.addEventListener('keydown', (e) => this.handleKeywordsKeyDown(e));
        this.keywordsInput.addEventListener('paste', (e) => this.handleKeywordsPaste(e));
        this.keywordsInput.addEventListener('blur', () => this.commitUncommittedKeyword());
      }

      // Section 5: Complexity change
      if (this.complexityOptionsEl) {
        this.complexityOptionsEl.addEventListener('click', (e) => {
          const btn = e.target.closest('[data-complexity]');
          if (!btn) return;
          const level = btn.getAttribute('data-complexity');
          this.setComplexity(level);
        });
      }

      // Section 6: Cover upload & dropzone
      if (this.coverFileInput) {
        this.coverFileInput.addEventListener('change', (e) => {
          if (e.target.files && e.target.files[0]) {
            this.handleCoverFile(e.target.files[0]);
          }
        });
      }

      if (this.coverDropzone) {
        this.coverDropzone.addEventListener('dragover', (e) => {
          e.preventDefault();
          this.coverDropzone.classList.add('drag-over');
        });
        this.coverDropzone.addEventListener('dragleave', (e) => {
          e.preventDefault();
          this.coverDropzone.classList.remove('drag-over');
        });
        this.coverDropzone.addEventListener('drop', (e) => {
          e.preventDefault();
          this.coverDropzone.classList.remove('drag-over');
          if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            this.handleCoverFile(e.dataTransfer.files[0]);
          }
        });
        this.coverDropzone.addEventListener('click', () => {
          if (this.coverFileInput) this.coverFileInput.click();
        });
      }

      if (this.coverReplaceBtn) {
        this.coverReplaceBtn.addEventListener('click', () => {
          if (this.coverFileInput) this.coverFileInput.click();
        });
      }

      if (this.coverCropBtn) {
        this.coverCropBtn.addEventListener('click', () => {
          if (this.rawCoverImage) {
            this.openCropper();
          }
        });
      }

      if (this.coverDeleteBtn) {
        this.coverDeleteBtn.addEventListener('click', () => {
          this.deleteCover();
        });
      }

      // Cropper events
      if (this.cropperZoomInput) {
        this.cropperZoomInput.addEventListener('input', (e) => {
          this.cropZoom = parseFloat(e.target.value) || 1;
          this.drawCropperCanvas();
        });
      }

      if (this.cropperCanvas) {
        const getCanvasScale = () => {
          const rect = this.cropperCanvas.getBoundingClientRect();
          return {
            scaleX: rect.width ? (this.cropperCanvas.width / rect.width) : 1,
            scaleY: rect.height ? (this.cropperCanvas.height / rect.height) : 1
          };
        };

        this.cropperCanvas.addEventListener('mousedown', (e) => {
          this.isDraggingCrop = true;
          const s = getCanvasScale();
          this.dragStartX = (e.clientX * s.scaleX) - this.cropPanX;
          this.dragStartY = (e.clientY * s.scaleY) - this.cropPanY;
        });

        window.addEventListener('mousemove', (e) => {
          if (!this.isDraggingCrop) return;
          const s = getCanvasScale();
          this.cropPanX = (e.clientX * s.scaleX) - this.dragStartX;
          this.cropPanY = (e.clientY * s.scaleY) - this.dragStartY;
          this.drawCropperCanvas();
        });

        window.addEventListener('mouseup', () => {
          this.isDraggingCrop = false;
        });

        // Touch support for mobile cropper
        this.cropperCanvas.addEventListener('touchstart', (e) => {
          if (e.touches && e.touches[0]) {
            this.isDraggingCrop = true;
            const s = getCanvasScale();
            this.dragStartX = (e.touches[0].clientX * s.scaleX) - this.cropPanX;
            this.dragStartY = (e.touches[0].clientY * s.scaleY) - this.cropPanY;
          }
        }, { passive: false });

        this.cropperCanvas.addEventListener('touchmove', (e) => {
          if (!this.isDraggingCrop || !e.touches || !e.touches[0]) return;
          e.preventDefault();
          const s = getCanvasScale();
          this.cropPanX = (e.touches[0].clientX * s.scaleX) - this.dragStartX;
          this.cropPanY = (e.touches[0].clientY * s.scaleY) - this.dragStartY;
          this.drawCropperCanvas();
        }, { passive: false });

        this.cropperCanvas.addEventListener('touchend', () => {
          this.isDraggingCrop = false;
        });
      }

      if (this.cropperApplyBtn) {
        this.cropperApplyBtn.addEventListener('click', () => this.applyCropping());
      }
      if (this.cropperCancelBtn) {
        this.cropperCancelBtn.addEventListener('click', () => this.closeCropper(true));
      }

      // Description input & counter
      if (this.descriptionInput) {
        this.descriptionInput.addEventListener('input', (e) => {
          this.description = e.target.value;
          this.isDescriptionCustom = true;
          this.updateDescCounter();
          this.updateCardPreview();
          if (this.descriptionErrorEl) this.descriptionErrorEl.textContent = '';
        });
      }
    }

    /* ==========================================================================
       Article Readiness Verification
       ========================================================================== */
    isArticleReady() {
      const title = (this.titleInput ? this.titleInput.value : '').trim();
      if (!title) return false;

      // Extract editor text and verify at least one letter or digit
      // Standalone images, empty paragraphs, spaces, nbsp, invisible chars, and dividers do NOT count
      const text = this.editor ? this.editor.getText() : '';
      const hasLettersOrDigits = /[a-zA-Zа-яёА-ЯЁ0-9]/.test(text);

      return hasLettersOrDigits;
    }

    updateReadinessUI() {
      if (!this.btnNextToSettings) return;

      const ready = this.isArticleReady();
      if (ready) {
        this.btnNextToSettings.disabled = false;
        this.btnNextToSettings.classList.remove('disabled');
        this.btnNextToSettings.setAttribute('title', 'Перейти к настройкам публикации');
        this.btnNextToSettings.removeAttribute('aria-disabled');
      } else {
        this.btnNextToSettings.disabled = true;
        this.btnNextToSettings.classList.add('disabled');
        this.btnNextToSettings.setAttribute('title', 'Добавьте заголовок и текст статьи');
        this.btnNextToSettings.setAttribute('aria-disabled', 'true');
      }
    }

    async handleNextToSettingsClick(e) {
      if (e) e.preventDefault();

      if (!this.isArticleReady()) {
        if (window.EditorApp && window.EditorApp.showToast) {
          window.EditorApp.showToast('Добавьте заголовок и текст статьи', 'info');
        }
        return;
      }

      // Save draft first
      try {
        if (window.EditorApp && window.EditorApp.Drafts) {
          await window.EditorApp.Drafts.saveCurrent({ isManual: false });
        }
        this.openModal();
      } catch (err) {
        console.error('Failed to save draft before opening publication settings:', err);
        if (window.EditorApp && window.EditorApp.showToast) {
          window.EditorApp.showToast('Не удалось сохранить черновик. Пожалуйста, повторите попытку.', 'danger');
        }
      }
    }

    /* ==========================================================================
       Modal Dialog Management (Desktop 800-900px, Mobile Fullscreen, Focus Trap)
       ========================================================================== */
    openModal() {
      if (!this.modalOverlay) return;

      this.previousActiveElement = document.activeElement;
      this.isOpen = true;
      document.body.classList.add('modal-open');
      this.modalOverlay.classList.add('show');
      this.modalOverlay.setAttribute('aria-hidden', 'false');

      // Auto-extract description on first modal open if not modified by author
      if (!this.isDescriptionCustom && (!this.description || !this.description.trim())) {
        this.extractDescriptionFromEditor();
      }

      this.render();
      this.updateCardPreview();

      // Focus trap initial focus
      const firstInput = this.modalOverlay.querySelector('input, button:not([disabled])');
      if (firstInput) {
        setTimeout(() => firstInput.focus(), 50);
      }
    }

    closeModal(save = true) {
      if (!this.modalOverlay) return;

      if (save) {
        this.commitUncommittedKeyword();
        // Save publication settings with current draft
        if (window.EditorApp && window.EditorApp.Drafts) {
          window.EditorApp.Drafts.saveCurrent({ isManual: false });
        }
      }

      this.isOpen = false;
      this.modalOverlay.classList.remove('show');
      this.modalOverlay.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('modal-open');

      // Return focus to #btn-next-to-settings
      if (this.btnNextToSettings) {
        this.btnNextToSettings.focus();
      } else if (this.previousActiveElement) {
        this.previousActiveElement.focus();
      }
    }

    handleKeyDown(e) {
      if (!this.isOpen) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        this.closeModal(true);
        return;
      }

      if (e.key === 'Tab') {
        const focusables = Array.from(this.modalOverlay.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )).filter(el => el.offsetParent !== null);

        if (focusables.length === 0) return;

        const first = focusables[0];
        const last = focusables[focusables.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first || !this.modalOverlay.contains(document.activeElement)) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last || !this.modalOverlay.contains(document.activeElement)) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    }

    /* ==========================================================================
       Rendering All Sections
       ========================================================================== */
    render() {
      this.renderAudienceList();
      this.renderTopicsSelected();
      this.renderTopicsAvailable();
      this.renderKeywords();
      this.renderFormats();
      this.renderComplexities();
      this.renderCoverUI();
      this.renderDescription();
    }

    /* ==========================================================================
       Section 1: Target Audience
       ========================================================================== */
    renderAudienceList() {
      if (!this.audienceListEl) return;

      const q = this.audienceSearchQuery;
      const filtered = this.config.AUDIENCES.filter(a => {
        if (!q) return true;
        return a.title.toLowerCase().includes(q) || (a.description && a.description.toLowerCase().includes(q));
      });

      if (filtered.length === 0) {
        this.audienceListEl.innerHTML = '<div class="pub-empty-search">Ничего не найдено</div>';
        return;
      }

      let html = '';
      filtered.forEach(aud => {
        const isSelected = this.audience === aud.id;
        html += `
          <div class="pub-audience-item ${isSelected ? 'is-selected' : ''}" data-audience-id="${aud.id}" role="radio" aria-checked="${isSelected}">
            <div class="pub-radio-indicator">
              ${isSelected ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>' : ''}
            </div>
            <div class="pub-audience-info">
              <div class="pub-audience-title">${aud.title}</div>
              <div class="pub-audience-desc">${aud.description || ''}</div>
            </div>
          </div>
        `;
      });

      this.audienceListEl.innerHTML = html;

      // Bind selection clicks
      this.audienceListEl.querySelectorAll('.pub-audience-item').forEach(el => {
        el.addEventListener('click', () => {
          const id = el.getAttribute('data-audience-id');
          this.setAudience(id);
        });
      });
    }

    setAudience(id) {
      this.audience = id;
      if (this.audienceErrorEl) this.audienceErrorEl.textContent = '';
      this.renderAudienceList();
      this.updateCardPreview();
    }

    /* ==========================================================================
       Section 2: Topics (1 to 5)
       ========================================================================== */
    renderTopicsSelected() {
      if (!this.topicsSelectedEl) return;

      if (this.topics.length === 0) {
        this.topicsSelectedEl.innerHTML = '<div class="pub-chips-placeholder">Темы не выбраны. Выберите от 1 до 5 тем ниже.</div>';
      } else {
        let html = '';
        this.topics.forEach(tid => {
          const topic = this.config.getTopicById(tid);
          const title = topic ? topic.title : tid;
          html += `
            <span class="pub-chip pub-topic-chip" data-topic-id="${tid}">
              <span class="pub-chip-text">${title}</span>
              <button type="button" class="pub-chip-remove" aria-label="Удалить тему" data-remove-topic="${tid}">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </span>
          `;
        });
        this.topicsSelectedEl.innerHTML = html;

        this.topicsSelectedEl.querySelectorAll('[data-remove-topic]').forEach(btn => {
          btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const tid = btn.getAttribute('data-remove-topic');
            this.removeTopic(tid);
          });
        });
      }

      if (this.topicsCountEl) {
        this.topicsCountEl.textContent = this.topics.length;
      }
    }

    renderTopicsAvailable() {
      if (!this.topicsAvailableEl) return;

      const q = this.topicsSearchQuery;
      const unselected = this.config.TOPICS.filter(t => !this.topics.includes(t.id));
      const filtered = unselected.filter(t => {
        if (!q) return true;
        return t.title.toLowerCase().includes(q);
      });

      if (filtered.length === 0) {
        this.topicsAvailableEl.innerHTML = '<div class="pub-empty-search">Все темы выбраны или ничего не найдено</div>';
        return;
      }

      let html = '';
      filtered.forEach(top => {
        const canAdd = this.topics.length < this.config.LIMITS.TOPICS_MAX;
        html += `
          <button type="button" class="pub-topic-pill ${!canAdd ? 'is-disabled' : ''}" data-add-topic="${top.id}" ${!canAdd ? 'disabled' : ''}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            <span>${top.title}</span>
          </button>
        `;
      });

      this.topicsAvailableEl.innerHTML = html;

      this.topicsAvailableEl.querySelectorAll('[data-add-topic]').forEach(btn => {
        btn.addEventListener('click', () => {
          const tid = btn.getAttribute('data-add-topic');
          this.addTopic(tid);
        });
      });
    }

    addTopic(topicId) {
      if (this.topics.includes(topicId)) return;
      if (this.topics.length >= this.config.LIMITS.TOPICS_MAX) {
        if (this.topicsErrorEl) {
          this.topicsErrorEl.textContent = 'Можно выбрать максимум 5 тем публикации.';
        }
        return;
      }

      this.topics.push(topicId);
      if (this.topicsErrorEl) this.topicsErrorEl.textContent = '';
      this.renderTopicsSelected();
      this.renderTopicsAvailable();
    }

    removeTopic(topicId) {
      this.topics = this.topics.filter(t => t !== topicId);
      if (this.topicsErrorEl) this.topicsErrorEl.textContent = '';
      this.renderTopicsSelected();
      this.renderTopicsAvailable();
    }

    /* ==========================================================================
       Section 3: Keywords Tag Input (1 to 10 tags, 60 char max)
       ========================================================================== */
    renderKeywords() {
      if (!this.keywordsContainerEl) return;

      const chips = this.keywordsContainerEl.querySelectorAll('.pub-keyword-chip');
      chips.forEach(c => c.remove());

      const frag = document.createDocumentFragment();
      this.keywords.forEach((kw, idx) => {
        const chip = document.createElement('span');
        chip.className = 'pub-chip pub-keyword-chip';
        chip.innerHTML = `
          <span class="pub-chip-text">${this.escapeHTML(kw)}</span>
          <button type="button" class="pub-chip-remove" aria-label="Удалить ключевую фразу" data-kw-idx="${idx}">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        `;
        chip.querySelector('button').addEventListener('click', (e) => {
          e.stopPropagation();
          this.removeKeyword(idx);
        });
        frag.appendChild(chip);
      });

      if (this.keywordsInput) {
        this.keywordsContainerEl.insertBefore(frag, this.keywordsInput);
      } else {
        this.keywordsContainerEl.appendChild(frag);
      }

      if (this.keywordsCountEl) {
        this.keywordsCountEl.textContent = this.keywords.length;
      }
    }

    normalizeKeyword(raw) {
      if (!raw) return '';
      return raw.trim().replace(/\s+/g, ' ');
    }

    addKeyword(raw) {
      const norm = this.normalizeKeyword(raw);
      if (!norm) return { ok: false, reason: 'empty' };

      if (norm.length > this.config.LIMITS.KEYWORD_MAX_LEN) {
        return { ok: false, reason: 'too_long', value: norm };
      }

      const lower = norm.toLowerCase();
      if (this.keywords.some(k => k.toLowerCase() === lower)) {
        return { ok: false, reason: 'duplicate', value: norm };
      }

      if (this.keywords.length >= this.config.LIMITS.KEYWORDS_MAX) {
        return { ok: false, reason: 'limit_reached', value: norm };
      }

      this.keywords.push(norm);
      return { ok: true, value: norm };
    }

    removeKeyword(idx) {
      this.keywords.splice(idx, 1);
      if (this.keywordsErrorEl) this.keywordsErrorEl.textContent = '';
      this.renderKeywords();
    }

    handleKeywordsKeyDown(e) {
      if (e.key === 'Enter' || e.key === ',') {
        e.preventDefault();
        const val = this.keywordsInput.value;
        if (!val) return;

        const res = this.addKeyword(val);
        if (res.ok) {
          this.keywordsInput.value = '';
          if (this.keywordsErrorEl) this.keywordsErrorEl.textContent = '';
          this.renderKeywords();
        } else {
          if (res.reason === 'too_long') {
            if (this.keywordsErrorEl) {
              this.keywordsErrorEl.textContent = `Ключевая фраза не может быть длиннее ${this.config.LIMITS.KEYWORD_MAX_LEN} символов.`;
            }
          } else if (res.reason === 'duplicate') {
            if (this.keywordsErrorEl) {
              this.keywordsErrorEl.textContent = 'Эта ключевая фраза уже добавлена.';
            }
          } else if (res.reason === 'limit_reached') {
            if (this.keywordsErrorEl) {
              this.keywordsErrorEl.textContent = `Максимум ${this.config.LIMITS.KEYWORDS_MAX} ключевых фраз.`;
            }
          }
        }
      } else if (e.key === 'Backspace' && !this.keywordsInput.value && this.keywords.length > 0) {
        // Remove last tag on Backspace in empty input
        this.removeKeyword(this.keywords.length - 1);
      }
    }

    handleKeywordsPaste(e) {
      const text = (e.clipboardData || window.clipboardData).getData('text');
      if (!text || !text.includes(',')) return;

      e.preventDefault();
      const chunks = text.split(/,|\n/).map(c => c.trim()).filter(Boolean);
      const rejected = [];

      chunks.forEach(chunk => {
        const res = this.addKeyword(chunk);
        if (!res.ok && res.reason !== 'duplicate') {
          rejected.push(chunk);
        }
      });

      this.renderKeywords();

      if (rejected.length > 0) {
        // Preserve unadded tags in input without silent loss
        this.keywordsInput.value = rejected.join(', ');
        if (this.keywordsErrorEl) {
          this.keywordsErrorEl.textContent = `Добавлены подходящие теги. Не удалось добавить: ${rejected.length} (превышен лимит 10 фраз или длина > 60 симв.). Оставшийся текст сохранен в поле ввода.`;
        }
      } else {
        this.keywordsInput.value = '';
        if (this.keywordsErrorEl) this.keywordsErrorEl.textContent = '';
      }
    }

    commitUncommittedKeyword() {
      if (!this.keywordsInput) return;
      const val = this.keywordsInput.value;
      if (!val || !val.trim()) return;

      const chunks = val.split(/,|\n/).map(c => c.trim()).filter(Boolean);
      const remaining = [];

      chunks.forEach(chunk => {
        const res = this.addKeyword(chunk);
        if (!res.ok) {
          remaining.push(chunk);
        }
      });

      this.renderKeywords();

      if (remaining.length > 0) {
        this.keywordsInput.value = remaining.join(', ');
      } else {
        this.keywordsInput.value = '';
      }
    }

    /* ==========================================================================
       Section 4: Format (11 formats + 'not_specified')
       ========================================================================== */
    renderFormats() {
      if (!this.formatOptionsEl) return;

      let html = `
        <div class="pub-format-card ${this.format === 'not_specified' ? 'is-selected' : ''}" data-format-id="not_specified">
          <div class="pub-format-title">Не указан</div>
          <div class="pub-format-desc">Формат статьи не выбран</div>
        </div>
      `;

      this.config.FORMATS.forEach(fmt => {
        const isSelected = this.format === fmt.id;
        html += `
          <div class="pub-format-card ${isSelected ? 'is-selected' : ''}" data-format-id="${fmt.id}">
            <div class="pub-format-title">${fmt.title}</div>
            <div class="pub-format-desc">${fmt.description}</div>
          </div>
        `;
      });

      this.formatOptionsEl.innerHTML = html;

      this.formatOptionsEl.querySelectorAll('.pub-format-card').forEach(el => {
        el.addEventListener('click', () => {
          const fid = el.getAttribute('data-format-id');
          this.setFormat(fid);
        });
      });
    }

    setFormat(fmtId) {
      this.format = fmtId;
      this.renderFormats();
      this.updateCardPreview();
    }

    /* ==========================================================================
       Section 5: Complexity Level (none, easy, medium, hard)
       ========================================================================== */
    renderComplexities() {
      if (!this.complexityOptionsEl) return;

      this.complexityOptionsEl.querySelectorAll('[data-complexity]').forEach(btn => {
        const level = btn.getAttribute('data-complexity');
        if (level === this.complexity) {
          btn.classList.add('is-active');
        } else {
          btn.classList.remove('is-active');
        }
      });

      if (this.complexityDescEl) {
        const item = this.config.getComplexityById(this.complexity);
        this.complexityDescEl.textContent = item ? item.description : '';
      }
    }

    setComplexity(level) {
      this.complexity = level || 'none';
      this.renderComplexities();
      this.updateCardPreview();
    }

    /* ==========================================================================
       Section 6: Cover Image & Canvas Cropper (39:22 / 780x440)
       ========================================================================== */
    saveCoverBackup() {
      this.previousCoverState = {
        coverDataUrl: this.coverDataUrl,
        rawCoverImage: this.rawCoverImage,
        rawCoverImageSource: this.rawCoverImageSource,
        cropParams: this.cropParams ? { ...this.cropParams } : { zoom: 1, panX: 0, panY: 0 },
        coverMeta: this.coverMeta ? { ...this.coverMeta } : null
      };
    }

    restoreCoverBackup() {
      if (this.previousCoverState) {
        this.coverDataUrl = this.previousCoverState.coverDataUrl;
        this.rawCoverImage = this.previousCoverState.rawCoverImage;
        this.rawCoverImageSource = this.previousCoverState.rawCoverImageSource;
        this.cropParams = this.previousCoverState.cropParams ? { ...this.previousCoverState.cropParams } : { zoom: 1, panX: 0, panY: 0 };
        this.coverMeta = this.previousCoverState.coverMeta ? { ...this.previousCoverState.coverMeta } : null;
        this.cropZoom = this.cropParams.zoom || 1;
        this.cropPanX = this.cropParams.panX || 0;
        this.cropPanY = this.cropParams.panY || 0;
      }
      this.renderCoverUI();
      this.updateCardPreview();
    }

    handleCoverFile(file) {
      if (!file) return;
      if (this.coverErrorEl) this.coverErrorEl.textContent = '';
      if (this.coverWarningEl) this.coverWarningEl.textContent = '';
      if (this.coverNoticeEl) this.coverNoticeEl.textContent = '';

      const coverConfig = (window.PublicationConfig && window.PublicationConfig.COVER) || {
        MAX_FILE_BYTES: 10 * 1024 * 1024,
        ALLOWED_FORMATS: ['image/jpeg', 'image/png', 'image/webp', 'image/gif'],
        TARGET_WIDTH: 780,
        TARGET_HEIGHT: 440,
        ASPECT_RATIO_VALUE: 39 / 22
      };

      // Validate size (max 10MB)
      if (file.size > coverConfig.MAX_FILE_BYTES) {
        if (this.coverErrorEl) {
          this.coverErrorEl.textContent = 'Размер файла превышает 10 МБ. Выберите изображение меньшего размера.';
        }
        if (this.coverFileInput) this.coverFileInput.value = '';
        return;
      }

      // Validate MIME type & file extension
      const validTypes = coverConfig.ALLOWED_FORMATS || ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
      const fileName = (file.name || '').toLowerCase();
      const validExts = ['.jpg', '.jpeg', '.png', '.webp', '.gif'];
      const hasValidExt = validExts.some(ext => fileName.endsWith(ext));
      if (!validTypes.includes(file.type) && !hasValidExt) {
        if (this.coverErrorEl) {
          this.coverErrorEl.textContent = 'Неподдерживаемый формат. Разрешены только JPEG, PNG, WebP и GIF.';
        }
        if (this.coverFileInput) this.coverFileInput.value = '';
        return;
      }

      const isGif = file.type === 'image/gif' || fileName.endsWith('.gif');

      // Preserve existing cover state for cancellation/error recovery
      this.saveCoverBackup();

      const reader = new FileReader();
      reader.onload = (e) => {
        const rawDataUrl = e.target.result;
        const img = new Image();
        img.onload = () => {
          this.rawCoverImage = img;
          this.rawCoverImageSource = rawDataUrl;
          this.coverMeta = {
            originalName: file.name,
            originalWidth: img.naturalWidth,
            originalHeight: img.naturalHeight,
            isGif: isGif
          };

          // Resolution warning if below recommended 780x440
          if (img.naturalWidth < coverConfig.TARGET_WIDTH || img.naturalHeight < coverConfig.TARGET_HEIGHT) {
            if (this.coverWarningEl) {
              this.coverWarningEl.textContent = `Разрешение изображения (${img.naturalWidth}×${img.naturalHeight} px) меньше рекомендуемого (${coverConfig.TARGET_WIDTH}×${coverConfig.TARGET_HEIGHT} px). Возможно снижение четкости.`;
            }
          }

          // Static GIF notice
          if (isGif && this.coverNoticeEl) {
            this.coverNoticeEl.textContent = 'Для GIF используется первый кадр в качестве статичной обложки.';
          }

          // Check aspect ratio (39:22 with ~0.02 epsilon)
          const targetRatio = coverConfig.ASPECT_RATIO_VALUE || (39 / 22);
          const imgRatio = img.naturalWidth / img.naturalHeight;
          const is39x22 = Math.abs(imgRatio - targetRatio) <= 0.02;

          if (is39x22) {
            // Already 39:22 -> save whole frame by default without forced cropping modal
            const targetW = coverConfig.TARGET_WIDTH;
            const targetH = coverConfig.TARGET_HEIGHT;
            const offscreen = document.createElement('canvas');
            offscreen.width = targetW;
            offscreen.height = targetH;
            const ctx = offscreen.getContext('2d');
            ctx.drawImage(img, 0, 0, targetW, targetH);
            this.coverDataUrl = offscreen.toDataURL('image/jpeg', 0.92);
            this.cropParams = { zoom: 1, panX: 0, panY: 0 };
            this.cropZoom = 1;
            this.cropPanX = 0;
            this.cropPanY = 0;
            this.saveCoverBackup();
            this.closeCropper(false);
            this.renderCoverUI();
            this.updateCardPreview();
          } else {
            // Proportions differ -> open cropper with fixed 39:22
            this.cropParams = { zoom: 1, panX: 0, panY: 0 };
            this.cropZoom = 1;
            this.cropPanX = 0;
            this.cropPanY = 0;
            this.openCropper();
          }
        };

        img.onerror = () => {
          if (this.coverErrorEl) {
            this.coverErrorEl.textContent = 'Не удалось декодировать изображение. Файл поврежден или не является валидной картинкой.';
          }
          this.restoreCoverBackup();
        };

        img.src = rawDataUrl;
      };

      reader.onerror = () => {
        if (this.coverErrorEl) {
          this.coverErrorEl.textContent = 'Ошибка чтения файла изображения.';
        }
        this.restoreCoverBackup();
      };

      reader.readAsDataURL(file);
    }

    openCropper() {
      if (!this.cropperWrapper || !this.rawCoverImage) return;

      this.saveCoverBackup();
      this.cropperWrapper.classList.add('is-active');

      if (this.cropParams) {
        this.cropZoom = this.cropParams.zoom || 1;
        this.cropPanX = this.cropParams.panX || 0;
        this.cropPanY = this.cropParams.panY || 0;
      } else {
        this.cropZoom = 1;
        this.cropPanX = 0;
        this.cropPanY = 0;
      }

      if (this.cropperZoomInput) {
        this.cropperZoomInput.value = String(this.cropZoom);
      }

      this.drawCropperCanvas();
    }

    closeCropper(wasCancelled = false) {
      if (wasCancelled) {
        this.restoreCoverBackup();
      }
      if (this.cropperWrapper) {
        this.cropperWrapper.classList.remove('is-active');
      }
    }

    drawCropperCanvas() {
      if (!this.cropperCanvas || !this.rawCoverImage) return;

      const canvas = this.cropperCanvas;
      const ctx = canvas.getContext('2d');
      const cw = canvas.width;
      const ch = canvas.height;

      ctx.clearRect(0, 0, cw, ch);

      // Background
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(0, 0, cw, ch);

      const img = this.rawCoverImage;
      const baseScale = Math.max(cw / img.naturalWidth, ch / img.naturalHeight);
      const scale = baseScale * this.cropZoom;

      const drawW = img.naturalWidth * scale;
      const drawH = img.naturalHeight * scale;

      // Pan clamping within frame bounds
      const maxPanX = Math.max(0, (drawW - cw) / 2);
      const maxPanY = Math.max(0, (drawH - ch) / 2);
      this.cropPanX = Math.max(-maxPanX, Math.min(maxPanX, this.cropPanX));
      this.cropPanY = Math.max(-maxPanY, Math.min(maxPanY, this.cropPanY));

      const drawX = (cw - drawW) / 2 + this.cropPanX;
      const drawY = (ch - drawH) / 2 + this.cropPanY;

      ctx.drawImage(img, drawX, drawY, drawW, drawH);

      // Frame border overlay
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
      ctx.lineWidth = 1;
      ctx.strokeRect(0.5, 0.5, cw - 1, ch - 1);
    }

    applyCropping() {
      if (!this.cropperCanvas || !this.rawCoverImage) return;

      const coverConfig = (window.PublicationConfig && window.PublicationConfig.COVER) || {
        TARGET_WIDTH: 780,
        TARGET_HEIGHT: 440
      };
      const targetW = coverConfig.TARGET_WIDTH;
      const targetH = coverConfig.TARGET_HEIGHT;

      const offscreen = document.createElement('canvas');
      offscreen.width = targetW;
      offscreen.height = targetH;
      const ctx = offscreen.getContext('2d');

      const img = this.rawCoverImage;
      const baseScale = Math.max(targetW / img.naturalWidth, targetH / img.naturalHeight);
      const scale = baseScale * this.cropZoom;

      const drawW = img.naturalWidth * scale;
      const drawH = img.naturalHeight * scale;

      const drawX = (targetW - drawW) / 2 + this.cropPanX;
      const drawY = (targetH - drawH) / 2 + this.cropPanY;

      ctx.drawImage(img, drawX, drawY, drawW, drawH);

      // Export to permanent Data URL
      this.coverDataUrl = offscreen.toDataURL('image/jpeg', 0.92);
      this.cropParams = {
        zoom: this.cropZoom,
        panX: this.cropPanX,
        panY: this.cropPanY
      };
      this.saveCoverBackup();

      this.closeCropper(false);
      this.renderCoverUI();
      this.updateCardPreview();
    }

    deleteCover() {
      this.coverDataUrl = null;
      this.rawCoverImage = null;
      this.rawCoverImageSource = null;
      this.cropParams = { zoom: 1, panX: 0, panY: 0 };
      this.cropZoom = 1;
      this.cropPanX = 0;
      this.cropPanY = 0;
      this.coverMeta = null;
      this.previousCoverState = null;
      if (this.coverFileInput) this.coverFileInput.value = '';
      if (this.coverNoticeEl) this.coverNoticeEl.textContent = '';
      if (this.coverWarningEl) this.coverWarningEl.textContent = '';
      if (this.coverErrorEl) this.coverErrorEl.textContent = '';
      this.closeCropper(false);
      this.renderCoverUI();
      this.updateCardPreview();
    }

    renderCoverUI() {
      if (!this.coverPreviewWrapper || !this.coverDropzone) return;

      if (this.coverDataUrl) {
        this.coverDropzone.style.display = 'none';
        this.coverPreviewWrapper.style.display = 'block';
        if (this.coverImg) this.coverImg.src = this.coverDataUrl;
      } else {
        this.coverDropzone.style.display = 'flex';
        this.coverPreviewWrapper.style.display = 'none';
        if (this.coverImg) this.coverImg.src = '';
      }
    }

    escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    /* ==========================================================================
       Section 6: Description (50 to 500 chars)
       ========================================================================== */
    extractDescriptionFromEditor() {
      if (!this.editor) return;

      // Look for first paragraph with letters/digits and length >= 20
      const blocks = Array.from(this.editor.root.querySelectorAll('p, div, blockquote'));
      for (const b of blocks) {
        const text = (b.textContent || '').trim().replace(/\s+/g, ' ');
        if (text && /[a-zA-Zа-яёА-ЯЁ0-9]/.test(text) && text.length >= 20) {
          this.description = text.length > 500 ? text.substring(0, 497) + '...' : text;
          break;
        }
      }

      if (!this.description) {
        const raw = this.editor.getText().trim().replace(/\s+/g, ' ');
        if (raw && /[a-zA-Zа-яёА-ЯЁ0-9]/.test(raw)) {
          this.description = raw.length > 500 ? raw.substring(0, 497) + '...' : raw;
        }
      }

      if (this.descriptionInput) {
        this.descriptionInput.value = this.description;
      }
      this.updateDescCounter();
    }

    renderDescription() {
      if (this.descriptionInput) {
        this.descriptionInput.value = this.description || '';
      }
      this.updateDescCounter();
    }

    updateDescCounter() {
      if (!this.descriptionCountEl) return;
      const len = this.description ? this.description.length : 0;
      this.descriptionCountEl.textContent = len;
      if (len < this.config.LIMITS.DESCRIPTION_MIN || len > this.config.LIMITS.DESCRIPTION_MAX) {
        this.descriptionCountEl.classList.add('text-danger');
      } else {
        this.descriptionCountEl.classList.remove('text-danger');
      }
    }

    /* ==========================================================================
       Live Card Preview (Uniform 7-Step Feed Card Order)
       ========================================================================== */
    updateCardPreview() {
      // 1. Author and Date
      const authorName = (window.currentUser && window.currentUser.name) ||
        (window.EditorApp && window.EditorApp.authorName) ||
        'Автор платформы';
      const authorRole = (window.currentUser && window.currentUser.role) || '';
      const authorInitials = authorName.split(/\s+/).map(p => p[0]).filter(Boolean).slice(0, 2).join('').toUpperCase() || 'АП';

      if (this.cardPreviewAvatar) this.cardPreviewAvatar.textContent = authorInitials;
      if (this.cardPreviewAuthor) this.cardPreviewAuthor.textContent = authorName;
      if (this.cardPreviewDate) this.cardPreviewDate.textContent = 'Недавно';
      if (this.cardPreviewRole) {
        if (authorRole) {
          this.cardPreviewRole.textContent = authorRole;
          this.cardPreviewRole.style.display = 'inline';
          if (this.cardPreviewDot) this.cardPreviewDot.style.display = 'inline-block';
        } else {
          this.cardPreviewRole.style.display = 'none';
          if (this.cardPreviewDot) this.cardPreviewDot.style.display = 'none';
        }
      }

      // 2. Title
      if (this.cardPreviewTitle) {
        const rawTitle = this.titleInput ? this.titleInput.value.trim() : '';
        this.cardPreviewTitle.textContent = rawTitle || 'Заголовок публикации';
      }

      // 3. Badges: Topic, Format, Complexity
      let badgesCount = 0;
      // Topic badge
      if (this.cardPreviewBadgeTopic) {
        if (this.topics && this.topics.length > 0) {
          const topicId = this.topics[0];
          const t = this.config.getTopicById ? this.config.getTopicById(topicId) : null;
          if (t) {
            this.cardPreviewBadgeTopic.textContent = t.title;
            this.cardPreviewBadgeTopic.style.display = 'inline-flex';
            badgesCount++;
          } else {
            this.cardPreviewBadgeTopic.style.display = 'none';
          }
        } else {
          this.cardPreviewBadgeTopic.style.display = 'none';
        }
      }

      // Format badge
      if (this.cardPreviewBadgeFormat) {
        if (this.format && this.format !== 'not_specified' && this.format !== 'none') {
          const fmt = this.config.getFormatById ? this.config.getFormatById(this.format) : null;
          if (fmt && fmt.title && fmt.title.toLowerCase() !== 'не указан') {
            this.cardPreviewBadgeFormat.style.display = 'inline-flex';
            this.cardPreviewBadgeFormat.textContent = fmt.title;
            badgesCount++;
          } else {
            this.cardPreviewBadgeFormat.style.display = 'none';
          }
        } else {
          this.cardPreviewBadgeFormat.style.display = 'none';
        }
      }

      // Complexity badge
      if (this.cardPreviewBadgeComplexity) {
        if (this.complexity && this.complexity !== 'none') {
          const c = this.config.getComplexityById ? this.config.getComplexityById(this.complexity) : null;
          if (c && c.title && c.title.toLowerCase() !== 'не указан') {
            this.cardPreviewBadgeComplexity.style.display = 'inline-flex';
            this.cardPreviewBadgeComplexity.textContent = c.title;
            this.cardPreviewBadgeComplexity.className = `meta-badge complexity-badge complexity-${this.complexity} pub-badge pub-badge-${this.complexity}`;
            badgesCount++;
          } else {
            this.cardPreviewBadgeComplexity.style.display = 'none';
          }
        } else {
          this.cardPreviewBadgeComplexity.style.display = 'none';
        }
      }

      if (this.cardPreviewBadges) {
        this.cardPreviewBadges.style.display = badgesCount > 0 ? 'flex' : 'none';
      }

      // 4. Cover
      if (this.cardPreviewCover) {
        if (this.coverDataUrl) {
          this.cardPreviewCover.style.display = 'block';
          this.cardPreviewCover.classList.add('is-loaded');
          this.cardPreviewCover.innerHTML = `<img src="${this.coverDataUrl}" alt="Обложка статьи" class="card-cover-img pub-preview-img">`;
        } else {
          this.cardPreviewCover.style.display = 'none';
          this.cardPreviewCover.classList.remove('is-loaded');
          this.cardPreviewCover.innerHTML = '';
        }
      }

      // 5. Description
      if (this.cardPreviewDesc) {
        const rawDesc = this.description ? this.description.trim() : '';
        this.cardPreviewDesc.textContent = rawDesc || 'Краткое описание публикации появится здесь...';
      }

      // 6. Keywords
      if (this.cardPreviewTags) {
        if (this.keywords && this.keywords.length > 0) {
          this.cardPreviewTags.style.display = 'flex';
          const maxVisible = 3;
          const visible = this.keywords.slice(0, maxVisible);
          const hiddenCount = this.keywords.length - visible.length;
          let tagsHtml = '';
          visible.forEach(tag => {
            tagsHtml += `<button type="button" class="tag-chip" tabindex="-1">#${this.escapeHtml(tag)}</button>`;
          });
          if (hiddenCount > 0) {
            tagsHtml += `<span class="tag-expand-btn">+${hiddenCount} еще</span>`;
          }
          this.cardPreviewTags.innerHTML = tagsHtml;
        } else {
          this.cardPreviewTags.style.display = 'none';
          this.cardPreviewTags.innerHTML = '';
        }
      }

      // 7. Reading Time
      if (this.cardPreviewTime) {
        const text = this.editor ? this.editor.getText().trim() : '';
        const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
        const minutes = Math.max(1, Math.ceil(words / 200));
        this.cardPreviewTime.textContent = `~${minutes} мин чтения`;
      }
    }

    /* ==========================================================================
       Settings Persistence & DraftsManager Integration
       ========================================================================== */
    getSettings() {
      return {
        audience: this.audience,
        targetAudience: this.audience,
        topics: [...this.topics],
        keywords: [...this.keywords],
        format: (this.format === 'not_specified' || !this.format) ? null : this.format,
        complexity: this.complexity || 'none',
        description: this.description,
        isDescriptionCustom: this.isDescriptionCustom,
        coverDataUrl: this.coverDataUrl,
        rawCoverImageSource: this.rawCoverImageSource,
        cropParams: this.cropParams ? { ...this.cropParams } : { zoom: 1, panX: 0, panY: 0 },
        coverMeta: this.coverMeta,
        status: this.status
      };
    }

    loadSettings(settings) {
      if (!settings || typeof settings !== 'object') {
        this.resetSettings();
        return;
      }

      this.audience = settings.targetAudience || settings.audience || null;
      this.topics = Array.isArray(settings.topics) ? [...settings.topics] : [];
      this.keywords = Array.isArray(settings.keywords) ? [...settings.keywords] : [];
      this.format = settings.format || 'not_specified';
      this.complexity = settings.complexity || 'none';
      this.description = typeof settings.description === 'string' ? settings.description : '';
      this.isDescriptionCustom = Boolean(settings.isDescriptionCustom || (settings.description && settings.description.length > 0));
      this.coverDataUrl = settings.coverDataUrl || null;
      this.rawCoverImageSource = settings.rawCoverImageSource || null;
      this.cropParams = settings.cropParams || { zoom: 1, panX: 0, panY: 0 };
      this.coverMeta = settings.coverMeta || null;
      this.status = settings.status || 'draft';

      if (this.rawCoverImageSource) {
        const img = new Image();
        img.onload = () => {
          this.rawCoverImage = img;
        };
        img.src = this.rawCoverImageSource;
      } else if (this.coverDataUrl) {
        const img = new Image();
        img.onload = () => {
          this.rawCoverImage = img;
        };
        img.src = this.coverDataUrl;
      } else {
        this.rawCoverImage = null;
      }

      this.render();
      this.updateCardPreview();
      this.updateReadinessUI();
    }

    resetSettings() {
      this.audience = null;
      this.topics = [];
      this.keywords = [];
      this.format = 'not_specified';
      this.complexity = 'none';
      this.description = '';
      this.isDescriptionCustom = false;
      this.coverDataUrl = null;
      this.rawCoverImageSource = null;
      this.cropParams = { zoom: 1, panX: 0, panY: 0 };
      this.coverMeta = null;
      this.rawCoverImage = null;
      this.previousCoverState = null;
      this.status = 'draft';

      this.render();
      this.updateCardPreview();
      this.updateReadinessUI();
    }

    /* ==========================================================================
       Validation & Submission to Moderation Queue
       ========================================================================== */
    validate() {
      // Commit any uncommitted keyword text
      this.commitUncommittedKeyword();

      let isValid = true;
      let firstInvalidEl = null;

      // 1. Title validation
      const title = (this.titleInput ? this.titleInput.value : '').trim();
      if (!title) {
        isValid = false;
      }

      // 2. Text validation
      const text = this.editor ? this.editor.getText() : '';
      if (!/[a-zA-Zа-яёА-ЯЁ0-9]/.test(text)) {
        isValid = false;
      }

      // 3. Audience validation
      if (!this.audience) {
        isValid = false;
        if (this.audienceErrorEl) {
          this.audienceErrorEl.textContent = 'Пожалуйста, выберите целевую аудиторию статьи.';
        }
        if (!firstInvalidEl) firstInvalidEl = this.audienceSearchInput || this.audienceListEl;
      } else {
        if (this.audienceErrorEl) this.audienceErrorEl.textContent = '';
      }

      // 4. Topics validation (1 to 5)
      if (this.topics.length < this.config.LIMITS.TOPICS_MIN || this.topics.length > this.config.LIMITS.TOPICS_MAX) {
        isValid = false;
        if (this.topicsErrorEl) {
          this.topicsErrorEl.textContent = `Выберите от ${this.config.LIMITS.TOPICS_MIN} до ${this.config.LIMITS.TOPICS_MAX} тем публикации.`;
        }
        if (!firstInvalidEl) firstInvalidEl = this.topicsSearchInput || this.topicsAvailableEl;
      } else {
        if (this.topicsErrorEl) this.topicsErrorEl.textContent = '';
      }

      // 5. Keywords validation (1 to 10)
      if (this.keywords.length < this.config.LIMITS.KEYWORDS_MIN || this.keywords.length > this.config.LIMITS.KEYWORDS_MAX) {
        isValid = false;
        if (this.keywordsErrorEl) {
          this.keywordsErrorEl.textContent = `Укажите от ${this.config.LIMITS.KEYWORDS_MIN} до ${this.config.LIMITS.KEYWORDS_MAX} ключевых фраз.`;
        }
        if (!firstInvalidEl) firstInvalidEl = this.keywordsInput;
      } else {
        if (this.keywordsErrorEl) this.keywordsErrorEl.textContent = '';
      }

      // 6. Description validation (50 to 500 chars)
      const descLen = this.description ? this.description.trim().length : 0;
      if (descLen < this.config.LIMITS.DESCRIPTION_MIN || descLen > this.config.LIMITS.DESCRIPTION_MAX) {
        isValid = false;
        if (this.descriptionErrorEl) {
          this.descriptionErrorEl.textContent = `Краткое описание должно содержать от ${this.config.LIMITS.DESCRIPTION_MIN} до ${this.config.LIMITS.DESCRIPTION_MAX} символов (сейчас ${descLen}).`;
        }
        if (!firstInvalidEl) firstInvalidEl = this.descriptionInput;
      } else {
        if (this.descriptionErrorEl) this.descriptionErrorEl.textContent = '';
      }

      if (!isValid && firstInvalidEl) {
        firstInvalidEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        firstInvalidEl.focus();
      }

      return isValid;
    }

    async submitToModeration() {
      if (this.isSubmitting) return;

      if (!this.validate()) {
        if (window.EditorApp && window.EditorApp.showToast) {
          window.EditorApp.showToast('Пожалуйста, заполните все обязательные поля публикации', 'danger');
        }
        return;
      }

      this.isSubmitting = true;
      const originalSubmitText = this.btnPubSubmit.innerHTML;
      this.btnPubSubmit.disabled = true;
      this.btnPubSubmit.innerHTML = `
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="spin" style="margin-right: 6px; animation: spin 1s linear infinite;">
          <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
          <path d="M12 2a10 10 0 0 1 10 10"></path>
        </svg>
        <span>Отправляем…</span>
      `;

      const idempotencyKey = 'pub_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
      const draftId = (window.EditorApp && window.EditorApp.Drafts) ? window.EditorApp.Drafts.currentDraftId : ('draft_' + Date.now());

      const title = (this.titleInput ? this.titleInput.value : '').trim();
      const delta = this.editor ? this.editor.getContents() : null;
      const html = (window.EditorApp && window.EditorApp.Converter)
        ? window.EditorApp.Converter.sanitizeHTML(this.editor.root.innerHTML)
        : (this.editor ? this.editor.root.innerHTML : '');

      const settings = this.getSettings();
      const payload = {
        idempotencyKey: idempotencyKey,
        draftId: draftId,
        title: title,
        delta: delta,
        html: html,
        settings: settings,
        publicationSettings: settings,
        submittedAt: new Date().toISOString()
      };

      try {
        const response = await fetch('/api/moderation/submit', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Idempotency-Key': idempotencyKey
          },
          body: JSON.stringify(payload)
        });

        if (response.ok) {
          this.status = 'in_moderation';

          // Save draft locally with in_moderation status
          if (window.EditorApp && window.EditorApp.Drafts) {
            await window.EditorApp.Drafts.saveCurrent({ isManual: false });
          }

          if (window.EditorApp && window.EditorApp.showToast) {
            window.EditorApp.showToast('Статья отправлена на модерацию', 'success');
          }

          this.closeModal(false);
        } else {
          let errText = 'Ошибка сервера при отправке на модерацию';
          try {
            const errData = await response.json();
            if (errData && errData.message) errText = errData.message;
          } catch (e) {
            errText = `Ошибка HTTP ${response.status}: ${response.statusText}`;
          }

          if (window.EditorApp && window.EditorApp.showToast) {
            window.EditorApp.showToast(errText, 'danger');
          }
        }
      } catch (networkErr) {
        console.warn('Network error or server unavailable during moderation submit:', networkErr);
        // Offline-friendly fallback: preserve local draft and inform author
        if (window.EditorApp && window.EditorApp.Drafts) {
          await window.EditorApp.Drafts.saveCurrent({ isManual: false });
        }
        if (window.EditorApp && window.EditorApp.showToast) {
          window.EditorApp.showToast('Сервер модерации временно недоступен. Черновик сохранен локально, повторите отправку позже.', 'danger');
        }
      } finally {
        this.isSubmitting = false;
        this.btnPubSubmit.disabled = false;
        this.btnPubSubmit.innerHTML = originalSubmitText;
      }
    }

    escapeHTML(str) {
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }
  }

  window.PublicationManager = PublicationManager;

})(window);
