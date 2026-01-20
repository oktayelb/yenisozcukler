/* ========================================
   app.js - Final Version (Dynamic Contribution Text)
   ========================================
*/

/* --- GLOBAL VARIABLES & SETTINGS --- */
const THEME_KEY = 'userTheme'; 
const COLOR_THEME_KEY = 'userColorTheme'; 
const ITEMS_PER_PAGE = 20; 
const COMMENTS_PER_PAGE = 10;

let currentWordId = null; 
let activeCardClone = null; 
let currentPage = 1;
let currentCommentPage = 1;
let isLoading = false;
let currentProfileUser = null; 
let wordIdForExample = null; 

// Auth State
let currentAuthMode = 'login'; // 'login' or 'register'
const isUserLoggedIn = document.body.getAttribute('data-user-auth') === 'true';
const currentUserUsername = document.body.getAttribute('data-username');

/* --- INIT --- */
document.addEventListener('DOMContentLoaded', () => {
    ['mainTitle', 'subtitleText'].forEach(id => {
        const el = document.getElementById(id);
        if(el) el.classList.add('loaded');
    });

    setupAuthTriggers();
    setupTheme();
    initLogoSystem();
    fetchWords(currentPage);
});

/* --- UTILS --- */
function getCSRFToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : null;
}

function showCustomAlert(message, type = 'success') {
    const container = document.getElementById('notificationContainer');
    const alertDiv = document.createElement('div');
    alertDiv.className = `custom-alert custom-alert-${type}`;
    alertDiv.textContent = message;
    alertDiv.onclick = () => alertDiv.remove();
    container.prepend(alertDiv);
    
    setTimeout(() => alertDiv.classList.add('show'), 10);
    setTimeout(() => { 
        alertDiv.classList.remove('show'); 
        setTimeout(() => alertDiv.remove(), 500); 
    }, 4000);
}

async function apiRequest(url, method = 'GET', body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() }
    };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(url, options);
    
    const contentType = response.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
        throw new Error("Sunucu hatası (Invalid JSON).");
    }

    const data = await response.json();
    if (response.status === 429) throw new Error(data.error || "Çok fazla istek gönderdiniz.");
    if (!response.ok) throw new Error(data.error || "İşlem başarısız.");
    return data;
}

function updateCount(field) { 
    const count = field.value.length;
    document.getElementById('charCount').innerText = `${count} / 300`; 
}

/* --- THEME & LOGO --- */
function setupTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    const btn = document.getElementById('darkModeToggle');
    const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (saved === 'dark' || (!saved && sysDark)) {
        document.body.classList.add('dark-mode');
        btn.textContent = 'Aydınlık Mod';
    } else {
        btn.textContent = 'Karanlık Mod';
    }

    btn.addEventListener('click', () => {
        const isDark = document.body.classList.toggle('dark-mode');
        localStorage.setItem(THEME_KEY, isDark ? 'dark' : 'light');
        btn.textContent = isDark ? 'Aydınlık Mod' : 'Karanlık Mod';
    });
}

function initLogoSystem() {
    const theme = localStorage.getItem(COLOR_THEME_KEY) || 'default';
    document.body.setAttribute('data-theme', theme);
    updateLogoVisuals(theme);
}

function animateLogo(el) {
    const curr = localStorage.getItem(COLOR_THEME_KEY) || 'default';
    const next = curr === 'default' ? 'red' : 'default';
    localStorage.setItem(COLOR_THEME_KEY, next);
    document.body.setAttribute('data-theme', next);
    updateLogoVisuals(next);
    currentPage = 1; fetchWords(currentPage);
}

function updateLogoVisuals(theme) {
    const def = document.getElementById('cardDefault');
    const red = document.getElementById('cardRed');
    if (!def || !red) return;
    
    if (theme === 'red') {
        red.className = 'logo-card theme-red pos-center';
        def.className = 'logo-card theme-default pos-behind';
    } else {
        def.className = 'logo-card theme-default pos-center';
        red.className = 'logo-card theme-red pos-behind';
    }
}

