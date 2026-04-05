/* --- AUTHENTICATION --- */
import { state, isUserLoggedIn } from './state.js';
import { apiRequest, showCustomAlert } from './utils.js';
import { openModal, closeModal } from './modal.js';
import { openProfileModal } from './profile.js';
import { submitWord } from './form.js';

export function openAuthModal() {
    toggleAuthMode('login');
    openModal('authModal');
}

export function toggleAuthMode(mode) {
    state.currentAuthMode = mode;

    const tabLogin = document.getElementById('tabLogin');
    const tabRegister = document.getElementById('tabRegister');
    const confirmGroup = document.getElementById('confirmPassGroup');
    const subtitle = document.getElementById('authSubtitle');
    const btn = document.getElementById('authSubmitBtn');
    const errorMsg = document.getElementById('authErrorMsg');

    if (errorMsg) errorMsg.style.display = 'none';

    if (mode === 'login') {
        if (tabLogin) tabLogin.classList.add('active');
        if (tabRegister) tabRegister.classList.remove('active');

        if (confirmGroup) confirmGroup.style.display = 'none';
        if (subtitle) subtitle.innerText = "Sözcüklerine adını eklemek ve oy vermek için giriş yap.";
        if (btn) btn.innerText = "Giriş Yap";
    } else {
        if (tabRegister) tabRegister.classList.add('active');
        if (tabLogin) tabLogin.classList.remove('active');

        if (confirmGroup) confirmGroup.style.display = 'block';
        if (subtitle) subtitle.innerText = "Yeni bir hesap oluştur ve aramıza katıl!";
        if (btn) btn.innerText = "Kayıt Ol";
    }
}

export function setupAuthTriggers() {
    // Word submission form — Enter on any field submits
    ['inputWord', 'inputDef', 'inputExample', 'inputEtymology'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    submitWord();
                }
            });
        }
    });

    // Auth modal — Enter on any input submits login/register
    ['authUsername', 'authPassword', 'authPasswordConfirm'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAuthSubmit();
                }
            });
        }
    });

    const authorBtn = document.getElementById('authorTrigger');
    if (authorBtn) {
        authorBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (!isUserLoggedIn) {
                openAuthModal();
            } else {
                openProfileModal(state.currentUserUsername);
            }
        });
    }
}

export function handleAuthSubmit() {
    const u = document.getElementById('authUsername').value.trim();
    const p = document.getElementById('authPassword').value.trim();
    const pConfirm = document.getElementById('authPasswordConfirm').value.trim();
    const t = document.querySelector('[name="cf-turnstile-response"]')?.value;
    const err = document.getElementById('authErrorMsg');
    const btn = document.getElementById('authSubmitBtn');

    if (err) err.style.display = 'none';

    if (!u || !p) {
        if (err) { err.innerText = "Kullanıcı adı ve şifre gerekli."; err.style.display = 'block'; }
        return;
    }

    if (u.length > 30) {
        if (err) { err.innerText = "Kullanıcı adı en fazla 30 karakter olabilir."; err.style.display = 'block'; }
        return;
    }

    if (state.currentAuthMode === 'register') {
        if (p.length < 6) {
            if (err) { err.innerText = "Şifre en az 6 karakter olmalı."; err.style.display = 'block'; }
            return;
        }
        if (p.length > 60) {
            if (err) { err.innerText = "Şifre en fazla 60 karakter olabilir."; err.style.display = 'block'; }
            return;
        }
        if (p !== pConfirm) {
            if (err) { err.innerText = "Şifreler eşleşmiyor."; err.style.display = 'block'; }
            return;
        }
    }

    if (!t) {
        if (err) { err.innerText = "Robot doğrulaması gerekli."; err.style.display = 'block'; }
        return;
    }

    btn.disabled = true;
    btn.innerText = "İşleniyor...";

    const endpoint = state.currentAuthMode === 'login' ? '/api/login' : '/api/register';

    apiRequest(endpoint, 'POST', {
        username: u,
        password: p,
        token: t
    })
    .then(data => {
        closeModal('authModal', true);
        showCustomAlert(data.message, "success");
        setTimeout(() => window.location.reload(), 1000);
    })
    .catch(e => {
        if (err) { err.innerText = e.message; err.style.display = 'block'; }
        if (window.turnstile) window.turnstile.reset();
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerText = state.currentAuthMode === 'login' ? "Giriş Yap" : "Kayıt Ol";
    });
}

export function handleLogout() {
    apiRequest('/api/logout', 'POST').finally(() => window.location.reload());
}
