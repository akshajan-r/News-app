document.addEventListener('DOMContentLoaded', () => {
    // Pull colours from the active theme so charts match the page
    const css = getComputedStyle(document.documentElement);
    const token = name => css.getPropertyValue(name).trim();
    const ink = token('--ink');
    const ink2 = token('--ink-2');
    const ink3 = token('--ink-3');
    const rule = token('--rule');
    const bg = token('--bg');
    const accent = token('--accent');
    const accentRgb = token('--accent-rgb');
    const inkRgb = token('--ink-rgb');

    Chart.defaults.font.family = '"JetBrains Mono", ui-monospace, monospace';
    Chart.defaults.font.size = 11;
    Chart.defaults.color = ink3;
    Chart.defaults.responsive = true;
    Chart.defaults.maintainAspectRatio = false;
    
    // Create Activity Chart
    const activityData = document.getElementById('activity-data');
    if (activityData) {
        try {
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
                            borderColor: accent,
                            borderWidth: 1.5,
                            backgroundColor: `rgba(${accentRgb}, 0.08)`,
                            fill: true,
                            tension: 0.25,
                            pointRadius: 0,
                            pointHoverRadius: 4,
                            pointBackgroundColor: accent
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                mode: 'index',
                                intersect: false,
                                backgroundColor: ink,
                                titleColor: bg,
                                bodyColor: bg,
                                cornerRadius: 2,
                                padding: 10,
                                displayColors: false
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                border: { display: false },
                                grid: {
                                    drawBorder: false,
                                    color: rule
                                },
                                ticks: {
                                    stepSize: 1,
                                    padding: 8
                                }
                            },
                            x: {
                                border: { color: rule },
                                grid: {
                                    display: false
                                },
                                ticks: {
                                    maxRotation: 0,
                                    autoSkipPadding: 24
                                }
                            }
                        },
                        interaction: {
                            intersect: false,
                            mode: 'nearest'
                        },
                        animation: {
                            duration: 600,
                            easing: 'easeOutQuart'
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
                            // Accent for the top section, then fading steps of ink
                            backgroundColor: chartData.map((_, i) =>
                                i === 0 ? accent : `rgba(${inkRgb}, ${Math.max(0.12, 0.7 - i * 0.14)})`),
                            borderWidth: 2,
                            borderColor: bg,
                            hoverOffset: 4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: {
                                    color: ink2,
                                    padding: 16,
                                    boxWidth: 8,
                                    boxHeight: 8,
                                    usePointStyle: true,
                                    pointStyle: 'rect'
                                }
                            },
                            tooltip: {
                                backgroundColor: ink,
                                titleColor: bg,
                                bodyColor: bg,
                                cornerRadius: 2,
                                padding: 10,
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
                        cutout: '72%',
                        animation: {
                            animateRotate: true,
                            animateScale: false
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