/* --- FORM TOGGLE LOGIC (UPDATED) --- */
function toggleContributionForm() {
    const card = document.getElementById('contributionCard');
    const title = document.getElementById('contributionTitle');

    if (card) {
        const isExpanded = card.classList.contains('expanded');
        
        if (isExpanded) {
            // Closing the form
            card.classList.remove('expanded');
            card.classList.add('collapsed');
            
            // Set text back to "Katkıda Bulun" with + icon
            if(title) title.innerHTML = 'Katkıda Bulun <span class="toggle-icon">+</span>';
        } else {
            // Opening the form
            card.classList.remove('collapsed');
            card.classList.add('expanded');
            
            // Set text to "Vazgeç" with - icon
            if(title) title.innerHTML = '';
        }
    }
}


/* --- AUTHENTICATION --- */

function toggleAuthMode(mode) {
    currentAuthMode = mode;
    
    const tabLogin = document.getElementById('tabLogin');
    const tabRegister = document.getElementById('tabRegister');
    const confirmGroup = document.getElementById('confirmPassGroup');
    const subtitle = document.getElementById('authSubtitle');
    const btn = document.getElementById('authSubmitBtn');
    const errorMsg = document.getElementById('authErrorMsg');
    
    if(errorMsg) errorMsg.style.display = 'none';

    if (mode === 'login') {
        if(tabLogin) tabLogin.classList.add('active');
        if(tabRegister) tabRegister.classList.remove('active');
        
        if(confirmGroup) confirmGroup.style.display = 'none';
        if(subtitle) subtitle.innerText = "Hesabına giriş yap ve paylaşmaya başla.";
        if(btn) btn.innerText = "Giriş Yap";
    } else {
        if(tabRegister) tabRegister.classList.add('active');
        if(tabLogin) tabLogin.classList.remove('active');
        
        if(confirmGroup) confirmGroup.style.display = 'block';
        if(subtitle) subtitle.innerText = "Yeni bir hesap oluştur ve aramıza katıl!\n Önceden paylaştığın sözcükleri hesabına tanımlayabilirsin! ";
        if(btn) btn.innerText = "Kayıt Ol";
    }
}

function setupAuthTriggers() {
    const def = document.getElementById('inputDef');
    if (def) {
        def.addEventListener('keydown', (e) => { 
            if (e.key === 'Enter' && !e.shiftKey) { 
                e.preventDefault(); 
                submitWord(); 
            } 
        });
    }

    const authorBtn = document.getElementById('authorTrigger');
    if (authorBtn) {
        authorBtn.addEventListener('click', (e) => {
            e.preventDefault(); 
            if (!isUserLoggedIn) {
                openAuthModal();
            } else {
                openProfileModal(currentUserUsername);
            }
        });
    }
}

function handleAuthSubmit() {
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

    if (currentAuthMode === 'register') {
        if (p.length < 6) {
            if (err) { err.innerText = "Şifre en az 6 karakter olmalı."; err.style.display = 'block'; }
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
    
    const endpoint = currentAuthMode === 'login' ? '/api/login' : '/api/register';

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
        if(window.turnstile) window.turnstile.reset(); 
    })
    .finally(() => { 
        btn.disabled = false; 
        btn.innerText = currentAuthMode === 'login' ? "Giriş Yap" : "Kayıt Ol"; 
    });
}
function handleLogout() { 
    apiRequest('/api/logout', 'POST').finally(() => window.location.reload()); 
}

/* --- MODAL MANAGEMENT --- */
function openModal(id) { 
    const m = document.getElementById(id); 
    if(m) m.classList.add('show'); 
    if(id === 'aboutModal') document.body.style.overflow = 'hidden'; 
}

function closeModal(id, force = false, e = null) {
    const m = document.getElementById(id);
    if(force || (e && e.target === m)) {
        m.classList.remove('show');
        if(id === 'aboutModal') document.body.style.overflow = '';
        if(id === 'authModal') document.getElementById('authErrorMsg').style.display = 'none';
        
        if(id === 'addExampleModal') {
             wordIdForExample = null;
        }
    }
}

function openAuthModal() {
    toggleAuthMode('login');
    openModal('authModal');
}

const closeAuthModal = (e, f) => closeModal('authModal', f, e);
const showAboutInfo = () => openModal('aboutModal'); 
const closeAboutInfo = (e, f) => closeModal('aboutModal', f, e);
const closeProfileModal = (e, f) => closeModal('profileModal', f, e); 
const closeEditProfileModal = (e, f) => closeModal('editProfileModal', f, e);
const closeMyWordsModal = (e, f) => closeModal('myWordsModal', f, e);

