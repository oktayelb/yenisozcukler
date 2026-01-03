const THEME_KEY = 'userTheme'; 
const COLOR_THEME_KEY = 'userColorTheme'; 
let currentWordId = null; 
let activeCardClone = null;

// Auth durumunu HTML'den oku
let isUserLoggedIn = document.body.getAttribute('data-user-auth') === 'true';

let currentPage = 1;
const ITEMS_PER_PAGE = 20; 
let isLoading = false;

// --- COMMENTS VARIABLES ---
let currentCommentPage = 1;
const COMMENTS_PER_PAGE = 10;
let currentWordCommentsHasNext = false;

document.addEventListener('DOMContentLoaded', () => {
    const mainTitle = document.getElementById('mainTitle');
    const subtitle = document.getElementById('subtitleText');
    if(mainTitle) mainTitle.classList.add('loaded');
    if(subtitle) subtitle.classList.add('loaded');
    
    // --- AUTH TRIGGER LOGIC (GÜNCELLENDİ) ---
    const nickInput = document.getElementById('inputNick');
    const defInput = document.getElementById('inputDef');

    // 1. Durum: Tanım girerken ENTER'a basılırsa -> Anonim Gönder
    if (defInput) {
        defInput.addEventListener('keydown', function(event) {
            // Enter'a basıldıysa VE Shift'e basılmıyorsa (Yeni satır istemiyorsa)
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault(); // Yeni satıra geçmeyi engelle
                submitWord(); // Direkt gönder (Takma ad boş gidecek, backend Anonim yapacak)
            }
        });
    }

    // 2. Durum: Takma Ad'a (TAB ile veya TIKLAYARAK) odaklanılırsa -> Modal Aç
    if (nickInput) {
        nickInput.addEventListener('focus', triggerAuthRequirement);
    }
    // ----------------------------------------

    // --- DARK MODE SETUP ---
    const savedTheme = localStorage.getItem(THEME_KEY);
    const darkModeToggle = document.getElementById('darkModeToggle');

    if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.body.classList.add('dark-mode');
        darkModeToggle.textContent = 'Aydınlık Mod';
    } else {
        darkModeToggle.textContent = 'Karanlık Mod';
    }

    darkModeToggle.addEventListener('click', toggleDarkMode);
    
    // --- LOGO & COLOR THEME SETUP ---
    initLogoSystem();

    fetchWords(currentPage);
});

// --- YENİ ÇIKIŞ FONKSİYONU ---
function handleLogout() {
    fetch('/api/logout', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => {
        // Başarılı olsa da olmasa da sayfayı yenilemek en temizi
        window.location.reload();
    })
    .catch(err => {
        console.error("Çıkış hatası:", err);
        window.location.reload();
    });
}

function toggleDarkMode() {
    const isDarkMode = document.body.classList.toggle('dark-mode');
    const darkModeToggle = document.getElementById('darkModeToggle');
    
    if (isDarkMode) {
        localStorage.setItem(THEME_KEY, 'dark');
        darkModeToggle.textContent = 'Aydınlık Mod';
    } else {
        localStorage.setItem(THEME_KEY, 'light');
        darkModeToggle.textContent = 'Karanlık Mod';
    }
}

function showAboutInfo() {
    const modal = document.getElementById('aboutModal');
    modal.classList.add('show');
    document.body.style.overflow = 'hidden'; 
}

function closeAboutInfo(event, forceClose = false) {
    const modal = document.getElementById('aboutModal');
    if (forceClose || event.target === modal) {
        modal.classList.remove('show');
        document.body.style.overflow = ''; 
    }
}

function updateCount(field) {
    document.getElementById('charCount').innerText = `${field.value.length} / 300`;
}

function allowOnlyLetters(event, allowSpaces) {
    const key = event.key;
    if (event.ctrlKey || event.altKey || event.metaKey || 
        ['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Tab', 'Enter'].includes(key)) {
        return true;
    }
    if (event.ctrlKey && ['a', 'c', 'x', 'v'].includes(key.toLowerCase())) {
        return true;
    }
    
    let regex;
    if (allowSpaces) { 
        regex = /^[a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ\s.,0-9()-]+$/; 
    } else { 
        regex = /^[a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ.,0-9()-]+$/; 
    }
    
    if (regex.test(key)) { return true; } else { event.preventDefault(); return false; }
}

