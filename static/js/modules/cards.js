/* === CARD GENERATION === */
import { state, isUserLoggedIn } from './state.js';
import { createVoteControls } from './voting.js';
import { animateAndOpenCommentView } from './comments.js';
import { openProfileModal } from './profile.js';
import { openAddExampleModal } from './example.js';
import { handleTagClick } from './feed.js';

export function createCardElement(item, isModalMode) {
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

    const contentDiv = document.createElement('div');

    const wordTitle = document.createElement('h3');
    wordTitle.textContent = item.word;
    contentDiv.appendChild(wordTitle);

    if (item.etymology) {
        const etyDiv = document.createElement('div');
        etyDiv.className = 'word-etymology';
        etyDiv.style.cssText = 'font-size:0.85rem; color:var(--text-muted); margin-bottom:8px;';
        etyDiv.innerHTML = '<em>Köken:</em> ';
        etyDiv.appendChild(document.createTextNode(item.etymology));
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
        state.currentUserUsername === item.author &&
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

            if (cat.description) {
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
