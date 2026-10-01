/**
 * votes.js - Unified Voting Capsule and Global Voting Controller
 * SmartContractum Platform (100% Offline-First, Zero Emojis, Zero Em Dashes)
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

  function getCurrentUser() {
    if (window.currentUser) return window.currentUser;
    if (typeof window.getCurrentUser === 'function') {
      return window.getCurrentUser();
    }
    return null;
  }

  function invokeAuthModal() {
    if (typeof window.openAuthModal === 'function') {
      try {
        window.openAuthModal();
        return;
      } catch (e) {}
    }
    const loginBtn = document.getElementById('headerLoginBtn');
    if (loginBtn) {
      loginBtn.click();
      return;
    }
    const modal = document.getElementById('authModal') || document.getElementById('feedAuthModal');
    if (modal) {
      modal.style.display = 'flex';
    }
  }

  function showToast(message, type) {
    if (!message) return;
    const articleToast = document.getElementById('articleToast');
    if (articleToast) {
      articleToast.textContent = message;
      articleToast.style.display = 'block';
      articleToast.className = 'article-toast show' + (type === 'error' ? ' toast-error' : '');
      clearTimeout(articleToast._timer);
      articleToast._timer = setTimeout(function () {
        articleToast.style.display = 'none';
        articleToast.className = 'article-toast';
      }, 3500);
      return;
    }

    const feedToast = document.getElementById('feedToast');
    if (feedToast) {
      feedToast.textContent = message;
      feedToast.style.display = 'block';
      feedToast.className = 'feed-toast is-visible' + (type === 'error' ? ' feed-toast-error' : '');
      clearTimeout(feedToast._timer);
      feedToast._timer = setTimeout(function () {
        feedToast.style.display = 'none';
        feedToast.className = 'feed-toast';
      }, 3500);
      return;
    }

    const container = document.getElementById('toast-container');
    if (container) {
      const toast = document.createElement('div');
      toast.className = 'toast toast-' + (type === 'error' ? 'error' : 'info');
      toast.textContent = message;
      container.appendChild(toast);
      setTimeout(function () {
        toast.remove();
      }, 3500);
      return;
    }

    // Fallback alert
    if (type === 'error') {
      alert(message);
    }
  }

  function renderVoteCapsuleHtml(options) {
    options = options || {};
    const targetType = options.targetType || 'article';
    const targetId = options.targetId ? String(options.targetId) : '';
    const score = Number.isInteger(options.score) ? options.score : (parseInt(options.score, 10) || 0);
    const myVote = Number.isInteger(options.myVote) ? options.myVote : (parseInt(options.myVote, 10) || 0);
    const isAuthor = Boolean(options.isAuthor);
    const canVote = options.canVote !== undefined ? Boolean(options.canVote) : (!isAuthor);
    const isDeleted = Boolean(options.isDeleted);
    const isPreview = Boolean(options.isPreview);

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
      if (myVote === 1) {
        upTitle = 'Снять голос';
      }
      if (myVote === -1) {
        downTitle = 'Снять голос';
      }
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

  function updateCapsuleElement(c, state) {
    if (!c) return;
    c.classList.remove('is-pending');
    c.setAttribute('data-score', String(state.score));
    c.setAttribute('data-my-vote', String(state.myVote));
    c.setAttribute('data-can-vote', state.canVote ? 'true' : 'false');

    c.classList.toggle('has-voted-up', state.myVote === 1);
    c.classList.toggle('has-voted-down', state.myVote === -1);

    const scoreEl = c.querySelector('.vote-score');
    if (scoreEl) {
      scoreEl.textContent = String(state.score);
      scoreEl.setAttribute('data-score', String(state.score));
      scoreEl.classList.toggle('is-positive', state.score > 0);
      scoreEl.classList.toggle('is-negative', state.score < 0);
      scoreEl.classList.toggle('is-zero', state.score === 0);
    }

    const isAuthor = c.getAttribute('data-is-author') === 'true' || state.canVote === false;
    const targetType = c.getAttribute('data-vote-target-type') || 'article';
    const authorTitle = targetType === 'comment'
      ? 'Нельзя голосовать за собственный комментарий'
      : 'Нельзя голосовать за собственный материал';

    const upBtn = c.querySelector('.vote-btn-up');
    if (upBtn) {
      const isUp = state.myVote === 1;
      upBtn.classList.toggle('is-voted', isUp);
      upBtn.setAttribute('aria-pressed', isUp ? 'true' : 'false');
      upBtn.title = isAuthor ? authorTitle : (isUp ? 'Снять голос' : 'Повысить рейтинг');
      upBtn.setAttribute('aria-label', isAuthor ? authorTitle : (isUp ? 'Снять голос' : 'Повысить рейтинг'));
      upBtn.disabled = isAuthor;
      if (isAuthor) {
        upBtn.setAttribute('aria-disabled', 'true');
      } else {
        upBtn.removeAttribute('aria-disabled');
      }
    }

    const downBtn = c.querySelector('.vote-btn-down');
    if (downBtn) {
      const isDown = state.myVote === -1;
      downBtn.classList.toggle('is-voted', isDown);
      downBtn.setAttribute('aria-pressed', isDown ? 'true' : 'false');
      downBtn.title = isAuthor ? authorTitle : (isDown ? 'Снять голос' : 'Понизить рейтинг');
      downBtn.setAttribute('aria-label', isAuthor ? authorTitle : (isDown ? 'Снять голос' : 'Понизить рейтинг'));
      downBtn.disabled = isAuthor;
      if (isAuthor) {
        downBtn.setAttribute('aria-disabled', 'true');
      } else {
        downBtn.removeAttribute('aria-disabled');
      }
    }
  }

  function syncVoteCapsules(targetType, targetId, state) {
    if (!targetId) return;
    const selector = '.vote-capsule[data-vote-target-type="' + targetType + '"][data-vote-target-id="' + targetId + '"]';
    const capsules = document.querySelectorAll(selector);
    capsules.forEach(function (c) {
      updateCapsuleElement(c, state);
    });
  }

  function handleVoteClick(e) {
    const btn = e.target.closest('.vote-btn');
    if (!btn) return;

    e.preventDefault();
    e.stopPropagation();
    if (typeof e.stopImmediatePropagation === 'function') {
      e.stopImmediatePropagation();
    }

    const capsule = btn.closest('.vote-capsule');
    if (!capsule) return;

    if (capsule.classList.contains('is-preview')) {
      return;
    }

    const user = getCurrentUser();
    if (!user) {
      invokeAuthModal();
      return;
    }

    const isAuthor = capsule.getAttribute('data-is-author') === 'true' || capsule.getAttribute('data-can-vote') === 'false';
    if (isAuthor || btn.disabled || btn.getAttribute('aria-disabled') === 'true') {
      const targetType = capsule.getAttribute('data-vote-target-type') || 'article';
      const authorMsg = targetType === 'comment'
        ? 'Нельзя голосовать за собственный комментарий'
        : 'Нельзя голосовать за собственный материал';
      showToast(authorMsg, 'error');
      return;
    }

    if (capsule.classList.contains('is-pending')) {
      return;
    }

    const targetType = capsule.getAttribute('data-vote-target-type') || 'article';
    const targetId = capsule.getAttribute('data-vote-target-id');
    if (!targetId) return;

    const dir = parseInt(btn.getAttribute('data-dir'), 10) || 0;
    const isVoted = btn.classList.contains('is-voted') || btn.getAttribute('aria-pressed') === 'true';
    const newVal = isVoted ? 0 : dir;

    const selector = '.vote-capsule[data-vote-target-type="' + targetType + '"][data-vote-target-id="' + targetId + '"]';
    const matchingCapsules = Array.from(document.querySelectorAll(selector));

    const previousState = {
      score: parseInt(capsule.getAttribute('data-score'), 10) || 0,
      myVote: parseInt(capsule.getAttribute('data-my-vote'), 10) || 0,
      canVote: true
    };

    // Lock all matching capsules on page
    matchingCapsules.forEach(function (c) {
      c.classList.add('is-pending');
      const btns = c.querySelectorAll('.vote-btn');
      btns.forEach(function (b) { b.disabled = true; });
    });

    const endpoint = targetType === 'comment'
      ? ('/api/comments/' + encodeURIComponent(targetId) + '/vote')
      : ('/api/articles/' + encodeURIComponent(targetId) + '/vote');

    fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json; charset=utf-8'
      },
      body: JSON.stringify({ value: newVal })
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { status: res.status, data: data };
        });
      })
      .then(function (resObj) {
        const status = resObj.status;
        const data = resObj.data;

        if (status === 200 && data && data.success) {
          const updatedState = {
            score: data.score,
            myVote: data.myVote,
            canVote: data.canVote !== false
          };
          matchingCapsules.forEach(function (c) {
            updateCapsuleElement(c, updatedState);
          });

          // Dispatch window event for external caches
          try {
            window.dispatchEvent(new CustomEvent('smartcontractum:voted', {
              detail: {
                targetType: targetType,
                targetId: targetId,
                score: data.score,
                myVote: data.myVote,
                canVote: data.canVote
              }
            }));
          } catch (e) {}
        } else if (status === 401) {
          matchingCapsules.forEach(function (c) {
            updateCapsuleElement(c, previousState);
          });
          invokeAuthModal();
        } else if (status === 403) {
          matchingCapsules.forEach(function (c) {
            c.setAttribute('data-is-author', 'true');
            c.setAttribute('data-can-vote', 'false');
            updateCapsuleElement(c, {
              score: previousState.score,
              myVote: 0,
              canVote: false
            });
          });
          const errText = (data && data.error) || 'Нельзя голосовать за собственный материал';
          showToast(errText, 'error');
        } else {
          matchingCapsules.forEach(function (c) {
            updateCapsuleElement(c, previousState);
          });
          const errText = (data && data.error) || 'Ошибка при сохранении голоса';
          showToast(errText, 'error');
        }
      })
      .catch(function () {
        matchingCapsules.forEach(function (c) {
          updateCapsuleElement(c, previousState);
        });
        showToast('Ошибка сети при отправке голоса', 'error');
      });
  }

  function initVoting() {
    if (window._smartContractumVotingInitialized) return;
    window._smartContractumVotingInitialized = true;
    document.addEventListener('click', handleVoteClick, true);
  }

  // Auto-initialize controller
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVoting);
  } else {
    initVoting();
  }

  window.SmartContractumVotes = {
    renderVoteCapsuleHtml: renderVoteCapsuleHtml,
    updateCapsuleElement: updateCapsuleElement,
    syncVoteCapsules: syncVoteCapsules,
    handleVoteClick: handleVoteClick,
    initVoting: initVoting,
    showToast: showToast
  };

})(window);
