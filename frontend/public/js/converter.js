/**
 * Antigravity WYSIWYG Editor - Document Converter & Exporter
 * HTML, Markdown, JSON export, JSON import, and XSS sanitization
 */

(function (window) {
  'use strict';

  class Converter {
    constructor(editor, titleInput) {
      this.editor = editor;
      this.titleInput = titleInput;
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

    /* ==========================================================================
       HTML Sanitization (XSS Protection)
       ========================================================================== */
    sanitizeHTML(dirtyHtml) {
      if (!dirtyHtml) return '';

      const doc = new DOMParser().parseFromString(dirtyHtml, 'text/html');
      const body = doc.body;

      // Disallowed elements to remove completely
      const dangerousTags = ['script', 'iframe', 'object', 'embed', 'form', 'style', 'link', 'meta', 'base'];
      dangerousTags.forEach(tag => {
        const elements = body.querySelectorAll(tag);
        elements.forEach(el => el.remove());
      });

      // Walk all nodes to remove dangerous attributes
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
     * Export complete article to clean HTML
     */
    exportToHTML(fullDocument = true) {
      const title = this.getTitle();
      const contentHtml = this.sanitizeHTML(this.editor.root.innerHTML);

      if (!fullDocument) {
        return (title ? `<h1>${this.escapeHTML(title)}</h1>\n` : '') + contentHtml;
      }

      return `<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>${this.escapeHTML(title || 'Статья')}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; max-width: 820px; margin: 40px auto; padding: 0 20px; line-height: 1.7; color: #1a1a1a; }
    h1 { font-size: 2.25rem; margin-bottom: 0.8em; line-height: 1.25; }
    h2 { font-size: 1.75rem; margin-top: 1.8em; margin-bottom: 0.6em; }
    h3 { font-size: 1.35rem; margin-top: 1.5em; margin-bottom: 0.5em; }
    pre { background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow-x: auto; }
    blockquote { border-left: 4px solid #3b82f6; margin: 1.5em 0; padding: 8px 16px; background: #f8fafc; font-style: italic; }
    table { width: 100%; border-collapse: collapse; margin: 1.5em 0; }
    th, td { border: 1px solid #cbd5e1; padding: 8px 12px; }
    details { border: 1px solid #cbd5e1; border-radius: 8px; margin: 1.5em 0; padding: 12px; background: #f8fafc; }
    summary { font-weight: 600; cursor: pointer; }
    figure { margin: 2em 0; text-align: center; }
    figure img { max-width: 100%; border-radius: 8px; }
    figcaption { color: #64748b; font-size: 0.875rem; margin-top: 6px; font-style: italic; }
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
     * Export article to CommonMark / GitHub Flavored Markdown
     */
    exportToMarkdown() {
      const title = this.getTitle();
      let md = '';

      if (title) {
        md += `# ${title}\n\n`;
      }

      const tempContainer = document.createElement('div');
      tempContainer.innerHTML = this.sanitizeHTML(this.editor.root.innerHTML);

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
          case 'p':
            return `${this.processChildren(node)}\n\n`;
          case 'strong':
          case 'b':
            return `**${this.processChildren(node)}**`;
          case 'em':
          case 'i':
            return `*${this.processChildren(node)}*`;
          case 'u':
            return `<u>${this.processChildren(node)}</u>`;
          case 's':
          case 'strike':
          case 'del':
            return `~~${this.processChildren(node)}~~`;
          case 'code':
            if (node.parentNode && node.parentNode.tagName.toLowerCase() === 'pre') {
              return node.textContent;
            }
            return `\`${node.textContent}\``;
          case 'pre': {
            const lang = node.getAttribute('data-language') || '';
            const code = node.textContent;
            return `\`\`\`${lang}\n${code}\n\`\`\`\n\n`;
          }
          case 'blockquote':
            return `> ${this.processChildren(node).trim()}\n\n`;
          case 'hr':
            return `---\n\n`;
          case 'ul': {
            let listMd = '';
            Array.from(node.children).forEach(li => {
              if (li.getAttribute('data-checked') === 'true') {
                listMd += `- [x] ${this.processChildren(li).trim()}\n`;
              } else if (li.getAttribute('data-checked') === 'false') {
                listMd += `- [ ] ${this.processChildren(li).trim()}\n`;
              } else {
                listMd += `- ${this.processChildren(li).trim()}\n`;
              }
            });
            return listMd + '\n';
          }
          case 'ol': {
            let listMd = '';
            Array.from(node.children).forEach((li, idx) => {
              listMd += `${idx + 1}. ${this.processChildren(li).trim()}\n`;
            });
            return listMd + '\n';
          }
          case 'a': {
            const href = node.getAttribute('href') || '';
            const text = this.processChildren(node);
            return `[${text}](${href})`;
          }
          case 'figure': {
            const img = node.querySelector('img');
            const cap = node.querySelector('figcaption');
            if (img) {
              const src = img.getAttribute('src') || '';
              const alt = img.getAttribute('alt') || 'image';
              const caption = cap ? cap.textContent.trim() : '';
              return `![${alt}](${src})${caption ? `\n*${caption}*` : ''}\n\n`;
            }
            return '';
          }
          case 'img': {
            const src = node.getAttribute('src') || '';
            const alt = node.getAttribute('alt') || 'image';
            return `![${alt}](${src})`;
          }
          case 'details': {
            const summary = node.querySelector('summary');
            const summaryText = summary ? summary.textContent.trim() : 'Спойлер';
            const bodyText = node.querySelector('.editor-spoiler-body') ? node.querySelector('.editor-spoiler-body').textContent.trim() : node.textContent.replace(summaryText, '').trim();
            return `<details>\n<summary>${summaryText}</summary>\n\n${bodyText}\n</details>\n\n`;
          }
          case 'table': {
            return this.tableToMarkdown(node) + '\n\n';
          }
          default:
            return this.processChildren(node);
        }
      };

      Array.from(rootNode.childNodes).forEach(child => {
        output += processNode(child);
      });

      return output;
    }

    processChildren(node) {
      let result = '';
      Array.from(node.childNodes).forEach(child => {
        if (child.nodeType === Node.TEXT_NODE) {
          result += child.textContent;
        } else if (child.nodeType === Node.ELEMENT_NODE) {
          const tag = child.tagName.toLowerCase();
          if (tag === 'strong' || tag === 'b') result += `**${this.processChildren(child)}**`;
          else if (tag === 'em' || tag === 'i') result += `*${this.processChildren(child)}*`;
          else if (tag === 'u') result += `<u>${this.processChildren(child)}</u>`;
          else if (tag === 's' || tag === 'strike') result += `~~${this.processChildren(child)}~~`;
          else if (tag === 'code') result += `\`${child.textContent}\``;
          else if (tag === 'a') result += `[${this.processChildren(child)}](${child.getAttribute('href') || ''})`;
          else result += this.processChildren(child);
        }
      });
      return result;
    }

    getChildText(node) {
      return node.textContent.trim();
    }

    tableToMarkdown(tableEl) {
      const rows = Array.from(tableEl.querySelectorAll('tr'));
      if (rows.length === 0) return '';

      let md = '';
      const matrix = [];

      rows.forEach(tr => {
        const cells = Array.from(tr.querySelectorAll('th, td')).map(cell => cell.textContent.trim().replace(/\|/g, '\\|'));
        if (cells.length > 0) matrix.push(cells);
      });

      if (matrix.length === 0) return '';

      const maxCols = Math.max(...matrix.map(r => r.length));

      // Header row
      const header = matrix[0];
      while (header.length < maxCols) header.push('');
      md += '| ' + header.join(' | ') + ' |\n';

      // Divider row
      const dividers = new Array(maxCols).fill('---');
      md += '| ' + dividers.join(' | ') + ' |\n';

      // Body rows
      for (let i = 1; i < matrix.length; i++) {
        const row = matrix[i];
        while (row.length < maxCols) row.push('');
        md += '| ' + row.join(' | ') + ' |\n';
      }

      return md;
    }

    /**
     * Export article to structured JSON
     */
    exportToJSON() {
      const title = this.getTitle();
      const delta = this.editor.getContents();
      const html = this.sanitizeHTML(this.editor.root.innerHTML);
      const text = this.editor.getText().trim();
      const words = text ? text.split(/\s+/).filter(Boolean).length : 0;

      const doc = {
        schema: 'antigravity-editor-v1',
        title: title || 'Без названия',
        contents: delta,
        html: html,
        metadata: {
          wordCount: words,
          charCount: text.length,
          readingTime: Math.max(1, Math.ceil(words / 200)),
          exportedAt: new Date().toISOString()
        }
      };

      return JSON.stringify(doc, null, 2);
    }

    /**
     * Import structured document from JSON string
     */
    importFromJSON(jsonString) {
      try {
        const data = JSON.parse(jsonString);

        if (!data) {
          throw new Error('Некорректный JSON');
        }

        if (data.title) {
          this.setTitle(data.title);
        }

        if (data.contents) {
          this.editor.setContents(data.contents, 'user');
        } else if (data.html) {
          this.editor.root.innerHTML = this.sanitizeHTML(data.html);
        } else {
          throw new Error('В JSON отсутствуют поля contents или html');
        }

        if (window.EditorApp && window.EditorApp.showToast) {
          window.EditorApp.showToast('Документ успешно импортирован', 'success');
        }
        return true;
      } catch (err) {
        alert('Ошибка при импорте JSON: ' + err.message);
        return false;
      }
    }

    /* ==========================================================================
       Download & Clipboard Helpers
       ========================================================================== */
    downloadFile(filename, content, mimeType = 'text/plain;charset=utf-8') {
      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }, 100);
    }

    copyToClipboard(text) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        return Promise.resolve();
      }
    }

    escapeHTML(str) {
      return (str || '').replace(/[&<>"']/g, (m) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[m]));
    }
  }

  window.Converter = Converter;

})(window);
