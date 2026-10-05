// Themes, in the order they appear in the masthead. `bg`/`accent` drive the swatch.
const THEMES = {
    dark:   { name: 'Dark',   bg: '#0b0b0a', accent: '#e0603f', required_streak: 0 },
    light:  { name: 'Light',  bg: '#f3f1eb', accent: '#c4432a', required_streak: 0 },
    mono:   { name: 'Mono',   bg: '#000000', accent: '#f2f2f2', required_streak: 1 },
    sunset: { name: 'Sunset', bg: '#14100e', accent: '#e8955c', required_streak: 7 },
    ocean:  { name: 'Ocean',  bg: '#0a0f12', accent: '#6fb6c8', required_streak: 14 },
    forest: { name: 'Forest', bg: '#0c100d', accent: '#93bb84', required_streak: 30 }
};

// Only these are accepted by /set_theme
const SERVER_THEMES = ['light', 'dark'];

function storeTheme(theme) {
    try { localStorage.setItem('theme', theme); } catch (e) {}
}

function readStoredTheme() {
    try { return localStorage.getItem('theme'); } catch (e) { return null; }
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    // Only save to localStorage if there's no universal theme
    if (!document.querySelector('meta[name="universal-theme"]')) {
        storeTheme(theme);
    }
    markCurrentSwatch();
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    storeTheme(theme);
    markCurrentSwatch();
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    setTheme(next);
    updateThemeOnServer(next);
}

function updateThemeOnServer(theme) {
    if (!SERVER_THEMES.includes(theme)) return;
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

    fetch('/set_theme', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify({ theme: theme }),
        credentials: 'same-origin'
    }).catch(error => console.error('Error updating theme:', error));
}

function markCurrentSwatch() {
    const current = document.documentElement.getAttribute('data-theme');
    document.querySelectorAll('.theme-swatch').forEach(el => {
        el.classList.toggle('is-current', el.dataset.theme === current);
        el.setAttribute('aria-pressed', el.dataset.theme === current ? 'true' : 'false');
    });
}

function updateThemeSelector() {
    const container = document.getElementById('theme-selector');
    if (!container) return;

    const userStreak = parseInt(document.querySelector('meta[name="user-streak"]')?.content || '0', 10);

    container.innerHTML = Object.entries(THEMES).map(([id, theme]) => {
        const isUnlocked = theme.required_streak <= userStreak;
        const title = isUnlocked
            ? `${theme.name} theme`
            : `${theme.name} — unlocks at a ${theme.required_streak}-day streak (${theme.required_streak - userStreak} to go)`;
        return `
            <button type="button"
                    class="theme-swatch ${isUnlocked ? '' : 'locked'}"
                    data-theme="${id}"
                    style="--swatch-bg:${theme.bg};--swatch-accent:${theme.accent}"
                    title="${title}"
                    aria-label="${title}"
                    ${isUnlocked ? '' : 'disabled'}></button>
        `;
    }).join('');

    container.querySelectorAll('.theme-swatch:not(.locked)').forEach(btn => {
        btn.addEventListener('click', () => {
            setTheme(btn.dataset.theme);
            updateThemeOnServer(btn.dataset.theme);
        });
    });

    markCurrentSwatch();
}

// Resolve the theme on load. A universal (admin) theme wins; otherwise a locally
// picked unlockable theme (which the server can't store) beats the account
// setting; otherwise the account setting, then whatever was saved locally.
document.addEventListener('DOMContentLoaded', function () {
    const userTheme = document.querySelector('meta[name="user-theme"]')?.content;
    const universalTheme = document.querySelector('meta[name="universal-theme"]')?.content;
    const savedTheme = readStoredTheme();

    let theme;
    if (universalTheme) {
        theme = universalTheme;
    } else if (savedTheme && !SERVER_THEMES.includes(savedTheme)) {
        theme = savedTheme;
    } else {
        theme = userTheme || savedTheme;
    }
    if (theme) applyTheme(theme);

    const toggleButton = document.getElementById('theme-toggle');
    if (toggleButton) {
        toggleButton.addEventListener('click', toggleTheme);
    }

    // Mount the swatch row into the masthead
    const slot = document.getElementById('theme-slot');
    if (slot) {
        const selector = document.createElement('div');
        selector.id = 'theme-selector';
        selector.className = 'theme-selector';
        selector.setAttribute('role', 'group');
        selector.setAttribute('aria-label', 'Theme');
        slot.appendChild(selector);
        updateThemeSelector();
    }
});
