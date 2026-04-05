# Static Files Reference

This document describes every file under `static/`, what it does, and how the JavaScript modules depend on each other.

---

## CSS (`static/css/`)

All stylesheets are imported through `style.css` in cascade order.

| File | Role |
|---|---|
| **style.css** | Master stylesheet. Only file referenced in HTML. Imports all others in order: variables -> layout -> components -> modals -> responsive. |
| **variables.css** | CSS custom properties: fonts (`--font-heading`, `--font-body`), spacing, z-index layers (1-9999), and full color palette for both light and dark modes. |
| **layout.css** | Structural skeleton: body defaults, scrollbar styling, `.app-wrapper` max-width (1200px), header, and top app bar layout. |
| **components.css** | Reusable UI elements: `.spinner`, `.word-card` (hover/animation states), buttons, form inputs, sort bar, category pills, vote controls, filter banners, notification alerts, contribution form, and the envelope submit animation. |
| **modals.css** | All modal/overlay styles: `.modal-backdrop`, `.auth-box`, `.about-box`, profile/edit-profile/my-words modals, comment detail view (`.full-comment-view`), add-example modal, and challenge discussion view. Scale/fade transitions. |
| **responsive.css** | Media queries for screens <= 900px. Adjusts form layouts, header sizing, modal dimensions, card spacing, and button sizes for mobile. |

**Load order matters** because later files rely on variables defined in `variables.css` and override component styles in `responsive.css`.

---

## JavaScript (`static/js/`)

### Entry Point

| File | Role |
|---|---|
| **app.js** | Single entry point loaded by `index.html` as `<script type="module">`. Imports every module, runs `DOMContentLoaded` initialization, and wires all event listeners to DOM elements. Contains no business logic itself. |

### Modules (`static/js/modules/`)

| File | Role |
|---|---|
| **state.js** | Shared application state. Exports constants (`THEME_KEY`, `ITEMS_PER_PAGE`, `COMMENTS_PER_PAGE`, `CHALLENGE_COMMENTS_PER_PAGE`), a mutable `state` object holding all page-level variables (current page, sort, filters, active modals, auth mode, etc.), `isUserLoggedIn` (read from DOM), and a shared `pendingVotes` map for vote debouncing. |
| **utils.js** | Pure utility functions with no dependencies: `escapeHTML` (XSS prevention), `getCSRFToken` (reads cookie), `showCustomAlert` (toast notifications), `apiRequest` (fetch wrapper with CSRF, JSON parsing, error handling), `updateCount` (character counter for textarea). |
| **theme.js** | Reads saved theme from `localStorage`, applies dark/light mode to `<body>`, and binds the toggle button. |
| **sort.js** | Sets up sort bar click handlers, tracks active sort in `state.currentSort`, and triggers a feed refetch on change. |
| **modal.js** | Generic `openModal(id)` / `closeModal(id)` that add/remove `.show` class. Also exports shorthand close helpers for each specific modal (auth, about, profile, edit-profile, my-words). |
| **auth.js** | Login/register/logout flow: form validation, Turnstile CAPTCHA check, API calls to `/api/login`, `/api/register`, `/api/logout`. Also sets up the author trigger (click username -> open profile or auth modal). |
| **categories.js** | Fetches categories from `/api/categories`, renders selectable pills in the contribution form, and manages the `selectedFormCategories` set in state. |
| **voting.js** | Creates vote button UI (thumbs up/down + score) for word and comment cards. Implements optimistic UI updates with 500ms debounce before sending the actual API request. Rolls back on failure. |
| **cards.js** | Builds a complete word card DOM element: title, etymology, definition, example, category tags, author badge, comment count hint, and floating vote controls. Binds click handlers that open comment view, profile, tag filter, or add-example modal. |
| **feed.js** | Fetches paginated word list from `/api/words` with sort/filter/search params. Manages the "Load More" button, search input debounce, category filter banner, and the contribution form focus shortcut. Uses `cards.js` to render each word. |
| **form.js** | Contribution form expand/collapse toggle, word submission to `/api/word` (with validation), and the envelope fly-away animation that plays on successful submit. |
| **example.js** | "Add Example" modal for words that lack one. Submits to `/api/example` and live-updates the card in the DOM without a page reload. |
| **comments.js** | Opens the full-screen comment detail view for a word. Loads paginated comments from `/api/comments/{id}`, renders each with author badge and vote controls, and handles new comment submission. |
| **profile.js** | Profile modal (stats: word count, comment count, total score), "My Words" modal (fetches user's words and renders them as cards), edit profile modal (username change via `/api/username`, password change via `/api/password`). |
| **challenge.js** | Translation Challenge feature: collapsible challenge box, fetches challenges from `/api/challenges`, renders challenge items, challenge suggestion form, discussion view with its own comment system and vote controls (separate from word comments). |

---

## JS Dependency Graph

Arrows read as "imports from". Every module is ultimately imported by `app.js`.

```
app.js
 ├── state
 ├── utils
 ├── theme ──────────> state
 ├── sort ───────────> state, feed
 ├── modal ──────────> state
 ├── auth ───────────> state, utils, modal, profile, form
 ├── categories ─────> state, utils
 ├── voting ─────────> state, utils, auth
 ├── cards ──────────> state, voting, comments, profile, example, feed
 ├── feed ───────────> state, utils, cards, form
 ├── form ───────────> state, utils
 ├── example ────────> state, utils, modal
 ├── comments ───────> state, utils, voting, auth, profile
 ├── profile ────────> state, utils, modal, feed
 └── challenge ──────> state, utils, auth, profile
```

### Circular Dependencies

These cycles exist but are safe because all cross-references are accessed only inside functions at runtime (never during module evaluation), and ES module imports are live bindings:

- **feed <-> cards**: feed imports `createCardElement`, cards imports `handleTagClick`
- **feed <-> cards -> profile -> feed**: profile imports `appendCards` from feed
- **feed <-> cards -> comments -> profile -> feed**: comments imports `openProfileModal`

### Shared State Flow

```
state.js (single source of truth)
   │
   ├── Read by: every module
   ├── Written by: sort, auth, feed, form, categories, comments, profile, challenge, modal, example
   │
   └── state object properties:
         currentPage, currentSort, currentSearchQuery     ← feed/sort control
         activeCategorySlug, allCategories                 ← category filtering
         selectedFormCategories                             ← contribution form
         currentAuthMode                                   ← auth modal
         currentWordId, activeCardClone, currentCommentPage ← comment detail view
         currentProfileUser, currentUserUsername            ← profile modals
         wordIdForExample                                  ← add-example modal
         challengeExpanded, activeChallengeView,            ← challenge feature
         currentChallengeId, currentChallengeCommentPage
```

---

## Other Static Files

| File | Role |
|---|---|
| **favicon.ico** | Site favicon served at `/static/favicon.ico`. |
