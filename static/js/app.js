/* ========================================
   app.js - Final Version
   ========================================
*/

/* --- GLOBAL VARIABLES & SETTINGS --- */
const THEME_KEY = 'userTheme'; 
const ITEMS_PER_PAGE = 20; 
const COMMENTS_PER_PAGE = 10;

let currentWordId = null; 
let activeCardClone = null; 
let currentPage = 1;
let currentCommentPage = 1;
let isLoading = false;
let currentProfileUser = null; 
let wordIdForExample = null; 
let currentSearchQuery = '';

// --- CATEGORY VARIABLES ---
let activeCategorySlug = null; // Current filter
let allCategories = [];        // Loaded from API
let selectedFormCategories = new Set(); // For submission

// Sorting
let currentSort = 'date_desc'; // 'date_desc', 'date_asc', 'score_desc', 'score_asc'

// Auth State
let currentAuthMode = 'login'; // 'login' or 'register'
const isUserLoggedIn = document.body.getAttribute('data-user-auth') === 'true';
let currentUserUsername = document.body.getAttribute('data-username');

/* --- INIT --- */
document.addEventListener('DOMContentLoaded', () => {
    ['mainTitle', 'subtitleText'].forEach(id => {
        const el = document.getElementById(id);
        if(el) el.classList.add('loaded');
    });

    setupAllEventListeners();

    setupAuthTriggers();
    setupSortBar();
    setupTheme();
    initTopAppBar();
    fetchCategories(); 
    fetchWords(currentPage);
});

