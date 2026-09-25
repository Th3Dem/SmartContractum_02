/**
 * Antigravity WYSIWYG Editor - Interactive Table Manager
 * Table insertion, row/column addition/removal, and contextual action bar
 */

(function (window) {
  'use strict';

  class TableManager {
    constructor(editor) {
      this.editor = editor;
      this.tableModule = editor.getModule('table');
      this.actionBar = document.getElementById('table-action-bar');
      this.tableModal = document.getElementById('table-modal');
      this.rowsInput = document.getElementById('table-rows-input');
      this.colsInput = document.getElementById('table-cols-input');
      this.insertBtn = document.getElementById('table-insert-btn');

      this.currentCell = null;
      this.bindEvents();
    }

    bindEvents() {
      // Monitor selection to detect when cursor is inside a table
      this.editor.on('selection-change', (range) => {
        if (!range) {
          this.hideActionBar();
          return;
        }

        const [tableNode, rowNode, cellNode] = this.tableModule ? this.tableModule.getTable(range) : [null, null, null];
        if (cellNode && cellNode.domNode) {
          this.currentCell = cellNode.domNode;
          this.showActionBar(cellNode.domNode);
        } else {
          this.currentCell = null;
          this.hideActionBar();
        }
      });

      // Handle table action bar clicks
      if (this.actionBar) {
        this.actionBar.addEventListener('click', (e) => {
          const btn = e.target.closest('button[data-table-action]');
          if (!btn) return;

          const action = btn.getAttribute('data-table-action');
          this.executeAction(action);
        });
      }

      // Insert Table modal events
      if (this.insertBtn) {
        this.insertBtn.addEventListener('click', () => {
          const rows = parseInt(this.rowsInput ? this.rowsInput.value : '3', 10) || 3;
          const cols = parseInt(this.colsInput ? this.colsInput.value : '3', 10) || 3;
          this.insertTable(rows, cols);
          this.closeModal();
        });
      }
    }

    executeAction(action) {
      if (!this.tableModule) return;
      this.editor.focus();

      switch (action) {
        case 'row-above':
          this.tableModule.insertRowAbove();
          break;
        case 'row-below':
          this.tableModule.insertRowBelow();
          break;
        case 'col-left':
          this.tableModule.insertColumnLeft();
          break;
        case 'col-right':
          this.tableModule.insertColumnRight();
          break;
        case 'delete-row':
          this.tableModule.deleteRow();
          break;
        case 'delete-col':
          this.tableModule.deleteColumn();
          break;
        case 'delete-table':
          this.tableModule.deleteTable();
          this.hideActionBar();
          break;
        default:
          break;
      }
    }

    insertTable(rows = 3, cols = 3) {
      if (this.tableModule) {
        this.editor.focus();
        this.tableModule.insertTable(rows, cols);
      }
    }

    insertDefaultTable(index) {
      if (this.tableModule) {
        this.editor.focus();
        if (typeof index === 'number') {
          this.editor.setSelection(index, 0);
        }
        this.tableModule.insertTable(3, 3);
      }
    }

    showActionBar(cellDomNode) {
      if (!this.actionBar || !cellDomNode) return;

      const cellRect = cellDomNode.getBoundingClientRect();
      const editorWrapper = document.querySelector('.editor-wrapper') || document.body;
      const wrapperRect = editorWrapper.getBoundingClientRect();

      const top = (cellRect.top - wrapperRect.top) - 44;
      const left = (cellRect.left - wrapperRect.left);

      this.actionBar.style.top = `${Math.max(0, top)}px`;
      this.actionBar.style.left = `${Math.max(10, left)}px`;
      this.actionBar.classList.add('show');
    }

    hideActionBar() {
      if (this.actionBar) {
        this.actionBar.classList.remove('show');
      }
    }

    openInsertModal() {
      if (this.tableModal) {
        this.tableModal.classList.add('show');
        if (this.rowsInput) this.rowsInput.focus();
      }
    }

    closeModal() {
      if (this.tableModal) {
        this.tableModal.classList.remove('show');
      }
    }
  }

  window.TableManager = TableManager;

})(window);
