/**
 * SmartContractum Article Reading Page - Native Modular JavaScript
 * 100% Offline-First, Zero Emojis, Syntax Highlighting, KaTeX / Math, Spoilers & TOC.
 */

(function () {
  'use strict';

  let currentUser = null;
  let currentArticle = null;

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
  // 3. Auth & Profile Management
  // --------------------------------------------------------------------------
  function checkAuthStatus(callback) {
    fetch('/api/auth/status')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.authenticated && data.user) {
          currentUser = data.user;
        } else {
          currentUser = null;
        }
        updateAuthUI();
        if (callback) callback();
      })
      .catch(function () {
        currentUser = null;
        updateAuthUI();
        if (callback) callback();
      });
  }

  function updateAuthUI() {
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

    const commentForm = document.getElementById('commentForm');
    const guestPrompt = document.getElementById('commentGuestPrompt');
    if (commentForm && guestPrompt) {
      if (currentUser) {
        commentForm.style.display = 'block';
        guestPrompt.style.display = 'none';
      } else {
        commentForm.style.display = 'none';
        guestPrompt.style.display = 'flex';
      }
    }
  }

  function openAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) modal.style.display = 'flex';
  }

  function closeAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) modal.style.display = 'none';
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
                currentUser = null;
                updateAuthUI();
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

    const modal = document.getElementById('authModal');
    if (modal) {
      modal.addEventListener('click', function (e) {
        if (e.target === modal) closeAuthModal();
      });
    }

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        if (modal && modal.style.display !== 'none') closeAuthModal();
      }
    });

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
              currentUser = data.user;
              updateAuthUI();
              closeAuthModal();
              showToast('Вход выполнен: ' + data.user.name);
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
              currentUser = data.user;
              updateAuthUI();
              closeAuthModal();
              showToast('Вход выполнен: ' + data.user.name);
            }
          });
      });
    }

    const guestLoginBtn = document.getElementById('btnCommentLogin');
    if (guestLoginBtn) {
      guestLoginBtn.addEventListener('click', openAuthModal);
    }
  }

  // --------------------------------------------------------------------------
  // 4. Likes & Comments Interaction
  // --------------------------------------------------------------------------
  function syncLikeButtons(likesCount, hasLiked) {
    const btns = [
      document.getElementById('btnArticleLike'),
      document.getElementById('btnArticleLikeBottom')
    ];
    const countEls = [
      document.getElementById('articleLikeCount'),
      document.getElementById('articleLikeCountBottom')
    ];

    btns.forEach(function (btn) {
      if (!btn) return;
      btn.classList.toggle('is-liked', Boolean(hasLiked));
      btn.setAttribute('aria-pressed', hasLiked ? 'true' : 'false');
      btn.title = hasLiked ? 'Больше не нравится' : 'Нравится';
    });

    countEls.forEach(function (el) {
      if (!el) return;
      el.textContent = typeof likesCount === 'number' ? likesCount : 0;
    });
  }

  function toggleArticleLike(articleId) {
    if (!currentUser) {
      openAuthModal();
      showToast('Войдите, чтобы поставить лайк');
      return;
    }

    const topBtn = document.getElementById('btnArticleLike');
    const wasLiked = topBtn ? topBtn.classList.contains('is-liked') : false;
    const countEl = document.getElementById('articleLikeCount');
    const prevCount = parseInt(countEl ? countEl.textContent : '0', 10) || 0;

    const newLiked = !wasLiked;
    const newCount = newLiked ? (prevCount + 1) : Math.max(0, prevCount - 1);

    // Optimistic UI update
    syncLikeButtons(newCount, newLiked);

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
          syncLikeButtons(data.likesCount, data.hasLiked);
          if (currentArticle) {
            currentArticle.hasLiked = data.hasLiked;
            currentArticle.likesCount = data.likesCount;
          }
        } else {
          // Rollback
          syncLikeButtons(prevCount, wasLiked);
          showToast(data.error || 'Ошибка при обновлении отметки');
        }
      })
      .catch(function (err) {
        if (err.message !== 'AUTH_REQUIRED') {
          syncLikeButtons(prevCount, wasLiked);
          showToast('Не удалось обновить отметку');
        }
      });
  }

  function formatCommentDate(isoStr) {
    if (!isoStr) return 'Недавно';
    try {
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return 'Недавно';
      const day = String(d.getDate()).padStart(2, '0');
      const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
      const month = months[d.getMonth()] || '';
      const year = d.getFullYear();
      const hours = String(d.getHours()).padStart(2, '0');
      const minutes = String(d.getMinutes()).padStart(2, '0');
      return day + ' ' + month + ' ' + year + ' в ' + hours + ':' + minutes;
    } catch (e) {
      return 'Недавно';
    }
  }

  function renderCommentItem(comment) {
    const el = document.createElement('div');
    const isSol = Boolean(comment.isSolution || comment.is_solution);
    el.className = 'comment-item' + (isSol ? ' is-solution-comment' : '');
    el.setAttribute('data-id', comment.id);

    const authorName = comment.authorName || 'Пользователь';
    let initials = 'SC';
    if (authorName) {
      const parts = authorName.trim().split(/\s+/);
      initials = parts.length > 1
        ? (parts[0][0] + parts[1][0]).toUpperCase()
        : authorName.substring(0, 2).toUpperCase();
    }

    const dateText = formatCommentDate(comment.createdAt || comment.created_at);

    let solutionBadgeHtml = '';
    if (isSol) {
      solutionBadgeHtml =
        '<div class="solution-badge">' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
            '<polyline points="20 6 9 17 4 12"></polyline>' +
          '</svg>' +
          '<span>Решение принято автором</span>' +
        '</div>';
    }

    let solutionActionBtn = '';
    const isQuestion = currentArticle && (currentArticle.materialType === 'question' || (currentArticle.publication_settings && currentArticle.publication_settings.materialType === 'question'));
    const isAuthor = currentUser && currentArticle && (currentUser.id === currentArticle.authorId || currentUser.id === currentArticle.author_id);
    if (isQuestion && isAuthor) {
      solutionActionBtn =
        '<button type="button" class="btn btn-sm btn-toggle-solution" data-comment-id="' + escapeHtml(comment.id) + '">' +
          (isSol ? 'Снять отметку решения' : 'Отметить как решение') +
        '</button>';
    }

    const isAnswer = comment.commentType === 'answer' || comment.comment_type === 'answer';
    const commentTypeBadge = isAnswer ? '<span class="comment-type-badge answer-badge">Ответ</span>' : '';

    el.innerHTML =
      '<div class="comment-item-header" style="display: flex; align-items: center; justify-content: space-between;">' +
        '<div style="display: flex; align-items: center; gap: 8px;">' +
          '<div class="comment-author-avatar">' + escapeHtml(initials) + '</div>' +
          '<span class="comment-author-name">' + escapeHtml(authorName) + '</span>' +
          commentTypeBadge +
          '<span class="comment-date">' + escapeHtml(dateText) + '</span>' +
        '</div>' +
        solutionActionBtn +
      '</div>' +
      solutionBadgeHtml +
      '<div class="comment-text">' + (comment.content ? escapeHtml(comment.content).replace(/\n/g, '<br>') : '') + '</div>';

    const toggleBtn = el.querySelector('.btn-toggle-solution');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', function (e) {
        e.preventDefault();
        const cid = toggleBtn.getAttribute('data-comment-id');
        toggleSolution(cid);
      });
    }

    return el;
  }

  function toggleSolution(commentId) {
    if (!currentArticle) return;
    const articleId = currentArticle.id;
    fetch('/api/articles/' + encodeURIComponent(articleId) + '/comments/' + encodeURIComponent(commentId) + '/solution', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    })
      .then(function (res) {
        if (res.status === 403) {
          showToast('Только автор вопроса может отмечать решение');
          throw new Error('FORBIDDEN');
        }
        return res.json();
      })
      .then(function (data) {
        if (data && data.success) {
          showToast(data.isSolution ? 'Ответ отмечен как решение' : 'Отметка решения снята');
          loadComments(articleId);
        } else {
          showToast((data && data.error) || 'Ошибка изменения статуса решения');
        }
      })
      .catch(function (err) {
        console.error('Failed to toggle solution:', err);
      });
  }

  function renderCommentsList(comments) {
    const listEl = document.getElementById('commentsList');
    const badgeEl = document.getElementById('commentsCountBadge');
    const emptyEl = document.getElementById('commentsEmpty');

    if (badgeEl) {
      badgeEl.textContent = comments.length;
    }

    if (!listEl) return;
    listEl.innerHTML = '';

    if (comments.length === 0) {
      if (emptyEl) emptyEl.style.display = 'block';
      return;
    }

    if (emptyEl) emptyEl.style.display = 'none';

    // Put solution comment first if present
    const sortedComments = comments.slice().sort(function (a, b) {
      const aSol = Boolean(a.isSolution || a.is_solution);
      const bSol = Boolean(b.isSolution || b.is_solution);
      if (aSol && !bSol) return -1;
      if (!aSol && bSol) return 1;
      return 0;
    });

    sortedComments.forEach(function (c) {
      listEl.appendChild(renderCommentItem(c));
    });
  }

  function loadComments(articleId) {
    fetch('/api/articles/' + encodeURIComponent(articleId) + '/comments')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.success) {
          renderCommentsList(data.comments || []);
        }
      })
      .catch(function (err) {
        console.error('Failed to load comments:', err);
      });
  }

  let isCommentsInitialized = false;

  function initComments(articleId) {
    const textarea = document.getElementById('commentTextInput');
    const charCountEl = document.getElementById('commentCharCount');
    const form = document.getElementById('commentForm');
    const submitBtn = document.getElementById('btnSubmitComment');

    if (textarea && charCountEl && !isCommentsInitialized) {
      textarea.addEventListener('input', function () {
        charCountEl.textContent = textarea.value.length;
      });
    }

    if (form && !isCommentsInitialized) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();

        if (!currentUser) {
          openAuthModal();
          showToast('Войдите, чтобы оставить комментарий');
          return;
        }

        const content = textarea ? textarea.value.trim() : '';
        if (!content) {
          showToast('Комментарий не может быть пустым');
          if (textarea) textarea.focus();
          return;
        }

        if (content.length > 5000) {
          showToast('Превышен лимит длины (максимум 5000 символов)');
          return;
        }

        if (submitBtn) submitBtn.disabled = true;

        fetch('/api/articles/' + encodeURIComponent(articleId) + '/comments', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: content })
        })
          .then(function (res) {
            if (res.status === 401) {
              openAuthModal();
              throw new Error('AUTH_REQUIRED');
            }
            return res.json();
          })
          .then(function (data) {
            if (submitBtn) submitBtn.disabled = false;
            if (data && data.success && data.comment) {
              if (textarea) textarea.value = '';
              if (charCountEl) charCountEl.textContent = '0';

              const listEl = document.getElementById('commentsList');
              const emptyEl = document.getElementById('commentsEmpty');
              const badgeEl = document.getElementById('commentsCountBadge');

              if (emptyEl) emptyEl.style.display = 'none';

              if (listEl) {
                const newCommentEl = renderCommentItem(data.comment);
                listEl.appendChild(newCommentEl);
              }

              if (badgeEl) {
                const currentBadge = parseInt(badgeEl.textContent || '0', 10) || 0;
                badgeEl.textContent = data.commentsCount !== undefined ? data.commentsCount : (currentBadge + 1);
              }

              showToast('Комментарий опубликован');
            } else {
              showToast((data && data.error) || 'Ошибка при отправке комментария');
            }
          })
          .catch(function (err) {
            if (submitBtn) submitBtn.disabled = false;
            if (err.message !== 'AUTH_REQUIRED') {
              showToast('Не удалось отправить комментарий');
            }
          });
      });
      isCommentsInitialized = true;
    }

    loadComments(articleId);
  }

  // --------------------------------------------------------------------------
  // 5. Navigation & Actions Binding
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

    // Like buttons
    const likeBtnTop = document.getElementById('btnArticleLike');
    const likeBtnBottom = document.getElementById('btnArticleLikeBottom');
    if (likeBtnTop) {
      likeBtnTop.addEventListener('click', function () {
        toggleArticleLike(articleId);
      });
    }
    if (likeBtnBottom) {
      likeBtnBottom.addEventListener('click', function () {
        toggleArticleLike(articleId);
      });
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
    currentArticle = article;
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

    // Author Subscription Button Wiring
    const subBtn = document.getElementById('btnSubscribeAuthor');
    if (subBtn && article.author) {
      const authorId = article.authorId || article.author;
      const authorTitle = article.author;
      subBtn.style.display = 'inline-flex';

      function updateSubBtn(isSub) {
        subBtn.classList.toggle('is-subscribed', isSub);
        const txt = subBtn.querySelector('.subscribe-text');
        if (txt) txt.textContent = isSub ? 'Вы подписаны' : 'Подписаться';
        subBtn.title = isSub ? 'Отписаться от автора' : 'Подписаться на автора';
      }

      fetch('/api/subscriptions')
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (data && data.success && data.subscriptions && Array.isArray(data.subscriptions.authors)) {
            const isSub = data.subscriptions.authors.some(function (a) {
              return a.id === authorId || a.title === authorTitle;
            });
            updateSubBtn(isSub);
          }
        })
        .catch(function () {});

      subBtn.addEventListener('click', function () {
        fetch('/api/subscriptions/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ targetType: 'author', targetId: authorId, targetTitle: authorTitle })
        })
        .then(function (res) {
          if (res.status === 401) {
            showToast('Для подписки на автора необходимо войти в систему');
            return null;
          }
          return res.json();
        })
        .then(function (data) {
          if (data && data.success) {
            updateSubBtn(data.subscribed);
            showToast(data.subscribed ? 'Вы подписались на автора ' + authorTitle : 'Вы отписались от автора ' + authorTitle);
          }
        })
        .catch(function () {});
      });
    }

    // Sync header auth label
    fetch('/api/auth/status')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.authenticated && data.user) {
          const lbl = document.getElementById('headerUserLabel');
          if (lbl) lbl.textContent = data.user.name;
        }
      })
      .catch(function () {});

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

    // Sync Like State
    syncLikeButtons(article.likesCount, Boolean(article.hasLiked || article.isLiked));

    // Customize Comments / Answers section for Questions
    const isQuestion = article.materialType === 'question' || (article.publication_settings && article.publication_settings.materialType === 'question');
    const commentsTitle = document.getElementById('commentsTitle') || document.querySelector('.comments-title');
    const commentInput = document.getElementById('commentTextInput');
    const commentsEmptyTitle = document.getElementById('commentsEmptyTitle');

    if (isQuestion) {
      if (commentsTitle) {
        const badge = commentsTitle.querySelector('#commentsCountBadge');
        commentsTitle.childNodes[0].textContent = 'Ответы ';
      }
      if (commentInput) {
        commentInput.placeholder = 'Напишите содержательный ответ или решение с кодом...';
      }
      if (commentsEmptyTitle) {
        commentsEmptyTitle.textContent = 'Пока нет ответов на этот вопрос';
      }
    }

    // Initialize code block copy buttons
    initCodeBlockCopyButtons();

    // Reveal Comments Section & Load Comments
    const commentsSec = document.getElementById('comments');
    if (commentsSec) {
      commentsSec.style.display = 'block';
    }
    initComments(article.id);

    // Scroll to #comments if specified in URL hash
    if (window.location.hash === '#comments') {
      setTimeout(function () {
        const c = document.getElementById('comments');
        if (c) c.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 150);
    }
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
  // 7b. Code Block Copy Buttons & Notifications
  // --------------------------------------------------------------------------
  function initCodeBlockCopyButtons() {
    const codeBlocks = document.querySelectorAll('pre code, pre');
    codeBlocks.forEach(function (codeEl) {
      const pre = codeEl.tagName === 'PRE' ? codeEl : codeEl.closest('pre');
      if (!pre || pre.querySelector('.btn-copy-code')) return;
      pre.style.position = 'relative';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn-copy-code';
      btn.title = 'Скопировать код';
      btn.textContent = 'Копировать';
      btn.addEventListener('click', function () {
        const text = pre.innerText || pre.textContent || '';
        navigator.clipboard.writeText(text).then(function () {
          btn.textContent = 'Скопировано!';
          setTimeout(function () { btn.textContent = 'Копировать'; }, 2000);
        }).catch(function () {
          btn.textContent = 'Ошибка';
        });
      });
      pre.appendChild(btn);
    });
  }

  function initHeaderNotifications() {
    const notifBtn = document.getElementById('headerNotificationsBtn');
    const notifBadge = document.getElementById('headerNotifBadge');
    const notifPopup = document.getElementById('headerNotifPopup');
    const notifList = document.getElementById('notifListContainer');
    const markAllBtn = document.getElementById('notifMarkAllReadBtn');
    const notifWrap = document.getElementById('headerNotifWrap');

    if (!notifBtn || !notifPopup) return;

    function loadNotifications() {
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

    notifBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      const isVisible = notifPopup.style.display !== 'none';
      if (isVisible) {
        notifPopup.style.display = 'none';
        notifBtn.setAttribute('aria-expanded', 'false');
      } else {
        notifPopup.style.display = 'block';
        notifBtn.setAttribute('aria-expanded', 'true');
        loadNotifications();
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

    loadNotifications();
  }

  // --------------------------------------------------------------------------
  // 8. DOM Ready Entry Point
  // --------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    initTheme();
    initAuthControls();
    initHeaderNotifications();
    checkAuthStatus(function () {
      loadArticle();
    });
  });
})();