/* --- ALL EXTRACTED EVENT BINDINGS --- */
function setupAllEventListeners() {
    // Backdrop / Overlays
    document.getElementById('modalBackdrop')?.addEventListener('click', closeCommentView);
    
    // About Modal
    document.getElementById('aboutModal')?.addEventListener('click', closeAboutInfo);
    document.getElementById('aboutCloseBtn')?.addEventListener('click', (e) => closeAboutInfo(e, true));
    document.getElementById('headerAboutBtn')?.addEventListener('click', showAboutInfo);
    
    // Auth Modal
    document.getElementById('authModal')?.addEventListener('click', closeAuthModal);
    document.getElementById('authCloseBtn')?.addEventListener('click', (e) => closeAuthModal(e, true));
    document.getElementById('tabLogin')?.addEventListener('click', () => toggleAuthMode('login'));
    document.getElementById('tabRegister')?.addEventListener('click', () => toggleAuthMode('register'));
    document.getElementById('authSubmitBtn')?.addEventListener('click', handleAuthSubmit);
    
    // Shared Triggers
    document.querySelectorAll('.auth-login-trigger').forEach(btn => {
        btn.addEventListener('click', () => openModal('authModal'));
    });
    document.querySelectorAll('.auth-profile-trigger').forEach(btn => {
        btn.addEventListener('click', () => openProfileModal(currentUserUsername));
    });

    // Header / Form actions
    document.getElementById('topAddWordBtn')?.addEventListener('click', focusContributionForm);
    document.getElementById('formCollapseBtn')?.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleContributionForm();
    });
    document.getElementById('formHeaderToggle')?.addEventListener('click', toggleContributionForm);
    document.getElementById('contributionForm')?.addEventListener('submit', handleWordSubmit);
    document.getElementById('contributionCard')?.addEventListener('click', function() {
        if (this.classList.contains('collapsed')) toggleContributionForm();
    });

    // Form Interactions / Validations
    const inputWord = document.getElementById('inputWord');
    if (inputWord) {
        inputWord.addEventListener('input', function() { this.value = this.value.replace(/^\s+/g, ''); });
        inputWord.addEventListener('keypress', (e) => {
            if (typeof allowOnlyLetters === 'function' && !allowOnlyLetters(e, true)) e.preventDefault();
        });
    }

    const inputDef = document.getElementById('inputDef');
    if (inputDef) {
        inputDef.addEventListener('input', function() { updateCount(this); });
        inputDef.addEventListener('keypress', (e) => {
            if (typeof allowOnlyLetters === 'function' && !allowOnlyLetters(e, true)) e.preventDefault();
        });
    }

    const inputExample = document.getElementById('inputExample');
    if (inputExample) {
        inputExample.addEventListener('keypress', (e) => {
            if (typeof allowOnlyLetters === 'function' && !allowOnlyLetters(e, true)) e.preventDefault();
        });
    }

    // Filter, Feed and Search logic
    document.getElementById('clearFilterBtn')?.addEventListener('click', clearCategoryFilter);
    document.getElementById('loadMoreBtn')?.addEventListener('click', loadMoreWords);

    const searchInput = document.getElementById('mainSearchInput');
    const clearSearchBtn = document.getElementById('clearSearchBtn');

    if (searchInput) {
        let searchTimeout = null;
        searchInput.addEventListener('input', (e) => {
            const val = e.target.value;
            if (val.length > 0) {
                if (clearSearchBtn) clearSearchBtn.style.display = 'block';
            } else {
                if (clearSearchBtn) clearSearchBtn.style.display = 'none';
            }
            
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                executeSearch(val);
            }, 500); 
        });
        
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(searchTimeout);
                executeSearch(searchInput.value);
            }
        });
    }

    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            if(searchInput) searchInput.value = '';
            clearSearchBtn.style.display = 'none';
            executeSearch('');
        });
    }

    // Add Example Modal
    document.getElementById('addExampleModal')?.addEventListener('click', (e) => closeModal('addExampleModal', false, e));
    document.getElementById('addExampleCloseBtn')?.addEventListener('click', () => closeModal('addExampleModal', true));
    document.getElementById('submitExampleBtn')?.addEventListener('click', submitExample);

    // Profile Modal
    document.getElementById('profileModal')?.addEventListener('click', closeProfileModal);
    document.getElementById('profileCloseBtn')?.addEventListener('click', (e) => closeProfileModal(e, true));
    document.getElementById('myWordsStatBtn')?.addEventListener('click', openMyWordsModal);
    document.getElementById('editProfileBtn')?.addEventListener('click', openEditProfileModal);
    document.getElementById('logoutBtn')?.addEventListener('click', handleLogout);

    // My Words Modal
    document.getElementById('myWordsModal')?.addEventListener('click', closeMyWordsModal);
    document.getElementById('myWordsCloseBtn')?.addEventListener('click', (e) => closeMyWordsModal(e, true));
    document.getElementById('myWordsProfileBtn')?.addEventListener('click', () => {
        openProfileModal();
        document.getElementById('myWordsModal').classList.remove('show');
    });

    // Edit Profile Modal
    document.getElementById('editProfileModal')?.addEventListener('click', closeEditProfileModal);
    document.getElementById('editProfileCloseBtn')?.addEventListener('click', (e) => closeEditProfileModal(e, true));
    document.getElementById('saveUsernameBtn')?.addEventListener('click', handleChangeUsername);
    document.getElementById('savePasswordBtn')?.addEventListener('click', handleChangePassword);
    document.getElementById('backToProfileBtn')?.addEventListener('click', backToProfile);
}

function executeSearch(query) {
    const trimmed = query.trim();
    if (currentSearchQuery === trimmed) return;
    currentSearchQuery = trimmed;
    currentPage = 1;
    fetchWords(currentPage);
}

