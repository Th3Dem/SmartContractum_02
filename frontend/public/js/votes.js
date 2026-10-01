/**
 * votes.js - Unified Voting Capsule and Global Voting Controller
 * SmartContractum Platform (100% Offline-First, Zero Emojis, Zero Em Dashes)
 */

(function (window) {
  'use strict';

  window._activePendingVotes = window._activePendingVotes || new Set();

  let _globalSessionGeneration = 1;
  let _lastObservedUserId = null;
  let _voteRequestSeq = 0;
  const _activeVoteRequests = new Map();

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

  function getCurrentUserId() {
    const user = getCurrentUser();
    if (!user || user.isGuest) return null;
    return user.id || null;
  }

  _lastObservedUserId = getCurrentUserId();

  function getSessionToken() {
    const curUserId = getCurrentUserId();
    if (curUserId !== _lastObservedUserId) {
      _lastObservedUserId = curUserId;
      _globalSessionGeneration++;
    }
    return _globalSessionGeneration;
  }

  function bumpSessionToken() {
    _globalSessionGeneration++;
    _lastObservedUserId = getCurrentUserId();
    return _globalSessionGeneration;
  }

  if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
    window.addEventListener('smartcontractum:auth-changed', function () {
      bumpSessionToken();
    });
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

    const user = getCurrentUser();
    const isGuest = !user || Boolean(user.isGuest);
    const isAuthor = Boolean(options.isAuthor || (user && options.authorId && user.id === options.authorId));
    const isDeleted = Boolean(options.isDeleted);
    const isPreview = Boolean(options.isPreview);
    const canVote = options.canVote !== undefined ? Boolean(options.canVote) : (!isAuthor && !isGuest && !isDeleted && !isPreview);

    const targetKey = targetType + ':' + targetId;
    const isPending = Boolean(targetId && window._activePendingVotes && window._activePendingVotes.has(targetKey));

    const authorTitle = targetType === 'comment'
      ? 'Нельзя голосовать за собственный комментарий'
      : 'Нельзя голосовать за собственный материал';

    let upTitle = 'Повысить рейтинг';
    let upLabel = 'Повысить рейтинг';
    let upDisabled = false;
    let downTitle = 'Понизить рейтинг';
    let downLabel = 'Понизить рейтинг';
    let downDisabled = false;

    if (isPreview) {
      upTitle = 'Предпросмотр';
      upDisabled = true;
      downTitle = 'Предпросмотр';
      downDisabled = true;
    } else if (isDeleted) {
      upTitle = 'Комментарий удален';
      upLabel = 'Комментарий удален';
      upDisabled = true;
      downTitle = 'Комментарий удален';
      downLabel = 'Комментарий удален';
      downDisabled = true;
    } else if (isAuthor) {
      upTitle = authorTitle;
      upLabel = authorTitle;
      upDisabled = true;
      downTitle = authorTitle;
      downLabel = authorTitle;
      downDisabled = true;
    } else if (isGuest) {
      upTitle = 'Войдите, чтобы повысить рейтинг';
      upLabel = 'Войдите, чтобы повысить рейтинг';
      upDisabled = false; // Guest can click to trigger login modal
      downTitle = 'Войдите, чтобы понизить рейтинг';
      downLabel = 'Войдите, чтобы понизить рейтинг';
      downDisabled = false; // Guest can click to trigger login modal
    } else {
      if (myVote === 1) {
        upTitle = 'Снять голос';
      }
      if (myVote === -1) {
        downTitle = 'Снять голос';
      }
    }

    if (isPending) {
      upDisabled = true;
      downDisabled = true;
    }

    const upClass = 'vote-btn vote-btn-up' + (myVote === 1 ? ' is-voted' : '');
    const downClass = 'vote-btn vote-btn-down' + (myVote === -1 ? ' is-voted' : '');

    const upArrowSvg =
      '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<line x1="12" y1="19" x2="12" y2="5"></line>' +
        '<polyline points="5 12 12 5 19 12"></polyline>' +
      '</svg>';

    const downArrowSvg =
      '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<line x1="12" y1="5" x2="12" y2="19"></line>' +
        '<polyline points="19 12 12 19 5 12"></polyline>' +
      '</svg>';

    const upBtnHtml =
      '<button type="button" class="' + upClass + '" data-dir="1" ' +
      'aria-label="' + escapeHtml(upLabel) + '" title="' + escapeHtml(upTitle) + '" ' +
      'aria-pressed="' + (myVote === 1 ? 'true' : 'false') + '"' +
      (upDisabled ? ' disabled aria-disabled="true"' : '') + '>' +
        upArrowSvg +
      '</button>';

    const downBtnHtml =
      '<button type="button" class="' + downClass + '" data-dir="-1" ' +
      'aria-label="' + escapeHtml(downLabel) + '" title="' + escapeHtml(downTitle) + '" ' +
      'aria-pressed="' + (myVote === -1 ? 'true' : 'false') + '"' +
      (downDisabled ? ' disabled aria-disabled="true"' : '') + '>' +
        downArrowSvg +
      '</button>';

    let scoreClass = 'vote-score';
    if (score > 0) scoreClass += ' is-positive';
    else if (score < 0) scoreClass += ' is-negative';
    else scoreClass += ' is-zero';

    const scoreHtml = '<span class="' + scoreClass + '" data-score="' + score + '">' + score + '</span>';

    const capsuleClass = 'vote-capsule' +
      (myVote === 1 ? ' has-voted-up' : (myVote === -1 ? ' has-voted-down' : '')) +
      (isPreview ? ' is-preview' : '') +
      (isPending ? ' is-pending' : '') +
      (isGuest ? ' is-guest' : '');

    return (
      '<div class="' + capsuleClass + '" ' +
        'data-vote-target-type="' + escapeHtml(targetType) + '" ' +
        'data-vote-target-id="' + escapeHtml(targetId) + '" ' +
        'data-score="' + score + '" ' +
        'data-my-vote="' + myVote + '" ' +
        'data-can-vote="' + (canVote ? 'true' : 'false') + '"' +
        (isAuthor ? ' data-is-author="true"' : '') +
        (isDeleted ? ' data-is-deleted="true"' : '') +
        (isGuest ? ' data-is-guest="true"' : '') + '>' +
        upBtnHtml +
        scoreHtml +
        downBtnHtml +
      '</div>'
    );
  }

  function updateCapsuleElement(c, state) {
    if (!c) return;
    const targetType = c.getAttribute('data-vote-target-type') || 'article';
    const targetId = c.getAttribute('data-vote-target-id') || '';
    const targetKey = targetType + ':' + targetId;
    const isPending = Boolean(targetId && window._activePendingVotes && window._activePendingVotes.has(targetKey));

    if (isPending) {
      c.classList.add('is-pending');
    } else {
      c.classList.remove('is-pending');
    }

    const score = Number.isInteger(state.score) ? state.score : (parseInt(state.score, 10) || 0);
    const myVote = Number.isInteger(state.myVote) ? state.myVote : (parseInt(state.myVote, 10) || 0);

    c.setAttribute('data-score', String(score));
    c.setAttribute('data-my-vote', String(myVote));
    if (state.canVote !== undefined) {
      c.setAttribute('data-can-vote', state.canVote ? 'true' : 'false');
    }

    c.classList.toggle('has-voted-up', myVote === 1);
    c.classList.toggle('has-voted-down', myVote === -1);

    const scoreEl = c.querySelector('.vote-score');
    if (scoreEl) {
      scoreEl.textContent = String(score);
      scoreEl.setAttribute('data-score', String(score));
      scoreEl.classList.toggle('is-positive', score > 0);
      scoreEl.classList.toggle('is-negative', score < 0);
      scoreEl.classList.toggle('is-zero', score === 0);
    }

    const user = getCurrentUser();
    const isGuest = !user || Boolean(user.isGuest);
    const isAuthor = c.getAttribute('data-is-author') === 'true' || state.isAuthor === true;
    const isDeleted = c.getAttribute('data-is-deleted') === 'true' || state.isDeleted === true;
    const isPreview = c.classList.contains('is-preview') || state.isPreview === true;

    const authorTitle = targetType === 'comment'
      ? 'Нельзя голосовать за собственный комментарий'
      : 'Нельзя голосовать за собственный материал';

    const upBtn = c.querySelector('.vote-btn-up');
    const downBtn = c.querySelector('.vote-btn-down');

    let upDisabled = false;
    let downDisabled = false;
    let upTitle = 'Повысить рейтинг';
    let downTitle = 'Понизить рейтинг';

    if (isPreview) {
      upTitle = 'Предпросмотр';
      downTitle = 'Предпросмотр';
      upDisabled = true;
      downDisabled = true;
    } else if (isDeleted) {
      upTitle = 'Комментарий удален';
      downTitle = 'Комментарий удален';
      upDisabled = true;
      downDisabled = true;
    } else if (isAuthor) {
      upTitle = authorTitle;
      downTitle = authorTitle;
      upDisabled = true;
      downDisabled = true;
    } else if (isGuest) {
      upTitle = 'Войдите, чтобы повысить рейтинг';
      downTitle = 'Войдите, чтобы понизить рейтинг';
      upDisabled = false; // guest can click to open auth modal
      downDisabled = false;
    } else {
      if (myVote === 1) upTitle = 'Снять голос';
      if (myVote === -1) downTitle = 'Снять голос';
    }

    if (isPending) {
      upDisabled = true;
      downDisabled = true;
    }

    if (upBtn) {
      const isUp = myVote === 1;
      upBtn.classList.toggle('is-voted', isUp);
      upBtn.setAttribute('aria-pressed', isUp ? 'true' : 'false');
      upBtn.title = upTitle;
      upBtn.setAttribute('aria-label', upTitle);
      upBtn.disabled = upDisabled;
      if (upDisabled) {
        upBtn.setAttribute('aria-disabled', 'true');
      } else {
        upBtn.removeAttribute('aria-disabled');
      }
    }

    if (downBtn) {
      const isDown = myVote === -1;
      downBtn.classList.toggle('is-voted', isDown);
      downBtn.setAttribute('aria-pressed', isDown ? 'true' : 'false');
      downBtn.title = downTitle;
      downBtn.setAttribute('aria-label', downTitle);
      downBtn.disabled = downDisabled;
      if (downDisabled) {
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

    // 1. Guest click: invoke auth modal!
    const user = getCurrentUser();
    if (!user || user.isGuest) {
      invokeAuthModal();
      return;
    }

    // 2. Author check
    const isAuthor = capsule.getAttribute('data-is-author') === 'true';
    if (isAuthor || (btn.disabled && !capsule.classList.contains('is-pending') && !capsule.classList.contains('is-guest'))) {
      const targetType = capsule.getAttribute('data-vote-target-type') || 'article';
      const authorMsg = targetType === 'comment'
        ? 'Нельзя голосовать за собственный комментарий'
        : 'Нельзя голосовать за собственный материал';
      showToast(authorMsg, 'error');
      return;
    }

    // 3. Pending check
    const targetType = capsule.getAttribute('data-vote-target-type') || 'article';
    const targetId = capsule.getAttribute('data-vote-target-id');
    if (!targetId) return;

    const targetKey = targetType + ':' + targetId;
    if (window._activePendingVotes && window._activePendingVotes.has(targetKey)) {
      return;
    }

    const dir = parseInt(btn.getAttribute('data-dir'), 10) || 0;
    const isVoted = btn.classList.contains('is-voted') || btn.getAttribute('aria-pressed') === 'true';
    const newVal = isVoted ? 0 : dir;

    const selector = '.vote-capsule[data-vote-target-type="' + targetType + '"][data-vote-target-id="' + targetId + '"]';
    const matchingCapsules = Array.from(document.querySelectorAll(selector));

    const previousState = {
      score: parseInt(capsule.getAttribute('data-score'), 10) || 0,
      myVote: parseInt(capsule.getAttribute('data-my-vote'), 10) || 0,
      canVote: true,
      isAuthor: false
    };

    // Mark as pending globally and lock all matching capsules on page
    window._activePendingVotes = window._activePendingVotes || new Set();
    window._activePendingVotes.add(targetKey);

    matchingCapsules.forEach(function (c) {
      c.classList.add('is-pending');
      const btns = c.querySelectorAll('.vote-btn');
      btns.forEach(function (b) { b.disabled = true; });
    });

    const reqSeq = ++_voteRequestSeq;
    _activeVoteRequests.set(targetKey, reqSeq);
    const requestSessionToken = getSessionToken();

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
        }).catch(function () {
          return { status: res.status, data: null };
        });
      })
      .then(function (resObj) {
        const isLatestRequest = _activeVoteRequests.get(targetKey) === reqSeq;
        if (isLatestRequest) {
          _activeVoteRequests.delete(targetKey);
          if (window._activePendingVotes) {
            window._activePendingVotes.delete(targetKey);
          }
        }

        if (requestSessionToken !== getSessionToken()) {
          if (isLatestRequest) {
            document.querySelectorAll(selector).forEach(function (c) {
              updateCapsuleElement(c, {
                score: parseInt(c.getAttribute('data-score'), 10) || 0,
                myVote: parseInt(c.getAttribute('data-my-vote'), 10) || 0,
                canVote: c.getAttribute('data-can-vote') === 'true'
              });
            });
          }
          return;
        }

        if (!isLatestRequest) {
          return;
        }

        const currentMatching = Array.from(document.querySelectorAll(selector));
        const allToUpdate = Array.from(new Set([...matchingCapsules, ...currentMatching]));

        const status = resObj.status;
        const data = resObj.data;

        // Validate response format:
        // score is integer, myVote in {-1, 0, 1}, targetId matches request
        const isValid =
          status === 200 &&
          data &&
          data.success === true &&
          data.targetId === targetId &&
          typeof data.score === 'number' &&
          Number.isInteger(data.score) &&
          typeof data.myVote === 'number' &&
          [-1, 0, 1].indexOf(data.myVote) !== -1;

        if (isValid) {
          const updatedState = {
            score: data.score,
            myVote: data.myVote,
            canVote: data.canVote !== false,
            isAuthor: false
          };
          allToUpdate.forEach(function (c) {
            updateCapsuleElement(c, updatedState);
          });

          // Dispatch window event for sync across all models/views
          try {
            window.dispatchEvent(new CustomEvent('smartcontractum:voted', {
              detail: {
                targetType: targetType,
                targetId: targetId,
                score: data.score,
                myVote: data.myVote,
                canVote: data.canVote,
                sessionToken: requestSessionToken
              }
            }));
          } catch (e) {}
        } else if (status === 401) {
          allToUpdate.forEach(function (c) {
            updateCapsuleElement(c, previousState);
          });
          invokeAuthModal();
        } else if (status === 403) {
          allToUpdate.forEach(function (c) {
            c.setAttribute('data-is-author', 'true');
            c.setAttribute('data-can-vote', 'false');
            updateCapsuleElement(c, {
              score: previousState.score,
              myVote: 0,
              canVote: false,
              isAuthor: true
            });
          });
          const errText = (data && data.error) || 'Нельзя голосовать за собственный материал';
          showToast(errText, 'error');
        } else {
          allToUpdate.forEach(function (c) {
            updateCapsuleElement(c, previousState);
          });
          const errText = (data && data.error) || 'Ошибка при сохранении голоса';
          showToast(errText, 'error');
        }
      })
      .catch(function () {
        const isLatestRequest = _activeVoteRequests.get(targetKey) === reqSeq;
        if (isLatestRequest) {
          _activeVoteRequests.delete(targetKey);
          if (window._activePendingVotes) {
            window._activePendingVotes.delete(targetKey);
          }
        }

        if (requestSessionToken !== getSessionToken()) {
          if (isLatestRequest) {
            document.querySelectorAll(selector).forEach(function (c) {
              updateCapsuleElement(c, {
                score: parseInt(c.getAttribute('data-score'), 10) || 0,
                myVote: parseInt(c.getAttribute('data-my-vote'), 10) || 0,
                canVote: c.getAttribute('data-can-vote') === 'true'
              });
            });
          }
          return;
        }

        if (!isLatestRequest) {
          return;
        }

        const currentMatching = Array.from(document.querySelectorAll(selector));
        const allToUpdate = Array.from(new Set([...matchingCapsules, ...currentMatching]));
        allToUpdate.forEach(function (c) {
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
    showToast: showToast,
    getSessionToken: getSessionToken,
    bumpSessionToken: bumpSessionToken
  };

})(window);
