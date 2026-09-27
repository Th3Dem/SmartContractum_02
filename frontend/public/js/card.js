/**
 * card.js — Единый общий компонент карточки публикации SmartContractum
 *
 * Используется совместно в:
 * 1. Ленте публикаций (feed.html, feed.js)
 * 2. Живом предпросмотре формы публикации (editor.html, publication.js)
 *
 * Обеспечивает:
 * - Единый 7-ступенчатый порядок блоков:
 *   1. Автор и дата
 *   2. Заголовок
 *   3. Бейджи (тема, формат, сложность, демо)
 *   4. Полноширинная обложка (100% внутренней ширины, пропорции 39:22)
 *   5. Краткое описание
 *   6. Ключевые слова (#хэштеги)
 *   7. Футер (время чтения, закладка)
 * - Чистоту обложки: на обложку НЕ накладываются никакие элементы сайта (заголовки, бейджи, водяные знаки).
 * - Состояния: 0px при отсутствии обложки или ошибке, шиммер при загрузке, 100% ширина при показе.
 */

(function (window) {
  'use strict';

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function cleanString(str) {
    return (str || '')
      .replace(/\s*\((демо|demo)\)\s*/gi, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function getBadgesHtml(item, options) {
    options = options || {};
    const isPreview = Boolean(options.isPreview);
    let badgesHtml = '';

    // 1. Topic Title & Badge
    let topicTitle = '';
    if (window.PublicationConfig && item.topic) {
      const t = window.PublicationConfig.getTopicById(item.topic);
      if (t) topicTitle = t.title;
    } else if (item.topicTitle) {
      topicTitle = item.topicTitle;
    }
    if (topicTitle) {
      badgesHtml += '<span class="meta-badge topic-badge"' + (isPreview ? ' id="preview-card-badge-topic"' : '') + '>' + escapeHtml(topicTitle) + '</span>';
    }

    // 2. Format Badge
    let formatTitle = '';
    if (window.PublicationConfig && item.format && item.format !== 'not_specified' && item.format !== 'none') {
      const f = window.PublicationConfig.getFormatById(item.format);
      if (f && f.title && f.title.toLowerCase() !== 'не указан') {
        formatTitle = f.title;
      }
    } else if (item.formatTitle) {
      formatTitle = item.formatTitle;
    }
    if (formatTitle) {
      badgesHtml += '<span class="meta-badge format-badge"' + (isPreview ? ' id="preview-card-badge-format"' : '') + '>' + escapeHtml(formatTitle) + '</span>';
    }

    // 3. Complexity Badge
    let complexityTitle = '';
    let complexityClass = '';
    if (window.PublicationConfig && item.complexity && item.complexity !== 'none') {
      const c = window.PublicationConfig.getComplexityById(item.complexity);
      if (c && c.title && c.title.toLowerCase() !== 'не указан') {
        complexityTitle = c.title;
        complexityClass = 'complexity-' + item.complexity;
      }
    } else if (item.complexityTitle) {
      complexityTitle = item.complexityTitle;
      complexityClass = item.complexity ? 'complexity-' + item.complexity : '';
    }
    if (complexityTitle) {
      badgesHtml += '<span class="meta-badge complexity-badge ' + complexityClass + '"' + (isPreview ? ' id="preview-card-badge-complexity"' : '') + '>' + escapeHtml(complexityTitle) + '</span>';
    }

    // 4. Demo Badge
    if (item.isDemo || (item.id && String(item.id).indexOf('art-0') === 0)) {
      badgesHtml += '<span class="meta-badge badge-demo">Демонстрационный материал</span>';
    }

    return badgesHtml;
  }

  function renderCardInnerHtml(item, options, isBookmarked) {
    options = options || {};
    const isPreview = Boolean(options.isPreview);

    const cleanTitle = cleanString(item.title) || (isPreview ? 'Заголовок публикации' : '');
    const cleanRole = cleanString(item.authorRole);
    const authorName = item.author || 'Автор платформы';
    const authorInitials = item.authorInitials ||
      authorName.split(/\s+/).map(p => p[0]).filter(Boolean).slice(0, 2).join('').toUpperCase() || 'АП';
    const dateText = item.date || (isPreview ? 'Недавно' : 'Недавно');

    // 0. Subscription Reason Badge (Feed only)
    let subscriptionBadgeHtml = '';
    if (!isPreview && item.subscriptionReason) {
      subscriptionBadgeHtml =
        '<div class="card-subscription-badge">' +
          '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>' +
          '</svg>' +
          '<span>' + escapeHtml(item.subscriptionReason) + '</span>' +
        '</div>';
    }

    // 1. Author and Date
    const authorHtml =
      '<div class="card-meta">' +
        '<div class="author-info">' +
          '<div class="author-avatar"' + (isPreview ? ' id="preview-card-avatar"' : '') + '>' + escapeHtml(authorInitials) + '</div>' +
          '<div class="author-details">' +
            '<span class="author-name"' + (isPreview ? ' id="preview-card-author"' : '') + '>' + escapeHtml(authorName) + '</span>' +
            '<div class="meta-sub-row">' +
              '<span class="publish-date"' + (isPreview ? ' id="preview-card-date"' : '') + '>' + escapeHtml(dateText) + '</span>' +
              (cleanRole
                ? ('<span class="meta-dot"' + (isPreview ? ' id="preview-card-dot"' : '') + '></span>' +
                   '<span class="author-role"' + (isPreview ? ' id="preview-card-role"' : '') + '>' + escapeHtml(cleanRole) + '</span>')
                : (isPreview ? '<span class="meta-dot" id="preview-card-dot" style="display: none;"></span><span class="author-role" id="preview-card-role" style="display: none;"></span>' : '')
              ) +
            '</div>' +
          '</div>' +
        '</div>' +
      '</div>';

    // 2. Title
    const articleUrl = isPreview ? '#' : ('article.html?id=' + encodeURIComponent(item.id || ''));
    const titleTag = isPreview ? 'h3' : 'h2';
    const titleHtml =
      '<' + titleTag + ' class="card-title' + (isPreview ? ' pub-feed-card-title' : '') + '"' + (isPreview ? ' id="preview-card-title"' : '') + '>' +
        (isPreview
          ? escapeHtml(cleanTitle)
          : ('<a href="' + articleUrl + '">' + escapeHtml(cleanTitle) + '</a>')
        ) +
      '</' + titleTag + '>';

    // 3. Badges
    const badgesHtml = getBadgesHtml(item, options);
    const badgesContainerHtml =
      '<div class="card-meta-badges' + (isPreview ? ' pub-feed-card-meta' : '') + '"' + (isPreview ? ' id="preview-card-badges"' : '') + (badgesHtml ? '' : ' style="display: none;"') + '>' +
        badgesHtml +
      '</div>';

    // 4. Cover Image: 100% full card width, 39:22 aspect ratio, zero site overlays!
    let coverHtml = '';
    if (item.coverImage) {
      coverHtml =
        '<div class="card-cover-container is-loading' + (isPreview ? ' pub-feed-card-cover is-loaded' : '') + '"' + (isPreview ? ' id="preview-card-cover"' : '') + '>' +
          '<img class="card-cover-img pub-preview-img" src="' + escapeHtml(item.coverImage) + '" alt="' + escapeHtml(cleanTitle) + '" loading="lazy" ' +
            'onload="this.parentElement.classList.remove(\'is-loading\'); this.parentElement.classList.add(\'is-loaded\');" ' +
            'onerror="var c=this.closest(\'.card-cover-container\'); if(c) { c.style.display=\'none\'; c.remove(); }">' +
        '</div>';
    } else if (isPreview) {
      // In preview template, preserve empty hidden container with id="preview-card-cover"
      coverHtml = '<div class="card-cover-container pub-feed-card-cover" id="preview-card-cover" style="display: none;"></div>';
    }

    // 5. Description
    const descText = item.description || (isPreview ? 'Краткое описание публикации появится здесь...' : '');
    const leadHtml = '<p class="card-lead' + (isPreview ? ' pub-feed-card-desc' : '') + '"' + (isPreview ? ' id="preview-card-desc"' : '') + '>' + escapeHtml(descText) + '</p>';

    // 6. Keywords
    const tags = Array.isArray(item.keywords) ? item.keywords : [];
    let tagsHtml = '';
    if (tags.length > 0) {
      const maxVisible = 3;
      const visible = tags.slice(0, maxVisible);
      const hidden = tags.slice(maxVisible);

      visible.forEach(function (tag) {
        tagsHtml +=
          '<button type="button" class="tag-chip" data-tag="' + escapeHtml(tag) + '" tabindex="' + (isPreview ? '-1' : '0') + '">' +
            '#' + escapeHtml(tag) +
          '</button>';
      });

      if (hidden.length > 0) {
        if (isPreview) {
          tagsHtml += '<span class="tag-expand-btn">+' + hidden.length + ' еще</span>';
        } else {
          tagsHtml +=
            '<button type="button" class="tag-expand-btn" aria-expanded="false">+' + hidden.length + ' еще</button>' +
            '<span class="extra-tags" style="display: none;">';
          hidden.forEach(function (tag) {
            tagsHtml +=
              '<button type="button" class="tag-chip" data-tag="' + escapeHtml(tag) + '">' +
                '#' + escapeHtml(tag) +
              '</button>';
          });
          tagsHtml += '</span>';
        }
      }
    }
    const tagsContainerHtml =
      '<div class="card-tags' + (isPreview ? ' pub-feed-card-tags' : '') + '"' + (isPreview ? ' id="preview-card-tags"' : '') + (tagsHtml ? '' : (isPreview ? ' style="display: none;"' : '')) + '>' +
        tagsHtml +
      '</div>';

    // 7. Footer (Reading time & Bookmark)
    const bookmarkTooltip = isBookmarked ? 'Убрать из сохраненного' : 'Сохранить статью';
    let bookmarkHtml = '';
    if (isPreview) {
      bookmarkHtml =
        '<button type="button" class="btn-card-bookmark" id="preview-card-bookmark" title="Сохранить статью" aria-label="Сохранить статью" disabled>' +
          '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"></path>' +
          '</svg>' +
        '</button>';
    } else {
      bookmarkHtml =
        '<button type="button" class="btn-card-bookmark ' + (isBookmarked ? 'is-bookmarked' : '') + '" id="btn-bookmark" title="' + bookmarkTooltip + '" aria-label="' + bookmarkTooltip + '">' +
          '<svg width="17" height="17" viewBox="0 0 24 24" fill="' + (isBookmarked ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"></path>' +
          '</svg>' +
        '</button>';
    }

    const readingTimeText = item.readingTime || (isPreview ? '~1 мин чтения' : '5 мин чтения');
    const footerHtml =
      '<footer class="card-footer">' +
        '<div class="reading-time">' +
          '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>' +
          '<span' + (isPreview ? ' class="pub-feed-card-time" id="preview-card-time"' : '') + '>' + escapeHtml(readingTimeText) + '</span>' +
        '</div>' +
        bookmarkHtml +
      '</footer>';

    return subscriptionBadgeHtml +
      authorHtml +
      titleHtml +
      badgesContainerHtml +
      coverHtml +
      leadHtml +
      tagsContainerHtml +
      footerHtml;
  }

  function createCardElement(item, options) {
    options = options || {};
    const isPreview = Boolean(options.isPreview);
    const isBookmarked = typeof options.isBookmarked === 'function'
      ? options.isBookmarked(item.id)
      : Boolean(options.isBookmarked);

    const card = document.createElement('article');
    card.className = 'feed-card' + (isPreview ? ' pub-feed-card is-preview-card' : '');
    if (item.id) card.setAttribute('data-id', item.id);
    if (item.topic) card.setAttribute('data-topic', item.topic);

    card.innerHTML = renderCardInnerHtml(item, options, isBookmarked);

    // Event handlers for active feed cards
    if (!isPreview) {
      const authorEl = card.querySelector('.author-info');
      if (authorEl) {
        authorEl.addEventListener('click', function (e) {
          e.stopPropagation();
        });
      }

      const titleLink = card.querySelector('.card-title a');
      if (titleLink) {
        titleLink.addEventListener('click', function () {
          try {
            sessionStorage.setItem('sc_feed_scroll', String(window.scrollY || window.pageYOffset || 0));
          } catch (e) {}
        });
      }

      const expandBtn = card.querySelector('.tag-expand-btn');
      if (expandBtn) {
        expandBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          const extraTags = card.querySelector('.extra-tags');
          if (extraTags) {
            const isExpanded = extraTags.style.display !== 'none';
            extraTags.style.display = isExpanded ? 'none' : 'inline';
            const hiddenCount = (item.keywords && item.keywords.length > 3) ? (item.keywords.length - 3) : 0;
            expandBtn.textContent = isExpanded ? ('+' + hiddenCount + ' еще') : 'Свернуть';
            expandBtn.setAttribute('aria-expanded', String(!isExpanded));
          }
        });
      }
    }

    return card;
  }

  window.SmartContractumCard = {
    escapeHtml: escapeHtml,
    cleanString: cleanString,
    getBadgesHtml: getBadgesHtml,
    renderCardInnerHtml: renderCardInnerHtml,
    createCardElement: createCardElement
  };

})(window);
