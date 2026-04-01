/* --- SORTING --- */
import { state } from './state.js';
import { fetchWords } from './feed.js';

export function setupSortBar() {
    const bars = document.querySelectorAll('.sort-bar');
    if (!bars.length) return;

    bars.forEach(bar => {
        bar.style.cursor = 'pointer';

        bar.addEventListener('click', (e) => {
            if (!e.target.closest('.sort-btn')) {
                bar.classList.toggle('collapsed');
            }
        });

        const buttons = bar.querySelectorAll('.sort-btn');
        buttons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const sortVal = btn.getAttribute('data-sort');
                changeSort(sortVal);
                bar.classList.add('collapsed');
            });
        });
    });

    updateSortButtonsActive();
}

function changeSort(sortVal) {
    if (!sortVal || sortVal === state.currentSort) return;

    state.currentSort = sortVal;
    updateSortButtonsActive();

    state.currentPage = 1;
    fetchWords(state.currentPage);
}

function updateSortButtonsActive() {
    const buttons = document.querySelectorAll('.sort-btn');
    buttons.forEach(btn => {
        const sortVal = btn.getAttribute('data-sort');
        if (sortVal === state.currentSort) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}
