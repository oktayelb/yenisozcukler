const THEME_KEY = 'userTheme'; 
const LIKE_COOLDOWN_MS = 1000; 
const buttonsCooldown = {}; 
let currentWordId = null; 
let activeCardClone = null;

let currentPage = 1;
const ITEMS_PER_PAGE = 20; 
let isLoading = false;

// --- YORUMLAR İÇİN EKLENEN DEĞİŞKENLER ---
let currentCommentPage = 1;
const COMMENTS_PER_PAGE = 10;
let currentWordCommentsHasNext = false;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('mainTitle').classList.add('loaded');
    document.getElementById('subtitleText').classList.add('loaded');
    
    const savedTheme = localStorage.getItem(THEME_KEY);
    const darkModeToggle = document.getElementById('darkModeToggle');

    if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.body.classList.add('dark-mode');
        darkModeToggle.textContent = 'Aydınlık Mod';
    } else {
        darkModeToggle.textContent = 'Karanlık Mod';
    }

    darkModeToggle.addEventListener('click', toggleDarkMode);
    
    fetchWords(currentPage);
});

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
    if (allowSpaces) { regex = /^[a-zA-ZçÇğĞıIİöÖşŞüÜ\s.,0-9]$/; } else { regex = /^[a-zA-ZçÇğĞıIİöÖşŞüÜ.,0-9]$/; }
    if (regex.test(key)) { return true; } else { event.preventDefault(); return false; }
}

function createLikeButton(item) {
    const wordId = item.id;
    const container = document.createElement('div');
    container.className = 'like-container';
    
    const button = document.createElement('button');
    button.className = item.is_liked ? 'like-button liked' : 'like-button';
    button.id = `like-btn-${wordId}`;
    button.onclick = (e) => {
        e.stopPropagation(); 
        likeWord(wordId, button);
    };
    
    button.innerHTML = `
        <svg class="like-icon" width="24" height="24" viewBox="0 0 24 24">
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
        </svg>
    `;
    
    const countSpan = document.createElement('span');
    countSpan.className = 'like-count';
    countSpan.id = `like-count-${wordId}`;
    countSpan.textContent = item.likes || 0;

    container.appendChild(button);
    container.appendChild(countSpan);
    return container;
}

