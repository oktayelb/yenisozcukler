/* --- ADD EXAMPLE FEATURE --- */
import { state } from './state.js';
import { apiRequest, showCustomAlert } from './utils.js';
import { openModal, closeModal } from './modal.js';

export function openAddExampleModal(wordId, wordText) {
    state.wordIdForExample = wordId;

    const wordDisplay = document.getElementById('exampleModalWord');
    if (wordDisplay) {
        wordDisplay.innerText = wordText ? `"${wordText}"` : '';
    }

    const input = document.getElementById('newExampleInput');
    const count = document.getElementById('exampleCharCount');

    if (input) input.value = '';
    if (count) count.innerText = '0 / 200';

    if (input) {
        input.oninput = function () {
            if (count) count.innerText = `${this.value.length} / 200`;
        };
    }

    openModal('addExampleModal');
    setTimeout(() => { if (input) input.focus(); }, 100);
}

export async function submitExample() {
    const input = document.getElementById('newExampleInput');
    const btn = document.getElementById('submitExampleBtn');
    const exampleText = input.value.trim();

    if (!exampleText) return showCustomAlert("Lütfen bir cümle yazın.", "error");
    if (exampleText.length > 200) return showCustomAlert("Cümle çok uzun.", "error");

    btn.disabled = true;
    btn.innerText = "Kaydediliyor...";

    try {
        await apiRequest('/api/example', 'PATCH', {
            word_id: state.wordIdForExample,
            example: exampleText
        });

        showCustomAlert("Örnek cümle başarıyla eklendi!");
        closeModal('addExampleModal');

        updateCardWithExample(state.wordIdForExample, exampleText);

    } catch (e) {
        showCustomAlert(e.message, "error");
    } finally {
        btn.disabled = false;
        btn.innerText = "Kaydet";
        state.wordIdForExample = null;
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
