(function() {
  'use strict';

  const companyId = new URLSearchParams(window.location.search).get('id') || '';
  const $ = (id) => document.getElementById(id);
  const state = {
    company: null,
    user: null,
    tab: 'publications',
    directions: {},
    subsOffset: 0,
    entities: null
  };

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function initials(name) {
    const clean = String(name || '').replace(/^(ООО|АО|ПАО|ЗАО|ИП)\s+/i, '').replace(/[«»"]/g, '').trim();
    const parts = clean.split(/\s+/).filter(Boolean);
    if (!parts.length) return 'SC';
    return (parts.length === 1 ? parts[0].slice(0, 2) : parts[0][0] + parts[1][0]).toUpperCase();
  }

  function formatDate(iso) {
    const d = new Date(iso);
    return isNaN(d.getTime()) ? '' : d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
  }

  function plural(n, one, few, many) {
    const m10 = n % 10, m100 = n % 100;
    if (m10 === 1 && m100 !== 11) return one;
    if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
    return many;
  }

  function websiteHref(url) {
    if (!url) return '';
    return /^https?:\/\//i.test(url) ? url : 'https://' + url;
  }

  function toast(message, isError) {
    const el = $('companyToast');
    el.textContent = message;
    el.className = 'co-toast' + (isError ? ' is-error' : '');
    el.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { el.hidden = true; }, 3000);
  }

  async function api(method, path, body) {
    const res = await fetch(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body)
    });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data };
  }

  /* ---------------------------------------------------------------- load */

  async function load() {
    if (!companyId) return showState('Компания не указана', 'Откройте компанию из ленты или каталога блогов.');
    const [profile, directions] = await Promise.all([
      api('GET', '/api/companies/' + encodeURIComponent(companyId) + '/profile'),
      api('GET', '/api/directions')
    ]);
    (directions.data.directions || []).forEach(d => { state.directions[d.id] = d.title; });
    if (!profile.ok) {
      return profile.status === 404
        ? showState('Компания не найдена', 'Возможно, ссылка устарела или компания удалена.')
        : showState('Не удалось загрузить компанию', 'Обновите страницу через минуту.');
    }
    state.company = profile.data.company;
    document.title = state.company.name + ' - SmartContractum';
    render();
    loadTab();
  }

  function showState(title, text) {
    $('companyView').hidden = true;
    $('companyState').innerHTML = `
      <div class="co-card co-empty-state">
        <h1 class="co-empty-title">${escapeHtml(title)}</h1>
        <p class="co-empty-text">${escapeHtml(text)}</p>
        <a class="co-btn co-btn-primary" href="feed.html?tab=companies">Все компании</a>
      </div>`;
  }

  /* ---------------------------------------------------------------- render */

  function render() {
    const c = state.company;
    $('companyState').innerHTML = '';
    $('companyView').hidden = false;

    const logo = $('companyLogo');
    logo.innerHTML = c.logo
      ? `<img src="${escapeHtml(c.logo)}" alt="" onerror="this.remove()">`
      : '';
    logo.dataset.initials = initials(c.name);

    const cover = $('companyCover');
    cover.classList.toggle('media-has-image', Boolean(c.cover));
    cover.style.backgroundImage = c.cover ? `url("${encodeURI(c.cover)}")` : '';
    cover.style.backgroundPosition = 'center';
    renderMediaControls(c);
    $('companyName').textContent = c.name;
    $('companyVerified').hidden = !c.isVerified;
    $('companySpecialization').textContent = c.specialization || '';
    $('companyDescription').textContent = c.description || '';

    const actions = [];
    if (c.canEdit) {
      actions.push(`<a class="co-btn co-btn-ghost" id="btnEditCompany" href="settings.html#company=${encodeURIComponent(c.id)}">${ICON_PEN}Редактировать</a>`);
    }
    if (c.canPublish) {
      actions.push(`<a class="co-btn co-btn-ghost" href="editor.html?companyId=${encodeURIComponent(c.id)}">Написать от имени компании</a>`);
    }
    if (!c.isOwner) {
      actions.push(`<button type="button" class="co-btn ${c.isSubscribed ? 'co-btn-ghost is-subscribed' : 'co-btn-primary'}" id="btnSubscribe">${c.isSubscribed ? 'Вы подписаны' : 'Подписаться'}</button>`);
    }
    actions.push('<button type="button" class="co-icon-btn co-icon-outline" id="btnCopyLink" title="Скопировать ссылку" aria-label="Скопировать ссылку"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg></button>');
    $('companyActions').innerHTML = actions.join('');

    const s = c.stats;
    $('companyStats').innerHTML = [
      ['rating', s.rating, 'Рейтинг'],
      ['publications', s.publications, plural(s.publications, 'Публикация', 'Публикации', 'Публикаций')],
      ['questions', s.questions, plural(s.questions, 'Вопрос', 'Вопроса', 'Вопросов')],
      ['subscribers', s.subscribers, plural(s.subscribers, 'Подписчик', 'Подписчика', 'Подписчиков')],
      ['following', s.following, plural(s.following, 'Подписка', 'Подписки', 'Подписок')]
    ].map(([key, value, label]) => `<div class="co-stat${key === 'rating' ? ' is-accent' : ''}"><b>${value}</b><span>${label}</span></div>`).join('');

    document.querySelectorAll('[data-count]').forEach(el => {
      const n = s[el.dataset.count] || 0;
      el.textContent = n ? String(n) : '';
    });

    const aboutText = (c.about || c.description || '').trim();
    $('companyAbout').innerHTML = aboutText
      ? aboutText.split(/\n\s*\n/).map(p => `<p>${escapeHtml(p).replace(/\n/g, '<br>')}</p>`).join('')
      : '<p class="co-muted">Компания пока не рассказала о себе подробнее.</p>';
    const facts = [];
    if (c.website) facts.push(['Сайт', `<a href="${escapeHtml(websiteHref(c.website))}" target="_blank" rel="noopener nofollow">${escapeHtml(c.website.replace(/^https?:\/\//i, '').replace(/\/$/, ''))}</a>`]);
    if (c.owner) facts.push(['Владелец', `<a href="profile.html?id=${encodeURIComponent(c.owner.id)}">${escapeHtml(c.owner.name)}</a>`]);
    if (c.stats.members) facts.push(['Авторы', String(c.stats.members)]);
    facts.push(['На платформе', escapeHtml(formatDate(c.createdAt))]);
    $('companyFacts').innerHTML = facts.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');

    const dirs = c.directions || [];
    $('companyDirectionsCard').hidden = !dirs.length;
    $('companyDirections').innerHTML = dirs.map(d => `<span class="co-chip">${escapeHtml(state.directions[d] || d)}</span>`).join('');
  }

  /* ---------------------------------------------------------------- logo and cover */

  const ICON_IMAGE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/></svg>';
  const ICON_TRASH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>';
  const ICON_CAMERA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>';
  const ICON_PEN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>';

  function renderMediaControls(c) {
    document.querySelectorAll('.co-media-control').forEach(n => n.remove());
    if (!c.canEdit || !window.SCMediaCrop) return;
    $('companyCover').style.position = 'relative';
    $('companyCover').insertAdjacentHTML('beforeend', `
      <div class="media-edit-bar co-media-control">
        <button type="button" class="media-edit-btn" data-media="cover">${ICON_IMAGE}<span>${c.cover ? 'Изменить обложку' : 'Добавить обложку'}</span></button>
        ${c.cover ? `<button type="button" class="media-edit-btn" data-media-remove="cover" aria-label="Удалить обложку">${ICON_TRASH}</button>` : ''}
      </div>`);
    document.querySelector('.co-logo-wrap').insertAdjacentHTML('beforeend', `
      <button type="button" class="co-media-control co-logo-edit" data-media="logo" aria-label="${c.logo ? 'Изменить логотип' : 'Добавить логотип'}" title="${c.logo ? 'Изменить логотип' : 'Добавить логотип'}">${ICON_CAMERA}</button>`);
  }

  async function editMedia(kind) {
    const picked = await window.SCMediaCrop.open(kind === 'logo'
      ? { title: 'Логотип компании', aspect: 1, outputWidth: 400, outputHeight: 400, minWidth: 64, minHeight: 64 }
      : { title: 'Обложка компании', aspect: 3, outputWidth: 1500, outputHeight: 500, minWidth: 600, minHeight: 200 });
    if (!picked) return;
    await saveMedia({ kind, url: picked.url, focal: picked.focal });
  }

  async function saveMedia(payload) {
    const { ok, data } = await api('POST', `/api/companies/${encodeURIComponent(companyId)}/media`, payload);
    if (!ok) return toast(data.error || 'Не удалось сохранить изображение', true);
    state.company.logo = data.logo;
    state.company.cover = data.cover;
    state.company.coverFocal = data.coverFocal;
    render();
    toast(payload.remove ? 'Изображение удалено' : 'Изображение сохранено');
  }

  /* ---------------------------------------------------------------- tabs */

  function setTab(tab) {
    state.tab = tab;
    document.querySelectorAll('.co-tab').forEach(b => {
      const active = b.dataset.tab === tab;
      b.classList.toggle('is-active', active);
      b.setAttribute('aria-selected', String(active));
    });
    const url = new URL(window.location.href);
    if (tab === 'publications') url.searchParams.delete('tab'); else url.searchParams.set('tab', tab);
    history.replaceState(null, '', url.toString());
    loadTab();
  }

  function loadTab() {
    if (state.tab === 'publications' || state.tab === 'questions') return loadMaterials();
    if (state.tab === 'subscribers') return loadSubscribers(true);
    return loadFollowing();
  }

  async function loadMaterials() {
    const body = $('companyTabBody');
    body.innerHTML = '<div class="co-loading">Загрузка...</div>';
    const isQuestions = state.tab === 'questions';
    const params = new URLSearchParams({ companyId, limit: '50' });
    if (isQuestions) params.set('tab', 'questions');
    const { ok, data } = await api('GET', '/api/articles?' + params.toString());
    if (!ok) {
      body.innerHTML = '<div class="co-empty">Не удалось загрузить материалы</div>';
      return;
    }
    const items = (data.items || data.articles || []).filter(i => (i.materialType === 'question') === isQuestions);
    if (!items.length) {
      const c = state.company;
      body.innerHTML = `
        <div class="co-empty">
          <p class="co-empty-title">${isQuestions ? 'Вопросов от компании пока нет' : 'Публикаций пока нет'}</p>
          ${c.canPublish ? `<a class="co-btn co-btn-primary" href="${isQuestions ? 'question-editor.html' : 'editor.html'}?companyId=${encodeURIComponent(c.id)}">${isQuestions ? 'Задать вопрос' : 'Написать публикацию'}</a>` : ''}
        </div>`;
      return;
    }
    body.innerHTML = `<div class="co-materials">${items.map(item => `
      <a class="co-material" href="article.html?id=${encodeURIComponent(item.id)}">
        <span class="co-material-top">
          <span class="co-badge">${isQuestions ? 'Вопрос' : 'Публикация'}</span>
          ${typeof item.score === 'number' && item.score ? `<span class="co-score ${item.score > 0 ? 'is-positive' : 'is-negative'}">${item.score > 0 ? '+' : ''}${item.score}</span>` : ''}
        </span>
        <span class="co-material-title">${escapeHtml(item.title)}</span>
        ${item.description ? `<span class="co-material-text">${escapeHtml(item.description)}</span>` : ''}
        <span class="co-material-meta">${escapeHtml(item.author || '')}${item.date ? ' · ' + escapeHtml(item.date) : ''}${item.commentsCount ? ' · ' + item.commentsCount + ' ' + plural(item.commentsCount, 'комментарий', 'комментария', 'комментариев') : ''}</span>
      </a>`).join('')}</div>`;
  }

  async function loadSubscribers(reset) {
    const body = $('companyTabBody');
    if (reset) {
      state.subsOffset = 0;
      body.innerHTML = '<div class="co-loading">Загрузка...</div>';
    }
    const { ok, data } = await api('GET', `/api/companies/${encodeURIComponent(companyId)}/subscribers?limit=30&offset=${state.subsOffset}`);
    if (!ok) {
      body.innerHTML = '<div class="co-empty">Не удалось загрузить подписчиков</div>';
      return;
    }
    if (reset && !data.items.length) {
      body.innerHTML = '<div class="co-empty"><p class="co-empty-title">Подписчиков пока нет</p><p class="co-empty-text">Подпишитесь первым, чтобы видеть публикации компании в своей ленте.</p></div>';
      return;
    }
    const html = data.items.map(u => `
      <a class="co-person" href="profile.html?id=${encodeURIComponent(u.id)}">
        <span class="co-avatar">${u.avatar ? `<img src="${escapeHtml(u.avatar)}" alt="" onerror="this.remove()">` : ''}<span>${escapeHtml(initials(u.name))}</span></span>
        <span class="co-person-text"><span class="co-person-name">${escapeHtml(u.name)}</span>${u.specialization ? `<span class="co-person-sub">${escapeHtml(u.specialization)}</span>` : ''}</span>
      </a>`).join('');
    if (reset) body.innerHTML = '<div class="co-people"></div><button type="button" class="co-btn co-btn-ghost co-more" id="subsMore" hidden>Показать еще</button>';
    body.querySelector('.co-people').insertAdjacentHTML('beforeend', html);
    state.subsOffset += data.items.length;
    $('subsMore').hidden = !data.hasMore;
  }

  async function loadFollowing() {
    const body = $('companyTabBody');
    body.innerHTML = '<div class="co-loading">Загрузка...</div>';
    const { ok, data } = await api('GET', `/api/companies/${encodeURIComponent(companyId)}/subscriptions`);
    if (!ok) {
      body.innerHTML = '<div class="co-empty">Не удалось загрузить подписки</div>';
      return;
    }
    const items = data.items || [];
    const groups = { topic: 'Темы', company: 'Компании', user: 'Люди' };
    const link = (it) => it.targetType === 'company' ? `company.html?id=${encodeURIComponent(it.targetId)}`
      : it.targetType === 'user' ? `profile.html?id=${encodeURIComponent(it.targetId)}`
      : `feed.html?topics=${encodeURIComponent(it.targetId)}`;
    let html = state.company.isOwner
      ? '<p class="co-note">Это подписки компании, а не ваши личные. Управлять ими можете только вы как владелец.</p>'
      : '';
    if (!items.length) {
      html += '<div class="co-empty"><p class="co-empty-title">Компания пока ни на кого не подписана</p></div>';
    } else {
      html += Object.keys(groups).map(type => {
        const list = items.filter(i => i.targetType === type);
        if (!list.length) return '';
        return `<div class="co-follow-group"><h3 class="co-follow-title">${groups[type]}</h3><div class="co-chips">${list.map(i => `
          <span class="co-chip co-chip-link"><a href="${link(i)}">${escapeHtml(i.title)}</a>${state.company.isOwner ? `<button type="button" class="co-chip-remove" data-unfollow-type="${i.targetType}" data-unfollow-id="${escapeHtml(i.targetId)}" aria-label="Отписать компанию">&times;</button>` : ''}</span>`).join('')}</div></div>`;
      }).join('');
    }
    if (state.company.isOwner) html += await followManagerHtml(items);
    body.innerHTML = html;
  }

  async function followManagerHtml(current) {
    if (!state.entities) {
      const { ok, data } = await api('GET', '/api/subscriptions/entities');
      state.entities = ok ? data : { topics: [], companies: [], authors: [] };
    }
    const followed = new Set(current.map(i => i.targetType + ':' + i.targetId));
    const block = (title, type, list) => {
      const options = list.filter(e => !(type === 'company' && e.id === companyId))
        .filter(e => !followed.has(type + ':' + e.id)).slice(0, 24);
      if (!options.length) return '';
      return `<div class="co-follow-group"><h3 class="co-follow-title">${title}</h3><div class="co-chips">${options.map(e => `
        <button type="button" class="co-chip co-chip-add" data-follow-type="${type}" data-follow-id="${escapeHtml(e.id)}">+ ${escapeHtml(e.title || e.name)}</button>`).join('')}</div></div>`;
    };
    const e = state.entities;
    const inner = block('Темы', 'topic', e.topics || []) + block('Компании', 'company', e.companies || []) + block('Авторы', 'user', e.authors || []);
    return inner ? `<details class="co-follow-manager"><summary>Подписать компанию</summary>${inner}</details>` : '';
  }

  async function toggleFollow(type, id, action) {
    const { ok, data } = await api('POST', `/api/companies/${encodeURIComponent(companyId)}/subscriptions/toggle`, { targetType: type, targetId: id, action });
    if (!ok) return toast(data.error || 'Не удалось изменить подписку', true);
    state.company.stats.following += action === 'subscribe' ? 1 : -1;
    render();
    loadFollowing();
  }

  /* ---------------------------------------------------------------- actions */

  async function toggleSubscribe() {
    if (!state.user) {
      if (window.SCAuth) window.SCAuth.openModal('login');
      return;
    }
    const c = state.company;
    const action = c.isSubscribed ? 'unsubscribe' : 'subscribe';
    const { ok, data } = await api('POST', '/api/subscriptions/toggle', { targetType: 'company', targetId: c.id, title: c.name, action });
    if (!ok) return toast(data.error || 'Не удалось изменить подписку', true);
    c.isSubscribed = action === 'subscribe';
    c.stats.subscribers += c.isSubscribed ? 1 : -1;
    render();
    if (state.tab === 'subscribers') loadSubscribers(true);
  }

  /* ---------------------------------------------------------------- events */

  document.addEventListener('click', (e) => {
    if (e.target.closest('#btnSubscribe')) return toggleSubscribe();
    if (e.target.closest('#btnCopyLink')) {
      const url = window.location.origin + window.location.pathname + '?id=' + encodeURIComponent(companyId);
      (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(
        () => toast('Ссылка скопирована'), () => toast(url));
      return;
    }
    if (e.target.closest('#subsMore')) return loadSubscribers(false);
    const media = e.target.closest('[data-media]');
    if (media) return editMedia(media.dataset.media);
    const removeMedia = e.target.closest('[data-media-remove]');
    if (removeMedia) return saveMedia({ kind: removeMedia.dataset.mediaRemove, remove: true });
    const tab = e.target.closest('.co-tab');
    if (tab) return setTab(tab.dataset.tab);
    const add = e.target.closest('[data-follow-type]');
    if (add) return toggleFollow(add.dataset.followType, add.dataset.followId, 'subscribe');
    const remove = e.target.closest('[data-unfollow-type]');
    if (remove) return toggleFollow(remove.dataset.unfollowType, remove.dataset.unfollowId, 'unsubscribe');
  });

  const initialTab = new URLSearchParams(window.location.search).get('tab');
  if (['questions', 'subscribers', 'following'].includes(initialTab)) {
    state.tab = initialTab;
    document.querySelectorAll('.co-tab').forEach(b => {
      b.classList.toggle('is-active', b.dataset.tab === initialTab);
      b.setAttribute('aria-selected', String(b.dataset.tab === initialTab));
    });
  }

  // Reload the profile when the viewer signs in or out: buttons depend on who is looking
  window.addEventListener('auth:change', (e) => {
    const user = e.detail && e.detail.authenticated ? e.detail.user : null;
    const changed = (user && user.id) !== (state.user && state.user.id);
    state.user = user;
    if (changed || !state.company) load();
  });
  state.user = window.SCAuth && window.SCAuth.currentUser;
  load();
})();
