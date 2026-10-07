(function() {
  'use strict';

  const PROFILE_FIELDS = ['name', 'firstName', 'lastName', 'specialization', 'company', 'bio', 'website'];
  const SECTIONS = ['profile', 'security', 'sessions', 'companies', 'appearance'];
  const ROLE_LABEL = { admin: 'Администратор', moderator: 'Модератор', user: 'Участник' };
  const COMPLETENESS = [
    { key: 'avatar', label: 'Фото', test: (s) => Boolean(s.avatar), focus: 'btnAvatarEdit' },
    { key: 'name', label: 'Имя', test: (s, f) => Boolean(f.name), focus: 'name' },
    { key: 'specialization', label: 'Специализация', test: (s, f) => Boolean(f.specialization), focus: 'specialization' },
    { key: 'company', label: 'Организация', test: (s, f) => Boolean(f.company), focus: 'company' },
    { key: 'bio', label: 'О себе', test: (s, f) => f.bio.length >= 30, focus: 'bio' },
    { key: 'website', label: 'Сайт', test: (s, f) => Boolean(f.website), focus: 'website' },
    { key: 'cover', label: 'Обложка', test: (s) => Boolean(s.cover), focus: 'btnCoverEdit' }
  ];

  const state = { settings: null, initial: {}, user: null, saving: false };
  const $ = (id) => document.getElementById(id);

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function initials(name) {
    const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return 'SC';
    return (parts.length === 1 ? parts[0].slice(0, 2) : parts[0][0] + parts[1][0]).toUpperCase();
  }

  function formatDate(iso, withTime) {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleString('ru-RU', withTime
      ? { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }
      : { day: 'numeric', month: 'long', year: 'numeric' });
  }

  function toast(message, isError) {
    const el = $('settingsToast');
    el.textContent = message;
    el.className = 'st-toast' + (isError ? ' is-error' : '');
    el.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { el.hidden = true; }, 3200);
  }

  function showAlert(id, message, kind) {
    const el = $(id);
    if (!el) return;
    el.textContent = message || '';
    el.className = 'st-alert' + (kind === 'success' ? ' is-success' : '');
    el.hidden = !message;
  }

  async function api(method, path, body) {
    try {
      const res = await fetch(path, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body)
      });
      const data = await res.json().catch(() => ({}));
      return { ok: res.ok, status: res.status, data };
    } catch (e) {
      return { ok: false, status: 0, data: { error: 'Нет связи с сервером. Попробуйте еще раз.' } };
    }
  }

  /* ---------------------------------------------------------------- navigation */

  function showSection(name, push) {
    if (!SECTIONS.includes(name)) name = 'profile';
    document.querySelectorAll('.st-nav-item').forEach(b => {
      const active = b.dataset.section === name;
      b.classList.toggle('is-active', active);
      if (active) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
    });
    document.querySelectorAll('.st-section').forEach(s => { s.hidden = s.dataset.section !== name; });
    if (push !== false) history.replaceState(null, '', name === 'profile' ? window.location.pathname : '#' + name);
    if (name === 'sessions') loadSessions();
    if (name === 'companies') loadCompanies();
    if (name === 'appearance') renderThemeChoice();
  }

  /* ---------------------------------------------------------------- profile */

  function formValues() {
    const values = {};
    PROFILE_FIELDS.forEach(f => { values[f] = ($(f).value || '').trim(); });
    return values;
  }

  function changedFields() {
    const now = formValues();
    return PROFILE_FIELDS.filter(f => now[f] !== (state.initial[f] || ''));
  }

  function populateProfile(settings) {
    state.settings = settings;
    PROFILE_FIELDS.forEach(f => { $(f).value = settings[f] || ''; });
    state.initial = formValues();
    renderIdentity();
    renderCounters();
    renderProgress();
    updateSaveBar();
    validateWebsite();
  }

  function renderIdentity() {
    const s = state.settings || {};
    const f = formValues();
    const name = f.name || s.login || '';
    const sub = [f.specialization, f.company].filter(Boolean).join(' · ') || 'Специализация не указана';
    $('previewName').textContent = name;
    $('previewSub').textContent = sub;
    const avatarHtml = s.avatar ? `<img src="${escapeHtml(s.avatar)}" alt="" onerror="this.remove()">` : '';
    $('avatarPreview').innerHTML = avatarHtml + `<span>${escapeHtml(initials(name))}</span>`;
    $('meAvatar').innerHTML = avatarHtml + `<span>${escapeHtml(initials(name))}</span>`;
    $('meName').textContent = name;
    $('meLogin').textContent = s.login ? '@' + s.login : '';
    $('btnAvatarRemove').hidden = !s.avatar;
    const cover = $('coverPreview');
    cover.style.backgroundImage = s.cover ? `url("${encodeURI(s.cover)}")` : '';
    cover.classList.toggle('has-image', Boolean(s.cover));
    $('btnCoverRemove').hidden = !s.cover;
    if (s.id) $('linkViewProfile').href = 'profile.html?id=' + encodeURIComponent(s.id);
  }

  function renderCounters() {
    document.querySelectorAll('.st-counter').forEach(el => {
      const input = $(el.dataset.for);
      const max = Number(input.getAttribute('maxlength'));
      const len = input.value.length;
      el.textContent = `${len} / ${max}`;
      el.classList.toggle('is-near', len > max * 0.9);
    });
  }

  function renderProgress() {
    const s = state.settings || {};
    const f = formValues();
    const done = COMPLETENESS.filter(step => step.test(s, f));
    const pct = Math.round((done.length / COMPLETENESS.length) * 100);
    $('progressValue').textContent = pct + '%';
    $('progressBar').style.width = pct + '%';
    $('profileProgress').classList.toggle('is-complete', pct === 100);
    const missing = COMPLETENESS.filter(step => !step.test(s, f));
    $('progressHint').textContent = pct === 100
      ? 'Отлично, профиль заполнен полностью'
      : 'Заполненный профиль вызывает больше доверия у читателей';
    $('progressSteps').innerHTML = COMPLETENESS.map(step => {
      const ok = step.test(s, f);
      return `<button type="button" class="st-step${ok ? ' is-done' : ''}" data-focus="${step.focus}" ${ok ? 'tabindex="-1"' : ''}>
        <svg><use href="#${ok ? 'i-check' : 'i-plus'}"/></svg>${step.label}</button>`;
    }).join('');
    $('profileProgress').hidden = false;
    return missing;
  }

  function updateSaveBar() {
    const dirty = changedFields().length > 0;
    $('saveBar').hidden = !dirty;
    document.body.classList.toggle('st-has-savebar', dirty);
  }

  function validateWebsite() {
    const input = $('website');
    const value = input.value.trim();
    const hint = $('websiteHint');
    const bad = value && /^[a-z][a-z0-9+.-]*:/i.test(value) && !/^https?:\/\//i.test(value);
    input.classList.toggle('is-invalid', Boolean(bad));
    hint.textContent = bad ? 'Укажите адрес, который начинается с http:// или https://' : 'Ссылка появится в карточке профиля';
    hint.classList.toggle('is-error', Boolean(bad));
    return !bad;
  }

  async function saveProfile(e) {
    if (e) e.preventDefault();
    if (state.saving) return;
    const changed = changedFields();
    if (!changed.length) return;
    const values = formValues();
    if (!values.name) {
      $('name').focus();
      return toast('Укажите отображаемое имя', true);
    }
    if (!validateWebsite()) {
      $('website').focus();
      return;
    }
    const payload = {};
    changed.forEach(f => { payload[f] = values[f]; });
    state.saving = true;
    $('btnSaveProfile').disabled = true;
    $('btnSaveProfile').textContent = 'Сохраняем...';
    const { ok, data } = await api('POST', '/api/user/profile', payload);
    state.saving = false;
    $('btnSaveProfile').disabled = false;
    $('btnSaveProfile').textContent = 'Сохранить';
    if (!ok) return toast(data.error || 'Не удалось сохранить профиль', true);
    state.initial = formValues();
    Object.assign(state.settings, state.initial);
    updateSaveBar();
    renderIdentity();
    toast('Профиль сохранен');
    // The header shows the display name; refresh it from the server
    if (window.SCAuth && typeof window.SCAuth.checkStatus === 'function') window.SCAuth.checkStatus();
  }

  function resetProfile() {
    PROFILE_FIELDS.forEach(f => { $(f).value = state.initial[f] || ''; });
    renderIdentity();
    renderCounters();
    renderProgress();
    updateSaveBar();
    validateWebsite();
  }

  async function editImage(kind) {
    if (!window.SCMediaCrop) return;
    const picked = await window.SCMediaCrop.open(kind === 'avatar'
      ? { title: 'Фото профиля', aspect: 1, round: true, outputWidth: 400, outputHeight: 400, minWidth: 64, minHeight: 64 }
      : { title: 'Обложка профиля', aspect: 3, outputWidth: 1500, outputHeight: 500, minWidth: 600, minHeight: 200 });
    if (picked) saveImage({ kind, url: picked.url, focal: picked.focal });
  }

  async function saveImage(payload) {
    const { ok, data } = await api('POST', '/api/user/profile-media', payload);
    if (!ok) return toast(data.error || 'Не удалось сохранить изображение', true);
    state.settings.avatar = data.avatar || '';
    state.settings.cover = data.cover || '';
    renderIdentity();
    renderProgress();
    toast(payload.remove ? 'Изображение удалено' : 'Изображение сохранено');
    if (payload.kind === 'avatar' && window.SCAuth && window.SCAuth.checkStatus) window.SCAuth.checkStatus();
  }

  /* ---------------------------------------------------------------- security */

  function populateSecurity(settings) {
    $('secUsername').textContent = settings.login || '';
    $('secEmail').textContent = settings.email || 'не указан';
    const badge = $('secEmailStatus');
    badge.textContent = settings.emailVerified ? 'Подтвержден' : 'Не подтвержден';
    badge.className = 'st-badge ' + (settings.emailVerified ? 'is-ok' : 'is-warn');
    $('secRole').textContent = ROLE_LABEL[settings.role] || 'Участник';
    $('secCreated').textContent = formatDate(settings.createdAt) || 'неизвестно';
  }

  function togglePanel(id) {
    const panel = $(id);
    const open = panel.hidden;
    document.querySelectorAll('.st-expand').forEach(p => { if (p !== panel) p.hidden = true; });
    panel.hidden = !open;
    if (open) {
      const first = panel.querySelector('input');
      if (first) setTimeout(() => first.focus(), 0);
    } else {
      panel.querySelectorAll('form').forEach(f => f.reset());
      panel.querySelectorAll('.st-alert').forEach(a => { a.hidden = true; });
      if (id === 'passwordPanel') renderPasswordRules();
    }
  }

  function passwordScore(pw) {
    let score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[a-zа-яё]/.test(pw) && /[A-ZА-ЯЁ]/.test(pw)) score++;
    if (/\d/.test(pw)) score++;
    if (/[^A-Za-zА-Яа-яЁё0-9]/.test(pw)) score++;
    return Math.min(score, 4);
  }

  function renderPasswordRules() {
    const current = $('currentPassword').value;
    const pw = $('newPassword').value;
    const confirm = $('newPasswordConfirm').value;
    const rules = {
      length: pw.length >= 8,
      mixed: /[A-Za-zА-Яа-яЁё]/.test(pw) && /\d/.test(pw),
      different: Boolean(pw) && pw !== current,
      match: Boolean(pw) && pw === confirm
    };
    document.querySelectorAll('#passwordRules li').forEach(li => li.classList.toggle('is-ok', rules[li.dataset.rule]));
    const score = pw ? passwordScore(pw) : 0;
    const labels = ['Слишком простой', 'Слабый', 'Средний', 'Хороший', 'Надежный'];
    $('strengthBar').style.width = pw ? ((score + 1) * 20) + '%' : '0';
    $('strengthBar').dataset.level = String(score);
    $('strengthLabel').textContent = pw ? labels[score] : 'Введите новый пароль';
    return rules.length && rules.different && rules.match;
  }

  async function changePassword(e) {
    e.preventDefault();
    if (!renderPasswordRules()) {
      return showAlert('passwordAlert', 'Проверьте требования к новому паролю');
    }
    const btn = $('btnChangePassword');
    btn.disabled = true;
    const { ok, data } = await api('POST', '/api/auth/change-password', {
      currentPassword: $('currentPassword').value,
      newPassword: $('newPassword').value
    });
    btn.disabled = false;
    if (!ok) return showAlert('passwordAlert', data.error || 'Не удалось сменить пароль');
    togglePanel('passwordPanel');
    toast('Пароль изменен. Другие устройства вышли из аккаунта');
  }

  async function requestEmailChange(e) {
    e.preventDefault();
    const newEmail = $('newEmail').value.trim();
    if (!newEmail || !$('emailCurrentPassword').value) return showAlert('emailAlert', 'Укажите новый email и текущий пароль');
    const btn = $('btnRequestChangeEmail');
    btn.disabled = true;
    const { ok, data } = await api('POST', '/api/auth/change-email', { newEmail, password: $('emailCurrentPassword').value });
    btn.disabled = false;
    if (!ok) return showAlert('emailAlert', data.error || 'Не удалось отправить код');
    showAlert('emailAlert', '');
    $('changeEmailForm').hidden = true;
    $('confirmEmailForm').hidden = false;
    showAlert('emailConfirmAlert', `Код отправлен на ${newEmail}`, 'success');
    $('emailCode').focus();
  }

  async function confirmEmailChange(e) {
    e.preventDefault();
    const code = $('emailCode').value.trim();
    if (!/^\d{6}$/.test(code)) return showAlert('emailConfirmAlert', 'Код состоит из 6 цифр');
    const btn = $('btnConfirmChangeEmail');
    btn.disabled = true;
    const { ok, data } = await api('POST', '/api/auth/verify-change-email', { code });
    btn.disabled = false;
    if (!ok) return showAlert('emailConfirmAlert', data.error || 'Неверный код');
    $('confirmEmailForm').hidden = true;
    $('changeEmailForm').hidden = false;
    togglePanel('emailPanel');
    toast('Email изменен');
    loadSettings();
  }

  /* ---------------------------------------------------------------- sessions */

  function describeAgent(ua) {
    if (!ua) return { name: 'Неизвестное устройство', mobile: false };
    const browser = /YaBrowser/.test(ua) ? 'Яндекс Браузер' : /Edg\//.test(ua) ? 'Edge' : /OPR\//.test(ua) ? 'Opera'
      : /Firefox\//.test(ua) ? 'Firefox' : /Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari'
      : /python|curl|urllib/i.test(ua) ? 'Программа' : 'Браузер';
    const os = /Windows/.test(ua) ? 'Windows' : /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS'
      : /Mac OS X/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : '';
    return { name: os ? `${browser}, ${os}` : browser, mobile: /Android|iPhone|iPad|Mobile/.test(ua) };
  }

  async function loadSessions() {
    const list = $('sessionsList');
    list.innerHTML = '<div class="st-loading">Загрузка...</div>';
    const { ok, data } = await api('GET', '/api/auth/sessions');
    if (!ok) {
      list.innerHTML = `<div class="st-empty">${escapeHtml(data.error || 'Не удалось загрузить сеансы')}</div>`;
      return;
    }
    const sessions = data.sessions || [];
    $('sessionsCount').textContent = sessions.length ? String(sessions.length) : '';
    list.innerHTML = sessions.map(s => {
      const agent = describeAgent(s.userAgent);
      return `<div class="st-session${s.current ? ' is-current' : ''}">
        <span class="st-list-icon"><svg><use href="#i-devices"/></svg></span>
        <div class="st-list-text">
          <span class="st-list-value">${escapeHtml(agent.name)}${s.current ? ' <span class="st-badge is-ok">Это устройство</span>' : ''}</span>
          <span class="st-list-hint">Вход ${escapeHtml(formatDate(s.createdAt, true))} · активен до ${escapeHtml(formatDate(s.expiresAt))}</span>
        </div>
        ${s.current ? '' : `<button type="button" class="st-btn st-btn-ghost st-btn-sm" data-revoke="${escapeHtml(s.id)}">Завершить</button>`}
      </div>`;
    }).join('') || '<div class="st-empty">Активных сеансов нет</div>';
  }

  async function revokeSession(id, btn) {
    btn.disabled = true;
    const { ok, data } = await api('POST', '/api/auth/sessions/revoke', { id });
    if (!ok) {
      btn.disabled = false;
      return toast(data.error || 'Не удалось завершить сеанс', true);
    }
    toast('Сеанс завершен');
    loadSessions();
  }

  async function logoutAll() {
    const btn = $('btnLogoutAll');
    if (btn.dataset.confirm !== '1') {
      btn.dataset.confirm = '1';
      btn.lastChild.textContent = 'Нажмите еще раз для подтверждения';
      setTimeout(() => { btn.dataset.confirm = ''; btn.lastChild.textContent = 'Выйти везде'; }, 4000);
      return;
    }
    const { ok, data } = await api('POST', '/api/auth/logout-all', {});
    if (!ok) return toast(data.error || 'Не удалось завершить сеансы', true);
    window.location.href = '/';
  }

  /* ---------------------------------------------------------------- companies */

  async function loadCompanies() {
    const list = $('settingsCompaniesList');
    list.innerHTML = '<div class="st-card st-loading">Загрузка...</div>';
    const { ok, data } = await api('GET', '/api/user/companies');
    if (!ok) {
      list.innerHTML = '<div class="st-card st-empty">Не удалось загрузить компании</div>';
      return;
    }
    const items = data.items || [];
    $('companiesCount').textContent = items.length ? String(items.length) : '';
    if (!items.length) {
      list.innerHTML = `<div class="st-card st-empty-state">
        <span class="st-guard-icon"><svg><use href="#i-building"/></svg></span>
        <p class="st-empty-title">У вас пока нет компаний</p>
        <p class="st-empty-text">Создайте профиль компании, чтобы публиковать материалы от ее имени и собирать подписчиков.</p>
      </div>`;
      return;
    }
    list.innerHTML = items.map(c => `
      <div class="st-card st-company">
        <span class="st-company-logo">${c.logo ? `<img src="${escapeHtml(c.logo)}" alt="" onerror="this.remove()">` : ''}<span>${escapeHtml(initials(c.name))}</span></span>
        <div class="st-list-text">
          <span class="st-list-value">${escapeHtml(c.name)} <span class="st-badge ${c.role === 'owner' ? 'is-ok' : ''}">${c.role === 'owner' ? 'Владелец' : 'Автор'}</span></span>
          <span class="st-list-hint">${escapeHtml(c.specialization || '')}</span>
        </div>
        <div class="st-company-actions">
          <a class="st-btn st-btn-ghost st-btn-sm" href="editor.html?companyId=${encodeURIComponent(c.id)}"><svg><use href="#i-pen"/></svg>Написать</a>
          <a class="st-btn st-btn-ghost st-btn-sm" href="company.html?id=${encodeURIComponent(c.id)}">Открыть</a>
        </div>
      </div>`).join('');
  }

  /* ---------------------------------------------------------------- appearance */

  function currentTheme() {
    return document.documentElement.getAttribute('data-theme') || 'dark';
  }

  function renderThemeChoice() {
    document.querySelectorAll('[data-theme-choice]').forEach(b => {
      const active = b.dataset.themeChoice === currentTheme();
      b.classList.toggle('is-active', active);
      b.setAttribute('aria-checked', String(active));
    });
  }

  function setTheme(theme) {
    if (typeof window.applyTheme === 'function') {
      window.applyTheme(theme);
    } else {
      document.documentElement.setAttribute('data-theme', theme);
      try { localStorage.setItem('ag_theme', theme); localStorage.setItem('sc_theme', theme); } catch (e) {}
    }
    renderThemeChoice();
  }

  /* ---------------------------------------------------------------- load */

  async function loadSettings() {
    const { ok, data } = await api('GET', '/api/user/settings');
    if (!ok) {
      if (data && data.requireAuth) return onAuth(null);
      return toast(data.error || 'Не удалось загрузить настройки', true);
    }
    const settings = data.settings || {};
    populateProfile(settings);
    populateSecurity(settings);
  }

  function onAuth(user) {
    // A repeated auth event for the same account (e.g. after saving the name) must not reload
    // the form over edits in progress
    const sameAccount = Boolean(state.user && user && state.user.id === user.id && state.settings);
    state.user = user;
    if (sameAccount) return;
    $('unauthorizedCard').hidden = Boolean(user);
    $('settingsContent').hidden = !user;
    if (!user) return;
    loadSettings();
    loadCompanies();
    api('GET', '/api/auth/sessions').then(({ ok, data }) => {
      if (ok) $('sessionsCount').textContent = (data.sessions || []).length ? String(data.sessions.length) : '';
    });
    showSection((window.location.hash || '').replace('#', ''), false);
  }

  /* ---------------------------------------------------------------- events */

  document.querySelectorAll('.st-nav-item').forEach(b => b.addEventListener('click', () => showSection(b.dataset.section)));
  $('btnGuardLogin').addEventListener('click', () => window.SCAuth && window.SCAuth.openModal('login'));
  $('profileForm').addEventListener('submit', saveProfile);
  $('profileForm').addEventListener('input', () => {
    renderIdentity();
    renderCounters();
    renderProgress();
    updateSaveBar();
    validateWebsite();
  });
  $('btnResetProfile').addEventListener('click', resetProfile);
  $('btnAvatarEdit').addEventListener('click', () => editImage('avatar'));
  $('btnCoverEdit').addEventListener('click', () => editImage('cover'));
  $('btnAvatarRemove').addEventListener('click', () => saveImage({ kind: 'avatar', remove: true }));
  $('btnCoverRemove').addEventListener('click', () => saveImage({ kind: 'cover', remove: true }));
  $('progressSteps').addEventListener('click', (e) => {
    const step = e.target.closest('[data-focus]');
    if (!step || step.classList.contains('is-done')) return;
    const target = $(step.dataset.focus);
    if (target.tagName === 'BUTTON') return target.click();
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    target.focus();
  });
  document.addEventListener('click', (e) => {
    const toggle = e.target.closest('[data-toggle]');
    if (toggle) return togglePanel(toggle.dataset.toggle);
    const reveal = e.target.closest('[data-reveal]');
    if (reveal) {
      const input = $(reveal.dataset.reveal);
      input.type = input.type === 'password' ? 'text' : 'password';
      reveal.classList.toggle('is-on', input.type === 'text');
      return;
    }
    const revoke = e.target.closest('[data-revoke]');
    if (revoke) return revokeSession(revoke.dataset.revoke, revoke);
    const theme = e.target.closest('[data-theme-choice]');
    if (theme) return setTheme(theme.dataset.themeChoice);
  });
  $('btnCopyLogin').addEventListener('click', () => {
    const login = (state.settings && state.settings.login) || '';
    (navigator.clipboard ? navigator.clipboard.writeText(login) : Promise.reject()).then(
      () => toast('Логин скопирован'), () => toast(login));
  });
  $('changePasswordForm').addEventListener('input', renderPasswordRules);
  $('changePasswordForm').addEventListener('submit', changePassword);
  $('changeEmailForm').addEventListener('submit', requestEmailChange);
  $('confirmEmailForm').addEventListener('submit', confirmEmailChange);
  $('btnEmailBack').addEventListener('click', () => {
    $('confirmEmailForm').hidden = true;
    $('changeEmailForm').hidden = false;
  });
  $('btnLogoutAll').addEventListener('click', logoutAll);
  window.addEventListener('hashchange', () => showSection(window.location.hash.replace('#', ''), false));
  window.addEventListener('beforeunload', (e) => {
    if (state.settings && changedFields().length) {
      e.preventDefault();
      e.returnValue = '';
    }
  });

  window.addEventListener('auth:change', (e) => onAuth(e.detail && e.detail.authenticated ? e.detail.user : null));
  if (window.SCAuth && window.SCAuth.currentUser) onAuth(window.SCAuth.currentUser);
})();
