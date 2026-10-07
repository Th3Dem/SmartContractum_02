(function() {
  'use strict';

  const STATUS_CLASS = {
    pending_moderation: 'is-pending',
    needs_revision: 'is-revision',
    approved: 'is-approved',
    rejected: 'is-rejected',
    draft: 'is-muted'
  };
  const DECISION_LABEL = { approve: 'Одобрено', revise: 'На доработку', reject: 'Отклонено' };
  const ROLE_LABEL = { admin: 'Администратор', moderator: 'Модератор', user: 'Пользователь' };
  const USER_STATUS_LABEL = { active: 'Активен', disabled: 'Заблокирован', pending: 'Не подтвердил email' };
  const REVISE_TEMPLATES = [
    'Добавьте источники для приведенных данных и цитат.',
    'Исправьте форматирование: заголовки, списки и блоки кода.',
    'Уточните заголовок: он должен отражать содержание материала.',
    'Уберите рекламные упоминания и ссылки, не относящиеся к теме.',
    'Раскройте тему подробнее: материалу не хватает практических примеров.'
  ];

  const state = {
    user: null,
    tab: 'queue',
    status: 'pending_moderation',
    type: '',
    search: '',
    items: [],
    selectedId: null,
    selected: null,
    rejectReasons: {},
    decision: null,
    logOffset: 0,
    usersOffset: 0,
    searchTimer: null
  };

  const $ = (id) => document.getElementById(id);

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
  }

  function toast(message, kind) {
    const el = $('modToast');
    el.textContent = message;
    el.className = 'mod-toast ' + (kind === 'error' ? 'is-error' : 'is-success');
    el.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { el.hidden = true; }, 3500);
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

  /* ---------------------------------------------------------------- access */

  function showGuard(title, text, canLogin) {
    $('modShell').hidden = true;
    $('modGuard').hidden = false;
    $('modGuardTitle').textContent = title;
    $('modGuardText').textContent = text;
    $('modGuardLogin').hidden = !canLogin;
  }

  function onAuth(user) {
    state.user = user;
    if (!user) {
      showGuard('Нужен вход', 'Панель модерации доступна модераторам и администраторам. Войдите в свой аккаунт.', true);
      return;
    }
    const caps = user.capabilities || [];
    if (!caps.includes('moderate')) {
      showGuard('Нет доступа', 'Эта страница доступна только модераторам и администраторам.', false);
      return;
    }
    $('modGuard').hidden = true;
    $('modShell').hidden = false;
    $('modRoleLabel').textContent = ROLE_LABEL[user.role] || '';
    $('tabUsersBtn').hidden = !caps.includes('manage_users');
    loadQueue();
  }

  /* ---------------------------------------------------------------- tabs */

  function switchTab(tab) {
    state.tab = tab;
    document.querySelectorAll('.mod-tab').forEach(b => {
      const active = b.dataset.tab === tab;
      b.classList.toggle('is-active', active);
      b.setAttribute('aria-selected', String(active));
    });
    $('sectionQueue').hidden = tab !== 'queue';
    $('sectionLog').hidden = tab !== 'log';
    $('sectionUsers').hidden = tab !== 'users';
    if (tab === 'log') { state.logOffset = 0; $('logBody').innerHTML = ''; loadLog(); }
    if (tab === 'users') { state.usersOffset = 0; $('usersBody').innerHTML = ''; loadUsers(); }
    if (tab === 'queue') loadQueue();
  }

  /* ---------------------------------------------------------------- queue */

  async function loadQueue() {
    const params = new URLSearchParams({ status: state.status, limit: '50' });
    if (state.type) params.set('type', state.type);
    if (state.search) params.set('q', state.search);
    const list = $('queueList');
    list.innerHTML = '<div class="mod-loading">Загрузка...</div>';
    const { ok, data } = await api('GET', '/api/admin/moderation/queue?' + params.toString());
    if (!ok) {
      list.innerHTML = `<div class="mod-list-empty">${escapeHtml(data.error || 'Не удалось загрузить очередь')}</div>`;
      return;
    }
    state.items = data.items || [];
    const counts = data.counts || {};
    document.querySelectorAll('[data-count]').forEach(el => {
      const n = counts[el.dataset.count] || 0;
      el.textContent = n ? String(n) : '';
    });
    $('tabQueueCount').textContent = counts.pending_moderation ? String(counts.pending_moderation) : '';
    renderQueue();
    if (state.selectedId && !state.items.some(i => i.id === state.selectedId)) {
      state.selectedId = null;
      renderEmptyDetail();
    }
  }

  function renderQueue() {
    const list = $('queueList');
    if (!state.items.length) {
      const empty = state.status === 'pending_moderation'
        ? 'Очередь пуста. Новые материалы появятся здесь.'
        : 'Здесь пока ничего нет.';
      list.innerHTML = `<div class="mod-list-empty">${empty}</div>`;
      return;
    }
    list.innerHTML = state.items.map(item => `
      <button type="button" class="mod-item${item.id === state.selectedId ? ' is-selected' : ''}" data-id="${escapeHtml(item.id)}">
        <span class="mod-item-top">
          <span class="mod-type">${item.materialType === 'question' ? 'Вопрос' : 'Публикация'}</span>
          ${item.claimedBy ? `<span class="mod-claim${item.claimedByMe ? ' is-mine' : ''}">${item.claimedByMe ? 'В работе у вас' : 'В работе: ' + escapeHtml(item.claimedBy.name)}</span>` : ''}
        </span>
        <span class="mod-item-title">${escapeHtml(item.title)}</span>
        <span class="mod-item-meta">${escapeHtml(item.author.name)}${item.company ? ' · ' + escapeHtml(item.company.name || '') : ''} · ${escapeHtml(formatDate(item.createdAt))}</span>
      </button>`).join('');
  }

  function renderEmptyDetail() {
    $('queueDetail').innerHTML = `
      <div class="mod-empty">
        <p class="mod-empty-title">Выберите материал</p>
        <p class="mod-empty-text">Слева список материалов. Откройте любой, чтобы прочитать его и принять решение.</p>
      </div>`;
  }

  async function openSubmission(id) {
    state.selectedId = id;
    renderQueue();
    const detail = $('queueDetail');
    detail.innerHTML = '<div class="mod-loading">Загрузка...</div>';
    const { ok, data } = await api('GET', '/api/admin/moderation/submissions/' + encodeURIComponent(id));
    if (!ok) {
      detail.innerHTML = `<div class="mod-empty"><p class="mod-empty-title">${escapeHtml(data.error || 'Ошибка загрузки')}</p></div>`;
      return;
    }
    state.selected = data.submission;
    state.rejectReasons = data.rejectReasons || {};
    renderDetail();
  }

  function renderDetail() {
    const s = state.selected;
    const st = s.authorStats || {};
    const pending = s.status === 'pending_moderation';
    const lockedByOther = s.claimedBy && !s.claimedByMe;
    const versions = (s.versions || []).filter(v => v.status !== 'draft' || v.reviewComment);
    const review = (s.reviewComment || s.reviewReasonLabel) ? `
      <div class="mod-note ${STATUS_CLASS[s.status] || ''}">
        <span class="mod-note-title">${escapeHtml(s.statusLabel)}${s.reviewedAt ? ' · ' + escapeHtml(formatDate(s.reviewedAt)) : ''}</span>
        ${s.reviewReasonLabel ? `<span class="mod-note-reason">${escapeHtml(s.reviewReasonLabel)}</span>` : ''}
        ${s.reviewComment ? `<p>${escapeHtml(s.reviewComment)}</p>` : ''}
      </div>` : '';

    $('queueDetail').innerHTML = `
      <div class="mod-detail-head">
        <div class="mod-detail-tags">
          <span class="mod-type">${s.materialType === 'question' ? 'Вопрос' : 'Публикация'}</span>
          <span class="mod-status ${STATUS_CLASS[s.status] || ''}">${escapeHtml(s.statusLabel)}</span>
          ${(s.topics || []).slice(0, 4).map(t => `<span class="mod-tag">${escapeHtml(t)}</span>`).join('')}
        </div>
        <h2 class="mod-detail-title">${escapeHtml(s.title)}</h2>
        <div class="mod-author">
          <a href="profile.html?id=${encodeURIComponent(s.author.id)}" target="_blank" rel="noopener" class="mod-author-name">${escapeHtml(s.author.name)}</a>
          ${s.company ? `<span class="mod-author-company">от имени ${escapeHtml(s.company.name || s.company.id)}</span>` : ''}
          <span class="mod-author-date">отправлено ${escapeHtml(formatDate(s.createdAt))}</span>
        </div>
        <div class="mod-stats" title="История автора">
          <span>Опубликовано: <b>${st.approved || 0}</b></span>
          <span>На доработке: <b>${st.needs_revision || 0}</b></span>
          <span>Отклонено: <b>${st.rejected || 0}</b></span>
        </div>
        ${review}
        ${versions.length ? `
          <details class="mod-versions">
            <summary>Предыдущие версии: ${versions.length}</summary>
            <ul>${versions.map(v => `<li><span class="mod-status ${STATUS_CLASS[v.status] || ''}">${escapeHtml(v.statusLabel)}</span> ${escapeHtml(formatDate(v.createdAt))}${v.reviewReasonLabel ? ' · ' + escapeHtml(v.reviewReasonLabel) : ''}${v.reviewComment ? `<p>${escapeHtml(v.reviewComment)}</p>` : ''}</li>`).join('')}</ul>
          </details>` : ''}
      </div>
      <div class="mod-article">${s.html || ''}</div>
      ${pending ? `
        <div class="mod-decision-bar">
          <div class="mod-claim-row">
            ${s.claimedByMe
              ? '<span class="mod-claim is-mine">Материал в работе у вас</span><button type="button" class="mod-link" data-action="release">Освободить</button>'
              : lockedByOther
                ? `<span class="mod-claim">Материалом занимается ${escapeHtml(s.claimedBy.name)}</span>`
                : '<button type="button" class="mod-link" data-action="claim">Взять в работу</button>'}
          </div>
          <div class="mod-decision-actions">
            <button type="button" class="mod-btn mod-btn-danger-ghost" data-decision="reject" ${lockedByOther ? 'disabled' : ''}>Отклонить</button>
            <button type="button" class="mod-btn mod-btn-warning" data-decision="revise" ${lockedByOther ? 'disabled' : ''}>На доработку</button>
            <button type="button" class="mod-btn mod-btn-success" data-decision="approve" ${lockedByOther ? 'disabled' : ''}>Одобрить</button>
          </div>
        </div>` : ''}`;
  }

  async function claimAction(action) {
    const { ok, data } = await api('POST', `/api/admin/moderation/submissions/${encodeURIComponent(state.selectedId)}/${action}`, {});
    if (!ok) toast(data.error || 'Действие недоступно', 'error');
    await openSubmission(state.selectedId);
    loadQueue();
  }

  /* ---------------------------------------------------------------- decisions */

  function openDecision(decision) {
    state.decision = decision;
    const dlg = $('decisionDialog');
    const title = state.selected ? state.selected.title : '';
    $('decisionMessage').hidden = true;
    $('decisionComment').value = '';
    $('rejectReasons').hidden = decision !== 'reject';
    $('reviseTemplates').hidden = decision !== 'revise';
    const submit = $('decisionSubmit');
    submit.className = 'mod-btn ' + ({ approve: 'mod-btn-success', revise: 'mod-btn-warning', reject: 'mod-btn-danger' })[decision];

    if (decision === 'approve') {
      $('decisionTitle').textContent = 'Одобрить материал';
      $('decisionLead').textContent = `«${title}» появится в ленте сразу после одобрения. Автор получит уведомление и письмо.`;
      $('decisionCommentLabel').textContent = 'Комментарий для автора (необязательно)';
      $('decisionHint').textContent = '';
      submit.textContent = 'Одобрить и опубликовать';
    } else if (decision === 'revise') {
      $('decisionTitle').textContent = 'Вернуть на доработку';
      $('decisionLead').textContent = 'Автор получит замечания, исправит материал и отправит его снова.';
      $('decisionCommentLabel').textContent = 'Что нужно исправить';
      $('decisionHint').textContent = 'Обязательно. Можно добавить готовые замечания кнопками выше.';
      $('reviseTemplates').innerHTML = REVISE_TEMPLATES.map((t, i) => `<button type="button" class="mod-chip" data-template="${i}">${escapeHtml(t)}</button>`).join('');
      submit.textContent = 'Вернуть на доработку';
    } else {
      $('decisionTitle').textContent = 'Отклонить материал';
      $('decisionLead').textContent = 'Отклоненный материал нельзя отправить повторно. Если его можно исправить, лучше вернуть на доработку.';
      $('rejectReasonOptions').innerHTML = Object.entries(state.rejectReasons).map(([code, label], i) => `
        <label class="mod-radio"><input type="radio" name="rejectReason" value="${escapeHtml(code)}" ${i === 0 ? 'checked' : ''}> <span>${escapeHtml(label)}</span></label>`).join('');
      $('decisionCommentLabel').textContent = 'Пояснение для автора';
      $('decisionHint').textContent = 'Необязательно, кроме причины «Другая причина».';
      submit.textContent = 'Отклонить';
    }
    dlg.hidden = false;
    setTimeout(() => (decision === 'approve' ? submit : $('decisionComment')).focus(), 0);
  }

  function closeDecision() {
    $('decisionDialog').hidden = true;
    state.decision = null;
  }

  async function submitDecision(e) {
    e.preventDefault();
    const comment = $('decisionComment').value.trim();
    const payload = { decision: state.decision, comment };
    if (state.decision === 'reject') {
      const picked = document.querySelector('input[name="rejectReason"]:checked');
      payload.reasonCode = picked ? picked.value : null;
    }
    const msg = $('decisionMessage');
    if (state.decision === 'revise' && comment.length < 10) {
      msg.textContent = 'Опишите, что нужно доработать (не короче 10 символов)';
      msg.hidden = false;
      return;
    }
    const submit = $('decisionSubmit');
    submit.disabled = true;
    const { ok, data } = await api('POST', `/api/admin/moderation/submissions/${encodeURIComponent(state.selectedId)}/decision`, payload);
    submit.disabled = false;
    if (!ok) {
      msg.textContent = data.error || 'Не удалось сохранить решение';
      msg.hidden = false;
      return;
    }
    closeDecision();
    toast(({ approve: 'Материал опубликован', revise: 'Материал возвращен на доработку', reject: 'Материал отклонен' })[payload.decision] + '. Автор уведомлен.');
    state.selectedId = null;
    renderEmptyDetail();
    loadQueue();
  }

  /* ---------------------------------------------------------------- log */

  async function loadLog() {
    const { ok, data } = await api('GET', `/api/admin/moderation/log?limit=50&offset=${state.logOffset}`);
    const body = $('logBody');
    if (!ok) {
      body.innerHTML = `<tr><td colspan="6" class="mod-table-empty">${escapeHtml(data.error || 'Ошибка загрузки')}</td></tr>`;
      return;
    }
    if (!data.items.length && state.logOffset === 0) {
      body.innerHTML = '<tr><td colspan="6" class="mod-table-empty">Решений пока не было</td></tr>';
    }
    body.insertAdjacentHTML('beforeend', data.items.map(d => `
      <tr>
        <td class="mod-nowrap">${escapeHtml(formatDate(d.createdAt))}</td>
        <td>${escapeHtml(d.title || d.submissionId)}</td>
        <td>${escapeHtml(d.author.name)}</td>
        <td><span class="mod-status ${({ approve: 'is-approved', revise: 'is-revision', reject: 'is-rejected' })[d.decision]}">${DECISION_LABEL[d.decision]}</span></td>
        <td>${escapeHtml(d.moderator.name)}</td>
        <td class="mod-comment-cell">${d.reasonLabel ? `<b>${escapeHtml(d.reasonLabel)}</b> ` : ''}${escapeHtml(d.comment || '')}</td>
      </tr>`).join(''));
    state.logOffset += data.items.length;
    $('logMore').hidden = !data.hasMore;
  }

  /* ---------------------------------------------------------------- users */

  async function loadUsers() {
    const params = new URLSearchParams({ limit: '50', offset: String(state.usersOffset) });
    const q = $('userSearch').value.trim();
    if (q) params.set('q', q);
    const role = $('userRoleFilter').value;
    if (role) params.set('role', role);
    const { ok, data } = await api('GET', '/api/admin/users?' + params.toString());
    const body = $('usersBody');
    if (!ok) {
      body.innerHTML = `<tr><td colspan="6" class="mod-table-empty">${escapeHtml(data.error || 'Ошибка загрузки')}</td></tr>`;
      return;
    }
    if (!data.items.length && state.usersOffset === 0) {
      body.innerHTML = '<tr><td colspan="6" class="mod-table-empty">Никого не найдено</td></tr>';
    }
    const me = state.user && state.user.id;
    body.insertAdjacentHTML('beforeend', data.items.map(u => {
      const locked = u.role === 'admin' || u.id === me;
      return `
      <tr data-user="${escapeHtml(u.id)}">
        <td><a href="profile.html?id=${encodeURIComponent(u.id)}" target="_blank" rel="noopener">${escapeHtml(u.name)}</a><div class="mod-sub">@${escapeHtml(u.login)}</div></td>
        <td>${escapeHtml(u.email || '')}</td>
        <td>${locked ? escapeHtml(ROLE_LABEL[u.role] || u.role) : `
          <select class="mod-select mod-select-sm" data-field="role" aria-label="Роль">
            <option value="user" ${u.role === 'user' ? 'selected' : ''}>Пользователь</option>
            <option value="moderator" ${u.role === 'moderator' ? 'selected' : ''}>Модератор</option>
          </select>`}</td>
        <td><span class="mod-status ${u.status === 'active' ? 'is-approved' : u.status === 'disabled' ? 'is-rejected' : 'is-muted'}">${escapeHtml(USER_STATUS_LABEL[u.status] || u.status)}</span></td>
        <td>${u.published}</td>
        <td class="mod-nowrap">${locked ? '' : (u.status === 'disabled'
          ? '<button type="button" class="mod-link" data-status="active">Разблокировать</button>'
          : '<button type="button" class="mod-link mod-link-danger" data-status="disabled">Заблокировать</button>')}</td>
      </tr>`;
    }).join(''));
    state.usersOffset += data.items.length;
    $('usersMore').hidden = !data.hasMore;
  }

  async function updateUser(userId, field, value, row) {
    const { ok, data } = await api('POST', `/api/admin/users/${encodeURIComponent(userId)}/${field}`, { [field]: value });
    if (!ok) {
      toast(data.error || 'Не удалось сохранить', 'error');
    } else {
      toast(field === 'role'
        ? (value === 'moderator' ? 'Пользователь назначен модератором' : 'Права модератора сняты')
        : (value === 'disabled' ? 'Пользователь заблокирован, его сессии завершены' : 'Пользователь разблокирован'));
    }
    state.usersOffset = 0;
    $('usersBody').innerHTML = '';
    loadUsers();
  }

  /* ---------------------------------------------------------------- events */

  function bind() {
    $('modGuardLogin').addEventListener('click', () => window.SCAuth && window.SCAuth.openModal('login'));
    document.querySelectorAll('.mod-tab').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));
    $('statusFilter').addEventListener('click', (e) => {
      const btn = e.target.closest('[data-status]');
      if (!btn) return;
      state.status = btn.dataset.status;
      document.querySelectorAll('#statusFilter .mod-seg').forEach(b => b.classList.toggle('is-active', b === btn));
      state.selectedId = null;
      renderEmptyDetail();
      loadQueue();
    });
    $('typeFilter').addEventListener('change', (e) => { state.type = e.target.value; loadQueue(); });
    $('queueSearch').addEventListener('input', (e) => {
      clearTimeout(state.searchTimer);
      state.searchTimer = setTimeout(() => { state.search = e.target.value.trim(); loadQueue(); }, 300);
    });
    $('queueList').addEventListener('click', (e) => {
      const item = e.target.closest('.mod-item');
      if (item) openSubmission(item.dataset.id);
    });
    $('queueDetail').addEventListener('click', (e) => {
      const d = e.target.closest('[data-decision]');
      if (d && !d.disabled) return openDecision(d.dataset.decision);
      const a = e.target.closest('[data-action]');
      if (a) claimAction(a.dataset.action);
    });
    $('decisionDialog').addEventListener('click', (e) => {
      if (e.target.closest('[data-close]')) return closeDecision();
      const chip = e.target.closest('[data-template]');
      if (chip) {
        const ta = $('decisionComment');
        const text = REVISE_TEMPLATES[Number(chip.dataset.template)];
        ta.value = ta.value ? ta.value.replace(/\s*$/, '') + '\n' + text : text;
        ta.focus();
      }
    });
    $('decisionForm').addEventListener('submit', submitDecision);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('decisionDialog').hidden) closeDecision(); });
    $('logMore').addEventListener('click', loadLog);
    $('usersMore').addEventListener('click', loadUsers);
    $('userSearch').addEventListener('input', () => {
      clearTimeout(state.searchTimer);
      state.searchTimer = setTimeout(() => { state.usersOffset = 0; $('usersBody').innerHTML = ''; loadUsers(); }, 300);
    });
    $('userRoleFilter').addEventListener('change', () => { state.usersOffset = 0; $('usersBody').innerHTML = ''; loadUsers(); });
    $('usersBody').addEventListener('change', (e) => {
      const sel = e.target.closest('select[data-field="role"]');
      if (sel) updateUser(sel.closest('tr').dataset.user, 'role', sel.value);
    });
    $('usersBody').addEventListener('click', (e) => {
      const btn = e.target.closest('[data-status]');
      if (btn) updateUser(btn.closest('tr').dataset.user, 'status', btn.dataset.status);
    });
  }

  bind();
  window.addEventListener('auth:change', (e) => onAuth(e.detail && e.detail.authenticated ? e.detail.user : null));
  if (window.SCAuth && window.SCAuth.currentUser) onAuth(window.SCAuth.currentUser);
})();
