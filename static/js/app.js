/* --- GLOBAL SABİTLER VE DEĞİŞKENLER --- */
const THEME_KEY = 'userTheme'; 
const COLOR_THEME_KEY = 'userColorTheme'; 
const ITEMS_PER_PAGE = 20; 
const COMMENTS_PER_PAGE = 10;

let currentWordId = null; 
let activeCardClone = null;
let currentPage = 1;
let currentCommentPage = 1;
let isLoading = false;

// Auth durumunu ve Kullanıcı adını HTML'den oku
const isUserLoggedIn = document.body.getAttribute('data-user-auth') === 'true';
const currentUserUsername = document.body.getAttribute('data-username');

/* --- BAŞLANGIÇ (INIT) MANTIĞI --- */
document.addEventListener('DOMContentLoaded', () => {
    // 1. Animasyon Sınıflarını Ekle
    ['mainTitle', 'subtitleText'].forEach(id => {
        const el = document.getElementById(id);
        if(el) el.classList.add('loaded');
    });
    
    // 2. Auth Tetikleyicileri (Anonim Giriş / Login Zorlama)
    setupAuthTriggers();

    // 3. Tema Ayarları (Dark Mode & Renk Teması)
    setupTheme();
    initLogoSystem();

    // 4. İlk İçeriği Çek
    fetchWords(currentPage);
});

/* --- AUTH VE INPUT YÖNETİMİ --- */
function setupAuthTriggers() {
    const nickInput = document.getElementById('inputNick');
    const defInput = document.getElementById('inputDef');

    // Enter'a basınca gönder (Shift+Enter hariç)
    if (defInput) {
        defInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submitWord();
            }
        });
    }

    // Takma ada odaklanınca giriş modalını aç (Sadece çıkış yapmışsa)
    if (nickInput && !isUserLoggedIn) {
        nickInput.addEventListener('focus', (e) => {
            e.preventDefault();
            e.target.blur();
            openModal('authModal');
        });
    }
}

function updateCount(field) {
    document.getElementById('charCount').innerText = `${field.value.length} / 300`;
}

function allowOnlyLetters(event, allowSpaces) {
    const key = event.key;
    // İzin verilen kontrol tuşları
    if (event.ctrlKey || event.altKey || event.metaKey || 
        ['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Tab', 'Enter'].includes(key)) {
        return true;
    }
    // İzin verilen Regex
    const regex = allowSpaces ? /^[a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ\s.,0-9()-]+$/ : /^[a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ.,0-9()-]+$/;
    if (!regex.test(key)) {
        event.preventDefault();
        return false;
    }
    return true;
}

/* --- TEMA YÖNETİMİ --- */
function setupTheme() {
    const savedTheme = localStorage.getItem(THEME_KEY);
    const darkModeToggle = document.getElementById('darkModeToggle');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        document.body.classList.add('dark-mode');
        darkModeToggle.textContent = 'Aydınlık Mod';
    } else {
        darkModeToggle.textContent = 'Karanlık Mod';
    }

    darkModeToggle.addEventListener('click', () => {
        const isDark = document.body.classList.toggle('dark-mode');
        localStorage.setItem(THEME_KEY, isDark ? 'dark' : 'light');
        darkModeToggle.textContent = isDark ? 'Aydınlık Mod' : 'Karanlık Mod';
    });
}

function initLogoSystem() {
    const savedTheme = localStorage.getItem(COLOR_THEME_KEY) || 'default';
    document.body.setAttribute('data-theme', savedTheme);
    updateLogoVisuals(savedTheme);
}

function animateLogo(clickedElement) {
    const currentTheme = localStorage.getItem(COLOR_THEME_KEY) || 'default';
    const newTheme = currentTheme === 'default' ? 'red' : 'default';

    localStorage.setItem(COLOR_THEME_KEY, newTheme);
    document.body.setAttribute('data-theme', newTheme);
    updateLogoVisuals(newTheme);

    currentPage = 1;
    fetchWords(currentPage);
}

function updateLogoVisuals(activeTheme) {
    const cardDefault = document.getElementById('cardDefault');
    const cardRed = document.getElementById('cardRed');
    if (!cardDefault || !cardRed) return;

    if (activeTheme === 'red') {
        setLogoClasses(cardRed, 'pos-center');
        setLogoClasses(cardDefault, 'pos-behind');
    } else {
        setLogoClasses(cardDefault, 'pos-center');
        setLogoClasses(cardRed, 'pos-behind');
    }
}

