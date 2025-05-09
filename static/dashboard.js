// Remove or comment out this line at the top if it exists:
// import API_CONFIG from './api.config.js';

let editMode = false;

// Initialize sortable grids
document.addEventListener('DOMContentLoaded', () => {
    const grids = document.querySelectorAll('.sortable-grid');
    grids.forEach(grid => {
        new Sortable(grid, {
            animation: 150,
            handle: '.drag-handle',
            ghostClass: 'sortable-ghost',
            dragClass: 'sortable-drag',
            chosenClass: 'sortable-chosen',
            forceFallback: false,
            fallbackTolerance: 3,
            onEnd: function(evt) {
                // Maintain original size class
                const item = evt.item;
                const isLargeCard = item.classList.contains('insight-card');
                const targetGrid = evt.to;
                
                if (isLargeCard) {
                    // If it's a large card, make sure it spans 2 columns
                    item.classList.add('module-large');
                    item.style.gridColumn = 'span 2';
                } else {
                    // If it's a small card, make it span 1 column
                    item.classList.add('module-small');
                    item.style.gridColumn = 'span 1';
                }
                
                saveLayout();
            },
            group: 'dashboard-modules',
            draggable: '.stat-card, .insight-card'
        });
    });
    
    // Initialize size classes
    document.querySelectorAll('.stat-card').forEach(card => {
        card.classList.add('module-small');
    });
    document.querySelectorAll('.insight-card').forEach(card => {
        card.classList.add('module-large');
    });
    
    // Initialize resizable modules
    initializeResizable();
    
    loadLayout();
});

// Toggle customize mode
function toggleCustomize() {
    editMode = !editMode;
    const container = document.querySelector('.dashboard-container');
    const button = document.querySelector('.control-btn');
    
    container.classList.toggle('edit-mode');
    button.classList.toggle('active');
    button.textContent = editMode ? '✓ Done' : '⚙️ Customize';
    
    // Add/remove remove buttons and drag handles
    const modules = document.querySelectorAll('.sortable-grid > div');
    modules.forEach(module => {
        let removeBtn = module.querySelector('.remove-button');
        let dragHandle = module.querySelector('.drag-handle');
        
        if (editMode) {
            if (!removeBtn) {
                removeBtn = document.createElement('div');
                removeBtn.className = 'remove-button';
                removeBtn.innerHTML = '−';
                removeBtn.onclick = (e) => {
                    e.stopPropagation();
                    removeModule(module);
                };
                module.appendChild(removeBtn);
            }
            
            if (!dragHandle) {
                dragHandle = document.createElement('div');
                dragHandle.className = 'drag-handle';
                dragHandle.innerHTML = '⋮⋮';
                module.appendChild(dragHandle);
            }
        } else {
            removeBtn?.remove();
            dragHandle?.remove();
        }
    });
    
    // Show/hide restore menu
    const restoreMenu = document.querySelector('.restore-menu');
    if (editMode) {
        restoreMenu.classList.add('visible');
        // Add any hidden modules to restore menu
        document.querySelectorAll('.sortable-grid > div.hidden').forEach(module => {
            addToRestoreMenu(module.dataset.moduleId);
        });
    } else {
        restoreMenu.classList.remove('visible');
        // Clear restore menu
        restoreMenu.innerHTML = '';
        saveLayout();
    }
}

// Toggle module visibility
function toggleModule(moduleId) {
    const module = document.querySelector(`[data-module-id="${moduleId}"]`);
    if (module) {
        module.classList.toggle('hidden');
        saveLayout();
    }
}

// Save layout to localStorage and server
function saveLayout() {
    const layout = {
        stats: getGridLayout('statsGrid'),
        insights: getGridLayout('insightsGrid'),
    };
    
    localStorage.setItem('dashboardLayout', JSON.stringify(layout));
    
    // Save to server
    fetch('/save_dashboard_layout', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        },
        body: JSON.stringify(layout)
    });
}

// Get layout of a grid
function getGridLayout(gridId) {
    const grid = document.getElementById(gridId);
    return Array.from(grid.children).map(child => ({
        id: child.dataset.moduleId,
        visible: !child.classList.contains('hidden')
    }));
}

