/**
 * Antigravity WYSIWYG Editor - Node Controls & Image Menu (Habr Reference)
 * 1. Node Controls for each block:
 *    - Left: node__drag-control with ':::' icon (draggable="true") + HTML5 Drag & Drop reordering with visual drop-line.
 *    - Right: node__dots button ('...') opening context menu:
 *      * «Преобразовать» (Параграф, H2, H3, Цитата, Список)
 *      * «Дублировать блок»
 *      * «Удалить блок»
 * 2. Floating Image Menu:
 *    - Above clicked image: «В тексте», «Во всю ширину», «В рамку», «Удалить»
 *    - Editable caption (<figcaption>) below image.
 * 100% offline-first.
 */

(function (window) {
  'use strict';

  /* ==========================================================================
     Node Controls Manager
     ========================================================================== */
  class NodeControlsManager {
    constructor(editor) {
      this.editor = editor;
      this.editorCard = document.getElementById('editor-card');
      this.controls = document.getElementById('node-controls');
      this.dragHandle = this.controls ? this.controls.querySelector('.node__drag-control') : null;
      this.dotsBtn = this.controls ? this.controls.querySelector('.node__dots') : null;
      this.actionMenu = document.getElementById('node-action-menu');
      this.dropLine = document.getElementById('node-drop-line');

      this.activeBlock = null;
      this.draggedBlock = null;
      this.isMenuOpen = false;

      if (!this.controls || !this.editorCard) return;

      this.bindHoverAndFocus();
      this.bindDragAndDrop();
      this.bindActionMenu();
    }

    bindHoverAndFocus() {
      const editorRoot = this.editor.root;

      // Track mouseover across blocks in .ql-editor
      editorRoot.addEventListener('mouseover', (e) => {
        if (this.isMenuOpen || this.draggedBlock) return;
        const block = e.target.closest('.ql-editor > *');
        if (block && block !== this.activeBlock) {
          this.attachToBlock(block);
        }
      });

      // Update position on selection / cursor change
      this.editor.on('selection-change', (range) => {
        if (!range || this.isMenuOpen || this.draggedBlock) return;
        const [line] = this.editor.getLine(range.index);
        if (line && line.domNode) {
          const block = line.domNode.closest('.ql-editor > *');
          if (block) {
            this.attachToBlock(block);
          }
        }
      });

      // Keep controls visible when hovering over the controls themselves
      this.controls.addEventListener('mouseenter', () => {
        // keep active
      });

      // Hide controls when moving mouse away from editor card
      this.editorCard.addEventListener('mouseleave', (e) => {
        if (this.isMenuOpen || this.draggedBlock) return;
        // Check if cursor left editor card completely
        const rect = this.editorCard.getBoundingClientRect();
        if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) {
          this.hide();
        }
      });
    }

    attachToBlock(block) {
      if (!block || (window.EditorApp && window.EditorApp.mode === 'preview')) {
        this.hide();
        return;
      }

      this.activeBlock = block;

      const cardRect = this.editorCard.getBoundingClientRect();
      const blockRect = block.getBoundingClientRect();

      // Top aligned with top of the block + small vertical centering offset
      const topOffset = blockRect.top - cardRect.top + Math.max(0, (blockRect.height - 28) / 2);

      this.controls.style.top = `${topOffset}px`;
      this.controls.style.display = 'flex';
      this.controls.classList.add('visible');

      // Also ensure block has node class for styling compatibility
      block.classList.add('node-active-hover');
    }

    hide() {
      if (this.isMenuOpen) return;
      if (this.controls) {
        this.controls.style.display = 'none';
        this.controls.classList.remove('visible');
      }
      if (this.activeBlock) {
        this.activeBlock.classList.remove('node-active-hover');
        this.activeBlock = null;
      }
      this.closeMenu();
    }

    /* ==========================================================================
       HTML5 Drag & Drop Reordering
       ========================================================================== */
    bindDragAndDrop() {
      if (!this.dragHandle) return;

      this.dragHandle.addEventListener('dragstart', (e) => {
        if (!this.activeBlock) {
          e.preventDefault();
          return;
        }

        this.draggedBlock = this.activeBlock;
        this.draggedBlock.classList.add('is-dragging');
        this.closeMenu();

        if (e.dataTransfer) {
          e.dataTransfer.effectAllowed = 'move';
          e.dataTransfer.setData('text/plain', 'antigravity-node');
          // Ghost preview image adjustment
          if (e.dataTransfer.setDragImage) {
            e.dataTransfer.setDragImage(this.draggedBlock, 20, 20);
          }
        }
      });

      this.dragHandle.addEventListener('dragend', () => {
        if (this.draggedBlock) {
          this.draggedBlock.classList.remove('is-dragging');
          this.draggedBlock = null;
        }
        if (this.dropLine) {
          this.dropLine.style.display = 'none';
        }
      });

      const editorRoot = this.editor.root;

      editorRoot.addEventListener('dragover', (e) => {
        if (!this.draggedBlock) return;
        e.preventDefault();

        const targetBlock = e.target.closest('.ql-editor > *');
        if (!targetBlock || targetBlock === this.draggedBlock) {
          if (this.dropLine) this.dropLine.style.display = 'none';
          return;
        }

        const cardRect = this.editorCard.getBoundingClientRect();
        const targetRect = targetBlock.getBoundingClientRect();
        const isAbove = (e.clientY - targetRect.top) < (targetRect.height / 2);

        if (this.dropLine) {
          const lineTop = isAbove
            ? (targetRect.top - cardRect.top)
            : (targetRect.bottom - cardRect.top);

          this.dropLine.style.top = `${lineTop}px`;
          this.dropLine.style.display = 'block';
          this.dropLine.setAttribute('data-target-above', isAbove ? 'true' : 'false');
          this.currentDropTarget = targetBlock;
          this.currentDropAbove = isAbove;
        }
      });

      editorRoot.addEventListener('drop', (e) => {
        if (!this.draggedBlock || !this.currentDropTarget) return;
        e.preventDefault();

        const targetBlock = this.currentDropTarget;
        const isAbove = this.currentDropAbove;

        // Move DOM node cleanly
        if (isAbove) {
          targetBlock.parentNode.insertBefore(this.draggedBlock, targetBlock);
        } else {
          targetBlock.parentNode.insertBefore(this.draggedBlock, targetBlock.nextSibling);
        }

        // Notify Quill to update internal document model and history
        this.editor.update('user');

        if (this.dropLine) {
          this.dropLine.style.display = 'none';
        }

        if (this.draggedBlock) {
          this.draggedBlock.classList.remove('is-dragging');
        }

        this.attachToBlock(this.draggedBlock);
        this.draggedBlock = null;
        this.currentDropTarget = null;
      });
    }

    /* ==========================================================================
       Node Actions Context Menu (...)
       ========================================================================== */
    bindActionMenu() {
      if (!this.dotsBtn || !this.actionMenu) return;

      this.dotsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleMenu();
      });

      // Close menu when clicking outside
      document.addEventListener('click', (e) => {
        if (this.isMenuOpen && !this.actionMenu.contains(e.target) && !this.dotsBtn.contains(e.target)) {
          this.closeMenu();
        }
      });

      // Transform Submenu Toggle
      const transformBtn = document.getElementById('btn-node-transform');
      const transformSubmenu = document.getElementById('node-transform-submenu');
      if (transformBtn && transformSubmenu) {
        transformBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          transformSubmenu.classList.toggle('show');
        });
      }

      // Handle Transform Item Clicks
      document.querySelectorAll('[data-transform]').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const targetType = btn.getAttribute('data-transform');
          this.transformBlock(targetType);
          this.closeMenu();
        });
      });

      // Handle Duplicate Block Click
      const dupBtn = document.getElementById('btn-node-duplicate');
      if (dupBtn) {
        dupBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.duplicateBlock();
          this.closeMenu();
        });
      }

      // Handle Delete Block Click
      const delBtn = document.getElementById('btn-node-delete');
      if (delBtn) {
        delBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.deleteBlock();
          this.closeMenu();
        });
      }
    }

    toggleMenu() {
      if (this.isMenuOpen) {
        this.closeMenu();
      } else {
        this.openMenu();
      }
    }

    openMenu() {
      if (!this.actionMenu) return;
      this.isMenuOpen = true;
      this.actionMenu.classList.add('show');
      this.dotsBtn.classList.add('active');
    }

    closeMenu() {
      if (!this.actionMenu) return;
      this.isMenuOpen = false;
      this.actionMenu.classList.remove('show');
      if (this.dotsBtn) this.dotsBtn.classList.remove('active');
      const submenu = document.getElementById('node-transform-submenu');
      if (submenu) submenu.classList.remove('show');
    }

    getActiveBlockBlot() {
      if (!this.activeBlock || !window.Quill) return null;
      try {
        const blot = window.Quill.find(this.activeBlock);
        return blot;
      } catch (err) {
        return null;
      }
    }

    transformBlock(targetType) {
      const blot = this.getActiveBlockBlot();
      if (!blot) return;

      const index = this.editor.getIndex(blot);
      const length = blot.length();

      switch (targetType) {
        case 'paragraph':
        case 'p':
          this.editor.formatLine(index, length, { header: false, blockquote: false, list: false }, 'user');
          break;
        case 'header-2':
        case 'h2':
          this.editor.formatLine(index, length, { header: 2, blockquote: false, list: false }, 'user');
          break;
        case 'header-3':
        case 'h3':
          this.editor.formatLine(index, length, { header: 3, blockquote: false, list: false }, 'user');
          break;
        case 'blockquote':
          this.editor.formatLine(index, length, { header: false, blockquote: true, list: false }, 'user');
          break;
        case 'bullet-list':
        case 'bullet':
          this.editor.formatLine(index, length, { header: false, blockquote: false, list: 'bullet' }, 'user');
          break;
      }
    }

    duplicateBlock() {
      const blot = this.getActiveBlockBlot();
      if (!blot) return;

      const index = this.editor.getIndex(blot);
      const length = blot.length();
      const Delta = this.editor.constructor.import ? this.editor.constructor.import('delta') : window.Quill.import('delta');

      const blockDelta = this.editor.getContents(index, length);
      if (Delta && blockDelta) {
        this.editor.updateContents(new Delta().retain(index + length).concat(blockDelta), 'user');
      }
    }

    deleteBlock() {
      const blot = this.getActiveBlockBlot();
      if (!blot) {
        if (this.activeBlock) {
          this.activeBlock.remove();
          this.editor.update('user');
        }
        this.hide();
        return;
      }

      const index = this.editor.getIndex(blot);
      const length = blot.length();
      this.editor.deleteText(index, length, 'user');
      this.hide();
    }
  }


  /* ==========================================================================
     Floating Image Menu Manager (Habr Image-Menu Reference)
     ========================================================================== */
  class ImageMenuManager {
    constructor(editor) {
      this.editor = editor;
      this.editorCard = document.getElementById('editor-card');
      this.menu = document.getElementById('image-menu');
      this.btnInline = document.getElementById('btn-image-inline');
      this.btnFull = document.getElementById('btn-image-full');
      this.btnBorder = document.getElementById('btn-image-border');
      this.btnDelete = document.getElementById('btn-image-delete');

      this.activeFigure = null;

      if (!this.menu || !this.editorCard) return;

      this.bindEvents();
    }

    bindEvents() {
      const editorRoot = this.editor.root;

      // Click on image or figure in editor
      editorRoot.addEventListener('click', (e) => {
        const img = e.target.closest('img');
        const figure = e.target.closest('figure, .editor-figure');

        if (img || figure) {
          const targetFigure = figure || (img ? img.closest('figure') || img.parentElement : null);
          if (targetFigure) {
            e.stopPropagation();
            this.showForFigure(targetFigure);
          }
        } else if (!this.menu.contains(e.target)) {
          this.hide();
        }
      });

      // Close menu when clicking outside
      document.addEventListener('click', (e) => {
        if (this.menu && !this.menu.contains(e.target) && !e.target.closest('figure, img')) {
          this.hide();
        }
      });

      // 1. «В тексте» (standard 100% text width)
      if (this.btnInline) {
        this.btnInline.addEventListener('click', (e) => {
          e.stopPropagation();
          if (!this.activeFigure) return;
          this.activeFigure.classList.remove('align-full', 'align-left', 'align-right');
          this.activeFigure.classList.add('align-center');
          this.editor.update('user');
          this.updateButtonsState();
        });
      }

      // 2. «Во всю ширину» (expanded full-card width)
      if (this.btnFull) {
        this.btnFull.addEventListener('click', (e) => {
          e.stopPropagation();
          if (!this.activeFigure) return;
          this.activeFigure.classList.remove('align-center', 'align-left', 'align-right');
          this.activeFigure.classList.add('align-full');
          this.editor.update('user');
          this.updateButtonsState();
        });
      }

      // 3. «В рамку» (toggle border)
      if (this.btnBorder) {
        this.btnBorder.addEventListener('click', (e) => {
          e.stopPropagation();
          if (!this.activeFigure) return;
          this.activeFigure.classList.toggle('has-border');
          this.editor.update('user');
          this.updateButtonsState();
        });
      }

      // 4. «Удалить» (delete image)
      if (this.btnDelete) {
        this.btnDelete.addEventListener('click', (e) => {
          e.stopPropagation();
          if (!this.activeFigure) return;

          let deleted = false;
          if (window.Quill) {
            try {
              const blot = window.Quill.find(this.activeFigure);
              if (blot) {
                const index = this.editor.getIndex(blot);
                const length = blot.length();
                this.editor.deleteText(index, length, 'user');
                deleted = true;
              }
            } catch (err) {
              // fallback
            }
          }

          if (!deleted) {
            this.activeFigure.remove();
            this.editor.update('user');
          }

          this.hide();
        });
      }
    }

    showForFigure(figure) {
      if (!figure || (window.EditorApp && window.EditorApp.mode === 'preview')) {
        this.hide();
        return;
      }

      this.activeFigure = figure;

      // Ensure editable <figcaption> exists
      let caption = figure.querySelector('figcaption');
      if (!caption) {
        caption = document.createElement('figcaption');
        caption.contentEditable = 'true';
        caption.setAttribute('placeholder', 'Подпись к изображению...');
        caption.addEventListener('keydown', (e) => e.stopPropagation());
        caption.addEventListener('keyup', (e) => e.stopPropagation());
        figure.appendChild(caption);
      }

      // Position floating toolbar above image centered
      const cardRect = this.editorCard.getBoundingClientRect();
      const figRect = figure.getBoundingClientRect();

      const topOffset = figRect.top - cardRect.top - 46;
      const leftOffset = (figRect.left - cardRect.left) + (figRect.width / 2);

      this.menu.style.top = `${topOffset}px`;
      this.menu.style.left = `${leftOffset}px`;
      this.menu.style.display = 'block';

      this.updateButtonsState();
    }

    updateButtonsState() {
      if (!this.activeFigure) return;

      const isFull = this.activeFigure.classList.contains('align-full');
      const hasBorder = this.activeFigure.classList.contains('has-border');

      if (this.btnFull) this.btnFull.classList.toggle('active', isFull);
      if (this.btnInline) this.btnInline.classList.toggle('active', !isFull);
      if (this.btnBorder) this.btnBorder.classList.toggle('active', hasBorder);
    }

    hide() {
      if (this.menu) {
        this.menu.style.display = 'none';
      }
      this.activeFigure = null;
    }
  }

  // Bind to window
  window.NodeControlsManager = NodeControlsManager;
  window.ImageMenuManager = ImageMenuManager;

})(window);
