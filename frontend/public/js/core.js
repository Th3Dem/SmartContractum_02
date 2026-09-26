/**
 * Antigravity WYSIWYG Editor - Core Quill Engine
 * Custom Blots (Divider, Spoiler, Inline Spoiler, LaTeX Formulas, Video Media, Anchor, Person, Image),
 * Keyboard Shortcuts, and Editor Initialization
 * 100% offline-first.
 */

(function (window) {
  'use strict';

  // Ensure Quill is loaded
  if (typeof window.Quill === 'undefined') {
    console.error('Quill is not loaded.');
    return;
  }

  const Quill = window.Quill;
  const BlockEmbed = Quill.import('blots/block/embed');
  const Inline = Quill.import('blots/inline');
  const Embed = Quill.import('blots/embed');

  /* ==========================================================================
     Custom Blots
     ========================================================================== */

  /**
   * 1. Divider Blot (<hr class="editor-divider">)
   */
  class DividerBlot extends BlockEmbed {
    static blotName = 'divider';
    static tagName = 'hr';
    static className = 'editor-divider';
  }
  Quill.register(DividerBlot, true);

  /**
   * 2. Block Spoiler Blot (<details class="editor-spoiler"><summary>...</summary><div>...</div></details>)
   */
  class SpoilerBlot extends BlockEmbed {
    static blotName = 'spoiler';
    static tagName = 'details';
    static className = 'editor-spoiler';

    static create(value) {
      const node = super.create();
      node.setAttribute('open', '');

      const titleText = (typeof value === 'object' && value.title) ? value.title : (typeof value === 'string' && value ? value : '');
      const bodyText = (typeof value === 'object' && value.body) ? value.body : '';

      const summary = document.createElement('summary');
      summary.className = 'editor-spoiler-title';
      summary.contentEditable = 'true';
      summary.setAttribute('data-placeholder', 'Заголовок спойлера');
      if (titleText && titleText !== 'Заголовок спойлера (нажмите для редактирования)') {
        summary.innerText = titleText;
      }

      const body = document.createElement('div');
      body.className = 'editor-spoiler-body';
      body.contentEditable = 'true';
      body.setAttribute('data-placeholder', 'Скрытый текст спойлера...');
      if (bodyText && bodyText !== 'Скрытый текст спойлера...') {
        body.innerText = bodyText;
      }

      // Prevent Quill selection interference & handle empty state cleanup so :empty works reliably
      [summary, body].forEach(el => {
        el.addEventListener('keydown', (e) => e.stopPropagation());
        el.addEventListener('keypress', (e) => e.stopPropagation());
        el.addEventListener('keyup', (e) => {
          e.stopPropagation();
          if (el.innerHTML === '<br>' || !el.textContent.trim()) {
            el.innerHTML = '';
          }
        });
        el.addEventListener('input', (e) => {
          if (el.innerHTML === '<br>' || !el.textContent.trim()) {
            el.innerHTML = '';
          }
        });
      });

      node.appendChild(summary);
      node.appendChild(body);
      return node;
    }

    static value(node) {
      const summary = node.querySelector('.editor-spoiler-title');
      const body = node.querySelector('.editor-spoiler-body');
      return {
        title: summary ? summary.innerText.trim() : '',
        body: body ? body.innerText.trim() : ''
      };
    }
  }
  Quill.register(SpoilerBlot, true);

  /**
   * 3. Inline Spoiler Blot (Hidden text, revealed on click in preview mode)
   */
  class InlineSpoilerBlot extends Inline {
    static blotName = 'inline-spoiler';
    static tagName = 'span';
    static className = 'editor-inline-spoiler';
  }
  Quill.register(InlineSpoilerBlot, true);

  /**
   * 4. Inline LaTeX Formula Blot
   */
  class InlineFormulaBlot extends Embed {
    static blotName = 'inlineFormula';
    static tagName = 'span';
    static className = 'editor-inline-formula';

    static create(value) {
      const node = super.create();
      const latex = typeof value === 'string' ? value : (value && value.latex ? value.latex : '');
      node.setAttribute('data-latex', latex);
      node.textContent = latex ? `\\(${latex}\\)` : '\\(...)';
      node.title = `LaTeX: ${latex}`;
      return node;
    }

    static value(node) {
      return {
        latex: node.getAttribute('data-latex') || ''
      };
    }
  }
  Quill.register(InlineFormulaBlot, true);

  /**
   * 5. Block LaTeX Formula Blot
   */
  class BlockFormulaBlot extends BlockEmbed {
    static blotName = 'blockFormula';
    static tagName = 'div';
    static className = 'editor-block-formula';

    static create(value) {
      const node = super.create();
      const latex = typeof value === 'string' ? value : (value && value.latex ? value.latex : '');
      node.setAttribute('data-latex', latex);

      const renderDiv = document.createElement('div');
      renderDiv.className = 'formula-rendered';
      renderDiv.textContent = latex ? `$$\n${latex}\n$$` : '$$ ... $$';
      node.appendChild(renderDiv);

      const badge = document.createElement('div');
      badge.className = 'formula-badge';
      badge.innerHTML = `<span>LaTeX</span> <button type="button" class="formula-edit-action" title="Редактировать формулу"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:3px;"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg><span>Изменить</span></button>`;
      node.appendChild(badge);

      return node;
    }

    static value(node) {
      return {
        latex: node.getAttribute('data-latex') || ''
      };
    }
  }
  Quill.register(BlockFormulaBlot, true);

  /**
   * 6. Media Element Blot (YouTube, Vimeo, VK Video with responsive iframe)
   */
  class MediaEmbedBlot extends BlockEmbed {
    static blotName = 'mediaEmbed';
    static tagName = 'div';
    static className = 'editor-media-embed';

    static create(value) {
      const node = super.create();
      const data = typeof value === 'object' && value ? value : {};
      const embedUrl = data.embedUrl || '';
      let originalUrl = data.originalUrl || embedUrl;
      if (originalUrl && !/^https?:\/\//i.test(originalUrl)) {
        originalUrl = 'https://' + originalUrl;
      }
      const provider = data.provider || 'video';
      const caption = data.caption || '';

      node.setAttribute('data-provider', provider);
      node.setAttribute('data-embed-url', embedUrl);
      node.setAttribute('data-original-url', originalUrl);

      const ratio = document.createElement('div');
      ratio.className = 'media-aspect-ratio';

      const iframe = document.createElement('iframe');
      iframe.src = embedUrl;
      iframe.setAttribute('frameborder', '0');
      iframe.setAttribute('allowfullscreen', 'true');
      iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
      iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation allow-popups');
      ratio.appendChild(iframe);
      node.appendChild(ratio);

      const fallback = document.createElement('div');
      fallback.className = 'media-fallback-banner';
      fallback.innerHTML = `<span>Видео (${provider.toUpperCase()})</span> <a href="${originalUrl}" target="_blank" rel="noopener noreferrer">Смотреть на источнике ↗</a>`;

      const linkEl = fallback.querySelector('a');
      if (linkEl) {
        linkEl.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          if (originalUrl) {
            window.open(originalUrl, '_blank', 'noopener,noreferrer');
          }
        });
      }

      node.appendChild(fallback);

      const cap = document.createElement('div');
      cap.className = 'media-caption';
      cap.contentEditable = 'true';
      cap.setAttribute('placeholder', 'Подпись к видео...');
      cap.innerText = caption;
      cap.addEventListener('keydown', (e) => e.stopPropagation());
      cap.addEventListener('keyup', (e) => e.stopPropagation());
      node.appendChild(cap);

      return node;
    }

    static value(node) {
      const cap = node.querySelector('.media-caption');
      return {
        provider: node.getAttribute('data-provider') || '',
        embedUrl: node.getAttribute('data-embed-url') || '',
        originalUrl: node.getAttribute('data-original-url') || '',
        caption: cap ? cap.innerText.trim() : ''
      };
    }
  }
  Quill.register(MediaEmbedBlot, true);
  window.MediaEmbedBlot = MediaEmbedBlot;
  window.VideoEmbed = MediaEmbedBlot;
  window.VideoBlot = MediaEmbedBlot;

  // Also safely override Quill default 'video' blot if available to ensure sandbox isolation
  try {
    const QuillVideo = Quill.import('formats/video');
    if (QuillVideo) {
      class SafeVideoBlot extends QuillVideo {
        static blotName = 'video';
        static create(value) {
          const node = super.create(value);
          if (node && node.tagName && node.tagName.toLowerCase() === 'iframe') {
            node.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation allow-popups');
          }
          return node;
        }
      }
      Quill.register(SafeVideoBlot, true);
    }
  } catch (e) {
    // Ignore if formats/video is not present
  }

  /**
   * 7. Custom Image Blot (Caption, Alt, Alignment)
   */
  class CustomImageBlot extends BlockEmbed {
    static blotName = 'customImage';
    static tagName = 'figure';
    static className = 'editor-figure';

    static create(value) {
      const node = super.create();
      const data = typeof value === 'string' ? { src: value } : (value || {});

      node.classList.add(`align-${data.align || 'center'}`);

      const img = document.createElement('img');
      img.src = data.src || '';
      if (data.alt) img.alt = data.alt;
      node.appendChild(img);

      const caption = document.createElement('figcaption');
      caption.contentEditable = 'true';
      caption.innerText = data.caption || '';
      caption.setAttribute('placeholder', 'Подпись к изображению...');
      caption.addEventListener('keydown', (e) => e.stopPropagation());
      caption.addEventListener('keyup', (e) => e.stopPropagation());
      node.appendChild(caption);

      return node;
    }

    static value(node) {
      const img = node.querySelector('img');
      const cap = node.querySelector('figcaption');
      let align = 'center';
      if (node.classList.contains('align-left')) align = 'left';
      if (node.classList.contains('align-right')) align = 'right';
      if (node.classList.contains('align-full')) align = 'full';

      return {
        src: img ? img.src : '',
        alt: img ? img.alt : '',
        caption: cap ? cap.innerText.trim() : '',
        align: align
      };
    }
  }
  Quill.register(CustomImageBlot, true);

  /**
   * 8. Anchor Blot (Named anchor with unique ID check)
   */
  class AnchorBlot extends BlockEmbed {
    static blotName = 'anchor';
    static tagName = 'div';
    static className = 'editor-anchor-block';

    static create(value) {
      const node = super.create();
      const id = typeof value === 'string' ? value : (value && value.id ? value.id : 'anchor');
      const cleanId = id.trim().toLowerCase().replace(/[^a-z0-9а-яё_-]/gi, '-');
      node.setAttribute('data-anchor-id', cleanId);

      const targetA = document.createElement('a');
      targetA.id = cleanId;
      targetA.className = 'editor-anchor-target';
      node.appendChild(targetA);

      const badge = document.createElement('span');
      badge.className = 'editor-anchor-badge';
      badge.innerHTML = `<span class="anchor-icon"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;"><circle cx="12" cy="5" r="3"></circle><line x1="12" y1="22" x2="12" y2="8"></line><path d="M5 12H2a10 10 0 0 0 20 0h-3"></path></svg></span> <span class="anchor-id-display">#${cleanId}</span>`;
      node.appendChild(badge);

      const hint = document.createElement('span');
      hint.className = 'editor-anchor-hint';
      hint.textContent = 'Якорь для перехода по ссылке';
      node.appendChild(hint);

      return node;
    }

    static value(node) {
      return {
        id: node.getAttribute('data-anchor-id') || ''
      };
    }
  }
  Quill.register(AnchorBlot, true);

  /**
   * 9. Person Card Blot (Avatar, Name, Role, Link)
   */
  class PersonBlot extends BlockEmbed {
    static blotName = 'person';
    static tagName = 'div';
    static className = 'editor-person-card';

    static create(value) {
      const data = typeof value === 'object' && value ? value : {};
      const name = data.name || 'Имя Фамилия';
      const role = data.role || 'Специализация / Должность';
      const link = data.link || '';
      const avatar = data.avatar || '';

      const node = super.create();
      node.setAttribute('data-name', name);
      node.setAttribute('data-role', role);
      node.setAttribute('data-link', link);
      node.setAttribute('data-avatar', avatar);

      const avatarWrap = document.createElement('div');
      avatarWrap.className = 'person-avatar-wrap';

      if (avatar) {
        const img = document.createElement('img');
        img.src = avatar;
        img.alt = name;
        img.className = 'person-avatar-img';
        avatarWrap.appendChild(img);
      } else {
        const placeholder = document.createElement('div');
        placeholder.className = 'person-avatar-placeholder';
        const initial = name.trim().charAt(0).toUpperCase();
        if (initial) {
          placeholder.textContent = initial;
        } else {
          placeholder.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`;
        }
        avatarWrap.appendChild(placeholder);
      }

      const info = document.createElement('div');
      info.className = 'person-info';

      const nameEl = document.createElement('div');
      nameEl.className = 'person-name';
      nameEl.textContent = name;
      info.appendChild(nameEl);

      const roleEl = document.createElement('div');
      roleEl.className = 'person-role';
      roleEl.textContent = role;
      info.appendChild(roleEl);

      if (link) {
        const linkEl = document.createElement('a');
        linkEl.className = 'person-link';
        linkEl.href = link;
        linkEl.target = '_blank';
        linkEl.rel = 'noopener noreferrer';
        linkEl.textContent = link.replace(/^https?:\/\//i, '');
        info.appendChild(linkEl);
      }

      node.appendChild(avatarWrap);
      node.appendChild(info);
      return node;
    }

    static value(node) {
      return {
        name: node.getAttribute('data-name') || '',
        role: node.getAttribute('data-role') || '',
        link: node.getAttribute('data-link') || '',
        avatar: node.getAttribute('data-avatar') || ''
      };
    }
  }
  Quill.register(PersonBlot, true);

  /* ==========================================================================
     Core Editor Initialization
     ========================================================================== */

  /**
   * Initialize Quill instance
   * @param {string|HTMLElement} container
   * @returns {Quill}
   */
  function initQuill(container) {
    const editor = new Quill(container, {
      theme: 'snow',
      placeholder: 'Начните писать статью или нажмите "+" для добавления блоков...',
      modules: {
        toolbar: false, // Formatting toolbar replaced with contextual Bubble Toolbar
        table: true,
        syntax: window.hljs ? { hljs: window.hljs } : false,
        history: {
          delay: 1000,
          maxStack: 150,
          userOnly: true
        }
      }
    });

    // Setup global keyboard shortcuts
    editor.keyboard.addBinding({
      key: 'S',
      shortKey: true
    }, function () {
      if (window.EditorApp && window.EditorApp.Drafts) {
        window.EditorApp.Drafts.saveCurrent({ isManual: true });
      }
      return false; // Prevent browser default save page dialog
    });

    editor.keyboard.addBinding({
      key: 'K',
      shortKey: true
    }, function () {
      if (window.EditorApp && window.EditorApp.Toolbar) {
        window.EditorApp.Toolbar.openLinkModal();
      }
      return false;
    });

    return editor;
  }

  // Export to global namespace
  window.EditorCore = {
    initQuill: initQuill
  };

})(window);