/* --- REUSABLE VOTE SYSTEM LOGIC --- */
function createVoteControls(entityType, data) {
    const container = document.createElement('div');
    container.className = 'vote-container';
    
    const netScore = data.score;
    
    const likeBtn = document.createElement('button');
    likeBtn.className = `vote-btn like ${data.user_vote === 'like' ? 'active' : ''}`;
    likeBtn.innerHTML = `
        <svg viewBox="0 0 24 24"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>
    `;
    likeBtn.onclick = (e) => {
        e.stopPropagation();
        handleVote(entityType, data.id, 'like', container);
    };

    const scoreSpan = document.createElement('span');
    scoreSpan.className = 'vote-score';
    scoreSpan.innerText = netScore;

    const dislikeBtn = document.createElement('button');
    dislikeBtn.className = `vote-btn dislike ${data.user_vote === 'dislike' ? 'active' : ''}`;
    dislikeBtn.innerHTML = `
        <svg viewBox="0 0 24 24"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path></svg>
    `;
    dislikeBtn.onclick = (e) => {
        e.stopPropagation();
        handleVote(entityType, data.id, 'dislike', container);
    };

    container.appendChild(likeBtn);
    container.appendChild(scoreSpan);
    container.appendChild(dislikeBtn);

    return container;
}

async function handleVote(entityType, entityId, action, container) {
    const likeBtn = container.querySelector('.like');
    const dislikeBtn = container.querySelector('.dislike');
    const scoreSpan = container.querySelector('.vote-score');
    
    if (likeBtn.disabled || dislikeBtn.disabled) return;
    likeBtn.disabled = true;
    dislikeBtn.disabled = true;

    const endpoint = `/api/vote/${entityType}/${entityId}`;

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({ action: action })
        });

        if (response.ok) {
            const data = await response.json();
            scoreSpan.innerText = data.new_score;
            
            likeBtn.classList.remove('active');
            dislikeBtn.classList.remove('active');

            if (data.user_action === 'liked') {
                likeBtn.classList.add('active');
            } else if (data.user_action === 'disliked') {
                dislikeBtn.classList.add('active');
            }
        } else {
            const err = await response.json();
            showCustomAlert(err.error || "İşlem başarısız.", "error");
        }
    } catch (error) {
        showCustomAlert("Bağlantı hatası.", "error");
    } finally {
        setTimeout(() => {
            likeBtn.disabled = false;
            dislikeBtn.disabled = false;
        }, 500); 
    }
}

// Global değişkenlerin olduğu en tepeye bunu da ekleyebilirsin (Opsiyonel, aşağıda zaten okuyoruz)
let currentUserUsername = document.body.getAttribute('data-username');

