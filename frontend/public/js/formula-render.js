/**
 * SmartContractum formula rendering (Issue #263).
 *
 * Formulas keep their storage format: a block formula is
 * <div class="editor-block-formula" data-latex="..."><div class="formula-rendered">$$...$$</div></div>,
 * an inline formula is <span class="editor-inline-formula" data-latex="...">\(...\)</span>.
 * This module draws them with the vendored KaTeX (vendor/katex, offline) and can put the
 * plain LaTeX text back before the HTML is saved, so stored articles and drafts do not
 * contain KaTeX markup.
 */
(function (window) {
  'use strict';

  const SELECTOR = '.editor-block-formula[data-latex], .editor-inline-formula[data-latex]';
  const KATEX_OPTIONS = { throwOnError: true, strict: 'ignore', trust: false, output: 'htmlAndMathml' };

  function sourceText(latex, isBlock) {
    if (!latex) return isBlock ? '$$ ... $$' : '\\(...)';
    return isBlock ? `$$\n${latex}\n$$` : `\\(${latex}\\)`;
  }

  function targetOf(node, isBlock) {
    return isBlock ? (node.querySelector('.formula-rendered') || node) : node;
  }

  /** Draws LaTeX into an element; on error shows the source text and returns false. */
  function renderLatex(latex, element, isBlock) {
    if (!element) return false;
    const text = String(latex || '').trim();
    if (!text || !window.katex) {
      element.textContent = sourceText(text, isBlock);
      return false;
    }
    try {
      window.katex.render(text, element, Object.assign({ displayMode: Boolean(isBlock) }, KATEX_OPTIONS));
      return true;
    } catch (err) {
      element.textContent = sourceText(text, isBlock);
      return false;
    }
  }

  /** Renders one stored formula node in place. */
  function render(node) {
    if (!node || !node.getAttribute) return false;
    const isBlock = node.classList.contains('editor-block-formula');
    const latex = node.getAttribute('data-latex') || '';
    const ok = renderLatex(latex, targetOf(node, isBlock), isBlock);
    node.classList.toggle('is-rendered', ok);
    node.classList.toggle('formula-error', !ok && Boolean(latex.trim()));
    if (!ok && latex.trim()) {
      node.setAttribute('title', 'Не удалось отобразить формулу, показан исходный LaTeX');
    } else if (node.getAttribute('title') === 'Не удалось отобразить формулу, показан исходный LaTeX') {
      node.removeAttribute('title');
    }
    return ok;
  }

  /** Renders every stored formula inside root. */
  function renderIn(root) {
    if (!root || !root.querySelectorAll) return 0;
    let count = 0;
    root.querySelectorAll(SELECTOR).forEach(node => { if (render(node)) count += 1; });
    return count;
  }

  /** HTML of root with every formula reduced back to its stored LaTeX text. */
  function sourceHtml(root) {
    if (!root) return '';
    const clone = root.cloneNode(true);
    clone.querySelectorAll(SELECTOR).forEach(node => {
      const isBlock = node.classList.contains('editor-block-formula');
      const latex = node.getAttribute('data-latex') || '';
      // Inline embeds keep Quill's inner wrapper; only the visible content changes
      const target = isBlock ? targetOf(node, true) : (node.querySelector('span[contenteditable]') || node);
      target.textContent = sourceText(latex, isBlock);
      node.classList.remove('is-rendered', 'formula-error');
    });
    return clone.innerHTML;
  }

  window.SCFormula = { render, renderIn, renderLatex, sourceHtml };
})(window);
