/* === TRANSLATION CHALLENGE === */
import { state, isUserLoggedIn, CHALLENGE_COMMENTS_PER_PAGE, pendingVotes } from './state.js';
import { escapeHTML, apiRequest, showCustomAlert } from './utils.js';
import { openAuthModal } from './auth.js';
import { openProfileModal } from './profile.js';

export function setupChallengeBox() {
    const header = document.getElementById('challengeHeader');
    if (header) {
        header.addEventListener('click', toggleChallengeBox);
    }

    const suggestBtn = document.getElementById('challengeSuggestBtn');
    if (suggestBtn) {
        suggestBtn.addEventListener('click', () => {
            document.getElementById('challengeForm').style.display = 'block';
            suggestBtn.style.display = 'none';
        });
    }

    const cancelBtn = document.getElementById('challengeCancelBtn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            document.getElementById('challengeForm').style.display = 'none';
            document.getElementById('challengeSuggestBtn').style.display = 'block';
            document.getElementById('challengeWordInput').value = '';
            document.getElementById('challengeMeaningInput').value = '';
        });
    }

    const submitBtn = document.getElementById('challengeSubmitBtn');
    if (submitBtn) {
        submitBtn.addEventListener('click', submitChallenge);
    }
}

function toggleChallengeBox() {
    const body = document.getElementById('challengeBody');
    const icon = document.getElementById('challengeToggleIcon');
    if (!body) return;

    state.challengeExpanded = !state.challengeExpanded;
    body.style.display = state.challengeExpanded ? 'block' : 'none';
    if (icon) icon.innerHTML = state.challengeExpanded ? '&#9650;' : '&#9660;';

    if (state.challengeExpanded) {
        fetchChallenges();
    }
}

async function fetchChallenges() {
    const list = document.getElementById('challengeList');
    if (!list) return;
    list.innerHTML = '<div class="spinner"></div>';

    try {
        const data = await apiRequest('/api/challenges');
        list.innerHTML = '';
        if (data.challenges?.length > 0) {
            data.challenges.forEach(ch => {
                list.appendChild(createChallengeItem(ch));
            });
        } else {
            list.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:15px;">Henüz meydan okuma yok.</div>';
        }
    } catch (e) {
        list.innerHTML = '<div style="text-align:center;color:var(--error-color);padding:15px;">Yüklenemedi.</div>';
    }
}

function createChallengeItem(ch) {
    const item = document.createElement('div');
    item.className = 'challenge-item';
    item.setAttribute('data-challenge-id', ch.id);

    const wordEl = document.createElement('div');
    wordEl.className = 'challenge-word';
    wordEl.textContent = ch.foreign_word;
    item.appendChild(wordEl);

    const meaningEl = document.createElement('div');
    meaningEl.className = 'challenge-meaning';
    meaningEl.textContent = ch.meaning;
    item.appendChild(meaningEl);

    const footer = document.createElement('div');
    footer.className = 'challenge-item-footer';

    const commentHint = document.createElement('span');
    commentHint.className = 'challenge-comment-hint';
    const cCount = Number(ch.comment_count) || 0;
    commentHint.textContent = `Tartışma (${cCount})`;
    footer.appendChild(commentHint);

    const authorEl = document.createElement('span');
    authorEl.className = 'challenge-author';
    authorEl.textContent = ch.author || 'Anonim';
    footer.appendChild(authorEl);

    item.appendChild(footer);

    item.addEventListener('click', () => {
        openChallengeDiscussion(ch.id, ch.foreign_word, ch.meaning);
    });

    return item;
}

async function submitChallenge() {
    const wordInput = document.getElementById('challengeWordInput');
    const meaningInput = document.getElementById('challengeMeaningInput');
    const btn = document.getElementById('challengeSubmitBtn');

    const word = wordInput.value.trim();
    const meaning = meaningInput.value.trim();

    if (!word || !meaning) return showCustomAlert("Lütfen tüm alanları doldurun.", "error");

    btn.disabled = true;
    btn.innerText = "Gönderiliyor...";

    try {
        await apiRequest('/api/challenge', 'POST', { foreign_word: word, meaning: meaning });
        showCustomAlert("Sözcük önerisi gönderildi (Onay bekleniyor)!");
        wordInput.value = '';
        meaningInput.value = '';
        document.getElementById('challengeForm').style.display = 'none';
        document.getElementById('challengeSuggestBtn').style.display = 'block';
    } catch (e) {
        showCustomAlert(e.message, "error");
    } finally {
        btn.disabled = false;
        btn.innerText = "Gönder";
    }
}

