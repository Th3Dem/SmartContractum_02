(function() {
  if (window.SCAuth && window.SCAuth._initialized) return window.SCAuth;

  class SCAuthClient {
    constructor() {
      this._initialized = true;
      this.currentUser = null;
      this.modalMode = 'login';
      this.init();
    }

    init() {
      this.injectModal();
      this.checkStatus();

      window.addEventListener('storage', (e) => {
        if (e.key === 'sc_auth_sync_event') {
          this.checkStatus();
        }
      });

      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          this.closeModal();
          this.closeDropdown();
        }
      });

      document.addEventListener('click', (e) => {
        if (this.modalOpen && !e.target.closest('#scAuthModal .sc-auth-modal-content') && !e.target.closest('.sc-auth-btn-login')) {
          this.closeModal();
        }
        if (this.dropdownOpen && !e.target.closest('.sc-auth-user-menu-wrapper')) {
          this.closeDropdown();
        }
      });
    }

    injectModal() {
      if (document.getElementById('scAuthModal')) return;
      const modalHtml = `
        <div id="scAuthModal" class="sc-auth-modal" style="display: none;" role="dialog" aria-modal="true">
          <div class="sc-auth-modal-content">
            <button class="sc-auth-modal-close" aria-label="Close">x</button>
            <div class="sc-auth-tabs">
              <button data-tab="login" class="sc-auth-tab">Войти</button>
              <button data-tab="register" class="sc-auth-tab">Зарегистрироваться</button>
              <button data-tab="verify" class="sc-auth-tab">Подтвердить</button>
              <button data-tab="forgot" class="sc-auth-tab">Забыли пароль</button>
            </div>
            <div class="sc-auth-tab-content active" id="tab-login">
              <input type="text" id="login-identifier" placeholder="Логин или Email">
              <input type="password" id="login-password" placeholder="Пароль">
              <button id="btn-login-submit">Войти</button>
            </div>
            <div class="sc-auth-tab-content" id="tab-register" style="display:none;">
              <input type="text" id="register-username" placeholder="Логин">
              <input type="email" id="register-email" placeholder="Email">
              <input type="text" id="register-name" placeholder="Имя">
              <input type="password" id="register-password" placeholder="Пароль">
              <button id="btn-register-submit">Зарегистрироваться</button>
            </div>
            <div class="sc-auth-tab-content" id="tab-verify" style="display:none;">
              <input type="text" id="verify-code" placeholder="6-значный код">
              <button id="btn-verify-submit">Подтвердить</button>
              <button id="btn-verify-resend">Отправить код повторно</button>
            </div>
            <div class="sc-auth-tab-content" id="tab-forgot" style="display:none;">
              <div class="sc-auth-banner">Введите email или логин для восстановления</div>
              <input type="text" id="forgot-identifier" placeholder="Логин или Email">
            </div>
          </div>
        </div>
      `;
      document.body.insertAdjacentHTML('beforeend', modalHtml);
      this.bindModalEvents();
    }

    bindModalEvents() {
      document.querySelector('.sc-auth-modal-close').addEventListener('click', () => this.closeModal());
      
      document.querySelectorAll('.sc-auth-tab').forEach(btn => {
        btn.addEventListener('click', (e) => {
          this.switchTab(e.target.dataset.tab);
        });
      });

      document.getElementById('btn-login-submit').addEventListener('click', () => this.handleLogin());
      document.getElementById('btn-register-submit').addEventListener('click', () => this.handleRegister());
      document.getElementById('btn-verify-submit').addEventListener('click', () => this.handleVerify());
      document.getElementById('btn-verify-resend').addEventListener('click', () => this.handleResend());
    }

    switchTab(tab) {
      this.modalMode = tab;
      document.getElementById('login-password').value = '';
      document.getElementById('register-password').value = '';
      
      document.querySelectorAll('.sc-auth-tab-content').forEach(c => c.style.display = 'none');
      document.getElementById('tab-' + tab).style.display = 'block';
    }

    openModal(tab = 'login') {
      this.modalOpen = true;
      document.getElementById('scAuthModal').style.display = 'flex';
      this.switchTab(tab);
    }

    closeModal() {
      this.modalOpen = false;
      document.getElementById('scAuthModal').style.display = 'none';
    }

    closeDropdown() {
      this.dropdownOpen = false;
      const dropdown = document.querySelector('.sc-auth-dropdown');
      if (dropdown) dropdown.style.display = 'none';
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

    renderGuest() {
      const container = document.querySelector('.header-user-bar') || document.getElementById('headerLoginBtn')?.parentElement;
      if (!container) return;
      
      container.innerHTML = `<button class="sc-auth-btn-login header-login-action-btn">Вход</button>`;
      container.querySelector('.sc-auth-btn-login').addEventListener('click', () => this.openModal('login'));
    }

    renderUser(user) {
      const container = document.querySelector('.header-user-bar') || document.getElementById('headerLoginBtn')?.parentElement;
      if (!container) return;

      const userName = user.name || user.username || 'User';
      const initial = userName.charAt(0).toUpperCase();

      container.innerHTML = `
        <div class="sc-auth-user-menu-wrapper" style="position:relative;">
          <button class="sc-auth-user-trigger" aria-expanded="false" aria-haspopup="menu">
            <span class="sc-auth-avatar">${initial}</span>
            <span class="sc-auth-name" style="max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block;vertical-align:middle;">${userName}</span>
            <span class="sc-auth-chevron">v</span>
          </button>
          <div class="sc-auth-dropdown" role="menu" style="display:none; position:absolute; right:0;">
            <a href="profile.html?id=${encodeURIComponent(user.id)}" role="menuitem">Мой профиль</a>
            <a href="#settings" role="menuitem">Настройки</a>
            <button class="sc-auth-logout-btn" role="menuitem">Выход</button>
          </div>
        </div>
      `;

      const trigger = container.querySelector('.sc-auth-user-trigger');
      const dropdown = container.querySelector('.sc-auth-dropdown');

      trigger.addEventListener('click', () => {
        this.dropdownOpen = !this.dropdownOpen;
        dropdown.style.display = this.dropdownOpen ? 'block' : 'none';
        trigger.setAttribute('aria-expanded', this.dropdownOpen.toString());
      });

      container.querySelector('.sc-auth-logout-btn').addEventListener('click', () => this.logout());
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

    showError(msg) {
      let errDiv = document.getElementById('sc-auth-error-msg');
      if (!errDiv) {
        const tabs = document.querySelector('.sc-auth-tabs');
        if (tabs) {
          errDiv = document.createElement('div');
          errDiv.id = 'sc-auth-error-msg';
          errDiv.style.color = 'red';
          errDiv.style.marginBottom = '10px';
          tabs.parentNode.insertBefore(errDiv, tabs.nextSibling);
        }
      }
      if (errDiv) {
        errDiv.textContent = msg;
        errDiv.style.display = 'block';
      } else {
        alert(msg);
      }
    }

    hideError() {
      const errDiv = document.getElementById('sc-auth-error-msg');
      if (errDiv) errDiv.style.display = 'none';
    }

    async handleLogin() {
      this.hideError();
      const btn = document.getElementById('btn-login-submit');
      const id = document.getElementById('login-identifier').value;
      const pw = document.getElementById('login-password').value;
      btn.disabled = true;
      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ login: id, password: pw })
        });
        const data = await res.json().catch(() => ({}));
        if (res.status === 403) {
          if (data.requiresEmailVerification) {
            this.pendingEmailOrLogin = id;
            this.switchTab('verify');
            return;
          }
        }
        if (res.ok) {
          localStorage.setItem('sc_auth_sync_event', Date.now().toString());
          this.closeModal();
          this.checkStatus();
        } else {
          this.showError(data.error || 'Login error');
        }
      } catch (e) {
        console.error('Login error', e);
        this.showError('Network error');
      } finally {
        btn.disabled = false;
      }
    }

    async handleRegister() {
      this.hideError();
      const btn = document.getElementById('btn-register-submit');
      const login = document.getElementById('register-username').value;
      const email = document.getElementById('register-email').value;
      const name = document.getElementById('register-name').value;
      const password = document.getElementById('register-password').value;
      btn.disabled = true;
      try {
        const res = await fetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ login, email, name, password })
        });
        const data = await res.json().catch(() => ({}));
        if (res.status === 201) {
          localStorage.setItem('sc_auth_sync_event', Date.now().toString());
          this.pendingEmailOrLogin = email || login;
          this.switchTab('verify');
        } else {
          this.showError(data.error || 'Register error');
        }
      } catch (e) {
        console.error('Register error', e);
        this.showError('Network error');
      } finally {
        btn.disabled = false;
      }
    }

    async handleVerify() {
      this.hideError();
      const btn = document.getElementById('btn-verify-submit');
      const verifyCode = document.getElementById('verify-code').value;
      btn.disabled = true;
      try {
        const res = await fetch('/api/auth/verify-email', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identifier: this.pendingEmailOrLogin, code: verifyCode })
        });
        const data = await res.json().catch(() => ({}));
        if (res.status === 200) {
          this.closeModal();
          this.checkStatus();
        } else {
          this.showError(data.error || 'Verify error');
        }
      } catch (e) {
        console.error('Verify error', e);
        this.showError('Network error');
      } finally {
        btn.disabled = false;
      }
    }

    async handleResend() {
      this.hideError();
      const btn = document.getElementById('btn-verify-resend');
      btn.disabled = true;
      try {
        const res = await fetch('/api/auth/resend-code', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identifier: this.pendingEmailOrLogin })
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
          let timeLeft = 60;
          btn.textContent = `Отправить код повторно (${timeLeft})`;
          const timer = setInterval(() => {
            timeLeft--;
            if (timeLeft <= 0) {
              clearInterval(timer);
              btn.disabled = false;
              btn.textContent = 'Отправить код повторно';
            } else {
              btn.textContent = `Отправить код повторно (${timeLeft})`;
            }
          }, 1000);
        } else {
          this.showError(data.error || 'Resend error');
          btn.disabled = false;
        }
      } catch (e) {
        console.error('Resend error', e);
        this.showError('Network error');
        btn.disabled = false;
      }
    }
  }

  window.SCAuth = new SCAuthClient();
  window.AuthClient = window.SCAuth;
})();
