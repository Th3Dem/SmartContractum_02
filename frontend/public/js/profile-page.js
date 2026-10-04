/**
 * profile-page.js - Client script for full author profile page (profile.html)
 * 100% Offline-First, Zero Emojis, Zero Em Dashes
 */

(function (window) {
  'use strict';

  let currentProfile = null;
  let currentUser = null;
  let profileAbortController = null;

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function getInitials(name) {
    if (!name) return 'SC';
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function formatRegistrationDateRu(dateStr) {
    if (!dateStr) return 'недавно';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return 'недавно';
      const day = d.getDate();
      const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
      const month = months[d.getMonth()] || '';
      const year = d.getFullYear();
      return day + ' ' + month + ' ' + year;
    } catch (e) {
      return 'недавно';
    }
  }

  function showToast(message) {
    let toast = document.getElementById('feedToast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'feedToast';
      toast.className = 'feed-toast';
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.style.display = 'inline-flex';
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(function () {
      toast.style.display = 'none';
    }, 2800);
  }

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
        toggleBtn.title = isLight ? 'Переключить на темную тему' : 'Переключить на светлую тему';
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

  function checkAuthStatus(callback) {
    fetch('/api/auth/status')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.authenticated && data.user) {
          currentUser = data.user;
          window.currentUser = data.user;
        } else {
          currentUser = null;
          window.currentUser = null;
        }
        updateHeaderUserBar();
        if (typeof callback === 'function') callback(currentUser);
      })
      .catch(function () {
        currentUser = null;
        window.currentUser = null;
        updateHeaderUserBar();
        if (typeof callback === 'function') callback(null);
      });
  }

  function updateHeaderUserBar() {
    const userLabel = document.getElementById('headerUserLabel');
    const loginBtn = document.getElementById('headerLoginBtn');
    if (userLabel) {
      userLabel.textContent = currentUser ? currentUser.name : 'Вход';
    }
    if (loginBtn) {
      loginBtn.title = currentUser
        ? 'Вы вошли как ' + currentUser.name + ' (нажмите для выхода)'
        : 'Войти в личный кабинет';
    }
  }

  function getUserIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    let userId = params.get('id') || params.get('userId') || params.get('user');
    if (!userId) {
      const pathname = window.location.pathname;
      if (pathname.startsWith('/user/')) {
        userId = pathname.substring('/user/'.length).replace(/\/$/, '').trim();
      }
    }
    return userId ? decodeURIComponent(userId).trim() : null;
  }

  function loadProfile(userId, isSilentRefresh) {
    if (!userId) {
      const errorMsgEl = document.getElementById('profileErrorMessage');
      if (errorMsgEl) {
        errorMsgEl.textContent = 'Пользователь не указан';
        errorMsgEl.style.display = 'block';
      }
      return;
    }

    if (profileAbortController) {
      try { profileAbortController.abort(); } catch (e) {}
    }
    profileAbortController = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    const fetchOpts = profileAbortController ? { signal: profileAbortController.signal } : {};

    fetch('/api/users/' + encodeURIComponent(userId), fetchOpts)
      .then(function (res) {
        if (res.status === 404) {
          throw new Error('USER_NOT_FOUND');
        }
        return res.ok ? res.json() : null;
      })
      .then(function (data) {
        if (!data || !data.success) {
          throw new Error('PROFILE_LOAD_FAILED');
        }
        currentProfile = (data.profile || data.user || data);
        renderProfile(currentProfile);
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') return;
        renderError(err && err.message === 'USER_NOT_FOUND' ? 'Пользователь не найден' : 'Ошибка загрузки профиля');
      });
  }

  function renderProfile(p) {
    if (!p) return;

    // Document title
    const displayName = p.name || p.id || 'Пользователь';
    document.title = displayName + ' - SmartContractum';

    // Hide error container if shown
    const errBox = document.getElementById('profileErrorContainer');
    if (errBox) errBox.style.display = 'none';

    // Show main profile view
    const mainWrap = document.getElementById('profileMainContent');
    if (mainWrap) mainWrap.style.display = 'block';

    // 1. Avatar
    const avatarImg = document.getElementById('profileAvatarImg');
    const avatarInitials = document.getElementById('profileAvatarInitials');
    if (p.avatar) {
      if (avatarImg) {
        avatarImg.src = p.avatar;
        avatarImg.alt = displayName;
        avatarImg.style.display = 'block';
      }
      if (avatarInitials) avatarInitials.style.display = 'none';
    } else {
      if (avatarImg) avatarImg.style.display = 'none';
      if (avatarInitials) {
        avatarInitials.textContent = getInitials(displayName);
        avatarInitials.style.display = 'block';
      }
    }

    // 2. Identity info
    const nameEl = document.getElementById('profileName');
    if (nameEl) nameEl.textContent = displayName;

    const specEl = document.getElementById('profileSpec');
    if (specEl) {
      specEl.textContent = p.specialization || 'Участник сообщества';
      specEl.style.display = 'block';
    }

    const compEl = document.getElementById('profileCompany');
    if (compEl) {
      if (p.company) {
        compEl.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect><path d="M9 22v-4h6v4"></path><path d="M8 6h.01"></path><path d="M16 6h.01"></path><path d="M12 6h.01"></path><path d="M12 10h.01"></path><path d="M12 14h.01"></path><path d="M16 10h.01"></path><path d="M16 14h.01"></path><path d="M8 10h.01"></path><path d="M8 14h.01"></path></svg> <span>' + escapeHtml(p.company) + '</span>';
        compEl.style.display = 'inline-flex';
      } else {
        compEl.innerHTML = '';
        compEl.style.display = 'none';
      }
    }

    const bioEl = document.getElementById('profileBio');
    if (bioEl) {
      if (p.bio && p.bio.trim()) {
        bioEl.textContent = p.bio.trim();
        bioEl.style.display = 'block';
      } else {
        bioEl.textContent = '';
        bioEl.style.display = 'none';
      }
    }

    // 3. Stats & Reputation
    const stats = p.stats || {};
    const ratingVal = stats.rating !== undefined ? stats.rating : (p.rating !== undefined ? p.rating : 0);
    const pubVal = stats.publicationsCount !== undefined ? stats.publicationsCount : (p.publicationsCount || 0);
    const questVal = stats.questionsCount !== undefined ? stats.questionsCount : (p.questionsCount || 0);
    const ansVal = stats.answersCount !== undefined ? stats.answersCount : (p.answersCount || 0);
    const solVal = stats.solutionsCount !== undefined ? stats.solutionsCount : (p.solutionsCount || 0);
    const followVal = stats.followersCount !== undefined ? stats.followersCount : (p.followersCount || 0);
    const followingVal = stats.followingCount !== undefined ? stats.followingCount : (p.followingCount || 0);

    const rEl = document.getElementById('profileStatRating');
    if (rEl) rEl.textContent = ratingVal;

    const pEl = document.getElementById('profileStatPublications');
    if (pEl) pEl.textContent = pubVal;

    const qEl = document.getElementById('profileStatQuestions');
    if (qEl) qEl.textContent = questVal;

    const aEl = document.getElementById('profileStatAnswers');
    if (aEl) aEl.textContent = ansVal;

    const sEl = document.getElementById('profileStatSolutions');
    if (sEl) sEl.textContent = solVal;

    const fEl = document.getElementById('profileStatFollowers');
    if (fEl) fEl.textContent = followVal;

    const fwEl = document.getElementById('profileStatFollowing');
    if (fwEl) fwEl.textContent = followingVal;

    const ageEl = document.getElementById('profileAccountAge');
    if (ageEl) {
      ageEl.textContent = 'На платформе с ' + formatRegistrationDateRu(p.createdAt);
    }

    // 4. Action Buttons (Own profile vs Foreign profile)
    renderActions(p);

    // 5. Recent Publications List
    renderPublications(p.publications || p.articles || []);
  }

  function renderActions(p) {
    const isOwn = Boolean(currentUser && (currentUser.id === p.id || currentUser.id === p.userId));
    const btnSubscribe = document.getElementById('btnProfileSubscribe');
    const btnEdit = document.getElementById('btnProfileEdit');
    const btnMore = document.getElementById('btnProfileMore');

    if (isOwn) {
      if (btnSubscribe) btnSubscribe.style.display = 'none';
      if (btnEdit) btnEdit.style.display = 'inline-flex';
    } else {
      if (btnEdit) btnEdit.style.display = 'none';
      if (btnSubscribe) {
        btnSubscribe.style.display = 'inline-flex';
        updateSubscribeButtonState(btnSubscribe, Boolean(p.isSubscribed));
      }
    }

    if (btnMore) {
      btnMore.style.display = 'inline-flex';
    }
  }

  function updateSubscribeButtonState(btn, isSubscribed) {
    if (!btn) return;
    if (isSubscribed) {
      btn.classList.add('is-subscribed');
      btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Вы подписаны</span>';
      btn.title = 'Отписаться от автора';
    } else {
      btn.classList.remove('is-subscribed');
      btn.innerHTML = '<span>Подписаться</span>';
      btn.title = 'Подписаться на публикации автора';
    }
  }

  function renderPublications(pubs) {
    const container = document.getElementById('profileArticlesList');
    if (!container) return;

    if (!Array.isArray(pubs) || pubs.length === 0) {
      container.innerHTML = '<div class="profile-empty-state">Нет опубликованных материалов</div>';
      return;
    }

    container.innerHTML = pubs.map(function (item) {
      const title = item.title || 'Без названия';
      const dateStr = item.date || (item.createdAt ? formatRegistrationDateRu(item.createdAt) : '');
      const itemUrl = 'article.html?id=' + encodeURIComponent(item.id);
      const isQuestion = (item.materialType === 'question' || item.type === 'question');
      const badgeHtml = isQuestion
        ? '<span class="meta-badge question-badge" style="font-size: 0.72rem; padding: 2px 6px; margin-right: 8px;">Вопрос</span>'
        : '<span class="meta-badge" style="font-size: 0.72rem; padding: 2px 6px; margin-right: 8px;">Статья</span>';

      return '<div class="user-profile-article-item">' +
        '<div style="display: flex; align-items: center; min-width: 0; gap: 4px;">' +
          badgeHtml +
          '<a href="' + itemUrl + '" style="color: var(--text-primary); text-decoration: none; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' +
            escapeHtml(title) +
          '</a>' +
        '</div>' +
        '<span style="color: var(--text-muted); font-size: 0.78rem; flex-shrink: 0; margin-left: 12px;">' +
          escapeHtml(dateStr) +
        '</span>' +
      '</div>';
    }).join('');
  }

  function renderError(message) {
    const mainWrap = document.getElementById('profileMainContent');
    if (mainWrap) mainWrap.style.display = 'none';

    let errBox = document.getElementById('profileErrorContainer');
    if (!errBox) {
      const container = document.querySelector('.profile-page-container');
      if (container) {
        errBox = document.createElement('div');
        errBox.id = 'profileErrorContainer';
        container.appendChild(errBox);
      }
    }

    if (errBox) {
      errBox.className = 'feed-settings-error-msg';
      errBox.style.cssText = 'padding: 40px 20px; text-align: center; font-size: 1.05rem; display: block; background: var(--bg-card); border-radius: var(--radius-lg); border: 1px solid var(--border-color);';
      errBox.innerHTML = '<h2 style="font-size: 1.25rem; font-weight: 700; color: var(--text-primary); margin-bottom: 8px;">' + escapeHtml(message) + '</h2>' +
        '<p style="color: var(--text-secondary); margin-bottom: 20px;">Запрашиваемый профиль не найден или был удален</p>' +
        '<a href="feed.html" class="btn-profile-edit" style="display: inline-flex; text-decoration: none;">Вернуться в ленту</a>';
    }
  }

  function toggleSubscription() {
    if (!currentProfile) return;
    if (!currentUser) {
      openAuthModal();
      return;
    }

    const btn = document.getElementById('btnProfileSubscribe');
    if (btn) btn.disabled = true;

    fetch('/api/subscriptions/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({
        targetType: 'author',
        targetId: currentProfile.id || currentProfile.userId
      })
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (btn) btn.disabled = false;
        if (data && data.success) {
          const isSub = Boolean(data.subscribed);
          currentProfile.isSubscribed = isSub;
          updateSubscribeButtonState(btn, isSub);

          // Update follower counter in UI
          const fEl = document.getElementById('profileStatFollowers');
          if (fEl) {
            let count = parseInt(fEl.textContent, 10) || 0;
            count = isSub ? (count + 1) : Math.max(0, count - 1);
            fEl.textContent = count;
          }

          showToast(isSub ? 'Вы подписались на автора' : 'Вы отписались от автора');
        } else if (data && data.error) {
          showToast(data.error);
        }
      })
      .catch(function () {
        if (btn) btn.disabled = false;
        showToast('Ошибка при переключении подписки');
      });
  }

  function copyProfileLink() {
    const url = window.location.href;
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      navigator.clipboard.writeText(url)
        .then(function () {
          showToast('Ссылка на профиль скопирована');
        })
        .catch(function () {
          fallbackCopyText(url);
        });
    } else {
      fallbackCopyText(url);
    }
  }

  function fallbackCopyText(text) {
    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      showToast('Ссылка на профиль скопирована');
    } catch (e) {
      showToast('Не удалось скопировать ссылку');
    }
  }

  function openEditModal() {
    const modal = document.getElementById('editProfileModal');
    if (!modal || !currentProfile) return;

    const inpName = document.getElementById('editProfileName');
    const inpSpec = document.getElementById('editProfileSpec');
    const inpComp = document.getElementById('editProfileCompany');
    const inpBio = document.getElementById('editProfileBio');

    if (inpName) inpName.value = currentProfile.name || '';
    if (inpSpec) inpSpec.value = currentProfile.specialization || '';
    if (inpComp) inpComp.value = currentProfile.company || '';
    if (inpBio) inpBio.value = currentProfile.bio || '';

    modal.style.display = 'flex';
    if (inpName) {
      setTimeout(function () { inpName.focus(); }, 50);
    }
  }

  function closeEditModal() {
    const modal = document.getElementById('editProfileModal');
    if (modal) modal.style.display = 'none';
  }

  function saveProfileEdit() {
    if (!currentProfile) return;

    const inpName = document.getElementById('editProfileName');
    const inpSpec = document.getElementById('editProfileSpec');
    const inpComp = document.getElementById('editProfileCompany');
    const inpBio = document.getElementById('editProfileBio');
    const saveBtn = document.getElementById('btnSaveProfile');

    const payload = {
      name: (inpName ? inpName.value : '').trim(),
      specialization: (inpSpec ? inpSpec.value : '').trim(),
      company: (inpComp ? inpComp.value : '').trim(),
      bio: (inpBio ? inpBio.value : '').trim()
    };

    if (saveBtn) saveBtn.disabled = true;

    fetch('/api/user/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify(payload)
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (saveBtn) saveBtn.disabled = false;
        if (data && data.success && data.profile) {
          currentProfile.name = data.profile.name || payload.name;
          currentProfile.specialization = data.profile.specialization || payload.specialization;
          currentProfile.company = data.profile.company || payload.company;
          currentProfile.bio = data.profile.bio || payload.bio;

          renderProfile(currentProfile);
          closeEditModal();
          showToast('Профиль успешно обновлен');
        } else {
          showToast((data && data.error) || 'Ошибка сохранения профиля');
        }
      })
      .catch(function () {
        if (saveBtn) saveBtn.disabled = false;
        showToast('Ошибка сети при сохранении профиля');
      });
  }

  function openAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) modal.style.display = 'flex';
  }

  function closeAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) modal.style.display = 'none';
  }

  function initEventListeners() {
    // 1. Subscribe button
    const btnSubscribe = document.getElementById('btnProfileSubscribe');
    if (btnSubscribe) {
      btnSubscribe.addEventListener('click', toggleSubscription);
    }

    // 2. More button (copy link)
    const btnMore = document.getElementById('btnProfileMore');
    if (btnMore) {
      btnMore.addEventListener('click', copyProfileLink);
    }

    // 3. Edit profile button
    const btnEdit = document.getElementById('btnProfileEdit');
    if (btnEdit) {
      btnEdit.addEventListener('click', openEditModal);
    }

    // 4. Edit modal controls
    const btnCloseEdit = document.getElementById('btnCloseEditProfileModal');
    if (btnCloseEdit) {
      btnCloseEdit.addEventListener('click', closeEditModal);
    }

    const btnCancelEdit = document.getElementById('btnCancelEditProfile');
    if (btnCancelEdit) {
      btnCancelEdit.addEventListener('click', closeEditModal);
    }

    const btnSave = document.getElementById('btnSaveProfile');
    if (btnSave) {
      btnSave.addEventListener('click', saveProfileEdit);
    }

    const editModal = document.getElementById('editProfileModal');
    if (editModal) {
      editModal.addEventListener('click', function (e) {
        if (e.target === editModal) closeEditModal();
      });
    }

    // 5. Auth modal controls
    const btnLogin = document.getElementById('headerLoginBtn');
    if (btnLogin) {
      btnLogin.addEventListener('click', function (e) {
        e.preventDefault();
        if (currentUser) {
          if (confirm('Вы вошли как «' + currentUser.name + '». Выйти из профиля?')) {
            fetch('/api/auth/logout', { method: 'POST' })
              .then(function () {
                checkAuthStatus(function () {
                  const uid = getUserIdFromUrl() || (currentProfile && currentProfile.id);
                  if (uid) loadProfile(uid);
                });
              });
          }
        } else {
          openAuthModal();
        }
      });
    }

    const btnCloseAuth = document.getElementById('btnCloseAuthModal');
    if (btnCloseAuth) {
      btnCloseAuth.addEventListener('click', closeAuthModal);
    }

    const authModal = document.getElementById('authModal');
    if (authModal) {
      authModal.addEventListener('click', function (e) {
        if (e.target === authModal) closeAuthModal();
      });
    }

    const btnDemoLogin = document.getElementById('btnAuthLoginDemo');
    if (btnDemoLogin) {
      btnDemoLogin.addEventListener('click', function () {
        fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ userId: 'user_demo', name: 'Демо Пользователь' })
        })
          .then(function (res) { return res.json(); })
          .then(function (data) {
            if (data && data.success && data.user) {
              closeAuthModal();
              checkAuthStatus(function () {
                const uid = getUserIdFromUrl() || data.user.id;
                loadProfile(uid);
              });
            }
          });
      });
    }

    // 6. Keyboard dismissals (Escape)
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        const editModal = document.getElementById('editProfileModal');
        if (editModal && editModal.style.display !== 'none') {
          e.preventDefault();
          closeEditModal();
          return;
        }
        const authModal = document.getElementById('authModal');
        if (authModal && authModal.style.display !== 'none') {
          e.preventDefault();
          closeAuthModal();
        }
      }
    });

    // 7. Silent refresh on votes
    window.addEventListener('smartcontractum:voted', function () {
      if (currentProfile && currentProfile.id) {
        loadProfile(currentProfile.id, true);
      }
    });
  }

  function init() {
    initTheme();
    initEventListeners();

    checkAuthStatus(function (user) {
      let targetUserId = getUserIdFromUrl();
      if (!targetUserId && user) {
        targetUserId = user.id;
      }
      if (targetUserId) {
        loadProfile(targetUserId);
      } else {
        renderError('Пользователь не указан');
      }
    });
  }

  // Export module
  window.SmartContractumProfilePage = {
    init: init,
    loadProfile: loadProfile,
    renderProfile: renderProfile,
    toggleSubscription: toggleSubscription,
    copyProfileLink: copyProfileLink,
    openEditModal: openEditModal,
    closeEditModal: closeEditModal,
    saveProfileEdit: saveProfileEdit
  };

  document.addEventListener('DOMContentLoaded', init);

})(window);