/* --- FEED & WORDS --- */
async function fetchWords(page) {
    if (isLoading) return;
    isLoading = true;
    const list = document.getElementById('feedList');
    const loadBtn = document.querySelector('#loadMoreContainer button');
    
    const mode = localStorage.getItem(COLOR_THEME_KEY) === 'red' ? 'profane' : 'all';

    if (page === 1) { 
        list.innerHTML = '<div class="spinner"></div>'; 
        document.getElementById('loadMoreContainer').style.display = 'none'; 
    } else { 
        loadBtn.textContent = 'Yükleniyor...'; 
        loadBtn.disabled = true; 
    }

    try {
        const data = await apiRequest(`/api/words?page=${page}&limit=${ITEMS_PER_PAGE}&mode=${mode}`);
        if(page === 1) list.innerHTML = '';
        
        if (data.words?.length > 0) {
            appendCards(data.words, list, false);
            const hasMore = data.words.length >= ITEMS_PER_PAGE && (!data.total_count || (page * ITEMS_PER_PAGE < data.total_count));
            document.getElementById('loadMoreContainer').style.display = hasMore ? 'block' : 'none';
        } else if(page === 1) {
            list.innerHTML = '<div style="text-align:center;color:#ccc;margin-top:20px;">Henüz içerik yok.</div>';
        }
    } catch (e) {
        if(page === 1) list.innerHTML = '<div style="text-align:center;color:var(--error-color);">Yüklenemedi.</div>';
    } finally {
        isLoading = false; 
        loadBtn.textContent = 'Daha Fazla Göster'; 
        loadBtn.disabled = false;
    }
}

function loadMoreWords() { 
    currentPage++; 
    fetchWords(currentPage); 
}

function appendCards(words, container, isModalMode) {
    const frag = document.createDocumentFragment();
    words.forEach(w => frag.appendChild(createCardElement(w, isModalMode)));
    container.appendChild(frag);
    Array.from(container.children).slice(-words.length).forEach((c, i) => {
        requestAnimationFrame(() => setTimeout(() => { 
            c.classList.remove('fade-in'); 
            c.classList.add('show'); 
        }, i * 50));
    });
}

/* === CARD GENERATION === */
function createCardElement(item, isModalMode) {
    const card = document.createElement('div');
    card.className = 'word-card fade-in';
    card.setAttribute('data-id', item.id);
    
    const parser = new DOMParser();
    const decode = (s) => s ? parser.parseFromString(s, "text/html").documentElement.textContent : '';

    card.onclick = (e) => {
        if (e.target.closest('.vote-btn') || 
            e.target.closest('.user-badge') || 
            e.target.closest('.add-example-btn') || 
            card.classList.contains('is-profane-content')) return;
            
        animateAndOpenCommentView(card, item.id, decode(item.word), decode(item.def), decode(item.example), isModalMode);
    };

    const votePill = createVoteControls('word', item);
    votePill.className = 'vote-container-floating'; 
    card.appendChild(votePill);

    const contentDiv = document.createElement('div');
    const exampleHTML = item.example ? `<div class="word-example">"${decode(item.example)}"</div>` : '';
    contentDiv.innerHTML = `<h3>${decode(item.word)}</h3><p>${decode(item.def)}</p>${exampleHTML}`;
    
    // --- Add Example Button ---
    if (isUserLoggedIn && 
        currentUserUsername === item.author && 
        (!item.example || item.example.trim() === "")) {
        
        const addExBtn = document.createElement('button');
        addExBtn.className = 'add-example-btn';
        addExBtn.innerText = '+ Örnek Ekle';
        addExBtn.onclick = (e) => {
            e.stopPropagation();
            openAddExampleModal(item.id, decode(item.word));
        };
        addExBtn.style.cssText = "background:none; border:1px dashed var(--accent); color:var(--accent); cursor:pointer; font-size:0.75rem; padding:4px 8px; border-radius:4px; margin-top:8px; opacity:0.8;";
        
        contentDiv.appendChild(addExBtn);
    }

    card.appendChild(contentDiv);

    const foot = document.createElement('div'); 
    foot.className = 'word-footer';
    
    const hint = document.createElement('div'); 
    hint.className = 'click-hint'; 
    const cCount = item.comment_count || 0; 
    hint.innerHTML = `Detaylar & Yorumlar (${cCount}) <span>&rarr;</span>`;
    foot.appendChild(hint);

    const authorName = item.author ? decode(item.author) : 'Anonim';
    const authorSpan = document.createElement('div');
    authorSpan.className = 'card-author';
    authorSpan.innerHTML = '';

    if (authorName !== 'Anonim') {
        const badge = document.createElement('span');
        badge.className = 'user-badge';
        badge.innerText = authorName;
        badge.onclick = (e) => {
            e.stopPropagation(); 
            openProfileModal(authorName);
        };
        authorSpan.appendChild(badge);
    } else {
        authorSpan.innerHTML += ' anonim';
    }

    foot.appendChild(authorSpan);
    card.appendChild(foot);

    if (item.is_profane) {
        card.classList.add('is-profane-content');
        const ov = document.createElement('div'); 
        ov.className = 'profane-wrapper';
        ov.innerHTML = `<div class="profane-badge">+18</div><div class="profane-warning">Görmek için tıkla</div>`;
        ov.onclick = (e) => { 
            e.stopPropagation(); e.preventDefault();
            ov.classList.add('hiding'); 
            card.classList.remove('is-profane-content'); 
            setTimeout(() => { if(ov.parentNode) ov.remove(); }, 600);
        };
        card.appendChild(ov);
    }

    return card;
}

