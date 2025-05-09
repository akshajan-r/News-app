document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard charts script loaded');
    Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen-Sans, Ubuntu, Cantarell, "Helvetica Neue", sans-serif';
    Chart.defaults.color = getComputedStyle(document.documentElement).getPropertyValue('--mdc-theme-on-surface');
    Chart.defaults.responsive = true;
    Chart.defaults.maintainAspectRatio = false;
    
    // Create Activity Chart
    const activityData = document.getElementById('activity-data');
    if (activityData) {
        try {
            console.log('Creating activity chart');
            const dates = JSON.parse(activityData.dataset.dates);
            const counts = JSON.parse(activityData.dataset.counts);
            
            const activityCtx = document.getElementById('activityChart');
            if (!activityCtx) {
                console.error('Activity chart canvas not found');
                return;
            }
            const activityChart = new Chart(
                activityCtx,
                {
                    type: 'line',
                    data: {
                        labels: dates,
                        datasets: [{
                            label: 'Articles Read',
                            data: counts,
                            borderColor: '#7C4DFF',
                            backgroundColor: 'rgba(124, 77, 255, 0.2)',
                            fill: true,
                            tension: 0.4,
                            pointRadius: 4,
                            pointHoverRadius: 6,
                            pointBackgroundColor: '#7C4DFF'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top',
                                labels: {
                                    usePointStyle: true,
                                    padding: 20
                                }
                            },
                            tooltip: {
                                mode: 'index',
                                intersect: false,
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                padding: 12,
                                displayColors: false
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                grid: {
                                    drawBorder: false,
                                    color: 'rgba(200, 200, 200, 0.1)'
                                },
                                ticks: {
                                    stepSize: 1
                                }
                            },
                            x: {
                                grid: {
                                    display: false
                                }
                            }
                        },
                        interaction: {
                            intersect: false,
                            mode: 'nearest'
                        },
                        animation: {
                            duration: 1000,
                            easing: 'easeInOutQuart'
                        }
                    }
                }
            );
        } catch (e) {
            console.error('Activity chart error:', e);
        }
    }
    
    // Create Category Chart
    const categoryData = document.getElementById('category-data');
    if (categoryData) {
        try {
            console.log('Creating category chart');
            const categories = JSON.parse(categoryData.dataset.categories);
            const counts = JSON.parse(categoryData.dataset.counts);
            
            const chartLabels = categories.length ? categories : ['No Data'];
            const chartData = counts.length ? counts : [1];
            
            const categoryCtx = document.getElementById('categoryChart');
            if (!categoryCtx) {
                console.error('Category chart canvas not found');
                return;
            }
            const categoryChart = new Chart(
                categoryCtx,
                {
                    type: 'doughnut',
                    data: {
                        labels: chartLabels,
                        datasets: [{
                            data: chartData,
                            backgroundColor: [
                                '#FF6B6B', '#4ECDC4', '#45B7D1', 
                                '#96CEB4', '#FFEEAD', '#D4A5A5',
                                '#FFB6B9', '#8785A2', '#A8E6CF',
                                '#FFAAA5'
                            ],
                            borderWidth: 2,
                            borderColor: 'rgba(255, 255, 255, 0.8)'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'right',
                                labels: {
                                    padding: 20,
                                    usePointStyle: true,
                                    pointStyle: 'circle'
                                }
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                padding: 12,
                                callbacks: {
                                    label: function(context) {
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        const value = context.raw;
                                        const percentage = ((value / total) * 100).toFixed(1);
                                        return ` ${context.label}: ${value} (${percentage}%)`;
                                    }
                                }
                            }
                        },
                        cutout: '60%',
                        animation: {
                            animateRotate: true,
                            animateScale: true
                        },
                        hover: {
                            mode: 'nearest',
                            intersect: true
                        }
                    }
                }
            );
        } catch (e) {
            console.error('Category chart error:', e);
        }
    }
});