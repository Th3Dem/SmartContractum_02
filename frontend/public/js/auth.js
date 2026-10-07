/*
 * CSRF: every same-origin POST, PUT, PATCH or DELETE carries the sc_csrf cookie value in the
 * X-CSRF-Token header. auth.js is loaded on every page with the header, so pages that do not
 * load config.js (settings, company, admin, my-materials) are covered too. The flag is shared
 * with config.js, so the interceptor is installed once whichever script runs first.
 */
(function() {
  if (typeof window === 'undefined' || typeof window.fetch !== 'function' || window.__sc_csrf_interceptor_installed) return;
  window.__sc_csrf_interceptor_installed = true;
  const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
  const originalFetch = window.fetch;

  function csrfToken() {
    const match = document.cookie.split(';').map(c => c.trim()).find(c => c.indexOf('sc_csrf=') === 0);
    return match ? decodeURIComponent(match.slice('sc_csrf='.length)) : '';
  }

  window.fetch = function(input, init) {
    try {
      const url = typeof input === 'string' || input instanceof URL ? String(input) : (input && input.url) || '';
      const method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();
      const token = csrfToken();
      if (token && MUTATING.has(method) && new URL(url, window.location.href).origin === window.location.origin) {
        const headers = new Headers((init && init.headers) || (input instanceof Request ? input.headers : undefined));
        if (!headers.has('X-CSRF-Token')) headers.set('X-CSRF-Token', token);
        init = Object.assign({}, init, { headers });
      }
    } catch (e) {
      // Leave the request as it is
    }
    return originalFetch.call(this, input, init);
  };
})();