/* --- ADD WORD & COMMENT --- */
function handleWordSubmit(e) { e.preventDefault(); submitWord(); }
async function submitWord() {
    const w = document.getElementById('inputWord').value.trim();
    const d = document.getElementById('inputDef').value.trim();
    const ex = document.getElementById('inputExample').value.trim();
    const n = isUserLoggedIn ? currentUserUsername : 'Anonim';

    const btn = document.querySelector(".form-card button");
    const prof = localStorage.getItem(COLOR_THEME_KEY) === 'red';

    if (!w || !d) return showCustomAlert("Lütfen tüm alanları doldurun.", "error");
    if (!ex) return showCustomAlert("Lütfen bir örnek cümle yazın.", "error");
    
    if (d.length > 300) return showCustomAlert("Tanım çok uzun.", "error");
    if (ex.length > 200) return showCustomAlert("Örnek cümle çok uzun.", "error");

    btn.disabled = true; btn.innerText = "Kaydediliyor...";
    try {
        await apiRequest('/api/add', 'POST', { 
            word: w, 
            definition: d, 
            example: ex, 
            nickname: n, 
            is_profane: prof 
        });
        
        document.getElementById('inputWord').value=''; 
        document.getElementById('inputDef').value='';
        document.getElementById('inputExample').value='';
        updateCount({value:''});
        showCustomAlert("Sözcük gönderildi (Onay bekleniyor)!");
        
    } catch (e) { showCustomAlert(e.message, "error"); }
    finally { btn.disabled = false; btn.innerText = "Sözlüğe Ekle"; }
}

/* --- ADD EXAMPLE FEATURE (NEW) --- */
function openAddExampleModal(wordId, wordText) {
    wordIdForExample = wordId;
    
    // Set the word in the header
    const wordDisplay = document.getElementById('exampleModalWord');
    if (wordDisplay) {
        wordDisplay.innerText = wordText ? `"${wordText}"` : '';
    }

    const input = document.getElementById('newExampleInput');
    const count = document.getElementById('exampleCharCount');
    
    // Reset state
    if(input) input.value = '';
    if(count) count.innerText = '0 / 200';
    
    if (input) {
        input.oninput = function() {
            if(count) count.innerText = `${this.value.length} / 200`;
        };
    }

    openModal('addExampleModal');
    setTimeout(() => { if(input) input.focus(); }, 100);
}

async function submitExample() {
    const input = document.getElementById('newExampleInput');
    const btn = document.getElementById('submitExampleBtn');
    const exampleText = input.value.trim();

    if (!exampleText) return showCustomAlert("Lütfen bir cümle yazın.", "error");
    if (exampleText.length > 200) return showCustomAlert("Cümle çok uzun.", "error");

    btn.disabled = true;
    btn.innerText = "Kaydediliyor...";

    try {
        await apiRequest('/api/add-example', 'POST', {
            word_id: wordIdForExample,
            example: exampleText
        });

        showCustomAlert("Örnek cümle başarıyla eklendi!");
        closeModal('addExampleModal');
        
        // Update the UI immediately without reloading
        updateCardWithExample(wordIdForExample, exampleText);
        
    } catch (e) {
        showCustomAlert(e.message, "error");
    } finally {
        btn.disabled = false;
        btn.innerText = "Kaydet";
        wordIdForExample = null;
    }
}

