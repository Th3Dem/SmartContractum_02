/**
 * Antigravity WYSIWYG Editor - Media & Image Manager
 * 100% offline-first image upload (DataURL/base64), URL insertion, caption, alt, and alignment
 */

(function (window) {
  'use strict';

  class MediaManager {
    constructor(editor) {
      this.editor = editor;
      this.modal = document.getElementById('image-modal');
      this.fileInput = document.getElementById('image-file-input');
      this.urlInput = document.getElementById('image-url-input');
      this.altInput = document.getElementById('image-alt-input');
      this.captionInput = document.getElementById('image-caption-input');
      this.alignSelect = document.getElementById('image-align-select');
      this.previewEl = document.getElementById('image-preview');
      this.insertBtn = document.getElementById('image-insert-btn');

      this.currentImageDataUrl = null;
      this.activeTab = 'file'; // 'file' or 'url'

      this.initElements();
      this.bindEvents();
      this.bindDragDropPaste();
    }

    initElements() {
      // Tab switching
      const tabBtns = document.querySelectorAll('[data-image-tab]');
      tabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
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

      // Drag & Drop
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

    insertImage() {
      let src = '';
      if (this.activeTab === 'file') {
        src = this.currentImageDataUrl;
      } else {
        src = this.urlInput ? this.urlInput.value.trim() : '';
      }

      if (!src) {
        alert('Пожалуйста, выберите файл изображения или введите ссылку.');
        return;
      }

      const alt = this.altInput ? this.altInput.value.trim() : '';
      const caption = this.captionInput ? this.captionInput.value.trim() : '';
      const align = this.alignSelect ? this.alignSelect.value : 'center';

      const range = this.editor.getSelection(true);
      const index = range ? range.index : this.editor.getLength();

      this.editor.insertEmbed(index, 'customImage', {
        src: src,
        alt: alt,
        caption: caption,
        align: align
      }, 'user');

      this.editor.insertText(index + 1, '\n', 'user');
      this.editor.setSelection(index + 2, 'user');

      this.closeModal();
    }

    sanitizeSrc(src) {
      if (/^(javascript|vbscript|data:text\/html):/i.test(src)) {
        return '';
      }
      return src;
    }

    openModal() {
      this.resetModal();
      if (this.modal) {
        this.modal.classList.add('show');
      }
    }

    closeModal() {
      if (this.modal) {
        this.modal.classList.remove('show');
      }
      this.resetModal();
    }

    resetModal() {
      this.currentImageDataUrl = null;
      if (this.fileInput) this.fileInput.value = '';
      if (this.urlInput) this.urlInput.value = '';
      if (this.altInput) this.altInput.value = '';
      if (this.captionInput) this.captionInput.value = '';
      if (this.previewEl) this.previewEl.innerHTML = '';
      if (this.alignSelect) this.alignSelect.value = 'center';
    }
  }

  window.MediaManager = MediaManager;

})(window);