// Load saved layout
function loadLayout() {
    const saved = localStorage.getItem('dashboardLayout');
    const sizes = JSON.parse(localStorage.getItem('moduleSizes') || '{}');
    
    if (saved) {
        const layout = JSON.parse(saved);
        applyLayout('statsGrid', layout.stats);
        applyLayout('insightsGrid', layout.insights);
        
        // Restore sizes
        Object.entries(sizes).forEach(([moduleId, size]) => {
            const module = document.querySelector(`[data-module-id="${moduleId}"]`);
            if (module) {
                module.style.width = size.width;
                module.style.height = size.height;
                module.style.gridColumn = size.spans;
            }
        });
    }
}

// Apply layout to a grid
function applyLayout(gridId, layout) {
    const grid = document.getElementById(gridId);
    layout.forEach(item => {
        const module = grid.querySelector(`[data-module-id="${item.id}"]`);
        if (module) {
            if (!item.visible) {
                module.classList.add('hidden');
            }
            grid.appendChild(module); // Reorder
        }
    });
}

function removeModule(module) {
    module.classList.add('hidden');
    addToRestoreMenu(module.dataset.moduleId);
    saveLayout();
}

function restoreModule(moduleId) {
    const module = document.querySelector(`.stat-card[data-module-id="${moduleId}"], .insight-card[data-module-id="${moduleId}"]`);
    const menuItem = document.querySelector(`.restore-item[data-module-id="${moduleId}"]`);
    
    if (module) {
        const grid = module.closest('.sortable-grid');
        const gridWidth = Math.floor(grid.offsetWidth / 250);
        
        // Create a grid map
        const gridMap = [];
        const visibleModules = Array.from(grid.children).filter(child => 
            !child.classList.contains('hidden') && 
            child !== module &&
            !child.classList.contains('sortable-ghost')
        );
        
        // Map out all occupied positions
        visibleModules.forEach(other => {
            const rect = other.getBoundingClientRect();
            const row = Math.floor((rect.top - grid.getBoundingClientRect().top) / 120);
            const col = Math.floor((rect.left - grid.getBoundingClientRect().left) / 250);
            const spans = parseInt(other.style.gridColumn?.split(' ')[1] || 1);
            
            while (gridMap.length <= row) {
                gridMap.push(new Array(gridWidth).fill(false));
            }
            
            for (let i = 0; i < spans; i++) {
                if (col + i < gridWidth) {
                    gridMap[row][col + i] = true;
                }
            }
        });
        
        // Find first available position
        let foundSpot = false;
        let targetRow = 0;
        let targetCol = 0;
        
        rowLoop: for (let row = 0; row < gridMap.length + 1; row++) {
            if (!gridMap[row]) gridMap[row] = new Array(gridWidth).fill(false);
            
            for (let col = 0; col < gridWidth; col++) {
                if (!gridMap[row][col]) {
                    foundSpot = true;
                    targetRow = row;
                    targetCol = col;
                    break rowLoop;
                }
            }
        }
        
        // Position the module
        module.style.gridRow = `${targetRow + 1}`;
        module.style.gridColumn = `${targetCol + 1} / span 1`;
        module.classList.remove('hidden');
        
        if (menuItem) {
            menuItem.remove();
        }
        
        // Animate in
        module.style.opacity = '0';
        requestAnimationFrame(() => {
            module.style.transition = 'all 0.3s ease';
            module.style.opacity = '1';
        });
        
        saveLayout();
    }
}

function addToRestoreMenu(moduleId) {
    const menu = document.querySelector('.restore-menu');
    if (!menu) return;
    
    // Don't add if already in menu
    if (menu.querySelector(`.restore-item[data-module-id="${moduleId}"]`)) return;
    
    // First verify that the module exists and is hidden
    const module = document.querySelector(`.stat-card[data-module-id="${moduleId}"], .insight-card[data-module-id="${moduleId}"]`);
    if (!module || !module.classList.contains('hidden')) return;
    
    const item = document.createElement('div');
    item.className = 'restore-item';
    item.dataset.moduleId = moduleId;
    item.textContent = getModuleName(moduleId);
    
    item.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        console.log('Clicked restore item:', moduleId);
        restoreModule(moduleId);
    };
    
    menu.appendChild(item);
}

function getModuleName(moduleId) {
    const names = {
        'articles_today': 'Articles Today',
        'streak': 'Streak',
        'favorite_category': 'Favorite Category',
        'peak_hours': 'Peak Hours',
        'most_active_day': 'Most Active Day',
        'streak_stats': 'Achievement Stats'
    };
    return names[moduleId] || moduleId;
}

