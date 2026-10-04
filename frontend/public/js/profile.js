/**
 * profile.js - Единый общий модуль профиля пользователя SmartContractum
 *
 * Используется совместно в:
 * 1. Ленте публикаций (feed.html, feed.js)
 * 2. Чтении публикации (article.html, article.js)
 * 3. Отдельной странице профиля (profile.html)
 *
 * Обеспечивает:
 * - Инициализацию и управление модальным окном профиля (#userProfileModal)
 * - Делегирование кликов по .btn-author-profile (data-author-id / data-user-id)
 * - Загрузку данных профиля с бэкенда (/api/users/:id)
 * - Отображение статистики (Рейтинг, Публикации, Ответы, Решения)
 * - Список публикаций автора с переходом к чтению
 * - Обновление при голосованиях (событие 'smartcontractum:voted')
 * - Доступность: закрытие по Escape, клику вне карточки, фокус на кнопке закрытия
 */

(function (window) {
  'use strict';

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  let userModal = null;
  let btnCloseUserModal = null;
  let userModalBody = null;
  let currentOpenUserId = null;
  let profileRequestSeq = 0;
  let profileAbortController = null;
  let lastProfileTriggerEl = null;
  let isEventsBound = false;

  function closeUserProfileModal() {
    userModal = userModal || document.getElementById('userProfileModal');
    if (!userModal) return;
    if (profileAbortController) {
      try { profileAbortController.abort(); } catch (e) {}
      profileAbortController = null;
    }
    currentOpenUserId = null;
    profileRequestSeq++;
    userModal.style.display = 'none';
    if (lastProfileTriggerEl && typeof lastProfileTriggerEl.focus === 'function') {
      try { lastProfileTriggerEl.focus(); } catch (e) {}
    }
    lastProfileTriggerEl = null;
  }

  function openUserProfileModal(userId, triggerEl, isSilentRefresh) {
    userModal = userModal || document.getElementById('userProfileModal');
    userModalBody = userModalBody || document.getElementById('userProfileModalBody');
    btnCloseUserModal = btnCloseUserModal || document.getElementById('btnCloseUserProfileModal');
    if (!userModal || !userModalBody) return;

    if (triggerEl) {
      lastProfileTriggerEl = triggerEl;
    } else if (!isSilentRefresh) {
      lastProfileTriggerEl = document.activeElement;
    }

    currentOpenUserId = userId;
    const seq = ++profileRequestSeq;

    if (profileAbortController) {
      try { profileAbortController.abort(); } catch (e) {}
    }
    profileAbortController = (typeof AbortController !== 'undefined') ? new AbortController() : null;

    if (!isSilentRefresh) {
      userModalBody.innerHTML = '<div style="text-align: center; padding: 24px; color: var(--text-muted);">Загрузка профиля...</div>';
      userModal.style.display = 'flex';
      if (btnCloseUserModal) {
        try { btnCloseUserModal.focus(); } catch (e) {}
      }
    }

    const fetchOpts = profileAbortController ? { signal: profileAbortController.signal } : {};

    fetch('/api/users/' + encodeURIComponent(userId), fetchOpts)
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (seq !== profileRequestSeq || currentOpenUserId !== userId) return;
        const u = (data && (data.user || data.profile)) || data;
        if (!data || !data.success || !u || (!u.name && !u.id)) {
          userModalBody.innerHTML = '<div class="feed-settings-error-msg" style="padding: 20px;">Профиль пользователя не найден</div>';
          return;
        }
        const initials = u.initials || (u.name ? u.name.split(' ').map(function (s) { return s[0]; }).join('').toUpperCase() : 'SC');
        const stats = u.stats || {};
        const articlesList = u.articles || u.publications || [];
        let articlesHtml = '';
        if (Array.isArray(articlesList) && articlesList.length > 0) {
          articlesHtml = '<div class="user-profile-articles-title">Публикации автора (' + articlesList.length + ')</div>' +
            '<div class="user-profile-articles-list">' +
            articlesList.map(function (a) {
              const articleDate = a.created_at ? a.created_at.substring(0, 10) : (a.createdAt ? a.createdAt.substring(0, 10) : (a.date || ''));
              return '<a href="article.html?id=' + encodeURIComponent(a.id) + '" class="user-profile-article-item">' +
                '<span>' + escapeHtml(a.title) + '</span>' +
                '<span style="color: var(--text-muted); font-size: 0.78rem;">' + escapeHtml(articleDate) + '</span>' +
              '</a>';
            }).join('') +
            '</div>';
        }

        userModalBody.innerHTML =
          '<div class="user-profile-header">' +
            '<div class="user-profile-avatar">' + escapeHtml(initials) + '</div>' +
            '<div>' +
              '<div class="user-profile-name">' + escapeHtml(u.name || userId) + '</div>' +
              (u.specialization ? '<div class="user-profile-spec">' + escapeHtml(u.specialization) + '</div>' : '') +
              (u.company ? '<div class="user-profile-company">' + escapeHtml(u.company) + '</div>' : '') +
            '</div>' +
          '</div>' +
          (u.bio ? '<div class="user-profile-bio">' + escapeHtml(u.bio) + '</div>' : '') +
          '<div class="user-profile-stats">' +
            '<div class="user-profile-stat-box" title="Сумма оценок публикаций, ответов и комментариев. Лайки не учитываются"><span class="user-profile-stat-num user-profile-rating-num">' + (stats.rating !== undefined ? stats.rating : (u.rating !== undefined ? u.rating : 0)) + '</span><span class="user-profile-stat-label">Рейтинг</span></div>' +
            '<div class="user-profile-stat-box"><span class="user-profile-stat-num">' + (stats.articlesCount || stats.publicationsCount || 0) + '</span><span class="user-profile-stat-label">Публикаций</span></div>' +
            '<div class="user-profile-stat-box"><span class="user-profile-stat-num">' + (stats.answersCount || 0) + '</span><span class="user-profile-stat-label">Ответов</span></div>' +
            '<div class="user-profile-stat-box"><span class="user-profile-stat-num">' + (stats.solutionsCount || 0) + '</span><span class="user-profile-stat-label">Решений</span></div>' +
          '</div>' +
          articlesHtml;
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') return;
        if (seq !== profileRequestSeq || currentOpenUserId !== userId) return;
        userModalBody.innerHTML = '<div class="feed-settings-error-msg" style="padding: 20px;">Ошибка загрузки профиля</div>';
      });
  }

  function initUserProfileModal() {
    userModal = document.getElementById('userProfileModal');
    btnCloseUserModal = document.getElementById('btnCloseUserProfileModal');
    userModalBody = document.getElementById('userProfileModalBody');

    if (btnCloseUserModal && userModal) {
      btnCloseUserModal.removeEventListener('click', closeUserProfileModal);
      btnCloseUserModal.addEventListener('click', closeUserProfileModal);

      userModal.addEventListener('click', function (e) {
        if (e.target === userModal) closeUserProfileModal();
      });
    }

    if (!isEventsBound) {
      isEventsBound = true;

      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && userModal && userModal.style.display !== 'none') {
          e.preventDefault();
          closeUserProfileModal();
        } else if (e.key === 'Enter' || e.key === ' ') {
          const authorBtn = e.target.closest && e.target.closest('.btn-author-profile');
          if (authorBtn && authorBtn.tagName !== 'BUTTON' && authorBtn.tagName !== 'A') {
            e.preventDefault();
            authorBtn.click();
          }
        }
      });

      document.addEventListener('click', function (e) {
        const authorBtn = e.target.closest && e.target.closest('.btn-author-profile');
        if (authorBtn) {
          e.preventDefault();
          e.stopPropagation();
          const authorId = authorBtn.getAttribute('data-author-id') || authorBtn.getAttribute('data-user-id');
          if (authorId) {
            lastProfileTriggerEl = authorBtn;
            openUserProfileModal(authorId, authorBtn);
          }
        }
      }, true);

      window.addEventListener('smartcontractum:voted', function () {
        if (currentOpenUserId && userModal && userModal.style.display !== 'none') {
          openUserProfileModal(currentOpenUserId, null, true);
        }
      });
    }
  }

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initUserProfileModal);
    } else {
      initUserProfileModal();
    }
  }

  window.openUserProfileModal = openUserProfileModal;
  window.closeUserProfileModal = closeUserProfileModal;
  window.SmartContractumProfile = {
    initUserProfileModal: initUserProfileModal,
    openUserProfileModal: openUserProfileModal,
    closeUserProfileModal: closeUserProfileModal
  };

})(typeof window !== 'undefined' ? window : this);