function animateAndOpenCommentView(originalCard, wordId, wordText, wordDef) { 
    if (activeCardClone) return; 
    
    if (originalCard.querySelector('.profane-wrapper')) {
        return;
    }

    const rect = originalCard.getBoundingClientRect();
    const originalContentClone = originalCard.cloneNode(true);
    
    const voteControls = originalContentClone.querySelector('.vote-container');
    if(voteControls) voteControls.remove();
    
    const cleanOriginalHTML = originalContentClone.innerHTML;

    const backdrop = document.getElementById('modalBackdrop');
    backdrop.style.display = 'block';
    requestAnimationFrame(() => { backdrop.classList.add('show'); });
    document.body.style.overflow = 'hidden';

    const clone = document.createElement('div');
    clone.className = 'full-comment-view';
    clone.style.top = rect.top + 'px';
    clone.style.left = rect.left + 'px';
    clone.style.width = rect.width + 'px';
    clone.style.height = rect.height + 'px';
    clone.style.position = 'fixed'; 

    // --- YENİ EKLENEN KISIM: Kullanıcı Durumu ---
    // Eğer giriş yapmışsa username'i al, yapmamışsa boş bırak.
    const currentUsername = document.body.getAttribute('data-username') || '';
    
    const authValue = isUserLoggedIn ? currentUsername : '';
    const authReadOnly = isUserLoggedIn ? 'readonly' : '';
    const authPlaceholder = isUserLoggedIn ? '' : 'Takma Ad (İsteğe bağlı)';
    // ---------------------------------------------

    const fullContentHTML = `
        <div class="drawer-header">
            <div style="flex-grow: 1; padding-right: 15px;">
                <h2 id="commentTitle">${wordText}</h2>
                <div class="comment-subtitle">${wordDef}</div>
            </div>
            <button class="close-btn" onclick="closeCommentView()">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>
        <div class="comment-section">
            <div class="custom-comment-wrapper">
                <div class="custom-comment-header">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                    
                    <input type="text" id="commentAuthor" class="custom-input-minimal" 
                           maxlength="30" 
                           value="${authValue}" 
                           ${authReadOnly}
                           placeholder="${authPlaceholder}">
                </div>
                <textarea id="commentInput" class="custom-textarea-minimal" rows="3" placeholder="Bu sözcük hakkında ne düşünüyorsun?.." maxlength="200" oninput="document.getElementById('liveCharCount').innerText = this.value.length + '/200'"></textarea>
                <div class="custom-comment-footer">
                    <span id="liveCharCount" class="char-counter-minimal">0/200</span>
                    <button class="send-btn-minimal" onclick="submitComment()">
                        Gönder
                        <svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                    </button>
                </div>
            </div>
        </div>
        <div class="comments-list" id="commentsList"></div>
    `;

    clone.innerHTML = `
        <div class="view-layer-placeholder">${cleanOriginalHTML}</div>
        <div class="view-layer-full">${fullContentHTML}</div>
    `;

    document.body.appendChild(clone);
    
    // --- EVENT LISTENERS (YENİ MANTIK) ---
    const commentInput = clone.querySelector('#commentInput');
    const commentAuthor = clone.querySelector('#commentAuthor');

    // 1. Textarea'da Enter'a basılırsa -> Anonim Gönder (Shift+Enter hariç)
    if (commentInput) {
        commentInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submitComment();
            }
        });
        // Modalı açınca direkt yoruma odaklan
        setTimeout(() => commentInput.focus(), 100);
    }

    // 2. Eğer giriş YAPMAMIŞSA: Takma Ad'a tıklayınca/odaklanınca -> Auth Modal Aç
    if (commentAuthor && !isUserLoggedIn) {
        commentAuthor.addEventListener('focus', triggerAuthRequirement);
    }
    // -------------------------------------
    
    activeCardClone = clone;
    originalCard.style.opacity = '0';
    currentWordId = wordId;

    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            clone.classList.add('expanded');
            loadComments(wordId, 1, false);
        });
    });
}

function closeCommentView() {
    if (!activeCardClone) return;
    activeCardClone.classList.remove('expanded');
    const backdrop = document.getElementById('modalBackdrop');
    backdrop.classList.remove('show');

    setTimeout(() => {
        const originalCards = document.querySelectorAll('.word-card');
        const titleElement = activeCardClone.querySelector('#commentTitle');
        const titleText = titleElement ? titleElement.textContent : ''; 

        originalCards.forEach(card => {
            const cardTitle = card.querySelector('.word-title span');
            if (cardTitle && cardTitle.textContent === titleText) {
                card.style.opacity = '1';
            }
        });
        if (activeCardClone) { activeCardClone.remove(); activeCardClone = null; }
        document.body.style.overflow = '';
        backdrop.style.display = 'none';
    }, 500); 
}

function handleCommentEnter(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault(); 
        submitComment(); 
    }
}

