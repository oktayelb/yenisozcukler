/* --- FEED & WORDS --- */
import { state, ITEMS_PER_PAGE } from './state.js';
import { apiRequest, updatePageMeta } from './utils.js';
import { createCardElement } from './cards.js';
import { toggleContributionForm } from './form.js';

export async function fetchWords(page) {
    if (state.isLoading) return;
    state.isLoading = true;
    const list = document.getElementById('feedList');
    const loadBtn = document.querySelector('#loadMoreContainer button');

    let url = `/api/words?page=${page}&limit=${ITEMS_PER_PAGE}&sort=${encodeURIComponent(state.currentSort)}`;
    if (state.activeCategorySlug) {
        url += `&tag=${state.activeCategorySlug}`;
    }
    if (state.currentSearchQuery) {
        url += `&search=${encodeURIComponent(state.currentSearchQuery)}`;
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
        if (page === 1) list.innerHTML = '';

        if (data.words?.length > 0) {
            appendCards(data.words, list, false);
            const hasMore = data.words.length >= ITEMS_PER_PAGE && (!data.total_count || (page * ITEMS_PER_PAGE < data.total_count));
            document.getElementById('loadMoreContainer').style.display = hasMore ? 'block' : 'none';
        } else if (page === 1) {
            if (state.currentSearchQuery) {
                list.innerHTML = '';
                const noResultMsg = document.createElement('div');
                noResultMsg.style.cssText = 'text-align:center;color:#ccc;margin-top:20px;';
                noResultMsg.textContent = `"${state.currentSearchQuery}" için sonuç bulunamadı.`;
                list.appendChild(noResultMsg);
            } else {
                list.innerHTML = '<div style="text-align:center;color:#ccc;margin-top:20px;">Henüz içerik yok.</div>';
            }
        }
    } catch (e) {
        if (page === 1) list.innerHTML = '<div style="text-align:center;color:var(--error-color);">Yüklenemedi.</div>';
    } finally {
        state.isLoading = false;
        loadBtn.textContent = 'Daha Fazla Göster';
        loadBtn.disabled = false;
    }
}

export function handleTagClick(slug, name, description) {
    state.activeCategorySlug = slug;
    state.currentPage = 1;

    window.scrollTo({ top: 0, behavior: 'smooth' });

    updateFilterBanner(true, name, description);
    updatePageMeta(
        `${name} - Yeni Sözcükler`,
        description || `${name} kategorisindeki yeni Türkçe sözcükler.`
    );

    fetchWords(state.currentPage);
}

export function clearCategoryFilter() {
    state.activeCategorySlug = null;
    state.currentPage = 1;
    updateFilterBanner(false);
    updatePageMeta();
    // Update URL when user explicitly clears filter (not during router dispatch)
    if (location.pathname !== '/') {
        history.pushState(null, '', '/');
    }
    fetchWords(state.currentPage);
}

function updateFilterBanner(show, name = '', description = '') {
    const banner = document.getElementById('activeFilterBanner');
    const nameDisplay = document.getElementById('filterNameDisplay');
    const descDisplay = document.getElementById('filterDescDisplay');

    if (banner) {
        banner.style.display = show ? 'flex' : 'none';

        if (show) {
            if (nameDisplay) nameDisplay.innerText = name;

            if (descDisplay) {
                if (description) {
                    descDisplay.innerText = description;
                    descDisplay.style.display = 'block';
                } else {
                    descDisplay.style.display = 'none';
                }
            }
        }
    }
}

export function loadMoreWords() {
    state.currentPage++;
    fetchWords(state.currentPage);
}

export function appendCards(words, container, isModalMode) {
    const frag = document.createDocumentFragment();
    words.forEach((w, i) => {
        const card = createCardElement(w, isModalMode);
        card.style.animationDelay = `${i * 60 + 30}ms`;
        frag.appendChild(card);
    });
    container.appendChild(frag);
    // Trigger show class on next frame so the animationDelay CSS takes effect
    requestAnimationFrame(() => {
        Array.from(container.children).slice(-words.length).forEach(c => {
            c.classList.remove('fade-in');
            c.classList.add('show');
        });
    });
}

export function executeSearch(query) {
    const trimmed = query.trim();
    if (state.currentSearchQuery === trimmed) return;
    state.currentSearchQuery = trimmed;
    state.currentPage = 1;
    if (trimmed) {
        updatePageMeta(`"${trimmed}" araması - Yeni Sözcükler`, `"${trimmed}" için arama sonuçları.`);
    } else {
        updatePageMeta();
    }
    fetchWords(state.currentPage);
}

export function focusContributionForm() {
    const card = document.getElementById('contributionCard');
    if (!card) return;

    if (!card.classList.contains('expanded')) {
        toggleContributionForm();
    }

    card.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
