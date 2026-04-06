/* === CLIENT-SIDE ROUTER (pushState) ===
 *
 * Routes:
 *   /                  → home feed
 *   /sozcuk/<id>/      → word detail (comment overlay)
 *   /kategori/<slug>/  → category-filtered feed
 *
 * The site stays single-page: navigateTo() updates the URL bar
 * via pushState and calls the appropriate view handler — no reload.
 * On direct load / refresh, Django serves index.html (the SPA shell)
 * and this router reads the URL to restore the correct view.
 */

import { state } from './state.js';
import { apiRequest, updatePageMeta } from './utils.js';
import { fetchWords } from './feed.js';
import { animateAndOpenCommentView, closeCommentView } from './comments.js';

/**
 * True while the router is dispatching a route handler.
 * Other modules check this to avoid double-pushing URLs.
 */
export let isRouterDispatching = false;

// ── Route matching ──────────────────────────────────────────────

function matchRoute(path) {
    let m;
    m = path.match(/^\/sozcuk\/(\d+)\/?$/);
    if (m) return { name: 'word', id: parseInt(m[1], 10) };

    m = path.match(/^\/kategori\/([\w-]+)\/?$/);
    if (m) return { name: 'category', slug: m[1] };

    return { name: 'home' };
}

// ── Public API ──────────────────────────────────────────────────

/** Push a new URL and handle the route. No page reload. */
export function navigateTo(url, { replace = false } = {}) {
    if (url === location.pathname) return;
    if (replace) history.replaceState(null, '', url);
    else history.pushState(null, '', url);
    dispatch();
}

// ── Route dispatcher ────────────────────────────────────────────

function dispatch() {
    isRouterDispatching = true;
    try {
        const route = matchRoute(location.pathname);

        switch (route.name) {
            case 'word':
                handleWordRoute(route.id);
                break;
            case 'category':
                handleCategoryRoute(route.slug);
                break;
            default:
                handleHomeRoute();
                break;
        }
    } finally {
        isRouterDispatching = false;
    }
}

// ── Route handlers ──────────────────────────────────────────────

function handleHomeRoute() {
    // Close word detail overlay if open
    if (state.activeCardClone) closeCommentView();

    // If we were filtering by category, clear it and re-fetch
    if (state.activeCategorySlug) {
        state.activeCategorySlug = null;
        state.currentPage = 1;

        const banner = document.getElementById('activeFilterBanner');
        if (banner) banner.style.display = 'none';

        updatePageMeta();
        fetchWords(state.currentPage);
    }
}

async function handleWordRoute(wordId) {
    // Already showing this word
    if (state.activeCardClone && state.currentWordId === wordId) return;

    // Close existing overlay first
    if (state.activeCardClone) {
        closeCommentView();
        await new Promise(r => setTimeout(r, 420));
    }

    // Try clicking an existing card in the DOM (avoids an extra API call)
    const card = document.querySelector(`.word-card[data-id="${wordId}"]`);
    if (card) {
        card.click();
        return;
    }

    // Card not in DOM — fetch word data from API and open overlay
    try {
        const data = await apiRequest(`/api/word/${wordId}`);
        const w = data.word;
        updatePageMeta(
            `${w.word} - Yeni Sözcükler`,
            w.def || w.definition
        );
        animateAndOpenCommentView(
            null, w.id, w.word,
            w.def || w.definition,
            w.example || '',
            w.etymology || '',
            true   // modal mode (no originating card)
        );
    } catch {
        // Word doesn't exist or not approved — go home
        navigateTo('/', { replace: true });
    }
}

function handleCategoryRoute(slug) {
    if (state.activeCardClone) closeCommentView();

    // Already filtering this category
    if (state.activeCategorySlug === slug) return;

    state.activeCategorySlug = slug;
    state.currentPage = 1;

    window.scrollTo({ top: 0, behavior: 'smooth' });

    // Use full category info if available
    const cat = state.allCategories.find(c => c.slug === slug);
    const name = cat ? cat.name : slug;
    const description = cat ? cat.description : '';

    // Update filter banner
    const banner = document.getElementById('activeFilterBanner');
    const nameDisplay = document.getElementById('filterNameDisplay');
    const descDisplay = document.getElementById('filterDescDisplay');
    if (banner) {
        banner.style.display = 'flex';
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

    updatePageMeta(
        `${name} - Yeni Sözcükler`,
        description || `${name} kategorisindeki yeni Türkçe sözcükler.`
    );

    fetchWords(state.currentPage);
}

// ── Initialization ──────────────────────────────────────────────

/**
 * Call once from app.js after DOMContentLoaded.
 * Returns the initial route so app.js knows whether to fetch the
 * default feed or let the router handle it.
 */
export function initRouter() {
    // Back / forward button support
    window.addEventListener('popstate', () => dispatch());

    const route = matchRoute(location.pathname);

    // For category routes, set the filter SYNCHRONOUSLY before returning.
    // This way the fetchWords() call in app.js already uses the correct
    // category filter, avoiding a wasted unfiltered fetch.
    if (route.name === 'category') {
        state.activeCategorySlug = route.slug;
    }

    if (route.name !== 'home') {
        // Non-home route on initial load — dispatch after a short
        // delay so the DOM, categories, and initial feed are ready
        setTimeout(() => dispatch(), 350);
    }

    return route;
}
