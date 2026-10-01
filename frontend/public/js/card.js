/**
 * card.js - Единый общий компонент карточки публикации SmartContractum
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

    const isQuestion = Boolean(
      item.materialType === 'question' ||
      item.type === 'question' ||
      item.material_type === 'question'
    );

    // Explicit Question Badge
    if (isQuestion) {
      badgesHtml += '<span class="meta-badge question-badge"' + (isPreview ? ' id="preview-card-badge-question"' : '') + '>Вопрос</span>';
    }

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

    // 2. Format Badge (only for standard publications, NOT questions)
    if (!isQuestion) {
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
    }

    if (item.clubTitle) {
      badgesHtml += '<span class="meta-badge club-badge"' + (isPreview ? ' id="preview-card-badge-club"' : '') + '>' + escapeHtml(item.clubTitle) + '</span>';
    }

    // Note: Complexity badge has been moved down to the bottom service row.
    // Note: "Демонстрационный материал" badge has been completely removed per requirements.

    return badgesHtml;
  }

  function getComplexityBadgeHtml(item, options) {
    options = options || {};
    const isPreview = Boolean(options.isPreview);
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
      return '<span class="meta-badge complexity-badge ' + complexityClass + '"' + (isPreview ? ' id="preview-card-badge-complexity"' : '') + '>' + escapeHtml(complexityTitle) + '</span>';
    } else if (isPreview) {
      return '<span class="meta-badge complexity-badge" id="preview-card-badge-complexity" style="display: none;"></span>';
    }
    return '';
  }

  function renderVoteCapsuleHtml(params) {
    if (window.SmartContractumVotes && typeof window.SmartContractumVotes.renderVoteCapsuleHtml === 'function') {
      return window.SmartContractumVotes.renderVoteCapsuleHtml(params);
    }
    params = params || {};
    const targetType = params.targetType || 'article';
    const targetId = params.targetId ? String(params.targetId) : '';
    const score = Number.isInteger(params.score) ? params.score : (parseInt(params.score, 10) || 0);
    const myVote = Number.isInteger(params.myVote) ? params.myVote : (parseInt(params.myVote, 10) || 0);
    const isAuthor = Boolean(params.isAuthor);
    const canVote = params.canVote !== undefined ? Boolean(params.canVote) : (!isAuthor);
    const isDeleted = Boolean(params.isDeleted);
    const isPreview = Boolean(params.isPreview);

    const authorTitle = targetType === 'comment'
      ? 'Нельзя голосовать за собственный комментарий'
      : 'Нельзя голосовать за собственный материал';

    let upTitle = 'Повысить рейтинг';
    let upLabel = 'Повысить рейтинг';
    let upDisabled = false;
    let downTitle = 'Понизить рейтинг';
    let downLabel = 'Понизить рейтинг';
    let downDisabled = false;

    if (isAuthor || canVote === false) {
      upTitle = authorTitle;
      upLabel = authorTitle;
      upDisabled = true;
      downTitle = authorTitle;
      downLabel = authorTitle;
      downDisabled = true;
    } else if (isDeleted) {
      upTitle = 'Комментарий удален';
      upLabel = 'Комментарий удален';
      upDisabled = true;
      downTitle = 'Комментарий удален';
      downLabel = 'Комментарий удален';
      downDisabled = true;
    } else if (isPreview) {
      upTitle = 'Предпросмотр';
      upDisabled = true;
      downTitle = 'Предпросмотр';
      downDisabled = true;
    } else {
      if (myVote === 1) upTitle = 'Снять голос';
      if (myVote === -1) downTitle = 'Снять голос';
    }

    const upClass = 'vote-btn vote-btn-up' + (myVote === 1 ? ' is-voted' : '');
    const downClass = 'vote-btn vote-btn-down' + (myVote === -1 ? ' is-voted' : '');

    const upBtnHtml =
      '<button type="button" class="' + upClass + '" data-dir="1" ' +
      'aria-label="' + escapeHtml(upLabel) + '" title="' + escapeHtml(upTitle) + '" ' +
      'aria-pressed="' + (myVote === 1 ? 'true' : 'false') + '"' +
      (upDisabled ? ' disabled aria-disabled="true"' : '') + '>' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
          '<polyline points="18 15 12 9 6 15"></polyline>' +
        '</svg>' +
      '</button>';

    const downBtnHtml =
      '<button type="button" class="' + downClass + '" data-dir="-1" ' +
      'aria-label="' + escapeHtml(downLabel) + '" title="' + escapeHtml(downTitle) + '" ' +
      'aria-pressed="' + (myVote === -1 ? 'true' : 'false') + '"' +
      (downDisabled ? ' disabled aria-disabled="true"' : '') + '>' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
          '<polyline points="6 9 12 15 18 9"></polyline>' +
        '</svg>' +
      '</button>';

    let scoreClass = 'vote-score';
    if (score > 0) scoreClass += ' is-positive';
    else if (score < 0) scoreClass += ' is-negative';
    else scoreClass += ' is-zero';

    const scoreHtml = '<span class="' + scoreClass + '" data-score="' + score + '">' + score + '</span>';

    const capsuleClass = 'vote-capsule' +
      (myVote === 1 ? ' has-voted-up' : (myVote === -1 ? ' has-voted-down' : '')) +
      (isPreview ? ' is-preview' : '');

    return (
      '<div class="' + capsuleClass + '" ' +
        'data-vote-target-type="' + escapeHtml(targetType) + '" ' +
        'data-vote-target-id="' + escapeHtml(targetId) + '" ' +
        'data-score="' + score + '" ' +
        'data-my-vote="' + myVote + '" ' +
        'data-can-vote="' + (canVote ? 'true' : 'false') + '"' +
        (isAuthor ? ' data-is-author="true"' : '') + '>' +
        upBtnHtml +
        scoreHtml +
        downBtnHtml +
      '</div>'
    );
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

    const companyBadgeHtml = item.companyName
      ? ('<span class="card-company-badge"' + (isPreview ? ' id="preview-card-company"' : '') + '>' + escapeHtml(item.companyName) + '</span>')
      : (isPreview ? '<span class="card-company-badge" id="preview-card-company" style="display: none;"></span>' : '');

    // 1. Author
    const authorId = item.authorId || item.author_id || item.userId || '';
    const authorHtml =
      '<div class="card-meta">' +
        '<div class="author-info">' +
          '<div class="author-avatar"' + (isPreview ? ' id="preview-card-avatar"' : '') + '>' + escapeHtml(authorInitials) + '</div>' +
          '<div class="author-details">' +
            '<div style="display: flex; align-items: center; flex-wrap: wrap;">' +
              (isPreview
                ? ('<span class="author-name" id="preview-card-author">' + escapeHtml(authorName) + '</span>')
                : ('<button type="button" class="author-name btn-author-profile" data-author-id="' + escapeHtml(authorId) + '" data-user-id="' + escapeHtml(authorId) + '" data-user-name="' + escapeHtml(authorName) + '" title="Открыть профиль">' + escapeHtml(authorName) + '</button>')
              ) +
              companyBadgeHtml +
            '</div>' +
            (cleanRole
              ? ('<div class="meta-sub-row"><span class="author-role"' + (isPreview ? ' id="preview-card-role"' : '') + '>' + escapeHtml(cleanRole) + '</span></div>')
              : (isPreview ? '<div class="meta-sub-row"><span class="author-role" id="preview-card-role" style="display: none;"></span></div>' : '')
            ) +
          '</div>' +
        '</div>' +
      '</div>';

    // 2. Title
    const isQuestion = (item.materialType === 'question' || item.type === 'question');
    const articleUrl = isPreview ? '#' : ('article.html?id=' + encodeURIComponent(item.id || ''));
    const titleTag = isPreview ? 'h3' : 'h2';
    const titleHtml =
      '<' + titleTag + ' class="card-title' + (isPreview ? ' pub-feed-card-title' : '') + (isQuestion ? ' question-card-title' : '') + '"' + (isPreview ? ' id="preview-card-title"' : '') + '>' +
        (isPreview
          ? escapeHtml(cleanTitle)
          : ('<a href="' + articleUrl + '">' + escapeHtml(cleanTitle) + '</a>')
        ) +
      '</' + titleTag + '>';

    // 3. Badges: Topic, Solved (for question), Format (for article)
    let badgesHtml = getBadgesHtml(item, options);
    if (isQuestion && item.hasSolution) {
      badgesHtml = '<span class="meta-badge solved-badge">Решено</span>' + badgesHtml;
    }
    const badgesContainerHtml =
      '<div class="card-meta-badges' + (isPreview ? ' pub-feed-card-meta' : '') + '"' + (isPreview ? ' id="preview-card-badges"' : '') + (badgesHtml ? '' : ' style="display: none;"') + '>' +
        badgesHtml +
      '</div>';

    // 4. Cover Image: Questions do NOT have covers. Articles have 100% full width cover if available.
    let coverHtml = '';
    if (!isQuestion && item.material_type !== 'question' && item.coverImage) {
      coverHtml =
        '<div class="card-cover-container is-loading' + (isPreview ? ' pub-feed-card-cover is-loaded' : '') + '"' + (isPreview ? ' id="preview-card-cover"' : '') + '>' +
          '<img class="card-cover-img pub-preview-img" src="' + escapeHtml(item.coverImage) + '" alt="' + escapeHtml(cleanTitle) + '" loading="lazy" ' +
            'onload="this.parentElement.classList.remove(\'is-loading\'); this.parentElement.classList.add(\'is-loaded\');" ' +
            'onerror="var c=this.closest(\'.card-cover-container\'); if(c) { c.style.display=\'none\'; c.remove(); }">' +
        '</div>';
    } else if (isPreview && !isQuestion && item.material_type !== 'question') {
      coverHtml = '<div class="card-cover-container pub-feed-card-cover" id="preview-card-cover" style="display: none;"></div>';
    }

    // 5. Description & Matched Answer Snippet (if any)
    const descText = item.description || (isPreview ? 'Краткое описание публикации появится здесь...' : '');
    const leadHtml = '<p class="card-lead' + (isPreview ? ' pub-feed-card-desc' : '') + '"' + (isPreview ? ' id="preview-card-desc"' : '') + '>' + escapeHtml(descText) + '</p>';

    let snippetHtml = '';
    if (item.matchedAnswerSnippet) {
      snippetHtml =
        '<div class="card-matched-snippet">' +
          '<span class="matched-snippet-label">Найдено в ответе:</span> ' +
          '<span class="matched-snippet-text">' + escapeHtml(item.matchedAnswerSnippet) + '</span>' +
        '</div>';
    }

    // 6. Keywords (#hashtags)
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

    // 7. Bottom in 2 compact rows:
    const readingTimeText = item.readingTime || (isPreview ? '~1 мин чтения' : '5 мин чтения');
    const complexityBadgeHtml = getComplexityBadgeHtml(item, options);

    let subInfoHtml = '';
    if (isQuestion) {
      subInfoHtml =
        '<div class="card-sub-info card-meta-row-bottom">' +
          '<span class="publish-date"' + (isPreview ? ' id="preview-card-date"' : '') + '>' + escapeHtml(dateText) + '</span>' +
        '</div>';
    } else {
      subInfoHtml =
        '<div class="card-sub-info card-meta-row-bottom">' +
          '<span class="publish-date"' + (isPreview ? ' id="preview-card-date"' : '') + '>' + escapeHtml(dateText) + '</span>' +
          '<span class="meta-dot"></span>' +
          '<div class="reading-time">' +
            '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>' +
            '<span' + (isPreview ? ' class="pub-feed-card-time" id="preview-card-time"' : '') + '>' + escapeHtml(readingTimeText) + '</span>' +
          '</div>' +
          (complexityBadgeHtml ? ('<span class="meta-dot"></span>' + complexityBadgeHtml) : '') +
        '</div>';
    }

    // Row 2: Action row
    const isLiked = typeof options.isLiked === 'function' ? options.isLiked(item.id) : Boolean(item.hasLiked || item.isLiked);
    const likesCount = item.likesCount !== undefined ? item.likesCount : 0;
    const commentsCount = item.commentsCount !== undefined ? item.commentsCount : 0;
    const commentsUrl = isPreview ? '#' : ('article.html?id=' + encodeURIComponent(item.id || '') + '#comments');

    let likeBtnHtml = '';
    if (isPreview) {
      likeBtnHtml =
        '<button type="button" class="btn-card-action btn-card-like" id="preview-card-like" title="Нравится" aria-label="Нравится" disabled>' +
          '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>' +
          '</svg>' +
          '<span class="like-count">0</span>' +
        '</button>';
    } else {
      likeBtnHtml =
        '<button type="button" class="btn-card-action btn-card-like ' + (isLiked ? 'is-liked' : '') + '" data-id="' + escapeHtml(item.id) + '" title="' + (isLiked ? 'Больше не нравится' : 'Нравится') + '" aria-label="' + (isLiked ? 'Больше не нравится' : 'Нравится') + '">' +
          '<svg width="16" height="16" viewBox="0 0 24 24" fill="' + (isLiked ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>' +
          '</svg>' +
          '<span class="like-count">' + likesCount + '</span>' +
        '</button>';
    }

    let commentsBtnHtml = '';
    if (isPreview) {
      commentsBtnHtml =
        '<button type="button" class="btn-card-action btn-card-comments" id="preview-card-comments" title="Комментарии" aria-label="Комментарии" disabled>' +
          '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>' +
          '</svg>' +
          '<span class="comments-count">0</span>' +
        '</button>';
    } else {
      commentsBtnHtml =
        '<a href="' + commentsUrl + '" class="btn-card-action btn-card-comments" title="Перейти к комментариям" aria-label="Комментарии">' +
          '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>' +
          '</svg>' +
          '<span class="comments-count">' + commentsCount + '</span>' +
        '</a>';
    }

    const bookmarkTooltip = isBookmarked ? 'Убрать из сохраненного' : 'Сохранить';
    let bookmarkHtml = '';
    if (isPreview) {
      bookmarkHtml =
        '<button type="button" class="btn-card-action btn-card-bookmark" id="preview-card-bookmark" title="Сохранить" aria-label="Сохранить" disabled>' +
          '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"></path>' +
          '</svg>' +
        '</button>';
    } else {
      bookmarkHtml =
        '<button type="button" class="btn-card-action btn-card-bookmark ' + (isBookmarked ? 'is-bookmarked' : '') + '" id="btn-bookmark" title="' + bookmarkTooltip + '" aria-label="' + bookmarkTooltip + '">' +
          '<svg width="16" height="16" viewBox="0 0 24 24" fill="' + (isBookmarked ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"></path>' +
          '</svg>' +
        '</button>';
    }

    const score = item.score !== undefined ? item.score : 0;
    const myVote = item.myVote !== undefined ? item.myVote : 0;
    const canVote = item.canVote !== undefined ? Boolean(item.canVote) : true;
    const isAuthor = Boolean(options.currentUserId && (options.currentUserId === (item.authorId || item.author_id)));
    const voteCapsuleHtml = renderVoteCapsuleHtml({
      targetType: 'article',
      targetId: item.id || '',
      score: score,
      myVote: myVote,
      canVote: canVote && !isAuthor,
      isAuthor: isAuthor,
      isPreview: isPreview
    });

    let footerLeftHtml = '';
    let readMoreText = 'Читать далее';
    let actionTargetUrl = articleUrl;
    if (isQuestion) {
      const aCount = item.answersCount !== undefined ? item.answersCount : (item.commentsCount || 0);
      let aText = 'без ответов';
      if (aCount === 1) aText = '1 ответ';
      else if (aCount >= 2 && aCount <= 4) aText = aCount + ' ответа';
      else if (aCount >= 5) aText = aCount + ' ответов';

      const questionAnswerUrl = isPreview ? '#' : ('article.html?id=' + encodeURIComponent(item.id || '') + (aCount === 0 ? '#comment-form' : '#comments'));
      const answersClass = item.hasSolution ? 'is-solved' : (aCount > 0 ? 'has-answers' : 'no-answers');
      const answersBtnHtml =
        '<a href="' + questionAnswerUrl + '" class="btn-card-answers ' + answersClass + '" title="' + (aCount === 0 ? 'Ответить на вопрос' : 'Перейти к ответам') + '">' +
          '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>' +
          '</svg>' +
          '<span>' + (item.hasSolution ? 'Решение принято • ' : '') + aText + '</span>' +
        '</a>';
      footerLeftHtml = likeBtnHtml + voteCapsuleHtml + answersBtnHtml + bookmarkHtml;
      readMoreText = (aCount === 0 ? 'Ответить' : 'Смотреть вопрос');
      if (aCount === 0) {
        actionTargetUrl = questionAnswerUrl;
      }
    } else {
      footerLeftHtml = likeBtnHtml + voteCapsuleHtml + commentsBtnHtml + bookmarkHtml;
      readMoreText = 'Читать далее';
      actionTargetUrl = articleUrl;
    }

    let readMoreHtml = '';
    if (isPreview) {
      readMoreHtml =
        '<span class="card-read-more btn-read-more" style="opacity: 0.7;">' +
          '<span>' + readMoreText + '</span>' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<line x1="5" y1="12" x2="19" y2="12"></line>' +
            '<polyline points="12 5 19 12 12 19"></polyline>' +
          '</svg>' +
        '</span>';
    } else {
      readMoreHtml =
        '<a href="' + actionTargetUrl + '" class="card-read-more btn-read-more" title="' + readMoreText + '">' +
          '<span>' + readMoreText + '</span>' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<line x1="5" y1="12" x2="19" y2="12"></line>' +
            '<polyline points="12 5 19 12 12 19"></polyline>' +
          '</svg>' +
        '</a>';
    }

    const footerHtml =
      '<footer class="card-footer">' +
        '<div class="card-actions-row card-footer-actions">' +
          '<div class="card-footer-left">' +
            footerLeftHtml +
          '</div>' +
          '<div class="card-footer-right">' +
            readMoreHtml +
          '</div>' +
        '</div>' +
      '</footer>';

    return subscriptionBadgeHtml +
      authorHtml +
      titleHtml +
      badgesContainerHtml +
      coverHtml +
      leadHtml +
      snippetHtml +
      tagsContainerHtml +
      subInfoHtml +
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
          if (!e.target.closest('.btn-author-profile')) {
            e.stopPropagation();
          }
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

      const readMoreLink = card.querySelector('.card-read-more');
      if (readMoreLink) {
        readMoreLink.addEventListener('click', function () {
          try {
            sessionStorage.setItem('sc_feed_scroll', String(window.scrollY || window.pageYOffset || 0));
          } catch (e) {}
        });
      }

      const commentsLink = card.querySelector('.btn-card-comments');
      if (commentsLink) {
        commentsLink.addEventListener('click', function () {
          try {
            sessionStorage.setItem('sc_feed_scroll', String(window.scrollY || window.pageYOffset || 0));
          } catch (e) {}
        });
      }

      const likeBtn = card.querySelector('.btn-card-like');
      if (likeBtn) {
        likeBtn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          if (typeof options.onLikeToggle === 'function') {
            options.onLikeToggle(item.id, likeBtn, item);
          }
        });
      }

      const bookmarkBtn = card.querySelector('.btn-card-bookmark');
      if (bookmarkBtn) {
        bookmarkBtn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          if (typeof options.onBookmarkToggle === 'function') {
            options.onBookmarkToggle(item.id, bookmarkBtn, item);
          }
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

  function createAvatarEl(authorData, options) {
    options = options || {};
    let name = '';
    let avatarUrl = '';
    let initials = '';
    if (typeof authorData === 'string') {
      name = authorData;
    } else if (authorData && typeof authorData === 'object') {
      name = authorData.author || authorData.title || authorData.name || '';
      avatarUrl = authorData.avatar || authorData.avatarUrl || authorData.photo || '';
      initials = authorData.initials || authorData.authorInitials || '';
    }
    if (!initials) {
      initials = name.split(/\s+/).map(function (p) { return p[0]; }).filter(Boolean).slice(0, 2).join('').toUpperCase() || 'АП';
    }

    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'author-avatar' + (options.className ? (' ' + options.className) : '');
    if (options.id) avatarDiv.id = options.id;
    avatarDiv.setAttribute('aria-hidden', 'true');

    if (avatarUrl) {
      const img = document.createElement('img');
      img.className = 'author-avatar-img';
      img.src = avatarUrl;
      img.alt = name || 'Аватар';
      img.onerror = function () {
        avatarDiv.innerHTML = escapeHtml(initials);
      };
      avatarDiv.appendChild(img);
    } else {
      avatarDiv.textContent = initials;
    }
    return avatarDiv;
  }

  window.SmartContractumCard = {
    escapeHtml: escapeHtml,
    cleanString: cleanString,
    getBadgesHtml: getBadgesHtml,
    getComplexityBadgeHtml: getComplexityBadgeHtml,
    renderVoteCapsuleHtml: renderVoteCapsuleHtml,
    renderCardInnerHtml: renderCardInnerHtml,
    createCardElement: createCardElement,
    createAvatarEl: createAvatarEl
  };

})(window);