async function likeWord(wordId, button) {
    const now = Date.now();
    const lastClick = buttonsCooldown[wordId] || 0;
    if (now < lastClick) { return; }
    button.disabled = true;
    buttonsCooldown[wordId] = now + LIKE_COOLDOWN_MS; 
    
    try {
        const response = await fetch(`/api/like/${wordId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        if (response.ok) {
            const data = await response.json();
            const countElement = document.getElementById(`like-count-${wordId}`);
            if (countElement) { countElement.textContent = data.new_likes; }
            if (data.action === 'liked') { button.classList.add('liked'); } 
            else if (data.action === 'unliked') { button.classList.remove('liked'); }
        } else {
            const data = await response.json();
            showCustomAlert(data.error || "Oylama başarısız.", "error");
        }
    } catch (error) {
        showCustomAlert("Ağ hatası.", "error");
    } finally {
        setTimeout(() => { button.disabled = false; }, LIKE_COOLDOWN_MS);
    }
}

function animateAndOpenCommentView(originalCard, wordId, wordText, wordDef) { 
    if (activeCardClone) return; 
    
    if (originalCard.querySelector('.profane-wrapper')) {
        return;
    }

    const rect = originalCard.getBoundingClientRect();
    const originalContentClone = originalCard.cloneNode(true);
    const likeBtn = originalContentClone.querySelector('.like-container');
    if(likeBtn) likeBtn.remove();
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
                    <input type="text" id="commentAuthor" class="custom-input-minimal" maxlength="30" placeholder="Takma Adın (İsteğe bağlı)">
                </div>
                <textarea id="commentInput" class="custom-textarea-minimal" rows="3" placeholder="Bu sözcük hakkında ne düşünüyorsun?.." maxlength="200" oninput="document.getElementById('liveCharCount').innerText = this.value.length + '/200'" onkeydown="handleCommentEnter(event)"></textarea>
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
        const titleText = activeCardClone.querySelector('#commentTitle').textContent; 

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
    item.className = 'comment-item';
    
    const date = new Date(commentData.timestamp);
    const timeString = date.toLocaleDateString('tr-TR', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    
    const strong = document.createElement('strong');
    strong.textContent = (commentData.author || 'Anonim') + ':';
    
    const textNode = document.createTextNode(' ' + commentData.comment);
    
    const timeDiv = document.createElement('div');
    timeDiv.style.fontSize = '0.75rem';
    timeDiv.style.color = 'var(--text-muted)';
    timeDiv.style.marginTop = '5px';
    timeDiv.textContent = timeString;
    
    item.appendChild(strong);
    item.appendChild(textNode);
    item.appendChild(timeDiv);
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
    if (commentText.length === 0) { showCustomAlert("Lütfen bir yorum yazın.", "error"); return; }
    if (commentText.length > 200) { showCustomAlert("Yorum 200 karakterden uzun olamaz.", "error"); return; }
    
    const submitButton = activeCardClone.querySelector('.send-btn-minimal');
    submitButton.disabled = true;

    fetch('/api/comment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            word_id: currentWordId, 
            author: authorInput.value, 
            comment: commentText 
        })
    })
    .then(response => { if (response.status === 429) { return response.json().then(data => { throw new Error(data.error); }); } return response.json(); })
    .then(data => {
        if (data.success) {
            showCustomAlert("Yorum başarıyla eklendi!", "success");
            input.value = '';
            document.getElementById('liveCharCount').innerText = '0/200'; 
            
            const newItem = createCommentElement(data.comment);
            
            if (commentsList.firstElementChild && commentsList.firstElementChild.textContent.includes('Henüz yorum yok')) { 
                commentsList.innerHTML = ''; 
            }
            
            commentsList.insertBefore(newItem, commentsList.firstChild);
            
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
    
    titleDiv.appendChild(createLikeButton(item));

    const defDiv = document.createElement('div');
    defDiv.className = 'word-def';
    defDiv.textContent = decode(item.def);

    card.appendChild(titleDiv);
    card.appendChild(defDiv);

    if (item.author) {
        const authDiv = document.createElement('div');
        authDiv.className = 'word-author';
        authDiv.textContent = `— ekleyen ${decode(item.author)}`;
        card.appendChild(authDiv);
    }
    
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
    
    if (page === 1) {
        list.innerHTML = `<div class="spinner"></div>`;
        loadMoreContainer.style.display = 'none';
    } else {
        loadMoreBtn.textContent = 'Yükleniyor...';
        loadMoreBtn.disabled = true;
    }

    const url = `/api/words?page=${page}&limit=${ITEMS_PER_PAGE}`;
    
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

async function submitWord() {
    const wordInput = document.getElementById('inputWord');
    const defInput = document.getElementById('inputDef');
    const nickInput = document.getElementById('inputNick');
    const profaneInput = document.getElementById('inputProfane');
    const btn = document.querySelector(".form-card button");

    const word = wordInput.value.trim();
    const definition = defInput.value.trim();
    const nickname = nickInput.value.trim();
    const isProfane = profaneInput.checked;

    if (word.length === 0 || definition.length === 0) { showCustomAlert("Lütfen Sözcük ve Tanım alanlarını doldurun.", "error"); return; }

    btn.disabled = true;
    btn.innerText = "Kaydediliyor...";

    try {
        const response = await fetch('/api/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ word, definition, nickname, is_profane: isProfane })
        });

        if (response.ok) {
            wordInput.value = ''; defInput.value = ''; nickInput.value = '';
            profaneInput.checked = false; 
            updateCount(defInput);
            showCustomAlert("Sözcük gönderildi! Moderasyon incelemesinden sonra görünecektir.", "success");
            
        } else {
            const data = await response.json();
            showCustomAlert(data.error || "Sözcük kaydedilirken bir hata oluştu.", "error");
        }
    } catch (error) { showCustomAlert("Ağ hatası: Sunucuya ulaşılamadı.", "error"); } 
    finally { btn.disabled = false; btn.innerText = "Sözlüğe Ekle"; }
}