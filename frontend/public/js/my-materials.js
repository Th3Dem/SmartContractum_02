(function() {
  'use strict';

  const STATUS_CLASS = {
    pending_moderation: 'is-pending',
    needs_revision: 'is-revision',
    approved: 'is-approved',
    rejected: 'is-rejected'
  };
  const STATUS_HINT = {
    pending_moderation: 'Модератор еще не рассмотрел материал. Мы пришлем уведомление и письмо, когда решение будет принято.',
    needs_revision: 'Исправьте материал по замечаниям модератора и отправьте его снова.',
    rejected: 'Материал не будет опубликован. Отклоненный материал нельзя отправить повторно.',
    approved: ''
  };

  // my-materials.html?submitted=<id>: the material the author has just sent
  const state = { filter: '', items: [], submitted: new URLSearchParams(window.location.search).get('submitted') || '' };
  const $ = (id) => document.getElementById(id);

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return isNaN(d.getTime()) ? '' : d.toLocaleString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
  }

  function editorUrl(item) {
    const page = item.materialType === 'question' ? 'question-editor.html' : 'editor.html';
    return `${page}?revise=${encodeURIComponent(item.id)}`;
  }

  async function load() {
    const list = $('mineList');
    list.innerHTML = '<div class="mod-loading">Загрузка...</div>';
    let res, data;
    try {
      res = await fetch('/api/moderation/my');
      data = await res.json();
    } catch (e) {
      list.innerHTML = '<div class="mod-list-empty">Нет связи с сервером. Обновите страницу.</div>';
      return;
    }
    if (!res.ok) {
      list.innerHTML = `<div class="mod-list-empty">${escapeHtml(data.error || 'Не удалось загрузить материалы')}</div>`;
      return;
    }
    state.items = data.items || [];
    const counts = Object.assign({}, data.counts || {});
    counts.all = state.items.length;
    document.querySelectorAll('#mineFilter [data-count]').forEach(el => {
      const n = counts[el.dataset.count] || 0;
      el.textContent = n ? String(n) : '';
    });
    render();
  }

  function render() {
    const list = $('mineList');
    const items = state.filter ? state.items.filter(i => i.status === state.filter) : state.items;
    if (!items.length) {
      list.innerHTML = state.items.length
        ? '<div class="mod-list-empty">В этом разделе пока ничего нет.</div>'
        : `<div class="mine-empty">
             <p class="mod-empty-title">Вы еще ничего не отправляли на модерацию</p>
             <p class="mod-empty-text">Напишите публикацию или задайте вопрос: после проверки модератором материал появится в ленте.</p>
           </div>`;
      return;
    }
    list.innerHTML = items.map(item => {
      const note = (item.reviewComment || item.reviewReasonLabel) && item.status !== 'approved' ? `
        <div class="mod-note ${STATUS_CLASS[item.status] || ''}">
          <span class="mod-note-title">${item.status === 'rejected' ? 'Причина отклонения' : 'Замечания модератора'}</span>
          ${item.reviewReasonLabel ? `<span class="mod-note-reason">${escapeHtml(item.reviewReasonLabel)}</span>` : ''}
          ${item.reviewComment ? `<p>${escapeHtml(item.reviewComment)}</p>` : ''}
        </div>` : (item.status === 'approved' && item.reviewComment ? `
        <div class="mod-note is-approved"><span class="mod-note-title">Комментарий модератора</span><p>${escapeHtml(item.reviewComment)}</p></div>` : '');
      let action = '';
      if (item.status === 'needs_revision') action = `<a class="mod-btn mod-btn-primary" href="${editorUrl(item)}">Исправить в редакторе</a>`;
      if (item.status === 'approved' && item.url) action = `<a class="mod-btn mod-btn-ghost" href="${escapeHtml(item.url)}">Открыть</a>`;
      return `
        <article class="mine-card${item.id === state.submitted ? ' is-new' : ''}" id="mine-${escapeHtml(item.id)}">
          ${item.id === state.submitted ? '<p class="mine-new-note">Материал отправлен. Модератор проверит его, и мы пришлем уведомление и письмо с решением.</p>' : ''}
          <div class="mine-card-head">
            <span class="mod-type">${item.materialType === 'question' ? 'Вопрос' : 'Публикация'}</span>
            <span class="mod-status ${STATUS_CLASS[item.status] || ''}">${escapeHtml(item.statusLabel)}</span>
            <span class="mine-date">${item.reviewedAt ? 'решение ' + escapeHtml(formatDate(item.reviewedAt)) : 'отправлено ' + escapeHtml(formatDate(item.createdAt))}</span>
          </div>
          <h2 class="mine-title">${escapeHtml(item.title)}</h2>
          ${STATUS_HINT[item.status] && item.id !== state.submitted ? `<p class="mine-hint">${STATUS_HINT[item.status]}</p>` : ''}
          ${note}
          ${action ? `<div class="mine-actions">${action}</div>` : ''}
        </article>`;
    }).join('');
    const fresh = state.submitted && document.getElementById('mine-' + state.submitted);
    if (fresh && !render.scrolled) {
      render.scrolled = true;
      fresh.scrollIntoView({ block: 'center' });
    }
  }

  function onAuth(user) {
    $('modGuard').hidden = !!user;
    $('modShell').hidden = !user;
    if (user) load();
  }

  $('modGuardLogin').addEventListener('click', () => window.SCAuth && window.SCAuth.openModal('login'));
  $('mineFilter').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-status]');
    if (!btn) return;
    state.filter = btn.dataset.status;
    document.querySelectorAll('#mineFilter .mod-seg').forEach(b => b.classList.toggle('is-active', b === btn));
    render();
  });
  window.addEventListener('auth:change', (e) => onAuth(e.detail && e.detail.authenticated ? e.detail.user : null));
  if (window.SCAuth && window.SCAuth.currentUser) onAuth(window.SCAuth.currentUser);
})();