function setLogoClasses(el, posClass) {
    el.classList.remove('pos-center', 'pos-behind');
    el.classList.add(posClass);
}

/* --- GENEL MODAL YÖNETİMİ --- */
// Tüm modalları açıp kapatmak için tek fonksiyonlar
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if(modal) modal.classList.add('show');
    if(modalId === 'aboutModal') document.body.style.overflow = 'hidden';
}

function closeModal(event, modalId, forceClose = false) {
    const modal = document.getElementById(modalId);
    if (forceClose || (event && event.target === modal)) {
        modal.classList.remove('show');
        if(modalId === 'aboutModal') document.body.style.overflow = '';
        
        // Modal özel temizlik işlemleri
        if(modalId === 'authModal') {
            const errorMsg = document.getElementById('authErrorMsg');
            if(errorMsg) errorMsg.style.display = 'none';
        }
        if(modalId === 'editProfileModal') {
            document.getElementById('newPassword').value = '';
            document.getElementById('newPasswordConfirm').value = '';
        }
    }
}

// HTML onclick'leri için wrapperlar
const closeAuthModal = (e, f) => closeModal(e, 'authModal', f);
const showAboutInfo = () => openModal('aboutModal');
const closeAboutInfo = (e, f) => closeModal(e, 'aboutModal', f);
const closeProfileModal = (e, f) => closeModal(e, 'profileModal', f);
const closeEditProfileModal = (e, f) => closeModal(e, 'editProfileModal', f);
const closeMyWordsModal = (e, f) => closeModal(e, 'myWordsModal', f);

/* --- API YARDIMCILARI --- */
function getCSRFToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : null;
}

function showCustomAlert(message, type = 'success') {
    const container = document.getElementById('notificationContainer');
    const alertDiv = document.createElement('div');
    alertDiv.className = `custom-alert custom-alert-${type}`;
    alertDiv.textContent = message;
    
    // Tıklayınca hemen kapan
    alertDiv.onclick = () => { 
        alertDiv.classList.remove('show'); 
        setTimeout(() => alertDiv.remove(), 300); 
    };
    
    container.prepend(alertDiv); 
    // Animasyon
    setTimeout(() => alertDiv.classList.add('show'), 10); 
    // Otomatik kapan
    setTimeout(() => { 
        alertDiv.classList.remove('show'); 
        setTimeout(() => alertDiv.remove(), 500); 
    }, 4000);
}

async function apiRequest(url, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        }
    };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(url, options);
    const contentType = response.headers.get("content-type");
    
    // JSON olmayan yanıt hatası
    if (!contentType || !contentType.includes("application/json")) {
        throw new Error("Sunucu hatası: Beklenmedik yanıt formatı.");
    }
    
    const data = await response.json();
    
    if (response.status === 429) throw new Error(data.error || "Çok fazla istek.");
    if (!response.ok) throw new Error(data.error || "Bir hata oluştu.");
    
    return data;
}

/* --- KELİME (WORD) İŞLEMLERİ --- */
async function fetchWords(page) {
    if (isLoading) return;
    isLoading = true;
    
    const list = document.getElementById('feedList');
    const loadMoreContainer = document.getElementById('loadMoreContainer');
    const loadMoreBtn = loadMoreContainer.querySelector('button');
    const currentTheme = localStorage.getItem(COLOR_THEME_KEY);
    const mode = currentTheme === 'red' ? 'profane' : 'all';

    // UI Durumu
    if (page === 1) {
        list.innerHTML = `<div class="spinner"></div>`;
        loadMoreContainer.style.display = 'none';
    } else {
        loadMoreBtn.textContent = 'Yükleniyor...';
        loadMoreBtn.disabled = true;
    }

    try {
        const url = `/api/words?page=${page}&limit=${ITEMS_PER_PAGE}&mode=${mode}`;
        const response = await fetch(url); // GET isteği için düz fetch yeterli
        const data = await response.json();
        
        if (page === 1) list.innerHTML = '';
        
        if (data.words && data.words.length > 0) {
            appendCardsToDOM(data.words, list, false);
            
            // Daha fazla butonunu göster/gizle
            const hasMore = data.words.length >= ITEMS_PER_PAGE && 
                          (!data.total_count || (page * ITEMS_PER_PAGE < data.total_count));
            loadMoreContainer.style.display = hasMore ? 'block' : 'none';
        } else {
            if (page === 1) list.innerHTML = '<div style="text-align:center; color:#ccc; margin-top:20px;">Henüz içerik yok.</div>';
            loadMoreContainer.style.display = 'none';
        }
    } catch (e) {
        console.error("Fetch Error:", e);
        if (page === 1) list.innerHTML = '<div style="text-align:center; color:var(--error-color);">Yüklenemedi.</div>';
        else showCustomAlert("Daha fazla yüklenemedi.", "error");
    } finally {
        isLoading = false;
        loadMoreBtn.textContent = 'Daha Fazla Göster';
        loadMoreBtn.disabled = false;
    }
}

