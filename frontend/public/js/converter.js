/**
 * Antigravity WYSIWYG Editor - Document Converter & Exporter
 * HTML, Markdown, JSON export, JSON import, loss warnings, and strict XSS sanitization
 * with safe video embed whitelist.
 */

(function (window) {
  'use strict';

  class Converter {
    constructor(editor, titleInput) {
      this.editor = editor;
      this.titleInput = titleInput;
      this.lastExportWarnings = [];
    }

    getTitle() {
      return this.titleInput ? this.titleInput.value.trim() : '';
    }

    setTitle(title) {
      if (this.titleInput) {
        this.titleInput.value = title || '';
        if (window.EditorApp && window.EditorApp.adjustTitleHeight) {
          window.EditorApp.adjustTitleHeight();
        }
      }
    }

    getLastWarnings() {
      return this.lastExportWarnings;
    }

    /* ==========================================================================
       HTML Sanitization (XSS Protection with Safe Video Whitelist)
       ========================================================================== */
    sanitizeHTML(dirtyHtml) {
      if (!dirtyHtml) return '';

      const doc = new DOMParser().parseFromString(dirtyHtml, 'text/html');
      const body = doc.body;

      // Disallowed elements to remove completely
      const dangerousTags = ['script', 'object', 'embed', 'form', 'style', 'link', 'meta', 'base'];
      dangerousTags.forEach(tag => {
        const elements = body.querySelectorAll(tag);
        elements.forEach(el => el.remove());
      });

      // Filter iframes: Allow ONLY whitelisted safe video embed providers
      const allowedIframeHosts = [
        'youtube.com',
        'www.youtube.com',
        'youtube-nocookie.com',
        'www.youtube-nocookie.com',
        'player.vimeo.com',
        'vk.com',
        'vkvideo.ru'
      ];

      const iframes = body.querySelectorAll('iframe');
      iframes.forEach(iframe => {
        const src = iframe.getAttribute('src') || '';
        let isAllowed = false;
        try {
          const urlObj = new URL(src, window.location.href);
          isAllowed = allowedIframeHosts.some(host => urlObj.hostname === host || urlObj.hostname.endsWith('.' + host));
        } catch (e) {
          isAllowed = false;
        }

        if (!isAllowed) {
          iframe.remove();
        } else {
          // Enforce safe sandbox isolation on allowed video iframes
          iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation allow-popups');
        }
      });

      // Walk all remaining nodes to sanitize attributes
      const allElements = body.querySelectorAll('*');
      allElements.forEach(el => {
        const attrs = Array.from(el.attributes);
        attrs.forEach(attr => {
          const name = attr.name.toLowerCase();
          const val = attr.value.trim().toLowerCase();

          // Remove inline event handlers (onclick, onerror, onload, etc.)
          if (name.startsWith('on')) {
            el.removeAttribute(attr.name);
          }

          // Remove javascript: and vbscript: URIs
          if (['href', 'src', 'action', 'data'].includes(name)) {
            if (val.startsWith('javascript:') || val.startsWith('vbscript:') || val.startsWith('data:text/html')) {
              el.removeAttribute(attr.name);
            }
          }
        });
      });

      return body.innerHTML;
    }

    /* ==========================================================================
       Export Formats
       ========================================================================== */

    /**
     * Export complete article to clean HTML with loss warnings check
     */
    exportToHTML(fullDocument = true) {
      this.lastExportWarnings = [];
      const title = this.getTitle();
      const contentHtml = this.sanitizeHTML(this.editor.root.innerHTML);

      // Check for custom blocks to warn about external viewer compatibility
      if (contentHtml.includes('editor-person-card')) {
        this.lastExportWarnings.push('Блок «Персона» экспортирован с HTML-разметкой карточки, требующей CSS для полного оформления.');
      }
      if (contentHtml.includes('editor-anchor-block')) {
        this.lastExportWarnings.push('Блок «Якорь» экспортирован как элемент с целевым идентификатором.');
      }
      if (contentHtml.includes('editor-block-formula') || contentHtml.includes('editor-inline-formula')) {
        this.lastExportWarnings.push('Формулы экспортированы в нотации LaTeX и требуют поддержки рендера математики.');
      }

      if (!fullDocument) {
        return (title ? `<h1>${this.escapeHTML(title)}</h1>\n` : '') + contentHtml;
      }

      return `<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>${this.escapeHTML(title || 'Статья')}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; max-width: 840px; margin: 40px auto; padding: 0 24px; line-height: 1.7; color: #111827; background-color: #ffffff; }
    h1 { font-size: 2.25rem; font-weight: 800; margin-bottom: 0.8em; line-height: 1.25; }
    h2 { font-size: 1.75rem; font-weight: 700; margin-top: 1.8em; margin-bottom: 0.6em; }
    h3 { font-size: 1.35rem; font-weight: 600; margin-top: 1.5em; margin-bottom: 0.5em; }
    h4 { font-size: 1.15rem; font-weight: 600; margin-top: 1.3em; margin-bottom: 0.5em; }
    pre { background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow-x: auto; font-family: monospace; }
    blockquote { border-left: 4px solid #2563eb; margin: 1.5em 0; padding: 10px 18px; background: #f8fafc; font-style: italic; }
    table { width: 100%; border-collapse: collapse; margin: 1.5em 0; }
    th, td { border: 1px solid #d1d5db; padding: 8px 12px; }
    details { border: 1px solid #d1d5db; border-radius: 8px; margin: 1.5em 0; padding: 12px; background: #f9fafb; }
    summary { font-weight: 600; cursor: pointer; }
    figure { margin: 2em 0; text-align: center; }
    figure img { max-width: 100%; border-radius: 8px; }
    figcaption { color: #6b7280; font-size: 0.875rem; margin-top: 6px; font-style: italic; }
    .editor-person-card { border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; margin: 1.5em 0; display: flex; align-items: center; gap: 16px; }
    .person-avatar-wrap { width: 50px; height: 50px; border-radius: 50%; overflow: hidden; background: #f3f4f6; }
    .person-avatar-wrap img { width: 100%; height: 100%; object-fit: cover; }
    .editor-media-embed { margin: 2em 0; border-radius: 8px; overflow: hidden; }
    .media-aspect-ratio { position: relative; padding-bottom: 56.25%; height: 0; }
    .media-aspect-ratio iframe { position: absolute; top:0; left:0; width:100%; height:100%; border:0; }
    .editor-inline-spoiler { background: #e5e7eb; padding: 0 4px; border-radius: 3px; }
  </style>
</head>
<body>
  ${title ? `<h1>${this.escapeHTML(title)}</h1>` : ''}
  <article>
    ${contentHtml}
  </article>
</body>
</html>`;
    }

    /**
     * Export article to CommonMark / GitHub Flavored Markdown with loss warnings
     */
    exportToMarkdown() {
      this.lastExportWarnings = [];
      const title = this.getTitle();
      let md = '';

      if (title) {
        md += `# ${title}\n\n`;
      }

      const tempContainer = document.createElement('div');
      tempContainer.innerHTML = this.sanitizeHTML(this.editor.root.innerHTML);

      // Detect custom blocks for loss warnings
      if (tempContainer.querySelector('.editor-person-card')) {
        this.lastExportWarnings.push('Блок «Персона» конвертирован в цитату с метаданными (упрощение для Markdown).');
      }
      if (tempContainer.querySelector('.editor-media-embed')) {
        this.lastExportWarnings.push('Видеоэлементы конвертированы в markdown-ссылки на источник.');
      }
      if (tempContainer.querySelector('.editor-anchor-block')) {
        this.lastExportWarnings.push('Якоря сохранены как HTML-теги <a id="...">.');
      }

      md += this.htmlToMarkdown(tempContainer);
      return md.trim() + '\n';
    }

    htmlToMarkdown(rootNode) {
      let output = '';

      const processNode = (node) => {
        if (node.nodeType === Node.TEXT_NODE) {
          return node.textContent;
        }

        if (node.nodeType !== Node.ELEMENT_NODE) {
          return '';
        }

        const tag = node.tagName.toLowerCase();

        switch (tag) {
          case 'h1':
            return `# ${this.getChildText(node)}\n\n`;
          case 'h2':
            return `## ${this.getChildText(node)}\n\n`;
          case 'h3':
            return `### ${this.getChildText(node)}\n\n`;
          case 'h4':
            return `#### ${this.getChildText(node)}\n\n`;
          case 'p': {
            const inner = this.convertChildrenToMarkdown(node);
            return inner.trim() ? `${inner}\n\n` : '';
          }
          case 'blockquote': {
            const text = this.convertChildrenToMarkdown(node).trim();
            const lines = text.split('\n').map(l => `> ${l}`).join('\n');
            return `${lines}\n\n`;
          }
          case 'pre': {
            const code = node.textContent;
            return `\`\`\`\n${code}\n\`\`\`\n\n`;
          }
          case 'hr':
            return `---\n\n`;
          case 'ul': {
            let listOutput = '';
            Array.from(node.children).forEach(li => {
              if (li.getAttribute('data-list') === 'checked') {
                listOutput += `- [x] ${this.convertChildrenToMarkdown(li).trim()}\n`;
              } else if (li.getAttribute('data-list') === 'unchecked') {
                listOutput += `- [ ] ${this.convertChildrenToMarkdown(li).trim()}\n`;
              } else {
                listOutput += `- ${this.convertChildrenToMarkdown(li).trim()}\n`;
              }
            });
            return listOutput + '\n';
          }
          case 'ol': {
            let listOutput = '';
            let index = 1;
            Array.from(node.children).forEach(li => {
              listOutput += `${index}. ${this.convertChildrenToMarkdown(li).trim()}\n`;
              index++;
            });
            return listOutput + '\n';
          }
          case 'table':
            return this.tableToMarkdown(node) + '\n\n';
          case 'figure': {
            const img = node.querySelector('img');
            const cap = node.querySelector('figcaption');
            if (img) {
              const alt = img.getAttribute('alt') || (cap ? cap.textContent.trim() : 'Изображение');
              const src = img.getAttribute('src') || '';
              let figMd = `![${alt}](${src})\n`;
              if (cap && cap.textContent.trim()) {
                figMd += `*${cap.textContent.trim()}*\n`;
              }
              return figMd + '\n';
            }
            return '';
          }
          case 'details': {
            const summary = node.querySelector('summary');
            const summaryText = summary ? summary.textContent.trim() : 'Спойлер';
            const bodyEl = node.querySelector('.editor-spoiler-body') || node;
            const bodyClone = bodyEl.cloneNode(true);
            const sumInClone = bodyClone.querySelector('summary');
            if (sumInClone) sumInClone.remove();
            const bodyMd = this.convertChildrenToMarkdown(bodyClone).trim();
            return `<details>\n<summary>${summaryText}</summary>\n\n${bodyMd}\n\n</details>\n\n`;
          }
          case 'div': {
            // Check for Custom Blots
            if (node.classList.contains('editor-block-formula')) {
              const latex = node.getAttribute('data-latex') || '';
              return `$$\n${latex}\n$$\n\n`;
            }
            if (node.classList.contains('editor-media-embed')) {
              const url = node.getAttribute('data-original-url') || node.getAttribute('data-embed-url') || '';
              const cap = node.querySelector('.media-caption')?.textContent.trim() || '';
              return `[${cap ? 'Видео: ' + cap : 'Видео'}](${url})\n\n`;
            }
            if (node.classList.contains('editor-anchor-block')) {
              const anchorId = node.getAttribute('data-anchor-id') || '';
              return `<a id="${anchorId}"></a>\n\n`;
            }
            if (node.classList.contains('editor-person-card')) {
              const name = node.getAttribute('data-name') || '';
              const role = node.getAttribute('data-role') || '';
              const link = node.getAttribute('data-link') || '';
              let cardMd = `> **${name}**`;
              if (role) cardMd += ` — *${role}*`;
              if (link) cardMd += `\n> [Профиль](${link})`;
              return cardMd + '\n\n';
            }
            return this.convertChildrenToMarkdown(node);
          }
          case 'strong':
          case 'b':
            return `**${this.convertChildrenToMarkdown(node)}**`;
          case 'em':
          case 'i':
            return `*${this.convertChildrenToMarkdown(node)}*`;
          case 'u':
            return `<u>${this.convertChildrenToMarkdown(node)}</u>`;
          case 's':
          case 'strike':
            return `~~${this.convertChildrenToMarkdown(node)}~~`;
          case 'code':
            return `\`${node.textContent}\``;
          case 'a': {
            const href = node.getAttribute('href') || '#';
            return `[${this.convertChildrenToMarkdown(node)}](${href})`;
          }
          case 'span': {
            if (node.classList.contains('editor-inline-spoiler')) {
              return `||${this.convertChildrenToMarkdown(node)}||`;
            }
            if (node.classList.contains('editor-inline-formula')) {
              const latex = node.getAttribute('data-latex') || node.textContent;
              return `$${latex}$`;
            }
            return this.convertChildrenToMarkdown(node);
          }
          default:
            return this.convertChildrenToMarkdown(node);
        }
      };

      Array.from(rootNode.childNodes).forEach(child => {
        output += processNode(child);
      });

      return output;
    }

    convertChildrenToMarkdown(node) {
      let result = '';
      Array.from(node.childNodes).forEach(child => {
        if (child.nodeType === Node.TEXT_NODE) {
          result += child.textContent;
        } else if (child.nodeType === Node.ELEMENT_NODE) {
          const tag = child.tagName.toLowerCase();
          switch (tag) {
            case 'strong':
            case 'b':
              result += `**${this.convertChildrenToMarkdown(child)}**`;
              break;
            case 'em':
            case 'i':
              result += `*${this.convertChildrenToMarkdown(child)}*`;
              break;
            case 'u':
              result += `<u>${this.convertChildrenToMarkdown(child)}</u>`;
              break;
            case 's':
            case 'strike':
              result += `~~${this.convertChildrenToMarkdown(child)}~~`;
              break;
            case 'code':
              result += `\`${child.textContent}\``;
              break;
            case 'a': {
              const href = child.getAttribute('href') || '#';
              result += `[${this.convertChildrenToMarkdown(child)}](${href})`;
              break;
            }
            case 'span':
              if (child.classList.contains('editor-inline-spoiler')) {
                result += `||${this.convertChildrenToMarkdown(child)}||`;
              } else if (child.classList.contains('editor-inline-formula')) {
                const latex = child.getAttribute('data-latex') || child.textContent;
                result += `$${latex}$`;
              } else {
                result += this.convertChildrenToMarkdown(child);
              }
              break;
            default:
              result += this.convertChildrenToMarkdown(child);
              break;
          }
        }
      });
      return result;
    }

    tableToMarkdown(tableEl) {
      const rows = Array.from(tableEl.querySelectorAll('tr'));
      if (rows.length === 0) return '';

      let mdTable = '';
      const headerRow = rows[0];
      const headerCells = Array.from(headerRow.querySelectorAll('th, td'));
      const colCount = headerCells.length;

      const headerText = headerCells.map(c => c.textContent.trim().replace(/\|/g, '\\|') || ' ').join(' | ');
      mdTable += `| ${headerText} |\n`;

      const separator = Array(colCount).fill('---').join(' | ');
      mdTable += `| ${separator} |\n`;

      for (let i = 1; i < rows.length; i++) {
        const cells = Array.from(rows[i].querySelectorAll('th, td'));
        const rowText = cells.map(c => c.textContent.trim().replace(/\|/g, '\\|') || ' ').join(' | ');
        mdTable += `| ${rowText} |\n`;
      }

      return mdTable;
    }

    getChildText(node) {
      return node.textContent.trim();
    }

    /**
     * Export article to structured JSON with schema versioning
     */
    exportToJSON() {
      const title = this.getTitle();
      const delta = this.editor.getContents();
      const html = this.sanitizeHTML(this.editor.root.innerHTML);
      const text = this.editor.getText().trim();
      const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
      const chars = text.length;

      const doc = {
        schema: 'antigravity-editor-v2',
        title: title,
        contents: delta,
        html: html,
        metadata: {
          wordCount: words,
          charCount: chars,
          readingTime: Math.max(1, Math.ceil(words / 200)),
          exportedAt: new Date().toISOString(),
          version: '2.0.0'
        }
      };

      return JSON.stringify(doc, null, 2);
    }

    /**
     * Import article from JSON string
     */
    importFromJSON(jsonString) {
      try {
        const data = typeof jsonString === 'string' ? JSON.parse(jsonString) : jsonString;

        if (!data || typeof data !== 'object') {
          throw new Error('Неверная структура JSON');
        }

        // Title
        if (typeof data.title === 'string') {
          this.setTitle(data.title);
        }

        // Contents (Delta) or HTML fallback
        if (data.contents && data.contents.ops) {
          this.editor.setContents(data.contents);
        } else if (data.html) {
          this.editor.root.innerHTML = this.sanitizeHTML(data.html);
        } else {
          throw new Error('JSON не содержит полей "contents" или "html"');
        }

        if (window.EditorApp && window.EditorApp.showToast) {
          window.EditorApp.showToast('Документ успешно импортирован!', 'success');
        }

        return true;
      } catch (err) {
        console.error('Import JSON error:', err);
        alert(`Ошибка импорта JSON: ${err.message}`);
        return false;
      }
    }

    escapeHTML(str) {
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    copyToClipboard(text) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text);
      }
      return new Promise((resolve) => {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        resolve();
      });
    }

    downloadFile(filename, content, mimeType) {
      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  }

  window.Converter = Converter;

})(window);
