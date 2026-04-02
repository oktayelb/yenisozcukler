/* === TRANSLATION CHALLENGE === */
import { state, isUserLoggedIn, CHALLENGE_COMMENTS_PER_PAGE, pendingVotes } from './state.js';
import { escapeHTML, apiRequest, showCustomAlert, getCSRFToken } from './utils.js';
import { openAuthModal } from './auth.js';
import { openProfileModal } from './profile.js';

let allChallenges = [];

export function setupChallengeBox() {
    const toggleArea = document.getElementById('challengeToggleArea');
    if (toggleArea) {
        toggleArea.addEventListener('click', toggleChallengeExpand);
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

    fetchChallengesAndRender();
}

async function fetchChallengesAndRender() {
    const preview = document.getElementById('challengePreview');
    if (!preview) return;

    try {
        const data = await apiRequest('/api/challenges');
        allChallenges = data.challenges || [];
        renderPreview();
    } catch (e) {
        preview.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:10px;font-size:0.85rem;">Yüklenemedi.</div>';
    }
}

function renderPreview() {
    const preview = document.getElementById('challengePreview');
    if (!preview) return;
    preview.innerHTML = '';

    const top3 = allChallenges.slice(0, 3);
    if (top3.length === 0) {
        preview.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:10px;font-size:0.85rem;">Henüz meydan okuma yok.</div>';
        return;
    }

    top3.forEach(ch => {
        const chip = document.createElement('div');
        chip.className = 'challenge-chip';
        chip.addEventListener('click', (e) => {
            e.stopPropagation();
            openChallengeDiscussion(ch.id, ch.foreign_word, ch.meaning);
        });

        const word = document.createElement('span');
        word.className = 'challenge-chip-word';
        word.textContent = ch.foreign_word;

        const count = document.createElement('span');
        count.className = 'challenge-chip-count';
        count.textContent = Number(ch.comment_count) || 0;

        chip.append(word, count);
        preview.appendChild(chip);
    });
}

function toggleChallengeExpand() {
    const wrapper = document.getElementById('challengeBodyWrapper');
    const icon = document.getElementById('challengeToggleIcon');
    if (!wrapper) return;

    state.challengeExpanded = !state.challengeExpanded;

    if (state.challengeExpanded) {
        wrapper.classList.add('expanded');
        if (icon) icon.style.transform = 'rotate(180deg)';
        renderFullList();
    } else {
        wrapper.classList.remove('expanded');
        if (icon) icon.style.transform = 'rotate(0deg)';
    }
}

function renderFullList() {
    const list = document.getElementById('challengeList');
    if (!list) return;
    list.innerHTML = '';

    if (allChallenges.length === 0) {
        list.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:15px;">Henüz meydan okuma yok.</div>';
        return;
    }

    allChallenges.forEach(ch => list.appendChild(createChallengeItem(ch)));
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

    const hint = document.createElement('span');
    hint.className = 'challenge-comment-hint';
    hint.textContent = `Öneriler (${Number(ch.comment_count) || 0})`;
    footer.appendChild(hint);

    const authorEl = document.createElement('span');
    authorEl.className = 'challenge-author';
    authorEl.textContent = ch.author || 'Anonim';
    footer.appendChild(authorEl);

    item.appendChild(footer);
    item.addEventListener('click', () => openChallengeDiscussion(ch.id, ch.foreign_word, ch.meaning));
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

    const footerContent = isUserLoggedIn
        ? `<div class="custom-comment-wrapper">
               <div class="custom-comment-header">
                   <input type="text" id="challengeSuggestedWordInput" class="custom-input-minimal"
                          placeholder="Önerdiğiniz sözcük..." maxlength="30" autocomplete="off">
               </div>
               <textarea id="challengeExplanationInput" class="custom-textarea-minimal" rows="2"
                         placeholder="Neden bu sözcüğü öneriyorsunuz? (İsteğe bağlı)" maxlength="300"></textarea>
               <div class="custom-comment-footer">
                   <button class="send-btn-minimal" id="submitChallengeSuggestionBtn">Karşılık Öner</button>
               </div>
           </div>`
        : `<div class="custom-comment-wrapper" style="cursor:pointer;" id="loginPromptWrapper">
               <div class="custom-comment-header">
                   <input class="custom-input-minimal" readonly placeholder="Önerdiğiniz sözcük...">
               </div>
               <textarea class="custom-textarea-minimal" rows="2" readonly
                         placeholder="Karşılık önermek için giriş yapın..."></textarea>
               <div class="custom-comment-footer">
                   <button class="send-btn-minimal">Karşılık Öner</button>
               </div>
           </div>`;

    view.innerHTML = `
        <div class="view-header">
            <div style="display:flex; justify-content:space-between; align-items:start;">
                <div>
                    <h2 style="margin:0; font-size:1.4rem; color:var(--accent);">${safeWord}</h2>
                    <div style="font-size:0.92rem; color:var(--text-muted); margin-top:4px; font-style:italic;">${safeMeaning}</div>
                </div>
                <button class="close-icon-btn" id="closeChallengeViewBtn">&#10005;</button>
            </div>
        </div>
        <div id="challengeCommentsList" class="view-body">
            <div class="spinner"></div>
        </div>
        <div class="view-footer">${footerContent}</div>
    `;

    document.body.appendChild(view);
    requestAnimationFrame(() => requestAnimationFrame(() => view.classList.add('expanded')));

    document.getElementById('closeChallengeViewBtn')?.addEventListener('click', closeChallengeDiscussion);

    if (!isUserLoggedIn) {
        document.getElementById('loginPromptWrapper')?.addEventListener('click', openAuthModal);
    } else {
        document.getElementById('submitChallengeSuggestionBtn')?.addEventListener('click', submitChallengeSuggestion);
    }

    state.activeChallengeView = view;
    loadSuggestions(challengeId, 1);
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

async function loadSuggestions(challengeId, page = 1) {
    const list = state.activeChallengeView?.querySelector('#challengeCommentsList');
    if (!list) return;

    if (page === 1) {
        list.innerHTML = '<div class="spinner"></div>';
        state.currentChallengeCommentPage = 1;
    } else {
        const btn = list.querySelector('.load-more-comments-btn');
        if (btn) btn.innerText = 'Yükleniyor...';
    }

    try {
        const data = await apiRequest(`/api/challenge-comments/${challengeId}?page=${page}&limit=${CHALLENGE_COMMENTS_PER_PAGE}`);

        if (page === 1) list.innerHTML = '';
        else list.querySelector('.load-more-comments-btn')?.remove();

        if (data.comments?.length > 0) {
            data.comments.forEach(s => list.appendChild(createSuggestionCard(s)));
            if (data.has_next) {
                const btn = document.createElement('button');
                btn.className = 'load-more-comments-btn';
                btn.innerText = 'Daha fazla öneri';
                btn.addEventListener('click', () => loadSuggestions(challengeId, ++state.currentChallengeCommentPage));
                list.appendChild(btn);
            }
        } else if (page === 1) {
            list.innerHTML = '<div style="text-align:center;color:var(--text-muted);margin-top:20px;">Henüz öneri yok. İlk karşılığı sen öner!</div>';
        }
    } catch (e) {
        if (page === 1) list.innerHTML = '<div style="color:var(--error-color);">Hata.</div>';
    }
}

function createSuggestionCard(s) {
    const card = document.createElement('div');
    card.className = 'suggestion-card';
    card.setAttribute('data-suggestion-id', s.id);

    const displayWord = s.suggested_word || '';
    const wordEl = document.createElement('div');
    wordEl.className = 'suggestion-word';
    wordEl.textContent = displayWord;
    card.appendChild(wordEl);

    // Explanation (optional)
    const displayExpl = s.explanation || '';
    if (displayExpl) {
        const explEl = document.createElement('div');
        explEl.className = 'suggestion-explanation';
        explEl.textContent = displayExpl;
        card.appendChild(explEl);
    }

    // Footer: meta + votes
    const footer = document.createElement('div');
    footer.className = 'suggestion-footer';

    const meta = document.createElement('div');
    meta.className = 'suggestion-meta';

    const authorName = s.author || 'Anonim';
    if (authorName !== 'Anonim') {
        const badge = document.createElement('span');
        badge.className = 'user-badge';
        badge.innerText = authorName;
        badge.addEventListener('click', (e) => { e.stopPropagation(); openProfileModal(authorName); });
        meta.appendChild(badge);
    } else {
        const anonEl = document.createElement('span');
        anonEl.className = 'suggestion-anon';
        anonEl.textContent = 'Anonim';
        meta.appendChild(anonEl);
    }

    const date = new Date(s.timestamp).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' });
    const dateEl = document.createElement('span');
    dateEl.className = 'suggestion-date';
    dateEl.textContent = date;
    meta.appendChild(dateEl);

    footer.appendChild(meta);
    footer.appendChild(createChallengeVoteControls(s));
    card.appendChild(footer);

    return card;
}

async function submitChallengeSuggestion() {
    if (!state.activeChallengeView) return;
    if (!isUserLoggedIn) { openAuthModal(); return; }

    const wordInput = state.activeChallengeView.querySelector('#challengeSuggestedWordInput');
    const explInput = state.activeChallengeView.querySelector('#challengeExplanationInput');
    const btn = state.activeChallengeView.querySelector('#submitChallengeSuggestionBtn');

    const suggestedWord = wordInput?.value.trim() || '';
    const explanation = explInput?.value.trim() || '';

    if (!suggestedWord) {
        return showCustomAlert("Önerilen sözcük boş olamaz.", "error");
    }

    btn.disabled = true;
    btn.innerText = "Gönderiliyor...";

    try {
        const response = await fetch('/api/challenge-suggestion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                challenge_id: state.currentChallengeId,
                suggested_word: suggestedWord,
                explanation: explanation
            })
        });

        const data = await response.json();

        if (response.status === 409) {
            showCustomAlert("Bu sözcük zaten önerilmiş. Sizi mevcut öneriye yönlendiriyoruz, lütfen onu oylayın.");
            scrollToAndHighlight(data.existing_id);
            return;
        }

        if (!response.ok) {
            throw new Error(data.error || "İşlem başarısız.");
        }

        showCustomAlert("Öneriniz eklendi!");
        if (wordInput) wordInput.value = '';
        if (explInput) explInput.value = '';

        const list = state.activeChallengeView.querySelector('#challengeCommentsList');
        if (list) {
            if (list.querySelector('[style*="Henüz"]') || list.innerText.includes('Henüz')) list.innerHTML = '';
            const newCard = createSuggestionCard({ ...data.suggestion, user_vote: null });
            list.insertBefore(newCard, list.firstChild);
            list.scrollTop = 0;
        }
    } catch (e) {
        showCustomAlert(e.message, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = "Karşılık Öner";
        }
    }
}

function scrollToAndHighlight(suggestionId) {
    const list = state.activeChallengeView?.querySelector('#challengeCommentsList');
    if (!list) return;
    const target = list.querySelector(`[data-suggestion-id="${suggestionId}"]`);
    if (!target) return;

    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    // Remove and re-add class to restart animation if already present
    target.classList.remove('suggestion-highlight');
    void target.offsetWidth;
    target.classList.add('suggestion-highlight');
    target.addEventListener('animationend', () => target.classList.remove('suggestion-highlight'), { once: true });
}

function triggerVoteAnim(btn, container) {
    btn.classList.remove('vote-pop');
    void btn.offsetWidth;
    btn.classList.add('vote-pop');
    btn.addEventListener('animationend', () => btn.classList.remove('vote-pop'), { once: true });
    const score = container.querySelector('.vote-score');
    if (score) {
        score.classList.remove('score-flash');
        void score.offsetWidth;
        score.classList.add('score-flash');
        score.addEventListener('animationend', () => score.classList.remove('score-flash'), { once: true });
    }
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
            triggerVoteAnim(b, div);
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