function loadMoreWords() {
    currentPage++;
    fetchWords(currentPage);
}

async function submitWord() {
    const wordInput = document.getElementById('inputWord');
    const defInput = document.getElementById('inputDef');
    const nickInput = document.getElementById('inputNick'); 
    const btn = document.querySelector(".form-card button");

    const word = wordInput.value.trim();
    const definition = defInput.value.trim();
    const author = nickInput.value.trim(); 
    const isProfane = (localStorage.getItem(COLOR_THEME_KEY) === 'red'); 

    if (!word || !definition) { 
        showCustomAlert("Lütfen Sözcük ve Tanım alanlarını doldurun.", "error"); 
        return; 
    }
    if (definition.length > 300) {
        showCustomAlert("Tanım 300 karakterden uzun olamaz.", "error");
        return;
    }

    btn.disabled = true;
    btn.innerText = "Kaydediliyor...";

    try {
        await apiRequest('/api/add', 'POST', { 
            word, 
            definition, 
            nickname: author, 
            is_profane: isProfane 
        });

        // Başarılı
        wordInput.value = ''; 
        defInput.value = ''; 
        if (!isUserLoggedIn) nickInput.value = '';
        updateCount({ value: '' }); 
        
        showCustomAlert("Sözcük gönderildi! Moderasyon sonrası görünecektir.", "success");
        
    } catch (error) { 
        showCustomAlert(error.message, "error"); 
    } finally { 
        btn.disabled = false; 
        btn.innerText = "Sözlüğe Ekle"; 
    }
}

function handleWordSubmit(event) {
    event.preventDefault(); 
    submitWord();
}

/* --- KART VE ARAYÜZ OLUŞTURMA (UI) --- */
function createWordCardElement(item, isMini = false) {
    const card = document.createElement('div');
    card.className = 'word-card fade-in';
    card.style.cursor = 'pointer';
    
    // HTML Decode
    const parser = new DOMParser();
    const decode = (str) => str ? parser.parseFromString(str, "text/html").documentElement.textContent : '';
    
    // Profane (Argo) sansür mantığı
    if (item.is_profane) {
        card.classList.add('is-profane-content'); 
        const overlay = document.createElement('div');
        overlay.className = 'profane-wrapper';
        overlay.innerHTML = `<div class="profane-badge">+18</div><div class="profane-warning">Görmek için tıkla</div>`;
        overlay.onclick = (e) => {
            e.stopPropagation(); 
            overlay.remove();
            card.classList.remove('is-profane-content');
        };
        card.appendChild(overlay);
    }
    
    // Tıklayınca Detay Aç
    card.onclick = (e) => {
        if (e.target.closest('.vote-btn')) return; // Oylara tıklayınca açma
        animateAndOpenCommentView(card, item.id, decode(item.word), decode(item.def));    
    };
    
    // İçerik HTML'i
    const dateStr = new Date(item.timestamp).toLocaleDateString('tr-TR');
    
    card.innerHTML += `
        <div class="card-header">
             ${item.author ? `<span class="author-name">@${decode(item.author)}</span>` : ''}
             <span class="card-date">${dateStr}</span>
        </div>
        <div class="card-content">
            <h3>${decode(item.word)}</h3>
            <p>${decode(item.def)}</p>
        </div>
    `;

    // Footer (Oylama ve Hint)
    const footerDiv = document.createElement('div');
    footerDiv.className = 'word-footer';
    
    // Oylama kontrolü (Mini kartlarda oylama kapalı olabilir tercihen)
    footerDiv.appendChild(createVoteControls('word', item));

    const hintSpan = document.createElement('span');
    hintSpan.className = 'click-hint';
    hintSpan.innerHTML = `Detay <span>&rarr;</span>`;
    footerDiv.appendChild(hintSpan);

    card.appendChild(footerDiv);
    return card;
}

