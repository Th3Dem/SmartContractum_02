/**
 * profile.js - Единый общий модуль профиля пользователя SmartContractum
 *
 * Используется совместно в:
 * 1. Ленте публикаций (feed.html, feed.js)
 * 2. Чтении публикации (article.html, article.js)
 * 3. Отдельной странице профиля (profile.html)
 *
 * Обеспечивает:
 * - Инициализацию и управление компактным модальным окном профиля (#userProfileModal)
 * - Делегирование кликов по .btn-author-profile (data-author-id / data-user-id)
 * - Загрузку данных профиля с бэкенда (/api/users/:id)
 * - Отображение репутации и активности (Рейтинг, мета-строка активности)
 * - Подписку на автора и переход в полный профиль (profile.html?id=:id)
 * - Обновление при голосованиях (событие 'smartcontractum:voted')
 * - Доступность: закрытие по Escape, клику вне карточки, фокус на кнопке закрытия
 *
 * 100% Offline-First, Zero Emojis, Zero Em Dashes
 */

(function (window) {
  'use strict';

  function escapeHtml(str) {
    if (!str && str !== 0) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function pluralizeRu(n, one, few, many) {
    var count = Math.abs(Number(n) || 0);
    var rem100 = count % 100;
    var rem10 = count % 10;
    if (rem100 >= 11 && rem100 <= 19) {
      return count + ' ' + many;
    }
    if (rem10 === 1) {
      return count + ' ' + one;
    }
    if (rem10 >= 2 && rem10 <= 4) {
      return count + ' ' + few;
    }
    return count + ' ' + many;
  }

  function pluralizePublications(n) {
    return pluralizeRu(n, 'публикация', 'публикации', 'публикаций');
  }

  function pluralizeAnswers(n) {
    return pluralizeRu(n, 'ответ', 'ответа', 'ответов');
  }

  function pluralizeSolutions(n) {
    return pluralizeRu(n, 'решение', 'решения', 'решений');
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

    const modalTitle = document.getElementById('userProfileModalTitle');
    if (modalTitle) {
      modalTitle.textContent = 'Профиль пользователя';
    }

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

        const isOwn = !!(u.isOwnProfile || (window.currentUser && (window.currentUser.id === userId || window.currentUser.id === u.id)));
        const isSubscribed = !isOwn && !!u.isSubscribed;

        const initials = u.initials || (u.name ? u.name.split(' ').map(function (s) { return s[0]; }).join('').toUpperCase() : 'SC');
        const stats = u.stats || {};
        const rating = stats.rating !== undefined ? stats.rating : (u.rating !== undefined ? u.rating : 0);
        const pubsCount = stats.publicationsCount !== undefined ? stats.publicationsCount : (stats.articlesCount !== undefined ? stats.articlesCount : (u.publicationsCount !== undefined ? u.publicationsCount : 0));
        const answersCount = stats.answersCount !== undefined ? stats.answersCount : (u.answersCount !== undefined ? u.answersCount : 0);
        const solutionsCount = stats.solutionsCount !== undefined ? stats.solutionsCount : (u.solutionsCount !== undefined ? u.solutionsCount : 0);

        let avatarHtml = '';
        if (u.avatar) {
          avatarHtml = '<img src="' + escapeHtml(u.avatar) + '" alt="' + escapeHtml(u.name || userId) + '" class="user-profile-avatar-img">';
        } else {
          avatarHtml = '<span class="user-profile-avatar-initials">' + escapeHtml(initials) + '</span>';
        }

        const profileUrl = 'profile.html?id=' + encodeURIComponent(userId);

        let actionsHtml = '<div class="quick-profile-actions">';
        if (!isOwn) {
          actionsHtml += '<button type="button" class="btn btn-secondary btn-quick-profile-subscribe' + (isSubscribed ? ' is-subscribed' : '') + '" data-author-id="' + escapeHtml(userId) + '">' +
            (isSubscribed ? 'Вы подписаны' : 'Подписаться') +
          '</button>';
        }
        actionsHtml += '<a href="' + escapeHtml(profileUrl) + '" class="btn btn-primary btn-quick-profile-open">Открыть профиль →</a>' +
        '</div>';

        const metaLine = escapeHtml(pluralizePublications(pubsCount)) + ' · ' +
                         escapeHtml(pluralizeAnswers(answersCount)) + ' · ' +
                         escapeHtml(pluralizeSolutions(solutionsCount));

        userModalBody.innerHTML =
          '<div class="user-profile-header">' +
            '<div class="user-profile-avatar">' + avatarHtml + '</div>' +
            '<div class="user-profile-identity">' +
              '<h3 class="user-profile-name"><a href="' + escapeHtml(profileUrl) + '" class="user-profile-name-link" title="Перейти в профиль">' + escapeHtml(u.name || userId) + '</a></h3>' +
              (u.specialization ? '<div class="user-profile-spec">' + escapeHtml(u.specialization) + '</div>' : '') +
              (u.company ? '<div class="user-profile-company"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect><line x1="9" y1="22" x2="9" y2="22.01"></line><line x1="15" y1="22" x2="15" y2="22.01"></line><line x1="9" y1="18" x2="9" y2="18.01"></line><line x1="15" y1="18" x2="15" y2="18.01"></line><line x1="9" y1="14" x2="9" y2="14.01"></line><line x1="15" y1="14" x2="15" y2="14.01"></line><line x1="9" y1="10" x2="9" y2="10.01"></line><line x1="15" y1="10" x2="15" y2="10.01"></line><line x1="9" y1="6" x2="9" y2="6.01"></line><line x1="15" y1="6" x2="15" y2="6.01"></line></svg><span>' + escapeHtml(u.company) + '</span></div>' : '') +
            '</div>' +
          '</div>' +
          (u.bio ? '<div class="user-profile-bio">' + escapeHtml(u.bio) + '</div>' : '') +
          '<div class="user-profile-summary">' +
            '<div class="user-profile-stats">' +
              '<div class="user-profile-stat-box user-profile-rating-box" title="Сумма оценок публикаций, ответов и комментариев. Лайки не учитываются">' +
                '<span class="user-profile-stat-num user-profile-rating-num">' + escapeHtml(rating) + '</span>' +
                '<span class="user-profile-stat-label">Рейтинг</span>' +
              '</div>' +
            '</div>' +
            '<div class="user-profile-meta-line">' + metaLine + '</div>' +
          '</div>' +
          actionsHtml;

        const btnSub = userModalBody.querySelector('.btn-quick-profile-subscribe');
        if (btnSub) {
          btnSub.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (btnSub.disabled) return;
            btnSub.disabled = true;

            fetch('/api/subscriptions/toggle', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                targetType: 'author',
                targetId: userId,
                targetTitle: u.name || userId
              })
            })
              .then(function (res) {
                if (res.status === 401) {
                  const authModal = document.getElementById('authModal');
                  if (authModal) {
                    closeUserProfileModal();
                    authModal.style.display = 'flex';
                  }
                  return null;
                }
                return res.json();
              })
              .then(function (resData) {
                btnSub.disabled = false;
                if (!resData || !resData.success) return;
                const subState = !!(resData.subscribed || resData.isSubscribed);
                if (subState) {
                  btnSub.classList.add('is-subscribed');
                  btnSub.textContent = 'Вы подписаны';
                } else {
                  btnSub.classList.remove('is-subscribed');
                  btnSub.textContent = 'Подписаться';
                }
              })
              .catch(function () {
                btnSub.disabled = false;
              });
          });
        }
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

  function aggregateUserTopics(publications, options) {
    options = options || {};
    const maxTopics = options.maxTopics || 6;
    if (!Array.isArray(publications) || publications.length === 0) {
      return [];
    }

    const counts = {};
    publications.forEach(function (pub) {
      if (!pub) return;
      let topicsList = [];
      if (Array.isArray(pub.topics) && pub.topics.length > 0) {
        topicsList = pub.topics;
      } else if (pub.topic) {
        topicsList = [pub.topic];
      } else if (pub.publicationSettings && pub.publicationSettings.topics) {
        topicsList = pub.publicationSettings.topics;
      }

      topicsList.forEach(function (t) {
        if (!t) return;
        const topicId = typeof t === 'object' ? (t.id || t.title) : String(t);
        if (topicId) {
          counts[topicId] = (counts[topicId] || 0) + 1;
        }
      });
    });

    const result = Object.keys(counts).map(function (tid) {
      let title = tid;
      if (window.PublicationConfig && typeof window.PublicationConfig.getTopicById === 'function') {
        const conf = window.PublicationConfig.getTopicById(tid);
        if (conf && conf.title) {
          title = conf.title;
        }
      }
      return {
        id: tid,
        title: title,
        count: counts[tid]
      };
    });

    result.sort(function (a, b) {
      return b.count - a.count;
    });

    return result.slice(0, maxTopics);
  }

  window.openUserProfileModal = openUserProfileModal;
  window.closeUserProfileModal = closeUserProfileModal;
  window.SmartContractumProfile = {
    initUserProfileModal: initUserProfileModal,
    openUserProfileModal: openUserProfileModal,
    closeUserProfileModal: closeUserProfileModal,
    aggregateUserTopics: aggregateUserTopics
  };

})(typeof window !== 'undefined' ? window : this);