function focusContributionForm() {
    const card = document.getElementById('contributionCard');
    if (!card) return;

    if (!card.classList.contains('expanded')) {
        toggleContributionForm();
    }

    card.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* --- UTILS --- */

// HTML Escaping Utility to prevent DOM-based XSS
function escapeHTML(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function getCSRFToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : null;
}

function showCustomAlert(message, type = 'success') {
    const container = document.getElementById('notificationContainer');
    const alertDiv = document.createElement('div');
    alertDiv.className = `custom-alert custom-alert-${type}`;
    alertDiv.textContent = message; // Safely assign text content
    alertDiv.addEventListener('click', () => alertDiv.remove());
    container.prepend(alertDiv);
    
    setTimeout(() => alertDiv.classList.add('show'), 10);
    setTimeout(() => { 
        alertDiv.classList.remove('show'); 
        setTimeout(() => alertDiv.remove(), 500); 
    }, 4000);
}

async function apiRequest(url, method = 'GET', body = null) {
    const headers = { 'Content-Type': 'application/json' };
    const csrfToken = getCSRFToken();
    
    // Only attach token if it exists to prevent malformed headers
    if (csrfToken) {
        headers['X-CSRFToken'] = csrfToken;
    }

    const options = { method, headers };
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

/* --- THEME --- */
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

/* --- SORTING --- */
function setupSortBar() {
    const bars = document.querySelectorAll('.sort-bar');
    if (!bars.length) return;

    bars.forEach(bar => {
        bar.style.cursor = 'pointer'; 
        
        bar.addEventListener('click', (e) => {
            if (!e.target.closest('.sort-btn')) {
                bar.classList.toggle('collapsed');
            }
        });

        const buttons = bar.querySelectorAll('.sort-btn');
        buttons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation(); 
                const sortVal = btn.getAttribute('data-sort');
                changeSort(sortVal);
                
                bar.classList.add('collapsed');
            });
        });
    });

    updateSortButtonsActive();
}

function changeSort(sortVal) {
    if (!sortVal || sortVal === currentSort) return;

    currentSort = sortVal;
    updateSortButtonsActive();

    currentPage = 1;
    fetchWords(currentPage);
}