function appendCardsToDOM(words, listElement, isMini = false) {
    // Spinner varsa temizle
    const spinner = listElement.querySelector('.spinner');
    if (spinner) spinner.remove();

    const fragment = document.createDocumentFragment();
    const cardsToAnimate = [];

    words.forEach(item => {
        const card = createWordCardElement(item, isMini);
        cardsToAnimate.push(card);
        fragment.appendChild(card);
    });

    listElement.appendChild(fragment);
    
    // Giriş Animasyonu
    cardsToAnimate.forEach((card, index) => {
        requestAnimationFrame(() => {
            setTimeout(() => { 
                card.classList.remove('fade-in'); 
                card.classList.add('show'); 
            }, index * 50);
        });
    });
}

/* --- OYLAMA (VOTE) SİSTEMİ --- */
function createVoteControls(entityType, data) {
    const container = document.createElement('div');
    container.className = 'vote-container';
    
    const createBtn = (cls, iconPath, action) => {
        const btn = document.createElement('button');
        btn.className = `vote-btn ${cls} ${data.user_vote === cls ? 'active' : ''}`;
        btn.innerHTML = `<svg viewBox="0 0 24 24"><path d="${iconPath}"></path></svg>`;
        btn.onclick = (e) => {
            e.stopPropagation();
            handleVote(entityType, data.id, cls, container);
        };
        return btn;
    };

    const likeBtn = createBtn('like', 'M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3');
    const dislikeBtn = createBtn('dislike', 'M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17');
    
    const scoreSpan = document.createElement('span');
    scoreSpan.className = 'vote-score';
    scoreSpan.innerText = data.score;

    container.append(likeBtn, scoreSpan, dislikeBtn);
    return container;
}

async function handleVote(entityType, entityId, action, container) {
    const btns = container.querySelectorAll('.vote-btn');
    btns.forEach(b => b.disabled = true); // Tıklamayı engelle

    try {
        const data = await apiRequest(`/api/vote/${entityType}/${entityId}`, 'POST', { action });
        
        // Skoru güncelle
        container.querySelector('.vote-score').innerText = data.new_score;
        
        // Buton stillerini güncelle
        const likeBtn = container.querySelector('.like');
        const dislikeBtn = container.querySelector('.dislike');
        
        likeBtn.classList.remove('active');
        dislikeBtn.classList.remove('active');
        
        if (data.user_action === 'liked') likeBtn.classList.add('active');
        if (data.user_action === 'disliked') dislikeBtn.classList.add('active');

    } catch (error) {
        showCustomAlert(error.message, "error");
    } finally {
        setTimeout(() => btns.forEach(b => b.disabled = false), 300);
    }
}

/* --- DETAY PENCERESİ (COMMENT VIEW) --- */
function animateAndOpenCommentView(cardElement, wordId, word, def) {
    // Varsa eskisini sil
    closeCommentView();

    const backdrop = document.getElementById('modalBackdrop');
    if(backdrop) {
        backdrop.style.display = 'block';
        backdrop.style.zIndex = '1990';
    }

    // Modal Oluştur
    const container = document.createElement('div');
    container.className = 'comment-view-container'; // CSS class'ı style.css'te olmalı
    // Veya inline stiller (Senin önceki kodundaki gibi, ama CSS class kullanmak daha temizdir)
    Object.assign(container.style, {
        position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%) scale(0.9)',
        width: '90%', maxWidth: '500px', maxHeight: '85vh',
        backgroundColor: 'var(--card-bg)', borderRadius: '12px',
        boxShadow: '0 10px 40px rgba(0,0,0,0.3)', zIndex: '2000',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        opacity: '0', transition: 'all 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)'
    });

    container.innerHTML = `
        <div style="padding:15px 20px; border-bottom:1px solid var(--border-light);">
            <div style="display:flex; justify-content:space-between;">
                <h2 style="margin:0; font-size:1.4rem; color:var(--accent);">${word}</h2>
                <button class="close-icon-btn" onclick="closeCommentView()">✕</button>
            </div>
            <p style="margin:5px 0 0 0; color:var(--text-main); font-size:0.95rem;">${def}</p>
        </div>
        
        <div id="commentsList" style="flex:1; overflow-y:auto; padding:20px;">
            <div class="spinner"></div>
        </div>

        <div style="padding:15px; border-top:1px solid var(--border-light); background:var(--input-bg);">
            <form onsubmit="handleCommentSubmit(event, ${wordId})" style="display:flex; gap:10px;">
                <input type="text" id="commentInput" placeholder="Yorum yaz..." maxlength="200" autocomplete="off"
                       style="flex:1; padding:10px; border-radius:20px; border:1px solid var(--input-border);">
                <button type="submit" class="send-btn-minimal">Gönder</button>
            </form>
        </div>
    `;

    document.body.appendChild(container);
    
    // Aktif kartı takip et
    currentWordId = wordId;
    activeCardClone = container; // Helper fonksiyonlar için ref

    requestAnimationFrame(() => {
        container.style.opacity = '1';
        container.style.transform = 'translate(-50%, -50%) scale(1)';
    });

    loadComments(wordId);
}

