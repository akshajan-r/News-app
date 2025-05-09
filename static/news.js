document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('.news-filters');
    
    if (form) {
        form.addEventListener('submit', function(e) {
            // Let the form submit normally - the CSRF token is already included by Flask-WTF
            console.log('Form submitting...');
        });
    }
}); 