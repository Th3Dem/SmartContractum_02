// frontend/public/js/settings.js

document.addEventListener('DOMContentLoaded', () => {
  const elements = {
    unauthorizedCard: document.getElementById('unauthorizedCard'),
    settingsContent: document.getElementById('settingsContent'),
    
    // Tabs
    tabBtnProfile: document.getElementById('tabBtnProfile'),
    tabBtnSecurity: document.getElementById('tabBtnSecurity'),
    tabContentProfile: document.getElementById('tabContentProfile'),
    tabContentSecurity: document.getElementById('tabContentSecurity'),
    
    // Profile form
    profileForm: document.getElementById('profileForm'),
    btnSaveProfile: document.getElementById('btnSaveProfile'),
    
    // Security fields
    secUsername: document.getElementById('secUsername'),
    secEmail: document.getElementById('secEmail'),
    secEmailStatus: document.getElementById('secEmailStatus'),
    
    // Change email
    changeEmailForm: document.getElementById('changeEmailForm'),
    confirmEmailForm: document.getElementById('confirmEmailForm'),
    btnRequestChangeEmail: document.getElementById('btnRequestChangeEmail'),
    btnConfirmChangeEmail: document.getElementById('btnConfirmChangeEmail'),
    emailAlert: document.getElementById('emailAlert'),
    
    // Change password
    changePasswordForm: document.getElementById('changePasswordForm'),
    btnChangePassword: document.getElementById('btnChangePassword'),
    passwordAlert: document.getElementById('passwordAlert'),
    
    // Logout all
    btnLogoutAll: document.getElementById('btnLogoutAll')
  };

  let initialProfileData = {};

  // Init
  function init() {
    window.addEventListener('auth:change', (e) => {
      const { authenticated } = e.detail;
      if (authenticated) {
        showSettings();
        loadSettings();
      } else {
        showUnauthorized();
      }
    });

    if (window.SCAuth && window.SCAuth._initialized) {
      if (window.SCAuth.currentUser) {
        showSettings();
        loadSettings();
      } else {
        showUnauthorized();
      }
    } else {
      showUnauthorized(); // wait for auth sync
    }

    bindEvents();
  }

  function showUnauthorized() {
    if (elements.unauthorizedCard) {
      elements.unauthorizedCard.classList.remove('hidden');
      elements.unauthorizedCard.classList.add('active');
    }
    if (elements.settingsContent) {
      elements.settingsContent.classList.add('hidden');
    }
  }

  function showSettings() {
    if (elements.unauthorizedCard) {
      elements.unauthorizedCard.classList.add('hidden');
      elements.unauthorizedCard.classList.remove('active');
    }
    if (elements.settingsContent) {
      elements.settingsContent.classList.remove('hidden');
    }
  }

  function bindEvents() {
    // Tabs
    if (elements.tabBtnProfile) elements.tabBtnProfile.addEventListener('click', () => switchTab('profile'));
    if (elements.tabBtnSecurity) elements.tabBtnSecurity.addEventListener('click', () => switchTab('security'));

    // Forms
    if (elements.profileForm) elements.profileForm.addEventListener('submit', handleProfileSave);
    if (elements.changeEmailForm) elements.changeEmailForm.addEventListener('submit', handleRequestChangeEmail);
    if (elements.confirmEmailForm) elements.confirmEmailForm.addEventListener('submit', handleConfirmChangeEmail);
    if (elements.changePasswordForm) elements.changePasswordForm.addEventListener('submit', handleChangePassword);
    if (elements.btnLogoutAll) elements.btnLogoutAll.addEventListener('click', handleLogoutAll);

    // Unsaved changes warning
    window.addEventListener('beforeunload', (e) => {
      if (hasUnsavedProfileChanges()) {
        e.preventDefault();
        e.returnValue = '';
      }
    });
  }

  function switchTab(tab) {
    if (tab === 'profile') {
      elements.tabBtnProfile.classList.add('active');
      elements.tabBtnSecurity.classList.remove('active');
      elements.tabContentProfile.classList.add('active');
      elements.tabContentSecurity.classList.remove('active');
    } else {
      elements.tabBtnSecurity.classList.add('active');
      elements.tabBtnProfile.classList.remove('active');
      elements.tabContentSecurity.classList.add('active');
      elements.tabContentProfile.classList.remove('active');
    }
  }

  async function loadSettings() {
    try {
      const res = await fetch('/api/user/settings');
      if (res.ok) {
        const data = await res.json();
        populateProfile(data.profile);
        populateSecurity(data.security);
      }
    } catch (e) {
      console.error('Failed to load settings', e);
    }
  }

  function populateProfile(profile) {
    initialProfileData = profile || {};
    const fields = ['name', 'firstName', 'lastName', 'specialization', 'company', 'bio', 'website'];
    fields.forEach(field => {
      const el = document.getElementById(field);
      if (el) el.value = initialProfileData[field] || '';
    });
  }

  function populateSecurity(security) {
    if (!security) return;
    if (elements.secUsername) elements.secUsername.value = security.username || '';
    if (elements.secEmail) elements.secEmail.value = security.email || '';
    
    if (elements.secEmailStatus) {
      elements.secEmailStatus.textContent = security.emailVerified ? 'Подтвержден' : 'Не подтвержден';
      elements.secEmailStatus.className = 'settings-status-badge ' + (security.emailVerified ? 'verified' : 'unverified');
    }
  }

  function hasUnsavedProfileChanges() {
    const fields = ['name', 'firstName', 'lastName', 'specialization', 'company', 'bio', 'website'];
    for (const field of fields) {
      const el = document.getElementById(field);
      if (el && el.value !== (initialProfileData[field] || '')) {
        return true;
      }
    }
    return false;
  }

  async function handleProfileSave(e) {
    e.preventDefault();
    elements.btnSaveProfile.disabled = true;
    const body = {
      name: document.getElementById('name').value,
      firstName: document.getElementById('firstName').value,
      lastName: document.getElementById('lastName').value,
      specialization: document.getElementById('specialization').value,
      company: document.getElementById('company').value,
      bio: document.getElementById('bio').value,
      website: document.getElementById('website').value
    };

    try {
      const res = await fetch('/api/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (res.ok) {
        initialProfileData = { ...body };
        alert('Профиль сохранен');
        if (window.SCAuth) window.SCAuth.checkStatus();
      } else {
        const data = await res.json().catch(()=>({}));
        alert(data.error || 'Ошибка при сохранении профиля');
      }
    } catch (err) {
      console.error(err);
      alert('Ошибка сети');
    } finally {
      elements.btnSaveProfile.disabled = false;
    }
  }

  async function handleRequestChangeEmail(e) {
    e.preventDefault();
    elements.btnRequestChangeEmail.disabled = true;
    showAlert(elements.emailAlert, '', 'none');

    const currentPassword = document.getElementById('emailCurrentPassword').value;
    const newEmail = document.getElementById('newEmail').value;

    try {
      const res = await fetch('/api/auth/change-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ currentPassword, newEmail })
      });
      const data = await res.json().catch(()=>({}));
      if (res.ok) {
        elements.changeEmailForm.classList.add('hidden');
        elements.confirmEmailForm.classList.remove('hidden');
        showAlert(elements.emailAlert, 'Код отправлен на новый email', 'success');
      } else {
        showAlert(elements.emailAlert, data.error || 'Ошибка', 'error');
      }
    } catch (err) {
      console.error(err);
      showAlert(elements.emailAlert, 'Ошибка сети', 'error');
    } finally {
      elements.btnRequestChangeEmail.disabled = false;
    }
  }

  async function handleConfirmChangeEmail(e) {
    e.preventDefault();
    elements.btnConfirmChangeEmail.disabled = true;
    showAlert(elements.emailAlert, '', 'none');

    const code = document.getElementById('emailCode').value;

    try {
      const res = await fetch('/api/auth/verify-change-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code })
      });
      const data = await res.json().catch(()=>({}));
      if (res.ok) {
        showAlert(elements.emailAlert, 'Email успешно изменен', 'success');
        elements.confirmEmailForm.classList.add('hidden');
        elements.changeEmailForm.classList.remove('hidden');
        elements.changeEmailForm.reset();
        loadSettings();
        if (window.SCAuth) window.SCAuth.checkStatus();
      } else {
        showAlert(elements.emailAlert, data.error || 'Ошибка подтверждения', 'error');
      }
    } catch (err) {
      console.error(err);
      showAlert(elements.emailAlert, 'Ошибка сети', 'error');
    } finally {
      elements.btnConfirmChangeEmail.disabled = false;
    }
  }

  async function handleChangePassword(e) {
    e.preventDefault();
    elements.btnChangePassword.disabled = true;
    showAlert(elements.passwordAlert, '', 'none');

    const currentPassword = document.getElementById('currentPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const newPasswordConfirm = document.getElementById('newPasswordConfirm').value;

    if (newPassword !== newPasswordConfirm) {
      showAlert(elements.passwordAlert, 'Пароли не совпадают', 'error');
      elements.btnChangePassword.disabled = false;
      return;
    }

    try {
      const res = await fetch('/api/auth/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ currentPassword, newPassword })
      });
      const data = await res.json().catch(()=>({}));
      if (res.ok) {
        showAlert(elements.passwordAlert, data.message || 'Пароль успешно изменен', 'success');
        elements.changePasswordForm.reset();
      } else {
        showAlert(elements.passwordAlert, data.error || 'Ошибка', 'error');
      }
    } catch (err) {
      console.error(err);
      showAlert(elements.passwordAlert, 'Ошибка сети', 'error');
    } finally {
      elements.btnChangePassword.disabled = false;
    }
  }

  async function handleLogoutAll() {
    if (!confirm('Завершить сессии на всех устройствах, включая это? Потребуется войти заново.')) return;
    elements.btnLogoutAll.disabled = true;
    try {
      const res = await fetch('/api/auth/logout-all', { method: 'POST' });
      if (res.ok) {
        window.location.href = '/';
        return;
      } else {
        const data = await res.json().catch(()=>({}));
        alert(data.error || 'Ошибка');
      }
    } catch (err) {
      console.error(err);
      alert('Ошибка сети');
    } finally {
      elements.btnLogoutAll.disabled = false;
    }
  }

  function showAlert(el, msg, type) {
    el.textContent = msg;
    el.className = 'settings-alert';
    if (type !== 'none') {
      el.classList.add(type);
    }
  }

  init();
});
