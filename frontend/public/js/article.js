/**
 * SmartContractum Article Reading Page - Native Modular JavaScript
 * 100% Offline-First, Zero Emojis, Syntax Highlighting, KaTeX / Math, Spoilers & TOC.
 */

(function () {
  'use strict';

  let currentUser = null;
  let currentArticle = null;
  let currentMyAnswerId = null;

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
  // Client-side HTML Sanitizer (defense-in-depth against stored XSS)
  // --------------------------------------------------------------------------
  function sanitizeArticleHtml(dirtyHtml) {
    if (!dirtyHtml || typeof dirtyHtml !== 'string') return '';
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(dirtyHtml, 'text/html');
      const body = doc.body;

      // Disallowed elements to remove completely with their content
      const dropTags = [
        'script', 'style', 'iframe', 'object', 'embed', 'applet',
        'meta', 'link', 'base', 'form', 'input', 'button',
        'textarea', 'noscript'
      ];
      dropTags.forEach(function (tag) {
        const elements = body.querySelectorAll(tag);
        elements.forEach(function (el) { el.remove(); });
      });

      // Allowed tags allowlist
      const allowedTags = new Set([
        'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'blockquote', 'ul', 'ol', 'li', 'pre', 'code',
        'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'img', 'a', 'strong', 'b', 'em', 'i', 'u', 's',
        'del', 'strike', 'sub', 'sup', 'span', 'div',
        'br', 'hr'
      ]);

      // Strip unallowed tags while unwrapping child nodes
      const allElements = Array.from(body.querySelectorAll('*'));
      allElements.forEach(function (el) {
        const tagName = el.tagName.toLowerCase();
        if (!allowedTags.has(tagName)) {
          while (el.firstChild) {
            el.parentNode.insertBefore(el.firstChild, el);
          }
          el.remove();
          return;
        }

        // Sanitize attributes
        const attrs = Array.from(el.attributes);
        attrs.forEach(function (attr) {
          const name = attr.name.toLowerCase();
          const val = attr.value;

          // Remove event handler attributes (onclick, onerror, onload, etc.)
          if (name.startsWith('on')) {
            el.removeAttribute(attr.name);
            return;
          }

          // Validate a.href
          if (tagName === 'a' && name === 'href') {
            const clean = val.replace(/[\s\x00-\x1f\x7f-\x9f]/g, '').toLowerCase();
            if (
              clean.startsWith('javascript:') ||
              clean.startsWith('vbscript:') ||
              clean.startsWith('data:') ||
              clean.startsWith('file:') ||
              clean.startsWith('blob:')
            ) {
              el.removeAttribute(attr.name);
            }
            return;
          }

          // Validate img.src
          if (tagName === 'img' && name === 'src') {
            const clean = val.replace(/[\s\x00-\x1f\x7f-\x9f]/g, '').toLowerCase();
            if (clean.startsWith('javascript:') || clean.startsWith('vbscript:')) {
              el.removeAttribute(attr.name);
            } else if (clean.startsWith('data:') && !clean.match(/^data:image\/(png|jpeg|jpg|webp|gif);base64,/i)) {
              el.removeAttribute(attr.name);
            }
            return;
          }

          // Validate a.target
          if (tagName === 'a' && name === 'target') {
            if (val !== '_blank' && val !== '_self') {
              el.removeAttribute(attr.name);
            }
            return;
          }

          // Whitelist allowed attributes
          const allowedAttrs = ['class', 'title', 'id'];
          if (tagName === 'a') allowedAttrs.push('href', 'target', 'rel');
          if (tagName === 'img') allowedAttrs.push('src', 'alt', 'width', 'height', 'loading');
          if (tagName === 'th' || tagName === 'td') allowedAttrs.push('colspan', 'rowspan', 'scope');
          if (tagName === 'pre' || tagName === 'code') allowedAttrs.push('data-language');

          if (!allowedAttrs.includes(name)) {
            el.removeAttribute(attr.name);
          }
        });
      });

      return body.innerHTML;
    } catch (e) {
      return '';
    }
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
          window.currentUser = data.user;
        } else {
          currentUser = null;
          window.currentUser = null;
        }
        updateAuthUI();
        if (currentArticle) syncArticleVoteCapsules(currentArticle);
        if (callback) callback();
      })
      .catch(function () {
        currentUser = null;
        window.currentUser = null;
        updateAuthUI();
        if (currentArticle) syncArticleVoteCapsules(currentArticle);
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

    const questionGuestPrompt = document.getElementById('questionGuestPrompt');
    const myAnswerFormWrap = document.getElementById('myAnswerFormWrap');
    const myAnswerBanner = document.getElementById('myAnswerBanner');
    if (questionGuestPrompt) {
      if (!currentUser) {
        questionGuestPrompt.style.display = 'flex';
        if (myAnswerFormWrap) myAnswerFormWrap.style.display = 'none';
        if (myAnswerBanner) myAnswerBanner.style.display = 'none';
      } else {
        questionGuestPrompt.style.display = 'none';
        if (currentMyAnswerId) {
          if (myAnswerFormWrap) myAnswerFormWrap.style.display = 'none';
          if (myAnswerBanner) myAnswerBanner.style.display = 'block';
        } else {
          if (myAnswerFormWrap) myAnswerFormWrap.style.display = 'block';
          if (myAnswerBanner) myAnswerBanner.style.display = 'none';
        }
      }
    }
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

  let currentAuthSessionToken = 0;

  function updateVoteDataStore(targetType, targetId, score, myVote, canVote) {
    if (!targetId) return;

    if (targetType === 'article' && currentArticle && (currentArticle.id === targetId || currentArticle.draftId === targetId)) {
      currentArticle.score = score;
      currentArticle.myVote = myVote;
      if (canVote !== undefined) {
        currentArticle.canVote = canVote;
      }
    }

    function updateCommentObj(item) {
      if (!item) return;
      if (item.id === targetId) {
        item.score = score;
        item.myVote = myVote;
        if (canVote !== undefined) {
          item.canVote = canVote;
        }
      }
    }

    if (window._allCommentsMap && window._allCommentsMap[targetId]) {
      updateCommentObj(window._allCommentsMap[targetId]);
    }

    if (window._commentsResponseData) {
      const resp = window._commentsResponseData;
      if (Array.isArray(resp.comments)) {
        resp.comments.forEach(updateCommentObj);
      }
      if (Array.isArray(resp.answers)) {
        resp.answers.forEach(function (ans) {
          updateCommentObj(ans);
          if (Array.isArray(ans.comments)) {
            ans.comments.forEach(updateCommentObj);
          }
        });
      }
      if (Array.isArray(resp.questionComments)) {
        resp.questionComments.forEach(updateCommentObj);
      }
    }

    if (Array.isArray(window._rawCommentsData)) {
      window._rawCommentsData.forEach(updateCommentObj);
    }
  }

  window.addEventListener('smartcontractum:voted', function (e) {
    const detail = e.detail;
    if (!detail) return;
    updateVoteDataStore(detail.targetType, detail.targetId, detail.score, detail.myVote, detail.canVote);
  });

  function syncArticleVoteCapsules(article) {
    if (!article) return;
    const authorId = article.authorId || article.author_id;
    const isAuthor = article.isAuthor !== undefined ? Boolean(article.isAuthor) : Boolean(currentUser && (currentUser.id === authorId));
    const isGuest = !currentUser || Boolean(currentUser.isGuest);
    const canVote = article.canVote !== undefined ? Boolean(article.canVote) : (!isAuthor && !isGuest);
    const score = article.score !== undefined ? article.score : 0;
    const myVote = article.myVote !== undefined ? article.myVote : 0;

    const capsuleHtml = (window.SmartContractumVotes && typeof window.SmartContractumVotes.renderVoteCapsuleHtml === 'function')
      ? window.SmartContractumVotes.renderVoteCapsuleHtml({
          targetType: 'article',
          targetId: article.id,
          score: score,
          myVote: myVote,
          canVote: canVote,
          isAuthor: isAuthor
        })
      : '';

    const topEl = document.getElementById('voteArticleTop');
    if (topEl) topEl.innerHTML = capsuleHtml;

    const bottomEl = document.getElementById('voteArticleBottom');
    if (bottomEl) bottomEl.innerHTML = capsuleHtml;
  }

  function refreshArticleAndCommentsOnAuthChange() {
    const sessionToken = ++currentAuthSessionToken;
    if (!currentArticle) return;
    const artId = currentArticle.id;

    // Immediately clear personalized vote state in currentArticle so old vote does not flash
    if (!currentUser) {
      currentArticle.myVote = 0;
      currentArticle.canVote = false;
      currentArticle.isAuthor = false;
      syncArticleVoteCapsules(currentArticle);
    } else {
      currentArticle.myVote = 0;
      currentArticle.isAuthor = Boolean(currentUser.id === (currentArticle.authorId || currentArticle.author_id));
      syncArticleVoteCapsules(currentArticle);
    }

    // Re-fetch personalized article state
    fetch('/api/articles/' + encodeURIComponent(artId))
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (sessionToken !== currentAuthSessionToken) return; // Stale session response discarded
        if (data && data.success && data.article) {
          const fresh = data.article;
          currentArticle.score = fresh.score !== undefined ? fresh.score : currentArticle.score;
          currentArticle.myVote = fresh.myVote !== undefined ? fresh.myVote : 0;
          currentArticle.canVote = fresh.canVote !== undefined ? fresh.canVote : false;
          currentArticle.isAuthor = fresh.isAuthor !== undefined ? fresh.isAuthor : Boolean(currentUser && (currentUser.id === currentArticle.authorId || currentUser.id === currentArticle.author_id));
          syncArticleVoteCapsules(currentArticle);
        }
      })
      .catch(function () {});

    // Re-fetch comments with personalized votes
    loadComments(artId);
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
                window.currentUser = null;
                currentMyAnswerId = null;
                updateAuthUI();
                showToast('Вы вышли из системы');
                refreshArticleAndCommentsOnAuthChange();
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
              window.currentUser = data.user;
              updateAuthUI();
              closeAuthModal();
              showToast('Вход выполнен: ' + data.user.name);
              refreshArticleAndCommentsOnAuthChange();
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
              window.currentUser = data.user;
              updateAuthUI();
              closeAuthModal();
              showToast('Вход выполнен: ' + data.user.name);
              refreshArticleAndCommentsOnAuthChange();
            }
          });
      });
    }

    const guestLoginBtn = document.getElementById('btnCommentLogin');
    if (guestLoginBtn) {
      guestLoginBtn.addEventListener('click', openAuthModal);
    }

    const questionLoginBtn = document.getElementById('btnQuestionLogin');
    if (questionLoginBtn) {
      questionLoginBtn.addEventListener('click', openAuthModal);
    }

    window.addEventListener('smartcontractum:auth-changed', function (e) {
      if (e.detail && e.detail.user !== undefined) {
        currentUser = e.detail.user;
        window.currentUser = e.detail.user;
      }
      updateAuthUI();
      refreshArticleAndCommentsOnAuthChange();
    });
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

  function getRussianPlural(n, one, few, many) {
    const mod10 = n % 10;
    const mod100 = n % 100;
    if (mod10 === 1 && mod100 !== 11) {
      return one;
    }
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) {
      return few;
    }
    return many;
  }

  function formatCommentTimeRelative(isoStr, nowMs) {
    if (!isoStr) return 'Недавно';
    try {
      const d = new Date(isoStr);
      const timeMs = d.getTime();
      if (isNaN(timeMs)) return 'Недавно';

      const now = (typeof nowMs === 'number' && !isNaN(nowMs)) ? nowMs : Date.now();
      const diffMs = now - timeMs;

      if (diffMs < 1000) {
        return '1 секунду назад';
      }

      const diffSec = Math.floor(diffMs / 1000);
      if (diffSec < 60) {
        if (diffSec <= 1) return '1 секунду назад';
        return diffSec + ' ' + getRussianPlural(diffSec, 'секунду', 'секунды', 'секунд') + ' назад';
      }

      const diffMin = Math.floor(diffSec / 60);
      if (diffMin < 60) {
        return diffMin + ' ' + getRussianPlural(diffMin, 'минуту', 'минуты', 'минут') + ' назад';
      }

      if (diffSec <= 86400) {
        const diffHours = Math.floor(diffSec / 3600);
        return diffHours + ' ' + getRussianPlural(diffHours, 'час', 'часа', 'часов') + ' назад';
      }

      return formatCommentDate(isoStr);
    } catch (e) {
      return 'Недавно';
    }
  }

  function updateCommentTimestamps() {
    const timeElements = document.querySelectorAll('time.comment-time[datetime]');
    const now = Date.now();
    let minNextDelaySec = 60;

    if (timeElements && timeElements.length > 0) {
      timeElements.forEach(function (el) {
        const iso = el.getAttribute('datetime');
        if (!iso) return;
        const timeMs = new Date(iso).getTime();
        const diffSec = (!isNaN(timeMs) && timeMs > 0) ? Math.max(0, Math.floor((now - timeMs) / 1000)) : 86401;

        const rel = formatCommentTimeRelative(iso, now);
        if (el.textContent !== rel) {
          el.textContent = rel;
        }

        if (diffSec < 60) {
          minNextDelaySec = Math.min(minNextDelaySec, 1);
        } else if (diffSec < 3600) {
          const remMin = 60 - (diffSec % 60);
          const delay = Math.max(1, Math.min(60, remMin));
          minNextDelaySec = Math.min(minNextDelaySec, delay);
        } else if (diffSec <= 86400) {
          const remHour = 3600 - (diffSec % 3600);
          const delay = Math.max(1, Math.min(60, remHour));
          minNextDelaySec = Math.min(minNextDelaySec, delay);
        }
      });
    }

    return Math.max(1, Math.min(60, minNextDelaySec)) * 1000;
  }

  function runCommentTimestampScheduler() {
    if (window._commentTimestampTimer) {
      clearTimeout(window._commentTimestampTimer);
      window._commentTimestampTimer = null;
    }
    const nextDelayMs = updateCommentTimestamps();
    window._commentTimestampTimer = setTimeout(runCommentTimestampScheduler, nextDelayMs);
  }

  // Cleanup previous scheduler and event listeners on re-init
  if (window._commentTimestampTimer) {
    clearTimeout(window._commentTimestampTimer);
    window._commentTimestampTimer = null;
  }
  if (window._commentTimestampVisibilityHandler) {
    document.removeEventListener('visibilitychange', window._commentTimestampVisibilityHandler);
    window._commentTimestampVisibilityHandler = null;
  }
  if (window._commentTimestampFocusHandler) {
    window.removeEventListener('focus', window._commentTimestampFocusHandler);
    window._commentTimestampFocusHandler = null;
  }

  window._commentTimestampVisibilityHandler = function () {
    if (!document.hidden) {
      runCommentTimestampScheduler();
    }
  };
  document.addEventListener('visibilitychange', window._commentTimestampVisibilityHandler);

  window._commentTimestampFocusHandler = function () {
    runCommentTimestampScheduler();
  };
  window.addEventListener('focus', window._commentTimestampFocusHandler);

  window.updateCommentTimestamps = updateCommentTimestamps;
  window.runCommentTimestampScheduler = runCommentTimestampScheduler;
  runCommentTimestampScheduler();

  function getAuthorInitials(name) {
    if (!name) return 'SC';
    const parts = name.trim().split(/\s+/);
    return parts.length > 1
      ? (parts[0][0] + parts[1][0]).toUpperCase()
      : name.substring(0, 2).toUpperCase();
  }

  // Global set of expanded comment IDs to preserve expansion state across re-renders
  window._expandedCommentIds = window._expandedCommentIds || new Set();
  window._commentDrilldownState = window._commentDrilldownState || { stack: [] };
  window._commentDrafts = window._commentDrafts || {};

  function generateClientOpId() {
    return 'op_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
  }

  function getOrCreateClientOpId(formEl) {
    if (!formEl) return generateClientOpId();
    if (!formEl.dataset.clientOpId) {
      formEl.dataset.clientOpId = generateClientOpId();
    }
    return formEl.dataset.clientOpId;
  }

  function resetClientOpId(formEl) {
    if (!formEl) return;
    delete formEl.dataset.clientOpId;
    delete formEl.dataset.lastSubmittedText;
  }

  function handleFormTextInput(formEl, currentText) {
    if (!formEl) return;
    if (!formEl.dataset.clientOpId) {
      formEl.dataset.clientOpId = generateClientOpId();
    } else if (formEl.dataset.lastSubmittedText !== undefined && formEl.dataset.lastSubmittedText !== null) {
      if ((currentText || '').trim() !== formEl.dataset.lastSubmittedText) {
        formEl.dataset.clientOpId = generateClientOpId();
        delete formEl.dataset.lastSubmittedText;
      }
    }
  }

  function showConcurrencyConflictBox(editWrap, comment, resultData, editTextarea, editCharCount, draftKey) {
    if (!editWrap) return;
    const currentRevision = (resultData && resultData.currentRevision !== undefined)
      ? resultData.currentRevision
      : ((comment.revision !== undefined ? comment.revision : 1) + 1);
    const currentContent = (resultData && resultData.currentContent !== undefined)
      ? resultData.currentContent
      : '';

    let conflictBox = editWrap.querySelector('.edit-conflict-box');
    if (!conflictBox) {
      conflictBox = document.createElement('div');
      conflictBox.className = 'edit-conflict-box';
      const footer = editWrap.querySelector('.comment-form-footer');
      if (footer) {
        editWrap.insertBefore(conflictBox, footer);
      } else {
        editWrap.appendChild(conflictBox);
      }
    }

    conflictBox.innerHTML =
      '<div class="conflict-message">Текст был изменен в другой сессии. Ваша версия не сохранена.</div>' +
      '<div class="conflict-server-preview"></div>' +
      '<div class="conflict-actions">' +
        '<button type="button" class="btn btn-secondary btn-sm btn-conflict-load-server">Загрузить версию с сервера</button>' +
        '<button type="button" class="btn btn-secondary btn-sm btn-conflict-keep-local">Оставить мой текст</button>' +
      '</div>';

    const previewEl = conflictBox.querySelector('.conflict-server-preview');
    if (previewEl) {
      previewEl.textContent = currentContent;
    }

    const loadServerBtn = conflictBox.querySelector('.btn-conflict-load-server');
    if (loadServerBtn) {
      loadServerBtn.addEventListener('click', function () {
        if (editTextarea) {
          editTextarea.value = currentContent;
          if (editCharCount) editCharCount.textContent = currentContent.length;
          if (draftKey && window._commentDrafts) {
            window._commentDrafts[draftKey] = currentContent;
          }
          editTextarea.focus();
        }
        comment.revision = currentRevision;
        conflictBox.remove();
      });
    }

    const keepLocalBtn = conflictBox.querySelector('.btn-conflict-keep-local');
    if (keepLocalBtn) {
      keepLocalBtn.addEventListener('click', function () {
        comment.revision = currentRevision;
        conflictBox.remove();
      });
    }
  }

  function getMaxWindowDepth() {
    if (window.innerWidth < 680) {
      return 5;
    }
    return 8;
  }

  function buildCommentTree(comments) {
    const byId = {};
    (comments || []).forEach(function (c) {
      byId[c.id] = Object.assign({}, c, { children: [] });
    });
    const roots = [];
    (comments || []).forEach(function (c) {
      const node = byId[c.id];
      if (c.parentCommentId && byId[c.parentCommentId]) {
        byId[c.parentCommentId].children.push(node);
      } else {
        roots.push(node);
      }
    });
    return { roots: roots, byId: byId };
  }

  function countDescendants(node) {
    let count = 0;
    if (!node || !Array.isArray(node.children)) return 0;
    node.children.forEach(function (child) {
      if (!child.isDeleted) {
        count += 1;
      }
      count += countDescendants(child);
    });
    return count;
  }

  function renderCommentNode(comment, depth, treeContext, isLastChild, hasContinuation) {
    const el = document.createElement('div');
    const isSol = Boolean(comment.isSolution || comment.is_solution);
    const isClarification = Boolean(treeContext && treeContext.isQuestionClarification);
    const isAnswerReply = Boolean(comment.parentAnswerId || comment.parent_answer_id || (treeContext && treeContext.isAnswerReply));
    const isChild = depth > 0 || Boolean(comment.parentCommentId);
    const totalDescendants = countDescendants(comment);
    isLastChild = (isLastChild === undefined) ? true : Boolean(isLastChild);
    hasContinuation = Boolean(hasContinuation);

    const classList = ['comment-item'];
    if (isSol) classList.push('is-solution-comment');
    if (isClarification) {
      classList.push('question-comment-item');
      classList.push('question-clarification-item');
    }
    if (isAnswerReply) {
      classList.push('answer-reply-item');
    }
    if (comment.isDeleted) {
      classList.push('comment-deleted-placeholder');
    }
    if (isChild) {
      classList.push('comment-child-node');
    }
    if (depth >= 3) {
      classList.push('comment-thread-depth-limit');
    }
    el.className = classList.join(' ');
    el.setAttribute('data-id', comment.id);
    el.id = 'comm_' + comment.id;

    // Reddit geometry continuous connectors for child comments
    let elbow = null;
    let stem = null;
    let connector = null;
    if (isChild) {
      elbow = document.createElement('div');
      elbow.className = 'comment-branch-elbow';
      elbow.setAttribute('aria-hidden', 'true');
      el.appendChild(elbow);

      if (!isLastChild || hasContinuation) {
        stem = document.createElement('div');
        stem.className = 'comment-branch-stem';
        stem.setAttribute('aria-hidden', 'true');
        el.appendChild(stem);
      }

      // Backward compatible hidden marker
      connector = document.createElement('div');
      connector.className = 'comment-branch-connector';
      connector.setAttribute('aria-hidden', 'true');
      connector.style.display = 'none';
      el.appendChild(connector);
    }

    const authorName = comment.authorName || 'Пользователь';
    const authorId = comment.userId || comment.user_id || '';
    const initials = getAuthorInitials(authorName);
    const rawDate = comment.createdAt || comment.created_at;
    const absDateText = formatCommentDate(rawDate);
    const relTimeText = formatCommentTimeRelative(rawDate);

    function scrollToParentComment(targetId) {
      if (!targetId) return;
      let targetEl = document.getElementById('comm_' + targetId);
      if (!targetEl && window._commentDrilldownState && window._commentDrilldownState.stack.length > 0) {
        while (window._commentDrilldownState.stack.length > 0 && !targetEl) {
          window._commentDrilldownState.stack.pop();
          if (treeContext && typeof treeContext.onReload === 'function') {
            treeContext.onReload();
          }
          targetEl = document.getElementById('comm_' + targetId);
        }
      }

      // Expand ancestors
      let curr = window._allCommentsMap ? window._allCommentsMap[targetId] : null;
      let visited = new Set();
      while (curr) {
        const pId = curr.parentCommentId || curr.parent_comment_id;
        if (pId && !visited.has(pId)) {
          visited.add(pId);
          window._expandedCommentIds.add(pId);
          const chCont = document.getElementById('thread_' + pId);
          if (chCont) chCont.style.display = 'flex';
          const tBtn = document.querySelector('[aria-controls="thread_' + pId + '"]');
          if (tBtn) {
            tBtn.setAttribute('aria-expanded', 'true');
            tBtn.setAttribute('aria-label', 'Скрыть комментарии');
            tBtn.setAttribute('title', 'Скрыть комментарии');
            const minusSvg = '<svg width="9" height="9" viewBox="0 0 9 9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><line x1="0" y1="4.5" x2="9" y2="4.5"></line></svg>';
            const iconEl = tBtn.querySelector('.thread-toggle-icon');
            if (iconEl) iconEl.innerHTML = minusSvg + '<span class="sr-only">-</span>';
            const txtEl = tBtn.querySelector('.toggle-thread-text');
            if (txtEl) {
              txtEl.className = 'toggle-thread-text sr-only';
              txtEl.textContent = 'Скрыть комментарии';
            }
            const pRow = tBtn.closest('.comment-toggle-row');
            if (pRow) pRow.classList.add('is-expanded');
            const pThrough = pRow ? pRow.querySelector('.comment-stem-through') : null;
            if (pThrough) pThrough.style.display = 'block';
          }
          curr = window._allCommentsMap[pId];
        } else {
          break;
        }
      }

      setTimeout(function () {
        const finalTarget = document.getElementById('comm_' + targetId);
        if (finalTarget) {
          finalTarget.scrollIntoView({ behavior: 'smooth', block: 'center' });
          finalTarget.classList.add('comment-highlight');
          setTimeout(function () {
            finalTarget.classList.remove('comment-highlight');
          }, 2500);
        }
      }, 100);
    }

    function setTreePathHighlight(active) {
      if (elbow) {
        elbow.classList.toggle('is-tree-path-active', active);
      }
      if (connector) {
        connector.classList.toggle('is-connection-active', active);
      }
      const myAvatar = el.querySelector('.comment-main .comment-author-avatar');
      if (myAvatar) {
        myAvatar.classList.toggle('avatar-peer-highlight', active);
      }

      const parentThread = el.closest('.comment-thread-children');
      if (!parentThread) return;
      const parentItem = parentThread.closest('.comment-item');
      if (!parentItem) return;

      const parentUpper = parentItem.querySelector('.comment-main .comment-stem-upper');
      if (parentUpper) {
        parentUpper.classList.toggle('is-tree-path-active', active);
      }

      const parentToggleRow = parentItem.querySelector(':scope > .comment-toggle-row');
      if (parentToggleRow) {
        const pStemUpper = parentToggleRow.querySelector('.comment-toggle-stem-upper');
        if (pStemUpper) pStemUpper.classList.toggle('is-tree-path-active', active);

        const pStemThrough = parentToggleRow.querySelector('.comment-stem-through');
        if (pStemThrough) pStemThrough.classList.toggle('is-tree-path-active', active);

        const pToggleBtn = parentToggleRow.querySelector('.btn-toggle-thread');
        if (pToggleBtn) pToggleBtn.classList.toggle('is-tree-path-active', active);

        const pToggleIcon = parentToggleRow.querySelector('.thread-toggle-icon');
        if (pToggleIcon) pToggleIcon.classList.toggle('is-tree-path-active', active);
      }

      const parentAvatar = parentItem.querySelector('.comment-main .comment-author-avatar');
      if (parentAvatar) {
        parentAvatar.classList.toggle('avatar-peer-highlight', active);
      }

      let prevSib = el.previousElementSibling;
      while (prevSib) {
        if (prevSib.classList.contains('comment-child-node')) {
          const sibStem = prevSib.querySelector(':scope > .comment-branch-stem');
          if (sibStem) {
            sibStem.classList.toggle('is-tree-path-active', active);
          }
        }
        prevSib = prevSib.previousElementSibling;
      }
    }

    if (elbow) {
      elbow.addEventListener('mouseenter', function () { setTreePathHighlight(true); });
      elbow.addEventListener('mouseleave', function () { setTreePathHighlight(false); });
      elbow.addEventListener('focus', function () { setTreePathHighlight(true); });
      elbow.addEventListener('blur', function () { setTreePathHighlight(false); });
    }

    if (stem) {
      stem.addEventListener('mouseenter', function () {
        if (el.nextElementSibling && typeof el.nextElementSibling._setTreePathHighlight === 'function') {
          el.nextElementSibling._setTreePathHighlight(true);
        }
      });
      stem.addEventListener('mouseleave', function () {
        if (el.nextElementSibling && typeof el.nextElementSibling._setTreePathHighlight === 'function') {
          el.nextElementSibling._setTreePathHighlight(false);
        }
      });
    }
    el._setTreePathHighlight = setTreePathHighlight;

    if (comment.isDeleted) {
      const deletedMain = document.createElement('div');
      deletedMain.className = 'comment-main';
      deletedMain.innerHTML =
        '<div class="comment-gutter comment-avatar-col">' +
          '<div class="comment-author-avatar" style="opacity: 0.5;">?</div>' +
          (totalDescendants > 0 ? '<div class="comment-stem-upper" aria-hidden="true"></div>' : '') +
        '</div>' +
        '<div class="comment-body-col">' +
          '<div class="comment-text" style="font-style: italic; color: var(--text-muted);">' +
            'Комментарий удален' +
          '</div>' +
        '</div>';
      el.appendChild(deletedMain);
    } else {
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

      const isAnswer = comment.commentType === 'answer' || comment.comment_type === 'answer';
      const commentTypeBadge = isAnswer ? '<span class="comment-type-badge answer-badge">Ответ</span>' : '';
      const hasUpdated = Boolean(comment.updatedAt || comment.updated_at);
      const updatedBadgeHtml = hasUpdated
        ? '<span class="comment-updated-badge" style="font-size: 0.74rem; color: var(--text-muted); margin-left: 6px;">(изменен)</span>'
        : '';

      let srOnlyReplyHtml = '';
      if (comment.parentCommentId) {
        const parentComment = (treeContext && treeContext.allCommentsById) ? treeContext.allCommentsById[comment.parentCommentId] : null;
        const parentName = parentComment ? (parentComment.authorName || 'автору') : 'автору';
        srOnlyReplyHtml = '<span class="sr-only">В ответ на комментарий @' + escapeHtml(parentName) + '</span>';
      }

      const isMyComment = Boolean(currentUser && (
        currentUser.id === comment.userId ||
        currentUser.id === comment.user_id
      ));
      const commScore = comment.score !== undefined ? comment.score : 0;
      const commMyVote = comment.myVote !== undefined ? comment.myVote : 0;
      const commCanVote = comment.canVote !== false && !isMyComment;
      const commVoteCapsuleHtml = (window.SmartContractumVotes && typeof window.SmartContractumVotes.renderVoteCapsuleHtml === 'function')
        ? window.SmartContractumVotes.renderVoteCapsuleHtml({
            targetType: 'comment',
            targetId: comment.id,
            score: commScore,
            myVote: commMyVote,
            canVote: commCanVote,
            isAuthor: isMyComment,
            isDeleted: Boolean(comment.isDeleted)
          })
        : '';

      let editBtnHtml = '';
      if (isMyComment) {
        editBtnHtml =
          '<button type="button" class="btn-action-text btn-edit-comment">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
              '<path d="M12 20h9"></path>' +
              '<path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>' +
            '</svg>' +
            '<span>Редактировать</span>' +
          '</button>';
      }

      const mainContainer = document.createElement('div');
      mainContainer.className = 'comment-main';

      const gutter = document.createElement('div');
      gutter.className = 'comment-gutter comment-avatar-col';

      const avatarEl = document.createElement('div');
      avatarEl.className = 'comment-author-avatar';
      avatarEl.textContent = initials;
      gutter.appendChild(avatarEl);

      let stemUpper = null;
      if (totalDescendants > 0) {
        stemUpper = document.createElement('div');
        stemUpper.className = 'comment-stem-upper';
        stemUpper.setAttribute('aria-hidden', 'true');
        stemUpper.addEventListener('mouseenter', function () {
          stemUpper.classList.add('is-tree-path-active');
          if (avatarEl) avatarEl.classList.add('avatar-peer-highlight');
          const pToggleRow = el.querySelector(':scope > .comment-toggle-row');
          if (pToggleRow) {
            const tBtn = pToggleRow.querySelector('.btn-toggle-thread');
            if (tBtn) tBtn.classList.add('is-tree-path-active');
            const tIcon = pToggleRow.querySelector('.thread-toggle-icon');
            if (tIcon) tIcon.classList.add('is-tree-path-active');
            const tStemUpper = pToggleRow.querySelector('.comment-toggle-stem-upper');
            if (tStemUpper) tStemUpper.classList.add('is-tree-path-active');
            const tStemThrough = pToggleRow.querySelector('.comment-stem-through');
            if (tStemThrough) tStemThrough.classList.add('is-tree-path-active');
          }
        });
        stemUpper.addEventListener('mouseleave', function () {
          stemUpper.classList.remove('is-tree-path-active');
          if (avatarEl) avatarEl.classList.remove('avatar-peer-highlight');
          const pToggleRow = el.querySelector(':scope > .comment-toggle-row');
          if (pToggleRow) {
            const tBtn = pToggleRow.querySelector('.btn-toggle-thread');
            if (tBtn) tBtn.classList.remove('is-tree-path-active');
            const tIcon = pToggleRow.querySelector('.thread-toggle-icon');
            if (tIcon) tIcon.classList.remove('is-tree-path-active');
            const tStemUpper = pToggleRow.querySelector('.comment-toggle-stem-upper');
            if (tStemUpper) tStemUpper.classList.remove('is-tree-path-active');
            const tStemThrough = pToggleRow.querySelector('.comment-stem-through');
            if (tStemThrough) tStemThrough.classList.remove('is-tree-path-active');
          }
        });
        gutter.appendChild(stemUpper);
      }
      mainContainer.appendChild(gutter);

      const bodyCol = document.createElement('div');
      bodyCol.className = 'comment-body-col';
      bodyCol.innerHTML =
        '<div class="comment-item-header" style="display: flex; align-items: center; justify-content: space-between;">' +
          '<div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">' +
            '<button type="button" class="btn-author-profile" data-author-id="' + escapeHtml(authorId) + '" data-user-id="' + escapeHtml(authorId) + '">' + escapeHtml(authorName) + '</button>' +
            commentTypeBadge +
            '<time class="comment-date comment-time" datetime="' + escapeHtml(rawDate || '') + '" title="' + escapeHtml(absDateText) + '">' + escapeHtml(relTimeText) + '</time>' +
            updatedBadgeHtml +
            srOnlyReplyHtml +
          '</div>' +
          solutionActionBtn +
        '</div>' +
        solutionBadgeHtml +
        '<div class="comment-content-wrap">' +
          '<div class="comment-text">' + (comment.content ? escapeHtml(comment.content).replace(/\n/g, '<br>') : '') + '</div>' +
        '</div>' +
        '<div class="comment-edit-wrap" style="display: none;">' +
          '<textarea class="comment-textarea comment-edit-textarea" rows="3" maxlength="5000">' + escapeHtml(comment.content || '') + '</textarea>' +
          '<div class="comment-form-footer" style="margin-top: 8px;">' +
            '<span class="comment-char-counter"><span class="edit-char-count">' + (comment.content ? comment.content.length : 0) + '</span> / 5000</span>' +
            '<div style="display: flex; gap: 8px;">' +
              '<button type="button" class="btn btn-secondary btn-sm btn-cancel-comment-edit">Отмена</button>' +
              '<button type="button" class="btn btn-primary btn-sm btn-save-comment-edit">Сохранить</button>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '<div class="comment-vote-row">' +
          commVoteCapsuleHtml +
        '</div>' +
        '<div class="comment-actions">' +
          editBtnHtml +
          '<button type="button" class="btn-action-text btn-reply-comment">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
              '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>' +
            '</svg>' +
            '<span>Ответить</span>' +
          '</button>' +
        '</div>' +
        '<div class="comment-reply-form-wrap" style="display: none;">' +
          '<div class="comment-reply-header">Ответ для <strong>' + escapeHtml(authorName) + '</strong></div>' +
          '<textarea class="comment-textarea comment-reply-textarea" rows="2" maxlength="5000" placeholder="Написать ответ..."></textarea>' +
          '<div class="comment-form-footer" style="margin-top: 8px;">' +
            '<span class="comment-char-counter"><span class="reply-char-count">0</span> / 5000</span>' +
            '<div style="display: flex; gap: 8px;">' +
              '<button type="button" class="btn btn-secondary btn-sm btn-cancel-reply-form">Отмена</button>' +
              '<button type="button" class="btn btn-primary btn-sm btn-submit-reply-form">Отправить</button>' +
            '</div>' +
          '</div>' +
        '</div>';

      mainContainer.appendChild(bodyCol);
      el.appendChild(mainContainer);

      // Inline edit handlers
      const editBtn = el.querySelector('.btn-edit-comment');
      const editWrap = el.querySelector('.comment-edit-wrap');
      const contentWrap = el.querySelector('.comment-content-wrap');
      const editTextarea = el.querySelector('.comment-edit-textarea');
      const editCharCount = el.querySelector('.edit-char-count');
      const cancelEditBtn = el.querySelector('.btn-cancel-comment-edit');
      const saveEditBtn = el.querySelector('.btn-save-comment-edit');
      const commentTextEl = el.querySelector('.comment-text');

      const editDraftKey = 'edit_' + comment.id;
      if (window._commentDrafts && window._commentDrafts[editDraftKey] && editTextarea) {
        editTextarea.value = window._commentDrafts[editDraftKey];
        if (editCharCount) editCharCount.textContent = editTextarea.value.length;
      }

      if (editBtn && editWrap && contentWrap) {
        editBtn.addEventListener('click', function (e) {
          e.preventDefault();
          const conflictBox = editWrap.querySelector('.edit-conflict-box');
          if (conflictBox) conflictBox.remove();
          contentWrap.style.display = 'none';
          editWrap.style.display = 'block';
          if (editTextarea) {
            if (!editTextarea.value) {
              editTextarea.value = comment.content || '';
            }
            editTextarea.focus();
            if (editCharCount) editCharCount.textContent = editTextarea.value.length;
          }
        });

        if (cancelEditBtn) {
          cancelEditBtn.addEventListener('click', function () {
            if (window._commentDrafts) delete window._commentDrafts[editDraftKey];
            const conflictBox = editWrap.querySelector('.edit-conflict-box');
            if (conflictBox) conflictBox.remove();
            editWrap.style.display = 'none';
            contentWrap.style.display = 'block';
            if (editTextarea) {
              editTextarea.value = comment.content || '';
              if (editCharCount) editCharCount.textContent = editTextarea.value.length;
            }
          });
        }

        if (editTextarea && editCharCount) {
          editTextarea.addEventListener('input', function () {
            editCharCount.textContent = editTextarea.value.length;
            window._commentDrafts = window._commentDrafts || {};
            window._commentDrafts[editDraftKey] = editTextarea.value;
          });
        }

        if (saveEditBtn && editTextarea) {
          saveEditBtn.addEventListener('click', function (e) {
            e.preventDefault();
            const newContent = editTextarea.value.trim();
            if (!newContent) {
              showToast('Комментарий не может быть пустым');
              editTextarea.focus();
              return;
            }
            if (newContent.length > 5000) {
              showToast('Превышен лимит длины (максимум 5000 символов)');
              return;
            }

            saveEditBtn.disabled = true;
            const targetArtId = (treeContext && treeContext.articleId) || (currentArticle ? currentArticle.id : '');

            fetch('/api/articles/' + encodeURIComponent(targetArtId) + '/comments/' + encodeURIComponent(comment.id), {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                content: newContent,
                revision: comment.revision !== undefined ? comment.revision : 1
              })
            })
              .then(function (res) {
                return res.json().then(function (data) {
                  return { status: res.status, data: data };
                });
              })
              .then(function (result) {
                saveEditBtn.disabled = false;
                if (result.status === 409 || (result.data && result.data.code === 'CONCURRENCY_CONFLICT')) {
                  showConcurrencyConflictBox(editWrap, comment, result.data, editTextarea, editCharCount, editDraftKey);
                  return;
                }

                if (result.data && result.data.success && result.data.comment) {
                  const conflictBox = editWrap.querySelector('.edit-conflict-box');
                  if (conflictBox) conflictBox.remove();
                  if (window._commentDrafts) delete window._commentDrafts[editDraftKey];
                  const updated = result.data.comment;
                  comment.content = updated.content;
                  comment.revision = updated.revision;
                  comment.updatedAt = updated.updatedAt;

                  if (commentTextEl) {
                    commentTextEl.innerHTML = escapeHtml(comment.content).replace(/\n/g, '<br>');
                  }
                  let updatedBadge = el.querySelector('.comment-updated-badge');
                  if (!updatedBadge) {
                    const timeEl = el.querySelector('time.comment-time');
                    if (timeEl) {
                      const badgeSpan = document.createElement('span');
                      badgeSpan.className = 'comment-updated-badge';
                      badgeSpan.style.cssText = 'font-size: 0.74rem; color: var(--text-muted); margin-left: 6px;';
                      badgeSpan.textContent = '(изменен)';
                      timeEl.insertAdjacentElement('afterend', badgeSpan);
                    }
                  }
                  editWrap.style.display = 'none';
                  contentWrap.style.display = 'block';
                  showToast('Комментарий сохранен');
                } else {
                  showToast((result.data && result.data.error) || 'Ошибка при сохранении комментария');
                }
              })
              .catch(function (err) {
                saveEditBtn.disabled = false;
                console.error('Failed to save comment edit:', err);
                showToast('Не удалось сохранить комментарий');
              });
          });
        }
      }

      // Inline reply handlers
      const replyBtn = el.querySelector('.btn-reply-comment');
      const replyWrap = el.querySelector('.comment-reply-form-wrap');
      const replyTextarea = el.querySelector('.comment-reply-textarea');
      const replyCharCount = el.querySelector('.reply-char-count');
      const cancelReplyBtn = el.querySelector('.btn-cancel-reply-form');
      const submitReplyBtn = el.querySelector('.btn-submit-reply-form');

      const replyDraftKey = 'reply_' + comment.id;
      if (window._commentDrafts && window._commentDrafts[replyDraftKey] && replyTextarea) {
        replyTextarea.value = window._commentDrafts[replyDraftKey];
        if (replyCharCount) replyCharCount.textContent = replyTextarea.value.length;
        if (replyWrap) {
          replyWrap.style.display = 'block';
          getOrCreateClientOpId(replyWrap);
        }
      }

      if (replyBtn && replyWrap) {
        replyBtn.addEventListener('click', function (e) {
          e.preventDefault();
          if (!currentUser) {
            openAuthModal();
            showToast('Войдите, чтобы ответить на комментарий');
            return;
          }
          const isShown = replyWrap.style.display === 'block';
          replyWrap.style.display = isShown ? 'none' : 'block';
          if (!isShown) {
            getOrCreateClientOpId(replyWrap);
            if (replyTextarea) {
              replyTextarea.focus();
            }
          }
        });

        if (cancelReplyBtn) {
          cancelReplyBtn.addEventListener('click', function () {
            if (window._commentDrafts) delete window._commentDrafts[replyDraftKey];
            resetClientOpId(replyWrap);
            replyWrap.style.display = 'none';
            if (replyTextarea) replyTextarea.value = '';
          });
        }

        if (replyTextarea && replyCharCount) {
          replyTextarea.addEventListener('input', function () {
            replyCharCount.textContent = replyTextarea.value.length;
            handleFormTextInput(replyWrap, replyTextarea.value);
            window._commentDrafts = window._commentDrafts || {};
            window._commentDrafts[replyDraftKey] = replyTextarea.value;
          });
        }

        if (submitReplyBtn && replyTextarea) {
          submitReplyBtn.addEventListener('click', function (e) {
            e.preventDefault();
            if (!currentUser) {
              openAuthModal();
              showToast('Войдите, чтобы оставить комментарий');
              return;
            }
            const replyText = replyTextarea.value.trim();
            if (!replyText) {
              showToast('Комментарий не может быть пустым');
              replyTextarea.focus();
              return;
            }
            if (replyText.length > 5000) {
              showToast('Превышен лимит длины (максимум 5000 символов)');
              return;
            }

            submitReplyBtn.disabled = true;
            const targetArtId = (treeContext && treeContext.articleId) || (currentArticle ? currentArticle.id : '');
            const clientOpId = getOrCreateClientOpId(replyWrap);
            replyWrap.dataset.lastSubmittedText = replyText;

            fetch('/api/articles/' + encodeURIComponent(targetArtId) + '/comments', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                content: replyText,
                commentType: 'comment',
                parentCommentId: comment.id,
                clientOperationId: clientOpId
              })
            })
              .then(function (res) {
                if (res.status === 401) {
                  submitReplyBtn.disabled = false;
                  openAuthModal();
                  throw new Error('AUTH_REQUIRED');
                }
                return res.json().then(function (data) {
                  return { status: res.status, data: data };
                });
              })
              .then(function (result) {
                submitReplyBtn.disabled = false;
                const data = result.data;
                if ((result.status === 200 || result.status === 201) && data && data.success && data.comment) {
                  resetClientOpId(replyWrap);
                  if (window._commentDrafts) delete window._commentDrafts[replyDraftKey];
                  replyTextarea.value = '';
                  if (replyCharCount) replyCharCount.textContent = '0';
                  replyWrap.style.display = 'none';
                  showToast('Ответ опубликован');

                  // Make sure parent is expanded
                  window._expandedCommentIds.add(comment.id);
                  if (treeContext && typeof treeContext.onReload === 'function') {
                    treeContext.onReload(data.comment.id);
                  }
                } else {
                  showToast((data && data.error) || 'Ошибка при отправке ответа');
                }
              })
              .catch(function (err) {
                submitReplyBtn.disabled = false;
                if (err.message !== 'AUTH_REQUIRED') {
                  console.error('Failed to submit reply:', err);
                  showToast('Не удалось отправить ответ');
                }
              });
          });
        }
      }
    }

    // Children & Thread toggle / Drilldown continuation
    if (totalDescendants > 0) {
      const maxDepth = getMaxWindowDepth();
      if (depth >= maxDepth) {
        const continueRow = document.createElement('div');
        continueRow.className = 'comment-toggle-row comment-continue-row';

        const toggleStemUpper = document.createElement('div');
        toggleStemUpper.className = 'comment-toggle-stem-upper';
        toggleStemUpper.setAttribute('aria-hidden', 'true');
        continueRow.appendChild(toggleStemUpper);

        const continueBtn = document.createElement('button');
        continueBtn.type = 'button';
        continueBtn.className = 'btn btn-continue-thread';
        continueBtn.setAttribute('data-comment-id', comment.id);
        continueBtn.setAttribute('aria-label', 'Продолжить ветку (' + totalDescendants + ')');
        continueBtn.innerHTML =
          '<span class="thread-toggle-icon continue-thread-icon" aria-hidden="true">' +
            '<svg width="9" height="9" viewBox="0 0 9 9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
              '<polyline points="3 1.5 6 4.5 3 7.5"></polyline>' +
            '</svg>' +
          '</span>' +
          '<span class="continue-thread-text">Продолжить ветку (' + totalDescendants + ')</span>';

        continueBtn.addEventListener('click', function (e) {
          e.preventDefault();
          window._commentDrilldownState = window._commentDrilldownState || { stack: [] };
          window._commentDrilldownState.stack.push({
            rootCommentId: comment.id,
            scrollY: window.scrollY
          });
          if (treeContext && typeof treeContext.onReload === 'function') {
            treeContext.onReload(comment.id);
          }
        });

        continueRow.appendChild(continueBtn);
        el.appendChild(continueRow);
      } else {
        const isExpanded = window._expandedCommentIds.has(comment.id);

        const toggleRow = document.createElement('div');
        toggleRow.className = 'comment-toggle-row' + (isExpanded ? ' is-expanded' : '');

        const toggleStemUpper = document.createElement('div');
        toggleStemUpper.className = 'comment-toggle-stem-upper';
        toggleStemUpper.setAttribute('aria-hidden', 'true');
        toggleRow.appendChild(toggleStemUpper);

        const stemThrough = document.createElement('div');
        stemThrough.className = 'comment-stem-through';
        stemThrough.setAttribute('aria-hidden', 'true');
        stemThrough.style.display = isExpanded ? 'block' : 'none';
        toggleRow.appendChild(stemThrough);

        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'btn-toggle-thread';
        toggleBtn.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
        toggleBtn.setAttribute('aria-controls', 'thread_' + comment.id);

        const minusSvg = '<svg width="9" height="9" viewBox="0 0 9 9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><line x1="0" y1="4.5" x2="9" y2="4.5"></line></svg>';
        const plusSvg = '<svg width="9" height="9" viewBox="0 0 9 9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><line x1="0" y1="4.5" x2="9" y2="4.5"></line><line x1="4.5" y1="0" x2="4.5" y2="9"></line></svg>';

        function updateToggleContent(expanded) {
          if (expanded) {
            toggleBtn.innerHTML =
              '<span class="thread-toggle-icon" aria-hidden="true">' +
                minusSvg +
                '<span class="sr-only">-</span>' +
              '</span>' +
              '<span class="toggle-thread-text sr-only">Скрыть комментарии</span>';
            toggleBtn.setAttribute('aria-label', 'Скрыть комментарии');
            toggleBtn.setAttribute('title', 'Скрыть комментарии');
            toggleRow.classList.add('is-expanded');
          } else {
            toggleBtn.innerHTML =
              '<span class="thread-toggle-icon" aria-hidden="true">' +
                plusSvg +
                '<span class="sr-only">+</span>' +
              '</span>' +
              '<span class="toggle-thread-text">Показать комментарии (' + totalDescendants + ')</span>';
            toggleBtn.setAttribute('aria-label', 'Показать комментарии (' + totalDescendants + ')');
            toggleBtn.setAttribute('title', 'Показать комментарии (' + totalDescendants + ')');
            toggleRow.classList.remove('is-expanded');
          }
        }

        updateToggleContent(isExpanded);
        toggleRow.appendChild(toggleBtn);

        const commentActions = el.querySelector('.comment-actions');
        if (commentActions) {
          toggleRow.appendChild(commentActions);
        }

        el.appendChild(toggleRow);

        const replyWrap = el.querySelector('.comment-reply-form-wrap');
        if (replyWrap) {
          toggleRow.insertAdjacentElement('afterend', replyWrap);
        }

        function setLocalToggleHighlight(active) {
          toggleBtn.classList.toggle('is-tree-path-active', active);
          const tIcon = toggleBtn.querySelector('.thread-toggle-icon');
          if (tIcon) tIcon.classList.toggle('is-tree-path-active', active);
          toggleStemUpper.classList.toggle('is-tree-path-active', active);
          stemThrough.classList.toggle('is-tree-path-active', active);
          const upper = el.querySelector('.comment-main .comment-stem-upper');
          if (upper) upper.classList.toggle('is-tree-path-active', active);
          const av = el.querySelector('.comment-main .comment-author-avatar');
          if (av) av.classList.toggle('avatar-peer-highlight', active);
        }

        toggleBtn.addEventListener('mouseenter', function () { setLocalToggleHighlight(true); });
        toggleBtn.addEventListener('mouseleave', function () { setLocalToggleHighlight(false); });
        toggleStemUpper.addEventListener('mouseenter', function () { setLocalToggleHighlight(true); });
        toggleStemUpper.addEventListener('mouseleave', function () { setLocalToggleHighlight(false); });
        stemThrough.addEventListener('mouseenter', function () { setLocalToggleHighlight(true); });
        stemThrough.addEventListener('mouseleave', function () { setLocalToggleHighlight(false); });

        const childrenContainer = document.createElement('div');
        childrenContainer.className = 'comment-thread-children';
        childrenContainer.id = 'thread_' + comment.id;
        childrenContainer.style.display = isExpanded ? 'flex' : 'none';

        const childList = comment.children || [];
        childList.forEach(function (child, idx) {
          const isLast = (idx === childList.length - 1);
          childrenContainer.appendChild(renderCommentNode(child, depth + 1, treeContext, isLast, false));
        });

        toggleBtn.addEventListener('click', function (e) {
          e.preventDefault();
          const currentlyExpanded = window._expandedCommentIds.has(comment.id);
          if (currentlyExpanded) {
            if (childrenContainer.contains(document.activeElement)) {
              toggleBtn.focus();
            }
            window._expandedCommentIds.delete(comment.id);
            toggleBtn.setAttribute('aria-expanded', 'false');
            updateToggleContent(false);
            childrenContainer.style.display = 'none';
            stemThrough.style.display = 'none';
          } else {
            window._expandedCommentIds.add(comment.id);
            toggleBtn.setAttribute('aria-expanded', 'true');
            updateToggleContent(true);
            childrenContainer.style.display = 'flex';
            stemThrough.style.display = 'block';
          }
        });

        el.appendChild(toggleRow);
        el.appendChild(childrenContainer);
      }
    }

    return el;
  }

  function renderCommentItem(comment) {
    return renderCommentNode(comment, 0, {
      articleId: currentArticle ? currentArticle.id : '',
      allCommentsById: window._allCommentsMap || {},
      isQuestionClarification: false,
      onReload: function (newId) {
        if (currentArticle) loadComments(currentArticle.id);
      }
    });
  }

  function renderQuestionClarificationItem(comment) {
    return renderCommentNode(comment, 0, {
      articleId: currentArticle ? currentArticle.id : '',
      allCommentsById: window._allCommentsMap || {},
      isQuestionClarification: true,
      onReload: function (newId) {
        if (currentArticle) loadComments(currentArticle.id);
      }
    });
  }

  function renderAnswerReplyItem(reply) {
    return renderCommentNode(reply, 1, {
      articleId: currentArticle ? currentArticle.id : '',
      allCommentsById: window._allCommentsMap || {},
      isQuestionClarification: false,
      isAnswerReply: true,
      onReload: function (newId) {
        if (currentArticle) loadComments(currentArticle.id);
      }
    });
  }

  // Render Answer Card (.answer-card)
  function renderAnswerCard(comment, articleId, allComments) {
    const el = document.createElement('div');
    const isSol = Boolean(comment.isSolution || comment.is_solution);
    el.className = 'answer-card' + (isSol ? ' is-solution-answer' : '');
    el.setAttribute('data-id', comment.id);
    el.id = 'comm_' + comment.id;

    const authorName = comment.authorName || 'Пользователь';
    const authorId = comment.userId || comment.user_id || '';
    const initials = getAuthorInitials(authorName);
    const rawDate = comment.createdAt || comment.created_at;
    const absDateText = formatCommentDate(rawDate);
    const relTimeText = formatCommentTimeRelative(rawDate);

    const hasUpdated = Boolean(comment.updatedAt || comment.updated_at);
    const updatedBadgeHtml = hasUpdated
      ? '<span class="comment-updated-badge" style="font-size: 0.74rem; color: var(--text-muted); margin-left: 6px;">(изменен)</span>'
      : '';

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

    const isAuthor = Boolean(currentUser && currentArticle && (currentUser.id === currentArticle.authorId || currentUser.id === currentArticle.author_id));

    let solutionActionBtn = '';
    if (isAuthor) {
      solutionActionBtn =
        '<button type="button" class="btn btn-sm btn-toggle-solution" data-comment-id="' + escapeHtml(comment.id) + '">' +
          (isSol ? 'Снять отметку решения' : 'Отметить как решение') +
        '</button>';
    }

    const isMyAnswer = Boolean(currentUser && (
      currentUser.id === comment.userId ||
      currentUser.id === comment.user_id
    ));
    const ansScore = comment.score !== undefined ? comment.score : 0;
    const ansMyVote = comment.myVote !== undefined ? comment.myVote : 0;
    const ansCanVote = comment.canVote !== false && !isMyAnswer;
    const ansVoteCapsuleHtml = (window.SmartContractumVotes && typeof window.SmartContractumVotes.renderVoteCapsuleHtml === 'function')
      ? window.SmartContractumVotes.renderVoteCapsuleHtml({
          targetType: 'comment',
          targetId: comment.id,
          score: ansScore,
          myVote: ansMyVote,
          canVote: ansCanVote,
          isAuthor: isMyAnswer,
          isDeleted: Boolean(comment.isDeleted)
        })
      : '';

    let editBtnHtml = '';
    if (isMyAnswer) {
      editBtnHtml = '<button type="button" class="btn btn-secondary btn-sm btn-edit-answer">Редактировать</button>';
    }

    let replies = comment.comments;
    if (!Array.isArray(replies) && Array.isArray(allComments)) {
      replies = allComments.filter(function (c) {
        return c.parentAnswerId === comment.id || c.parent_answer_id === comment.id;
      });
    }
    if (!Array.isArray(replies)) replies = [];

    el.innerHTML =
      '<div class="answer-header">' +
        '<div class="answer-author-info">' +
          '<div class="comment-author-avatar">' + escapeHtml(initials) + '</div>' +
          '<div class="answer-author-meta">' +
            '<button type="button" class="btn-author-profile" data-author-id="' + escapeHtml(authorId) + '" data-user-id="' + escapeHtml(authorId) + '">' + escapeHtml(authorName) + '</button>' +
            '<time class="comment-date comment-time" datetime="' + escapeHtml(rawDate || '') + '" title="' + escapeHtml(absDateText) + '">' + escapeHtml(relTimeText) + '</time>' +
            '<span class="answer-updated-wrap">' + updatedBadgeHtml + '</span>' +
          '</div>' +
        '</div>' +
        solutionActionBtn +
      '</div>' +
      solutionBadgeHtml +
      '<div class="answer-content">' +
        '<div class="answer-text">' + (comment.content ? escapeHtml(comment.content).replace(/\n/g, '<br>') : '') + '</div>' +
      '</div>' +
      '<div class="answer-edit-form-wrap" style="display: none;">' +
        '<textarea class="comment-textarea answer-edit-textarea" rows="4" maxlength="5000" placeholder="Редактировать ответ...">' + escapeHtml(comment.content || '') + '</textarea>' +
        '<div class="comment-form-footer" style="margin-top: 8px;">' +
          '<span class="comment-char-counter"><span class="answer-edit-char-count">' + (comment.content ? comment.content.length : 0) + '</span> / 5000</span>' +
          '<div style="display: flex; gap: 8px;">' +
            '<button type="button" class="btn btn-secondary btn-sm btn-cancel-answer-edit">Отмена</button>' +
            '<button type="button" class="btn btn-primary btn-sm btn-save-answer-edit">Сохранить</button>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<div class="comment-vote-row answer-vote-row">' +
        ansVoteCapsuleHtml +
      '</div>' +
      '<div class="answer-actions">' +
        editBtnHtml +
        '<button type="button" class="btn btn-secondary btn-sm btn-reply-answer">Комментировать ответ</button>' +
      '</div>' +
      '<div class="answer-replies-container" style="' + (replies.length > 0 ? '' : 'display: none;') + '">' +
        '<div class="answer-replies-list"></div>' +
        '<form class="comment-form answer-reply-form" style="display: none;">' +
          '<div class="comment-textarea-wrap">' +
            '<textarea class="comment-textarea answer-reply-textarea" placeholder="Написать комментарий к ответу..." maxlength="5000" rows="2" required></textarea>' +
            '<div class="comment-form-footer">' +
              '<span class="comment-char-counter"><span class="answer-reply-char-count">0</span> / 5000</span>' +
              '<div style="display: flex; gap: 8px;">' +
                '<button type="button" class="btn btn-secondary btn-sm btn-cancel-reply">Отмена</button>' +
                '<button type="submit" class="btn btn-primary btn-sm btn-submit-reply">Отправить</button>' +
              '</div>' +
            '</div>' +
          '</div>' +
        '</form>' +
      '</div>';

    // Populate replies
    const repliesListEl = el.querySelector('.answer-replies-list');
    if (repliesListEl && replies.length > 0) {
      const tree = buildCommentTree(replies);
      const stack = (window._commentDrilldownState && window._commentDrilldownState.stack) || [];
      let renderedDrilldown = false;
      if (stack.length > 0) {
        const currentFrame = stack[stack.length - 1];
        const drilldownRoot = tree.byId[currentFrame.rootCommentId];
        if (drilldownRoot) {
          renderedDrilldown = true;
          const drilldownBar = document.createElement('div');
          drilldownBar.className = 'thread-drilldown-bar';
          drilldownBar.innerHTML =
            '<button type="button" class="btn-drilldown-back">' +
              '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                '<polyline points="15 18 9 12 15 6"></polyline>' +
              '</svg>' +
              '<span>Назад к ответу</span>' +
            '</button>' +
            '<span class="thread-drilldown-title">Ветка обсуждения</span>';

          const backBtn = drilldownBar.querySelector('.btn-drilldown-back');
          if (backBtn) {
            backBtn.addEventListener('click', function (e) {
              e.preventDefault();
              const popped = window._commentDrilldownState.stack.pop();
              if (window._commentsResponseData) {
                renderCommentsData(window._commentsResponseData);
              } else {
                loadComments(articleId);
              }
              if (popped && typeof popped.scrollY === 'number') {
                window.scrollTo({ top: popped.scrollY, behavior: 'auto' });
              }
            });
          }
          repliesListEl.appendChild(drilldownBar);
          window._expandedCommentIds.add(drilldownRoot.id);
          repliesListEl.appendChild(renderCommentNode(drilldownRoot, 0, {
            articleId: articleId,
            allCommentsById: window._allCommentsMap || tree.byId,
            isQuestionClarification: false,
            isAnswerReply: true,
            onReload: function () {
              loadComments(articleId);
            }
          }));
        }
      }

      if (!renderedDrilldown) {
        tree.roots.forEach(function (r) {
          repliesListEl.appendChild(renderCommentNode(r, 0, {
            articleId: articleId,
            allCommentsById: window._allCommentsMap || tree.byId,
            isQuestionClarification: false,
            isAnswerReply: true,
            onReload: function () {
              loadComments(articleId);
            }
          }));
        });
      }
    }

    // Solution button handler
    const toggleBtn = el.querySelector('.btn-toggle-solution');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', function (e) {
        e.preventDefault();
        toggleSolution(comment.id, !isSol);
      });
    }

    // Inline edit handlers
    const editBtn = el.querySelector('.btn-edit-answer');
    const editWrap = el.querySelector('.answer-edit-form-wrap');
    const contentWrap = el.querySelector('.answer-content');
    const actionsWrap = el.querySelector('.answer-actions');
    const editTextarea = el.querySelector('.answer-edit-textarea');
    const editCharCount = el.querySelector('.answer-edit-char-count');
    const cancelEditBtn = el.querySelector('.btn-cancel-answer-edit');
    const saveEditBtn = el.querySelector('.btn-save-answer-edit');
    const textEl = el.querySelector('.answer-text');
    const updatedWrap = el.querySelector('.answer-updated-wrap');

    if (editBtn && editWrap && contentWrap && actionsWrap) {
      editBtn.addEventListener('click', function () {
        const conflictBox = editWrap.querySelector('.edit-conflict-box');
        if (conflictBox) conflictBox.remove();
        contentWrap.style.display = 'none';
        actionsWrap.style.display = 'none';
        editWrap.style.display = 'block';
        if (editTextarea) {
          editTextarea.value = comment.content || '';
          editTextarea.focus();
          if (editCharCount) editCharCount.textContent = editTextarea.value.length;
        }
      });

      if (cancelEditBtn) {
        cancelEditBtn.addEventListener('click', function () {
          const conflictBox = editWrap.querySelector('.edit-conflict-box');
          if (conflictBox) conflictBox.remove();
          editWrap.style.display = 'none';
          contentWrap.style.display = 'block';
          actionsWrap.style.display = 'flex';
          if (editTextarea) {
            editTextarea.value = comment.content || '';
            if (editCharCount) editCharCount.textContent = editTextarea.value.length;
          }
        });
      }

      if (editTextarea && editCharCount) {
        editTextarea.addEventListener('input', function () {
          editCharCount.textContent = editTextarea.value.length;
        });
      }

      if (saveEditBtn && editTextarea) {
        saveEditBtn.addEventListener('click', function (e) {
          e.preventDefault();
          const newContent = editTextarea.value.trim();
          if (!newContent) {
            showToast('Ответ не может быть пустым');
            editTextarea.focus();
            return;
          }
          if (newContent.length > 5000) {
            showToast('Превышен лимит длины (максимум 5000 символов)');
            return;
          }

          saveEditBtn.disabled = true;

          fetch('/api/articles/' + encodeURIComponent(articleId) + '/comments/' + encodeURIComponent(comment.id), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              content: newContent,
              revision: comment.revision !== undefined ? comment.revision : 1
            })
          })
            .then(function (res) {
              return res.json().then(function (data) {
                return { status: res.status, data: data };
              });
            })
            .then(function (result) {
              saveEditBtn.disabled = false;
              if (result.status === 409 || (result.data && result.data.code === 'CONCURRENCY_CONFLICT')) {
                showConcurrencyConflictBox(editWrap, comment, result.data, editTextarea, editCharCount, null);
                return;
              }

              if (result.data && result.data.success && result.data.comment) {
                const conflictBox = editWrap.querySelector('.edit-conflict-box');
                if (conflictBox) conflictBox.remove();
                const updated = result.data.comment;
                comment.content = updated.content;
                comment.revision = updated.revision;
                comment.updatedAt = updated.updatedAt;

                if (textEl) {
                  textEl.innerHTML = escapeHtml(comment.content).replace(/\n/g, '<br>');
                }
                let updatedBadge = el.querySelector('.comment-updated-badge');
                if (!updatedBadge) {
                  const timeEl = el.querySelector('time.comment-time');
                  if (timeEl) {
                    const badgeSpan = document.createElement('span');
                    badgeSpan.className = 'comment-updated-badge';
                    badgeSpan.style.cssText = 'font-size: 0.74rem; color: var(--text-muted); margin-left: 6px;';
                    badgeSpan.textContent = '(изменен)';
                    timeEl.insertAdjacentElement('afterend', badgeSpan);
                  } else if (updatedWrap) {
                    updatedWrap.innerHTML = '<span class="comment-updated-badge" style="font-size: 0.74rem; color: var(--text-muted); margin-left: 6px;">(изменен)</span>';
                  }
                } else {
                  updatedBadge.textContent = '(изменен)';
                }

                editWrap.style.display = 'none';
                contentWrap.style.display = 'block';
                actionsWrap.style.display = 'flex';
                showToast('Ответ обновлен');
              } else {
                showToast((result.data && result.data.error) || 'Ошибка при сохранении ответа');
              }
            })
            .catch(function (err) {
              saveEditBtn.disabled = false;
              console.error('Failed to update answer:', err);
              showToast('Не удалось обновить ответ');
            });
        });
      }
    }

    // Reply handlers
    const replyBtn = el.querySelector('.btn-reply-answer');
    const repliesContainer = el.querySelector('.answer-replies-container');
    const replyForm = el.querySelector('.answer-reply-form');
    const replyTextarea = el.querySelector('.answer-reply-textarea');
    const replyCharCount = el.querySelector('.answer-reply-char-count');
    const cancelReplyBtn = el.querySelector('.btn-cancel-reply');
    const submitReplyBtn = el.querySelector('.btn-submit-reply');

    if (replyBtn && replyForm && repliesContainer) {
      replyBtn.addEventListener('click', function () {
        if (!currentUser) {
          openAuthModal();
          showToast('Войдите, чтобы оставить комментарий');
          return;
        }
        repliesContainer.style.display = 'block';
        replyForm.style.display = 'block';
        getOrCreateClientOpId(replyForm);
        if (replyTextarea) {
          replyTextarea.focus();
        }
      });

      if (cancelReplyBtn) {
        cancelReplyBtn.addEventListener('click', function () {
          resetClientOpId(replyForm);
          replyForm.style.display = 'none';
          if (replyTextarea) replyTextarea.value = '';
          if (replyCharCount) replyCharCount.textContent = '0';
          if (replies.length === 0) {
            repliesContainer.style.display = 'none';
          }
        });
      }

      if (replyTextarea && replyCharCount) {
        replyTextarea.addEventListener('input', function () {
          replyCharCount.textContent = replyTextarea.value.length;
          handleFormTextInput(replyForm, replyTextarea.value);
        });
      }

      if (replyForm) {
        replyForm.addEventListener('submit', function (e) {
          e.preventDefault();
          if (!currentUser) {
            openAuthModal();
            showToast('Войдите, чтобы оставить комментарий');
            return;
          }
          const replyContent = replyTextarea ? replyTextarea.value.trim() : '';
          if (!replyContent) {
            showToast('Комментарий не может быть пустым');
            if (replyTextarea) replyTextarea.focus();
            return;
          }
          if (replyContent.length > 5000) {
            showToast('Превышен лимит длины (максимум 5000 символов)');
            return;
          }

          if (submitReplyBtn) submitReplyBtn.disabled = true;
          const clientOpId = getOrCreateClientOpId(replyForm);
          replyForm.dataset.lastSubmittedText = replyContent;

          fetch('/api/articles/' + encodeURIComponent(articleId) + '/comments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              content: replyContent,
              commentType: 'comment',
              parentAnswerId: comment.id,
              clientOperationId: clientOpId
            })
          })
            .then(function (res) {
              if (res.status === 401) {
                if (submitReplyBtn) submitReplyBtn.disabled = false;
                openAuthModal();
                throw new Error('AUTH_REQUIRED');
              }
              return res.json().then(function (data) {
                return { status: res.status, data: data };
              });
            })
            .then(function (result) {
              if (submitReplyBtn) submitReplyBtn.disabled = false;
              const data = result.data;
              if ((result.status === 200 || result.status === 201) && data && data.success) {
                resetClientOpId(replyForm);
                if (replyTextarea) replyTextarea.value = '';
                if (replyCharCount) replyCharCount.textContent = '0';
                replyForm.style.display = 'none';
                showToast('Комментарий опубликован');
                loadComments(articleId);
              } else {
                showToast((data && data.error) || 'Ошибка при отправке комментария');
              }
            })
            .catch(function (err) {
              if (submitReplyBtn) submitReplyBtn.disabled = false;
              if (err.message !== 'AUTH_REQUIRED') {
                console.error('Failed to submit reply:', err);
                showToast('Не удалось отправить комментарий');
              }
            });
        });
      }
    }

    return el;
  }

  function toggleSolution(commentId, targetIsSolution) {
    if (!currentArticle) return;
    const articleId = currentArticle.id;
    const bodyPayload = typeof targetIsSolution === 'boolean'
      ? { isSolution: targetIsSolution }
      : {};
    fetch('/api/articles/' + encodeURIComponent(articleId) + '/comments/' + encodeURIComponent(commentId) + '/solution', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bodyPayload)
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
        if (err.message !== 'FORBIDDEN') {
          console.error('Failed to toggle solution:', err);
        }
      });
  }

  function handleDeepLink() {
    const hash = window.location.hash;
    if (!hash) return;
    if (hash.startsWith('#comm_') || hash.startsWith('#comment-')) {
      let rawTargetId = hash.replace(/^#(comm_|comment-)/, '');
      let item = window._allCommentsMap ? (window._allCommentsMap[rawTargetId] || window._allCommentsMap['comm_' + rawTargetId]) : null;
      if (item) {
        rawTargetId = item.id;
      }
      if (item) {
        // Build ancestor chain from root down to this item
        let path = [];
        let curr = item;
        let visited = new Set();
        while (curr && !visited.has(curr.id)) {
          visited.add(curr.id);
          path.unshift(curr);
          const pId = curr.parentCommentId || curr.parent_comment_id;
          curr = pId ? window._allCommentsMap[pId] : null;
        }

        const maxDepth = getMaxWindowDepth();
        const targetIdx = path.length - 1;
        if (targetIdx >= maxDepth) {
          window._commentDrilldownState = window._commentDrilldownState || { stack: [] };
          window._commentDrilldownState.stack = [];
          for (let d = maxDepth; d <= targetIdx; d += maxDepth) {
            window._commentDrilldownState.stack.push({
              rootCommentId: path[d].id,
              scrollY: window.scrollY
            });
          }
          if (window._commentsResponseData) {
            renderCommentsData(window._commentsResponseData);
          } else if (window._rawCommentsData && currentArticle) {
            renderCommentsList(window._rawCommentsData);
          }
        }

        let parentId = item.parentCommentId || item.parent_comment_id;
        visited = new Set();
        while (parentId && !visited.has(parentId)) {
          visited.add(parentId);
          window._expandedCommentIds.add(parentId);
          const childrenContainer = document.getElementById('thread_' + parentId);
          if (childrenContainer) {
            childrenContainer.style.display = 'flex';
            const btn = document.querySelector('[aria-controls="thread_' + parentId + '"]');
            if (btn) {
              btn.setAttribute('aria-expanded', 'true');
              const iconEl = btn.querySelector('.thread-toggle-icon');
              if (iconEl) iconEl.textContent = '-';
              const txtEl = btn.querySelector('.toggle-thread-text');
              if (txtEl) txtEl.textContent = 'Скрыть комментарии';
            }
          }
          const parentObj = window._allCommentsMap[parentId];
          parentId = parentObj ? (parentObj.parentCommentId || parentObj.parent_comment_id) : null;
        }

        const ansId = item.parentAnswerId || item.parent_answer_id;
        if (ansId) {
          const ansCard = document.getElementById('comm_' + ansId) || document.querySelector('[data-id="' + ansId + '"]');
          if (ansCard) {
            const repliesContainer = ansCard.querySelector('.answer-replies-container');
            if (repliesContainer) {
              repliesContainer.style.display = 'block';
            }
          }
        }
      }

      const targetEl = document.getElementById('comm_' + rawTargetId) ||
        document.getElementById(hash.substring(1)) ||
        document.querySelector('[data-id="' + rawTargetId + '"]');
      if (targetEl) {
        setTimeout(function () {
          targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
          targetEl.classList.add('comment-highlight');
          setTimeout(function () {
            targetEl.classList.remove('comment-highlight');
          }, 2500);
        }, 150);
      }
    }
  }

  function renderCommentsList(comments) {
    const listEl = document.getElementById('commentsList');
    const badgeEl = document.getElementById('commentsCountBadge');
    const emptyEl = document.getElementById('commentsEmpty');

    if (badgeEl) {
      const activeComments = (comments || []).filter(function (c) { return !c.isDeleted; });
      badgeEl.textContent = activeComments.length;
    }

    if (!listEl) return;
    listEl.innerHTML = '';

    if (!comments || comments.length === 0) {
      if (emptyEl) emptyEl.style.display = 'block';
      return;
    }

    if (emptyEl) emptyEl.style.display = 'none';

    window._rawCommentsData = comments;
    const tree = buildCommentTree(comments);

    // Drilldown Window mode
    const stack = (window._commentDrilldownState && window._commentDrilldownState.stack) || [];
    if (stack.length > 0) {
      const currentFrame = stack[stack.length - 1];
      const drilldownRoot = tree.byId[currentFrame.rootCommentId];
      if (drilldownRoot) {
        const drilldownBar = document.createElement('div');
        drilldownBar.className = 'thread-drilldown-bar';
        drilldownBar.innerHTML =
          '<button type="button" class="btn-drilldown-back">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
              '<polyline points="15 18 9 12 15 6"></polyline>' +
            '</svg>' +
            '<span>Назад к обсуждению</span>' +
          '</button>' +
          '<span class="thread-drilldown-title">Ветка комментариев</span>';

        const backBtn = drilldownBar.querySelector('.btn-drilldown-back');
        if (backBtn) {
          backBtn.addEventListener('click', function (e) {
            e.preventDefault();
            const popped = window._commentDrilldownState.stack.pop();
            if (window._commentsResponseData) {
              renderCommentsData(window._commentsResponseData);
            } else {
              renderCommentsList(comments);
            }
            if (popped && typeof popped.scrollY === 'number') {
              window.scrollTo({ top: popped.scrollY, behavior: 'auto' });
            }
          });
        }

        listEl.appendChild(drilldownBar);
        window._expandedCommentIds.add(drilldownRoot.id);
        listEl.appendChild(renderCommentNode(drilldownRoot, 0, {
          articleId: currentArticle ? currentArticle.id : '',
          allCommentsById: window._allCommentsMap || tree.byId,
          isQuestionClarification: false,
          onReload: function (newId) {
            if (currentArticle) {
              loadComments(currentArticle.id);
            }
          }
        }));
        return;
      }
    }

    // Put solution comment first if present
    const sortedRoots = tree.roots.slice().sort(function (a, b) {
      const aSol = Boolean(a.isSolution || a.is_solution);
      const bSol = Boolean(b.isSolution || b.is_solution);
      if (aSol && !bSol) return -1;
      if (!aSol && bSol) return 1;
      return 0;
    });

    sortedRoots.forEach(function (rootNode) {
      listEl.appendChild(renderCommentNode(rootNode, 0, {
        articleId: currentArticle ? currentArticle.id : '',
        allCommentsById: window._allCommentsMap || tree.byId,
        isQuestionClarification: false,
        onReload: function (newId) {
          if (currentArticle) {
            loadComments(currentArticle.id);
            if (newId) {
              setTimeout(function () {
                const target = document.getElementById('comm_' + newId);
                if (target) {
                  target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                  target.classList.add('comment-highlight');
                  setTimeout(function () { target.classList.remove('comment-highlight'); }, 2500);
                }
              }, 300);
            }
          }
        }
      }));
    });
  }

  function renderCommentsData(data) {
    if (!data) return;
    window._commentsResponseData = data;
    window._rawCommentsData = data.comments || [];
    window._allCommentsMap = {};
    (data.comments || []).forEach(function (c) {
      window._allCommentsMap[c.id] = c;
    });

    // Pre-expand ancestors if navigating via deep link
    const hash = window.location.hash;
    if (hash && (hash.startsWith('#comm_') || hash.startsWith('#comment-'))) {
      let rawTargetId = hash.replace(/^#(comm_|comment-)/, '');
      let curr = window._allCommentsMap ? (window._allCommentsMap[rawTargetId] || window._allCommentsMap['comm_' + rawTargetId]) : null;
      let visited = new Set();
      while (curr) {
        const pId = curr.parentCommentId || curr.parent_comment_id;
        if (pId && !visited.has(pId)) {
          visited.add(pId);
          window._expandedCommentIds.add(pId);
          curr = window._allCommentsMap[pId];
        } else {
          break;
        }
      }
    }

    currentMyAnswerId = data.myAnswerId || null;
    updateAuthUI();

    const isQuestion = Boolean(currentArticle && (
      currentArticle.materialType === 'question' ||
      currentArticle.material_type === 'question' ||
      (currentArticle.publication_settings && (
        currentArticle.publication_settings.materialType === 'question' ||
        (typeof currentArticle.publication_settings === 'string' && currentArticle.publication_settings.indexOf('"materialType":"question"') !== -1)
      ))
    ));

    const standardCommentsWrapper = document.getElementById('standardCommentsWrapper');
    const questionCommentsWrapper = document.getElementById('questionCommentsWrapper');

    if (isQuestion) {
      if (standardCommentsWrapper) standardCommentsWrapper.style.display = 'none';
      if (questionCommentsWrapper) questionCommentsWrapper.style.display = 'block';

      // Update badges
      const qBadge = document.getElementById('questionCommentsCountBadge');
      if (qBadge) {
        qBadge.textContent = data.questionCommentsCount !== undefined
          ? data.questionCommentsCount
          : (data.questionComments ? data.questionComments.filter(function (q) { return !q.isDeleted; }).length : 0);
      }
      const aBadge = document.getElementById('answersCountBadge');
      if (aBadge) {
        aBadge.textContent = data.answersCount !== undefined
          ? data.answersCount
          : (data.answers ? data.answers.filter(function (a) { return !a.isDeleted; }).length : 0);
      }

      // Render Question Clarifications
      const qList = document.getElementById('questionCommentsList');
      if (qList) {
        qList.innerHTML = '';
        const qComments = data.questionComments || [];
        const qTree = buildCommentTree(qComments);

        const stack = (window._commentDrilldownState && window._commentDrilldownState.stack) || [];
        let renderedDrilldown = false;
        if (stack.length > 0) {
          const currentFrame = stack[stack.length - 1];
          const drilldownRoot = qTree.byId[currentFrame.rootCommentId];
          if (drilldownRoot) {
            renderedDrilldown = true;
            const drilldownBar = document.createElement('div');
            drilldownBar.className = 'thread-drilldown-bar';
            drilldownBar.innerHTML =
              '<button type="button" class="btn-drilldown-back">' +
                '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                  '<polyline points="15 18 9 12 15 6"></polyline>' +
                '</svg>' +
                '<span>Назад к обсуждению</span>' +
              '</button>' +
              '<span class="thread-drilldown-title">Ветка уточнений</span>';

            const backBtn = drilldownBar.querySelector('.btn-drilldown-back');
            if (backBtn) {
              backBtn.addEventListener('click', function (e) {
                e.preventDefault();
                const popped = window._commentDrilldownState.stack.pop();
                if (window._commentsResponseData) {
                  renderCommentsData(window._commentsResponseData);
                } else if (currentArticle) {
                  loadComments(currentArticle.id);
                }
                if (popped && typeof popped.scrollY === 'number') {
                  window.scrollTo({ top: popped.scrollY, behavior: 'auto' });
                }
              });
            }
            qList.appendChild(drilldownBar);
            window._expandedCommentIds.add(drilldownRoot.id);
            qList.appendChild(renderCommentNode(drilldownRoot, 0, {
              articleId: currentArticle ? currentArticle.id : '',
              allCommentsById: window._allCommentsMap || qTree.byId,
              isQuestionClarification: true,
              onReload: function (newId) {
                if (currentArticle) loadComments(currentArticle.id);
              }
            }));
          }
        }

        if (!renderedDrilldown) {
          qTree.roots.forEach(function (qc) {
            qList.appendChild(renderCommentNode(qc, 0, {
              articleId: currentArticle ? currentArticle.id : '',
              allCommentsById: window._allCommentsMap || qTree.byId,
              isQuestionClarification: true,
              onReload: function (newId) {
                if (currentArticle) loadComments(currentArticle.id);
                if (newId) {
                  setTimeout(function () {
                    const target = document.getElementById('comm_' + newId);
                    if (target) {
                      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                      target.classList.add('comment-highlight');
                      setTimeout(function () { target.classList.remove('comment-highlight'); }, 2500);
                    }
                  }, 300);
                }
              }
            }));
          });
        }
      }

      // Render Answers List
      const answersList = document.getElementById('answersList');
      const answersEmpty = document.getElementById('answersEmpty');
      const rawAnswers = data.answers || [];

      const sortedAnswers = rawAnswers.slice().sort(function (a, b) {
        const aSol = Boolean(a.isSolution || a.is_solution);
        const bSol = Boolean(b.isSolution || b.is_solution);
        if (aSol && !bSol) return -1;
        if (!aSol && bSol) return 1;
        const aTime = new Date(a.createdAt || a.created_at || 0).getTime();
        const bTime = new Date(b.createdAt || b.created_at || 0).getTime();
        return aTime - bTime;
      });

      if (answersEmpty) {
        answersEmpty.style.display = sortedAnswers.length === 0 ? 'block' : 'none';
      }

      if (answersList) {
        answersList.innerHTML = '';
        const targetArtId = currentArticle ? currentArticle.id : '';
        sortedAnswers.forEach(function (ans) {
          answersList.appendChild(renderAnswerCard(ans, targetArtId, data.comments));
        });
      }
    } else {
      if (standardCommentsWrapper) standardCommentsWrapper.style.display = 'block';
      if (questionCommentsWrapper) questionCommentsWrapper.style.display = 'none';

      renderCommentsList(data.comments || []);
    }
  }

  function loadComments(articleId) {
    fetch('/api/articles/' + encodeURIComponent(articleId) + '/comments')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!data || !data.success) {
          console.error('Failed to load comments:', data && data.error);
          return;
        }

        renderCommentsData(data);
        handleDeepLink();
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

    // Question clarification elements
    const addClarificationBtn = document.getElementById('btnAddQuestionClarification');
    const clarificationForm = document.getElementById('questionClarificationForm');
    const clarificationInput = document.getElementById('questionClarificationInput');
    const clarificationCharCount = document.getElementById('clarificationCharCount');
    const cancelClarificationBtn = document.getElementById('btnCancelClarification');
    const submitClarificationBtn = document.getElementById('btnSubmitClarification');

    // Question answer submission elements
    const answerForm = document.getElementById('questionAnswerForm');
    const answerTextInput = document.getElementById('answerTextInput');
    const answerCharCount = document.getElementById('answerCharCount');
    const submitAnswerBtn = document.getElementById('btnSubmitAnswer');

    // My answer banner buttons
    const btnGoToMyAnswer = document.getElementById('btnGoToMyAnswer');
    const btnEditMyAnswer = document.getElementById('btnEditMyAnswer');

    if (!isCommentsInitialized) {
      // 1. Standard comments listeners
      if (form) {
        getOrCreateClientOpId(form);
      }
      if (textarea && charCountEl) {
        textarea.addEventListener('input', function () {
          charCountEl.textContent = textarea.value.length;
          if (form) {
            handleFormTextInput(form, textarea.value);
          }
        });
      }

      if (form) {
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
          const clientOpId = getOrCreateClientOpId(form);
          form.dataset.lastSubmittedText = content;

          fetch('/api/articles/' + encodeURIComponent(articleId) + '/comments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content, commentType: 'comment', clientOperationId: clientOpId })
          })
            .then(function (res) {
              if (res.status === 401) {
                if (submitBtn) submitBtn.disabled = false;
                openAuthModal();
                throw new Error('AUTH_REQUIRED');
              }
              return res.json().then(function (data) {
                return { status: res.status, data: data };
              });
            })
            .then(function (result) {
              if (submitBtn) submitBtn.disabled = false;
              const data = result.data;
              if ((result.status === 200 || result.status === 201) && data && data.success) {
                resetClientOpId(form);
                if (textarea) textarea.value = '';
                if (charCountEl) charCountEl.textContent = '0';
                showToast('Комментарий опубликован');
                loadComments(articleId);
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
      }

      // 2. Question clarification listeners
      if (addClarificationBtn && clarificationForm) {
        addClarificationBtn.addEventListener('click', function () {
          if (!currentUser) {
            openAuthModal();
            showToast('Войдите, чтобы оставить уточнение');
            return;
          }
          const isOpening = clarificationForm.style.display === 'none' || !clarificationForm.style.display;
          clarificationForm.style.display = isOpening ? 'block' : 'none';
          if (isOpening) {
            getOrCreateClientOpId(clarificationForm);
            if (clarificationInput) {
              clarificationInput.focus();
            }
          }
        });
      }

      if (cancelClarificationBtn && clarificationForm) {
        cancelClarificationBtn.addEventListener('click', function () {
          resetClientOpId(clarificationForm);
          clarificationForm.style.display = 'none';
          if (clarificationInput) clarificationInput.value = '';
          if (clarificationCharCount) clarificationCharCount.textContent = '0';
        });
      }

      if (clarificationInput && clarificationCharCount) {
        clarificationInput.addEventListener('input', function () {
          clarificationCharCount.textContent = clarificationInput.value.length;
          if (clarificationForm) {
            handleFormTextInput(clarificationForm, clarificationInput.value);
          }
        });
      }

      if (clarificationForm) {
        clarificationForm.addEventListener('submit', function (e) {
          e.preventDefault();

          if (!currentUser) {
            openAuthModal();
            showToast('Войдите, чтобы оставить уточнение');
            return;
          }

          const content = clarificationInput ? clarificationInput.value.trim() : '';
          if (!content) {
            showToast('Уточнение не может быть пустым');
            if (clarificationInput) clarificationInput.focus();
            return;
          }

          if (content.length > 5000) {
            showToast('Превышен лимит длины (максимум 5000 символов)');
            return;
          }

          if (submitClarificationBtn) submitClarificationBtn.disabled = true;
          const clientOpId = getOrCreateClientOpId(clarificationForm);
          clarificationForm.dataset.lastSubmittedText = content;

          fetch('/api/articles/' + encodeURIComponent(articleId) + '/comments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content, commentType: 'comment', clientOperationId: clientOpId })
          })
            .then(function (res) {
              if (res.status === 401) {
                if (submitClarificationBtn) submitClarificationBtn.disabled = false;
                openAuthModal();
                throw new Error('AUTH_REQUIRED');
              }
              return res.json().then(function (data) {
                return { status: res.status, data: data };
              });
            })
            .then(function (result) {
              if (submitClarificationBtn) submitClarificationBtn.disabled = false;
              const data = result.data;
              if ((result.status === 200 || result.status === 201) && data && data.success) {
                resetClientOpId(clarificationForm);
                if (clarificationInput) clarificationInput.value = '';
                if (clarificationCharCount) clarificationCharCount.textContent = '0';
                clarificationForm.style.display = 'none';
                showToast('Уточнение опубликовано');
                loadComments(articleId);
              } else {
                showToast((data && data.error) || 'Ошибка при отправке уточнения');
              }
            })
            .catch(function (err) {
              if (submitClarificationBtn) submitClarificationBtn.disabled = false;
              if (err.message !== 'AUTH_REQUIRED') {
                console.error('Failed to submit clarification:', err);
                showToast('Не удалось отправить уточнение');
              }
            });
        });
      }

      // 3. Question answer submission listeners
      if (answerForm) {
        getOrCreateClientOpId(answerForm);
      }
      if (answerTextInput && answerCharCount) {
        answerTextInput.addEventListener('input', function () {
          answerCharCount.textContent = answerTextInput.value.length;
          if (answerForm) {
            handleFormTextInput(answerForm, answerTextInput.value);
          }
        });
      }

      if (answerForm) {
        answerForm.addEventListener('submit', function (e) {
          e.preventDefault();

          if (!currentUser) {
            openAuthModal();
            showToast('Войдите, чтобы ответить на вопрос');
            return;
          }

          const content = answerTextInput ? answerTextInput.value.trim() : '';
          if (!content) {
            showToast('Ответ не может быть пустым');
            if (answerTextInput) answerTextInput.focus();
            return;
          }

          if (content.length > 5000) {
            showToast('Превышен лимит длины (максимум 5000 символов)');
            return;
          }

          if (submitAnswerBtn) submitAnswerBtn.disabled = true;
          const clientOpId = getOrCreateClientOpId(answerForm);
          answerForm.dataset.lastSubmittedText = content;

          fetch('/api/articles/' + encodeURIComponent(articleId) + '/comments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              content: content,
              commentType: 'answer',
              clientOperationId: clientOpId
            })
          })
            .then(function (res) {
              if (res.status === 401) {
                if (submitAnswerBtn) submitAnswerBtn.disabled = false;
                openAuthModal();
                throw new Error('AUTH_REQUIRED');
              }
              return res.json().then(function (data) {
                return { status: res.status, data: data };
              });
            })
            .then(function (result) {
              if (submitAnswerBtn) submitAnswerBtn.disabled = false;
              const data = result.data;
              if (result.status === 409 || (data && data.code === 'ANSWER_ALREADY_EXISTS')) {
                // Do NOT erase typed text in answerTextInput!
                showToast((data && data.error) || 'Вы уже опубликовали ответ на этот вопрос');
                if (data && data.myAnswerId) {
                  currentMyAnswerId = data.myAnswerId;
                  updateAuthUI();
                }
                return;
              }

              if ((result.status === 200 || result.status === 201) && data && data.success) {
                resetClientOpId(answerForm);
                if (answerTextInput) answerTextInput.value = '';
                if (answerCharCount) answerCharCount.textContent = '0';
                if (data.comment && data.comment.id) {
                  currentMyAnswerId = data.comment.id;
                }
                showToast('Ответ опубликован');
                loadComments(articleId);
              } else {
                showToast((data && data.error) || 'Ошибка при отправке ответа');
              }
            })
            .catch(function (err) {
              if (submitAnswerBtn) submitAnswerBtn.disabled = false;
              if (err.message !== 'AUTH_REQUIRED') {
                console.error('Failed to submit answer:', err);
                showToast('Не удалось отправить ответ');
              }
            });
        });
      }

      // 4. My answer banner buttons
      if (btnGoToMyAnswer) {
        btnGoToMyAnswer.addEventListener('click', function () {
          if (!currentMyAnswerId) return;
          const targetEl = document.getElementById('comm_' + currentMyAnswerId) ||
            document.querySelector('[data-id="' + currentMyAnswerId + '"]');
          if (targetEl) {
            targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            targetEl.classList.add('comment-highlight');
            setTimeout(function () {
              targetEl.classList.remove('comment-highlight');
            }, 2500);
          }
        });
      }

      if (btnEditMyAnswer) {
        btnEditMyAnswer.addEventListener('click', function () {
          if (!currentMyAnswerId) return;
          const targetEl = document.getElementById('comm_' + currentMyAnswerId) ||
            document.querySelector('[data-id="' + currentMyAnswerId + '"]');
          if (targetEl) {
            targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            const editBtn = targetEl.querySelector('.btn-edit-answer');
            if (editBtn) {
              editBtn.click();
            }
          }
        });
      }

      window.addEventListener('hashchange', handleDeepLink);

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
    document.title = (article.title || 'Публикация') + ' - SmartContractum';

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
      const sanitized = sanitizeArticleHtml(article.html || '');
      bodyEl.innerHTML = sanitized || '<p>Текст статьи пуст.</p>';
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

    // Sync Article Vote Capsules (Top and Bottom)
    syncArticleVoteCapsules(article);

    // Customize Comments / Answers section for Questions
    const isQuestion = Boolean(
      article.materialType === 'question' ||
      article.material_type === 'question' ||
      (article.publication_settings && (
        article.publication_settings.materialType === 'question' ||
        (typeof article.publication_settings === 'string' && article.publication_settings.indexOf('"materialType":"question"') !== -1)
      ))
    );
    const standardCommentsWrapper = document.getElementById('standardCommentsWrapper');
    const questionCommentsWrapper = document.getElementById('questionCommentsWrapper');

    if (standardCommentsWrapper && questionCommentsWrapper) {
      if (isQuestion) {
        standardCommentsWrapper.style.display = 'none';
        questionCommentsWrapper.style.display = 'block';
      } else {
        standardCommentsWrapper.style.display = 'block';
        questionCommentsWrapper.style.display = 'none';
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

    // Scroll to #comments or #comment-form if specified in URL hash
    const hash = window.location.hash;
    if (hash === '#comments' || hash === '#comment-form' || hash === '#commentForm') {
      setTimeout(function () {
        const formEl = document.getElementById('commentForm');
        const guestPromptEl = document.getElementById('commentGuestPrompt');
        if (hash === '#comment-form' || hash === '#commentForm') {
          if (currentUser && formEl && formEl.style.display !== 'none') {
            formEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            const ta = document.getElementById('commentTextInput');
            if (ta) ta.focus();
          } else if (!currentUser && guestPromptEl) {
            guestPromptEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            openAuthModal();
          } else {
            const c = document.getElementById('comments');
            if (c) c.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        } else {
          const c = document.getElementById('comments');
          if (c) c.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
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