function initializeResizable() {
    document.querySelectorAll('.stat-card, .insight-card').forEach(module => {
        const handle = document.createElement('div');
        handle.className = 'resize-handle';
        handle.innerHTML = '⤡';
        module.appendChild(handle);
        
        let initialSize = null;
        let currentSpans = 1;
        
        interact(module).resizable({
            edges: { 
                right: '.resize-handle', 
                bottom: '.resize-handle' 
            },
            inertia: {
                resistance: 20,
                minSpeed: 50,
                endSpeed: 5
            },
            modifiers: [
                interact.modifiers.restrictEdges({
                    outer: 'parent'
                }),
                interact.modifiers.restrictSize({
                    min: { width: 250, height: 100 },
                    max: { width: 500, height: 220 }
                })
            ],
            listeners: {
                start: function(event) {
                    const target = event.target;
                    initialSize = {
                        width: target.offsetWidth,
                        height: target.offsetHeight,
                        spans: parseInt(target.style.gridColumn?.split(' ')[1] || 1)
                    };
                    currentSpans = initialSize.spans;
                    target.classList.add('resizing');
                    document.body.style.userSelect = 'none';
                },
                move: function(event) {
                    const target = event.target;
                    let width = event.rect.width;
                    let height = event.rect.height;
                    
                    // Determine if we're trying to make a square
                    const isNearSquare = Math.abs(width - height) < 50;
                    
                    if (isNearSquare) {
                        // Make it a perfect square based on the larger dimension
                        const size = Math.max(width, height);
                        width = size;
                        height = size;
                    }
                    
                    // Determine spans based on width
                    const newSpans = width > 400 ? 2 : 1;
                    
                    if (!wouldOverlap(target, newSpans)) {
                        currentSpans = newSpans;
                        
                        requestAnimationFrame(() => {
                            target.style.width = `${width}px`;
                            target.style.height = `${height}px`;
                            target.style.gridColumn = `span ${currentSpans}`;
                        });
                    }
                },
                end: function(event) {
                    const target = event.target;
                    const width = event.rect.width;
                    const height = event.rect.height;
                    
                    // Check if we ended up with a near-square shape
                    const isSquare = Math.abs(width - height) < 50;
                    
                    let finalSize;
                    if (isSquare) {
                        finalSize = 'square';
                    } else if (currentSpans === 1) {
                        finalSize = height > 160 ? 'tall' : 'small';
                    } else {
                        finalSize = height > 160 ? 'large' : 'wide';
                    }
                    
                    requestAnimationFrame(() => {
                        target.classList.remove('resizing');
                        target.classList.add('resizing-end');
                        
                        if (!wouldOverlap(target, currentSpans)) {
                            target.style.width = '';
                            target.style.height = '';
                            target.classList.remove('size-small', 'size-wide', 'size-tall', 'size-large', 'size-square');
                            target.classList.add(`size-${finalSize}`);
                            target.style.gridColumn = `span ${currentSpans}`;
                            
                            saveModuleSize(target.dataset.moduleId, {
                                size: finalSize,
                                spans: target.style.gridColumn
                            });
                        } else {
                            revertToOriginalSize(target);
                        }
                        
                        setTimeout(() => {
                            target.classList.remove('resizing-end');
                            document.body.style.userSelect = '';
                        }, 300);
                    });
                }
            }
        });
    });
}

function wouldOverlap(module, newSpans) {
    const grid = module.closest('.sortable-grid');
    const gridRect = grid.getBoundingClientRect();
    const moduleRect = module.getBoundingClientRect();
    const row = Math.round((moduleRect.top - gridRect.top) / moduleRect.height);
    const col = Math.round((moduleRect.left - gridRect.left) / 250);
    
    // Get all other modules in the same row
    const siblings = Array.from(grid.children).filter(child => 
        child !== module && 
        !child.classList.contains('hidden') &&
        Math.round((child.getBoundingClientRect().top - gridRect.top) / moduleRect.height) === row
    );
    
    // Check if new size would overlap with any sibling
    for (const sibling of siblings) {
        const siblingRect = sibling.getBoundingClientRect();
        const siblingCol = Math.round((siblingRect.left - gridRect.left) / 250);
        const siblingSpans = parseInt(sibling.style.gridColumn?.split(' ')[1] || 1);
        
        // Check for overlap
        if (col < siblingCol + siblingSpans && col + newSpans > siblingCol) {
            return true;
        }
    }
    
    // Check if new size would exceed grid width
    const gridWidth = Math.floor(grid.offsetWidth / 250);
    return (col + newSpans) > gridWidth;
}

