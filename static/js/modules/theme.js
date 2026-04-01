/* --- THEME --- */
import { THEME_KEY } from './state.js';

export function setupTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    const btn = document.getElementById('darkModeToggle');
    const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (saved === 'dark' || (!saved && sysDark)) {
        document.body.classList.add('dark-mode');
        btn.textContent = 'Aydınlık Mod';
    } else {
        btn.textContent = 'Karanlık Mod';
    }

    btn.addEventListener('click', () => {
        const isDark = document.body.classList.toggle('dark-mode');
        localStorage.setItem(THEME_KEY, isDark ? 'dark' : 'light');
        btn.textContent = isDark ? 'Aydınlık Mod' : 'Karanlık Mod';
    });
}
