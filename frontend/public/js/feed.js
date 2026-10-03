/**
 * SmartContractum Feed Page - Native Modular JavaScript
 * 100% Offline-First, Zero Emojis, Clean Performance
 * Production-ready search, filters, topic navigation, bookmarks, and subscriptions.
 */

(function () {
  'use strict';

  // --------------------------------------------------------------------------
  // 1. Theme Management & Tumbler Binding
  // --------------------------------------------------------------------------
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
      savedTheme =
        localStorage.getItem('ag_theme') ||
        localStorage.getItem('sc_theme') ||
        'dark';
    } catch (e) {}

    applyTheme(savedTheme);

    if (toggleBtn) {
      toggleBtn.addEventListener('click', function () {
        const currentTheme =
          document.documentElement.getAttribute('data-theme') || 'dark';
        const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(nextTheme);
      });
    }
  }

  // --------------------------------------------------------------------------
  // 2. Bookmarks Management (user-scoped with legacy migration)
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
    } catch (e) {}
    updateSavedCounter();
  }

  function isBookmarked(id, item) {
    if (!id) return false;
    if (currentUser && item && (item.hasSaved !== undefined || item.isSaved !== undefined)) {
      return Boolean(item.hasSaved || item.isSaved);
    }
    const bookmarks = getBookmarks();
    return bookmarks.indexOf(id) !== -1;
  }

  function toggleBookmark(id) {
    if (!id) return false;
    const bookmarks = getBookmarks();
    const idx = bookmarks.indexOf(id);
    let bookmarked = false;
    if (idx !== -1) {
      bookmarks.splice(idx, 1);
      bookmarked = false;
      showToast('Публикация удалена из закладок');
    } else {
      bookmarks.push(id);
      bookmarked = true;
      showToast('Публикация сохранена');
    }
    saveBookmarks(bookmarks);
    return bookmarked;
  }

  function updateSavedCounter() {
    const counterEl = document.getElementById('feedSavedCount');
    if (!counterEl) return;
    if (!currentUser || !currentUser.id) {
      const count = getBookmarks().length;
      counterEl.textContent = count;
      counterEl.style.display = 'inline-block';
      return;
    }
    fetch('/api/saved/counts')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.success) {
          counterEl.textContent = data.total;
          counterEl.style.display = 'inline-block';
          const pAll = document.getElementById('savedCountAll');
          const pPub = document.getElementById('savedCountPublications');
          const pQ = document.getElementById('savedCountQuestions');
          const pComm = document.getElementById('savedCountComments');
          if (pAll) pAll.textContent = data.total;
          if (pPub) pPub.textContent = data.publications;
          if (pQ) pQ.textContent = data.questions;
          if (pComm) pComm.textContent = data.comments;
        }
      })
      .catch(function () {
        const count = getBookmarks().length;
        counterEl.textContent = count;
      });
  }

  function runLegacyBookmarksMigration() {
    if (!currentUser || !currentUser.id) return;
    try {
      const migrated = localStorage.getItem('sc_bookmarks_migrated');
      const legacy = localStorage.getItem('sc_bookmarks');
      if (legacy && !migrated) {
        let parsed = JSON.parse(legacy);
        if (Array.isArray(parsed) && parsed.length > 0) {
          fetch('/api/articles/sync-saves', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ articleIds: parsed })
          })
          .then(function (res) { return res.json(); })
          .then(function () {
            const userKey = 'sc_bookmarks_' + currentUser.id;
            localStorage.setItem(userKey, JSON.stringify(parsed));
            localStorage.setItem('sc_bookmarks_migrated', 'true');
            localStorage.removeItem('sc_bookmarks');
            updateSavedCounter();
          })
          .catch(function () {});
          return;
        }
      }
      if (legacy && migrated) {
        localStorage.removeItem('sc_bookmarks');
      }
    } catch (e) {}
  }

  function runLegacyCommentBookmarksMigration() {
    if (!currentUser || !currentUser.id) return;
    try {
      const legacy = localStorage.getItem('sc_comment_bookmarks');
      if (legacy) {
        let parsed = JSON.parse(legacy);
        if (Array.isArray(parsed) && parsed.length > 0) {
          fetch('/api/comments/sync-saves', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ commentIds: parsed })
          })
          .then(function (res) { return res.json(); })
          .then(function (data) {
            if (data && data.success) {
              localStorage.removeItem('sc_comment_bookmarks');
              updateSavedCounter();
            }
          })
          .catch(function () {});
        }
      }
    } catch (e) {}
  }

  function syncLocalBookmarksWithServer() {
    runLegacyBookmarksMigration();
  }

  function showToast(message, actionText, onAction) {
    let toast = document.getElementById('feedToast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'feedToast';
      toast.className = 'feed-toast';
      document.body.appendChild(toast);
    }
    toast.innerHTML = '';
    const span = document.createElement('span');
    span.textContent = message;
    toast.appendChild(span);

    if (actionText && typeof onAction === 'function') {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'feed-toast-action-btn';
      btn.textContent = actionText;
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        toast.style.display = 'none';
        onAction();
      });
      toast.appendChild(btn);
    }

    toast.style.display = 'inline-flex';
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(function () {
      toast.style.display = 'none';
    }, actionText ? 5000 : 2800);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // --------------------------------------------------------------------------
  // --------------------------------------------------------------------------
  // 3. Russian Pluralization & Text Helpers (Strict Onest & Offline)
  // --------------------------------------------------------------------------
  function pluralize(n, one, two, five) {
    const num = Math.abs(n) % 100;
    const num1 = num % 10;
    if (num > 10 && num < 20) return five;
    if (num1 > 1 && num1 < 5) return two;
    if (num1 === 1) return one;
    return five;
  }

  function pluralizePublications(n) {
    return n + ' ' + pluralize(n, 'публикация', 'публикации', 'публикаций');
  }

  function pluralizeAuthors(n) {
    return n + ' ' + pluralize(n, 'автор', 'автора', 'авторов');
  }

  function pluralizeTopics(n) {
    return n + ' ' + pluralize(n, 'тема', 'темы', 'тем');
  }

  function pluralizeTags(n) {
    return n + ' ' + pluralize(n, 'хэштег', 'хэштега', 'хэштегов');
  }

  // --------------------------------------------------------------------------
  // 3b. State Management & URL Synchronization
  // --------------------------------------------------------------------------
  const state = {
    search: '',
    sort: 'newest',
    tab: 'focus', // 'focus' | 'top' | 'new' | 'subscriptions' | 'clubs' | 'companies' | 'directions' | 'saved'
    questionStatus: 'all', // 'all' | 'unanswered' | 'solved'
    topPeriod: 'week', // 'day' | 'week' | 'month' | 'all'
    activeClubId: null,
    activeCompanyId: null,
    companiesSubtab: 'catalog', // 'catalog' | 'articles'
    savedOnly: false,
    savedType: 'all', // 'all' | 'publications' | 'questions' | 'comments'
    limit: 10,
    offset: 0,
    total: 0,
    hasMore: false,
    articles: [],
    topicCounts: {},
    isLoading: false,
    requestGeneration: 0,
    noSubscriptions: false,
    feedSettings: {
      materialTypes: ['publication', 'question'],
      complexityLevels: []
    },
    filters: {
      types: [],
      topics: [],
      complexities: [],
      period: 'all',
      dateFrom: '',
      dateTo: '',
      format: 'all',
      formats: [],
      audience: 'all',
      audiences: []
    },
    userSubscriptions: {
      authors: [],
      topics: [],
      tags: [],
      clubs: [],
      companies: []
    },
    userExceptions: {
      authors: [],
      topics: [],
      tags: [],
      clubs: [],
      companies: []
    }
  };

  let currentUser = null;
  let pendingTabAfterAuth = null;
  let feedAbortController = null;

  function parseURLParams() {
    const params = new URLSearchParams(window.location.search);
    let sortVal = params.get('sort') || 'newest';
    if (sortVal === 'comments') sortVal = 'discussed';
    state.sort = sortVal;

    const tabParam = (params.get('tab') || '').toLowerCase();
    const savedParam = params.get('saved');
    const clubParam = params.get('club') || params.get('clubId');
    const companyParam = params.get('company') || params.get('companyId');
    const periodParam = params.get('period');

    if (periodParam && ['day', 'week', 'month', 'all'].includes(periodParam)) {
      state.topPeriod = periodParam;
    } else {
      state.topPeriod = 'week';
    }

    if (clubParam) {
      state.tab = 'clubs';
      state.activeClubId = clubParam;
      state.savedOnly = false;
    } else if (companyParam) {
      state.tab = 'companies';
      state.activeCompanyId = companyParam;
      state.savedOnly = false;
    } else if (tabParam === 'questions') {
      state.tab = 'questions';
      state.savedOnly = false;
    } else if (tabParam === 'my' || tabParam === 'subscriptions') {
      state.tab = 'subscriptions';
      state.savedOnly = false;
    } else if (tabParam === 'saved' || savedParam === '1' || savedParam === 'true') {
      state.tab = 'saved';
      state.savedOnly = true;
      const typeParam = (params.get('type') || params.get('savedType') || 'all').toLowerCase();
      if (['all', 'publications', 'questions', 'comments'].includes(typeParam)) {
        state.savedType = typeParam;
      } else {
        state.savedType = 'all';
      }
    } else if (tabParam === 'all' || tabParam === 'focus') {
      state.tab = 'all';
      state.savedOnly = false;
    } else if (['top', 'new', 'clubs', 'companies', 'directions', 'topics', 'blogs'].includes(tabParam)) {
      if (tabParam === 'topics') {
        state.tab = 'directions';
      } else if (tabParam === 'blogs') {
        state.tab = 'companies';
      } else {
        state.tab = tabParam;
      }
      state.savedOnly = false;
    } else {
      state.tab = 'all';
      state.savedOnly = false;
    }
    state.questionStatus = params.get('questionStatus') || 'all';

    // Temporary filters from URL
    const typesParam = params.get('types');
    state.filters.types = typesParam ? typesParam.split(',').filter(Boolean) : [];

    const topicsParam = params.get('topics') || params.get('topic');
    if (topicsParam && topicsParam !== 'all') {
      state.filters.topics = topicsParam.split(',').filter(Boolean);
    } else {
      state.filters.topics = [];
    }

    const compParam = params.get('complexities') || params.get('complexity') || params.get('complexityLevels');
    if (compParam && compParam !== 'all') {
      state.filters.complexities = compParam.split(',').filter(Boolean);
    } else {
      state.filters.complexities = [];
    }

    state.filters.period = params.get('period') || 'all';
    state.filters.dateFrom = params.get('dateFrom') || '';
    state.filters.dateTo = params.get('dateTo') || '';

    // Formats: supports 'formats' (comma-separated or repeated) and 'format' (single)
    const formatsParam = params.get('formats') || params.get('format');
    if (formatsParam && formatsParam !== 'all') {
      state.filters.formats = formatsParam.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
      state.filters.format = state.filters.formats[0] || 'all';
    } else {
      state.filters.formats = [];
      state.filters.format = 'all';
    }

    // Audiences: supports 'audiences' (comma-separated or repeated) and 'audience' (single)
    const audiencesParam = params.get('audiences') || params.get('audience');
    if (audiencesParam && audiencesParam !== 'all') {
      state.filters.audiences = audiencesParam.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
      state.filters.audience = state.filters.audiences[0] || 'all';
    } else {
      state.filters.audiences = [];
      state.filters.audience = 'all';
    }

    // Sync input controls with URL state
    const searchInput = document.getElementById('feedSearchInput');
    const clearBtn = document.getElementById('feedSearchClearBtn');
    if (searchInput) {
      searchInput.value = state.search;
      if (clearBtn) {
        clearBtn.style.display = state.search ? 'inline-flex' : 'none';
      }
    }

    const sortSelect = document.getElementById('feedSortSelect');
    if (sortSelect) {
      sortSelect.value = state.sort;
    }
    updateSortUI(state.sort);

    updatePeriodVisibility();
    updateSubnavTabsUI();
    updateQuestionStatusPillsUI();
    renderActiveChips();
    updateFilterBadge();
  }

  const SORT_LABELS = {
    newest: 'Сначала новые',
    rating: 'По рейтингу',
    popular: 'По популярности',
    discussed: 'По обсуждаемости'
  };

  function updateSortUI(sortValue) {
    const val = sortValue || state.sort || 'newest';
    const labelEl = document.getElementById('feedSortCurrentLabel');
    if (labelEl) {
      labelEl.textContent = SORT_LABELS[val] || SORT_LABELS.newest;
    }
    const sortSelect = document.getElementById('feedSortSelect');
    if (sortSelect && sortSelect.value !== val) {
      sortSelect.value = val;
    }
    const menu = document.getElementById('feedSortCustomMenu');
    if (menu) {
      const options = menu.querySelectorAll('.feed-sort-option');
      options.forEach(function (opt) {
        const optVal = opt.getAttribute('data-value');
        const isMatch = optVal === val;
        opt.classList.toggle('active', isMatch);
        opt.setAttribute('aria-selected', isMatch ? 'true' : 'false');
        opt.setAttribute('tabindex', isMatch ? '0' : '-1');
      });
    }
  }

  function updateQuestionStatusPillsUI() {
    const wrap = document.getElementById('feedQuestionsStatusPills');
    if (!wrap) return;
    const current = state.questionStatus || 'all';
    const pills = wrap.querySelectorAll('.feed-status-pill');
    pills.forEach(function (pill) {
      const s = pill.getAttribute('data-status') || 'all';
      pill.classList.toggle('active', s === current);
    });
  }

  function updatePeriodVisibility() {
    const wrap = document.getElementById('feedPeriodSelectWrap');
    if (!wrap) return;
    const showPeriod = state.sort !== 'newest';
    wrap.style.display = showPeriod ? 'inline-block' : 'none';
  }

  function syncURL(replace) {
    const params = new URLSearchParams();
    if (state.tab && state.tab !== 'focus') {
      params.set('tab', state.tab);
    }
    if (state.tab === 'saved' && state.savedType && state.savedType !== 'all') {
      params.set('type', state.savedType);
    }
    if (state.tab === 'questions' && state.questionStatus && state.questionStatus !== 'all') {
      params.set('questionStatus', state.questionStatus);
    }
    if (state.tab === 'top' && state.topPeriod && state.topPeriod !== 'week') {
      params.set('period', state.topPeriod);
    }
    if (state.tab === 'clubs' && state.activeClubId) {
      params.set('club', state.activeClubId);
    }
    if (state.tab === 'companies' && state.activeCompanyId) {
      params.set('company', state.activeCompanyId);
    }
    if (state.search) params.set('search', state.search);
    if (state.sort && state.sort !== 'newest') params.set('sort', state.sort);

    if (state.filters.types && state.filters.types.length > 0) {
      params.set('types', state.filters.types.join(','));
    }
    if (state.filters.topics && state.filters.topics.length > 0) {
      params.set('topics', state.filters.topics.join(','));
    }
    if (state.filters.complexities && state.filters.complexities.length > 0) {
      params.set('complexities', state.filters.complexities.join(','));
    }
    if (state.filters.period && state.filters.period !== 'all') {
      params.set('period', state.filters.period);
    }
    if (state.filters.dateFrom) params.set('dateFrom', state.filters.dateFrom);
    if (state.filters.dateTo) params.set('dateTo', state.filters.dateTo);
    if (state.filters.formats && state.filters.formats.length > 0) {
      params.set('formats', state.filters.formats.join(','));
      params.set('format', state.filters.formats[0]);
    } else if (state.filters.format && state.filters.format !== 'all') {
      params.set('format', state.filters.format);
    }
    if (state.filters.audiences && state.filters.audiences.length > 0) {
      params.set('audiences', state.filters.audiences.join(','));
      params.set('audience', state.filters.audiences[0]);
    } else if (state.filters.audience && state.filters.audience !== 'all') {
      params.set('audience', state.filters.audience);
    }

    const queryString = params.toString();
    const newURL = window.location.pathname + (queryString ? '?' + queryString : '');

    try {
      if (replace) {
        window.history.replaceState({ feedState: Object.assign({}, state) }, '', newURL);
      } else {
        window.history.pushState({ feedState: Object.assign({}, state) }, '', newURL);
      }
      sessionStorage.setItem('sc_feed_url', window.location.href);
    } catch (e) {}

    renderActiveChips();
    updateFilterBadge();
  }

  // --------------------------------------------------------------------------
  // 4. Auth & User Profile Management
  // --------------------------------------------------------------------------
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
    currentUser = user;
    window.currentUser = user;
    window._reportedArticleIds = new Set();
    const personalElements = document.querySelectorAll('.personal-tab');
    personalElements.forEach(function (el) {
      el.style.display = user ? 'inline-flex' : 'none';
    });

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

    const manageSubsBtn = document.getElementById('btnManageSubscriptions');
    if (manageSubsBtn) {
      manageSubsBtn.style.display = (state.tab === 'my' && user) ? 'inline-flex' : 'none';
    }

    if (user) {
      loadFeedSettings();
      syncLocalBookmarksWithServer();
      runLegacyCommentBookmarksMigration();
      updateSavedCounter();
    } else {
      updateSavedCounter();
    }
  }

  function openAuthModal(targetTab) {
    pendingTabAfterAuth = targetTab || null;
    const modal = document.getElementById('authModal');
    if (modal) modal.style.display = 'flex';
  }
  window.openAuthModal = openAuthModal;

  function closeAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) modal.style.display = 'none';
    pendingTabAfterAuth = null;
  }

  function initAuthControls() {
    const loginBtn = document.getElementById('headerLoginBtn');
    if (loginBtn) {
      loginBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (currentUser) {
          if (confirm('Вы вошли как «' + currentUser.name + '». Выйти из профиля?')) {
            fetch('/api/auth/logout', { method: 'POST' })
              .then(function (res) { return res.json(); })
              .then(function () {
                setAuthState(null);
                if (state.tab === 'my' || state.tab === 'saved') {
                  switchTab('all');
                } else {
                  fetchFeed(true);
                }
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

    const demoLoginBtn = document.getElementById('btnAuthLoginDemo');
    if (demoLoginBtn) {
      demoLoginBtn.addEventListener('click', function () {
        fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ userId: 'user_demo', name: 'Демо Пользователь' })
        })
          .then(function (res) { return res.json(); })
          .then(function (data) {
            if (data && data.success && data.user) {
              setAuthState(data.user);
              closeAuthModal();
              showToast('Вход выполнен: ' + data.user.name);
              if (pendingTabAfterAuth) {
                switchTab(pendingTabAfterAuth);
              } else {
                fetchFeed(true);
              }
            }
          });
      });
    }

    const customSubmitBtn = document.getElementById('btnAuthLoginSubmit');
    if (customSubmitBtn) {
      customSubmitBtn.addEventListener('click', function () {
        const inp = document.getElementById('authUserIdInput');
        const val = (inp ? inp.value.trim() : '') || 'user_demo';
        fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ userId: val, name: val })
        })
          .then(function (res) { return res.json(); })
          .then(function (data) {
            if (data && data.success && data.user) {
              setAuthState(data.user);
              closeAuthModal();
              showToast('Вход выполнен: ' + data.user.name);
              if (pendingTabAfterAuth) {
                switchTab(pendingTabAfterAuth);
              } else {
                fetchFeed(true);
              }
            }
          });
      });
    }
  }

  // --------------------------------------------------------------------------
  // 5. Sub-Nav Bar & Feed Settings Panel (Unified Slide-out Panel)
  // --------------------------------------------------------------------------
  let savedSettingsState = {
    materialTypes: ['article', 'post', 'news', 'question'],
    complexityLevels: ['all'],
    subscriptions: { authors: [], topics: [], tags: [] },
    exceptions: { authors: [], topics: [], tags: [] }
  };

  let draftSettingsState = {
    materialTypes: ['article', 'post', 'news', 'question'],
    complexityLevels: ['all'],
    subscriptions: { authors: [], topics: [], tags: [] },
    exceptions: { authors: [], topics: [], tags: [] }
  };

  let activeSubsMode = 'subscriptions'; // 'subscriptions' | 'exceptions'
  let activeSettingsSubsType = 'author'; // 'author' | 'topic' | 'tag'
  let isCatalogOpen = false;
  let catalogOffset = 0;
  const CATALOG_LIMIT = 20;
  let catalogItems = [];
  let catalogHasMore = false;
  let catalogRequestSeq = 0;
  let catalogDebounceTimer = null;

  function cloneItem(item) {
    if (!item) return null;
    if (typeof item !== 'object') return { id: String(item), title: String(item) };
    return Object.assign({}, item);
  }

  function cloneSettings(s) {
    if (!s) return {};
    return {
      materialTypes: Array.isArray(s.materialTypes) ? s.materialTypes.slice() : ['article', 'post', 'news', 'question'],
      complexityLevels: Array.isArray(s.complexityLevels) ? s.complexityLevels.slice() : ['all'],
      subscriptions: {
        authors: Array.isArray(s.subscriptions && s.subscriptions.authors) ? s.subscriptions.authors.map(cloneItem) : [],
        topics: Array.isArray(s.subscriptions && s.subscriptions.topics) ? s.subscriptions.topics.map(cloneItem) : [],
        tags: Array.isArray(s.subscriptions && s.subscriptions.tags) ? s.subscriptions.tags.map(cloneItem) : []
      },
      exceptions: {
        authors: Array.isArray(s.exceptions && s.exceptions.authors) ? s.exceptions.authors.map(cloneItem) : [],
        topics: Array.isArray(s.exceptions && s.exceptions.topics) ? s.exceptions.topics.map(cloneItem) : [],
        tags: Array.isArray(s.exceptions && s.exceptions.tags) ? s.exceptions.tags.map(cloneItem) : []
      }
    };
  }

  function hasUnsavedSettingsChanges() {
    const draftMT = (draftSettingsState.materialTypes || []).slice().sort();
    const savedMT = (savedSettingsState.materialTypes || []).slice().sort();
    if (draftMT.length !== savedMT.length) return true;
    for (let i = 0; i < draftMT.length; i++) {
      if (draftMT[i] !== savedMT[i]) return true;
    }

    const draftCL = (draftSettingsState.complexityLevels || []).slice().sort();
    const savedCL = (savedSettingsState.complexityLevels || []).slice().sort();
    if (draftCL.length !== savedCL.length) return true;
    for (let i = 0; i < draftCL.length; i++) {
      if (draftCL[i] !== savedCL[i]) return true;
    }

    return false;
  }

  function validateMaterialTypes() {
    const types = draftSettingsState.materialTypes || [];
    const isValid = types.length > 0;
    const err = document.getElementById('feedMaterialTypesError');
    if (err) {
      err.style.display = isValid ? 'none' : 'block';
    }
    return isValid;
  }

  function updateSettingsDraftUI() {
    const hasChanges = hasUnsavedSettingsChanges();
    const isValid = validateMaterialTypes();

    const indicator = document.getElementById('feedSettingsUnsavedIndicator');
    if (indicator) {
      indicator.style.display = hasChanges ? 'inline-flex' : 'none';
    }

    const saveBtn = document.getElementById('btnSaveFeedSettings');
    if (saveBtn) {
      saveBtn.disabled = !hasChanges || !isValid;
    }
  }

  function handleComplexityTumblerChange(inputs, clickedInput, onUpdate) {
    const val = clickedInput.value || clickedInput.getAttribute('data-complexity');
    const isTurningOn = clickedInput.checked;
    const allInput = Array.from(inputs).find(function (i) {
      const c = i.value || i.getAttribute('data-complexity');
      return c === 'all';
    });
    const specificInputs = Array.from(inputs).filter(function (i) {
      return i !== allInput;
    });

    const c = val;
    if (c === 'all') {
      if (!isTurningOn) {
        // Cannot uncheck only active "Любой уровень"
        clickedInput.checked = true;
        return;
      }
      // Turning on "Любой уровень" resets specific levels
      specificInputs.forEach(function (inp) {
        inp.checked = false;
      });
    } else {
      if (isTurningOn) {
        // Turning on specific disables "Любой уровень"
        if (allInput) allInput.checked = false;
      } else {
        // Turning off specific: if no specific remaining, re-enable "Любой уровень"
        const anySpecificChecked = specificInputs.some(function (inp) { return inp.checked; });
        if (!anySpecificChecked && allInput) {
          allInput.checked = true;
        }
      }
    }
    if (onUpdate) onUpdate();
  }

  function handleFilterTypeTumblerChange(inputs, clickedInput, onUpdate) {
    const val = clickedInput.value || clickedInput.getAttribute('data-type');
    const isTurningOn = clickedInput.checked;
    const allInput = Array.from(inputs).find(function (i) {
      const t = i.value || i.getAttribute('data-type');
      return t === 'all';
    });
    const specificInputs = Array.from(inputs).filter(function (i) {
      return i !== allInput;
    });

    const t = val;
    if (t === 'all') {
      if (!isTurningOn) {
        // Cannot uncheck only active "Все типы"
        clickedInput.checked = true;
        return;
      }
      // Turning on "Все типы" resets specific types
      specificInputs.forEach(function (inp) {
        inp.checked = false;
      });
    } else {
      if (isTurningOn) {
        // Turning on specific disables "Все типы"
        if (allInput) allInput.checked = false;
      } else {
        // Turning off specific: if no specific remaining, re-enable "Все типы"
        const anySpecificChecked = specificInputs.some(function (inp) { return inp.checked; });
        if (!anySpecificChecked && allInput) {
          allInput.checked = true;
        }
      }
    }
    if (onUpdate) onUpdate();
  }

  function syncSettingsUIFromDraft() {
    // 1. Material Types Tumblers
    const types = draftSettingsState.materialTypes || ['publication', 'question'];
    const typeInputs = document.querySelectorAll('input[name="feedMaterialType"]');
    typeInputs.forEach(function (inp) {
      const isPub = (inp.value === 'publication');
      inp.checked = (types.indexOf(inp.value) !== -1 || (isPub && (types.indexOf('article') !== -1 || types.indexOf('post') !== -1 || types.indexOf('news') !== -1)));
    });

    // 2. Complexity Tumblers
    const compLevels = draftSettingsState.complexityLevels || ['all'];
    const isAll = (compLevels.indexOf('all') !== -1 || compLevels.length === 0);
    const compInputs = document.querySelectorAll('input[name="feedComplexityLevel"]');
    compInputs.forEach(function (inp) {
      const c = inp.value || inp.getAttribute('data-complexity');
      if (c === 'all') {
        inp.checked = isAll;
      } else {
        inp.checked = (!isAll && (compLevels.indexOf(c) !== -1 || (c === 'none' && compLevels.indexOf('unspecified') !== -1)));
      }
    });

    validateMaterialTypes();
    updateSettingsDraftUI();
  }

  function updateFeedPanelsPosition() {
    const subnav = document.getElementById('feedSubnavBar') || document.querySelector('.feed-subnav-bar');
    if (!subnav) return;
    const rect = subnav.getBoundingClientRect();
    const bottomPos = Math.max(0, Math.round(rect.bottom));
    document.documentElement.style.setProperty('--feed-header-total-height', bottomPos + 'px');
  }

  window.addEventListener('resize', updateFeedPanelsPosition);
  window.addEventListener('scroll', updateFeedPanelsPosition, { passive: true });
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', updateFeedPanelsPosition);
    window.visualViewport.addEventListener('scroll', updateFeedPanelsPosition, { passive: true });
  }

  function openFeedSettingsPanel() {
    closeFeedFiltersPanel();
    updateFeedPanelsPosition();

    const panel = document.getElementById('feedSettingsPanel');
    const toggleBtn = document.getElementById('btnFeedSettingsToggle');

    if (panel) {
      panel.style.display = 'block';
    }
    if (toggleBtn) {
      toggleBtn.classList.add('active');
      toggleBtn.setAttribute('aria-expanded', 'true');
    }

    syncSettingsUIFromDraft();
  }

  function closeFeedSettingsPanel(isSaved, preserveDraft) {
    const panel = document.getElementById('feedSettingsPanel');
    const toggleBtn = document.getElementById('btnFeedSettingsToggle');

    if (panel) {
      panel.style.display = 'none';
    }
    if (toggleBtn) {
      toggleBtn.classList.remove('active');
      toggleBtn.setAttribute('aria-expanded', 'false');
    }

    if (!isSaved && !preserveDraft) {
      // Discard unsaved changes and reset draft to saved state
      draftSettingsState = cloneSettings(savedSettingsState);
      isCatalogOpen = false;
      const catPane = document.getElementById('feedCatalogPane');
      const userPane = document.getElementById('feedUserItemsPane');
      if (catPane) catPane.style.display = 'none';
      if (userPane) userPane.style.display = 'block';
      syncSettingsUIFromDraft();
    }
  }

  function toggleFeedSettingsPanel() {
    const panel = document.getElementById('feedSettingsPanel');
    if (panel && panel.style.display !== 'none') {
      closeFeedSettingsPanel(false);
    } else {
      openFeedSettingsPanel();
    }
  }

  function openFeedFiltersPanel() {
    closeFeedSettingsPanel(false, true); // Close settings panel preserving draft in memory
    updateFeedPanelsPosition();

    const panel = document.getElementById('feedFiltersPanel');
    const toggleBtn = document.getElementById('btnFeedFiltersToggle');
    const drawerWrap = document.getElementById('feedFiltersDrawerWrap');

    if (panel) {
      panel.style.display = 'block';
    }
    if (drawerWrap) {
      requestAnimationFrame(function () {
        drawerWrap.classList.add('is-open');
      });
    }
    if (toggleBtn) {
      toggleBtn.classList.add('active');
      toggleBtn.setAttribute('aria-expanded', 'true');
    }

    syncFilterFormUI();
  }

  function closeFeedFiltersPanel() {
    const panel = document.getElementById('feedFiltersPanel');
    const toggleBtn = document.getElementById('btnFeedFiltersToggle');
    const drawerWrap = document.getElementById('feedFiltersDrawerWrap');

    if (drawerWrap) {
      drawerWrap.classList.remove('is-open');
    }
    if (toggleBtn) {
      toggleBtn.classList.remove('active');
      toggleBtn.setAttribute('aria-expanded', 'false');
    }
    if (panel) {
      setTimeout(function () {
        if (!drawerWrap || !drawerWrap.classList.contains('is-open')) {
          panel.style.display = 'none';
        }
      }, 230);
    }
  }

  function toggleFeedFiltersPanel() {
    const panel = document.getElementById('feedFiltersPanel');
    const drawerWrap = document.getElementById('feedFiltersDrawerWrap');
    const isOpen = (panel && panel.style.display !== 'none') || (drawerWrap && drawerWrap.classList.contains('is-open'));
    if (isOpen) {
      closeFeedFiltersPanel();
    } else {
      openFeedFiltersPanel();
    }
  }

  const defaultFiltersState = {
    types: [],
    topics: [],
    complexities: [],
    period: 'all',
    dateFrom: '',
    dateTo: '',
    format: 'all',
    formats: [],
    audience: 'all',
    audiences: []
  };

  function cloneFilters(f) {
    if (!f) return Object.assign({}, defaultFiltersState);
    return {
      types: Array.isArray(f.types) ? f.types.slice() : [],
      topics: Array.isArray(f.topics) ? f.topics.slice() : [],
      complexities: Array.isArray(f.complexities) ? f.complexities.slice() : [],
      period: f.period || 'all',
      dateFrom: f.dateFrom || '',
      dateTo: f.dateTo || '',
      format: f.format || 'all',
      formats: Array.isArray(f.formats) ? f.formats.slice() : [],
      audience: f.audience || 'all',
      audiences: Array.isArray(f.audiences) ? f.audiences.slice() : []
    };
  }

  function initSubnavTabs() {
    const tabFocus = document.getElementById('tabFeedFocus');
    const tabTop = document.getElementById('tabFeedTop');
    const tabNew = document.getElementById('tabFeedNew');
    const tabSubs = document.getElementById('tabFeedSubscriptions');
    const tabClubs = document.getElementById('tabFeedClubs');
    const tabCompanies = document.getElementById('tabFeedCompanies');
    const tabDirections = document.getElementById('tabFeedDirections');

    const tabAll = document.getElementById('tabFeedAll');
    const tabQuestions = document.getElementById('tabFeedQuestions');
    const tabMy = document.getElementById('tabFeedMy');
    const tabSaved = document.getElementById('feedSavedTab');
    const btnFeedSettings = document.getElementById('btnFeedSettingsToggle');
    const btnFeedFilters = document.getElementById('btnFeedFiltersToggle');
    const manageSubsBtn = document.getElementById('btnManageSubscriptions');

    if (btnFeedSettings) {
      btnFeedSettings.addEventListener('click', toggleFeedSettingsPanel);
    }

    if (btnFeedFilters) {
      btnFeedFilters.addEventListener('click', toggleFeedFiltersPanel);
    }

    if (manageSubsBtn) {
      manageSubsBtn.addEventListener('click', function () {
        openSubscriptionsModal('author');
      });
    }

    if (tabAll) {
      tabAll.addEventListener('click', function () {
        switchTab('all');
      });
    }

    if (tabQuestions) {
      tabQuestions.addEventListener('click', function () {
        switchTab('questions');
      });
    }

    if (tabFocus) {
      tabFocus.addEventListener('click', function () {
        switchTab('all');
      });
    }

    if (tabTop) {
      tabTop.addEventListener('click', function () {
        switchTab('top');
      });
    }

    if (tabNew) {
      tabNew.addEventListener('click', function () {
        switchTab('new');
      });
    }

    if (tabSubs) {
      tabSubs.addEventListener('click', function () {
        if (state.tab === 'subscriptions' || state.tab === 'my') {
          showToast('Возврат ко всем публикациям');
          switchTab('all');
        } else if (!currentUser) {
          openAuthModal('subscriptions');
        } else {
          switchTab('subscriptions');
        }
      });
    }

    if (tabClubs) {
      tabClubs.addEventListener('click', function () {
        switchTab('clubs');
      });
    }

    if (tabCompanies) {
      tabCompanies.addEventListener('click', function () {
        switchTab('companies');
      });
    }

    if (tabDirections) {
      tabDirections.addEventListener('click', function () {
        switchTab('directions');
      });
    }

    if (tabMy) {
      tabMy.addEventListener('click', function () {
        if (state.tab === 'my' || state.tab === 'subscriptions') {
          showToast('Возврат ко всем публикациям');
          switchTab('all');
        } else if (!currentUser) {
          openAuthModal('subscriptions');
        } else {
          switchTab('subscriptions');
        }
      });
    }

    if (tabSaved) {
      tabSaved.addEventListener('click', function () {
        if (!currentUser) {
          openAuthModal('saved');
        } else {
          switchTab('saved');
        }
      });
    }

    // Top period pills
    const periodPills = document.querySelectorAll('.feed-top-period-bar .feed-period-pill');
    periodPills.forEach(function (pill) {
      pill.addEventListener('click', function () {
        const p = pill.getAttribute('data-period');
        if (p) {
          state.topPeriod = p;
          periodPills.forEach(function (btn) { btn.classList.toggle('active', btn === pill); });
          syncURL(false);
          fetchFeed(true);
        }
      });
    });

    // Sidebar All Directions button
    const btnShowAllTopics = document.getElementById('btnShowAllTopics');
    if (btnShowAllTopics) {
      btnShowAllTopics.addEventListener('click', function () {
        switchTab('directions');
        syncURL(false);
      });
    }
  }

  function switchTab(tabName) {
    if (tabName === 'my') tabName = 'subscriptions';
    if (tabName === 'focus') tabName = 'all';

    // Isolate filter state per tab
    state.tabFilters = state.tabFilters || {};
    if (state.tab) {
      state.tabFilters[state.tab] = cloneFilters(state.filters);
    }

    state.tab = tabName;
    state.savedOnly = (tabName === 'saved');
    state.offset = 0;

    if (state.tabFilters[tabName]) {
      state.filters = cloneFilters(state.tabFilters[tabName]);
      if (typeof syncFilterFormUI === 'function') {
        syncFilterFormUI();
      }
    }

    // Adjust controls for Questions tab vs standard tabs
    const questionsPills = document.getElementById('feedQuestionsStatusPills');
    const searchInput = document.getElementById('feedSearchInput');
    const typesFilterGroup = document.getElementById('feedFilterGroupTypes');
    const compFilterGroup = document.getElementById('feedFilterGroupComplexity');

    if (tabName === 'questions') {
      if (questionsPills) questionsPills.style.display = 'inline-flex';
      if (searchInput) searchInput.placeholder = 'Поиск по вопросам и ответам...';
      if (typesFilterGroup) typesFilterGroup.style.display = 'none';
      if (compFilterGroup) compFilterGroup.style.display = 'none';
      updateQuestionStatusPillsUI();
    } else {
      if (questionsPills) questionsPills.style.display = 'none';
      if (searchInput) searchInput.placeholder = 'Поиск по ленте...';
      if (typesFilterGroup) typesFilterGroup.style.display = 'block';
      if (compFilterGroup) compFilterGroup.style.display = 'block';
    }

    if (tabName !== 'clubs') state.activeClubId = null;
    if (tabName !== 'companies') state.activeCompanyId = null;

    updateSubnavTabsUI();

    const manageSubsBtn = document.getElementById('btnManageSubscriptions');
    if (manageSubsBtn) {
      manageSubsBtn.style.display = ((tabName === 'subscriptions' || tabName === 'my') && currentUser) ? 'inline-flex' : 'none';
    }

    syncURL(false);

    if (tabName === 'clubs' || tabName === 'companies' || tabName === 'directions') {
      hideOfflineBadge();
      if (feedAbortController) {
        feedAbortController.abort();
        feedAbortController = null;
      }
      state.requestGeneration = (state.requestGeneration || 0) + 1;
    }

    if (tabName === 'clubs') {
      if (state.activeClubId) {
        openClubDetail(state.activeClubId);
      } else {
        loadClubs();
      }
    } else if (tabName === 'companies') {
      if (state.activeCompanyId) {
        openCompanyDetail(state.activeCompanyId);
      } else {
        loadCompanies(state.companiesSubtab || 'catalog');
      }
    } else if (tabName === 'directions') {
      loadDirections();
    } else {
      fetchFeed(true);
    }
  }

  function updateFeedTitleUI() {
    const titleEl = document.querySelector('.feed-compact-title');
    const titles = {
      all: 'Публикации — SmartContractum',
      questions: 'Вопросы — SmartContractum',
      focus: 'Публикации — SmartContractum',
      top: 'Топ публикаций — SmartContractum',
      new: 'Новые публикации — SmartContractum',
      subscriptions: 'Мои подписки — SmartContractum',
      my: 'Мои подписки — SmartContractum',
      clubs: 'Клубы и сообщества — SmartContractum',
      companies: 'Блоги - SmartContractum',
      blogs: 'Блоги - SmartContractum',
      directions: 'Темы — SmartContractum',
      saved: 'Сохраненные — SmartContractum'
    };
    const t = titles[state.tab] || 'Лента публикаций — SmartContractum';
    document.title = t;
    if (titleEl) {
      titleEl.textContent = t.split(' - ')[0].replace(/ \S+ SmartContractum$/, '');
    }
  }

  function updateSubnavTabsUI() {
    const tabFocus = document.getElementById('tabFeedFocus');
    const tabTop = document.getElementById('tabFeedTop');
    const tabNew = document.getElementById('tabFeedNew');
    const tabSubs = document.getElementById('tabFeedSubscriptions');
    const tabClubs = document.getElementById('tabFeedClubs');
    const tabCompanies = document.getElementById('tabFeedCompanies');
    const tabDirections = document.getElementById('tabFeedDirections');
    const tabAll = document.getElementById('tabFeedAll');
    const tabQuestions = document.getElementById('tabFeedQuestions');
    const tabMy = document.getElementById('tabFeedMy');
    const tabSaved = document.getElementById('feedSavedTab');

    const cur = state.tab;

    if (tabAll) {
      const isAll = cur === 'all' || cur === 'focus';
      tabAll.classList.toggle('active', isAll);
      tabAll.setAttribute('aria-selected', isAll ? 'true' : 'false');
    }
    if (tabQuestions) {
      const isQ = cur === 'questions';
      tabQuestions.classList.toggle('active', isQ);
      tabQuestions.setAttribute('aria-selected', isQ ? 'true' : 'false');
    }
    if (tabFocus) {
      const isFocus = cur === 'focus' || cur === 'all';
      tabFocus.classList.toggle('active', isFocus);
      tabFocus.setAttribute('aria-selected', isFocus ? 'true' : 'false');
    }
    if (tabTop) {
      const isTop = cur === 'top';
      tabTop.classList.toggle('active', isTop);
      tabTop.setAttribute('aria-selected', isTop ? 'true' : 'false');
    }
    if (tabNew) {
      const isNew = cur === 'new';
      tabNew.classList.toggle('active', isNew);
      tabNew.setAttribute('aria-selected', isNew ? 'true' : 'false');
    }
    if (tabSubs) {
      const isSubs = cur === 'subscriptions' || cur === 'my';
      tabSubs.classList.toggle('active', isSubs);
      tabSubs.setAttribute('aria-selected', isSubs ? 'true' : 'false');
    }
    if (tabClubs) {
      const isClubs = cur === 'clubs';
      tabClubs.classList.toggle('active', isClubs);
      tabClubs.setAttribute('aria-selected', isClubs ? 'true' : 'false');
    }
    if (tabCompanies) {
      const isComp = cur === 'companies';
      tabCompanies.classList.toggle('active', isComp);
      tabCompanies.setAttribute('aria-selected', isComp ? 'true' : 'false');
    }
    if (tabDirections) {
      const isDir = cur === 'directions';
      tabDirections.classList.toggle('active', isDir);
      tabDirections.setAttribute('aria-selected', isDir ? 'true' : 'false');
    }
    if (tabMy) {
      const isMy = cur === 'subscriptions' || cur === 'my';
      tabMy.classList.toggle('active', isMy);
      tabMy.setAttribute('aria-selected', isMy ? 'true' : 'false');
    }
    if (tabSaved) {
      const isSaved = cur === 'saved';
      tabSaved.classList.toggle('active', isSaved);
      tabSaved.setAttribute('aria-selected', isSaved ? 'true' : 'false');
    }

    // Saved Hub & Questions Pills Bar in Stream Toolbar
    const savedHubPills = document.getElementById('feedSavedHubPills');
    if (savedHubPills) {
      savedHubPills.style.display = (cur === 'saved') ? 'inline-flex' : 'none';
      const pills = savedHubPills.querySelectorAll('.feed-saved-pill');
      pills.forEach(function (pill) {
        const pType = pill.getAttribute('data-saved-type') || pill.getAttribute('data-type');
        const isAct = pType === (state.savedType || 'all');
        pill.classList.toggle('active', isAct);
        pill.setAttribute('aria-checked', isAct ? 'true' : 'false');
      });
    }

    const qStatusPills = document.getElementById('feedQuestionsStatusPills');
    if (qStatusPills) {
      qStatusPills.style.display = (cur === 'questions') ? 'inline-flex' : 'none';
    }

    const filtersBtn = document.getElementById('btnFeedFiltersToggle');
    if (filtersBtn) {
      filtersBtn.style.display = (cur === 'saved') ? 'none' : 'inline-flex';
    }

    const searchInput = document.getElementById('feedSearchInput');
    if (searchInput) {
      if (cur === 'saved') {
        searchInput.placeholder = 'Поиск в сохраненном...';
      } else if (cur === 'questions') {
        searchInput.placeholder = 'Поиск по вопросам...';
      } else {
        searchInput.placeholder = 'Поиск публикаций';
      }
    }

    // Top Period Bar
    const periodBar = document.getElementById('feedTopPeriodBar');
    if (periodBar) {
      periodBar.style.display = (cur === 'top') ? 'block' : 'none';
      const periodPills = periodBar.querySelectorAll('.feed-period-pill');
      periodPills.forEach(function (pill) {
        pill.classList.toggle('active', pill.getAttribute('data-period') === state.topPeriod);
      });
    }

    // View toggling in main column
    const articlesView = document.getElementById('feedArticlesView');
    const clubsView = document.getElementById('clubsView');
    const clubDetailView = document.getElementById('clubDetailView');
    const companiesView = document.getElementById('companiesView');
    const companyDetailView = document.getElementById('companyDetailView');
    const directionsView = document.getElementById('directionsView');

    if (cur === 'clubs') {
      if (articlesView) articlesView.style.display = 'none';
      if (companiesView) companiesView.style.display = 'none';
      if (companyDetailView) companyDetailView.style.display = 'none';
      if (directionsView) directionsView.style.display = 'none';
      if (state.activeClubId) {
        if (clubsView) clubsView.style.display = 'none';
        if (clubDetailView) clubDetailView.style.display = 'flex';
      } else {
        if (clubsView) clubsView.style.display = 'flex';
        if (clubDetailView) clubDetailView.style.display = 'none';
      }
    } else if (cur === 'companies') {
      if (articlesView) articlesView.style.display = 'none';
      if (clubsView) clubsView.style.display = 'none';
      if (clubDetailView) clubDetailView.style.display = 'none';
      if (directionsView) directionsView.style.display = 'none';
      if (state.activeCompanyId) {
        if (companiesView) companiesView.style.display = 'none';
        if (companyDetailView) companyDetailView.style.display = 'flex';
      } else {
        if (companiesView) companiesView.style.display = 'flex';
        if (companyDetailView) companyDetailView.style.display = 'none';
      }
    } else if (cur === 'directions') {
      if (articlesView) articlesView.style.display = 'none';
      if (clubsView) clubsView.style.display = 'none';
      if (clubDetailView) clubDetailView.style.display = 'none';
      if (companiesView) companiesView.style.display = 'none';
      if (companyDetailView) companyDetailView.style.display = 'none';
      if (directionsView) directionsView.style.display = 'flex';
    } else {
      if (articlesView) articlesView.style.display = 'block';
      if (clubsView) clubsView.style.display = 'none';
      if (clubDetailView) clubDetailView.style.display = 'none';
      if (companiesView) companiesView.style.display = 'none';
      if (companyDetailView) companyDetailView.style.display = 'none';
      if (directionsView) directionsView.style.display = 'none';
    }

    updateFeedTitleUI();
  }

  function loadFeedSettings(callback) {
    Promise.all([
      fetch('/api/user/feed-settings').then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }),
      fetch('/api/subscriptions').then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }),
      fetch('/api/exceptions').then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
    ]).then(function (results) {
      const settingsData = results[0];
      const subsDataRes = results[1];
      const excDataRes = results[2];

      if (settingsData && settingsData.success) {
        const s = settingsData.settings || settingsData;
        if (Array.isArray(s.materialTypes) && s.materialTypes.length > 0) {
          savedSettingsState.materialTypes = s.materialTypes.slice();
        }
        if (Array.isArray(s.complexityLevels) && s.complexityLevels.length > 0) {
          savedSettingsState.complexityLevels = s.complexityLevels.slice();
        }
        if (s.welcomeDismissed) {
          try {
            localStorage.setItem('sc_welcome_dismissed', '1');
            const wb = document.getElementById('feedWelcomeBanner');
            if (wb) wb.style.display = 'none';
          } catch (e) {}
        }
      }

      if (subsDataRes && subsDataRes.success && subsDataRes.subscriptions) {
        savedSettingsState.subscriptions = {
          authors: Array.isArray(subsDataRes.subscriptions.authors) ? subsDataRes.subscriptions.authors.map(cloneItem) : [],
          topics: Array.isArray(subsDataRes.subscriptions.topics) ? subsDataRes.subscriptions.topics.map(cloneItem) : [],
          tags: Array.isArray(subsDataRes.subscriptions.tags) ? subsDataRes.subscriptions.tags.map(cloneItem) : []
        };
      }

      if (excDataRes && excDataRes.success && excDataRes.exceptions) {
        savedSettingsState.exceptions = {
          authors: Array.isArray(excDataRes.exceptions.authors) ? excDataRes.exceptions.authors.map(cloneItem) : [],
          topics: Array.isArray(excDataRes.exceptions.topics) ? excDataRes.exceptions.topics.map(cloneItem) : [],
          tags: Array.isArray(excDataRes.exceptions.tags) ? excDataRes.exceptions.tags.map(cloneItem) : []
        };
      }

      draftSettingsState = cloneSettings(savedSettingsState);
      state.feedSettings.materialTypes = savedSettingsState.materialTypes.slice();
      state.feedSettings.complexityLevels = savedSettingsState.complexityLevels.slice();
      state.userSubscriptions = cloneSettings(savedSettingsState.subscriptions);
      state.userExceptions = cloneSettings(savedSettingsState.exceptions);

      syncSettingsUIFromDraft();
      if (callback) callback();
    }).catch(function () {
      if (callback) callback();
    });
  }

  function toggleItemInDraft(type, item) {
    if (!item || !item.id) return;
    const cat = type + 's';
    const itemId = String(item.id);
    const itemTitle = item.title || itemId;

    const subsList = draftSettingsState.subscriptions[cat] || [];
    const excList = draftSettingsState.exceptions[cat] || [];

    const subIdx = subsList.findIndex(function (x) { return String(x.id || x) === itemId; });
    const excIdx = excList.findIndex(function (x) { return String(x.id || x) === itemId; });

    if (activeSubsMode === 'subscriptions') {
      if (excIdx !== -1) {
        excList.splice(excIdx, 1);
        if (subIdx === -1) {
          subsList.push(cloneItem(item));
        }
        showToast('«' + itemTitle + '» удален из исключений и добавлен в подписки');
      } else if (subIdx !== -1) {
        subsList.splice(subIdx, 1);
        showToast('Вы отписались от «' + itemTitle + '»');
      } else {
        subsList.push(cloneItem(item));
        showToast('Вы подписались на «' + itemTitle + '»');
      }
    } else {
      if (subIdx !== -1) {
        subsList.splice(subIdx, 1);
        if (excIdx === -1) {
          excList.push(cloneItem(item));
        }
        showToast('«' + itemTitle + '» удален из подписок и добавлен в исключения');
      } else if (excIdx !== -1) {
        excList.splice(excIdx, 1);
        showToast('Исключение снято с «' + itemTitle + '»');
      } else {
        excList.push(cloneItem(item));
        showToast('«' + itemTitle + '» добавлено в исключения');
      }
    }

    updateSettingsDraftUI();
  }

  function renderFeedSettingsSubsList() {
    const container = document.getElementById('feedUserSubsList') || document.getElementById('feedSettingsSubsList');
    if (!container) return;
    container.innerHTML = '';

    const cat = activeSettingsSubsType + 's';
    const store = draftSettingsState[activeSubsMode] || {};
    const items = store[cat] || [];

    if (items.length === 0) {
      let emptyTitle = '';
      let emptyBtnText = '';
      if (activeSubsMode === 'subscriptions') {
        if (activeSettingsSubsType === 'author') {
          emptyTitle = 'Вы пока не подписаны на авторов';
          emptyBtnText = 'Найти авторов';
        } else if (activeSettingsSubsType === 'topic') {
          emptyTitle = 'Вы пока не подписаны на темы';
          emptyBtnText = 'Выбрать темы';
        } else {
          emptyTitle = 'Вы пока не подписаны на хэштеги';
          emptyBtnText = 'Найти хэштеги';
        }
      } else {
        if (activeSettingsSubsType === 'author') {
          emptyTitle = 'У вас нет исключённых авторов';
          emptyBtnText = 'Исключить автора';
        } else if (activeSettingsSubsType === 'topic') {
          emptyTitle = 'У вас нет исключённых тем';
          emptyBtnText = 'Исключить тему';
        } else {
          emptyTitle = 'У вас нет исключённых хэштегов';
          emptyBtnText = 'Исключить хэштег';
        }
      }

      const emptyWrap = document.createElement('div');
      emptyWrap.className = 'feed-subs-empty-state';
      emptyWrap.innerHTML =
        '<div class="feed-subs-empty-icon">' +
          (activeSubsMode === 'subscriptions'
            ? '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><line x1="20" y1="8" x2="20" y2="14"></line><line x1="23" y1="11" x2="17" y2="11"></line></svg>'
            : '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg>') +
        '</div>' +
        '<div class="feed-subs-empty-title">' + escapeHtml(emptyTitle) + '</div>' +
        '<p class="feed-subs-empty-desc">' +
          (activeSubsMode === 'subscriptions'
            ? 'Добавьте элементы, чтобы сформировать свою персональную ленту.'
            : 'Публикации с исключёнными элементами скрываются из общей и персональной ленты.') +
        '</p>' +
        '<button type="button" class="btn btn-secondary btn-sm feed-subs-empty-btn" id="btnEmptyStateOpenCatalog">' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>' +
          '<span>' + escapeHtml(emptyBtnText) + '</span>' +
        '</button>';

      emptyWrap.querySelector('#btnEmptyStateOpenCatalog').addEventListener('click', function () {
        openCatalogPane();
      });

      container.appendChild(emptyWrap);
      return;
    }

    items.forEach(function (item) {
      const el = document.createElement('div');
      el.className = 'subs-item' +
        (activeSettingsSubsType === 'author' ? ' subs-item--author' : '') +
        (activeSubsMode === 'exceptions' ? ' is-exception-item' : '');

      let subText = item.role || item.description || '';
      if (!subText && item.count !== undefined) {
        subText = pluralizePublications(item.count);
      }
      const displayTitle = (activeSettingsSubsType === 'tag' ? '#' : '') + item.title;

      const btnLabel = (activeSubsMode === 'subscriptions') ? 'Отписаться' : 'Убрать исключение';
      const btnClass = (activeSubsMode === 'subscriptions') ? 'is-subscribed' : 'is-excluded';

      if (activeSettingsSubsType === 'author') {
        let avatarEl = null;
        if (window.SmartContractumCard && typeof window.SmartContractumCard.createAvatarEl === 'function') {
          avatarEl = window.SmartContractumCard.createAvatarEl(item, { className: 'subs-author-avatar' });
        } else {
          avatarEl = document.createElement('div');
          avatarEl.className = 'author-avatar subs-author-avatar';
          const initials = (item.title || 'АП').split(/\s+/).map(function (p) { return p[0]; }).filter(Boolean).slice(0, 2).join('').toUpperCase() || 'АП';
          avatarEl.textContent = initials;
        }

        const mainWrap = document.createElement('div');
        mainWrap.className = 'subs-item-main';
        mainWrap.appendChild(avatarEl);

        const infoWrap = document.createElement('div');
        infoWrap.className = 'subs-item-info';
        infoWrap.innerHTML =
          '<span class="subs-item-title">' + escapeHtml(displayTitle) + '</span>' +
          (subText ? '<span class="subs-item-sub">' + escapeHtml(subText) + '</span>' : '');
        mainWrap.appendChild(infoWrap);

        el.appendChild(mainWrap);
      } else {
        const infoWrap = document.createElement('div');
        infoWrap.className = 'subs-item-info subs-item-info--compact';
        infoWrap.innerHTML =
          '<span class="subs-item-title subs-item-title--wrap">' + escapeHtml(displayTitle) + '</span>' +
          (subText ? '<span class="subs-item-sub">' + escapeHtml(subText) + '</span>' : '');
        el.appendChild(infoWrap);
      }

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-secondary subs-toggle-btn ' + btnClass;
      btn.setAttribute('data-id', item.id);
      btn.textContent = btnLabel;
      btn.addEventListener('click', function () {
        toggleItemInDraft(activeSettingsSubsType, item);
      });
      el.appendChild(btn);

      container.appendChild(el);
    });
  }

  function openCatalogPane() {
    isCatalogOpen = true;
    const catPane = document.getElementById('feedCatalogPane');
    const userPane = document.getElementById('feedUserItemsPane');
    if (catPane) catPane.style.display = 'block';
    if (userPane) userPane.style.display = 'none';

    catalogOffset = 0;
    const searchInput = document.getElementById('feedSettingsSubsSearch');
    if (searchInput) {
      searchInput.value = '';
      if (activeSettingsSubsType === 'author') searchInput.placeholder = 'Найти автора...';
      else if (activeSettingsSubsType === 'topic') searchInput.placeholder = 'Найти тему...';
      else if (activeSettingsSubsType === 'tag') searchInput.placeholder = 'Найти хэштег...';
      setTimeout(function () { searchInput.focus(); }, 50);
    }

    fetchAndRenderCatalog(true);
  }

  function closeCatalogPane() {
    isCatalogOpen = false;
    const catPane = document.getElementById('feedCatalogPane');
    const userPane = document.getElementById('feedUserItemsPane');
    if (catPane) catPane.style.display = 'none';
    if (userPane) userPane.style.display = 'block';
    renderFeedSettingsSubsList();
  }

  function fetchAndRenderCatalog(isInitial) {
    if (isInitial) {
      catalogOffset = 0;
      catalogItems = [];
    }

    const searchInput = document.getElementById('feedSettingsSubsSearch');
    const q = (searchInput ? searchInput.value.trim() : '');
    const spinner = document.getElementById('feedCatalogSearchSpinner');
    const footer = document.getElementById('feedCatalogFooter');
    const currentSeq = ++catalogRequestSeq;

    if (spinner) spinner.style.display = 'inline-block';

    // Topics: displayed completely from PublicationConfig
    if (activeSettingsSubsType === 'topic') {
      if (spinner) spinner.style.display = 'none';
      let allTopics = (window.PublicationConfig && Array.isArray(window.PublicationConfig.TOPICS))
        ? window.PublicationConfig.TOPICS
        : [];
      if (q) {
        const queryLower = q.toLowerCase();
        allTopics = allTopics.filter(function (t) {
          return (t.title && t.title.toLowerCase().indexOf(queryLower) !== -1) ||
                 (t.description && t.description.toLowerCase().indexOf(queryLower) !== -1) ||
                 (t.id && t.id.toLowerCase().indexOf(queryLower) !== -1);
        });
      }
      catalogItems = allTopics.map(function (t) {
        return {
          id: t.id,
          title: t.title,
          description: t.description || ''
        };
      });
      catalogHasMore = false;
      if (footer) footer.style.display = 'none';
      renderFeedSettingsCatalogList();
      return;
    }

    // Authors and Tags: fetch with 20-item chunk pagination
    const params = new URLSearchParams();
    params.set('type', activeSettingsSubsType);
    params.set('limit', String(CATALOG_LIMIT));
    params.set('offset', String(catalogOffset));
    if (q) params.set('search', q);

    fetch('/api/subscriptions/entities?' + params.toString())
      .then(function (res) {
        if (!res.ok) throw new Error('Failed to fetch entities');
        return res.json();
      })
      .then(function (data) {
        if (currentSeq !== catalogRequestSeq) return;
        if (spinner) spinner.style.display = 'none';

        if (data && data.success) {
          const items = data.items || [];
          if (isInitial) {
            catalogItems = items;
          } else {
            const existingIds = new Set(catalogItems.map(function (it) { return it.id; }));
            items.forEach(function (it) {
              if (!existingIds.has(it.id)) catalogItems.push(it);
            });
          }
          catalogHasMore = Boolean(data.hasMore);
          if (footer) footer.style.display = catalogHasMore ? 'flex' : 'none';
          renderFeedSettingsCatalogList();
        } else {
          fallbackCatalog(isInitial, q);
        }
      })
      .catch(function () {
        if (currentSeq !== catalogRequestSeq) return;
        if (spinner) spinner.style.display = 'none';
        fallbackCatalog(isInitial, q);
      });
  }

  function fallbackCatalog(isInitial, query) {
    const footer = document.getElementById('feedCatalogFooter');
    let fallbackPool = [];
    if (activeSettingsSubsType === 'author') {
      fallbackPool = [
        { id: 'alexey-smirnov', title: 'Алексей Смирнов', role: 'Архитектор решений', count: 8 },
        { id: 'ekaterina-romanova', title: 'Екатерина Романова', role: 'Ведущий аудитор безопасности', count: 12 },
        { id: 'ilya-melnikov', title: 'Илья Мельников', role: 'Советник по правовым вопросам ЦФА', count: 6 },
        { id: 'viktor-nesterov', title: 'Виктор Нестеров', role: 'Инженер распределенных систем', count: 10 },
        { id: 'dmitry-kuznetsov', title: 'Дмитрий Кузнецов', role: 'Tech Lead Blockchain Core', count: 5 },
        { id: 'anna-orlova', title: 'Анна Орлова', role: 'Руководитель комплаенс практики', count: 4 }
      ];
    } else if (activeSettingsSubsType === 'tag') {
      fallbackPool = [
        { id: 'смарт-контракты', title: 'смарт-контракты', count: 15 },
        { id: 'цифровой-рубль', title: 'цифровой-рубль', count: 12 },
        { id: 'безопасность', title: 'безопасность', count: 10 },
        { id: 'аудит', title: 'аудит', count: 8 },
        { id: 'цфа', title: 'цфа', count: 7 },
        { id: 'пкск', title: 'пкск', count: 6 },
        { id: 'оракулы', title: 'оракулы', count: 5 },
        { id: 'комплаенс', title: 'комплаенс', count: 5 },
        { id: 'reentrancy', title: 'reentrancy', count: 4 },
        { id: 'solidity', title: 'solidity', count: 4 }
      ];
    }

    if (query) {
      const qLower = query.toLowerCase();
      fallbackPool = fallbackPool.filter(function (it) {
        return (it.title && it.title.toLowerCase().indexOf(qLower) !== -1) ||
               (it.role && it.role.toLowerCase().indexOf(qLower) !== -1);
      });
    }

    catalogItems = fallbackPool;
    catalogHasMore = false;
    if (footer) footer.style.display = 'none';
    renderFeedSettingsCatalogList();
  }

  function renderFeedSettingsCatalogList() {
    const container = document.getElementById('feedSettingsCatalogList');
    if (!container) return;
    container.innerHTML = '';

    if (catalogItems.length === 0) {
      container.innerHTML =
        '<div style="text-align: center; padding: 32px 16px; color: var(--text-muted); font-size: 0.9rem;">' +
          'Ничего не найдено по вашему запросу' +
        '</div>';
      return;
    }

    const cat = activeSettingsSubsType + 's';
    const currentSubs = (draftSettingsState.subscriptions[cat] || []).map(function (x) { return String(x.id || x); });
    const currentExc = (draftSettingsState.exceptions[cat] || []).map(function (x) { return String(x.id || x); });

    catalogItems.forEach(function (item) {
      const itemId = String(item.id);
      const isSub = currentSubs.indexOf(itemId) !== -1;
      const isExc = currentExc.indexOf(itemId) !== -1;

      const el = document.createElement('div');
      el.className = 'subs-item';

      let subText = item.role || item.description || '';
      if (!subText && item.count !== undefined) {
        subText = pluralizePublications(item.count);
      }
      const displayTitle = (activeSettingsSubsType === 'tag' ? '#' : '') + item.title;

      let btnLabel = '';
      let btnClass = '';
      let btnTitle = '';

      if (activeSubsMode === 'subscriptions') {
        if (isSub) {
          btnLabel = 'Вы подписаны';
          btnClass = 'is-subscribed';
        } else if (isExc) {
          btnLabel = 'В исключениях';
          btnClass = 'is-conflict';
          btnTitle = 'Нажмите, чтобы перенести в подписки';
        } else {
          btnLabel = 'Подписаться';
          btnClass = '';
        }
      } else {
        if (isExc) {
          btnLabel = 'Исключено';
          btnClass = 'is-excluded';
        } else if (isSub) {
          btnLabel = 'В подписках';
          btnClass = 'is-conflict';
          btnTitle = 'Нажмите, чтобы перенести в исключения';
        } else {
          btnLabel = 'Не показывать';
          btnClass = '';
        }
      }

      if (activeSettingsSubsType === 'author') {
        let avatarEl = null;
        if (window.SmartContractumCard && typeof window.SmartContractumCard.createAvatarEl === 'function') {
          avatarEl = window.SmartContractumCard.createAvatarEl(item, { className: 'subs-author-avatar' });
        } else {
          avatarEl = document.createElement('div');
          avatarEl.className = 'author-avatar subs-author-avatar';
          const initials = (item.title || 'АП').split(/\s+/).map(function (p) { return p[0]; }).filter(Boolean).slice(0, 2).join('').toUpperCase() || 'АП';
          avatarEl.textContent = initials;
        }

        const mainWrap = document.createElement('div');
        mainWrap.className = 'subs-item-main';
        mainWrap.appendChild(avatarEl);

        const infoWrap = document.createElement('div');
        infoWrap.className = 'subs-item-info';
        infoWrap.innerHTML =
          '<span class="subs-item-title">' + escapeHtml(displayTitle) + '</span>' +
          (subText ? '<span class="subs-item-sub">' + escapeHtml(subText) + '</span>' : '');
        mainWrap.appendChild(infoWrap);

        el.appendChild(mainWrap);
      } else {
        const infoWrap = document.createElement('div');
        infoWrap.className = 'subs-item-info subs-item-info--compact';
        infoWrap.innerHTML =
          '<span class="subs-item-title subs-item-title--wrap">' + escapeHtml(displayTitle) + '</span>' +
          (subText ? '<span class="subs-item-sub">' + escapeHtml(subText) + '</span>' : '');
        el.appendChild(infoWrap);
      }

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-secondary subs-toggle-btn ' + btnClass;
      btn.setAttribute('data-id', itemId);
      if (btnTitle) btn.title = btnTitle;
      btn.textContent = btnLabel;
      btn.addEventListener('click', function () {
        toggleItemInDraft(activeSettingsSubsType, item);
      });
      el.appendChild(btn);

      container.appendChild(el);
    });
  }

  function initFeedSettingsPanel() {
    const closeBtn = document.getElementById('btnCloseFeedSettings');
    const cancelBtn = document.getElementById('btnCancelFeedSettings');
    const saveBtn = document.getElementById('btnSaveFeedSettings');

    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        closeFeedSettingsPanel(false);
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener('click', function () {
        closeFeedSettingsPanel(false);
      });
    }

    // Material type tumblers
    const typeInputs = document.querySelectorAll('input[name="feedMaterialType"]');
    typeInputs.forEach(function (inp) {
      inp.addEventListener('change', function () {
        const checkedVals = Array.from(document.querySelectorAll('input[name="feedMaterialType"]:checked')).map(function (i) {
          return i.value;
        });
        draftSettingsState.materialTypes = checkedVals;
        validateMaterialTypes();
        updateSettingsDraftUI();
      });
    });

    // Complexity tumblers
    const compInputs = document.querySelectorAll('input[name="feedComplexityLevel"]');
    compInputs.forEach(function (inp) {
      inp.addEventListener('change', function () {
        handleComplexityTumblerChange(compInputs, inp, function () {
          const allInp = Array.from(compInputs).find(function (i) {
            const val = i.value || i.getAttribute('data-complexity');
            return val === 'all';
          });
          if (allInp && allInp.checked) {
            draftSettingsState.complexityLevels = ['all'];
          } else {
            draftSettingsState.complexityLevels = Array.from(compInputs)
              .filter(function (i) {
                const val = i.value || i.getAttribute('data-complexity');
                return val !== 'all' && i.checked;
              })
              .map(function (i) { return i.value || i.getAttribute('data-complexity'); });
            if (draftSettingsState.complexityLevels.length === 0) {
              draftSettingsState.complexityLevels = ['all'];
              if (allInp) allInp.checked = true;
            }
          }
          updateSettingsDraftUI();
        });
      });
    });

    // Save button
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        if (!validateMaterialTypes()) return;

        const payload = {
          materialTypes: draftSettingsState.materialTypes,
          complexityLevels: draftSettingsState.complexityLevels
        };

        if (currentUser) {
          saveBtn.disabled = true;
          fetch('/api/user/feed-settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          })
            .then(function (res) { return res.json(); })
            .then(function (data) {
              saveBtn.disabled = false;
              if (data && data.success) {
                savedSettingsState.materialTypes = draftSettingsState.materialTypes.slice();
                savedSettingsState.complexityLevels = draftSettingsState.complexityLevels.slice();
                state.feedSettings.materialTypes = savedSettingsState.materialTypes.slice();
                state.feedSettings.complexityLevels = savedSettingsState.complexityLevels.slice();

                closeFeedSettingsPanel(true);
                if (state.tab === 'all') {
                  showToast('Настройки сохранены', 'Открыть мою ленту', function () {
                    switchTab('my');
                  });
                } else {
                  showToast('Настройки ленты сохранены');
                }
                syncURL(false);
                fetchFeed(true);
              } else {
                showToast(data.error || 'Не удалось сохранить настройки');
              }
            })
            .catch(function (err) {
              saveBtn.disabled = false;
              console.error('Failed to save settings:', err);
              showToast('Ошибка при сохранении настроек');
            });
        } else {
          // Guest mode: save locally in session
          savedSettingsState.materialTypes = draftSettingsState.materialTypes.slice();
          savedSettingsState.complexityLevels = draftSettingsState.complexityLevels.slice();
          state.feedSettings.materialTypes = savedSettingsState.materialTypes.slice();
          state.feedSettings.complexityLevels = savedSettingsState.complexityLevels.slice();

          try {
            localStorage.setItem('sc_guest_feed_settings', JSON.stringify(savedSettingsState));
          } catch (e) {}

          closeFeedSettingsPanel(true);
          if (state.tab === 'all') {
            showToast('Настройки сохранены', 'Открыть мою ленту', function () {
              switchTab('my');
            });
          } else {
            showToast('Настройки сохранены для текущей сессии');
          }
          syncURL(false);
          fetchFeed(true);
        }
      });
    }
  }

  // --------------------------------------------------------------------------
  // 6. UI Controls Initialization
  // --------------------------------------------------------------------------
  function initControls() {
    // Populate Audience select from PublicationConfig
    const audienceSelect = document.getElementById('feedAudienceSelect');
    if (audienceSelect && window.PublicationConfig && Array.isArray(window.PublicationConfig.AUDIENCES)) {
      audienceSelect.innerHTML = '<option value="all">Любая аудитория</option>';
      window.PublicationConfig.AUDIENCES.forEach(function (aud) {
        const opt = document.createElement('option');
        opt.value = aud.id;
        opt.textContent = aud.title;
        audienceSelect.appendChild(opt);
      });
      if (state.filters.audience) audienceSelect.value = state.filters.audience;
    }

    // Populate Format select from PublicationConfig
    const formatSelect = document.getElementById('feedFormatSelect');
    if (formatSelect && window.PublicationConfig && Array.isArray(window.PublicationConfig.FORMATS)) {
      formatSelect.innerHTML = '<option value="all">Любой формат</option>';
      window.PublicationConfig.FORMATS.forEach(function (fmt) {
        const opt = document.createElement('option');
        opt.value = fmt.id;
        opt.textContent = fmt.title;
        formatSelect.appendChild(opt);
      });
      if (state.filters.format) formatSelect.value = state.filters.format;
    }

    // Search input, clear button, expandable group & submit button
    const searchInput = document.getElementById('feedSearchInput');
    const clearBtn = document.getElementById('feedSearchClearBtn');
    const searchGroup = document.getElementById('feedSearchGroup');
    const searchSubmitBtn = document.getElementById('btnFeedSearchSubmit');

    let debounceTimer = null;

    function triggerSearch(val) {
      clearTimeout(debounceTimer);
      state.search = (val !== undefined ? val : (searchInput ? searchInput.value.trim() : ''));
      state.offset = 0;
      syncURL(false);
      fetchFeed(true);
    }

    if (searchGroup && searchInput) {
      searchInput.addEventListener('focus', function () {
        searchGroup.classList.add('is-expanded');
        searchInput.placeholder = 'По статьям, авторам, тегам...';
      });
      searchInput.addEventListener('blur', function () {
        if (!searchInput.value.trim()) {
          searchGroup.classList.remove('is-expanded');
          searchInput.placeholder = 'Поиск публикаций';
        }
      });
      if (searchInput.value.trim()) {
        searchGroup.classList.add('is-expanded');
      }
    }

    if (searchSubmitBtn && searchInput) {
      searchSubmitBtn.addEventListener('mousedown', function (e) {
        e.preventDefault();
      });

      searchSubmitBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (searchGroup && !searchGroup.classList.contains('is-expanded')) {
          searchGroup.classList.add('is-expanded');
          searchInput.focus();
          return;
        }
        triggerSearch(searchInput.value.trim());
      });
    }

    if (searchInput) {
      searchInput.addEventListener('input', function () {
        const val = searchInput.value.trim();
        if (clearBtn) {
          clearBtn.style.display = searchInput.value ? 'inline-flex' : 'none';
        }
        if (searchGroup) {
          if (val) searchGroup.classList.add('is-expanded');
        }
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () {
          if (state.search !== val) {
            triggerSearch(val);
          }
        }, 350);
      });

      searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          triggerSearch(searchInput.value.trim());
        }
      });
    }

    if (clearBtn && searchInput) {
      clearBtn.addEventListener('click', function () {
        searchInput.value = '';
        clearBtn.style.display = 'none';
        if (searchGroup) {
          searchGroup.classList.remove('is-expanded');
          searchInput.placeholder = 'Поиск публикаций';
        }
        triggerSearch('');
        searchInput.focus();
      });
    }

    // Direct toolbar Sorters
    const periodSelect = document.getElementById('feedPeriodSelect');
    if (periodSelect) {
      periodSelect.addEventListener('change', function () {
        state.filters.period = periodSelect.value;
        state.period = periodSelect.value;
        state.offset = 0;
        syncURL(false);
        fetchFeed(true);
      });
    }

    const sortSelect = document.getElementById('feedSortSelect');
    if (sortSelect) {
      sortSelect.addEventListener('change', function () {
        state.sort = sortSelect.value;
        state.offset = 0;
        updateSortUI(sortSelect.value);
        updatePeriodVisibility();
        syncURL(false);
        fetchFeed(true);
      });
    }

    initCustomSortDropdown();

    // Reset All Filters button on chips bar
    const resetAllBtn = document.getElementById('feedResetAllBtn');
    if (resetAllBtn) {
      resetAllBtn.addEventListener('click', resetAllFilters);
    }

    // Load More pagination button
    const loadMoreBtn = document.getElementById('feedLoadMoreBtn');
    if (loadMoreBtn) {
      loadMoreBtn.addEventListener('click', function () {
        state.offset += state.limit;
        fetchFeed(false);
      });
    }
  }

  function initCustomSortDropdown() {
    const trigger = document.getElementById('feedSortCustomTrigger');
    const menu = document.getElementById('feedSortCustomMenu');
    const select = document.getElementById('feedSortSelect');
    if (!trigger || !menu) return;

    function openMenu() {
      menu.style.display = 'flex';
      trigger.setAttribute('aria-expanded', 'true');
      const activeOption = menu.querySelector('.feed-sort-option.active') || menu.querySelector('.feed-sort-option');
      if (activeOption) {
        activeOption.focus();
      }
    }

    function closeMenu(focusTrigger) {
      menu.style.display = 'none';
      trigger.setAttribute('aria-expanded', 'false');
      if (focusTrigger) {
        trigger.focus();
      }
    }

    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      const isOpen = trigger.getAttribute('aria-expanded') === 'true';
      if (isOpen) {
        closeMenu(false);
      } else {
        openMenu();
      }
    });

    trigger.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openMenu();
      }
    });

    const options = Array.from(menu.querySelectorAll('.feed-sort-option'));

    options.forEach(function (opt, idx) {
      opt.addEventListener('click', function (e) {
        e.stopPropagation();
        const val = opt.getAttribute('data-value');
        if (val) {
          state.sort = val;
          state.offset = 0;
          if (select) {
            select.value = val;
          }
          updateSortUI(val);
          updatePeriodVisibility();
          closeMenu(true);
          syncURL(false);
          fetchFeed(true);
        }
      });

      opt.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          opt.click();
        } else if (e.key === 'ArrowDown') {
          e.preventDefault();
          const next = options[(idx + 1) % options.length];
          if (next) next.focus();
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          const prev = options[(idx - 1 + options.length) % options.length];
          if (prev) prev.focus();
        } else if (e.key === 'Home') {
          e.preventDefault();
          options[0].focus();
        } else if (e.key === 'End') {
          e.preventDefault();
          options[options.length - 1].focus();
        } else if (e.key === 'Escape' || e.key === 'Tab') {
          e.preventDefault();
          closeMenu(false);
          trigger.focus();
        }
      });
    });

    document.addEventListener('click', function (e) {
      if (!trigger.contains(e.target) && !menu.contains(e.target)) {
        closeMenu(false);
      }
    });
  }

  // --------------------------------------------------------------------------
  // 7. Slide-Out Feed Filters Panel (#feedFiltersPanel)
  // --------------------------------------------------------------------------
  let filtersDraftState = null;

  function initFiltersDraftState() {
    if (!filtersDraftState) {
      filtersDraftState = {
        types: (state.filters.types || []).slice(),
        complexities: (state.filters.complexities || []).slice(),
        topics: (state.filters.topics || []).slice(),
        period: state.filters.period || 'all',
        dateFrom: state.filters.dateFrom || '',
        dateTo: state.filters.dateTo || '',
        formats: (state.filters.formats && state.filters.formats.length > 0)
          ? state.filters.formats.slice()
          : (state.filters.format && state.filters.format !== 'all' ? [state.filters.format] : []),
        audiences: (state.filters.audiences && state.filters.audiences.length > 0)
          ? state.filters.audiences.slice()
          : (state.filters.audience && state.filters.audience !== 'all' ? [state.filters.audience] : [])
      };
    }
    return filtersDraftState;
  }

  function getAppliedFiltersSnapshot() {
    return JSON.stringify({
      types: (state.filters.types || []).slice().sort(),
      complexities: (state.filters.complexities || []).slice().sort(),
      topics: (state.filters.topics || []).slice().sort(),
      period: state.filters.period || 'all',
      dateFrom: (state.filters.period === 'custom') ? (state.filters.dateFrom || '') : '',
      dateTo: (state.filters.period === 'custom') ? (state.filters.dateTo || '') : '',
      formats: ((state.filters.formats && state.filters.formats.length > 0)
        ? state.filters.formats
        : (state.filters.format && state.filters.format !== 'all' ? [state.filters.format] : [])).slice().sort(),
      audiences: ((state.filters.audiences && state.filters.audiences.length > 0)
        ? state.filters.audiences
        : (state.filters.audience && state.filters.audience !== 'all' ? [state.filters.audience] : [])).slice().sort()
    });
  }

  function getCurrentPanelFiltersSnapshot() {
    const draft = initFiltersDraftState();
    return JSON.stringify({
      types: (draft.types || []).slice().sort(),
      complexities: (draft.complexities || []).slice().sort(),
      topics: (draft.topics || []).slice().sort(),
      period: draft.period || 'all',
      dateFrom: (draft.period === 'custom') ? (draft.dateFrom || '') : '',
      dateTo: (draft.period === 'custom') ? (draft.dateTo || '') : '',
      formats: (draft.formats || []).slice().sort(),
      audiences: (draft.audiences || []).slice().sort()
    });
  }

  function checkFiltersPanelUnappliedChanges() {
    const indicator = document.getElementById('feedFiltersUnappliedIndicator');
    if (!indicator) return;
    const hasUnapplied = (getCurrentPanelFiltersSnapshot() !== getAppliedFiltersSnapshot());
    indicator.style.display = hasUnapplied ? 'inline-flex' : 'none';
  }

  function updateAdvancedFiltersUI() {
    const adv = document.getElementById('feedFiltersAdvanced');
    const badge = document.getElementById('feedAdvancedFiltersCountBadge');
    const draft = initFiltersDraftState();
    const formatsCount = (draft.formats && draft.formats.length > 0) ? draft.formats.length : 0;
    const audiencesCount = (draft.audiences && draft.audiences.length > 0) ? draft.audiences.length : 0;

    let count = 0;
    if (formatsCount > 0) count++;
    if (audiencesCount > 0) count++;

    if (badge) {
      if (count > 0) {
        badge.textContent = count;
        badge.style.display = 'inline-flex';
      } else {
        badge.style.display = 'none';
      }
    }

    if (adv) {
      adv.open = (count > 0);
    }
  }

  let activeDropdownMenu = null;
  let activeDropdownTrigger = null;

  function positionDropdownMenu(menu, trigger) {
    if (!menu || !trigger || menu.style.display === 'none') return;
    const rect = trigger.getBoundingClientRect();
    const panelBody = document.querySelector('#feedFiltersPanel .feed-slide-panel-body');
    if (panelBody) {
      const bodyRect = panelBody.getBoundingClientRect();
      if (rect.bottom < bodyRect.top || rect.top > bodyRect.bottom) {
        closeDropdownMenu(menu, trigger);
        return;
      }
    }

    const headerEl = document.getElementById('feedSubnavBar') || document.querySelector('.feed-slide-panel-header');
    const headerBottom = headerEl ? Math.max(0, headerEl.getBoundingClientRect().bottom) : 0;
    const panelFooter = document.querySelector('#feedFiltersPanel .feed-slide-panel-footer');
    const footerTop = panelFooter ? panelFooter.getBoundingClientRect().top : window.innerHeight;

    const spaceBelow = Math.max(0, footerTop - rect.bottom - 8);
    const spaceAbove = Math.max(0, rect.top - headerBottom - 8);

    menu.style.position = 'fixed';
    menu.style.left = Math.round(rect.left) + 'px';
    menu.style.width = Math.round(rect.width) + 'px';
    menu.style.zIndex = '1050';

    const estimatedHeight = 220;
    if (spaceBelow < estimatedHeight && spaceAbove > spaceBelow) {
      menu.classList.add('opens-up');
      menu.style.top = 'auto';
      menu.style.bottom = Math.round(window.innerHeight - rect.top + 4) + 'px';
      menu.style.maxHeight = Math.min(360, Math.floor(spaceAbove)) + 'px';
    } else {
      menu.classList.remove('opens-up');
      menu.style.bottom = 'auto';
      menu.style.top = Math.round(rect.bottom + 4) + 'px';
      menu.style.maxHeight = Math.min(360, Math.floor(spaceBelow)) + 'px';
    }
  }

  function openDropdownMenu(wrap, menu, trigger, searchInput) {
    closeAllFilterDropdowns(menu);
    menu.style.display = 'flex';
    if (trigger) trigger.setAttribute('aria-expanded', 'true');
    activeDropdownMenu = menu;
    activeDropdownTrigger = trigger;
    positionDropdownMenu(menu, trigger);

    if (searchInput) {
      setTimeout(function () { searchInput.focus(); }, 40);
    }
  }

  function closeDropdownMenu(menu, trigger) {
    if (!menu) return;
    menu.style.display = 'none';
    menu.classList.remove('opens-up');
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
    if (activeDropdownMenu === menu) {
      activeDropdownMenu = null;
      activeDropdownTrigger = null;
    }
  }

  function closeAllFilterDropdowns(exceptMenu) {
    const menus = [
      document.getElementById('feedTopicsDropdownMenu'),
      document.getElementById('feedFormatsDropdownMenu'),
      document.getElementById('feedAudiencesDropdownMenu'),
      document.getElementById('feedDateDropdownMenu')
    ];
    menus.forEach(function (m) {
      if (m && m !== exceptMenu && m.style.display !== 'none') {
        const wrap = m.closest('.feed-multiselect-dropdown-wrap, .feed-topics-dropdown-wrap, .feed-date-dropdown-wrap');
        const trig = wrap ? wrap.querySelector('.feed-multiselect-dropdown-trigger, .feed-topics-dropdown-trigger, .feed-date-dropdown-trigger') : null;
        closeDropdownMenu(m, trig);
      }
    });
  }

  function updateActiveDropdownPosition() {
    if (activeDropdownMenu && activeDropdownTrigger && activeDropdownMenu.style.display !== 'none') {
      positionDropdownMenu(activeDropdownMenu, activeDropdownTrigger);
    }
  }
  window.addEventListener('resize', updateActiveDropdownPosition);
  window.addEventListener('scroll', updateActiveDropdownPosition, { passive: true });
  document.addEventListener('DOMContentLoaded', function () {
    const filterPanelBody = document.querySelector('#feedFiltersPanel .feed-slide-panel-body');
    if (filterPanelBody) {
      filterPanelBody.addEventListener('scroll', updateActiveDropdownPosition, { passive: true });
    }
  });

  function setupGenericMultiselect(options) {
    const wrap = document.getElementById(options.wrapId);
    const trigger = document.getElementById(options.triggerId);
    const triggerText = document.getElementById(options.triggerTextId);
    const menu = document.getElementById(options.menuId);
    const searchInput = document.getElementById(options.searchInputId);
    const actionsBar = document.getElementById(options.actionsBarId);
    const clearBtn = document.getElementById(options.clearBtnId);
    const list = document.getElementById(options.listId);
    const chipsBar = document.getElementById(options.chipsBarId);

    if (!wrap || !trigger || !menu || !list) return null;

    // Toggle menu
    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      const isOpen = menu.style.display !== 'none';
      if (isOpen) {
        closeDropdownMenu(menu, trigger);
      } else {
        closeAllFilterDropdowns(menu);
        openDropdownMenu(wrap, menu, trigger, searchInput);
      }
    });

    // Close on click outside
    document.addEventListener('click', function (e) {
      if (!wrap.contains(e.target) && menu.style.display !== 'none') {
        closeDropdownMenu(menu, trigger);
      }
    });

    // Clear selection button
    if (clearBtn) {
      clearBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        options.onClear();
        updateUI();
        checkFiltersPanelUnappliedChanges();
      });
    }

    // Search filter
    if (searchInput) {
      searchInput.addEventListener('input', function () {
        const q = searchInput.value.trim().toLowerCase();
        const items = list.querySelectorAll('.' + options.itemClass);
        items.forEach(function (item) {
          const text = (item.textContent || '').toLowerCase();
          item.style.display = (!q || text.indexOf(q) !== -1) ? 'flex' : 'none';
        });
      });
    }

    // Keyboard navigation within the dropdown
    wrap.addEventListener('keydown', function (e) {
      if (menu.style.display === 'none') {
        if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          closeAllFilterDropdowns(menu);
          openDropdownMenu(wrap, menu, trigger, searchInput);
        }
        return;
      }

      if (e.key === 'Escape') {
        e.stopPropagation();
        closeDropdownMenu(menu, trigger);
        trigger.focus();
        return;
      }

      const focusable = Array.from(menu.querySelectorAll('input, button, label'));
      const activeIdx = focusable.indexOf(document.activeElement);

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        const nextIdx = (activeIdx + 1) % focusable.length;
        if (focusable[nextIdx]) focusable[nextIdx].focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prevIdx = (activeIdx - 1 + focusable.length) % focusable.length;
        if (focusable[prevIdx]) focusable[prevIdx].focus();
      }
    });

    // Populate list items once
    function renderListItems() {
      list.innerHTML = '';
      const items = options.getItems() || [];
      items.forEach(function (item) {
        const lbl = document.createElement('label');
        lbl.className = options.itemClass + ' feed-multiselect-checkbox-item';
        lbl.setAttribute('data-id', item.id);
        lbl.setAttribute('data-topic', item.id); // for backward compatibility in topic tests
        lbl.setAttribute('tabindex', '0');
        lbl.innerHTML =
          '<input type="checkbox" class="feed-multiselect-checkbox ' + options.checkboxClass + '" value="' + escapeHtml(item.id) + '">' +
          '<span class="feed-topic-checkbox-custom" aria-hidden="true"></span>' +
          '<span class="' + options.titleClass + ' feed-multiselect-checkbox-title">' + escapeHtml(item.title) + '</span>';

        // Keyboard toggle on label
        lbl.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            const chk = lbl.querySelector('input[type="checkbox"]');
            if (chk) {
              chk.checked = !chk.checked;
              chk.dispatchEvent(new Event('change', { bubbles: true }));
            }
          }
        });

        list.appendChild(lbl);
      });

      list.addEventListener('change', function (e) {
        const chk = e.target.closest('input[type="checkbox"]');
        if (!chk) return;
        const id = chk.value;
        options.onToggle(id, chk.checked);
        updateUI();
        checkFiltersPanelUnappliedChanges();
      });
    }

    // Update UI (checkboxes, trigger text, clear btn, chips)
    function updateUI() {
      const selectedIds = options.getSelected() || [];

      // Update checkboxes in menu
      list.querySelectorAll('.' + options.itemClass).forEach(function (lbl) {
        const id = lbl.getAttribute('data-id');
        const chk = lbl.querySelector('input[type="checkbox"]');
        const isSel = selectedIds.indexOf(id) !== -1;
        if (chk) chk.checked = isSel;
        lbl.classList.toggle('is-selected', isSel);
      });

      // Update trigger text
      if (triggerText) {
        if (selectedIds.length === 0) {
          triggerText.textContent = options.defaultText;
        } else if (selectedIds.length === 1) {
          const item = options.getItemById(selectedIds[0]);
          triggerText.textContent = item ? item.title : selectedIds[0];
        } else {
          triggerText.textContent = options.countPrefix + selectedIds.length;
        }
      }

      // Actions bar (clear button)
      if (actionsBar) {
        actionsBar.style.display = (selectedIds.length > 0) ? 'flex' : 'none';
      }

      // Render selected chips
      if (chipsBar) {
        chipsBar.innerHTML = '';
        if (selectedIds.length === 0) {
          chipsBar.style.display = 'none';
        } else {
          chipsBar.style.display = 'flex';
          selectedIds.forEach(function (id) {
            const item = options.getItemById(id);
            const title = item ? item.title : id;
            const chip = document.createElement('div');
            chip.className = 'filter-selected-chip';
            chip.innerHTML =
              '<span class="filter-selected-chip-title chip-name">' + escapeHtml(title) + '</span>' +
              '<button type="button" class="filter-selected-chip-remove chip-del-btn" aria-label="Удалить ' + escapeHtml(title) + '">' +
                '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
                  '<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>' +
                '</svg>' +
              '</button>';

            chip.querySelector('.filter-selected-chip-remove').addEventListener('click', function (e) {
              e.stopPropagation();
              options.onToggle(id, false);
              updateUI();
              checkFiltersPanelUnappliedChanges();
            });

            chipsBar.appendChild(chip);
          });
        }
      }
    }

    renderListItems();
    updateUI();

    return {
      updateUI: updateUI
    };
  }

  let topicsDropdownCtrl = null;
  let formatsDropdownCtrl = null;
  let audiencesDropdownCtrl = null;

  function initAllFilterDropdowns() {
    initFiltersDraftState();

    // 1. Topics
    topicsDropdownCtrl = setupGenericMultiselect({
      wrapId: 'feedTopicsDropdownWrap',
      triggerId: 'feedTopicsDropdownTrigger',
      triggerTextId: 'feedTopicsDropdownTriggerText',
      menuId: 'feedTopicsDropdownMenu',
      searchInputId: 'filterTopicSearchInput',
      actionsBarId: 'feedTopicsActionsBar',
      clearBtnId: 'btnTopicsClearSelection',
      listId: 'modalTopicsFilterBar',
      chipsBarId: 'filterSelectedTopicsChips',
      itemClass: 'feed-topic-checkbox-item',
      checkboxClass: 'feed-topic-checkbox',
      titleClass: 'feed-topic-title',
      defaultText: 'Все темы',
      countPrefix: 'Выбрано тем: ',
      getItems: function () {
        return (window.PublicationConfig && Array.isArray(window.PublicationConfig.TOPICS)) ? window.PublicationConfig.TOPICS : [];
      },
      getItemById: function (id) {
        return window.PublicationConfig ? window.PublicationConfig.getTopicById(id) : null;
      },
      getSelected: function () {
        const draft = initFiltersDraftState();
        return draft.topics || [];
      },
      onToggle: function (id, isChecked) {
        const draft = initFiltersDraftState();
        if (isChecked) {
          if (draft.topics.indexOf(id) === -1) draft.topics.push(id);
        } else {
          draft.topics = draft.topics.filter(function (x) { return x !== id; });
        }
      },
      onClear: function () {
        const draft = initFiltersDraftState();
        draft.topics = [];
      }
    });

    // 2. Formats
    formatsDropdownCtrl = setupGenericMultiselect({
      wrapId: 'feedFormatsDropdownWrap',
      triggerId: 'feedFormatsDropdownTrigger',
      triggerTextId: 'feedFormatsDropdownTriggerText',
      menuId: 'feedFormatsDropdownMenu',
      searchInputId: 'filterFormatSearchInput',
      actionsBarId: 'feedFormatsActionsBar',
      clearBtnId: 'btnFormatsClearSelection',
      listId: 'modalFormatsFilterBar',
      chipsBarId: 'filterSelectedFormatsChips',
      itemClass: 'feed-format-checkbox-item',
      checkboxClass: 'feed-format-checkbox',
      titleClass: 'feed-format-title',
      defaultText: 'Все форматы',
      countPrefix: 'Выбрано форматов: ',
      getItems: function () {
        return (window.PublicationConfig && Array.isArray(window.PublicationConfig.FORMATS)) ? window.PublicationConfig.FORMATS : [];
      },
      getItemById: function (id) {
        return window.PublicationConfig ? window.PublicationConfig.getFormatById(id) : null;
      },
      getSelected: function () {
        const draft = initFiltersDraftState();
        return draft.formats || [];
      },
      onToggle: function (id, isChecked) {
        const draft = initFiltersDraftState();
        if (isChecked) {
          if (draft.formats.indexOf(id) === -1) draft.formats.push(id);
        } else {
          draft.formats = draft.formats.filter(function (x) { return x !== id; });
        }
        updateAdvancedFiltersUI();
      },
      onClear: function () {
        const draft = initFiltersDraftState();
        draft.formats = [];
        updateAdvancedFiltersUI();
      }
    });

    // 3. Audiences
    audiencesDropdownCtrl = setupGenericMultiselect({
      wrapId: 'feedAudiencesDropdownWrap',
      triggerId: 'feedAudiencesDropdownTrigger',
      triggerTextId: 'feedAudiencesDropdownTriggerText',
      menuId: 'feedAudiencesDropdownMenu',
      searchInputId: 'filterAudienceSearchInput',
      actionsBarId: 'feedAudiencesActionsBar',
      clearBtnId: 'btnAudiencesClearSelection',
      listId: 'modalAudiencesFilterBar',
      chipsBarId: 'filterSelectedAudiencesChips',
      itemClass: 'feed-audience-checkbox-item',
      checkboxClass: 'feed-audience-checkbox',
      titleClass: 'feed-audience-title',
      defaultText: 'Все аудитории',
      countPrefix: 'Выбрано аудиторий: ',
      getItems: function () {
        return (window.PublicationConfig && Array.isArray(window.PublicationConfig.AUDIENCES)) ? window.PublicationConfig.AUDIENCES : [];
      },
      getItemById: function (id) {
        return window.PublicationConfig ? window.PublicationConfig.getAudienceById(id) : null;
      },
      getSelected: function () {
        const draft = initFiltersDraftState();
        return draft.audiences || [];
      },
      onToggle: function (id, isChecked) {
        const draft = initFiltersDraftState();
        if (isChecked) {
          if (draft.audiences.indexOf(id) === -1) draft.audiences.push(id);
        } else {
          draft.audiences = draft.audiences.filter(function (x) { return x !== id; });
        }
        updateAdvancedFiltersUI();
      },
      onClear: function () {
        const draft = initFiltersDraftState();
        draft.audiences = [];
        updateAdvancedFiltersUI();
      }
    });

    initDateDropdown();
  }

  function initDateDropdown() {
    const wrap = document.getElementById('feedDateDropdownWrap');
    const trigger = document.getElementById('feedDateDropdownTrigger');
    const triggerText = document.getElementById('feedDateDropdownTriggerText');
    const menu = document.getElementById('feedDateDropdownMenu');
    const optionBtns = document.querySelectorAll('.feed-date-option-item');
    const periodSelect = document.getElementById('feedFilterPeriodSelect');
    const customDates = document.getElementById('feedFilterCustomDates');

    if (!wrap || !trigger || !menu) return;

    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      const isOpen = menu.style.display !== 'none';
      if (isOpen) {
        closeDropdownMenu(menu, trigger);
      } else {
        closeAllFilterDropdowns(menu);
        openDropdownMenu(wrap, menu, trigger, null);
      }
    });

    document.addEventListener('click', function (e) {
      if (!wrap.contains(e.target) && menu.style.display !== 'none') {
        closeDropdownMenu(menu, trigger);
      }
    });

    optionBtns.forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        const val = btn.getAttribute('data-value');
        const textEl = btn.querySelector('.feed-date-option-text');
        const label = textEl ? textEl.textContent.trim() : val;
        const draft = initFiltersDraftState();
        draft.period = val;

        if (periodSelect) periodSelect.value = val;
        if (triggerText) triggerText.textContent = label;

        optionBtns.forEach(function (b) {
          const isSel = (b === btn);
          b.classList.toggle('is-selected', isSel);
          b.setAttribute('aria-selected', isSel ? 'true' : 'false');
        });

        if (customDates) {
          customDates.style.display = (val === 'custom') ? 'flex' : 'none';
        }
        if (val !== 'custom') {
          draft.dateFrom = '';
          draft.dateTo = '';
          const dFrom = document.getElementById('filterDateFrom');
          const dTo = document.getElementById('filterDateTo');
          if (dFrom) dFrom.value = '';
          if (dTo) dTo.value = '';
        }

        closeDropdownMenu(menu, trigger);
        checkFiltersPanelUnappliedChanges();
      });
    });

    wrap.addEventListener('keydown', function (e) {
      if (menu.style.display === 'none') {
        if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          closeAllFilterDropdowns(menu);
          openDropdownMenu(wrap, menu, trigger, null);
        }
        return;
      }

      if (e.key === 'Escape') {
        e.stopPropagation();
        closeDropdownMenu(menu, trigger);
        trigger.focus();
        return;
      }

      const options = Array.from(menu.querySelectorAll('.feed-date-option-item'));
      const activeIdx = options.indexOf(document.activeElement);

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        const next = options[activeIdx + 1] || options[0];
        if (next) next.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prev = options[activeIdx - 1] || options[options.length - 1];
        if (prev) prev.focus();
      }
    });
  }

  function renderFilterTopicsUI() {
    if (topicsDropdownCtrl) topicsDropdownCtrl.updateUI();
  }

  function updateFilterTopicsUI() {
    if (topicsDropdownCtrl) topicsDropdownCtrl.updateUI();
  }

  function renderSelectedTopicsChips() {
    if (topicsDropdownCtrl) topicsDropdownCtrl.updateUI();
  }

  function initFeedFiltersPanel() {
    const closeBtn = document.getElementById('btnCloseFeedFilters');
    const cancelBtn = document.getElementById('btnCancelFeedFilters');
    const applyBtn = document.getElementById('btnApplyFilters');
    const resetBtn = document.getElementById('feedResetFiltersBtn');

    if (closeBtn) {
      closeBtn.addEventListener('click', closeFeedFiltersPanel);
    }

    if (cancelBtn) {
      cancelBtn.addEventListener('click', function () {
        filtersDraftState = null;
        syncFilterFormUI();
        checkFiltersPanelUnappliedChanges();
        closeFeedFiltersPanel();
      });
    }

    // 1. Material Types tumblers with "Все типы"
    const filterTypeInputs = document.querySelectorAll('input[name="feedFilterMaterialType"]');
    filterTypeInputs.forEach(function (inp) {
      inp.addEventListener('change', function () {
        const draft = initFiltersDraftState();
        const t = inp.value || inp.getAttribute('data-type');
        handleFilterTypeTumblerChange(filterTypeInputs, inp, function () {
          const allInp = Array.from(filterTypeInputs).find(function (i) {
            const val = i.value || i.getAttribute('data-type');
            return val === 'all';
          });
          if (allInp && allInp.checked) {
            draft.types = [];
          } else {
            draft.types = Array.from(filterTypeInputs)
              .filter(function (i) {
                const val = i.value || i.getAttribute('data-type');
                return val !== 'all' && i.checked;
              })
              .map(function (i) { return i.value || i.getAttribute('data-type'); });
            if (draft.types.length === 0) {
              draft.types = [];
              if (allInp) allInp.checked = true;
            }
          }
          checkFiltersPanelUnappliedChanges();
        });
      });
    });

    // 2. Complexity tumblers with "Любой уровень"
    const filterCompInputs = document.querySelectorAll('input[name="feedFilterComplexity"]');
    filterCompInputs.forEach(function (inp) {
      inp.addEventListener('change', function () {
        const draft = initFiltersDraftState();
        const c = inp.value || inp.getAttribute('data-complexity');
        handleComplexityTumblerChange(filterCompInputs, inp, function () {
          const allInp = Array.from(filterCompInputs).find(function (i) {
            const val = i.value || i.getAttribute('data-complexity');
            return val === 'all';
          });
          if (allInp && allInp.checked) {
            draft.complexities = [];
          } else {
            draft.complexities = Array.from(filterCompInputs)
              .filter(function (i) {
                const val = i.value || i.getAttribute('data-complexity');
                return val !== 'all' && i.checked;
              })
              .map(function (i) { return i.value || i.getAttribute('data-complexity'); });
            if (draft.complexities.length === 0) {
              draft.complexities = [];
              if (allInp) allInp.checked = true;
            }
          }
          checkFiltersPanelUnappliedChanges();
        });
      });
    });

    // 3. Period selector & custom dates
    const periodSelect = document.getElementById('feedFilterPeriodSelect');
    const periodChips = document.querySelectorAll('#feedFilterPeriods .feed-filter-chip');
    const customDates = document.getElementById('feedFilterCustomDates');
    const dFromInput = document.getElementById('filterDateFrom');
    const dToInput = document.getElementById('filterDateTo');

    if (periodSelect) {
      periodSelect.addEventListener('change', function () {
        const draft = initFiltersDraftState();
        const val = periodSelect.value;
        draft.period = val;
        if (customDates) {
          customDates.style.display = (val === 'custom') ? 'flex' : 'none';
        }
        checkFiltersPanelUnappliedChanges();
      });
    }

    if (dFromInput && dToInput) {
      dFromInput.addEventListener('change', function () {
        const draft = initFiltersDraftState();
        draft.dateFrom = dFromInput.value;
        if (dFromInput.value) {
          dToInput.min = dFromInput.value;
        } else {
          dToInput.removeAttribute('min');
        }
        checkFiltersPanelUnappliedChanges();
      });
      dToInput.addEventListener('change', function () {
        const draft = initFiltersDraftState();
        draft.dateTo = dToInput.value;
        if (dToInput.value) {
          dFromInput.max = dToInput.value;
        } else {
          dFromInput.removeAttribute('max');
        }
        checkFiltersPanelUnappliedChanges();
      });
    }

    periodChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        const draft = initFiltersDraftState();
        periodChips.forEach(function (c) { c.classList.remove('active'); });
        chip.classList.add('active');
        const p = chip.getAttribute('data-period');
        draft.period = p;
        if (periodSelect) {
          periodSelect.value = p;
        }
        if (customDates) {
          customDates.style.display = (p === 'custom') ? 'flex' : 'none';
        }
        checkFiltersPanelUnappliedChanges();
      });
    });

    // 4. Initialize all dropdowns
    initAllFilterDropdowns();

    // 5. Action buttons
    if (applyBtn) {
      applyBtn.addEventListener('click', applyFiltersFromPanel);
    }

    if (resetBtn) {
      resetBtn.addEventListener('click', resetFiltersForm);
    }

    // Global escape key handler for panels & dropdowns
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        const sortMenu = document.getElementById('feedSortCustomMenu');
        if (sortMenu && sortMenu.style.display !== 'none') {
          const sortTrigger = document.getElementById('feedSortCustomTrigger');
          sortMenu.style.display = 'none';
          if (sortTrigger) {
            sortTrigger.setAttribute('aria-expanded', 'false');
            sortTrigger.focus();
          }
          return;
        }

        const openMenu = document.querySelector('.feed-multiselect-dropdown-menu[style*="display: flex"], .feed-topics-dropdown-menu[style*="display: flex"], .feed-date-dropdown-menu[style*="display: flex"], .feed-multiselect-dropdown-menu[style*="display: block"], .feed-topics-dropdown-menu[style*="display: block"], .feed-date-dropdown-menu[style*="display: block"]');
        if (openMenu && openMenu.style.display !== 'none') {
          openMenu.style.display = 'none';
          openMenu.classList.remove('opens-up');
          const wrap = openMenu.closest('.feed-multiselect-dropdown-wrap, .feed-topics-dropdown-wrap, .feed-date-dropdown-wrap');
          const trigger = wrap ? wrap.querySelector('.feed-multiselect-dropdown-trigger, .feed-topics-dropdown-trigger, .feed-date-dropdown-trigger') : null;
          if (trigger) {
            trigger.setAttribute('aria-expanded', 'false');
            trigger.focus();
          }
          return;
        }

        const settingsPanel = document.getElementById('feedSettingsPanel');
        if (settingsPanel && settingsPanel.style.display !== 'none') {
          closeFeedSettingsPanel(false);
          return;
        }
        const filtersPanel = document.getElementById('feedFiltersPanel');
        const drawerWrap = document.getElementById('feedFiltersDrawerWrap');
        if ((filtersPanel && filtersPanel.style.display !== 'none') || (drawerWrap && drawerWrap.classList.contains('is-open'))) {
          closeFeedFiltersPanel();
          const toggleBtn = document.getElementById('btnFeedFiltersToggle');
          if (toggleBtn) {
            toggleBtn.focus();
          }
          return;
        }
        const authModal = document.getElementById('authModal');
        if (authModal && authModal.style.display !== 'none') {
          closeAuthModal();
          return;
        }
      }
    });

    syncFilterFormUI();
  }

  function syncFilterFormUI() {
    const draft = initFiltersDraftState();

    // 1. Types
    const types = draft.types || [];
    const isAllTypes = (types.length === 0);
    document.querySelectorAll('input[name="feedFilterMaterialType"]').forEach(function (inp) {
      const dt = inp.value || inp.getAttribute('data-type');
      if (dt === 'all') {
        inp.checked = isAllTypes;
      } else {
        inp.checked = (!isAllTypes && types.indexOf(dt) !== -1);
      }
    });
    document.querySelectorAll('#feedFilterMaterialTypes .feed-filter-chip').forEach(function (b) {
      const dt = b.getAttribute('data-type');
      if (dt === 'all') {
        b.classList.toggle('active', isAllTypes);
      } else {
        b.classList.toggle('active', !isAllTypes && types.indexOf(dt) !== -1);
      }
    });

    // 2. Complexities
    const comp = draft.complexities || [];
    const isAllComp = (comp.length === 0);
    document.querySelectorAll('input[name="feedFilterComplexity"]').forEach(function (inp) {
      const dc = inp.value || inp.getAttribute('data-complexity');
      if (dc === 'all') {
        inp.checked = isAllComp;
      } else {
        inp.checked = (!isAllComp && (comp.indexOf(dc) !== -1 || (dc === 'none' && comp.indexOf('unspecified') !== -1)));
      }
    });
    document.querySelectorAll('#feedFilterComplexityLevels .feed-filter-chip').forEach(function (b) {
      const dc = b.getAttribute('data-complexity');
      if (dc === 'all') {
        b.classList.toggle('active', isAllComp);
      } else {
        b.classList.toggle('active', !isAllComp && comp.indexOf(dc) !== -1);
      }
    });

    // 3. Period & Date Dropdown
    const per = draft.period || 'all';
    const periodSelect = document.getElementById('feedFilterPeriodSelect');
    if (periodSelect) {
      periodSelect.value = per;
    }
    const dateLabels = {
      all: 'За всё время',
      week: 'За неделю',
      month: 'За месяц',
      year: 'За год',
      custom: 'Указать период'
    };
    const dateTrigText = document.getElementById('feedDateDropdownTriggerText');
    if (dateTrigText) {
      dateTrigText.textContent = dateLabels[per] || 'За всё время';
    }
    document.querySelectorAll('.feed-date-option-item').forEach(function (btn) {
      const isSel = (btn.getAttribute('data-value') === per);
      btn.classList.toggle('is-selected', isSel);
      btn.setAttribute('aria-selected', isSel ? 'true' : 'false');
    });
    document.querySelectorAll('#feedFilterPeriods .feed-filter-chip').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-period') === per);
    });
    const customDates = document.getElementById('feedFilterCustomDates');
    if (customDates) customDates.style.display = (per === 'custom') ? 'flex' : 'none';
    const dFrom = document.getElementById('filterDateFrom');
    const dTo = document.getElementById('filterDateTo');
    const valFrom = draft.dateFrom || '';
    const valTo = draft.dateTo || '';
    if (dFrom) {
      dFrom.value = valFrom;
      if (valTo) dFrom.max = valTo;
      else dFrom.removeAttribute('max');
    }
    if (dTo) {
      dTo.value = valTo;
      if (valFrom) dTo.min = valFrom;
      else dTo.removeAttribute('min');
    }

    // 4. Dropdowns UI
    if (topicsDropdownCtrl) topicsDropdownCtrl.updateUI();
    if (formatsDropdownCtrl) formatsDropdownCtrl.updateUI();
    if (audiencesDropdownCtrl) audiencesDropdownCtrl.updateUI();

    // 5. Sync hidden selects for legacy compat
    const fmtSel = document.getElementById('feedFormatSelect');
    if (fmtSel) fmtSel.value = (draft.formats && draft.formats[0]) || 'all';
    const audSel = document.getElementById('feedAudienceSelect');
    if (audSel) audSel.value = (draft.audiences && draft.audiences[0]) || 'all';

    updateAdvancedFiltersUI();
    checkFiltersPanelUnappliedChanges();
  }

  function resetFiltersForm() {
    const draft = initFiltersDraftState();
    draft.types = [];
    draft.complexities = [];
    draft.topics = [];
    draft.period = 'all';
    draft.dateFrom = '';
    draft.dateTo = '';
    draft.formats = [];
    draft.audiences = [];

    const topicSearch = document.getElementById('filterTopicSearchInput');
    if (topicSearch) topicSearch.value = '';
    const formatSearch = document.getElementById('filterFormatSearchInput');
    if (formatSearch) formatSearch.value = '';
    const audienceSearch = document.getElementById('filterAudienceSearchInput');
    if (audienceSearch) audienceSearch.value = '';

    syncFilterFormUI();
  }

  function applyFiltersFromPanel() {
    const draft = initFiltersDraftState();

    // Read current types from tumblers or chips
    const allTypeInp = document.getElementById('feedFilterTypeAll');
    const isAllTypes = allTypeInp ? allTypeInp.checked : (draft.types.length === 0);
    if (isAllTypes) {
      draft.types = [];
    } else {
      draft.types = Array.from(document.querySelectorAll('input[name="feedFilterMaterialType"]:checked'))
        .filter(function (i) { return i.value !== 'all'; })
        .map(function (i) { return i.value || i.getAttribute('data-type'); });
    }

    // Read current complexities from tumblers or chips
    const allCompInp = document.getElementById('feedFilterCompAll');
    const isAllComp = allCompInp ? allCompInp.checked : (draft.complexities.length === 0);
    if (isAllComp) {
      draft.complexities = [];
    } else {
      draft.complexities = Array.from(document.querySelectorAll('input[name="feedFilterComplexity"]:checked'))
        .filter(function (i) { return i.value !== 'all'; })
        .map(function (i) { return i.value || i.getAttribute('data-complexity'); });
    }

    // Read period
    const periodSelect = document.getElementById('feedFilterPeriodSelect');
    const activePeriodBtn = document.querySelector('#feedFilterPeriods .feed-filter-chip.active');
    const periodVal = draft.period || (periodSelect ? periodSelect.value : (activePeriodBtn ? activePeriodBtn.getAttribute('data-period') : 'all'));

    if (periodVal === 'custom') {
      const dFrom = document.getElementById('filterDateFrom');
      const dTo = document.getElementById('filterDateTo');
      const valFrom = dFrom ? dFrom.value : '';
      const valTo = dTo ? dTo.value : '';
      if (valFrom && valTo && valFrom > valTo) {
        showToast('Начальная дата не может быть позже конечной');
        return;
      }
      draft.period = periodVal;
      draft.dateFrom = valFrom;
      draft.dateTo = valTo;
    } else {
      draft.period = periodVal;
      draft.dateFrom = '';
      draft.dateTo = '';
    }

    // Apply draft to state.filters
    state.filters.types = (draft.types || []).slice();
    state.filters.complexities = (draft.complexities || []).slice();
    state.filters.period = draft.period;
    state.filters.dateFrom = draft.dateFrom;
    state.filters.dateTo = draft.dateTo;
    state.filters.topics = (draft.topics || []).slice();
    state.topic = state.filters.topics[0] || 'all';
    state.filters.formats = (draft.formats || []).slice();
    state.filters.format = state.filters.formats[0] || 'all';
    state.filters.audiences = (draft.audiences || []).slice();
    state.filters.audience = state.filters.audiences[0] || 'all';

    // Keep legacy selects in sync
    const fmtSel = document.getElementById('feedFormatSelect');
    if (fmtSel) fmtSel.value = state.filters.format;
    const audSel = document.getElementById('feedAudienceSelect');
    if (audSel) audSel.value = state.filters.audience;

    updateAdvancedFiltersUI();
    updateFilterBadge();
    checkFiltersPanelUnappliedChanges();

    closeFeedFiltersPanel();
    state.offset = 0;
    syncURL(false);
    fetchFeed(true);

    const chipsBar = document.getElementById('feedActiveChipsBar');
    const scrollTarget = (chipsBar && chipsBar.style.display !== 'none')
      ? chipsBar
      : (document.getElementById('feedCardsContainer') || document.querySelector('.feed-main-column'));
    if (scrollTarget) {
      scrollTarget.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  // --------------------------------------------------------------------------
  // 8. Active Chips, Badge, Client Filtering & Reset
  // --------------------------------------------------------------------------
  const MONTHS_RU = {
    'января': 0, 'февраля': 1, 'марта': 2, 'апреля': 3, 'мая': 4, 'июня': 5,
    'июля': 6, 'августа': 7, 'сентября': 8, 'октября': 9, 'ноября': 10, 'декабря': 11
  };

  function parseArticleDate(art) {
    if (!art) return null;
    if (art.isoDate) {
      const d = new Date(art.isoDate);
      if (!isNaN(d.getTime())) return d;
    }
    if (art.createdAt) {
      const d = new Date(art.createdAt);
      if (!isNaN(d.getTime())) return d;
    }
    if (typeof art.date === 'string') {
      const parts = art.date.trim().split(/\s+/);
      if (parts.length === 3) {
        const day = parseInt(parts[0], 10);
        const mStr = parts[1].toLowerCase();
        const year = parseInt(parts[2], 10);
        if (!isNaN(day) && !isNaN(year) && MONTHS_RU[mStr] !== undefined) {
          return new Date(year, MONTHS_RU[mStr], day);
        }
      }
      const d = new Date(art.date);
      if (!isNaN(d.getTime())) return d;
    }
    return null;
  }

  function filterArticleList(articles) {
    if (!Array.isArray(articles)) return [];
    if (state.tab === 'saved') {
      return articles;
    }

    const excAuthors = new Set((state.userExceptions.authors || []).map(function (a) { return String(a.id || a).toLowerCase(); }));
    const excTopics = new Set((state.userExceptions.topics || []).map(function (t) { return String(t.id || t).toLowerCase(); }));
    const excTags = new Set((state.userExceptions.tags || []).map(function (tg) {
      return String(tg.id || tg).replace(/^#/, '').toLowerCase().trim();
    }));

    const subAuthors = new Set((state.userSubscriptions.authors || []).map(function (a) { return String(a.id || a).toLowerCase(); }));
    const subTopics = new Set((state.userSubscriptions.topics || []).map(function (t) { return String(t.id || t).toLowerCase(); }));
    const subTags = new Set((state.userSubscriptions.tags || []).map(function (tg) {
      return String(tg.id || tg).replace(/^#/, '').toLowerCase().trim();
    }));

    return articles.filter(function (art) {
      // 1. Exceptions priority: any excluded author, topic, or hashtag hides publication
      const artAuthorId = String(art.authorId || art.author || '').toLowerCase();
      const artAuthorName = String(art.author || '').toLowerCase();
      if (excAuthors.has(artAuthorId) || excAuthors.has(artAuthorName)) {
        return false;
      }

      const artTopics = Array.isArray(art.topics) ? art.topics : (art.topic ? [art.topic] : []);
      for (let i = 0; i < artTopics.length; i++) {
        if (excTopics.has(String(artTopics[i]).toLowerCase())) {
          return false;
        }
      }

      const artTags = Array.isArray(art.keywords) ? art.keywords : [];
      for (let i = 0; i < artTags.length; i++) {
        const normTag = String(artTags[i]).replace(/^#/, '').toLowerCase().trim();
        if (excTags.has(normTag)) {
          return false;
        }
      }

      // 2. Personal feed rules (tab === 'my')
      if (state.tab === 'my') {
        const allowedTypes = state.feedSettings.materialTypes || [];
        if (allowedTypes.length > 0 && allowedTypes.indexOf(art.format || art.type || 'article') === -1) {
          return false;
        }

        const allowedComp = state.feedSettings.complexityLevels || ['all'];
        if (allowedComp.indexOf('all') === -1 && allowedComp.length > 0) {
          const artComp = art.complexity || 'none';
          if (allowedComp.indexOf(artComp) === -1) {
            return false;
          }
        }

        let matchedSub = false;
        if (subAuthors.has(artAuthorId) || subAuthors.has(artAuthorName)) {
          matchedSub = true;
        }
        if (!matchedSub) {
          for (let i = 0; i < artTopics.length; i++) {
            if (subTopics.has(String(artTopics[i]).toLowerCase())) {
              matchedSub = true;
              break;
            }
          }
        }
        if (!matchedSub) {
          for (let i = 0; i < artTags.length; i++) {
            const normTag = String(artTags[i]).replace(/^#/, '').toLowerCase().trim();
            if (subTags.has(normTag)) {
              matchedSub = true;
              break;
            }
          }
        }

        const totalSubs = subAuthors.size + subTopics.size + subTags.size;
        if (totalSubs > 0 && !matchedSub) {
          return false;
        }
      }

      // 3. Temporary filters
      if (state.filters.types && state.filters.types.length > 0) {
        if (state.filters.types.indexOf(art.format || art.type || 'article') === -1) {
          return false;
        }
      }

      if (state.filters.complexities && state.filters.complexities.length > 0) {
        const artComp = art.complexity || 'none';
        if (state.filters.complexities.indexOf(artComp) === -1) {
          return false;
        }
      }

      if (state.filters.topics && state.filters.topics.length > 0) {
        let topicMatches = false;
        for (let i = 0; i < artTopics.length; i++) {
          if (state.filters.topics.indexOf(artTopics[i]) !== -1) {
            topicMatches = true;
            break;
          }
        }
        if (!topicMatches) return false;
      }

      // Format filter: multiple formats joined via OR
      const allowedFormats = (state.filters.formats && state.filters.formats.length > 0)
        ? state.filters.formats
        : (state.filters.format && state.filters.format !== 'all' ? [state.filters.format] : []);

      if (allowedFormats.length > 0) {
        if (!art.format || allowedFormats.indexOf(art.format) === -1) {
          return false;
        }
      }

      // Audience filter: multiple audiences joined via OR
      const allowedAudiences = (state.filters.audiences && state.filters.audiences.length > 0)
        ? state.filters.audiences
        : (state.filters.audience && state.filters.audience !== 'all' ? [state.filters.audience] : []);

      if (allowedAudiences.length > 0) {
        const artAud = art.targetAudience || art.audience;
        if (!artAud || allowedAudiences.indexOf(artAud) === -1) {
          return false;
        }
      }

      if (state.filters.period && state.filters.period !== 'all') {
        const artDate = parseArticleDate(art);
        if (artDate) {
          const now = new Date();
          if (state.filters.period === 'week') {
            const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
            if (artDate < weekAgo) return false;
          } else if (state.filters.period === 'month') {
            const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
            if (artDate < monthAgo) return false;
          } else if (state.filters.period === 'year') {
            const yearAgo = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000);
            if (artDate < yearAgo) return false;
          } else if (state.filters.period === 'custom') {
            if (state.filters.dateFrom) {
              const dFrom = new Date(state.filters.dateFrom);
              if (!isNaN(dFrom.getTime()) && artDate < dFrom) return false;
            }
            if (state.filters.dateTo) {
              const dTo = new Date(state.filters.dateTo + 'T23:59:59');
              if (!isNaN(dTo.getTime()) && artDate > dTo) return false;
            }
          }
        }
      }

      if (state.search) {
        const q = state.search.toLowerCase();
        const author = art.author || '';
        const role = art.authorRole || '';
        const kws = Array.isArray(art.keywords) ? art.keywords.join(' ') : '';
        const haystack = (art.title + ' ' + author + ' ' + role + ' ' + (art.description || '') + ' ' + kws).toLowerCase();
        if (haystack.indexOf(q) === -1) return false;
      }

      return true;
    });
  }

  function updateFilterBadge() {
    let groups = 0;
    if (state.filters.types && state.filters.types.length > 0) groups++;
    if (state.filters.topics && state.filters.topics.length > 0) groups++;
    if (state.filters.complexities && state.filters.complexities.length > 0) groups++;
    if ((state.filters.period && state.filters.period !== 'all') || state.filters.dateFrom || state.filters.dateTo) groups++;
    if ((state.filters.formats && state.filters.formats.length > 0) || (state.filters.format && state.filters.format !== 'all')) groups++;
    if ((state.filters.audiences && state.filters.audiences.length > 0) || (state.filters.audience && state.filters.audience !== 'all')) groups++;

    const badge = document.getElementById('feedFiltersCountBadge');
    if (badge) {
      if (groups > 0) {
        badge.textContent = groups;
        badge.style.display = 'inline-block';
      } else {
        badge.style.display = 'none';
      }
    }
  }

  function renderActiveChips() {
    const bar = document.getElementById('feedActiveChipsBar');
    const list = document.getElementById('feedActiveChipsList');
    if (!bar || !list) return;

    list.innerHTML = '';
    const chips = [];

    if (state.search) {
      chips.push({
        id: 'search',
        label: 'Поиск: "' + state.search + '"',
        remove: function () {
          state.search = '';
          const inp = document.getElementById('feedSearchInput');
          const clr = document.getElementById('feedSearchClearBtn');
          if (inp) inp.value = '';
          if (clr) clr.style.display = 'none';
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        }
      });
    }

    const typeLabels = { article: 'Статьи', post: 'Посты', news: 'Новости', question: 'Вопросы' };
    (state.filters.types || []).forEach(function (t) {
      chips.push({
        id: 'type-' + t,
        label: 'Тип: ' + (typeLabels[t] || t),
        remove: function () {
          state.filters.types = state.filters.types.filter(function (x) { return x !== t; });
          syncFilterFormUI();
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        }
      });
    });

    (state.filters.topics || []).forEach(function (topId) {
      let topTitle = topId;
      if (window.PublicationConfig) {
        const tObj = window.PublicationConfig.getTopicById(topId);
        if (tObj) topTitle = tObj.title;
      }
      chips.push({
        id: 'topic-' + topId,
        label: 'Тема: ' + topTitle,
        remove: function () {
          state.filters.topics = state.filters.topics.filter(function (x) { return x !== topId; });
          if (state.filters.topics.length === 0) state.topic = 'all';
          syncFilterFormUI();
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        }
      });
    });

    const compLabels = { easy: 'Простой', medium: 'Средний', hard: 'Сложный', none: 'Без уровня' };
    (state.filters.complexities || []).forEach(function (c) {
      chips.push({
        id: 'comp-' + c,
        label: 'Сложность: ' + (compLabels[c] || c),
        remove: function () {
          state.filters.complexities = state.filters.complexities.filter(function (x) { return x !== c; });
          syncFilterFormUI();
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        }
      });
    });

    if (state.filters.period && state.filters.period !== 'all') {
      const periodLabels = { week: 'За неделю', month: 'За месяц', year: 'За год' };
      let pLabel = periodLabels[state.filters.period] || state.filters.period;
      if (state.filters.period === 'custom') {
        pLabel = (state.filters.dateFrom || '...') + ' - ' + (state.filters.dateTo || '...');
      }
      chips.push({
        id: 'period',
        label: 'Период: ' + pLabel,
        remove: function () {
          state.filters.period = 'all';
          state.filters.dateFrom = '';
          state.filters.dateTo = '';
          state.period = 'all';
          syncFilterFormUI();
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        }
      });
    }

    const activeFormats = (state.filters.formats && state.filters.formats.length > 0)
      ? state.filters.formats
      : (state.filters.format && state.filters.format !== 'all' ? [state.filters.format] : []);

    activeFormats.forEach(function (fmtId) {
      let fmtTitle = fmtId;
      if (window.PublicationConfig) {
        const fObj = window.PublicationConfig.getFormatById(fmtId);
        if (fObj) fmtTitle = fObj.title;
      }
      chips.push({
        id: 'format-' + fmtId,
        label: 'Формат: ' + fmtTitle,
        remove: function () {
          state.filters.formats = (state.filters.formats || []).filter(function (x) { return x !== fmtId; });
          state.filters.format = state.filters.formats[0] || 'all';
          if (filtersDraftState) {
            filtersDraftState.formats = state.filters.formats.slice();
          }
          syncFilterFormUI();
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        }
      });
    });

    const activeAudiences = (state.filters.audiences && state.filters.audiences.length > 0)
      ? state.filters.audiences
      : (state.filters.audience && state.filters.audience !== 'all' ? [state.filters.audience] : []);

    activeAudiences.forEach(function (audId) {
      let audTitle = audId;
      if (window.PublicationConfig) {
        const aObj = window.PublicationConfig.getAudienceById(audId);
        if (aObj) audTitle = aObj.title;
      }
      chips.push({
        id: 'audience-' + audId,
        label: 'Аудитория: ' + audTitle,
        remove: function () {
          state.filters.audiences = (state.filters.audiences || []).filter(function (x) { return x !== audId; });
          state.filters.audience = state.filters.audiences[0] || 'all';
          if (filtersDraftState) {
            filtersDraftState.audiences = state.filters.audiences.slice();
          }
          syncFilterFormUI();
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        }
      });
    });

    if (chips.length === 0) {
      bar.style.display = 'none';
      return;
    }

    bar.style.display = 'flex';
    chips.forEach(function (chip) {
      const chipEl = document.createElement('div');
      chipEl.className = 'active-chip';
      chipEl.innerHTML =
        '<span class="chip-label">' + escapeHtml(chip.label) + '</span>' +
        '<button type="button" class="chip-remove-btn" title="Удалить фильтр ' + escapeHtml(chip.label) + '" aria-label="Удалить фильтр">' +
          '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<line x1="18" y1="6" x2="6" y2="18"></line>' +
            '<line x1="6" y1="6" x2="18" y2="18"></line>' +
          '</svg>' +
        '</button>';

      chipEl.querySelector('.chip-remove-btn').addEventListener('click', function (e) {
        e.stopPropagation();
        chip.remove();
      });

      list.appendChild(chipEl);
    });
  }

  function resetAllFilters() {
    state.search = '';
    state.filters.types = [];
    state.filters.topics = [];
    state.filters.complexities = [];
    state.filters.period = 'all';
    state.filters.dateFrom = '';
    state.filters.dateTo = '';
    state.filters.format = 'all';
    state.filters.formats = [];
    state.filters.audience = 'all';
    state.filters.audiences = [];
    filtersDraftState = null;
    state.topic = 'all';
    state.period = 'all';
    state.offset = 0;

    const searchInput = document.getElementById('feedSearchInput');
    const clearBtn = document.getElementById('feedSearchClearBtn');
    if (searchInput) {
      searchInput.value = '';
      if (clearBtn) clearBtn.style.display = 'none';
    }

    const periodSelect = document.getElementById('feedPeriodSelect');
    if (periodSelect) periodSelect.value = 'all';

    updatePeriodVisibility();
    resetFiltersForm();
    syncFilterFormUI();
    syncURL(false);
    fetchFeed(true);
  }

  // --------------------------------------------------------------------------
  // 9. Data Fetching & Rendering
  // --------------------------------------------------------------------------
  function renderSkeletons() {
    const container = document.getElementById('feedCardsContainer');
    if (!container) return;
    container.innerHTML = '';
    for (let i = 0; i < 3; i++) {
      const sk = document.createElement('div');
      sk.className = 'feed-skeleton-card';
      sk.innerHTML =
        '<div class="skeleton-author">' +
          '<div class="skeleton-avatar skeleton-shimmer"></div>' +
          '<div class="skeleton-line skeleton-shimmer" style="width: 140px;"></div>' +
        '</div>' +
        '<div class="skeleton-title skeleton-shimmer"></div>' +
        '<div class="skeleton-body skeleton-shimmer"></div>' +
        '<div class="skeleton-footer skeleton-shimmer"></div>';
      container.appendChild(sk);
    }
  }

  // --------------------------------------------------------------------------
  // Offline Badge & Status Controls
  // --------------------------------------------------------------------------
  function showOfflineBadge() {
    let badge = document.getElementById('feedOfflineBadge');
    if (!badge) {
      const container = document.getElementById('feedCardsContainer');
      if (!container || !container.parentNode) return;
      const tmp = document.createElement('div');
      tmp.innerHTML = '<div class="feed-offline-badge" id="feedOfflineBadge"><span class="feed-offline-dot"></span>Автономный режим (демо-данные)</div>';
      badge = tmp.firstElementChild;
      container.parentNode.insertBefore(badge, container);
    }
    badge.style.display = 'inline-flex';
  }

  function hideOfflineBadge() {
    const badge = document.getElementById('feedOfflineBadge');
    if (badge) {
      badge.style.display = 'none';
    }
  }

  function fetchFeed(isInitial) {
    if (!isInitial && state.isLoading) return;

    if (isInitial) {
      if (feedAbortController) {
        feedAbortController.abort();
      }
      feedAbortController = new AbortController();
      state.offset = 0;
      renderSkeletons();
    } else if (!feedAbortController || feedAbortController.signal.aborted) {
      feedAbortController = new AbortController();
    }

    state.requestGeneration = (state.requestGeneration || 0) + 1;
    const currentGeneration = state.requestGeneration;
    state.isLoading = true;

    // Build API query
    const params = new URLSearchParams();
    let backendTab = state.tab;
    if (backendTab === 'my') backendTab = 'subscriptions';
    if (backendTab === 'focus') backendTab = 'all';
    params.set('tab', backendTab);

    if (backendTab === 'questions' && state.questionStatus) {
      params.set('questionStatus', state.questionStatus);
    }

    if (backendTab === 'top') {
      params.set('period', state.topPeriod || 'week');
    }

    if (state.search) params.set('search', state.search);
    if (state.sort) params.set('sort', state.sort);

    // Active filters
    if (state.filters.types && state.filters.types.length > 0) {
      params.set('types', state.filters.types.join(','));
    }
    if (state.filters.topics && state.filters.topics.length > 0) {
      params.set('topics', state.filters.topics.join(','));
      params.set('topic', state.filters.topics[0]);
    } else if (!state.savedOnly && state.topic && state.topic !== 'all') {
      params.set('topic', state.topic);
    }
    if (state.filters.complexities && state.filters.complexities.length > 0) {
      params.set('complexities', state.filters.complexities.join(','));
    }
    if (state.filters.period && state.filters.period !== 'all') {
      params.set('period', state.filters.period);
    }
    if (state.filters.dateFrom) params.set('dateFrom', state.filters.dateFrom);
    if (state.filters.dateTo) params.set('dateTo', state.filters.dateTo);
    if (state.filters.formats && state.filters.formats.length > 0) {
      params.set('formats', state.filters.formats.join(','));
      params.set('format', state.filters.formats[0]);
    } else if (state.filters.format && state.filters.format !== 'all') {
      params.set('format', state.filters.format);
    }
    if (state.filters.audiences && state.filters.audiences.length > 0) {
      params.set('audiences', state.filters.audiences.join(','));
      params.set('audience', state.filters.audiences[0]);
    } else if (state.filters.audience && state.filters.audience !== 'all') {
      params.set('audience', state.filters.audience);
    }

    // Personal feed settings apply to subscriptions / my tab
    if (state.tab === 'my' || state.tab === 'subscriptions') {
      if (state.feedSettings && state.feedSettings.materialTypes && state.feedSettings.materialTypes.length < 4) {
        params.set('types', state.feedSettings.materialTypes.join(','));
      }
      if (state.feedSettings && state.feedSettings.complexityLevels && (state.feedSettings.complexityLevels.indexOf('all') === -1 || state.feedSettings.complexityLevels.length > 1)) {
        params.set('complexityLevels', state.feedSettings.complexityLevels.join(','));
      }
    }

    params.set('limit', String(state.limit));
    params.set('offset', String(state.offset));

    if (state.tab === 'saved') {
      if (!currentUser) {
        state.isLoading = false;
        openAuthModal('saved');
        return;
      }
      const savedParams = new URLSearchParams();
      savedParams.set('type', state.savedType || 'all');
      if (state.search) savedParams.set('search', state.search);
      savedParams.set('limit', String(state.limit));
      savedParams.set('offset', String(state.offset));

      fetch('/api/saved?' + savedParams.toString(), { signal: feedAbortController.signal })
        .then(function (res) {
          if (currentGeneration !== state.requestGeneration) return;
          if (res.status === 401) {
            state.isLoading = false;
            openAuthModal('saved');
            throw new Error('AUTH_REQUIRED');
          }
          if (!res.ok) {
            const err = new Error('HTTP error ' + res.status);
            err.status = res.status;
            throw err;
          }
          return res.json();
        })
        .then(function (data) {
          if (currentGeneration !== state.requestGeneration || !data) return;
          state.isLoading = false;
          if (data && data.success) {
            hideOfflineBadge();
            const items = data.items || [];
            if (isInitial) {
              state.articles = items;
            } else {
              const existingIds = new Set(state.articles.map(function (a) { return a.id; }));
              const incoming = items.filter(function (a) { return !existingIds.has(a.id); });
              state.articles = state.articles.concat(incoming);
            }
            state.total = data.total !== undefined ? data.total : state.articles.length;
            state.hasMore = Boolean(data.hasMore);

            if (data.counts) {
              const pAll = document.getElementById('savedCountAll');
              const pPub = document.getElementById('savedCountPublications');
              const pQ = document.getElementById('savedCountQuestions');
              const pComm = document.getElementById('savedCountComments');
              const sBadge = document.getElementById('feedSavedCount');
              if (pAll) pAll.textContent = data.counts.total;
              if (pPub) pPub.textContent = data.counts.publications;
              if (pQ) pQ.textContent = data.counts.questions;
              if (pComm) pComm.textContent = data.counts.comments;
              if (sBadge) sBadge.textContent = data.counts.total;
            }

            renderFeedCards(isInitial);
            updateResultsCount();
          } else {
            hideOfflineBadge();
            renderErrorState('Не удалось загрузить сохраненные материалы: ' + (data ? data.error : 'Неизвестная ошибка'));
          }
        })
        .catch(function (err) {
          if (err.name === 'AbortError' || currentGeneration !== state.requestGeneration) {
            return;
          }
          state.isLoading = false;
          if (err.message === 'AUTH_REQUIRED') return;
          if (typeof navigator !== 'undefined' && navigator.onLine === false) {
            handleOfflineFallback(isInitial);
          } else {
            renderErrorState('Ошибка при загрузке сохраненных материалов');
          }
        });
      return;
    }

    if (state.savedOnly) {
      const bookmarks = getBookmarks();
      if (bookmarks.length === 0) {
        state.isLoading = false;
        state.articles = [];
        state.total = 0;
        state.hasMore = false;
        renderFeedCards(isInitial);
        updateResultsCount();
        return;
      }
      params.set('ids', bookmarks.join(','));
    }

    fetch('/api/articles?' + params.toString(), { signal: feedAbortController.signal })
      .then(function (res) {
        if (currentGeneration !== state.requestGeneration) return;
        if (res.status === 401 && (state.tab === 'my' || state.tab === 'subscriptions')) {
          state.isLoading = false;
          openAuthModal('subscriptions');
          throw new Error('AUTH_REQUIRED');
        }
        if (!res.ok) {
          const err = new Error('HTTP error ' + res.status);
          err.status = res.status;
          throw err;
        }
        return res.json();
      })
      .then(function (data) {
        if (currentGeneration !== state.requestGeneration || !data) return;
        state.isLoading = false;
        if (data && data.success) {
          hideOfflineBadge();
          const rawArticles = data.articles || [];
          const filtered = filterArticleList(rawArticles);

          state.noSubscriptions = Boolean(data.noSubscriptions);
          if (isInitial) {
            state.articles = filtered;
          } else {
            const existingIds = new Set(state.articles.map(function (a) { return a.id; }));
            const incoming = filtered.filter(function (a) { return !existingIds.has(a.id); });
            state.articles = state.articles.concat(incoming);
          }
          state.total = data.total !== undefined ? data.total : state.articles.length;
          state.hasMore = Boolean(data.hasMore);

          if (data.topicCounts) {
            state.topicCounts = data.topicCounts;
            renderSidebarTopics(data.topicCounts);
          }
          renderFeedCards(isInitial);
          updateResultsCount();
        } else {
          hideOfflineBadge();
          renderErrorState('Не удалось загрузить статьи: ' + (data ? data.error : 'Неизвестная ошибка'));
        }
      })
      .catch(function (err) {
        if (err.name === 'AbortError' || currentGeneration !== state.requestGeneration) {
          return;
        }
        state.isLoading = false;
        if (err.message === 'AUTH_REQUIRED') return;
        // handleOfflineFallback(isInitial) only when client is offline:
        const isOffline = (typeof navigator !== 'undefined' && navigator.onLine === false) || (typeof window !== 'undefined' && window.location && window.location.protocol === 'file:');
        if (isOffline) {
          showOfflineBadge();
          handleOfflineFallback(isInitial);
        } else {
          hideOfflineBadge();
          let message;
          if (err && err.status && err.status >= 500) {
            message = 'Ошибка сервера (' + err.status + '). Не удалось загрузить публикации.';
          } else if (err && err.status && err.status >= 400) {
            message = 'Ошибка запроса (' + err.status + '). Не удалось загрузить публикации.';
          } else {
            message = 'Ошибка сети при загрузке публикаций.';
          }
          renderErrorState(message);
        }
      });
  }

  const loadArticles = fetchFeed;

  function handleOfflineFallback(isInitial) {
    if (state.savedOnly) {
      const bookmarks = getBookmarks();
      const filtered = FALLBACK_ARTICLES.filter(function (a) {
        return bookmarks.indexOf(a.id) !== -1;
      });
      state.articles = filtered;
      state.total = filtered.length;
      state.hasMore = false;
      renderFeedCards(isInitial);
      updateResultsCount();
      return;
    }

    let items = filterArticleList(FALLBACK_ARTICLES);

    // Apply sorting in offline fallback: explicit state.sort has strict priority over tab
    const hasExplicitSort = Boolean(state.sort && state.sort !== 'default' && state.sort !== 'none');
    if (hasExplicitSort && state.sort === 'rating') {
      items.sort(function (a, b) {
        const sa = a.score !== undefined ? a.score : 0;
        const sb = b.score !== undefined ? b.score : 0;
        if (sb !== sa) return sb - sa;
        const da = parseArticleDate(a) || 0;
        const db = parseArticleDate(b) || 0;
        return db - da;
      });
    } else if (hasExplicitSort && state.sort === 'popular') {
      items.sort(function (a, b) {
        const la = (a.likesCount !== undefined ? a.likesCount : a.views || 0);
        const lb = (b.likesCount !== undefined ? b.likesCount : b.views || 0);
        if (lb !== la) return lb - la;
        const da = parseArticleDate(a) || 0;
        const db = parseArticleDate(b) || 0;
        return db - da;
      });
    } else if (hasExplicitSort && state.sort === 'oldest') {
      items.sort(function (a, b) {
        const da = parseArticleDate(a) || 0;
        const db = parseArticleDate(b) || 0;
        return da - db;
      });
    } else if (hasExplicitSort && (state.sort === 'discussed' || state.sort === 'comments')) {
      items.sort(function (a, b) {
        const ca = a.commentsCount || 0;
        const cb = b.commentsCount || 0;
        if (cb !== ca) return cb - ca;
        const da = parseArticleDate(a) || 0;
        const db = parseArticleDate(b) || 0;
        return db - da;
      });
    } else if (hasExplicitSort && state.sort === 'newest') {
      items.sort(function (a, b) {
        const da = parseArticleDate(a) || 0;
        const db = parseArticleDate(b) || 0;
        return db - da;
      });
    } else if (state.tab === 'top') {
      items.sort(function (a, b) {
        const sa = a.score !== undefined ? a.score : 0;
        const sb = b.score !== undefined ? b.score : 0;
        if (sb !== sa) return sb - sa;
        const ca = a.commentsCount || 0;
        const cb = b.commentsCount || 0;
        if (cb !== ca) return cb - ca;
        const da = parseArticleDate(a) || 0;
        const db = parseArticleDate(b) || 0;
        return db - da;
      });
    } else if (state.tab === 'focus') {
      items.sort(function (a, b) {
        const la = (a.likesCount !== undefined ? a.likesCount : a.views || 0);
        const lb = (b.likesCount !== undefined ? b.likesCount : b.views || 0);
        if (lb !== la) return lb - la;
        const da = parseArticleDate(a) || 0;
        const db = parseArticleDate(b) || 0;
        return db - da;
      });
    } else {
      items.sort(function (a, b) {
        const da = parseArticleDate(a) || 0;
        const db = parseArticleDate(b) || 0;
        return db - da;
      });
    }

    state.articles = items;
    state.total = items.length;
    state.hasMore = false;
    renderFeedCards(isInitial);
    updateResultsCount();
    renderSidebarTopics({
      'digital-ruble-payments': 1,
      'smart-contracts-development': 2,
      'information-security': 1,
      'law-and-compliance': 1,
      'oracles-and-data': 1
    });
  }

  function updateResultsCount() {
    const el = document.getElementById('feedResultsCount');
    if (!el) return;
    const n = state.total || 0;
    el.textContent = pluralizePublications(n);
  }

  function renderSavedCommentCard(comment) {
    const card = document.createElement('article');
    card.className = 'feed-card saved-comment-card';
    card.setAttribute('data-id', comment.id);
    card.setAttribute('data-comment-id', comment.id);

    const authorInitials = getInitials(comment.authorName || 'Пользователь');
    const avatarHtml = comment.authorAvatar
      ? '<img src="' + escapeHtml(comment.authorAvatar) + '" alt="' + escapeHtml(comment.authorName || '') + '" class="author-avatar-img">'
      : '<span class="author-avatar-initials">' + escapeHtml(authorInitials) + '</span>';

    const dateRu = comment.date || (comment.createdAt ? formatRuDate(comment.createdAt) : 'Недавно');
    const targetLabel = (comment.commentType === 'answer' || comment.articleType === 'question') ? 'к вопросу:' : 'к публикации:';
    const permalink = comment.permalink || ('article.html?id=' + encodeURIComponent(comment.articleId) + '#comment-' + encodeURIComponent(comment.id));

    card.innerHTML =
      '<div class="saved-comment-header">' +
        '<div class="saved-comment-author-wrap">' +
          '<div class="author-avatar-circle">' + avatarHtml + '</div>' +
          '<div class="saved-comment-author-info">' +
            '<span class="saved-comment-author-name">' + escapeHtml(comment.authorName || 'Пользователь') + '</span>' +
            '<span class="saved-comment-date">' + escapeHtml(dateRu) + '</span>' +
          '</div>' +
        '</div>' +
        '<button type="button" class="btn-saved-comment-unsave" title="Удалить из сохраненного" aria-label="Удалить из сохраненного">' +
          '<svg width="18" height="18" viewBox="0 0 24 24" fill="#f59e0b" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>' +
          '</svg>' +
        '</button>' +
      '</div>' +
      '<div class="saved-comment-target-meta">' +
        '<span class="saved-comment-target-label">' + escapeHtml(targetLabel) + '</span> ' +
        '<a href="' + escapeHtml(permalink) + '" class="saved-comment-target-title">' + escapeHtml(comment.articleTitle || 'Материал сообщества') + '</a>' +
      '</div>' +
      '<blockquote class="saved-comment-quote">' +
        escapeHtml(comment.text || '') +
      '</blockquote>' +
      '<div class="saved-comment-actions">' +
        '<a href="' + escapeHtml(permalink) + '" class="saved-comment-permalink-btn">' +
          '<span>Перейти к комментарию</span>' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>' +
        '</a>' +
      '</div>';

    const unsaveBtn = card.querySelector('.btn-saved-comment-unsave');
    if (unsaveBtn) {
      unsaveBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        unsaveComment(comment.id, card);
      });
    }

    return card;
  }

  function unsaveComment(commentId, cardEl) {
    fetch('/api/comments/' + encodeURIComponent(commentId) + '/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'unsave' })
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.success) {
          showToast('Комментарий удален из сохраненного');
          if (cardEl && cardEl.parentNode) {
            cardEl.remove();
          }
          state.articles = state.articles.filter(function (a) { return a.id !== commentId; });
          updateSavedCounter();
          const container = document.getElementById('feedCardsContainer');
          if (container && container.children.length === 0) {
            renderEmptyState();
          }
        } else {
          showToast('Не удалось удалить из сохраненного', 'error');
        }
      })
      .catch(function () {
        showToast('Ошибка при удалении из сохраненного', 'error');
      });
  }

  function renderFeedCards(isInitial) {
    const container = document.getElementById('feedCardsContainer');
    if (!container) return;

    if (isInitial) {
      container.innerHTML = '';
    }

    if (state.articles.length === 0) {
      renderEmptyState();
      updatePaginationControls();
      return;
    }

    function renderCardItem(item) {
      if (item.entityType === 'comment') {
        return renderSavedCommentCard(item);
      }
      return createCardElement(item, {
        onBookmarkToggle: function (itemId, btn, art) {
          window.CardComponent.toggleCardBookmark(itemId, btn);
          if (state.tab === 'saved') {
            const cardEl = container.querySelector('.feed-card[data-id="' + itemId + '"]');
            if (cardEl) cardEl.remove();
            state.articles = state.articles.filter(function (a) { return a.id !== itemId; });
            updateSavedCounter();
            if (container.children.length === 0) {
              renderEmptyState();
            }
          }
        }
      });
    }

    // Render cards avoiding DOM duplicates
    if (isInitial) {
      state.articles.forEach(function (item) {
        container.appendChild(renderCardItem(item));
      });
    } else {
      const existingDomIds = new Set(
        Array.from(container.querySelectorAll('.feed-card')).map(function (c) {
          return c.getAttribute('data-id');
        })
      );
      state.articles.forEach(function (item) {
        if (!existingDomIds.has(item.id)) {
          container.appendChild(renderCardItem(item));
        }
      });
    }

    updatePaginationControls();

    // Scroll restoration after returning from full article reading
    if (isInitial) {
      try {
        const savedScroll = sessionStorage.getItem('sc_feed_scroll');
        if (savedScroll !== null) {
          sessionStorage.removeItem('sc_feed_scroll');
          const scrollY = parseInt(savedScroll, 10);
          if (!isNaN(scrollY) && scrollY > 0) {
            requestAnimationFrame(function () {
              window.scrollTo({ top: scrollY, behavior: 'instant' });
            });
          }
        }
      } catch (e) {}
    }
  }

  function updatePaginationControls() {
    const loadMoreBtn = document.getElementById('feedLoadMoreBtn');
    const endOfList = document.getElementById('feedEndOfList');

    if (loadMoreBtn) {
      loadMoreBtn.style.display = state.hasMore ? 'inline-block' : 'none';
    }
    if (endOfList) {
      endOfList.style.display =
        !state.hasMore && state.articles.length > 0 ? 'block' : 'none';
    }
  }

  function renderEmptyState() {
    const container = document.getElementById('feedCardsContainer');
    if (!container) return;

    if (state.tab === 'my' || state.tab === 'subscriptions') {
      if (!currentUser) {
        container.innerHTML =
          '<div class="my-feed-empty-state">' +
            '<div class="empty-state-icon-box">' +
              '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>' +
                '<circle cx="12" cy="7" r="4"></circle>' +
              '</svg>' +
            '</div>' +
            '<h3 class="empty-state-title">Войдите в аккаунт</h3>' +
            '<p class="empty-state-desc">Войдите в аккаунт, чтобы управлять подписками и читать персональную ленту материалов.</p>' +
            '<div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; margin-top: 16px;">' +
              '<button type="button" class="btn btn-primary empty-state-btn" id="btnEmptyLogin">' +
                '<span>Войти в аккаунт</span>' +
              '</button>' +
            '</div>' +
          '</div>';
        const loginBtn = document.getElementById('btnEmptyLogin');
        if (loginBtn) {
          loginBtn.addEventListener('click', function () { openAuthModal('subscriptions'); });
        }
        return;
      } else if (state.noSubscriptions) {
        container.innerHTML =
          '<div class="my-feed-empty-state">' +
            '<div class="empty-state-icon-box">' +
              '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                '<path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>' +
                '<circle cx="8.5" cy="7" r="4"></circle>' +
                '<line x1="20" y1="8" x2="20" y2="14"></line>' +
                '<line x1="23" y1="11" x2="17" y2="11"></line>' +
              '</svg>' +
            '</div>' +
            '<h3 class="empty-state-title">У вас пока нет подписок</h3>' +
            '<p class="empty-state-desc">Подпишитесь на авторов, клубы, компании, направления или теги, чтобы собрать свою ленту.</p>' +
            '<div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; margin-top: 16px;">' +
              '<button type="button" class="btn btn-primary empty-state-btn" id="btnEmptyChooseSubs">' +
                '<span>Выбрать подписки</span>' +
              '</button>' +
              '<button type="button" class="btn btn-secondary empty-state-btn" id="btnEmptyOpenSettings">' +
                '<span>Настроить ленту</span>' +
              '</button>' +
            '</div>' +
          '</div>';

        const openSettingsBtn = document.getElementById('btnEmptyOpenSettings');
        if (openSettingsBtn) {
          openSettingsBtn.addEventListener('click', openFeedSettingsPanel);
        }
        const chooseBtn = document.getElementById('btnEmptyChooseSubs');
        if (chooseBtn) {
          chooseBtn.addEventListener('click', function () { openSubscriptionsModal('author'); });
        }
        return;
      } else {
        container.innerHTML =
          '<div class="my-feed-empty-state">' +
            '<div class="empty-state-icon-box">' +
              '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                '<circle cx="12" cy="12" r="10"></circle>' +
                '<line x1="12" y1="8" x2="12" y2="12"></line>' +
                '<line x1="12" y1="16" x2="12.01" y2="16"></line>' +
              '</svg>' +
            '</div>' +
            '<h3 class="empty-state-title">В вашей ленте пока нет новых публикаций</h3>' +
            '<p class="empty-state-desc">Попробуйте расширить круг подписок, изменить настройки ленты или перейти ко всем публикациям.</p>' +
            '<div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; margin-top: 16px;">' +
              '<button type="button" class="btn btn-primary empty-state-btn" id="btnEmptyManageSubs">' +
                '<span>Управление подписками</span>' +
              '</button>' +
              '<button type="button" class="btn btn-secondary empty-state-btn" id="btnEmptyAllFeed">' +
                '<span>В фокусе</span>' +
              '</button>' +
            '</div>' +
          '</div>';

        const manageBtn = document.getElementById('btnEmptyManageSubs');
        if (manageBtn) {
          manageBtn.addEventListener('click', function () { openSubscriptionsModal('author'); });
        }
        const allFeedBtn = document.getElementById('btnEmptyAllFeed');
        if (allFeedBtn) {
          allFeedBtn.addEventListener('click', function () {
            switchTab('focus');
          });
        }
        return;
      }
    }

    const isSaved = state.tab === 'saved';
    let title = isSaved ? 'Нет сохраненных публикаций' : 'Ничего не найдено';
    let desc = isSaved
      ? 'Вы еще не добавили ни одной статьи в закладки. Нажмите на иконку закладки на любой публикации в ленте, чтобы сохранить ее.'
      : 'По вашему запросу и выбранным фильтрам не найдено публикаций. Попробуйте изменить параметры или сбросить фильтры.';

    if (isSaved) {
      if (state.savedType === 'comments') {
        title = 'Нет сохраненных комментариев';
        desc = 'Вы еще не добавили ни одного комментария в закладки. Сохраняйте полезные комментарии прямо при чтении материалов.';
      } else if (state.savedType === 'questions') {
        title = 'Нет сохраненных вопросов';
        desc = 'Вы еще не сохранили ни одного вопроса сообщества.';
      } else if (state.savedType === 'publications') {
        title = 'Нет сохраненных публикаций';
        desc = 'Вы еще не сохранили ни одной публикации в закладки. Нажмите на иконку закладки на любой публикации, чтобы сохранить ее.';
      } else {
        title = 'Нет сохраненных материалов';
        desc = 'Вы еще не сохранили ни одной публикации, вопроса или комментария.';
      }
    }

    container.innerHTML =
      '<div class="feed-empty-state">' +
        '<svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
          '<circle cx="11" cy="11" r="8"></circle>' +
          '<line x1="21" y1="21" x2="16.65" y2="16.65"></line>' +
          '<line x1="8" y1="11" x2="14" y2="11"></line>' +
        '</svg>' +
        '<h3 class="empty-state-title">' + escapeHtml(title) + '</h3>' +
        '<p class="empty-state-desc">' + escapeHtml(desc) + '</p>' +
        '<div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; margin-top: 16px;">' +
          (!isSaved
            ? '<button type="button" id="feedEmptyChangeFiltersBtn" class="btn btn-secondary">' +
                '<span>Изменить фильтры</span>' +
              '</button>'
            : '') +
          '<button type="button" id="feedEmptyResetBtn" class="btn btn-primary">' +
            '<span>' + (isSaved ? 'Перейти ко всем статьям' : 'Сбросить фильтры') + '</span>' +
          '</button>' +
        '</div>' +
      '</div>';

    const changeFiltersBtn = document.getElementById('feedEmptyChangeFiltersBtn');
    if (changeFiltersBtn) {
      changeFiltersBtn.addEventListener('click', function () {
        openFeedFiltersPanel();
      });
    }

    const btn = document.getElementById('feedEmptyResetBtn');
    if (btn) {
      btn.addEventListener('click', function () {
        if (isSaved) {
          switchTab('all');
        } else {
          resetAllFilters();
        }
      });
    }
  }

  function renderErrorState(message) {
    const container = document.getElementById('feedCardsContainer');
    if (!container) return;

    container.innerHTML =
      '<div class="feed-empty-state">' +
        '<svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
          '<circle cx="12" cy="12" r="10"></circle>' +
          '<line x1="12" y1="8" x2="12" y2="12"></line>' +
          '<line x1="12" y1="16" x2="12.01" y2="16"></line>' +
        '</svg>' +
        '<h3 class="empty-state-title">Ошибка загрузки</h3>' +
        '<p class="empty-state-desc">' + escapeHtml(message) + '</p>' +
        '<button type="button" class="btn btn-secondary" id="feedRetryBtn" onclick="if(window.FeedApp&&window.FeedApp.loadArticles){window.FeedApp.loadArticles(true);}else{window.location.reload();}">' +
          'Повторить попытку' +
        '</button>' +
      '</div>';

    const retryBtn = document.getElementById('feedRetryBtn');
    if (retryBtn) {
      retryBtn.addEventListener('click', function (e) {
        e.preventDefault();
        loadArticles(true);
      });
    }
  }

  // --------------------------------------------------------------------------
  // 10. Article Card Generator & Likes Interaction
  // --------------------------------------------------------------------------
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

    // Optimistic UI update
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
          showToast(data.error || 'Ошибка при сохранении отметки');
        }
      })
      .catch(function (err) {
        if (err.message !== 'AUTH_REQUIRED') {
          // Rollback
          btn.classList.toggle('is-liked', currentLiked);
          btn.setAttribute('aria-pressed', currentLiked ? 'true' : 'false');
          btn.title = currentLiked ? 'Больше не нравится' : 'Нравится';
          if (countEl) countEl.textContent = currentCount;
          if (item) {
            item.hasLiked = currentLiked;
            item.likesCount = currentCount;
          }
          showToast('Не удалось обновить отметку');
        }
      });
  }

  // --------------------------------------------------------------------------
  // Article Share Popover & Article Report Modal Logic
  // --------------------------------------------------------------------------
  function isArticleReported(articleId, item) {
    if (!articleId) return false;
    if (!currentUser) return false;
    if (item && (item.hasReported !== undefined || item.isReported !== undefined)) {
      return Boolean(item.hasReported || item.isReported);
    }
    if (window._reportedArticleIds && window._reportedArticleIds.has(articleId)) return true;
    try {
      const userKey = 'sc_reported_articles_' + currentUser.id;
      const stored = JSON.parse(localStorage.getItem(userKey) || '[]');
      if (stored.includes(articleId)) {
        window._reportedArticleIds = window._reportedArticleIds || new Set();
        window._reportedArticleIds.add(articleId);
        return true;
      }
    } catch (e) {}
    return false;
  }

  function markArticleAsReported(articleId) {
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
    if (Array.isArray(state.articles)) {
      state.articles.forEach(function (a) {
        if (a && (a.id === articleId || a.draftId === articleId)) {
          a.hasReported = true;
          a.isReported = true;
        }
      });
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
        if (svg) {
          svg.setAttribute('fill', 'currentColor');
        }
      }
    });
  }

  let activeFeedSharePopoverArticleId = null;
  let activeFeedSharePopoverTrigger = null;

  function isFeedSharePopoverOpen() {
    const popover = document.getElementById('feedSharePopover');
    return Boolean(popover && popover.style.display !== 'none');
  }

  function closeFeedSharePopover() {
    const popover = document.getElementById('feedSharePopover');
    if (popover) {
      popover.style.display = 'none';
    }
    if (activeFeedSharePopoverTrigger) {
      activeFeedSharePopoverTrigger.setAttribute('aria-expanded', 'false');
      activeFeedSharePopoverTrigger = null;
    }
    activeFeedSharePopoverArticleId = null;
  }

  function openArticleSharePopover(articleId, triggerBtn, item) {
    const popover = document.getElementById('feedSharePopover');
    if (!popover || !triggerBtn) return;

    if (activeFeedSharePopoverArticleId === articleId && isFeedSharePopoverOpen()) {
      closeFeedSharePopover();
      return;
    }

    if (activeFeedSharePopoverTrigger && activeFeedSharePopoverTrigger !== triggerBtn) {
      activeFeedSharePopoverTrigger.setAttribute('aria-expanded', 'false');
    }

    activeFeedSharePopoverArticleId = articleId;
    activeFeedSharePopoverTrigger = triggerBtn;
    triggerBtn.setAttribute('aria-haspopup', 'true');
    triggerBtn.setAttribute('aria-expanded', 'true');

    const origin = window.location.origin || '';
    const permalink = origin + '/article.html?id=' + encodeURIComponent(articleId);
    const title = (item && item.title) || document.title || 'SmartContractum';
    const encodedUrl = encodeURIComponent(permalink);
    const encodedText = encodeURIComponent(title);

    const proto = 'https:' + '//';
    const tgLink = popover.querySelector('[data-action="telegram"]');
    if (tgLink) {
      tgLink.href = proto + 't.me/share/url?url=' + encodedUrl + '&text=' + encodedText;
    }
    const vkLink = popover.querySelector('[data-action="vk"]');
    if (vkLink) {
      vkLink.href = proto + 'vk.com/share.php?url=' + encodedUrl + '&title=' + encodedText;
    }
    const okLink = popover.querySelector('[data-action="ok"]');
    if (okLink) {
      okLink.href = proto + 'connect.ok.ru/offer?url=' + encodedUrl + '&title=' + encodedText;
    }

    const copyBtn = popover.querySelector('[data-action="copy"]');
    if (copyBtn) {
      copyBtn.onclick = function (e) {
        e.preventDefault();
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(permalink)
            .then(function () {
              showToast('Ссылка скопирована');
            })
            .catch(function () {
              fallbackCopyArticleLink(permalink);
            });
        } else {
          fallbackCopyArticleLink(permalink);
        }
        closeFeedSharePopover();
      };
    }

    const socialLinks = popover.querySelectorAll('a.comment-share-item');
    socialLinks.forEach(function (link) {
      link.onclick = function () {
        setTimeout(closeFeedSharePopover, 100);
      };
    });

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

  function fallbackCopyArticleLink(text) {
    const input = document.createElement('input');
    input.value = text;
    document.body.appendChild(input);
    input.select();
    try {
      document.execCommand('copy');
      showToast('Ссылка скопирована');
    } catch (e) {
      showToast('Не удалось скопировать ссылку');
    }
    document.body.removeChild(input);
  }

  document.addEventListener('click', function (e) {
    if (!isFeedSharePopoverOpen()) return;
    const popover = document.getElementById('feedSharePopover');
    if (popover && popover.contains(e.target)) return;
    if (e.target.closest('.btn-card-share')) return;
    closeFeedSharePopover();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && isFeedSharePopoverOpen()) {
      closeFeedSharePopover();
      if (activeFeedSharePopoverTrigger) {
        activeFeedSharePopoverTrigger.focus();
      }
    }
  });

  function openArticleReportModal(articleId, triggerBtn, item) {
    if (isArticleReported(articleId)) {
      showToast('Жалоба уже отправлена');
      return;
    }
    if (!currentUser) {
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

  function initArticleReportModalEvents() {
    const modal = document.getElementById('articleReportModal');
    if (!modal || modal._eventsBound) return;
    modal._eventsBound = true;

    function closeModal() {
      modal.style.display = 'none';
      modal._activeReportBtn = null;
    }

    const closeBtn = modal.querySelector('#btnCloseArticleReportModal');
    if (closeBtn) closeBtn.addEventListener('click', closeModal);

    const cancelBtn = modal.querySelector('#btnCancelArticleReport');
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

    modal.addEventListener('click', function (e) {
      if (e.target === modal) closeModal();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal.style.display === 'flex') {
        closeModal();
      }
    });

    const form = modal.querySelector('#articleReportForm');
    if (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        const articleId = (modal.querySelector('#reportArticleId') || {}).value;
        const selectedReasonRadio = modal.querySelector('input[name="articleReportReason"]:checked');
        const reason = selectedReasonRadio ? selectedReasonRadio.value : 'spam';
        const detailsEl = modal.querySelector('#articleReportDetails');
        const details = detailsEl ? detailsEl.value.trim() : '';

        if (!articleId) {
          closeModal();
          return;
        }

        const submitBtn = modal.querySelector('#btnSubmitArticleReport');
        if (submitBtn) submitBtn.disabled = true;

        fetch('/api/articles/' + encodeURIComponent(articleId) + '/report', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            reason: reason,
            details: details
          })
        })
          .then(function (res) {
            return res.json().then(function (data) {
              return { status: res.status, data: data };
            });
          })
          .then(function (result) {
            if (submitBtn) submitBtn.disabled = false;
            if (result.status === 200 && result.data && result.data.success) {
              closeModal();
              showToast('Жалоба отправлена');
              markArticleAsReported(articleId);
            } else if (result.status === 409) {
              closeModal();
              showToast('Вы уже отправили жалобу на этот материал');
              markArticleAsReported(articleId);
            } else if (result.status === 403) {
              closeModal();
              showToast('Нельзя пожаловаться на собственный материал');
            } else if (result.status === 401) {
              closeModal();
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
  }

  function createCardElement(item) {
    if (window.SmartContractumCard && typeof window.SmartContractumCard.createCardElement === 'function') {
      initArticleReportModalEvents();
      return window.SmartContractumCard.createCardElement(item, {
        isBookmarked: function (artId, artItem) {
          return isBookmarked(artId, artItem || item);
        },
        isReported: isArticleReported,
        currentUserId: currentUser ? currentUser.id : '',
        onLikeToggle: toggleArticleLike,
        onShareClick: openArticleSharePopover,
        onReportClick: openArticleReportModal,
        onBookmarkToggle: function (id, btn) {
          if (!currentUser) {
            showToast('Для сохранения публикации необходимо войти');
            openAuthModal();
            return;
          }
          const wasActive = btn.classList.contains('is-bookmarked');
          const nextActive = !wasActive;
          btn.classList.toggle('is-bookmarked', nextActive);
          btn.classList.toggle('is-saved', nextActive);
          const svg = btn.querySelector('svg');
          if (svg) svg.setAttribute('fill', nextActive ? 'currentColor' : 'none');
          const newTooltip = nextActive ? 'Убрать из сохраненного' : 'Сохранить статью';
          btn.title = newTooltip;
          btn.setAttribute('aria-label', newTooltip);
          const countEl = btn.querySelector('.card-save-count');
          const prevCount = countEl ? (parseInt(countEl.textContent, 10) || 0) : 0;
          if (countEl) {
            countEl.textContent = nextActive ? (prevCount + 1) : Math.max(0, prevCount - 1);
          }

          // Optimistic local cache update
          const bms = getBookmarks();
          const idx = bms.indexOf(id);
          if (nextActive && idx === -1) { bms.push(id); saveBookmarks(bms); }
          else if (!nextActive && idx !== -1) { bms.splice(idx, 1); saveBookmarks(bms); }

          fetch('/api/articles/' + encodeURIComponent(id) + (nextActive ? '/save' : '/unsave'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
          })
          .then(function (res) {
            if (!res.ok) {
              throw new Error('HTTP ' + res.status);
            }
            return res.json();
          })
          .then(function (data) {
            if (data && data.success) {
              const finalSaved = Boolean(data.isSaved);
              btn.classList.toggle('is-bookmarked', finalSaved);
              btn.classList.toggle('is-saved', finalSaved);
              if (svg) svg.setAttribute('fill', finalSaved ? 'currentColor' : 'none');
              const tip = finalSaved ? 'Убрать из сохраненного' : 'Сохранить статью';
              btn.title = tip;
              btn.setAttribute('aria-label', tip);
              if (typeof data.savesCount === 'number' && countEl) {
                countEl.textContent = data.savesCount;
              }
              if (item) {
                item.savesCount = data.savesCount;
                item.hasSaved = finalSaved;
                item.isSaved = finalSaved;
              }
              showToast(finalSaved ? 'Публикация сохранена' : 'Публикация удалена из сохраненного');
              if (state.savedOnly && !finalSaved) {
                const cardEl = btn.closest('.feed-card');
                if (cardEl) cardEl.remove();
                state.articles = state.articles.filter(function (a) { return a.id !== id; });
                state.total = Math.max(0, state.total - 1);
                updateResultsCount();
                if (state.articles.length === 0) {
                  renderEmptyState();
                }
              }
            } else {
              // Rollback on logical error
              btn.classList.toggle('is-bookmarked', wasActive);
              btn.classList.toggle('is-saved', wasActive);
              if (svg) svg.setAttribute('fill', wasActive ? 'currentColor' : 'none');
              btn.title = wasActive ? 'Убрать из сохраненного' : 'Сохранить статью';
              btn.setAttribute('aria-label', btn.title);
              if (countEl) countEl.textContent = prevCount;
              const curBms = getBookmarks();
              const curIdx = curBms.indexOf(id);
              if (wasActive && curIdx === -1) { curBms.push(id); saveBookmarks(curBms); }
              else if (!wasActive && curIdx !== -1) { curBms.splice(curIdx, 1); saveBookmarks(curBms); }
              showToast((data && data.error) || 'Ошибка сохранения публикации');
            }
          })
          .catch(function (err) {
            // Rollback on network or HTTP error
            btn.classList.toggle('is-bookmarked', wasActive);
            btn.classList.toggle('is-saved', wasActive);
            if (svg) svg.setAttribute('fill', wasActive ? 'currentColor' : 'none');
            btn.title = wasActive ? 'Убрать из сохраненного' : 'Сохранить статью';
            btn.setAttribute('aria-label', btn.title);
            if (countEl) countEl.textContent = prevCount;
            const curBms = getBookmarks();
            const curIdx = curBms.indexOf(id);
            if (wasActive && curIdx === -1) { curBms.push(id); saveBookmarks(curBms); }
            else if (!wasActive && curIdx !== -1) { curBms.splice(curIdx, 1); saveBookmarks(curBms); }
            if (err && String(err.message).indexOf('401') !== -1) {
              showToast('Для сохранения публикации необходимо войти');
              openAuthModal();
            } else {
              showToast('Не удалось связаться с сервером');
            }
          });
        }
      });
    }

    const fallbackCard = document.createElement('article');
    fallbackCard.className = 'feed-card';
    if (item && item.id) fallbackCard.setAttribute('data-id', item.id);
    return fallbackCard;
  }

  // --------------------------------------------------------------------------
  // 11. Sidebar Widgets Management
  // --------------------------------------------------------------------------
  let isSidebarTopicsExpanded = false;

  function renderSidebarTopics(topicCounts) {
    const listEl = document.getElementById('widgetTopicsList');
    if (!listEl) return;

    if (!window.PublicationConfig || !Array.isArray(window.PublicationConfig.TOPICS)) {
      return;
    }

    const topics = window.PublicationConfig.TOPICS;
    const initialVisible = 6;

    // Sort: descending by publication count, then alphabetical by title in Russian
    const sortedTopics = topics.slice().sort(function (a, b) {
      const countA = (topicCounts && typeof topicCounts[a.id] === 'number') ? topicCounts[a.id] : 0;
      const countB = (topicCounts && typeof topicCounts[b.id] === 'number') ? topicCounts[b.id] : 0;
      if (countB !== countA) {
        return countB - countA;
      }
      return (a.title || '').localeCompare(b.title || '', 'ru');
    });

    function renderItems() {
      listEl.innerHTML = '';

      // Update total topics count in footer button dynamically
      const totalCountEl = document.getElementById('widgetTopicsTotalCount');
      if (totalCountEl) {
        totalCountEl.textContent = sortedTopics.length;
      }

      // Short list: show ONLY topics with published articles (count > 0)
      const nonZeroTopics = sortedTopics.filter(function (t) {
        const count = (topicCounts && typeof topicCounts[t.id] === 'number') ? topicCounts[t.id] : 0;
        return count > 0;
      });

      const visible = isSidebarTopicsExpanded ? sortedTopics : nonZeroTopics.slice(0, initialVisible);
      // Compatibility stub: btnToggleAllSidebarTopics unified into single footer button

      visible.forEach(function (t) {
        const count = (topicCounts && typeof topicCounts[t.id] === 'number') ? topicCounts[t.id] : 0;
        const btn = document.createElement('button');
        btn.type = 'button';
        const isActive = (state.topic === t.id);
        btn.className = 'widget-topic-row widget-topic-chip' + (isActive ? ' is-active' : '');
        btn.setAttribute('data-topic', t.id);
        btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        btn.title = t.title;

        btn.innerHTML =
          '<span class="widget-topic-title">' + escapeHtml(t.title) + '</span>' +
          '<span class="widget-topic-count">' + count + '</span>';

        btn.addEventListener('click', function () {
          if (state.topic === t.id) {
            state.topic = 'all';
          } else {
            state.topic = t.id;
          }
          state.savedOnly = false;
          state.offset = 0;
          updateModalFiltersState();
          syncURL(false);
          fetchFeed(true);
        });

        listEl.appendChild(btn);
      });
    }

    renderItems();
  }

  // --------------------------------------------------------------------------
  // 12. Offline Fallback Seed Articles
  // --------------------------------------------------------------------------
  const FALLBACK_ARTICLES = [
    {
      id: 'art-01',
      title: 'Интеграция смарт-контрактов с платформой Цифрового рубля Банка России',
      description: 'Архитектурный обзор и практический кейс интеграции децентрализованных коммерческих смарт-контрактов с двухуровневой платформой Цифрового рубля.',
      author: 'Алексей Смирнов',
      authorRole: 'Архитектор решений',
      authorInitials: 'АС',
      date: '26 сентября 2026',
      readingTime: '8 мин',
      readingMinutes: 8,
      topic: 'smart-contracts-development',
      topics: ['smart-contracts-development', 'digital-ruble-payments', 'pksc-architecture'],
      targetAudience: 'architects-developers',
      format: 'article',
      complexity: 'hard',
      isDemo: true,
      keywords: ['Цифровой рубль', 'Банк России', 'ПКСК', 'Смарт-контракты', 'Атомарные расчеты'],
      coverImage: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA3ODAgNDQwIiB3aWR0aD0iNzgwIiBoZWlnaHQ9IjQ0MCI+PGRlZnM+PGxpbmVhckdyYWRpZW50IGlkPSJiZzEiIHgxPSIwIiB5MT0iMCIgeDI9IjEiIHkyPSIxIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjMDYwYzE4Ii8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjMGUxZTM4Ii8+PC9saW5lYXJHcmFkaWVudD48bGluZWFyR3JhZGllbnQgaWQ9ImFjYzEiIHgxPSIwIiB5MT0iMCIgeDI9IjEiIHkyPSIwIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjMzhiZGY4Ii8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjNjM2NmYxIi8+PC9saW5lYXJHcmFkaWVudD48L2RlZnM+PHJlY3Qgd2lkdGg9Ijc4MCIgaGVpZ2h0PSI0NDAiIGZpbGw9InVybCgjYmcxKSIvPjxjaXJjbGUgY3g9IjYyMCIgY3k9IjE4MCIgcj0iMTYwIiBmaWxsPSJub25lIiBzdHJva2U9InJnYmEoNTYsMTg5LDI0OCwwLjE1KSIgc3Ryb2tlLXdpZHRoPSIyIi8+PGNpcmNsZSBjeD0iNjIwIiBjeT0iMTgwIiByPSIxMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSg5OSwxMDIsMjQxLDAuMikiIHN0cm9rZS13aWR0aD0iMS41IiBzdHJva2UtZGFzaGFycmF5PSI4IDYiLz48Y2lyY2xlIGN4PSI2MjAiIGN5PSIxODAiIHI9IjYwIiBmaWxsPSJyZ2JhKDU2LDE4OSwyNDgsMC4wOCkiLz48cmVjdCB4PSI2NCIgeT0iNjQiIHdpZHRoPSIxNjAiIGhlaWdodD0iMzIiIHJ4PSIxNiIgZmlsbD0icmdiYSg1NiwxODksMjQ4LDAuMTIpIiBzdHJva2U9InJnYmEoNTYsMTg5LDI0OCwwLjMpIi8+PHRleHQgeD0iODQiIHk9Ijg1IiBmaWxsPSIjMzhiZGY4IiBmb250LWZhbWlseT0iT25lc3QsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTMiIGZvbnQtd2VpZ2h0PSI3MDAiIGxldHRlci1zcGFjaW5nPSIxIj7QptCY0KTQoNCe0JLQntCZINCg0KPQkdCb0Kw8L3RleHQ+PHRleHQgeD0iNjQiIHk9IjE2MCIgZmlsbD0iI2ZmZmZmZiIgZm9udC1mYW1pbHk9Ik9uZXN0LCBzYW5zLXNlcmlmIiBmb250LXNpemU9IjM0IiBmb250LXdlaWdodD0iODAwIj7QmNC90YLQtdCz0YDQsNGG0LjRjyDRgdC80LDRgNGCLdC60L7QvdGC0YDQsNC60YLQvtCyPC90ZXh0Pjx0ZXh0IHg9IjY0IiB5PSIyMDIiIGZpbGw9IiM5NGEzYjgiIGZvbnQtZmFtaWx5PSJPbmVzdCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIzNCIgZm9udC13ZWlnaHQ9IjgwMCI+0YEg0L/Qu9Cw0YLRhNC+0YDQvNC+0Lkg0JHQsNC90LrQsCDQoNC+0YHRgdC40Lg8L3RleHQ+PGxpbmUgeDE9IjY0IiB5MT0iMjM2IiB4Mj0iMzgwIiB5Mj0iMjM2IiBzdHJva2U9InVybCgjYWNjMSkiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIi8+PHRleHQgeD0iNjQiIHk9IjI3NCIgZmlsbD0iI2NiZDVlMSIgZm9udC1mYW1pbHk9Ik9uZXN0LCBzYW5zLXNlcmlmIiBmb250LXNpemU9IjE2Ij7QkNGA0YXQuNGC0LXQutGC0YPRgNCwINGI0LvRjtC30LAg4oCiINCU0LLRg9GF0YTQsNC30L3Ri9C5INC60L7QvNC80LjRgiAyUEMg4oCiINCT0J7QodCiINCgIDM0LjEwLTIwMTI8L3RleHQ+PC9zdmc+'
    },
    {
      id: 'art-02',
      title: 'Практическое руководство по аудиту информационной безопасности смарт-контрактов',
      description: 'Исчерпывающая методология проведения статического и динамического аудита безопасности смарт-контрактов в соответствии с требованиями ГОСТ Р 57580.',
      author: 'Екатерина Романова',
      authorRole: 'Ведущий аудитор безопасности',
      authorInitials: 'ЕР',
      date: '25 сентября 2026',
      readingTime: '12 мин',
      readingMinutes: 12,
      topic: 'information-security',
      topics: ['information-security', 'audit-and-verification', 'testing-and-quality'],
      targetAudience: 'security-auditors',
      format: 'guide',
      complexity: 'medium',
      isDemo: true,
      keywords: ['Аудит ИБ', 'ГОСТ Р 57580', 'Уязвимости', 'Reentrancy', 'Формальная верификация'],
      coverImage: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA3ODAgNDQwIiB3aWR0aD0iNzgwIiBoZWlnaHQ9IjQ0MCI+PGRlZnM+PGxpbmVhckdyYWRpZW50IGlkPSJiZzIiIHgxPSIwIiB5MT0iMCIgeDI9IjEiIHkyPSIxIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjMDYwZjE0Ii8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjMGQyMjIwIi8+PC9saW5lYXJHcmFkaWVudD48bGluZWFyR3JhZGllbnQgaWQ9ImFjYzIiIHgxPSIwIiB5MT0iMCIgeDI9IjEiIHkyPSIwIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjMTBiOTgxIi8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjMzhiZGY4Ii8+PC9saW5lYXJHcmFkaWVudD48L2RlZnM+PHJlY3Qgd2lkdGg9Ijc4MCIgaGVpZ2h0PSI0NDAiIGZpbGw9InVybCgjYmcyKSIvPjxwYXRoIGQ9Ik02MDAgOTAgTDcxMCAxNDAgTDcxMCAyNzAgTDYwMCAzNTAgTDQ5MCAyNzAgTDQ5MCAxNDAgWiIgZmlsbD0icmdiYSgxNiwxODUsMTI5LDAuMDYpIiBzdHJva2U9InJnYmEoMTYsMTg1LDEyOSwwLjMpIiBzdHJva2Utd2lkdGg9IjIiLz48cGF0aCBkPSJNNjAwIDEzMCBMNjcwIDE2NSBMNjcwIDI0NSBMNjAwIDI5NSBMNTMwIDI0NSBMNTMwIDE2NSBaIiBmaWxsPSJub25lIiBzdHJva2U9InJnYmEoNTYsMTg5LDI0OCwwLjI1KSIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1kYXNoYXJyYXk9IjYgNCIvPjxyZWN0IHg9IjY0IiB5PSI2NCIgd2lkdGg9IjE0MCIgaGVpZ2h0PSIzMiIgcng9IjE2IiBmaWxsPSJyZ2JhKDE2LDE4NSwxMjksMC4xMikiIHN0cm9rZT0icmdiYSgxNiwxODUsMTI5LDAuMykiLz48dGV4dCB4PSI4NCIgeT0iODUiIGZpbGw9IiMxMGI5ODEiIGZvbnQtZmFtaWx5PSJPbmVzdCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxMyIgZm9udC13ZWlnaHQ9IjcwMCIgbGV0dGVyLXNwYWNpbmc9IjEiPtCR0JXQl9Ce0J/QkNCh0J3QntCh0KLQrDwvdGV4dD48dGV4dCB4PSI2NCIgeT0iMTYwIiBmaWxsPSIjZmZmZmZmIiBmb250LWZhbWlseT0iT25lc3QsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMzQiIGZvbnQtd2VpZ2h0PSI4MDAiPtCQ0YPQtNC40YIg0YHQvNCw0YDRgi3QutC+0L3RgtGA0LDQutGC0L7QsjwvdGV4dD48dGV4dCB4PSI2NCIgeT0iMjAyIiBmaWxsPSIjOTRhM2I4IiBmb250LWZhbWlseT0iT25lc3QsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMzQiIGZvbnQtd2VpZ2h0PSI4MDAiPtC/0L4g0YHRgtCw0L3QtNCw0YDRgtGDINCT0J7QodCiINCgIDU3NTgwPC90ZXh0PjxsaW5lIHgxPSI2NCIgeTE9IjIzNiIgeDI9IjM4MCIgeTI9IjIzNiIgc3Ryb2tlPSJ1cmwoI2FjYzIpIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPjx0ZXh0IHg9IjY0IiB5PSIyNzQiIGZpbGw9IiNjYmQ1ZTEiIGZvbnQtZmFtaWx5PSJPbmVzdCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNiI+0J/RgNC10LLQtdC90YLQuNCy0L3Ri9C5INCw0L3QsNC70LjQtyDigKIgUmVlbnRyYW5jeUd1YXJkIOKAoiDQpNC+0YDQvNCw0LvRjNC90LDRjyDQstC10YDQuNGE0LjQutCw0YbQuNGPPC90ZXh0Pjwvc3ZnPg=='
    },
    {
      id: 'art-03',
      title: 'Правовая квалификация смарт-контрактов и комплаенс ЦФА в РФ',
      description: 'Анализ актуальной судебной практики, регуляторных требований Федерального закона № 259-ФЗ и правового статуса самоисполняемых соглашений.',
      author: 'Илья Мельников',
      authorRole: 'Советник по правовым вопросам ЦФА',
      authorInitials: 'ИМ',
      date: '24 сентября 2026',
      readingTime: '6 мин',
      readingMinutes: 6,
      topic: 'law-and-compliance',
      topics: ['law-and-compliance', 'business-cases-adoption'],
      targetAudience: 'lawyers-compliance',
      format: 'analytics',
      complexity: 'easy',
      isDemo: true,
      keywords: ['Право', 'Комплаенс', 'ГК РФ', 'Цифровые права', 'ЦФА'],
      coverImage: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA3ODAgNDQwIiB3aWR0aD0iNzgwIiBoZWlnaHQ9IjQ0MCI+PGRlZnM+PGxpbmVhckdyYWRpZW50IGlkPSJiZzMiIHgxPSIwIiB5MT0iMCIgeDI9IjEiIHkyPSIxIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjMTAwYzFlIi8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjMWExNTMyIi8+PC9saW5lYXJHcmFkaWVudD48bGluZWFyR3JhZGllbnQgaWQ9ImFjYzMiIHgxPSIwIiB5MT0iMCIgeDI9IjEiIHkyPSIwIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjYTg1NWY3Ii8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjNjM2NmYxIi8+PC9saW5lYXJHcmFkaWVudD48L2RlZnM+PHJlY3Qgd2lkdGg9Ijc4MCIgaGVpZ2h0PSI0NDAiIGZpbGw9InVybCgjYmczKSIvPjxwYXRoIGQ9Ik01NTAgMTIwIEw2NzAgMTIwIEw2MTAgMjAwIFoiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgxNjgsODUsMjQ3LDAuMykiIHN0cm9rZS13aWR0aD0iMiIvPjxsaW5lIHgxPSI2MTAiIHkxPSI4MCIgeDI9IjYxMCIgeTI9IjMwMCIgc3Ryb2tlPSJyZ2JhKDE2OCw4NSwyNDcsMC4yKSIgc3Ryb2tlLXdpZHRoPSIzIi8+PHJlY3QgeD0iNjQiIHk9IjY0IiB3aWR0aD0iMTgwIiBoZWlnaHQ9IjMyIiByeD0iMTYiIGZpbGw9InJnYmEoMTY4LDg1LDI0NywwLjEyKSIgc3Ryb2tlPSJyZ2JhKDE2OCw4NSwyNDcsMC4zKSIvPjx0ZXh0IHg9Ijg0IiB5PSI4NSIgZmlsbD0iI2MwODRmYyIgZm9udC1mYW1pbHk9Ik9uZXN0LCBzYW5zLXNlcmlmIiBmb250LXNpemU9IjEzIiBmb250LXdlaWdodD0iNzAwIiBsZXR0ZXItc3BhY2luZz0iMSI+0J/QoNCQ0JLQniDQmCDQmtCe0JzQn9Cb0JDQldCd0KE8L3RleHQ+PHRleHQgeD0iNjQiIHk9IjE2MCIgZmlsbD0iI2ZmZmZmZiIgZm9udC1mYW1pbHk9Ik9uZXN0LCBzYW5zLXNlcmlmIiBmb250LXNpemU9IjM0IiBmb250LXdlaWdodD0iODAwIj7Qn9GA0LDQstC+0LLQsNGPINC60LLQsNC70LjRhNC40LrQsNGG0LjRjzwvdGV4dD48dGV4dCB4PSI2NCIgeT0iMjAyIiBmaWxsPSIjOTRhM2I4IiBmb250LWZhbWlseT0iT25lc3QsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMzQiIGZvbnQtd2VpZ2h0PSI4MDAiPtGB0LzQsNGA0YIt0LrQvtC90YLRgNCw0LrRgtC+0LIg0LIg0KDQpDwvdGV4dD48bGluZSB4MT0iNjQiIHkxPSIyMzYiIHgyPSIzODAiIHkyPSIyMzYiIHN0cm9rZT0idXJsKCNhY2MzKSIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiLz48dGV4dCB4PSI2NCIgeT0iMjc0IiBmaWxsPSIjY2JkNWUxIiBmb250LWZhbWlseT0iT25lc3QsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTYiPtCh0YLQsNGC0YzRjyAzMDkg0JPQmiDQoNCkIOKAoiDQptCk0JAgKDI1OS3QpNCXKSDigKIg0JDRgNCx0LjRgtGA0LDQttC90LDRjyDQv9GA0LDQutGC0LjQutCwPC90ZXh0Pjwvc3ZnPg=='
    },
    {
      id: 'art-04',
      title: 'Архитектура надежных оракулов данных для распределенных реестров',
      description: 'Проектирование децентрализованной поставки рыночных данных, валютных курсов и фактов исполнения внешних обязательств в защищенные реестры.',
      author: 'Виктор Нестеров',
      authorRole: 'Инженер распределенных систем',
      authorInitials: 'ВН',
      date: '23 сентября 2026',
      readingTime: '10 мин',
      readingMinutes: 10,
      topic: 'oracles-and-data',
      topics: ['oracles-and-data', 'integrations-and-api'],
      targetAudience: 'architects-developers',
      format: 'case',
      complexity: 'hard',
      isDemo: true,
      keywords: ['Оракулы', 'Внешние данные', 'API', 'Консенсус', 'ЦФА'],
      coverImage: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA3ODAgNDQwIiB3aWR0aD0iNzgwIiBoZWlnaHQ9IjQ0MCI+PGRlZnM+PGxpbmVhckdyYWRpZW50IGlkPSJiZzQiIHgxPSIwIiB5MT0iMCIgeDI9IjEiIHkyPSIxIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjMGMxNDFlIi8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjMTMyNzNhIi8+PC9saW5lYXJHcmFkaWVudD48bGluZWFyR3JhZGllbnQgaWQ9ImFjYzQiIHgxPSIwIiB5MT0iMCIgeDI9IjEiIHkyPSIwIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjZjU5ZTBiIi8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjMzhiZGY4Ii8+PC9saW5lYXJHcmFkaWVudD48L2RlZnM+PHJlY3Qgd2lkdGg9Ijc4MCIgaGVpZ2h0PSI0NDAiIGZpbGw9InVybCgjYmc0KSIvPjxjaXJjbGUgY3g9IjYyMCIgY3k9IjE4MCIgcj0iMTMwIiBmaWxsPSJub25lIiBzdHJva2U9InJnYmEoMjQ1LDE1OCwxMSwwLjIpIiBzdHJva2Utd2lkdGg9IjEuNSIvPjxjaXJjbGUgY3g9IjU2MCIgY3k9IjE1MCIgcj0iMTQiIGZpbGw9IiNmNTllMGIiLz48Y2lyY2xlIGN4PSI2NzAiIGN5PSIxMzAiIHI9IjEwIiBmaWxsPSIjMzhiZGY4Ii8+PGNpcmNsZSBjeD0iNjQwIiBjeT0iMjQwIiByPSIxMiIgZmlsbD0iIzEwYjk4MSIvPjxsaW5lIHgxPSI1NjAiIHkxPSIxNTAiIHgyPSI2NzAiIHkyPSIxMzAiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjIpIiBzdHJva2Utd2lkdGg9IjEuNSIvPjxsaW5lIHgxPSI2NzAiIHkxPSIxMzAiIHgyPSI2NDAiIHkyPSIyNDAiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjIpIiBzdHJva2Utd2lkdGg9IjEuNSIvPjxsaW5lIHgxPSI2NDAiIHkxPSIyNDAiIHgyPSI1NjAiIHkyPSIxNTAiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjIpIiBzdHJva2Utd2lkdGg9IjEuNSIvPjxyZWN0IHg9IjY0IiB5PSI2NCIgd2lkdGg9IjE2MCIgaGVpZ2h0PSIzMiIgcng9IjE2IiBmaWxsPSJyZ2JhKDI0NSwxNTgsMTEsMC4xMikiIHN0cm9rZT0icmdiYSgyNDUsMTU4LDExLDAuMykiLz48dGV4dCB4PSI4NCIgeT0iODUiIGZpbGw9IiNmYmJmMjQiIGZvbnQtZmFtaWx5PSJPbmVzdCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxMyIgZm9udC13ZWlnaHQ9IjcwMCIgbGV0dGVyLXNwYWNpbmc9IjEiPtCe0KDQkNCa0KPQm9CrINCYINCU0JDQndCd0KvQlTwvdGV4dD48dGV4dCB4PSI2NCIgeT0iMTYwIiBmaWxsPSIjZmZmZmZmIiBmb250LWZhbWlseT0iT25lc3QsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMzQiIGZvbnQtd2VpZ2h0PSI4MDAiPtCf0L7RgdGC0LDQstC60LAg0LLQvdC10YjQvdC40YUg0LTQsNC90L3Ri9GFPC90ZXh0Pjx0ZXh0IHg9IjY0IiB5PSIyMDIiIGZpbGw9IiM5NGEzYjgiIGZvbnQtZmFtaWx5PSJPbmVzdCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIzNCIgZm9udC13ZWlnaHQ9IjgwMCI+0LTQu9GPINC60L7RgNC/0L7RgNCw0YLQuNCy0L3Ri9GFINGA0LXQtdGB0YLRgNC+0LI8L3RleHQ+PGxpbmUgeDE9IjY0IiB5MT0iMjM2IiB4Mj0iMzgwIiB5Mj0iMjM2IiBzdHJva2U9InVybCgjYWNjNCkiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIi8+PHRleHQgeD0iNjQiIHk9IjI3NCIgZmlsbD0iI2NiZDVlMSIgZm9udC1mYW1pbHk9Ik9uZXN0LCBzYW5zLXNlcmlmIiBmb250LXNpemU9IjE2Ij5CRlQt0LrQstC+0YDRg9C8IOKAoiDQkNCz0YDQtdCz0LDRhtC40Y8g0LzQtdC00LjQsNC90Ysg4oCiINCX0LDRidC40YLQsCDQvtGCINGB0LPQvtCy0L7RgNCwPC90ZXh0Pjwvc3ZnPg=='
    },
    {
      id: 'art-05',
      title: 'Оптимизация расхода газа при пакетной обработке транзакций в смарт-контрактах',
      description: 'Вопрос по лучшим практикам уменьшения storage writes и оптимизации циклов при массовых взаиморасчетах с контрагентами.',
      author: 'Дмитрий Кузнецов',
      authorRole: 'Tech Lead Blockchain Core',
      authorInitials: 'ДК',
      date: '22 сентября 2026',
      isoDate: '2026-09-22T08:00:00Z',
      readingTime: '4 мин',
      readingMinutes: 4,
      topic: 'smart-contracts-development',
      topics: ['smart-contracts-development'],
      targetAudience: 'architects-developers',
      format: 'question',
      complexity: 'none',
      isDemo: true,
      keywords: ['Вопрос', 'Solidity', 'Газ', 'Storage', 'Оптимизация'],
      coverImage: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA3ODAgNDQwIiB3aWR0aD0iNzgwIiBoZWlnaHQ9IjQ0MCI+PGRlZnM+PGxpbmVhckdyYWRpZW50IGlkPSJiZzUiIHgxPSIwIiB5MT0iMCIgeDI9IjEiIHkyPSIxIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjMTAwZTE4Ii8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjMWExNzMwIi8+PC9saW5lYXJHcmFkaWVudD48bGluZWFyR3JhZGllbnQgaWQ9ImFjYzUiIHgxPSIwIiB5MT0iMCIgeDI9IjEiIHkyPSIwIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjMzhkZmY4Ii8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjMTBiOTgxIi8+PC9saW5lYXJHcmFkaWVudD48L2RlZnM+PHJlY3Qgd2lkdGg9Ijc4MCIgaGVpZ2h0PSI0NDAiIGZpbGw9InVybCgjYmc1KSIvPjxyZWN0IHg9IjY0IiB5PSI2NCIgd2lkdGg9IjEzMCIgaGVpZ2h0PSIzMiIgcng9IjE2IiBmaWxsPSJyZ2JhKDU2LDE4OSwyNDgsMC4xMikiIHN0cm9rZT0icmdiYSg1NiwxODksMjQ4LDAuMykiLz48dGV4dCB4PSI4NCIgeT0iODUiIGZpbGw9IiMzOGRmZjgiIGZvbnQtZmFtaWx5PSJPbmVzdCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxMyIgZm9udC13ZWlnaHQ9IjcwMCIgbGV0dGVyLXNwYWNpbmc9IjEiPtCS0J7Qn9Cg0J7QoTwvdGV4dD48dGV4dCB4PSI2NCIgeT0iMTYwIiBmaWxsPSIjZmZmZmZmIiBmb250LWZhbWlseT0iT25lc3QsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMzQiIGZvbnQtd2VpZ2h0PSI4MDAiPtCe0L/RgtC40LzQuNC30LDRhtC40Y8g0LPQsNC30LA8L3RleHQ+PHRleHQgeD0iNjQiIHk9IjIwMiIgZmlsbD0iIzk0YTNiOCIgZm9udC1mYW1pbHk9Ik9uZXN0LCBzYW5zLXNlcmlmIiBmb250LXNpemU9IjM0IiBmb250LXdlaWdodD0iODAwIj7Qv9GA0Lgg0L/QsNC60LXRgtC90L7QuSDRgdCx0L7RgNC60LU8L3RleHQ+PC9zdmc+'
    }
  ];

  // --------------------------------------------------------------------------
  // 12b. Task 37: Entities (Clubs, Companies, Directions) & Subscriptions Modal
  // --------------------------------------------------------------------------
  function debounce(fn, ms) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  function getTopicTitle(topicId) {
    if (window.PublicationConfig && typeof window.PublicationConfig.getTopicById === 'function') {
      const t = window.PublicationConfig.getTopicById(topicId);
      if (t) return t.title;
    }
    return topicId;
  }

  function getInitials(str) {
    if (!str) return 'SC';
    const parts = str.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return str.slice(0, 2).toUpperCase();
  }

  function toggleSubscription(targetType, targetId, btnEl, title) {
    if (!currentUser) {
      openAuthModal('subscriptions');
      return;
    }
    if (btnEl) btnEl.disabled = true;
    fetch('/api/subscriptions/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_type: targetType,
        target_id: targetId,
        target_title: title || ''
      })
    })
      .then(function (res) {
        if (!res.ok) throw new Error('Status: ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (btnEl) btnEl.disabled = false;
        if (data && data.success) {
          const isSub = Boolean(data.isSubscribed);
          if (btnEl) {
            btnEl.classList.toggle('is-subscribed', isSub);
            btnEl.textContent = isSub ? 'Вы подписаны' : 'Подписаться';
          }
          showToast(isSub ? 'Подписка оформлена' : 'Подписка отменена');
          updateModalSubsCounts();
        }
      })
      .catch(function () {
        if (btnEl) btnEl.disabled = false;
        showToast('Не удалось обновить подписку', 'error');
      });
  }

  function toggleException(targetType, targetId, btnEl, title) {
    if (!currentUser) {
      openAuthModal('subscriptions');
      return;
    }
    if (btnEl) btnEl.disabled = true;
    fetch('/api/exceptions/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_type: targetType,
        target_id: targetId,
        target_title: title || ''
      })
    })
      .then(function (res) {
        if (!res.ok) throw new Error('Status: ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (btnEl) btnEl.disabled = false;
        if (data && data.success) {
          const isExc = Boolean(data.isExcluded);
          if (btnEl) {
            btnEl.classList.toggle('is-excluded', isExc);
            btnEl.textContent = isExc ? 'В исключениях' : 'Скрыть';
          }
          showToast(isExc ? 'Добавлено в исключения' : 'Удалено из исключений');
        }
      })
      .catch(function () {
        if (btnEl) btnEl.disabled = false;
        showToast('Не удалось обновить исключение', 'error');
      });
  }

  // --- CLUBS ---
  function loadClubs() {
    const grid = document.getElementById('clubsGrid');
    if (!grid) return;
    grid.innerHTML = '<div class="feed-skeleton-card" style="height: 140px; margin: 12px 0;"></div>';

    const searchInput = document.getElementById('clubsSearchInput');
    const dirFilter = document.getElementById('clubsDirectionFilter');
    const q = searchInput ? searchInput.value.trim() : '';
    const dir = dirFilter ? dirFilter.value : '';

    const params = new URLSearchParams();
    if (q) params.set('search', q);
    if (dir && dir !== 'all') params.set('direction', dir);

    fetch('/api/clubs?' + params.toString())
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.success) {
          renderClubsGrid(data.clubs || []);
        } else {
          grid.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Не удалось загрузить каталог клубов.</p></div>';
        }
      })
      .catch(function () {
        grid.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Ошибка при загрузке клубов.</p></div>';
      });
  }

  function renderClubsGrid(clubs) {
    const grid = document.getElementById('clubsGrid');
    if (!grid) return;
    grid.innerHTML = '';

    if (!clubs || clubs.length === 0) {
      grid.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Клубы не найдены. Вы можете создать первое сообщество.</p></div>';
      return;
    }

    clubs.forEach(function (club) {
      const card = document.createElement('div');
      card.className = 'entity-card';
      card.setAttribute('data-club-id', club.id);

      const avatarInitials = getInitials(club.title);
      const badgesHtml = (club.directions || []).map(function (d) {
        return '<span class="meta-badge topic-badge">' + escapeHtml(getTopicTitle(d)) + '</span>';
      }).join('');

      card.innerHTML =
        '<div class="entity-card-header">' +
          '<div class="entity-avatar">' + escapeHtml(avatarInitials) + '</div>' +
          '<div class="entity-card-title-wrap">' +
            '<h3 class="entity-card-title">' + escapeHtml(club.title) + '</h3>' +
            (badgesHtml ? '<div class="entity-card-badges">' + badgesHtml + '</div>' : '') +
          '</div>' +
        '</div>' +
        '<p class="entity-card-desc">' + escapeHtml(club.description) + '</p>' +
        '<div class="entity-card-meta">' +
          '<span class="entity-meta-item">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>' +
            '<span>' + pluralize(club.subscribersCount || 0, 'участник', 'участника', 'участников') + '</span>' +
          '</span>' +
          '<span class="entity-meta-item">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>' +
            '<span>' + pluralizePublications(club.articlesCount || 0) + '</span>' +
          '</span>' +
        '</div>' +
        '<div class="entity-card-actions">' +
          '<button type="button" class="btn btn-secondary btn-entity-open">В клуб</button>' +
          '<button type="button" class="btn btn-secondary btn-entity-sub ' + (club.isSubscribed ? 'is-subscribed' : '') + '">' +
            (club.isSubscribed ? 'Вы подписаны' : 'Подписаться') +
          '</button>' +
        '</div>';

      const openBtn = card.querySelector('.btn-entity-open');
      if (openBtn) {
        openBtn.addEventListener('click', function () { openClubDetail(club.id); });
      }
      const titleEl = card.querySelector('.entity-card-title');
      if (titleEl) {
        titleEl.style.cursor = 'pointer';
        titleEl.addEventListener('click', function () { openClubDetail(club.id); });
      }

      const subBtn = card.querySelector('.btn-entity-sub');
      if (subBtn) {
        subBtn.addEventListener('click', function () {
          toggleSubscription('club', club.id, subBtn, club.title);
        });
      }

      grid.appendChild(card);
    });
  }

  function openClubDetail(clubId) {
    state.activeClubId = clubId;
    state.tab = 'clubs';
    syncURL(false);
    updateSubnavTabsUI();

    const detailCard = document.getElementById('clubDetailCard');
    const articlesContainer = document.getElementById('clubArticlesContainer');
    if (detailCard) detailCard.innerHTML = '<div class="feed-skeleton-card" style="height: 160px;"></div>';
    if (articlesContainer) articlesContainer.innerHTML = '';

    fetch('/api/clubs/' + encodeURIComponent(clubId))
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.success && data.club) {
          renderClubDetailCard(data.club);
          loadClubArticles(clubId);
        } else {
          showToast('Клуб не найден', 'error');
          state.activeClubId = null;
          syncURL(false);
          updateSubnavTabsUI();
          loadClubs();
        }
      })
      .catch(function () {
        showToast('Ошибка при загрузке клуба', 'error');
      });
  }

  function renderClubDetailCard(club) {
    const detailCard = document.getElementById('clubDetailCard');
    if (!detailCard) return;

    const avatarInitials = getInitials(club.title);
    const badgesHtml = (club.directions || []).map(function (d) {
      return '<span class="meta-badge topic-badge">' + escapeHtml(getTopicTitle(d)) + '</span>';
    }).join('');

    detailCard.innerHTML =
      '<div class="entity-detail-top">' +
        '<div class="entity-avatar entity-avatar-large">' + escapeHtml(avatarInitials) + '</div>' +
        '<div class="entity-detail-info">' +
          '<h2 class="entity-detail-title">' + escapeHtml(club.title) + '</h2>' +
          (badgesHtml ? '<div class="entity-detail-badges">' + badgesHtml + '</div>' : '') +
          '<p class="entity-detail-desc">' + escapeHtml(club.description) + '</p>' +
          (club.rules ? '<div class="entity-detail-rules"><strong>Правила сообщества:</strong> ' + escapeHtml(club.rules) + '</div>' : '') +
          '<div class="entity-detail-stats">' +
            '<span class="entity-meta-item">' +
              '<strong>' + (club.subscribersCount || 0) + '</strong> ' +
              pluralize(club.subscribersCount || 0, 'подписчик', 'подписчика', 'подписчиков') +
            '</span>' +
            '<span class="entity-meta-item">' +
              '<strong>' + (club.articlesCount || 0) + '</strong> ' +
              pluralize(club.articlesCount || 0, 'статья', 'статьи', 'статей') +
            '</span>' +
          '</div>' +
          '<div class="entity-detail-actions" style="margin-top: 14px; display: flex; gap: 10px; flex-wrap: wrap;">' +
            '<button type="button" class="btn btn-secondary btn-club-sub ' + (club.isSubscribed ? 'is-subscribed' : '') + '">' +
              (club.isSubscribed ? 'Вы подписаны' : 'Подписаться') +
            '</button>' +
            '<a href="editor.html?clubId=' + encodeURIComponent(club.id) + '&clubTitle=' + encodeURIComponent(club.title) + '" class="btn btn-primary btn-club-write">' +
              '<span>Написать в клуб</span>' +
            '</a>' +
          '</div>' +
        '</div>' +
      '</div>';

    const subBtn = detailCard.querySelector('.btn-club-sub');
    if (subBtn) {
      subBtn.addEventListener('click', function () {
        toggleSubscription('club', club.id, subBtn, club.title);
      });
    }
  }

  function loadClubArticles(clubId) {
    const container = document.getElementById('clubArticlesContainer');
    if (!container) return;
    container.innerHTML = '<div class="feed-skeleton-card" style="height: 120px;"></div>';

    fetch('/api/articles?club=' + encodeURIComponent(clubId))
      .then(function (res) { return res.json(); })
      .then(function (data) {
        container.innerHTML = '';
        if (data && data.success && data.articles && data.articles.length > 0) {
          data.articles.forEach(function (art) {
            container.appendChild(createCardElement(art));
          });
        } else {
          container.innerHTML =
            '<div class="feed-empty-state">' +
              '<p class="empty-state-desc">В этом клубе пока нет опубликованных материалов. Станьте первым автором!</p>' +
              '<a href="editor.html?clubId=' + encodeURIComponent(clubId) + '" class="btn btn-primary" style="margin-top: 12px;">Написать первую публикацию</a>' +
            '</div>';
        }
      })
      .catch(function () {
        container.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Ошибка при загрузке публикаций клуба.</p></div>';
      });
  }

  // --- COMPANIES ---
  function loadCompanies(subtab) {
    state.companiesSubtab = subtab || 'catalog';

    const btnCat = document.getElementById('btnCompaniesTabCatalog');
    const btnArt = document.getElementById('btnCompaniesTabArticles');
    const catGrid = document.getElementById('companiesGrid');
    const artGrid = document.getElementById('companiesArticlesGrid');
    const toolbar = document.getElementById('companiesToolbar');

    if (btnCat) btnCat.classList.toggle('active', state.companiesSubtab === 'catalog');
    if (btnArt) btnArt.classList.toggle('active', state.companiesSubtab === 'articles');

    if (state.companiesSubtab === 'catalog') {
      if (catGrid) catGrid.style.display = 'grid';
      if (toolbar) toolbar.style.display = 'flex';
      if (artGrid) artGrid.style.display = 'none';

      const searchInput = document.getElementById('companiesSearchInput');
      const q = searchInput ? searchInput.value.trim() : '';

      if (catGrid) catGrid.innerHTML = '<div class="feed-skeleton-card" style="height: 140px; margin: 12px 0;"></div>';

      fetch('/api/companies' + (q ? '?search=' + encodeURIComponent(q) : ''))
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (data && data.success) {
            renderCompaniesGrid(data.companies || []);
          } else {
            if (catGrid) catGrid.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Не удалось загрузить компании.</p></div>';
          }
        })
        .catch(function () {
          if (catGrid) catGrid.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Ошибка при загрузке компаний.</p></div>';
        });
    } else {
      if (catGrid) catGrid.style.display = 'none';
      if (toolbar) toolbar.style.display = 'none';
      if (artGrid) artGrid.style.display = 'block';

      if (artGrid) artGrid.innerHTML = '<div class="feed-skeleton-card" style="height: 140px; margin: 12px 0;"></div>';

      fetch('/api/articles?isCompany=true')
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (artGrid) artGrid.innerHTML = '';
          const articles = (data && Array.isArray(data.articles)) ? data.articles : [];
          if (articles.length > 0) {
            articles.forEach(function (art) {
              artGrid.appendChild(createCardElement(art));
            });
          } else {
            if (artGrid) {
              artGrid.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Пока нет публикаций от технологических компаний.</p></div>';
            }
          }
        })
        .catch(function () {
          if (artGrid) artGrid.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Ошибка при загрузке публикаций компаний.</p></div>';
        });
    }
  }

  function renderCompaniesGrid(companies) {
    const grid = document.getElementById('companiesGrid');
    if (!grid) return;
    grid.innerHTML = '';

    if (!companies || companies.length === 0) {
      grid.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Блоги компаний не найдены. Создайте первый корпоративный блог.</p></div>';
      return;
    }

    companies.forEach(function (comp) {
      const card = document.createElement('div');
      card.className = 'entity-card company-card';
      card.setAttribute('data-company-id', comp.id);

      const avatarInitials = getInitials(comp.name);
      const avatarHtml = comp.logo
        ? '<img src="' + escapeHtml(comp.logo) + '" alt="' + escapeHtml(comp.name) + '" class="entity-avatar entity-avatar-img">'
        : '<div class="entity-avatar">' + escapeHtml(avatarInitials) + '</div>';

      const verifiedIcon = comp.isVerified
        ? '<span class="verified-icon" title="Верифицированная компания"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg></span>'
        : '';

      card.innerHTML =
        '<div class="entity-card-header">' +
          avatarHtml +
          '<div class="entity-card-title-wrap">' +
            '<div style="display: flex; align-items: center; gap: 6px;">' +
              '<h3 class="entity-card-title">' + escapeHtml(comp.name) + '</h3>' +
              verifiedIcon +
            '</div>' +
            (comp.specialization ? '<span class="entity-card-spec">' + escapeHtml(comp.specialization) + '</span>' : '') +
          '</div>' +
        '</div>' +
        '<p class="entity-card-desc">' + escapeHtml(comp.description) + '</p>' +
        (comp.website ? '<div class="entity-card-website"><a href="' + escapeHtml(comp.website) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(comp.website) + '</a></div>' : '') +
        '<div class="entity-card-meta">' +
          '<span class="entity-meta-item">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>' +
            '<span>' + pluralize(comp.subscribersCount || 0, 'подписчик', 'подписчика', 'подписчиков') + '</span>' +
          '</span>' +
          '<span class="entity-meta-item">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>' +
            '<span>' + pluralizePublications(comp.articlesCount || 0) + '</span>' +
          '</span>' +
        '</div>' +
        '<div class="entity-card-actions">' +
          '<button type="button" class="btn btn-secondary btn-entity-open">О блоге</button>' +
          '<button type="button" class="btn btn-secondary btn-entity-sub ' + (comp.isSubscribed ? 'is-subscribed' : '') + '">' +
            (comp.isSubscribed ? 'Вы подписаны' : 'Подписаться') +
          '</button>' +
        '</div>';

      const openBtn = card.querySelector('.btn-entity-open');
      if (openBtn) {
        openBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          openCompanyDetail(comp.id);
        });
      }
      const titleEl = card.querySelector('.entity-card-title');
      if (titleEl) {
        titleEl.style.cursor = 'pointer';
        titleEl.addEventListener('click', function (e) {
          e.stopPropagation();
          openCompanyDetail(comp.id);
        });
      }

      const subBtn = card.querySelector('.btn-entity-sub');
      if (subBtn) {
        subBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          toggleSubscription('company', comp.id, subBtn, comp.name);
        });
      }

      card.addEventListener('click', function (e) {
        if (e.target.closest('button') || e.target.closest('a')) return;
        openCompanyDetail(comp.id);
      });

      grid.appendChild(card);
    });
  }

  function openCompanyDetail(companyId) {
    state.activeCompanyId = companyId;
    state.tab = 'companies';
    syncURL(false);
    updateSubnavTabsUI();

    const detailCard = document.getElementById('companyDetailCard');
    const articlesContainer = document.getElementById('companyArticlesContainer');
    if (detailCard) detailCard.innerHTML = '<div class="feed-skeleton-card" style="height: 160px;"></div>';
    if (articlesContainer) articlesContainer.innerHTML = '';

    fetch('/api/companies/' + encodeURIComponent(companyId))
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.success && data.company) {
          renderCompanyDetailCard(data.company);
          loadCompanyArticles(companyId);
        } else {
          showToast('Компания не найдена', 'error');
          state.activeCompanyId = null;
          syncURL(false);
          updateSubnavTabsUI();
          loadCompanies('catalog');
        }
      })
      .catch(function () {
        showToast('Ошибка при загрузке компании', 'error');
      });
  }

  function renderCompanyDetailCard(comp) {
    const detailCard = document.getElementById('companyDetailCard');
    if (!detailCard) return;

    const avatarInitials = getInitials(comp.name);
    const avatarHtml = comp.logo
      ? '<img src="' + escapeHtml(comp.logo) + '" alt="' + escapeHtml(comp.name) + '" class="entity-avatar entity-avatar-large entity-avatar-img">'
      : '<div class="entity-avatar entity-avatar-large">' + escapeHtml(avatarInitials) + '</div>';
    const verifiedIcon = comp.isVerified
      ? '<span class="verified-icon" title="Верифицированная компания"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg></span>'
      : '';

    const writeBtnHtml = comp.canPublish
      ? '<a href="editor.html?companyId=' + encodeURIComponent(comp.id) + '" class="btn btn-primary btn-comp-write" style="margin-left: 8px;">Написать от компании</a>'
      : '';

    detailCard.innerHTML =
      '<div class="entity-detail-top">' +
        avatarHtml +
        '<div class="entity-detail-info">' +
          '<div style="display: flex; align-items: center; gap: 8px;">' +
            '<h2 class="entity-detail-title">' + escapeHtml(comp.name) + '</h2>' +
            verifiedIcon +
          '</div>' +
          (comp.specialization ? '<div class="entity-detail-spec">' + escapeHtml(comp.specialization) + '</div>' : '') +
          '<p class="entity-detail-desc">' + escapeHtml(comp.description) + '</p>' +
          (comp.website ? '<div class="entity-detail-website"><a href="' + escapeHtml(comp.website) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(comp.website) + '</a></div>' : '') +
          '<div class="entity-detail-stats">' +
            '<span class="entity-meta-item">' +
              '<strong>' + (comp.subscribersCount || 0) + '</strong> ' +
              pluralize(comp.subscribersCount || 0, 'подписчик', 'подписчика', 'подписчиков') +
            '</span>' +
            '<span class="entity-meta-item">' +
              '<strong>' + (comp.articlesCount || 0) + '</strong> ' +
              pluralize(comp.articlesCount || 0, 'статья', 'статьи', 'статей') +
            '</span>' +
          '</div>' +
          '<div class="entity-detail-actions" style="margin-top: 14px;">' +
            '<button type="button" class="btn btn-secondary btn-comp-sub ' + (comp.isSubscribed ? 'is-subscribed' : '') + '">' +
              (comp.isSubscribed ? 'Вы подписаны' : 'Подписаться') +
            '</button>' +
            writeBtnHtml +
          '</div>' +
        '</div>' +
      '</div>';

    const subBtn = detailCard.querySelector('.btn-comp-sub');
    if (subBtn) {
      subBtn.addEventListener('click', function () {
        toggleSubscription('company', comp.id, subBtn, comp.name);
      });
    }
  }

  function loadCompanyArticles(companyId) {
    const container = document.getElementById('companyArticlesContainer');
    if (!container) return;
    container.innerHTML = '<div class="feed-skeleton-card" style="height: 120px;"></div>';

    fetch('/api/articles?company=' + encodeURIComponent(companyId))
      .then(function (res) { return res.json(); })
      .then(function (data) {
        container.innerHTML = '';
        if (data && data.success && data.articles && data.articles.length > 0) {
          data.articles.forEach(function (art) {
            container.appendChild(createCardElement(art));
          });
        } else {
          container.innerHTML =
            '<div class="feed-empty-state">' +
              '<p class="empty-state-desc">У этой компании пока нет опубликованных материалов.</p>' +
            '</div>';
        }
      })
      .catch(function () {
        container.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Ошибка при загрузке публикаций компании.</p></div>';
      });
  }

  // --- DIRECTIONS ---
  function loadDirections() {
    const grid = document.getElementById('directionsGrid');
    if (!grid) return;
    grid.innerHTML = '<div class="feed-skeleton-card" style="height: 140px; margin: 12px 0;"></div>';

    const searchInput = document.getElementById('directionsSearchInput');
    const q = searchInput ? searchInput.value.trim() : '';

    fetch('/api/directions' + (q ? '?search=' + encodeURIComponent(q) : ''))
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.success) {
          renderDirectionsGrid(data.directions || []);
        } else {
          grid.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Не удалось загрузить темы.</p></div>';
        }
      })
      .catch(function () {
        grid.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Ошибка при загрузке тем.</p></div>';
      });
  }

  const TOPIC_ICONS = {
    'pksc-architecture': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/></svg>',
    'smart-contracts-development': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
    'business-logic-deals': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>',
    'testing-and-quality': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
    'testing-audits': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
    'information-security': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    'security-cryptography': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    'audit-and-verification': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><path d="m11 8 0 6"/><path d="m8 11 6 0"/></svg>',
    'law-and-compliance': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/></svg>',
    'oracles-and-data': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"/><path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"/><circle cx="12" cy="12" r="2"/><path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"/><path d="M19.1 4.9C23 8.8 23 15.1 19.1 19"/></svg>',
    'integrations-and-api': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
    'digital-ruble-payments': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9 7h5a3 3 0 0 1 0 6H9v4"/><path d="M7 13h6"/></svg>',
    'tokenomics-mechanics': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h2v4"/><path d="m14 13 2 4"/></svg>',
    'lifecycle-versioning': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" y1="9" x2="6" y2="21"/></svg>',
    'infrastructure-operations': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>',
    'infrastructure-devops': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>',
    'business-cases-adoption': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg>',
    'zk-privacy': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/><line x1="3" y1="3" x2="21" y2="21"/></svg>',
    'cross-chain-bridges': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><path d="M6 14V9a3 3 0 0 1 3-3h5"/><path d="m15 10 3-3-3-3"/></svg>',
    'evm-internals': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>',
    'daos-governance': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    'defi-protocols': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>',
    'developer-tools': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>',
    'analytics-data': '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>'
  };

  const DEFAULT_TOPIC_ICON = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>';

  function renderDirectionsGrid(directions) {
    const grid = document.getElementById('directionsGrid');
    if (!grid) return;
    grid.innerHTML = '';

    if (!directions || directions.length === 0) {
      grid.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Темы не найдены.</p></div>';
      return;
    }

    directions.forEach(function (dir) {
      const card = document.createElement('div');
      card.className = 'entity-card direction-card';
      card.setAttribute('data-direction-id', dir.id);

      const iconSvg = TOPIC_ICONS[dir.id] || DEFAULT_TOPIC_ICON;

      card.innerHTML =
        '<div class="entity-card-header">' +
          '<div class="entity-avatar direction-avatar">' +
            iconSvg +
          '</div>' +
          '<div class="entity-card-title-wrap">' +
            '<h3 class="entity-card-title">' + escapeHtml(dir.title) + '</h3>' +
            '<span class="entity-meta-item">' +
              '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>' +
              '<span>' + pluralizePublications(dir.articlesCount || dir.count || 0) + '</span>' +
            '</span>' +
          '</div>' +
        '</div>' +
        '<p class="entity-card-desc">' + escapeHtml(dir.description) + '</p>' +
        '<div class="entity-card-meta">' +
          '<span class="entity-meta-item">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>' +
            '<span>' + pluralize(dir.subscribersCount || 0, 'подписчик', 'подписчика', 'подписчиков') + '</span>' +
          '</span>' +
        '</div>' +
        '<div class="entity-card-actions">' +
          '<button type="button" class="btn btn-secondary btn-direction-feed">К публикациям</button>' +
          '<button type="button" class="btn btn-secondary btn-direction-sub ' + (dir.isSubscribed ? 'is-subscribed' : '') + '">' +
            (dir.isSubscribed ? 'Вы подписаны' : 'Подписаться') +
          '</button>' +
        '</div>';

      const feedBtn = card.querySelector('.btn-direction-feed');
      if (feedBtn) {
        feedBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          state.filters.topics = [dir.id];
          state.tab = 'all';
          syncURL(false);
          switchTab('all');
        });
      }

      const subBtn = card.querySelector('.btn-direction-sub');
      if (subBtn) {
        subBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          toggleSubscription('topic', dir.id, subBtn, dir.title);
        });
      }

      card.addEventListener('click', function (e) {
        if (e.target.closest('button') || e.target.closest('a')) return;
        state.filters.topics = [dir.id];
        state.tab = 'all';
        syncURL(false);
        switchTab('all');
      });

      grid.appendChild(card);
    });
  }

  // --- SUBSCRIPTIONS MODAL (5 TABS) ---
  let activeSubsModalTab = 'author';

  function openSubscriptionsModal(initialTab) {
    if (!currentUser) {
      openAuthModal('subscriptions');
      return;
    }
    const modal = document.getElementById('subscriptionsModal');
    if (!modal) return;

    activeSubsModalTab = initialTab || 'author';
    setModalSubsTab(activeSubsModalTab);

    const searchInput = document.getElementById('subsSearchInput');
    if (searchInput) searchInput.value = '';

    modal.style.display = 'flex';
    document.body.classList.add('feed-modal-open');
    loadModalSubsList();
    updateModalSubsCounts();
  }

  function closeSubscriptionsModal() {
    const modal = document.getElementById('subscriptionsModal');
    if (!modal) return;
    modal.style.display = 'none';
    document.body.classList.remove('feed-modal-open');
    if (state.tab === 'subscriptions' || state.tab === 'my') {
      fetchFeed(true);
    }
  }

  function setModalSubsTab(type) {
    activeSubsModalTab = type;
    const tabBtns = document.querySelectorAll('.subs-tab-btn');
    tabBtns.forEach(function (btn) {
      const isAct = btn.getAttribute('data-type') === type;
      btn.classList.toggle('active', isAct);
      btn.setAttribute('aria-selected', isAct ? 'true' : 'false');
    });

    const searchInput = document.getElementById('subsSearchInput');
    if (searchInput) {
      const placeholders = {
        author: 'Поиск по авторам...',
        club: 'Поиск по клубам...',
        company: 'Поиск по компаниям...',
        topic: 'Поиск по направлениям...',
        tag: 'Поиск по тегам...'
      };
      searchInput.placeholder = placeholders[type] || 'Поиск в каталоге...';
    }

    loadModalSubsList();
  }

  function updateModalSubsCounts() {
    fetch('/api/subscriptions')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.success && data.subscriptions) {
          const subs = data.subscriptions;
          const aCount = document.getElementById('subsAuthorsCount');
          const clCount = document.getElementById('subsClubsCount');
          const cpCount = document.getElementById('subsCompaniesCount');
          const tpCount = document.getElementById('subsTopicsCount');
          const tgCount = document.getElementById('subsTagsCount');

          if (aCount) aCount.textContent = (subs.authors || []).length;
          if (clCount) clCount.textContent = (subs.clubs || []).length;
          if (cpCount) cpCount.textContent = (subs.companies || []).length;
          if (tpCount) tpCount.textContent = (subs.topics || []).length;
          if (tgCount) tgCount.textContent = (subs.tags || []).length;
        }
      })
      .catch(function () {});
  }

  function loadModalSubsList() {
    const container = document.getElementById('subsListContainer');
    if (!container) return;
    container.innerHTML = '<div class="feed-skeleton-card" style="height: 60px; margin: 8px 0;"></div>';

    const searchInput = document.getElementById('subsSearchInput');
    const q = searchInput ? searchInput.value.trim() : '';

    const params = new URLSearchParams();
    params.set('type', activeSubsModalTab);
    if (q) params.set('search', q);
    params.set('limit', '50');

    fetch('/api/subscriptions/entities?' + params.toString())
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.success) {
          renderModalSubsList(data.items || []);
        } else {
          container.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Не удалось загрузить данные.</p></div>';
        }
      })
      .catch(function () {
        container.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Ошибка соединения.</p></div>';
      });
  }

  function renderModalSubsList(items) {
    const container = document.getElementById('subsListContainer');
    if (!container) return;
    container.innerHTML = '';

    if (!items || items.length === 0) {
      container.innerHTML = '<div class="feed-empty-state"><p class="empty-state-desc">Ничего не найдено.</p></div>';
      return;
    }

    items.forEach(function (item) {
      const row = document.createElement('div');
      row.className = 'subs-modal-item';

      const title = item.title || item.name || item.id;
      const displayTitle = (activeSubsModalTab === 'tag') ? ('#' + title.replace(/^#/, '')) : title;
      const subtitle = item.role || item.specialization || item.description ||
        (item.articlesCount !== undefined ? pluralizePublications(item.articlesCount) :
        (item.count !== undefined ? pluralizePublications(item.count) : ''));

      const avatarInitials = getInitials(title);

      row.innerHTML =
        '<div class="subs-item-main">' +
          '<div class="author-avatar subs-author-avatar">' + escapeHtml(avatarInitials) + '</div>' +
          '<div class="subs-item-info">' +
            '<span class="subs-item-title">' + escapeHtml(displayTitle) + '</span>' +
            (subtitle ? '<span class="subs-item-sub">' + escapeHtml(subtitle) + '</span>' : '') +
          '</div>' +
        '</div>' +
        '<div class="subs-item-actions" style="display: flex; gap: 8px;">' +
          '<button type="button" class="btn btn-secondary subs-toggle-btn ' + (item.isSubscribed ? 'is-subscribed' : '') + '">' +
            (item.isSubscribed ? 'Вы подписаны' : 'Подписаться') +
          '</button>' +
          '<button type="button" class="btn btn-secondary subs-toggle-exc-btn ' + (item.isExcluded ? 'is-excluded' : '') + '">' +
            (item.isExcluded ? 'В исключениях' : 'Скрыть') +
          '</button>' +
        '</div>';

      const subBtn = row.querySelector('.subs-toggle-btn');
      if (subBtn) {
        subBtn.addEventListener('click', function () {
          toggleSubscription(activeSubsModalTab, item.id, subBtn, title);
        });
      }

      const excBtn = row.querySelector('.subs-toggle-exc-btn');
      if (excBtn) {
        excBtn.addEventListener('click', function () {
          toggleException(activeSubsModalTab, item.id, excBtn, title);
        });
      }

      container.appendChild(row);
    });
  }

  // --- CREATE CLUB MODAL ---
  function openCreateClubModal() {
    if (!currentUser) {
      openAuthModal('create_club');
      return;
    }
    const modal = document.getElementById('createClubModal');
    if (!modal) return;

    // Reset form
    const form = document.getElementById('createClubForm');
    if (form) form.reset();
    const err = document.getElementById('createClubError');
    if (err) { err.style.display = 'none'; err.textContent = ''; }

    // Populate directions container
    const dirContainer = document.getElementById('newClubDirectionsContainer');
    if (dirContainer && (!dirContainer.children || dirContainer.children.length === 0)) {
      fetch('/api/directions')
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (data && data.success && data.directions) {
            dirContainer.innerHTML = '';
            data.directions.forEach(function (d) {
              const label = document.createElement('label');
              label.style.display = 'inline-flex';
              label.style.alignItems = 'center';
              label.style.gap = '6px';
              label.style.padding = '4px 10px';
              label.style.borderRadius = '16px';
              label.style.background = 'var(--bg-secondary)';
              label.style.fontSize = '0.8rem';
              label.style.cursor = 'pointer';
              label.innerHTML = '<input type="checkbox" name="clubDirection" value="' + escapeHtml(d.id) + '"><span>' + escapeHtml(d.title) + '</span>';
              dirContainer.appendChild(label);
            });
          }
        })
        .catch(function () {});
    }

    modal.style.display = 'flex';
    document.body.classList.add('feed-modal-open');
  }

  function closeCreateClubModal() {
    const modal = document.getElementById('createClubModal');
    if (!modal) return;
    modal.style.display = 'none';
    document.body.classList.remove('feed-modal-open');
  }

  function submitCreateClub() {
    const titleInput = document.getElementById('newClubTitle');
    const descInput = document.getElementById('newClubDescription');
    const rulesInput = document.getElementById('newClubRules');
    const tagsInput = document.getElementById('newClubTags');
    const err = document.getElementById('createClubError');
    const submitBtn = document.getElementById('btnSubmitCreateClub');

    const title = titleInput ? titleInput.value.trim() : '';
    const description = descInput ? descInput.value.trim() : '';
    const rules = rulesInput ? rulesInput.value.trim() : '';
    const tagsRaw = tagsInput ? tagsInput.value.trim() : '';

    if (!title) {
      if (err) { err.style.display = 'block'; err.textContent = 'Укажите название клуба'; }
      if (titleInput) titleInput.focus();
      return;
    }
    if (!description) {
      if (err) { err.style.display = 'block'; err.textContent = 'Укажите описание клуба'; }
      if (descInput) descInput.focus();
      return;
    }

    const checkedDirs = Array.from(document.querySelectorAll('input[name="clubDirection"]:checked')).map(function (inp) {
      return inp.value;
    });
    const tags = tagsRaw.split(',').map(function (t) { return t.trim(); }).filter(Boolean);

    if (submitBtn) submitBtn.disabled = true;

    fetch('/api/clubs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: title,
        description: description,
        rules: rules,
        directions: checkedDirs,
        tags: tags
      })
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (d) { throw new Error(d.error || 'Ошибка при создании клуба'); });
        }
        return res.json();
      })
      .then(function (data) {
        if (submitBtn) submitBtn.disabled = false;
        if (data && data.success && data.club) {
          closeCreateClubModal();
          showToast('Клуб успешно создан!');
          openClubDetail(data.club.id);
        }
      })
      .catch(function (e) {
        if (submitBtn) submitBtn.disabled = false;
        if (err) { err.style.display = 'block'; err.textContent = e.message; }
      });
  }

  // --- CREATE COMPANY MODAL ---
  function openCreateCompanyModal() {
    if (!currentUser) {
      openAuthModal('create_company');
      return;
    }
    const modal = document.getElementById('createCompanyModal');
    if (!modal) return;

    const form = document.getElementById('createCompanyForm');
    if (form) form.reset();
    const err = document.getElementById('createCompanyError');
    if (err) { err.style.display = 'none'; err.textContent = ''; }

    modal.style.display = 'flex';
    document.body.classList.add('feed-modal-open');
  }

  function closeCreateCompanyModal() {
    const modal = document.getElementById('createCompanyModal');
    if (!modal) return;
    modal.style.display = 'none';
    document.body.classList.remove('feed-modal-open');
  }

  function submitCreateCompany() {
    const nameInput = document.getElementById('newCompanyName');
    const descInput = document.getElementById('newCompanyDescription');
    const specInput = document.getElementById('newCompanyIndustry');
    const webInput = document.getElementById('newCompanyWebsite');
    const err = document.getElementById('createCompanyError');
    const submitBtn = document.getElementById('btnSubmitCreateCompany');

    const name = nameInput ? nameInput.value.trim() : '';
    const description = descInput ? descInput.value.trim() : '';
    const specialization = specInput ? specInput.value.trim() : '';
    const website = webInput ? webInput.value.trim() : '';

    if (!name) {
      if (err) { err.style.display = 'block'; err.textContent = 'Укажите название компании'; }
      if (nameInput) nameInput.focus();
      return;
    }
    if (!description) {
      if (err) { err.style.display = 'block'; err.textContent = 'Укажите описание деятельности'; }
      if (descInput) descInput.focus();
      return;
    }
    if (!specialization) {
      if (err) { err.style.display = 'block'; err.textContent = 'Укажите отраслевое направление'; }
      if (specInput) specInput.focus();
      return;
    }

    if (submitBtn) submitBtn.disabled = true;

    fetch('/api/companies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name,
        description: description,
        specialization: specialization,
        website: website
      })
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (d) { throw new Error(d.error || 'Ошибка при регистрации компании'); });
        }
        return res.json();
      })
      .then(function (data) {
        if (submitBtn) submitBtn.disabled = false;
        if (data && data.success && data.company) {
          closeCreateCompanyModal();
          showToast('Компания успешно зарегистрирована!');
          openCompanyDetail(data.company.id);
        }
      })
      .catch(function (e) {
        if (submitBtn) submitBtn.disabled = false;
        if (err) { err.style.display = 'block'; err.textContent = e.message; }
      });
  }

  // --- INITIALIZE ALL TASK 37 CONTROLS ---
  function initTask37Entities() {
    // Back buttons
    const btnBackToClubs = document.getElementById('btnBackToClubs');
    if (btnBackToClubs) {
      btnBackToClubs.addEventListener('click', function () {
        state.activeClubId = null;
        syncURL(false);
        switchTab('clubs');
      });
    }

    const btnBackToCompanies = document.getElementById('btnBackToCompanies');
    if (btnBackToCompanies) {
      btnBackToCompanies.addEventListener('click', function () {
        state.activeCompanyId = null;
        syncURL(false);
        switchTab('companies');
      });
    }

    // Companies Subtabs
    const btnCompaniesTabCatalog = document.getElementById('btnCompaniesTabCatalog');
    const btnCompaniesTabArticles = document.getElementById('btnCompaniesTabArticles');
    if (btnCompaniesTabCatalog) {
      btnCompaniesTabCatalog.addEventListener('click', function () {
        loadCompanies('catalog');
      });
    }
    if (btnCompaniesTabArticles) {
      btnCompaniesTabArticles.addEventListener('click', function () {
        loadCompanies('articles');
      });
    }

    // Search and filters
    const clubsSearchInput = document.getElementById('clubsSearchInput');
    if (clubsSearchInput) {
      clubsSearchInput.addEventListener('input', debounce(function () {
        loadClubs();
      }, 300));
    }
    const clubsDirFilter = document.getElementById('clubsDirectionFilter');
    if (clubsDirFilter) {
      clubsDirFilter.addEventListener('change', function () {
        loadClubs();
      });
      // Populate directions in select
      fetch('/api/directions')
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (data && data.success && data.directions) {
            data.directions.forEach(function (d) {
              const opt = document.createElement('option');
              opt.value = d.id;
              opt.textContent = d.title;
              clubsDirFilter.appendChild(opt);
            });
          }
        })
        .catch(function () {});
    }

    const companiesSearchInput = document.getElementById('companiesSearchInput');
    if (companiesSearchInput) {
      companiesSearchInput.addEventListener('input', debounce(function () {
        loadCompanies('catalog');
      }, 300));
    }

    const directionsSearchInput = document.getElementById('directionsSearchInput');
    if (directionsSearchInput) {
      directionsSearchInput.addEventListener('input', debounce(function () {
        loadDirections();
      }, 300));
    }

    // Modals: Create Club
    const btnOpenCreateClub = document.getElementById('btnOpenCreateClub');
    if (btnOpenCreateClub) {
      btnOpenCreateClub.addEventListener('click', openCreateClubModal);
    }
    const btnCloseCreateClubModalEl = document.getElementById('btnCloseCreateClubModal');
    if (btnCloseCreateClubModalEl) {
      btnCloseCreateClubModalEl.addEventListener('click', closeCreateClubModal);
    }
    const btnCancelCreateClub = document.getElementById('btnCancelCreateClub');
    if (btnCancelCreateClub) {
      btnCancelCreateClub.addEventListener('click', closeCreateClubModal);
    }
    const btnSubmitCreateClubEl = document.getElementById('btnSubmitCreateClub');
    if (btnSubmitCreateClubEl) {
      btnSubmitCreateClubEl.addEventListener('click', submitCreateClub);
    }

    // Modals: Create Company
    const btnOpenCreateCompany = document.getElementById('btnOpenCreateCompany');
    if (btnOpenCreateCompany) {
      btnOpenCreateCompany.addEventListener('click', openCreateCompanyModal);
    }
    const btnCloseCreateCompanyModalEl = document.getElementById('btnCloseCreateCompanyModal');
    if (btnCloseCreateCompanyModalEl) {
      btnCloseCreateCompanyModalEl.addEventListener('click', closeCreateCompanyModal);
    }
    const btnCancelCreateCompany = document.getElementById('btnCancelCreateCompany');
    if (btnCancelCreateCompany) {
      btnCancelCreateCompany.addEventListener('click', closeCreateCompanyModal);
    }
    const btnSubmitCreateCompanyEl = document.getElementById('btnSubmitCreateCompany');
    if (btnSubmitCreateCompanyEl) {
      btnSubmitCreateCompanyEl.addEventListener('click', submitCreateCompany);
    }

    // Modals: Subscriptions
    const btnCloseSubsModalEl = document.getElementById('btnCloseSubsModal');
    if (btnCloseSubsModalEl) {
      btnCloseSubsModalEl.addEventListener('click', closeSubscriptionsModal);
    }

    const subsModalTabBtns = document.querySelectorAll('.subs-tab-btn');
    subsModalTabBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        const type = btn.getAttribute('data-type');
        if (type) setModalSubsTab(type);
      });
    });

    const subsSearchInput = document.getElementById('subsSearchInput');
    if (subsSearchInput) {
      subsSearchInput.addEventListener('input', debounce(function () {
        loadModalSubsList();
      }, 300));
    }

    // Backdrop clicks to close modals
    const createClubModalEl = document.getElementById('createClubModal');
    if (createClubModalEl) {
      createClubModalEl.addEventListener('click', function (e) {
        if (e.target === createClubModalEl) closeCreateClubModal();
      });
    }
    const createCompanyModalEl = document.getElementById('createCompanyModal');
    if (createCompanyModalEl) {
      createCompanyModalEl.addEventListener('click', function (e) {
        if (e.target === createCompanyModalEl) closeCreateCompanyModal();
      });
    }
    const subscriptionsModalEl = document.getElementById('subscriptionsModal');
    if (subscriptionsModalEl) {
      subscriptionsModalEl.addEventListener('click', function (e) {
        if (e.target === subscriptionsModalEl) closeSubscriptionsModal();
      });
    }
  }

  // --------------------------------------------------------------------------
  // 12b. Task 38 Community MVP Features (Navigation, Questions, Notifications)
  // --------------------------------------------------------------------------
  function initTask38CommunityFeatures() {
    // 1. «Создать +» Dropdown in subnav
    const btnCreate = document.getElementById('btnCreateDropdown');
    const createMenu = document.getElementById('feedCreateMenu');
    const createWrap = document.getElementById('feedCreateDropdownWrap');
    if (btnCreate && createMenu) {
      btnCreate.addEventListener('click', function (e) {
        e.stopPropagation();
        const isOpen = createMenu.style.display !== 'none';
        createMenu.style.display = isOpen ? 'none' : 'flex';
        btnCreate.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
      });

      document.addEventListener('click', function (e) {
        if (createWrap && !createWrap.contains(e.target)) {
          createMenu.style.display = 'none';
          btnCreate.setAttribute('aria-expanded', 'false');
        }
      });
    }

    // 2. Questions Status Pills in feed toolbar
    const statusPillsWrap = document.getElementById('feedQuestionsStatusPills');
    if (statusPillsWrap) {
      const pills = statusPillsWrap.querySelectorAll('.feed-status-pill');
      pills.forEach(function (pill) {
        pill.addEventListener('click', function () {
          const s = pill.getAttribute('data-status') || 'all';
          state.questionStatus = s;
          updateQuestionStatusPillsUI();
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        });
      });
    }

    // 2b. Saved Hub Category Pills in feed toolbar
    const savedPillsWrap = document.getElementById('feedSavedHubPills');
    if (savedPillsWrap) {
      const pills = savedPillsWrap.querySelectorAll('.feed-saved-pill');
      pills.forEach(function (pill) {
        pill.addEventListener('click', function () {
          const t = pill.getAttribute('data-saved-type') || pill.getAttribute('data-type') || 'all';
          state.savedType = t;
          pills.forEach(function (p) {
            const pType = p.getAttribute('data-saved-type') || p.getAttribute('data-type');
            const isAct = pType === t;
            p.classList.toggle('active', isAct);
            p.setAttribute('aria-checked', isAct ? 'true' : 'false');
          });
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        });
      });
    }

    // 3. Dismissible Welcome Banner
    const welcomeBanner = document.getElementById('feedWelcomeBanner');
    const btnDismissWelcome = document.getElementById('btnDismissWelcomeBanner');
    if (welcomeBanner) {
      try {
        if (localStorage.getItem('sc_welcome_dismissed') === '1') {
          welcomeBanner.style.display = 'none';
        } else {
          welcomeBanner.style.display = 'flex';
        }
      } catch (e) {
        welcomeBanner.style.display = 'flex';
      }

      if (btnDismissWelcome) {
        btnDismissWelcome.addEventListener('click', function () {
          try {
            localStorage.setItem('sc_welcome_dismissed', '1');
          } catch (e) {}
          welcomeBanner.style.display = 'none';
          if (state.user && state.user.id) {
            fetch('/api/user/feed-settings', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ welcomeDismissed: true })
            }).catch(function () {});
          }
        });
      }
    }

    // 4. Unanswered Questions Sidebar Widget
    function loadUnansweredQuestions() {
      const widget = document.getElementById('widgetUnansweredQuestions');
      const listEl = document.getElementById('unansweredQuestionsList');
      if (!widget || !listEl) return;

      fetch('/api/questions/unanswered')
        .then(function (res) { return res.ok ? res.json() : null; })
        .then(function (data) {
          if (!data || !data.success || !Array.isArray(data.questions) || data.questions.length === 0) {
            widget.style.display = 'none';
            return;
          }
          widget.style.display = 'block';
          listEl.innerHTML = '';
          data.questions.slice(0, 3).forEach(function (q) {
            const item = document.createElement('div');
            item.className = 'unanswered-item';
            const dateStr = q.date || '';
            item.innerHTML =
              '<a href="article.html?id=' + encodeURIComponent(q.id) + '" class="unanswered-item-title">' + escapeHtml(q.title) + '</a>' +
              '<div class="unanswered-item-meta">' +
                (dateStr ? '<span>' + escapeHtml(dateStr) + '</span>' : '') +
              '</div>';
            listEl.appendChild(item);
          });
        })
        .catch(function () {
          widget.style.display = 'none';
        });

      const allUnansweredLink = document.getElementById('linkAllUnanswered');
      if (allUnansweredLink && !allUnansweredLink._boundClick) {
        allUnansweredLink._boundClick = true;
        allUnansweredLink.addEventListener('click', function (e) {
          e.preventDefault();
          state.questionStatus = 'unanswered';
          switchTab('questions');
        });
      }
    }
    loadUnansweredQuestions();

    // 5. Topics Catalog Modal
    const topicsModal = document.getElementById('topicsCatalogModal');
    const btnShowAllTopics = document.getElementById('btnShowAllTopics');
    const btnCloseTopicsModal = document.getElementById('btnCloseTopicsCatalogModal');
    const topicsModalGrid = document.getElementById('topicsCatalogModalGrid');

    window.openTopicsCatalogModal = function () {
      if (!topicsModal || !topicsModalGrid) return;
      topicsModalGrid.innerHTML = '';
      const topics = (window.PublicationConfig && window.PublicationConfig.TOPICS) || [];
      topics.forEach(function (t) {
        const card = document.createElement('button');
        card.type = 'button';
        card.className = 'topic-catalog-card';
        const count = state.topicCounts[t.id] || 0;
        card.innerHTML =
          '<span class="topic-catalog-card-name">' + escapeHtml(t.title) + '</span>' +
          '<span class="topic-catalog-card-count">' + count + ' ' + pluralize(count, 'статья', 'статьи', 'статей') + '</span>';
        card.addEventListener('click', function () {
          topicsModal.style.display = 'none';
          state.filters.topics = [t.id];
          state.offset = 0;
          if (typeof syncFilterFormUI === 'function') {
            syncFilterFormUI();
          }
          syncURL(false);
          fetchFeed(true);
        });
        topicsModalGrid.appendChild(card);
      });
      topicsModal.style.display = 'flex';
    };

    if (btnShowAllTopics) {
      btnShowAllTopics.addEventListener('click', function (e) {
        e.preventDefault();
        switchTab('directions');
        syncURL(false);
      });
    }

    if (btnCloseTopicsModal && topicsModal) {
      btnCloseTopicsModal.addEventListener('click', function () {
        topicsModal.style.display = 'none';
      });
      topicsModal.addEventListener('click', function (e) {
        if (e.target === topicsModal) topicsModal.style.display = 'none';
      });
    }

    // 6. Header Notifications
    const notifBtn = document.getElementById('headerNotificationsBtn');
    const notifBadge = document.getElementById('headerNotifBadge');
    const notifPopup = document.getElementById('headerNotifPopup');
    const notifList = document.getElementById('notifListContainer');
    const markAllBtn = document.getElementById('notifMarkAllReadBtn');
    const notifWrap = document.getElementById('headerNotifWrap');

    function loadHeaderNotifications() {
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

      loadHeaderNotifications();
    }

    // 7. User Profile Modal
    const userModal = document.getElementById('userProfileModal');
    const btnCloseUserModal = document.getElementById('btnCloseUserProfileModal');
    const userModalBody = document.getElementById('userProfileModalBody');
    let currentOpenUserId = null;
    let profileRequestSeq = 0;
    let profileAbortController = null;
    let lastProfileTriggerEl = null;

    function closeUserProfileModal() {
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

    if (btnCloseUserModal && userModal) {
      btnCloseUserModal.addEventListener('click', closeUserProfileModal);
      userModal.addEventListener('click', function (e) {
        if (e.target === userModal) closeUserProfileModal();
      });
    }

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && userModal && userModal.style.display !== 'none') {
        e.preventDefault();
        closeUserProfileModal();
      }
    });

    document.addEventListener('click', function (e) {
      const authorBtn = e.target.closest('.btn-author-profile');
      if (authorBtn) {
        e.preventDefault();
        e.stopPropagation();
        const authorId = authorBtn.getAttribute('data-author-id') || authorBtn.getAttribute('data-user-id');
        if (authorId) {
          lastProfileTriggerEl = authorBtn;
          openUserProfileModal(authorId);
        }
      }
    }, true);

    window.addEventListener('smartcontractum:voted', function () {
      if (currentOpenUserId && userModal && userModal.style.display !== 'none') {
        openUserProfileModal(currentOpenUserId, null, true);
      }
    });
  }

  // --------------------------------------------------------------------------
  // 13. DOM Ready Entry Point
  // --------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    initTheme();
    updateSavedCounter();
    initControls();
    initSubnavTabs();
    initFeedSettingsPanel();
    initFeedFiltersPanel();
    initAuthControls();
    initTask37Entities();
    initTask38CommunityFeatures();

    checkAuthStatus(function () {
      parseURLParams();
      if (state.tab === 'clubs') {
        if (state.activeClubId) openClubDetail(state.activeClubId);
        else loadClubs();
      } else if (state.tab === 'companies') {
        if (state.activeCompanyId) openCompanyDetail(state.activeCompanyId);
        else loadCompanies(state.companiesSubtab || 'catalog');
      } else if (state.tab === 'directions') {
        loadDirections();
      } else {
        fetchFeed(true);
      }
    });

    window.addEventListener('popstate', function () {
      parseURLParams();
      if (state.tab === 'clubs') {
        if (state.activeClubId) openClubDetail(state.activeClubId);
        else loadClubs();
      } else if (state.tab === 'companies') {
        if (state.activeCompanyId) openCompanyDetail(state.activeCompanyId);
        else loadCompanies(state.companiesSubtab || 'catalog');
      } else if (state.tab === 'directions') {
        loadDirections();
      } else {
        fetchFeed(true);
      }
    });
  });

  window.addEventListener('smartcontractum:voted', function (e) {
    if (!e || !e.detail) return;
    const detail = e.detail;
    if (detail.targetType === 'article') {
      const art = (state.articles || []).find(function (a) { return a.id === detail.targetId; });
      if (art) {
        art.score = detail.score;
        art.myVote = detail.myVote;
        art.canVote = detail.canVote;
      }
    }
  });

  if (typeof window !== 'undefined') {
    window.__getFeedAbortController = function () { return feedAbortController; };
    window.__getFeedState = function () { return state; };
    window.__updateQuestionStatusPillsUI = updateQuestionStatusPillsUI;
    window.__parseURLParams = parseURLParams;
    window.__syncURL = syncURL;
    window.loadArticles = loadArticles;
    window.fetchFeed = fetchFeed;
    window.showOfflineBadge = showOfflineBadge;
    window.hideOfflineBadge = hideOfflineBadge;
    window.renderErrorState = renderErrorState;
    window.handleOfflineFallback = handleOfflineFallback;
    window.FeedApp = window.FeedApp || {};
    window.FeedApp.loadArticles = loadArticles;
    window.FeedApp.retryLoad = function () {
      loadArticles(true);
    };
  }

})();
