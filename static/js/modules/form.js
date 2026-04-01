/* --- FORM TOGGLE & WORD SUBMISSION --- */
import { state, isUserLoggedIn } from './state.js';
import { apiRequest, showCustomAlert, updateCount } from './utils.js';

export function toggleContributionForm() {
    const card = document.getElementById('contributionCard');
    const title = document.getElementById('contributionTitle');

    if (card) {
        const isExpanded = card.classList.contains('expanded');

        if (isExpanded) {
            card.classList.remove('expanded');
            card.classList.add('collapsed');
            if (title) title.innerHTML = 'Katkıda Bulun <span class="toggle-icon">+</span>';
        } else {
            card.classList.remove('collapsed');
            card.classList.add('expanded');
            if (title) title.innerHTML = '';
        }
    }
}

export function initTopAppBar() {
    const bar = document.getElementById('topAppBar');
    if (!bar) return;

    const onScroll = () => {
        if (window.scrollY > 150) {
            bar.classList.add('is-visible');
        } else {
            bar.classList.remove('is-visible');
        }
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
}

export function handleWordSubmit(e) { e.preventDefault(); submitWord(); }

export async function submitWord() {
    const w = document.getElementById('inputWord').value.trim();
    const d = document.getElementById('inputDef').value.trim();
    const ex = document.getElementById('inputExample').value.trim();
    const et = document.getElementById('inputEtymology').value.trim();
    const n = isUserLoggedIn ? state.currentUserUsername : 'Anonim';

    const btn = document.querySelector(".form-card button[type='submit']");

    if (!w || !d || !ex || !et) return showCustomAlert("Lütfen tüm alanları doldurun.", "error");

    if (d.length > 300) return showCustomAlert("Tanım çok uzun.", "error");
    if (ex.length > 200) return showCustomAlert("Örnek cümle çok uzun.", "error");
    if (et.length > 200) return showCustomAlert("Köken bilgisi çok uzun.", "error");

    btn.disabled = true; btn.innerText = "Kaydediliyor...";
    try {
        await apiRequest('/api/word', 'POST', {
            word: w,
            definition: d,
            example: ex,
            etymology: et,
            nickname: n,
            category_ids: Array.from(state.selectedFormCategories)
        });

        await playSubmitEnvelopeAnimation(btn);

        document.getElementById('inputWord').value = '';
        document.getElementById('inputDef').value = '';
        document.getElementById('inputExample').value = '';
        document.getElementById('inputEtymology').value = '';
        updateCount({ value: '' });

        state.selectedFormCategories.clear();
        document.querySelectorAll('.category-pill.selected').forEach(el => el.classList.remove('selected'));

        showCustomAlert("Sözcük gönderildi (Onay bekleniyor)!");

    } catch (e) { showCustomAlert(e.message, "error"); }
    finally {
        btn.disabled = false;
        btn.innerText = "Sözcüğü ekle";
        btn.style.color = '';
    }
}

/* --- SUBMIT ENVELOPE ANIMATION --- */
function playSubmitEnvelopeAnimation(btn) {
    return new Promise(resolve => {
        const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (prefersReduced) { resolve(); return; }

        const scrollX = window.scrollX;
        const scrollY = window.scrollY;

        const fields = ['inputWord', 'inputDef', 'inputEtymology', 'inputExample'];
        const snapshots = [];
        const cachedPlaceholders = {};

        fields.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                cachedPlaceholders[id] = el.getAttribute('placeholder') || '';
                el.setAttribute('placeholder', '');

                if (el.value.trim()) {
                    const rect = el.getBoundingClientRect();
                    snapshots.push({
                        text: el.value.trim(),
                        left: rect.left + scrollX,
                        top: rect.top + scrollY
                    });
                    el.value = '';
                }
            }
        });
        updateCount({ value: '' });

        btn.style.color = 'transparent';

        if (!snapshots.length) {
            restoreFields();
            resolve();
            return;
        }

        const btnRect = btn.getBoundingClientRect();
        const btnAbsoluteCX = btnRect.left + scrollX + btnRect.width / 2;
        const btnAbsoluteCY = btnRect.top + scrollY + btnRect.height / 2;

        const envelope = document.createElement('div');
        envelope.className = 'submit-envelope';
        envelope.innerHTML = `
        <svg viewBox="0 0 60 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M2 16L30 32L58 16V44C58 45.1046 57.1046 46 56 46H4C2.89543 46 2 45.1046 2 44V16Z" fill="var(--card-bg)" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round"/>
            <path d="M2 46L24 30" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>
            <path d="M58 46L36 30" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>
            <path class="env-flap" d="M2 16L30 2L58 16" fill="var(--card-bg)" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>`;

        envelope.style.left = (btnAbsoluteCX - 30) + 'px';
        envelope.style.top = (btnAbsoluteCY - 24) + 'px';
        envelope.style.transform = 'scale(0.8) translateY(20px)';
        envelope.style.opacity = '0';
        document.body.appendChild(envelope);

        const flyingTexts = snapshots.map(s => {
            const span = document.createElement('div');
            span.className = 'submit-flying-text';
            span.textContent = s.text;

            span.style.left = (s.left + 14) + 'px';
            span.style.top = (s.top + 14) + 'px';

            document.body.appendChild(span);
            return { el: span, startX: s.left + 14, startY: s.top + 14 };
        });

        function restoreFields() {
            fields.forEach(id => {
                const el = document.getElementById(id);
                if (el && cachedPlaceholders[id] !== undefined) {
                    el.setAttribute('placeholder', cachedPlaceholders[id]);
                }
            });
            btn.style.color = '';
        }

        requestAnimationFrame(() => {
            requestAnimationFrame(() => {

                envelope.style.transition = 'transform 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275), opacity 0.4s ease';
                envelope.style.transform = 'scale(1) translateY(0)';
                envelope.style.opacity = '1';

                setTimeout(() => {
                    flyingTexts.forEach((item, i) => {
                        const itemCX = item.startX + item.el.offsetWidth / 2;
                        const itemCY = item.startY + item.el.offsetHeight / 2;

                        const dx = btnAbsoluteCX - itemCX;
                        const dy = btnAbsoluteCY - itemCY;

                        setTimeout(() => {
                            item.el.style.transition = 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.4s ease 0.1s';
                            item.el.style.transform = `translate(${dx}px, ${dy}px) scale(0.1)`;
                            item.el.style.opacity = '0';
                        }, i * 150);
                    });

                    const arriveTime = (flyingTexts.length - 1) * 150 + 500;

                    setTimeout(() => {
                        flyingTexts.forEach(item => item.el.remove());

                        const flap = envelope.querySelector('.env-flap');
                        if (flap) {
                            flap.style.transform = 'rotateX(180deg)';
                        }

                        setTimeout(() => {
                            const logo = document.getElementById('mainTitle');
                            let targetDx = 0;
                            let targetDy = -200;

                            if (logo) {
                                const logoRect = logo.getBoundingClientRect();
                                const logoCX = logoRect.left + scrollX + logoRect.width / 2;
                                const logoCY = logoRect.top + scrollY + logoRect.height / 2;
                                targetDx = logoCX - btnAbsoluteCX;
                                targetDy = logoCY - btnAbsoluteCY;
                            }

                            envelope.style.transition = 'transform 1.1s cubic-bezier(0.25, 0.1, 0.25, 1), opacity 0.8s ease 0.3s';
                            envelope.style.transform = `translate(${targetDx}px, ${targetDy}px) scale(0.25) rotate(-15deg)`;
                            envelope.style.opacity = '0';

                            setTimeout(() => {
                                envelope.remove();
                                if (logo) {
                                    logo.style.transition = 'transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)';
                                    logo.style.transform = 'scale(1.1)';
                                    setTimeout(() => logo.style.transform = '', 300);
                                }
                                restoreFields();
                                resolve();
                            }, 1100);

                        }, 300);

                    }, arriveTime);

                }, 350);

            });
        });
    });
}