function revertToOriginalSize(module) {
    const originalSize = module.classList.contains('insight-card') ? 'large' : 'small';
    module.style.width = '';
    module.style.height = '';
    module.classList.remove('size-small', 'size-wide', 'size-tall', 'size-large');
    module.classList.add(`size-${originalSize}`);
    module.style.gridColumn = `span ${originalSize === 'large' ? 2 : 1}`;
}

const SIZE_PRESETS = {
    'small': { width: '1', height: '100px', minGridWidth: 1 },     // 1x1
    'wide': { width: '2', height: '100px', minGridWidth: 2 },      // 2x1
    'tall': { width: '1', height: '220px', minGridWidth: 1 },      // 1x2
    'large': { width: '2', height: '220px', minGridWidth: 2 }      // 2x2
};

function cycleModuleSize(module) {
    const currentSize = getModuleCurrentSize(module);
    const nextSize = getNextSize(currentSize);
    
    // Check if the next size would fit in the grid
    if (canFitSize(module, nextSize)) {
        applyModuleSize(module, nextSize);
        saveModuleSize(module.dataset.moduleId, nextSize);
    }
}

function canFitSize(module, newSizeName) {
    const grid = module.closest('.sortable-grid');
    const newSize = SIZE_PRESETS[newSizeName];
    const gridWidth = Math.floor(grid.offsetWidth / 250);
    
    // Get module's current position
    const moduleRect = module.getBoundingClientRect();
    const gridRect = grid.getBoundingClientRect();
    const currentRow = Math.floor((moduleRect.top - gridRect.top) / 120);
    const currentCol = Math.floor((moduleRect.left - gridRect.left) / 250);
    
    // If shrinking, always allow it
    const currentSpans = parseInt(module.style.gridColumn?.split(' ')[1] || 1);
    const newSpans = parseInt(newSize.width);
    if (newSpans < currentSpans) {
        return true;
    }
    
    // Check if it would exceed grid width
    if (currentCol + newSpans > gridWidth) {
        return false;
    }
    
    // Get all modules in the same row
    const visibleModules = Array.from(grid.children).filter(child => 
        !child.classList.contains('hidden') && 
        child !== module &&
        !child.classList.contains('sortable-ghost')
    );
    
    // Create a grid map for the current row
    const gridMap = new Array(gridWidth).fill(false);
    
    // Mark current module's position
    for (let i = 0; i < currentSpans; i++) {
        if (currentCol + i < gridWidth) {
            gridMap[currentCol + i] = true;
        }
    }
    
    // Check for overlaps in the same row
    for (const other of visibleModules) {
        const otherRect = other.getBoundingClientRect();
        const otherRow = Math.floor((otherRect.top - gridRect.top) / 120);
        
        if (otherRow === currentRow) {
            const otherCol = Math.floor((otherRect.left - gridRect.left) / 250);
            const otherSpans = parseInt(other.style.gridColumn?.split(' ')[1] || 1);
            
            // Mark occupied positions
            for (let i = 0; i < otherSpans; i++) {
                if (otherCol + i < gridWidth) {
                    gridMap[otherCol + i] = true;
                }
            }
        }
    }
    
    // Check if there's enough consecutive space for the new size
    let consecutiveSpace = 0;
    for (let i = currentCol; i < Math.min(currentCol + newSpans, gridWidth); i++) {
        if (!gridMap[i]) {
            consecutiveSpace++;
        } else if (i !== currentCol && i !== currentCol + currentSpans - 1) {
            // Allow overlap with current module's positions
            return false;
        }
    }
    
    return consecutiveSpace >= newSpans;
}

function getModuleCurrentSize(module) {
    const width = module.style.gridColumn.replace('span ', '') || '1';
    const height = module.style.height || '100px';
    
    // Match current dimensions to a preset
    for (const [name, preset] of Object.entries(SIZE_PRESETS)) {
        if (preset.width === width && preset.height === height) {
            return name;
        }
    }
    return 'small'; // Default
}