function createCommentElement(commentData) {
    const item = document.createElement('div');
    item.className = 'comment-card';
    
    // --- Header ---
    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.justifyContent = 'space-between';
    
    const strong = document.createElement('strong');
    strong.textContent = commentData.author || 'Anonim';
    
    const date = new Date(commentData.timestamp);
    const timeString = date.toLocaleDateString('tr-TR', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    const timeSpan = document.createElement('span');
    timeSpan.style.fontSize = '0.75rem';
    timeSpan.style.color = 'var(--text-muted)';
    timeSpan.textContent = timeString;

    header.appendChild(strong);
    header.appendChild(timeSpan);

    // --- Body ---
    const body = document.createElement('div');
    body.textContent = commentData.comment;
    
    // --- Footer ---
    const footer = document.createElement('div');
    footer.style.display = 'flex';
    footer.style.justifyContent = 'flex-end'; 
    footer.style.marginTop = '4px';

    footer.appendChild(createVoteControls('comment', commentData));

    item.appendChild(header);
    item.appendChild(body);
    item.appendChild(footer);
    
    return item;
}

async function loadComments(wordId, page = 1, append = false) {
    const commentsList = activeCardClone.querySelector('#commentsList');
    
    if (!append) {
        commentsList.innerHTML = `<div class="spinner"></div>`;
        currentCommentPage = 1;
    } else {
        const existingBtn = commentsList.querySelector('.load-more-comments-btn');
        if(existingBtn) existingBtn.textContent = 'Yükleniyor...';
    }

    try {
        const response = await fetch(`/api/comments/${wordId}?page=${page}&limit=${COMMENTS_PER_PAGE}`);
        const data = await response.json();
        
        if (!append) commentsList.innerHTML = ''; 
        else {
             const existingBtn = commentsList.querySelector('.load-more-comments-btn');
             if(existingBtn) existingBtn.remove();
        }
        
        if (data.success && data.comments && data.comments.length > 0) {
            data.comments.forEach(comment => {
                const item = createCommentElement(comment);
                commentsList.appendChild(item); 
            });

            if (data.has_next) {
                currentWordCommentsHasNext = true;
                const loadBtn = document.createElement('button');
                loadBtn.className = 'load-more-comments-btn';
                loadBtn.innerText = 'Daha eski yorumları gör';
                loadBtn.onclick = () => {
                    currentCommentPage++;
                    loadComments(wordId, currentCommentPage, true);
                };
                commentsList.appendChild(loadBtn);
            } else {
                currentWordCommentsHasNext = false;
            }

        } else if (!append) {
            commentsList.innerHTML = `<div style="text-align: center; color: var(--text-muted); margin-top: 20px;">Henüz yorum yok. İlk siz yapın!</div>`;
        }
    } catch (error) {
        console.error(error);
        if(!append) commentsList.innerHTML = `<div style="text-align: center; color: var(--error-color); margin-top: 20px;">Yorumlar yüklenirken bir hata oluştu.</div>`;
    }
}

function submitComment() {
    if (!activeCardClone) return;
    const input = activeCardClone.querySelector('#commentInput');
    const authorInput = activeCardClone.querySelector('#commentAuthor');
    const commentsList = activeCardClone.querySelector('#commentsList');
    
    const commentText = input.value.trim();
    
    // Yazar adı mantığı:
    // 1. Giriş yapmışsa: Input dolu olsa bile Backend override edip username yapacak (Güvenlik).
    // 2. Giriş yapmamışsa: Input boşsa Backend 'Anonim' yapacak.
    let authorNameToSend = authorInput.value.trim();

    if (commentText.length === 0) { showCustomAlert("Lütfen bir yorum yazın.", "error"); return; }
    if (commentText.length > 200) { showCustomAlert("Yorum 200 karakterden uzun olamaz.", "error"); return; }
    
    const submitButton = activeCardClone.querySelector('.send-btn-minimal');
    submitButton.disabled = true;

    fetch('/api/comment', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ 
            word_id: currentWordId, 
            author: authorNameToSend, // Boş giderse backend 'Anonim' yapar
            comment: commentText 
        })
    })
    .then(response => { if (response.status === 429) { return response.json().then(data => { throw new Error(data.error); }); } return response.json(); })
    .then(data => {
        if (data.success) {
            showCustomAlert("Yorum başarıyla eklendi!", "success");
            input.value = '';
            document.getElementById('liveCharCount').innerText = '0/200'; 
            
            // Backend'den dönen veriyi kullanıyoruz (data.comment).
            // Backend, isim boş gittiyse oraya "Anonim" yazıp geri gönderir.
            const newCommentData = {
                ...data.comment,
                likes: 0,
                dislikes: 0,
                is_liked: false,
                is_disliked: false
            };
            
            const newItem = createCommentElement(newCommentData);
            
            // Eğer "Henüz yorum yok" yazısı varsa onu temizle
            if (commentsList.firstElementChild && commentsList.firstElementChild.textContent.includes('Henüz yorum yok')) { 
                commentsList.innerHTML = ''; 
            }
            
            // Yeni yorumu en başa ekle
            commentsList.insertBefore(newItem, commentsList.firstChild);
            
            // Listeyi en üste kaydır (kullanıcı görsün)
            commentsList.scrollTop = 0;

        } else {
            showCustomAlert(data.error || "Yorum eklenirken hata oluştu.", "error"); 
        }
    })
    .catch(error => { showCustomAlert(error.message || "Ağ hatası.", "error"); })
    .finally(() => { submitButton.disabled = false; });
}

