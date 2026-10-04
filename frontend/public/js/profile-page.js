/**
 * profile-page.js - Client script for full author profile page (profile.html)
 * 100% Offline-First, Zero Emojis, Zero Em Dashes
 */

(function (window) {
  'use strict';

  let currentProfile = null;
  let currentUser = null;
  let profileAbortController = null;
  let activeTab = 'overview';
  let activityItems = [];
  let activityOffset = 0;
  const activityLimit = 15;
  let activityHasMore = false;
  let isLoadingActivity = false;

  let pubSort = 'newest';
  let pubOffset = 0;
  const pubLimit = 10;
  let pubItems = [];
  let pubHasMore = false;
  let isLoadingPub = false;

  let questSort = 'newest';
  let questStatus = 'all';
  let questOffset = 0;
  const questLimit = 10;
  let questItems = [];
  let questHasMore = false;
  let isLoadingQuest = false;

  let ansFilter = 'all';
  let ansOffset = 0;
  const ansLimit = 10;
  let ansItems = [];
  let ansHasMore = false;
  let isLoadingAns = false;

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

    // 5. Tab counts
    renderTabCounts(p);

    // 6. Top contributions
    renderTopContributions(p.topContributions || []);

    // 7. Desktop sidebar
    renderSidebar(p);

    // 8. Reset tab caches
    pubOffset = 0; pubItems = [];
    questOffset = 0; questItems = [];
    ansOffset = 0; ansItems = [];

    // 8. Backwards-compatible publications container
    renderPublications(p.publications || p.articles || []);

    // 9. Load unified activity feed
    loadActivity(p.id || p.userId, false);

    // 10. Activate initial tab from URL
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const initialTab = urlParams.get('tab') || 'overview';
      setActiveTab(initialTab, false);
    } catch (e) {
      setActiveTab('overview', false);
    }
  }

  function setActiveTab(tabName, updateUrl) {
    if (updateUrl === undefined) updateUrl = true;
    const validTabs = ['overview', 'publications', 'questions', 'answers'];
    if (validTabs.indexOf(tabName) === -1) {
      tabName = 'overview';
    }
    activeTab = tabName;

    const tabButtons = {
      overview: document.getElementById('tabBtnOverview'),
      publications: document.getElementById('tabBtnPublications'),
      questions: document.getElementById('tabBtnQuestions'),
      answers: document.getElementById('tabBtnAnswers')
    };

    const tabPanels = {
      overview: document.getElementById('profileTabOverview'),
      publications: document.getElementById('profileTabPublications'),
      questions: document.getElementById('profileTabQuestions'),
      answers: document.getElementById('profileTabAnswers')
    };

    Object.keys(tabButtons).forEach(function (key) {
      const btn = tabButtons[key];
      const panel = tabPanels[key];
      const isCurrent = (key === tabName);

      if (btn) {
        btn.classList.toggle('is-active', isCurrent);
        btn.setAttribute('aria-selected', isCurrent ? 'true' : 'false');
      }
      if (panel) {
        panel.classList.toggle('is-active', isCurrent);
        panel.style.display = isCurrent ? 'block' : 'none';
      }
    });

    if (updateUrl && window.history && window.history.replaceState) {
      try {
        const url = new URL(window.location.href);
        if (tabName === 'overview') {
          url.searchParams.delete('tab');
        } else {
          url.searchParams.set('tab', tabName);
        }
        window.history.replaceState({}, '', url.toString());
      } catch (e) {}
    }

    if (currentProfile) {
      const uid = currentProfile.id || currentProfile.userId;
      if (tabName === 'publications') {
        if (pubItems.length === 0) {
          loadPublications(uid, false);
        }
      } else if (tabName === 'questions') {
        if (questItems.length === 0) {
          loadQuestions(uid, false);
        }
      } else if (tabName === 'answers') {
        if (ansItems.length === 0) {
          loadAnswers(uid, false);
        }
      }
    }
  }

  function renderTabCounts(p) {
    if (!p) return;
    const stats = p.stats || {};
    const pubVal = stats.publicationsCount !== undefined ? stats.publicationsCount : (p.publicationsCount || 0);
    const questVal = stats.questionsCount !== undefined ? stats.questionsCount : (p.questionsCount || 0);
    const ansVal = stats.answersCount !== undefined ? stats.answersCount : (p.answersCount || 0);

    const cPub = document.getElementById('tabCountPublications');
    if (cPub) cPub.textContent = pubVal;

    const cQuest = document.getElementById('tabCountQuestions');
    if (cQuest) cQuest.textContent = questVal;

    const cAns = document.getElementById('tabCountAnswers');
    if (cAns) cAns.textContent = ansVal;
  }

  function renderTopContributions(topList) {
    const sec = document.getElementById('profileTopContributionsSection');
    const grid = document.getElementById('profileTopContributionsGrid');
    if (!sec || !grid) return;

    if (!Array.isArray(topList) || topList.length === 0) {
      sec.style.display = 'none';
      grid.innerHTML = '';
      return;
    }

    sec.style.display = 'block';
    grid.innerHTML = topList.map(function (item) {
      const isSolution = item.isSolution || item.type === 'solution';
      const isQuestion = item.type === 'question' || item.materialType === 'question';
      let badgeClass = 'publication';
      let badgeText = 'Статья';
      if (isSolution) {
        badgeClass = 'solution';
        badgeText = '✓ Решение';
      } else if (isQuestion) {
        badgeClass = 'question';
        badgeText = 'Вопрос';
      }

      const ratingNum = item.rating || 0;
      const ratingDisplay = ratingNum >= 0 ? '+' + ratingNum : ratingNum;
      const title = item.title || 'Без названия';
      const url = item.url || ('article.html?id=' + encodeURIComponent(item.id));
      const snippet = item.contentSnippet ? '<p class="top-contrib-snippet">' + escapeHtml(item.contentSnippet) + '</p>' : '';
      const dateStr = item.date || (item.createdAt ? formatRegistrationDateRu(item.createdAt) : '');

      return '<div class="top-contribution-card">' +
        '<div class="top-contrib-header">' +
          '<span class="top-contrib-badge ' + badgeClass + '">' + badgeText + '</span>' +
          '<span class="top-contrib-rating">' + ratingDisplay + '</span>' +
        '</div>' +
        '<a href="' + url + '" class="top-contrib-title">' + escapeHtml(title) + '</a>' +
        snippet +
        '<div class="top-contrib-footer" style="display: flex; justify-content: space-between; align-items: center; margin-top: auto; font-size: 0.78rem; color: var(--text-muted);">' +
          '<span>' + escapeHtml(dateStr) + '</span>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  function renderSidebar(p) {
    if (!p) return;

    // 1. About widget
    const bioEl = document.getElementById('sidebarUserBio');
    if (bioEl) {
      if (p.bio && p.bio.trim()) {
        bioEl.textContent = p.bio.trim();
        bioEl.style.display = 'block';
      } else {
        bioEl.textContent = '';
        bioEl.style.display = 'none';
      }
    }

    const companyRow = document.getElementById('sidebarUserCompanyRow');
    const companyEl = document.getElementById('sidebarUserCompany');
    if (companyRow && companyEl) {
      if (p.company && p.company.trim()) {
        companyEl.textContent = p.company.trim();
        companyRow.style.display = 'flex';
      } else {
        companyRow.style.display = 'none';
      }
    }

    const websiteRow = document.getElementById('sidebarUserWebsiteRow');
    const websiteEl = document.getElementById('sidebarUserWebsite');
    if (websiteRow && websiteEl) {
      const site = (p.website || '').trim();
      if (site) {
        const fullUrl = /^[a-zA-Z][a-zA-Z\d+\-.]*:\/\//.test(site) ? site : ('https:' + '//' + site);
        const displaySite = site.replace(/^https?:\/\//i, '').replace(/\/$/, '');
        websiteEl.href = fullUrl;
        websiteEl.textContent = displaySite;
        websiteRow.style.display = 'flex';
      } else {
        websiteRow.style.display = 'none';
      }
    }

    const regRow = document.getElementById('sidebarUserRegistrationRow');
    const regEl = document.getElementById('sidebarUserRegistration');
    if (regEl) {
      const dateText = p.createdAt ? formatRegistrationDateRu(p.createdAt) : 'Недавно';
      regEl.textContent = dateText;
      if (regRow) regRow.style.display = 'flex';
    }

    // 2. Expertise widget
    const specEl = document.getElementById('sidebarUserSpecialization');
    if (specEl) {
      specEl.textContent = p.specialization && p.specialization.trim() ? p.specialization.trim() : 'Участник сообщества';
    }

    // 3. Topics widget
    const topicsContainer = document.getElementById('sidebarUserTopics');
    if (topicsContainer) {
      let topics = [];
      if (Array.isArray(p.topics) && p.topics.length > 0) {
        topics = p.topics;
      } else if (window.SmartContractumProfile && typeof window.SmartContractumProfile.aggregateUserTopics === 'function') {
        topics = window.SmartContractumProfile.aggregateUserTopics(p.publications || []);
      }

      if (topics.length > 0) {
        topicsContainer.innerHTML = topics.map(function (item) {
          let title = item.title || item.name || item.id || 'Тема';
          if (window.PublicationConfig && typeof window.PublicationConfig.getTopicById === 'function') {
            const conf = window.PublicationConfig.getTopicById(item.id || item.title);
            if (conf && conf.title) {
              title = conf.title;
            }
          }
          const cnt = item.count !== undefined ? item.count : '';
          const countBadge = cnt ? (' <span class="profile-topic-count">' + cnt + '</span>') : '';
          return '<span class="profile-sidebar-topic-pill" data-topic-id="' + escapeHtml(item.id || item.title) + '">' +
            '<span class="profile-topic-name">' + escapeHtml(title) + '</span>' +
            countBadge +
          '</span>';
        }).join('');
      } else {
        topicsContainer.innerHTML = '<div class="profile-sidebar-empty">Темы пока не определены</div>';
      }
    }

    // 4. Reputation widget
    const stats = p.stats || {};
    const ratingVal = stats.rating !== undefined ? stats.rating : (p.rating || 0);
    const pubVal = stats.publicationsCount !== undefined ? stats.publicationsCount : (p.publicationsCount || 0);
    const questVal = stats.questionsCount !== undefined ? stats.questionsCount : (p.questionsCount || 0);
    const solVal = stats.solutionsCount !== undefined ? stats.solutionsCount : (p.solutionsCount || 0);

    const rEl = document.getElementById('sidebarReputationRating');
    if (rEl) rEl.textContent = ratingVal;

    const sEl = document.getElementById('sidebarReputationSolutions');
    if (sEl) sEl.textContent = solVal;

    const pEl = document.getElementById('sidebarReputationPubs');
    if (pEl) pEl.textContent = pubVal;

    const qEl = document.getElementById('sidebarReputationQuestions');
    if (qEl) qEl.textContent = questVal;
  }

  function loadActivity(userId, append) {
    if (!userId || isLoadingActivity) return;

    const feedContainer = document.getElementById('profileActivityFeed');
    const actionsContainer = document.getElementById('profileActivityActions');

    if (!append) {
      activityOffset = 0;
      activityItems = [];
      if (feedContainer) {
        feedContainer.innerHTML = '<div class="profile-empty-state">Загрузка активности...</div>';
      }
    }

    isLoadingActivity = true;
    const url = '/api/users/' + encodeURIComponent(userId) + '/activity?limit=' + activityLimit + '&offset=' + activityOffset;

    fetch(url)
      .then(function (res) {
        if (!res.ok) throw new Error('ACTIVITY_LOAD_FAILED');
        return res.json();
      })
      .then(function (data) {
        isLoadingActivity = false;
        if (!data || !data.success) {
          throw new Error('ACTIVITY_INVALID_DATA');
        }
        const newItems = data.activity || [];
        if (append) {
          activityItems = activityItems.concat(newItems);
        } else {
          activityItems = newItems;
        }
        activityHasMore = Boolean(data.hasMore);
        renderActivityFeed(activityItems, activityHasMore);

        if (activeTab === 'answers') {
          renderAnswersTab();
        }
      })
      .catch(function () {
        isLoadingActivity = false;
        if (!append && feedContainer) {
          feedContainer.innerHTML = '<div class="profile-empty-state">Ошибка загрузки ленты активности</div>';
        }
        if (actionsContainer) {
          actionsContainer.style.display = 'none';
        }
      });
  }

  function renderActivityFeed(items, hasMore) {
    const feedContainer = document.getElementById('profileActivityFeed');
    const actionsContainer = document.getElementById('profileActivityActions');
    if (!feedContainer) return;

    if (!Array.isArray(items) || items.length === 0) {
      feedContainer.innerHTML = '<div class="profile-empty-state">Нет недавней активности</div>';
      if (actionsContainer) actionsContainer.style.display = 'none';
      return;
    }

    feedContainer.innerHTML = items.map(function (item) {
      let badgeHtml = '';
      let titleWrapHtml = '';

      const ratingVal = item.rating || 0;
      const ratingDisplay = ratingVal >= 0 ? '+' + ratingVal : ratingVal;
      const dateDisplay = item.date || (item.createdAt ? formatRegistrationDateRu(item.createdAt) : '');
      const url = item.url || ('article.html?id=' + encodeURIComponent(item.id));

      if (item.type === 'answer') {
        const solutionBadge = item.isSolution
          ? '<span class="activity-solution-badge">✓ Решение</span>'
          : '';
        badgeHtml = '<span class="activity-type-badge activity-badge-answer">Ответ</span>' + solutionBadge;
        titleWrapHtml = '<div class="activity-card-title-wrap">' +
          '<span class="activity-context-label">К вопросу:</span>' +
          '<a href="' + url + '" class="activity-card-title">' + escapeHtml(item.title) + '</a>' +
        '</div>';
      } else if (item.type === 'question') {
        badgeHtml = '<span class="activity-type-badge activity-badge-question">Вопрос</span>';
        titleWrapHtml = '<div class="activity-card-title-wrap">' +
          '<a href="' + url + '" class="activity-card-title">' + escapeHtml(item.title) + '</a>' +
        '</div>';
      } else {
        badgeHtml = '<span class="activity-type-badge activity-badge-publication">Статья</span>';
        titleWrapHtml = '<div class="activity-card-title-wrap">' +
          '<a href="' + url + '" class="activity-card-title">' + escapeHtml(item.title) + '</a>' +
        '</div>';
      }

      const snippetHtml = item.contentSnippet
        ? '<div class="activity-card-snippet">' + escapeHtml(item.contentSnippet) + '</div>'
        : '';

      let extraMeta = '';
      if (item.type === 'publication' && item.commentsCount !== undefined) {
        extraMeta = '<span class="activity-meta-stat" title="Комментарии">' +
          '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>' +
          ' <span>' + item.commentsCount + '</span>' +
        '</span>';
      } else if (item.type === 'question' && item.answersCount !== undefined) {
        extraMeta = '<span class="activity-meta-stat" title="Ответы">' +
          '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>' +
          ' <span>' + item.answersCount + '</span>' +
        '</span>';
      }

      return '<div class="activity-card">' +
        '<div class="activity-card-header">' +
          badgeHtml +
          titleWrapHtml +
        '</div>' +
        snippetHtml +
        '<div class="activity-card-footer">' +
          '<span class="activity-meta-date">' + escapeHtml(dateDisplay) + '</span>' +
          '<span class="activity-meta-stat" title="Рейтинг">' +
            '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>' +
            ' <span>' + ratingDisplay + '</span>' +
          '</span>' +
          extraMeta +
        '</div>' +
      '</div>';
    }).join('');

    if (actionsContainer) {
      actionsContainer.style.display = hasMore ? 'block' : 'none';
    }
  }

  // --------------------------------------------------------------------------
  // Publications Tab: Loader & Renderer
  // --------------------------------------------------------------------------
  function loadPublications(userId, append) {
    if (!userId || isLoadingPub) return;

    const list = document.getElementById('profilePublicationsList');
    const actions = document.getElementById('profilePublicationsActions');

    if (!append) {
      pubOffset = 0;
      pubItems = [];
      if (list) {
        list.innerHTML = '<div class="profile-empty-state">Загрузка материалов...</div>';
      }
      if (actions) actions.style.display = 'none';
    }

    isLoadingPub = true;
    const url = '/api/users/' + encodeURIComponent(userId) + '/publications?sort=' + encodeURIComponent(pubSort) + '&limit=' + pubLimit + '&offset=' + pubOffset;

    fetch(url)
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (!data || !data.success) {
          throw new Error((data && data.error) || 'Failed to load publications');
        }
        const incoming = Array.isArray(data.items) ? data.items : [];
        pubItems = append ? pubItems.concat(incoming) : incoming;
        pubHasMore = Boolean(data.hasMore);
        renderPublicationsTab(pubItems, append, pubHasMore, incoming);
      })
      .catch(function () {
        if (!append && list) {
          list.innerHTML = '<div class="profile-empty-state">Ошибка загрузки публикаций</div>';
        }
      })
      .finally(function () {
        isLoadingPub = false;
      });
  }

  function renderPublicationsTab(items, append, hasMore, newItems) {
    const list = document.getElementById('profilePublicationsList');
    const actions = document.getElementById('profilePublicationsActions');
    if (!list) return;

    if (!Array.isArray(items) || items.length === 0) {
      list.innerHTML = '<div class="profile-empty-state">Пользователь пока не публиковал материалы.</div>';
      if (actions) actions.style.display = 'none';
      return;
    }

    if (!append) {
      list.innerHTML = '';
    }

    const toRender = append ? (newItems || []) : items;
    toRender.forEach(function (item) {
      if (window.SmartContractumCard && typeof window.SmartContractumCard.createCardElement === 'function') {
        const cardEl = window.SmartContractumCard.createCardElement(item);
        list.appendChild(cardEl);
      } else {
        const fallback = document.createElement('div');
        fallback.className = 'user-profile-article-item';
        fallback.innerHTML = '<a href="' + (item.url || ('article.html?id=' + encodeURIComponent(item.id))) + '">' + escapeHtml(item.title) + '</a>';
        list.appendChild(fallback);
      }
    });

    if (actions) {
      actions.style.display = hasMore ? 'block' : 'none';
    }
  }

  // --------------------------------------------------------------------------
  // Questions Tab: Loader & Renderer
  // --------------------------------------------------------------------------
  function loadQuestions(userId, append) {
    if (!userId || isLoadingQuest) return;

    const list = document.getElementById('profileQuestionsList');
    const actions = document.getElementById('profileQuestionsActions');

    if (!append) {
      questOffset = 0;
      questItems = [];
      if (list) {
        list.innerHTML = '<div class="profile-empty-state">Загрузка вопросов...</div>';
      }
      if (actions) actions.style.display = 'none';
    }

    isLoadingQuest = true;
    const url = '/api/users/' + encodeURIComponent(userId) + '/questions?sort=' + encodeURIComponent(questSort) + '&status=' + encodeURIComponent(questStatus) + '&limit=' + questLimit + '&offset=' + questOffset;

    fetch(url)
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (!data || !data.success) {
          throw new Error((data && data.error) || 'Failed to load questions');
        }
        const incoming = Array.isArray(data.items) ? data.items : [];
        questItems = append ? questItems.concat(incoming) : incoming;
        questHasMore = Boolean(data.hasMore);
        renderQuestionsTab(questItems, append, questHasMore, incoming);
      })
      .catch(function () {
        if (!append && list) {
          list.innerHTML = '<div class="profile-empty-state">Ошибка загрузки вопросов</div>';
        }
      })
      .finally(function () {
        isLoadingQuest = false;
      });
  }

  function renderQuestionsTab(items, append, hasMore, newItems) {
    const list = document.getElementById('profileQuestionsList');
    const actions = document.getElementById('profileQuestionsActions');
    if (!list) return;

    if (!Array.isArray(items) || items.length === 0) {
      list.innerHTML = '<div class="profile-empty-state">Пользователь пока не задавал вопросы.</div>';
      if (actions) actions.style.display = 'none';
      return;
    }

    if (!append) {
      list.innerHTML = '';
    }

    const toRender = append ? (newItems || []) : items;
    toRender.forEach(function (item) {
      item.materialType = 'question';
      if (item.isSolved) {
        item.hasSolution = true;
      }
      if (window.SmartContractumCard && typeof window.SmartContractumCard.createCardElement === 'function') {
        const cardEl = window.SmartContractumCard.createCardElement(item);
        list.appendChild(cardEl);
      } else {
        const fallback = document.createElement('div');
        fallback.className = 'user-profile-article-item';
        fallback.innerHTML = '<a href="' + (item.url || ('article.html?id=' + encodeURIComponent(item.id))) + '">' + escapeHtml(item.title) + '</a>';
        list.appendChild(fallback);
      }
    });

    if (actions) {
      actions.style.display = hasMore ? 'block' : 'none';
    }
  }

  // --------------------------------------------------------------------------
  // Answers Tab: Loader & Renderer
  // --------------------------------------------------------------------------
  function loadAnswers(userId, append) {
    if (!userId || isLoadingAns) return;

    const list = document.getElementById('profileAnswersList');
    const actions = document.getElementById('profileAnswersActions');

    if (!append) {
      ansOffset = 0;
      ansItems = [];
      if (list) {
        list.innerHTML = '<div class="profile-empty-state">Загрузка ответов...</div>';
      }
      if (actions) actions.style.display = 'none';
    }

    isLoadingAns = true;
    const url = '/api/users/' + encodeURIComponent(userId) + '/answers?filter=' + encodeURIComponent(ansFilter) + '&limit=' + ansLimit + '&offset=' + ansOffset;

    fetch(url)
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (!data || !data.success) {
          throw new Error((data && data.error) || 'Failed to load answers');
        }
        const incoming = Array.isArray(data.items) ? data.items : [];
        ansItems = append ? ansItems.concat(incoming) : incoming;
        ansHasMore = Boolean(data.hasMore);
        renderAnswersTab(ansItems, append, ansHasMore, incoming);
      })
      .catch(function () {
        if (!append && list) {
          list.innerHTML = '<div class="profile-empty-state">Ошибка загрузки ответов</div>';
        }
      })
      .finally(function () {
        isLoadingAns = false;
      });
  }

  function renderAnswersTab(items, append, hasMore, newItems) {
    const list = document.getElementById('profileAnswersList');
    const actions = document.getElementById('profileAnswersActions');
    if (!list) return;

    if (!Array.isArray(items) || items.length === 0) {
      list.innerHTML = '<div class="profile-empty-state">Пользователь пока не публиковал ответы на вопросы.</div>';
      if (actions) actions.style.display = 'none';
      return;
    }

    if (!append) {
      list.innerHTML = '';
    }

    const toRender = append ? (newItems || []) : items;
    toRender.forEach(function (item) {
      const cardEl = document.createElement('div');
      cardEl.className = 'answer-item-card';

      const ratingVal = item.rating || 0;
      const ratingDisplay = ratingVal >= 0 ? '+' + ratingVal : ratingVal;
      const dateDisplay = item.date || (item.createdAt ? formatRegistrationDateRu(item.createdAt) : '');
      const questionTitle = item.questionTitle || item.title || 'Вопрос';
      const questionUrl = item.url || ('article.html?id=' + encodeURIComponent(item.questionId || item.id));

      const solutionBadge = item.isSolution
        ? '<span class="meta-badge solution-badge">✓ Решение</span>'
        : '';
      const snippetHtml = item.contentSnippet
        ? '<div class="answer-card-snippet">' + escapeHtml(item.contentSnippet) + '</div>'
        : '';

      cardEl.innerHTML =
        '<div class="answer-item-header">' +
          '<div class="answer-badges">' +
            '<span class="meta-badge answer-badge">Ответ</span>' +
            solutionBadge +
          '</div>' +
          '<div class="answer-question-wrap">' +
            '<span class="answer-context-label">К вопросу:</span>' +
            '<a href="' + questionUrl + '" class="answer-question-title">' + escapeHtml(questionTitle) + '</a>' +
          '</div>' +
        '</div>' +
        snippetHtml +
        '<div class="answer-item-footer">' +
          '<span class="answer-meta-date">' + escapeHtml(dateDisplay) + '</span>' +
          '<span class="answer-meta-rating" title="Рейтинг ответа">' +
            '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>' +
            ' <span>' + ratingDisplay + '</span>' +
          '</span>' +
        '</div>';

      list.appendChild(cardEl);
    });

    if (actions) {
      actions.style.display = hasMore ? 'block' : 'none';
    }
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
    const inpSite = document.getElementById('editProfileWebsite');
    const inpBio = document.getElementById('editProfileBio');

    if (inpName) inpName.value = currentProfile.name || '';
    if (inpSpec) inpSpec.value = currentProfile.specialization || '';
    if (inpComp) inpComp.value = currentProfile.company || '';
    if (inpSite) inpSite.value = currentProfile.website || '';
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
    const inpSite = document.getElementById('editProfileWebsite');
    const inpBio = document.getElementById('editProfileBio');
    const saveBtn = document.getElementById('btnSaveProfile');

    const payload = {
      name: (inpName ? inpName.value : '').trim(),
      specialization: (inpSpec ? inpSpec.value : '').trim(),
      company: (inpComp ? inpComp.value : '').trim(),
      website: (inpSite ? inpSite.value : '').trim(),
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
          currentProfile.website = data.profile.website || payload.website;
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

    // 8. Tab switching navigation
    const tabBtns = document.querySelectorAll('.profile-tab-btn[data-tab]');
    for (let i = 0; i < tabBtns.length; i++) {
      tabBtns[i].addEventListener('click', function () {
        const tab = this.getAttribute('data-tab');
        if (tab) setActiveTab(tab, true);
      });
    }

    // 9. Load more activity
    const btnLoadMore = document.getElementById('btnProfileLoadMore');
    if (btnLoadMore) {
      btnLoadMore.addEventListener('click', function () {
        if (currentProfile && (currentProfile.id || currentProfile.userId)) {
          activityOffset += activityLimit;
          loadActivity(currentProfile.id || currentProfile.userId, true);
        }
      });
    }

    // 10. History popstate navigation
    window.addEventListener('popstate', function () {
      try {
        const params = new URLSearchParams(window.location.search);
        const tab = params.get('tab') || 'overview';
        setActiveTab(tab, false);
      } catch (e) {}
    });

    // 11. Publications toolbar sorting
    const pubSortBtns = document.querySelectorAll('[data-pub-sort]');
    for (let i = 0; i < pubSortBtns.length; i++) {
      pubSortBtns[i].addEventListener('click', function () {
        const sort = this.getAttribute('data-pub-sort');
        if (sort === pubSort) return;
        pubSort = sort;
        for (let j = 0; j < pubSortBtns.length; j++) {
          pubSortBtns[j].classList.toggle('is-active', pubSortBtns[j] === this);
        }
        pubOffset = 0;
        pubItems = [];
        if (currentProfile && (currentProfile.id || currentProfile.userId)) {
          loadPublications(currentProfile.id || currentProfile.userId, false);
        }
      });
    }

    // 12. Publications Load More
    const btnLoadMorePub = document.getElementById('btnProfileLoadMorePublications');
    if (btnLoadMorePub) {
      btnLoadMorePub.addEventListener('click', function () {
        if (currentProfile && (currentProfile.id || currentProfile.userId) && pubHasMore && !isLoadingPub) {
          pubOffset += pubLimit;
          loadPublications(currentProfile.id || currentProfile.userId, true);
        }
      });
    }

    // 13. Questions toolbar sorting & status filtering
    const questSortBtns = document.querySelectorAll('[data-quest-sort]');
    for (let i = 0; i < questSortBtns.length; i++) {
      questSortBtns[i].addEventListener('click', function () {
        const sort = this.getAttribute('data-quest-sort');
        if (sort === questSort) return;
        questSort = sort;
        for (let j = 0; j < questSortBtns.length; j++) {
          questSortBtns[j].classList.toggle('is-active', questSortBtns[j] === this);
        }
        questOffset = 0;
        questItems = [];
        if (currentProfile && (currentProfile.id || currentProfile.userId)) {
          loadQuestions(currentProfile.id || currentProfile.userId, false);
        }
      });
    }

    const questStatusBtns = document.querySelectorAll('[data-quest-status]');
    for (let i = 0; i < questStatusBtns.length; i++) {
      questStatusBtns[i].addEventListener('click', function () {
        const status = this.getAttribute('data-quest-status');
        if (status === questStatus) return;
        questStatus = status;
        for (let j = 0; j < questStatusBtns.length; j++) {
          questStatusBtns[j].classList.toggle('is-active', questStatusBtns[j] === this);
        }
        questOffset = 0;
        questItems = [];
        if (currentProfile && (currentProfile.id || currentProfile.userId)) {
          loadQuestions(currentProfile.id || currentProfile.userId, false);
        }
      });
    }

    // 14. Questions Load More
    const btnLoadMoreQuest = document.getElementById('btnProfileLoadMoreQuestions');
    if (btnLoadMoreQuest) {
      btnLoadMoreQuest.addEventListener('click', function () {
        if (currentProfile && (currentProfile.id || currentProfile.userId) && questHasMore && !isLoadingQuest) {
          questOffset += questLimit;
          loadQuestions(currentProfile.id || currentProfile.userId, true);
        }
      });
    }

    // 15. Answers toolbar filter
    const ansFilterBtns = document.querySelectorAll('[data-ans-filter]');
    for (let i = 0; i < ansFilterBtns.length; i++) {
      ansFilterBtns[i].addEventListener('click', function () {
        const filter = this.getAttribute('data-ans-filter');
        if (filter === ansFilter) return;
        ansFilter = filter;
        for (let j = 0; j < ansFilterBtns.length; j++) {
          ansFilterBtns[j].classList.toggle('is-active', ansFilterBtns[j] === this);
        }
        ansOffset = 0;
        ansItems = [];
        if (currentProfile && (currentProfile.id || currentProfile.userId)) {
          loadAnswers(currentProfile.id || currentProfile.userId, false);
        }
      });
    }

    // 16. Answers Load More
    const btnLoadMoreAns = document.getElementById('btnProfileLoadMoreAnswers');
    if (btnLoadMoreAns) {
      btnLoadMoreAns.addEventListener('click', function () {
        if (currentProfile && (currentProfile.id || currentProfile.userId) && ansHasMore && !isLoadingAns) {
          ansOffset += ansLimit;
          loadAnswers(currentProfile.id || currentProfile.userId, true);
        }
      });
    }
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
    setActiveTab: setActiveTab,
    loadActivity: loadActivity,
    renderTopContributions: renderTopContributions,
    renderActivityFeed: renderActivityFeed,
    renderSidebar: renderSidebar,
    loadPublications: loadPublications,
    renderPublicationsTab: renderPublicationsTab,
    loadQuestions: loadQuestions,
    renderQuestionsTab: renderQuestionsTab,
    loadAnswers: loadAnswers,
    renderAnswersTab: renderAnswersTab,
    toggleSubscription: toggleSubscription,
    copyProfileLink: copyProfileLink,
    openEditModal: openEditModal,
    closeEditModal: closeEditModal,
    saveProfileEdit: saveProfileEdit
  };

  document.addEventListener('DOMContentLoaded', init);

})(window);
