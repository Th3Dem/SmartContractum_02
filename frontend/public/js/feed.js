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
  // 3. State Management & URL Synchronization
  // --------------------------------------------------------------------------
  const state = {
    search: '',
    topic: 'all',
    audience: 'all',
    format: 'all',
    complexity: 'all',
    period: 'all',
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
    noSubscriptions: false
  };

  let currentUser = null;
  let pendingTabAfterAuth = null;

  function parseURLParams() {
    const params = new URLSearchParams(window.location.search);
    state.search = (params.get('search') || params.get('q') || '').trim();
    state.topic = params.get('topic') || 'all';
    state.audience = params.get('audience') || 'all';
    state.format = params.get('format') || 'all';
    state.complexity = params.get('complexity') || 'all';
    state.period = params.get('period') || 'all';
    state.sort = params.get('sort') || 'newest';

    const tabParam = (params.get('tab') || '').toLowerCase();
    const savedParam = params.get('saved');

    if (tabParam === 'my') {
      state.tab = 'my';
      state.savedOnly = false;
    } else if (tabParam === 'saved' || savedParam === '1' || savedParam === 'true' || state.topic === 'saved') {
      state.tab = 'saved';
      state.savedOnly = true;
    } else {
      state.tab = 'all';
      state.savedOnly = false;
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

    const periodSelect = document.getElementById('feedPeriodSelect');
    if (periodSelect && state.period) {
      periodSelect.value = state.period;
    }

    const sortSelect = document.getElementById('feedSortSelect');
    if (sortSelect && state.sort) {
      sortSelect.value = state.sort;
    }

    const audienceSelect = document.getElementById('feedAudienceSelect');
    if (audienceSelect && state.audience) {
      audienceSelect.value = state.audience;
    }

    const formatSelect = document.getElementById('feedFormatSelect');
    if (formatSelect && state.format) {
      formatSelect.value = state.format;
    }

    const complexitySelect = document.getElementById('feedComplexitySelect');
    if (complexitySelect && state.complexity) {
      complexitySelect.value = state.complexity;
    }

    updatePeriodVisibility();
    updateSubnavTabsUI();
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
    if (!state.savedOnly && state.topic && state.topic !== 'all') {
      params.set('topic', state.topic);
    }
    if (state.audience && state.audience !== 'all') params.set('audience', state.audience);
    if (state.format && state.format !== 'all') params.set('format', state.format);
    if (state.complexity && state.complexity !== 'all') params.set('complexity', state.complexity);
    if (state.period && state.period !== 'all') params.set('period', state.period);
    if (state.sort && state.sort !== 'newest') params.set('sort', state.sort);

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
  // 5. Sub-Nav Bar (Second Level Menu)
  // --------------------------------------------------------------------------
  function initSubnavTabs() {
    const tabAll = document.getElementById('tabFeedAll');
    const tabMy = document.getElementById('tabFeedMy');
    const tabSaved = document.getElementById('feedSavedTab');

    if (tabAll) {
      tabAll.addEventListener('click', function () {
        switchTab('all');
      });
    }
    if (tabMy) {
      tabMy.addEventListener('click', function () {
        if (!currentUser) {
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

  // --------------------------------------------------------------------------
  // 6. UI Controls Initialization
  // --------------------------------------------------------------------------
  function initControls() {
    // Populate Audience select from PublicationConfig
    const audienceSelect = document.getElementById('feedAudienceSelect');
    if (audienceSelect && window.PublicationConfig && Array.isArray(window.PublicationConfig.AUDIENCES)) {
      window.PublicationConfig.AUDIENCES.forEach(function (aud) {
        const opt = document.createElement('option');
        opt.value = aud.id;
        opt.textContent = aud.title;
        audienceSelect.appendChild(opt);
      });
      if (state.audience) audienceSelect.value = state.audience;
    }

    // Populate Format select from PublicationConfig
    const formatSelect = document.getElementById('feedFormatSelect');
    if (formatSelect && window.PublicationConfig && Array.isArray(window.PublicationConfig.FORMATS)) {
      window.PublicationConfig.FORMATS.forEach(function (fmt) {
        const opt = document.createElement('option');
        opt.value = fmt.id;
        opt.textContent = fmt.title;
        formatSelect.appendChild(opt);
      });
      if (state.format) formatSelect.value = state.format;
    }

    // Search input & clear button
    const searchInput = document.getElementById('feedSearchInput');
    const clearBtn = document.getElementById('feedSearchClearBtn');

    if (searchInput) {
      let debounceTimer = null;
      searchInput.addEventListener('input', function () {
        const val = searchInput.value.trim();
        if (clearBtn) {
          clearBtn.style.display = searchInput.value ? 'inline-flex' : 'none';
        }
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () {
          if (state.search !== val) {
            state.search = val;
            state.offset = 0;
            syncURL(false);
            fetchFeed(true);
          }
        }, 350);
      });

      searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          clearTimeout(debounceTimer);
          const val = searchInput.value.trim();
          state.search = val;
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        }
      });
    }

    if (clearBtn && searchInput) {
      clearBtn.addEventListener('click', function () {
        searchInput.value = '';
        clearBtn.style.display = 'none';
        state.search = '';
        state.offset = 0;
        syncURL(false);
        fetchFeed(true);
        searchInput.focus();
      });
    }

    // Sorters
    const periodSelect = document.getElementById('feedPeriodSelect');
    if (periodSelect) {
      periodSelect.addEventListener('change', function () {
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

  function resetAllFilters() {
    state.search = '';
    state.topic = 'all';
    state.audience = 'all';
    state.format = 'all';
    state.complexity = 'all';
    state.period = 'all';
    state.sort = 'newest';
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

    const audienceSelect = document.getElementById('feedAudienceSelect');
    if (audienceSelect) audienceSelect.value = 'all';

    const formatSelect = document.getElementById('feedFormatSelect');
    if (formatSelect) formatSelect.value = 'all';

    const complexitySelect = document.getElementById('feedComplexitySelect');
    if (complexitySelect) complexitySelect.value = 'all';

    updatePeriodVisibility();
    updateModalFiltersState();
    syncURL(false);
    fetchFeed(true);
  }

  function updateFilterBadge() {
    let count = 0;
    if (state.topic && state.topic !== 'all') count++;
    if (state.audience && state.audience !== 'all') count++;
    if (state.format && state.format !== 'all') count++;
    if (state.complexity && state.complexity !== 'all') count++;

    const badge = document.getElementById('feedFiltersCountBadge');
    if (badge) {
      if (count > 0) {
        badge.textContent = count;
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

    if (!state.savedOnly && state.topic && state.topic !== 'all') {
      let topicName = state.topic;
      if (window.PublicationConfig) {
        const t = window.PublicationConfig.getTopicById(state.topic);
        if (t) topicName = t.title;
      }
      chips.push({
        id: 'topic',
        label: 'Тема: ' + topicName,
        remove: function () {
          state.topic = 'all';
          state.offset = 0;
          updateModalFiltersState();
          syncURL(false);
          fetchFeed(true);
        }
      });
    }

    if (state.audience && state.audience !== 'all') {
      let audName = state.audience;
      if (window.PublicationConfig) {
        const a = window.PublicationConfig.getAudienceById(state.audience);
        if (a) audName = a.title;
      }
      chips.push({
        id: 'audience',
        label: 'Аудитория: ' + audName,
        remove: function () {
          state.audience = 'all';
          const sel = document.getElementById('feedAudienceSelect');
          if (sel) sel.value = 'all';
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        }
      });
    }

    if (state.format && state.format !== 'all') {
      let fmtName = state.format;
      if (window.PublicationConfig) {
        const f = window.PublicationConfig.getFormatById(state.format);
        if (f) fmtName = f.title;
      }
      chips.push({
        id: 'format',
        label: 'Формат: ' + fmtName,
        remove: function () {
          state.format = 'all';
          const sel = document.getElementById('feedFormatSelect');
          if (sel) sel.value = 'all';
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        }
      });
    }

    if (state.complexity && state.complexity !== 'all') {
      let compName = state.complexity;
      if (window.PublicationConfig) {
        const c = window.PublicationConfig.getComplexityById(state.complexity);
        if (c) compName = c.title;
      }
      chips.push({
        id: 'complexity',
        label: 'Сложность: ' + compName,
        remove: function () {
          state.complexity = 'all';
          const sel = document.getElementById('feedComplexitySelect');
          if (sel) sel.value = 'all';
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
        '<button type="button" class="chip-remove-btn" title="Удалить фильтр" aria-label="Удалить фильтр">' +
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

  // --------------------------------------------------------------------------
  // 7. Unified Filters Modal
  // --------------------------------------------------------------------------
  function initFiltersModal() {
    const openBtn = document.getElementById('btnFeedFiltersToggle');
    const closeBtn = document.getElementById('btnCloseFiltersModal');
    const modal = document.getElementById('feedFiltersModal');
    const applyBtn = document.getElementById('btnApplyFilters');
    const resetBtn = document.getElementById('feedResetFiltersBtn');
    const topicSearchInput = document.getElementById('filterTopicSearchInput');

    if (openBtn && modal) {
      openBtn.addEventListener('click', function () {
        modal.style.display = 'flex';
        updateModalFiltersState();
      });
    }

    if (closeBtn && modal) {
      closeBtn.addEventListener('click', function () {
        modal.style.display = 'none';
      });
    }

    if (modal) {
      modal.addEventListener('click', function (e) {
        if (e.target === modal) modal.style.display = 'none';
      });
    }

    // Escape key closes modal
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        if (modal && modal.style.display !== 'none') modal.style.display = 'none';
        const subsModal = document.getElementById('subscriptionsModal');
        if (subsModal && subsModal.style.display !== 'none') {
          subsModal.style.display = 'none';
          if (state.tab === 'my') fetchFeed(true);
        }
        const authModal = document.getElementById('authModal');
        if (authModal && authModal.style.display !== 'none') authModal.style.display = 'none';
      }
    });

    // Topic search filter inside modal
    if (topicSearchInput) {
      topicSearchInput.addEventListener('input', function () {
        const q = topicSearchInput.value.trim().toLowerCase();
        const btns = document.querySelectorAll('#modalTopicsFilterBar .feed-filter-btn');
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

    // Topic button selection inside modal
    const topicsBar = document.getElementById('modalTopicsFilterBar');
    if (topicsBar) {
      topicsBar.addEventListener('click', function (e) {
        const btn = e.target.closest('.feed-filter-btn');
        if (!btn) return;
        document.querySelectorAll('#modalTopicsFilterBar .feed-filter-btn').forEach(function (b) {
          const isActive = (b === btn);
          b.classList.toggle('active', isActive);
          b.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });
      });
    }

    if (applyBtn) {
      applyBtn.addEventListener('click', function () {
        const activeTopicBtn = document.querySelector('#modalTopicsFilterBar .feed-filter-btn.active');
        state.topic = activeTopicBtn ? (activeTopicBtn.getAttribute('data-topic') || 'all') : 'all';

        const aud = document.getElementById('feedAudienceSelect');
        if (aud) state.audience = aud.value;

        const fmt = document.getElementById('feedFormatSelect');
        if (fmt) state.format = fmt.value;

        const comp = document.getElementById('feedComplexitySelect');
        if (comp) state.complexity = comp.value;

        state.offset = 0;
        modal.style.display = 'none';
        syncURL(false);
        fetchFeed(true);
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        state.topic = 'all';
        state.audience = 'all';
        state.format = 'all';
        state.complexity = 'all';
        state.offset = 0;
        updateModalFiltersState();
        modal.style.display = 'none';
        syncURL(false);
        fetchFeed(true);
      });
    }
  }

  function updateModalFiltersState() {
    document.querySelectorAll('#modalTopicsFilterBar .feed-filter-btn').forEach(function (btn) {
      const isActive = btn.getAttribute('data-topic') === state.topic;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });

    const aud = document.getElementById('feedAudienceSelect');
    if (aud) aud.value = state.audience || 'all';

    const fmt = document.getElementById('feedFormatSelect');
    if (fmt) fmt.value = state.format || 'all';

    const comp = document.getElementById('feedComplexitySelect');
    if (comp) comp.value = state.complexity || 'all';
  }

  // --------------------------------------------------------------------------
  // 8. Subscriptions Management Modal
  // --------------------------------------------------------------------------
  let subsData = { authors: [], topics: [], tags: [] };
  let activeSubsType = 'author';

  function initSubscriptionsModal() {
    const manageBtn = document.getElementById('btnManageSubscriptions');
    const closeBtn = document.getElementById('btnCloseSubsModal');
    const modal = document.getElementById('subscriptionsModal');
    const searchInput = document.getElementById('subsSearchInput');

    if (manageBtn && modal) {
      manageBtn.addEventListener('click', openSubscriptionsModal);
    }

    if (closeBtn && modal) {
      closeBtn.addEventListener('click', function () {
        modal.style.display = 'none';
        if (state.tab === 'my') fetchFeed(true);
      });
    }

    if (modal) {
      modal.addEventListener('click', function (e) {
        if (e.target === modal) {
          modal.style.display = 'none';
          if (state.tab === 'my') fetchFeed(true);
        }
      });
    }

    // Tabs
    const tabAuthors = document.getElementById('tabSubsAuthors');
    const tabTopics = document.getElementById('tabSubsTopics');
    const tabTags = document.getElementById('tabSubsTags');

    if (tabAuthors) tabAuthors.addEventListener('click', function () { switchSubsTab('author'); });
    if (tabTopics) tabTopics.addEventListener('click', function () { switchSubsTab('topic'); });
    if (tabTags) tabTags.addEventListener('click', function () { switchSubsTab('tag'); });

    if (searchInput) {
      searchInput.addEventListener('input', renderSubsList);
    }
  }

  function openSubscriptionsModal() {
    const modal = document.getElementById('subscriptionsModal');
    if (!modal) return;
    modal.style.display = 'flex';

    fetch('/api/subscriptions/entities')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.success) {
          subsData.authors = data.authors || [];
          subsData.topics = data.topics || [];
          subsData.tags = data.tags || [];

          const aCount = document.getElementById('subsAuthorsCount');
          const tCount = document.getElementById('subsTopicsCount');
          const tgCount = document.getElementById('subsTagsCount');
          if (aCount) aCount.textContent = subsData.authors.length;
          if (tCount) tCount.textContent = subsData.topics.length;
          if (tgCount) tgCount.textContent = subsData.tags.length;

          renderSubsList();
        }
      })
      .catch(function (err) {
        console.error('Failed to load subscriptions entities:', err);
      });
  }

  function switchSubsTab(type) {
    activeSubsType = type;
    const tabAuthors = document.getElementById('tabSubsAuthors');
    const tabTopics = document.getElementById('tabSubsTopics');
    const tabTags = document.getElementById('tabSubsTags');

    if (tabAuthors) tabAuthors.classList.toggle('active', type === 'author');
    if (tabTopics) tabTopics.classList.toggle('active', type === 'topic');
    if (tabTags) tabTags.classList.toggle('active', type === 'tag');

    const searchInput = document.getElementById('subsSearchInput');
    if (searchInput) searchInput.value = '';
    renderSubsList();
  }

  function renderSubsList() {
    const container = document.getElementById('subsListContainer');
    if (!container) return;
    container.innerHTML = '';

    const searchInput = document.getElementById('subsSearchInput');
    const q = (searchInput ? searchInput.value.trim().toLowerCase() : '');

    let list = [];
    if (activeSubsType === 'author') list = subsData.authors;
    else if (activeSubsType === 'topic') list = subsData.topics;
    else if (activeSubsType === 'tag') list = subsData.tags;

    if (q) {
      list = list.filter(function (item) {
        return (item.title && item.title.toLowerCase().indexOf(q) !== -1) ||
               (item.role && item.role.toLowerCase().indexOf(q) !== -1);
      });
    }

    if (list.length === 0) {
      container.innerHTML = '<div style="text-align: center; padding: 28px; color: var(--text-muted); font-size: 0.88rem;">Ничего не найдено</div>';
      return;
    }

    list.forEach(function (item) {
      const el = document.createElement('div');
      el.className = 'subs-item';
      const subText = item.role || (item.count !== undefined ? (item.count + ' публикаций') : '');
      const isSub = Boolean(item.isSubscribed);

      el.innerHTML =
        '<div class="subs-item-info">' +
          '<span class="subs-item-title">' + escapeHtml(item.title) + '</span>' +
          (subText ? '<span class="subs-item-sub">' + escapeHtml(subText) + '</span>' : '') +
        '</div>' +
        '<button type="button" class="btn btn-secondary subs-toggle-btn ' + (isSub ? 'is-subscribed' : '') + '" data-id="' + escapeHtml(item.id) + '">' +
          (isSub ? 'Вы подписаны' : 'Подписаться') +
        '</button>';

      const btn = el.querySelector('.subs-toggle-btn');
      btn.addEventListener('click', function () {
        toggleSubscription(activeSubsType, item.id, item.title, btn, item);
      });

      container.appendChild(el);
    });
  }

  function toggleSubscription(targetType, targetId, targetTitle, btn, item) {
    if (!currentUser) {
      openAuthModal();
      return;
    }

    fetch('/api/subscriptions/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ targetType: targetType, targetId: targetId, targetTitle: targetTitle })
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.success) {
          item.isSubscribed = data.subscribed;
          btn.classList.toggle('is-subscribed', data.subscribed);
          btn.textContent = data.subscribed ? 'Вы подписаны' : 'Подписаться';
          showToast(data.subscribed ? 'Вы подписались на «' + targetTitle + '»' : 'Вы отписались от «' + targetTitle + '»');
        }
      })
      .catch(function (err) {
        console.error('Failed to toggle subscription:', err);
      });
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
    if (!state.savedOnly && state.topic && state.topic !== 'all') {
      params.set('topic', state.topic);
    }
    if (state.audience && state.audience !== 'all') params.set('audience', state.audience);
    if (state.format && state.format !== 'all') params.set('format', state.format);
    if (state.complexity && state.complexity !== 'all') params.set('complexity', state.complexity);
    if (state.period && state.period !== 'all') params.set('period', state.period);
    if (state.sort) params.set('sort', state.sort);
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
          state.noSubscriptions = Boolean(data.noSubscriptions);
          if (isInitial) {
            state.articles = data.articles || [];
          } else {
            const existingIds = new Set(state.articles.map(function (a) { return a.id; }));
            const incoming = (data.articles || []).filter(function (a) { return !existingIds.has(a.id); });
            state.articles = state.articles.concat(incoming);
          }
          state.total = data.total || 0;
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

    let items = FALLBACK_ARTICLES.slice();

    if (state.tab === 'my') {
      items = items.filter(function (a) {
        return a.topics && a.topics.indexOf('smart-contracts-development') !== -1;
      });
      items.forEach(function (a) {
        a.subscriptionReason = 'Вы подписаны на тему «Разработка смарт-контрактов»';
      });
    } else if (state.topic && state.topic !== 'all') {
      items = items.filter(function (a) {
        return a.topics && a.topics.indexOf(state.topic) !== -1;
      });
    }

    if (state.search) {
      const q = state.search.toLowerCase();
      items = items.filter(function (a) {
        const author = a.author || '';
        const role = a.authorRole || '';
        const kws = Array.isArray(a.keywords) ? a.keywords.join(' ') : '';
        const haystack = (a.title + ' ' + author + ' ' + role + ' ' + (a.description || '') + ' ' + kws).toLowerCase();
        return haystack.indexOf(q) !== -1;
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
    let word = 'публикаций';
    if (n % 10 === 1 && n % 100 !== 11) {
      word = 'публикация';
    } else if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) {
      word = 'публикации';
    }

    if (n === 0) {
      el.textContent = 'Ничего не найдено';
    } else {
      el.textContent = 'Найдено ' + n + ' ' + word;
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
            '<p class="empty-state-desc">Подпишитесь на интересных авторов, ключевые темы или теги, чтобы формировать персональную ленту материалов.</p>' +
            '<button type="button" class="btn btn-primary empty-state-btn" id="btnEmptyChooseSubs">' +
              '<span>Выбрать темы и авторов</span>' +
            '</button>' +
          '</div>';

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
            '<p class="empty-state-desc">Попробуйте расширить круг подписок или сбросить активные фильтры.</p>' +
            '<button type="button" class="btn btn-secondary empty-state-btn" id="btnEmptyManageSubs">' +
              '<span>Управление подписками</span>' +
            '</button>' +
          '</div>';

        const manageBtn = document.getElementById('btnEmptyManageSubs');
        if (manageBtn) {
          manageBtn.addEventListener('click', openSubscriptionsModal);
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
  // 10. Article Card Generator (Accurate Tokens, Click Isolation)
  // --------------------------------------------------------------------------
  function createCardElement(item) {
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
    initFiltersModal();
    initSubscriptionsModal();
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
