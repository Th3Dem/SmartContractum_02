/**
 * Dedicated Simplified Question Editor (question-editor.js)
 * SmartContractum - 100% Offline-First, Zero Emojis, Clean Performance.
 */

(function (window) {
  'use strict';

  // Constants
  const DRAFT_STORAGE_KEY = 'smartcontractum_question_draft';
  const MAX_TAGS = 10;
  const MIN_TITLE_LEN = 5;
  const MAX_TITLE_LEN = 250;
  const MIN_DETAILS_LEN = 15;
  const MAX_IMAGE_BYTES = 10 * 1024 * 1024; // 10 MB

  // Application State
  const state = {
    currentUser: null,
    tags: [],
    quill: null,
    draftsManager: null,
    autosaveTimer: null,
    isSubmitting: false
  };

  /* ==========================================================================
     Theme Management
     ========================================================================== */
  function initTheme() {
    const toggleBtn = document.getElementById('btnThemeToggle');

    function applyTheme(theme) {
      document.documentElement.setAttribute('data-theme', theme);
      try {
        localStorage.setItem('ag_theme', theme);
        localStorage.setItem('sc_theme', theme);
      } catch (e) {}

      if (toggleBtn) {
        const isLight = theme === 'light';
        toggleBtn.setAttribute('aria-checked', isLight ? 'true' : 'false');
        toggleBtn.title = isLight
          ? 'Переключить на тёмную тему'
          : 'Переключить на светлую тему';
      }
    }

    let savedTheme = 'dark';
    try {
      savedTheme = localStorage.getItem('ag_theme') || localStorage.getItem('sc_theme') || 'dark';
    } catch (e) {}

    applyTheme(savedTheme);

    if (toggleBtn) {
      toggleBtn.addEventListener('click', function () {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
        const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(nextTheme);
      });
    }
  }

  /* ==========================================================================
     Header Navigation & Create Dropdown
     ========================================================================== */
  function initHeaderControls() {
    const btnCreate = document.getElementById('btnCreateDropdown');
    const createMenu = document.getElementById('feedCreateMenu');

    if (btnCreate && createMenu) {
      btnCreate.addEventListener('click', function (e) {
        e.stopPropagation();
        const isOpen = createMenu.style.display === 'block';
        createMenu.style.display = isOpen ? 'none' : 'block';
        btnCreate.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
      });

      document.addEventListener('click', function (e) {
        if (!btnCreate.contains(e.target) && !createMenu.contains(e.target)) {
          createMenu.style.display = 'none';
          btnCreate.setAttribute('aria-expanded', 'false');
        }
      });
    }

    // Notifications bell dummy handler
    const notifBtn = document.getElementById('headerNotificationsBtn');
    const notifPopup = document.getElementById('headerNotifPopup');
    if (notifBtn && notifPopup) {
      notifBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        const isOpen = notifPopup.style.display === 'block';
        notifPopup.style.display = isOpen ? 'none' : 'block';
        notifBtn.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
      });

      document.addEventListener('click', function (e) {
        if (!notifBtn.contains(e.target) && !notifPopup.contains(e.target)) {
          notifPopup.style.display = 'none';
          notifBtn.setAttribute('aria-expanded', 'false');
        }
      });
    }
  }

  /* ==========================================================================
     Auth Controls & Modal
     ========================================================================== */
  function checkAuthStatus(callback) {
    fetch('/api/auth/status')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.authenticated && data.user) {
          setAuthState(data.user);
        } else {
          setAuthState(null);
        }
        if (callback) callback();
      })
      .catch(function () {
        setAuthState(null);
        if (callback) callback();
      });
  }

  function setAuthState(user) {
    state.currentUser = user;
    window.currentUser = user;

    const userLabel = document.getElementById('headerUserLabel');
    const loginBtn = document.getElementById('headerLoginBtn');

    if (userLabel) {
      userLabel.textContent = user ? user.name : 'Вход';
    }
    if (loginBtn) {
      loginBtn.title = user
        ? 'Вы вошли как ' + user.name + ' (нажмите для выхода)'
        : 'Войти в личный кабинет';
    }
  }

  function openAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) modal.style.display = 'flex';
  }

  function closeAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) modal.style.display = 'none';
  }

  function initAuthControls() {
  if (window.SCAuth && window.SCAuth._initialized) return;

    const loginBtn = document.getElementById('headerLoginBtn');
    if (loginBtn) {
      loginBtn.addEventListener('click', function (e) {
    if (window.SCAuth && window.SCAuth._initialized) return;
        e.preventDefault();
        if (state.currentUser) {
          if (confirm('Вы вошли как «' + state.currentUser.name + '». Выйти из профиля?')) {
            fetch('/api/auth/logout', { method: 'POST' })
              .then(function (res) { return res.json(); })
              .then(function () {
                setAuthState(null);
                showToast('Вы вышли из системы');
              });
          }
        } else {
          openAuthModal();
        }
      });
    }

    const closeBtn = document.getElementById('btnCloseAuthModal');
    if (closeBtn) {
      closeBtn.addEventListener('click', closeAuthModal);
    }

    const authModal = document.getElementById('authModal');
    if (authModal) {
      authModal.addEventListener('click', function (e) {
        if (e.target === authModal) closeAuthModal();
      });
    }

    const btnDemo = document.getElementById('btnAuthLoginDemo');
    if (btnDemo) {
      btnDemo.addEventListener('click', function () {
        fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ userId: 'user_demo' })
        })
          .then(function (res) { return res.json(); })
          .then(function (data) {
            if (data && data.success && data.user) {
              setAuthState(data.user);
              closeAuthModal();
              showToast('Авторизован как Демо Пользователь');
              clearFormError();
            }
          });
      });
    }

    const btnSubmitLogin = document.getElementById('btnAuthLoginSubmit');
    const inputLogin = document.getElementById('authUserIdInput');
    if (btnSubmitLogin && inputLogin) {
      btnSubmitLogin.addEventListener('click', function () {
        const val = inputLogin.value.trim();
        if (!val) return;
        fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ userId: val })
        })
          .then(function (res) { return res.json(); })
          .then(function (data) {
            if (data && data.success && data.user) {
              setAuthState(data.user);
              closeAuthModal();
              showToast('Авторизован как ' + data.user.name);
              clearFormError();
            }
          });
      });
    }
  }

  /* ==========================================================================
     Toast Notifications
     ========================================================================== */
  function showToast(message, type = 'info') {
    const toast = document.getElementById('questionToast');
    if (!toast) return;

    toast.textContent = message;
    toast.className = 'feed-toast' + (type === 'danger' ? ' feed-toast-danger' : '');
    toast.style.display = 'block';

    setTimeout(function () {
      toast.style.display = 'none';
    }, 3500);
  }

  /* ==========================================================================
     Minimal Rich-Text Editor (Quill)
     ========================================================================== */
  function initQuillEditor() {
    if (typeof window.Quill === 'undefined') {
      console.error('Quill is not loaded.');
      return null;
    }

    const Quill = window.Quill;

    // Minimal toolbar configuration:
    // Inline: bold, italic, code, link
    // Structural: bullet list, ordered list, blockquote, code-block, custom-spoiler
    // Media: image
    const toolbarOptions = [
      ['bold', 'italic', 'code', 'link'],
      [{ 'list': 'bullet' }, { 'list': 'ordered' }],
      ['blockquote', 'code-block', 'custom-spoiler'],
      ['image']
    ];

    const editorBox = document.getElementById('questionEditorBox');

    const quill = new Quill('#questionEditor', {
      theme: 'snow',
      placeholder: 'Опишите контекст, что вы пытались сделать, что произошло и какой результат ожидали...',
      modules: {
        syntax: window.hljs ? { hljs: window.hljs } : false,
        toolbar: {
          container: toolbarOptions,
          handlers: {
            'custom-spoiler': handleInsertSpoiler,
            'image': handleImageUploadClick
          }
        },
        history: {
          delay: 1000,
          maxStack: 100,
          userOnly: true
        }
      }
    });

    state.quill = quill;

    // Decorate custom-spoiler button with icon
    const spoilerBtn = document.querySelector('.ql-custom-spoiler');
    if (spoilerBtn) {
      spoilerBtn.setAttribute('title', 'Добавить спойлер');
      spoilerBtn.setAttribute('aria-label', 'Добавить спойлер');
      spoilerBtn.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
          <polyline points="9 11 12 14 15 11"></polyline>
        </svg>
      `;
    }

    // Bind focus styling
    quill.on('selection-change', function (range) {
      if (editorBox) {
        if (range) {
          editorBox.classList.add('focused');
        } else {
          editorBox.classList.remove('focused');
        }
      }
    });

    // Content change: clear inline details error, update CTA readiness & trigger autosave
    quill.on('text-change', function () {
      clearFieldError('questionDetails');
      clearFormError();
      updateSubmitReadiness();
      triggerAutosave();
    });

    // Enable drag & drop and paste image support
    bindEditorMediaEvents(quill);

    // Initialize DraftsManager with Question Editor settings
    const titleInput = document.getElementById('questionTitleInput') || document.getElementById('question-title');
    if (window.DraftsManager) {
      state.draftsManager = new window.DraftsManager(quill, titleInput, {
        materialType: 'question',
        activeDraftKey: 'ag_active_question_draft_id',
        getTags: getTagsArray,
        tagsGetter: getTagsArray,
        setTags: setTagsArray,
        tagsSetter: setTagsArray,
        onDraftLoaded: function () {
          updateTitleCounter();
          updateSubmitReadiness();
        },
        onDraftReset: function () {
          setTagsArray([]);
          updateTitleCounter();
          updateSubmitReadiness();
        },
        onDraftSaved: function () {
          updateSubmitReadiness();
        },
        showToast: showToast
      });
    }

    return quill;
  }

  function handleInsertSpoiler() {
    if (!state.quill) return;
    const range = state.quill.getSelection(true);
    const index = range ? range.index : state.quill.getLength();

    state.quill.insertEmbed(index, 'spoiler', {
      title: 'Заголовок спойлера',
      body: 'Скрытый текст...'
    }, 'user');

    state.quill.insertText(index + 1, '\n', 'user');
    state.quill.setSelection(index + 2, 'user');
  }

  function handleImageUploadClick() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/png,image/jpeg,image/webp,image/gif,image/svg+xml';
    fileInput.style.display = 'none';
    document.body.appendChild(fileInput);

    fileInput.addEventListener('change', async function () {
      const file = fileInput.files && fileInput.files[0];
      if (file) {
        await uploadAndInsertImage(file);
      }
      fileInput.remove();
    });

    fileInput.click();
  }

  async function uploadAndInsertImage(file) {
    if (!file) return;

    if (file.size > MAX_IMAGE_BYTES) {
      setFieldError('questionDetails', 'Размер изображения не должен превышать 10 МБ.');
      return;
    }

    // Try uploading image to POST /api/upload/image (with fallback to /api/media/upload)
    const formData = new FormData();
    formData.append('image', file);

    try {
      updateAutosaveStatus('saving', 'Загрузка изображения...');
      const response = await fetch('/api/upload/image', {
        method: 'POST',
        body: formData
      });

      const resData = await response.json().catch(function () { return {}; });

      if (response.ok && resData.success && resData.url) {
        insertImageIntoEditor(resData.url, file.name);
        updateAutosaveStatus('saved', 'Все изменения сохранены');
      } else {
        const errMsg = resData.error || 'Ошибка загрузки изображения на сервер.';
        setFieldError('questionDetails', errMsg);
        updateAutosaveStatus('error', 'Ошибка сохранения');
      }
    } catch (err) {
      console.warn('Network failure during image upload, using data URL fallback:', err);
      // Client-side DataURL fallback
      const reader = new FileReader();
      reader.onload = function (e) {
        insertImageIntoEditor(e.target.result, file.name);
        updateAutosaveStatus('saved', 'Все изменения сохранены');
      };
      reader.readAsDataURL(file);
    }
  }

  function insertImageIntoEditor(srcUrl, altText = 'Изображение') {
    if (!state.quill || !srcUrl) return;
    const range = state.quill.getSelection(true);
    const index = range ? range.index : state.quill.getLength();

    state.quill.insertEmbed(index, 'image', srcUrl, 'user');
    state.quill.insertText(index + 1, '\n', 'user');
    state.quill.setSelection(index + 2, 'user');
    triggerAutosave();
  }

  function bindEditorMediaEvents(quill) {
    const root = quill.root;

    // Drag and Drop
    root.addEventListener('dragover', function (e) {
      e.preventDefault();
    });

    root.addEventListener('drop', function (e) {
      e.preventDefault();
      const files = e.dataTransfer && e.dataTransfer.files;
      if (files && files.length > 0 && files[0].type.startsWith('image/')) {
        uploadAndInsertImage(files[0]);
      }
    });

    // Paste Image
    root.addEventListener('paste', function (e) {
      const items = e.clipboardData && e.clipboardData.items;
      if (!items) return;

      for (let i = 0; i < items.length; i++) {
        if (items[i].type.startsWith('image/')) {
          const file = items[i].getAsFile();
          if (file) {
            e.preventDefault();
            uploadAndInsertImage(file);
            break;
          }
        }
      }
    });
  }

  /* ==========================================================================
     Tags Management
     ========================================================================== */
  function initTagsInput() {
    const wrapper = document.getElementById('questionTagsWrapper');
    const input = document.getElementById('questionTagInput');
    const list = document.getElementById('questionTagsList');

    if (!wrapper || !input || !list) return;

    wrapper.addEventListener('click', function (e) {
      if (e.target !== input && !e.target.closest('.chip-remove-btn')) {
        input.focus();
      }
    });

    input.addEventListener('focus', function () {
      wrapper.classList.add('focused');
    });

    input.addEventListener('blur', function () {
      wrapper.classList.remove('focused');
      addTagFromInput();
    });

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ',') {
        e.preventDefault();
        addTagFromInput();
      } else if (e.key === 'Backspace' && !input.value && state.tags.length > 0) {
        state.tags.pop();
        renderTags();
        triggerAutosave();
        clearFieldError('questionTags');
      }
    });

    input.addEventListener('paste', function (e) {
      const text = (e.clipboardData || window.clipboardData).getData('text');
      if (text && (text.includes(',') || text.includes('\n'))) {
        e.preventDefault();
        const parts = text.split(/[,\n]+/);
        let addedCount = 0;
        for (const part of parts) {
          if (addTag(part)) addedCount++;
        }
        input.value = '';
        renderTags();
        triggerAutosave();
      }
    });
  }

  function addTag(rawTag) {
    if (!rawTag) return false;
    const clean = rawTag.trim().replace(/^#+/, '').trim();
    if (!clean) return false;

    if (state.tags.length >= MAX_TAGS) {
      setFieldError('questionTags', `Максимум ${MAX_TAGS} тегов.`);
      return false;
    }

    if (clean.length > 60) {
      setFieldError('questionTags', 'Длина тега не должна превышать 60 символов.');
      return false;
    }

    const isDuplicate = state.tags.some(function (t) {
      return t.toLowerCase() === clean.toLowerCase();
    });

    if (isDuplicate) {
      return false;
    }

    state.tags.push(clean);
    clearFieldError('questionTags');
    return true;
  }

  function getTagsArray() {
    return state.tags.slice();
  }

  function setTagsArray(tags) {
    state.tags = Array.isArray(tags) ? tags.slice(0, MAX_TAGS) : [];
    renderTags();
    updateSubmitReadiness();
  }

  function addTagFromInput() {
    const input = document.getElementById('questionTagInput');
    if (!input) return;
    const val = input.value;
    if (val && val.trim()) {
      if (addTag(val)) {
        input.value = '';
        renderTags();
        updateSubmitReadiness();
        triggerAutosave();
      }
    }
  }

  function removeTag(tagToRemove) {
    state.tags = state.tags.filter(function (t) {
      return t.toLowerCase() !== tagToRemove.toLowerCase();
    });
    renderTags();
    updateSubmitReadiness();
    triggerAutosave();
    clearFieldError('questionTags');
  }

  function renderTags() {
    const list = document.getElementById('questionTagsList');
    const input = document.getElementById('questionTagInput');
    if (!list) return;

    list.innerHTML = '';
    state.tags.forEach(function (tag) {
      const chip = document.createElement('span');
      chip.className = 'question-tag-chip';
      chip.setAttribute('data-tag', tag);

      const text = document.createElement('span');
      text.className = 'chip-text';
      text.textContent = '#' + tag;

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chip-remove-btn';
      btn.setAttribute('aria-label', 'Удалить тег ' + tag);
      btn.innerHTML = '&times;';
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        removeTag(tag);
      });

      chip.appendChild(text);
      chip.appendChild(btn);
      list.appendChild(chip);
    });

    if (input) {
      if (state.tags.length >= MAX_TAGS) {
        input.placeholder = `Достигнут максимум (${MAX_TAGS} тегов)`;
      } else {
        input.placeholder = state.tags.length === 0
          ? 'Введите тег и нажмите Enter или запятую...'
          : 'Добавить еще тег...';
      }
    }
  }

  /* ==========================================================================
     Inline Validation & Form Errors
     ========================================================================== */
  function setFieldError(fieldPrefix, message) {
    const errorEl = document.getElementById(fieldPrefix + 'Error');
    const inputEl = document.getElementById(fieldPrefix + 'Input') ||
                    document.getElementById(fieldPrefix + 'Wrapper') ||
                    document.getElementById(fieldPrefix + 'Box');

    if (errorEl) {
      errorEl.textContent = message;
    }
    if (inputEl) {
      inputEl.classList.add('is-invalid');
    }
  }

  function clearFieldError(fieldPrefix) {
    const errorEl = document.getElementById(fieldPrefix + 'Error');
    const inputEl = document.getElementById(fieldPrefix + 'Input') ||
                    document.getElementById(fieldPrefix + 'Wrapper') ||
                    document.getElementById(fieldPrefix + 'Box');

    if (errorEl) {
      errorEl.textContent = '';
    }
    if (inputEl) {
      inputEl.classList.remove('is-invalid');
    }
  }

  function setFormError(message) {
    const formError = document.getElementById('questionFormError');
    if (formError) {
      formError.textContent = message;
      formError.style.display = 'block';
    }
  }

  function clearFormError() {
    const formError = document.getElementById('questionFormError');
    if (formError) {
      formError.textContent = '';
      formError.style.display = 'none';
    }
  }

  function validateForm() {
    let isValid = true;
    clearFormError();

    // 1. Title validation
    const titleInput = document.getElementById('questionTitleInput');
    const title = titleInput ? titleInput.value.trim() : '';

    if (!title) {
      setFieldError('questionTitle', 'Пожалуйста, сформулируйте вопрос.');
      isValid = false;
    } else if (title.length < MIN_TITLE_LEN) {
      setFieldError('questionTitle', `Заголовок вопроса слишком короткий (минимум ${MIN_TITLE_LEN} символов).`);
      isValid = false;
    } else if (title.length > MAX_TITLE_LEN) {
      setFieldError('questionTitle', `Заголовок вопроса не должен превышать ${MAX_TITLE_LEN} символов.`);
      isValid = false;
    } else {
      clearFieldError('questionTitle');
    }

    // 2. Details validation
    const quillText = state.quill ? state.quill.getText().trim() : '';
    if (!quillText || quillText.length < MIN_DETAILS_LEN) {
      setFieldError('questionDetails', `Опишите детали вопроса подробнее (минимум ${MIN_DETAILS_LEN} символов).`);
      isValid = false;
    } else {
      clearFieldError('questionDetails');
    }

    // 3. Tags validation
    if (state.tags.length > MAX_TAGS) {
      setFieldError('questionTags', `Максимальное количество тегов: ${MAX_TAGS}.`);
      isValid = false;
    } else {
      clearFieldError('questionTags');
    }

    return isValid;
  }

  /* ==========================================================================
     Draft Autosave & Restore
     ========================================================================== */
  function updateAutosaveStatus(status, text) {
    if (state.draftsManager && typeof state.draftsManager.setStatus === 'function') {
      state.draftsManager.setStatus(status);
    }

    const statusEl = document.getElementById('save-status');
    const textEl = document.getElementById('save-status-text');

    if (statusEl) {
      statusEl.classList.remove('status-saved', 'status-unsaved', 'status-saving', 'status-error', 'saving');
      if (status === 'saving') {
        statusEl.classList.add('status-saving', 'saving');
      } else if (status === 'unsaved') {
        statusEl.classList.add('status-unsaved');
      } else if (status === 'error') {
        statusEl.classList.add('status-error');
      } else {
        statusEl.classList.add('status-saved');
      }
    }

    if (textEl) {
      if (text) {
        textEl.textContent = text;
      } else if (status === 'saving') {
        textEl.textContent = 'Сохранение...';
      } else if (status === 'unsaved') {
        textEl.textContent = 'Есть изменения';
      } else if (status === 'error') {
        textEl.textContent = 'Ошибка сохранения';
      } else {
        textEl.textContent = 'Все изменения сохранены';
      }
    }
  }

  function updateDraftsBadge() {
    if (state.draftsManager && typeof state.draftsManager.updateBadge === 'function') {
      return state.draftsManager.updateBadge();
    }

    const badge = document.getElementById('drafts-badge');
    if (!badge) return;
    try {
      const saved = localStorage.getItem(DRAFT_STORAGE_KEY);
      if (saved) {
        const draft = JSON.parse(saved);
        if (draft && typeof draft === 'object') {
          const hasTitle = Boolean(draft.title && draft.title.trim());
          const hasTags = Array.isArray(draft.tags) && draft.tags.length > 0;
          const hasHtml = Boolean(draft.html && draft.html.replace(/<[^>]*>/g, '').trim());
          if (hasTitle || hasTags || hasHtml) {
            badge.textContent = '1';
            return;
          }
        }
      }
    } catch (e) {}
    badge.textContent = '0';
  }

  function updateSubmitReadiness() {
    const submitBtn = document.getElementById('btn-submit-question') || document.getElementById('btnSubmitQuestion');
    if (!submitBtn) return;

    const titleInput = document.getElementById('questionTitleInput');
    const title = titleInput ? titleInput.value.trim() : '';
    const rawText = state.quill ? state.quill.getText().trim() : '';

    const isReady = title.length >= MIN_TITLE_LEN && rawText.length >= MIN_DETAILS_LEN;

    if (isReady && !state.isSubmitting) {
      submitBtn.removeAttribute('disabled');
      submitBtn.disabled = false;
      submitBtn.setAttribute('title', 'Опубликовать вопрос');
    } else {
      submitBtn.setAttribute('disabled', 'disabled');
      submitBtn.disabled = true;
      submitBtn.setAttribute('title', 'Добавьте вопрос и его описание');
    }
  }

  function updateTitleCounter() {
    const titleInput = document.getElementById('questionTitleInput');
    const counter = document.getElementById('title-char-counter');
    if (!titleInput || !counter) return;

    const len = titleInput.value.length;
    counter.textContent = `${len} / ${MAX_TITLE_LEN}`;
    if (len > MAX_TITLE_LEN) {
      counter.classList.add('error');
    } else {
      counter.classList.remove('error');
    }
  }

  function triggerAutosave() {
    if (state.draftsManager && typeof state.draftsManager.triggerAutosave === 'function') {
      state.draftsManager.triggerAutosave();
    } else {
      updateAutosaveStatus('saving', 'Сохранение...');
      if (state.autosaveTimer) {
        clearTimeout(state.autosaveTimer);
      }
      state.autosaveTimer = setTimeout(saveDraft, 500);
    }
  }

  function saveDraft() {
    if (state.draftsManager && typeof state.draftsManager.saveCurrent === 'function') {
      return state.draftsManager.saveCurrent({ isManual: false });
    }

    const titleInput = document.getElementById('questionTitleInput');
    const title = titleInput ? titleInput.value : '';
    const html = state.quill ? state.quill.root.innerHTML : '';
    const delta = state.quill ? state.quill.getContents() : null;

    // Do not save completely empty drafts
    const rawText = state.quill ? state.quill.getText().trim() : '';
    if (!title.trim() && !rawText && state.tags.length === 0) {
      updateAutosaveStatus('saved', 'Все изменения сохранены');
      updateDraftsBadge();
      return;
    }

    const draftData = {
      title: title,
      tags: state.tags,
      html: html,
      delta: delta,
      updatedAt: new Date().toISOString()
    };

    try {
      localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draftData));
      updateAutosaveStatus('saved', 'Все изменения сохранены');
      updateDraftsBadge();
    } catch (e) {
      console.warn('LocalStorage error while autosaving question draft:', e);
      updateAutosaveStatus('error', 'Ошибка сохранения');
    }
  }

  function restoreDraft() {
    if (state.draftsManager && typeof state.draftsManager.autoRestore === 'function') {
      return state.draftsManager.autoRestore();
    }

    try {
      const saved = localStorage.getItem(DRAFT_STORAGE_KEY);
      if (!saved) {
        updateDraftsBadge();
        updateTitleCounter();
        updateSubmitReadiness();
        return;
      }

      const draft = JSON.parse(saved);
      if (!draft || typeof draft !== 'object') {
        updateDraftsBadge();
        updateTitleCounter();
        updateSubmitReadiness();
        return;
      }

      const titleInput = document.getElementById('questionTitleInput');
      if (titleInput && typeof draft.title === 'string') {
        titleInput.value = draft.title;
      }

      if (Array.isArray(draft.tags)) {
        setTagsArray(draft.tags);
      }

      if (state.quill) {
        if (draft.delta && draft.delta.ops && draft.delta.ops.length > 0) {
          state.quill.setContents(draft.delta, 'silent');
        } else if (draft.html) {
          state.quill.root.innerHTML = draft.html;
        }
      }

      updateTitleCounter();
      updateSubmitReadiness();
      updateDraftsBadge();
      updateAutosaveStatus('saved', 'Все изменения сохранены');
    } catch (e) {
      console.warn('Failed to restore question draft:', e);
      updateTitleCounter();
      updateSubmitReadiness();
      updateDraftsBadge();
    }
  }

  function clearDraft() {
    if (state.draftsManager && typeof state.draftsManager.deleteCurrentDraft === 'function') {
      return state.draftsManager.deleteCurrentDraft();
    }

    try {
      localStorage.removeItem(DRAFT_STORAGE_KEY);
      updateDraftsBadge();
    } catch (e) {}
  }

  /* ==========================================================================
     Submission Logic
     ========================================================================== */
  async function handleSubmitQuestion() {
    if (state.isSubmitting) return;

    // Real-time tag addition from any leftover typed text
    addTagFromInput();

    if (!validateForm()) {
      return;
    }

    const titleInput = document.getElementById('questionTitleInput');
    const title = titleInput.value.trim();
    const quillHtml = state.quill.root.innerHTML;
    const rawText = state.quill.getText().trim();

    // Generate description snippet (50 to 500 chars)
    let snippet = rawText.slice(0, 300);
    if (snippet.length < 50) {
      snippet = (title + ' - ' + snippet).slice(0, 500);
    }
    if (snippet.length < 50) {
      snippet = (snippet + ' Вопрос сообществу разработчиков смарт-контрактов SmartContractum.').slice(0, 500);
    }

    const draftId = (state.draftsManager && state.draftsManager.currentDraftId) || `draft_q_${Date.now()}`;
    const idempotencyKey = (state.draftsManager && typeof state.draftsManager.getSubmissionIdempotencyKey === 'function')
      ? state.draftsManager.getSubmissionIdempotencyKey()
      : `idemp_q_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    const payload = {
      draftId: draftId,
      title: title,
      html: quillHtml,
      materialType: 'question',
      publicationSettings: {
        keywords: state.tags.length > 0 ? state.tags : ['question'],
        targetAudience: 'developers',
        topics: ['smart-contracts-development'],
        description: snippet
      },
      idempotencyKey: idempotencyKey
    };

    const submitBtn = document.getElementById('btn-submit-question') || document.getElementById('btnSubmitQuestion');
    const originalBtnText = submitBtn ? submitBtn.innerHTML : '';

    try {
      state.isSubmitting = true;
      if (submitBtn) {
        submitBtn.setAttribute('disabled', 'disabled');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span>Публикация...</span>';
      }

      const response = await fetch('/api/moderation/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Idempotency-Key': payload.idempotencyKey
        },
        body: JSON.stringify(payload)
      });

      const resData = await response.json().catch(function () { return {}; });

      if (response.status === 401) {
        setFormError('Для публикации вопроса необходимо войти в систему.');
        openAuthModal();
        return;
      }

      if (response.ok && resData.success) {
        // Clear active draft upon successful submission
        if (state.draftsManager && typeof state.draftsManager.deleteCurrentDraft === 'function') {
          await state.draftsManager.deleteCurrentDraft();
        } else {
          clearDraft();
        }
        updateDraftsBadge();
        showToast('Вопрос успешно опубликован!', 'success');

        const targetUrl = resData.url || (resData.submissionId ? `/article.html?id=${resData.submissionId}` : '/feed.html?tab=questions');
        setTimeout(function () {
          window.location.href = targetUrl;
        }, 300);
      } else {
        const errorMsg = resData.error || (resData.fieldErrors && Object.values(resData.fieldErrors)[0]) || 'Не удалось отправить вопрос на модерацию.';
        setFormError(errorMsg);
      }
    } catch (networkErr) {
      console.error('Submission network error:', networkErr);
      setFormError('Ошибка соединения с сервером. Пожалуйста, проверьте подключение и повторите попытку.');
    } finally {
      state.isSubmitting = false;
      if (submitBtn) {
        submitBtn.innerHTML = originalBtnText;
        updateSubmitReadiness();
      }
    }
  }

  /* ==========================================================================
     Application Bootstrap
     ========================================================================== */
  function init() {
    initTheme();
    initHeaderControls();
    initAuthControls();
    initTagsInput();
    initQuillEditor();

    if (!state.draftsManager) {
      restoreDraft();
      updateDraftsBadge();
    }
    updateTitleCounter();
    updateSubmitReadiness();

    // Drafts modal button in docbar
    const draftsBtn = document.getElementById('btn-drafts-modal');
    if (draftsBtn) {
      draftsBtn.addEventListener('click', function () {
        if (state.draftsManager && typeof state.draftsManager.openDraftsModal === 'function') {
          state.draftsManager.openDraftsModal();
        } else {
          restoreDraft();
          showToast('Черновик загружен', 'info');
        }
      });
    }

    // Title input listeners
    const titleInput = document.getElementById('questionTitleInput');
    if (titleInput) {
      titleInput.addEventListener('input', function () {
        clearFieldError('questionTitle');
        clearFormError();
        updateTitleCounter();
        updateSubmitReadiness();
        triggerAutosave();
      });
    }

    // Submit button listener (unified #btn-submit-question and fallback #btnSubmitQuestion)
    const submitBtn = document.getElementById('btn-submit-question') || document.getElementById('btnSubmitQuestion');
    if (submitBtn) {
      submitBtn.addEventListener('click', handleSubmitQuestion);
    }

    // Check auth status in background
    checkAuthStatus();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose API for targeted automated tests
  window.QuestionEditor = {
    state: state,
    addTag: addTag,
    removeTag: removeTag,
    getTagsArray: getTagsArray,
    setTagsArray: setTagsArray,
    validateForm: validateForm,
    saveDraft: saveDraft,
    restoreDraft: restoreDraft,
    clearDraft: clearDraft,
    updateSubmitReadiness: updateSubmitReadiness,
    updateTitleCounter: updateTitleCounter,
    updateAutosaveStatus: updateAutosaveStatus,
    updateDraftsBadge: updateDraftsBadge,
    showToast: showToast
  };

})(window);