function updateCardWithExample(wordId, text) {
    const card = document.querySelector(`.word-card[data-id="${wordId}"]`);
    if (!card) return;

    const addBtn = card.querySelector('.add-example-btn');
    if (addBtn) addBtn.remove();

    const contentDiv = card.querySelector('div:nth-child(2)'); 
    if (contentDiv) {
        const exampleDiv = document.createElement('div');
        exampleDiv.className = 'word-example';
        exampleDiv.innerText = `"${text}"`;
        contentDiv.appendChild(exampleDiv);
    }
}

/* --- VOTING SYSTEM --- */
function createVoteControls(type, data) {
    const div = document.createElement('div'); div.className = 'vote-container';
    const mkBtn = (act, icon) => {
        const b = document.createElement('button'); 
        b.className=`vote-btn ${act} ${data.user_vote === act ? 'active' : ''}`;
        b.innerHTML=`<svg viewBox="0 0 24 24"><path d="${icon}"></path></svg>`;
        b.onclick = (e) => { e.stopPropagation(); sendVote(type, data.id, act, div); };
        return b;
    };
    div.append(
        mkBtn('like','M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3'), 
        Object.assign(document.createElement('span'), { className: 'vote-score', innerText: data.score }), 
        mkBtn('dislike','M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17')
    );
    return div;
}

async function sendVote(type, id, act, con) {
    const btns = con.querySelectorAll('.vote-btn'); btns.forEach(b => b.disabled = true);
    try {
        const data = await apiRequest(`/api/vote/${type}/${id}`, 'POST', { action: act });
        
        con.querySelector('.vote-score').innerText = data.new_score;
        con.querySelectorAll('.vote-btn').forEach(b => b.classList.remove('active'));
        if(data.user_action && data.user_action !== 'none') {
            const cls = data.user_action === 'liked' ? 'like' : 'dislike';
            con.querySelector(`.${cls}`).classList.add('active');
        }
    } catch (e) { showCustomAlert("Hata oluştu.", "error"); }
    finally { setTimeout(() => btns.forEach(b => b.disabled = false), 300); }
}

/* === DETAIL VIEW & COMMENTS === */
function animateAndOpenCommentView(originalCard, wordId, wordText, wordDef, wordExample, isModalMode = false) { 
    if (activeCardClone) return; 
    if (originalCard.classList.contains('is-profane-content')) return;

    currentWordId = wordId;

    const backdrop = document.getElementById('modalBackdrop');
    backdrop.style.display = 'block';
    requestAnimationFrame(() => backdrop.classList.add('show'));
    
    const clone = document.createElement('div');
    clone.className = 'full-comment-view'; 
    if(isModalMode) clone.classList.add('mode-modal');

    const userValue = isUserLoggedIn ? currentUserUsername : '';
    const readOnlyAttr = isUserLoggedIn ? 'readonly' : '';
    
    const exampleHTML = wordExample ? `<div class="word-example" style="margin-top:8px;">"${wordExample}"</div>` : '';

    const contentHTML = `
        <div class="view-header">
            <div style="display:flex; justify-content:space-between; align-items:start;">
                <div>
                    <h2 id="commentTitle" style="margin:0; font-size:1.4rem; color:var(--accent);">${wordText}</h2>
                    <div style="font-size:1rem; color:var(--text-muted); margin-top:5px; font-style:italic;">${wordDef}</div>
                    ${exampleHTML}
                </div>
                <button class="close-icon-btn" onclick="closeCommentView()">✕</button>
            </div>
        </div>
        <div id="commentsList" class="view-body">
            <div class="spinner"></div>
        </div>
        <div class="view-footer">
            <div class="custom-comment-wrapper">
                <div class="custom-comment-header">
                    <input type="text" id="commentAuthor" class="custom-input-minimal" 
                           placeholder="Takma Adın (İsteğe bağlı)" 
                           value="${userValue}" 
                           ${readOnlyAttr}>
                </div>
                <textarea id="commentInput" class="custom-textarea-minimal" rows="2" placeholder="Yorum yaz..." maxlength="200"></textarea>
                <div class="custom-comment-footer">
                    <button class="send-btn-minimal" onclick="submitComment()">Gönder</button>
                </div>
            </div>
        </div>
    `;

    clone.innerHTML = contentHTML;
    document.body.appendChild(clone);
    requestAnimationFrame(() => requestAnimationFrame(() => clone.classList.add('expanded')));

    activeCardClone = clone;
    loadComments(wordId, 1, false);

    const authorIn = clone.querySelector('#commentAuthor');
    if(authorIn && !isUserLoggedIn) {
        authorIn.addEventListener('click', (e) => { e.preventDefault(); e.target.blur(); openAuthModal(); });
        authorIn.addEventListener('focus', (e) => { e.preventDefault(); e.target.blur(); openAuthModal(); });
    }
}

