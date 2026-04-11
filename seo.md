# SEO Optimization

This document describes the SEO optimizations implemented for yenisozcukler.com.

## Dynamic Rendering (Bot vs Browser)

All public routes serve two different responses from the same URL:

- **Bots** (Googlebot, social media crawlers, etc.) receive lightweight, fully-rendered HTML with semantic markup, meta tags, and crawlable links. No JS required.
- **Browsers** receive the SPA shell (`index.html`). The JS router handles navigation without page reloads.

Bot detection uses both specific identifiers (`googlebot`, `facebookexternalhit`, etc.) and generic patterns (`bot`, `crawler`, `spider`, `fetch`, `preview`). All dynamic rendering responses include `Vary: User-Agent` to prevent CDN cache poisoning between bot and browser responses.

### Routes with dynamic rendering

| Route | Bot response | Browser response |
|---|---|---|
| `/` | `bot_index.html` — list of 50 recent words as `<a>` links | SPA shell |
| `/sozcuk/<id>/` | `word_detail.html` — full word page with structured data | SPA shell (router opens word overlay) |
| `/kategori/<slug>/` | `bot_category.html` — filtered word list with category info | SPA shell (router applies category filter) |

## Client-Side Router (pushState)

The SPA uses the History API to maintain clean URLs without page reloads:

- Clicking a word card pushes `/sozcuk/<id>/` to the address bar
- Clicking a category tag navigates to `/kategori/<slug>/`
- Closing a word overlay restores the previous URL (`/` or `/kategori/...`)
- Back/forward buttons work via `popstate` event handling
- Direct URL access and page refresh work via Django catch-all routes

The router lives in `static/js/modules/router.js`.

## Meta Tags

### Static (home page — `head.html`)
- `<title>`, `<meta description>`
- Open Graph tags (`og:title`, `og:description`, `og:url`, `og:type`, `og:site_name`)
- Twitter Card tags
- Canonical URL

### Dynamic (JS-side — `utils.js:updatePageMeta`)
When the SPA navigates between views, the following tags are updated in real-time:
- `document.title`
- `<meta name="description">`
- All Open Graph and Twitter Card tags
- `<link rel="canonical">`

### Per-word (SSR — `word_detail.html`)
Bot-served word pages include per-word meta tags, OG tags, Twitter cards, and canonical URLs.

## Structured Data (JSON-LD)

Word detail pages served to bots include `schema.org/DefinedTerm` structured data:

```json
{
    "@context": "https://schema.org",
    "@type": "DefinedTerm",
    "name": "word",
    "description": "definition",
    "termCode": "etymology"
}
```

Values use Django's `|escapejs` filter to produce valid JSON inside `<script>` tags.

## Crawlable Links (`<a href>`)

All key navigation elements in the JS-rendered feed use proper `<a>` tags with `href` attributes:

- **Word titles**: `<a href="/sozcuk/<id>/">`
- **Category tags**: `<a href="/kategori/<slug>/">`
- **Comment links**: `<a href="/sozcuk/<id>/">`

JavaScript intercepts clicks via `preventDefault()` for SPA behavior, but crawlers that don't execute JS can still discover and follow the links.

## robots.txt

Served at `/robots.txt`:
- Allows all public content
- Disallows `/api/` (JSON endpoints) and `/admin/`
- Points to sitemap (for future implementation)

## Files

### Created
- `templates/word_detail.html` — SSR word page for bots
- `templates/bot_index.html` — SSR home page for bots
- `templates/bot_category.html` — SSR category page for bots
- `static/js/modules/router.js` — pushState client-side router
- `static/robots.txt`

### Modified
- `core/views.py` — dynamic rendering views, bot detection, single-word API
- `core/urls.py` — SEO routes, SPA catch-all, robots.txt
- `templates/head.html` — meta tags, OG, Twitter cards, canonical
- `static/js/app.js` — router initialization
- `static/js/modules/cards.js` — `<a>` tags, URL pushing
- `static/js/modules/comments.js` — URL restoration on close
- `static/js/modules/feed.js` — URL updates on filter/search
- `static/js/modules/utils.js` — `updatePageMeta()` helper
