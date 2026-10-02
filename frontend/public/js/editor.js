/**
 * Antigravity WYSIWYG Editor - Heading Validation & H1 Duplicate Protection
 * Protects articles from duplicate H1 headings between document title and article body.
 * 100% offline-first.
 */

(function (window) {
  'use strict';

  /**
   * Normalizes heading text by lowercasing, trimming, removing leading markdown hashes,
   * stripping HTML tags, removing punctuation, and collapsing whitespace.
   * @param {string} text
   * @returns {string}
   */
  function normalizeHeading(text) {
    if (!text) return '';
    let str = String(text).replace(/<[^>]*>/g, ' ');
    str = str.replace(/^#+\s*/, '');
    str = str.toLowerCase();
    str = str.replace(/[.,\/#!$%\^&\*;:{}=\-_`~()?"'«»\u2013\u2014]/g, ' ');
    str = str.replace(/\s+/g, ' ').trim();
    return str;
  }

  /**
   * Finds the first meaningful block element inside an editor root.
   * @param {HTMLElement} root
   * @returns {HTMLElement|null}
   */
  function getFirstBlockElement(root) {
    if (!root) return null;
    const children = root.children;
    for (let i = 0; i < children.length; i++) {
      const el = children[i];
      if (el.textContent && el.textContent.trim().length > 0) {
        return el;
      }
    }
    return null;
  }

  /**
   * Checks if the first element in editor is an H1 that matches the article title.
   * @param {HTMLElement|string} editorRoot
   * @param {string} title
   * @param {HTMLElement} [bannerEl]
   * @returns {boolean}
   */
  function checkH1Duplicate(editorRoot, title, bannerEl) {
    const normTitle = normalizeHeading(title);
    if (!normTitle) {
      if (bannerEl) bannerEl.style.display = 'none';
      return false;
    }

    if (typeof editorRoot === 'string') {
      // Markdown or HTML string check
      const raw = editorRoot.trim();
      const firstLine = raw.split('\n')[0] || '';
      if (firstLine.startsWith('# ') && !firstLine.startsWith('## ')) {
        const normHeading = normalizeHeading(firstLine);
        if (normHeading && normHeading === normTitle) {
          if (bannerEl) bannerEl.style.display = 'flex';
          return true;
        }
      }
      const match = raw.match(/<h1[^>]*>(.*?)<\/h1>/i);
      if (match) {
        const normH1 = normalizeHeading(match[1]);
        if (normH1 && normH1 === normTitle) {
          if (bannerEl) bannerEl.style.display = 'flex';
          return true;
        }
      }
      if (bannerEl) bannerEl.style.display = 'none';
      return false;
    }

    const firstEl = getFirstBlockElement(editorRoot);
    if (firstEl && firstEl.tagName === 'H1') {
      const normHeading = normalizeHeading(firstEl.textContent);
      if (normHeading && normHeading === normTitle) {
        if (bannerEl) bannerEl.style.display = 'flex';
        return true;
      }
    }

    if (bannerEl) bannerEl.style.display = 'none';
    return false;
  }

  /**
   * Converts the first H1 in the editor to an H2 element.
   * @param {HTMLElement} editorRoot
   * @param {HTMLElement} [bannerEl]
   * @returns {HTMLElement|null}
   */
  function convertFirstH1ToH2(editorRoot, bannerEl) {
    const firstEl = getFirstBlockElement(editorRoot);
    if (firstEl && firstEl.tagName === 'H1') {
      const h2 = document.createElement('h2');
      h2.innerHTML = firstEl.innerHTML;
      if (firstEl.className) h2.className = firstEl.className;
      firstEl.replaceWith(h2);
      if (bannerEl) bannerEl.style.display = 'none';
      return h2;
    }
    if (bannerEl) bannerEl.style.display = 'none';
    return null;
  }

  /**
   * Removes the first H1 element from the editor.
   * @param {HTMLElement} editorRoot
   * @param {HTMLElement} [bannerEl]
   * @returns {boolean}
   */
  function removeFirstH1(editorRoot, bannerEl) {
    const firstEl = getFirstBlockElement(editorRoot);
    if (firstEl && firstEl.tagName === 'H1') {
      firstEl.remove();
      if (bannerEl) bannerEl.style.display = 'none';
      return true;
    }
    if (bannerEl) bannerEl.style.display = 'none';
    return false;
  }

  const H1DuplicateChecker = {
    normalizeHeading: normalizeHeading,
    getFirstBlockElement: getFirstBlockElement,
    checkH1Duplicate: checkH1Duplicate,
    convertFirstH1ToH2: convertFirstH1ToH2,
    removeFirstH1: removeFirstH1
  };

  // Wire UI banner events on DOM ready if elements are present
  document.addEventListener('DOMContentLoaded', function () {
    const banner = document.getElementById('h1DuplicateWarningBanner');
    const titleInput = document.getElementById('article-title');
    const editorEl = document.getElementById('editor');
    const btnConvertH2 = document.getElementById('btnConvertH2');
    const btnRemove = document.getElementById('btnRemoveDuplicateH1');
    const btnDismiss = document.getElementById('btnDismissH1Warning');

    function runCheck() {
      const editorRoot = (editorEl && editorEl.querySelector('.ql-editor')) || editorEl;
      const title = titleInput ? titleInput.value : '';
      checkH1Duplicate(editorRoot, title, banner);
    }

    if (btnConvertH2) {
      btnConvertH2.addEventListener('click', function () {
        const editorRoot = (editorEl && editorEl.querySelector('.ql-editor')) || editorEl;
        convertFirstH1ToH2(editorRoot, banner);
      });
    }

    if (btnRemove) {
      btnRemove.addEventListener('click', function () {
        const editorRoot = (editorEl && editorEl.querySelector('.ql-editor')) || editorEl;
        removeFirstH1(editorRoot, banner);
      });
    }

    if (btnDismiss) {
      btnDismiss.addEventListener('click', function () {
        if (banner) banner.style.display = 'none';
      });
    }

    if (titleInput) {
      titleInput.addEventListener('input', runCheck);
    }

    if (editorEl) {
      editorEl.addEventListener('paste', function () {
        setTimeout(runCheck, 100);
      });
    }
  });

  if (typeof window !== 'undefined') {
    window.H1DuplicateChecker = H1DuplicateChecker;
    window.normalizeHeading = normalizeHeading;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = H1DuplicateChecker;
  }
})(typeof window !== 'undefined' ? window : globalThis);
