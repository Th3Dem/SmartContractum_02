/**
 * card.js - Единый общий компонент карточки публикации SmartContractum
 *
 * Используется совместно в:
 * 1. Ленте публикаций (feed.html, feed.js)
 * 2. Живом предпросмотре формы публикации (editor.html, publication.js)
 *
 * Обеспечивает:
 * - Единый порядок блоков (Хабр-подобный компактный лейаут):
 *   1. Автор (аватар, имя, компания)
 *   2. Заголовок
 *   3. Бейджи (вопрос, все темы 1-5, клуб)
 *   4. Полноширинная обложка (100% внутренней ширины, пропорции 780:350 / 78:35)
 *   5. Краткое описание (clamped до 2 строк)
 *   6. Сервисная строка (дата публикации, время чтения, формат публикации)
 *   7. Футер (лайк, рейтинг капсула, комментарии / ответы, сохранение публикации, читать далее)
 * - Чистоту обложки: на обложку НЕ накладываются никакие элементы сайта.
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

    // 1. Topic Titles & Badges (all topics 1 to 5)
    let topicIds = [];
    if (Array.isArray(item.topics) && item.topics.length > 0) {
      topicIds = item.topics;
    } else if (item.topic) {
      topicIds = [item.topic];
    }

    if (topicIds.length > 0) {
      topicIds.forEach(function (topicId, idx) {
        let topicTitle = '';
        if (window.PublicationConfig && typeof window.PublicationConfig.getTopicById === 'function') {
          const t = window.PublicationConfig.getTopicById(topicId);
          if (t) topicTitle = t.title;
        }
        if (!topicTitle && item.topicTitles && Array.isArray(item.topicTitles) && item.topicTitles[idx]) {
          topicTitle = item.topicTitles[idx];
        }
        if (!topicTitle && idx === 0 && item.topicTitle) {
          topicTitle = item.topicTitle;
        }
        if (!topicTitle && typeof topicId === 'string') {
          topicTitle = topicId;
        }
        if (topicTitle) {
          const idAttr = (isPreview && idx === 0) ? ' id="preview-card-badge-topic"' : '';
          badgesHtml += '<span class="meta-badge topic-badge"' + idAttr + '>' + escapeHtml(topicTitle) + '</span>';
        }
      });
    } else if (item.topicTitle) {
      badgesHtml += '<span class="meta-badge topic-badge"' + (isPreview ? ' id="preview-card-badge-topic"' : '') + '>' + escapeHtml(item.topicTitle) + '</span>';
    }

    if (item.clubTitle) {
      badgesHtml += '<span class="meta-badge club-badge"' + (isPreview ? ' id="preview-card-badge-club"' : '') + '>' + escapeHtml(item.clubTitle) + '</span>';
    }

    // Note: Format badge is rendered in the bottom service row.
    // Note: Complexity and audience badges are completely removed per Issue #61.

    return badgesHtml;
  }

  function getFormatBadgeHtml(item, options) {
    options = options || {};
    const isPreview = Boolean(options.isPreview);
    const isQuestion = Boolean(
      item.materialType === 'question' ||
      item.type === 'question' ||
      item.material_type === 'question'
    );
    if (isQuestion) {
      return '';
    }

    let formatTitle = '';
    if (window.PublicationConfig && typeof window.PublicationConfig.getFormatById === 'function' && item.format && item.format !== 'not_specified' && item.format !== 'none') {
      const f = window.PublicationConfig.getFormatById(item.format);
      if (f && f.title && f.title.toLowerCase() !== 'не указан') {
        formatTitle = f.title;
      }
    } else if (item.formatTitle) {
      formatTitle = item.formatTitle;
    }
    if (formatTitle) {
      // Strip any legacy 'Формат: ' prefix
      const cleanFormat = formatTitle.replace(/^формат:\s*/i, '').trim();
      return '<span class="meta-badge format-badge card-format-badge"' + (isPreview ? ' id="preview-card-badge-format"' : '') + '>' + escapeHtml(cleanFormat) + '</span>';
    } else if (isPreview) {
      return '<span class="meta-badge format-badge card-format-badge" id="preview-card-badge-format" style="display: none;"></span>';
    }
    return '';
  }

  function getComplexityBadgeHtml() {
    return '';
  }

  function renderVoteCapsuleHtml(params) {
    if (window.SmartContractumVotes && typeof window.SmartContractumVotes.renderVoteCapsuleHtml === 'function') {
      return window.SmartContractumVotes.renderVoteCapsuleHtml(params);
    }
    return '';
  }

  function renderCardInnerHtml(item, options, isBookmarked) {
    options = options || {};
    const isPreview = Boolean(options.isPreview);

    const cleanTitle = cleanString(item.title) || (isPreview ? 'Заголовок публикации' : '');
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
      let objPos = '';
      if (item.coverPosition || item.objectPosition) {
        objPos = item.coverPosition || item.objectPosition;
      } else if (typeof item.focalPoint === 'string' && item.focalPoint) {
        objPos = item.focalPoint;
      } else if (item.focalPoint && item.focalPoint.x != null && item.focalPoint.y != null) {
        objPos = item.focalPoint.x + '% ' + item.focalPoint.y + '%';
      }
      const posAttr = objPos ? (' style="object-position: ' + escapeHtml(objPos) + ';"') : '';

      coverHtml =
        '<div class="card-cover-container is-loading' + (isPreview ? ' pub-feed-card-cover is-loaded' : '') + '"' + (isPreview ? ' id="preview-card-cover"' : '') + '>' +
          '<img class="card-cover-img pub-preview-img" src="' + escapeHtml(item.coverImage) + '" alt="' + escapeHtml(cleanTitle) + '"' + posAttr + ' loading="lazy" ' +
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


    // 7. Bottom in 2 compact rows:
    const readingTimeText = item.readingTime || (isPreview ? '~1 мин чтения' : '5 мин чтения');
    const formatBadgeHtml = getFormatBadgeHtml(item, options);

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
          (formatBadgeHtml ? ('<span class="meta-dot"></span>' + formatBadgeHtml) : '') +
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

    const bookmarkTooltip = isBookmarked ? 'Сохранено' : 'Сохранить';
    const bookmarkAriaLabel = isBookmarked ? 'Удалить из сохраненного' : 'Сохранить публикацию';
    const savesCount = item.savesCount !== undefined ? item.savesCount : (item.saves_count !== undefined ? item.saves_count : 0);
    let bookmarkHtml = '';
    if (isPreview) {
      bookmarkHtml =
        '<button type="button" class="btn-card-action btn-card-bookmark has-count" id="preview-card-bookmark" title="Сохранить" aria-label="Сохранить публикацию" disabled>' +
          '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"></path>' +
          '</svg>' +
          '<span class="card-action-count card-save-count">' + savesCount + '</span>' +
        '</button>';
    } else {
      const activeClasses = isBookmarked ? 'is-bookmarked is-saved' : '';
      bookmarkHtml =
        '<button type="button" class="btn-card-action btn-card-bookmark has-count ' + activeClasses + '" id="btn-bookmark" title="' + bookmarkTooltip + '" aria-label="' + bookmarkAriaLabel + '">' +
          '<svg width="16" height="16" viewBox="0 0 24 24" fill="' + (isBookmarked ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"></path>' +
          '</svg>' +
          '<span class="card-action-count card-save-count">' + savesCount + '</span>' +
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

    let shareHtml = '';
    if (isPreview) {
      shareHtml =
        '<button type="button" class="btn-card-action btn-card-share" id="preview-card-share" title="Поделиться" aria-label="Поделиться" disabled>' +
          '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<circle cx="18" cy="5" r="3"></circle>' +
            '<circle cx="6" cy="12" r="3"></circle>' +
            '<circle cx="18" cy="19" r="3"></circle>' +
            '<line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>' +
            '<line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>' +
          '</svg>' +
        '</button>';
    } else {
      shareHtml =
        '<button type="button" class="btn-card-action btn-card-share" data-id="' + escapeHtml(item.id) + '" title="Поделиться" aria-label="Поделиться" aria-haspopup="true" aria-expanded="false">' +
          '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<circle cx="18" cy="5" r="3"></circle>' +
            '<circle cx="6" cy="12" r="3"></circle>' +
            '<circle cx="18" cy="19" r="3"></circle>' +
            '<line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>' +
            '<line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>' +
          '</svg>' +
        '</button>';
    }

    const isReported = typeof options.isReported === 'function' ? options.isReported(item.id) : Boolean(options.isReported);
    let reportHtml = '';
    if (!isAuthor) {
      const reportTooltip = isReported ? 'Жалоба уже отправлена' : 'Пожаловаться';
      if (isPreview) {
        reportHtml =
          '<button type="button" class="btn-card-action btn-card-report" id="preview-card-report" title="Пожаловаться" aria-label="Пожаловаться" disabled>' +
            '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
              '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"></path>' +
              '<line x1="4" y1="22" x2="4" y2="15"></line>' +
            '</svg>' +
          '</button>';
      } else {
        reportHtml =
          '<button type="button" class="btn-card-action btn-card-report' + (isReported ? ' is-reported' : '') + '" data-id="' + escapeHtml(item.id) + '" title="' + reportTooltip + '" aria-label="Пожаловаться">' +
            '<svg width="16" height="16" viewBox="0 0 24 24" fill="' + (isReported ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
              '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"></path>' +
              '<line x1="4" y1="22" x2="4" y2="15"></line>' +
            '</svg>' +
          '</button>';
      }
    }

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
      footerLeftHtml += shareHtml + reportHtml;
      readMoreText = (aCount === 0 ? 'Ответить' : 'Смотреть вопрос');
      if (aCount === 0) {
        actionTargetUrl = questionAnswerUrl;
      }
    } else {
      footerLeftHtml = likeBtnHtml + voteCapsuleHtml + commentsBtnHtml + bookmarkHtml;
      footerLeftHtml += shareHtml + reportHtml;
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
      subInfoHtml +
      footerHtml;
  }

  function createCardElement(item, options) {
    options = options || {};
    const isPreview = Boolean(options.isPreview);
    const isBookmarked = typeof options.isBookmarked === 'function'
      ? options.isBookmarked(item.id)
      : (options.isBookmarked !== undefined ? Boolean(options.isBookmarked) : isCardBookmarked(item.id));

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
          } else {
            toggleCardBookmark(item.id, bookmarkBtn);
          }
        });
      }

      const shareBtn = card.querySelector('.btn-card-share');
      if (shareBtn) {
        shareBtn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          if (typeof options.onShareClick === 'function') {
            options.onShareClick(item.id, shareBtn, item);
          }
        });
      }

      const reportBtn = card.querySelector('.btn-card-report');
      if (reportBtn) {
        reportBtn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          if (typeof options.onReportClick === 'function') {
            options.onReportClick(item.id, reportBtn, item);
          }
        });
      }

    }

    return card;
  }

  // --------------------------------------------------------------------------
  // Bookmarks Management & Helpers (sc_bookmarks)
  // --------------------------------------------------------------------------
  function getStoredBookmarks() {
    try {
      const data = localStorage.getItem('sc_bookmarks');
      if (data) {
        const parsed = JSON.parse(data);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (e) {}
    return [];
  }

  function isCardBookmarked(id) {
    if (!id) return false;
    return getStoredBookmarks().indexOf(id) !== -1;
  }

  function updateBookmarkButtonState(btn, isBookmarked) {
    if (!btn) return;
    btn.classList.toggle('is-bookmarked', Boolean(isBookmarked));
    btn.classList.toggle('is-saved', Boolean(isBookmarked));
    const title = isBookmarked ? 'Сохранено' : 'Сохранить';
    const ariaLabel = isBookmarked ? 'Удалить из сохраненного' : 'Сохранить публикацию';
    btn.title = title;
    btn.setAttribute('aria-label', ariaLabel);
    const svg = btn.querySelector('svg');
    if (svg) {
      svg.setAttribute('fill', isBookmarked ? 'currentColor' : 'none');
    }
  }

  function showCardToast(message) {
    if (typeof window !== 'undefined' && typeof window.showToast === 'function') {
      window.showToast(message);
      return;
    }
    let toast = document.getElementById('cardToast') || document.getElementById('feedToast') || document.getElementById('articleToast');
    if (!toast && typeof document !== 'undefined') {
      toast = document.createElement('div');
      toast.id = 'cardToast';
      toast.className = 'feed-toast';
      document.body.appendChild(toast);
    }
    if (toast) {
      toast.textContent = message;
      toast.classList.add('show');
      setTimeout(function () {
        toast.classList.remove('show');
      }, 3000);
    }
  }

  function toggleCardBookmark(id, btn) {
    if (!id) return false;
    const bookmarks = getStoredBookmarks();
    const idx = bookmarks.indexOf(id);
    let bookmarked = false;
    if (idx !== -1) {
      bookmarks.splice(idx, 1);
      bookmarked = false;
      showCardToast('Публикация удалена из сохраненного');
    } else {
      bookmarks.push(id);
      bookmarked = true;
      showCardToast('Публикация сохранена');
    }
    try {
      localStorage.setItem('sc_bookmarks', JSON.stringify(bookmarks));
    } catch (e) {}

    if (btn) {
      updateBookmarkButtonState(btn, bookmarked);
      const countEl = btn.querySelector('.card-save-count');
      if (countEl) {
        const curCount = parseInt(countEl.textContent, 10) || 0;
        countEl.textContent = bookmarked ? (curCount + 1) : Math.max(0, curCount - 1);
      }
    }

    if (typeof window !== 'undefined' && window.currentUser) {
      fetch('/api/articles/' + encodeURIComponent(id) + (bookmarked ? '/save' : '/unsave'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data && data.success && typeof data.savesCount === 'number' && btn) {
          const countEl = btn.querySelector('.card-save-count');
          if (countEl) countEl.textContent = data.savesCount;
        }
      })
      .catch(function () {});
    }

    return bookmarked;
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
    getFormatBadgeHtml: getFormatBadgeHtml,
    getComplexityBadgeHtml: getComplexityBadgeHtml,
    renderVoteCapsuleHtml: renderVoteCapsuleHtml,
    renderCardInnerHtml: renderCardInnerHtml,
    createCardElement: createCardElement,
    createAvatarEl: createAvatarEl,
    getStoredBookmarks: getStoredBookmarks,
    isCardBookmarked: isCardBookmarked,
    updateBookmarkButtonState: updateBookmarkButtonState,
    toggleCardBookmark: toggleCardBookmark,
    showCardToast: showCardToast
  };

})(window);
