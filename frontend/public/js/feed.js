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
  // 2. Bookmarks Management (localStorage sc_bookmarks)
  // --------------------------------------------------------------------------
  function getBookmarks() {
    try {
      const data = localStorage.getItem('sc_bookmarks');
      if (data) {
        const parsed = JSON.parse(data);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (e) {}
    return [];
  }

  function saveBookmarks(bookmarks) {
    try {
      localStorage.setItem('sc_bookmarks', JSON.stringify(bookmarks));
    } catch (e) {}
    updateSavedCounter();
  }

  function isBookmarked(id) {
    if (!id) return false;
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
      showToast('Статья удалена из закладок');
    } else {
      bookmarks.push(id);
      bookmarked = true;
      showToast('Статья сохранена в закладки');
    }
    saveBookmarks(bookmarks);
    return bookmarked;
  }

  function updateSavedCounter() {
    const counterEl = document.getElementById('feedSavedCount');
    if (counterEl) {
      const count = getBookmarks().length;
      counterEl.textContent = count;
      counterEl.style.display = 'inline-block';
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
    toast.style.display = 'block';
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(function () {
      toast.style.display = 'none';
    }, 2800);
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
    tab: 'all', // 'all' | 'my' | 'saved'
    savedOnly: false,
    limit: 10,
    offset: 0,
    total: 0,
    hasMore: false,
    articles: [],
    topicCounts: {},
    isLoading: false,
    noSubscriptions: false,
    feedSettings: {
      materialTypes: ['article', 'post', 'news', 'question'],
      complexityLevels: ['all']
    },
    filters: {
      types: [],
      topics: [],
      complexities: [],
      period: 'all',
      dateFrom: '',
      dateTo: '',
      format: 'all',
      audience: 'all'
    },
    userSubscriptions: {
      authors: [],
      topics: [],
      tags: []
    },
    userExceptions: {
      authors: [],
      topics: [],
      tags: []
    }
  };

  let currentUser = null;
  let pendingTabAfterAuth = null;

  function parseURLParams() {
    const params = new URLSearchParams(window.location.search);
    state.search = (params.get('search') || params.get('q') || '').trim();
    state.sort = params.get('sort') || 'newest';

    const tabParam = (params.get('tab') || '').toLowerCase();
    const savedParam = params.get('saved');

    if (tabParam === 'my') {
      state.tab = 'my';
      state.savedOnly = false;
    } else if (tabParam === 'saved' || savedParam === '1' || savedParam === 'true') {
      state.tab = 'saved';
      state.savedOnly = true;
    } else {
      state.tab = 'all';
      state.savedOnly = false;
    }

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
    state.filters.format = params.get('format') || 'all';
    state.filters.audience = params.get('audience') || 'all';

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

    updatePeriodVisibility();
    updateSubnavTabsUI();
    renderActiveChips();
    updateFilterBadge();
  }

  function updatePeriodVisibility() {
    const wrap = document.getElementById('feedPeriodSelectWrap');
    if (!wrap) return;
    const showPeriod = state.sort !== 'newest';
    wrap.style.display = showPeriod ? 'inline-block' : 'none';
  }

  function syncURL(replace) {
    const params = new URLSearchParams();
    if (state.tab && state.tab !== 'all') {
      params.set('tab', state.tab);
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
    if (state.filters.format && state.filters.format !== 'all') {
      params.set('format', state.filters.format);
    }
    if (state.filters.audience && state.filters.audience !== 'all') {
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
    }
  }

  function openAuthModal(targetTab) {
    pendingTabAfterAuth = targetTab || null;
    const modal = document.getElementById('authModal');
    if (modal) modal.style.display = 'flex';
  }

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

    const categories = ['authors', 'topics', 'tags'];
    for (let c = 0; c < categories.length; c++) {
      const cat = categories[c];
      const dSubs = (draftSettingsState.subscriptions[cat] || []).map(function (x) { return x.id || x; }).sort();
      const sSubs = (savedSettingsState.subscriptions[cat] || []).map(function (x) { return x.id || x; }).sort();
      if (dSubs.length !== sSubs.length) return true;
      for (let i = 0; i < dSubs.length; i++) {
        if (dSubs[i] !== sSubs[i]) return true;
      }

      const dExc = (draftSettingsState.exceptions[cat] || []).map(function (x) { return x.id || x; }).sort();
      const sExc = (savedSettingsState.exceptions[cat] || []).map(function (x) { return x.id || x; }).sort();
      if (dExc.length !== sExc.length) return true;
      for (let i = 0; i < dExc.length; i++) {
        if (dExc[i] !== sExc[i]) return true;
      }
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

    // Update counters on category tabs
    const authorsCountEl = document.getElementById('feedSettingsSubsAuthorsCount');
    const topicsCountEl = document.getElementById('feedSettingsSubsTopicsCount');
    const tagsCountEl = document.getElementById('feedSettingsSubsTagsCount');

    const curStore = draftSettingsState[activeSubsMode] || {};
    if (authorsCountEl) authorsCountEl.textContent = (curStore.authors || []).length;
    if (topicsCountEl) topicsCountEl.textContent = (curStore.topics || []).length;
    if (tagsCountEl) tagsCountEl.textContent = (curStore.tags || []).length;

    if (isCatalogOpen) {
      renderFeedSettingsCatalogList();
    } else {
      renderFeedSettingsSubsList();
    }
  }

  function syncSettingsUIFromDraft() {
    // 1. Tumblers
    const types = draftSettingsState.materialTypes || ['article', 'post', 'news', 'question'];
    const typeInputs = document.querySelectorAll('input[name="feedMaterialType"]');
    typeInputs.forEach(function (inp) {
      inp.checked = (types.indexOf(inp.value) !== -1);
    });

    // 2. Complexity buttons
    const compLevels = draftSettingsState.complexityLevels || ['all'];
    const compButtons = document.querySelectorAll('#feedComplexityLevelsList .feed-choice-btn');
    const isAll = (compLevels.indexOf('all') !== -1 || compLevels.length === 0);
    compButtons.forEach(function (btn) {
      const c = btn.getAttribute('data-complexity');
      const active = (c === 'all') ? isAll : (!isAll && compLevels.indexOf(c) !== -1);
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });

    // 3. Segmented control
    const subModeBtn = document.getElementById('btnSubsModeSubscriptions');
    const excModeBtn = document.getElementById('btnSubsModeExceptions');
    if (subModeBtn) {
      subModeBtn.classList.toggle('active', activeSubsMode === 'subscriptions');
      subModeBtn.setAttribute('aria-selected', activeSubsMode === 'subscriptions' ? 'true' : 'false');
    }
    if (excModeBtn) {
      excModeBtn.classList.toggle('active', activeSubsMode === 'exceptions');
      excModeBtn.setAttribute('aria-selected', activeSubsMode === 'exceptions' ? 'true' : 'false');
    }

    // 4. Sub tabs
    const tabAuthors = document.getElementById('tabFeedSettingsSubsAuthors');
    const tabTopics = document.getElementById('tabFeedSettingsSubsTopics');
    const tabTags = document.getElementById('tabFeedSettingsSubsTags');
    if (tabAuthors) {
      tabAuthors.classList.toggle('active', activeSettingsSubsType === 'author');
      tabAuthors.setAttribute('aria-selected', activeSettingsSubsType === 'author' ? 'true' : 'false');
    }
    if (tabTopics) {
      tabTopics.classList.toggle('active', activeSettingsSubsType === 'topic');
      tabTopics.setAttribute('aria-selected', activeSettingsSubsType === 'topic' ? 'true' : 'false');
    }
    if (tabTags) {
      tabTags.classList.toggle('active', activeSettingsSubsType === 'tag');
      tabTags.setAttribute('aria-selected', activeSettingsSubsType === 'tag' ? 'true' : 'false');
    }

    // 5. Action button text
    const actionText = document.getElementById('btnToggleCatalogSearchText');
    if (actionText) {
      actionText.textContent = (activeSubsMode === 'subscriptions') ? 'Добавить подписки' : 'Добавить исключения';
    }

    updateSettingsDraftUI();
  }

  function openFeedSettingsPanel() {
    closeFeedFiltersPanel();

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

    const panel = document.getElementById('feedFiltersPanel');
    const toggleBtn = document.getElementById('btnFeedFiltersToggle');

    if (panel) {
      panel.style.display = 'block';
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

    if (panel) {
      panel.style.display = 'none';
    }
    if (toggleBtn) {
      toggleBtn.classList.remove('active');
      toggleBtn.setAttribute('aria-expanded', 'false');
    }
  }

  function toggleFeedFiltersPanel() {
    const panel = document.getElementById('feedFiltersPanel');
    if (panel && panel.style.display !== 'none') {
      closeFeedFiltersPanel();
    } else {
      openFeedFiltersPanel();
    }
  }

  function initSubnavTabs() {
    const tabAll = document.getElementById('tabFeedAll');
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
        openFeedSettingsPanel();
        const subsSection = document.getElementById('feedSettingsSectionSubscriptions');
        if (subsSection) {
          subsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      });
    }

    if (tabAll) {
      tabAll.addEventListener('click', function () {
        switchTab('all');
      });
    }

    if (tabMy) {
      tabMy.addEventListener('click', function () {
        if (state.tab === 'my') {
          showToast('Возврат ко всем публикациям');
          switchTab('all');
        } else if (!currentUser) {
          openAuthModal('my');
        } else {
          switchTab('my');
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
  }

  function switchTab(tabName) {
    state.tab = tabName;
    state.savedOnly = (tabName === 'saved');
    state.offset = 0;

    updateSubnavTabsUI();

    const manageSubsBtn = document.getElementById('btnManageSubscriptions');
    if (manageSubsBtn) {
      manageSubsBtn.style.display = (tabName === 'my' && currentUser) ? 'inline-flex' : 'none';
    }

    syncURL(false);
    fetchFeed(true);
  }

  function updateSubnavTabsUI() {
    const tabAll = document.getElementById('tabFeedAll');
    const tabMy = document.getElementById('tabFeedMy');
    const tabSaved = document.getElementById('feedSavedTab');

    if (tabAll) {
      const isAll = state.tab === 'all';
      tabAll.classList.toggle('active', isAll);
      tabAll.setAttribute('aria-selected', isAll ? 'true' : 'false');
    }
    if (tabMy) {
      const isMy = state.tab === 'my';
      tabMy.classList.toggle('active', isMy);
      tabMy.setAttribute('aria-selected', isMy ? 'true' : 'false');
    }
    if (tabSaved) {
      const isSaved = state.tab === 'saved';
      tabSaved.classList.toggle('active', isSaved);
      tabSaved.setAttribute('aria-selected', isSaved ? 'true' : 'false');
    }
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
    const container = document.getElementById('feedSettingsSubsList');
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
      el.className = 'subs-item' + (activeSubsMode === 'exceptions' ? ' is-exception-item' : '');

      let subText = item.role || item.description || '';
      if (!subText && item.count !== undefined) {
        subText = pluralizePublications(item.count);
      }
      const displayTitle = (activeSettingsSubsType === 'tag' ? '#' : '') + item.title;

      const btnLabel = (activeSubsMode === 'subscriptions') ? 'Отписаться' : 'Убрать исключение';
      const btnClass = (activeSubsMode === 'subscriptions') ? 'is-subscribed' : 'is-excluded';

      el.innerHTML =
        '<div class="subs-item-info">' +
          '<span class="subs-item-title">' + escapeHtml(displayTitle) + '</span>' +
          (subText ? '<span class="subs-item-sub">' + escapeHtml(subText) + '</span>' : '') +
        '</div>' +
        '<button type="button" class="btn btn-secondary subs-toggle-btn ' + btnClass + '" data-id="' + escapeHtml(item.id) + '">' +
          escapeHtml(btnLabel) +
        '</button>';

      el.querySelector('.subs-toggle-btn').addEventListener('click', function () {
        toggleItemInDraft(activeSettingsSubsType, item);
      });

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

      el.innerHTML =
        '<div class="subs-item-info">' +
          '<span class="subs-item-title">' + escapeHtml(displayTitle) + '</span>' +
          (subText ? '<span class="subs-item-sub">' + escapeHtml(subText) + '</span>' : '') +
        '</div>' +
        '<button type="button" class="btn btn-secondary subs-toggle-btn ' + btnClass + '" data-id="' + escapeHtml(itemId) + '" title="' + escapeHtml(btnTitle) + '">' +
          escapeHtml(btnLabel) +
        '</button>';

      el.querySelector('.subs-toggle-btn').addEventListener('click', function () {
        toggleItemInDraft(activeSettingsSubsType, item);
      });

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
        updateSettingsDraftUI();
      });
    });

    // Complexity choice buttons
    const compButtons = document.querySelectorAll('#feedComplexityLevelsList .feed-choice-btn');
    compButtons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        const c = btn.getAttribute('data-complexity');
        if (c === 'all') {
          draftSettingsState.complexityLevels = ['all'];
        } else {
          draftSettingsState.complexityLevels = (draftSettingsState.complexityLevels || []).filter(function (x) { return x !== 'all'; });
          const idx = draftSettingsState.complexityLevels.indexOf(c);
          if (idx !== -1) {
            draftSettingsState.complexityLevels.splice(idx, 1);
          } else {
            draftSettingsState.complexityLevels.push(c);
          }
          if (draftSettingsState.complexityLevels.length === 0) {
            draftSettingsState.complexityLevels = ['all'];
          }
        }
        syncSettingsUIFromDraft();
      });
    });

    // Segmented control buttons
    const subModeBtn = document.getElementById('btnSubsModeSubscriptions');
    const excModeBtn = document.getElementById('btnSubsModeExceptions');
    if (subModeBtn) {
      subModeBtn.addEventListener('click', function () {
        activeSubsMode = 'subscriptions';
        syncSettingsUIFromDraft();
        if (isCatalogOpen) fetchAndRenderCatalog(true);
      });
    }
    if (excModeBtn) {
      excModeBtn.addEventListener('click', function () {
        activeSubsMode = 'exceptions';
        syncSettingsUIFromDraft();
        if (isCatalogOpen) fetchAndRenderCatalog(true);
      });
    }

    // Sub tabs
    const tabAuthors = document.getElementById('tabFeedSettingsSubsAuthors');
    const tabTopics = document.getElementById('tabFeedSettingsSubsTopics');
    const tabTags = document.getElementById('tabFeedSettingsSubsTags');
    if (tabAuthors) {
      tabAuthors.addEventListener('click', function () {
        activeSettingsSubsType = 'author';
        syncSettingsUIFromDraft();
        if (isCatalogOpen) openCatalogPane();
      });
    }
    if (tabTopics) {
      tabTopics.addEventListener('click', function () {
        activeSettingsSubsType = 'topic';
        syncSettingsUIFromDraft();
        if (isCatalogOpen) openCatalogPane();
      });
    }
    if (tabTags) {
      tabTags.addEventListener('click', function () {
        activeSettingsSubsType = 'tag';
        syncSettingsUIFromDraft();
        if (isCatalogOpen) openCatalogPane();
      });
    }

    // Catalog toggle and close buttons
    const btnToggleCatalog = document.getElementById('btnToggleCatalogSearch');
    if (btnToggleCatalog) {
      btnToggleCatalog.addEventListener('click', function () {
        if (isCatalogOpen) {
          closeCatalogPane();
        } else {
          openCatalogPane();
        }
      });
    }
    const btnCloseCatalog = document.getElementById('btnCloseCatalogPane');
    if (btnCloseCatalog) {
      btnCloseCatalog.addEventListener('click', closeCatalogPane);
    }

    // Catalog search input
    const subsSearchInput = document.getElementById('feedSettingsSubsSearch');
    if (subsSearchInput) {
      subsSearchInput.addEventListener('input', function () {
        clearTimeout(catalogDebounceTimer);
        catalogDebounceTimer = setTimeout(function () {
          fetchAndRenderCatalog(true);
        }, 250);
      });
    }

    // Catalog load more button
    const btnCatLoadMore = document.getElementById('btnCatalogLoadMore');
    if (btnCatLoadMore) {
      btnCatLoadMore.addEventListener('click', function () {
        catalogOffset += CATALOG_LIMIT;
        fetchAndRenderCatalog(false);
      });
    }

    // Save button
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        if (!validateMaterialTypes()) return;

        const payload = {
          materialTypes: draftSettingsState.materialTypes,
          complexityLevels: draftSettingsState.complexityLevels,
          subscriptions: draftSettingsState.subscriptions,
          exceptions: draftSettingsState.exceptions
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
                savedSettingsState = cloneSettings(draftSettingsState);
                state.feedSettings.materialTypes = savedSettingsState.materialTypes.slice();
                state.feedSettings.complexityLevels = savedSettingsState.complexityLevels.slice();
                state.userSubscriptions = cloneSettings(savedSettingsState.subscriptions);
                state.userExceptions = cloneSettings(savedSettingsState.exceptions);

                closeFeedSettingsPanel(true);
                showToast('Настройки ленты сохранены');
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
          savedSettingsState = cloneSettings(draftSettingsState);
          state.feedSettings.materialTypes = savedSettingsState.materialTypes.slice();
          state.feedSettings.complexityLevels = savedSettingsState.complexityLevels.slice();
          state.userSubscriptions = cloneSettings(savedSettingsState.subscriptions);
          state.userExceptions = cloneSettings(savedSettingsState.exceptions);

          try {
            localStorage.setItem('sc_guest_feed_settings', JSON.stringify(savedSettingsState));
          } catch (e) {}

          closeFeedSettingsPanel(true);
          showToast('Настройки сохранены для текущей сессии');
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
      });
      searchInput.addEventListener('blur', function () {
        if (!searchInput.value.trim()) {
          searchGroup.classList.remove('is-expanded');
        }
      });
      if (searchInput.value.trim()) {
        searchGroup.classList.add('is-expanded');
      }
    }

    if (searchSubmitBtn && searchInput) {
      searchSubmitBtn.addEventListener('click', function (e) {
        e.preventDefault();
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
        updatePeriodVisibility();
        syncURL(false);
        fetchFeed(true);
      });
    }

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

  // --------------------------------------------------------------------------
  // 7. Slide-Out Feed Filters Panel (#feedFiltersPanel)
  // --------------------------------------------------------------------------
  function initFeedFiltersPanel() {
    const closeBtn = document.getElementById('btnCloseFeedFilters');
    const applyBtn = document.getElementById('btnApplyFilters');
    const resetBtn = document.getElementById('feedResetFiltersBtn');
    const topicSearchInput = document.getElementById('filterTopicSearchInput');

    if (closeBtn) {
      closeBtn.addEventListener('click', closeFeedFiltersPanel);
    }

    // Material Types multi-select chips
    const typeChips = document.querySelectorAll('#feedFilterMaterialTypes .feed-filter-chip');
    typeChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        chip.classList.toggle('active');
      });
    });

    // Complexity multi-select chips
    const compChips = document.querySelectorAll('#feedFilterComplexityLevels .feed-filter-chip');
    compChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        chip.classList.toggle('active');
      });
    });

    // Period chips
    const periodChips = document.querySelectorAll('#feedFilterPeriods .feed-filter-chip');
    const customDates = document.getElementById('feedFilterCustomDates');
    periodChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        periodChips.forEach(function (c) { c.classList.remove('active'); });
        chip.classList.add('active');
        const p = chip.getAttribute('data-period');
        if (customDates) {
          customDates.style.display = (p === 'custom') ? 'flex' : 'none';
        }
      });
    });

    // Sort chips
    const sortChips = document.querySelectorAll('#feedFilterSortGroup .feed-filter-chip');
    sortChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        sortChips.forEach(function (c) { c.classList.remove('active'); });
        chip.classList.add('active');
      });
    });

    // Topic search in filters panel
    if (topicSearchInput) {
      topicSearchInput.addEventListener('input', function () {
        const q = topicSearchInput.value.trim().toLowerCase();
        const btns = document.querySelectorAll('#modalTopicsFilterBar .feed-filter-chip');
        btns.forEach(function (btn) {
          if (!q || btn.getAttribute('data-topic') === 'all') {
            btn.style.display = 'inline-flex';
          } else {
            const text = btn.textContent.toLowerCase();
            btn.style.display = text.indexOf(q) !== -1 ? 'inline-flex' : 'none';
          }
        });
      });
    }

    // Topics list clicks
    const topicsBar = document.getElementById('modalTopicsFilterBar');
    if (topicsBar) {
      topicsBar.addEventListener('click', function (e) {
        const btn = e.target.closest('.feed-filter-chip');
        if (!btn) return;
        const topicId = btn.getAttribute('data-topic');
        if (topicId === 'all') {
          state.filters.topics = [];
          state.topic = 'all';
          renderFilterTopicsUI();
        } else {
          const idx = state.filters.topics.indexOf(topicId);
          if (idx !== -1) {
            state.filters.topics.splice(idx, 1);
          } else {
            state.filters.topics.push(topicId);
          }
          state.topic = state.filters.topics[0] || 'all';
          renderFilterTopicsUI();
        }
      });
    }

    if (applyBtn) {
      applyBtn.addEventListener('click', applyFiltersFromPanel);
    }

    if (resetBtn) {
      resetBtn.addEventListener('click', resetFiltersForm);
    }

    // Global escape key handler for panels
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        const settingsPanel = document.getElementById('feedSettingsPanel');
        if (settingsPanel && settingsPanel.style.display !== 'none') {
          closeFeedSettingsPanel(false);
        }
        const filtersPanel = document.getElementById('feedFiltersPanel');
        if (filtersPanel && filtersPanel.style.display !== 'none') {
          closeFeedFiltersPanel();
        }
        const authModal = document.getElementById('authModal');
        if (authModal && authModal.style.display !== 'none') {
          closeAuthModal();
        }
      }
    });

    renderFilterTopicsUI();
  }

  function renderFilterTopicsUI() {
    const bar = document.getElementById('modalTopicsFilterBar');
    if (!bar) return;

    if (!bar.querySelector('.feed-filter-chip')) {
      bar.innerHTML = '<button type="button" class="feed-filter-chip active" data-topic="all">Все темы</button>';
      if (window.PublicationConfig && Array.isArray(window.PublicationConfig.TOPICS)) {
        window.PublicationConfig.TOPICS.forEach(function (t) {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'feed-filter-chip';
          btn.setAttribute('data-topic', t.id);
          btn.textContent = t.title;
          bar.appendChild(btn);
        });
      }
    }

    const selTopics = state.filters.topics || [];
    const isAll = (selTopics.length === 0);

    bar.querySelectorAll('.feed-filter-chip').forEach(function (b) {
      const tid = b.getAttribute('data-topic');
      if (tid === 'all') {
        b.classList.toggle('active', isAll);
      } else {
        b.classList.toggle('active', selTopics.indexOf(tid) !== -1);
      }
    });

    renderSelectedTopicsChips();
  }

  function renderSelectedTopicsChips() {
    const chipsBar = document.getElementById('filterSelectedTopicsChips');
    if (!chipsBar) return;
    chipsBar.innerHTML = '';

    const selTopics = state.filters.topics || [];
    if (selTopics.length === 0) {
      chipsBar.style.display = 'none';
      return;
    }

    chipsBar.style.display = 'flex';
    selTopics.forEach(function (tid) {
      let title = tid;
      if (window.PublicationConfig) {
        const topObj = window.PublicationConfig.getTopicById(tid);
        if (topObj) title = topObj.title;
      }
      const chip = document.createElement('div');
      chip.className = 'filter-selected-chip';
      chip.innerHTML =
        '<span class="chip-name">' + escapeHtml(title) + '</span>' +
        '<button type="button" class="chip-del-btn" aria-label="Удалить тему ' + escapeHtml(title) + '">' +
          '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>' +
        '</button>';

      chip.querySelector('.chip-del-btn').addEventListener('click', function () {
        state.filters.topics = state.filters.topics.filter(function (x) { return x !== tid; });
        if (state.filters.topics.length === 0) state.topic = 'all';
        renderFilterTopicsUI();
      });

      chipsBar.appendChild(chip);
    });
  }

  function syncFilterFormUI() {
    // 1. Types
    const types = state.filters.types || [];
    document.querySelectorAll('#feedFilterMaterialTypes .feed-filter-chip').forEach(function (b) {
      b.classList.toggle('active', types.indexOf(b.getAttribute('data-type')) !== -1);
    });

    // 2. Complexities
    const comp = state.filters.complexities || [];
    document.querySelectorAll('#feedFilterComplexityLevels .feed-filter-chip').forEach(function (b) {
      b.classList.toggle('active', comp.indexOf(b.getAttribute('data-complexity')) !== -1);
    });

    // 3. Period
    const per = state.filters.period || 'all';
    document.querySelectorAll('#feedFilterPeriods .feed-filter-chip').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-period') === per);
    });
    const customDates = document.getElementById('feedFilterCustomDates');
    if (customDates) customDates.style.display = (per === 'custom') ? 'flex' : 'none';
    const dFrom = document.getElementById('filterDateFrom');
    const dTo = document.getElementById('filterDateTo');
    if (dFrom) dFrom.value = state.filters.dateFrom || '';
    if (dTo) dTo.value = state.filters.dateTo || '';

    // 4. Sort
    const s = state.sort || 'newest';
    document.querySelectorAll('#feedFilterSortGroup .feed-filter-chip').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-sort') === s);
    });

    // 5. Topics
    renderFilterTopicsUI();

    // 6. Format & Audience
    const fmtSel = document.getElementById('feedFormatSelect');
    if (fmtSel) fmtSel.value = state.filters.format || 'all';
    const audSel = document.getElementById('feedAudienceSelect');
    if (audSel) audSel.value = state.filters.audience || 'all';
  }

  function resetFiltersForm() {
    document.querySelectorAll('#feedFilterMaterialTypes .feed-filter-chip').forEach(function (b) { b.classList.remove('active'); });
    document.querySelectorAll('#feedFilterComplexityLevels .feed-filter-chip').forEach(function (b) { b.classList.remove('active'); });

    document.querySelectorAll('#feedFilterPeriods .feed-filter-chip').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-period') === 'all');
    });
    const customDates = document.getElementById('feedFilterCustomDates');
    if (customDates) customDates.style.display = 'none';
    const dFrom = document.getElementById('filterDateFrom');
    const dTo = document.getElementById('filterDateTo');
    if (dFrom) dFrom.value = '';
    if (dTo) dTo.value = '';

    document.querySelectorAll('#feedFilterSortGroup .feed-filter-chip').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-sort') === 'newest');
    });

    const topicSearch = document.getElementById('filterTopicSearchInput');
    if (topicSearch) topicSearch.value = '';
    document.querySelectorAll('#modalTopicsFilterBar .feed-filter-chip').forEach(function (b) {
      b.style.display = 'inline-flex';
      b.classList.toggle('active', b.getAttribute('data-topic') === 'all');
    });
    const chipsBar = document.getElementById('filterSelectedTopicsChips');
    if (chipsBar) {
      chipsBar.innerHTML = '';
      chipsBar.style.display = 'none';
    }

    const fmtSel = document.getElementById('feedFormatSelect');
    if (fmtSel) fmtSel.value = 'all';
    const audSel = document.getElementById('feedAudienceSelect');
    if (audSel) audSel.value = 'all';
  }

  function applyFiltersFromPanel() {
    const activeTypes = Array.from(document.querySelectorAll('#feedFilterMaterialTypes .feed-filter-chip.active')).map(function (b) {
      return b.getAttribute('data-type');
    });
    state.filters.types = activeTypes;

    const activeComp = Array.from(document.querySelectorAll('#feedFilterComplexityLevels .feed-filter-chip.active')).map(function (b) {
      return b.getAttribute('data-complexity');
    });
    state.filters.complexities = activeComp;

    const activePeriodBtn = document.querySelector('#feedFilterPeriods .feed-filter-chip.active');
    const periodVal = activePeriodBtn ? activePeriodBtn.getAttribute('data-period') : 'all';
    state.filters.period = periodVal;
    if (periodVal === 'custom') {
      const dFrom = document.getElementById('filterDateFrom');
      const dTo = document.getElementById('filterDateTo');
      state.filters.dateFrom = dFrom ? dFrom.value : '';
      state.filters.dateTo = dTo ? dTo.value : '';
    } else {
      state.filters.dateFrom = '';
      state.filters.dateTo = '';
    }

    const activeSortBtn = document.querySelector('#feedFilterSortGroup .feed-filter-chip.active');
    if (activeSortBtn) {
      state.sort = activeSortBtn.getAttribute('data-sort') || 'newest';
      const sortSel = document.getElementById('feedSortSelect');
      if (sortSel) sortSel.value = state.sort;
      updatePeriodVisibility();
    }

    const isAllTopics = Boolean(document.querySelector('#modalTopicsFilterBar .feed-filter-chip[data-topic="all"].active'));
    if (isAllTopics) {
      state.filters.topics = [];
      state.topic = 'all';
    } else {
      const activeTopicBtns = Array.from(document.querySelectorAll('#modalTopicsFilterBar .feed-filter-chip.active:not([data-topic="all"])')).map(function (b) {
        return b.getAttribute('data-topic');
      });
      state.filters.topics = activeTopicBtns;
      state.topic = activeTopicBtns[0] || 'all';
    }

    const fmtSel = document.getElementById('feedFormatSelect');
    if (fmtSel) state.filters.format = fmtSel.value;
    const audSel = document.getElementById('feedAudienceSelect');
    if (audSel) state.filters.audience = audSel.value;

    closeFeedFiltersPanel();
    state.offset = 0;
    syncURL(false);
    fetchFeed(true);

    const scrollTarget = document.getElementById('feedDirectToolbar') || document.getElementById('feedResultsCount');
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

      if (state.filters.format && state.filters.format !== 'all') {
        if (art.format !== state.filters.format) return false;
      }

      if (state.filters.audience && state.filters.audience !== 'all') {
        if (art.targetAudience !== state.filters.audience && art.audience !== state.filters.audience) {
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
    if (state.filters.format && state.filters.format !== 'all') groups++;
    if (state.filters.audience && state.filters.audience !== 'all') groups++;

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
        pLabel = (state.filters.dateFrom || '...') + ' — ' + (state.filters.dateTo || '...');
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

    if (state.filters.format && state.filters.format !== 'all') {
      let fmtTitle = state.filters.format;
      if (window.PublicationConfig) {
        const fObj = window.PublicationConfig.getFormatById(state.filters.format);
        if (fObj) fmtTitle = fObj.title;
      }
      chips.push({
        id: 'format',
        label: 'Формат: ' + fmtTitle,
        remove: function () {
          state.filters.format = 'all';
          syncFilterFormUI();
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        }
      });
    }

    if (state.filters.audience && state.filters.audience !== 'all') {
      let audTitle = state.filters.audience;
      if (window.PublicationConfig) {
        const aObj = window.PublicationConfig.getAudienceById(state.filters.audience);
        if (aObj) audTitle = aObj.title;
      }
      chips.push({
        id: 'audience',
        label: 'Аудитория: ' + audTitle,
        remove: function () {
          state.filters.audience = 'all';
          syncFilterFormUI();
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        }
      });
    }

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
    state.filters.audience = 'all';
    state.topic = 'all';
    state.sort = 'newest';
    state.period = 'all';
    state.offset = 0;

    const searchInput = document.getElementById('feedSearchInput');
    const clearBtn = document.getElementById('feedSearchClearBtn');
    if (searchInput) {
      searchInput.value = '';
      if (clearBtn) clearBtn.style.display = 'none';
    }

    const sortSelect = document.getElementById('feedSortSelect');
    if (sortSelect) sortSelect.value = 'newest';

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

  function fetchFeed(isInitial) {
    if (state.isLoading) return;
    state.isLoading = true;

    if (isInitial) {
      state.offset = 0;
      renderSkeletons();
    }

    // Build API query
    const params = new URLSearchParams();
    params.set('tab', state.tab);
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
    if (state.filters.format && state.filters.format !== 'all') {
      params.set('format', state.filters.format);
    }
    if (state.filters.audience && state.filters.audience !== 'all') {
      params.set('audience', state.filters.audience);
    }

    // Personal feed settings apply to 'my' tab
    if (state.tab === 'my') {
      if (state.feedSettings && state.feedSettings.materialTypes && state.feedSettings.materialTypes.length < 4) {
        params.set('types', state.feedSettings.materialTypes.join(','));
      }
      if (state.feedSettings && state.feedSettings.complexityLevels && (state.feedSettings.complexityLevels.indexOf('all') === -1 || state.feedSettings.complexityLevels.length > 1)) {
        params.set('complexityLevels', state.feedSettings.complexityLevels.join(','));
      }
    }

    params.set('limit', String(state.limit));
    params.set('offset', String(state.offset));

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

    fetch('/api/articles?' + params.toString())
      .then(function (res) {
        if (res.status === 401 && state.tab === 'my') {
          state.isLoading = false;
          openAuthModal('my');
          throw new Error('AUTH_REQUIRED');
        }
        if (!res.ok) throw new Error('API status: ' + res.status);
        return res.json();
      })
      .then(function (data) {
        state.isLoading = false;
        if (data && data.success) {
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
          renderErrorState('Не удалось загрузить статьи: ' + (data ? data.error : 'Неизвестная ошибка'));
        }
      })
      .catch(function (err) {
        state.isLoading = false;
        if (err.message === 'AUTH_REQUIRED') return;
        // Offline / file protocol fallback: provide fallback data
        handleOfflineFallback(isInitial);
      });
  }

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

    // Apply sorting in offline fallback
    if (state.sort === 'oldest') {
      items.sort(function (a, b) {
        const da = parseArticleDate(a) || 0;
        const db = parseArticleDate(b) || 0;
        return da - db;
      });
    } else if (state.sort === 'popular') {
      items.sort(function (a, b) { return (b.views || 0) - (a.views || 0); });
    } else if (state.sort === 'comments') {
      items.sort(function (a, b) { return (b.commentsCount || 0) - (a.commentsCount || 0); });
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

    if (state.tab === 'saved') {
      el.textContent = 'Сохраненных публикаций: ' + state.total;
      return;
    }

    if (state.tab === 'my') {
      el.textContent = 'В персональной ленте: ' + state.total;
      return;
    }

    const n = state.total;
    if (n === 0) {
      el.textContent = 'Ничего не найдено';
    } else {
      el.textContent = 'Найдено ' + pluralizePublications(n);
    }
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

    // Render cards avoiding DOM duplicates
    if (isInitial) {
      state.articles.forEach(function (item) {
        container.appendChild(createCardElement(item));
      });
    } else {
      const existingDomIds = new Set(
        Array.from(container.querySelectorAll('.feed-card')).map(function (c) {
          return c.getAttribute('data-id');
        })
      );
      state.articles.forEach(function (item) {
        if (!existingDomIds.has(item.id)) {
          container.appendChild(createCardElement(item));
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

    if (state.tab === 'my') {
      if (state.noSubscriptions) {
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
            '<p class="empty-state-desc">Подпишитесь на авторов, темы или хэштеги, чтобы собрать свою ленту.</p>' +
            '<div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; margin-top: 16px;">' +
              '<button type="button" class="btn btn-primary empty-state-btn" id="btnEmptyOpenSettings">' +
                '<span>Настроить ленту</span>' +
              '</button>' +
              '<button type="button" class="btn btn-secondary empty-state-btn" id="btnEmptyChooseSubs">' +
                '<span>Выбрать темы и авторов</span>' +
              '</button>' +
            '</div>' +
          '</div>';

        const openSettingsBtn = document.getElementById('btnEmptyOpenSettings');
        if (openSettingsBtn) {
          openSettingsBtn.addEventListener('click', openFeedSettingsPanel);
        }
        const chooseBtn = document.getElementById('btnEmptyChooseSubs');
        if (chooseBtn) {
          chooseBtn.addEventListener('click', openSubscriptionsModal);
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
              '<button type="button" class="btn btn-primary empty-state-btn" id="btnEmptyOpenSettings">' +
                '<span>Настроить ленту</span>' +
              '</button>' +
              '<button type="button" class="btn btn-secondary empty-state-btn" id="btnEmptyAllFeed">' +
                '<span>Все публикации</span>' +
              '</button>' +
            '</div>' +
          '</div>';

        const openSettingsBtn = document.getElementById('btnEmptyOpenSettings');
        if (openSettingsBtn) {
          openSettingsBtn.addEventListener('click', openFeedSettingsPanel);
        }
        const allFeedBtn = document.getElementById('btnEmptyAllFeed');
        if (allFeedBtn) {
          allFeedBtn.addEventListener('click', function () {
            switchTab('all');
          });
        }
        return;
      }
    }

    const isSaved = state.tab === 'saved';
    const title = isSaved ? 'Нет сохраненных публикаций' : 'Ничего не найдено';
    const desc = isSaved
      ? 'Вы еще не добавили ни одной статьи в закладки. Нажмите на иконку закладки на любой публикации в ленте, чтобы сохранить ее.'
      : 'По вашему запросу и выбранным фильтрам не найдено публикаций. Попробуйте изменить параметры или сбросить фильтры.';

    container.innerHTML =
      '<div class="feed-empty-state">' +
        '<svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
          '<circle cx="11" cy="11" r="8"></circle>' +
          '<line x1="21" y1="21" x2="16.65" y2="16.65"></line>' +
          '<line x1="8" y1="11" x2="14" y2="11"></line>' +
        '</svg>' +
        '<h3 class="empty-state-title">' + escapeHtml(title) + '</h3>' +
        '<p class="empty-state-desc">' + escapeHtml(desc) + '</p>' +
        '<button type="button" id="feedEmptyResetBtn" class="btn btn-primary">' +
          (isSaved ? 'Перейти ко всем статьям' : 'Сбросить фильтры') +
        '</button>' +
      '</div>';

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
        '<button type="button" class="btn btn-secondary" onclick="window.location.reload()">' +
          'Повторить попытку' +
        '</button>' +
      '</div>';
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

  function createCardElement(item) {
    if (window.SmartContractumCard && typeof window.SmartContractumCard.createCardElement === 'function') {
      return window.SmartContractumCard.createCardElement(item, {
        isBookmarked: isBookmarked,
        onLikeToggle: toggleArticleLike,
        onBookmarkToggle: function (id, btn) {
          const active = toggleBookmark(id);
          btn.classList.toggle('is-bookmarked', active);
          const svg = btn.querySelector('svg');
          if (svg) svg.setAttribute('fill', active ? 'currentColor' : 'none');
          const newTooltip = active ? 'Убрать из сохраненного' : 'Сохранить статью';
          btn.title = newTooltip;
          btn.setAttribute('aria-label', newTooltip);
          if (state.savedOnly && !active) {
            const cardEl = btn.closest('.feed-card');
            if (cardEl) cardEl.remove();
            state.articles = state.articles.filter(function (a) { return a.id !== id; });
            state.total = Math.max(0, state.total - 1);
            updateResultsCount();
            if (state.articles.length === 0) {
              renderEmptyState();
            }
          }
        }
      });
    }

    const card = document.createElement('article');
    card.className = 'feed-card';
    card.setAttribute('data-id', item.id);
    card.setAttribute('data-topic', item.topic || '');

    const articleUrl = 'article.html?id=' + encodeURIComponent(item.id);

    // Subscription Reason Badge
    let subscriptionBadgeHtml = '';
    if (item.subscriptionReason) {
      subscriptionBadgeHtml =
        '<div class="card-subscription-badge">' +
          '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>' +
          '</svg>' +
          '<span>' + escapeHtml(item.subscriptionReason) + '</span>' +
        '</div>';
    }

    // 1. Topic Title & Badge
    let topicTitle = '';
    if (window.PublicationConfig && item.topic) {
      const t = window.PublicationConfig.getTopicById(item.topic);
      if (t) topicTitle = t.title;
    }

    // 2. Format & Complexity Titles (Uniform order: Topic -> Format -> Complexity)
    let formatTitle = '';
    if (window.PublicationConfig && item.format && item.format !== 'not_specified' && item.format !== 'none') {
      const f = window.PublicationConfig.getFormatById(item.format);
      if (f && f.title && f.title.toLowerCase() !== 'не указан') {
        formatTitle = f.title;
      }
    }

    let complexityTitle = '';
    let complexityClass = '';
    if (window.PublicationConfig && item.complexity && item.complexity !== 'none') {
      const c = window.PublicationConfig.getComplexityById(item.complexity);
      if (c && c.title && c.title.toLowerCase() !== 'не указан') {
        complexityTitle = c.title;
        complexityClass = 'complexity-' + item.complexity;
      }
    }

    // Badges HTML in uniform order: Topic, Format, Complexity, Demo
    let badgesHtml = '';
    if (topicTitle) {
      badgesHtml += '<span class="meta-badge topic-badge">' + escapeHtml(topicTitle) + '</span>';
    }
    if (formatTitle) {
      badgesHtml += '<span class="meta-badge format-badge">' + escapeHtml(formatTitle) + '</span>';
    }
    if (complexityTitle) {
      badgesHtml += '<span class="meta-badge complexity-badge ' + complexityClass + '">' + escapeHtml(complexityTitle) + '</span>';
    }
    if (item.isDemo || (item.id && String(item.id).indexOf('art-0') === 0)) {
      badgesHtml += '<span class="meta-badge badge-demo">Демонстрационный материал</span>';
    }

    // Clean titles and author roles from any redundant "(демо)" suffix or prefix
    const cleanTitle = (item.title || '')
      .replace(/\s*\((демо|demo)\)\s*/gi, ' ')
      .replace(/\s+/g, ' ')
      .trim();
    const cleanRole = (item.authorRole || '')
      .replace(/\s*\((демо|demo)\)\s*/gi, ' ')
      .replace(/\s+/g, ' ')
      .trim();

    // Tags HTML: Up to 3 tags directly, rest revealed on clicking "+N еще" / "Свернуть"
    const tags = Array.isArray(item.keywords) ? item.keywords : [];
    const maxVisibleTags = 3;
    let tagsHtml = '';
    const visibleTags = tags.slice(0, maxVisibleTags);
    const hiddenTags = tags.slice(maxVisibleTags);

    visibleTags.forEach(function (tag) {
      tagsHtml +=
        '<button type="button" class="tag-chip" data-tag="' + escapeHtml(tag) + '">' +
          '#' + escapeHtml(tag) +
        '</button>';
    });

    if (hiddenTags.length > 0) {
      tagsHtml +=
        '<button type="button" class="tag-expand-btn" aria-expanded="false">+' + hiddenTags.length + ' еще</button>' +
        '<span class="extra-tags" style="display: none;">';
      hiddenTags.forEach(function (tag) {
        tagsHtml +=
          '<button type="button" class="tag-chip" data-tag="' + escapeHtml(tag) + '">' +
            '#' + escapeHtml(tag) +
          '</button>';
      });
      tagsHtml += '</span>';
    }

    // Cover Image HTML (780:440 aspect-ratio container with loading, loaded, and error states)
    let coverHtml = '';
    if (item.coverImage) {
      coverHtml =
        '<div class="card-cover-container is-loading">' +
          '<img class="card-cover-img" src="' + escapeHtml(item.coverImage) + '" alt="' + escapeHtml(cleanTitle) + '" loading="lazy" ' +
            'onload="this.parentElement.classList.remove(\'is-loading\'); this.parentElement.classList.add(\'is-loaded\');" ' +
            'onerror="var c=this.closest(\'.card-cover-container\'); if(c) c.remove();">' +
        '</div>';
    }

    // Bookmark State
    const bookmarked = isBookmarked(item.id);
    const bookmarkTooltip = bookmarked ? 'Убрать из сохраненного' : 'Сохранить статью';

    card.innerHTML =
      subscriptionBadgeHtml +
      '<div class="card-meta">' +
        '<div class="author-info">' +
          '<div class="author-avatar">' + escapeHtml(item.authorInitials || 'SC') + '</div>' +
          '<div class="author-details">' +
            '<span class="author-name">' + escapeHtml(item.author || 'Автор платформы') + '</span>' +
            '<div class="meta-sub-row">' +
              '<span class="publish-date">' + escapeHtml(item.date || 'Недавно') + '</span>' +
              (cleanRole ? '<span class="meta-dot"></span><span class="author-role">' + escapeHtml(cleanRole) + '</span>' : '') +
            '</div>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<h2 class="card-title">' +
        '<a href="' + articleUrl + '">' + escapeHtml(cleanTitle) + '</a>' +
      '</h2>' +
      (badgesHtml ? '<div class="card-meta-badges">' + badgesHtml + '</div>' : '') +
      coverHtml +
      '<p class="card-lead">' + escapeHtml(item.description || '') + '</p>' +
      (tagsHtml ? '<div class="card-tags">' + tagsHtml + '</div>' : '') +
      '<footer class="card-footer">' +
        '<div class="reading-time">' +
          '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>' +
          '<span>' + escapeHtml(item.readingTime || '5 мин') + ' чтения</span>' +
        '</div>' +
        '<button type="button" class="btn-card-bookmark ' + (bookmarked ? 'is-bookmarked' : '') + '" id="btn-bookmark" title="' + bookmarkTooltip + '" aria-label="' + bookmarkTooltip + '">' +
          '<svg width="17" height="17" viewBox="0 0 24 24" fill="' + (bookmarked ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"></path>' +
          '</svg>' +
        '</button>' +
      '</footer>';

    // Click isolation: clicking author must not open the article!
    const authorEl = card.querySelector('.author-info');
    if (authorEl) {
      authorEl.addEventListener('click', function (e) {
        e.stopPropagation();
      });
    }

    // Save scroll position when navigating to article
    const titleLink = card.querySelector('.card-title a');
    if (titleLink) {
      titleLink.addEventListener('click', function () {
        try {
          sessionStorage.setItem('sc_feed_scroll', String(window.scrollY || window.pageYOffset || 0));
        } catch (e) {}
      });
    }

    const bookmarkBtn = card.querySelector('.btn-card-bookmark');
    if (bookmarkBtn) {
      bookmarkBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        const active = toggleBookmark(item.id);
        bookmarkBtn.classList.toggle('is-bookmarked', active);
        const svg = bookmarkBtn.querySelector('svg');
        if (svg) svg.setAttribute('fill', active ? 'currentColor' : 'none');
        const newTooltip = active ? 'Убрать из сохраненного' : 'Сохранить статью';
        bookmarkBtn.title = newTooltip;
        bookmarkBtn.setAttribute('aria-label', newTooltip);
        if (state.savedOnly && !active) {
          card.remove();
          state.articles = state.articles.filter(function (a) { return a.id !== item.id; });
          state.total = Math.max(0, state.total - 1);
          updateResultsCount();
          if (state.articles.length === 0) {
            renderEmptyState();
          }
        }
      });
    }

    // Expand / collapse tags on "+N еще" click
    const tagExpandBtn = card.querySelector('.tag-expand-btn');
    const extraTags = card.querySelector('.extra-tags');
    if (tagExpandBtn && extraTags) {
      tagExpandBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        const isExpanded = extraTags.style.display !== 'none';
        extraTags.style.display = isExpanded ? 'none' : 'inline-flex';
        extraTags.style.gap = '6px';
        extraTags.style.flexWrap = 'wrap';
        tagExpandBtn.textContent = isExpanded ? '+' + hiddenTags.length + ' еще' : 'Свернуть';
        tagExpandBtn.setAttribute('aria-expanded', isExpanded ? 'false' : 'true');
      });
    }

    const tagChips = card.querySelectorAll('.tag-chip');
    tagChips.forEach(function (chip) {
      chip.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        const tag = chip.getAttribute('data-tag');
        if (tag) {
          state.search = tag;
          const searchInput = document.getElementById('feedSearchInput');
          const clearBtn = document.getElementById('feedSearchClearBtn');
          if (searchInput) searchInput.value = tag;
          if (clearBtn) clearBtn.style.display = 'inline-flex';
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        }
      });
    });

    return card;
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
      // Short list: show ONLY topics with published articles (count > 0)
      const nonZeroTopics = sortedTopics.filter(function (t) {
        const count = (topicCounts && typeof topicCounts[t.id] === 'number') ? topicCounts[t.id] : 0;
        return count > 0;
      });

      const visible = isSidebarTopicsExpanded ? sortedTopics : nonZeroTopics.slice(0, initialVisible);

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

      if (sortedTopics.length > visible.length || isSidebarTopicsExpanded) {
        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'widget-topics-toggle-btn';
        toggleBtn.id = 'btnToggleAllSidebarTopics';
        toggleBtn.textContent = isSidebarTopicsExpanded ? 'Свернуть' : 'Показать все (' + sortedTopics.length + ')';
        toggleBtn.addEventListener('click', function () {
          isSidebarTopicsExpanded = !isSidebarTopicsExpanded;
          renderItems();
        });
        listEl.appendChild(toggleBtn);
      }
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

    checkAuthStatus(function () {
      parseURLParams();
      fetchFeed(true);
    });

    window.addEventListener('popstate', function () {
      parseURLParams();
      fetchFeed(true);
    });
  });

})();