function createWordCardElement(item) {
    const card = document.createElement('div');
    card.className = 'word-card fade-in'; 

    const parser = new DOMParser();
    const decode = (str) => { if (!str) return ''; return parser.parseFromString(str, "text/html").documentElement.textContent; };
    
    if (item.is_profane) {
        card.classList.add('is-profane-content'); 

        const profaneOverlay = document.createElement('div');
        profaneOverlay.className = 'profane-wrapper';
        profaneOverlay.innerHTML = `
            <div class="profane-badge">+18</div>
            <div class="profane-warning">Görmek için tıkla</div>
        `;
        
        profaneOverlay.onclick = (e) => {
            e.stopPropagation(); 
            profaneOverlay.style.opacity = '0';
            setTimeout(() => {
                profaneOverlay.remove();
                card.classList.remove('is-profane-content');
            }, 300);
        };
        card.appendChild(profaneOverlay);
    }
    
    card.style.cursor = 'pointer'; 
    card.onclick = () => animateAndOpenCommentView(card, item.id, decode(item.word), decode(item.def));    
    
    const titleDiv = document.createElement('div');
    titleDiv.className = 'word-title';
    
    const wordText = document.createElement('span');
    wordText.textContent = decode(item.word);
    titleDiv.appendChild(wordText);
    
    titleDiv.appendChild(createVoteControls('word', item));

    const defDiv = document.createElement('div');
    defDiv.className = 'word-def';
    defDiv.textContent = decode(item.def);

    card.appendChild(titleDiv);
    card.appendChild(defDiv);

    // --- Footer Section ---
    const footerDiv = document.createElement('div');
    footerDiv.className = 'word-footer';

    const hintSpan = document.createElement('span');
    hintSpan.className = 'click-hint';
    hintSpan.textContent = 'Detaylar & Yorumlar ↴'; 
    footerDiv.appendChild(hintSpan);

    if (item.author) {
        const authSpan = document.createElement('span');
        authSpan.className = 'word-author';
        authSpan.textContent = `— ekleyen ${decode(item.author)}`;
        footerDiv.appendChild(authSpan);
    }

    card.appendChild(footerDiv);
    
    return card;
}

function appendCardsToDOM(words, listElement, prepend = false) {
    const spinner = listElement.querySelector('.spinner');
    if (spinner) { spinner.remove(); }
    
    const loadingMessage = document.getElementById('loadingMessage');
    if (loadingMessage) { loadingMessage.remove(); }
    
    const fragment = document.createDocumentFragment();
    const cardsToAnimate = [];

    words.forEach(item => {
        const card = createWordCardElement(item);
        cardsToAnimate.push(card); 
        fragment.appendChild(card); 
    });

    if (prepend) {
        if (listElement.firstChild) { listElement.insertBefore(fragment, listElement.firstChild); } 
        else { listElement.appendChild(fragment); }
    } else { listElement.appendChild(fragment); }
    
    cardsToAnimate.forEach((card, index) => {
        requestAnimationFrame(() => {
            if (card.classList.contains('fade-in')) {
                const delay = index * 80;
                setTimeout(() => { 
                    card.classList.remove('fade-in'); 
                    card.classList.add('show'); 
                }, delay);
            }
        });
    });
}

