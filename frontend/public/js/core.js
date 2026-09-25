/**
 * Antigravity WYSIWYG Editor - Core Quill Engine
 * Custom Blots, Keyboard Shortcuts, and Editor Initialization
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

  /* ==========================================================================
     Custom Blots
     ========================================================================== */

  /**
   * Divider Blot (<hr class="editor-divider">)
   */
  class DividerBlot extends BlockEmbed {
    static blotName = 'divider';
    static tagName = 'hr';
    static className = 'editor-divider';
  }
  Quill.register(DividerBlot, true);

  /**
   * Spoiler Blot (<details class="editor-spoiler"><summary>...</summary><div>...</div></details>)
   */
  class SpoilerBlot extends BlockEmbed {
    static blotName = 'spoiler';
    static tagName = 'details';
    static className = 'editor-spoiler';

    static create(value) {
      const node = super.create();
      node.setAttribute('open', '');

      const titleText = (typeof value === 'object' && value.title) ? value.title : (typeof value === 'string' && value ? value : 'Заголовок спойлера');
      const bodyText = (typeof value === 'object' && value.body) ? value.body : 'Скрытый текст спойлера...';

      const summary = document.createElement('summary');
      summary.className = 'editor-spoiler-title';
      summary.contentEditable = 'true';
      summary.innerText = titleText;

      const body = document.createElement('div');
      body.className = 'editor-spoiler-body';
      body.contentEditable = 'true';
      body.innerText = bodyText;

      // Stop propagation to prevent Quill from interfering with embed inner content editing
      [summary, body].forEach(el => {
        el.addEventListener('keydown', (e) => e.stopPropagation());
        el.addEventListener('keyup', (e) => e.stopPropagation());
        el.addEventListener('keypress', (e) => e.stopPropagation());
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
   * Custom Figure / Image Blot with Caption, Alt, and Alignment
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

  /* ==========================================================================
     Core Editor Initialization
     ========================================================================== */

  /**
   * Initialize Quill instance with full module support
   * @param {string|HTMLElement} container
   * @returns {Quill}
   */
  function initQuill(container) {
    const editor = new Quill(container, {
      theme: 'snow',
      placeholder: 'Начните писать статью или нажмите "+" для добавления блоков...',
      modules: {
        toolbar: false, // We control the UI via our sticky toolbar & bubble toolbar
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