function getNextSize(currentSize) {
    const sizeOrder = ['small', 'wide', 'tall', 'large'];
    const currentIndex = sizeOrder.indexOf(currentSize);
    return sizeOrder[(currentIndex + 1) % sizeOrder.length];
}

function applyModuleSize(module, sizeName) {
    const size = SIZE_PRESETS[sizeName];
    
    // First check if we need to move the module to prevent overlap
    const grid = module.closest('.sortable-grid');
    const visibleModules = Array.from(grid.children).filter(child => 
        !child.classList.contains('hidden') && child !== module
    );
    
    // Try to find a suitable position
    let foundPosition = false;
    const gridWidth = Math.floor(grid.offsetWidth / 250);
    
    for (let row = 0; row < 10 && !foundPosition; row++) { // Check up to 10 rows
        for (let col = 0; col < gridWidth && !foundPosition; col++) {
            let canFit = true;
            
            // Check if this position is occupied
            visibleModules.forEach(other => {
                const otherRect = other.getBoundingClientRect();
                const otherRow = Math.floor((otherRect.top - grid.getBoundingClientRect().top) / 120);
                const otherCol = Math.floor((otherRect.left - grid.getBoundingClientRect().left) / 250);
                const otherSpans = parseInt(other.style.gridColumn?.split(' ')[1] || 1);
                
                if (otherRow === row) {
                    for (let i = 0; i < otherSpans; i++) {
                        if (col + parseInt(size.width) > otherCol && col < otherCol + otherSpans) {
                            canFit = false;
                        }
                    }
                }
            });
            
            if (canFit && col + parseInt(size.width) <= gridWidth) {
                foundPosition = true;
                module.style.gridRow = `${row + 1}`;
                module.style.gridColumn = `${col + 1} / span ${size.width}`;
            }
        }
    }
    
    if (!foundPosition) {
        // If no position found, keep current size
        return false;
    }
    
    module.style.height = size.height;
    module.style.transition = 'all 0.3s ease';
    module.classList.remove('size-small', 'size-wide', 'size-tall', 'size-large');
    module.classList.add(`size-${sizeName}`);
    
    return true;
}

function saveModuleSize(moduleId, size) {
    const sizes = JSON.parse(localStorage.getItem('moduleSizes') || '{}');
    sizes[moduleId] = size;
    localStorage.setItem('moduleSizes', JSON.stringify(sizes));
}

function resetDashboard() {
    if (confirm('Are you sure you want to reset the dashboard to its default layout?')) {
        // Clear stored layouts
        localStorage.removeItem('dashboardLayout');
        localStorage.removeItem('moduleSizes');
        
        // Reset all modules to visible
        document.querySelectorAll('.sortable-grid > div').forEach(module => {
            module.classList.remove('hidden');
            module.style.gridColumn = '';
            module.style.gridRow = '';
            module.style.height = '';
            module.style.width = '';
            
            // Reset size classes
            module.classList.remove('size-small', 'size-wide', 'size-tall', 'size-large');
            if (module.classList.contains('insight-card')) {
                module.classList.add('size-large');
            } else {
                module.classList.add('size-small');
            }
        });
        
        // Clear restore menu
        const restoreMenu = document.querySelector('.restore-menu');
        if (restoreMenu) {
            restoreMenu.innerHTML = '';
        }
        
        // Exit edit mode if active
        if (editMode) {
            toggleCustomize();
        }
        
        // Save the reset state
        saveLayout();
        
        // Reload the page to ensure everything is fresh
        location.reload();
    }
}

// Add refresh functionality
function refreshRecommendations() {
    const button = document.querySelector('.refresh-button');
    button.style.pointerEvents = 'none'; // Prevent multiple clicks
    
    // Add loading state
    const originalText = button.innerHTML;
    button.innerHTML = '↻ Refreshing...';
    
    // Make the API call
    fetch('/refresh_recommendations', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
        },
        credentials: 'same-origin'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload(); // Refresh the page to show new recommendations
        } else {
            button.innerHTML = originalText;
            console.error('Failed to refresh recommendations');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        button.innerHTML = originalText;
    })
    .finally(() => {
        button.style.pointerEvents = 'auto';
    });
} 