function closeCommentView() {
    const container = document.querySelector('.comment-view-container');
    const backdrop = document.getElementById('modalBackdrop');
    
    if(backdrop) backdrop.style.display = 'none';
    if(container) {
        container.style.opacity = '0';
        container.style.transform = 'translate(-50%, -50%) scale(0.9)';
        setTimeout(() => container.remove(), 300);
    }
    currentWordId = null;
    activeCardClone = null;
}

/* --- YORUM (COMMENT) İŞLEMLERİ --- */
async function loadComments(wordId, page = 1, append = false) {
    const list = activeCardClone.querySelector('#commentsList');
    if (!append) {
        list.innerHTML = `<div class="spinner"></div>`;
        currentCommentPage = 1;
    } else {
        const btn = list.querySelector('.load-more-btn');
        if(btn) btn.textContent = 'Yükleniyor...';
    }

    try {
        const response = await fetch(`/api/comments/${wordId}?page=${page}&limit=${COMMENTS_PER_PAGE}`);
        const data = await response.json();
        
        if (!append) list.innerHTML = '';
        else list.querySelector('.load-more-btn')?.remove();

        if (data.success && data.comments.length > 0) {
            data.comments.forEach(c => list.appendChild(createCommentElement(c)));
            
            if (data.has_next) {
                const btn = document.createElement('button');
                btn.className = 'load-more-btn';
                btn.innerText = 'Daha eski yorumlar';
                btn.onclick = () => loadComments(wordId, ++currentCommentPage, true);
                list.appendChild(btn);
            }
        } else if (!append) {
            list.innerHTML = `<div style="text-align:center; color:var(--text-muted);">Henüz yorum yok.</div>`;
        }
    } catch (e) {
        if(!append) list.innerHTML = `<div style="color:var(--error-color);">Yüklenirken hata oluştu.</div>`;
    }
}

function createCommentElement(data) {
    const item = document.createElement('div');
    item.className = 'comment-card';
    
    const dateStr = new Date(data.timestamp).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', hour:'2-digit', minute:'2-digit' });
    
    item.innerHTML = `
        <div style="display:flex; justify-content:space-between;">
            <strong>${data.author || 'Anonim'}</strong>
            <span style="font-size:0.75rem; color:var(--text-muted);">${dateStr}</span>
        </div>
        <div style="margin:5px 0;">${data.comment}</div>
        <div style="display:flex; justify-content:flex-end;"></div>
    `;
    
    item.lastElementChild.appendChild(createVoteControls('comment', data));
    return item;
}

async function handleCommentSubmit(event, wordId) {
    event.preventDefault();
    const input = document.getElementById('commentInput');
    const text = input.value.trim();
    const btn = activeCardClone.querySelector('.send-btn-minimal');

    if (!text) return;
    if (text.length > 200) { showCustomAlert("Yorum çok uzun.", "error"); return; }

    btn.disabled = true;
    try {
        // Backend'de author inputu yoksa Anonim yapıyor zaten
        const data = await apiRequest('/api/comment', 'POST', {
            word_id: wordId,
            comment: text
        });

        showCustomAlert("Yorum eklendi!", "success");
        input.value = '';
        
        // Yeni yorumu ekle
        const list = activeCardClone.querySelector('#commentsList');
        if (list.textContent.includes('Henüz yorum yok')) list.innerHTML = '';
        
        const newComment = { ...data.comment, user_vote: null }; // Yeni yorum oysuz gelir
        list.insertBefore(createCommentElement(newComment), list.firstChild);
        list.scrollTop = 0;

    } catch (error) {
        showCustomAlert(error.message, "error");
    } finally {
        btn.disabled = false;
    }
}

/* --- KULLANICI PROFİL İŞLEMLERİ --- */
function openProfileModal() {
    openModal('profileModal');
    fetchProfileData();
}

