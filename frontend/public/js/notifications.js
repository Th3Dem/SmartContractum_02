(function() {
  if (window.SCNotifications && window.SCNotifications._initialized) {
    return window.SCNotifications;
  }

  const NotificationsClient = {
    _initialized: true,
    currentUser: null,
    pollTimer: null,
    pollIntervalMs: 30000,
    unreadCount: 0,
    notifications: [],
    activeFetchPromise: null,
    activeFetchUserId: null,
    // Bumped on every request and on sign-out: a late response of an older request or account is dropped
    fetchSeq: 0,

    init: function() {
      this.btn = document.getElementById('headerNotificationsBtn');
      this.badge = document.getElementById('headerNotifBadge');
      this.popup = document.getElementById('headerNotifPopup');
      this.listContainer = document.getElementById('notifListContainer');
      this.markAllBtn = document.getElementById('notifMarkAllReadBtn');
      this.wrap = document.getElementById('headerNotifWrap');

      if (!this.wrap || !this.btn || !this.popup) return;

      this.btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.togglePopup();
      });

      if (this.markAllBtn) {
        this.markAllBtn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.markAllRead();
        });
      }

      document.addEventListener('click', (e) => {
        if (this.popup.getAttribute('aria-expanded') === 'true' && !this.wrap.contains(e.target)) {
          this.closePopup();
        }
      });

      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.popup.getAttribute('aria-expanded') === 'true') {
          this.closePopup();
        }
      });

      window.addEventListener('auth:change', (e) => {
        if (e.detail && e.detail.authenticated && e.detail.user) {
          const switched = !this.currentUser || this.currentUser.id !== e.detail.user.id;
          this.currentUser = e.detail.user;
          if (switched) {
            // Another account: never show the previous user's list while the new one loads
            this.fetchSeq++;
            this.resetUI();
          }
          this.fetchNotifications();
          this.startPolling();
        } else {
          this.currentUser = null;
          this.fetchSeq++;
          this.stopPolling();
          this.resetUI();
        }
      });

      document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
          this.stopPolling(true);
        } else {
          if (this.currentUser) {
            this.fetchNotifications();
            this.startPolling();
          }
        }
      });

      this.checkInitialAuth();
    },

    checkInitialAuth: function() {
      if (window.SCAuth && window.SCAuth.currentUser) {
        this.currentUser = window.SCAuth.currentUser;
        this.fetchNotifications();
        this.startPolling();
      } else {
        fetch('/api/auth/status')
          .then(res => res.json())
          .then(data => {
            if (data && data.authenticated && data.user) {
              this.currentUser = data.user;
              this.fetchNotifications();
              this.startPolling();
            }
          })
          .catch(() => {});
      }
    },

    togglePopup: function() {
      const isExpanded = this.popup.getAttribute('aria-expanded') === 'true';
      this.popup.setAttribute('aria-expanded', !isExpanded);
    },

    closePopup: function() {
      this.popup.setAttribute('aria-expanded', 'false');
    },

    startPolling: function() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer);
      }
      this.pollTimer = setInterval(() => {
        this.fetchNotifications();
      }, this.pollIntervalMs);
    },

    stopPolling: function(temporary = false) {
      if (this.pollTimer) {
        clearInterval(this.pollTimer);
        this.pollTimer = null;
      }
    },

    resetUI: function() {
      this.unreadCount = 0;
      this.notifications = [];
      if (this.badge) {
        this.badge.style.display = 'none';
        this.badge.textContent = '';
      }
      if (this.listContainer) {
        this.listContainer.innerHTML = '<div class="notif-empty-state">Нет новых уведомлений</div>';
      }
    },

    fetchNotifications: function() {
      if (!this.currentUser) return;

      const currentUserId = this.currentUser.id;

      if (this.activeFetchPromise && this.activeFetchUserId === currentUserId) {
        return this.activeFetchPromise;
      }

      const seq = ++this.fetchSeq;
      this.activeFetchUserId = currentUserId;
      const request = fetch('/api/notifications', { credentials: 'same-origin' })
        .then(res => {
          if (!res.ok) throw new Error('Failed to fetch notifications');
          return res.json();
        })
        .then(data => {
          if (seq !== this.fetchSeq || !this.currentUser || this.currentUser.id !== currentUserId) {
            return;
          }
          this.unreadCount = data.unreadCount || 0;
          this.notifications = data.notifications || [];
          this.updateUI();
        })
        .catch(err => {
          console.error('Error fetching notifications:', err);
        })
        .finally(() => {
          if (this.activeFetchPromise === request) {
            this.activeFetchPromise = null;
            this.activeFetchUserId = null;
          }
        });

      this.activeFetchPromise = request;
      return request;
    },

    updateUI: function() {
      if (this.badge) {
        if (this.unreadCount > 0) {
          this.badge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
          this.badge.style.display = 'block';
        } else {
          this.badge.style.display = 'none';
        }
      }

      if (!this.listContainer) return;

      this.listContainer.innerHTML = '';

      if (!this.notifications || this.notifications.length === 0) {
        this.listContainer.innerHTML = '<div class="notif-empty-state">Нет новых уведомлений</div>';
        return;
      }

      this.notifications.forEach(n => {
        // The API returns camelCase fields; accept snake_case too for older responses
        const isRead = Boolean(n.isRead !== undefined ? n.isRead : n.is_read);
        const rawArticleId = n.articleId || n.article_id || '';
        const rawCommentId = n.commentId || n.comment_id || '';
        const createdAt = n.createdAt || n.created_at;

        const item = document.createElement('a');
        item.className = 'notif-item ' + (isRead ? 'is-read' : 'is-unread');
        const isAuthorMaterial = n.type === 'author_publication' || n.type === 'author_question';
        const unavailable = isAuthorMaterial && n.available === false;
        if (isAuthorMaterial) {
          item.classList.add('notif-item-author');
          item.setAttribute('data-notif-type', n.type);
        }

        if (unavailable) {
          // The material is no longer public: no link, no title, only the neutral text from the server
          item.href = '#';
          item.classList.add('is-unavailable');
          item.setAttribute('role', 'button');
        } else if (n.type === 'moderation_revision' || n.type === 'moderation_rejected') {
          item.href = 'my-materials.html';
        } else {
          const articleId = encodeURIComponent(rawArticleId);
          item.href = rawCommentId
            ? `article.html?id=${articleId}#comment-${encodeURIComponent(rawCommentId)}`
            : `article.html?id=${articleId}`;
        }

        item.innerHTML = `
          <div class="notif-item-title">${this.escapeHTML(n.title || 'Уведомление')}</div>
          <div class="notif-item-msg">${this.escapeHTML(n.message || '')}</div>
          <div class="notif-item-time">${this.formatTime(createdAt)}</div>
        `;

        item.addEventListener('click', (e) => {
          if (unavailable) e.preventDefault();
          if (!isRead) {
            this.markAsRead(n.id, item);
          }
        });

        this.listContainer.appendChild(item);
      });
    },

    markAsRead: function(notificationId, itemElement) {
      const userId = this.currentUser && this.currentUser.id;
      const notif = (this.notifications || []).find(x => x.id === notificationId);
      if (notif) notif.isRead = true;
      // keepalive: the click also navigates to the material, the request must outlive the page
      fetch('/api/notifications/read', {
        method: 'POST',
        keepalive: true,
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ notificationId: notificationId })
      }).then(res => {
        if (!this.currentUser || this.currentUser.id !== userId) return;
        if (res.ok) {
          return res.json().then(data => {
            if (!this.currentUser || this.currentUser.id !== userId) return;
            itemElement.classList.remove('is-unread');
            itemElement.classList.add('is-read');
            this.unreadCount = data && typeof data.unreadCount === 'number'
              ? data.unreadCount
              : Math.max(0, this.unreadCount - 1);
            this.updateUIBadgeOnly();
          });
        }
        if (notif) notif.isRead = false;
      }).catch(err => console.error('Error marking read:', err));
    },

    markAllRead: function() {
      if (this.unreadCount === 0 && (!this.notifications || this.notifications.every(n => (n.isRead !== undefined ? n.isRead : n.is_read)))) {
        return;
      }

      const userId = this.currentUser && this.currentUser.id;
      fetch('/api/notifications/read', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({})
      }).then(res => {
        if (!this.currentUser || this.currentUser.id !== userId) return;
        if (res.ok) {
          this.unreadCount = 0;
          this.updateUIBadgeOnly();
          if (this.listContainer) {
            const items = this.listContainer.querySelectorAll('.notif-item');
            items.forEach(item => {
              item.classList.remove('is-unread');
              item.classList.add('is-read');
            });
          }
          if (this.notifications) {
            this.notifications.forEach(n => { n.isRead = true; n.is_read = true; });
          }
        }
      }).catch(err => console.error('Error marking all read:', err));
    },

    updateUIBadgeOnly: function() {
      if (this.badge) {
        if (this.unreadCount > 0) {
          this.badge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
          this.badge.style.display = 'block';
        } else {
          this.badge.style.display = 'none';
        }
      }
    },

    escapeHTML: function(str) {
      if (!str) return '';
      const div = document.createElement('div');
      div.textContent = str;
      return div.innerHTML;
    },

    formatTime: function(isoString) {
      if (!isoString) return '';
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return isoString;
      return date.toLocaleString('ru-RU', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    }
  };

  window.SCNotifications = NotificationsClient;
  window.NotificationsClient = NotificationsClient;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      window.SCNotifications.init();
    });
  } else {
    window.SCNotifications.init();
  }
})();
