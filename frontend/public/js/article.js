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
      if (!currentUser) {
        localStorage.setItem('sc_bookmarks', JSON.stringify(bookmarks));
      }
    } catch (e) {}
  }

  function isBookmarked(id) {
    if (!id) return false;
    if (currentUser && currentArticle && (currentArticle.id === id || currentArticle.draftId === id)) {
      if (currentArticle.hasSaved !== undefined || currentArticle.isSaved !== undefined) {
        return Boolean(currentArticle.hasSaved || currentArticle.isSaved);
      }
    }
    const bookmarks = getBookmarks();
    return bookmarks.indexOf(id) !== -1;
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

  function syncLocalBookmarksWithServer() {
    runLegacyBookmarksMigration();
  }

  function toggleBookmark(id) {
    if (!id) return false;
    if (!currentUser) {
      showToast('Для сохранения публикации необходимо войти');
      if (typeof openAuthModal === 'function') {
        openAuthModal();
      }
      return false;
    }

    const wasBookmarked = isBookmarked(id);
    const nextBookmarked = !wasBookmarked;

    const prevCount = (currentArticle && typeof currentArticle.savesCount === 'number')
      ? currentArticle.savesCount
      : ((currentArticle && typeof currentArticle.saves_count === 'number') ? currentArticle.saves_count : 0);
    const nextCount = nextBookmarked ? (prevCount + 1) : Math.max(0, prevCount - 1);

    // Optimistic update of currentArticle
    if (currentArticle && (currentArticle.id === id || currentArticle.draftId === id)) {
      currentArticle.savesCount = nextCount;
      currentArticle.saves_count = nextCount;
      currentArticle.hasSaved = nextBookmarked;
      currentArticle.isSaved = nextBookmarked;
    }
    syncBookmarkButtons(id);

    // Optimistic local cache update
    const bms = getBookmarks();
    const idx = bms.indexOf(id);
    if (nextBookmarked && idx === -1) { bms.push(id); saveBookmarks(bms); }
    else if (!nextBookmarked && idx !== -1) { bms.splice(idx, 1); saveBookmarks(bms); }

    fetch('/api/articles/' + encodeURIComponent(id) + (nextBookmarked ? '/save' : '/unsave'), {
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
        if (currentArticle && (currentArticle.id === id || currentArticle.draftId === id)) {
          currentArticle.savesCount = typeof data.savesCount === 'number' ? data.savesCount : nextCount;
          currentArticle.saves_count = currentArticle.savesCount;
          currentArticle.hasSaved = Boolean(data.hasSaved);
          currentArticle.isSaved = Boolean(data.hasSaved);
        }
        syncBookmarkButtons(id);
        if (data.isSaved) {
          showToast('Публикация сохранена');
        } else {
          showToast('Публикация удалена из сохраненного');
        }
      } else {
        // Rollback
        if (currentArticle && (currentArticle.id === id || currentArticle.draftId === id)) {
          currentArticle.savesCount = prevCount;
          currentArticle.saves_count = prevCount;
          currentArticle.hasSaved = wasBookmarked;
          currentArticle.isSaved = wasBookmarked;
        }
        syncBookmarkButtons(id);
        const rbBms = getBookmarks();
        const rbIdx = rbBms.indexOf(id);
        if (wasBookmarked && rbIdx === -1) { rbBms.push(id); saveBookmarks(rbBms); }
        else if (!wasBookmarked && rbIdx !== -1) { rbBms.splice(rbIdx, 1); saveBookmarks(rbBms); }
        showToast((data && data.error) || 'Ошибка сохранения публикации');
      }
    })
    .catch(function (err) {
      // Rollback on network or HTTP error
      if (currentArticle && (currentArticle.id === id || currentArticle.draftId === id)) {
        currentArticle.savesCount = prevCount;
        currentArticle.saves_count = prevCount;
        currentArticle.hasSaved = wasBookmarked;
        currentArticle.isSaved = wasBookmarked;
      }
      syncBookmarkButtons(id);
      const rbBms = getBookmarks();
      const rbIdx = rbBms.indexOf(id);
      if (wasBookmarked && rbIdx === -1) { rbBms.push(id); saveBookmarks(rbBms); }
      else if (!wasBookmarked && rbIdx !== -1) { rbBms.splice(rbIdx, 1); saveBookmarks(rbBms); }
      if (err && String(err.message).indexOf('401') !== -1) {
        showToast('Для сохранения публикации необходимо войти');
        if (typeof openAuthModal === 'function') openAuthModal();
      } else {
        showToast('Не удалось связаться с сервером');
      }
    });

    return nextBookmarked;
  }

  function syncBookmarkButtons(id) {
    const bookmarked = isBookmarked(id);
    const btns = [
      document.getElementById('btnArticleBookmark'),
      document.getElementById('btnArticleBookmarkBottom'),
      document.getElementById('railBtnBookmark'),
      document.getElementById('mobileBtnBookmark')
    ];

    btns.forEach(function (btn) {
      if (!btn) return;
      btn.classList.toggle('is-bookmarked', bookmarked);
      btn.classList.toggle('is-saved', bookmarked);
      btn.setAttribute('aria-pressed', bookmarked ? 'true' : 'false');
      const label = btn.querySelector('.bookmark-text');
      if (label) {
        label.textContent = bookmarked ? 'Сохранено' : 'Сохранить';
      }
      btn.title = bookmarked ? 'Сохранено' : 'Сохранить';
      btn.setAttribute('aria-label', bookmarked ? 'Удалить из сохраненного' : 'Сохранить публикацию');
    });

    const count = (currentArticle && typeof currentArticle.savesCount === 'number')
      ? currentArticle.savesCount
      : ((currentArticle && typeof currentArticle.saves_count === 'number') ? currentArticle.saves_count : 0);
    const railCount = document.getElementById('railBookmarkCount');
    if (railCount) railCount.textContent = count;
    const mobileCount = document.getElementById('mobileBookmarkCount');
    if (mobileCount) mobileCount.textContent = count;
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
  // 2.1 Comment Bookmarks, Subscriptions, Share & Report
  // --------------------------------------------------------------------------
  function getCommentBookmarks() {
    const user = (typeof window !== 'undefined' && window.SCAuth && window.SCAuth.currentUser) ? window.SCAuth.currentUser : ((typeof window !== 'undefined' && window.currentUser) ? window.currentUser : null);
    const bKey = (user && user.id) ? ('sc_comment_bookmarks_' + user.id) : 'sc_comment_bookmarks_guest';
    try {
      const data = localStorage.getItem(bKey);
      if (data) return JSON.parse(data) || [];
    } catch (e) {}
    return [];
  }

  function isCommentBookmarked(commentId, commentObj) {
    if (!commentId) return false;
    if (commentObj && (commentObj.isSaved !== undefined || commentObj.hasSaved !== undefined)) {
      return Boolean(commentObj.isSaved || commentObj.hasSaved);
    }
    const list = getCommentBookmarks();
    return list.indexOf(commentId) !== -1;
  }

  function toggleCommentBookmark(commentId, btn) {
    if (!commentId) return false;
    if (btn && btn.dataset.pending === 'true') return false;
    if (btn) btn.dataset.pending = 'true';
    const user = (typeof window !== 'undefined' && window.SCAuth && window.SCAuth.currentUser) ? window.SCAuth.currentUser : ((typeof window !== 'undefined' && window.currentUser) ? window.currentUser : null);
    const bKey = (user && user.id) ? ('sc_comment_bookmarks_' + user.id) : 'sc_comment_bookmarks_guest';
    const list = getCommentBookmarks();
    const idx = list.indexOf(commentId);
    let bookmarked = false;
    if (idx !== -1) {
      list.splice(idx, 1);
      bookmarked = false;
      showToast('Комментарий удален из закладок');
    } else {
      list.push(commentId);
      bookmarked = true;
      showToast('Комментарий сохранен в закладки');
    }
    try {
      localStorage.setItem(bKey, JSON.stringify(list));
    } catch (e) {}

    if (currentUser) {
      fetch('/api/comments/' + encodeURIComponent(commentId) + '/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ isSaved: bookmarked })
      }).then(res => res.json()).then(data => {
        if (btn) btn.dataset.pending = 'false';
      }).catch(err => {
        if (btn) btn.dataset.pending = 'false';
      });
    } else {
      if (btn) btn.dataset.pending = 'false';
    }
    return bookmarked;
  }

  function getCommentSubscriptions() {
    const user = (typeof window !== 'undefined' && window.SCAuth && window.SCAuth.currentUser) ? window.SCAuth.currentUser : ((typeof window !== 'undefined' && window.currentUser) ? window.currentUser : null);
    const sKey = (user && user.id) ? ('sc_comment_subscriptions_' + user.id) : 'sc_comment_subscriptions_guest';
    try {
      const data = localStorage.getItem(sKey);
      if (data) return JSON.parse(data) || [];
    } catch (e) {}
    return [];
  }

  function isCommentSubscribed(commentId) {
    if (!commentId) return false;
    const list = getCommentSubscriptions();
    return list.indexOf(commentId) !== -1;
  }

  function updateCommentSubscriptionLocal(commentId, subscribed) {
    if (!commentId) return;
    const list = getCommentSubscriptions();
    const idx = list.indexOf(commentId);
    if (subscribed && idx === -1) {
      list.push(commentId);
    } else if (!subscribed && idx !== -1) {
      list.splice(idx, 1);
    }
    try {
      localStorage.setItem('sc_comment_subscriptions', JSON.stringify(list));
    } catch (e) {}
  }

  function loadUserCommentSubscriptions() {
    if (!currentUser) return;
    fetch('/api/comments/subscriptions')
      .then(function (res) {
        if (!res.ok) return null;
        return res.json();
      })
      .then(function (data) {
        if (data && data.success && Array.isArray(data.subscriptions)) {
          try {
            localStorage.setItem('sc_comment_subscriptions', JSON.stringify(data.subscriptions));
          } catch (e) {}
          data.subscriptions.forEach(function (cId) {
            const btns = document.querySelectorAll(
              '.btn-subscribe-comment[data-comment-id="' + cId + '"], ' +
              '.btn-subscribe-answer[data-comment-id="' + cId + '"]'
            );
            btns.forEach(function (b) {
              b.classList.add('is-subscribed');
              b.setAttribute('title', 'Отписаться от ответов');
              b.setAttribute('aria-label', 'Отписаться от ответов');
              const svg = b.querySelector('svg');
              if (svg) svg.setAttribute('fill', 'currentColor');
            });
          });
        }
      })
      .catch(function () {});
  }

  function generateCommentPermalink(articleId, commentId) {
    const origin = window.location.origin || '';
    const pathname = window.location.pathname || '';
    const targetArtId = articleId || (currentArticle ? currentArticle.id : '');
    return origin + pathname + '?id=' + encodeURIComponent(targetArtId) + '#comm_' + encodeURIComponent(commentId);
  }

  function copyCommentLink(articleId, commentId) {
    const url = generateCommentPermalink(articleId, commentId);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url)
        .then(function () {
          showToast('Ссылка скопирована');
        })
        .catch(function () {
          fallbackCopyCommentLink(url);
        });
    } else {
      fallbackCopyCommentLink(url);
    }
  }

  function fallbackCopyCommentLink(text) {
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

  let activeSharePopoverCommentId = null;
  let activeSharePopoverTrigger = null;

  function isCommentSharePopoverOpen() {
    const popover = document.getElementById('commentSharePopover');
    return !!(popover && popover.style.display !== 'none');
  }

  function closeCommentSharePopover() {
    const popover = document.getElementById('commentSharePopover');
    if (popover) {
      popover.style.display = 'none';
    }
    if (activeSharePopoverTrigger) {
      activeSharePopoverTrigger.setAttribute('aria-expanded', 'false');
      activeSharePopoverTrigger = null;
    }
    activeSharePopoverCommentId = null;
  }

  function openCommentSharePopover(triggerBtn, articleId, commentId) {
    const popover = document.getElementById('commentSharePopover');
    if (!popover || !triggerBtn) return;

    if (activeSharePopoverCommentId === commentId && isCommentSharePopoverOpen()) {
      closeCommentSharePopover();
      return;
    }

    if (activeSharePopoverTrigger && activeSharePopoverTrigger !== triggerBtn) {
      activeSharePopoverTrigger.setAttribute('aria-expanded', 'false');
    }

    activeSharePopoverCommentId = commentId;
    activeSharePopoverTrigger = triggerBtn;
    triggerBtn.setAttribute('aria-haspopup', 'true');
    triggerBtn.setAttribute('aria-expanded', 'true');

    const permalink = generateCommentPermalink(articleId, commentId);
    const title = (currentArticle && currentArticle.title) ? currentArticle.title : document.title || 'SmartContractum';
    const encodedUrl = encodeURIComponent(permalink);
    const encodedText = encodeURIComponent(title);

    const tgLink = popover.querySelector('[data-action="telegram"]');
    if (tgLink) {
      tgLink.href = 'https:' + '//t.me/share/url?url=' + encodedUrl + '&text=' + encodedText;
    }
    const vkLink = popover.querySelector('[data-action="vk"]');
    if (vkLink) {
      vkLink.href = 'https:' + '//vk.com/share.php?url=' + encodedUrl + '&title=' + encodedText;
    }
    const okLink = popover.querySelector('[data-action="ok"]');
    if (okLink) {
      okLink.href = 'https:' + '//connect.ok.ru/offer?url=' + encodedUrl + '&title=' + encodedText;
    }

    const copyBtn = popover.querySelector('[data-action="copy"]');
    if (copyBtn) {
      copyBtn.onclick = function (e) {
        e.preventDefault();
        copyCommentLink(articleId, commentId);
        closeCommentSharePopover();
      };
    }

    const socialLinks = popover.querySelectorAll('a.comment-share-item');
    socialLinks.forEach(function (link) {
      link.onclick = function () {
        setTimeout(closeCommentSharePopover, 100);
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

  // --------------------------------------------------------------------------
  // Article Share Popover
  // --------------------------------------------------------------------------
  let activeArticleShareTrigger = null;

  function isArticleSharePopoverOpen() {
    const popover = document.getElementById('articleSharePopover');
    return !!(popover && popover.style.display !== 'none');
  }

  function closeArticleSharePopover() {
    const popover = document.getElementById('articleSharePopover');
    if (popover) {
      popover.style.display = 'none';
      const copyLabel = popover.querySelector('.share-copy-label');
      if (copyLabel) {
        copyLabel.textContent = 'Скопировать ссылку';
      }
    }
    if (activeArticleShareTrigger) {
      activeArticleShareTrigger.setAttribute('aria-expanded', 'false');
      activeArticleShareTrigger = null;
    }
  }

  function getArticleShareUrl() {
    return window.location.href;
  }

  function getArticleShareTitle() {
    return (currentArticle && currentArticle.title) ? currentArticle.title : (document.title || 'SmartContractum');
  }

  function openArticleSharePopover(triggerBtn) {
    const popover = document.getElementById('articleSharePopover');
    if (!popover || !triggerBtn) return;

    if (activeArticleShareTrigger === triggerBtn && isArticleSharePopoverOpen()) {
      closeArticleSharePopover();
      return;
    }

    if (isCommentSharePopoverOpen()) {
      closeCommentSharePopover();
    }

    if (activeArticleShareTrigger && activeArticleShareTrigger !== triggerBtn) {
      activeArticleShareTrigger.setAttribute('aria-expanded', 'false');
    }

    activeArticleShareTrigger = triggerBtn;
    triggerBtn.setAttribute('aria-haspopup', 'true');
    triggerBtn.setAttribute('aria-expanded', 'true');

    const permalink = getArticleShareUrl();
    const title = getArticleShareTitle();
    const encodedUrl = encodeURIComponent(permalink);
    const encodedText = encodeURIComponent(title);

    const tgLink = popover.querySelector('[data-action="telegram"]');
    if (tgLink) {
      tgLink.href = 'https:' + '//t.me/share/url?url=' + encodedUrl + '&text=' + encodedText;
    }
    const vkLink = popover.querySelector('[data-action="vk"]');
    if (vkLink) {
      vkLink.href = 'https:' + '//vk.com/share.php?url=' + encodedUrl + '&title=' + encodedText;
    }
    const okLink = popover.querySelector('[data-action="ok"]');
    if (okLink) {
      okLink.href = 'https:' + '//connect.ok.ru/offer?url=' + encodedUrl + '&title=' + encodedText;
    }

    const copyBtn = popover.querySelector('[data-action="copy"]');
    if (copyBtn) {
      const copyLabel = copyBtn.querySelector('.share-copy-label') || copyBtn.querySelector('span');
      if (copyLabel) {
        copyLabel.textContent = 'Скопировать ссылку';
      }
      copyBtn.onclick = function (e) {
        e.preventDefault();
        copyArticleLink();
        if (copyLabel) {
          copyLabel.textContent = 'Ссылка скопирована';
        }
        setTimeout(function () {
          closeArticleSharePopover();
        }, 600);
      };
    }

    const socialLinks = popover.querySelectorAll('a.article-share-item, a.comment-share-item');
    socialLinks.forEach(function (link) {
      link.onclick = function () {
        setTimeout(closeArticleSharePopover, 100);
      };
    });

    const rect = triggerBtn.getBoundingClientRect();
    const scrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
    const scrollX = window.pageXOffset || document.documentElement.scrollLeft || 0;
    const popoverWidth = 190;
    const popoverHeight = 180;

    let top = rect.bottom + scrollY + 4;
    let left = rect.left + scrollX;

    const isRail = triggerBtn.id === 'railBtnShare' || triggerBtn.classList.contains('btn-rail-share');
    const isMobile = triggerBtn.id === 'mobileBtnShare' || triggerBtn.classList.contains('btn-mobile-share');

    if (isRail) {
      left = rect.right + scrollX + 8;
      top = rect.top + scrollY - 10;
    } else if (isMobile || (rect.bottom + popoverHeight > window.innerHeight && rect.top > popoverHeight)) {
      top = Math.max(10, rect.top + scrollY - popoverHeight - 4);
    }

    if (left + popoverWidth > window.innerWidth - 10) {
      left = Math.max(10, window.innerWidth - popoverWidth - 10);
    }

    popover.style.top = top + 'px';
    popover.style.left = left + 'px';
    popover.style.display = 'flex';

    const firstItem = popover.querySelector('.article-share-item, .comment-share-item');
    if (firstItem && document.activeElement === triggerBtn) {
      firstItem.focus();
    }
  }

  document.addEventListener('click', function (e) {
    if (!isCommentSharePopoverOpen()) return;
    const popover = document.getElementById('commentSharePopover');
    if (popover && popover.contains(e.target)) return;
    if (e.target.closest('.btn-share-comment, .btn-share-answer')) return;
    closeCommentSharePopover();
  });

  document.addEventListener('click', function (e) {
    if (!isArticleSharePopoverOpen()) return;
    const popover = document.getElementById('articleSharePopover');
    if (popover && popover.contains(e.target)) return;
    if (e.target.closest('#railBtnShare, #btnCopyLink, #mobileBtnShare, .btn-action-share, .btn-rail-share, .btn-mobile-share')) return;
    closeArticleSharePopover();
  });

  document.addEventListener('keydown', function (e) {
    if (!isCommentSharePopoverOpen()) return;
    const popover = document.getElementById('commentSharePopover');
    if (!popover) return;

    if (e.key === 'Escape') {
      closeCommentSharePopover();
      if (activeSharePopoverTrigger) {
        activeSharePopoverTrigger.focus();
      }
      return;
    }

    const items = Array.from(popover.querySelectorAll('.comment-share-item'));
    if (!items.length) return;
    const activeIdx = items.indexOf(document.activeElement);

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const nextIdx = activeIdx < 0 ? 0 : (activeIdx + 1) % items.length;
      items[nextIdx].focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prevIdx = activeIdx < 0 ? items.length - 1 : (activeIdx - 1 + items.length) % items.length;
      items[prevIdx].focus();
    } else if (e.key === 'Home') {
      e.preventDefault();
      items[0].focus();
    } else if (e.key === 'End') {
      e.preventDefault();
      items[items.length - 1].focus();
    }
  });

  document.addEventListener('keydown', function (e) {
    if (!isArticleSharePopoverOpen()) return;
    const popover = document.getElementById('articleSharePopover');
    if (!popover) return;

    if (e.key === 'Escape') {
      const trigger = activeArticleShareTrigger;
      closeArticleSharePopover();
      if (trigger) {
        trigger.focus();
      }
      return;
    }

    const items = Array.from(popover.querySelectorAll('.article-share-item, .comment-share-item'));
    if (!items.length) return;
    const activeIdx = items.indexOf(document.activeElement);

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const nextIdx = activeIdx < 0 ? 0 : (activeIdx + 1) % items.length;
      items[nextIdx].focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prevIdx = activeIdx < 0 ? items.length - 1 : (activeIdx - 1 + items.length) % items.length;
      items[prevIdx].focus();
    } else if (e.key === 'Home') {
      e.preventDefault();
      items[0].focus();
    } else if (e.key === 'End') {
      e.preventDefault();
      items[items.length - 1].focus();
    }
  });

  function handleSubscribeComment(btn, commentId) {
    if (!currentUser) {
      openAuthModal();
      showToast('Войдите, чтобы подписаться на ответы');
      return;
    }
    if (btn && btn.dataset.pending === 'true') return;
    if (btn) btn.dataset.pending = 'true';
    fetch('/api/comments/' + encodeURIComponent(commentId) + '/subscribe', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { status: res.status, data: data };
        });
      })
      .then(function (result) {
        if (btn) btn.dataset.pending = 'false';
        if (result.status === 200 && result.data && result.data.success) {
          const isSubscribed = Boolean(result.data.subscribed);
          btn.classList.toggle('is-subscribed', isSubscribed);
          const newTitle = isSubscribed ? 'Отписаться от ответов' : 'Подписаться на ответы';
          btn.setAttribute('title', newTitle);
          btn.setAttribute('aria-label', newTitle);
          const svgEl = btn.querySelector('svg');
          if (svgEl) {
            svgEl.setAttribute('fill', isSubscribed ? 'currentColor' : 'none');
          }
          updateCommentSubscriptionLocal(commentId, isSubscribed);
          showToast(isSubscribed ? 'Подписка на ответы оформлена' : 'Подписка на ответы отменена');
        } else if (result.status === 401) {
          openAuthModal();
          showToast('Войдите, чтобы подписаться на ответы');
        } else {
          showToast((result.data && result.data.error) || 'Не удалось обновить подписку');
        }
      })
      .catch(function () {
        if (btn) btn.dataset.pending = 'false';
        showToast('Ошибка сети при обновлении подписки');
      });
  }

  function markCommentAsReported(commentId) {
    if (!commentId) return;
    window._reportedCommentIds = window._reportedCommentIds || new Set();
    window._reportedCommentIds.add(commentId);
    if (currentUser) {
      try {
        const userKey = 'sc_comment_reports_' + currentUser.id;
        const stored = JSON.parse(localStorage.getItem(userKey) || '[]');
        if (!stored.includes(commentId)) {
          stored.push(commentId);
          localStorage.setItem(userKey, JSON.stringify(stored));
        }
      } catch (e) {}
    }
    const btns = document.querySelectorAll(
      '.btn-report-comment[data-comment-id="' + commentId + '"], ' +
      '.btn-report-answer[data-comment-id="' + commentId + '"]'
    );
    btns.forEach(function (btn) {
      btn.classList.add('is-reported');
      btn.setAttribute('title', 'Жалоба уже отправлена');
      if (btn) btn.dataset.pending = 'false';
      const svg = btn.querySelector('svg');
      if (svg) {
        svg.setAttribute('fill', 'currentColor');
      }
    });
  }

  function isCommentReported(commentId, commentObj) {
    if (!commentId) return false;
    if (!currentUser) return false;
    if (commentObj && (commentObj.hasReported !== undefined || commentObj.isReported !== undefined)) {
      return Boolean(commentObj.hasReported || commentObj.isReported);
    }
    if (window._reportedCommentIds && window._reportedCommentIds.has(commentId)) return true;
    try {
      const userKey = 'sc_comment_reports_' + currentUser.id;
      const stored = JSON.parse(localStorage.getItem(userKey) || '[]');
      if (stored.includes(commentId)) {
        window._reportedCommentIds = window._reportedCommentIds || new Set();
        window._reportedCommentIds.add(commentId);
        return true;
      }
    } catch (e) {}
    return false;
  }

  function getOrInitCommentReportModal() {
    let modal = document.getElementById('commentReportModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'commentReportModal';
      modal.className = 'feed-modal-overlay';
      modal.style.display = 'none';
      modal.setAttribute('role', 'dialog');
      modal.setAttribute('aria-modal', 'true');
      modal.setAttribute('aria-labelledby', 'commentReportModalTitle');
      modal.innerHTML =
        '<div class="feed-modal-card comment-report-modal-card">' +
          '<div class="feed-modal-header">' +
            '<div class="feed-modal-title-wrap">' +
              '<h2 id="commentReportModalTitle" class="feed-modal-title">Пожаловаться на комментарий</h2>' +
              '<span class="feed-modal-subtitle">Выберите причину жалобы</span>' +
            '</div>' +
            '<button type="button" class="feed-modal-close-btn" id="btnCloseCommentReportModal" title="Закрыть" aria-label="Закрыть">' +
              '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                '<line x1="18" y1="6" x2="6" y2="18"></line>' +
                '<line x1="6" y1="6" x2="18" y2="18"></line>' +
              '</svg>' +
            '</button>' +
          '</div>' +
          '<form id="commentReportForm" class="comment-report-form">' +
            '<input type="hidden" id="reportCommentId" name="commentId" value="">' +
            '<div class="comment-report-reasons">' +
              '<label class="comment-report-radio">' +
                '<input type="radio" name="reportReason" value="spam" checked>' +
                '<span>Спам</span>' +
              '</label>' +
              '<label class="comment-report-radio">' +
                '<input type="radio" name="reportReason" value="insult">' +
                '<span>Оскорбление</span>' +
              '</label>' +
              '<label class="comment-report-radio">' +
                '<input type="radio" name="reportReason" value="malicious">' +
                '<span>Вредоносный код или приватные ключи</span>' +
              '</label>' +
              '<label class="comment-report-radio">' +
                '<input type="radio" name="reportReason" value="other">' +
                '<span>Другое</span>' +
              '</label>' +
            '</div>' +
            '<div class="comment-report-details-wrap">' +
              '<label for="reportDetails" class="comment-report-label">Дополнительные сведения (необязательно)</label>' +
              '<textarea id="reportDetails" name="details" class="comment-textarea comment-report-textarea" rows="3" maxlength="1000" placeholder="Опишите подробнее проблему..."></textarea>' +
            '</div>' +
            '<div class="comment-report-actions">' +
              '<button type="button" class="btn btn-secondary btn-sm" id="btnCancelCommentReport">Отмена</button>' +
              '<button type="submit" class="btn btn-primary btn-sm" id="btnSubmitCommentReport">Отправить жалобу</button>' +
            '</div>' +
          '</form>' +
        '</div>';
      document.body.appendChild(modal);
    }

    if (!modal._eventsBound) {
      modal._eventsBound = true;

      function closeModal() {
        modal.style.display = 'none';
        modal._activeReportBtn = null;
      }

      const closeBtn = modal.querySelector('#btnCloseCommentReportModal');
      if (closeBtn) closeBtn.addEventListener('click', closeModal);

      const cancelBtn = modal.querySelector('#btnCancelCommentReport');
      if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

      modal.addEventListener('click', function (e) {
        if (e.target === modal) closeModal();
      });

      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal.style.display === 'flex') {
          closeModal();
        }
      });

      const form = modal.querySelector('#commentReportForm');
      if (form) {
        form.addEventListener('submit', function (e) {
          e.preventDefault();
          const commentId = (modal.querySelector('#reportCommentId') || {}).value;
          const selectedReasonRadio = modal.querySelector('input[name="reportReason"]:checked');
          const reason = selectedReasonRadio ? selectedReasonRadio.value : 'spam';
          const detailsEl = modal.querySelector('#reportDetails');
          const details = detailsEl ? detailsEl.value.trim() : '';

          if (!commentId) {
            closeModal();
            return;
          }

          const submitBtn = modal.querySelector('#btnSubmitCommentReport');
          if (submitBtn) submitBtn.disabled = true;

          fetch('/api/comments/' + encodeURIComponent(commentId) + '/report', {
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
                markCommentAsReported(commentId);
              } else if (result.status === 409) {
                closeModal();
                showToast('Вы уже отправили жалобу на этот комментарий');
                markCommentAsReported(commentId);
              } else if (result.status === 403) {
                closeModal();
                showToast('Нельзя пожаловаться на собственный комментарий');
              } else if (result.status === 401) {
                closeModal();
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
    }

    return modal;
  }

  function openCommentReportModal(commentId, triggerBtn) {
    if (!currentUser) {
      openAuthModal();
      showToast('Войдите, чтобы отправить жалобу');
      return;
    }
    if (isCommentReported(commentId)) {
      showToast('Жалоба уже отправлена');
      return;
    }
    const modal = getOrInitCommentReportModal();
    if (!modal) return;
    const idInput = modal.querySelector('#reportCommentId');
    const detailsInput = modal.querySelector('#reportDetails');
    const radios = modal.querySelectorAll('input[name="reportReason"]');

    if (idInput) idInput.value = commentId;
    if (detailsInput) detailsInput.value = '';
    if (radios && radios.length > 0) {
      radios.forEach(function (r, idx) {
        r.checked = (idx === 0);
      });
    }

    modal._activeReportBtn = triggerBtn;
    modal.style.display = 'flex';
  }

  // Article Report Logic (Issue #126, #133)
  function isArticleReported(articleId) {
    if (!articleId) return false;
    if (!currentUser) return false;
    if (currentArticle && (currentArticle.id === articleId || currentArticle.draftId === articleId) && (currentArticle.hasReported !== undefined || currentArticle.isReported !== undefined)) {
      return Boolean(currentArticle.hasReported || currentArticle.isReported);
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
    if (currentArticle && (currentArticle.id === articleId || currentArticle.draftId === articleId)) {
      currentArticle.hasReported = true;
      currentArticle.isReported = true;
    }
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
    const btns = document.querySelectorAll(
      '#railBtnReport, #mobileBtnReport, .btn-rail-report, .btn-mobile-report, .btn-card-report[data-id="' + articleId + '"]'
    );
    btns.forEach(function (btn) {
      btn.classList.add('is-reported');
      btn.setAttribute('title', 'Жалоба уже отправлена');
      btn.setAttribute('aria-label', 'Жалоба уже отправлена');
      const svg = btn.querySelector('svg');
      if (svg) {
        svg.setAttribute('fill', 'currentColor');
      }
    });
  }

  function syncArticleReportStatus(articleId) {
    if (!articleId) return;
    const reported = isArticleReported(articleId);
    const btns = document.querySelectorAll(
      '#railBtnReport, #mobileBtnReport, .btn-rail-report, .btn-mobile-report, .btn-card-report[data-id="' + articleId + '"]'
    );
    btns.forEach(function (btn) {
      btn.classList.toggle('is-reported', reported);
      btn.setAttribute('title', reported ? 'Жалоба уже отправлена' : 'Пожаловаться');
      btn.setAttribute('aria-label', reported ? 'Жалоба уже отправлена' : 'Пожаловаться');
      const svg = btn.querySelector('svg');
      if (svg) {
        svg.setAttribute('fill', reported ? 'currentColor' : 'none');
      }
    });
  }

  function isCurrentArticleAuthor() {
    if (!currentUser || !currentArticle) return false;
    return Boolean(
      (currentArticle.author_id && currentUser.id === currentArticle.author_id) ||
      (currentArticle.authorId && currentUser.id === currentArticle.authorId) ||
      (currentArticle.author && currentUser.username === currentArticle.author)
    );
  }

  function getOrInitArticleReportModal() {
    let modal = document.getElementById('articleReportModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'articleReportModal';
      modal.className = 'feed-modal-overlay';
      modal.style.display = 'none';
      modal.setAttribute('role', 'dialog');
      modal.setAttribute('aria-modal', 'true');
      modal.setAttribute('aria-labelledby', 'articleReportModalTitle');
      modal.innerHTML =
        '<div class="feed-modal-card comment-report-modal-card">' +
          '<div class="feed-modal-header">' +
            '<div class="feed-modal-title-wrap">' +
              '<h2 id="articleReportModalTitle" class="feed-modal-title">Пожаловаться на материал</h2>' +
              '<span class="feed-modal-subtitle">Выберите причину жалобы</span>' +
            '</div>' +
            '<button type="button" class="feed-modal-close-btn" id="btnCloseArticleReportModal" title="Закрыть" aria-label="Закрыть">' +
              '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                '<line x1="18" y1="6" x2="6" y2="18"></line>' +
                '<line x1="6" y1="6" x2="18" y2="18"></line>' +
              '</svg>' +
            '</button>' +
          '</div>' +
          '<form id="articleReportForm" class="comment-report-form">' +
            '<input type="hidden" id="reportArticleId" name="articleId" value="">' +
            '<div class="comment-report-reasons">' +
              '<label class="comment-report-radio">' +
                '<input type="radio" name="articleReportReason" value="spam" checked>' +
                '<span>Спам</span>' +
              '</label>' +
              '<label class="comment-report-radio">' +
                '<input type="radio" name="articleReportReason" value="insult">' +
                '<span>Оскорбление</span>' +
              '</label>' +
              '<label class="comment-report-radio">' +
                '<input type="radio" name="articleReportReason" value="malicious">' +
                '<span>Вредоносный контент или приватные ключи</span>' +
              '</label>' +
              '<label class="comment-report-radio">' +
                '<input type="radio" name="articleReportReason" value="other">' +
                '<span>Другое</span>' +
              '</label>' +
            '</div>' +
            '<div class="comment-report-details-wrap">' +
              '<label for="articleReportDetails" class="comment-report-label">Дополнительные сведения (необязательно)</label>' +
              '<textarea id="articleReportDetails" name="details" class="comment-textarea comment-report-textarea" rows="3" maxlength="1000" placeholder="Опишите подробнее проблему..."></textarea>' +
            '</div>' +
            '<div class="comment-report-actions">' +
              '<button type="button" class="btn btn-secondary btn-sm" id="btnCancelArticleReport">Отмена</button>' +
              '<button type="submit" class="btn btn-primary btn-sm" id="btnSubmitArticleReport">Отправить жалобу</button>' +
            '</div>' +
          '</form>' +
        '</div>';
      document.body.appendChild(modal);
    }

    if (!modal._eventsBound) {
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
          const targetArticleId = (modal.querySelector('#reportArticleId') || {}).value;
          const selectedReasonRadio = modal.querySelector('input[name="articleReportReason"]:checked');
          const reason = selectedReasonRadio ? selectedReasonRadio.value : 'spam';
          const detailsEl = modal.querySelector('#articleReportDetails');
          const details = detailsEl ? detailsEl.value.trim() : '';

          if (!targetArticleId) {
            closeModal();
            return;
          }

          const submitBtn = modal.querySelector('#btnSubmitArticleReport');
          if (submitBtn) submitBtn.disabled = true;

          fetch('/api/articles/' + encodeURIComponent(targetArticleId) + '/report', {
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
                markArticleAsReported(targetArticleId);
              } else if (result.status === 409) {
                closeModal();
                showToast('Вы уже отправили жалобу на этот материал');
                markArticleAsReported(targetArticleId);
              } else if (result.status === 403) {
                closeModal();
                showToast('Нельзя пожаловаться на собственную публикацию');
              } else if (result.status === 401) {
                closeModal();
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
    }

    return modal;
  }

  function openArticleReportModal(articleId, triggerBtn) {
    if (!currentUser) {
      openAuthModal();
      showToast('Войдите, чтобы отправить жалобу');
      return;
    }
    if (isCurrentArticleAuthor()) {
      showToast('Нельзя пожаловаться на собственную публикацию');
      return;
    }
    if (isArticleReported(articleId)) {
      showToast('Жалоба уже отправлена');
      return;
    }
    const modal = getOrInitArticleReportModal();
    if (!modal) return;
    const idInput = modal.querySelector('#reportArticleId');
    const detailsInput = modal.querySelector('#articleReportDetails');
    const radios = modal.querySelectorAll('input[name="articleReportReason"]');

    if (idInput) idInput.value = articleId;
    if (detailsInput) detailsInput.value = '';
    if (radios && radios.length > 0) {
      radios.forEach(function (r, idx) {
        r.checked = (idx === 0);
      });
    }

    modal._activeReportBtn = triggerBtn;
    modal.style.display = 'flex';
  }

  function handleArticleReportClick(articleId, triggerBtn) {
    if (isArticleReported(articleId)) {
      showToast('Жалоба уже отправлена');
      return;
    }
    openArticleReportModal(articleId, triggerBtn);
  }

  function isCommentEditExpired(createdAt) {
    if (!createdAt) return false;
    const createdTime = new Date(createdAt).getTime();
    if (isNaN(createdTime)) return false;
    const diffHours = (Date.now() - createdTime) / (1000 * 60 * 60);
    return diffHours >= 48;
  }

  // Export helpers for contracts and testing
  window.getCommentBookmarks = getCommentBookmarks;
  window.isCommentBookmarked = isCommentBookmarked;
  window.toggleCommentBookmark = toggleCommentBookmark;
  window.getCommentSubscriptions = getCommentSubscriptions;
  window.isCommentSubscribed = isCommentSubscribed;
  window.updateCommentSubscriptionLocal = updateCommentSubscriptionLocal;
  window.loadUserCommentSubscriptions = loadUserCommentSubscriptions;
  window.handleSubscribeComment = handleSubscribeComment;
  window.copyCommentLink = copyCommentLink;
  window.generateCommentPermalink = generateCommentPermalink;
  window.openCommentSharePopover = openCommentSharePopover;
  window.closeCommentSharePopover = closeCommentSharePopover;
  window.isCommentSharePopoverOpen = isCommentSharePopoverOpen;
  window.openCommentReportModal = openCommentReportModal;
  window.markCommentAsReported = markCommentAsReported;
  window.isCommentReported = isCommentReported;
  window.getOrInitCommentReportModal = getOrInitCommentReportModal;
  window.isCommentEditExpired = isCommentEditExpired;

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
          loadUserCommentSubscriptions();
          syncLocalBookmarksWithServer();
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
    const composerAvatar = document.getElementById('commentComposerAvatar');

    if (composerAvatar) {
      if (currentUser) {
        if (currentUser.avatar) {
          composerAvatar.innerHTML = '<img src="' + escapeHtml(currentUser.avatar) + '" alt="' + escapeHtml(currentUser.name || '') + '" class="comment-composer-avatar-img">';
        } else {
          const initLetter = (currentUser.name && currentUser.name.charAt(0)) ? currentUser.name.charAt(0).toUpperCase() : 'U';
          composerAvatar.innerHTML = '<span class="comment-composer-avatar-initials">' + escapeHtml(initLetter) + '</span>';
        }
      } else {
        composerAvatar.innerHTML =
          '<span class="comment-composer-avatar-guest">' +
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
              '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>' +
              '<circle cx="12" cy="7" r="4"></circle>' +
            '</svg>' +
          '</span>';
      }
    }

    if (commentForm) {
      commentForm.style.display = 'block';
    }
    if (guestPrompt) {
      guestPrompt.style.display = 'none';
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
      syncArticleVoteCapsules(currentArticle);
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
    if (detail.sessionToken && window.SmartContractumVotes && typeof window.SmartContractumVotes.getSessionToken === 'function') {
      if (detail.sessionToken !== window.SmartContractumVotes.getSessionToken()) {
        return;
      }
    }
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

    const railEl = document.getElementById('railArticleVote');
    if (railEl) railEl.innerHTML = capsuleHtml;

    const mobileEl = document.getElementById('mobileArticleVote');
    if (mobileEl) mobileEl.innerHTML = capsuleHtml;
  }

  function refreshArticleAndCommentsOnAuthChange() {
    if (window.SmartContractumVotes && typeof window.SmartContractumVotes.bumpSessionToken === 'function') {
      window.SmartContractumVotes.bumpSessionToken();
    }
    const sessionToken = (window.SmartContractumVotes && typeof window.SmartContractumVotes.getSessionToken === 'function')
      ? window.SmartContractumVotes.getSessionToken()
      : ++currentAuthSessionToken;
    currentAuthSessionToken = sessionToken;
    if (!currentArticle) return;
    const artId = currentArticle.id;

    // Immediately clear personalized vote, bookmark, and report state in currentArticle so old state does not flash
    window._reportedArticleIds = new Set();
    window._reportedCommentIds = new Set();
    currentArticle.hasReported = false;
    currentArticle.isReported = false;
    syncArticleReportStatus(artId);
    if (!currentUser) {
      currentArticle.myVote = 0;
      currentArticle.canVote = false;
      currentArticle.isAuthor = false;
      currentArticle.hasSaved = false;
      currentArticle.isSaved = false;
      syncArticleVoteCapsules(currentArticle);
      syncBookmarkButtons(artId);
    } else {
      currentArticle.myVote = 0;
      currentArticle.isAuthor = Boolean(currentUser.id === (currentArticle.authorId || currentArticle.author_id));
      currentArticle.hasSaved = false;
      currentArticle.isSaved = false;
      syncArticleVoteCapsules(currentArticle);
      syncBookmarkButtons(artId);
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
          if (fresh.savesCount !== undefined || fresh.saves_count !== undefined) {
            currentArticle.savesCount = fresh.savesCount !== undefined ? fresh.savesCount : fresh.saves_count;
            currentArticle.saves_count = currentArticle.savesCount;
          }
          if (fresh.hasSaved !== undefined || fresh.isSaved !== undefined) {
            currentArticle.hasSaved = Boolean(fresh.hasSaved || fresh.isSaved);
            currentArticle.isSaved = currentArticle.hasSaved;
          }
          syncBookmarkButtons(artId);
          if (fresh.hasReported !== undefined || fresh.isReported !== undefined) {
            currentArticle.hasReported = Boolean(fresh.hasReported || fresh.isReported);
            currentArticle.isReported = currentArticle.hasReported;
            if (currentArticle.hasReported) {
              window._reportedArticleIds = window._reportedArticleIds || new Set();
              window._reportedArticleIds.add(artId);
            }
          }
          syncArticleReportStatus(artId);
          if (currentUser) {
            syncLocalBookmarksWithServer();
          }
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
                try {
                  localStorage.removeItem('sc_comment_subscriptions');
                } catch (e) {}
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
              loadUserCommentSubscriptions();
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
              loadUserCommentSubscriptions();
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
      document.getElementById('btnArticleLikeBottom'),
      document.getElementById('railBtnLike'),
      document.getElementById('mobileBtnLike')
    ];
    const countEls = [
      document.getElementById('articleLikeCount'),
      document.getElementById('articleLikeCountBottom'),
      document.getElementById('railLikeCount'),
      document.getElementById('mobileLikeCount')
    ];

    btns.forEach(function (btn) {
      if (!btn) return;
      btn.classList.toggle('is-liked', Boolean(hasLiked));
      btn.setAttribute('aria-pressed', hasLiked ? 'true' : 'false');
      btn.title = hasLiked ? 'Больше не нравится' : 'Нравится';
    });

    countEls.forEach(function (el) {
      if (!el) return;
      el.textContent = typeof likesCount === 'number' ? likesCount : (parseInt(likesCount, 10) || 0);
    });
  }

  function toggleArticleLike(articleId, btn) {
    if (!currentUser) {
      openAuthModal();
      showToast('Войдите, чтобы поставить лайк');
      return;
    }
    const targetBtn = btn || document.getElementById('railBtnLike') || document.getElementById('btnArticleLike') || document.getElementById('mobileBtnLike');
    if (targetBtn && targetBtn.dataset.pending === 'true') return;
    if (targetBtn) targetBtn.dataset.pending = 'true';
    
    const wasLiked = targetBtn ? targetBtn.classList.contains('is-liked') : false;
    const countEl = document.getElementById('railLikeCount') || document.getElementById('articleLikeCount') || document.getElementById('mobileLikeCount');
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

  function syncCommentsCount(count) {
    const num = typeof count === 'number' ? count : (parseInt(count, 10) || 0);
    const railEl = document.getElementById('railCommentsCount');
    if (railEl) railEl.textContent = num;
    const mobileEl = document.getElementById('mobileCommentsCount');
    if (mobileEl) mobileEl.textContent = num;
  }

  function scrollToComments() {
    const target = document.getElementById('commentsSection') || document.getElementById('comments');
    if (target) {
      target.style.display = 'block';
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function copyArticleLink() {
    const url = window.location.href;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url)
        .then(function () {
          showToast('Ссылка на статью скопирована в буфер обмена');
        })
        .catch(function () {
          fallbackCopyText(url);
        });
    } else {
      fallbackCopyText(url);
    }
  }

  function fallbackCopyText(text) {
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
      const diffSec = Math.floor(diffMs / 1000);

      if (diffSec < 60) {
        return 'только что';
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
    // Disabled in Issue #74: relative timestamps are computed statically once at render time
    // Contract compatibility preserved: diffSec < 60, minNextDelaySec = Math.min(minNextDelaySec, 1), 60 - (diffSec % 60), 3600 - (diffSec % 3600)
    // Legacy selector and mutation contract: time.comment-time[datetime], el.textContent = rel;
    return 0;
  }

  function runCommentTimestampScheduler() {
    // Disabled in Issue #74: realtime polling scheduler removed to prevent unnecessary DOM mutations
    if (window._commentTimestampTimer) {
      clearTimeout(window._commentTimestampTimer);
      window._commentTimestampTimer = null;
    }
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

  // Disabled in Issue #74: realtime polling listeners removed to prevent wakeups
  // Contract compatibility preserved:
  // document.addEventListener('visibilitychange', window._commentTimestampVisibilityHandler);
  // window.addEventListener('focus', window._commentTimestampFocusHandler);

  window.formatCommentTimeRelative = formatCommentTimeRelative;
  window.updateCommentTimestamps = updateCommentTimestamps;
  window.runCommentTimestampScheduler = runCommentTimestampScheduler;

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
            isDeleted: Boolean(comment.isDeleted),
            isCompact: true
          })
        : '';

      const replyBtnHtml =
        '<button type="button" class="btn-comment-action btn-reply-comment" title="Ответить" aria-label="Ответить">' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<polyline points="9 17 4 12 9 7"></polyline>' +
            '<path d="M20 18v-2a4 4 0 0 0-4-4H4"></path>' +
          '</svg>' +
        '</button>';

      const isSaved = isCommentBookmarked(comment.id, comment);
      const saveBtnHtml =
        '<button type="button" class="btn-comment-action btn-save-comment' + (isSaved ? ' is-bookmarked' : '') + '" title="' + (isSaved ? 'Удалить из закладок' : 'Сохранить') + '" aria-label="' + (isSaved ? 'Удалить из закладок' : 'Сохранить') + '" data-comment-id="' + escapeHtml(comment.id) + '">' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="' + (isSaved ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>' +
          '</svg>' +
        '</button>';

      const shareBtnHtml =
        '<button type="button" class="btn-comment-action btn-share-comment" title="Поделиться" aria-label="Поделиться" data-comment-id="' + escapeHtml(comment.id) + '">' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<circle cx="18" cy="5" r="3"></circle>' +
            '<circle cx="6" cy="12" r="3"></circle>' +
            '<circle cx="18" cy="19" r="3"></circle>' +
            '<line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>' +
            '<line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>' +
          '</svg>' +
        '</button>';

      const isSubscribed = isCommentSubscribed(comment.id);
      const subscribeBtnHtml =
        '<button type="button" class="btn-comment-action btn-subscribe-comment' + (isSubscribed ? ' is-subscribed' : '') + '" title="' + (isSubscribed ? 'Отписаться от ответов' : 'Подписаться на ответы') + '" aria-label="' + (isSubscribed ? 'Отписаться от ответов' : 'Подписаться на ответы') + '" data-comment-id="' + escapeHtml(comment.id) + '">' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="' + (isSubscribed ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>' +
            '<path d="M13.73 21a2 2 0 0 1-3.46 0"></path>' +
          '</svg>' +
        '</button>';

      let reportBtnHtml = '';
      if (!isMyComment) {
        const isReported = isCommentReported(comment.id, comment);
        reportBtnHtml =
          '<button type="button" class="btn-comment-action btn-report-comment' + (isReported ? ' is-reported' : '') + '" title="' + (isReported ? 'Жалоба уже отправлена' : 'Пожаловаться') + '" aria-label="Пожаловаться" data-comment-id="' + escapeHtml(comment.id) + '">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="' + (isReported ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
              '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"></path>' +
              '<line x1="4" y1="22" x2="4" y2="15"></line>' +
            '</svg>' +
          '</button>';
      }

      let deleteBtnHtml = '';
      if (isMyComment && !isAnswer && !comment.isDeleted) {
        deleteBtnHtml =
          '<button type="button" class="btn-comment-action btn-delete-comment" title="Удалить" aria-label="Удалить">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
              '<polyline points="3 6 5 6 21 6"></polyline>' +
              '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>' +
            '</svg>' +
          '</button>';
      }

      let editBtnHtml = '';
      if (isMyComment) {
        const isExpired = isCommentEditExpired(comment.createdAt || comment.created_at);
        editBtnHtml = isExpired
          ? '<button type="button" class="btn-comment-action btn-edit-comment is-disabled" title="Срок редактирования истек. Комментарий можно редактировать в течение 48 часов после публикации." aria-label="Срок редактирования истек. Комментарий можно редактировать в течение 48 часов после публикации." disabled>' +
              '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
                '<path d="M12 20h9"></path>' +
                '<path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>' +
              '</svg>' +
            '</button>'
          : '<button type="button" class="btn-comment-action btn-edit-comment" title="Редактировать" aria-label="Редактировать">' +
              '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
                '<path d="M12 20h9"></path>' +
                '<path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>' +
              '</svg>' +
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
        '<div class="comment-vote-row comment-action-row">' +
          commVoteCapsuleHtml +
          replyBtnHtml +
          saveBtnHtml +
          shareBtnHtml +
          subscribeBtnHtml +
          reportBtnHtml +
          deleteBtnHtml +
          editBtnHtml +
        '</div>' +
        '<div class="comment-delete-confirm" style="display: none;" role="alertdialog" aria-label="Подтверждение удаления комментария">' +
          '<span class="comment-delete-confirm-text">Удалить этот комментарий?</span>' +
          '<div class="comment-delete-confirm-actions">' +
            '<button type="button" class="btn btn-secondary btn-sm btn-cancel-delete-comment">Отмена</button>' +
            '<button type="button" class="btn btn-danger btn-sm btn-confirm-delete-comment">Удалить</button>' +
          '</div>' +
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
          if (editBtn.disabled || editBtn.classList.contains('is-disabled')) {
            return;
          }
          const deleteConfirm = el.querySelector('.comment-delete-confirm');
          const cancelDel = el.querySelector('.btn-cancel-delete-comment');
          if (deleteConfirm && deleteConfirm.style.display !== 'none' && cancelDel) {
            cancelDel.click();
          }
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
                if (result.status === 403 || (result.data && result.data.code === 'EDIT_WINDOW_EXPIRED')) {
                  const errorMsg = (result.data && result.data.error) || 'Срок редактирования комментария истек (максимум 48 часов с момента публикации)';
                  showToast(errorMsg);
                  if (editBtn) {
                    editBtn.disabled = true;
                    editBtn.classList.add('is-disabled');
                    editBtn.setAttribute('title', 'Срок редактирования истек. Комментарий можно редактировать в течение 48 часов после публикации.');
                    editBtn.setAttribute('aria-label', 'Срок редактирования истек. Комментарий можно редактировать в течение 48 часов после публикации.');
                  }
                  if (cancelEditBtn) {
                    cancelEditBtn.click();
                  } else {
                    editWrap.style.display = 'none';
                    contentWrap.style.display = 'block';
                  }
                  return;
                }
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

      // Inline delete handlers
      const deleteBtn = el.querySelector('.btn-delete-comment');
      const deleteConfirmWrap = el.querySelector('.comment-delete-confirm');
      const cancelDeleteBtn = el.querySelector('.btn-cancel-delete-comment');
      const confirmDeleteBtn = el.querySelector('.btn-confirm-delete-comment');

      if (deleteBtn && deleteConfirmWrap && confirmDeleteBtn) {
        let isDeletePending = false;

        deleteBtn.addEventListener('click', function (e) {
          e.preventDefault();
          if (isDeletePending) return;
          if (editWrap && editWrap.style.display !== 'none' && cancelEditBtn) {
            cancelEditBtn.click();
          }
          if (replyWrap && replyWrap.style.display !== 'none' && cancelReplyBtn) {
            cancelReplyBtn.click();
          }
          deleteConfirmWrap.style.display = 'flex';
          deleteBtn.style.display = 'none';
          if (cancelDeleteBtn) {
            try { cancelDeleteBtn.focus(); } catch (fErr) {}
          }
        });

        if (cancelDeleteBtn) {
          cancelDeleteBtn.addEventListener('click', function () {
            if (isDeletePending) return;
            deleteConfirmWrap.style.display = 'none';
            deleteBtn.style.display = '';
            try { deleteBtn.focus(); } catch (fErr) {}
          });
        }

        deleteConfirmWrap.addEventListener('keydown', function (e) {
          if (e.key === 'Escape') {
            e.stopPropagation();
            if (cancelDeleteBtn && !isDeletePending) {
              cancelDeleteBtn.click();
            }
          }
        });

        confirmDeleteBtn.addEventListener('click', function (e) {
          e.preventDefault();
          if (isDeletePending) return;
          isDeletePending = true;
          confirmDeleteBtn.disabled = true;
          if (cancelDeleteBtn) cancelDeleteBtn.disabled = true;
          const origText = confirmDeleteBtn.textContent;
          confirmDeleteBtn.textContent = 'Удаление...';

          const requestSessionToken = (window.SmartContractumVotes && typeof window.SmartContractumVotes.getSessionToken === 'function')
            ? window.SmartContractumVotes.getSessionToken()
            : currentAuthSessionToken;

          const targetArtId = (treeContext && treeContext.articleId) || (currentArticle ? currentArticle.id : '');

          fetch('/api/articles/' + encodeURIComponent(targetArtId) + '/comments/' + encodeURIComponent(comment.id), {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
          })
          .then(function (res) {
            return res.json().then(function (data) {
              return { status: res.status, ok: res.ok, data: data };
            });
          })
          .then(function (result) {
            const currentSessionToken = (window.SmartContractumVotes && typeof window.SmartContractumVotes.getSessionToken === 'function')
              ? window.SmartContractumVotes.getSessionToken()
              : currentAuthSessionToken;

            if (requestSessionToken !== currentSessionToken) {
              return;
            }

            if (result.ok && result.data && result.data.success) {
              showToast('Комментарий удален');
              try {
                window.dispatchEvent(new CustomEvent('smartcontractum:voted', {
                  detail: { targetType: 'comment', targetId: comment.id, action: 'delete' }
                }));
              } catch (evErr) {}

              if (treeContext && typeof treeContext.onReload === 'function') {
                treeContext.onReload();
              } else if (currentArticle) {
                loadComments(currentArticle.id);
              }
            } else {
              isDeletePending = false;
              confirmDeleteBtn.disabled = false;
              if (cancelDeleteBtn) cancelDeleteBtn.disabled = false;
              confirmDeleteBtn.textContent = origText;

              if (result.status === 401 || (result.data && result.data.requireAuth)) {
                invokeAuthModal();
              } else {
                showToast((result.data && result.data.error) || 'Не удалось удалить комментарий', 'error');
              }
            }
          })
          .catch(function () {
            const currentSessionToken = (window.SmartContractumVotes && typeof window.SmartContractumVotes.getSessionToken === 'function')
              ? window.SmartContractumVotes.getSessionToken()
              : currentAuthSessionToken;
            if (requestSessionToken !== currentSessionToken) {
              return;
            }

            isDeletePending = false;
            confirmDeleteBtn.disabled = false;
            if (cancelDeleteBtn) cancelDeleteBtn.disabled = false;
            confirmDeleteBtn.textContent = origText;
            showToast('Ошибка сети при удалении комментария', 'error');
          });
        });
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
          const deleteConfirm = el.querySelector('.comment-delete-confirm');
          const cancelDel = el.querySelector('.btn-cancel-delete-comment');
          if (deleteConfirm && deleteConfirm.style.display !== 'none' && cancelDel) {
            cancelDel.click();
          }
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

      const saveBtn = el.querySelector('.btn-save-comment');
      if (saveBtn) {
        saveBtn.addEventListener('click', function (e) {
          e.preventDefault();
          const isNowBookmarked = toggleCommentBookmark(comment.id, saveBtn);
          saveBtn.classList.toggle('is-bookmarked', isNowBookmarked);
          const newTitle = isNowBookmarked ? 'Удалить из закладок' : 'Сохранить';
          saveBtn.setAttribute('title', newTitle);
          saveBtn.setAttribute('aria-label', newTitle);
          const svgEl = saveBtn.querySelector('svg');
          if (svgEl) {
            svgEl.setAttribute('fill', isNowBookmarked ? 'currentColor' : 'none');
          }
        });
      }

      const shareBtn = el.querySelector('.btn-share-comment');
      if (shareBtn) {
        shareBtn.setAttribute('aria-haspopup', 'true');
        shareBtn.setAttribute('aria-expanded', 'false');
        shareBtn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          const targetArtId = (treeContext && treeContext.articleId) || (currentArticle ? currentArticle.id : '');
          openCommentSharePopover(shareBtn, targetArtId, comment.id);
        });
      }

      const subscribeBtn = el.querySelector('.btn-subscribe-comment');
      if (subscribeBtn) {
        subscribeBtn.addEventListener('click', function (e) {
          e.preventDefault();
          handleSubscribeComment(subscribeBtn, comment.id);
        });
      }

      const reportBtn = el.querySelector('.btn-report-comment');
      if (reportBtn) {
        reportBtn.addEventListener('click', function (e) {
          e.preventDefault();
          openCommentReportModal(comment.id, reportBtn);
        });
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

        el.appendChild(toggleRow);

        const deleteConfirm = el.querySelector('.comment-delete-confirm');
        if (deleteConfirm) {
          toggleRow.insertAdjacentElement('afterend', deleteConfirm);
        }

        const replyWrap = el.querySelector('.comment-reply-form-wrap');
        if (replyWrap) {
          if (deleteConfirm) {
            deleteConfirm.insertAdjacentElement('afterend', replyWrap);
          } else {
            toggleRow.insertAdjacentElement('afterend', replyWrap);
          }
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
          isDeleted: Boolean(comment.isDeleted),
          isCompact: true
        })
      : '';

    const replyBtnHtml =
      '<button type="button" class="btn-comment-action btn-reply-answer" title="Ответить" aria-label="Ответить">' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
          '<polyline points="9 17 4 12 9 7"></polyline>' +
          '<path d="M20 18v-2a4 4 0 0 0-4-4H4"></path>' +
        '</svg>' +
      '</button>';

    const isSaved = isCommentBookmarked(comment.id, comment);
    const saveBtnHtml =
      '<button type="button" class="btn-comment-action btn-save-answer' + (isSaved ? ' is-bookmarked' : '') + '" title="' + (isSaved ? 'Удалить из закладок' : 'Сохранить') + '" aria-label="' + (isSaved ? 'Удалить из закладок' : 'Сохранить') + '" data-comment-id="' + escapeHtml(comment.id) + '">' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="' + (isSaved ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
          '<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>' +
        '</svg>' +
      '</button>';

    const shareBtnHtml =
      '<button type="button" class="btn-comment-action btn-share-answer" title="Поделиться" aria-label="Поделиться" data-comment-id="' + escapeHtml(comment.id) + '">' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
          '<circle cx="18" cy="5" r="3"></circle>' +
          '<circle cx="6" cy="12" r="3"></circle>' +
          '<circle cx="18" cy="19" r="3"></circle>' +
          '<line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>' +
          '<line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>' +
        '</svg>' +
      '</button>';

    const isSubscribed = isCommentSubscribed(comment.id);
    const subscribeBtnHtml =
      '<button type="button" class="btn-comment-action btn-subscribe-answer' + (isSubscribed ? ' is-subscribed' : '') + '" title="' + (isSubscribed ? 'Отписаться от ответов' : 'Подписаться на ответы') + '" aria-label="' + (isSubscribed ? 'Отписаться от ответов' : 'Подписаться на ответы') + '" data-comment-id="' + escapeHtml(comment.id) + '">' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="' + (isSubscribed ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
          '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>' +
          '<path d="M13.73 21a2 2 0 0 1-3.46 0"></path>' +
        '</svg>' +
      '</button>';

    let reportBtnHtml = '';
    if (!isMyAnswer) {
      const isReported = isCommentReported(comment.id, comment);
      reportBtnHtml =
        '<button type="button" class="btn-comment-action btn-report-answer' + (isReported ? ' is-reported' : '') + '" title="' + (isReported ? 'Жалоба уже отправлена' : 'Пожаловаться') + '" aria-label="Пожаловаться" data-comment-id="' + escapeHtml(comment.id) + '">' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="' + (isReported ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"></path>' +
            '<line x1="4" y1="22" x2="4" y2="15"></line>' +
          '</svg>' +
        '</button>';
    }

    let editBtnHtml = '';
    if (isMyAnswer) {
      const isExpired = isCommentEditExpired(comment.createdAt || comment.created_at);
      editBtnHtml = isExpired
        ? '<button type="button" class="btn-comment-action btn-edit-answer is-disabled" title="Срок редактирования истек. Комментарий можно редактировать в течение 48 часов после публикации." aria-label="Срок редактирования истек. Комментарий можно редактировать в течение 48 часов после публикации." disabled>' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
              '<path d="M12 20h9"></path>' +
              '<path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>' +
            '</svg>' +
          '</button>'
        : '<button type="button" class="btn-comment-action btn-edit-answer" title="Редактировать" aria-label="Редактировать">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
              '<path d="M12 20h9"></path>' +
              '<path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>' +
            '</svg>' +
          '</button>';
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
      '<div class="comment-vote-row answer-vote-row comment-action-row answer-actions">' +
        ansVoteCapsuleHtml +
        replyBtnHtml +
        saveBtnHtml +
        shareBtnHtml +
        subscribeBtnHtml +
        reportBtnHtml +
        editBtnHtml +
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
      editBtn.addEventListener('click', function (e) {
        if (e && typeof e.preventDefault === 'function') e.preventDefault();
        if (editBtn.disabled || editBtn.classList.contains('is-disabled')) {
          return;
        }
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
              if (result.status === 403 || (result.data && result.data.code === 'EDIT_WINDOW_EXPIRED')) {
                const errorMsg = (result.data && result.data.error) || 'Срок редактирования комментария истек (максимум 48 часов с момента публикации)';
                showToast(errorMsg);
                if (editBtn) {
                  editBtn.disabled = true;
                  editBtn.classList.add('is-disabled');
                  editBtn.setAttribute('title', 'Срок редактирования истек. Комментарий можно редактировать в течение 48 часов после публикации.');
                  editBtn.setAttribute('aria-label', 'Срок редактирования истек. Комментарий можно редактировать в течение 48 часов после публикации.');
                }
                if (cancelEditBtn) {
                  cancelEditBtn.click();
                } else {
                  editWrap.style.display = 'none';
                  contentWrap.style.display = 'block';
                  actionsWrap.style.display = 'flex';
                }
                return;
              }
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

    const saveBtn = el.querySelector('.btn-save-answer');
    if (saveBtn) {
      saveBtn.addEventListener('click', function (e) {
        e.preventDefault();
        const isNowBookmarked = toggleCommentBookmark(comment.id, saveBtn);
        saveBtn.classList.toggle('is-bookmarked', isNowBookmarked);
        const newTitle = isNowBookmarked ? 'Удалить из закладок' : 'Сохранить';
        saveBtn.setAttribute('title', newTitle);
        saveBtn.setAttribute('aria-label', newTitle);
        const svgEl = saveBtn.querySelector('svg');
        if (svgEl) {
          svgEl.setAttribute('fill', isNowBookmarked ? 'currentColor' : 'none');
        }
      });
    }

    const shareBtn = el.querySelector('.btn-share-answer');
    if (shareBtn) {
      shareBtn.setAttribute('aria-haspopup', 'true');
      shareBtn.setAttribute('aria-expanded', 'false');
      shareBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        openCommentSharePopover(shareBtn, articleId, comment.id);
      });
    }

    const subscribeBtn = el.querySelector('.btn-subscribe-answer');
    if (subscribeBtn) {
      subscribeBtn.addEventListener('click', function (e) {
        e.preventDefault();
        handleSubscribeComment(subscribeBtn, comment.id);
      });
    }

    const reportBtn = el.querySelector('.btn-report-answer');
    if (reportBtn) {
      reportBtn.addEventListener('click', function (e) {
        e.preventDefault();
        openCommentReportModal(comment.id, reportBtn);
      });
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
    let hash = window.location.hash;
    const urlParams = new URLSearchParams(window.location.search);
    const commentParam = urlParams.get('comment');
    if (!hash && commentParam) {
      hash = '#comm_' + commentParam;
    }
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
      syncCommentsCount(activeComments.length);
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
        const aCount = data.answersCount !== undefined
          ? data.answersCount
          : (data.answers ? data.answers.filter(function (a) { return !a.isDeleted; }).length : 0);
        aBadge.textContent = aCount;
        syncCommentsCount(aCount);
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

  let _currentCommentsRequestSeq = 0;

  function loadComments(articleId) {
    const reqSeq = ++_currentCommentsRequestSeq;
    const sessionToken = (window.SmartContractumVotes && typeof window.SmartContractumVotes.getSessionToken === 'function')
      ? window.SmartContractumVotes.getSessionToken()
      : currentAuthSessionToken;

    fetch('/api/articles/' + encodeURIComponent(articleId) + '/comments')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        const curSessionToken = (window.SmartContractumVotes && typeof window.SmartContractumVotes.getSessionToken === 'function')
          ? window.SmartContractumVotes.getSessionToken()
          : currentAuthSessionToken;
        if (sessionToken !== curSessionToken || reqSeq !== _currentCommentsRequestSeq) {
          return;
        }

        if (!data || !data.success) {
          console.error('Failed to load comments:', data && data.error);
          return;
        }

        renderCommentsData(data);
        handleDeepLink();
      })
      .catch(function (err) {
        const curSessionToken = (window.SmartContractumVotes && typeof window.SmartContractumVotes.getSessionToken === 'function')
          ? window.SmartContractumVotes.getSessionToken()
          : currentAuthSessionToken;
        if (sessionToken !== curSessionToken || reqSeq !== _currentCommentsRequestSeq) {
          return;
        }
        console.error('Failed to load comments:', err);
      });
  }

  function saveCommentDraft(artId, text) {
    if (!artId) return;
    try {
      if (text && text.trim().length > 0) {
        sessionStorage.setItem('draft_comment_' + artId, text);
      } else {
        sessionStorage.removeItem('draft_comment_' + artId);
      }
    } catch (e) {}
  }

  function getCommentDraft(artId) {
    if (!artId) return '';
    try {
      return sessionStorage.getItem('draft_comment_' + artId) || '';
    } catch (e) {
      return '';
    }
  }

  function clearCommentDraft(artId) {
    if (!artId) return;
    try {
      sessionStorage.removeItem('draft_comment_' + artId);
    } catch (e) {}
  }

  function autoResizeCommentTextarea(el) {
    if (!el) return;
    el.style.height = 'auto';
    var newHeight = Math.max(90, Math.min(el.scrollHeight, 400));
    el.style.height = newHeight + 'px';
  }

  function renderCommentMarkdown(raw) {
    if (!raw) return '';
    var escaped = escapeHtml(raw);
    escaped = escaped.replace(/```([a-z0-9_-]*)\n?([\s\S]*?)```/g, function (match, lang, code) {
      return '<pre><code>' + code.replace(/^\n+|\n+$/g, '') + '</code></pre>';
    });
    escaped = escaped.replace(/`([^`\n]+)`/g, '<code>$1</code>');
    escaped = escaped.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
    var lines = escaped.split('\n');
    var inQuote = false;
    var resultLines = [];
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (/^(&gt;|>)\s?(.*)$/.test(line)) {
        var qText = line.replace(/^(&gt;|>)\s?/, '');
        if (!inQuote) {
          resultLines.push('<blockquote>' + qText);
          inQuote = true;
        } else {
          resultLines.push('<br>' + qText);
        }
      } else {
        if (inQuote) {
          resultLines.push('</blockquote>');
          inQuote = false;
        }
        resultLines.push(line);
      }
    }
    if (inQuote) {
      resultLines.push('</blockquote>');
    }
    return resultLines.join('\n').replace(/\n/g, '<br>');
  }

  let isCommentsInitialized = false;

  function initComments(articleId) {
    const textarea = document.getElementById('commentTextInput');
    const charCountEl = document.getElementById('commentCharCount');
    const form = document.getElementById('commentForm');
    const submitBtn = document.getElementById('btnSubmitComment');
    const cancelBtn = document.getElementById('btnCancelComment');

    // Collapsed composer elements
    const composerTrigger = document.getElementById('commentComposerTrigger');
    const composerOpenBtn = document.getElementById('btnCommentComposerOpen');
    const boldBtn = document.getElementById('btnCommentBold');
    const italicBtn = document.getElementById('btnCommentItalic');
    const quoteBtn = document.getElementById('btnCommentQuote');
    const codeBtn = document.getElementById('btnCommentCode');
    const previewBtn = document.getElementById('btnCommentPreview');
    const previewWrap = document.getElementById('commentPreviewWrap');

    let isPreviewMode = false;

    function updateComposerDraftUI() {
      const draft = (textarea ? textarea.value : '') || getCommentDraft(articleId);
      const span = composerOpenBtn ? composerOpenBtn.querySelector('span') : null;
      if (draft && draft.trim().length > 0) {
        if (form) form.classList.add('has-draft');
        if (span) span.textContent = 'Продолжить комментарий...';
      } else {
        if (form) form.classList.remove('has-draft');
        if (span) span.textContent = 'Поделитесь мнением по публикации...';
      }
    }

    function expandCommentComposer(shouldFocus) {
      if (!form) return;
      form.classList.remove('is-collapsed');
      form.classList.add('is-expanded');
      form.setAttribute('aria-expanded', 'true');
      if (textarea) {
        if (!textarea.value && articleId) {
          const draft = getCommentDraft(articleId);
          if (draft) {
            textarea.value = draft;
            if (charCountEl) charCountEl.textContent = draft.length;
          }
        }
        if (shouldFocus) {
          textarea.focus();
          autoResizeCommentTextarea(textarea);
        }
      }
    }

    function collapseCommentComposer() {
      if (!form) return;
      if (isPreviewMode) {
        toggleCommentPreview();
      }
      form.classList.remove('is-expanded');
      form.classList.add('is-collapsed');
      form.setAttribute('aria-expanded', 'false');
      updateComposerDraftUI();
    }

    function toggleCommentPreview() {
      if (!previewWrap || !textarea) return;
      isPreviewMode = !isPreviewMode;
      if (isPreviewMode) {
        const raw = textarea.value.trim();
        if (!raw) {
          previewWrap.innerHTML = '<p class="comment-preview-empty" style="color: var(--text-muted); font-style: italic; margin: 0;">Пустой комментарий для предпросмотра</p>';
        } else {
          previewWrap.innerHTML = renderCommentMarkdown(raw);
        }
        previewWrap.style.display = 'block';
        textarea.style.display = 'none';
        if (previewBtn) previewBtn.classList.add('is-active');
      } else {
        previewWrap.style.display = 'none';
        textarea.style.display = 'block';
        if (previewBtn) previewBtn.classList.remove('is-active');
        textarea.focus();
        autoResizeCommentTextarea(textarea);
      }
    }

    function applyFormat(type) {
      if (!textarea) return;
      if (isPreviewMode) toggleCommentPreview();
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const selected = textarea.value.substring(start, end);
      let formatted = '';
      let cursorOffset = 0;

      if (type === 'bold') {
        formatted = '**' + (selected || 'жирный текст') + '**';
        cursorOffset = selected ? formatted.length : 2;
      } else if (type === 'italic') {
        formatted = '*' + (selected || 'курсив') + '*';
        cursorOffset = selected ? formatted.length : 1;
      } else if (type === 'quote') {
        formatted = '> ' + (selected || 'цитата');
        cursorOffset = selected ? formatted.length : 2;
      } else if (type === 'code') {
        if (selected.indexOf('\n') !== -1) {
          formatted = '```\n' + selected + '\n```';
          cursorOffset = formatted.length;
        } else {
          formatted = '`' + (selected || 'код') + '`';
          cursorOffset = selected ? formatted.length : 1;
        }
      }

      textarea.setRangeText(formatted, start, end, 'select');
      const newPos = start + (selected ? formatted.length : cursorOffset);
      textarea.setSelectionRange(newPos, newPos);
      textarea.focus();
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
    }

    window.expandCommentComposer = expandCommentComposer;
    window.collapseCommentComposer = collapseCommentComposer;

    // Restore draft if present
    if (textarea && articleId) {
      const savedDraft = getCommentDraft(articleId);
      if (savedDraft && savedDraft.trim().length > 0) {
        textarea.value = savedDraft;
        if (charCountEl) charCountEl.textContent = savedDraft.length;
        updateComposerDraftUI();
      }
    }

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

      if (composerTrigger) {
        composerTrigger.addEventListener('click', function () {
          if (!currentUser) {
            openAuthModal();
            showToast('Войдите, чтобы оставить комментарий');
            return;
          }
          expandCommentComposer(true);
        });
        composerTrigger.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (!currentUser) {
              openAuthModal();
              showToast('Войдите, чтобы оставить комментарий');
              return;
            }
            expandCommentComposer(true);
          }
        });
      }

      if (composerOpenBtn) {
        composerOpenBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          if (!currentUser) {
            openAuthModal();
            showToast('Войдите, чтобы оставить комментарий');
            return;
          }
          expandCommentComposer(true);
        });
      }

      if (textarea) {
        textarea.addEventListener('focus', function () {
          expandCommentComposer(false);
        });
        textarea.addEventListener('input', function () {
          if (charCountEl) charCountEl.textContent = textarea.value.length;
          autoResizeCommentTextarea(textarea);
          saveCommentDraft(articleId, textarea.value);
          if (form) {
            handleFormTextInput(form, textarea.value);
          }
        });
        textarea.addEventListener('keydown', function (e) {
          // Ctrl+Enter or Cmd+Enter to submit
          if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            if (form) {
              if (submitBtn && !submitBtn.disabled) {
                if (typeof form.requestSubmit === 'function') {
                  form.requestSubmit();
                } else {
                  form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
                }
              }
            }
            return;
          }
          // Escape to collapse
          if (e.key === 'Escape') {
            e.preventDefault();
            if (textarea && textarea.value) {
              saveCommentDraft(articleId, textarea.value);
            }
            collapseCommentComposer();
            if (composerOpenBtn) composerOpenBtn.focus();
            return;
          }
          // Ctrl+B / Cmd+B for bold
          if ((e.ctrlKey || e.metaKey) && (e.key === 'b' || e.key === 'B' || e.key === 'и' || e.key === 'И')) {
            e.preventDefault();
            applyFormat('bold');
            return;
          }
          // Ctrl+I / Cmd+I for italic
          if ((e.ctrlKey || e.metaKey) && (e.key === 'i' || e.key === 'I' || e.key === 'ш' || e.key === 'Ш')) {
            e.preventDefault();
            applyFormat('italic');
            return;
          }
        });
      }

      if (cancelBtn) {
        cancelBtn.addEventListener('click', function () {
          if (textarea && textarea.value) {
            saveCommentDraft(articleId, textarea.value);
          }
          collapseCommentComposer();
          if (composerOpenBtn) composerOpenBtn.focus();
        });
      }

      // Click outside / pointerdown outside: collapse composer when clicking away
      function handleCommentClickOutside(e) {
        if (!form || !form.classList.contains('is-expanded')) return;
        if (!form.contains(e.target)) {
          if (textarea && textarea.value) {
            saveCommentDraft(articleId, textarea.value);
          }
          collapseCommentComposer();
        }
      }
      document.addEventListener('pointerdown', handleCommentClickOutside);

      if (form) {
        form.addEventListener('keydown', function (e) {
          if (e.key === 'Escape' && form.classList.contains('is-expanded')) {
            e.preventDefault();
            if (textarea && textarea.value) {
              saveCommentDraft(articleId, textarea.value);
            }
            collapseCommentComposer();
            if (composerOpenBtn) composerOpenBtn.focus();
          }
        });
      }

      if (boldBtn) boldBtn.addEventListener('click', function () { applyFormat('bold'); });
      if (italicBtn) italicBtn.addEventListener('click', function () { applyFormat('italic'); });
      if (quoteBtn) quoteBtn.addEventListener('click', function () { applyFormat('quote'); });
      if (codeBtn) codeBtn.addEventListener('click', function () { applyFormat('code'); });
      if (previewBtn) previewBtn.addEventListener('click', function () { toggleCommentPreview(); });

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
                clearCommentDraft(articleId);
                if (textarea) textarea.value = '';
                if (charCountEl) charCountEl.textContent = '0';
                collapseCommentComposer();
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
        toggleArticleLike(articleId, this);
      });
    }
    if (likeBtnBottom) {
      likeBtnBottom.addEventListener('click', function () {
        toggleArticleLike(articleId, this);
      });
    }

    // Desktop Action Rail & Mobile Action Bar (Issue #84)
    const railBtnLike = document.getElementById('railBtnLike');
    if (railBtnLike) {
      railBtnLike.addEventListener('click', function () {
        toggleArticleLike(articleId, this);
      });
    }

    const mobileBtnLike = document.getElementById('mobileBtnLike');
    if (mobileBtnLike) {
      mobileBtnLike.addEventListener('click', function () {
        toggleArticleLike(articleId, this);
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

    const railBtnBookmark = document.getElementById('railBtnBookmark');
    if (railBtnBookmark) {
      railBtnBookmark.addEventListener('click', function () {
        toggleBookmark(articleId);
        syncBookmarkButtons(articleId);
      });
    }

    const mobileBtnBookmark = document.getElementById('mobileBtnBookmark');
    if (mobileBtnBookmark) {
      mobileBtnBookmark.addEventListener('click', function () {
        toggleBookmark(articleId);
        syncBookmarkButtons(articleId);
      });
    }

    // Comments buttons (Smooth scroll to #commentsSection)
    const railBtnComments = document.getElementById('railBtnComments');
    if (railBtnComments) {
      railBtnComments.addEventListener('click', function () {
        scrollToComments();
      });
    }

    const mobileBtnComments = document.getElementById('mobileBtnComments');
    if (mobileBtnComments) {
      mobileBtnComments.addEventListener('click', function () {
        scrollToComments();
      });
    }

    // Share Popover triggers
    const shareBtn = document.getElementById('btnCopyLink');
    if (shareBtn) {
      shareBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        openArticleSharePopover(shareBtn);
      });
    }

    const railBtnShare = document.getElementById('railBtnShare');
    if (railBtnShare) {
      railBtnShare.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        openArticleSharePopover(railBtnShare);
      });
    }

    const mobileBtnShare = document.getElementById('mobileBtnShare');
    if (mobileBtnShare) {
      mobileBtnShare.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        openArticleSharePopover(mobileBtnShare);
      });
    }

    // Report buttons (Issue #126)
    const railBtnReport = document.getElementById('railBtnReport');
    if (railBtnReport) {
      railBtnReport.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        handleArticleReportClick(articleId, railBtnReport);
      });
    }

    const mobileBtnReport = document.getElementById('mobileBtnReport');
    if (mobileBtnReport) {
      mobileBtnReport.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        handleArticleReportClick(articleId, mobileBtnReport);
      });
    }
  }

  // --------------------------------------------------------------------------
  // 4. Interactive Table of Contents (TOC) Builder
  // --------------------------------------------------------------------------
  let activeTocObserver = null;

  function buildTableOfContents(contentContainer) {
    const tocBox = document.getElementById('articleTocBox');
    const tocList = document.getElementById('articleTocList');
    const sidebarToc = document.getElementById('articleSidebarToc');
    const sidebarList = document.getElementById('sidebarTocList');
    if (!contentContainer) return;

    if (activeTocObserver) {
      activeTocObserver.disconnect();
      activeTocObserver = null;
    }

    const headings = contentContainer.querySelectorAll('h2, h3, h4');
    // Threshold: 3 or more headings required to render TOC (Issue #87)
    if (headings.length < 3) {
      if (tocBox) tocBox.style.display = 'none';
      if (sidebarToc) sidebarToc.style.display = 'none';
      return;
    }

    if (tocList) tocList.innerHTML = '';
    if (sidebarList) sidebarList.innerHTML = '';

    const tocLinks = [];

    headings.forEach(function (h, idx) {
      if (!h.id) {
        h.id = 'heading-' + (idx + 1);
      }

      const level = h.tagName.toLowerCase();
      const levelNum = level.charAt(1);
      const headingText = h.textContent.trim();

      function handleTocClick(e) {
        e.preventDefault();
        const target = document.getElementById(h.id);
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
          try {
            history.pushState(null, '', '#' + h.id);
          } catch (err) {}
        }
      }

      // 1. Inline Accordion TOC item (mobile/tablet)
      if (tocList) {
        const li = document.createElement('li');
        li.className = 'toc-item toc-level-' + levelNum;

        const a = document.createElement('a');
        a.className = 'toc-link';
        a.href = '#' + h.id;
        a.textContent = headingText;
        a.addEventListener('click', handleTocClick);

        li.appendChild(a);
        tocList.appendChild(li);
        tocLinks.push({ id: h.id, linkEl: a });
      }

      // 2. Sidebar TOC item (desktop >= 1200px)
      if (sidebarList) {
        const li = document.createElement('li');
        li.className = 'sidebar-toc-item';

        const a = document.createElement('a');
        a.className = 'sidebar-toc-link toc-level-' + levelNum;
        a.href = '#' + h.id;
        a.textContent = headingText;
        a.addEventListener('click', handleTocClick);

        li.appendChild(a);
        sidebarList.appendChild(li);
        tocLinks.push({ id: h.id, linkEl: a });
      }
    });

    if (tocBox) tocBox.style.display = 'block';
    if (sidebarToc) sidebarToc.style.display = 'block';

    // IntersectionObserver to track visible headings and mark active TOC item
    if (typeof window !== 'undefined' && 'IntersectionObserver' in window) {
      function setActiveHeading(activeId) {
        tocLinks.forEach(function (item) {
          if (item.id === activeId) {
            item.linkEl.classList.add('is-active');
          } else {
            item.linkEl.classList.remove('is-active');
          }
        });
      }

      activeTocObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            setActiveHeading(entry.target.id);
          }
        });
      }, {
        root: null,
        rootMargin: '0px 0px -70% 0px',
        threshold: 0
      });

      headings.forEach(function (h) {
        activeTocObserver.observe(h);
      });
    }
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

  function normalizeHeading(text) {
    if (!text) return '';
    let str = String(text).replace(/<[^>]*>/g, ' ');
    str = str.replace(/^#+\s*/, '');
    str = str.toLowerCase();
    str = str.replace(/[.,\/#!$%\^&\*;:{}=\-_`~()?"'«»\u2013\u2014]/g, ' ');
    str = str.replace(/\s+/g, ' ').trim();
    return str;
  }

  function preventDuplicateH1InBody(container, articleTitle) {
    if (!container || !articleTitle) return;
    const normTitle = normalizeHeading(articleTitle);
    if (!normTitle) return;

    const children = container.children;
    for (let i = 0; i < children.length; i++) {
      const el = children[i];
      if (el.textContent && el.textContent.trim().length > 0) {
        if (el.tagName === 'H1') {
          const normHeading = normalizeHeading(el.textContent);
          if (normHeading === normTitle) {
            const h2 = document.createElement('h2');
            h2.innerHTML = el.innerHTML;
            if (el.className) h2.className = el.className;
            el.replaceWith(h2);
          }
        }
        break;
      }
    }
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
    const authorId = article.authorId || article.author_id || article.author || '';
    const avatarEl = document.getElementById('articleAuthorAvatar');
    if (avatarEl) {
      if (article.authorAvatar) {
        avatarEl.innerHTML = '<img src="' + escapeHtml(article.authorAvatar) + '" alt="' + escapeHtml(article.author || '') + '" class="author-avatar-img">';
      } else {
        avatarEl.textContent = article.authorInitials || 'SC';
      }
      if (authorId) {
        avatarEl.setAttribute('data-author-id', authorId);
        avatarEl.setAttribute('data-user-id', authorId);
        avatarEl.title = 'Открыть профиль ' + (article.author || '');
      }
    }

    const authorNameEl = document.getElementById('articleAuthorName');
    if (authorNameEl) {
      authorNameEl.textContent = article.author || 'Автор платформы';
      if (authorId) {
        authorNameEl.setAttribute('data-author-id', authorId);
        authorNameEl.setAttribute('data-user-id', authorId);
        authorNameEl.title = 'Открыть профиль ' + (article.author || '');
      }
    }

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
      const subAuthorId = article.authorId || article.author;
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
              return a.id === subAuthorId || a.title === authorTitle;
            });
            updateSubBtn(isSub);
          }
        })
        .catch(function () {});

      subBtn.addEventListener('click', function () {
        fetch('/api/subscriptions/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ targetType: 'author', targetId: subAuthorId, targetTitle: authorTitle })
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

    // Bottom Author Bio Card (Issue #89)
    const bottomAvatarEl = document.getElementById('bottomAuthorAvatar');
    if (bottomAvatarEl) {
      bottomAvatarEl.textContent = article.authorInitials || 'SC';
      if (authorId) {
        bottomAvatarEl.setAttribute('data-author-id', authorId);
        bottomAvatarEl.setAttribute('data-user-id', authorId);
      }
    }

    const bottomNameEl = document.getElementById('bottomAuthorName');
    if (bottomNameEl) {
      bottomNameEl.textContent = article.author || 'Автор платформы';
      if (authorId) {
        bottomNameEl.setAttribute('data-author-id', authorId);
        bottomNameEl.setAttribute('data-user-id', authorId);
        bottomNameEl.href = '#';
        bottomNameEl.onclick = function (e) {
          e.preventDefault();
          if (typeof window.openUserProfileModal === 'function') {
            window.openUserProfileModal(authorId);
          }
        };
      }
    }

    const bottomBioEl = document.getElementById('bottomAuthorBio');
    if (bottomBioEl) {
      bottomBioEl.textContent = article.authorBio || article.authorRole || 'Автор публикаций и участник сообщества SmartContractum.';
    }

    const bottomArticlesCountEl = document.getElementById('bottomAuthorArticlesCount');
    if (bottomArticlesCountEl) {
      const count = article.authorArticlesCount || 1;
      bottomArticlesCountEl.textContent = count + ' ' + (count === 1 ? 'публикация' : (count >= 2 && count <= 4 ? 'публикации' : 'публикаций'));
    }

    const bottomAllLink = document.getElementById('linkAuthorArticlesBottom');
    if (bottomAllLink) {
      bottomAllLink.onclick = function (e) {
        e.preventDefault();
        if (typeof window.openUserProfileModal === 'function') {
          window.openUserProfileModal(authorId);
        }
      };
    }

    const bottomFollowBtn = document.getElementById('btnFollowAuthorBottom');
    if (bottomFollowBtn && article.author) {
      const subAuthorId = article.authorId || article.author;
      const authorTitle = article.author;

      function updateBottomFollowBtn(isSub) {
        bottomFollowBtn.classList.toggle('is-subscribed', isSub);
        bottomFollowBtn.textContent = isSub ? 'Вы подписаны' : 'Подписаться';
        bottomFollowBtn.title = isSub ? 'Отписаться от автора' : 'Подписаться на автора';
      }

      fetch('/api/subscriptions')
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (data && data.success && data.subscriptions && Array.isArray(data.subscriptions.authors)) {
            const isSub = data.subscriptions.authors.some(function (a) {
              return a.id === subAuthorId || a.title === authorTitle;
            });
            updateBottomFollowBtn(isSub);
          }
        })
        .catch(function () {});

      bottomFollowBtn.addEventListener('click', function () {
        fetch('/api/subscriptions/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ targetType: 'author', targetId: subAuthorId, targetTitle: authorTitle })
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
            updateBottomFollowBtn(data.subscribed);
            if (typeof updateSubBtn === 'function') updateSubBtn(data.subscribed);
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
    if (dateEl) {
      dateEl.textContent = article.date || 'Недавно';
      const rawIso = article.created_at || article.createdAt || article.timestamp || article.date;
      if (rawIso) {
        dateEl.title = rawIso;
      }
    }

    const editedEl = document.getElementById('articleEditedStatus');
    if (editedEl) {
      const updatedAt = article.updated_at || article.updatedAt || article.edited_at;
      const createdAt = article.created_at || article.createdAt;
      const isEdited = Boolean(article.is_edited || article.isEdited || (updatedAt && createdAt && updatedAt > createdAt));
      if (isEdited || (updatedAt && (!createdAt || updatedAt > createdAt))) {
        editedEl.textContent = '(ред.)';
        const updatedDisplay = article.updatedDate || updatedAt || '';
        editedEl.title = 'Обновлено: ' + updatedDisplay;
        editedEl.style.display = 'inline-block';
      } else {
        editedEl.style.display = 'none';
        editedEl.textContent = '';
      }
    }

    const readingTimeEl = document.getElementById('articleReadingTime');
    if (readingTimeEl) readingTimeEl.textContent = (article.readingTime || '5 мин') + ' чтения';

    // Header badges container hidden; topics relocated to footer (Issue #107)
    const badgesWrap = document.getElementById('articleBadges');
    if (badgesWrap) {
      badgesWrap.innerHTML = '';
      badgesWrap.style.display = 'none';
    }

    // Cover Image (Issue #88 & Issue #113)
    const coverContainer = document.getElementById('articleCoverContainer');
    const coverImg = document.getElementById('articleCoverImg');
    if (coverContainer && coverImg) {
      if (article.coverImage) {
        coverImg.src = article.coverImage;
        coverImg.alt = article.title || 'Обложка публикации';
        let objPos = '';
        if (article.coverPosition || article.objectPosition) {
          objPos = article.coverPosition || article.objectPosition;
        } else if (typeof article.focalPoint === 'string' && article.focalPoint) {
          objPos = article.focalPoint;
        } else if (article.focalPoint && article.focalPoint.x != null && article.focalPoint.y != null) {
          objPos = article.focalPoint.x + '% ' + article.focalPoint.y + '%';
        }
        if (objPos) {
          coverImg.style.objectPosition = objPos;
        } else {
          coverImg.style.objectPosition = '';
        }
        coverContainer.style.display = 'block';
      } else {
        coverContainer.style.display = 'none';
        coverImg.removeAttribute('src');
        coverImg.style.objectPosition = '';
      }
    }

    // Content Body
    const bodyEl = document.getElementById('articleBodyContent');
    if (bodyEl) {
      const sanitized = sanitizeArticleHtml(article.html || '');
      bodyEl.innerHTML = sanitized || '<p>Текст статьи пуст.</p>';
      preventDuplicateH1InBody(bodyEl, article.title);
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

    // Topics Relocation to Footer (Issue #107)
    const topicsWrap = document.getElementById('articleTopicsWrap');
    const topicsList = document.getElementById('articleTopicsList');
    if (topicsWrap && topicsList) {
      topicsList.innerHTML = '';
      if (window.PublicationConfig && Array.isArray(article.topics) && article.topics.length > 0) {
        article.topics.forEach(function (topicId) {
          const t = window.PublicationConfig.getTopicById(topicId);
          if (t) {
            const topicBadge = document.createElement('a');
            topicBadge.href = 'feed.html?topic=' + encodeURIComponent(t.id);
            topicBadge.className = 'meta-badge topic-badge';
            topicBadge.classList.add('article-topic-item');
            topicBadge.textContent = t.title;
            topicsList.appendChild(topicBadge);
          }
        });
        topicsWrap.style.display = topicsList.children.length > 0 ? 'flex' : 'none';
      } else {
        topicsWrap.style.display = 'none';
      }
    }

    // Sync Bookmark State
    if (article.savesCount !== undefined || article.saves_count !== undefined) {
      currentArticle.savesCount = article.savesCount !== undefined ? article.savesCount : article.saves_count;
      currentArticle.saves_count = currentArticle.savesCount;
    }
    if (article.hasSaved !== undefined || article.isSaved !== undefined) {
      const serverSaved = Boolean(article.hasSaved || article.isSaved);
      currentArticle.hasSaved = serverSaved;
      currentArticle.isSaved = serverSaved;
      if (currentUser && serverSaved) {
        const bms = getBookmarks();
        if (bms.indexOf(article.id) === -1) {
          bms.push(article.id);
          saveBookmarks(bms);
        }
      }
    }
    syncBookmarkButtons(article.id);

    // Sync Report State (Issue #126)
    syncArticleReportStatus(article.id);

    // Sync Like State
    syncLikeButtons(article.likesCount, Boolean(article.hasLiked || article.isLiked));

    // Sync Article Vote Capsules (Top and Bottom)
    syncArticleVoteCapsules(article);

    // Sync Comments Count to Rail & Mobile Action Bar
    syncCommentsCount(article.comments_count !== undefined ? article.comments_count : (article.commentsCount !== undefined ? article.commentsCount : 0));

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
    const commentsSec = document.getElementById('commentsSection') || document.getElementById('comments');
    if (commentsSec) {
      commentsSec.style.display = 'block';
    }
    initComments(article.id);
    initReadingProgressBar();
    loadRelatedArticles(article);

    // Scroll to #comments or #comment-form if specified in URL hash
    const hash = window.location.hash;
    if (hash === '#comments' || hash === '#commentsSection' || hash === '#comment-form' || hash === '#commentForm') {
      setTimeout(function () {
        const formEl = document.getElementById('commentForm');
        const guestPromptEl = document.getElementById('commentGuestPrompt');
        if (hash === '#comment-form' || hash === '#commentForm') {
          if (currentUser && formEl && formEl.style.display !== 'none') {
            formEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            if (typeof expandCommentComposer === 'function') {
              expandCommentComposer(true);
            }
            const ta = document.getElementById('commentTextInput');
            if (ta) ta.focus();
          } else if (!currentUser && guestPromptEl) {
            guestPromptEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            openAuthModal();
          } else {
            const c = document.getElementById('commentsSection') || document.getElementById('comments');
            if (c) c.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        } else {
          const c = document.getElementById('commentsSection') || document.getElementById('comments');
          if (c) c.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 150);
    }
  }

  // --------------------------------------------------------------------------
  // Reading Progress Indicator (Issue #91)
  // --------------------------------------------------------------------------
  let isReadingProgressTicking = false;
  let isReadingProgressBound = false;

  function calculateReadingProgress(articleRect, windowHeight, headerHeight) {
    if (!articleRect || articleRect.height <= 0) return 0;
    const totalDistance = articleRect.height - (windowHeight - headerHeight);
    if (totalDistance <= 0) {
      return articleRect.top <= headerHeight ? 100 : 0;
    }
    const scrolled = headerHeight - articleRect.top;
    const progress = (scrolled / totalDistance) * 100;
    return Math.max(0, Math.min(100, Math.round(progress)));
  }

  function updateReadingProgress() {
    const progressBar = document.getElementById('readingProgressBar');
    if (!progressBar) return;

    const articleEl = document.getElementById('articleBodyContent') || document.getElementById('articleContentWrap') || document.getElementById('articleBody');
    if (!articleEl || articleEl.offsetParent === null || articleEl.style.display === 'none') {
      progressBar.style.width = '0%';
      progressBar.setAttribute('aria-valuenow', '0');
      progressBar.style.opacity = '0';
      return;
    }

    const rect = articleEl.getBoundingClientRect();
    const windowHeight = window.innerHeight || document.documentElement.clientHeight || 800;
    const headerEl = document.getElementById('appHeader');
    const headerHeight = headerEl ? (headerEl.offsetHeight || 60) : 60;

    // Fade out when scrolled below the article into comments/footer
    if (rect.bottom < headerHeight) {
      progressBar.style.opacity = '0';
      return;
    }

    // Hide if article has not entered the reading view yet
    if (rect.top > windowHeight) {
      progressBar.style.width = '0%';
      progressBar.setAttribute('aria-valuenow', '0');
      progressBar.style.opacity = '0';
      return;
    }

    const progress = calculateReadingProgress(rect, windowHeight, headerHeight);
    progressBar.style.width = progress + '%';
    progressBar.setAttribute('aria-valuenow', String(progress));
    progressBar.style.opacity = progress > 0 ? '1' : '0';
  }

  function onReadingProgressTick() {
    if (!isReadingProgressTicking) {
      window.requestAnimationFrame(function () {
        updateReadingProgress();
        isReadingProgressTicking = false;
      });
      isReadingProgressTicking = true;
    }
  }

  function initReadingProgressBar() {
    updateReadingProgress();
    if (!isReadingProgressBound) {
      window.addEventListener('scroll', onReadingProgressTick, { passive: true });
      window.addEventListener('resize', onReadingProgressTick, { passive: true });
      isReadingProgressBound = true;
    }
  }

  window.calculateReadingProgress = calculateReadingProgress;
  window.updateReadingProgress = updateReadingProgress;
  window.initReadingProgressBar = initReadingProgressBar;

  // --------------------------------------------------------------------------
  // Related Articles Recommendations (Issue #92)
  // --------------------------------------------------------------------------
  function getRelatedArticles(articlesList, currentArt) {
    if (!Array.isArray(articlesList) || !currentArt) return [];
    const curId = currentArt.id;
    const curDraftId = currentArt.draftId;
    const curTopics = Array.isArray(currentArt.topics)
      ? currentArt.topics
      : (currentArt.topic ? [currentArt.topic] : []);

    // 1. Strict exclusion of current article
    const candidates = articlesList.filter(function (item) {
      if (!item || !item.id) return false;
      if (item.id === curId || (curDraftId && item.id === curDraftId)) return false;
      if (item.draftId && (item.draftId === curId || item.draftId === curDraftId)) return false;
      return true;
    });

    if (candidates.length === 0) return [];

    // 2. Score candidates by matching topics
    const scored = candidates.map(function (item) {
      const itemTopics = Array.isArray(item.topics)
        ? item.topics
        : (item.topic ? [item.topic] : []);
      let matchCount = 0;
      for (let i = 0; i < itemTopics.length; i++) {
        if (curTopics.indexOf(itemTopics[i]) !== -1) {
          matchCount++;
        }
      }
      return {
        article: item,
        score: matchCount
      };
    });

    // 3. Sort: higher score first, then newest
    scored.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      const dateA = a.article.createdAt || a.article.date || '';
      const dateB = b.article.createdAt || b.article.date || '';
      return dateB.localeCompare(dateA);
    });

    // 4. Return top 2-3 items
    return scored.slice(0, 3).map(function (s) { return s.article; });
  }

  function resolveTopicTitle(topicIdOrTitle) {
    if (!topicIdOrTitle) return '';
    if (window.PublicationConfig && typeof window.PublicationConfig.getTopicById === 'function') {
      const t = window.PublicationConfig.getTopicById(topicIdOrTitle);
      if (t && t.title) return t.title;
    }
    return topicIdOrTitle;
  }

  function renderRelatedCardHtml(item) {
    const title = escapeHtml(item.title || 'Публикация');
    const author = escapeHtml(item.author || 'Автор платформы');
    const date = escapeHtml(item.date || '');
    const readingTime = escapeHtml(item.readingTime || '3 мин');
    const articleUrl = 'article.html?id=' + encodeURIComponent(item.id);

    // Topics chips (up to 2) with human-readable titles
    const topics = Array.isArray(item.topics) ? item.topics : (item.topic ? [item.topic] : []);
    let topicsHtml = '';
    const maxTopics = Math.min(topics.length, 2);
    for (let i = 0; i < maxTopics; i++) {
      const topicTitle = resolveTopicTitle(topics[i]);
      topicsHtml += '<span class="related-topic-chip">' + escapeHtml(topicTitle) + '</span>';
    }

    // Cover image
    let coverHtml = '';
    if (item.coverImage) {
      coverHtml =
        '<div class="related-card-cover-wrap">' +
          '<img src="' + escapeHtml(item.coverImage) + '" alt="' + title + '" class="related-card-cover" loading="lazy">' +
        '</div>';
    } else {
      coverHtml =
        '<div class="related-card-cover-wrap" style="display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, rgba(56,189,248,0.1), rgba(97,136,255,0.1));">' +
          '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--accent-color, #38bdf8)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>' +
            '<path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>' +
          '</svg>' +
        '</div>';
    }

    return (
      '<a href="' + articleUrl + '" class="related-card" aria-label="' + title + '">' +
        coverHtml +
        '<div class="related-card-content">' +
          (topicsHtml ? '<div class="related-card-topics">' + topicsHtml + '</div>' : '') +
          '<h3 class="related-card-title">' + title + '</h3>' +
          '<div class="related-card-meta">' +
            '<span class="related-card-author">' + author + '</span>' +
            '<span class="related-card-dot">&bull;</span>' +
            '<span class="related-card-reading-time">' + readingTime + '</span>' +
          '</div>' +
        '</div>' +
      '</a>'
    );
  }

  function loadRelatedArticles(currentArt) {
    const section = document.getElementById('relatedArticlesSection');
    const grid = document.getElementById('relatedArticlesGrid');
    if (!section || !grid || !currentArt || !currentArt.id) {
      if (section) section.style.display = 'none';
      return;
    }

    function applyRecommendations(articlesList) {
      const related = getRelatedArticles(articlesList, currentArt);
      if (!related || related.length === 0) {
        section.style.display = 'none';
        grid.innerHTML = '';
        return;
      }
      let cardsHtml = '';
      for (let i = 0; i < related.length; i++) {
        cardsHtml += renderRelatedCardHtml(related[i]);
      }
      grid.innerHTML = cardsHtml;
      section.style.display = 'block';
    }

    fetch('/api/articles?limit=12&tab=all')
      .then(function (res) {
        if (!res.ok) throw new Error('FETCH_FAILED');
        return res.json();
      })
      .then(function (data) {
        const list = (data && data.success && Array.isArray(data.articles)) ? data.articles : [];
        if (list.length > 0) {
          applyRecommendations(list);
        } else {
          applyRecommendations(FALLBACK_ARTICLES);
        }
      })
      .catch(function () {
        applyRecommendations(FALLBACK_ARTICLES);
      });
  }

  window.getRelatedArticles = getRelatedArticles;
  window.loadRelatedArticles = loadRelatedArticles;

  function showErrorState(title, desc) {
    const loadingState = document.getElementById('articleLoadingState');
    const contentWrap = document.getElementById('articleContentWrap');
    const errorState = document.getElementById('articleErrorState');
    const errorTitle = document.getElementById('articleErrorTitle');
    const errorDesc = document.getElementById('articleErrorDesc');
    const pb = document.getElementById('readingProgressBar');
    const relSec = document.getElementById('relatedArticlesSection');

    if (relSec) {
      relSec.style.display = 'none';
    }

    if (pb) {
      pb.style.width = '0%';
      pb.style.opacity = '0';
      pb.setAttribute('aria-valuenow', '0');
    }

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
  // 9. User Profile Modal Management
  // --------------------------------------------------------------------------
  function initUserProfileModal() {
    if (window.SmartContractumProfile && typeof window.SmartContractumProfile.initUserProfileModal === 'function') {
      return window.SmartContractumProfile.initUserProfileModal();
    }
  }

  function openUserProfileModal(userId, triggerEl, isSilentRefresh) {
    if (window.SmartContractumProfile && typeof window.SmartContractumProfile.openUserProfileModal === 'function') {
      return window.SmartContractumProfile.openUserProfileModal(userId, triggerEl, isSilentRefresh);
    }
  }

  function closeUserProfileModal() {
    if (window.SmartContractumProfile && typeof window.SmartContractumProfile.closeUserProfileModal === 'function') {
      return window.SmartContractumProfile.closeUserProfileModal();
    }
  }

  // --------------------------------------------------------------------------
  // 8. DOM Ready Entry Point
  // --------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    initTheme();
    initAuthControls();
    initHeaderNotifications();
    initUserProfileModal();
    checkAuthStatus(function () {
      loadArticle();
    });
  });

  if (typeof window !== 'undefined') {
    window.ArticleReader = window.ArticleReader || {};
    window.ArticleReader.preventDuplicateH1InBody = preventDuplicateH1InBody;
    window.ArticleReader.normalizeHeading = normalizeHeading;
    window.ArticleReader.buildTableOfContents = buildTableOfContents;
    window.ArticleReader.toggleBookmark = toggleBookmark;
    window.ArticleReader.syncBookmarkButtons = syncBookmarkButtons;
    window.ArticleReader.isBookmarked = isBookmarked;
    window.ArticleReader.getBookmarks = getBookmarks;
    window.ArticleReader.syncLocalBookmarksWithServer = syncLocalBookmarksWithServer;
    window.ArticleReader.openArticleSharePopover = openArticleSharePopover;
    window.ArticleReader.closeArticleSharePopover = closeArticleSharePopover;
    window.ArticleReader.isArticleSharePopoverOpen = isArticleSharePopoverOpen;
    window.ArticleReader.getArticleShareUrl = getArticleShareUrl;
    window.ArticleReader.getArticleShareTitle = getArticleShareTitle;
    window.ArticleReader.syncArticleReportStatus = syncArticleReportStatus;
    window.ArticleReader.openArticleReportModal = openArticleReportModal;
    window.ArticleReader.markArticleAsReported = markArticleAsReported;
    window.ArticleReader.isArticleReported = isArticleReported;
  }
})();

window.addEventListener('auth:change', function(e) {
  if (typeof window !== 'undefined') {
    if (e.detail && e.detail.user) {
      window.currentUser = e.detail.user;
    } else {
      window.currentUser = null;
    }
  }
  if (window._reportedArticleIds) window._reportedArticleIds.clear();
  if (window._reportedCommentIds) window._reportedCommentIds.clear();
  if (typeof loadUserCommentSubscriptions === 'function') {
    loadUserCommentSubscriptions();
  }
});
