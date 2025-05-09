function fetchLatestArticles() {
    fetch('/get_latest_articles')
        .then(response => response.json())
        .then(data => {
            const latestArticlesDiv = document.getElementById('latest-articles');
            latestArticlesDiv.innerHTML = ''; // Clear existing content

            if (data.articles && data.articles.length > 0) {
                const ul = document.createElement('ul');
                ul.className = 'list-unstyled';

                data.articles.slice(0, 3).forEach(article => {
                    const li = document.createElement('li');
                    li.className = 'mb-2';
                    const a = document.createElement('a');
                    a.href = article.url;
                    a.target = '_blank';
                    a.textContent = article.title;
                    li.appendChild(a);
                    ul.appendChild(li);
                });

                latestArticlesDiv.appendChild(ul);
            } else {
                latestArticlesDiv.textContent = 'No articles available at the moment.';
            }
        })
        .catch(error => {
            console.error('Error fetching latest articles:', error);
            const latestArticlesDiv = document.getElementById('latest-articles');
            latestArticlesDiv.textContent = 'Error loading articles. Please try again later.';
        });
}

// Fetch latest articles every 5 minutes
setInterval(fetchLatestArticles, 5 * 60 * 1000);

// Initial fetch when the page loads
document.addEventListener('DOMContentLoaded', fetchLatestArticles);