function closeCommentView() {
    if (!activeCardClone) return;

    const backdrop = document.getElementById('modalBackdrop');
    backdrop.classList.remove('show');
    activeCardClone.classList.remove('expanded');
    
    setTimeout(() => {
        if(activeCardClone) activeCardClone.remove();
        activeCardClone = null;
        backdrop.style.display = 'none';
        currentWordId = null;
    }, 400);
}

async function loadComments(wordId, page = 1) {
    const list = activeCardClone.querySelector('#commentsList');
    if(!list) return;

    if (page === 1) { list.innerHTML = '<div class="spinner"></div>'; currentCommentPage=1; }
    else { const b = list.querySelector('.load-more-comments-btn'); if(b) b.innerText='Yükleniyor...'; }

    try {
        const data = await apiRequest(`/api/comments/${wordId}?page=${page}&limit=${COMMENTS_PER_PAGE}`);
        if(page === 1) list.innerHTML = ''; else list.querySelector('.load-more-comments-btn')?.remove();

        if (data.comments?.length > 0) {
            data.comments.forEach(c => list.appendChild(createCommentItem(c)));
            if (data.has_next) {
                const btn = document.createElement('button');
                btn.className = 'load-more-comments-btn';
                btn.innerText = 'Daha eski yorumlar';
                btn.onclick = () => loadComments(wordId, ++currentCommentPage);
                list.appendChild(btn);
            }
        } else if(page === 1) {
            list.innerHTML = '<div style="text-align:center;color:var(--text-muted);margin-top:20px;">Henüz yorum yok.</div>';
        }
    } catch (e) { if(page === 1) list.innerHTML='<div style="color:var(--error-color);">Hata.</div>'; }
}

function createCommentItem(c) {
    const d = document.createElement('div'); d.className='comment-card';
    const date = new Date(c.timestamp).toLocaleDateString('tr-TR', {day:'numeric', month:'short', hour:'2-digit', minute:'2-digit'});
    
    const authorName = c.author || 'Anonim';
    const head = document.createElement('div');
    head.style.display = 'flex';
    head.style.justifyContent = 'space-between';
    head.style.alignItems = 'center';

    const left = document.createElement('div');
    if (authorName !== 'Anonim') {
        const badge = document.createElement('span');
        badge.className = 'user-badge';
        badge.innerText = authorName;
        badge.onclick = (e) => { e.stopPropagation(); openProfileModal(authorName); };
        left.appendChild(badge);
    } else {
        const b = document.createElement('strong');
        b.innerText = 'Anonim';
        left.appendChild(b);
    }
    
    const right = document.createElement('span');
    right.style.fontSize = '0.75rem';
    right.style.color = 'var(--text-muted)';
    right.innerText = date;

    head.append(left, right);
    d.appendChild(head);

    const body = document.createElement('div');
    body.style.margin = '5px 0';
    body.innerText = c.comment;
    d.appendChild(body);

    const ft = document.createElement('div');
    ft.style.display = 'flex'; ft.style.justifyContent = 'flex-end';
    ft.appendChild(createVoteControls('comment', c));
    d.appendChild(ft);

    return d;
}

