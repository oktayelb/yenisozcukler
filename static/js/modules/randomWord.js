/* === RANDOM WORD MODE (DICE) ===
 *
 * Zar butonu feed'i tek bir rastgele sözcük kartına indirger.
 * Tekrar basıldığında yeni bir sözcük gelir; karta tıklanınca
 * normal detay/yorum görünümü açılır.
 * Çıkış: logo kartına tıklamak.
 */
import { state } from './state.js';
import { apiRequest, showCustomAlert, updatePageMeta } from './utils.js';
import { appendCards, fetchWords } from './feed.js';
import { closeCommentView } from './comments.js';

const DICE_ICON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="4"></rect><circle cx="8.5" cy="8.5" r="1.2" fill="currentColor" stroke="none"></circle><circle cx="15.5" cy="8.5" r="1.2" fill="currentColor" stroke="none"></circle><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none"></circle><circle cx="8.5" cy="15.5" r="1.2" fill="currentColor" stroke="none"></circle><circle cx="15.5" cy="15.5" r="1.2" fill="currentColor" stroke="none"></circle></svg>';

/* --- Zar at --- */

async function rollDice() {
    const btn = document.getElementById('randomWordBtn');
    if (!btn || btn.disabled) return;

    btn.disabled = true;
    btn.classList.add('dice-rolling');

    try {
        const data = await apiRequest(
            `/api/random-word?exclude=${encodeURIComponent(state.randomSlug || '')}`
        );
        // Detay görünümü açıksa kapat: zar her zaman feed'i tazeler
        if (state.activeCardClone) closeCommentView();
        enterRandomMode();
        renderRandomWord(data.word);
    } catch (err) {
        showCustomAlert(err.message || 'Rastgele sözcük getirilemedi.', 'error');
    } finally {
        btn.classList.remove('dice-rolling');
        btn.disabled = false;
    }
}

function renderRandomWord(word) {
    state.randomSlug = word.slug;

    const list = document.getElementById('feedList');
    if (!list) return;
    list.innerHTML = '';
    appendCards([word], list, false);

    updatePageMeta('Rastgele Sözcük - Yeni Sözcükler', word.def || word.definition);
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* --- Moda giriş / çıkış --- */

function enterRandomMode() {
    if (state.randomMode) return;
    state.randomMode = true;
    document.body.classList.add('random-mode');

    // Aktif kategori / arama filtrelerini temizle (tek kart gösteriliyor)
    state.activeCategorySlug = null;
    state.currentSearchQuery = '';
    state.currentPage = 1;

    const banner = document.getElementById('activeFilterBanner');
    if (banner) banner.style.display = 'none';

    const searchInput = document.getElementById('mainSearchInput');
    if (searchInput) searchInput.value = '';
    const clearSearchBtn = document.getElementById('clearSearchBtn');
    if (clearSearchBtn) clearSearchBtn.style.display = 'none';

    if (location.pathname !== '/') history.pushState(null, '', '/');
}

/**
 * Rastgele mod arayüzünü kapatır (feed'i tazelemeden).
 * Router, başka bir görünüme geçerken bunu kullanır.
 * @returns {boolean} mod açık mıydı
 */
export function clearRandomMode() {
    if (!state.randomMode) return false;
    state.randomMode = false;
    state.randomSlug = null;
    document.body.classList.remove('random-mode');
    return true;
}

export function exitRandomMode() {
    if (!clearRandomMode()) return;

    if (state.activeCardClone) closeCommentView();
    if (location.pathname !== '/') history.pushState(null, '', '/');

    updatePageMeta();
    state.currentPage = 1;
    fetchWords(state.currentPage);
}

/* --- Kurulum --- */

export function setupRandomWord() {
    const btn = document.getElementById('randomWordBtn');
    if (btn) {
        btn.innerHTML = DICE_ICON;
        btn.addEventListener('click', rollDice);
    }

    // Logo kartı: rastgele moddan (ve diğer görünümlerden) ana sayfaya dönüş
    const logo = document.querySelector('.logo-card');
    logo?.addEventListener('click', () => {
        if (state.randomMode) {
            exitRandomMode();
        } else {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    });
}
