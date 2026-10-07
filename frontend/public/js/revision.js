/*
 * Opens a material returned for revision in the editor (editor.html?revise=<submissionId> or
 * question-editor.html?revise=<submissionId>) and shows the moderator's remarks above the editor.
 */
(function() {
  'use strict';

  const params = new URLSearchParams(window.location.search);
  const submissionId = params.get('revise');
  if (!submissionId) return;

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function draftsManager() {
    if (window.EditorApp && window.EditorApp.Drafts) return window.EditorApp.Drafts;
    if (window.QuestionEditor && window.QuestionEditor.state && window.QuestionEditor.state.draftsManager) {
      return window.QuestionEditor.state.draftsManager;
    }
    return null;
  }

  function waitForDrafts(timeoutMs) {
    return new Promise((resolve) => {
      const started = Date.now();
      (function poll() {
        const dm = draftsManager();
        if (dm || Date.now() - started > timeoutMs) return resolve(dm);
        setTimeout(poll, 100);
      })();
    });
  }

  function showBanner(kind, title, body, reason) {
    const banner = document.createElement('div');
    banner.className = 'revision-banner mod-note ' + kind;
    banner.setAttribute('role', 'note');
    banner.innerHTML = `
      <div class="revision-banner-text">
        <span class="mod-note-title">${escapeHtml(title)}</span>
        ${reason ? `<span class="mod-note-reason">${escapeHtml(reason)}</span>` : ''}
        ${body ? `<p>${escapeHtml(body)}</p>` : ''}
      </div>
      <button type="button" class="mod-icon-btn" aria-label="Скрыть замечания"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg></button>`;
    banner.querySelector('button').addEventListener('click', () => banner.remove());
    const header = document.querySelector('header');
    if (header && header.parentNode) header.parentNode.insertBefore(banner, header.nextSibling);
    else document.body.insertBefore(banner, document.body.firstChild);
  }

  async function start() {
    let data;
    try {
      const res = await fetch('/api/moderation/my/' + encodeURIComponent(submissionId));
      data = await res.json();
      if (!res.ok) throw new Error(data.error || 'not found');
    } catch (e) {
      showBanner('is-rejected', 'Материал для доработки не найден', 'Откройте его заново из раздела «Мои материалы».');
      return;
    }
    const s = data.submission;
    if (!s.canRevise) {
      showBanner('is-pending', `Статус: ${s.statusLabel}`, 'Этот материал сейчас не ожидает доработки.');
      return;
    }

    const dm = await waitForDrafts(10000);
    if (!dm || typeof dm.loadDraft !== 'function') {
      showBanner('is-rejected', 'Не удалось открыть материал в редакторе', 'Обновите страницу.');
      return;
    }

    // Keep the server draft revision so the next autosave does not conflict with the stored draft
    let revision = 1;
    try {
      const res = await fetch('/api/drafts/' + encodeURIComponent(s.draftId));
      if (res.ok) {
        const d = await res.json();
        if (d && d.draft && d.draft.revision) revision = d.draft.revision;
      }
    } catch (_) {}

    const settings = s.publicationSettings || {};
    await dm.loadDraft({
      id: s.draftId,
      title: s.title,
      delta: s.delta,
      html: s.html,
      publicationSettings: settings,
      tags: Array.isArray(settings.keywords) ? settings.keywords : [],
      revision: revision,
      materialType: s.materialType
    }, false);

    showBanner('is-revision', 'Замечания модератора', s.reviewComment || '', '');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
