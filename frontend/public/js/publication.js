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
          COVER_HEIGHT: 350
        }
      };

      // Publication settings state
      this.audience = null; // string id
      this.topics = []; // array of topic ids (1-5)
      this.keywords = []; // array of keyword strings (1-10)
      this.format = 'not_specified'; // format id or 'not_specified'
      this.complexity = 'none'; // 'none' | 'easy' | 'medium' | 'hard'
      this.materialType = 'article'; // 'article' | 'post' | 'news' | 'question'
      this.description = ''; // plain text 50-500 chars
      this.isDescriptionCustom = false;
      this.coverDataUrl = null; // cropped 780x350 data URL
      this.rawCoverImageSource = null; // original Data URL string
      this.cropParams = { zoom: 1, panX: 0, panY: 0 };
      this.coverPosition = null; // CSS object-position e.g. '50% 30%'
      this.focalPoint = null; // focal point e.g. '50% 30%'
      this.objectPosition = null; // alias for coverPosition
      this.previousCoverState = null; // backup for cancel/replace error recovery
      this.coverMeta = null; // metadata { originalName, originalWidth, originalHeight, isGif }
      this.status = 'draft'; // 'draft' | 'in_moderation'

      // Entity & Club attribution state
      this.companyId = null;
      this.companyName = null;
      this.clubId = null;
      this.clubTitle = null;

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
      this.initEntityOptions();
      this.updateReadinessUI();

      // Check ?type=question from URL
      try {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('type') === 'question') {
          this.setMaterialType('question');
        }
      } catch (e) {}
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
      this.formatDropdownWrap = document.getElementById('pub-format-dropdown-wrap');
      this.formatTriggerBtn = document.getElementById('pub-format-trigger');
      this.formatTriggerText = document.getElementById('pub-format-trigger-text');
      this.formatOptionsEl = document.getElementById('pub-format-options');
      this.isFormatDropdownOpen = false;

      // Section 5: Complexity
      this.complexityOptionsEl = document.getElementById('pub-complexity-options');
      this.complexityDescEl = document.getElementById('pub-complexity-desc');

      // Section 6: Material Type
      this.materialTypeOptionsEl = document.getElementById('pub-material-type-options');

      // Section 7: Feed Display & Cover
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
      this.cardPreviewLike = document.getElementById('preview-card-like');
      this.cardPreviewComments = document.getElementById('preview-card-comments');

      // Section 8: Entity (Company & Club)
      this.companySelect = document.getElementById('pub-company-select');
      this.clubSelect = document.getElementById('pub-club-select');
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
          this.checkH1Duplicate();
        });
      }

      if (this.editor) {
        this.editor.on('text-change', () => {
          this.updateReadinessUI();
          this.updateCardPreview();
        });
        if (this.editor.root) {
          this.editor.root.addEventListener('paste', () => {
            setTimeout(() => this.checkH1Duplicate(), 100);
          });
        }
      }

      // H1 Duplicate Warning Banner buttons (Issue #83)
      const btnConvertH2 = document.getElementById('btnConvertH2');
      if (btnConvertH2) btnConvertH2.addEventListener('click', () => this.convertH1ToH2());

      const btnRemoveH1 = document.getElementById('btnRemoveDuplicateH1');
      if (btnRemoveH1) btnRemoveH1.addEventListener('click', () => this.removeDuplicateH1());

      const btnDismissH1 = document.getElementById('btnDismissH1Warning');
      if (btnDismissH1) btnDismissH1.addEventListener('click', () => this.dismissH1Warning());

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

      // Section 4: Format dropdown trigger and outside click
      if (this.formatTriggerBtn) {
        this.formatTriggerBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.toggleFormatDropdown();
        });
      }

      if (this.formatDropdownWrap) {
        this.formatDropdownWrap.addEventListener('keydown', (e) => {
          if (!this.isFormatDropdownOpen) {
            if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
              if (document.activeElement === this.formatTriggerBtn) {
                e.preventDefault();
                this.openFormatDropdown();
              }
            }
            return;
          }

          if (e.key === 'Escape') {
            e.preventDefault();
            e.stopPropagation();
            this.closeFormatDropdown(true);
            return;
          }

          const options = Array.from(this.formatOptionsEl ? this.formatOptionsEl.querySelectorAll('.pub-format-option') : []);
          if (options.length === 0) return;
          const currentIndex = options.indexOf(document.activeElement);

          if (e.key === 'ArrowDown') {
            e.preventDefault();
            const nextIndex = (currentIndex + 1) % options.length;
            if (options[nextIndex]) options[nextIndex].focus();
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            const prevIndex = (currentIndex - 1 + options.length) % options.length;
            if (options[prevIndex]) options[prevIndex].focus();
          } else if (e.key === 'Enter' || e.key === ' ') {
            if (document.activeElement && document.activeElement.classList.contains('pub-format-option')) {
              e.preventDefault();
              const fid = document.activeElement.getAttribute('data-format-id');
              this.setFormat(fid);
              this.closeFormatDropdown(true);
            }
          }
        });
      }

      // Close format dropdown on outside click
      document.addEventListener('click', (e) => {
        if (this.isFormatDropdownOpen && this.formatDropdownWrap && !this.formatDropdownWrap.contains(e.target)) {
          this.closeFormatDropdown();
        }
      });

      // Section 5: Complexity change
      if (this.complexityOptionsEl) {
        this.complexityOptionsEl.addEventListener('click', (e) => {
          const btn = e.target.closest('[data-complexity]');
          if (!btn) return;
          const level = btn.getAttribute('data-complexity');
          this.setComplexity(level);
        });
      }

      // Section 6: Material Type change
      if (this.materialTypeOptionsEl) {
        this.materialTypeOptionsEl.addEventListener('click', (e) => {
          const btn = e.target.closest('.pub-segment-btn');
          if (!btn) return;
          const type = btn.getAttribute('data-type') || btn.getAttribute('data-material-type');
          if (type) {
            this.setMaterialType(type);
          }
        });
      }

      // Section 7: Cover upload & dropzone
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

      // Section 8: Entity selects
      if (this.companySelect) {
        this.companySelect.addEventListener('change', () => {
          this.companyId = this.companySelect.value || null;
          const opt = this.companySelect.selectedOptions ? this.companySelect.selectedOptions[0] : null;
          this.companyName = (opt && this.companyId) ? opt.textContent : null;
          this.updateCardPreview();
        });
      }

      if (this.clubSelect) {
        this.clubSelect.addEventListener('change', () => {
          this.clubId = this.clubSelect.value || null;
          const opt = this.clubSelect.selectedOptions ? this.clubSelect.selectedOptions[0] : null;
          this.clubTitle = (opt && this.clubId) ? opt.textContent : null;
          this.updateCardPreview();
        });
      }
    }

    initEntityOptions() {
      const urlParams = new URLSearchParams(window.location.search);
      const preselectedClub = urlParams.get('clubId') || urlParams.get('club');
      const preselectedCompany = urlParams.get('companyId') || urlParams.get('company');

      if (this.companySelect) {
        fetch('/api/companies?manageable=1')
          .then(res => res.json())
          .then(data => {
            if (data && data.success && data.companies) {
              data.companies.forEach(comp => {
                const opt = document.createElement('option');
                opt.value = comp.id;
                opt.textContent = comp.name;
                this.companySelect.appendChild(opt);
              });
              if (preselectedCompany) {
                this.companySelect.value = preselectedCompany;
                if (this.companySelect.value === preselectedCompany) {
                  this.companyId = preselectedCompany;
                  const sel = this.companySelect.selectedOptions ? this.companySelect.selectedOptions[0] : null;
                  if (sel) this.companyName = sel.textContent;
                  this.updateCardPreview();
                } else {
                  this.companyId = null;
                  this.companyName = null;
                }
              }
            }
          })
          .catch(() => {});
      }

      if (this.clubSelect) {
        fetch('/api/clubs')
          .then(res => res.json())
          .then(data => {
            if (data && data.success && data.clubs) {
              data.clubs.forEach(club => {
                const opt = document.createElement('option');
                opt.value = club.id;
                opt.textContent = club.title;
                this.clubSelect.appendChild(opt);
              });
              if (preselectedClub) {
                this.clubSelect.value = preselectedClub;
                this.clubId = preselectedClub;
                const sel = this.clubSelect.selectedOptions ? this.clubSelect.selectedOptions[0] : null;
                if (sel) this.clubTitle = sel.textContent;
                this.updateCardPreview();
              }
            }
          })
          .catch(() => {});
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

      this.closeFormatDropdown();
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

      this.closeFormatDropdown();

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
        if (this.isFormatDropdownOpen) {
          e.preventDefault();
          e.stopPropagation();
          this.closeFormatDropdown(true);
          return;
        }
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
      this.renderMaterialTypes();
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
       Section 4: Format Dropdown (formats + 'not_specified')
       ========================================================================== */
    openFormatDropdown() {
      if (!this.formatOptionsEl || !this.formatTriggerBtn) return;
      this.isFormatDropdownOpen = true;
      this.formatOptionsEl.style.display = 'flex';
      this.formatOptionsEl.classList.add('is-open');
      this.formatTriggerBtn.setAttribute('aria-expanded', 'true');
      this.formatTriggerBtn.classList.add('is-open');

      const selectedOpt = this.formatOptionsEl.querySelector('.pub-format-option.is-selected') ||
                          this.formatOptionsEl.querySelector('.pub-format-option');
      if (selectedOpt) {
        selectedOpt.focus();
      }
    }

    closeFormatDropdown(returnFocus = false) {
      if (!this.formatOptionsEl || !this.formatTriggerBtn) return;
      this.isFormatDropdownOpen = false;
      this.formatOptionsEl.style.display = 'none';
      this.formatOptionsEl.classList.remove('is-open');
      this.formatTriggerBtn.setAttribute('aria-expanded', 'false');
      this.formatTriggerBtn.classList.remove('is-open');
      if (returnFocus && this.formatTriggerBtn) {
        this.formatTriggerBtn.focus();
      }
    }

    toggleFormatDropdown() {
      if (this.isFormatDropdownOpen) {
        this.closeFormatDropdown();
      } else {
        this.openFormatDropdown();
      }
    }

    updateFormatTriggerText() {
      if (!this.formatTriggerText) return;
      const currentFmtId = this.format;
      let currentTitle = 'Не указан';
      if (currentFmtId && currentFmtId !== 'not_specified' && currentFmtId !== 'none') {
        const formats = (window.PublicationConfig && Array.isArray(window.PublicationConfig.FORMATS))
          ? window.PublicationConfig.FORMATS
          : (this.config.FORMATS || []);
        const found = formats.find(f => f.id === currentFmtId);
        if (found) {
          currentTitle = found.title;
        } else {
          currentTitle = currentFmtId;
        }
      }
      this.formatTriggerText.textContent = currentTitle;
    }

    renderFormats() {
      if (!this.formatOptionsEl) return;

      const formats = (window.PublicationConfig && Array.isArray(window.PublicationConfig.FORMATS))
        ? window.PublicationConfig.FORMATS
        : (this.config.FORMATS || []);

      const isNotSpecified = !this.format || this.format === 'not_specified' || this.format === 'none';

      let html = `
        <div class="pub-format-option pub-format-card ${isNotSpecified ? 'is-selected' : ''}" role="option" aria-selected="${isNotSpecified ? 'true' : 'false'}" data-format-id="not_specified" tabindex="0">
          <div class="pub-format-option-info">
            <div class="pub-format-title">Не указан</div>
            <div class="pub-format-desc">Формат статьи не выбран</div>
          </div>
          ${isNotSpecified ? `
            <span class="pub-format-check-icon" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </span>
          ` : ''}
        </div>
      `;

      formats.forEach(fmt => {
        const isSelected = this.format === fmt.id;
        html += `
          <div class="pub-format-option pub-format-card ${isSelected ? 'is-selected' : ''}" role="option" aria-selected="${isSelected ? 'true' : 'false'}" data-format-id="${this.escapeHtml(fmt.id)}" tabindex="0">
            <div class="pub-format-option-info">
              <div class="pub-format-title">${this.escapeHtml(fmt.title)}</div>
              <div class="pub-format-desc">${this.escapeHtml(fmt.description || '')}</div>
            </div>
            ${isSelected ? `
              <span class="pub-format-check-icon" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              </span>
            ` : ''}
          </div>
        `;
      });

      this.formatOptionsEl.innerHTML = html;

      this.formatOptionsEl.querySelectorAll('.pub-format-option').forEach(el => {
        el.addEventListener('click', (e) => {
          e.stopPropagation();
          const fid = el.getAttribute('data-format-id');
          this.setFormat(fid);
          this.closeFormatDropdown(true);
        });
      });

      this.updateFormatTriggerText();
    }

    setFormat(fmtId) {
      this.format = fmtId;
      this.renderFormats();
      this.updateFormatTriggerText();
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
       Section 6: Material Type (article, post, news, question)
       ========================================================================== */
    renderMaterialTypes() {
      if (!this.materialTypeOptionsEl) return;
      this.materialTypeOptionsEl.querySelectorAll('.pub-segment-btn').forEach(btn => {
        const type = btn.getAttribute('data-type') || btn.getAttribute('data-material-type');
        if (type === this.materialType) {
          btn.classList.add('is-active');
        } else {
          btn.classList.remove('is-active');
        }
      });
    }

    setMaterialType(type) {
      if (type === 'article' || type === 'post' || type === 'news') {
        type = 'publication';
      }
      this.materialType = type || 'publication';
      this.renderMaterialTypes();

      // Question scenarios: prompts & security warning
      const questionGuidancePrompts = '1. Что вы пытались сделать?\n2. Что пошло не так (ошибка или неожиданное поведение)?\n3. Какой результат ожидался?';
      const questionSecurityWarning = 'Внимание: никогда не публикуйте приватные ключи, seed-фразы кошельков и боевые секреты смарт-контрактов.';

      const descInput = document.getElementById('pub-description');
      let questionSecWarning = document.getElementById('pub-question-security-warning');

      if (type === 'question' || this.materialType === 'question') {
        if (descInput) {
          descInput.placeholder = questionGuidancePrompts;
        }
        if (!questionSecWarning && descInput && descInput.parentNode) {
          questionSecWarning = document.createElement('div');
          questionSecWarning.id = 'pub-question-security-warning';
          questionSecWarning.className = 'feed-settings-error-msg';
          questionSecWarning.style.cssText = 'background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.25); color: #f87171; padding: 10px 14px; border-radius: 6px; font-size: 0.82rem; margin-top: 10px; display: block;';
          questionSecWarning.textContent = questionSecurityWarning;
          descInput.parentNode.insertBefore(questionSecWarning, descInput.nextSibling);
        } else if (questionSecWarning) {
          questionSecWarning.style.display = 'block';
        }
      } else {
        if (descInput) {
          descInput.placeholder = 'Краткое описание (лид) публикации...';
        }
        if (questionSecWarning) {
          questionSecWarning.style.display = 'none';
        }
      }

      this.updateCardPreview();
    }

    /* ==========================================================================
       Section 7: Cover Image & Canvas Cropper (39:22 / 780x440)
       ========================================================================== */
    saveCoverBackup() {
      this.previousCoverState = {
        coverDataUrl: this.coverDataUrl,
        rawCoverImage: this.rawCoverImage,
        rawCoverImageSource: this.rawCoverImageSource,
        cropParams: this.cropParams ? { ...this.cropParams } : { zoom: 1, panX: 0, panY: 0 },
        coverPosition: this.coverPosition,
        focalPoint: this.focalPoint,
        objectPosition: this.objectPosition,
        coverMeta: this.coverMeta ? { ...this.coverMeta } : null
      };
    }

    restoreCoverBackup() {
      if (this.previousCoverState) {
        this.coverDataUrl = this.previousCoverState.coverDataUrl;
        this.rawCoverImage = this.previousCoverState.rawCoverImage;
        this.rawCoverImageSource = this.previousCoverState.rawCoverImageSource;
        this.cropParams = this.previousCoverState.cropParams ? { ...this.previousCoverState.cropParams } : { zoom: 1, panX: 0, panY: 0 };
        this.coverPosition = this.previousCoverState.coverPosition || null;
        this.focalPoint = this.previousCoverState.focalPoint || null;
        this.objectPosition = this.previousCoverState.objectPosition || null;
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
        TARGET_HEIGHT: 350,
        ASPECT_RATIO_VALUE: 780 / 350
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

          // Check aspect ratio (780:350 with ~0.02 epsilon)
          const targetRatio = coverConfig.ASPECT_RATIO_VALUE || (780 / 350);
          const imgRatio = img.naturalWidth / img.naturalHeight;
          const is78x35 = Math.abs(imgRatio - targetRatio) <= 0.02;

          if (is78x35) {
            // Already 780:350 -> save whole frame by default without forced cropping modal
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
            // Proportions differ -> open cropper with fixed 780:350
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

      if (this.cropperCanvas) {
        const coverConfig = (window.PublicationConfig && window.PublicationConfig.COVER) || {
          TARGET_WIDTH: 780,
          TARGET_HEIGHT: 350
        };
        this.cropperCanvas.width = coverConfig.TARGET_WIDTH || 780;
        this.cropperCanvas.height = coverConfig.TARGET_HEIGHT || 350;
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
        TARGET_HEIGHT: 350
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

      // Compute and persist focal point / cover position
      const focalX = Math.round(Math.max(0, Math.min(100, ((targetW / 2 - drawX) / drawW) * 100)));
      const focalY = Math.round(Math.max(0, Math.min(100, ((targetH / 2 - drawY) / drawH) * 100)));
      this.coverPosition = `${focalX}% ${focalY}%`;
      this.focalPoint = `${focalX}% ${focalY}%`;
      this.objectPosition = `${focalX}% ${focalY}%`;

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
      this.coverPosition = null;
      this.focalPoint = null;
      this.objectPosition = null;
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
        if (this.coverImg) {
          this.coverImg.src = this.coverDataUrl;
          if (this.coverPosition) {
            this.coverImg.style.objectPosition = this.coverPosition;
          } else {
            this.coverImg.style.objectPosition = '';
          }
        }
      } else {
        this.coverDropzone.style.display = 'flex';
        this.coverPreviewWrapper.style.display = 'none';
        if (this.coverImg) {
          this.coverImg.src = '';
          this.coverImg.style.objectPosition = '';
        }
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
      if (window.SmartContractumCard && typeof window.SmartContractumCard.renderCardInnerHtml === 'function' && this.cardPreview) {
        const authorName = (window.currentUser && window.currentUser.name) ||
          (window.EditorApp && window.EditorApp.authorName) ||
          'Автор платформы';
        const authorRole = (window.currentUser && window.currentUser.role) || '';
        const authorInitials = authorName.split(/\s+/).map(p => p[0]).filter(Boolean).slice(0, 2).join('').toUpperCase() || 'АП';
        const rawTitle = this.titleInput ? this.titleInput.value.trim() : '';
        const rawDesc = this.description ? this.description.trim() : '';
        const text = this.editor ? this.editor.getText().trim() : '';
        const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
        const minutes = Math.max(1, Math.ceil(words / 200));

        const previewItem = {
          title: rawTitle || 'Заголовок публикации',
          author: authorName,
          authorInitials: authorInitials,
          date: 'Недавно',
          topics: (this.topics && this.topics.length > 0) ? this.topics : [],
          topic: (this.topics && this.topics.length > 0) ? this.topics[0] : null,
          format: (this.format && this.format !== 'not_specified' && this.format !== 'none') ? this.format : null,
          materialType: (this.materialType === 'question') ? 'question' : 'publication',
          type: (this.materialType === 'question') ? 'question' : 'publication',
          coverImage: this.coverDataUrl || null,
          coverPosition: this.coverPosition || null,
          focalPoint: this.focalPoint || null,
          objectPosition: this.objectPosition || this.coverPosition || null,
          description: rawDesc || 'Краткое описание публикации появится здесь...',
          readingTime: `~${minutes} мин чтения`,
          likesCount: 0,
          hasLiked: false,
          commentsCount: 0,
          companyName: this.companyName || null,
          clubTitle: this.clubTitle || null
        };

        this.cardPreview.innerHTML = window.SmartContractumCard.renderCardInnerHtml(previewItem, { isPreview: true });

        // Update cached references
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
        this.cardPreviewLike = document.getElementById('preview-card-like');
        this.cardPreviewComments = document.getElementById('preview-card-comments');
        return;
      }

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
        materialType: (this.materialType === 'question') ? 'question' : 'publication',
        type: (this.materialType === 'question') ? 'question' : 'publication',
        description: this.description,
        isDescriptionCustom: this.isDescriptionCustom,
        coverDataUrl: this.coverDataUrl,
        coverPosition: this.coverPosition || null,
        focalPoint: this.focalPoint || null,
        objectPosition: this.objectPosition || this.coverPosition || null,
        rawCoverImageSource: this.rawCoverImageSource,
        cropParams: this.cropParams ? { ...this.cropParams } : { zoom: 1, panX: 0, panY: 0 },
        coverMeta: this.coverMeta,
        companyId: this.companyId || null,
        companyName: this.companyName || null,
        clubId: this.clubId || null,
        clubTitle: this.clubTitle || null,
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
      let loadedType = settings.materialType || settings.type || 'publication';
      if (loadedType === 'article' || loadedType === 'post' || loadedType === 'news') {
        loadedType = 'publication';
      }
      this.materialType = loadedType;
      this.description = typeof settings.description === 'string' ? settings.description : '';
      this.isDescriptionCustom = Boolean(settings.isDescriptionCustom || (settings.description && settings.description.length > 0));
      this.coverDataUrl = settings.coverDataUrl || null;
      this.coverPosition = settings.coverPosition || settings.objectPosition || null;
      this.focalPoint = settings.focalPoint || null;
      this.objectPosition = settings.objectPosition || settings.coverPosition || null;
      this.rawCoverImageSource = settings.rawCoverImageSource || null;
      this.cropParams = settings.cropParams || { zoom: 1, panX: 0, panY: 0 };
      this.coverMeta = settings.coverMeta || null;
      this.companyId = settings.companyId || null;
      this.companyName = settings.companyName || null;
      this.clubId = settings.clubId || null;
      this.clubTitle = settings.clubTitle || null;
      this.status = settings.status || 'draft';

      if (this.companySelect) this.companySelect.value = this.companyId || '';
      if (this.clubSelect) this.clubSelect.value = this.clubId || '';

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
      this.setMaterialType(this.materialType);
      this.updateCardPreview();
      this.updateReadinessUI();
    }

    resetSettings() {
      this.audience = null;
      this.topics = [];
      this.keywords = [];
      this.format = 'not_specified';

      let defaultMaterialType = 'publication';
      try {
        if (typeof window !== 'undefined' && window.location && window.location.search) {
          const urlParams = new URLSearchParams(window.location.search);
          if (urlParams.get('type') === 'question' || urlParams.get('mode') === 'question') {
            defaultMaterialType = 'question';
          }
        }
      } catch (_) {}

      this.materialType = defaultMaterialType;
      this.description = '';
      this.isDescriptionCustom = false;
      this.coverDataUrl = null;
      this.coverPosition = null;
      this.focalPoint = null;
      this.objectPosition = null;
      this.rawCoverImageSource = null;
      this.cropParams = { zoom: 1, panX: 0, panY: 0 };
      this.coverMeta = null;
      this.rawCoverImage = null;
      this.previousCoverState = null;
      this.companyId = null;
      this.companyName = null;
      this.clubId = null;
      this.clubTitle = null;
      this.status = 'draft';

      if (this.companySelect) this.companySelect.value = '';
      if (this.clubSelect) this.clubSelect.value = '';

      this.closeFormatDropdown();
      this.render();
      this.setMaterialType(defaultMaterialType);
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

      const draftsManager = (window.EditorApp && window.EditorApp.Drafts)
        ? window.EditorApp.Drafts
        : (this.draftsManager || null);
      const draftId = draftsManager ? draftsManager.currentDraftId : ('draft_' + Date.now());

      let idempotencyKey = '';
      if (draftsManager && typeof draftsManager.getSubmissionIdempotencyKey === 'function') {
        idempotencyKey = draftsManager.getSubmissionIdempotencyKey();
      } else {
        if (!this._fallbackIdempotencyKeys) {
          this._fallbackIdempotencyKeys = {};
        }
        if (!this._fallbackIdempotencyKeys[draftId]) {
          this._fallbackIdempotencyKeys[draftId] = 'pub_' + draftId + '_rev_' + Date.now();
        }
        idempotencyKey = this._fallbackIdempotencyKeys[draftId];
      }

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
          let resData = null;
          try {
            resData = await response.json();
          } catch (_) {}

          this.status = (resData && resData.status) ? resData.status : 'in_moderation';

          // Save draft locally with in_moderation status
          if (window.EditorApp && window.EditorApp.Drafts) {
            await window.EditorApp.Drafts.saveCurrent({ isManual: false });
          }

          if (window.EditorApp && window.EditorApp.showToast) {
            if (resData && resData.isDuplicate) {
              window.EditorApp.showToast('Статья уже находится на модерации', 'info');
            } else {
              window.EditorApp.showToast('Статья отправлена на модерацию', 'success');
            }
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

    normalizeHeading(text) {
      if (!text) return '';
      let str = String(text).replace(/<[^>]*>/g, ' ');
      str = str.replace(/^#+\s*/, '');
      str = str.toLowerCase();
      str = str.replace(/[.,\/#!$%\^&\*;:{}=\-_`~()?"'«»\u2013\u2014]/g, ' ');
      str = str.replace(/\s+/g, ' ').trim();
      return str;
    }

    checkH1Duplicate() {
      const banner = document.getElementById('h1DuplicateWarningBanner');
      if (!banner) return false;

      const title = (this.titleInput ? this.titleInput.value : '').trim();
      const normTitle = this.normalizeHeading(title);
      if (!normTitle) {
        banner.style.display = 'none';
        return false;
      }

      const editorRoot = (this.editor && this.editor.root) ? this.editor.root : document.getElementById('editor');
      if (!editorRoot) return false;

      // Find first non-empty block
      let firstEl = null;
      const children = editorRoot.children;
      for (let i = 0; i < children.length; i++) {
        const el = children[i];
        if (el.textContent && el.textContent.trim().length > 0) {
          firstEl = el;
          break;
        }
      }

      if (firstEl && firstEl.tagName === 'H1') {
        const normHeading = this.normalizeHeading(firstEl.textContent);
        if (normHeading && normHeading === normTitle) {
          banner.style.display = 'flex';
          this.duplicateH1Element = firstEl;
          return true;
        }
      }

      banner.style.display = 'none';
      this.duplicateH1Element = null;
      return false;
    }

    convertH1ToH2() {
      const banner = document.getElementById('h1DuplicateWarningBanner');
      const editorRoot = (this.editor && this.editor.root) ? this.editor.root : document.getElementById('editor');
      let targetEl = this.duplicateH1Element;
      if (!targetEl && editorRoot) {
        const children = editorRoot.children;
        for (let i = 0; i < children.length; i++) {
          if (children[i].tagName === 'H1') {
            targetEl = children[i];
            break;
          }
        }
      }

      if (targetEl && targetEl.tagName === 'H1') {
        const h2 = document.createElement('h2');
        h2.innerHTML = targetEl.innerHTML;
        if (targetEl.className) h2.className = targetEl.className;
        targetEl.replaceWith(h2);

        if (this.editor && typeof this.editor.update === 'function') {
          this.editor.update();
        }
      }

      if (banner) banner.style.display = 'none';
      this.duplicateH1Element = null;
    }

    removeDuplicateH1() {
      const banner = document.getElementById('h1DuplicateWarningBanner');
      const editorRoot = (this.editor && this.editor.root) ? this.editor.root : document.getElementById('editor');
      let targetEl = this.duplicateH1Element;
      if (!targetEl && editorRoot) {
        const children = editorRoot.children;
        for (let i = 0; i < children.length; i++) {
          if (children[i].tagName === 'H1') {
            targetEl = children[i];
            break;
          }
        }
      }

      if (targetEl && targetEl.tagName === 'H1') {
        targetEl.remove();

        if (this.editor && typeof this.editor.update === 'function') {
          this.editor.update();
        }
      }

      if (banner) banner.style.display = 'none';
      this.duplicateH1Element = null;
    }

    dismissH1Warning() {
      const banner = document.getElementById('h1DuplicateWarningBanner');
      if (banner) banner.style.display = 'none';
      this.duplicateH1Element = null;
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
