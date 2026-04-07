/* ========================================
   app.js - Entry Point (ES Module)
   Imports all modules and wires up event listeners.
   ======================================== */

import { state, isUserLoggedIn } from './modules/state.js';
import { updateCount } from './modules/utils.js';
import { setupTheme } from './modules/theme.js';
import { setupSortBar } from './modules/sort.js';
import { openModal, closeModal, closeAuthModal, showAboutInfo, closeAboutInfo, closeProfileModal, closeEditProfileModal, closeMyWordsModal } from './modules/modal.js';
import { toggleAuthMode, setupAuthTriggers, handleAuthSubmit, handleLogout, openAuthModal } from './modules/auth.js';
import { fetchCategories } from './modules/categories.js';
import { fetchWords, clearCategoryFilter, loadMoreWords, executeSearch, focusContributionForm } from './modules/feed.js';
import { toggleContributionForm, initTopAppBar, handleWordSubmit } from './modules/form.js';
import { submitExample } from './modules/example.js';
import { closeCommentView } from './modules/comments.js';
import { openProfileModal, openMyWordsModal, openEditProfileModal, handleChangeUsername, handleChangePassword, backToProfile } from './modules/profile.js';
import { setupChallengeBox, closeChallengeDiscussion } from './modules/challenge.js';
import { initNotifications, openNotificationsModal, closeNotificationsModal, notifBackToProfile, loadMoreNotifications } from './modules/notifications.js';
import { initRouter } from './modules/router.js';

/* --- INIT --- */
document.addEventListener('DOMContentLoaded', () => {
    ['mainTitle', 'subtitleText'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('loaded');
    });

    setupAllEventListeners();

    setupAuthTriggers();
    setupSortBar();
    setupTheme();
    initTopAppBar();
    setupChallengeBox();
    initNotifications();
    fetchCategories();

    // Always fetch the home feed — it's the background content
    // that shows when overlays close or user navigates back to /
    fetchWords(state.currentPage);

    // Init router — handles non-home routes (e.g. /sozcuk/5/)
    // by opening the correct overlay after the feed loads
    initRouter();
});

/* --- ALL EXTRACTED EVENT BINDINGS --- */
function setupAllEventListeners() {
    // Backdrop / Overlays
    document.getElementById('modalBackdrop')?.addEventListener('click', () => {
        closeCommentView();
        closeChallengeDiscussion();
    });

    // About Modal
    document.getElementById('aboutModal')?.addEventListener('click', closeAboutInfo);
    document.getElementById('aboutCloseBtn')?.addEventListener('click', (e) => closeAboutInfo(e, true));
    document.getElementById('headerAboutBtn')?.addEventListener('click', showAboutInfo);

    // Auth Modal
    document.getElementById('authModal')?.addEventListener('click', closeAuthModal);
    document.getElementById('authCloseBtn')?.addEventListener('click', (e) => closeAuthModal(e, true));
    document.getElementById('tabLogin')?.addEventListener('click', () => toggleAuthMode('login'));
    document.getElementById('tabRegister')?.addEventListener('click', () => toggleAuthMode('register'));
    document.getElementById('authSubmitBtn')?.addEventListener('click', handleAuthSubmit);

    // Shared Triggers
    document.querySelectorAll('.auth-login-trigger').forEach(btn => {
        btn.addEventListener('click', () => openModal('authModal'));
    });
    document.querySelectorAll('.auth-profile-trigger').forEach(btn => {
        btn.addEventListener('click', () => openProfileModal(state.currentUserUsername));
    });

    // Header / Form actions
    document.getElementById('topAddWordBtn')?.addEventListener('click', focusContributionForm);
    document.getElementById('formCollapseBtn')?.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleContributionForm();
    });
    document.getElementById('formHeaderToggle')?.addEventListener('click', toggleContributionForm);
    document.getElementById('contributionForm')?.addEventListener('submit', handleWordSubmit);
    document.getElementById('contributionCard')?.addEventListener('click', function() {
        if (this.classList.contains('collapsed')) toggleContributionForm();
    });

    // Form Interactions / Validations
    const inputWord = document.getElementById('inputWord');
    if (inputWord) {
        inputWord.addEventListener('input', function() { this.value = this.value.replace(/^\s+/g, ''); });
    }

    const inputDef = document.getElementById('inputDef');
    if (inputDef) {
        inputDef.addEventListener('input', function() { updateCount(this); });
    }

    // Filter, Feed and Search logic
    document.getElementById('clearFilterBtn')?.addEventListener('click', clearCategoryFilter);
    document.getElementById('loadMoreBtn')?.addEventListener('click', loadMoreWords);

    const searchInput = document.getElementById('mainSearchInput');
    const clearSearchBtn = document.getElementById('clearSearchBtn');

    if (searchInput) {
        let searchTimeout = null;
        searchInput.addEventListener('input', (e) => {
            const val = e.target.value;
            if (val.length > 0) {
                if (clearSearchBtn) clearSearchBtn.style.display = 'block';
            } else {
                if (clearSearchBtn) clearSearchBtn.style.display = 'none';
            }

            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                executeSearch(val);
            }, 500);
        });

        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(searchTimeout);
                executeSearch(searchInput.value);
            }
        });
    }

    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            if (searchInput) searchInput.value = '';
            clearSearchBtn.style.display = 'none';
            executeSearch('');
        });
    }

    // Add Example Modal
    document.getElementById('addExampleModal')?.addEventListener('click', (e) => closeModal('addExampleModal', false, e));
    document.getElementById('addExampleCloseBtn')?.addEventListener('click', () => closeModal('addExampleModal', true));
    document.getElementById('submitExampleBtn')?.addEventListener('click', submitExample);

    // Profile Modal
    document.getElementById('profileModal')?.addEventListener('click', closeProfileModal);
    document.getElementById('profileCloseBtn')?.addEventListener('click', (e) => closeProfileModal(e, true));
    document.getElementById('myWordsStatBtn')?.addEventListener('click', openMyWordsModal);
    document.getElementById('editProfileBtn')?.addEventListener('click', openEditProfileModal);
    document.getElementById('logoutBtn')?.addEventListener('click', handleLogout);

    // My Words Modal
    document.getElementById('myWordsModal')?.addEventListener('click', closeMyWordsModal);
    document.getElementById('myWordsCloseBtn')?.addEventListener('click', (e) => closeMyWordsModal(e, true));
    document.getElementById('myWordsProfileBtn')?.addEventListener('click', () => {
        openProfileModal();
        document.getElementById('myWordsModal').classList.remove('show');
    });

    // Edit Profile Modal
    document.getElementById('editProfileModal')?.addEventListener('click', closeEditProfileModal);
    document.getElementById('editProfileCloseBtn')?.addEventListener('click', (e) => closeEditProfileModal(e, true));
    document.getElementById('saveUsernameBtn')?.addEventListener('click', handleChangeUsername);
    document.getElementById('savePasswordBtn')?.addEventListener('click', handleChangePassword);
    document.getElementById('backToProfileBtn')?.addEventListener('click', backToProfile);

    // Notifications Modal
    document.getElementById('openNotificationsBtn')?.addEventListener('click', openNotificationsModal);
    document.getElementById('notificationsModal')?.addEventListener('click', (e) => closeNotificationsModal(e));
    document.getElementById('notifCloseBtn')?.addEventListener('click', (e) => closeNotificationsModal(e, true));
    document.getElementById('notifLoadMoreBtn')?.addEventListener('click', loadMoreNotifications);
    document.getElementById('notifBackToProfileBtn')?.addEventListener('click', notifBackToProfile);
}
