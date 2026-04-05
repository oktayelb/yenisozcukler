/* --- CATEGORIES & HASHTAGS --- */
import { state } from './state.js';
import { apiRequest } from './utils.js';

export async function fetchCategories() {
    try {
        const data = await apiRequest('/api/categories');
        if (data.success) {
            state.allCategories = data.categories || [];
            renderCategorySelection();
        }
    } catch (e) {
        console.error("Failed to load categories:", e);
    }
}

function renderCategorySelection() {
    const container = document.getElementById('categoryPillsList');
    const wrapper = document.getElementById('categorySelectionContainer');

    if (!state.allCategories.length) {
        if (wrapper) wrapper.style.display = 'none';
        return;
    }

    if (wrapper) wrapper.style.display = 'block';
    container.innerHTML = '';

    state.allCategories.forEach(cat => {
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
    if (state.selectedFormCategories.has(id)) {
        state.selectedFormCategories.delete(id);
        el.classList.remove('selected');
    } else {
        state.selectedFormCategories.add(id);
        el.classList.add('selected');
    }

    const helpText = document.getElementById('categoryHelpText');
    if (helpText) {
        if (description) {
            helpText.innerHTML = '';
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
