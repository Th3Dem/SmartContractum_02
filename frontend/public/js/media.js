/**
 * Antigravity WYSIWYG Editor - Media Manager (Images & Video Elements)
 * 100% offline-first image upload (DataURL/base64), URL insertion, caption, alt, and alignment.
 * Video URL parser for YouTube, Vimeo, VK Video with safe responsive iframe embeds.
 */

(function (window) {
  'use strict';

  class MediaManager {
    constructor(editor) {
      this.editor = editor;
      this.imageModal = document.getElementById('image-modal');
      this.fileInput = document.getElementById('image-file-input');
      this.urlInput = document.getElementById('image-url-input');
      this.altInput = document.getElementById('image-alt-input');
      this.captionInput = document.getElementById('image-caption-input');
      this.alignSelect = document.getElementById('image-align-select');
      this.previewEl = document.getElementById('image-preview');
      this.insertBtn = document.getElementById('image-insert-btn');

      this.currentInsertionIndex = null;
      this.currentImageDataUrl = null;
      this.activeTab = 'file'; // 'file' or 'url'

      this.initElements();
      this.bindEvents();
      this.bindDragDropPaste();
    }

    /**
     * Video URL parser for YouTube, Vimeo, and VK Video
     * @param {string} inputUrl
     * @returns {object|null}
     */
    static parseVideoUrl(inputUrl) {
      if (!inputUrl || typeof inputUrl !== 'string') return null;
      const url = inputUrl.trim();

      // 1. YouTube (watch, youtu.be, embed, shorts)
      const ytMatch = url.match(/(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?|shorts)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/i);
      if (ytMatch) {
        const videoId = ytMatch[1];
        return {
          provider: 'youtube',
          id: videoId,
          embedUrl: `https://www.youtube-nocookie.com/embed/${videoId}`,
          originalUrl: url
        };
      }

      // 2. Vimeo (vimeo.com/{id}, player.vimeo.com/video/{id})
      const vimeoMatch = url.match(/(?:vimeo\.com\/|player\.vimeo\.com\/video\/)([0-9]+)/i);
      if (vimeoMatch) {
        const videoId = vimeoMatch[1];
        return {
          provider: 'vimeo',
          id: videoId,
          embedUrl: `https://player.vimeo.com/video/${videoId}`,
          originalUrl: url
        };
      }

      // 3. VK Video: iframe video_ext.php?oid=...&id=...(&hash=...)
      const vkExtMatch = url.match(/(?:vk\.com|vkvideo\.ru)\/video_ext\.php\?(?:[^"'\s]*&)?oid=(-?[0-9]+)&id=([0-9]+)(?:&hash=([a-zA-Z0-9]+))?/i);
      if (vkExtMatch) {
        const oid = vkExtMatch[1];
        const id = vkExtMatch[2];
        const hash = vkExtMatch[3] || '';
        return {
          provider: 'vk',
          oid: oid,
          id: id,
          hash: hash,
          embedUrl: `https://vk.com/video_ext.php?oid=${oid}&id=${id}${hash ? '&hash=' + hash : ''}&hd=2`,
          originalUrl: url
        };
      }

      // 4. VK Video: standard URL vk.com/video{oid}_{id} or vkvideo.ru/video{oid}_{id}
      const vkMatch = url.match(/(?:vk\.com|vkvideo\.ru)\/video(-?[0-9]+)_([0-9]+)/i);
      if (vkMatch) {
        const oid = vkMatch[1];
        const id = vkMatch[2];
        const hashMatch = url.match(/[?&]hash=([a-zA-Z0-9]+)/i);
        const hash = hashMatch ? hashMatch[1] : '';
        return {
          provider: 'vk',
          oid: oid,
          id: id,
          hash: hash,
          embedUrl: `https://vk.com/video_ext.php?oid=${oid}&id=${id}${hash ? '&hash=' + hash : ''}&hd=2`,
          originalUrl: url
        };
      }

      return null;
    }

    initElements() {
      // Tab switching
      const tabBtns = document.querySelectorAll('[data-image-tab]');
      tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
          tabBtns.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');

          const tabName = btn.getAttribute('data-image-tab');
          this.activeTab = tabName;

          const fileSection = document.getElementById('image-tab-file');
          const urlSection = document.getElementById('image-tab-url');

          if (fileSection && urlSection) {
            fileSection.style.display = tabName === 'file' ? 'block' : 'none';
            urlSection.style.display = tabName === 'url' ? 'block' : 'none';
          }
        });
      });
    }

    bindEvents() {
      // File input change
      if (this.fileInput) {
        this.fileInput.addEventListener('change', (e) => {
          const file = e.target.files && e.target.files[0];
          if (file) {
            this.readFile(file);
          }
        });
      }

      // URL input change
      if (this.urlInput) {
        this.urlInput.addEventListener('input', (e) => {
          const url = e.target.value.trim();
          if (url && this.previewEl) {
            this.previewEl.innerHTML = `<img src="${this.sanitizeSrc(url)}" alt="Preview" style="max-height: 180px; max-width: 100%; border-radius: 6px;">`;
          }
        });
      }

      // Insert button click
      if (this.insertBtn) {
        this.insertBtn.addEventListener('click', () => {
          this.insertImage();
        });
      }
    }

    readFile(file) {
      if (!file.type.startsWith('image/')) {
        alert('Пожалуйста, выберите файл изображения (PNG, JPG, WebP, GIF, SVG).');
        return;
      }

      const reader = new FileReader();
      reader.onload = (e) => {
        this.currentImageDataUrl = e.target.result;
        if (this.previewEl) {
          this.previewEl.innerHTML = `<img src="${this.currentImageDataUrl}" alt="Preview" style="max-height: 180px; max-width: 100%; border-radius: 6px;">`;
        }
      };
      reader.readAsDataURL(file);
    }

    bindDragDropPaste() {
      const editorRoot = this.editor.root;

      // Drag & Drop images into editor
      editorRoot.addEventListener('dragover', (e) => {
        e.preventDefault();
      });

      editorRoot.addEventListener('drop', (e) => {
        e.preventDefault();
        const files = e.dataTransfer && e.dataTransfer.files;
        if (files && files.length > 0 && files[0].type.startsWith('image/')) {
          this.insertFileDirectly(files[0]);
        }
      });

      // Paste image from clipboard (Ctrl+V)
      editorRoot.addEventListener('paste', (e) => {
        const items = e.clipboardData && e.clipboardData.items;
        if (!items) return;

        for (let i = 0; i < items.length; i++) {
          if (items[i].type.startsWith('image/')) {
            const file = items[i].getAsFile();
            if (file) {
              e.preventDefault();
              this.insertFileDirectly(file);
              break;
            }
          }
        }
      });
    }

    insertFileDirectly(file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const dataUrl = e.target.result;
        const range = this.editor.getSelection(true);
        const index = range ? range.index : this.editor.getLength();

        this.editor.insertEmbed(index, 'customImage', {
          src: dataUrl,
          alt: file.name || 'Изображение',
          caption: '',
          align: 'center'
        }, 'user');

        this.editor.insertText(index + 1, '\n', 'user');
        this.editor.setSelection(index + 2, 'user');
      };
      reader.readAsDataURL(file);
    }

    openModal(index = null) {
      this.currentInsertionIndex = index;
      this.currentImageDataUrl = null;

      if (this.fileInput) this.fileInput.value = '';
      if (this.urlInput) this.urlInput.value = '';
      if (this.altInput) this.altInput.value = '';
      if (this.captionInput) this.captionInput.value = '';
      if (this.alignSelect) this.alignSelect.value = 'center';
      if (this.previewEl) this.previewEl.innerHTML = '';

      if (this.imageModal) {
        this.imageModal.classList.add('show');
      }
    }

    insertImage() {
      let src = '';
      if (this.activeTab === 'file') {
        src = this.currentImageDataUrl;
      } else {
        src = this.urlInput ? this.urlInput.value.trim() : '';
      }

      if (!src) {
        alert('Пожалуйста, выберите файл или укажите URL изображения.');
        return;
      }

      const alt = this.altInput ? this.altInput.value.trim() : '';
      const caption = this.captionInput ? this.captionInput.value.trim() : '';
      const align = this.alignSelect ? this.alignSelect.value : 'center';

      let index = this.currentInsertionIndex;
      if (index === null || index === undefined) {
        const range = this.editor.getSelection(true);
        index = range ? range.index : this.editor.getLength();
      }

      this.editor.insertEmbed(index, 'customImage', {
        src: src,
        alt: alt,
        caption: caption,
        align: align
      }, 'user');

      this.editor.insertText(index + 1, '\n', 'user');
      this.editor.setSelection(index + 2, 'user');

      if (this.imageModal) {
        this.imageModal.classList.remove('show');
      }
    }

    sanitizeSrc(url) {
      if (!url) return '';
      const cleaned = url.trim();
      if (cleaned.startsWith('javascript:') || cleaned.startsWith('data:text/html') || cleaned.startsWith('vbscript:')) {
        return '';
      }
      return cleaned;
    }
  }

  // Safe sandbox attribute configuration for video embed iframes (DoD requirement)
  MediaManager.SAFE_IFRAME_SANDBOX = 'allow-scripts allow-same-origin allow-presentation allow-popups';

  window.MediaManager = MediaManager;

})(window);
