/* --- PROFILE --- */
import { state, isUserLoggedIn } from './state.js';
import { apiRequest, showCustomAlert } from './utils.js';
import { openModal, closeModal } from './modal.js';
import { appendCards } from './feed.js';

export function openProfileModal(targetUsername = null) {
    if (!targetUsername && isUserLoggedIn) targetUsername = state.currentUserUsername;
    if (!targetUsername) return;

    state.currentProfileUser = targetUsername;
    openModal('profileModal');

    const isOwnProfile = (targetUsername === state.currentUserUsername);
    document.querySelectorAll('.edit-profile-btn').forEach(el => {
        el.style.display = isOwnProfile ? 'flex' : 'none';
    });

    document.getElementById('profileUsername').innerText = targetUsername;
    fetchProfileData(targetUsername);
}

async function fetchProfileData(username) {
    try {
        const d = await apiRequest(`/api/profile?username=${encodeURIComponent(username)}`);
        document.getElementById('profileUsername').innerText = d.username;
        document.getElementById('profileDate').innerText = d.date_joined;
        document.getElementById('statWords').innerText = d.word_count;
        document.getElementById('statComments').innerText = d.comment_count;
        document.getElementById('statScore').innerText = d.total_score;
    } catch (e) {
        console.error(e);
        showCustomAlert("Kullanıcı bulunamadı", "error");
    }
}

export function openMyWordsModal() {
    closeModal('profileModal', true);
    openModal('myWordsModal');
    fetchMyWordsFeed();
}

async function fetchMyWordsFeed() {
    const c = document.getElementById('myWordsFeed');
    c.innerHTML = '<div class="spinner"></div>';

    let url = '/api/my-words';
    if (state.currentProfileUser) url += `?username=${encodeURIComponent(state.currentProfileUser)}`;

    const title = document.querySelector('#myWordsModal h2');
    if (title) {
        title.innerText = (state.currentProfileUser === state.currentUserUsername)
            ? "Sözcüklerim"
            : `${state.currentProfileUser} adlı kullanıcının sözcükleri`;
    }

    try {
        const d = await apiRequest(url);
        c.innerHTML = '';
        if (d.words?.length > 0) appendCards(d.words, c, false);
        else c.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted);">Sözcük yok.</div>';
    } catch (e) { c.innerHTML = '<div style="text-align:center;color:var(--error-color);">Hata.</div>'; }
}

export function openEditProfileModal() {
    closeModal('profileModal', true);
    openModal('editProfileModal');
    if (state.currentUserUsername) document.getElementById('newUsernameInput').value = state.currentUserUsername;
}

export function backToProfile() {
    closeModal('editProfileModal', true);
    openModal('profileModal');
}

export function handleChangePassword() {
    const current = document.getElementById('currentPassword').value;
    const p1 = document.getElementById('newPassword').value;
    const p2 = document.getElementById('newPasswordConfirm').value;
    if (!current) return showCustomAlert("Mevcut şifrenizi girin.", "error");
    if (current.length > 60) return showCustomAlert("Şifre en fazla 60 karakter olabilir.", "error");
    if (p1.length < 6 || p1 !== p2) return showCustomAlert("Hatalı veya eşleşmeyen şifre.", "error");
    if (p1.length > 60) return showCustomAlert("Yeni şifre en fazla 60 karakter olabilir.", "error");

    apiRequest('/api/password', 'PATCH', { current_password: current, new_password: p1 })
        .then(() => {
            showCustomAlert("Şifre değişti.");
            document.getElementById('currentPassword').value = '';
            document.getElementById('newPassword').value = '';
            document.getElementById('newPasswordConfirm').value = '';
        })
        .catch(e => showCustomAlert(e.message, "error"));
}

export function handleChangeUsername() {
    const newUsername = document.getElementById('newUsernameInput').value.trim();
    const oldUsername = state.currentUserUsername;
    if (newUsername) {
        apiRequest('/api/username', 'PATCH', { new_username: newUsername })
            .then(() => {
                showCustomAlert("Kullanıcı adı başarıyla değiştirildi.");
                state.currentUserUsername = newUsername;
                document.body.setAttribute('data-username', newUsername);
                document.querySelectorAll('.user-badge').forEach(badge => {
                    if (badge.innerText === oldUsername) {
                        badge.innerText = newUsername;
                    }
                });
                if (state.currentProfileUser === oldUsername) {
                    state.currentProfileUser = newUsername;
                    document.getElementById('profileUsername').innerText = newUsername;
                }
                const myWordsTitle = document.querySelector('#myWordsModal h2');
                if (myWordsTitle && myWordsTitle.innerText.includes(oldUsername)) {
                    myWordsTitle.innerText = `${newUsername} adlı kullanıcının sözcükleri`;
                }
                closeModal('editProfileModal', true);
                openModal('profileModal');

            })
            .catch(e => showCustomAlert(e.message, "error"));
    }
}
