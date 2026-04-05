/* --- NOTIFICATIONS --- */
import { isUserLoggedIn } from './state.js';
import { apiRequest, escapeHTML } from './utils.js';
import { openModal, closeModal } from './modal.js';
import { animateAndOpenCommentView } from './comments.js';

let notifPage = 1;
let hasMoreNotifs = false;

export function initNotifications() {
    if (!isUserLoggedIn) return;
    fetchUnreadCount();
}

export async function fetchUnreadCount() {
    if (!isUserLoggedIn) return;
    try {
        const d = await apiRequest('/api/notifications/unread-count');
        updateBadges(d.unread_count);
    } catch (e) {
        // silent fail
    }
}

function updateBadges(count) {
    const badge = document.getElementById('notifBadge');
    const profileBadge = document.getElementById('profileNotifBadge');

    [badge, profileBadge].forEach(b => {
        if (!b) return;
        if (count > 0) {
            b.textContent = count > 99 ? '99+' : count;
            b.style.display = 'inline-flex';
        } else {
            b.style.display = 'none';
        }
    });
}

export function openNotificationsModal() {
    closeModal('profileModal', true);
    openModal('notificationsModal');
    notifPage = 1;
    loadNotifications(1);
}

async function loadNotifications(page) {
    const feed = document.getElementById('notifFeed');
    const loadMoreBtn = document.getElementById('notifLoadMoreBtn');

    if (page === 1) feed.innerHTML = '<div class="spinner"></div>';

    try {
        const d = await apiRequest(`/api/notifications?page=${page}&limit=20`);

        if (page === 1) feed.innerHTML = '';

        if (d.notifications?.length > 0) {
            const unreadIds = [];
            d.notifications.forEach(n => {
                feed.appendChild(createNotifItem(n));
                if (!n.is_read) unreadIds.push(n.id);
            });

            // Mark visible notifications as read
            if (unreadIds.length > 0) {
                markRead(unreadIds);
            }

            hasMoreNotifs = d.has_next;
            loadMoreBtn.style.display = d.has_next ? 'block' : 'none';
        } else if (page === 1) {
            feed.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-muted);">Henüz bildirim yok.</div>';
            loadMoreBtn.style.display = 'none';
        }
    } catch (e) {
        if (page === 1) feed.innerHTML = '<div style="text-align:center;color:var(--error-color);">Hata.</div>';
    }
}

async function markRead(ids) {
    try {
        await apiRequest('/api/notifications/mark-read', 'POST', { ids });
        fetchUnreadCount();
    } catch (e) {
        // silent fail
    }
}

function createNotifItem(n) {
    const div = document.createElement('div');
    div.className = 'notif-item' + (n.is_read ? '' : ' notif-unread');

    const isClickable = ['word_vote', 'comment_vote', 'new_comment'].includes(n.notification_type) && n.word_id;
    if (isClickable) {
        div.style.cursor = 'pointer';
        div.addEventListener('click', () => {
            closeModal('notificationsModal', true);
            animateAndOpenCommentView(null, n.word_id, n.word_text, n.word_def || '', n.word_example || '', n.word_etymology || '', true);
        });
    }

    const icon = getNotifIcon(n.notification_type);
    const text = buildNotifText(n);
    const date = new Date(n.timestamp).toLocaleDateString('tr-TR', {
        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
    });

    div.innerHTML = `
        <div class="notif-icon">${icon}</div>
        <div class="notif-content">
            <div class="notif-text">${text}</div>
            <div class="notif-date">${escapeHTML(date)}</div>
        </div>
    `;

    return div;
}

function getNotifIcon(type) {
    switch (type) {
        case 'word_vote':
        case 'comment_vote':
            return '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="var(--accent)" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>';
        case 'new_comment':
            return '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="var(--accent)" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
        case 'challenge_win':
            return '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#f1c40f" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>';
        case 'word_rejected':
        case 'challenge_rejected':
            return '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#e74c3c" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
        default:
            return '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="var(--text-muted)" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>';
    }
}

function buildNotifText(n) {
    const actor = n.actor_username ? `<strong>${escapeHTML(n.actor_username)}</strong>` : 'Birisi';
    const word = n.word_text ? `<strong>${escapeHTML(n.word_text)}</strong>` : '';

    switch (n.notification_type) {
        case 'word_vote':
            return `${actor} ${word} sözcüğünü beğendi.`;
        case 'comment_vote':
            return `${actor} ${word} sözcüğündeki yorumunuzu beğendi.`;
        case 'new_comment':
            return `${actor} ${word} sözcüğünüze yorum yaptı.`;
        case 'challenge_win':
            return escapeHTML(n.message);
        case 'word_rejected':
            return `${word} sözcüğünüz reddedildi: "${escapeHTML(n.message)}"`;
        case 'challenge_rejected':
            return `Yarışma öneriniz reddedildi: "${escapeHTML(n.message)}"`;
        default:
            return escapeHTML(n.message || 'Bildirim');
    }
}

export function loadMoreNotifications() {
    if (hasMoreNotifs) {
        notifPage++;
        loadNotifications(notifPage);
    }
}

export function closeNotificationsModal(e, force) {
    closeModal('notificationsModal', force, e);
}

export function notifBackToProfile() {
    closeModal('notificationsModal', true);
    openModal('profileModal');
}
