/**
 * SmartContractum Feed Page - Native Modular JavaScript
 * 100% Offline-First, Zero Emojis, Clean Performance
 * Production-ready search, filters, topic navigation, and bookmarks.
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
      counterEl.style.display = count > 0 ? 'inline-block' : 'inline-block';
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
    savedOnly: false,
    limit: 10,
    offset: 0,
    total: 0,
    hasMore: false,
    articles: [],
    topicCounts: {},
    isLoading: false
  };

  function parseURLParams() {
    const params = new URLSearchParams(window.location.search);
    state.search = (params.get('search') || params.get('q') || '').trim();
    state.topic = params.get('topic') || 'all';
    state.audience = params.get('audience') || 'all';
    state.format = params.get('format') || 'all';
    state.complexity = params.get('complexity') || 'all';
    state.period = params.get('period') || 'all';
    state.sort = params.get('sort') || 'newest';

    const savedParam = params.get('saved');
    state.savedOnly = savedParam === '1' || savedParam === 'true' || state.topic === 'saved';
    if (state.savedOnly) {
      state.topic = 'saved';
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

    updateTopicButtonsState();
    updateFilterBadge();
  }

  function syncURL(replace) {
    const params = new URLSearchParams();
    if (state.search) params.set('search', state.search);
    if (state.savedOnly) {
      params.set('saved', '1');
    } else if (state.topic && state.topic !== 'all') {
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
  // 4. UI Controls Initialization
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
    const searchBtn = document.getElementById('feedSearchBtn');
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

    if (searchBtn && searchInput) {
      searchBtn.addEventListener('click', function () {
        const val = searchInput.value.trim();
        state.search = val;
        state.offset = 0;
        syncURL(false);
        fetchFeed(true);
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
        syncURL(false);
        fetchFeed(true);
      });
    }

    // Additional Filters Panel Toggle
    const filtersToggleBtn = document.getElementById('btnFeedFiltersToggle');
    const filtersPanel = document.getElementById('feedFiltersPanel');
    if (filtersToggleBtn && filtersPanel) {
      filtersToggleBtn.addEventListener('click', function () {
        const isOpen = filtersPanel.style.display !== 'none';
        filtersPanel.style.display = isOpen ? 'none' : 'flex';
        filtersToggleBtn.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
        filtersToggleBtn.classList.toggle('is-active', !isOpen);
      });
    }

    // Additional Filters dropdown changes
    if (audienceSelect) {
      audienceSelect.addEventListener('change', function () {
        state.audience = audienceSelect.value;
        state.offset = 0;
        syncURL(false);
        fetchFeed(true);
      });
    }

    if (formatSelect) {
      formatSelect.addEventListener('change', function () {
        state.format = formatSelect.value;
        state.offset = 0;
        syncURL(false);
        fetchFeed(true);
      });
    }

    const complexitySelect = document.getElementById('feedComplexitySelect');
    if (complexitySelect) {
      complexitySelect.addEventListener('change', function () {
        state.complexity = complexitySelect.value;
        state.offset = 0;
        syncURL(false);
        fetchFeed(true);
      });
    }

    const resetFiltersBtn = document.getElementById('feedResetFiltersBtn');
    if (resetFiltersBtn) {
      resetFiltersBtn.addEventListener('click', function () {
        if (audienceSelect) audienceSelect.value = 'all';
        if (formatSelect) formatSelect.value = 'all';
        if (complexitySelect) complexitySelect.value = 'all';
        state.audience = 'all';
        state.format = 'all';
        state.complexity = 'all';
        state.offset = 0;
        syncURL(false);
        fetchFeed(true);
      });
    }

    // Topics Bar Buttons
    const topicsBar = document.querySelector('.feed-topics-bar');
    if (topicsBar) {
      topicsBar.addEventListener('click', function (e) {
        const topicBtn = e.target.closest('.feed-filter-btn');
        if (!topicBtn || topicBtn.id === 'feedMoreTopicsBtn') return;

        if (topicBtn.id === 'feedSavedTab') {
          state.savedOnly = true;
          state.topic = 'saved';
        } else {
          const topic = topicBtn.getAttribute('data-topic');
          if (topic) {
            state.topic = topic;
            state.savedOnly = false;
          }
        }
        state.offset = 0;
        updateTopicButtonsState();
        syncURL(false);
        fetchFeed(true);
      });
    }

    // More Topics Dropdown
    const moreBtn = document.getElementById('feedMoreTopicsBtn');
    const dropdown = document.getElementById('feedTopicsDropdown');
    if (moreBtn && dropdown) {
      moreBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        const isOpen = dropdown.style.display !== 'none';
        dropdown.style.display = isOpen ? 'none' : 'flex';
        moreBtn.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
      });

      dropdown.addEventListener('click', function (e) {
        const item = e.target.closest('.feed-dropdown-item');
        if (item) {
          const topic = item.getAttribute('data-topic');
          if (topic) {
            state.topic = topic;
            state.savedOnly = false;
            state.offset = 0;
            dropdown.style.display = 'none';
            moreBtn.setAttribute('aria-expanded', 'false');
            updateTopicButtonsState();
            syncURL(false);
            fetchFeed(true);
          }
        }
      });

      document.addEventListener('click', function (e) {
        if (!e.target.closest('.feed-more-topics-wrap')) {
          dropdown.style.display = 'none';
          moreBtn.setAttribute('aria-expanded', 'false');
        }
      });
    }

    // Active Chips Reset All Button
    const resetAllBtn = document.getElementById('feedResetAllBtn');
    if (resetAllBtn) {
      resetAllBtn.addEventListener('click', resetAllFilters);
    }

    // Load More Button
    const loadMoreBtn = document.getElementById('feedLoadMoreBtn');
    if (loadMoreBtn) {
      loadMoreBtn.addEventListener('click', function () {
        if (!state.isLoading && state.hasMore) {
          state.offset += state.limit;
          fetchFeed(false);
        }
      });
    }

    // History popstate
    window.addEventListener('popstate', function () {
      parseURLParams();
      fetchFeed(true);
    });
  }

  function resetAllFilters() {
    state.search = '';
    state.topic = 'all';
    state.audience = 'all';
    state.format = 'all';
    state.complexity = 'all';
    state.period = 'all';
    state.savedOnly = false;
    state.offset = 0;

    const searchInput = document.getElementById('feedSearchInput');
    const clearBtn = document.getElementById('feedSearchClearBtn');
    if (searchInput) {
      searchInput.value = '';
      if (clearBtn) clearBtn.style.display = 'none';
    }

    const periodSelect = document.getElementById('feedPeriodSelect');
    if (periodSelect) periodSelect.value = 'all';

    const audienceSelect = document.getElementById('feedAudienceSelect');
    if (audienceSelect) audienceSelect.value = 'all';

    const formatSelect = document.getElementById('feedFormatSelect');
    if (formatSelect) formatSelect.value = 'all';

    const complexitySelect = document.getElementById('feedComplexitySelect');
    if (complexitySelect) complexitySelect.value = 'all';

    updateTopicButtonsState();
    syncURL(false);
    fetchFeed(true);
  }

  function updateTopicButtonsState() {
    const buttons = document.querySelectorAll('.feed-topics-bar .feed-filter-btn');
    buttons.forEach(function (btn) {
      if (btn.id === 'feedMoreTopicsBtn') return;

      if (btn.id === 'feedSavedTab') {
        const isSaved = state.savedOnly;
        btn.classList.toggle('active', isSaved);
        btn.setAttribute('aria-selected', isSaved ? 'true' : 'false');
      } else {
        const btnTopic = btn.getAttribute('data-topic');
        const isActive = !state.savedOnly && btnTopic === state.topic;
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
      }
    });

    const moreBtn = document.getElementById('feedMoreTopicsBtn');
    const dropdownItems = document.querySelectorAll('.feed-dropdown-item');
    let isDropdownTopicActive = false;

    dropdownItems.forEach(function (item) {
      const topic = item.getAttribute('data-topic');
      const isActive = !state.savedOnly && topic === state.topic;
      item.classList.toggle('active', isActive);
      if (isActive) isDropdownTopicActive = true;
    });

    if (moreBtn) {
      moreBtn.classList.toggle('active', isDropdownTopicActive);
    }
  }

  function updateFilterBadge() {
    let count = 0;
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
        label: 'Поиск: "' + state.search + '"',
        remove: function () {
          state.search = '';
          const input = document.getElementById('feedSearchInput');
          if (input) input.value = '';
          const clear = document.getElementById('feedSearchClearBtn');
          if (clear) clear.style.display = 'none';
          state.offset = 0;
          syncURL(false);
          fetchFeed(true);
        }
      });
    }

    if (state.savedOnly) {
      chips.push({
        label: 'Сохраненные',
        remove: function () {
          state.savedOnly = false;
          state.topic = 'all';
          state.offset = 0;
          updateTopicButtonsState();
          syncURL(false);
          fetchFeed(true);
        }
      });
    } else if (state.topic && state.topic !== 'all') {
      const topicObj = window.PublicationConfig && window.PublicationConfig.getTopicById(state.topic);
      chips.push({
        label: 'Тема: ' + (topicObj ? topicObj.title : state.topic),
        remove: function () {
          state.topic = 'all';
          state.offset = 0;
          updateTopicButtonsState();
          syncURL(false);
          fetchFeed(true);
        }
      });
    }

    if (state.audience && state.audience !== 'all') {
      const audObj = window.PublicationConfig && window.PublicationConfig.getAudienceById(state.audience);
      chips.push({
        label: 'Аудитория: ' + (audObj ? audObj.title : state.audience),
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
      const fmtObj = window.PublicationConfig && window.PublicationConfig.getFormatById(state.format);
      chips.push({
        label: 'Формат: ' + (fmtObj ? fmtObj.title : state.format),
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
      const compObj = window.PublicationConfig && window.PublicationConfig.getComplexityById(state.complexity);
      chips.push({
        label: 'Сложность: ' + (compObj ? compObj.title : state.complexity),
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

    if (state.period && state.period !== 'all') {
      const periodLabel = state.period === 'week' ? 'За неделю' : 'За месяц';
      chips.push({
        label: 'Период: ' + periodLabel,
        remove: function () {
          state.period = 'all';
          const sel = document.getElementById('feedPeriodSelect');
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
      const chipEl = document.createElement('span');
      chipEl.className = 'active-chip';
      chipEl.innerHTML =
        '<span>' + escapeHtml(chip.label) + '</span>' +
        '<button type="button" class="chip-remove-btn" title="Удалить фильтр" aria-label="Удалить фильтр">' +
          '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<line x1="18" y1="6" x2="6" y2="18"></line>' +
            '<line x1="6" y1="6" x2="18" y2="18"></line>' +
          '</svg>' +
        '</button>';

      chipEl.querySelector('.chip-remove-btn').addEventListener('click', chip.remove);
      list.appendChild(chipEl);
    });
  }

  // --------------------------------------------------------------------------
  // 5. Data Fetching & Rendering
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
        if (!res.ok) throw new Error('API status: ' + res.status);
        return res.json();
      })
      .then(function (data) {
        state.isLoading = false;
        if (data && data.success) {
          if (isInitial) {
            state.articles = data.articles || [];
          } else {
            state.articles = state.articles.concat(data.articles || []);
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

    if (state.topic && state.topic !== 'all') {
      items = items.filter(function (a) {
        return a.topics && a.topics.indexOf(state.topic) !== -1;
      });
    }

    if (state.search) {
      const q = state.search.toLowerCase();
      items = items.filter(function (a) {
        return (
          a.title.toLowerCase().indexOf(q) !== -1 ||
          (a.description && a.description.toLowerCase().indexOf(q) !== -1)
        );
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

    if (state.savedOnly) {
      el.textContent = 'Сохраненных публикаций: ' + state.total;
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

    // Render cards
    state.articles.forEach(function (item, index) {
      // If not initial, only append newly loaded items
      if (!isInitial && index < state.offset) return;

      const card = createCardElement(item);
      container.appendChild(card);
    });

    updatePaginationControls();
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

    const isSaved = state.savedOnly;
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
      btn.addEventListener('click', resetAllFilters);
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
  // 6. Article Card Generator (Accurate Tokens, Click Isolation)
  // --------------------------------------------------------------------------
  function createCardElement(item) {
    const card = document.createElement('article');
    card.className = 'feed-card';
    card.setAttribute('data-id', item.id);
    card.setAttribute('data-topic', item.topic || '');

    const articleUrl = 'article.html?id=' + encodeURIComponent(item.id);

    // Topic Title & Badge
    let topicTitle = '';
    if (window.PublicationConfig && item.topic) {
      const t = window.PublicationConfig.getTopicById(item.topic);
      if (t) topicTitle = t.title;
    }

    // Format & Complexity Titles
    let formatTitle = '';
    if (window.PublicationConfig && item.format) {
      const f = window.PublicationConfig.getFormatById(item.format);
      if (f) formatTitle = f.title;
    }

    let complexityTitle = '';
    let complexityClass = '';
    if (window.PublicationConfig && item.complexity && item.complexity !== 'none') {
      const c = window.PublicationConfig.getComplexityById(item.complexity);
      if (c) {
        complexityTitle = c.title;
        complexityClass = 'complexity-' + item.complexity;
      }
    }

    // Badges HTML
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

    // Tags HTML: Up to 3-4 tags directly, rest via "+N"
    const tags = Array.isArray(item.keywords) ? item.keywords : [];
    const maxVisibleTags = 4;
    let tagsHtml = '';
    const visibleTags = tags.slice(0, maxVisibleTags);
    const hiddenCount = tags.length - maxVisibleTags;

    visibleTags.forEach(function (tag) {
      tagsHtml +=
        '<button type="button" class="tag-chip" data-tag="' + escapeHtml(tag) + '">' +
          '#' + escapeHtml(tag) +
        '</button>';
    });

    if (hiddenCount > 0) {
      tagsHtml += '<span class="tag-chip-more">еще ' + hiddenCount + '</span>';
    }

    // Cover Image HTML (Only if present!)
    let coverHtml = '';
    if (item.coverImage) {
      coverHtml =
        '<div class="card-cover-container">' +
          '<img class="card-cover-img" src="' + item.coverImage + '" alt="' + escapeHtml(item.title) + '" loading="lazy">' +
        '</div>';
    }

    // Bookmark State
    const bookmarked = isBookmarked(item.id);

    card.innerHTML =
      '<div class="card-meta">' +
        '<div class="author-info">' +
          '<div class="author-avatar">' + escapeHtml(item.authorInitials || 'SC') + '</div>' +
          '<div class="author-details">' +
            '<span class="author-name">' + escapeHtml(item.author || 'Автор платформы') + '</span>' +
            '<div class="meta-sub-row">' +
              '<span class="publish-date">' + escapeHtml(item.date || 'Недавно') + '</span>' +
              (item.authorRole ? '<span class="meta-dot"></span><span class="author-role">' + escapeHtml(item.authorRole) + '</span>' : '') +
            '</div>' +
          '</div>' +
        '</div>' +
        '<div class="card-meta-badges">' + badgesHtml + '</div>' +
      '</div>' +
      '<h2 class="card-title">' +
        '<a href="' + articleUrl + '">' + escapeHtml(item.title) + '</a>' +
      '</h2>' +
      coverHtml +
      '<p class="card-lead">' + escapeHtml(item.description || '') + '</p>' +
      (tagsHtml ? '<div class="card-tags">' + tagsHtml + '</div>' : '') +
      '<footer class="card-footer">' +
        '<div class="reading-time">' +
          '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>' +
          '<span>' + escapeHtml(item.readingTime || '5 мин') + ' чтения</span>' +
        '</div>' +
        '<button type="button" class="btn-card-bookmark ' + (bookmarked ? 'is-bookmarked' : '') + '" id="btn-bookmark" title="' + (bookmarked ? 'Удалить из закладок' : 'Сохранить в закладки') + '" aria-label="Закладка">' +
          '<svg width="17" height="17" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"></path>' +
          '</svg>' +
        '</button>' +
      '</footer>';

    // Click isolation: clicking author, tags, bookmark button must not open the article!
    const authorEl = card.querySelector('.author-info');
    if (authorEl) {
      authorEl.addEventListener('click', function (e) {
        e.stopPropagation();
      });
    }

    const bookmarkBtn = card.querySelector('.btn-card-bookmark');
    if (bookmarkBtn) {
      bookmarkBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        const active = toggleBookmark(item.id);
        bookmarkBtn.classList.toggle('is-bookmarked', active);
        bookmarkBtn.title = active ? 'Удалить из закладок' : 'Сохранить в закладки';
        if (state.savedOnly && !active) {
          // If in saved mode and item unbookmarked, remove card smoothly
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

    const tagChips = card.querySelectorAll('.tag-chip');
    tagChips.forEach(function (chip) {
      chip.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        const tag = chip.getAttribute('data-tag');
        if (tag) {
          state.search = tag;
          const searchInput = document.getElementById('feedSearchInput');
          if (searchInput) searchInput.value = tag;
          const clearBtn = document.getElementById('feedSearchClearBtn');
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
  // 7. Sidebar Widgets Management
  // --------------------------------------------------------------------------
  function renderSidebarTopics(topicCounts) {
    const listEl = document.getElementById('widgetTopicsList');
    if (!listEl || !window.PublicationConfig || !Array.isArray(window.PublicationConfig.TOPICS)) return;

    listEl.innerHTML = '';
    window.PublicationConfig.TOPICS.forEach(function (topic) {
      const count = (topicCounts && topicCounts[topic.id]) || 0;
      const isSelected = !state.savedOnly && state.topic === topic.id;

      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'widget-topic-row ' + (isSelected ? 'is-active' : '');
      row.innerHTML =
        '<span class="widget-topic-title">' + escapeHtml(topic.title) + '</span>' +
        '<span class="widget-topic-count">' + count + '</span>';

      row.addEventListener('click', function () {
        if (state.topic === topic.id && !state.savedOnly) {
          state.topic = 'all';
        } else {
          state.topic = topic.id;
          state.savedOnly = false;
        }
        state.offset = 0;
        updateTopicButtonsState();
        syncURL(false);
        fetchFeed(true);
      });

      listEl.appendChild(row);
    });
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
  // 8. Offline Fallback Seed Articles
  // --------------------------------------------------------------------------
  const FALLBACK_ARTICLES = [
    {
      id: 'art-01',
      title: 'Интеграция смарт-контрактов с платформой цифрового рубля Банка России',
      description: 'Архитектурный анализ взаимодействия шлюзов ПКСК с платформой цифрового рубля: моделирование атомарных транзакций, двухфазный коммит и валидация криптографических подписей по ГОСТ Р 34.12-2015.',
      author: 'Алексей Смирнов',
      authorInitials: 'АС',
      authorRole: 'Главный архитектор ПКСК',
      date: '26 сентября 2026',
      topics: ['digital-ruble-payments', 'pksc-architecture', 'smart-contracts-development'],
      topic: 'digital-ruble-payments',
      targetAudience: 'architects-integrators',
      format: 'tutorial',
      complexity: 'hard',
      readingTime: '5 мин',
      keywords: ['Цифровой рубль', 'Банк России', 'ПКСК', 'Смарт-контракты', 'Атомарные расчеты']
    },
    {
      id: 'art-02',
      title: 'Аудит безопасности смарт-контрактов по ГОСТ Р 57580: типичные уязвимости и превентивный анализ',
      description: 'Разбор критических векторов атак на корпоративные распределенные реестры: повторный вход (reentrancy), ошибки управления доступом и методы автоматизированного аудита исходного кода.',
      author: 'Екатерина Романова',
      authorInitials: 'ЕР',
      authorRole: 'Ведущий аудитор безопасности смарт-контрактов',
      date: '25 сентября 2026',
      topics: ['information-security', 'audit-and-verification', 'smart-contracts-development'],
      topic: 'information-security',
      targetAudience: 'security-auditors',
      format: 'review',
      complexity: 'hard',
      readingTime: '6 мин',
      keywords: ['Аудит ИБ', 'ГОСТ Р 57580', 'Уязвимости', 'Reentrancy', 'Формальная верификация']
    },
    {
      id: 'art-03',
      title: 'Правовая квалификация смарт-контрактов и комплаенс сделок в российском праве',
      description: 'Практика применения статьи 309 ГК РФ к автоматизированному исполнению обязательств: самоисполняемые сделки, цифровые права (ЦФА) и особенности арбитражного доказывания.',
      author: 'Илья Мельников',
      authorInitials: 'ИМ',
      authorRole: 'Советник по LegalTech и комплаенсу',
      date: '24 сентября 2026',
      topics: ['law-and-compliance', 'business-logic-deals'],
      topic: 'law-and-compliance',
      targetAudience: 'legal-compliance',
      format: 'analytics',
      complexity: 'medium',
      readingTime: '5 мин',
      keywords: ['Право', 'Комплаенс', 'ГК РФ', 'Цифровые права', 'ЦФА']
    },
    {
      id: 'art-04',
      title: 'Поставка доверенных внешних данных: проектирование децентрализованных оракулов',
      description: 'Пошаговое проектирование отказоустойчивой сети поставщиков котировок и внешних юридически значимых событий для корпоративных смарт-контрактов без единой точки отказа.',
      author: 'Виктор Нестеров',
      authorInitials: 'ВН',
      authorRole: 'Инженер распределенных систем',
      date: '22 сентября 2026',
      topics: ['oracles-and-data', 'integrations-and-api'],
      topic: 'oracles-and-data',
      targetAudience: 'data-oracles',
      format: 'case-study',
      complexity: 'medium',
      readingTime: '5 мин',
      keywords: ['Оракулы', 'Внешние данные', 'API', 'Консенсус', 'ЦФА']
    }
  ];

  // --------------------------------------------------------------------------
  // 9. DOM Ready Entry Point
  // --------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    initTheme();
    updateSavedCounter();
    parseURLParams();
    initControls();
    renderActiveChips();
    fetchFeed(true);
  });
})();
