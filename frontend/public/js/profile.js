/**
 * profile.js - Единый общий модуль профиля пользователя SmartContractum
 *
 * Используется совместно в:
 * 1. Ленте публикаций (feed.html, feed.js)
 * 2. Чтении публикации (article.html, article.js)
 * 3. Отдельной странице профиля (profile.html)
 *
 * Обеспечивает:
 * - Мини-карточку автора (#authorCard) около .btn-author-profile: наведение, нажатие, клавиатура
 * - Делегирование событий по .btn-author-profile (data-author-id / data-user-id)
 * - Загрузку данных профиля с бэкенда (/api/users/:id)
 * - Отображение репутации и активности (Рейтинг, мета-строка активности)
 * - Подписку на автора и переход в полный профиль (profile.html?id=:id)
 * - Обновление при голосованиях (событие 'smartcontractum:voted')
 * - Доступность: немодальный диалог, Escape, клик вне карточки, Tab к действиям
 *
 * 100% Offline-First, Zero Emojis, Zero Em Dashes
 */

(function (window) {
  'use strict';

  function escapeHtml(str) {
    if (!str && str !== 0) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function pluralizeRu(n, one, few, many) {
    var count = Math.abs(Number(n) || 0);
    var rem100 = count % 100;
    var rem10 = count % 10;
    if (rem100 >= 11 && rem100 <= 19) {
      return count + ' ' + many;
    }
    if (rem10 === 1) {
      return count + ' ' + one;
    }
    if (rem10 >= 2 && rem10 <= 4) {
      return count + ' ' + few;
    }
    return count + ' ' + many;
  }

  function pluralizePublications(n) {
    return pluralizeRu(n, 'публикация', 'публикации', 'публикаций');
  }

  function pluralizeAnswers(n) {
    return pluralizeRu(n, 'ответ', 'ответа', 'ответов');
  }

  function pluralizeSolutions(n) {
    return pluralizeRu(n, 'решение', 'решения', 'решений');
  }

  /* ==========================================================================
     Author mini card (Issues #271, #272)
     A non-modal popover next to the author name or avatar: opens on hover with a
     delay, on click/tap (pinned) and from the keyboard. No overlay, no focus trap,
     no scroll lock. One card at a time; late responses never replace a newer card.
     ========================================================================== */

  var AUTHOR_CARD_OPEN_DELAY = 250;
  var AUTHOR_CARD_CLOSE_DELAY = 200;
  var AUTHOR_CARD_GAP = 8;
  var AUTHOR_CARD_EDGE = 12;
  var AUTHOR_CARD_CACHE_TTL = 60000;
  // The bell (#272) is wired to the API through SCAuthorBell (#275)
  var AUTHOR_BELL_ENABLED = true;

  var BELL_ICON_OFF = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"></path><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"></path></svg>';
  var BELL_ICON_ON = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"></path><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" fill="none"></path></svg>';
  var STAR_ICON = '<svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path></svg>';

  /* ==========================================================================
     Author notification bell (Issue #275): one client for the mini card, the full
     profile header and the "Авторы с уведомлениями" list. The server state from
     PUT /api/authors/<id>/notifications is the only truth; every change is announced
     with 'smartcontractum:author-notifications' in this tab and, through a
     BroadcastChannel, in other tabs of the same account.
     ========================================================================== */

  var BELL_LABEL_OFF = 'Уведомлять о новых публикациях и вопросах';
  var BELL_LABEL_ON = 'Отключить уведомления автора';
  var BELL_HINT = 'Подписка добавляет автора в вашу ленту. Колокольчик включает уведомления.';
  var BELL_KEPT_ON_UNSUBSCRIBE = 'Уведомления автора остаются включены';
  var BELL_EXCLUDED = 'Автор скрыт из вашей ленты. Сначала уберите его из исключений.';
  var BELL_FAILED = 'Не удалось изменить уведомления. Попробуйте еще раз';
  var BELL_EVENT = 'smartcontractum:author-notifications';
  var SUBSCRIPTION_EVENT = 'smartcontractum:author-subscription';
  var AUTH_INTENT_TTL = 10 * 60 * 1000;

  function currentViewerId() {
    var u = (window.SCAuth && window.SCAuth.currentUser) || window.currentUser || null;
    return u && u.id ? u.id : 'guest';
  }

  var bellChannel = null;
  try {
    if (typeof BroadcastChannel !== 'undefined') bellChannel = new BroadcastChannel('sc-author-state');
  } catch (e) { bellChannel = null; }

  var bellClient = {
    pending: {},
    enabled: {},          // authorId -> bool, last state known from the server for this viewer
    viewer: null,
    count: null,          // number of authors with the bell on (not unread notifications)
    listPromise: null,
    authIntent: null      // {authorId, action, at}: what a guest wanted to do before signing in
  };

  function resetBellState() {
    bellClient.enabled = {};
    bellClient.count = null;
    bellClient.listPromise = null;
    bellClient.viewer = currentViewerId();
  }

  function sameViewer() {
    if (bellClient.viewer !== currentViewerId()) resetBellState();
  }

  function announce(type, detail, fromOtherTab) {
    try {
      window.dispatchEvent(new CustomEvent(type, { detail: Object.assign({ remote: Boolean(fromOtherTab) }, detail) }));
    } catch (e) {}
    if (!fromOtherTab && bellChannel) {
      try { bellChannel.postMessage({ type: type, viewer: currentViewerId(), detail: detail }); } catch (e) {}
    }
  }

  if (bellChannel) {
    bellChannel.onmessage = function (msg) {
      var data = msg && msg.data;
      if (!data || data.viewer !== currentViewerId() || data.viewer === 'guest') return;
      if (data.type === BELL_EVENT && data.detail) {
        sameViewer();
        bellClient.enabled[data.detail.authorId] = Boolean(data.detail.enabled);
        if (typeof data.detail.count === 'number') bellClient.count = data.detail.count;
      }
      if (data.type === BELL_EVENT || data.type === SUBSCRIPTION_EVENT) announce(data.type, data.detail, true);
    };
  }

  function bellError(code, message) {
    var err = new Error(message || BELL_FAILED);
    err.code = code || 'FAILED';
    return err;
  }

  /**
   * Sets the bell for one author. Resolves with {authorId, enabled, isSubscribed, count} from the server.
   * Rejects with err.code: PENDING (a request for this author is in flight), AUTH (sign-in needed),
   * AUTHOR_EXCLUDED, AUTHOR_NOT_FOUND, SELF_NOTIFICATIONS_FORBIDDEN, STALE (the account changed) or FAILED.
   */
  function setAuthorBell(authorId, enabled) {
    sameViewer();
    if (!authorId) return Promise.reject(bellError('FAILED'));
    if (currentViewerId() === 'guest') return Promise.reject(bellError('AUTH', 'Войдите, чтобы включить уведомления'));
    if (bellClient.pending[authorId]) return Promise.reject(bellError('PENDING', 'Запрос уже выполняется'));
    var viewer = currentViewerId();
    bellClient.pending[authorId] = true;
    return fetch('/api/authors/' + encodeURIComponent(authorId) + '/notifications', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ enabled: Boolean(enabled) })
    })
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) { return { status: res.status, data: data || {} }; });
      }, function () {
        throw bellError('FAILED');
      })
      .then(function (r) {
        if (viewer !== currentViewerId()) throw bellError('STALE');
        if (r.status === 401) throw bellError('AUTH', 'Войдите, чтобы включить уведомления');
        if (r.status < 200 || r.status >= 300 || !r.data.success) {
          var code = r.data.code || 'FAILED';
          var text = code === 'AUTHOR_EXCLUDED' ? BELL_EXCLUDED
            : code === 'AUTHOR_NOT_FOUND' ? 'Автор недоступен, уведомления включить нельзя'
            : (r.data.error || BELL_FAILED);
          throw bellError(code, text);
        }
        var result = {
          authorId: authorId,
          enabled: Boolean(r.data.enabled),
          isSubscribed: Boolean(r.data.isSubscribed),
          count: typeof r.data.count === 'number' ? r.data.count : null
        };
        bellClient.enabled[authorId] = result.enabled;
        if (result.count !== null) bellClient.count = result.count;
        // Not pending any more before the views redraw from the announcement
        delete bellClient.pending[authorId];
        announce(BELL_EVENT, result);
        return result;
      })
      .catch(function (err) {
        delete bellClient.pending[authorId];
        throw err;
      });
  }

  /** Number of authors with the bell on and the set of their ids (first page, enough for warnings). */
  function loadBellList(force) {
    sameViewer();
    if (currentViewerId() === 'guest') return Promise.resolve({ count: 0, ids: {} });
    if (bellClient.listPromise && !force) return bellClient.listPromise;
    var viewer = currentViewerId();
    bellClient.listPromise = fetch('/api/user/author-notifications?limit=100', { credentials: 'same-origin' })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (!data || !data.success || viewer !== currentViewerId()) { bellClient.listPromise = null; return { count: null, ids: {} }; }
        var ids = {};
        (data.items || []).forEach(function (item) { ids[item.authorId] = true; bellClient.enabled[item.authorId] = true; });
        bellClient.count = typeof data.count === 'number' ? data.count : (data.items || []).length;
        return { count: bellClient.count, ids: ids };
      })
      .catch(function () { bellClient.listPromise = null; return { count: null, ids: {} }; });
    return bellClient.listPromise;
  }

  function isBellKnownOn(authorId) {
    sameViewer();
    return bellClient.enabled[authorId] === true;
  }

  /**
   * Hiding an author turns their bell off (#273). When the bell is on, the first press only
   * says so on the button; the second press within 5 s confirms. Resolves true to proceed.
   */
  function confirmAuthorExclusion(authorId, btn) {
    return loadBellList(false).then(function (list) {
      var on = isBellKnownOn(authorId) || Boolean(list.ids[authorId]);
      if (!on || !btn) return true;
      if (btn.getAttribute('data-bell-confirm') === authorId) {
        btn.removeAttribute('data-bell-confirm');
        clearTimeout(btn._bellConfirmTimer);
        return true;
      }
      var original = btn.textContent;
      var originalTitle = btn.title;
      btn.setAttribute('data-bell-confirm', authorId);
      btn.textContent = 'Скрыть и отключить уведомления';
      btn.title = 'У автора включены уведомления. Скрытие отключит их. Нажмите еще раз, чтобы подтвердить';
      btn.classList.add('is-confirming');
      clearTimeout(btn._bellConfirmTimer);
      btn._bellConfirmTimer = setTimeout(function () {
        if (btn.getAttribute('data-bell-confirm') !== authorId) return;
        btn.removeAttribute('data-bell-confirm');
        btn.textContent = original;
        btn.title = originalTitle;
        btn.classList.remove('is-confirming');
      }, 5000);
      return false;
    });
  }

  function rememberAuthIntent(authorId, action) {
    bellClient.authIntent = { authorId: authorId, action: action, at: Date.now() };
  }

  /** Returns and clears what a guest wanted to do, if it is still fresh. */
  function takeAuthIntent(authorId) {
    var intent = bellClient.authIntent;
    if (!intent || Date.now() - intent.at > AUTH_INTENT_TTL) { bellClient.authIntent = null; return null; }
    if (authorId && intent.authorId !== authorId) return null;
    bellClient.authIntent = null;
    return intent;
  }

  function peekAuthIntent() {
    var intent = bellClient.authIntent;
    return intent && Date.now() - intent.at <= AUTH_INTENT_TTL ? intent : null;
  }

  function bellButtonState(btn, enabled) {
    if (!btn) return;
    var label = enabled ? BELL_LABEL_ON : BELL_LABEL_OFF;
    btn.classList.toggle('is-on', Boolean(enabled));
    btn.setAttribute('aria-pressed', enabled ? 'true' : 'false');
    btn.setAttribute('aria-label', label);
    btn.title = label;
    btn.innerHTML = enabled ? BELL_ICON_ON : BELL_ICON_OFF;
  }

  if (typeof window !== 'undefined' && window.addEventListener) {
    // Per-account state never moves to another account; a guest's intent survives the sign-in
    window.addEventListener('auth:change', resetBellState);
  }

  var card = null;            // the popover element
  var cardState = {
    trigger: null,            // element the card is anchored to
    userId: null,
    pinned: false,
    openTimer: null,
    closeTimer: null,
    seq: 0,
    abort: null,
    suppressFocusFor: null,   // trigger that must not reopen on focus restore
    status: null,             // {userId, text}: last action result shown in the card
    afterRender: null         // callback after the next successful render (sign-in return)
  };
  var summaryCache = {};
  var isEventsBound = false;

  function viewerId() {
    var u = (window.SCAuth && window.SCAuth.currentUser) || window.currentUser || null;
    return u && u.id ? u.id : 'guest';
  }

  function authorIdOf(el) {
    return el ? (el.getAttribute('data-author-id') || el.getAttribute('data-user-id') || '') : '';
  }

  function triggerFrom(target) {
    var el = target && target.closest ? target.closest('.btn-author-profile') : null;
    return el && authorIdOf(el) ? el : null;
  }

  function isTouchLike(e) {
    return e && (e.pointerType === 'touch' || e.pointerType === 'pen');
  }

  function formatCount(value) {
    if (value === null || value === undefined || value === '' || isNaN(Number(value))) return null;
    var n = Number(value);
    if (Math.abs(n) < 10000) return String(n);
    try {
      return new Intl.NumberFormat('ru-RU', { notation: 'compact', maximumFractionDigits: 1 }).format(n);
    } catch (e) {
      return String(n);
    }
  }

  function formatRating(value) {
    var n = Number(value) || 0;
    if (n > 0) return '+' + n;
    if (n < 0) return '−' + Math.abs(n);
    return '0';
  }

  function ensureCard() {
    if (card && document.body.contains(card)) return card;
    card = document.createElement('div');
    card.id = 'authorCard';
    card.className = 'author-card';
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-labelledby', 'authorCardName');
    card.setAttribute('tabindex', '-1');
    card.hidden = true;
    card.addEventListener('pointerenter', function () { clearTimeout(cardState.closeTimer); });
    card.addEventListener('pointerleave', function (e) {
      if (!isTouchLike(e) && !cardState.pinned) scheduleClose();
    });
    card.addEventListener('click', onCardClick);
    card.addEventListener('keydown', onCardKeydown);
    document.body.appendChild(card);
    return card;
  }

  function setExpanded(trigger, expanded) {
    if (!trigger) return;
    trigger.setAttribute('aria-haspopup', 'dialog');
    if (expanded) {
      trigger.setAttribute('aria-expanded', 'true');
      trigger.setAttribute('aria-controls', 'authorCard');
    } else {
      trigger.setAttribute('aria-expanded', 'false');
      trigger.removeAttribute('aria-controls');
    }
  }

  function position() {
    if (!card || card.hidden || !cardState.trigger) return;
    var trigger = cardState.trigger;
    if (!trigger.isConnected) { closeCard(false); return; }
    var r = trigger.getBoundingClientRect();
    var vw = document.documentElement.clientWidth;
    var vh = window.innerHeight;
    card.style.maxWidth = Math.max(200, vw - AUTHOR_CARD_EDGE * 2) + 'px';
    var cw = card.offsetWidth;
    var ch = card.offsetHeight;
    var below = vh - r.bottom - AUTHOR_CARD_GAP;
    var above = r.top - AUTHOR_CARD_GAP;
    var placeAbove = below < ch + AUTHOR_CARD_EDGE && above > below;
    var top = placeAbove ? r.top - AUTHOR_CARD_GAP - ch : r.bottom + AUTHOR_CARD_GAP;
    top = Math.max(AUTHOR_CARD_EDGE, Math.min(top, vh - ch - AUTHOR_CARD_EDGE));
    var left = Math.min(Math.max(AUTHOR_CARD_EDGE, r.left), vw - cw - AUTHOR_CARD_EDGE);
    card.style.top = Math.round(top) + 'px';
    card.style.left = Math.round(Math.max(AUTHOR_CARD_EDGE, left)) + 'px';
    card.setAttribute('data-side', placeAbove ? 'top' : 'bottom');
  }

  function scheduleOpen(trigger) {
    clearTimeout(cardState.openTimer);
    clearTimeout(cardState.closeTimer);
    if (cardState.trigger === trigger && card && !card.hidden) return;
    cardState.openTimer = setTimeout(function () {
      cardState.openTimer = null;
      if (trigger.isConnected) openCard(trigger, { pinned: false });
    }, AUTHOR_CARD_OPEN_DELAY);
  }

  function scheduleClose() {
    clearTimeout(cardState.openTimer);
    cardState.openTimer = null;
    if (!card || card.hidden || cardState.pinned) return;
    clearTimeout(cardState.closeTimer);
    cardState.closeTimer = setTimeout(function () {
      cardState.closeTimer = null;
      if (!cardState.pinned) closeCard(false);
    }, AUTHOR_CARD_CLOSE_DELAY);
  }

  function openCard(trigger, opts) {
    opts = opts || {};
    var userId = authorIdOf(trigger);
    if (!userId) return;
    clearTimeout(cardState.openTimer);
    clearTimeout(cardState.closeTimer);
    if (cardState.trigger && cardState.trigger !== trigger) setExpanded(cardState.trigger, false);
    var sameCard = card && !card.hidden && cardState.trigger === trigger;
    cardState.trigger = trigger;
    cardState.pinned = cardState.pinned && sameCard ? true : Boolean(opts.pinned);
    setExpanded(trigger, true);
    ensureCard();
    if (!sameCard || cardState.userId !== userId) {
      if (cardState.status && cardState.status.userId !== userId) cardState.status = null;
      cardState.userId = userId;
      loadSummary(userId, false);
    }
    card.hidden = false;
    card.classList.toggle('is-pinned', cardState.pinned);
    position();
    if (opts.focus === 'first') {
      var first = card.querySelector('a[href], button:not([disabled])');
      (first || card).focus({ preventScroll: true });
    } else if (opts.focus === 'card') {
      card.focus({ preventScroll: true });
    }
  }

  function closeCard(restoreFocus) {
    clearTimeout(cardState.openTimer);
    clearTimeout(cardState.closeTimer);
    cardState.openTimer = cardState.closeTimer = null;
    if (cardState.abort) {
      try { cardState.abort.abort(); } catch (e) {}
      cardState.abort = null;
    }
    cardState.seq++;
    var trigger = cardState.trigger;
    var focusWasInside = card && card.contains(document.activeElement);
    if (card) card.hidden = true;
    setExpanded(trigger, false);
    cardState.trigger = null;
    cardState.userId = null;
    cardState.pinned = false;
    if (trigger && trigger.isConnected && (restoreFocus || focusWasInside)) {
      cardState.suppressFocusFor = trigger;
      try { trigger.focus({ preventScroll: true }); } catch (e) {}
    }
  }

  function loadSummary(userId, force) {
    var key = viewerId() + '|' + userId;
    var cached = summaryCache[key];
    if (!force && cached && Date.now() - cached.at < AUTHOR_CARD_CACHE_TTL) {
      render(cached.data, userId);
      return;
    }
    var seq = ++cardState.seq;
    if (cardState.abort) {
      try { cardState.abort.abort(); } catch (e) {}
    }
    cardState.abort = typeof AbortController !== 'undefined' ? new AbortController() : null;
    renderLoading();
    // Compact summary from #273 (about 0.6 KB instead of the full profile)
    fetch('/api/users/' + encodeURIComponent(userId) + '/summary', cardState.abort ? { signal: cardState.abort.signal } : {})
      .then(function (res) {
        if (res.status === 404) return { notFound: true };
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (seq !== cardState.seq || cardState.userId !== userId) return;
        if (data && data.notFound) { renderMessage('Профиль не найден', false); return; }
        var p = data && (data.summary || data.profile || data.user || data);
        if (!data || !data.success || !p) throw new Error('Bad response');
        summaryCache[key] = { at: Date.now(), data: p };
        render(p, userId);
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') return;
        if (seq !== cardState.seq || cardState.userId !== userId) return;
        renderMessage('Не удалось загрузить профиль', true);
      });
  }

  function renderLoading() {
    card.setAttribute('aria-busy', 'true');
    card.innerHTML =
      '<div class="author-card-head">' +
        '<span class="author-card-avatar author-card-skeleton"></span>' +
        '<span class="author-card-ident"><span class="author-card-skeleton author-card-skeleton-line" id="authorCardName">Загрузка профиля</span></span>' +
      '</div>' +
      '<div class="author-card-stats author-card-skeleton author-card-skeleton-block"></div>';
    position();
  }

  function renderMessage(text, canRetry) {
    card.removeAttribute('aria-busy');
    card.innerHTML =
      '<p class="author-card-message" id="authorCardName" role="status">' + escapeHtml(text) + '</p>' +
      (canRetry ? '<button type="button" class="author-card-btn author-card-retry">Повторить</button>' : '');
    position();
  }

  function stat(value, label) {
    var shown = formatCount(value);
    var exact = shown === null ? 'нет данных' : String(Number(value));
    return '<div class="author-card-stat" title="' + escapeHtml(label + ': ' + exact) + '">' +
      '<dt>' + escapeHtml(label) + '</dt>' +
      '<dd>' + escapeHtml(shown === null ? 'н/д' : shown) + '</dd>' +
    '</div>';
  }

  function bellHtml(enabled, userId, p) {
    if (!AUTHOR_BELL_ENABLED) return '';
    // An unavailable author cannot be turned on; an enabled bell can always be turned off
    if (!enabled && p && p.canNotify === false && viewerId() !== 'guest') return '';
    var label = enabled ? BELL_LABEL_ON : BELL_LABEL_OFF;
    var busy = bellClient.pending[userId];
    return '<button type="button" class="author-card-btn author-card-bell' + (enabled ? ' is-on' : '') + '"' +
      ' aria-pressed="' + (enabled ? 'true' : 'false') + '" aria-label="' + label + '" title="' + label + '"' +
      (busy ? ' disabled aria-busy="true"' : '') +
      ' data-author-id="' + escapeHtml(userId) + '">' + (enabled ? BELL_ICON_ON : BELL_ICON_OFF) + '</button>';
  }

  function setCardStatus(userId, text) {
    cardState.status = text ? { userId: userId, text: text } : null;
    var el = card && card.querySelector('.author-card-status');
    if (el && cardState.userId === userId) el.textContent = text || '';
  }

  function subscribeLabel(subscribed) {
    return subscribed ? 'Вы подписаны' : 'Подписаться';
  }

  function render(p, userId) {
    var focusedClass = null;
    if (card.contains(document.activeElement) && document.activeElement !== card) {
      focusedClass = ['author-card-subscribe', 'author-card-bell', 'author-card-profile', 'author-card-name']
        .filter(function (c) { return document.activeElement.classList.contains(c); })[0] || null;
    }
    card.removeAttribute('aria-busy');
    var name = p.name || userId;
    var initials = p.initials || (name ? name.split(' ').map(function (s) { return s[0] || ''; }).join('').slice(0, 2).toUpperCase() : 'SC');
    var profileUrl = 'profile.html?id=' + encodeURIComponent(userId);
    var me = viewerId();
    var isOwn = Boolean(p.isOwnProfile || (me !== 'guest' && me === userId));
    var subscribed = !isOwn && Boolean(p.isSubscribed);
    var bellOn = !isOwn && Boolean(p.authorNotificationsEnabled);
    var rating = p.rating !== undefined ? p.rating : (p.stats && p.stats.rating);
    var avatar = p.avatar
      ? '<img src="' + escapeHtml(p.avatar) + '" alt="" class="author-card-avatar-img" onerror="this.remove()">'
      : '';
    var bio = (p.bio || '').trim();

    var actions;
    if (isOwn) {
      actions = '<p class="author-card-own">Это ваш профиль</p>' +
        '<a class="author-card-btn author-card-profile" href="' + escapeHtml(profileUrl) + '">Перейти в профиль</a>';
    } else {
      actions =
        '<button type="button" class="author-card-btn author-card-subscribe' + (subscribed ? ' is-subscribed' : '') + '"' +
          ' aria-pressed="' + (subscribed ? 'true' : 'false') + '" data-author-id="' + escapeHtml(userId) + '"' +
          ' title="' + (subscribed ? 'Отписаться от автора' : 'Добавить автора в «Мою ленту»') + '">' + subscribeLabel(subscribed) + '</button>' +
        bellHtml(bellOn, userId, p) +
        '<a class="author-card-btn author-card-profile" href="' + escapeHtml(profileUrl) + '">Перейти в профиль</a>';
    }

    card.innerHTML =
      '<div class="author-card-head">' +
        '<a class="author-card-avatar" href="' + escapeHtml(profileUrl) + '" tabindex="-1" aria-hidden="true">' +
          '<span class="author-card-initials">' + escapeHtml(initials) + '</span>' + avatar +
        '</a>' +
        '<div class="author-card-ident">' +
          '<a class="author-card-name" id="authorCardName" href="' + escapeHtml(profileUrl) + '">' + escapeHtml(name) + '</a>' +
          (rating === undefined || rating === null ? '' :
            '<span class="author-card-rating' + (Number(rating) < 0 ? ' is-negative' : '') + '" title="Рейтинг ' + escapeHtml(String(rating)) + '. Сумма оценок публикаций, ответов и комментариев. Лайки не учитываются">' +
              STAR_ICON + '<span>' + escapeHtml(formatRating(rating)) + '</span>' +
            '</span>') +
        '</div>' +
      '</div>' +
      (bio ? '<p class="author-card-bio">' + escapeHtml(bio) + '</p>' : '') +
      '<dl class="author-card-stats">' +
        stat(p.followersCount, 'Подписчики') +
        stat(p.publicationsCount, 'Публикации') +
        stat(p.questionsCount, 'Вопросы') +
        stat(p.commentsCount, 'Комментарии') +
      '</dl>' +
      '<div class="author-card-actions">' + actions + '</div>' +
      (isOwn ? '' : '<p class="author-card-hint">' + escapeHtml(BELL_HINT) + '</p>') +
      '<p class="author-card-status" role="status" aria-live="polite">' +
        escapeHtml(cardState.status && cardState.status.userId === userId ? cardState.status.text : '') + '</p>';
    if (focusedClass) {
      var again = card.querySelector('.' + focusedClass);
      if (again) { try { again.focus({ preventScroll: true }); } catch (e) {} }
    }
    position();
    if (cardState.afterRender) {
      var after = cardState.afterRender;
      cardState.afterRender = null;
      after(p);
    }
  }

  function requireAuth(userId, action) {
    if (userId && action) rememberAuthIntent(userId, action);
    closeCard(false);
    if (window.SCAuth && typeof window.SCAuth.openModal === 'function') {
      window.SCAuth.openModal('login');
      return;
    }
    var authModal = document.getElementById('authModal');
    if (authModal) authModal.style.display = 'flex';
  }

  function toggleSubscription(btn) {
    var userId = btn.getAttribute('data-author-id');
    if (!userId || btn.disabled) return;
    if (viewerId() === 'guest') { requireAuth(userId, 'subscribe'); return; }
    var wasSubscribed = btn.classList.contains('is-subscribed');
    var viewer = viewerId();
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    fetch('/api/subscriptions/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ targetType: 'author', targetId: userId, action: wasSubscribed ? 'unsubscribe' : 'subscribe' })
    })
      .then(function (res) {
        if (res.status === 401) { requireAuth(userId, 'subscribe'); return null; }
        return res.json();
      })
      .then(function (data) {
        if (data === null) return;
        if (!data || !data.success) throw new Error('subscribe failed');
        if (viewer !== viewerId()) return;
        var subscribed = Boolean(data.subscribed || data.isSubscribed);
        var key = viewerId() + '|' + userId;
        var bellOn = summaryCache[key] ? Boolean(summaryCache[key].data.authorNotificationsEnabled) : isBellKnownOn(userId);
        setCardStatus(userId, !subscribed && bellOn ? BELL_KEPT_ON_UNSUBSCRIBE : '');
        announce(SUBSCRIPTION_EVENT, { authorId: userId, subscribed: subscribed, followersCount: data.followersCount });
      })
      .catch(function () {
        if (!btn.isConnected) return;
        btn.disabled = false;
        btn.removeAttribute('aria-busy');
        btn.title = 'Не удалось изменить подписку. Попробуйте еще раз';
        setCardStatus(userId, 'Не удалось изменить подписку. Попробуйте еще раз');
      });
  }

  function toggleBell(btn) {
    var userId = btn.getAttribute('data-author-id');
    if (!userId || btn.disabled) return;
    if (viewerId() === 'guest') { requireAuth(userId, 'bell'); return; }
    var key = viewerId() + '|' + userId;
    var cached = summaryCache[key] && summaryCache[key].data;
    var wasOn = btn.classList.contains('is-on');
    if (!wasOn && cached && cached.isExcluded) { setCardStatus(userId, BELL_EXCLUDED); return; }
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    setCardStatus(userId, '');
    setAuthorBell(userId, !wasOn)
      .then(function (result) {
        setCardStatus(userId, result.enabled ? 'Уведомления автора включены' : 'Уведомления автора отключены');
      })
      .catch(function (err) {
        if (err.code === 'PENDING' || err.code === 'STALE') return;
        if (err.code === 'AUTH') { requireAuth(userId, 'bell'); return; }
        if (err.code === 'AUTHOR_EXCLUDED' && summaryCache[key]) summaryCache[key].data.isExcluded = true;
        setCardStatus(userId, err.message || BELL_FAILED);
        // The button shows what the server last confirmed, never an assumed state
        if (cardState.userId === userId && summaryCache[key]) render(summaryCache[key].data, userId);
        else if (btn.isConnected) { btn.disabled = false; btn.removeAttribute('aria-busy'); }
      });
  }

  function applyAuthorState(detail) {
    if (!detail || !detail.authorId) return;
    var key = viewerId() + '|' + detail.authorId;
    var entry = summaryCache[key];
    if (entry) {
      if (detail.enabled !== undefined) entry.data.authorNotificationsEnabled = Boolean(detail.enabled);
      if (detail.isSubscribed !== undefined) entry.data.isSubscribed = Boolean(detail.isSubscribed);
      if (detail.subscribed !== undefined) entry.data.isSubscribed = Boolean(detail.subscribed);
      if (detail.followersCount !== undefined && detail.followersCount !== null) entry.data.followersCount = detail.followersCount;
    }
    if (card && !card.hidden && cardState.userId === detail.authorId) {
      if (entry) render(entry.data, detail.authorId);
      else loadSummary(detail.authorId, true);
    }
  }

  /** After signing in from the card: reopen it for the same author and ask to confirm, never act silently. */
  function resumeAuthIntent() {
    var intent = peekAuthIntent();
    if (!intent || viewerId() === 'guest') return;
    var selector = '.btn-author-profile[data-author-id="' + String(intent.authorId).replace(/["\\]/g, '') + '"]';
    var trigger = Array.prototype.filter.call(document.querySelectorAll(selector), function (el) {
      return el.getClientRects().length > 0;
    })[0];
    if (!trigger) return;
    takeAuthIntent(intent.authorId);
    cardState.afterRender = function (p) {
      if (p.isOwnProfile) { setCardStatus(intent.authorId, 'Это ваш профиль'); return; }
      var target = card.querySelector(intent.action === 'bell' ? '.author-card-bell' : '.author-card-subscribe');
      setCardStatus(intent.authorId, 'Вы вошли. Нажмите кнопку еще раз, чтобы подтвердить действие');
      if (target) { try { target.focus({ preventScroll: true }); } catch (e) {} }
    };
    openCard(trigger, { pinned: true });
  }

  function onCardClick(e) {
    // Clicks inside the card never reach the card or link underneath
    e.stopPropagation();
    var sub = e.target.closest('.author-card-subscribe');
    if (sub) { e.preventDefault(); toggleSubscription(sub); return; }
    var bell = e.target.closest('.author-card-bell');
    if (bell) { e.preventDefault(); toggleBell(bell); return; }
    var retry = e.target.closest('.author-card-retry');
    if (retry && cardState.userId) { e.preventDefault(); loadSummary(cardState.userId, true); return; }
    if (!cardState.pinned) {
      cardState.pinned = true;
      card.classList.add('is-pinned');
    }
  }

  function focusables(root) {
    return Array.prototype.filter.call(
      root.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'),
      function (el) { return el.getClientRects().length > 0 && !el.closest('[hidden]') && el.getAttribute('aria-hidden') !== 'true'; }
    );
  }

  function focusAfter(trigger) {
    var all = focusables(document).filter(function (el) { return !card.contains(el); });
    var i = all.indexOf(trigger);
    var next = i >= 0 ? all[i + 1] : null;
    closeCard(false);
    if (next) next.focus();
  }

  function onCardKeydown(e) {
    if (e.key === 'Escape') { e.preventDefault(); closeCard(true); return; }
    if (e.key !== 'Tab') return;
    var items = focusables(card);
    if (!items.length) return;
    var first = items[0];
    var last = items[items.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === card)) {
      e.preventDefault();
      var trigger = cardState.trigger;
      cardState.suppressFocusFor = trigger;
      if (trigger) trigger.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      focusAfter(cardState.trigger);
    }
  }

  function bindAuthorCardEvents() {
    if (isEventsBound) return;
    isEventsBound = true;

    document.addEventListener('pointerover', function (e) {
      if (isTouchLike(e)) return;
      var trigger = triggerFrom(e.target);
      if (!trigger || (e.relatedTarget && trigger.contains(e.relatedTarget))) return;
      scheduleOpen(trigger);
    });
    document.addEventListener('pointerout', function (e) {
      if (isTouchLike(e)) return;
      var trigger = triggerFrom(e.target);
      if (!trigger || (e.relatedTarget && (trigger.contains(e.relatedTarget) || (card && card.contains(e.relatedTarget))))) return;
      if (cardState.openTimer) { clearTimeout(cardState.openTimer); cardState.openTimer = null; }
      if (cardState.trigger === trigger) scheduleClose();
    });

    // Click / tap: open and pin; a second click on the same trigger closes. Capture phase so
    // the card underneath (a feed card that opens the material) does not react.
    document.addEventListener('click', function (e) {
      var trigger = triggerFrom(e.target);
      if (!trigger) return;
      e.preventDefault();
      e.stopPropagation();
      if (card && !card.hidden && cardState.trigger === trigger && cardState.pinned) {
        closeCard(false);
        return;
      }
      var byKeyboard = e.detail === 0;
      openCard(trigger, { pinned: true, focus: byKeyboard ? 'first' : null });
    }, true);

    document.addEventListener('keydown', function (e) {
      var trigger = triggerFrom(e.target);
      if (trigger && (e.key === 'Enter' || e.key === ' ') && trigger.tagName !== 'BUTTON') {
        e.preventDefault();
        openCard(trigger, { pinned: true, focus: 'first' });
        return;
      }
      if (trigger && e.key === 'Tab' && !e.shiftKey && card && !card.hidden && cardState.trigger === trigger) {
        var items = focusables(card);
        if (items.length) { e.preventDefault(); items[0].focus(); }
        return;
      }
      if (e.key === 'Escape' && card && !card.hidden && (!e.target.closest || !e.target.closest('#authorCard'))) {
        closeCard(Boolean(trigger));
      }
    });

    // Keyboard focus shows the card without moving focus into it
    document.addEventListener('focusin', function (e) {
      var trigger = triggerFrom(e.target);
      if (!trigger) return;
      if (cardState.suppressFocusFor === trigger) return;
      var visible = false;
      try { visible = trigger.matches(':focus-visible'); } catch (err) { visible = false; }
      if (visible) scheduleOpen(trigger);
    });
    document.addEventListener('focusout', function (e) {
      var trigger = triggerFrom(e.target);
      if (trigger && cardState.suppressFocusFor === trigger) cardState.suppressFocusFor = null;
      var next = e.relatedTarget;
      if (!card || card.hidden || cardState.pinned) return;
      if (next && (card.contains(next) || next === cardState.trigger)) return;
      if (trigger || (e.target.closest && e.target.closest('#authorCard'))) scheduleClose();
    });

    // Tap or click outside closes
    document.addEventListener('pointerdown', function (e) {
      if (!card || card.hidden) return;
      if (card.contains(e.target) || triggerFrom(e.target) === cardState.trigger) return;
      closeCard(false);
    }, true);

    var reposition = function () { if (card && !card.hidden) window.requestAnimationFrame(position); };
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);

    // Personal state must not move between accounts
    window.addEventListener('auth:change', function (e) {
      summaryCache = {};
      cardState.status = null;
      if (card && !card.hidden) closeCard(false);
      if (e && e.detail && e.detail.authenticated) resumeAuthIntent();
    });

    // Every visible copy of an author follows actions made elsewhere (card, profile, list, other tabs)
    window.addEventListener(BELL_EVENT, function (e) { applyAuthorState(e.detail); });
    window.addEventListener(SUBSCRIPTION_EVENT, function (e) { applyAuthorState(e.detail); });

    window.addEventListener('smartcontractum:voted', function () {
      summaryCache = {};
      if (card && !card.hidden && cardState.userId) loadSummary(cardState.userId, true);
    });

    // Feed pagination and re-renders can remove the anchor
    if (typeof MutationObserver !== 'undefined') {
      new MutationObserver(function () {
        if (card && !card.hidden && cardState.trigger && !cardState.trigger.isConnected) closeCard(false);
      }).observe(document.body, { childList: true, subtree: true });
    }
  }

  function initUserProfileModal() {
    // Kept name for existing callers: initialises the author mini card
    bindAuthorCardEvents();
  }

  function openUserProfileModal(userId, triggerEl) {
    var trigger = triggerEl || document.querySelector('.btn-author-profile[data-author-id="' + String(userId).replace(/"/g, '') + '"]');
    if (trigger) openCard(trigger, { pinned: true });
  }

  function closeUserProfileModal() {
    closeCard(false);
  }

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initUserProfileModal);
    } else {
      initUserProfileModal();
    }
  }

  function aggregateUserTopics(publications, options) {
    options = options || {};
    const maxTopics = options.maxTopics || 6;
    if (!Array.isArray(publications) || publications.length === 0) {
      return [];
    }

    const counts = {};
    publications.forEach(function (pub) {
      if (!pub) return;
      let topicsList = [];
      if (Array.isArray(pub.topics) && pub.topics.length > 0) {
        topicsList = pub.topics;
      } else if (pub.topic) {
        topicsList = [pub.topic];
      } else if (pub.publicationSettings && pub.publicationSettings.topics) {
        topicsList = pub.publicationSettings.topics;
      }

      topicsList.forEach(function (t) {
        if (!t) return;
        const topicId = typeof t === 'object' ? (t.id || t.title) : String(t);
        if (topicId) {
          counts[topicId] = (counts[topicId] || 0) + 1;
        }
      });
    });

    const result = Object.keys(counts).map(function (tid) {
      let title = tid;
      if (window.PublicationConfig && typeof window.PublicationConfig.getTopicById === 'function') {
        const conf = window.PublicationConfig.getTopicById(tid);
        if (conf && conf.title) {
          title = conf.title;
        }
      }
      return {
        id: tid,
        title: title,
        count: counts[tid]
      };
    });

    result.sort(function (a, b) {
      return b.count - a.count;
    });

    return result.slice(0, maxTopics);
  }

  window.openUserProfileModal = openUserProfileModal;
  window.closeUserProfileModal = closeUserProfileModal;
  window.SmartContractumProfile = {
    initUserProfileModal: initUserProfileModal,
    openUserProfileModal: openUserProfileModal,
    closeUserProfileModal: closeUserProfileModal,
    openAuthorCard: function (trigger, opts) { openCard(trigger, opts || { pinned: true }); },
    closeAuthorCard: closeUserProfileModal,
    authorCardDelays: { open: AUTHOR_CARD_OPEN_DELAY, close: AUTHOR_CARD_CLOSE_DELAY },
    aggregateUserTopics: aggregateUserTopics
  };
  window.SCAuthorBell = {
    set: setAuthorBell,
    loadList: loadBellList,
    isKnownOn: isBellKnownOn,
    confirmExclusion: confirmAuthorExclusion,
    rememberAuthIntent: rememberAuthIntent,
    takeAuthIntent: takeAuthIntent,
    applyButtonState: bellButtonState,
    announceSubscription: function (detail) { announce(SUBSCRIPTION_EVENT, detail); },
    // The server turned the bell off as a side effect (hiding the author, #273)
    noteOff: function (authorId) {
      if (!authorId || bellClient.enabled[authorId] === false) return;
      var wasOn = bellClient.enabled[authorId] === true;
      bellClient.enabled[authorId] = false;
      if (wasOn && typeof bellClient.count === 'number') bellClient.count = Math.max(0, bellClient.count - 1);
      announce(BELL_EVENT, { authorId: authorId, enabled: false, count: wasOn ? bellClient.count : null });
    },
    isPending: function (authorId) { return Boolean(bellClient.pending[authorId]); },
    count: function () { return bellClient.count; },
    labels: { off: BELL_LABEL_OFF, on: BELL_LABEL_ON, hint: BELL_HINT, keptOnUnsubscribe: BELL_KEPT_ON_UNSUBSCRIBE,
              excluded: BELL_EXCLUDED, failed: BELL_FAILED },
    icons: { off: BELL_ICON_OFF, on: BELL_ICON_ON },
    events: { bell: BELL_EVENT, subscription: SUBSCRIPTION_EVENT }
  };

})(typeof window !== 'undefined' ? window : this);