(function() {
  if (window.SCAuth && window.SCAuth._initialized) return window.SCAuth;

  const ICONS = {
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>',
    eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>',
    eyeOff: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.9 4.24A9.1 9.1 0 0 1 12 4c6.5 0 10 7 10 7a17.6 17.6 0 0 1-2.16 3.19M6.6 6.6A17.4 17.4 0 0 0 2 12s3.5 7 10 7a9.7 9.7 0 0 0 5.4-1.6"/><path d="M14.12 14.12A3 3 0 1 1 9.88 9.88"/><path d="m2 2 20 20"/></svg>',
    back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 18-6-6 6-6"/></svg>',
    mail: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/></svg>',
    user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
    settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.82-.33 1.7 1.7 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.7 1.7 0 0 0 1 1.51 1.7 1.7 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9a1.7 1.7 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1z"/></svg>',
    file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>',
    shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>',
    logout: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/></svg>',
    chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>',
    guest: '<svg class="btn-user-svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clip-rule="evenodd"></path></svg>'
  };

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function field(id, label, type, autocomplete, extra) {
    const isPassword = type === 'password';
    return `
      <div class="sc-auth-field">
        <label class="sc-auth-label" for="${id}">${label}</label>
        <div class="sc-auth-input-wrap">
          <input class="sc-auth-input" id="${id}" name="${id}" type="${type}" autocomplete="${autocomplete}" ${extra || ''} required>
          ${isPassword ? `<button type="button" class="sc-auth-reveal" data-reveal="${id}" aria-label="Показать пароль">${ICONS.eye}</button>` : ''}
        </div>
      </div>`;
  }

  const VIEWS = {
    login: {
      title: 'Вход',
      html: () => `
        <form class="sc-auth-form" data-form="login" novalidate>
          ${field('login-identifier', 'Логин или email', 'text', 'username', 'spellcheck="false" autocapitalize="off"')}
          ${field('login-password', 'Пароль', 'password', 'current-password')}
          <div class="sc-auth-row-end">
            <button type="button" class="sc-auth-link" data-view="forgot">Забыли пароль?</button>
          </div>
          <div class="sc-auth-message" role="alert" hidden></div>
          <button type="submit" class="sc-auth-submit">Войти</button>
        </form>
        <p class="sc-auth-switch">Нет аккаунта? <button type="button" class="sc-auth-link" data-view="register">Зарегистрироваться</button></p>`
    },
    register: {
      title: 'Регистрация',
      html: () => `
        <form class="sc-auth-form" data-form="register" novalidate>
          ${field('register-username', 'Логин', 'text', 'username', 'minlength="3" maxlength="30" spellcheck="false" autocapitalize="off"')}
          <p class="sc-auth-hint">От 3 до 30 символов: латинские буквы, цифры, дефис и подчеркивание</p>
          ${field('register-email', 'Email', 'email', 'email', 'spellcheck="false" autocapitalize="off"')}
          ${field('register-password', 'Пароль', 'password', 'new-password', 'minlength="8"')}
          <p class="sc-auth-hint">Не короче 8 символов</p>
          <div class="sc-auth-message" role="alert" hidden></div>
          <button type="submit" class="sc-auth-submit">Зарегистрироваться</button>
        </form>
        <p class="sc-auth-switch">Уже есть аккаунт? <button type="button" class="sc-auth-link" data-view="login">Войти</button></p>`
    },
    verify: {
      title: 'Подтверждение email',
      html: (ctx) => `
        <div class="sc-auth-notice">
          <span class="sc-auth-notice-icon">${ICONS.mail}</span>
          <p>Мы отправили 6-значный код на <strong>${escapeHtml(ctx.maskedEmail || 'ваш email')}</strong>. Введите его, чтобы завершить регистрацию.</p>
        </div>
        <form class="sc-auth-form" data-form="verify" novalidate>
          ${field('verify-code', 'Код из письма', 'text', 'one-time-code', 'inputmode="numeric" pattern="[0-9]*" maxlength="6"')}
          <div class="sc-auth-message" role="alert" hidden></div>
          <button type="submit" class="sc-auth-submit">Подтвердить</button>
        </form>
        <p class="sc-auth-switch">Не пришло письмо? <button type="button" class="sc-auth-link" id="btn-verify-resend">Отправить код повторно</button></p>`
    },
    forgot: {
      title: 'Восстановление пароля',
      back: 'login',
      html: () => `
        <p class="sc-auth-lead">Укажите логин или email. Если аккаунт существует, мы отправим на привязанную почту код для сброса пароля.</p>
        <form class="sc-auth-form" data-form="forgot" novalidate>
          ${field('forgot-identifier', 'Логин или email', 'text', 'username', 'spellcheck="false" autocapitalize="off"')}
          <div class="sc-auth-message" role="alert" hidden></div>
          <button type="submit" class="sc-auth-submit">Получить код</button>
        </form>`
    },
    reset: {
      title: 'Новый пароль',
      back: 'forgot',
      html: () => `
        <p class="sc-auth-lead">Введите код из письма и придумайте новый пароль. После сброса все устройства будут отключены от аккаунта.</p>
        <form class="sc-auth-form" data-form="reset" novalidate>
          ${field('forgot-code', 'Код из письма', 'text', 'one-time-code', 'inputmode="numeric" pattern="[0-9]*" maxlength="6"')}
          ${field('forgot-new-password', 'Новый пароль', 'password', 'new-password', 'minlength="8"')}
          <div class="sc-auth-message" role="alert" hidden></div>
          <button type="submit" class="sc-auth-submit">Сохранить пароль</button>
        </form>`
    }
  };

  class SCAuthClient {
    constructor() {
      this._initialized = true;
      this.currentUser = null;
      this.modalMode = 'login';
      this.modalOpen = false;
      this.dropdownOpen = false;
      this.flow = {};
      this.lastFocus = null;
      this.init();
    }

    init() {
      this.injectModal();
      this.bindHeaderButton();
      this.checkStatus();

      window.addEventListener('storage', (e) => {
        if (e.key === 'sc_auth_sync_event') this.checkStatus();
      });

      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          this.closeModal();
          this.closeDropdown();
        }
        if (e.key === 'Tab' && this.modalOpen) this.trapFocus(e);
      });

      document.addEventListener('click', (e) => {
        if (this.dropdownOpen && !e.target.closest('.sc-auth-user-menu-wrapper')) this.closeDropdown();
      });
    }

    injectModal() {
      if (document.getElementById('scAuthModal')) return;
      document.body.insertAdjacentHTML('beforeend', `
        <div id="scAuthModal" class="sc-auth-modal" hidden>
          <div class="sc-auth-backdrop" data-close></div>
          <div class="sc-auth-dialog" role="dialog" aria-modal="true" aria-labelledby="scAuthTitle">
            <div class="sc-auth-head">
              <button type="button" class="sc-auth-icon-btn sc-auth-back" aria-label="Назад" hidden>${ICONS.back}</button>
              <h2 class="sc-auth-title" id="scAuthTitle"></h2>
              <button type="button" class="sc-auth-icon-btn sc-auth-modal-close" aria-label="Закрыть" data-close>${ICONS.close}</button>
            </div>
            <div class="sc-auth-body"></div>
          </div>
        </div>`);

      const modal = document.getElementById('scAuthModal');
      modal.addEventListener('click', (e) => {
        if (e.target.closest('[data-close]')) return this.closeModal();
        const viewLink = e.target.closest('[data-view]');
        if (viewLink) return this.switchTab(viewLink.dataset.view);
        const back = e.target.closest('.sc-auth-back');
        if (back) return this.switchTab(VIEWS[this.modalMode].back || 'login');
        const reveal = e.target.closest('[data-reveal]');
        if (reveal) return this.togglePassword(reveal);
        if (e.target.closest('#btn-verify-resend')) return this.handleResend();
      });
      modal.addEventListener('submit', (e) => {
        e.preventDefault();
        const form = e.target.dataset.form;
        const handlers = {
          login: () => this.handleLogin(),
          register: () => this.handleRegister(),
          verify: () => this.handleVerify(),
          forgot: () => this.handleForgot(),
          reset: () => this.handleReset()
        };
        if (handlers[form]) handlers[form]();
      });
    }

    bindHeaderButton() {
      const btn = document.getElementById('headerLoginBtn');
      if (btn) {
        btn.classList.add('sc-auth-btn-login');
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          this.openModal('login');
        });
      }
    }

    switchTab(view) {
      if (!VIEWS[view]) view = 'login';
      this.modalMode = view;
      const def = VIEWS[view];
      document.getElementById('scAuthTitle').textContent = def.title;
      document.querySelector('#scAuthModal .sc-auth-back').hidden = !def.back;
      const body = document.querySelector('#scAuthModal .sc-auth-body');
      body.innerHTML = def.html(this.flow);

      if (view === 'login' && this.flow.loginPrefill) {
        document.getElementById('login-identifier').value = this.flow.loginPrefill;
      }
      if (view === 'login' && this.flow.notice) {
        this.showMessage(this.flow.notice, 'success');
        this.flow.notice = '';
      }
      this.focusFirstEmpty();
    }

    openModal(view = 'login') {
      const modal = document.getElementById('scAuthModal');
      this.lastFocus = document.activeElement;
      this.modalOpen = true;
      modal.hidden = false;
      document.documentElement.classList.add('sc-auth-lock');
      this.switchTab(view);
    }

    closeModal() {
      if (!this.modalOpen) return;
      this.modalOpen = false;
      document.getElementById('scAuthModal').hidden = true;
      document.documentElement.classList.remove('sc-auth-lock');
      if (this.lastFocus && typeof this.lastFocus.focus === 'function') this.lastFocus.focus();
    }

    focusFirstEmpty() {
      const inputs = document.querySelectorAll('#scAuthModal .sc-auth-input');
      const target = Array.from(inputs).find(i => !i.value) || inputs[0];
      if (target) setTimeout(() => target.focus(), 0);
    }

    trapFocus(e) {
      const focusable = document.querySelectorAll('#scAuthModal button:not([hidden]), #scAuthModal input');
      const list = Array.from(focusable).filter(el => el.offsetParent !== null);
      if (!list.length) return;
      const first = list[0];
      const last = list[list.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    togglePassword(btn) {
      const input = document.getElementById(btn.dataset.reveal);
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.innerHTML = show ? ICONS.eyeOff : ICONS.eye;
      btn.setAttribute('aria-label', show ? 'Скрыть пароль' : 'Показать пароль');
    }

    value(id) {
      const el = document.getElementById(id);
      return el ? el.value.trim() : '';
    }

    showMessage(msg, type = 'error') {
      const box = document.querySelector('#scAuthModal .sc-auth-message');
      if (!box) return;
      box.textContent = msg;
      box.className = 'sc-auth-message is-' + type;
      box.hidden = false;
    }

    showError(msg) {
      this.showMessage(msg, 'error');
    }

    hideError() {
      const box = document.querySelector('#scAuthModal .sc-auth-message');
      if (box) box.hidden = true;
    }

    setBusy(busy, label) {
      const btn = document.querySelector('#scAuthModal .sc-auth-submit');
      if (!btn) return;
      if (busy) {
        btn.dataset.label = btn.textContent;
        btn.textContent = label || 'Подождите...';
      } else if (btn.dataset.label) {
        btn.textContent = btn.dataset.label;
      }
      btn.disabled = busy;
    }

    async post(path, payload) {
      const res = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(() => ({}));
      return { res, data };
    }

    closeDropdown() {
      this.dropdownOpen = false;
      const dropdown = document.querySelector('.sc-auth-dropdown');
      if (dropdown) dropdown.hidden = true;
      const trigger = document.querySelector('.sc-auth-user-trigger');
      if (trigger) trigger.setAttribute('aria-expanded', 'false');
    }

    async checkStatus() {
      try {
        const res = await fetch('/api/auth/status');
        const data = await res.json();
        if (res.ok && data.authenticated) {
          this.currentUser = data.user;
          this.renderUser(data.user);
          window.dispatchEvent(new CustomEvent('auth:change', { detail: { authenticated: true, user: data.user } }));
        } else {
          this.currentUser = null;
          this.renderGuest();
          window.dispatchEvent(new CustomEvent('auth:change', { detail: { authenticated: false, user: null } }));
        }
      } catch (e) {
        console.error('Network error - offline first mode active', e);
      }
    }

    headerContainer() {
      return document.querySelector('.header-user-bar') || document.getElementById('headerLoginBtn')?.parentElement;
    }

    renderGuest() {
      const container = this.headerContainer();
      if (!container) return;
      if (container.querySelector('#headerLoginBtn')) return;
      container.innerHTML = `
        <a href="#auth" class="header-login-action-btn sc-auth-btn-login" id="headerLoginBtn" title="Войти в личный кабинет">
          <div class="btn-user-avatar-wrap" aria-hidden="true">${ICONS.guest}</div>
          <span class="btn-user-label" id="headerUserLabel">Вход</span>
        </a>`;
      this.bindHeaderButton();
    }

    renderUser(user) {
      const container = this.headerContainer();
      if (!container) return;

      const userName = user.name || user.username || 'Пользователь';
      const isStaff = Array.isArray(user.capabilities) && user.capabilities.includes('moderate');
      const initial = userName.trim().charAt(0).toUpperCase() || 'U';
      const avatar = user.avatar
        ? `<img class="sc-auth-user-avatar" src="${escapeHtml(user.avatar)}" alt="">`
        : `<span class="sc-auth-user-avatar sc-auth-avatar-fallback">${escapeHtml(initial)}</span>`;

      container.innerHTML = `
        <div class="sc-auth-user-menu-wrapper">
          <button type="button" class="sc-auth-user-trigger" aria-expanded="false" aria-haspopup="menu">
            ${avatar}
            <span class="sc-auth-user-name">${escapeHtml(userName)}</span>
            <span class="sc-auth-chevron-icon">${ICONS.chevron}</span>
          </button>
          <div class="sc-auth-dropdown" role="menu" hidden>
            <a class="sc-auth-dropdown-item" href="profile.html?id=${encodeURIComponent(user.id)}" role="menuitem">${ICONS.user}<span>Мой профиль</span></a>
            <a class="sc-auth-dropdown-item" href="my-materials.html" role="menuitem">${ICONS.file}<span>Мои материалы</span></a>
            <a class="sc-auth-dropdown-item" href="settings.html" role="menuitem">${ICONS.settings}<span>Настройки</span></a>
            ${isStaff ? `<a class="sc-auth-dropdown-item" href="admin.html" role="menuitem">${ICONS.shield}<span>Модерация</span></a>` : ''}
            <div class="sc-auth-dropdown-divider" role="separator"></div>
            <button type="button" class="sc-auth-dropdown-item sc-auth-dropdown-logout" role="menuitem">${ICONS.logout}<span>Выйти</span></button>
          </div>
        </div>`;

      const trigger = container.querySelector('.sc-auth-user-trigger');
      const dropdown = container.querySelector('.sc-auth-dropdown');
      trigger.addEventListener('click', () => {
        this.dropdownOpen = !this.dropdownOpen;
        dropdown.hidden = !this.dropdownOpen;
        trigger.setAttribute('aria-expanded', String(this.dropdownOpen));
      });
      container.querySelector('.sc-auth-dropdown-logout').addEventListener('click', () => this.logout());
    }

    async logout() {
      try {
        await fetch('/api/auth/logout', { method: 'POST' });
      } catch (e) {
        console.error('Logout error', e);
      }
      this.currentUser = null;
      this.renderGuest();
      localStorage.setItem('sc_auth_sync_event', Date.now().toString());
      window.dispatchEvent(new CustomEvent('auth:change', { detail: { authenticated: false, user: null } }));
    }

    onSignedIn() {
      this.flow = {};
      localStorage.setItem('sc_auth_sync_event', Date.now().toString());
      this.closeModal();
      this.checkStatus();
    }

    async handleLogin() {
      this.hideError();
      const login = this.value('login-identifier');
      const password = document.getElementById('login-password').value;
      if (!login || !password) return this.showError('Введите логин или email и пароль');
      this.setBusy(true, 'Входим...');
      try {
        const { res, data } = await this.post('/api/auth/login', { login, password });
        if (res.status === 403 && data.requiresEmailVerification) {
          this.flow = { identifier: login, maskedEmail: data.email, password };
          return this.switchTab('verify');
        }
        if (res.ok) return this.onSignedIn();
        this.showError(data.error || 'Неверный логин или пароль');
      } catch (e) {
        console.error('Login error', e);
        this.showError('Нет связи с сервером. Попробуйте еще раз.');
      } finally {
        this.setBusy(false);
      }
    }

    async handleRegister() {
      this.hideError();
      const login = this.value('register-username');
      const email = this.value('register-email');
      const password = document.getElementById('register-password').value;
      if (!login || !email || !password) return this.showError('Заполните логин, email и пароль');
      if (password.length < 8) return this.showError('Пароль должен быть не короче 8 символов');
      this.setBusy(true, 'Создаем аккаунт...');
      try {
        const { res, data } = await this.post('/api/auth/register', { login, email, password });
        if (res.status === 201) {
          this.flow = {
            identifier: email,
            maskedEmail: data.email,
            registrationToken: data.registrationToken || '',
            password,
            login
          };
          return this.switchTab('verify');
        }
        this.showError(data.error || 'Не удалось зарегистрироваться');
      } catch (e) {
        console.error('Register error', e);
        this.showError('Нет связи с сервером. Попробуйте еще раз.');
      } finally {
        this.setBusy(false);
      }
    }

    async handleVerify() {
      this.hideError();
      const code = this.value('verify-code');
      if (!/^\d{6}$/.test(code)) return this.showError('Код состоит из 6 цифр');
      this.setBusy(true, 'Проверяем...');
      try {
        const { res, data } = await this.post('/api/auth/verify-email', {
          identifier: this.flow.identifier,
          code,
          registrationToken: this.flow.registrationToken || undefined
        });
        if (!res.ok) {
          this.setBusy(false);
          return this.showError(data.error || 'Неверный код');
        }
        // Sign in right away with the password the user has just entered
        if (this.flow.password) {
          const login = await this.post('/api/auth/login', { login: this.flow.login || this.flow.identifier, password: this.flow.password });
          if (login.res.ok) return this.onSignedIn();
        }
        this.flow = { loginPrefill: this.flow.login || this.flow.identifier, notice: 'Email подтвержден. Войдите в аккаунт.' };
        this.switchTab('login');
      } catch (e) {
        console.error('Verify error', e);
        this.showError('Нет связи с сервером. Попробуйте еще раз.');
        this.setBusy(false);
      }
    }

    async handleResend() {
      this.hideError();
      const btn = document.getElementById('btn-verify-resend');
      if (!btn || btn.disabled) return;
      btn.disabled = true;
      try {
        const { res, data } = await this.post('/api/auth/resend-code', { identifier: this.flow.identifier });
        if (!res.ok) {
          this.showError(data.error || 'Не удалось отправить код');
          if (res.status !== 429) {
            btn.disabled = false;
            return;
          }
        } else {
          this.showMessage('Новый код отправлен', 'success');
        }
        let timeLeft = Number(data.retryAfter) > 0 && Number(data.retryAfter) < 3600 ? Number(data.retryAfter) : 60;
        const tick = () => {
          if (!document.body.contains(btn)) return;
          if (timeLeft <= 0) {
            btn.disabled = false;
            btn.textContent = 'Отправить код повторно';
            return;
          }
          btn.textContent = `Отправить повторно через ${timeLeft} с`;
          timeLeft--;
          setTimeout(tick, 1000);
        };
        tick();
      } catch (e) {
        console.error('Resend error', e);
        this.showError('Нет связи с сервером. Попробуйте еще раз.');
        btn.disabled = false;
      }
    }

    async handleForgot() {
      this.hideError();
      const identifier = this.value('forgot-identifier');
      if (!identifier) return this.showError('Введите логин или email');
      this.setBusy(true, 'Отправляем...');
      try {
        const { res, data } = await this.post('/api/auth/forgot-password', { identifier });
        if (res.ok) {
          this.flow = { forgotIdentifier: identifier };
          return this.switchTab('reset');
        }
        this.showError(data.error || 'Не удалось отправить код');
      } catch (e) {
        console.error('Forgot error', e);
        this.showError('Нет связи с сервером. Попробуйте еще раз.');
      } finally {
        this.setBusy(false);
      }
    }

    async handleReset() {
      this.hideError();
      const code = this.value('forgot-code');
      const newPassword = document.getElementById('forgot-new-password').value;
      if (!/^\d{6}$/.test(code)) return this.showError('Код состоит из 6 цифр');
      if (newPassword.length < 8) return this.showError('Пароль должен быть не короче 8 символов');
      this.setBusy(true, 'Сохраняем...');
      try {
        const { res, data } = await this.post('/api/auth/reset-password', {
          identifier: this.flow.forgotIdentifier,
          code,
          newPassword
        });
        if (res.ok) {
          this.flow = { loginPrefill: this.flow.forgotIdentifier, notice: 'Пароль изменен. Войдите с новым паролем.' };
          return this.switchTab('login');
        }
        this.showError(data.error || 'Не удалось сменить пароль');
      } catch (e) {
        console.error('Reset error', e);
        this.showError('Нет связи с сервером. Попробуйте еще раз.');
      } finally {
        this.setBusy(false);
      }
    }
  }

  window.SCAuth = new SCAuthClient();
  window.AuthClient = window.SCAuth;
})();
