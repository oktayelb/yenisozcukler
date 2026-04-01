/* --- VOTING SYSTEM --- */
import { isUserLoggedIn, pendingVotes } from './state.js';
import { apiRequest, showCustomAlert } from './utils.js';
import { openAuthModal } from './auth.js';

export function createVoteControls(type, data) {
    const div = document.createElement('div'); div.className = 'vote-container';
    const mkBtn = (act, icon) => {
        const b = document.createElement('button');
        b.className = `vote-btn ${act} ${data.user_vote === act ? 'active' : ''}`;
        b.innerHTML = `<svg viewBox="0 0 24 24"><path d="${icon}"></path></svg>`;
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
        mkBtn('like', 'M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3'),
        Object.assign(document.createElement('span'), { className: 'vote-score', innerText: data.score }),
        mkBtn('dislike', 'M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17')
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