async function fetchWords(page) {
    if (isLoading) return;
    isLoading = true;
    
    const list = document.getElementById('feedList');
    const loadMoreContainer = document.getElementById('loadMoreContainer');
    const loadMoreBtn = loadMoreContainer.querySelector('button');
    
    const currentTheme = localStorage.getItem(COLOR_THEME_KEY);
    const mode = currentTheme === 'red' ? 'profane' : 'all';

    if (page === 1) {
        list.innerHTML = `<div class="spinner"></div>`;
        loadMoreContainer.style.display = 'none';
    } else {
        loadMoreBtn.textContent = 'Yükleniyor...';
        loadMoreBtn.disabled = true;
    }

    const url = `/api/words?page=${page}&limit=${ITEMS_PER_PAGE}&mode=${mode}`;
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        if (page === 1) list.innerHTML = '';
        
        if (data.words && data.words.length > 0) {
            appendCardsToDOM(data.words, list, false);
            
            if (data.words.length >= ITEMS_PER_PAGE && (!data.total_count || (page * ITEMS_PER_PAGE < data.total_count))) {
                loadMoreContainer.style.display = 'block';
            } else {
                loadMoreContainer.style.display = 'none';
            }
        } else {
            if (page === 1) {
                list.innerHTML = '<div style="text-align:center; color:#ccc;">Henüz onaylanmış sözcük yok. İlk siz ekleyin!</div>';
            }
            loadMoreContainer.style.display = 'none';
        }
    } catch (e) {
        console.error("Error fetching words", e);
        if (page === 1) {
             list.innerHTML = '<div style="text-align:center; color:#f44336; margin-top:50px;">Sözcükler yüklenemedi. Ağ bağlantınızı kontrol edin.</div>';
        } else {
            showCustomAlert("Daha fazla sözcük yüklenemedi.", "error");
        }
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

function showCustomAlert(message, type = 'success') {
    const container = document.getElementById('notificationContainer');
    const alertDiv = document.createElement('div');
    alertDiv.className = `custom-alert custom-alert-${type}`;
    alertDiv.textContent = message;
    alertDiv.onclick = () => { alertDiv.classList.remove('show'); setTimeout(() => alertDiv.remove(), 500); };
    container.prepend(alertDiv); 
    setTimeout(() => { alertDiv.classList.add('show'); }, 10); 
    setTimeout(() => { alertDiv.classList.remove('show'); setTimeout(() => { alertDiv.remove(); }, 500); }, 4000);
}

function handleWordSubmit(event) {
    event.preventDefault(); 
    submitWord();
}

function getCSRFToken() {
    const name = "csrftoken=";
    const decodedCookie = decodeURIComponent(document.cookie);
    const ca = decodedCookie.split(';');
    for (let i = 0; i < ca.length; i++) {
        let c = ca[i].trim();
        if (c.indexOf(name) === 0) {
            return c.substring(name.length, c.length);
        }
    }
    return null;
}

async function submitWord() {
    const wordInput = document.getElementById('inputWord');
    const defInput = document.getElementById('inputDef');
    const nickInput = document.getElementById('inputNick'); 
    const btn = document.querySelector(".form-card button");

    const word = wordInput.value.trim();
    const definition = defInput.value.trim();
    const author = nickInput.value.trim(); 
    
    const currentTheme = localStorage.getItem(COLOR_THEME_KEY);
    const isProfane = (currentTheme === 'red'); 

    // Basit Validasyonlar
    if (word.length === 0 || definition.length === 0) { 
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
        const response = await fetch('/api/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({ word, definition, nickname: author, is_profane: isProfane })
        });

        // Check content type before parsing
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            const errorText = await response.text(); 
            throw new Error("Server returned non-JSON content: " + contentType);
        }

        const data = await response.json();

        if (response.status === 429) {
            throw new Error(data.error || "Çok fazla deneme yaptınız, lütfen bekleyin.");
        }

        if (response.ok) {
            wordInput.value = ''; 
            defInput.value = ''; 
            if (!isUserLoggedIn) nickInput.value = '';
            
            updateCount({ value: '' }); 
            
            if (isProfane) {
                showCustomAlert("Sözcük (Argo/+18) gönderildi! Moderasyon incelemesinden sonra görünecektir.", "success");
            } else {
                showCustomAlert("Sözcük gönderildi! Moderasyon incelemesinden sonra görünecektir.", "success");
            }
        } else {
            showCustomAlert(data.error || "Sözcük kaydedilirken bir hata oluştu.", "error");
        }
    } catch (error) { 
        showCustomAlert(error.message || "Ağ hatası: Sunucuya ulaşılamadı.", "error"); 
    } finally { 
        btn.disabled = false; 
        btn.innerText = "Sözlüğe Ekle"; 
    }
}

