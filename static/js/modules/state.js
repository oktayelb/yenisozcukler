/* --- GLOBAL VARIABLES & SETTINGS --- */

export const THEME_KEY = 'userTheme';
export const ITEMS_PER_PAGE = 20;
export const COMMENTS_PER_PAGE = 10;
export const CHALLENGE_COMMENTS_PER_PAGE = 10;

export const isUserLoggedIn = document.body.getAttribute('data-user-auth') === 'true';

export const state = {
    currentWordId: null,
    activeCardClone: null,
    currentPage: 1,
    currentCommentPage: 1,
    isLoading: false,
    currentProfileUser: null,
    wordIdForExample: null,
    currentSearchQuery: '',
    activeCategorySlug: null,
    allCategories: [],
    selectedFormCategories: new Set(),
    currentSort: 'date_desc',
    currentAuthMode: 'login',
    currentUserUsername: document.body.getAttribute('data-username'),
    // Challenge
    challengeExpanded: false,
    activeChallengeView: null,
    currentChallengeId: null,
    currentChallengeCommentPage: 1,
};

export const pendingVotes = {};
