/**
 * Antigravity WYSIWYG Editor - Floating Block Inserter (+) & Menu
 * Anchored to active insertion point, supports Up/Down/Enter/Escape keyboard navigation,
 * slash command '/' in empty line, 12 block items in exact order + Additional group.
 */

(function (window) {
  'use strict';

  class BlockInserter {
    constructor(editor) {
      this.editor = editor;
      this.inserter = document.getElementById('block-inserter');
      this.inserterBtn = document.getElementById('block-inserter-btn');
      this.blockMenu = document.getElementById('block-menu');
      this.headerSubmenu = document.getElementById('header-submenu');
      this.editorCard = document.getElementById('editor-card');

      if (!this.inserter || !this.inserterBtn || !this.blockMenu) return;

      // Portal to document.body to ensure unconstrained fixed positioning relative to viewport
      if (typeof document !== 'undefined' && document.body && this.blockMenu.parentElement !== document.body) {
        document.body.appendChild(this.blockMenu);
      }

      this.currentLineIndex = 0;
      this.highlightedIndex = -1;
      this.menuItems = [];

      this.bindEvents();
    }

    bindEvents() {
      // Track selection or cursor movement
      this.editor.on('selection-change', (range) => {
        if (!range) {
          this.hide();
          return;
        }

        // Only show '+' inserter if selection is collapsed (a single caret position)
        if (range.length === 0) {
          this.updatePosition(range.index);
        } else {
          this.hide();
        }
      });

      // Toggle menu on "+" button click
      this.inserterBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleMenu();
      });

      // Slash command '/' in empty line to trigger block menu
      this.editor.root.addEventListener('keydown', (e) => {
        if (e.key === '/') {
          const range = this.editor.getSelection();
          if (range && range.length === 0) {
            const [line] = this.editor.getLine(range.index);
            const lineText = line ? line.domNode.textContent : '';
            // If line is empty or whitespace
            if (!lineText.trim()) {
              setTimeout(() => {
                // Delete the typed '/'
                const currentRange = this.editor.getSelection();
                if (currentRange && currentRange.index > 0) {
                  this.editor.deleteText(currentRange.index - 1, 1);
                }
                this.updatePosition(range.index);
                this.openMenu();
              }, 10);
            }
          }
        }
      });

      // Handle item click in block menu
      this.blockMenu.addEventListener('click', (e) => {
        const item = e.target.closest('.block-menu-item');
        if (!item) return;

        const blockType = item.getAttribute('data-block');
        if (blockType === 'header') {
          this.insertHeader(2);
          this.closeMenu();
          return;
        }

        this.insertBlock(blockType);
        this.closeMenu();
      });

      // Keyboard navigation inside block menu (Arrows, Enter, Escape)
      document.addEventListener('keydown', (e) => {
        if (!this.blockMenu.classList.contains('show')) return;

        if (e.key === 'Escape') {
          e.preventDefault();
          this.closeMenu();
          this.editor.focus();
          return;
        }

        if (e.key === 'ArrowDown') {
          e.preventDefault();
          this.navigateMenu(1);
          return;
        }

        if (e.key === 'ArrowUp') {
          e.preventDefault();
          this.navigateMenu(-1);
          return;
        }

        if (e.key === 'Enter') {
          e.preventDefault();
          if (this.highlightedIndex >= 0 && this.menuItems[this.highlightedIndex]) {
            const item = this.menuItems[this.highlightedIndex];
            const blockType = item.getAttribute('data-block');
            if (blockType === 'header') {
              this.insertHeader(2);
              this.closeMenu();
            } else {
              this.insertBlock(blockType);
              this.closeMenu();
            }
          }
        }
      });

      // Close menu when clicking outside
      document.addEventListener('click', (e) => {
        if (!this.blockMenu.contains(e.target) &&
            !this.inserterBtn.contains(e.target)) {
          this.closeMenu();
        }
      });

      // Dynamic repositioning on scroll and resize
      const handleScrollOrResize = () => {
        if (this.blockMenu && this.blockMenu.classList.contains('show')) {
          this.updateMenuPosition();
        }
      };

      window.addEventListener('scroll', handleScrollOrResize, { passive: true, capture: true });
      window.addEventListener('resize', handleScrollOrResize, { passive: true });

      if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', handleScrollOrResize, { passive: true });
        window.visualViewport.addEventListener('scroll', handleScrollOrResize, { passive: true });
      }
    }

    updatePosition(index) {
      this.currentLineIndex = index;

      const bounds = this.editor.getBounds(index);
      if (!bounds) {
        this.hide();
        return;
      }

      const editorCard = this.editorCard || this.editor.container;
      const cardRect = editorCard.getBoundingClientRect();
      const containerRect = this.editor.container.getBoundingClientRect();

      // Calculate vertical offset relative to editor-card
      const topOffset = (containerRect.top - cardRect.top) + bounds.top;

      this.inserter.style.top = `${topOffset}px`;
      this.inserter.classList.add('visible');

      if (this.blockMenu && this.blockMenu.classList.contains('show')) {
        this.updateMenuPosition();
      }
    }

    hide() {
      if (this.inserter) {
        this.inserter.classList.remove('visible');
      }
      this.closeMenu();
    }

    toggleMenu() {
      const isOpen = this.blockMenu.classList.contains('show');
      if (isOpen) {
        this.closeMenu();
      } else {
        this.openMenu();
      }
    }

    openMenu() {
      this.menuItems = Array.from(this.blockMenu.querySelectorAll('.block-menu-item'));
      this.highlightedIndex = 0;
      this.updateHighlight();

      this.blockMenu.classList.add('show');
      this.inserterBtn.classList.add('active');

      this.updateMenuPosition();
    }

    closeMenu() {
      this.blockMenu.classList.remove('show');
      this.blockMenu.classList.remove('open-up');
      this.blockMenu.classList.remove('open-down');
      this.inserterBtn.classList.remove('active');
      this.highlightedIndex = -1;
      this.clearHighlight();
    }

    updateMenuPosition() {
      if (!this.blockMenu || !this.inserterBtn) return;

      const header = document.querySelector('.app-header');
      const statusBar = document.querySelector('.app-status-bar');
      const headerBottom = header ? header.getBoundingClientRect().bottom : 58;
      const statusTop = statusBar ? statusBar.getBoundingClientRect().top : (window.innerHeight - 44);

      const btnRect = this.inserterBtn.getBoundingClientRect();
      const GAP = 10;
      const minAllowedTop = headerBottom + GAP;
      const maxAllowedBottom = statusTop - GAP;

      // Close menu automatically if button has scrolled out of visible workspace
      if (btnRect.bottom < minAllowedTop || btnRect.top > maxAllowedBottom) {
        this.closeMenu();
        return;
      }

      const spaceBelow = maxAllowedBottom - btnRect.bottom;
      const spaceAbove = btnRect.top - minAllowedTop;

      const menuList = this.blockMenu.querySelector('.block-menu-list');
      const fullMenuHeight = Math.min(440, (menuList ? menuList.scrollHeight : this.blockMenu.scrollHeight) || 440);

      let direction = 'down';
      let maxHeight = fullMenuHeight;
      let top = 'auto';
      let bottom = 'auto';

      if (spaceBelow >= fullMenuHeight + 8) {
        direction = 'down';
        maxHeight = Math.min(fullMenuHeight, spaceBelow - 8);
        top = btnRect.bottom + 6;
        bottom = 'auto';
      } else if (spaceAbove >= fullMenuHeight + 8) {
        direction = 'up';
        maxHeight = Math.min(fullMenuHeight, spaceAbove - 8);
        bottom = (window.innerHeight - btnRect.top) + 6;
        top = 'auto';
      } else {
        // Insufficient space for full menu in either direction
        direction = spaceBelow >= spaceAbove ? 'down' : 'up';
        const chosenSpace = direction === 'down' ? spaceBelow : spaceAbove;
        maxHeight = Math.max(140, chosenSpace - 8);
        if (direction === 'down') {
          top = btnRect.bottom + 6;
          bottom = 'auto';
        } else {
          bottom = (window.innerHeight - btnRect.top) + 6;
          top = 'auto';
        }
      }

      // Horizontal clamping: keep within viewport with margin
      const menuWidth = this.blockMenu.offsetWidth || 330;
      const left = Math.max(12, Math.min(btnRect.left, window.innerWidth - menuWidth - 12));

      // Apply styles to blockMenu
      this.blockMenu.style.position = 'fixed';
      this.blockMenu.style.left = `${left}px`;
      this.blockMenu.style.top = top !== 'auto' ? `${top}px` : 'auto';
      this.blockMenu.style.bottom = bottom !== 'auto' ? `${bottom}px` : 'auto';
      this.blockMenu.style.maxHeight = `${maxHeight}px`;
      this.blockMenu.style.overflowY = 'auto';
      this.blockMenu.style.overscrollBehavior = 'contain';
      this.blockMenu.style.zIndex = '60';

      if (direction === 'up') {
        this.blockMenu.classList.add('open-up');
        this.blockMenu.classList.remove('open-down');
      } else {
        this.blockMenu.classList.add('open-down');
        this.blockMenu.classList.remove('open-up');
      }
    }

    navigateMenu(direction) {
      if (!this.menuItems.length) return;

      this.highlightedIndex += direction;
      if (this.highlightedIndex < 0) {
        this.highlightedIndex = this.menuItems.length - 1;
      } else if (this.highlightedIndex >= this.menuItems.length) {
        this.highlightedIndex = 0;
      }

      this.updateHighlight();
    }

    updateHighlight() {
      this.clearHighlight();
      if (this.highlightedIndex >= 0 && this.menuItems[this.highlightedIndex]) {
        const item = this.menuItems[this.highlightedIndex];
        item.classList.add('selected');
        item.scrollIntoView({ block: 'nearest' });
      }
    }

    clearHighlight() {
      if (this.menuItems) {
        this.menuItems.forEach(item => item.classList.remove('selected'));
      }
    }

    insertHeader(level) {
      const index = this.currentLineIndex;
      this.editor.focus();
      this.editor.formatLine(index, 1, 'header', level);
    }

    /**
     * Insert block by type in exact order of specification
     */
    insertBlock(type) {
      const index = this.currentLineIndex;
      this.editor.focus();

      // Check if current line is empty
      const [line, offset] = this.editor.getLine(index);
      const isLineEmpty = line && line.domNode.textContent.trim() === '';

      switch (type) {
        // 1. Header (H2 default)
        case 'header':
          this.insertHeader(2);
          break;

        // 2. Quote (blockquote)
        case 'blockquote':
          this.editor.formatLine(index, 1, 'blockquote', true);
          break;

        // 3. List (bullet)
        case 'bullet-list':
          this.editor.formatLine(index, 1, 'list', 'bullet');
          break;

        // 4. Numbered list (ordered)
        case 'ordered-list':
          this.editor.formatLine(index, 1, 'list', 'ordered');
          break;

        // 5. Media element (YouTube, Vimeo, VK Video)
        case 'media':
          if (window.EditorApp && window.EditorApp.Toolbar) {
            window.EditorApp.Toolbar.openMediaModal(index);
          }
          break;

        // 6. Image
        case 'image':
          if (window.EditorApp && window.EditorApp.Media) {
            window.EditorApp.Media.openModal(index);
          }
          break;

        // 7. Divider (<hr>)
        case 'divider':
          this.editor.insertEmbed(index, 'divider', true, 'user');
          if (isLineEmpty) {
            this.editor.setSelection(index + 1, 'user');
          } else {
            this.editor.insertText(index + 1, '\n', 'user');
            this.editor.setSelection(index + 2, 'user');
          }
          break;

        // 8. Code
        case 'code-block':
          this.editor.formatLine(index, 1, 'code-block', true);
          break;

        // 9. Formula (Block LaTeX)
        case 'formula':
          if (window.EditorApp && window.EditorApp.Toolbar) {
            window.EditorApp.Toolbar.openFormulaModal(null, index, true);
          }
          break;

        // 10. Spoiler (<details><summary>)
        case 'spoiler':
          this.editor.insertEmbed(index, 'spoiler', {
            title: 'Заголовок спойлера (нажмите для редактирования)',
            body: 'Скрытый текст спойлера...'
          }, 'user');
          if (!isLineEmpty) {
            this.editor.insertText(index + 1, '\n', 'user');
            this.editor.setSelection(index + 2, 'user');
          } else {
            this.editor.setSelection(index + 1, 'user');
          }
          break;

        // 11. Anchor
        case 'anchor':
          if (window.EditorApp && window.EditorApp.Toolbar) {
            window.EditorApp.Toolbar.openAnchorModal(index);
          }
          break;

        // 12. Person
        case 'person':
          if (window.EditorApp && window.EditorApp.Toolbar) {
            window.EditorApp.Toolbar.openPersonModal(index);
          }
          break;

        // Additional: Table
        case 'table':
          if (window.EditorApp && window.EditorApp.Table) {
            window.EditorApp.Table.insertDefaultTable(index);
          }
          break;

        default:
          break;
      }
    }
  }

  window.BlockInserter = BlockInserter;

})(window);
