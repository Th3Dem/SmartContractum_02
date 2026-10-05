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
  let actReqSeq = 0;
  let actAbortCtrl = null;

  let pubSort = 'newest';
  let pubOffset = 0;
  const pubLimit = 10;
  let pubItems = [];
  let pubHasMore = false;
  let isLoadingPub = false;
  let pubReqSeq = 0;
  let pubAbortCtrl = null;

  let questSort = 'newest';
  let questStatus = 'all';
  let questOffset = 0;
  const questLimit = 10;
  let questItems = [];
  let questHasMore = false;
  let isLoadingQuest = false;
  let questReqSeq = 0;
  let questAbortCtrl = null;

  let ansFilter = 'all';
  let ansSort = 'new';
  let ansOffset = 0;
  const ansLimit = 10;
  let ansItems = [];
  let ansHasMore = false;
  let isLoadingAns = false;
  let ansReqSeq = 0;
  let ansAbortCtrl = null;

  let commSort = 'new';
  let commOffset = 0;
  const commLimit = 10;
  let commItems = [];
  let commHasMore = false;
  let isLoadingComm = false;
  let commReqSeq = 0;
  let commAbortCtrl = null;

  let currentSearchQuery = '';
  let searchDebounceTimer = null;
  let lastEditTriggerEl = null;

  let currentTopic = '';
  let tabLoadedState = {
    overview: null,
    publications: null,
    questions: null,
    answers: null,
    comments: null
  };

  function getCurrentTabParams(tabName) {
    if (tabName === 'publications') {
      return { q: currentSearchQuery, sort: pubSort, topic: currentTopic };
    }
    if (tabName === 'questions') {
      return { q: currentSearchQuery, sort: questSort, topic: currentTopic, status: questStatus };
    }
    if (tabName === 'answers') {
      return { q: currentSearchQuery, filter: ansFilter, sort: ansSort };
    }
    if (tabName === 'overview') {
      return { q: currentSearchQuery };
    }
    if (tabName === 'comments') {
      return { q: currentSearchQuery, sort: commSort };
    }
    return {};
  }

  function areTabParamsEqual(p1, p2) {
    if (!p1 || !p2) return false;
    const keys1 = Object.keys(p1);
    const keys2 = Object.keys(p2);
    if (keys1.length !== keys2.length) return false;
    for (let i = 0; i < keys1.length; i++) {
      const k = keys1[i];
      if (p1[k] !== p2[k]) return false;
    }
    return true;
  }

  function invalidateTabCaches(tabs) {
    const list = tabs || ['overview', 'publications', 'questions', 'answers', 'comments'];
    for (let i = 0; i < list.length; i++) {
      const t = list[i];
      tabLoadedState[t] = null;
      if (t === 'publications') {
        pubItems = [];
        pubOffset = 0;
      } else if (t === 'questions') {
        questItems = [];
        questOffset = 0;
      } else if (t === 'answers') {
        ansItems = [];
        ansOffset = 0;
      } else if (t === 'overview') {
        activityItems = [];
        activityOffset = 0;
      } else if (t === 'comments') {
        commItems = [];
        commOffset = 0;
        if (typeof commentsItems !== 'undefined') commentsItems = [];
        if (typeof commentsOffset !== 'undefined') commentsOffset = 0;
      }
    }
  }

  function updateSearchInputUI(q) {
    const val = q || '';
    const profInput = document.getElementById('profileSearchInput');
    if (profInput) {
      profInput.value = val;
    }
    const searchInputs = document.querySelectorAll(
      '#profileSearchInput, .header-search-input, .feed-toolbar-search-input, input[type="search"]'
    );
    for (let i = 0; i < searchInputs.length; i++) {
      searchInputs[i].value = val;
    }
    const clearBtn = document.getElementById('btnProfileSearchClear');
    if (clearBtn) {
      clearBtn.style.display = (val && String(val).trim()) ? 'flex' : 'none';
    }
    const searchClearBtn = document.getElementById('btnProfileSearchClear');
    if (searchClearBtn) {
      searchClearBtn.style.display = q ? 'flex' : 'none';
    }
  }

  function updatePubSortUI(sort) {
    const pubSortBtns = document.querySelectorAll('[data-pub-sort]');
    for (let i = 0; i < pubSortBtns.length; i++) {
      const s = pubSortBtns[i].getAttribute('data-pub-sort');
      const isActive = (s === sort);
      pubSortBtns[i].classList.toggle('is-active', isActive);
      if (pubSortBtns[i].hasAttribute('aria-pressed')) {
        pubSortBtns[i].setAttribute('aria-pressed', isActive ? 'true' : 'false');
      }
    }
  }

  function updateQuestSortUI(sort) {
    const questSortBtns = document.querySelectorAll('[data-quest-sort]');
    for (let i = 0; i < questSortBtns.length; i++) {
      const s = questSortBtns[i].getAttribute('data-quest-sort');
      const isActive = (s === sort);
      questSortBtns[i].classList.toggle('is-active', isActive);
      if (questSortBtns[i].hasAttribute('aria-pressed')) {
        questSortBtns[i].setAttribute('aria-pressed', isActive ? 'true' : 'false');
      }
    }
  }

  function updateQuestStatusUI(status) {
    const questStatusBtns = document.querySelectorAll('[data-quest-status]');
    for (let i = 0; i < questStatusBtns.length; i++) {
      const s = questStatusBtns[i].getAttribute('data-quest-status');
      const isActive = (s === status);
      questStatusBtns[i].classList.toggle('is-active', isActive);
      if (questStatusBtns[i].hasAttribute('aria-pressed')) {
        questStatusBtns[i].setAttribute('aria-pressed', isActive ? 'true' : 'false');
      }
    }
  }

  function updateAnsFilterUI(filter) {
    const ansFilterBtns = document.querySelectorAll('[data-ans-filter]');
    for (let i = 0; i < ansFilterBtns.length; i++) {
      const f = ansFilterBtns[i].getAttribute('data-ans-filter');
      const isActive = (f === filter);
      ansFilterBtns[i].classList.toggle('is-active', isActive);
      if (ansFilterBtns[i].hasAttribute('aria-pressed')) {
        ansFilterBtns[i].setAttribute('aria-pressed', isActive ? 'true' : 'false');
      }
    }
  }

  function updateAnsSortUI(sort) {
    const ansSortBtns = document.querySelectorAll('[data-ans-sort], #sortAnswersNewest, #sortAnswersRating');
    for (let i = 0; i < ansSortBtns.length; i++) {
      const s = ansSortBtns[i].getAttribute('data-ans-sort');
      const isActive = (s === sort);
      ansSortBtns[i].classList.toggle('is-active', isActive);
      if (ansSortBtns[i].hasAttribute('aria-pressed')) {
        ansSortBtns[i].setAttribute('aria-pressed', isActive ? 'true' : 'false');
      }
    }
  }

  function updateCommSortUI(sort) {
    const commSortBtns = document.querySelectorAll('[data-comm-sort]');
    for (let i = 0; i < commSortBtns.length; i++) {
      const s = commSortBtns[i].getAttribute('data-comm-sort');
      const isActive = (s === sort) || (s === 'new' && sort === 'newest') || (s === 'newest' && sort === 'new');
      commSortBtns[i].classList.toggle('is-active', isActive);
      if (commSortBtns[i].hasAttribute('aria-pressed')) {
        commSortBtns[i].setAttribute('aria-pressed', isActive ? 'true' : 'false');
      }
    }
  }

  function updateTopicFilterUI(topic) {
    const topicPills = document.querySelectorAll('.profile-sidebar-topic-pill[data-topic-id], [data-profile-topic]');
    for (let i = 0; i < topicPills.length; i++) {
      const tid = topicPills[i].getAttribute('data-topic-id') || topicPills[i].getAttribute('data-profile-topic');
      topicPills[i].classList.toggle('is-active', Boolean(topic && tid === topic));
    }
  }

  function setSearchQuery(q, updateUrl) {
    if (q === undefined || q === null) q = '';
    const normalized = String(q).trim();

    let urlMatches = false;
    if (typeof window !== 'undefined' && window.location && window.location.search !== undefined) {
      try {
        const searchParams = new URLSearchParams(window.location.search);
        const urlQ = (searchParams.get('q') || '').trim();
        urlMatches = (urlQ === normalized);
      } catch (e) {}
    }

    if (normalized === currentSearchQuery) {
      if (!updateUrl || urlMatches) {
        return;
      }
    }

    const queryChanged = (normalized !== currentSearchQuery);
    currentSearchQuery = normalized;

    if (queryChanged) {
      invalidateTabCaches();
      if (activeTab === 'publications') {
        pubItems = [];
        pubOffset = 0;
      } else if (activeTab === 'questions') {
        questItems = [];
        questOffset = 0;
      } else if (activeTab === 'answers') {
        ansItems = [];
        ansOffset = 0;
      } else if (activeTab === 'comments') {
        commItems = [];
        commOffset = 0;
        if (typeof commentsItems !== 'undefined') commentsItems = [];
        if (typeof commentsOffset !== 'undefined') commentsOffset = 0;
      } else {
        activityItems = [];
        activityOffset = 0;
      }
    }

    updateSearchInputUI(currentSearchQuery);

    if (updateUrl && window.history) {
      try {
        const url = new URL(window.location.href);
        if (currentSearchQuery) {
          url.searchParams.set('q', currentSearchQuery);
        } else {
          url.searchParams.delete('q');
        }
        const stateObj = {
          tab: activeTab,
          q: currentSearchQuery || undefined,
          topic: currentTopic || undefined,
          sort: (activeTab === 'publications' ? pubSort : (activeTab === 'questions' ? questSort : (activeTab === 'answers' ? ansSort : (activeTab === 'comments' ? commSort : undefined)))),
          status: (activeTab === 'questions' ? questStatus : undefined),
          filter: (activeTab === 'answers' ? ansFilter : undefined),
          ans_sort: (activeTab === 'answers' ? ansSort : undefined),
          comm_sort: (activeTab === 'comments' ? commSort : undefined)
        };
        if (window.history.pushState) {
          window.history.pushState(stateObj, '', url.toString());
        } else if (window.history.replaceState) {
          window.history.replaceState(stateObj, '', url.toString());
        }
      } catch (e) {}
    }

    const uid = (currentProfile && (currentProfile.id || currentProfile.userId)) || getUserIdFromUrl();
    if (uid) {
      if (activeTab === 'publications') {
        loadPublications(uid, false);
      } else if (activeTab === 'questions') {
        loadQuestions(uid, false);
      } else if (activeTab === 'answers') {
        loadAnswers(uid, false);
      } else if (activeTab === 'comments') {
        commOffset = 0;
        commItems = [];
        if (typeof loadComments === 'function') {
          loadComments(uid, false);
        }
      } else {
        loadActivity(uid, false);
      }
    }
  }

  function triggerSearch(val) {
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = null;
    }
    setSearchQuery(val, true);
  }

  function setTopicFilter(topic, updateUrl) {
    if (topic === undefined || topic === null) topic = '';
    const normalized = String(topic).trim();
    if (normalized === currentTopic) return;
    currentTopic = normalized;

    tabLoadedState.publications = null;
    pubItems = [];
    pubOffset = 0;
    tabLoadedState.questions = null;
    questItems = [];
    questOffset = 0;
    updateTopicFilterUI(currentTopic);

    if (updateUrl && window.history) {
      try {
        const url = new URL(window.location.href);
        if (currentTopic) {
          url.searchParams.set('topic', currentTopic);
        } else {
          url.searchParams.delete('topic');
        }
        if (window.history.pushState) {
          window.history.pushState({
            tab: activeTab,
            q: currentSearchQuery || undefined,
            topic: currentTopic || undefined,
            sort: (activeTab === 'publications' ? pubSort : (activeTab === 'questions' ? questSort : undefined)),
            status: (activeTab === 'questions' ? questStatus : undefined)
          }, '', url.toString());
        }
      } catch (e) {}
    }

    if (currentProfile) {
      const uid = currentProfile.id || currentProfile.userId;
      if (activeTab === 'publications') {
        loadPublications(uid, false);
      } else if (activeTab === 'questions') {
        loadQuestions(uid, false);
      }
    }
  }

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
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return '';
      const day = d.getDate();
      const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
      const month = months[d.getMonth()] || '';
      const year = d.getFullYear();
      return day + ' ' + month + ' ' + year;
    } catch (e) {
      return '';
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

  function setAuthState(user) {
    currentUser = user || null;
    window.currentUser = user || null;
    updateHeaderUserBar();
  }

  function checkAuthStatus(callback) {
    fetch('/api/auth/status')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.authenticated && data.user) {
          setAuthState(data.user);
        } else {
          setAuthState(null);
        }
        if (typeof callback === 'function') callback(currentUser);
      })
      .catch(function () {
        setAuthState(null);
        if (typeof callback === 'function') callback(null);
      });
  }

  function updateHeaderUserBar() {
    const userLabel = document.getElementById('headerUserLabel');
    const loginBtn = document.getElementById('headerLoginBtn');
    const userMenu = document.getElementById('headerUserMenu');
    const profileLink = document.getElementById('headerMenuProfileLink');

    if (userLabel) {
      userLabel.textContent = currentUser ? currentUser.name : 'Вход';
    }
    if (loginBtn) {
      loginBtn.title = currentUser
        ? 'Вы вошли как ' + currentUser.name + ' (меню пользователя)'
        : 'Войти в личный кабинет';
      loginBtn.setAttribute('aria-expanded', 'false');
    }
    if (profileLink && currentUser) {
      profileLink.href = 'profile.html?id=' + encodeURIComponent(currentUser.id);
    }
    if (userMenu && !currentUser) {
      userMenu.style.display = 'none';
    }
  }

  function loadHeaderNotifications() {
    const notifBtn = document.getElementById('headerNotificationsBtn');
    const notifBadge = document.getElementById('headerNotifBadge');
    const notifList = document.getElementById('notifListContainer');

    if (!notifBtn) return;
    fetch('/api/notifications')
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (!data || !data.success) return;
        const count = data.unreadCount || 0;
        if (notifBadge) {
          if (count > 0) {
            notifBadge.textContent = count > 99 ? '99+' : count;
            notifBadge.style.display = 'inline-flex';
          } else {
            notifBadge.style.display = 'none';
          }
        }
        if (notifList) {
          const list = data.notifications || [];
          if (list.length === 0) {
            notifList.innerHTML = '<div class="notif-empty-state">Нет новых уведомлений</div>';
          } else {
            notifList.innerHTML = '';
            list.forEach(function (n) {
              const item = document.createElement('a');
              item.className = 'notif-item' + (n.is_read ? ' is-read' : ' is-unread');
              item.href = n.article_id ? ('article.html?id=' + encodeURIComponent(n.article_id) + '#comments') : '#';
              item.innerHTML =
                '<div class="notif-item-title">' + escapeHtml(n.title) + '</div>' +
                '<div class="notif-item-msg">' + escapeHtml(n.message) + '</div>' +
                '<div class="notif-item-time">' + escapeHtml(n.created_at ? n.created_at.substring(0, 16).replace('T', ' ') : '') + '</div>';
              notifList.appendChild(item);
            });
          }
        }
      })
      .catch(function () {});
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
        const profile = (data.profile || data.user || data);
        if (isSilentRefresh && currentProfile) {
          const s = profile.stats || {};
          updateProfileStats({
            rating: s.rating !== undefined ? s.rating : (profile.rating !== undefined ? profile.rating : 0),
            publicationsCount: s.publicationsCount !== undefined ? s.publicationsCount : (profile.publicationsCount || 0),
            questionsCount: s.questionsCount !== undefined ? s.questionsCount : (profile.questionsCount || 0),
            answersCount: s.answersCount !== undefined ? s.answersCount : (profile.answersCount || 0),
            solutionsCount: s.solutionsCount !== undefined ? s.solutionsCount : (profile.solutionsCount || 0),
            commentsCount: s.commentsCount !== undefined ? s.commentsCount : (s.comments_count !== undefined ? s.comments_count : (profile.commentsCount !== undefined ? profile.commentsCount : (profile.comments_count || 0))),
            followersCount: s.followersCount !== undefined ? s.followersCount : (profile.followersCount || 0),
            followingCount: s.followingCount !== undefined ? s.followingCount : (profile.followingCount || 0)
          });
          return;
        }
        currentProfile = profile;
        renderProfile(currentProfile);
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') return;
        renderError(err && err.message === 'USER_NOT_FOUND' ? 'Пользователь не найден' : 'Ошибка загрузки профиля');
      });
  }

  function updateProfileStats(stats) {
    if (!stats) return;

    if (currentProfile) {
      currentProfile.stats = currentProfile.stats || {};
      if (stats.rating !== undefined) {
        currentProfile.stats.rating = stats.rating;
        currentProfile.rating = stats.rating;
      }
      if (stats.publicationsCount !== undefined) {
        currentProfile.stats.publicationsCount = stats.publicationsCount;
        currentProfile.publicationsCount = stats.publicationsCount;
      }
      if (stats.questionsCount !== undefined) {
        currentProfile.stats.questionsCount = stats.questionsCount;
        currentProfile.questionsCount = stats.questionsCount;
      }
      if (stats.answersCount !== undefined) {
        currentProfile.stats.answersCount = stats.answersCount;
        currentProfile.answersCount = stats.answersCount;
      }
      if (stats.solutionsCount !== undefined) {
        currentProfile.stats.solutionsCount = stats.solutionsCount;
        currentProfile.solutionsCount = stats.solutionsCount;
      }
      if (stats.commentsCount !== undefined || stats.comments_count !== undefined) {
        const commCnt = stats.commentsCount !== undefined ? stats.commentsCount : stats.comments_count;
        currentProfile.stats.commentsCount = commCnt;
        currentProfile.stats.comments_count = commCnt;
        currentProfile.commentsCount = commCnt;
        currentProfile.comments_count = commCnt;
      }
      if (stats.followersCount !== undefined) {
        currentProfile.stats.followersCount = stats.followersCount;
        currentProfile.followersCount = stats.followersCount;
      }
      if (stats.followingCount !== undefined) {
        currentProfile.stats.followingCount = stats.followingCount;
        currentProfile.followingCount = stats.followingCount;
      }
    }

    if (stats.rating !== undefined) {
      const rEl = document.getElementById('profileStatRating');
      if (rEl) rEl.textContent = stats.rating;
      const srEl = document.getElementById('sidebarReputationRating');
      if (srEl) srEl.textContent = stats.rating;
    }
    if (stats.publicationsCount !== undefined) {
      const pEl = document.getElementById('profileStatPublications');
      if (pEl) pEl.textContent = stats.publicationsCount;
      const cPub = document.getElementById('tabCountPublications');
      if (cPub) cPub.textContent = stats.publicationsCount;
      const spEl = document.getElementById('sidebarReputationPubs');
      if (spEl) spEl.textContent = stats.publicationsCount;
    }
    if (stats.questionsCount !== undefined) {
      const qEl = document.getElementById('profileStatQuestions');
      if (qEl) qEl.textContent = stats.questionsCount;
      const cQuest = document.getElementById('tabCountQuestions');
      if (cQuest) cQuest.textContent = stats.questionsCount;
      const sqEl = document.getElementById('sidebarReputationQuestions');
      if (sqEl) sqEl.textContent = stats.questionsCount;
    }
    if (stats.answersCount !== undefined) {
      const aEl = document.getElementById('profileStatAnswers');
      if (aEl) aEl.textContent = stats.answersCount;
      const cAns = document.getElementById('tabCountAnswers');
      if (cAns) cAns.textContent = stats.answersCount;
    }
    if (stats.solutionsCount !== undefined) {
      const sEl = document.getElementById('profileStatSolutions');
      if (sEl) sEl.textContent = stats.solutionsCount;
      const ssEl = document.getElementById('sidebarReputationSolutions');
      if (ssEl) ssEl.textContent = stats.solutionsCount;
    }
    if (stats.commentsCount !== undefined || stats.comments_count !== undefined) {
      const commCnt = stats.commentsCount !== undefined ? stats.commentsCount : stats.comments_count;
      const cComm = document.getElementById('profileTabCountComments') || document.getElementById('tabCountComments');
      if (cComm) cComm.textContent = commCnt;
    }
    if (stats.followersCount !== undefined) {
      const fEl = document.getElementById('profileStatFollowers');
      if (fEl) fEl.textContent = stats.followersCount;
    }
    if (stats.followingCount !== undefined) {
      const fwEl = document.getElementById('profileStatFollowing');
      if (fwEl) fwEl.textContent = stats.followingCount;
    }
  }

  function renderProfile(p) {
    if (!p) return;
    currentProfile = p;

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
    if (avatarImg) {
      avatarImg.onerror = function () {
        avatarImg.style.display = 'none';
        if (avatarInitials) {
          avatarInitials.textContent = getInitials(displayName);
          avatarInitials.style.display = 'block';
        }
      };
    }
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
      if (p.specialization && p.specialization.trim()) {
        specEl.textContent = p.specialization.trim();
        specEl.style.display = 'block';
      } else {
        specEl.textContent = '';
        specEl.style.display = 'none';
      }
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

    // 3. Stats & Reputation via unified updater
    const stats = p.stats || {};
    updateProfileStats({
      rating: stats.rating !== undefined ? stats.rating : (p.rating !== undefined ? p.rating : 0),
      publicationsCount: stats.publicationsCount !== undefined ? stats.publicationsCount : (p.publicationsCount || 0),
      questionsCount: stats.questionsCount !== undefined ? stats.questionsCount : (p.questionsCount || 0),
      answersCount: stats.answersCount !== undefined ? stats.answersCount : (p.answersCount || 0),
      solutionsCount: stats.solutionsCount !== undefined ? stats.solutionsCount : (p.solutionsCount || 0),
      commentsCount: stats.commentsCount !== undefined ? stats.commentsCount :
        (stats.comments_count !== undefined ? stats.comments_count :
        (p.commentsCount !== undefined ? p.commentsCount :
        (p.comments_count !== undefined ? p.comments_count : 0))),
      followersCount: stats.followersCount !== undefined ? stats.followersCount : (p.followersCount || 0),
      followingCount: stats.followingCount !== undefined ? stats.followingCount : (p.followingCount || 0)
    });

    const ageEl = document.getElementById('profileAccountAge');
    if (ageEl) {
      const regFormatted = p.createdAt ? formatRegistrationDateRu(p.createdAt) : '';
      if (regFormatted) {
        ageEl.textContent = 'На платформе с ' + regFormatted;
      } else {
        ageEl.textContent = 'Участник сообщества';
      }
    }

    // 4. Action Buttons (Own profile vs Foreign profile)
    renderActions(p);

    // 5. Tab counts
    renderTabCounts(p);

    // 6. Top contributions with fallback
    renderTopContributions(p.topContributions || [], p.publications || p.articles || []);

    // 7. Desktop sidebar
    renderSidebar(p);

    // 8. Reset tab caches
    pubOffset = 0; pubItems = [];
    questOffset = 0; questItems = [];
    commOffset = 0; commItems = [];
    tabLoadedState = { overview: null, publications: null, questions: null, answers: null, comments: null };

    // 8. Backwards-compatible publications container
    renderPublications(p.publications || p.articles || []);

    // 9. Load unified activity feed
    loadActivity(p.id || p.userId, false);

    // 10. Activate initial tab from URL
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const initialTab = urlParams.get('tab') || 'overview';
      if (urlParams.get('q')) {
        currentSearchQuery = urlParams.get('q').trim();
        updateSearchInputUI(currentSearchQuery);
      }
      if (urlParams.get('topic')) {
        currentTopic = urlParams.get('topic').trim();
        updateTopicFilterUI(currentTopic);
      }
      if (urlParams.get('sort')) {
        const s = urlParams.get('sort').trim();
        pubSort = s;
        questSort = s;
        commSort = s;
        ansSort = s;
        updatePubSortUI(pubSort);
        updateQuestSortUI(questSort);
        updateCommSortUI(commSort);
        updateAnsSortUI(ansSort);
      }
      if (urlParams.get('ans_sort')) {
        ansSort = urlParams.get('ans_sort').trim();
        updateAnsSortUI(ansSort);
      }
      const restoredCommSort = urlParams.get('comm_sort') || (initialTab === 'comments' ? urlParams.get('sort') : null) || (initialTab === 'comments' ? 'newest' : null);
      if (restoredCommSort) {
        commSort = restoredCommSort.trim();
        updateCommSortUI(commSort);
      }
      if (urlParams.get('status')) {
        questStatus = urlParams.get('status').trim();
        updateQuestStatusUI(questStatus);
      }
      if (urlParams.get('filter')) {
        ansFilter = urlParams.get('filter').trim();
        updateAnsFilterUI(ansFilter);
      }
      setActiveTab(initialTab, false);
    } catch (e) {
      setActiveTab('overview', false);
    }
  }

  function setActiveTab(tabName, updateUrl) {
    if (updateUrl === undefined) updateUrl = true;
    const validTabs = ['overview', 'publications', 'questions', 'answers', 'comments'];
    if (validTabs.indexOf(tabName) === -1) {
      tabName = 'overview';
    }
    activeTab = tabName;

    const tabButtons = {
      overview: document.getElementById('tabBtnOverview'),
      publications: document.getElementById('tabBtnPublications'),
      questions: document.getElementById('tabBtnQuestions'),
      answers: document.getElementById('tabBtnAnswers'),
      comments: document.getElementById('tabProfileComments') || document.getElementById('tabBtnComments')
    };

    const tabPanels = {
      overview: document.getElementById('profileTabOverview'),
      publications: document.getElementById('profileTabPublications'),
      questions: document.getElementById('profileTabQuestions'),
      answers: document.getElementById('profileTabAnswers'),
      comments: document.getElementById('profileTabComments')
    };

    Object.keys(tabButtons).forEach(function (key) {
      const btn = tabButtons[key];
      const panel = tabPanels[key];
      const isCurrent = (key === tabName);

      if (btn) {
        btn.classList.toggle('is-active', isCurrent);
        btn.setAttribute('aria-selected', isCurrent ? 'true' : 'false');
        if (isCurrent) {
          btn.setAttribute('aria-current', 'page');
        } else {
          btn.removeAttribute('aria-current');
        }
      }
      if (panel) {
        panel.classList.toggle('is-active', isCurrent);
        panel.style.display = isCurrent ? 'block' : 'none';
      }
    });

    if (updateUrl && window.history) {
      try {
        const url = new URL(window.location.href);
        if (tabName === 'overview') {
          url.searchParams.delete('tab');
        } else {
          url.searchParams.set('tab', tabName);
        }
        if (currentSearchQuery) {
          url.searchParams.set('q', currentSearchQuery);
        } else {
          url.searchParams.delete('q');
        }
        if (currentTopic) {
          url.searchParams.set('topic', currentTopic);
        } else {
          url.searchParams.delete('topic');
        }
        if (tabName === 'publications') {
          if (pubSort !== 'newest') url.searchParams.set('sort', pubSort);
          else url.searchParams.delete('sort');
          url.searchParams.delete('status');
          url.searchParams.delete('filter');
          url.searchParams.delete('ans_sort');
          url.searchParams.delete('comm_sort');
        } else if (tabName === 'questions') {
          if (questSort !== 'newest') url.searchParams.set('sort', questSort);
          else url.searchParams.delete('sort');
          if (questStatus !== 'all') url.searchParams.set('status', questStatus);
          else url.searchParams.delete('status');
          url.searchParams.delete('filter');
          url.searchParams.delete('ans_sort');
          url.searchParams.delete('comm_sort');
        } else if (tabName === 'answers') {
          if (ansFilter !== 'all') url.searchParams.set('filter', ansFilter);
          else url.searchParams.delete('filter');
          if (ansSort !== 'new') {
            url.searchParams.set('sort', ansSort);
            url.searchParams.set('ans_sort', ansSort);
          } else {
            url.searchParams.delete('sort');
            url.searchParams.delete('ans_sort');
          }
          url.searchParams.delete('status');
          url.searchParams.delete('comm_sort');
        } else if (tabName === 'comments') {
          if (commSort !== 'new' && commSort !== 'newest') {
            url.searchParams.set('sort', commSort);
            url.searchParams.set('comm_sort', commSort);
          } else {
            url.searchParams.delete('sort');
            url.searchParams.delete('comm_sort');
          }
          url.searchParams.delete('status');
          url.searchParams.delete('filter');
          url.searchParams.delete('ans_sort');
        } else {
          url.searchParams.delete('sort');
          url.searchParams.delete('status');
          url.searchParams.delete('filter');
          url.searchParams.delete('ans_sort');
          url.searchParams.delete('comm_sort');
        }

        const stateObj = {
          tab: tabName,
          q: currentSearchQuery || undefined,
          topic: currentTopic || undefined,
          sort: (tabName === 'publications' ? pubSort : (tabName === 'questions' ? questSort : (tabName === 'answers' ? ansSort : (tabName === 'comments' ? commSort : undefined)))),
          status: (tabName === 'questions' ? questStatus : undefined),
          filter: (tabName === 'answers' ? ansFilter : undefined),
          ans_sort: (tabName === 'answers' ? ansSort : undefined),
          comm_sort: (tabName === 'comments' ? commSort : undefined)
        };
        if (updateUrl === true || updateUrl === 'push') {
          if (window.history.pushState) {
            window.history.pushState(stateObj, '', url.toString());
          } else if (window.history.replaceState) {
            window.history.replaceState(stateObj, '', url.toString());
          }
        } else if (updateUrl === 'replace') {
          if (window.history.replaceState) {
            window.history.replaceState(stateObj, '', url.toString());
          }
        }
      } catch (e) {}
    }

    const uid = (currentProfile && (currentProfile.id || currentProfile.userId)) || getUserIdFromUrl();
    if (uid) {
      if (tabName === 'publications') {
        const currentParams = getCurrentTabParams('publications');
        const isUpToDate = tabLoadedState.publications && areTabParamsEqual(tabLoadedState.publications, currentParams);
        if (!isUpToDate || (pubItems.length === 0 && !isLoadingPub)) {
          pubItems = [];
          pubOffset = 0;
          loadPublications(uid, false);
        }
      } else if (tabName === 'questions') {
        const currentParams = getCurrentTabParams('questions');
        const isUpToDate = tabLoadedState.questions && areTabParamsEqual(tabLoadedState.questions, currentParams);
        if (!isUpToDate || (questItems.length === 0 && !isLoadingQuest)) {
          questItems = [];
          questOffset = 0;
          loadQuestions(uid, false);
        }
      } else if (tabName === 'answers') {
        const currentParams = getCurrentTabParams('answers');
        const isUpToDate = tabLoadedState.answers && areTabParamsEqual(tabLoadedState.answers, currentParams);
        if (!isUpToDate || (ansItems.length === 0 && !isLoadingAns)) {
          ansItems = [];
          ansOffset = 0;
          loadAnswers(uid, false);
        }
      } else if (tabName === 'comments') {
        const currentParams = getCurrentTabParams('comments');
        const isUpToDate = tabLoadedState.comments && areTabParamsEqual(tabLoadedState.comments, currentParams);
        if (!isUpToDate || (commItems.length === 0 && !isLoadingComm)) {
          commItems = [];
          commOffset = 0;
          loadComments(uid, false);
        }
      } else if (tabName === 'overview') {
        const currentParams = getCurrentTabParams('overview');
        const isUpToDate = tabLoadedState.overview && areTabParamsEqual(tabLoadedState.overview, currentParams);
        if (!isUpToDate || (activityItems.length === 0 && !isLoadingActivity)) {
          activityItems = [];
          activityOffset = 0;
          loadActivity(uid, false);
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
    const commVal = stats.commentsCount !== undefined ? stats.commentsCount :
      (stats.comments_count !== undefined ? stats.comments_count :
      (p.commentsCount !== undefined ? p.commentsCount :
      (p.comments_count !== undefined ? p.comments_count : 0)));

    const cPub = document.getElementById('tabCountPublications');
    if (cPub) cPub.textContent = pubVal;

    const cQuest = document.getElementById('tabCountQuestions');
    if (cQuest) cQuest.textContent = questVal;

    const cAns = document.getElementById('tabCountAnswers');
    if (cAns) cAns.textContent = ansVal;

    const cComm = document.getElementById('profileTabCountComments') || document.getElementById('tabCountComments');
    if (cComm) cComm.textContent = commVal;
  }

  function updateSearchResultsCount(count) {
    const infoEl = document.getElementById('profileSearchResultsInfo');
    const countEl = document.getElementById('profileSearchResultsCount');
    if (infoEl && countEl) {
      if (currentSearchQuery) {
        countEl.textContent = count !== undefined ? count : 0;
        infoEl.style.display = 'flex';
      } else {
        infoEl.style.display = 'none';
      }
    }
  }

  function renderTopContributions(topList, fallbackPubs) {
    const sec = document.getElementById('profileTopContributionsSection');
    const grid = document.getElementById('profileTopContributionsGrid');
    if (!sec || !grid) return;

    let items = Array.isArray(topList) ? topList.slice() : [];
    if (items.length === 0) {
      const pubs = Array.isArray(fallbackPubs) ? fallbackPubs : (currentProfile && (currentProfile.publications || currentProfile.articles));
      if (Array.isArray(pubs) && pubs.length > 0) {
        const candidates = pubs.slice();
        candidates.sort(function (a, b) {
          const rA = a.rating !== undefined ? a.rating : 0;
          const rB = b.rating !== undefined ? b.rating : 0;
          if (rB !== rA) return rB - rA;
          const dA = new Date(a.date || a.createdAt || 0).getTime();
          const dB = new Date(b.date || b.createdAt || 0).getTime();
          return dB - dA;
        });
        items = candidates.slice(0, 3).map(function (item) {
          return {
            id: item.id,
            title: item.title,
            rating: item.rating !== undefined ? item.rating : 0,
            type: item.materialType || item.type || 'publication',
            url: item.url || ('article.html?id=' + encodeURIComponent(item.id)),
            contentSnippet: item.contentSnippet || '',
            date: item.date || (item.createdAt ? formatRegistrationDateRu(item.createdAt) : '')
          };
        });
      }
    }

    if (items.length === 0) {
      sec.style.display = 'none';
      grid.innerHTML = '';
      return;
    }

    sec.style.display = 'block';
    grid.innerHTML = items.map(function (item) {
      const isSolution = item.isSolution || item.type === 'solution';
      const isQuestion = item.type === 'question' || item.materialType === 'question';
      let badgeClass = 'publication';
      let badgeText = 'Публикация';
      if (isSolution) {
        badgeClass = 'solution';
        badgeText = 'Решение';
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
      const dateText = p.createdAt ? formatRegistrationDateRu(p.createdAt) : '';
      if (dateText) {
        regEl.textContent = dateText;
        if (regRow) regRow.style.display = 'flex';
      } else {
        if (regRow) regRow.style.display = 'none';
      }
    }

    const isOwn = !!(p.isOwnProfile || (window.currentUser && (window.currentUser.id === p.id || window.currentUser.id === p.userId)));

    // 2. Expertise widget
    const widgetExp = document.getElementById('profileWidgetExpertise');
    const specEl = document.getElementById('sidebarUserSpecialization');
    if (specEl) {
      if (p.specialization && p.specialization.trim()) {
        specEl.textContent = p.specialization.trim();
        specEl.className = 'profile-expertise-badge';
        if (widgetExp) widgetExp.style.display = 'flex';
      } else {
        if (isOwn) {
          specEl.textContent = 'Укажите специализацию';
          specEl.className = 'profile-expertise-badge profile-expertise-hint';
          if (widgetExp) widgetExp.style.display = 'flex';
        } else {
          if (widgetExp) widgetExp.style.display = 'none';
        }
      }
    }

    // 3. Topics widget
    const widgetTopics = document.getElementById('profileWidgetTopics');
    const topicsContainer = document.getElementById('sidebarUserTopics');
    if (topicsContainer) {
      let topics = [];
      if (Array.isArray(p.topics) && p.topics.length > 0) {
        topics = p.topics;
      } else if (window.SmartContractumProfile && typeof window.SmartContractumProfile.aggregateUserTopics === 'function') {
        topics = window.SmartContractumProfile.aggregateUserTopics(p.publications || []);
      }

      if (topics.length > 0) {
        if (widgetTopics) widgetTopics.style.display = 'flex';
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
        updateTopicFilterUI(currentTopic);
      } else {
        if (isOwn) {
          if (widgetTopics) widgetTopics.style.display = 'flex';
          topicsContainer.innerHTML = '<div class="profile-sidebar-empty">Темы формируются автоматически из ваших публикаций</div>';
        } else {
          if (widgetTopics) widgetTopics.style.display = 'none';
        }
      }
    }

    // 4. Reputation widget (hidden to eliminate duplicate statistics)
    const widgetRep = document.getElementById('profileWidgetReputation');
    if (widgetRep) {
      widgetRep.style.display = 'none';
    }

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
    if (!userId) return;
    if (append && isLoadingActivity) return;

    const feedContainer = document.getElementById('profileActivityFeed');
    const actionsContainer = document.getElementById('profileActivityActions');

    if (!append) {
      if (actAbortCtrl) {
        try { actAbortCtrl.abort(); } catch (e) {}
      }
      activityOffset = 0;
      activityItems = [];
      tabLoadedState.overview = { q: currentSearchQuery };
      if (feedContainer) {
        feedContainer.innerHTML = '<div class="profile-empty-state">Загрузка активности...</div>';
      }
      if (actionsContainer) {
        actionsContainer.style.display = 'none';
      }
    }

    actAbortCtrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    const currentReqSeq = ++actReqSeq;
    isLoadingActivity = true;
    let url = '/api/users/' + encodeURIComponent(userId) + '/activity?limit=' + activityLimit + '&offset=' + activityOffset;
    if (currentSearchQuery) {
      url += '&q=' + encodeURIComponent(currentSearchQuery);
    }
    const fetchOpts = actAbortCtrl ? { signal: actAbortCtrl.signal } : {};

    fetch(url, fetchOpts)
      .then(function (res) {
        if (!res.ok) throw new Error('ACTIVITY_LOAD_FAILED');
        return res.json();
      })
      .then(function (data) {
        if (currentReqSeq !== actReqSeq) return;
        isLoadingActivity = false;
        if (!data || !data.success) {
          throw new Error('ACTIVITY_INVALID_DATA');
        }
        const newItems = Array.isArray(data.activity) ? data.activity : [];
        if (append) {
          activityItems = activityItems.concat(newItems);
        } else {
          activityItems = newItems;
        }
        activityOffset += newItems.length;
        activityHasMore = Boolean(data.hasMore);
        renderActivityFeed(activityItems, activityHasMore);

        if (activeTab === 'answers') {
          renderAnswersTab();
        }
      })
      .catch(function (err) {
        if (currentReqSeq !== actReqSeq) return;
        if (err && err.name === 'AbortError') return;
        isLoadingActivity = false;
        if (!append) {
          tabLoadedState.overview = null;
          if (feedContainer) {
            feedContainer.innerHTML =
              '<div class="profile-error-state">' +
                '<p class="profile-error-text">Ошибка загрузки ленты активности</p>' +
                '<button type="button" class="btn-profile-retry" id="btnRetryActivity">Повторить попытку</button>' +
              '</div>';
            const btn = feedContainer.querySelector('#btnRetryActivity');
            if (btn) {
              btn.addEventListener('click', function () {
                loadActivity(userId, false);
              });
            }
          }
          if (actionsContainer) {
            actionsContainer.style.display = 'none';
          }
        } else {
          showToast('Не удалось загрузить активность. Попробуйте еще раз.');
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
          ? '<span class="activity-solution-badge">Решение</span>'
          : '';
        badgeHtml = '<span class="activity-type-badge activity-badge-answer">Ответ</span>' + solutionBadge;
        titleWrapHtml = '<div class="activity-card-title-wrap">' +
          '<span class="activity-context-label">К вопросу:</span>' +
          '<a href="' + url + '" class="activity-card-title">' + escapeHtml(item.title) + '</a>' +
        '</div>';
      } else if (item.type === 'comment') {
        badgeHtml = '<span class="activity-type-badge activity-badge-comment">Комментарий</span>';
        const parentTitle = item.parentTitle || item.title || 'Материал';
        titleWrapHtml = '<div class="activity-card-title-wrap">' +
          '<span class="activity-context-label">К материалу:</span>' +
          '<a href="' + url + '" class="activity-card-title">' + escapeHtml(parentTitle) + '</a>' +
        '</div>';
      } else if (item.type === 'question') {
        badgeHtml = '<span class="activity-type-badge activity-badge-question">Вопрос</span>';
        titleWrapHtml = '<div class="activity-card-title-wrap">' +
          '<a href="' + url + '" class="activity-card-title">' + escapeHtml(item.title) + '</a>' +
        '</div>';
      } else {
        badgeHtml = '<span class="activity-type-badge activity-badge-publication">Публикация</span>';
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

      let commentLinkHtml = '';
      if (item.type === 'comment' && url) {
        commentLinkHtml = '<a href="' + url + '" class="activity-comment-permalink" title="Перейти к комментарию" style="margin-left: auto; font-size: 0.76rem; color: var(--text-muted); text-decoration: none; display: inline-flex; align-items: center; gap: 4px;">' +
          '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>' +
          ' <span>Перейти</span>' +
        '</a>';
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
          commentLinkHtml +
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
    if (!userId) return;
    if (append && isLoadingPub) return;

    const list = document.getElementById('profilePublicationsList');
    const actions = document.getElementById('profilePublicationsActions');

    if (!append) {
      if (pubAbortCtrl) {
        try { pubAbortCtrl.abort(); } catch (e) {}
      }
      pubOffset = 0;
      pubItems = [];
      tabLoadedState.publications = { q: currentSearchQuery, sort: pubSort, topic: currentTopic };
      if (list) {
        list.innerHTML = '<div class="profile-empty-state">Загрузка материалов...</div>';
      }
      if (actions) actions.style.display = 'none';
    }

    pubAbortCtrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    const currentReqSeq = ++pubReqSeq;
    isLoadingPub = true;
    let url = '/api/users/' + encodeURIComponent(userId) + '/publications?sort=' + encodeURIComponent(pubSort) + '&limit=' + pubLimit + '&offset=' + pubOffset;
    if (currentSearchQuery) {
      url += '&q=' + encodeURIComponent(currentSearchQuery);
    }
    if (currentTopic) {
      url += '&topic=' + encodeURIComponent(currentTopic);
    }
    const fetchOpts = pubAbortCtrl ? { signal: pubAbortCtrl.signal } : {};

    fetch(url, fetchOpts)
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (currentReqSeq !== pubReqSeq) return;
        isLoadingPub = false;
        if (!data || !data.success) {
          throw new Error((data && data.error) || 'Failed to load publications');
        }
        const incoming = Array.isArray(data.items) ? data.items : [];
        pubItems = append ? pubItems.concat(incoming) : incoming;
        pubOffset += incoming.length;
        pubHasMore = Boolean(data.hasMore);
        updateSearchResultsCount(data.total !== undefined ? data.total : (data.totalCount !== undefined ? data.totalCount : incoming.length));
        renderPublicationsTab(pubItems, append, pubHasMore, incoming);
      })
      .catch(function (err) {
        if (currentReqSeq !== pubReqSeq) return;
        if (err && err.name === 'AbortError') return;
        isLoadingPub = false;
        if (!append) {
          tabLoadedState.publications = null;
          if (list) {
            list.innerHTML =
              '<div class="profile-error-state">' +
                '<p class="profile-error-text">Ошибка загрузки публикаций</p>' +
                '<button type="button" class="btn-profile-retry" id="btnRetryPublications">Повторить попытку</button>' +
              '</div>';
            const btn = list.querySelector('#btnRetryPublications');
            if (btn) {
              btn.addEventListener('click', function () {
                loadPublications(userId, false);
              });
            }
          }
          if (actions) actions.style.display = 'none';
        } else {
          showToast('Не удалось загрузить публикации. Попробуйте еще раз.');
        }
      });
  }

  // --------------------------------------------------------------------------
  // Article Card Actions & Interaction Helpers
  // --------------------------------------------------------------------------
  function getBookmarks() {
    try {
      const key = (currentUser && currentUser.id) ? ('sc_bookmarks_' + currentUser.id) : 'sc_bookmarks_guest';
      const data = localStorage.getItem(key);
      if (data) {
        const parsed = JSON.parse(data);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (e) {}
    return [];
  }

  function saveBookmarks(bookmarks) {
    try {
      const key = (currentUser && currentUser.id) ? ('sc_bookmarks_' + currentUser.id) : 'sc_bookmarks_guest';
      localStorage.setItem(key, JSON.stringify(bookmarks));
      if (!currentUser) {
        localStorage.setItem('sc_bookmarks', JSON.stringify(bookmarks));
      }
    } catch (e) {}
  }

  function isItemBookmarked(id, item) {
    if (!id) return false;
    if (item && (item.hasSaved !== undefined || item.isSaved !== undefined || item.isBookmarked !== undefined)) {
      return Boolean(item.hasSaved || item.isSaved || item.isBookmarked);
    }
    return getBookmarks().includes(id);
  }

  function isItemReported(id, item) {
    if (!id) return false;
    if (item && (item.hasReported !== undefined || item.isReported !== undefined)) {
      return Boolean(item.hasReported || item.isReported);
    }
    if (window._reportedArticleIds && window._reportedArticleIds.has(id)) return true;
    if (currentUser) {
      try {
        const userKey = 'sc_reported_articles_' + currentUser.id;
        const stored = JSON.parse(localStorage.getItem(userKey) || '[]');
        if (stored.includes(id)) {
          window._reportedArticleIds = window._reportedArticleIds || new Set();
          window._reportedArticleIds.add(id);
          return true;
        }
      } catch (e) {}
    }
    return false;
  }

  function markArticleReported(articleId) {
    if (!articleId) return;
    window._reportedArticleIds = window._reportedArticleIds || new Set();
    window._reportedArticleIds.add(articleId);
    if (currentUser) {
      try {
        const userKey = 'sc_reported_articles_' + currentUser.id;
        const stored = JSON.parse(localStorage.getItem(userKey) || '[]');
        if (!stored.includes(articleId)) {
          stored.push(articleId);
          localStorage.setItem(userKey, JSON.stringify(stored));
        }
      } catch (e) {}
    }
    const btns = document.querySelectorAll('.btn-card-report[data-id="' + articleId + '"]');
    btns.forEach(function (btn) {
      if (window.SmartContractumCard && typeof window.SmartContractumCard.updateReportButtonState === 'function') {
        window.SmartContractumCard.updateReportButtonState(btn, true);
      } else {
        btn.classList.add('is-reported');
        btn.setAttribute('title', 'Жалоба уже отправлена');
        btn.setAttribute('aria-label', 'Жалоба уже отправлена');
        const svg = btn.querySelector('svg');
        if (svg) svg.setAttribute('fill', 'currentColor');
      }
    });
  }

  function toggleArticleLike(articleId, btn, item) {
    if (!currentUser) {
      openAuthModal();
      showToast('Войдите, чтобы поставить лайк');
      return;
    }

    const currentLiked = btn.classList.contains('is-liked');
    const newLiked = !currentLiked;
    const countEl = btn.querySelector('.like-count');
    const currentCount = parseInt(countEl ? countEl.textContent : '0', 10) || 0;
    const optimisticCount = newLiked ? (currentCount + 1) : Math.max(0, currentCount - 1);

    btn.classList.toggle('is-liked', newLiked);
    btn.setAttribute('aria-pressed', newLiked ? 'true' : 'false');
    btn.title = newLiked ? 'Больше не нравится' : 'Нравится';
    if (countEl) countEl.textContent = optimisticCount;
    if (item) {
      item.hasLiked = newLiked;
      item.likesCount = optimisticCount;
    }

    fetch('/api/articles/' + encodeURIComponent(articleId) + '/like', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
      .then(function (res) {
        if (res.status === 401) {
          openAuthModal();
          throw new Error('AUTH_REQUIRED');
        }
        return res.json();
      })
      .then(function (data) {
        if (data && data.success) {
          const finalLiked = Boolean(data.hasLiked);
          btn.classList.toggle('is-liked', finalLiked);
          btn.setAttribute('aria-pressed', finalLiked ? 'true' : 'false');
          btn.title = finalLiked ? 'Больше не нравится' : 'Нравится';
          if (countEl) countEl.textContent = data.likesCount;
          if (item) {
            item.hasLiked = finalLiked;
            item.likesCount = data.likesCount;
          }
        } else {
          // Rollback
          btn.classList.toggle('is-liked', currentLiked);
          btn.setAttribute('aria-pressed', currentLiked ? 'true' : 'false');
          btn.title = currentLiked ? 'Больше не нравится' : 'Нравится';
          if (countEl) countEl.textContent = currentCount;
          if (item) {
            item.hasLiked = currentLiked;
            item.likesCount = currentCount;
          }
          showToast((data && data.error) || 'Ошибка при сохранении отметки');
        }
      })
      .catch(function (err) {
        // Rollback unconditionally
        btn.classList.toggle('is-liked', currentLiked);
        btn.setAttribute('aria-pressed', currentLiked ? 'true' : 'false');
        btn.title = currentLiked ? 'Больше не нравится' : 'Нравится';
        if (countEl) countEl.textContent = currentCount;
        if (item) {
          item.hasLiked = currentLiked;
          item.likesCount = currentCount;
        }
        if (err && err.message === 'AUTH_REQUIRED') {
          showToast('Войдите, чтобы поставить отметку');
        } else {
          showToast('Не удалось обновить отметку');
        }
      });
  }

  function toggleArticleBookmark(articleId, btn, item) {
    if (!currentUser) {
      openAuthModal();
      showToast('Для сохранения публикации необходимо войти');
      return;
    }

    const wasActive = btn.classList.contains('is-bookmarked') || btn.classList.contains('is-saved');
    const nextActive = !wasActive;
    const countEl = btn.querySelector('.card-save-count');
    const prevCount = countEl ? (parseInt(countEl.textContent, 10) || 0) : 0;
    const optimisticCount = nextActive ? (prevCount + 1) : Math.max(0, prevCount - 1);

    btn.classList.toggle('is-bookmarked', nextActive);
    btn.classList.toggle('is-saved', nextActive);
    const svg = btn.querySelector('svg');
    if (svg) svg.setAttribute('fill', nextActive ? 'currentColor' : 'none');
    const newTooltip = nextActive ? 'Убрать из сохраненного' : 'Сохранить публикацию';
    btn.title = newTooltip;
    btn.setAttribute('aria-label', newTooltip);
    if (countEl) countEl.textContent = optimisticCount;
    if (item) {
      item.hasSaved = nextActive;
      item.isSaved = nextActive;
      item.isBookmarked = nextActive;
      item.savesCount = optimisticCount;
    }

    const bms = getBookmarks();
    const idx = bms.indexOf(articleId);
    if (nextActive && idx === -1) { bms.push(articleId); saveBookmarks(bms); }
    else if (!nextActive && idx !== -1) { bms.splice(idx, 1); saveBookmarks(bms); }

    fetch('/api/articles/' + encodeURIComponent(articleId) + (nextActive ? '/save' : '/unsave'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
      .then(function (res) {
        if (res.status === 401) {
          openAuthModal();
          throw new Error('AUTH_REQUIRED');
        }
        return res.json();
      })
      .then(function (data) {
        if (data && data.success) {
          const finalSaved = Boolean(data.isSaved !== undefined ? data.isSaved : nextActive);
          btn.classList.toggle('is-bookmarked', finalSaved);
          btn.classList.toggle('is-saved', finalSaved);
          if (svg) svg.setAttribute('fill', finalSaved ? 'currentColor' : 'none');
          if (countEl && data.savesCount !== undefined) countEl.textContent = data.savesCount;
          if (item) {
            item.hasSaved = finalSaved;
            item.isSaved = finalSaved;
            item.isBookmarked = finalSaved;
            if (data.savesCount !== undefined) item.savesCount = data.savesCount;
          }
          showToast(finalSaved ? 'Публикация сохранена' : 'Публикация удалена из сохраненного');
        } else {
          // Rollback
          btn.classList.toggle('is-bookmarked', wasActive);
          btn.classList.toggle('is-saved', wasActive);
          if (svg) svg.setAttribute('fill', wasActive ? 'currentColor' : 'none');
          if (countEl) countEl.textContent = prevCount;
          if (item) {
            item.hasSaved = wasActive;
            item.isSaved = wasActive;
            item.isBookmarked = wasActive;
            item.savesCount = prevCount;
          }
          const rbBms = getBookmarks();
          const rbIdx = rbBms.indexOf(articleId);
          if (wasActive && rbIdx === -1) { rbBms.push(articleId); saveBookmarks(rbBms); }
          else if (!wasActive && rbIdx !== -1) { rbBms.splice(rbIdx, 1); saveBookmarks(rbBms); }
          showToast((data && data.error) || 'Ошибка сохранения публикации');
        }
      })
      .catch(function (err) {
        // Rollback unconditionally
        btn.classList.toggle('is-bookmarked', wasActive);
        btn.classList.toggle('is-saved', wasActive);
        if (svg) svg.setAttribute('fill', wasActive ? 'currentColor' : 'none');
        const prevTooltip = wasActive ? 'Убрать из сохраненного' : 'Сохранить публикацию';
        btn.title = prevTooltip;
        btn.setAttribute('aria-label', prevTooltip);
        if (countEl) countEl.textContent = prevCount;
        if (item) {
          item.hasSaved = wasActive;
          item.isSaved = wasActive;
          item.isBookmarked = wasActive;
          item.savesCount = prevCount;
        }
        const rbBms = getBookmarks();
        const rbIdx = rbBms.indexOf(articleId);
        if (wasActive && rbIdx === -1) { rbBms.push(articleId); saveBookmarks(rbBms); }
        else if (!wasActive && rbIdx !== -1) { rbBms.splice(rbIdx, 1); saveBookmarks(rbBms); }
        if (err && err.message === 'AUTH_REQUIRED') {
          showToast('Для сохранения публикации необходимо войти');
        } else {
          showToast('Не удалось обновить сохранение');
        }
      });
  }

  let activeSharePopoverArticleId = null;
  let activeSharePopoverTrigger = null;

  function closeSharePopover() {
    const popover = document.getElementById('feedSharePopover');
    if (popover) {
      popover.style.display = 'none';
    }
    if (activeSharePopoverTrigger) {
      activeSharePopoverTrigger.setAttribute('aria-expanded', 'false');
      activeSharePopoverTrigger = null;
    }
    activeSharePopoverArticleId = null;
  }

  function openArticleShare(articleId, triggerBtn, item) {
    const popover = document.getElementById('feedSharePopover');
    if (!popover || !triggerBtn) return;

    if (activeSharePopoverArticleId === articleId && popover.style.display !== 'none') {
      closeSharePopover();
      return;
    }

    if (activeSharePopoverTrigger && activeSharePopoverTrigger !== triggerBtn) {
      activeSharePopoverTrigger.setAttribute('aria-expanded', 'false');
    }

    activeSharePopoverArticleId = articleId;
    activeSharePopoverTrigger = triggerBtn;
    triggerBtn.setAttribute('aria-haspopup', 'true');
    triggerBtn.setAttribute('aria-expanded', 'true');

    const origin = window.location.origin || '';
    const permalink = origin + '/article.html?id=' + encodeURIComponent(articleId);
    const title = (item && item.title) || document.title || 'SmartContractum';
    const encodedUrl = encodeURIComponent(permalink);
    const encodedText = encodeURIComponent(title);

    const proto = 'https:' + '//';
    const tgLink = popover.querySelector('[data-action="telegram"]');
    if (tgLink) tgLink.href = proto + 't.me/share/url?url=' + encodedUrl + '&text=' + encodedText;
    const vkLink = popover.querySelector('[data-action="vk"]');
    if (vkLink) vkLink.href = proto + 'vk.com/share.php?url=' + encodedUrl + '&title=' + encodedText;
    const okLink = popover.querySelector('[data-action="ok"]');
    if (okLink) okLink.href = proto + 'connect.ok.ru/offer?url=' + encodedUrl + '&title=' + encodedText;

    popover._permalink = permalink;

    const rect = triggerBtn.getBoundingClientRect();
    const scrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
    const scrollX = window.pageXOffset || document.documentElement.scrollLeft || 0;
    const popoverWidth = 190;
    let top = rect.bottom + scrollY + 4;
    let left = rect.left + scrollX;

    if (left + popoverWidth > window.innerWidth - 10) {
      left = Math.max(10, window.innerWidth - popoverWidth - 10);
    }

    popover.style.top = top + 'px';
    popover.style.left = left + 'px';
    popover.style.display = 'flex';
  }

  function openArticleReport(articleId, triggerBtn, item) {
    if (isItemReported(articleId, item)) {
      showToast('Жалоба уже отправлена');
      return;
    }
    if (!currentUser) {
      openAuthModal();
      showToast('Войдите, чтобы отправить жалобу');
      return;
    }
    const modal = document.getElementById('articleReportModal');
    if (!modal) return;

    modal._activeReportBtn = triggerBtn;
    const idInput = modal.querySelector('#reportArticleId');
    if (idInput) idInput.value = articleId;
    const defaultRadio = modal.querySelector('input[name="articleReportReason"][value="spam"]');
    if (defaultRadio) defaultRadio.checked = true;
    const detailsEl = modal.querySelector('#articleReportDetails');
    if (detailsEl) detailsEl.value = '';

    modal.style.display = 'flex';
  }

  function closeArticleReportModal() {
    const modal = document.getElementById('articleReportModal');
    if (modal) {
      modal.style.display = 'none';
      modal._activeReportBtn = null;
    }
  }

  function renderPublicationsTab(items, append, hasMore, newItems) {
    const list = document.getElementById('profilePublicationsList');
    const actions = document.getElementById('profilePublicationsActions');
    if (!list) return;

    if (!Array.isArray(items) || items.length === 0) {
      const emptyText = currentSearchQuery
        ? 'По запросу «' + escapeHtml(currentSearchQuery) + '» ничего не найдено.'
        : 'Пользователь пока не публиковал материалы.';
      list.innerHTML = '<div class="profile-empty-state">' + emptyText + '</div>';
      if (actions) actions.style.display = 'none';
      return;
    }

    if (!append) {
      list.innerHTML = '';
    }

    const toRender = append ? (newItems || []) : items;
    toRender.forEach(function (item) {
      if (window.SmartContractumCard && typeof window.SmartContractumCard.createCardElement === 'function') {
        const cardEl = window.SmartContractumCard.createCardElement(item, {
          onLikeToggle: toggleArticleLike,
          onBookmarkToggle: toggleArticleBookmark,
          onShareClick: openArticleShare,
          onReportClick: openArticleReport,
          isBookmarked: isItemBookmarked,
          isReported: isItemReported,
          onAuthorClick: function (aid) { if (aid) window.location.href = 'profile.html?userId=' + encodeURIComponent(aid); },
          currentUserId: currentUser ? currentUser.id : null
        });
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
    if (!userId) return;
    if (append && isLoadingQuest) return;

    const list = document.getElementById('profileQuestionsList');
    const actions = document.getElementById('profileQuestionsActions');

    if (!append) {
      if (questAbortCtrl) {
        try { questAbortCtrl.abort(); } catch (e) {}
      }
      questOffset = 0;
      questItems = [];
      tabLoadedState.questions = { q: currentSearchQuery, sort: questSort, topic: currentTopic, status: questStatus };
      if (list) {
        list.innerHTML = '<div class="profile-empty-state">Загрузка вопросов...</div>';
      }
      if (actions) actions.style.display = 'none';
    }

    questAbortCtrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    const currentReqSeq = ++questReqSeq;
    isLoadingQuest = true;
    let url = '/api/users/' + encodeURIComponent(userId) + '/questions?sort=' + encodeURIComponent(questSort) + '&status=' + encodeURIComponent(questStatus) + '&limit=' + questLimit + '&offset=' + questOffset;
    if (currentSearchQuery) {
      url += '&q=' + encodeURIComponent(currentSearchQuery);
    }
    if (currentTopic) {
      url += '&topic=' + encodeURIComponent(currentTopic);
    }
    const fetchOpts = questAbortCtrl ? { signal: questAbortCtrl.signal } : {};

    fetch(url, fetchOpts)
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (currentReqSeq !== questReqSeq) return;
        isLoadingQuest = false;
        if (!data || !data.success) {
          throw new Error((data && data.error) || 'Failed to load questions');
        }
        const incoming = Array.isArray(data.items) ? data.items : [];
        questItems = append ? questItems.concat(incoming) : incoming;
        questOffset += incoming.length;
        questHasMore = Boolean(data.hasMore);
        updateSearchResultsCount(data.total !== undefined ? data.total : (data.totalCount !== undefined ? data.totalCount : incoming.length));
        renderQuestionsTab(questItems, append, questHasMore, incoming);
      })
      .catch(function (err) {
        if (currentReqSeq !== questReqSeq) return;
        if (err && err.name === 'AbortError') return;
        isLoadingQuest = false;
        if (!append) {
          tabLoadedState.questions = null;
          if (list) {
            list.innerHTML =
              '<div class="profile-error-state">' +
                '<p class="profile-error-text">Ошибка загрузки вопросов</p>' +
                '<button type="button" class="btn-profile-retry" id="btnRetryQuestions">Повторить попытку</button>' +
              '</div>';
            const btn = list.querySelector('#btnRetryQuestions');
            if (btn) {
              btn.addEventListener('click', function () {
                loadQuestions(userId, false);
              });
            }
          }
          if (actions) actions.style.display = 'none';
        } else {
          showToast('Не удалось загрузить вопросы. Попробуйте еще раз.');
        }
      });
  }

  function renderQuestionsTab(items, append, hasMore, newItems) {
    const list = document.getElementById('profileQuestionsList');
    const actions = document.getElementById('profileQuestionsActions');
    if (!list) return;

    if (!Array.isArray(items) || items.length === 0) {
      const emptyText = currentSearchQuery
        ? 'По запросу «' + escapeHtml(currentSearchQuery) + '» ничего не найдено.'
        : 'Пользователь пока не задавал вопросы.';
      list.innerHTML = '<div class="profile-empty-state">' + emptyText + '</div>';
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
        const cardEl = window.SmartContractumCard.createCardElement(item, {
          onLikeToggle: toggleArticleLike,
          onBookmarkToggle: toggleArticleBookmark,
          onShareClick: openArticleShare,
          onReportClick: openArticleReport,
          isBookmarked: isItemBookmarked,
          isReported: isItemReported,
          onAuthorClick: function (aid) { if (aid) window.location.href = 'profile.html?userId=' + encodeURIComponent(aid); },
          currentUserId: currentUser ? currentUser.id : null
        });
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
    if (!userId) return;
    if (append && isLoadingAns) return;

    const list = document.getElementById('profileAnswersList');
    const actions = document.getElementById('profileAnswersActions');

    if (!append) {
      if (ansAbortCtrl) {
        try { ansAbortCtrl.abort(); } catch (e) {}
      }
      ansOffset = 0;
      ansItems = [];
      tabLoadedState.answers = { q: currentSearchQuery, filter: ansFilter, sort: ansSort };
      if (list) {
        list.innerHTML = '<div class="profile-empty-state">Загрузка ответов...</div>';
      }
      if (actions) actions.style.display = 'none';
    }

    ansAbortCtrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    const currentReqSeq = ++ansReqSeq;
    isLoadingAns = true;
    let url = '/api/users/' + encodeURIComponent(userId) + '/answers?filter=' + encodeURIComponent(ansFilter) + '&limit=' + ansLimit + '&offset=' + ansOffset;
    url += '&sort=' + encodeURIComponent(ansSort);
    if (currentSearchQuery) {
      url += '&q=' + encodeURIComponent(currentSearchQuery);
    }
    const fetchOpts = ansAbortCtrl ? { signal: ansAbortCtrl.signal } : {};

    fetch(url, fetchOpts)
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (currentReqSeq !== ansReqSeq) return;
        isLoadingAns = false;
        if (!data || !data.success) {
          throw new Error((data && data.error) || 'Failed to load answers');
        }
        const incoming = Array.isArray(data.items) ? data.items : [];
        ansItems = append ? ansItems.concat(incoming) : incoming;
        ansOffset += incoming.length;
        ansHasMore = Boolean(data.hasMore);
        updateSearchResultsCount(data.total !== undefined ? data.total : (data.totalCount !== undefined ? data.totalCount : incoming.length));
        renderAnswersTab(ansItems, append, ansHasMore, incoming);
      })
      .catch(function (err) {
        if (currentReqSeq !== ansReqSeq) return;
        if (err && err.name === 'AbortError') return;
        isLoadingAns = false;
        if (!append) {
          tabLoadedState.answers = null;
          if (list) {
            list.innerHTML =
              '<div class="profile-error-state">' +
                '<p class="profile-error-text">Ошибка загрузки ответов</p>' +
                '<button type="button" class="btn-profile-retry" id="btnRetryAnswers">Повторить попытку</button>' +
              '</div>';
            const btn = list.querySelector('#btnRetryAnswers');
            if (btn) {
              btn.addEventListener('click', function () {
                loadAnswers(userId, false);
              });
            }
          }
          if (actions) actions.style.display = 'none';
        } else {
          showToast('Не удалось загрузить ответы. Попробуйте еще раз.');
        }
      });
  }

  function renderAnswersTab(items, append, hasMore, newItems) {
    const list = document.getElementById('profileAnswersList');
    const actions = document.getElementById('profileAnswersActions');
    if (!list) return;

    if (!Array.isArray(items) || items.length === 0) {
      const emptyText = currentSearchQuery
        ? 'По запросу «' + escapeHtml(currentSearchQuery) + '» ничего не найдено.'
        : 'Пользователь пока не публиковал ответы на вопросы.';
      list.innerHTML = '<div class="profile-empty-state">' + emptyText + '</div>';
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
        ? '<span class="meta-badge solution-badge">Решение</span>'
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

  // --------------------------------------------------------------------------
  // Comments Tab: Loader & Renderer
  // --------------------------------------------------------------------------
  function loadComments(userId, append) {
    if (!userId) return;
    if (append && isLoadingComm) return;

    const list = document.getElementById('profileCommentsList');
    const actions = document.getElementById('profileCommentsActions');

    if (!append) {
      if (commAbortCtrl) {
        try { commAbortCtrl.abort(); } catch (e) {}
      }
      commOffset = 0;
      commItems = [];
      if (list) {
        list.innerHTML = '<div class="profile-empty-state">Загрузка комментариев...</div>';
      }
      if (actions) actions.style.display = 'none';
    }

    commAbortCtrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    const currentReqSeq = ++commReqSeq;
    isLoadingComm = true;
    let url = '/api/users/' + encodeURIComponent(userId) + '/comments?sort=' + encodeURIComponent(commSort) + '&limit=' + commLimit + '&offset=' + commOffset;
    if (currentSearchQuery) {
      url += '&q=' + encodeURIComponent(currentSearchQuery);
    }
    const fetchOpts = commAbortCtrl ? { signal: commAbortCtrl.signal } : {};

    fetch(url, fetchOpts)
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (currentReqSeq !== commReqSeq) return;
        isLoadingComm = false;
        if (!data || !data.success) {
          throw new Error((data && data.error) || 'Failed to load comments');
        }
        const incoming = Array.isArray(data.items) ? data.items : (Array.isArray(data.comments) ? data.comments : []);
        commItems = append ? commItems.concat(incoming) : incoming;
        commOffset += incoming.length;
        commHasMore = Boolean(data.hasMore);
        tabLoadedState.comments = { q: currentSearchQuery, sort: commSort };
        updateSearchResultsCount(data.total !== undefined ? data.total : (data.totalCount !== undefined ? data.totalCount : incoming.length));
        renderCommentsTab(commItems, append, commHasMore, incoming);
      })
      .catch(function (err) {
        if (currentReqSeq !== commReqSeq) return;
        if (err && err.name === 'AbortError') return;
        isLoadingComm = false;
        tabLoadedState.comments = null;
        if (!append) {
          if (list) {
            list.innerHTML =
              '<div class="profile-error-state">' +
                '<p class="profile-error-text">Ошибка загрузки комментариев</p>' +
                '<button type="button" class="btn-profile-retry" id="btnRetryComments">Повторить попытку</button>' +
              '</div>';
            const btn = list.querySelector('#btnRetryComments');
            if (btn) {
              btn.addEventListener('click', function () {
                loadComments(userId, false);
              });
            }
          }
          if (actions) actions.style.display = 'none';
        } else {
          showToast('Не удалось загрузить комментарии. Попробуйте еще раз.');
        }
      });
  }

  // --------------------------------------------------------------------------
  // Comment Card Actions & Interaction Helpers
  // --------------------------------------------------------------------------
  function getCommentBookmarks() {
    try {
      const key = (currentUser && currentUser.id) ? ('sc_comment_bookmarks_' + currentUser.id) : 'sc_comment_bookmarks_guest';
      const data = localStorage.getItem(key) || localStorage.getItem('sc_comment_bookmarks');
      if (data) {
        const parsed = JSON.parse(data);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (e) {}
    return [];
  }

  function saveCommentBookmarks(bookmarks) {
    try {
      const key = (currentUser && currentUser.id) ? ('sc_comment_bookmarks_' + currentUser.id) : 'sc_comment_bookmarks_guest';
      localStorage.setItem(key, JSON.stringify(bookmarks));
      localStorage.setItem('sc_comment_bookmarks', JSON.stringify(bookmarks));
    } catch (e) {}
  }

  function isCommentBookmarked(id, item) {
    if (!id) return false;
    if (item && (item.isBookmarked !== undefined || item.isSaved !== undefined || item.hasSaved !== undefined)) {
      return Boolean(item.isBookmarked || item.isSaved || item.hasSaved);
    }
    return getCommentBookmarks().includes(id);
  }

  function isCommentReported(id, item) {
    if (!id) return false;
    if (item && (item.hasReported !== undefined || item.isReported !== undefined)) {
      return Boolean(item.hasReported || item.isReported);
    }
    if (window._reportedCommentIds && window._reportedCommentIds.has(id)) return true;
    if (currentUser) {
      try {
        const userKey = 'sc_reported_comments_' + currentUser.id;
        const stored = JSON.parse(localStorage.getItem(userKey) || '[]');
        if (stored.includes(id)) {
          window._reportedCommentIds = window._reportedCommentIds || new Set();
          window._reportedCommentIds.add(id);
          return true;
        }
      } catch (e) {}
    }
    return false;
  }

  function toggleCommentSave(commentId, btn, item) {
    if (!currentUser) {
      openAuthModal();
      showToast('Для сохранения комментария необходимо войти');
      return;
    }

    const wasActive = btn ? (btn.classList.contains('is-bookmarked') || btn.classList.contains('is-saved')) : false;
    const nextActive = !wasActive;

    if (btn) {
      btn.classList.toggle('is-bookmarked', nextActive);
      btn.classList.toggle('is-saved', nextActive);
      const svg = btn.querySelector('svg');
      if (svg) svg.setAttribute('fill', nextActive ? 'currentColor' : 'none');
      const newTooltip = nextActive ? 'Удалить из закладок' : 'Сохранить';
      btn.title = newTooltip;
      btn.setAttribute('aria-label', newTooltip);
    }
    if (item) {
      item.isSaved = nextActive;
      item.isBookmarked = nextActive;
    }

    const bms = getCommentBookmarks();
    const idx = bms.indexOf(commentId);
    if (nextActive && idx === -1) { bms.push(commentId); saveCommentBookmarks(bms); }
    else if (!nextActive && idx !== -1) { bms.splice(idx, 1); saveCommentBookmarks(bms); }

    fetch('/api/comments/' + encodeURIComponent(commentId) + '/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: nextActive ? 'save' : 'unsave' })
    })
      .then(function (res) {
        if (res.status === 401) {
          openAuthModal();
          throw new Error('AUTH_REQUIRED');
        }
        return res.json();
      })
      .then(function (data) {
        if (data && data.success) {
          const finalSaved = Boolean(data.isSaved !== undefined ? data.isSaved : nextActive);
          if (btn) {
            btn.classList.toggle('is-bookmarked', finalSaved);
            btn.classList.toggle('is-saved', finalSaved);
            const svg = btn.querySelector('svg');
            if (svg) svg.setAttribute('fill', finalSaved ? 'currentColor' : 'none');
          }
          if (item) {
            item.isSaved = finalSaved;
            item.isBookmarked = finalSaved;
          }
          showToast(finalSaved ? 'Комментарий сохранен в закладки' : 'Комментарий удален из закладок');
        } else {
          // Rollback
          if (btn) {
            btn.classList.toggle('is-bookmarked', wasActive);
            btn.classList.toggle('is-saved', wasActive);
            const svg = btn.querySelector('svg');
            if (svg) svg.setAttribute('fill', wasActive ? 'currentColor' : 'none');
            const prevTooltip = wasActive ? 'Удалить из закладок' : 'Сохранить';
            btn.title = prevTooltip;
            btn.setAttribute('aria-label', prevTooltip);
          }
          if (item) {
            item.isSaved = wasActive;
            item.isBookmarked = wasActive;
          }
          const rbBms = getCommentBookmarks();
          const rbIdx = rbBms.indexOf(commentId);
          if (wasActive && rbIdx === -1) { rbBms.push(commentId); saveCommentBookmarks(rbBms); }
          else if (!wasActive && rbIdx !== -1) { rbBms.splice(rbIdx, 1); saveCommentBookmarks(rbBms); }
          showToast((data && data.error) || 'Ошибка сохранения комментария');
        }
      })
      .catch(function (err) {
        // Rollback unconditionally
        if (btn) {
          btn.classList.toggle('is-bookmarked', wasActive);
          btn.classList.toggle('is-saved', wasActive);
          const svg = btn.querySelector('svg');
          if (svg) svg.setAttribute('fill', wasActive ? 'currentColor' : 'none');
          const prevTooltip = wasActive ? 'Удалить из закладок' : 'Сохранить';
          btn.title = prevTooltip;
          btn.setAttribute('aria-label', prevTooltip);
        }
        if (item) {
          item.isSaved = wasActive;
          item.isBookmarked = wasActive;
        }
        const rbBms = getCommentBookmarks();
        const rbIdx = rbBms.indexOf(commentId);
        if (wasActive && rbIdx === -1) { rbBms.push(commentId); saveCommentBookmarks(rbBms); }
        else if (!wasActive && rbIdx !== -1) { rbBms.splice(rbIdx, 1); saveCommentBookmarks(rbBms); }
        if (err && err.message === 'AUTH_REQUIRED') {
          showToast('Для сохранения комментария необходимо войти');
        } else {
          showToast('Не удалось обновить сохранение');
        }
      });
  }

  function openCommentReport(commentId, triggerBtn, item) {
    if (!currentUser) {
      openAuthModal();
      showToast('Для отправки жалобы необходимо войти');
      return;
    }
    if (isCommentReported(commentId, item)) {
      showToast('Жалоба уже отправлена');
      return;
    }

    fetch('/api/comments/' + encodeURIComponent(commentId) + '/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'spam' })
    })
      .then(function (res) {
        if (res.status === 401) {
          openAuthModal();
          throw new Error('AUTH_REQUIRED');
        }
        return res.json();
      })
      .then(function (data) {
        if (data && data.success) {
          if (triggerBtn) {
            triggerBtn.classList.add('is-reported');
            triggerBtn.title = 'Жалоба уже отправлена';
            triggerBtn.setAttribute('aria-label', 'Жалоба уже отправлена');
            const svg = triggerBtn.querySelector('svg');
            if (svg) svg.setAttribute('fill', 'currentColor');
          }
          if (item) {
            item.isReported = true;
            item.hasReported = true;
          }
          window._reportedCommentIds = window._reportedCommentIds || new Set();
          window._reportedCommentIds.add(commentId);
          if (currentUser) {
            try {
              const userKey = 'sc_reported_comments_' + currentUser.id;
              const stored = JSON.parse(localStorage.getItem(userKey) || '[]');
              if (!stored.includes(commentId)) {
                stored.push(commentId);
                localStorage.setItem(userKey, JSON.stringify(stored));
              }
            } catch (e) {}
          }
          showToast('Жалоба отправлена');
        } else {
          showToast((data && data.error) || 'Ошибка отправки жалобы');
        }
      })
      .catch(function (err) {
        if (err && err.message === 'AUTH_REQUIRED') {
          showToast('Для отправки жалобы необходимо войти');
        } else {
          showToast('Не удалось отправить жалобу');
        }
      });
  }

  function renderCommentsTab(items, append, hasMore, newItems) {
    const list = document.getElementById('profileCommentsList');
    const actions = document.getElementById('profileCommentsActions');
    if (!list) return;

    if (!Array.isArray(items) || items.length === 0) {
      const emptyText = currentSearchQuery
        ? 'По запросу «' + escapeHtml(currentSearchQuery) + '» ничего не найдено.'
        : 'Пользователь пока не оставлял комментарии.';
      list.innerHTML = '<div class="profile-empty-state">' + emptyText + '</div>';
      if (actions) actions.style.display = 'none';
      return;
    }

    if (!append) {
      list.innerHTML = '';
    }

    const toRender = append ? (newItems || []) : items;
    toRender.forEach(function (item) {
      const cardEl = document.createElement('div');
      cardEl.className = 'profile-comment-item profile-comment-card';

      const ratingVal = item.rating !== undefined ? item.rating : (item.score || 0);
      const ratingDisplay = ratingVal >= 0 ? '+' + ratingVal : ratingVal;
      const dateDisplay = item.date || (item.createdAt ? formatRegistrationDateRu(item.createdAt) : '');
      const parentTitle = item.parentTitle || item.title || 'Материал';
      const articleId = item.articleId || item.materialId;
      const commentId = item.id || item.commentId;
      const permalink = item.permalink || item.url || ('article.html?id=' + encodeURIComponent(articleId) + '#comment-' + encodeURIComponent(commentId));
      const parentUrl = 'article.html?id=' + encodeURIComponent(articleId);

      const snippet = item.contentSnippet || item.snippet || item.content || '';
      const snippetHtml = snippet
        ? '<div class="profile-comment-snippet">' + escapeHtml(snippet) + '</div>'
        : '';

      const isSaved = isCommentBookmarked(commentId, item);
      const isReported = isCommentReported(commentId, item);
      const authorId = item.userId || item.authorId || item.author_id || (currentProfile && (currentProfile.id || currentProfile.userId));
      const isMyComment = Boolean(currentUser && authorId && (currentUser.id === authorId));

      const saveBtnHtml =
        '<button type="button" class="btn-comment-action btn-save-comment' + (isSaved ? ' is-bookmarked is-saved' : '') + '" title="' + (isSaved ? 'Удалить из закладок' : 'Сохранить') + '" aria-label="' + (isSaved ? 'Удалить из закладок' : 'Сохранить') + '" data-comment-id="' + escapeHtml(commentId) + '">' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="' + (isSaved ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>' +
          '</svg>' +
        '</button>';

      const shareBtnHtml =
        '<button type="button" class="btn-comment-action btn-share-comment" title="Поделиться" aria-label="Поделиться" data-comment-id="' + escapeHtml(commentId) + '">' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<circle cx="18" cy="5" r="3"></circle>' +
            '<circle cx="6" cy="12" r="3"></circle>' +
            '<circle cx="18" cy="19" r="3"></circle>' +
            '<line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>' +
            '<line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>' +
          '</svg>' +
        '</button>';

      let reportBtnHtml = '';
      if (!isMyComment) {
        reportBtnHtml =
          '<button type="button" class="btn-comment-action btn-report-comment' + (isReported ? ' is-reported' : '') + '" title="' + (isReported ? 'Жалоба уже отправлена' : 'Пожаловаться') + '" aria-label="' + (isReported ? 'Жалоба уже отправлена' : 'Пожаловаться') + '" data-comment-id="' + escapeHtml(commentId) + '">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="' + (isReported ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
              '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"></path>' +
              '<line x1="4" y1="22" x2="4" y2="15"></line>' +
            '</svg>' +
          '</button>';
      }

      cardEl.innerHTML =
        '<div class="profile-comment-header">' +
          '<span class="profile-comment-badge">Комментарий</span>' +
          '<div class="profile-comment-context">' +
            '<span class="profile-comment-context-label">К материалу:</span>' +
            '<a href="' + parentUrl + '" class="profile-comment-parent-title">' + escapeHtml(parentTitle) + '</a>' +
          '</div>' +
        '</div>' +
        snippetHtml +
        '<div class="profile-comment-footer">' +
          '<span class="profile-comment-date">' + escapeHtml(dateDisplay) + '</span>' +
          '<span class="profile-comment-rating" title="Рейтинг комментария">' +
            '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>' +
            ' <span>' + ratingDisplay + '</span>' +
          '</span>' +
          '<div class="profile-comment-actions">' +
            saveBtnHtml +
            shareBtnHtml +
            reportBtnHtml +
          '</div>' +
          '<a href="' + permalink + '" class="profile-comment-link" title="Перейти к комментарию">' +
            '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>' +
            ' <span>Перейти</span>' +
          '</a>' +
        '</div>';

      const saveBtn = cardEl.querySelector('.btn-save-comment');
      if (saveBtn) {
        saveBtn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          toggleCommentSave(commentId, saveBtn, item);
        });
      }

      const shareBtn = cardEl.querySelector('.btn-share-comment');
      if (shareBtn) {
        shareBtn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          const origin = (typeof window !== 'undefined' && window.location && window.location.origin) ? window.location.origin : '';
          const fullUrl = permalink.startsWith('http') ? permalink : (origin + (permalink.startsWith('/') ? '' : '/') + permalink);
          copyTextToClipboard(fullUrl, 'Ссылка на комментарий скопирована');
        });
      }

      const reportBtn = cardEl.querySelector('.btn-report-comment');
      if (reportBtn) {
        reportBtn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          openCommentReport(commentId, reportBtn, item);
        });
      }

      list.appendChild(cardEl);
    });

    if (actions) {
      actions.style.display = hasMore ? 'block' : 'none';
    }
  }

  function triggerSearch(newQuery) {
    const q = (newQuery !== undefined && newQuery !== null) ? String(newQuery).trim() : '';
    if (q === currentSearchQuery && q !== '') return;
    currentSearchQuery = q;

    const searchInput = document.getElementById('profileSearchInput');
    if (searchInput && searchInput.value !== currentSearchQuery) {
      searchInput.value = currentSearchQuery;
    }

    const clearBtn = document.getElementById('btnProfileSearchClear');
    if (clearBtn) {
      clearBtn.style.display = currentSearchQuery ? 'flex' : 'none';
    }

    if (!currentSearchQuery) {
      const infoEl = document.getElementById('profileSearchResultsInfo');
      if (infoEl) infoEl.style.display = 'none';
    }

    if (window.history && (window.history.pushState || window.history.replaceState)) {
      try {
        const url = new URL(window.location.href);
        if (currentSearchQuery) {
          url.searchParams.set('q', currentSearchQuery);
        } else {
          url.searchParams.delete('q');
        }
        if (window.history.replaceState) {
          window.history.replaceState({ tab: activeTab, q: currentSearchQuery }, '', url.toString());
        }
      } catch (e) {}
    }

    if (!currentProfile) return;
    const uid = currentProfile.id || currentProfile.userId;

    if (activeTab === 'overview' && currentSearchQuery) {
      setActiveTab('publications', true);
      pubOffset = 0;
      pubItems = [];
      loadPublications(uid, false);
      return;
    }

    if (activeTab === 'publications') {
      pubOffset = 0;
      pubItems = [];
      loadPublications(uid, false);
    } else if (activeTab === 'questions') {
      questOffset = 0;
      questItems = [];
      loadQuestions(uid, false);
    } else if (activeTab === 'answers') {
      ansOffset = 0;
      ansItems = [];
      loadAnswers(uid, false);
    } else if (activeTab === 'comments') {
      commOffset = 0;
      commItems = [];
      loadComments(uid, false);
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
        : '<span class="meta-badge" style="font-size: 0.72rem; padding: 2px 6px; margin-right: 8px;">Публикация</span>';

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
          let prevFollowers = (currentProfile.stats && currentProfile.stats.followersCount !== undefined)
            ? currentProfile.stats.followersCount
            : (parseInt((document.getElementById('profileStatFollowers') || {}).textContent, 10) || 0);
          const newFollowers = isSub ? (prevFollowers + 1) : Math.max(0, prevFollowers - 1);
          updateProfileStats({ followersCount: newFollowers });

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

  function copyTextToClipboard(text, successMsg) {
    const msg = successMsg || 'Ссылка скопирована';
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      navigator.clipboard.writeText(text)
        .then(function () {
          showToast(msg);
        })
        .catch(function () {
          fallbackCopyText(text, msg);
        });
    } else {
      fallbackCopyText(text, msg);
    }
  }

  function fallbackCopyText(text, successMsg) {
    const msg = successMsg || 'Ссылка скопирована';
    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      showToast(msg);
    } catch (e) {
      showToast('Не удалось скопировать ссылку');
    }
  }

  function copyProfileLink() {
    copyTextToClipboard(window.location.href, 'Ссылка на профиль скопирована');
  }

  function openEditModal() {
    lastEditTriggerEl = document.activeElement;
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
    if (lastEditTriggerEl && typeof lastEditTriggerEl.focus === 'function') {
      try { lastEditTriggerEl.focus(); } catch (e) {}
    }
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
  window.openAuthModal = openAuthModal;

  function closeAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) modal.style.display = 'none';
  }

  function handlePopState(e) {
    try {
      const state = (e && e.state) || {};
      let params = null;
      try {
        if (typeof window !== 'undefined' && window.location && window.location.search !== undefined) {
          params = new URLSearchParams(window.location.search);
        }
      } catch (errParams) {}
      if (!params) {
        params = new URLSearchParams();
      }

      // Extract all parameters: tab, q, sort, topic, status from URL and state
      const tab = state.tab || params.get('tab') || 'overview';
      const targetQ = (state.q !== undefined && state.q !== null) ? String(state.q).trim() : (params.get('q') || '').trim();
      const targetTopic = (state.topic !== undefined && state.topic !== null) ? String(state.topic).trim() : (params.get('topic') || '').trim();
      const rawSort = (state.sort !== undefined && state.sort !== null) ? String(state.sort).trim() : (params.get('sort') || '').trim();
      const rawStatus = (state.status !== undefined && state.status !== null) ? String(state.status).trim() : (params.get('status') || '').trim();
      const rawFilter = (state.filter !== undefined && state.filter !== null) ? String(state.filter).trim() : (params.get('filter') || '').trim();
      const rawAnsSort = (state.ans_sort !== undefined && state.ans_sort !== null)
        ? String(state.ans_sort).trim()
        : ((tab === 'answers' && state.sort !== undefined && state.sort !== null)
          ? String(state.sort).trim()
          : (params.get('ans_sort') || (tab === 'answers' ? params.get('sort') : '') || '').trim());
      const rawCommSort = (state.comm_sort !== undefined && state.comm_sort !== null)
        ? String(state.comm_sort).trim()
        : ((tab === 'comments' && state.sort !== undefined && state.sort !== null)
          ? String(state.sort).trim()
          : (params.get('comm_sort') || (tab === 'comments' ? params.get('sort') : '') || '').trim());

      let targetPubSort = pubSort;
      let targetQuestSort = questSort;
      let targetCommSort = commSort;
      let targetAnsSort = ansSort;
      if (rawSort) {
        if (tab === 'publications') {
          targetPubSort = rawSort;
        } else if (tab === 'questions') {
          targetQuestSort = rawSort;
        } else if (tab === 'comments') {
          targetCommSort = rawSort;
        } else if (tab === 'answers') {
          targetAnsSort = rawSort;
        } else {
          targetPubSort = rawSort;
          targetQuestSort = rawSort;
          targetCommSort = rawSort;
          targetAnsSort = rawSort;
        }
      } else {
        if (tab === 'publications') targetPubSort = 'newest';
        if (tab === 'questions') targetQuestSort = 'newest';
        if (tab === 'comments') targetCommSort = 'new';
        if (tab === 'answers') targetAnsSort = 'new';
      }
      if (rawAnsSort) {
        targetAnsSort = rawAnsSort;
      }
      if (rawCommSort) {
        targetCommSort = rawCommSort;
      } else if (tab === 'comments') {
        targetCommSort = params.get('comm_sort') || (tab === 'comments' ? params.get('sort') : null) || 'newest';
      }

      const targetQuestStatus = rawStatus || 'all';
      const targetAnsFilter = rawFilter || 'all';

      // If any parameter changed, invalidate cached tab data
      if (targetQ !== currentSearchQuery) {
        currentSearchQuery = targetQ;
        const profileSearchInput = document.getElementById('profileSearchInput');
        if (profileSearchInput) {
          profileSearchInput.value = currentSearchQuery;
        }
        const searchClearBtn = document.getElementById('btnProfileSearchClear');
        if (searchClearBtn) {
          searchClearBtn.style.display = currentSearchQuery ? 'flex' : 'none';
        }
        invalidateTabCaches();
      }

      if (targetTopic !== currentTopic) {
        currentTopic = targetTopic;
        tabLoadedState.publications = null;
        pubItems = [];
        pubOffset = 0;
        tabLoadedState.questions = null;
        questItems = [];
        questOffset = 0;
      }

      if (targetPubSort !== pubSort) {
        pubSort = targetPubSort;
        tabLoadedState.publications = null;
        pubItems = [];
        pubOffset = 0;
      }

      if (targetQuestSort !== questSort) {
        questSort = targetQuestSort;
        tabLoadedState.questions = null;
        questItems = [];
        questOffset = 0;
      }

      if (targetQuestStatus !== questStatus) {
        questStatus = targetQuestStatus;
        tabLoadedState.questions = null;
        questItems = [];
        questOffset = 0;
      }

      if (targetAnsFilter !== ansFilter) {
        ansFilter = targetAnsFilter;
        tabLoadedState.answers = null;
        ansItems = [];
        ansOffset = 0;
      }

      if (targetAnsSort !== ansSort) {
        ansSort = targetAnsSort;
        tabLoadedState.answers = null;
        ansItems = [];
        ansOffset = 0;
      }

      const commSortChanged = (targetCommSort !== commSort);
      if (commSortChanged) {
        commSort = targetCommSort;
        tabLoadedState.comments = null;
        commItems = [];
        commOffset = 0;
      }

      if (tab === 'comments' && (targetQ !== currentSearchQuery || commSortChanged)) {
        tabLoadedState.comments = null;
        commItems = [];
        commOffset = 0;
      }

      // Restore UI controls
      updateSearchInputUI(currentSearchQuery);
      updatePubSortUI(pubSort);
      updateQuestSortUI(questSort);
      updateQuestStatusUI(questStatus);
      updateAnsFilterUI(ansFilter);
      updateAnsSortUI(ansSort);
      updateCommSortUI(commSort);
      updateTopicFilterUI(currentTopic);

      // Activate tab and reload fresh data if cache was invalidated
      setActiveTab(tab, false);
    } catch (err) {
      setActiveTab('overview', false);
    }
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

    // 5. Header user menu and auth controls
    const btnLogin = document.getElementById('headerLoginBtn');
    const userMenu = document.getElementById('headerUserMenu');
    if (btnLogin) {
      btnLogin.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (currentUser) {
          if (userMenu) {
            const isShown = userMenu.style.display === 'flex' || userMenu.style.display === 'block';
            userMenu.style.display = isShown ? 'none' : 'flex';
            btnLogin.setAttribute('aria-expanded', isShown ? 'false' : 'true');
          }
        } else {
          openAuthModal();
        }
      });
    }

    document.addEventListener('click', function (e) {
      const menu = document.getElementById('headerUserMenu');
      const loginBtn = document.getElementById('headerLoginBtn');
      if (menu && menu.style.display !== 'none') {
        if (!menu.contains(e.target) && !(loginBtn && loginBtn.contains(e.target))) {
          menu.style.display = 'none';
          if (loginBtn) loginBtn.setAttribute('aria-expanded', 'false');
        }
      }
    });

    // Header notifications controls
    const notifBtn = document.getElementById('headerNotificationsBtn');
    const notifBadge = document.getElementById('headerNotifBadge');
    const notifPopup = document.getElementById('headerNotifPopup');
    const notifList = document.getElementById('notifListContainer');
    const markAllBtn = document.getElementById('notifMarkAllReadBtn');
    const notifWrap = document.getElementById('headerNotifWrap');

    if (notifBtn && notifPopup) {
      notifBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        const isVisible = notifPopup.style.display !== 'none';
        if (isVisible) {
          notifPopup.style.display = 'none';
          notifBtn.setAttribute('aria-expanded', 'false');
        } else {
          notifPopup.style.display = 'block';
          notifBtn.setAttribute('aria-expanded', 'true');
          loadHeaderNotifications();
        }
      });

      if (markAllBtn) {
        markAllBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          fetch('/api/notifications/read', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
          })
            .then(function (res) { return res.json(); })
            .then(function (data) {
              if (data && data.success) {
                if (notifBadge) notifBadge.style.display = 'none';
                if (notifList) {
                  const items = notifList.querySelectorAll('.notif-item.is-unread');
                  items.forEach(function (el) {
                    el.classList.remove('is-unread');
                    el.classList.add('is-read');
                  });
                }
              }
            })
            .catch(function () {});
        });
      }

      document.addEventListener('click', function (e) {
        if (notifWrap && !notifWrap.contains(e.target)) {
          notifPopup.style.display = 'none';
          notifBtn.setAttribute('aria-expanded', 'false');
        }
      });
    }

    const logoutBtn = document.getElementById('headerLogoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', function (e) {
        e.preventDefault();
        const menu = document.getElementById('headerUserMenu');
        if (menu) menu.style.display = 'none';
        const loginBtn = document.getElementById('headerLoginBtn');
        if (loginBtn) loginBtn.setAttribute('aria-expanded', 'false');

        fetch('/api/auth/logout', { method: 'POST' })
          .then(function (res) { return res.json(); })
          .then(function () {
            setAuthState(null);
            const nBadge = document.getElementById('headerNotifBadge');
            if (nBadge) nBadge.style.display = 'none';
            const nPopup = document.getElementById('headerNotifPopup');
            if (nPopup) {
              nPopup.style.display = 'none';
              const nBtn = document.getElementById('headerNotificationsBtn');
              if (nBtn) nBtn.setAttribute('aria-expanded', 'false');
            }
            checkAuthStatus(function () {
              const uid = getUserIdFromUrl() || (currentProfile && (currentProfile.id || currentProfile.userId));
              if (uid) loadProfile(uid);
            });
            showToast('Вы вышли из системы');
          })
          .catch(function () {
            setAuthState(null);
            const nBadge = document.getElementById('headerNotifBadge');
            if (nBadge) nBadge.style.display = 'none';
            const nPopup = document.getElementById('headerNotifPopup');
            if (nPopup) {
              nPopup.style.display = 'none';
              const nBtn = document.getElementById('headerNotificationsBtn');
              if (nBtn) nBtn.setAttribute('aria-expanded', 'false');
            }
            showToast('Вы вышли из системы');
          });
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

    function performLogin(userId, name) {
      fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId: userId, name: name || userId })
      })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (data && data.success && data.user) {
            closeAuthModal();
            setAuthState(data.user);
            loadHeaderNotifications();
            checkAuthStatus(function () {
              const uid = getUserIdFromUrl() || data.user.id;
              if (uid) loadProfile(uid);
            });
            showToast('Вход выполнен: ' + data.user.name);
          } else {
            showToast((data && data.error) || 'Ошибка входа');
          }
        })
        .catch(function () {
          showToast('Ошибка сети при авторизации');
        });
    }

    const btnDemoLogin = document.getElementById('btnAuthLoginDemo');
    if (btnDemoLogin) {
      btnDemoLogin.addEventListener('click', function () {
        performLogin('user_demo', 'Демо Пользователь');
      });
    }

    const btnSubmitLogin = document.getElementById('btnAuthLoginSubmit');
    const authInput = document.getElementById('authUserIdInput');
    if (btnSubmitLogin) {
      btnSubmitLogin.addEventListener('click', function () {
        const val = (authInput ? authInput.value.trim() : '') || 'user_demo';
        performLogin(val, val);
      });
    }
    if (authInput) {
      authInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          const val = authInput.value.trim() || 'user_demo';
          performLogin(val, val);
        }
      });
    }

    // Article report modal controls
    const reportModal = document.getElementById('articleReportModal');
    const btnCloseReport = document.getElementById('btnCloseArticleReportModal');
    if (btnCloseReport) {
      btnCloseReport.addEventListener('click', closeArticleReportModal);
    }
    const btnCancelReport = document.getElementById('btnCancelArticleReport');
    if (btnCancelReport) {
      btnCancelReport.addEventListener('click', closeArticleReportModal);
    }
    if (reportModal) {
      reportModal.addEventListener('click', function (e) {
        if (e.target === reportModal) closeArticleReportModal();
      });
    }

    const reportForm = document.getElementById('articleReportForm');
    if (reportForm) {
      reportForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const articleId = (document.getElementById('reportArticleId') || {}).value;
        const selectedReasonRadio = reportForm.querySelector('input[name="articleReportReason"]:checked');
        const reason = selectedReasonRadio ? selectedReasonRadio.value : 'spam';
        const detailsEl = document.getElementById('articleReportDetails');
        const details = detailsEl ? detailsEl.value.trim() : '';

        if (!articleId) {
          closeArticleReportModal();
          return;
        }

        const submitBtn = document.getElementById('btnSubmitArticleReport');
        if (submitBtn) submitBtn.disabled = true;

        fetch('/api/articles/' + encodeURIComponent(articleId) + '/report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: reason, details: details })
        })
          .then(function (res) {
            return res.json().then(function (data) {
              return { status: res.status, data: data };
            });
          })
          .then(function (result) {
            if (submitBtn) submitBtn.disabled = false;
            if (result.status === 200 && result.data && result.data.success) {
              closeArticleReportModal();
              showToast('Жалоба отправлена');
              markArticleReported(articleId);
            } else if (result.status === 409) {
              closeArticleReportModal();
              showToast('Вы уже отправили жалобу на этот материал');
              markArticleReported(articleId);
            } else if (result.status === 403) {
              closeArticleReportModal();
              showToast('Нельзя пожаловаться на собственный материал');
            } else if (result.status === 401) {
              closeArticleReportModal();
              openAuthModal();
              showToast('Войдите, чтобы отправить жалобу');
            } else {
              showToast((result.data && result.data.error) || 'Ошибка при отправке жалобы');
            }
          })
          .catch(function () {
            if (submitBtn) submitBtn.disabled = false;
            showToast('Ошибка сети при отправке жалобы');
          });
      });
    }

    // Feed share popover controls
    const sharePopover = document.getElementById('feedSharePopover');
    if (sharePopover) {
      const copyBtn = sharePopover.querySelector('[data-action="copy"]');
      if (copyBtn) {
        copyBtn.addEventListener('click', function (e) {
          e.preventDefault();
          const permalink = sharePopover._permalink || window.location.href;
          copyTextToClipboard(permalink, 'Ссылка скопирована');
          closeSharePopover();
        });
      }

      const socialLinks = sharePopover.querySelectorAll('a.comment-share-item');
      socialLinks.forEach(function (link) {
        link.addEventListener('click', function () {
          setTimeout(closeSharePopover, 100);
        });
      });
    }

    document.addEventListener('click', function (e) {
      const popover = document.getElementById('feedSharePopover');
      if (popover && popover.style.display !== 'none') {
        if (!popover.contains(e.target) && !e.target.closest('.btn-card-share')) {
          closeSharePopover();
        }
      }
    });

    // 6. Keyboard dismissals (Escape)
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        const notifPopup = document.getElementById('headerNotifPopup');
        if (notifPopup && notifPopup.style.display !== 'none') {
          notifPopup.style.display = 'none';
          const notifBtn = document.getElementById('headerNotificationsBtn');
          if (notifBtn) notifBtn.setAttribute('aria-expanded', 'false');
          return;
        }
        const sharePopover = document.getElementById('feedSharePopover');
        if (sharePopover && sharePopover.style.display !== 'none') {
          closeSharePopover();
          return;
        }
        const reportModal = document.getElementById('articleReportModal');
        if (reportModal && reportModal.style.display !== 'none') {
          closeArticleReportModal();
          return;
        }
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
          return;
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
        if (currentProfile && (currentProfile.id || currentProfile.userId) && activityHasMore && !isLoadingActivity) {
          loadActivity(currentProfile.id || currentProfile.userId, true);
        }
      });
    }

    // 10. History popstate navigation
    window.addEventListener('popstate', handlePopState);

    // Search input (#profileSearchInput) and clear button (#btnProfileSearchClear)
    const profileSearchInput = document.getElementById('profileSearchInput');
    const searchClearBtn = document.getElementById('btnProfileSearchClear');

    if (profileSearchInput) {
      profileSearchInput.addEventListener('input', function (e) {
        const val = this.value || '';
        if (searchClearBtn) {
          searchClearBtn.style.display = val.trim() ? 'flex' : 'none';
        }
        if (searchDebounceTimer) {
          clearTimeout(searchDebounceTimer);
          searchDebounceTimer = null;
        }
        searchDebounceTimer = setTimeout(function () {
          setSearchQuery(val, true);
        }, 300);
      });

      profileSearchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          if (searchDebounceTimer) {
            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = null;
          }
          setSearchQuery(this.value || '', true);
        } else if (e.key === 'Escape') {
          if (this.value) {
            e.preventDefault();
            this.value = '';
            if (searchClearBtn) {
              searchClearBtn.style.display = 'none';
            }
            if (searchDebounceTimer) {
              clearTimeout(searchDebounceTimer);
              searchDebounceTimer = null;
            }
            setSearchQuery('', true);
          }
        }
      });
    }

    if (searchClearBtn) {
      searchClearBtn.addEventListener('click', function () {
        const searchInput = document.getElementById('profileSearchInput') || profileSearchInput;
        if (searchInput) {
          searchInput.value = '';
          if (typeof searchInput.focus === 'function') {
            searchInput.focus();
          }
        }
        searchClearBtn.style.display = 'none';
        if (searchDebounceTimer) {
          clearTimeout(searchDebounceTimer);
          searchDebounceTimer = null;
        }
        setSearchQuery('', true);
      });
    }

    const searchForms = document.querySelectorAll('.header-search-form, #profileSearchForm');
    for (let i = 0; i < searchForms.length; i++) {
      searchForms[i].addEventListener('submit', function (e) {
        e.preventDefault();
        const inp = this.querySelector('input');
        if (inp) {
          setSearchQuery(inp.value, true);
        }
      });
    }

    // Sidebar topic pill click listener
    document.addEventListener('click', function (e) {
      const pill = e.target.closest('.profile-sidebar-topic-pill[data-topic-id]');
      if (!pill) return;
      const topicId = pill.getAttribute('data-topic-id') || '';
      setTopicFilter(topicId === currentTopic ? '' : topicId, true);
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
        tabLoadedState.publications = null;
        pubOffset = 0;
        pubItems = [];
        if (window.history && window.history.pushState) {
          try {
            const url = new URL(window.location.href);
            if (pubSort !== 'newest') url.searchParams.set('sort', pubSort);
            else url.searchParams.delete('sort');
            window.history.pushState({
              tab: 'publications',
              sort: pubSort,
              q: currentSearchQuery || undefined,
              topic: currentTopic || undefined
            }, '', url.toString());
          } catch (e) {}
        }
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
        tabLoadedState.questions = null;
        questOffset = 0;
        questItems = [];
        if (window.history && window.history.pushState) {
          try {
            const url = new URL(window.location.href);
            if (questSort !== 'newest') url.searchParams.set('sort', questSort);
            else url.searchParams.delete('sort');
            window.history.pushState({
              tab: 'questions',
              sort: questSort,
              status: questStatus,
              q: currentSearchQuery || undefined,
              topic: currentTopic || undefined
            }, '', url.toString());
          } catch (e) {}
        }
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
        tabLoadedState.questions = null;
        questOffset = 0;
        questItems = [];
        if (window.history && window.history.pushState) {
          try {
            const url = new URL(window.location.href);
            if (questStatus !== 'all') url.searchParams.set('status', questStatus);
            else url.searchParams.delete('status');
            window.history.pushState({
              tab: 'questions',
              sort: questSort,
              status: questStatus,
              q: currentSearchQuery || undefined,
              topic: currentTopic || undefined
            }, '', url.toString());
          } catch (e) {}
        }
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
          loadQuestions(currentProfile.id || currentProfile.userId, true);
        }
      });
    }

    // 15. Answers toolbar filter & sorting
    const ansSortBtns = document.querySelectorAll('[data-ans-sort], #sortAnswersNewest, #sortAnswersRating');
    for (let i = 0; i < ansSortBtns.length; i++) {
      ansSortBtns[i].addEventListener('click', function () {
        const sort = this.getAttribute('data-ans-sort');
        if (sort === ansSort) return;
        ansSort = sort;
        for (let j = 0; j < ansSortBtns.length; j++) {
          ansSortBtns[j].classList.toggle('is-active', ansSortBtns[j] === this);
        }
        tabLoadedState.answers = null;
        ansOffset = 0;
        ansItems = [];
        if (window.history && window.history.pushState) {
          try {
            const url = new URL(window.location.href);
            if (ansSort !== 'new') {
              url.searchParams.set('sort', ansSort);
              url.searchParams.set('ans_sort', ansSort);
            } else {
              url.searchParams.delete('sort');
              url.searchParams.delete('ans_sort');
            }
            window.history.pushState({
              tab: 'answers',
              filter: ansFilter,
              sort: ansSort,
              ans_sort: ansSort,
              q: currentSearchQuery || undefined
            }, '', url.toString());
          } catch (e) {}
        }
        if (currentProfile && (currentProfile.id || currentProfile.userId)) {
          loadAnswers(currentProfile.id || currentProfile.userId, false);
        }
      });
    }

    const ansFilterBtns = document.querySelectorAll('[data-ans-filter]');
    for (let i = 0; i < ansFilterBtns.length; i++) {
      ansFilterBtns[i].addEventListener('click', function () {
        const filter = this.getAttribute('data-ans-filter');
        if (filter === ansFilter) return;
        ansFilter = filter;
        for (let j = 0; j < ansFilterBtns.length; j++) {
          ansFilterBtns[j].classList.toggle('is-active', ansFilterBtns[j] === this);
        }
        tabLoadedState.answers = null;
        ansOffset = 0;
        ansItems = [];
        if (window.history && window.history.pushState) {
          try {
            const url = new URL(window.location.href);
            if (ansFilter !== 'all') url.searchParams.set('filter', ansFilter);
            else url.searchParams.delete('filter');
            window.history.pushState({
              tab: 'answers',
              filter: ansFilter,
              sort: ansSort,
              ans_sort: ansSort,
              q: currentSearchQuery || undefined
            }, '', url.toString());
          } catch (e) {}
        }
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
          loadAnswers(currentProfile.id || currentProfile.userId, true);
        }
      });
    }

    // 17. Comments toolbar sorting
    const commSortBtns = document.querySelectorAll('[data-comm-sort]');
    for (let i = 0; i < commSortBtns.length; i++) {
      commSortBtns[i].addEventListener('click', function () {
        const sort = this.getAttribute('data-comm-sort');
        if (sort === commSort) return;
        commSort = sort;
        for (let j = 0; j < commSortBtns.length; j++) {
          commSortBtns[j].classList.toggle('is-active', commSortBtns[j] === this);
          if (commSortBtns[j].hasAttribute('aria-pressed')) {
            commSortBtns[j].setAttribute('aria-pressed', commSortBtns[j] === this ? 'true' : 'false');
          }
        }
        tabLoadedState.comments = null;
        commOffset = 0;
        commItems = [];
        if (window.history && (window.history.pushState || window.history.replaceState)) {
          try {
            const url = new URL(window.location.href);
            url.searchParams.set('tab', 'comments');
            if (commSort !== 'new' && commSort !== 'newest') {
              url.searchParams.set('sort', commSort);
              url.searchParams.set('comm_sort', commSort);
            } else {
              url.searchParams.delete('sort');
              url.searchParams.delete('comm_sort');
            }
            const stateObj = {
              tab: activeTab || 'comments',
              q: currentSearchQuery || undefined,
              topic: currentTopic || undefined,
              sort: commSort,
              comm_sort: commSort
            };
            if (window.history.pushState) {
              window.history.pushState(stateObj, '', url.toString());
            } else if (window.history.replaceState) {
              window.history.replaceState(stateObj, '', url.toString());
            }
          } catch (e) {}
        }
        const uid = (currentProfile && (currentProfile.id || currentProfile.userId)) || getUserIdFromUrl();
        if (uid) {
          loadComments(uid, false);
        }
      });
    }

    // 18. Comments Load More
    const btnLoadMoreComm = document.getElementById('btnProfileLoadMoreComments');
    if (btnLoadMoreComm) {
      btnLoadMoreComm.addEventListener('click', function () {
        if (currentProfile && (currentProfile.id || currentProfile.userId) && commHasMore && !isLoadingComm) {
          loadComments(currentProfile.id || currentProfile.userId, true);
        }
      });
    }

  }

  function init() {
    initTheme();
    initEventListeners();

    const urlParams = new URLSearchParams(window.location.search);
    const initialQ = urlParams.get('q') || '';
    if (initialQ) {
      currentSearchQuery = initialQ;
      const sInput = document.getElementById('profileSearchInput');
      if (sInput) sInput.value = initialQ;
      const sClear = document.getElementById('btnProfileSearchClear');
      if (sClear) sClear.style.display = 'flex';
    }
    const initTab = urlParams.get('tab') || 'overview';
    const initCommSort = urlParams.get('comm_sort') || (initTab === 'comments' ? urlParams.get('sort') : null) || (initTab === 'comments' ? 'newest' : null);
    if (initCommSort) {
      commSort = initCommSort.trim();
      updateCommSortUI(commSort);
    }

    checkAuthStatus(function (user) {
      if (user) {
        loadHeaderNotifications();
      }
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
    updateProfileStats: updateProfileStats,
    setActiveTab: setActiveTab,
    handlePopState: handlePopState,
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
    loadComments: loadComments,
    renderCommentsTab: renderCommentsTab,
    triggerSearch: triggerSearch,
    getSearchQuery: function () { return currentSearchQuery; },
    toggleSubscription: toggleSubscription,
    copyProfileLink: copyProfileLink,
    openEditModal: openEditModal,
    closeEditModal: closeEditModal,
    saveProfileEdit: saveProfileEdit,
    toggleArticleLike: toggleArticleLike,
    toggleArticleBookmark: toggleArticleBookmark,
    openArticleShare: openArticleShare,
    closeSharePopover: closeSharePopover,
    openArticleReport: openArticleReport,
    closeArticleReportModal: closeArticleReportModal,
    isItemBookmarked: isItemBookmarked,
    isItemReported: isItemReported,
    openAuthModal: openAuthModal,
    closeAuthModal: closeAuthModal,
    setAuthState: setAuthState,
    loadHeaderNotifications: loadHeaderNotifications,
    getOffsets: function () {
      return {
        activity: activityOffset,
        publications: pubOffset,
        questions: questOffset,
        answers: ansOffset,
        comments: commOffset
      };
    },
    getSeqTokens: function () {
      return {
        activity: actReqSeq,
        publications: pubReqSeq,
        questions: questReqSeq,
        answers: ansReqSeq,
        comments: commReqSeq
      };
    },
    getActiveTab: function () {
      return activeTab;
    },
    getCurrentProfile: function () {
      return currentProfile;
    },
    setSearchQuery: setSearchQuery,
    triggerSearch: triggerSearch,
    getSearchQuery: function () {
      return currentSearchQuery;
    },
    setTopicFilter: setTopicFilter,
    invalidateTabCaches: invalidateTabCaches,
    initEventListeners: initEventListeners,
    updateSearchResultsCount: updateSearchResultsCount,
    toggleCommentSave: toggleCommentSave,
    openCommentReport: openCommentReport,
    isCommentBookmarked: isCommentBookmarked,
    isCommentReported: isCommentReported,
    getAnsSort: function () { return ansSort; },
    setAnsSort: function (s) { ansSort = s; updateAnsSortUI(s); },
    getCommSort: function () { return commSort; },
    setCommSort: function (s) { commSort = s; updateCommSortUI(s); },
    getTabLoadedState: function () {
      return tabLoadedState;
    }
  };

  document.addEventListener('DOMContentLoaded', init);

})(window);
