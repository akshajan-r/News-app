function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    // Only save to localStorage if there's no universal theme
    if (!document.querySelector('meta[name="universal-theme"]')) {
        localStorage.setItem('theme', theme);
    }
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const button = document.getElementById('theme-toggle');
    if (button) {
        button.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
    }
    
    if (theme === 'dark') {
        document.body.classList.add('custom-theme');
    } else {
        document.body.classList.remove('custom-theme');
    }
    localStorage.setItem('theme', theme);
    createBackgroundElements(theme);
}
  
function toggleTheme() {
    const currentTheme = localStorage.getItem('theme') || 'light';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    updateThemeOnServer(newTheme);
}
  
function updateThemeOnServer(theme) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    
    fetch('/set_theme', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify({ theme: theme }),
        credentials: 'same-origin'
    })
    .catch(error => {
        console.error('Error updating theme:', error);
        const currentTheme = localStorage.getItem('theme');
        setTheme(currentTheme || 'light');
    });
}
  
// Apply theme on page load
document.addEventListener('DOMContentLoaded', function() {
    // Check for user-specific theme first
    const userTheme = document.querySelector('meta[name="user-theme"]')?.content;
    if (userTheme) {
        applyTheme(userTheme);
        return;
    }
    
    // Then check for universal theme
    const universalTheme = document.querySelector('meta[name="universal-theme"]')?.content;
    if (universalTheme) {
        applyTheme(universalTheme);
        return;
    }
    
    // Finally fall back to saved theme or default
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);
    
    // Add event listener for theme toggle button
    const toggleButton = document.getElementById('theme-toggle');
    if (toggleButton) {
        toggleButton.addEventListener('click', toggleTheme);
    }
});
  
// Handle theme for dynamic content (simplified)
window.addEventListener('load', () => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        setTheme(savedTheme);
    }
});

function updateThemeSelector() {
    const themes = {
        light: { name: 'Light', icon: '☀️', required_streak: 0 },
        dark: { name: 'Dark', icon: '🌙', required_streak: 0 },
        mono: { name: 'Mono', icon: '◾', required_streak: 1 },
        mystery1: { name: 'Sunset', icon: '🌅', required_streak: 7 },
        mystery2: { name: 'Ocean', icon: '🌊', required_streak: 14 },
        mystery3: { name: 'Forest', icon: '🌲', required_streak: 30 }
    };
    
    const container = document.getElementById('theme-selector');
    if (!container) return;

    const userStreak = parseInt(document.querySelector('meta[name="user-streak"]')?.content || '0');
    const unlockedThemes = (document.querySelector('meta[name="unlocked-themes"]')?.content || 'light,dark').split(',');
    
    container.innerHTML = Object.entries(themes).map(([id, theme]) => {
        const isUnlocked = theme.required_streak <= userStreak;
        const realThemeName = id === 'mystery1' ? 'sunset' : 
                            id === 'mystery2' ? 'ocean' : 
                            id === 'mystery3' ? 'forest' : id;
        
        return `
            <div class="theme-option ${isUnlocked ? '' : 'locked'}" 
                 ${isUnlocked ? `onclick="setTheme('${realThemeName}')"` : ''}
                 title="${isUnlocked ? 
                        'Click to apply theme' : 
                        `${theme.required_streak - userStreak} more days to unlock`}">
                <span class="theme-icon">${theme.icon}</span>
                <span class="theme-name">${theme.name}</span>
                ${!isUnlocked ? 
                  `<span class="days-required">${theme.required_streak}d</span>` : ''}
            </div>
        `;
    }).join('');
}

// Add this to show the theme selector
document.addEventListener('DOMContentLoaded', () => {
    // Add theme selector to navbar
    const navbar = document.querySelector('.navbar-nav');
    if (navbar) {
        const themeSelector = document.createElement('div');
        themeSelector.id = 'theme-selector';
        themeSelector.className = 'theme-selector';
        navbar.insertBefore(themeSelector, navbar.firstChild);
        updateThemeSelector();
    }
});

function createBackgroundElements(theme) {
    // Remove existing elements
    document.querySelectorAll('.bg-element').forEach(el => el.remove());
    
    // Create new elements based on theme
    const count = 5; // Keep the number low for subtle effect
    for (let i = 0; i < count; i++) {
        const el = document.createElement('div');
        el.className = 'bg-element';
        el.style.setProperty('--x', `${Math.random() * 100}vw`);
        el.style.left = `${Math.random() * 100}vw`;
        el.style.animationDelay = `${Math.random() * 10}s`;
        document.body.appendChild(el);
    }
}

// Add this to your existing code
document.addEventListener('mousemove', (e) => {
    const cards = document.querySelectorAll('.article-card, .preferences-card, .stats-card');
    cards.forEach(card => {
        const rect = card.getBoundingClientRect();
        const x = ((e.clientX - rect.left) / card.offsetWidth) * 100;
        const y = ((e.clientY - rect.top) / card.offsetHeight) * 100;
        card.style.setProperty('--x', `${x}%`);
        card.style.setProperty('--y', `${y}%`);
    });
});