function openChallengeDiscussion(challengeId, foreignWord, meaning) {
    if (state.activeChallengeView) return;
    state.currentChallengeId = challengeId;

    const backdrop = document.getElementById('modalBackdrop');
    backdrop.style.display = 'block';
    requestAnimationFrame(() => backdrop.classList.add('show'));

    const view = document.createElement('div');
    view.className = 'full-comment-view';

    const safeWord = escapeHTML(foreignWord);
    const safeMeaning = escapeHTML(meaning);
    const commentPlaceholder = isUserLoggedIn ? "Bir Türkçe karşılık öner veya tartışmaya katıl..." : "Yorum yapmak için giriş yapın...";

    view.innerHTML = `
        <div class="view-header">
            <div style="display:flex; justify-content:space-between; align-items:start;">
                <div>
                    <h2 style="margin:0; font-size:1.4rem; color:var(--accent);">${safeWord}</h2>
                    <div style="font-size:1rem; color:var(--text-muted); margin-top:5px; font-style:italic;">${safeMeaning}</div>
                </div>
                <button class="close-icon-btn" id="closeChallengeViewBtn">&#10005;</button>
            </div>
        </div>
        <div id="challengeCommentsList" class="view-body">
            <div class="spinner"></div>
        </div>
        <div class="view-footer">
            <div class="custom-comment-wrapper">
                <textarea id="challengeCommentInput" class="custom-textarea-minimal" rows="2" placeholder="${commentPlaceholder}" maxlength="300" ${isUserLoggedIn ? "" : 'readonly'}></textarea>
                <div class="custom-comment-footer">
                    <button class="send-btn-minimal" id="submitChallengeCommentBtn">Gönder</button>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(view);
    requestAnimationFrame(() => requestAnimationFrame(() => view.classList.add('expanded')));

    document.getElementById('closeChallengeViewBtn')?.addEventListener('click', closeChallengeDiscussion);
    if (!isUserLoggedIn) {
        document.getElementById('challengeCommentInput')?.addEventListener('click', openAuthModal);
        document.getElementById('submitChallengeCommentBtn')?.addEventListener('click', openAuthModal);
    } else {
        document.getElementById('submitChallengeCommentBtn')?.addEventListener('click', submitChallengeComment);
    }

    state.activeChallengeView = view;
    loadChallengeComments(challengeId, 1);
}

export function closeChallengeDiscussion() {
    if (!state.activeChallengeView) return;

    const backdrop = document.getElementById('modalBackdrop');
    backdrop.classList.remove('show');
    state.activeChallengeView.classList.remove('expanded');

    setTimeout(() => {
        if (state.activeChallengeView) state.activeChallengeView.remove();
        state.activeChallengeView = null;
        backdrop.style.display = 'none';
        state.currentChallengeId = null;
    }, 400);
}

async function loadChallengeComments(challengeId, page = 1) {
    const list = state.activeChallengeView?.querySelector('#challengeCommentsList');
    if (!list) return;

    if (page === 1) { list.innerHTML = '<div class="spinner"></div>'; state.currentChallengeCommentPage = 1; }
    else { const b = list.querySelector('.load-more-comments-btn'); if (b) b.innerText = 'Yükleniyor...'; }

    try {
        const data = await apiRequest(`/api/challenge-comments/${challengeId}?page=${page}&limit=${CHALLENGE_COMMENTS_PER_PAGE}`);
        if (page === 1) list.innerHTML = ''; else list.querySelector('.load-more-comments-btn')?.remove();

        if (data.comments?.length > 0) {
            data.comments.forEach(c => list.appendChild(createChallengeCommentItem(c)));
            if (data.has_next) {
                const btn = document.createElement('button');
                btn.className = 'load-more-comments-btn';
                btn.innerText = 'Daha eski yorumlar';
                btn.addEventListener('click', () => loadChallengeComments(challengeId, ++state.currentChallengeCommentPage));
                list.appendChild(btn);
            }
        } else if (page === 1) {
            list.innerHTML = '<div style="text-align:center;color:var(--text-muted);margin-top:20px;">Henüz öneri yok. İlk öneriyi sen yap!</div>';
        }
    } catch (e) {
        if (page === 1) list.innerHTML = '<div style="color:var(--error-color);">Hata.</div>';
    }
}

function createChallengeCommentItem(c) {
    const d = document.createElement('div');
    d.className = 'comment-card';
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
    ft.style.display = 'flex';
    ft.style.justifyContent = 'flex-end';
    ft.appendChild(createChallengeVoteControls(c));
    d.appendChild(ft);

    return d;
}

function createChallengeVoteControls(data) {
    const div = document.createElement('div');
    div.className = 'vote-container';
    const mkBtn = (act, icon) => {
        const b = document.createElement('button');
        b.className = `vote-btn ${act} ${data.user_vote === act ? 'active' : ''}`;
        b.innerHTML = `<svg viewBox="0 0 24 24"><path d="${icon}"></path></svg>`;
        b.addEventListener('click', (e) => {
            e.stopPropagation();
            if (!isUserLoggedIn) { openAuthModal(); return; }
            sendChallengeCommentVote(data.id, act, div);
        });
        return b;
    };
    div.append(
        mkBtn('like', 'M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3'),
        Object.assign(document.createElement('span'), { className: 'vote-score', innerText: data.score }),
        mkBtn('dislike', 'M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17')
    );
    return div;
}

function sendChallengeCommentVote(commentId, act, con) {
    const uniqueId = `challenge_comment_${commentId}`;
    const likeBtn = con.querySelector('.like');
    const dislikeBtn = con.querySelector('.dislike');
    const scoreSpan = con.querySelector('.vote-score');

    if (!pendingVotes[uniqueId]) {
        let voteState = 'none';
        if (likeBtn.classList.contains('active')) voteState = 'like';
        else if (dislikeBtn.classList.contains('active')) voteState = 'dislike';
        pendingVotes[uniqueId] = {
            originalState: voteState,
            originalScore: parseInt(scoreSpan.innerText, 10) || 0,
            currentState: voteState,
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
        if (voteData.currentState === 'none') diff = (act === 'like') ? 1 : -1;
        else diff = (act === 'like') ? 2 : -2;
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
        if (finalState === initialState) { delete pendingVotes[uniqueId]; return; }

        const actionToSend = (finalState === 'none') ? initialState : finalState;
        const btns = con.querySelectorAll('.vote-btn');
        btns.forEach(b => b.disabled = true);

        try {
            const data = await apiRequest(`/api/challenge-comment-vote/${commentId}`, 'POST', { action: actionToSend });
            scoreSpan.innerText = data.new_score;
            likeBtn.classList.remove('active');
            dislikeBtn.classList.remove('active');
            if (data.user_action === 'liked') likeBtn.classList.add('active');
            else if (data.user_action === 'disliked') dislikeBtn.classList.add('active');
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

function submitChallengeComment() {
    if (!state.activeChallengeView) return;
    if (!isUserLoggedIn) { openAuthModal(); return; }

    const txt = state.activeChallengeView.querySelector('#challengeCommentInput').value.trim();
    if (!txt) return showCustomAlert("Yorum yazın.", "error");
    if (txt.length > 300) return showCustomAlert("Çok uzun.", "error");

    const btn = state.activeChallengeView.querySelector('#submitChallengeCommentBtn');
    btn.disabled = true;

    apiRequest('/api/challenge-comment', 'POST', { challenge_id: state.currentChallengeId, comment: txt })
        .then(data => {
            showCustomAlert("Yorum eklendi!");
            state.activeChallengeView.querySelector('#challengeCommentInput').value = '';
            const list = state.activeChallengeView.querySelector('#challengeCommentsList');
            if (list.innerText.includes('Henüz')) list.innerHTML = '';
            list.insertBefore(createChallengeCommentItem({ ...data.comment, user_vote: null }), list.firstChild);
            list.scrollTop = 0;
        })
        .catch(e => showCustomAlert(e.message, "error"))
        .finally(() => btn.disabled = false);
}