function updateSortButtonsActive() {
    const buttons = document.querySelectorAll('.sort-btn');
    buttons.forEach(btn => {
        const sortVal = btn.getAttribute('data-sort');
        if (sortVal === currentSort) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

/* --- FORM TOGGLE LOGIC --- */
function toggleContributionForm() {
    const card = document.getElementById('contributionCard');
    const title = document.getElementById('contributionTitle');

    if (card) {
        const isExpanded = card.classList.contains('expanded');
        
        if (isExpanded) {
            card.classList.remove('expanded');
            card.classList.add('collapsed');
            if(title) title.innerHTML = 'Katkıda Bulun <span class="toggle-icon">+</span>'; // Static HTML, safe
        } else {
            card.classList.remove('collapsed');
            card.classList.add('expanded');
            if(title) title.innerHTML = '';
        }
    }
}

function initTopAppBar() {
    const bar = document.getElementById('topAppBar');
    if (!bar) return;

    const onScroll = () => {
        if (window.scrollY > 150) {
            bar.classList.add('is-visible');
        } else {
            bar.classList.remove('is-visible');
        }
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
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
        if(subtitle) subtitle.innerText = "Sözcüklerine adını eklemek ve oy vermek için giriş yap.";
        if(btn) btn.innerText = "Giriş Yap";
    } else {
        if(tabRegister) tabRegister.classList.add('active');
        if(tabLogin) tabLogin.classList.remove('active');
        
        if(confirmGroup) confirmGroup.style.display = 'block';
        if(subtitle) subtitle.innerText = "Yeni bir hesap oluştur ve aramıza katıl!";
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

    if (u.length > 30) {
        if (err) { err.innerText = "Kullanıcı adı en fazla 30 karakter olabilir."; err.style.display = 'block'; }
        return;
    }

    if (currentAuthMode === 'register') {
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

/* --- CATEGORIES & HASHTAGS --- */

async function fetchCategories() {
    try {
        const data = await apiRequest('/api/categories');
        if(data.success) {
            allCategories = data.categories || [];
            renderCategorySelection();
        }
    } catch (e) {
        console.error("Failed to load categories:", e);
    }
}

function renderCategorySelection() {
    const container = document.getElementById('categoryPillsList');
    const wrapper = document.getElementById('categorySelectionContainer');
    
    if (!allCategories.length) {
        if(wrapper) wrapper.style.display = 'none';
        return;
    }
    
    if(wrapper) wrapper.style.display = 'block';
    container.innerHTML = '';
    
    allCategories.forEach(cat => {
        const pill = document.createElement('div');
        pill.className = 'category-pill';
        pill.textContent = cat.name;
        
        const desc = cat.description || ""; 
        
        if (desc) pill.setAttribute('data-desc', desc);
        
        pill.addEventListener('click', () => toggleCategorySelection(cat.id, pill, desc));
        container.appendChild(pill);
    });
}

function toggleCategorySelection(id, el, description) {
    if (selectedFormCategories.has(id)) {
        selectedFormCategories.delete(id);
        el.classList.remove('selected');
    } else {
        selectedFormCategories.add(id);
        el.classList.add('selected');
    }

    const helpText = document.getElementById('categoryHelpText');
    if (helpText) {
        if (description) {
             helpText.innerHTML = ''; // Clear contents safely
             const strongNode = document.createElement('strong');
             strongNode.textContent = `${el.textContent}: `;
             helpText.appendChild(strongNode);
             helpText.appendChild(document.createTextNode(description));
             helpText.classList.add('active');
        } else {
             helpText.textContent = '';
             helpText.classList.remove('active');
        }
    }
}

/* --- FEED & WORDS --- */

async function fetchWords(page) {
    if (isLoading) return;
    isLoading = true;
    const list = document.getElementById('feedList');
    const loadBtn = document.querySelector('#loadMoreContainer button');
    
    let url = `/api/words?page=${page}&limit=${ITEMS_PER_PAGE}&sort=${encodeURIComponent(currentSort)}`;
    if (activeCategorySlug) {
        url += `&tag=${activeCategorySlug}`;
    }
    if (currentSearchQuery) {
        url += `&search=${encodeURIComponent(currentSearchQuery)}`;
    }

    if (page === 1) { 
        list.innerHTML = '<div class="spinner"></div>'; 
        document.getElementById('loadMoreContainer').style.display = 'none'; 
    } else { 
        loadBtn.textContent = 'Yükleniyor...'; 
        loadBtn.disabled = true; 
    }

    try {
        const data = await apiRequest(url);
        if(page === 1) list.innerHTML = '';
        
        if (data.words?.length > 0) {
            appendCards(data.words, list, false);
            const hasMore = data.words.length >= ITEMS_PER_PAGE && (!data.total_count || (page * ITEMS_PER_PAGE < data.total_count));
            document.getElementById('loadMoreContainer').style.display = hasMore ? 'block' : 'none';
        } else if(page === 1) {
            if(currentSearchQuery) {
                // Safely render the search query without innerHTML
                list.innerHTML = '';
                const noResultMsg = document.createElement('div');
                noResultMsg.style.cssText = 'text-align:center;color:#ccc;margin-top:20px;';
                noResultMsg.textContent = `"${currentSearchQuery}" için sonuç bulunamadı.`;
                list.appendChild(noResultMsg);
            } else {
                list.innerHTML = '<div style="text-align:center;color:#ccc;margin-top:20px;">Henüz içerik yok.</div>';
            }
        }
    } catch (e) {
        if(page === 1) list.innerHTML = '<div style="text-align:center;color:var(--error-color);">Yüklenemedi.</div>';
    } finally {
        isLoading = false; 
        loadBtn.textContent = 'Daha Fazla Göster'; 
        loadBtn.disabled = false;
    }
}

function handleTagClick(slug, name, description) {
    activeCategorySlug = slug;
    currentPage = 1;
    
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    updateFilterBanner(true, name, description);
    
    fetchWords(currentPage);
}

function clearCategoryFilter() {
    activeCategorySlug = null;
    currentPage = 1;
    updateFilterBanner(false);
    fetchWords(currentPage);
}

function updateFilterBanner(show, name = '', description = '') {
    const banner = document.getElementById('activeFilterBanner');
    const nameDisplay = document.getElementById('filterNameDisplay');
    const descDisplay = document.getElementById('filterDescDisplay');
    
    if (banner) {
        banner.style.display = show ? 'flex' : 'none';
        
        if (show) {
            if(nameDisplay) nameDisplay.innerText = name;
            
            if(descDisplay) {
                if(description) {
                    descDisplay.innerText = description;
                    descDisplay.style.display = 'block';
                } else {
                    descDisplay.style.display = 'none';
                }
            }
        }
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
        setTimeout(() => {
            c.classList.remove('fade-in');
            c.classList.add('show');
        }, i * 40);
    });
}

/* === CARD GENERATION === */
function createCardElement(item, isModalMode) {
    const card = document.createElement('div');
    card.className = 'word-card fade-in';
    card.setAttribute('data-id', item.id);

    card.addEventListener('click', (e) => {
        if (e.target.closest('.vote-btn') || 
            e.target.closest('.vote-container-floating') || 
            e.target.closest('.user-badge') || 
            e.target.closest('.add-example-btn') || 
            e.target.closest('.tag-badge')) return;
            
        animateAndOpenCommentView(card, item.id, item.word, item.def || item.definition, item.example, item.etymology, isModalMode);
    });

    const votePill = createVoteControls('word', item);
    votePill.className = 'vote-container-floating'; 
    card.appendChild(votePill);

    // Build the DOM safely using Node creation instead of innerHTML
    const contentDiv = document.createElement('div');
    
    const wordTitle = document.createElement('h3');
    wordTitle.textContent = item.word;
    contentDiv.appendChild(wordTitle);

    if (item.etymology) {
        const etyDiv = document.createElement('div');
        etyDiv.className = 'word-etymology';
        etyDiv.style.cssText = 'font-size:0.85rem; color:var(--text-muted); margin-bottom:8px;';
        etyDiv.innerHTML = '<em>Köken:</em> '; // Safe static HTML
        etyDiv.appendChild(document.createTextNode(item.etymology)); // Safe dynamic content
        contentDiv.appendChild(etyDiv);
    }

    const defP = document.createElement('p');
    defP.textContent = item.def || item.definition;
    contentDiv.appendChild(defP);

    if (item.example) {
        const exampleDiv = document.createElement('div');
        exampleDiv.className = 'word-example';
        exampleDiv.textContent = `"${item.example}"`;
        contentDiv.appendChild(exampleDiv);
    }
    
    if (isUserLoggedIn && 
        currentUserUsername === item.author && 
        (!item.example || item.example.trim() === "")) {
        
        const addExBtn = document.createElement('button');
        addExBtn.className = 'add-example-btn';
        addExBtn.innerText = '+ Örnek Ekle';
        addExBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            openAddExampleModal(item.id, item.word);
        });
        addExBtn.style.cssText = "background:none; border:1px dashed var(--accent); color:var(--accent); cursor:pointer; font-size:0.75rem; padding:4px 8px; border-radius:4px; margin-top:8px; opacity:0.8;";
        
        contentDiv.appendChild(addExBtn);
    }

    card.appendChild(contentDiv);

    if (item.categories && item.categories.length > 0) {
        const tagsDiv = document.createElement('div');
        tagsDiv.className = 'tag-list';
        
        item.categories.forEach(cat => {
            const tag = document.createElement('span');
            tag.className = 'tag-badge';
            tag.innerText = cat.name;
            
            if(cat.description) {
                tag.setAttribute('data-desc', cat.description);
            }
            
            tag.addEventListener('click', (e) => {
                e.stopPropagation();
                handleTagClick(cat.slug, cat.name, cat.description);
            });
            tagsDiv.appendChild(tag);
        });
        
        card.appendChild(tagsDiv);
    }

    const foot = document.createElement('div'); 
    foot.className = 'word-footer';
    
    const hint = document.createElement('div'); 
    hint.className = 'click-hint'; 
    const cCount = Number(item.comment_count) || 0; 
    hint.innerHTML = `Yorumlar (${cCount}) <span>&rarr;</span>`;
    foot.appendChild(hint);

    const authorName = item.author ? item.author : 'Anonim';
    const authorSpan = document.createElement('div');
    authorSpan.className = 'card-author';

    if (authorName !== 'Anonim') {
        const badge = document.createElement('span');
        badge.className = 'user-badge';
        badge.innerText = authorName;
        badge.addEventListener('click', (e) => {
            e.stopPropagation(); 
            openProfileModal(authorName);
        });
        authorSpan.appendChild(badge);
    } else {
        authorSpan.textContent = ' anonim';
    }

    foot.appendChild(authorSpan);
    card.appendChild(foot);

    return card;
}

/* --- ADD WORD & COMMENT --- */
function handleWordSubmit(e) { e.preventDefault(); submitWord(); }
async function submitWord() {
    const w = document.getElementById('inputWord').value.trim();
    const d = document.getElementById('inputDef').value.trim();
    const ex = document.getElementById('inputExample').value.trim();
    const et = document.getElementById('inputEtymology').value.trim();
    const n = isUserLoggedIn ? currentUserUsername : 'Anonim';

    const btn = document.querySelector(".form-card button[type='submit']");

    if (!w || !d || !ex || !et) return showCustomAlert("Lütfen tüm alanları doldurun.", "error");
    
    if (d.length > 300) return showCustomAlert("Tanım çok uzun.", "error");
    if (ex.length > 200) return showCustomAlert("Örnek cümle çok uzun.", "error");
    if (et.length > 200) return showCustomAlert("Köken bilgisi çok uzun.", "error");

    btn.disabled = true; btn.innerText = "Kaydediliyor...";
    try {
        await apiRequest('/api/word', 'POST', { 
            word: w, 
            definition: d, 
            example: ex, 
            etymology: et,
            nickname: n, 
            category_ids: Array.from(selectedFormCategories)
        });
        
        document.getElementById('inputWord').value=''; 
        document.getElementById('inputDef').value='';
        document.getElementById('inputExample').value='';
        document.getElementById('inputEtymology').value='';
        updateCount({value:''});
        
        selectedFormCategories.clear();
        document.querySelectorAll('.category-pill.selected').forEach(el => el.classList.remove('selected'));

        showCustomAlert("Sözcük gönderildi (Onay bekleniyor)!");
        
    } catch (e) { showCustomAlert(e.message, "error"); }
    finally { btn.disabled = false; btn.innerText = "Sözlüğe Ekle"; }
}

/* --- ADD EXAMPLE FEATURE (NEW) --- */
function openAddExampleModal(wordId, wordText) {
    wordIdForExample = wordId;
    
    const wordDisplay = document.getElementById('exampleModalWord');
    if (wordDisplay) {
        wordDisplay.innerText = wordText ? `"${wordText}"` : '';
    }

    const input = document.getElementById('newExampleInput');
    const count = document.getElementById('exampleCharCount');
    
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
        await apiRequest('/api/example', 'PATCH', {
            word_id: wordIdForExample,
            example: exampleText
        });

        showCustomAlert("Örnek cümle başarıyla eklendi!");
        closeModal('addExampleModal');
        
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
const pendingVotes = {};

function createVoteControls(type, data) {
    const div = document.createElement('div'); div.className = 'vote-container';
    const mkBtn = (act, icon) => {
        const b = document.createElement('button'); 
        b.className=`vote-btn ${act} ${data.user_vote === act ? 'active' : ''}`;
        b.innerHTML=`<svg viewBox="0 0 24 24"><path d="${icon}"></path></svg>`;
        b.addEventListener('click', (e) => { 
            e.stopPropagation(); 
            if (!isUserLoggedIn) {
                openAuthModal();
                return;
            }
            sendVote(type, data.id, act, div); 
        });
        return b;
    };
    div.append(
        mkBtn('like','M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3'), 
        Object.assign(document.createElement('span'), { className: 'vote-score', innerText: data.score }), 
        mkBtn('dislike','M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17')
    );
    return div;
}

function sendVote(type, id, act, con) {
    const uniqueId = `${type}_${id}`;
    
    const likeBtn = con.querySelector('.like');
    const dislikeBtn = con.querySelector('.dislike');
    const scoreSpan = con.querySelector('.vote-score');
    
    if (!pendingVotes[uniqueId]) {
        let state = 'none';
        if (likeBtn.classList.contains('active')) state = 'like';
        else if (dislikeBtn.classList.contains('active')) state = 'dislike';
        
        pendingVotes[uniqueId] = {
            originalState: state,
            originalScore: parseInt(scoreSpan.innerText, 10) || 0,
            currentState: state,
            currentScore: parseInt(scoreSpan.innerText, 10) || 0,
            timer: null
        };
    }
    
    const voteData = pendingVotes[uniqueId];
    clearTimeout(voteData.timer);
    
    if (voteData.currentState === act) {
        voteData.currentState = 'none';
        voteData.currentScore -= (act === 'like' ? 1 : -1);
    } else {
        let diff = 0;
        if (voteData.currentState === 'none') {
            diff = (act === 'like') ? 1 : -1;
        } else {
            diff = (act === 'like') ? 2 : -2; 
        }
        voteData.currentState = act;
        voteData.currentScore += diff;
    }
    
    likeBtn.classList.remove('active');
    dislikeBtn.classList.remove('active');
    if (voteData.currentState === 'like') likeBtn.classList.add('active');
    if (voteData.currentState === 'dislike') dislikeBtn.classList.add('active');
    scoreSpan.innerText = voteData.currentScore;
    
    voteData.timer = setTimeout(async () => {
        const finalState = voteData.currentState;
        const initialState = voteData.originalState;
        
        if (finalState === initialState) {
            delete pendingVotes[uniqueId];
            return;
        }
        
        const actionToSend = (finalState === 'none') ? initialState : finalState;
        
        const btns = con.querySelectorAll('.vote-btn');
        btns.forEach(b => b.disabled = true);
        
        try {
            const data = await apiRequest(`/api/vote/${type}/${id}`, 'POST', { action: actionToSend });
            
            scoreSpan.innerText = data.new_score;
            likeBtn.classList.remove('active');
            dislikeBtn.classList.remove('active');
            if(data.user_action === 'liked') likeBtn.classList.add('active');
            else if(data.user_action === 'disliked') dislikeBtn.classList.add('active');
        } catch (e) {
            showCustomAlert("Hata oluştu, oy kaydedilemedi.", "error");
            
            likeBtn.classList.remove('active');
            dislikeBtn.classList.remove('active');
            if (initialState === 'like') likeBtn.classList.add('active');
            if (initialState === 'dislike') dislikeBtn.classList.add('active');
            scoreSpan.innerText = voteData.originalScore;
        } finally {
            btns.forEach(b => b.disabled = false);
            delete pendingVotes[uniqueId];
        }
    }, 500);
}

/* === DETAIL VIEW & COMMENTS === */
function animateAndOpenCommentView(originalCard, wordId, wordText, wordDef, wordExample, wordEtymology, isModalMode = false) { 
    if (activeCardClone) return; 

    currentWordId = wordId;

    const backdrop = document.getElementById('modalBackdrop');
    backdrop.style.display = 'block';
    requestAnimationFrame(() => backdrop.classList.add('show'));
    
    const clone = document.createElement('div');
    clone.className = 'full-comment-view'; 
    if(isModalMode) clone.classList.add('mode-modal');
    
    // Safely escape parameters before inserting into innerHTML
    const safeWordText = escapeHTML(wordText);
    const safeWordDef = escapeHTML(wordDef);
    const safeExample = escapeHTML(wordExample);
    const safeEtymology = escapeHTML(wordEtymology);

    const exampleHTML = safeExample ? `<div class="word-example" style="margin-top:8px;">"${safeExample}"</div>` : '';
    const etymologyHTML = safeEtymology ? `<div class="word-etymology" style="font-size:0.9rem; color:var(--text-muted); margin-top:5px; margin-bottom:5px;"><em>Köken:</em> ${safeEtymology}</div>` : '';

    const commentPlaceholder = isUserLoggedIn ? "Yorum yaz..." : "Yorum yapmak için giriş yapın...";

    const contentHTML = `
        <div class="view-header">
            <div style="display:flex; justify-content:space-between; align-items:start;">
                <div>
                    <h2 id="commentTitle" style="margin:0; font-size:1.4rem; color:var(--accent);">${safeWordText}</h2>
                    ${etymologyHTML}
                    <div style="font-size:1rem; color:var(--text-muted); margin-top:5px; font-style:italic;">${safeWordDef}</div>
                    ${exampleHTML}
                </div>
                <button class="close-icon-btn" id="closeCommentViewBtn">✕</button>
            </div>
        </div>
        <div id="commentsList" class="view-body">
            <div class="spinner"></div>
        </div>
        <div class="view-footer">
            <div class="custom-comment-wrapper">
                <textarea id="commentInput" class="custom-textarea-minimal" rows="2" placeholder="${commentPlaceholder}" maxlength="200" ${isUserLoggedIn ? "" : 'readonly'}></textarea>
                <div class="custom-comment-footer">
                    <button class="send-btn-minimal" id="submitCommentActionBtn">Gönder</button>
                </div>
            </div>
        </div>
    `;

    clone.innerHTML = contentHTML;
    document.body.appendChild(clone);
    requestAnimationFrame(() => requestAnimationFrame(() => clone.classList.add('expanded')));

    document.getElementById('closeCommentViewBtn')?.addEventListener('click', closeCommentView);
    if (!isUserLoggedIn) {
        document.getElementById('commentInput')?.addEventListener('click', openAuthModal);
        document.getElementById('submitCommentActionBtn')?.addEventListener('click', openAuthModal);
    } else {
        document.getElementById('submitCommentActionBtn')?.addEventListener('click', submitComment);
    }

    activeCardClone = clone;
    loadComments(wordId, 1, false);
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
                btn.addEventListener('click', () => loadComments(wordId, ++currentCommentPage));
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
        badge.addEventListener('click', (e) => { e.stopPropagation(); openProfileModal(authorName); });
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

    if (!isUserLoggedIn) {
        openAuthModal();
        return;
    }

    const txt = activeCardClone.querySelector('#commentInput').value.trim();
    if(!txt) return showCustomAlert("Yorum yazın.","error");
    if(txt.length > 200) return showCustomAlert("Çok uzun.","error");

    const btn = activeCardClone.querySelector('.send-btn-minimal');
    btn.disabled = true; 

    apiRequest('/api/comment', 'POST', { word_id: currentWordId, comment: txt })
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
        showCustomAlert("Kullanıcı bulunamadı", "error");
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
    const current = document.getElementById('currentPassword').value;
    const p1 = document.getElementById('newPassword').value;
    const p2 = document.getElementById('newPasswordConfirm').value;
    if(!current) return showCustomAlert("Mevcut şifrenizi girin.", "error");
    if(current.length > 60) return showCustomAlert("Şifre en fazla 60 karakter olabilir.", "error");
    if(p1.length < 6 || p1 !== p2) return showCustomAlert("Hatalı veya eşleşmeyen şifre.", "error");
    if(p1.length > 60) return showCustomAlert("Yeni şifre en fazla 60 karakter olabilir.", "error");

    apiRequest('/api/password','PATCH',{current_password: current, new_password: p1})
    .then(() => {
        showCustomAlert("Şifre değişti.");
        document.getElementById('currentPassword').value = '';
        document.getElementById('newPassword').value = '';
        document.getElementById('newPasswordConfirm').value = '';
    })
    .catch(e => showCustomAlert(e.message, "error"));
}

function handleChangeUsername() {
    const newUsername = document.getElementById('newUsernameInput').value.trim();
    const oldUsername = currentUserUsername;
    if (newUsername) {
        apiRequest('/api/username', 'PATCH', { new_username: newUsername })
            .then(() => {
                showCustomAlert("Kullanıcı adı başarıyla değiştirildi.");
                currentUserUsername = newUsername;
                document.body.setAttribute('data-username', newUsername);
                document.querySelectorAll('.user-badge').forEach(badge => {
                    if (badge.innerText === oldUsername) {
                        badge.innerText = newUsername;
                    }
                });
                if (currentProfileUser === oldUsername) {
                    currentProfileUser = newUsername;
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