/*
 * Cover and avatar of a person on profile.html: the owner changes them in place through the
 * shared crop dialog (js/media-crop.js), the same one the settings page uses. Every other
 * profile field is edited on settings.html#profile.
 */
(function() {
  'use strict';

  const params = new URLSearchParams(window.location.search);
  const profileId = params.get('id') || params.get('userId') || params.get('user') ||
    (window.location.pathname.startsWith('/user/') ? window.location.pathname.slice('/user/'.length).replace(/\/$/, '') : '');
  if (!profileId) return;

  const ICON_IMAGE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/></svg>';
  const ICON_CAMERA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>';
  const ICON_TRASH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>';
  const state = { cover: null, isOwn: false };

  function coverEl() {
    return document.querySelector('#profileHero .profile-cover');
  }

  function render() {
    const el = coverEl();
    if (!el) return;
    el.classList.toggle('media-has-image', Boolean(state.cover));
    el.style.backgroundImage = state.cover ? `url("${encodeURI(state.cover)}")` : '';
    el.style.backgroundPosition = 'center';
    el.querySelectorAll('.media-edit-bar').forEach(n => n.remove());
    renderAvatarButton();
    if (!state.isOwn || !window.SCMediaCrop) return;
    el.insertAdjacentHTML('beforeend', `
      <div class="media-edit-bar">
        <button type="button" class="media-edit-btn" data-cover-edit>${ICON_IMAGE}<span>${state.cover ? 'Изменить обложку' : 'Добавить обложку'}</span></button>
        ${state.cover ? `<button type="button" class="media-edit-btn" data-cover-remove aria-label="Удалить обложку">${ICON_TRASH}</button>` : ''}
      </div>`);
  }

  function renderAvatarButton() {
    const wrap = document.querySelector('#profileHero .profile-avatar-wrap');
    if (!wrap) return;
    wrap.querySelectorAll('.profile-avatar-edit').forEach(n => n.remove());
    if (!state.isOwn || !window.SCMediaCrop) return;
    wrap.insertAdjacentHTML('beforeend',
      `<button type="button" class="profile-avatar-edit" data-avatar-edit title="Изменить фото" aria-label="Изменить фото">${ICON_CAMERA}</button>`);
  }

  function showAvatar(url) {
    const img = document.getElementById('profileAvatarImg');
    const initials = document.getElementById('profileAvatarInitials');
    if (img) {
      img.src = url || '';
      img.style.display = url ? 'block' : 'none';
    }
    if (initials) initials.style.display = url ? 'none' : 'block';
  }

  async function save(payload) {
    const kind = payload.kind || 'cover';
    const res = await fetch('/api/user/profile-media', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.assign({ kind: 'cover' }, payload))
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      window.alert(data.error || (kind === 'avatar' ? 'Не удалось сохранить фото' : 'Не удалось сохранить обложку'));
      return;
    }
    if (kind === 'avatar') {
      showAvatar(data.avatar);
      // The header shows the same photo
      if (window.SCAuth && typeof window.SCAuth.checkStatus === 'function') window.SCAuth.checkStatus();
      return;
    }
    state.cover = data.cover;
    render();
  }

  async function load() {
    try {
      const res = await fetch('/api/users/' + encodeURIComponent(profileId));
      const data = await res.json();
      const profile = data.profile || data.user || data;
      state.cover = profile.cover || null;
      state.isOwn = Boolean(profile.isOwnProfile);
    } catch (e) {
      return;
    }
    // The hero is rendered by profile-page.js; wait until it exists
    let tries = 0;
    (function apply() {
      if (coverEl()) return render();
      if (tries++ < 50) setTimeout(apply, 100);
    })();
  }

  document.addEventListener('click', async (e) => {
    if (e.target.closest('[data-cover-edit]')) {
      const picked = await window.SCMediaCrop.open({
        title: 'Обложка профиля', aspect: 3, outputWidth: 1500, outputHeight: 500, minWidth: 600, minHeight: 200
      });
      if (picked) save({ url: picked.url, focal: picked.focal });
    } else if (e.target.closest('[data-avatar-edit]')) {
      const picked = await window.SCMediaCrop.open({
        title: 'Фото профиля', aspect: 1, round: true, outputWidth: 400, outputHeight: 400, minWidth: 64, minHeight: 64
      });
      if (picked) save({ kind: 'avatar', url: picked.url });
    } else if (e.target.closest('[data-cover-remove]')) {
      save({ remove: true });
    }
  });

  window.addEventListener('auth:change', load);
  load();
})();
