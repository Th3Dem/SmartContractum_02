/*
 * Image crop dialog shared by profile covers, company logos and company covers.
 *
 * window.SCMediaCrop.open({ title, aspect, outputWidth, outputHeight, round, minWidth, minHeight })
 * resolves with { url, focal } after the cropped image is uploaded, or null when cancelled.
 * The image is re-encoded in the browser, so EXIF data (including location) is not uploaded.
 */
(function() {
  'use strict';
  if (window.SCMediaCrop) return;

  const MAX_BYTES = 8 * 1024 * 1024;
  const TYPES = ['image/jpeg', 'image/png', 'image/webp'];

  function el(html) {
    const t = document.createElement('template');
    t.innerHTML = html.trim();
    return t.content.firstChild;
  }

  function loadImage(file) {
    if (window.createImageBitmap) {
      return createImageBitmap(file, { imageOrientation: 'from-image' }).catch(() => loadViaElement(file));
    }
    return loadViaElement(file);
  }

  function loadViaElement(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('decode')); };
      img.src = url;
    });
  }

  function toBlob(canvas) {
    return new Promise((resolve) => {
      canvas.toBlob((blob) => {
        if (blob && blob.type === 'image/webp') return resolve(blob);
        canvas.toBlob(resolve, 'image/jpeg', 0.9);
      }, 'image/webp', 0.9);
    });
  }

  function open(options) {
    const opts = Object.assign({
      title: 'Изображение',
      aspect: 1,
      outputWidth: 400,
      outputHeight: 400,
      round: false,
      minWidth: 64,
      minHeight: 64
    }, options || {});

    return new Promise((resolve) => {
      const previous = document.activeElement;
      const dialog = el(`
        <div class="mc-dialog" role="dialog" aria-modal="true" aria-label="${opts.title}">
          <div class="mc-backdrop" data-mc-cancel></div>
          <div class="mc-card">
            <div class="mc-head">
              <h2 class="mc-title">${opts.title}</h2>
              <button type="button" class="mc-icon" data-mc-cancel aria-label="Закрыть"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
            </div>
            <label class="mc-drop" tabindex="0">
              <input type="file" accept="image/jpeg,image/png,image/webp" hidden>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/></svg>
              <span class="mc-drop-title">Выберите файл или перетащите его сюда</span>
              <span class="mc-drop-hint">JPEG, PNG или WebP, до 8 МБ, не меньше ${opts.minWidth}×${opts.minHeight} пикселей</span>
            </label>
            <div class="mc-editor" hidden>
              <div class="mc-stage" tabindex="0" aria-label="Область кадрирования: перетаскивайте изображение, стрелки сдвигают, плюс и минус меняют масштаб">
                <canvas class="mc-canvas"></canvas>
                <div class="mc-frame${opts.round ? ' is-round' : ''}"></div>
              </div>
              <div class="mc-zoom">
                <span aria-hidden="true">−</span>
                <input type="range" min="1" max="4" step="0.01" value="1" aria-label="Масштаб">
                <span aria-hidden="true">+</span>
              </div>
              <button type="button" class="mc-link" data-mc-choose>Выбрать другой файл</button>
            </div>
            <div class="mc-message" role="alert" hidden></div>
            <div class="mc-actions">
              <button type="button" class="mc-btn mc-btn-ghost" data-mc-cancel>Отмена</button>
              <button type="button" class="mc-btn mc-btn-primary" data-mc-save disabled>Сохранить</button>
            </div>
          </div>
        </div>`);
      document.body.appendChild(dialog);

      const q = (s) => dialog.querySelector(s);
      const input = q('input[type=file]');
      const drop = q('.mc-drop');
      const editor = q('.mc-editor');
      const stage = q('.mc-stage');
      const canvas = q('.mc-canvas');
      const frame = q('.mc-frame');
      const zoom = q('.mc-zoom input');
      const save = q('[data-mc-save]');
      const message = q('.mc-message');
      const ctx = canvas.getContext('2d');
      const view = { img: null, scale: 1, base: 1, x: 0, y: 0, frameW: 0, frameH: 0 };
      let dragging = null;
      let busy = false;

      function showError(text) {
        message.textContent = text;
        message.hidden = !text;
      }

      function layout() {
        const width = Math.min(stage.clientWidth || 520, 640);
        const height = Math.round(Math.min(width / Math.max(opts.aspect, 1) + 80, 420));
        const ratio = window.devicePixelRatio || 1;
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
        canvas.style.width = width + 'px';
        canvas.style.height = height + 'px';
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        const pad = 24;
        view.frameW = Math.min(width - pad * 2, (height - pad * 2) * opts.aspect);
        view.frameH = view.frameW / opts.aspect;
        frame.style.width = view.frameW + 'px';
        frame.style.height = view.frameH + 'px';
        if (view.img) view.base = Math.max(view.frameW / view.img.width, view.frameH / view.img.height);
      }

      function clamp() {
        const w = view.img.width * view.base * view.scale;
        const h = view.img.height * view.base * view.scale;
        const maxX = Math.max(0, (w - view.frameW) / 2);
        const maxY = Math.max(0, (h - view.frameH) / 2);
        view.x = Math.max(-maxX, Math.min(maxX, view.x));
        view.y = Math.max(-maxY, Math.min(maxY, view.y));
      }

      function draw() {
        if (!view.img) return;
        clamp();
        const cw = canvas.clientWidth;
        const ch = canvas.clientHeight;
        const w = view.img.width * view.base * view.scale;
        const h = view.img.height * view.base * view.scale;
        ctx.clearRect(0, 0, cw, ch);
        ctx.drawImage(view.img, (cw - w) / 2 + view.x, (ch - h) / 2 + view.y, w, h);
      }

      // Visible frame rectangle mapped to source pixels
      function cropRect() {
        const k = view.base * view.scale;
        const w = view.img.width * k;
        const h = view.img.height * k;
        const left = (w - view.frameW) / 2 - view.x;
        const top = (h - view.frameH) / 2 - view.y;
        return { sx: left / k, sy: top / k, sw: view.frameW / k, sh: view.frameH / k };
      }

      async function useFile(file) {
        showError('');
        if (!file) return;
        if (!TYPES.includes(file.type)) return showError('Поддерживаются JPEG, PNG и WebP');
        if (file.size > MAX_BYTES) return showError('Файл больше 8 МБ');
        let img;
        try {
          img = await loadImage(file);
        } catch (e) {
          return showError('Не удалось прочитать изображение');
        }
        if (img.width < opts.minWidth || img.height < opts.minHeight) {
          return showError(`Изображение слишком маленькое: нужно не меньше ${opts.minWidth}×${opts.minHeight} пикселей`);
        }
        view.img = img;
        view.scale = 1;
        view.x = 0;
        view.y = 0;
        zoom.value = '1';
        drop.hidden = true;
        editor.hidden = false;
        layout();
        draw();
        save.disabled = false;
        stage.focus();
      }

      function close(result) {
        document.removeEventListener('keydown', onKey, true);
        window.removeEventListener('resize', onResize);
        dialog.remove();
        if (previous && previous.focus) previous.focus();
        resolve(result);
      }

      async function onSave() {
        if (!view.img || busy) return;
        busy = true;
        save.disabled = true;
        save.textContent = 'Сохраняем...';
        showError('');
        const r = cropRect();
        const out = document.createElement('canvas');
        out.width = opts.outputWidth;
        out.height = opts.outputHeight;
        const octx = out.getContext('2d');
        octx.imageSmoothingQuality = 'high';
        octx.drawImage(view.img, r.sx, r.sy, r.sw, r.sh, 0, 0, out.width, out.height);
        const blob = await toBlob(out);
        try {
          const res = await fetch('/api/media/upload', { method: 'POST', headers: { 'Content-Type': blob.type }, body: blob });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || !data.url) throw new Error(data.error || 'Не удалось загрузить изображение');
          close({
            url: data.url,
            focal: { x: (r.sx + r.sw / 2) / view.img.width, y: (r.sy + r.sh / 2) / view.img.height }
          });
        } catch (e) {
          busy = false;
          save.disabled = false;
          save.textContent = 'Сохранить';
          showError(e.message);
        }
      }

      function setZoom(value, keepCenter) {
        const next = Math.max(1, Math.min(4, value));
        if (keepCenter !== false) {
          view.x *= next / view.scale;
          view.y *= next / view.scale;
        }
        view.scale = next;
        zoom.value = String(next);
        draw();
      }

      function onKey(e) {
        if (e.key === 'Escape') { e.preventDefault(); return close(null); }
        if (e.key === 'Tab') {
          const items = Array.from(dialog.querySelectorAll('button, input[type=range], [tabindex="0"]')).filter(x => x.offsetParent !== null && !x.disabled);
          if (!items.length) return;
          const first = items[0], last = items[items.length - 1];
          if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
          else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
          return;
        }
        if (!view.img || document.activeElement !== stage) return;
        const step = e.shiftKey ? 30 : 8;
        const moves = { ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
        if (moves[e.key]) {
          e.preventDefault();
          view.x += moves[e.key][0];
          view.y += moves[e.key][1];
          draw();
        } else if (e.key === '+' || e.key === '=') {
          e.preventDefault();
          setZoom(view.scale + 0.1);
        } else if (e.key === '-') {
          e.preventDefault();
          setZoom(view.scale - 0.1);
        }
      }

      function onResize() {
        if (!view.img) return;
        layout();
        draw();
      }

      input.addEventListener('change', () => useFile(input.files[0]));
      drop.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
      ['dragenter', 'dragover'].forEach(t => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add('is-over'); }));
      ['dragleave', 'drop'].forEach(t => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.remove('is-over'); }));
      drop.addEventListener('drop', (e) => useFile(e.dataTransfer.files[0]));
      q('[data-mc-choose]').addEventListener('click', () => input.click());
      dialog.querySelectorAll('[data-mc-cancel]').forEach(b => b.addEventListener('click', () => close(null)));
      save.addEventListener('click', onSave);
      zoom.addEventListener('input', () => setZoom(parseFloat(zoom.value)));
      stage.addEventListener('wheel', (e) => { if (!view.img) return; e.preventDefault(); setZoom(view.scale - e.deltaY * 0.002); }, { passive: false });
      stage.addEventListener('pointerdown', (e) => {
        if (!view.img) return;
        dragging = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
        stage.setPointerCapture(e.pointerId);
        stage.classList.add('is-dragging');
      });
      stage.addEventListener('pointermove', (e) => {
        if (!dragging) return;
        view.x = dragging.vx + (e.clientX - dragging.x);
        view.y = dragging.vy + (e.clientY - dragging.y);
        draw();
      });
      ['pointerup', 'pointercancel'].forEach(t => stage.addEventListener(t, () => { dragging = null; stage.classList.remove('is-dragging'); }));
      document.addEventListener('keydown', onKey, true);
      window.addEventListener('resize', onResize);
      setTimeout(() => drop.focus(), 0);
    });
  }

  window.SCMediaCrop = { open };
})();
