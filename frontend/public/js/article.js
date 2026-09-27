/**
 * SmartContractum Article Reading Page - Native Modular JavaScript
 * 100% Offline-First, Zero Emojis, Syntax Highlighting, KaTeX / Math, Spoilers & TOC.
 */

(function () {
  'use strict';

  // --------------------------------------------------------------------------
  // 1. Theme Management & Syntax Highlighting Theme Sync
  // --------------------------------------------------------------------------
  function initTheme() {
    const toggleBtn = document.getElementById('btnThemeToggle');
    const hljsThemeLink = document.getElementById('hljs-theme');

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

      if (hljsThemeLink) {
        hljsThemeLink.href =
          theme === 'light'
            ? 'vendor/highlight/github.min.css'
            : 'vendor/highlight/github-dark.min.css';
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

  function isBookmarked(id) {
    if (!id) return false;
    return getBookmarks().indexOf(id) !== -1;
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
    try {
      localStorage.setItem('sc_bookmarks', JSON.stringify(bookmarks));
    } catch (e) {}
    return bookmarked;
  }

  function syncBookmarkButtons(id) {
    const bookmarked = isBookmarked(id);
    const btns = [
      document.getElementById('btnArticleBookmark'),
      document.getElementById('btnArticleBookmarkBottom')
    ];

    btns.forEach(function (btn) {
      if (!btn) return;
      btn.classList.toggle('is-bookmarked', bookmarked);
      const label = btn.querySelector('.bookmark-text') || btn.querySelector('span');
      if (label) {
        label.textContent = bookmarked ? 'В закладках' : 'В закладки';
      }
      btn.title = bookmarked ? 'Удалить из закладок' : 'Сохранить в закладки';
    });
  }

  function showToast(message) {
    let toast = document.getElementById('articleToast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'articleToast';
      toast.className = 'article-toast';
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
  // 3. Navigation & Actions Binding
  // --------------------------------------------------------------------------
  function initActions(articleId) {
    // Back to feed
    function handleBack() {
      const savedFeedUrl = sessionStorage.getItem('sc_feed_url');
      if (savedFeedUrl && savedFeedUrl.indexOf('feed.html') !== -1) {
        window.location.href = savedFeedUrl;
      } else if (document.referrer && document.referrer.indexOf('feed.html') !== -1) {
        window.history.back();
      } else {
        window.location.href = 'feed.html';
      }
    }

    const backBtnTop = document.getElementById('btnBackToFeed');
    if (backBtnTop) {
      backBtnTop.addEventListener('click', handleBack);
    }

    const backBtnBottom = document.getElementById('btnBackToFeedBottom');
    if (backBtnBottom) {
      backBtnBottom.addEventListener('click', handleBack);
    }

    // Bookmark buttons
    const bookmarkBtnTop = document.getElementById('btnArticleBookmark');
    if (bookmarkBtnTop) {
      bookmarkBtnTop.addEventListener('click', function () {
        toggleBookmark(articleId);
        syncBookmarkButtons(articleId);
      });
    }

    const bookmarkBtnBottom = document.getElementById('btnArticleBookmarkBottom');
    if (bookmarkBtnBottom) {
      bookmarkBtnBottom.addEventListener('click', function () {
        toggleBookmark(articleId);
        syncBookmarkButtons(articleId);
      });
    }

    // Share / Copy Link
    const shareBtn = document.getElementById('btnCopyLink');
    if (shareBtn) {
      shareBtn.addEventListener('click', function () {
        const url = window.location.href;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url)
            .then(function () {
              showToast('Ссылка на статью скопирована в буфер обмена');
            })
            .catch(function () {
              fallbackCopy(url);
            });
        } else {
          fallbackCopy(url);
        }
      });
    }

    function fallbackCopy(text) {
      const input = document.createElement('input');
      input.value = text;
      document.body.appendChild(input);
      input.select();
      try {
        document.execCommand('copy');
        showToast('Ссылка на статью скопирована в буфер обмена');
      } catch (e) {
        showToast('Не удалось скопировать ссылку');
      }
      document.body.removeChild(input);
    }
  }

  // --------------------------------------------------------------------------
  // 4. Interactive Table of Contents (TOC) Builder
  // --------------------------------------------------------------------------
  function buildTableOfContents(contentContainer) {
    const tocBox = document.getElementById('articleTocBox');
    const tocList = document.getElementById('articleTocList');
    if (!tocBox || !tocList || !contentContainer) return;

    const headings = contentContainer.querySelectorAll('h2, h3, h4');
    if (headings.length < 2) {
      tocBox.style.display = 'none';
      return;
    }

    tocList.innerHTML = '';
    headings.forEach(function (h, idx) {
      if (!h.id) {
        h.id = 'heading-' + (idx + 1);
      }

      const li = document.createElement('li');
      const level = h.tagName.toLowerCase();
      li.className = 'toc-item toc-level-' + level.charAt(1);

      const a = document.createElement('a');
      a.className = 'toc-link';
      a.href = '#' + h.id;
      a.textContent = h.textContent.trim();

      a.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.getElementById(h.id);
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
          try {
            history.pushState(null, '', '#' + h.id);
          } catch (err) {}
        }
      });

      li.appendChild(a);
      tocList.appendChild(li);
    });

    tocBox.style.display = 'block';
  }

  // --------------------------------------------------------------------------
  // 5. Rich Content Enhancements (Tables, Highlight.js, Spoilers)
  // --------------------------------------------------------------------------
  function enhanceArticleContent(contentContainer) {
    if (!contentContainer) return;

    // 1. Wrap unwrapped tables in responsive wrapper
    const tables = contentContainer.querySelectorAll('table');
    tables.forEach(function (table) {
      if (!table.parentElement.classList.contains('table-responsive-wrapper')) {
        const wrapper = document.createElement('div');
        wrapper.className = 'table-responsive-wrapper';
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
      }
    });

    // 2. Syntax highlighting for code blocks
    if (window.hljs) {
      const codeBlocks = contentContainer.querySelectorAll('pre.ql-syntax, pre code, pre');
      codeBlocks.forEach(function (block) {
        try {
          window.hljs.highlightElement(block);
        } catch (e) {}
      });
    }

    // 3. Interactive inline spoilers (click to reveal / hide)
    const inlineSpoilers = contentContainer.querySelectorAll('.editor-inline-spoiler');
    inlineSpoilers.forEach(function (spoiler) {
      spoiler.setAttribute('tabindex', '0');
      spoiler.setAttribute('role', 'button');
      spoiler.addEventListener('click', function (e) {
        e.stopPropagation();
        spoiler.classList.toggle('is-revealed');
      });
      spoiler.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          spoiler.classList.toggle('is-revealed');
        }
      });
    });
  }

  // --------------------------------------------------------------------------
  // 6. Article Data Loading & View Population
  // --------------------------------------------------------------------------
  function loadArticle() {
    const params = new URLSearchParams(window.location.search);
    const articleId = params.get('id');

    if (!articleId) {
      showErrorState(
        'Идентификатор статьи не указан',
        'В адресе страницы отсутствует параметр id публикации. Выберите статью из ленты.'
      );
      return;
    }

    initActions(articleId);

    // Fetch from REST API
    fetch('/api/articles/' + encodeURIComponent(articleId))
      .then(function (res) {
        if (res.status === 404) {
          throw new Error('NOT_FOUND');
        }
        if (!res.ok) {
          throw new Error('SERVER_ERROR');
        }
        return res.json();
      })
      .then(function (data) {
        if (data && data.success && data.article) {
          populateArticle(data.article);
        } else {
          showErrorState(
            'Статья не найдена или еще не опубликована',
            (data && data.error) || 'Материал недоступен в публичном доступе.'
          );
        }
      })
      .catch(function (err) {
        if (err.message === 'NOT_FOUND') {
          showErrorState(
            'Статья не найдена или еще не опубликована',
            'Материал с указанным идентификатором не найден в утвержденном реестре публикаций платформы SmartContractum.'
          );
        } else {
          // Offline / local static fallback check
          const fallback = FALLBACK_ARTICLES.find(function (a) {
            return a.id === articleId || a.draftId === articleId;
          });
          if (fallback) {
            populateArticle(fallback);
          } else {
            showErrorState(
              'Не удалось загрузить публикацию',
              'Проверьте подключение к серверу платформы SmartContractum.'
            );
          }
        }
      });
  }

  function populateArticle(article) {
    const loadingState = document.getElementById('articleLoadingState');
    const contentWrap = document.getElementById('articleContentWrap');
    const errorState = document.getElementById('articleErrorState');

    if (loadingState) loadingState.style.display = 'none';
    if (errorState) errorState.style.display = 'none';
    if (contentWrap) contentWrap.style.display = 'block';

    // Page title
    document.title = (article.title || 'Публикация') + ' — SmartContractum';

    // Title & Lead
    const titleEl = document.getElementById('articleTitle');
    if (titleEl) titleEl.textContent = article.title || 'Без заголовка';

    const leadEl = document.getElementById('articleLead');
    if (leadEl) {
      if (article.description) {
        leadEl.textContent = article.description;
        leadEl.style.display = 'block';
      } else {
        leadEl.style.display = 'none';
      }
    }

    // Author & Meta
    const avatarEl = document.getElementById('articleAuthorAvatar');
    if (avatarEl) avatarEl.textContent = article.authorInitials || 'SC';

    const authorNameEl = document.getElementById('articleAuthorName');
    if (authorNameEl) authorNameEl.textContent = article.author || 'Автор платформы';

    const authorRoleEl = document.getElementById('articleAuthorRole');
    if (authorRoleEl) {
      if (article.authorRole) {
        authorRoleEl.textContent = article.authorRole;
        authorRoleEl.style.display = 'block';
      } else {
        authorRoleEl.style.display = 'none';
      }
    }

    const dateEl = document.getElementById('articlePublishDate');
    if (dateEl) dateEl.textContent = article.date || 'Недавно';

    const readingTimeEl = document.getElementById('articleReadingTime');
    if (readingTimeEl) readingTimeEl.textContent = (article.readingTime || '5 мин') + ' чтения';

    // Badges: Topic, Format, Complexity
    const badgesWrap = document.getElementById('articleBadges');
    if (badgesWrap) {
      badgesWrap.innerHTML = '';

      if (window.PublicationConfig && article.topics && article.topics.length > 0) {
        article.topics.forEach(function (topicId) {
          const t = window.PublicationConfig.getTopicById(topicId);
          if (t) {
            const topicBadge = document.createElement('a');
            topicBadge.href = 'feed.html?topic=' + encodeURIComponent(t.id);
            topicBadge.className = 'meta-badge topic-badge';
            topicBadge.textContent = t.title;
            badgesWrap.appendChild(topicBadge);
          }
        });
      }

      if (window.PublicationConfig && article.format) {
        const f = window.PublicationConfig.getFormatById(article.format);
        if (f) {
          const formatBadge = document.createElement('span');
          formatBadge.className = 'meta-badge format-badge';
          formatBadge.textContent = f.title;
          badgesWrap.appendChild(formatBadge);
        }
      }

      if (window.PublicationConfig && article.complexity && article.complexity !== 'none') {
        const c = window.PublicationConfig.getComplexityById(article.complexity);
        if (c) {
          const complexityBadge = document.createElement('span');
          complexityBadge.className = 'meta-badge complexity-badge complexity-' + article.complexity;
          complexityBadge.textContent = c.title;
          badgesWrap.appendChild(complexityBadge);
        }
      }
    }

    // Cover Image
    const coverContainer = document.getElementById('articleCoverContainer');
    const coverImg = document.getElementById('articleCoverImg');
    if (coverContainer && coverImg) {
      if (article.coverImage) {
        coverImg.src = article.coverImage;
        coverImg.alt = article.title || 'Обложка статьи';
        coverContainer.style.display = 'block';
      } else {
        coverContainer.style.display = 'none';
      }
    }

    // Content Body
    const bodyEl = document.getElementById('articleBodyContent');
    if (bodyEl) {
      bodyEl.innerHTML = article.html || '<p>Текст статьи пуст.</p>';
      enhanceArticleContent(bodyEl);
      buildTableOfContents(bodyEl);
    }

    // Keywords / Tags
    const tagsWrap = document.getElementById('articleTagsWrap');
    const tagsList = document.getElementById('articleTagsList');
    if (tagsWrap && tagsList) {
      const keywords = Array.isArray(article.keywords) ? article.keywords : [];
      if (keywords.length > 0) {
        tagsList.innerHTML = '';
        keywords.forEach(function (kw) {
          const tagLink = document.createElement('a');
          tagLink.href = 'feed.html?search=' + encodeURIComponent(kw);
          tagLink.className = 'article-tag-item';
          tagLink.textContent = '#' + kw;
          tagsList.appendChild(tagLink);
        });
        tagsWrap.style.display = 'flex';
      } else {
        tagsWrap.style.display = 'none';
      }
    }

    // Sync Bookmark State
    syncBookmarkButtons(article.id);
  }

  function showErrorState(title, desc) {
    const loadingState = document.getElementById('articleLoadingState');
    const contentWrap = document.getElementById('articleContentWrap');
    const errorState = document.getElementById('articleErrorState');
    const errorTitle = document.getElementById('articleErrorTitle');
    const errorDesc = document.getElementById('articleErrorDesc');

    if (loadingState) loadingState.style.display = 'none';
    if (contentWrap) contentWrap.style.display = 'none';
    if (errorState) errorState.style.display = 'flex';

    if (errorTitle) errorTitle.textContent = title;
    if (errorDesc) errorDesc.textContent = desc;
  }

  // --------------------------------------------------------------------------
  // 7. Offline Fallback Seed Articles
  // --------------------------------------------------------------------------
  const FALLBACK_ARTICLES = [
    {
      id: 'art-01',
      title: 'Интеграция смарт-контрактов с платформой цифрового рубля Банка России',
      description: 'Архитектурный анализ взаимодействия шлюзов ПКСК с платформой цифрового рубля: моделирование атомарных транзакций, двухфазный коммит и валидация криптографических подписей по ГОСТ Р 34.12-2015.',
      author: 'Алексей Смирнов',
      authorInitials: 'АС',
      authorRole: 'Архитектор решений (демо)',
      date: '26 сентября 2026',
      topics: ['digital-ruble-payments', 'pksc-architecture', 'smart-contracts-development'],
      format: 'tutorial',
      complexity: 'hard',
      readingTime: '5 мин',
      keywords: ['Цифровой рубль', 'Банк России', 'ПКСК', 'Смарт-контракты', 'Атомарные расчеты'],
      html: '<h2>Архитектурный обзор</h2><p>Интеграция корпоративных сетей со шлюзом цифрового рубля.</p>'
    },
    {
      id: 'art-02',
      title: 'Аудит безопасности смарт-контрактов по ГОСТ Р 57580: типичные уязвимости и превентивный анализ',
      description: 'Разбор критических векторов атак на корпоративные распределенные реестры: повторный вход (reentrancy), ошибки управления доступом и методы автоматизированного аудита исходного кода.',
      author: 'Екатерина Романова',
      authorInitials: 'ЕР',
      authorRole: 'Ведущий аудитор безопасности (демо)',
      date: '25 сентября 2026',
      topics: ['information-security', 'audit-and-verification', 'smart-contracts-development'],
      format: 'review',
      complexity: 'hard',
      readingTime: '6 мин',
      keywords: ['Аудит ИБ', 'ГОСТ Р 57580', 'Уязвимости', 'Reentrancy', 'Формальная верификация'],
      html: '<h2>Векторы атак</h2><p>Анализ безопасности смарт-контрактов по ГОСТ.</p>'
    }
  ];

  // --------------------------------------------------------------------------
  // 8. DOM Ready Entry Point
  // --------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    initTheme();
    loadArticle();
  });
})();
