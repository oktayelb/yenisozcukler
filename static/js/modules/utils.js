/* --- UTILS --- */

export function escapeHTML(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

export function getCSRFToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : null;
}

export function showCustomAlert(message, type = 'success') {
    const container = document.getElementById('notificationContainer');
    const alertDiv = document.createElement('div');
    alertDiv.className = `custom-alert custom-alert-${type}`;
    alertDiv.textContent = message;
    alertDiv.addEventListener('click', () => alertDiv.remove());
    container.prepend(alertDiv);

    setTimeout(() => alertDiv.classList.add('show'), 10);
    setTimeout(() => {
        alertDiv.classList.remove('show');
        setTimeout(() => alertDiv.remove(), 500);
    }, 4000);
}

export async function apiRequest(url, method = 'GET', body = null) {
    const headers = { 'Content-Type': 'application/json' };
    const csrfToken = getCSRFToken();

    if (csrfToken) {
        headers['X-CSRFToken'] = csrfToken;
    }

    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(url, options);

    const contentType = response.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
        throw new Error("Sunucu hatası (Invalid JSON).");
    }

    const data = await response.json();
    if (response.status === 429) throw new Error(data.error || "Çok fazla istek gönderdiniz.");
    if (!response.ok) throw new Error(data.error || "İşlem başarısız.");
    return data;
}

export function updateCount(field) {
    const count = field.value.length;
    document.getElementById('charCount').innerText = `${count} / 300`;
}

const DEFAULT_TITLE = 'Yeni Sözcükler - Türkçeye Yeni Sözcükler Türet';
const DEFAULT_DESCRIPTION = 'Yeni Türkçe sözcükler türetin, paylaşın ve oylayın. Türk dilinin gelişmesine katkıda bulunun.';
const BASE_URL = 'https://yenisozcukler.com';

export function updatePageMeta(title, description) {
    const finalTitle = title || DEFAULT_TITLE;
    const finalDesc = description || DEFAULT_DESCRIPTION;
    const currentUrl = BASE_URL + window.location.pathname;

    // Update Title
    document.title = finalTitle;
    
    // Update Meta Tags
    const updateMetaTag = (selector, attr, content) => {
        let tag = document.querySelector(selector);
        if (tag) {
            tag.setAttribute(attr, content);
        }
    };

    updateMetaTag('meta[name="description"]', 'content', finalDesc);
    
    // Update Open Graph and Twitter tags to prevent duplicate content issues in SPA
    updateMetaTag('meta[property="og:title"]', 'content', finalTitle);
    updateMetaTag('meta[property="og:description"]', 'content', finalDesc);
    updateMetaTag('meta[property="og:url"]', 'content', currentUrl);
    
    updateMetaTag('meta[name="twitter:title"]', 'content', finalTitle);
    updateMetaTag('meta[name="twitter:description"]', 'content', finalDesc);

    // Update Canonical URL
    updateMetaTag('link[rel="canonical"]', 'href', currentUrl);
}