async function fetchProfileData() {
    try {
        // CSRF Token'a gerek yok GET isteği için
        const response = await fetch('/api/profile');
        if (response.ok) {
            const data = await response.json();
            document.getElementById('profileUsername').textContent = data.username;
            document.getElementById('profileDate').textContent = data.date_joined;
            document.getElementById('statWords').textContent = data.word_count;
            document.getElementById('statComments').textContent = data.comment_count;
            document.getElementById('statScore').textContent = data.total_score;
        }
    } catch (e) { console.error(e); }
}

/* --- SÖZCÜKLERİM (MY WORDS) MODALI --- */
function openMyWordsModal() {
    closeProfileModal(null, true); // Profili kapat
    openModal('myWordsModal'); // Yenisini aç
    fetchMyWordsFeed();
}

async function fetchMyWordsFeed() {
    const container = document.getElementById('myWordsFeed');
    container.innerHTML = '<div class="spinner" style="margin:20px auto;"></div>';

    try {
        const response = await fetch('/api/my-words');
        const data = await response.json();

        if (data.success && data.words.length > 0) {
            container.innerHTML = '';
            // appendCardsToDOM fonksiyonunu burada da kullanabiliriz (DRY Prensibi)
            // Sadece container'ı veriyoruz
            appendCardsToDOM(data.words, container, false);
        } else {
            container.innerHTML = `
                <div style="text-align:center; padding:30px; color:var(--text-muted);">
                    Henüz yayımlanmış sözcüğün yok.
                </div>`;
        }
    } catch (e) {
        container.innerHTML = '<div style="text-align:center; color:var(--error-color);">Hata oluştu.</div>';
    }
}

/* --- PROFİL DÜZENLEME (EDIT PROFILE) --- */
function openEditProfileModal() {
    closeProfileModal(null, true);
    openModal('editProfileModal');
    
    // Mevcut kullanıcı adını inputa koy
    const input = document.getElementById('newUsernameInput');
    if(input && currentUserUsername) input.value = currentUserUsername;
}

function backToProfile() {
    closeEditProfileModal(null, true);
    openProfileModal();
}

// Şifre Değiştir
function handleChangePassword() {
    const p1 = document.getElementById('newPassword').value;
    const p2 = document.getElementById('newPasswordConfirm').value;
    
    if (p1.length < 6) return showCustomAlert("Şifre en az 6 karakter olmalı.", "error");
    if (p1 !== p2) return showCustomAlert("Şifreler eşleşmiyor.", "error");

    performAuthAction('/api/change-password', { new_password: p1 }, "Şifre güncellendi.");
}

// Kullanıcı Adı Değiştir
function handleChangeUsername() {
    const newName = document.getElementById('newUsernameInput').value.trim();
    if (!newName) return;

    performAuthAction('/api/change-username', { new_username: newName }, "Kullanıcı adı güncellendi.", true);
}

async function performAuthAction(url, body, successMsg, reload = false) {
    try {
        await apiRequest(url, 'POST', body);
        showCustomAlert(successMsg, "success");
        if (reload) setTimeout(() => window.location.reload(), 1000);
    } catch (e) {
        showCustomAlert(e.message, "error");
    }
}

/* --- AUTH (LOGIN/REGISTER) İŞLEMLERİ --- */
function handleAuthSubmit() {
    const u = document.getElementById('authUsername').value.trim();
    const p = document.getElementById('authPassword').value.trim();
    const token = document.querySelector('[name="cf-turnstile-response"]')?.value;
    const errorMsg = document.getElementById('authErrorMsg');

    if (!u || !p) {
        errorMsg.style.display = 'block';
        errorMsg.textContent = "Alanları doldurun.";
        return;
    }
    if (!token) {
        errorMsg.style.display = 'block';
        errorMsg.textContent = "Doğrulamayı tamamlayın.";
        return;
    }

    const btn = document.querySelector('.auth-submit-btn');
    const orgText = btn.innerText;
    btn.disabled = true; btn.innerText = "İşleniyor...";

    fetch('/api/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() },
        body: JSON.stringify({ username: u, password: p, token })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            closeModal(null, 'authModal', true);
            showCustomAlert(data.message, "success");
            setTimeout(() => window.location.reload(), 500);
        } else {
            errorMsg.style.display = 'block';
            errorMsg.textContent = data.error;
            if (window.turnstile) window.turnstile.reset();
        }
    })
    .catch(() => showCustomAlert("Bağlantı hatası.", "error"))
    .finally(() => {
        btn.disabled = false; btn.innerText = orgText;
    });
}

function handleLogout() {
    fetch('/api/logout', { method: 'POST', headers: {'X-CSRFToken': getCSRFToken()} })
    .finally(() => window.location.reload());
}