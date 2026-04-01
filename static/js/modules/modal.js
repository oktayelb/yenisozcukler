/* --- MODAL MANAGEMENT --- */
import { state } from './state.js';

export function openModal(id) {
    const m = document.getElementById(id);
    if (m) m.classList.add('show');
    if (id === 'aboutModal') document.body.style.overflow = 'hidden';
}

export function closeModal(id, force = false, e = null) {
    const m = document.getElementById(id);
    if (force || (e && e.target === m)) {
        m.classList.remove('show');
        if (id === 'aboutModal') document.body.style.overflow = '';
        if (id === 'authModal') document.getElementById('authErrorMsg').style.display = 'none';

        if (id === 'addExampleModal') {
            state.wordIdForExample = null;
        }
    }
}

export const closeAuthModal = (e, f) => closeModal('authModal', f, e);
export const showAboutInfo = () => openModal('aboutModal');
export const closeAboutInfo = (e, f) => closeModal('aboutModal', f, e);
export const closeProfileModal = (e, f) => closeModal('profileModal', f, e);
export const closeEditProfileModal = (e, f) => closeModal('editProfileModal', f, e);
export const closeMyWordsModal = (e, f) => closeModal('myWordsModal', f, e);
