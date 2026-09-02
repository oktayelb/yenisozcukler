/* --- HEADER DROPDOWN MENU --- */

export function setupHeaderMenu() {
    const menu = document.getElementById('aboutMenu');
    const btn = document.getElementById('aboutMenuBtn');
    if (!menu || !btn) return;

    const setOpen = (open) => {
        menu.classList.toggle('open', open);
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    };

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        setOpen(!menu.classList.contains('open'));
    });

    // Each item opens its own modal (wired in app.js); we only collapse the menu.
    menu.querySelectorAll('.header-menu-item').forEach(item => {
        item.addEventListener('click', () => setOpen(false));
    });

    document.addEventListener('click', (e) => {
        if (!menu.contains(e.target)) setOpen(false);
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') setOpen(false);
    });
}
