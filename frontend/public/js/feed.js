/**
 * SmartContractum Feed Page - Native Modular JavaScript
 * 100% Offline-First, Zero Emojis, Clean Performance
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
      } catch (e) {
        // LocalStorage fallback / private browsing
      }

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
  // 2. Sample Platform Articles (Default High-Quality Seed Data)
  // --------------------------------------------------------------------------
  const DEFAULT_ARTICLES = [
    {
      id: 'art-01',
      title: 'Интеграция смарт-контрактов с платформой цифрового рубля Банка России',
      lead: 'Архитектурный анализ взаимодействия шлюзов ПКСК с реестром ЦБ РФ: моделирование транзакций, атомарность расчетов и протоколы валидации прав доступа.',
      author: 'Алексей Смирнов',
      authorInitials: 'АС',
      date: 'Сегодня, 14:30',
      category: 'development',
      categoryName: 'Разработка',
      readingTime: '7 мин',
      views: 1420,
      likes: 98,
      comments: 24,
      tags: ['ПКСК', 'Цифровой рубль', 'Solidity', 'Архитектура']
    },
    {
      id: 'art-02',
      title: 'Аудит безопасности смарт-контрактов по ГОСТ Р 57580: типичные уязвимости и превентивный анализ',
      lead: 'Разбор 12 критических векторов атак на децентрализованные реестры: реентранси, арифметические переполнения, подмена оракулов и защита криптографических подписей.',
      author: 'Екатерина Романова',
      authorInitials: 'ЕР',
      date: 'Вчера, 18:15',
      category: 'security',
      categoryName: 'Безопасность',
      readingTime: '11 мин',
      views: 2180,
      likes: 156,
      comments: 42,
      tags: ['Аудит ИБ', 'ГОСТ', 'Безопасность', 'Смарт-контракты']
    },
    {
      id: 'art-03',
      title: 'Проектирование финтех-интерфейсов для B2B-контрактов: паттерны доверия и визуализация транзакций',
      lead: 'Как снизить когнитивную нагрузку оператора при согласовании сложных многосторонних договоров: цветовые индикаторы статусов, дерево вызовов и эргономика форм.',
      author: 'Михаил Волков',
      authorInitials: 'МВ',
      date: '24 сентября',
      category: 'design',
      categoryName: 'Дизайн',
      readingTime: '5 мин',
      views: 940,
      likes: 67,
      comments: 11,
      tags: ['UI/UX', 'Финтех', 'Дизайн-система', 'Эргономика']
    },
    {
      id: 'art-04',
      title: 'Аналитика рынка смарт-контрактов в РФ: динамика внедрения в банковском секторе за 2025–2026 гг.',
      lead: 'Количественные показатели пилотных запусков распределенных реестров в факторинге, торговом финансировании и цифровых финансовых активах (ЦФА).',
      author: 'Дмитрий Кузнецов',
      authorInitials: 'ДК',
      date: '22 сентября',
      category: 'analytics',
      categoryName: 'Аналитика',
      readingTime: '9 мин',
      views: 1850,
      likes: 112,
      comments: 19,
      tags: ['Аналитика', 'ЦФА', 'Банки', 'Рынок']
    }
  ];

  // --------------------------------------------------------------------------
  // 3. Card Template Generator (Strict SVG, No Emojis)
  // --------------------------------------------------------------------------
  function createCardElement(item) {
    const card = document.createElement('article');
    card.className = 'feed-card';
    card.setAttribute('data-category', item.category || 'development');
    card.setAttribute('data-id', item.id);

    const tagsHtml = (item.tags || [])
      .map(function (tag) {
        return '<button type="button" class="tag-chip" data-tag="' + escapeHtml(tag) + '">#' + escapeHtml(tag) + '</button>';
      })
      .join('');

    card.innerHTML =
      '<div class="card-meta">' +
        '<div class="author-info">' +
          '<div class="author-avatar">' + escapeHtml(item.authorInitials || 'SC') + '</div>' +
          '<span class="author-name">' + escapeHtml(item.author || 'Автор платформы') + '</span>' +
          '<span class="meta-dot"></span>' +
          '<span class="publish-date">' + escapeHtml(item.date || 'Недавно') + '</span>' +
        '</div>' +
        '<span class="category-badge category-' + escapeHtml(item.category || 'development') + '">' +
          escapeHtml(item.categoryName || item.category || 'Разработка') +
        '</span>' +
      '</div>' +
      '<h2 class="card-title">' +
        '<a href="editor.html?id=' + encodeURIComponent(item.id) + '">' + escapeHtml(item.title) + '</a>' +
      '</h2>' +
      '<p class="card-lead">' + escapeHtml(item.lead || '') + '</p>' +
      '<div class="card-tags">' + tagsHtml + '</div>' +
      '<footer class="card-footer">' +
        '<div class="card-metrics">' +
          '<button type="button" class="metric-item metric-views" title="Просмотры" aria-label="Просмотры">' +
            '<svg class="metric-svg" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>' +
            '<span>' + (item.views || 0) + '</span>' +
          '</button>' +
          '<button type="button" class="metric-item metric-like" title="Оценить публикацию" aria-label="Лайк">' +
            '<svg class="metric-svg" viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>' +
            '<span class="like-count">' + (item.likes || 0) + '</span>' +
          '</button>' +
          '<button type="button" class="metric-item metric-comments" title="Комментарии" aria-label="Комментарии">' +
            '<svg class="metric-svg" viewBox="0 0 24 24"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>' +
            '<span>' + (item.comments || 0) + '</span>' +
          '</button>' +
        '</div>' +
        '<div class="reading-time">' +
          '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>' +
          '<span>' + escapeHtml(item.readingTime || '5 мин') + '</span>' +
        '</div>' +
      '</footer>';

    return card;
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
  // 4. Feed Filtering & Interactions
  // --------------------------------------------------------------------------
  let currentFilter = 'all';
  let currentTagFilter = null;

  function applyFilter() {
    const cards = document.querySelectorAll('#feedCardsContainer .feed-card');
    let visibleCount = 0;

    cards.forEach(function (card) {
      const cardCategory = card.getAttribute('data-category');
      const matchesCategory = currentFilter === 'all' || cardCategory === currentFilter;

      let matchesTag = true;
      if (currentTagFilter) {
        const chips = card.querySelectorAll('.tag-chip');
        matchesTag = Array.from(chips).some(function (chip) {
          return chip.getAttribute('data-tag') === currentTagFilter;
        });
      }

      if (matchesCategory && matchesTag) {
        card.style.display = 'flex';
        visibleCount++;
      } else {
        card.style.display = 'none';
      }
    });

    // Check empty state
    let emptyState = document.getElementById('feedEmptyState');
    const container = document.getElementById('feedCardsContainer');
    if (visibleCount === 0) {
      if (!emptyState && container) {
        emptyState = document.createElement('div');
        emptyState.id = 'feedEmptyState';
        emptyState.className = 'feed-empty-state';
        emptyState.innerHTML =
          '<svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
            '<circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>' +
          '</svg>' +
          '<h3 class="empty-state-title">Публикаций пока нет</h3>' +
          '<p class="empty-state-desc">По выбранной категории или тегу еще не опубликовано материалов. Станьте первым автором!</p>' +
          '<a href="editor.html" class="btn btn-primary">Написать статью</a>';
        container.appendChild(emptyState);
      }
    } else if (emptyState) {
      emptyState.remove();
    }
  }

  function initFilterButtons() {
    const filterButtons = document.querySelectorAll('.feed-filter-btn');
    filterButtons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        filterButtons.forEach(function (b) {
          b.classList.remove('active');
          b.setAttribute('aria-selected', 'false');
        });
        btn.classList.add('active');
        btn.setAttribute('aria-selected', 'true');
        currentFilter = btn.getAttribute('data-category') || 'all';
        currentTagFilter = null; // reset tag filter on explicit tab switch
        applyFilter();
      });
    });
  }

  function initCardInteractions() {
    const container = document.getElementById('feedCardsContainer');
    if (!container) return;

    container.addEventListener('click', function (e) {
      // 1. Tag chip click
      const tagChip = e.target.closest('.tag-chip');
      if (tagChip) {
        e.preventDefault();
        const tag = tagChip.getAttribute('data-tag');
        currentTagFilter = currentTagFilter === tag ? null : tag;
        applyFilter();
        return;
      }

      // 2. Like button click
      const likeBtn = e.target.closest('.metric-like');
      if (likeBtn) {
        e.preventDefault();
        const countSpan = likeBtn.querySelector('.like-count');
        let count = parseInt(countSpan.textContent, 10) || 0;
        if (likeBtn.classList.contains('active')) {
          likeBtn.classList.remove('active');
          countSpan.textContent = Math.max(0, count - 1);
        } else {
          likeBtn.classList.add('active');
          countSpan.textContent = count + 1;
        }
      }
    });

    // Sidebar tag cloud clicks
    const tagCloud = document.querySelector('.widget-tags-cloud');
    if (tagCloud) {
      tagCloud.addEventListener('click', function (e) {
        const tagItem = e.target.closest('.widget-tag-item');
        if (tagItem) {
          e.preventDefault();
          const tag = tagItem.getAttribute('data-tag');
          currentTagFilter = currentTagFilter === tag ? null : tag;
          applyFilter();
        }
      });
    }
  }

  // --------------------------------------------------------------------------
  // 5. Load Feed Data (Local Storage / Seed + Live Moderation API)
  // --------------------------------------------------------------------------
  function loadFeed() {
    const container = document.getElementById('feedCardsContainer');
    if (!container) return;

    // Render default articles first
    container.innerHTML = '';
    DEFAULT_ARTICLES.forEach(function (item) {
      const card = createCardElement(item);
      container.appendChild(card);
    });

    // Attempt to fetch submissions from moderation API
    fetch('/api/moderation/list')
      .then(function (res) {
        if (!res.ok) throw new Error('API unavailable');
        return res.json();
      })
      .then(function (data) {
        if (data && data.success && Array.isArray(data.submissions)) {
          // Prepend user submissions
          data.submissions.forEach(function (sub) {
            const settings = sub.publicationSettings || {};
            const item = {
              id: sub.draftId || 'sub-' + sub.id,
              title: sub.title || 'Новая публикация',
              lead: settings.lead || 'Материал, отправленный через Antigravity Editor.',
              author: sub.authorId ? 'Пользователь #' + sub.authorId.slice(0, 6) : 'Автор Antigravity',
              authorInitials: 'SC',
              date: sub.createdAt ? new Date(sub.createdAt).toLocaleDateString('ru-RU') : 'Недавно',
              category: settings.category || 'development',
              categoryName: settings.categoryName || 'Разработка',
              readingTime: '4 мин',
              views: 1,
              likes: 0,
              comments: 0,
              tags: settings.tags && Array.isArray(settings.tags) ? settings.tags : ['Новое', 'Статья']
            };
            const card = createCardElement(item);
            container.insertBefore(card, container.firstChild);
          });
          applyFilter();
        }
      })
      .catch(function () {
        // Offline / dev fallback: default articles remain displayed seamlessly
      });
  }

  // --------------------------------------------------------------------------
  // 6. DOM Ready Entry Point
  // --------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    initTheme();
    loadFeed();
    initFilterButtons();
    initCardInteractions();
  });
})();