function submitComment() {
    if(!activeCardClone) return;
    const txt = activeCardClone.querySelector('#commentInput').value.trim();
    const aut = activeCardClone.querySelector('#commentAuthor').value.trim();
    if(!txt) return showCustomAlert("Yorum yazın.","error");
    if(txt.length > 200) return showCustomAlert("Çok uzun.","error");

    const btn = activeCardClone.querySelector('.send-btn-minimal');
    btn.disabled = true; 

    apiRequest('/api/comment', 'POST', { word_id: currentWordId, author: aut, comment: txt })
    .then(data => {
        showCustomAlert("Yorum eklendi!");
        activeCardClone.querySelector('#commentInput').value='';
        const list = activeCardClone.querySelector('#commentsList');
        if(list.innerText.includes('Henüz yorum')) list.innerHTML='';
        list.insertBefore(createCommentItem({...data.comment, user_vote:null}), list.firstChild);
        list.scrollTop = 0;
    })
    .catch(e => showCustomAlert(e.message, "error"))
    .finally(() => btn.disabled = false);
}

/* --- PROFILE --- */
function openProfileModal(targetUsername = null) {
    if (!targetUsername && isUserLoggedIn) targetUsername = currentUserUsername;
    if (!targetUsername) return; 

    currentProfileUser = targetUsername;
    openModal('profileModal');
    
    const editBtn = document.querySelector('.edit-profile-btn');
    const isOwnProfile = (targetUsername === currentUserUsername);
    if (editBtn) editBtn.style.display = isOwnProfile ? 'flex' : 'none';

    document.getElementById('profileUsername').innerText = targetUsername;
    fetchProfileData(targetUsername); 
}

async function fetchProfileData(username) {
    try {
        const d = await apiRequest(`/api/profile?username=${username}`);
        document.getElementById('profileUsername').innerText = d.username;
        document.getElementById('profileDate').innerText = d.date_joined;
        document.getElementById('statWords').innerText = d.word_count;
        document.getElementById('statComments').innerText = d.comment_count;
        document.getElementById('statScore').innerText = d.total_score;
    } catch (e) { 
        console.error(e); 
        showCustomAlert("Kullanıcı Zimmetlenmemiş", "error");
    }
}

function openMyWordsModal() { 
    closeModal('profileModal', true); 
    openModal('myWordsModal'); 
    fetchMyWordsFeed(); 
}

async function fetchMyWordsFeed() {
    const c = document.getElementById('myWordsFeed'); 
    c.innerHTML = '<div class="spinner"></div>';
    
    let url = '/api/my-words';
    if (currentProfileUser) url += `?username=${currentProfileUser}`;

    const title = document.querySelector('#myWordsModal h2');
    if (title) {
        title.innerText = (currentProfileUser === currentUserUsername) 
            ? "Sözcüklerim" 
            : `${currentProfileUser} adlı kullanıcının sözcükleri`;
    }

    try {
        const d = await apiRequest(url);
        c.innerHTML = '';
        if(d.words?.length > 0) appendCards(d.words, c, false); 
        else c.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted);">Sözcük yok.</div>';
    } catch (e) { c.innerHTML = '<div style="text-align:center;color:var(--error-color);">Hata.</div>'; }
}

function openEditProfileModal(){ 
    closeModal('profileModal', true); 
    openModal('editProfileModal'); 
    if(currentUserUsername) document.getElementById('newUsernameInput').value = currentUserUsername; 
}

function backToProfile(){ 
    closeModal('editProfileModal', true); 
    openModal('profileModal'); 
}

function handleChangePassword(){
    const p1 = document.getElementById('newPassword').value;
    const p2 = document.getElementById('newPasswordConfirm').value;
    if(p1.length < 6 || p1 !== p2) return showCustomAlert("Hatalı veya eşleşmeyen şifre.", "error");
    
    apiRequest('/api/change-password','POST',{new_password: p1})
    .then(() => {
        showCustomAlert("Şifre değişti.");
        document.getElementById('newPassword').value = '';
        document.getElementById('newPasswordConfirm').value = '';
    })
    .catch(e => showCustomAlert(e.message, "error"));
}

function handleChangeUsername(){
    const u = document.getElementById('newUsernameInput').value.trim();
    if(u) apiRequest('/api/change-username','POST',{new_username: u}).then(() => {
        showCustomAlert("Kullanıcı adı değişti."); 
        setTimeout(() => window.location.reload(), 1000);
    }).catch(e => showCustomAlert(e.message, "error"));
}