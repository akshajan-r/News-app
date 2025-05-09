// Utility functions for QOL features
const utils = {
    // Show loading spinner
    showLoading: () => {
        document.getElementById('loading-spinner').style.display = 'flex';
    },

    // Hide loading spinner
    hideLoading: () => {
        document.getElementById('loading-spinner').style.display = 'none';
    },

    // Show notification
    showNotification: (message, type = 'success') => {
        const notification = document.getElementById('notification');
        notification.textContent = message;
        notification.className = `notification ${type}`;
        notification.classList.add('show');

        setTimeout(() => {
            notification.classList.remove('show');
        }, 3000);
    },

    // Create skeleton loading
    createSkeleton: (count = 3) => {
        return Array(count).fill().map(() => `
            <div class="news-article skeleton">
                <div style="height: 200px; margin-bottom: 15px;"></div>
                <div style="height: 24px; width: 80%; margin-bottom: 10px;"></div>
                <div style="height: 16px; width: 60%; margin-bottom: 5px;"></div>
                <div style="height: 16px; width: 40%;"></div>
            </div>
        `).join('');
    }
};

// Add smooth scrolling to top
const scrollToTop = document.createElement('button');
scrollToTop.className = 'scroll-to-top';
scrollToTop.innerHTML = '↑';
document.body.appendChild(scrollToTop);

scrollToTop.addEventListener('click', () => {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
});

window.addEventListener('scroll', () => {
    if (window.pageYOffset > 100) {
        scrollToTop.classList.add('show');
    } else {
        scrollToTop.classList.remove('show');
    }
});

// Add keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K to focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        document.querySelector('input[name="keywords"]')?.focus();
    }
});

// Get CSRF token from meta tag
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]').content;
}

// Add CSRF token to fetch requests
async function fetchWithCSRF(url, options = {}) {
    const token = getCSRFToken();
    const defaultHeaders = {
        'X-CSRF-TOKEN': token,
        'Content-Type': 'application/json'
    };
    
    return fetch(url, {
        ...options,
        headers: {
            ...defaultHeaders,
            ...(options.headers || {})
        }
    });
} 