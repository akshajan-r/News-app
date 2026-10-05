// Shared helpers for story cards: rendering, saving, sharing, toasts.

const Stories = (() => {
    const ICONS = {
        bookmark: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.5h12v17l-6-4.2-6 4.2z"/></svg>',
        share: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15V3.5M7.5 8 12 3.5 16.5 8M5 12.5v7h14v-7"/></svg>'
    };

    function csrf() {
        return document.querySelector('meta[name="csrf-token"]')?.content || '';
    }

    function esc(str) {
        const d = document.createElement('div');
        d.textContent = str == null ? '' : String(str);
        return d.innerHTML;
    }

    function timeAgo(dateString) {
        if (!dateString) return '';
        const date = new Date(String(dateString).replace(' ', 'T'));
        const s = Math.floor((Date.now() - date) / 1000);
        if (!isFinite(s)) return '';
        if (s < 60) return 'Just now';
        if (s < 3600) return `${Math.floor(s / 60)}m ago`;
        if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
        return `${Math.floor(s / 86400)}d ago`;
    }

    function readingTime(text) {
        const words = (text || '').split(/\s+/).filter(Boolean).length;
        return Math.max(1, Math.round(words / 200));
    }

    function readerUrl(article) {
        return `/read_article?url=${encodeURIComponent(article.url)}` +
            `&title=${encodeURIComponent(article.title || '')}` +
            `&preview_image=${encodeURIComponent(article.urlToImage || '')}` +
            (article.category ? `&category=${encodeURIComponent(article.category)}` : '');
    }

    function toast(message) {
        let stack = document.querySelector('.toast-stack');
        if (!stack) {
            stack = document.createElement('div');
            stack.className = 'toast-stack';
            stack.setAttribute('role', 'status');
            document.body.appendChild(stack);
        }
        const el = document.createElement('div');
        el.className = 'toast-msg';
        el.textContent = message;
        stack.appendChild(el);
        setTimeout(() => el.remove(), 3000);
    }

    function bookmark(url, title, button) {
        return fetch('/bookmark_article', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
            body: JSON.stringify({ url, title })
        })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    if (button) button.classList.add('is-on');
                    toast('Saved for later');
                } else {
                    throw new Error('failed');
                }
            })
            .catch(() => toast('Could not save story'));
    }

    // Toggle a bookmark from a button carrying data-url / data-title / data-category.
    function toggleBookmark(button) {
        const { url, title, category } = button.dataset;
        return fetch('/toggle_bookmark', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
            body: JSON.stringify({ url, title, category: category || 'general' })
        })
            .then(r => r.json())
            .then(data => {
                if (data.status !== 'success') throw new Error('failed');
                button.classList.toggle('is-on', data.bookmarked);
                const text = button.querySelector('[data-label]');
                if (text) text.textContent = data.bookmarked ? 'Saved' : 'Save';
                toast(data.bookmarked ? 'Saved for later' : 'Removed from saved');
            })
            .catch(() => toast('Could not save story'));
    }

    function share(url, title) {
        if (navigator.share) {
            navigator.share({ title: title || 'From Newsense', url }).catch(() => {});
            return;
        }
        navigator.clipboard.writeText(url)
            .then(() => toast('Link copied'))
            .catch(() => toast('Could not copy link'));
    }

    /**
     * Build a story card element.
     * opts.index   – number shown top-left
     * opts.feature – render as the wide lead story
     * opts.actions – show save/share buttons (signed-in only)
     * opts.kicker  – text shown top-right (e.g. match score)
     */
    function card(article, opts = {}) {
        const el = document.createElement('article');
        el.className = 'story' + (opts.feature ? ' story-feature' : '');
        el.tabIndex = 0;

        const href = readerUrl(article);
        const go = () => { window.location.href = href; };
        el.addEventListener('click', go);
        el.addEventListener('keydown', e => { if (e.key === 'Enter') go(); });

        const index = opts.index != null ? String(opts.index).padStart(2, '0') : '';
        const source = article.source?.name || 'Unknown source';
        const meta = [timeAgo(article.publishedAt), `${readingTime(article.description || article.content)} min`]
            .filter(Boolean).join(' · ');

        // Sentiment from the recommender: { label: 'Very Positive' … 'Very Negative', match_score }
        const s = article.sentiment;
        const toneKey = s && s.label ? s.label.toLowerCase().replace(/\s+/g, '-') : '';
        const tone = s && s.label ? `
            <div class="story-tone tone-${esc(toneKey)}"
                 title="Tone of this story, and how closely it matches the tone of what you usually read">
                <span class="tone-dot" aria-hidden="true"></span>
                <span class="label tone-label">${esc(s.label)}</span>
                ${s.match_score != null ? `<span class="label">· ${esc(s.match_score)}% tone match</span>` : ''}
            </div>` : '';

        el.innerHTML = `
            <div class="story-index">
                <span class="label">${esc(index)}${index ? ' // ' : ''}${esc(source)}</span>
                ${opts.kicker ? `<span class="label label-accent">${esc(opts.kicker)}</span>` : ''}
            </div>
            ${article.urlToImage ? `
            <div class="story-media">
                <img src="${esc(article.urlToImage)}" alt="" loading="lazy">
            </div>` : ''}
            <h3 class="story-title">${esc(article.title)}</h3>
            ${article.description ? `<p class="story-dek">${esc(article.description)}</p>` : ''}
            ${tone}
            <div class="story-meta">
                <span class="label">${esc(meta)}</span>
                ${opts.actions ? `
                <div class="story-actions">
                    <button type="button" class="icon-btn" data-act="save" title="Save for later" aria-label="Save for later">${ICONS.bookmark}</button>
                    <button type="button" class="icon-btn" data-act="share" title="Share" aria-label="Share">${ICONS.share}</button>
                </div>` : ''}
            </div>
        `;

        const img = el.querySelector('.story-media img');
        if (img) {
            img.addEventListener('error', () => img.closest('.story-media').remove(), { once: true });
        }

        el.querySelectorAll('[data-act]').forEach(btn => {
            btn.addEventListener('click', e => {
                e.stopPropagation();
                if (btn.dataset.act === 'save') bookmark(article.url, article.title, btn);
                else share(article.url, article.title);
            });
        });

        return el;
    }

    return { card, bookmark, toggleBookmark, share, toast, timeAgo, esc, readerUrl, csrf, ICONS };
})();
