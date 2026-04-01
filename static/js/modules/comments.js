/* === DETAIL VIEW & COMMENTS === */
import { state, isUserLoggedIn, COMMENTS_PER_PAGE } from './state.js';
import { escapeHTML, apiRequest, showCustomAlert } from './utils.js';
import { createVoteControls } from './voting.js';
import { openAuthModal } from './auth.js';
import { openProfileModal } from './profile.js';

export function animateAndOpenCommentView(originalCard, wordId, wordText, wordDef, wordExample, wordEtymology, isModalMode = false) {
    if (state.activeCardClone) return;

    state.currentWordId = wordId;

    const backdrop = document.getElementById('modalBackdrop');
    backdrop.style.display = 'block';
    requestAnimationFrame(() => backdrop.classList.add('show'));

    const clone = document.createElement('div');
    clone.className = 'full-comment-view';
    if (isModalMode) clone.classList.add('mode-modal');

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
                <button class="close-icon-btn" id="closeCommentViewBtn">&#10005;</button>
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

    state.activeCardClone = clone;
    loadComments(wordId, 1);
}

export function closeCommentView() {
    if (!state.activeCardClone) return;

    const backdrop = document.getElementById('modalBackdrop');
    backdrop.classList.remove('show');
    state.activeCardClone.classList.remove('expanded');

    setTimeout(() => {
        if (state.activeCardClone) state.activeCardClone.remove();
        state.activeCardClone = null;
        backdrop.style.display = 'none';
        state.currentWordId = null;
    }, 400);
}

async function loadComments(wordId, page = 1) {
    const list = state.activeCardClone.querySelector('#commentsList');
    if (!list) return;

    if (page === 1) { list.innerHTML = '<div class="spinner"></div>'; state.currentCommentPage = 1; }
    else { const b = list.querySelector('.load-more-comments-btn'); if (b) b.innerText = 'Yükleniyor...'; }

    try {
        const data = await apiRequest(`/api/comments/${wordId}?page=${page}&limit=${COMMENTS_PER_PAGE}`);
        if (page === 1) list.innerHTML = ''; else list.querySelector('.load-more-comments-btn')?.remove();

        if (data.comments?.length > 0) {
            data.comments.forEach(c => list.appendChild(createCommentItem(c)));
            if (data.has_next) {
                const btn = document.createElement('button');
                btn.className = 'load-more-comments-btn';
                btn.innerText = 'Daha eski yorumlar';
                btn.addEventListener('click', () => loadComments(wordId, ++state.currentCommentPage));
                list.appendChild(btn);
            }
        } else if (page === 1) {
            list.innerHTML = '<div style="text-align:center;color:var(--text-muted);margin-top:20px;">Henüz yorum yok.</div>';
        }
    } catch (e) { if (page === 1) list.innerHTML = '<div style="color:var(--error-color);">Hata.</div>'; }
}

function createCommentItem(c) {
    const d = document.createElement('div'); d.className = 'comment-card';
    const date = new Date(c.timestamp).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

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
    if (!state.activeCardClone) return;

    if (!isUserLoggedIn) {
        openAuthModal();
        return;
    }

    const txt = state.activeCardClone.querySelector('#commentInput').value.trim();
    if (!txt) return showCustomAlert("Yorum yazın.", "error");
    if (txt.length > 200) return showCustomAlert("Çok uzun.", "error");

    const btn = state.activeCardClone.querySelector('.send-btn-minimal');
    btn.disabled = true;

    apiRequest('/api/comment', 'POST', { word_id: state.currentWordId, comment: txt })
        .then(data => {
            showCustomAlert("Yorum eklendi!");
            state.activeCardClone.querySelector('#commentInput').value = '';
            const list = state.activeCardClone.querySelector('#commentsList');
            if (list.innerText.includes('Henüz yorum')) list.innerHTML = '';
            list.insertBefore(createCommentItem({ ...data.comment, user_vote: null }), list.firstChild);
            list.scrollTop = 0;
        })
        .catch(e => showCustomAlert(e.message, "error"))
        .finally(() => btn.disabled = false);
}