/* --- YENİ LOGO SWAP SİSTEMİ --- */
function initLogoSystem() {
    const savedTheme = localStorage.getItem(COLOR_THEME_KEY) || 'default';
    const cardDefault = document.getElementById('cardDefault');
    const cardRed = document.getElementById('cardRed');

    if (!cardDefault || !cardRed) return;

    document.body.setAttribute('data-theme', savedTheme);

    if (savedTheme === 'red') {
        cardRed.className = 'logo-card theme-red pos-center';
        cardDefault.className = 'logo-card theme-default pos-behind';
    } else {
        cardDefault.className = 'logo-card theme-default pos-center';
        cardRed.className = 'logo-card theme-red pos-behind';
    }
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
        cardRed.classList.remove('pos-behind');
        cardRed.classList.add('pos-center');

        cardDefault.classList.remove('pos-center');
        cardDefault.classList.add('pos-behind');
    } else {
        cardDefault.classList.remove('pos-behind');
        cardDefault.classList.add('pos-center');

        cardRed.classList.remove('pos-center');
        cardRed.classList.add('pos-behind');
    }
}

/* --- AUTH MODAL LOGIC (GÜNCELLENDİ) --- */

function triggerAuthRequirement(event) {
    if (!isUserLoggedIn) {
        event.preventDefault(); 
        event.target.blur();    
        openAuthModal();
    }
}

function openAuthModal() {
    const modal = document.getElementById('authModal');
    if(modal) modal.classList.add('show');
    document.activeElement.blur();
}

function closeAuthModal(event, forceClose = false) {
    const modal = document.getElementById('authModal');
    if (forceClose || event.target === modal) {
        modal.classList.remove('show');
        const errorMsg = document.getElementById('authErrorMsg');
        if(errorMsg) errorMsg.style.display = 'none';
    }
}

// app.js

function handleAuthSubmit() {
    const usernameInput = document.getElementById('authUsername');
    const passwordInput = document.getElementById('authPassword');
    const errorMsg = document.getElementById('authErrorMsg');
    const btn = document.querySelector('.auth-submit-btn');

    const username = usernameInput.value.trim();
    const password = passwordInput.value.trim();

    // Turnstile token'ını al (Widget bu isimde gizli bir input oluşturur)
    const turnstileToken = document.querySelector('[name="cf-turnstile-response"]')?.value;

    if (!username || !password) {
        errorMsg.textContent = "Lütfen tüm alanları doldurun.";
        errorMsg.style.display = 'block';
        return;
    }

    // Token kontrolü
    if (!turnstileToken) {
        errorMsg.textContent = "Lütfen robot olmadığınızı doğrulayın.";
        errorMsg.style.display = 'block';
        return;
    }

    const originalText = btn.innerText;
    btn.innerText = "İşleniyor...";
    btn.disabled = true;
    errorMsg.style.display = 'none';

    fetch('/api/auth', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        // Token'ı da gönderiyoruz
        body: JSON.stringify({ username, password, token: turnstileToken })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showCustomAlert(data.message || "Giriş başarılı!", "success");
            closeAuthModal(null, true);
            setTimeout(() => {
                window.location.reload();
            }, 500);
        } else {
            errorMsg.textContent = data.error || "Bir hata oluştu.";
            errorMsg.style.display = 'block';
            btn.innerText = originalText;
            btn.disabled = false;
            
            // Hata durumunda Turnstile'ı sıfırla (Kullanıcı tekrar çözsün)
            if (window.turnstile) window.turnstile.reset();
        }
    })
    .catch(error => {
        console.error(error);
        errorMsg.textContent = "Sunucu bağlantı hatası.";
        errorMsg.style.display = 'block';
        btn.innerText = originalText;
        btn.disabled = false;
    });
}

/* --- PROFILE MODAL LOGIC --- */

function openProfileModal() {
    const modal = document.getElementById('profileModal');
    if(modal) {
        modal.classList.add('show');
        fetchProfileData(); // Açılır açılmaz verileri çek
    }
}

// app.js


// GÜNCELLENEN FONKSİYON: Kapatırken ayar menüsünü de gizle
function closeProfileModal(event, forceClose = false) {
    const modal = document.getElementById('profileModal');
    if (forceClose || event.target === modal) {
        modal.classList.remove('show');
        
        // Inputları temizle
        document.getElementById('newPassword').value = '';
        const confirmInput = document.getElementById('newPasswordConfirm');
        if(confirmInput) confirmInput.value = '';
        
        // --- YENİ: Ayar menüsünü kapat (Resetle) ---
        const editSection = document.getElementById('editProfileSection');
        if(editSection) editSection.style.display = 'none';
    }
}


async function fetchProfileData() {
    try {
        const response = await fetch('/api/profile', {
            headers: {
                'X-CSRFToken': getCSRFToken()
            }
        });
        const data = await response.json();
        
        if (response.ok) {
            document.getElementById('profileUsername').textContent = data.username;
            document.getElementById('profileDate').textContent = data.date_joined;
            document.getElementById('statWords').textContent = data.word_count;
            document.getElementById('statComments').textContent = data.comment_count;
            document.getElementById('statScore').textContent = data.total_score;
        }
    } catch (error) {
        console.error("Profil verisi çekilemedi:", error);
    }
}

// app.js dosyasının en altındaki ilgili fonksiyonları bununla değiştir:


function handleChangePassword() {
    const newPassInput = document.getElementById('newPassword');
    const confirmPassInput = document.getElementById('newPasswordConfirm'); // Yeni input
    
    const newPass = newPassInput.value.trim();
    const confirmPass = confirmPassInput.value.trim();
    
    const btn = document.querySelector('#profileModal .auth-submit-btn');
    
    // --- VALIDASYONLAR ---
    if (newPass.length < 6) {
        showCustomAlert("Şifre en az 6 karakter olmalıdır.", "error");
        return;
    }

    if (newPass !== confirmPass) {
        showCustomAlert("Şifreler birbiriyle eşleşmiyor.", "error");
        return;
    }
    // ---------------------

    const originalText = btn.innerText;
    btn.innerText = "Güncelleniyor...";
    btn.disabled = true;

    fetch('/api/change-password', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ new_password: newPass })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showCustomAlert(data.message, "success");
            newPassInput.value = '';
            confirmPassInput.value = ''; // Başarılı olunca temizle
        } else {
            showCustomAlert(data.error || "Hata oluştu.", "error");
        }
    })
    .catch(err => {
        showCustomAlert("Sunucu hatası.", "error");
    })
    .finally(() => {
        btn.innerText = originalText;
        btn.disabled = false;
    });
}

// app.js en altına ekle:

function handleChangeUsername() {
    const input = document.getElementById('newUsernameInput');
    const newUsername = input.value.trim();
    const btn = input.nextElementSibling; // Yanındaki buton

    if (!newUsername) return;

    const originalText = btn.innerText;
    btn.innerText = "...";
    btn.disabled = true;

    fetch('/api/change-username', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ new_username: newUsername })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showCustomAlert(data.message, "success");
            // Kullanıcı adı değiştiği için sayfayı yenilemek en sağlıklısıdır
            // (Header, yorumlar vb. her yerin güncellenmesi için)
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showCustomAlert(data.error || "Hata oluştu.", "error");
            btn.innerText = originalText;
            btn.disabled = false;
        }
    })
    .catch(err => {
        showCustomAlert("Sunucu hatası.", "error");
        btn.innerText = originalText;
        btn.disabled = false;
    });
}

// app.js - EN ALT KISIM

// 1. Düzenleme Modalını Aç (Profil modalını kapatır)
function openEditProfileModal() {
    // Önce mevcut profil modalını kapat
    const profileModal = document.getElementById('profileModal');
    profileModal.classList.remove('show');

    // Yeni modalı aç
    const editModal = document.getElementById('editProfileModal');
    editModal.classList.add('show');

    // Kullanıcı adını inputa otomatik doldur (Global değişkenden veya DOM'dan alarak)
    const currentUsername = document.body.getAttribute('data-username');
    const input = document.getElementById('newUsernameInput');
    if(input && currentUsername) input.value = currentUsername;
}

// 2. Düzenleme Modalını Kapat
function closeEditProfileModal(event, forceClose = false) {
    const modal = document.getElementById('editProfileModal');
    if (forceClose || event.target === modal) {
        modal.classList.remove('show');
        // Inputları temizle
        document.getElementById('newPassword').value = '';
        document.getElementById('newPasswordConfirm').value = '';
    }
}

// 3. "Profile Geri Dön" Fonksiyonu
function backToProfile() {
    // Edit'i kapat
    const editModal = document.getElementById('editProfileModal');
    editModal.classList.remove('show');
    
    // Profili geri aç
    openProfileModal();
}