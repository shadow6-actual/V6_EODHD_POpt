// ============================================================================
// FOLIOFORECAST - MAIN JAVASCRIPT (PHASE 5 - SUBSCRIPTION TIERS)
// Includes Group Constraints, Clerk Authentication, and Tier-based Feature Gating
// ============================================================================

let rowCount = 0;
let currentGroupData = null;
let clerkInstance = null;
let currentUser = null;
let userSubscription = null;

// ============================================================================
// SUBSCRIPTION TIER CONSTANTS (mirror backend)
// ============================================================================

const BASIC_METHODS = [
    'max_sharpe', 
    'min_volatility', 
    'equal_weight', 
    'risk_parity'
];
const ADVANCED_METHODS = [
    'min_vol_target_return',
    'max_return_target_vol',
    'min_cvar', 
    'min_cvar_target_return', 
    'max_return_target_cvar', 
    'min_tracking_error',
    'max_information_ratio', 
    'max_excess_return_target_te', 
    'max_kelly',
    'min_drawdown_target_return', 
    'max_omega_target_return', 
    'max_sortino_target_return'
];
const ROBUST_METHODS = [
    'robust_max_sharpe',
    'robust_min_volatility',
    'robust_min_vol_target_return',
    'robust_max_return_target_vol'
];

// ============================================================================
// CLERK AUTHENTICATION
// ============================================================================

window.addEventListener('load', async () => {
    await waitForClerk();
    initializeClerk();
});

function waitForClerk() {
    return new Promise((resolve) => {
        if (window.Clerk) {
            resolve();
        } else {
            const interval = setInterval(() => {
                if (window.Clerk) {
                    clearInterval(interval);
                    resolve();
                }
            }, 100);
            setTimeout(() => {
                clearInterval(interval);
                console.warn('Clerk failed to load');
                resolve();
            }, 10000);
        }
    });
}

async function initializeClerk() {
    try {
        clerkInstance = window.Clerk;
        
        if (!clerkInstance) {
            console.warn('Clerk not available');
            document.getElementById('authLoading').style.display = 'none';
            document.getElementById('signedOutButtons').style.display = 'block';
            applyTierRestrictions(); // Apply free tier restrictions
            return;
        }
        
        await clerkInstance.load();
        
        if (clerkInstance.user) {
            handleSignedIn(clerkInstance.user);
        } else {
            handleSignedOut();
        }
        
        clerkInstance.addListener(({ user }) => {
            if (user) {
                handleSignedIn(user);
            } else {
                handleSignedOut();
            }
        });
        
    } catch (error) {
        console.error('Clerk initialization error:', error);
        document.getElementById('authLoading').style.display = 'none';
        document.getElementById('signedOutButtons').style.display = 'block';
        applyTierRestrictions();
    }
}

async function handleSignedIn(user) {
    currentUser = user;
    
    document.getElementById('authLoading').style.display = 'none';
    document.getElementById('signedOutButtons').style.display = 'none';
    document.getElementById('signedInSection').style.display = 'flex';
    document.getElementById('usernameDisplay').innerText = user.username || 'User';
    
    // Show public portfolio option for signed-in users
    const publicOption = document.getElementById('publicPortfolioOption');
    if (publicOption) publicOption.style.display = 'block';
    
    await syncUserToBackend();
    console.log('Signed in as:', user.username);
}

function handleSignedOut() {
    currentUser = null;
    userSubscription = null;
    
    document.getElementById('authLoading').style.display = 'none';
    document.getElementById('signedOutButtons').style.display = 'block';
    document.getElementById('signedInSection').style.display = 'none';
    
    // Hide public portfolio option
    const publicOption = document.getElementById('publicPortfolioOption');
    if (publicOption) publicOption.style.display = 'none';
    
    applyTierRestrictions();
    console.log('Signed out');
}

async function syncUserToBackend() {
    try {
        const token = await clerkInstance.session.getToken();
        
        const response = await fetch('/api/auth/me', {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        userSubscription = data.subscription;
        console.log('User subscription:', userSubscription);
        
        applyTierRestrictions();
        
    } catch (error) {
        console.error('Failed to sync user:', error);
        applyTierRestrictions();
    }
}

async function getAuthToken() {
    if (!clerkInstance || !clerkInstance.session) {
        return null;
    }
    return await clerkInstance.session.getToken();
}

async function authenticatedFetch(url, options = {}) {
    const token = await getAuthToken();
    
    const headers = {
        ...options.headers,
        'Content-Type': 'application/json'
    };
    
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    return fetch(url, {
        ...options,
        headers
    });
}

// Clerk UI Functions
window.clerkSignIn = function() {
    if (clerkInstance) {
        clerkInstance.openSignIn();
    }
};

window.clerkSignUp = function() {
    if (clerkInstance) {
        clerkInstance.openSignUp();
    }
};

window.clerkSignOut = async function() {
    if (clerkInstance) {
        await clerkInstance.signOut();
    }
};

window.openUserProfile = function() {
    if (clerkInstance) {
        clerkInstance.openUserProfile();
    }
};

window.showMyPortfolios = async function() {
    alert('My Portfolios feature coming soon!');
};

// ============================================================================
// TIER-BASED FEATURE GATING
// ============================================================================

function getUserTier() {
    return userSubscription?.tier || 'free';
}

function canAccessFeature(featureName) {
    if (!userSubscription) return false;
    return userSubscription.features?.[featureName] || false;
}

function getMaxAssets() {
    return userSubscription?.max_assets || 5;
}

function applyTierRestrictions() {
    const tier = getUserTier();
    const maxAssets = getMaxAssets();
    
    console.log(`Applying tier restrictions: ${tier}, max assets: ${maxAssets}`);
    
    // Update optimization method dropdown
    updateOptimizationMethodsDropdown();
    
    // Update asset limit indicator
    updateAssetLimitIndicator();
    
    // Update feature toggles
    updateFeatureToggles();
    
    // Update CSV buttons
    updateCsvButtons();
    
    // Update group constraints
    updateGroupConstraintsAccess();
}

function updateOptimizationMethodsDropdown() {
    const select = document.getElementById('optGoal');
    if (!select) return;
    
    const tier = getUserTier();
    const canAdvanced = tier === 'premium' || tier === 'pro';
    const canRobust = tier === 'premium' || tier === 'pro';
    
    // Add lock icons and disable options
    Array.from(select.options).forEach(option => {
        const method = option.value;
        const originalText = option.getAttribute('data-original-text') || option.text.replace(' 🔒', '').replace(' (Premium)', '').replace(' (Pro)', '');
        option.setAttribute('data-original-text', originalText);
        
        if (ADVANCED_METHODS.includes(method) && !canAdvanced) {
            option.text = originalText + ' 🔒';
            option.disabled = true;
            option.style.color = '#6c757d';
        } else if (ROBUST_METHODS.includes(method) && !canRobust) {
            option.text = originalText + ' 🔒';
            option.disabled = true;
            option.style.color = '#6c757d';
        } else {
            option.text = originalText;
            option.disabled = false;
            option.style.color = '';
        }
    });
    
    // If current selection is locked, switch to max_sharpe
    const currentValue = select.value;
    if ((ADVANCED_METHODS.includes(currentValue) && !canAdvanced) ||
        (ROBUST_METHODS.includes(currentValue) && !canRobust)) {
        select.value = 'max_sharpe';
        updateConditionalFields();
    }
}

function updateAssetLimitIndicator() {
    const maxAssets = getMaxAssets();
    const tier = getUserTier();
    
    // Update the table header or add indicator
    const tableHeader = document.querySelector('#assetsTable thead');
    if (tableHeader) {
        let indicator = document.getElementById('assetLimitIndicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'assetLimitIndicator';
            indicator.className = 'small text-muted mb-2';
            tableHeader.parentElement.insertBefore(indicator, tableHeader.parentElement.firstChild);
        }
        
        const currentCount = document.querySelectorAll('#assetsTableBody tr').length;
        
        if (tier === 'pro') {
            indicator.innerHTML = `<i class="fas fa-infinity me-1"></i> Unlimited assets`;
        } else {
            const color = currentCount >= maxAssets ? 'text-danger' : 'text-muted';
            indicator.innerHTML = `<span class="${color}"><i class="fas fa-layer-group me-1"></i> ${currentCount}/${maxAssets} assets</span>`;
            if (currentCount >= maxAssets && tier !== 'pro') {
                indicator.innerHTML += ` <a href="/pricing" class="small text-primary">Upgrade for more</a>`;
            }
        }
    }
}

function updateFeatureToggles() {
    const tier = getUserTier();
    
    // Diversification Analytics (Pro only)
    const divToggle = document.getElementById('showDiversification');
    const divLabel = divToggle?.parentElement?.querySelector('label');
    
    if (divToggle && divLabel) {
        if (tier !== 'pro') {
            divToggle.checked = false;
            divToggle.disabled = true;
            divLabel.innerHTML = 'Show Diversification Analytics <span class="badge bg-warning text-dark">Pro</span>';
        } else {
            divToggle.disabled = false;
            divLabel.innerHTML = 'Show Diversification Analytics';
        }
    }
    
    // Health Score Card (Pro only)
    const healthCard = document.getElementById('healthScoreCard');
    if (healthCard) {
        healthCard.style.display = (tier === 'pro' && divToggle?.checked) ? 'block' : 'none';
    }
}

function updateCsvButtons() {
    const tier = getUserTier();
    const canCsv = tier === 'premium' || tier === 'pro';
    
    // Find CSV buttons and update them
    const csvButtonContainer = document.querySelector('.btn-group');
    if (csvButtonContainer) {
        const buttons = csvButtonContainer.querySelectorAll('button');
        buttons.forEach(btn => {
            if (btn.onclick?.toString().includes('CSV') || 
                btn.getAttribute('onclick')?.includes('CSV')) {
                if (!canCsv) {
                    btn.classList.add('disabled');
                    btn.setAttribute('data-original-onclick', btn.getAttribute('onclick'));
                    btn.setAttribute('onclick', 'showUpgradePrompt("csv_import_export", "CSV import/export")');
                    btn.title = 'Premium feature - click to upgrade';
                } else {
                    btn.classList.remove('disabled');
                    const originalOnclick = btn.getAttribute('data-original-onclick');
                    if (originalOnclick) {
                        btn.setAttribute('onclick', originalOnclick);
                    }
                    btn.title = '';
                }
            }
        });
    }
}

function updateGroupConstraintsAccess() {
    const tier = getUserTier();
    const canGroupConstraints = tier === 'pro';
    
    const groupCard = document.getElementById('groupConstraintsCard');
    const groupToggle = document.getElementById('useGroupConstraints');
    
    if (groupCard && !canGroupConstraints) {
        // Add Pro badge to header
        const header = groupCard.querySelector('.card-header h6');
        if (header && !header.innerHTML.includes('Pro')) {
            header.innerHTML = 'GROUP CONSTRAINTS <span class="badge bg-warning text-dark ms-2">Pro</span>';
        }
        
        if (groupToggle) {
            groupToggle.disabled = true;
            groupToggle.checked = false;
        }
    }
}

function showUpgradePrompt(feature, featureName) {
    const tier = getUserTier();
    
    let requiredTier = 'Premium';
    if (['diversification_analytics', 'health_score', 'group_constraints', 'view_others_allocations'].includes(feature)) {
        requiredTier = 'Pro';
    }
    
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'upgradeModal';
    modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content bg-dark text-light">
                <div class="modal-header border-secondary">
                    <h5 class="modal-title"><i class="fas fa-lock me-2"></i>Upgrade Required</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body text-center py-4">
                    <div class="mb-3">
                        <span class="display-1">🔒</span>
                    </div>
                    <h5 class="mb-3">${featureName}</h5>
                    <p class="text-muted">This feature requires a <strong>${requiredTier}</strong> subscription.</p>
                    <p class="small text-muted">You're currently on the <strong>${tier.charAt(0).toUpperCase() + tier.slice(1)}</strong> plan.</p>
                </div>
                <div class="modal-footer border-secondary justify-content-center">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Maybe Later</button>
                    <a href="/pricing" class="btn btn-primary"><i class="fas fa-arrow-up me-2"></i>View Plans</a>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    modal.addEventListener('hidden.bs.modal', () => {
        modal.remove();
    });
}

function handleTierError(response) {
    // Handle tier-related API errors
    if (response.error === 'login_required') {
        showLoginPrompt(response.message);
        return true;
    }
    if (response.upgrade_required) {
        showUpgradePrompt(response.feature || 'unknown', response.message);
        return true;
    }
    return false;
}

function showLoginPrompt(message) {
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'loginModal';
    modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content bg-dark text-light">
                <div class="modal-header border-secondary">
                    <h5 class="modal-title"><i class="fas fa-user me-2"></i>Sign In Required</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body text-center py-4">
                    <div class="mb-3">
                        <span class="display-1">👋</span>
                    </div>
                    <h5 class="mb-3">${message || 'Please sign in to continue'}</h5>
                    <p class="text-muted">Creating an account is free and takes just seconds.</p>
                </div>
                <div class="modal-footer border-secondary justify-content-center">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Maybe Later</button>
                    <button type="button" class="btn btn-primary" onclick="clerkSignIn(); bootstrap.Modal.getInstance(document.getElementById('loginModal')).hide();">
                        <i class="fas fa-sign-in-alt me-2"></i>Sign In
                    </button>
                    <button type="button" class="btn btn-success" onclick="clerkSignUp(); bootstrap.Modal.getInstance(document.getElementById('loginModal')).hide();">
                        <i class="fas fa-user-plus me-2"></i>Sign Up Free
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    modal.addEventListener('hidden.bs.modal', () => {
        modal.remove();
    });
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

window.setText = function(id, val) {
    const el = document.getElementById(id);
    if (el) el.innerText = val;
};

window.updateTotal = function() {
    const inputs = document.querySelectorAll('.asset-alloc');
    let sum = 0;
    inputs.forEach(input => sum += parseFloat(input.value || 0));
    
    const totalEl = document.getElementById('totalAllocation');
    if (totalEl) {
        totalEl.innerText = sum + '%';
        totalEl.className = sum === 100 
            ? 'text-success fw-bold' 
            : (sum > 100 ? 'text-danger fw-bold' : 'text-warning fw-bold');
    }
    
    updateGroupConstraintsDisplay();
    updateAssetLimitIndicator();
};

window.toggleUserBenchmark = function() {
    const checked = document.getElementById('useUserBenchmark').checked;
    const field = document.getElementById('userBenchmarkField');
    const standardBench = document.getElementById('benchmark');
    
    if (checked) {
        field.style.display = 'block';
        standardBench.disabled = true;
        loadUserBenchmarkOptions();
    } else {
        field.style.display = 'none';
        standardBench.disabled = false;
    }
};

window.toggleConstraints = function() {
    const checked = document.getElementById('useConstraints').checked;
    const cols = document.querySelectorAll('.constraint-col');
    cols.forEach(col => col.style.display = checked ? '' : 'none');
};

window.loadUserBenchmarkOptions = async function() {
    try {
        const res = await fetch('/api/portfolios');
        const portfolios = await res.json();
        
        const select = document.getElementById('userBenchmark');
        select.innerHTML = '<option value="">Select a saved portfolio...</option>';
        portfolios.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.text = p.name;
            select.appendChild(opt);
        });
    } catch(e) {
        console.error('Failed to load portfolios:', e);
    }
};

window.portfolioSelected = function() {
    const select = document.getElementById('portfolioManager');
    const deleteBtn = document.getElementById('deletePortfolioBtn');
    deleteBtn.disabled = !select.value;
};

window.deleteSelectedPortfolio = async function() {
    const select = document.getElementById('portfolioManager');
    const portfolioId = select.value;
    
    if (!portfolioId) return;
    
    const portfolioName = select.selectedOptions[0].text;
    if (!confirm(`Delete portfolio "${portfolioName}"?`)) return;
    
    try {
        const res = await fetch(`/api/portfolios/${portfolioId}`, { method: 'DELETE' });
        const data = await res.json();
        
        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            alert('Portfolio deleted');
            refreshPortfolioLists();
        }
    } catch(e) {
        alert('Delete failed: ' + e.message);
    }
};

window.refreshPortfolioLists = async function() {
    try {
        const res = await fetch('/api/portfolios');
        const portfolios = await res.json();
        
        const managerSelect = document.getElementById('portfolioManager');
        managerSelect.innerHTML = '<option value="">Select to manage...</option>';
        portfolios.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.text = p.name;
            managerSelect.appendChild(opt);
        });
        
        loadUserBenchmarkOptions();
    } catch(e) {
        console.error('Refresh portfolios error:', e);
    }
};

// ============================================================================
// GROUP CONSTRAINTS FUNCTIONS
// ============================================================================

async function fetchAssetMetadata(tickers) {
    if (!tickers || tickers.length === 0) return null;
    
    try {
        const res = await fetch('/api/asset-metadata', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({tickers: tickers})
        });
        
        if (!res.ok) return null;
        return await res.json();
    } catch(e) {
        console.error('Failed to fetch asset metadata:', e);
        return null;
    }
}

window.updateGroupConstraintsDisplay = async function() {
    const rows = document.querySelectorAll('#assetsTableBody tr');
    const tickers = [];
    const allocations = {};
    
    rows.forEach(row => {
        const ticker = row.querySelector('.asset-ticker').value.trim();
        if (ticker) {
            tickers.push(ticker);
            allocations[ticker] = parseFloat(row.querySelector('.asset-alloc').value) || 0;
        }
    });
    
    const card = document.getElementById('groupConstraintsCard');
    if (!card) return;
    
    if (tickers.length < 2) {
        card.style.display = 'none';
        return;
    }
    
    const optGoal = document.getElementById('optGoal').value;
    if (optGoal === 'equal_weight' || optGoal === 'risk_parity') {
        card.style.display = 'none';
        return;
    }
    
    const data = await fetchAssetMetadata(tickers);
    if (!data || !data.group_summary) {
        card.style.display = 'none';
        return;
    }
    
    currentGroupData = data;
    const groups = data.group_summary;
    
    if (Object.keys(groups).length < 2) {
        card.style.display = 'none';
        return;
    }
    
    card.style.display = 'block';
    updateGroupConstraintsAccess(); // Apply tier restrictions
    
    const tbody = document.getElementById('groupConstraintsBody');
    tbody.innerHTML = '';
    
    Object.entries(groups).sort().forEach(([groupName, groupInfo]) => {
        let currentAlloc = 0;
        groupInfo.tickers.forEach(ticker => {
            currentAlloc += allocations[ticker] || 0;
        });
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="small">${groupName}</td>
            <td class="small text-center">${groupInfo.count}</td>
            <td class="small text-center text-muted">${currentAlloc.toFixed(1)}%</td>
            <td>
                <input type="number" class="form-control form-control-sm group-min" 
                       data-group="${groupName}" value="" placeholder="0" min="0" max="100" step="1">
            </td>
            <td>
                <input type="number" class="form-control form-control-sm group-max" 
                       data-group="${groupName}" value="" placeholder="100" min="0" max="100" step="1">
            </td>
        `;
        tbody.appendChild(row);
    });
};

function collectGroupConstraints() {
    const constraints = {};
    const useGroupConstraints = document.getElementById('useGroupConstraints')?.checked;
    
    if (!useGroupConstraints) return constraints;
    
    const rows = document.querySelectorAll('#groupConstraintsBody tr');
    rows.forEach(row => {
        const groupName = row.querySelector('.group-min').dataset.group;
        const minVal = parseFloat(row.querySelector('.group-min').value);
        const maxVal = parseFloat(row.querySelector('.group-max').value);
        
        if (!isNaN(minVal) || !isNaN(maxVal)) {
            constraints[groupName] = {
                min: isNaN(minVal) ? 0 : minVal,
                max: isNaN(maxVal) ? 100 : maxVal
            };
        }
    });
    
    return constraints;
}

// ============================================================================
// CONDITIONAL FIELDS
// ============================================================================

window.updateConditionalFields = function() {
    const goal = document.getElementById('optGoal').value;
    
    document.getElementById('targetReturnField').style.display = 'none';
    document.getElementById('targetVolField').style.display = 'none';
    document.getElementById('targetCVaRField').style.display = 'none';
    document.getElementById('targetTEField').style.display = 'none';
    document.getElementById('robustResamplesField').style.display = 'none';
    
    // Show robust resamples for all robust methods
    if (goal.startsWith('robust_')) {
        document.getElementById('robustResamplesField').style.display = 'block';
    }
    
    // Target Return field
    if (['min_vol_target_return', 'min_cvar_target_return', 'min_drawdown_target_return', 
         'max_omega_target_return', 'max_sortino_target_return', 'robust_min_vol_target_return'].includes(goal)) {
        document.getElementById('targetReturnField').style.display = 'block';
    }
    
    // Target Volatility field
    if (['max_return_target_vol', 'robust_max_return_target_vol'].includes(goal)) {
        document.getElementById('targetVolField').style.display = 'block';
    }
    
    if (goal === 'max_return_target_cvar') {
        document.getElementById('targetCVaRField').style.display = 'block';
    }
    
    if (goal === 'max_excess_return_target_te') {
        document.getElementById('targetTEField').style.display = 'block';
    }
    
    updateGroupConstraintsDisplay();
};

// ============================================================================
// ASSET TABLE MANAGEMENT
// ============================================================================

window.addAssetRow = function(ticker = '', alloc = 0, min = '', max = '') {
    // Check asset limit
    const maxAssets = getMaxAssets();
    const currentCount = document.querySelectorAll('#assetsTableBody tr').length;
    
    if (currentCount >= maxAssets && getUserTier() !== 'pro') {
        showUpgradePrompt('max_assets', `Asset limit reached (${maxAssets} assets on ${getUserTier()} plan)`);
        return;
    }
    
    rowCount++;
    const tbody = document.getElementById('assetsTableBody');
    const tr = document.createElement('tr');
    tr.id = `row-${rowCount}`;
    tr.innerHTML = `
        <td>
            <div class="input-group input-group-sm position-relative">
                <input type="text" class="form-control asset-ticker" value="${ticker}" placeholder="Ticker" 
                       onkeyup="handleSearch(this, ${rowCount})" onblur="setTimeout(()=>hideSearch(${rowCount}), 200)"
                       onchange="updateGroupConstraintsDisplay()">
                <div id="searchResults-${rowCount}" class="list-group position-absolute w-100 shadow-sm" style="top: 100%; z-index: 1050; display: none;"></div>
            </div>
        </td>
        <td><input type="number" class="form-control form-control-sm asset-alloc" value="${alloc}" min="0" max="100" step="0.1" onchange="updateTotal()"></td>
        <td class="constraint-col"><input type="number" class="form-control form-control-sm asset-min" value="${min}" min="0" max="100" step="0.1"></td>
        <td class="constraint-col"><input type="number" class="form-control form-control-sm asset-max" value="${max}" min="0" max="100" step="0.1"></td>
        <td><button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="deleteAssetRow(${rowCount})"><i class="fas fa-times small"></i></button></td>
    `;
    tbody.appendChild(tr);
    updateTotal();
    
    if (ticker) {
        updateGroupConstraintsDisplay();
    }
};

window.deleteAssetRow = function(id) {
    const row = document.getElementById(`row-${id}`);
    if (row) {
        row.remove();
        updateTotal();
        updateGroupConstraintsDisplay();
    }
};

// ============================================================================
// TICKER SEARCH
// ============================================================================

let searchTimeout;
window.handleSearch = function(input, rowId) {
    clearTimeout(searchTimeout);
    const query = input.value.trim();
    const resultsDiv = document.getElementById(`searchResults-${rowId}`);
    
    if (query.length < 2) {
        resultsDiv.style.display = 'none';
        return;
    }
    
    searchTimeout = setTimeout(async () => {
        try {
            const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
            const data = await res.json();
            
            if (data.length === 0) {
                resultsDiv.style.display = 'none';
                return;
            }
            
            resultsDiv.innerHTML = '';
            data.forEach(asset => {
                const item = document.createElement('a');
                item.className = 'list-group-item list-group-item-action py-1 px-2 small';
                item.href = '#';
                item.innerHTML = `<strong>${asset.symbol}</strong> <span class="text-muted">${asset.name || ''}</span>`;
                item.onclick = (e) => {
                    e.preventDefault();
                    input.value = asset.symbol;
                    resultsDiv.style.display = 'none';
                    updateGroupConstraintsDisplay();
                };
                resultsDiv.appendChild(item);
            });
            
            resultsDiv.style.display = 'block';
        } catch(e) {
            console.error('Search error:', e);
        }
    }, 300);
};

window.hideSearch = function(rowId) {
    const resultsDiv = document.getElementById(`searchResults-${rowId}`);
    if (resultsDiv) resultsDiv.style.display = 'none';
};

// ============================================================================
// SAVE / LOAD PORTFOLIO
// ============================================================================

window.savePortfolio = async function() {
    const name = document.getElementById('portfolioName').value.trim();
    if (!name) {
        alert('Please enter a portfolio name');
        return;
    }
    
    const rows = document.querySelectorAll('#assetsTableBody tr');
    const tickers = [];
    const weights = {};
    const constraints = { assets: {} };

    rows.forEach(row => {
        const ticker = row.querySelector('.asset-ticker').value.trim();
        if (ticker) {
            tickers.push(ticker);
            weights[ticker] = parseFloat(row.querySelector('.asset-alloc').value) / 100.0 || 0;
            const minVal = parseFloat(row.querySelector('.asset-min').value);
            const maxVal = parseFloat(row.querySelector('.asset-max').value);
            if (!isNaN(minVal) || !isNaN(maxVal)) {
                constraints.assets[ticker] = {
                    min: (isNaN(minVal) ? 0 : minVal / 100.0),
                    max: (isNaN(maxVal) ? 1 : maxVal / 100.0)
                };
            }
        }
    });

    const isPublic = document.getElementById('makePortfolioPublic')?.checked || false;

    try {
        const res = await authenticatedFetch('/api/portfolios', {
            method: 'POST',
            body: JSON.stringify({ name, tickers, weights, constraints, is_public: isPublic })
        });
        const data = await res.json();
        
        if (data.error) {
            if (handleTierError(data)) return;
            alert('Error: ' + data.message || data.error);
        } else {
            let msg = data.message;
            if (data.portfolios_max && data.portfolios_max < 999) {
                msg += ` (${data.portfolios_used}/${data.portfolios_max} used)`;
            }
            alert(msg);
            document.getElementById('portfolioName').value = '';
            refreshPortfolioLists();
        }
    } catch(e) {
        alert('Save failed: ' + e.message);
    }
};

window.loadPortfolioModal = async function() {
    try {
        const res = await fetch('/api/portfolios');
        const portfolios = await res.json();
        
        const listDiv = document.getElementById('portfolioList');
        listDiv.innerHTML = '';
        
        if (portfolios.length === 0) {
            listDiv.innerHTML = '<div class="text-muted p-3">No saved portfolios</div>';
        } else {
            portfolios.forEach(p => {
                const item = document.createElement('button');
                item.className = 'list-group-item list-group-item-action d-flex justify-content-between';
                item.innerHTML = `
                    <span>${p.name}</span>
                    <small class="text-muted">${new Date(p.updated_at).toLocaleDateString()}</small>
                `;
                item.onclick = () => loadPortfolio(p.id);
                listDiv.appendChild(item);
            });
        }
        
        new bootstrap.Modal(document.getElementById('loadModal')).show();
    } catch(e) {
        alert('Load failed: ' + e.message);
    }
};

async function loadPortfolio(id) {
    try {
        const res = await fetch(`/api/portfolios/${id}`);
        const portfolio = await res.json();
        
        document.getElementById('assetsTableBody').innerHTML = '';
        rowCount = 0;
        
        portfolio.tickers.forEach(ticker => {
            const weight = (portfolio.weights[ticker] * 100) || 0;
            const minW = portfolio.constraints.assets && portfolio.constraints.assets[ticker] 
                ? (portfolio.constraints.assets[ticker].min * 100) : '';
            const maxW = portfolio.constraints.assets && portfolio.constraints.assets[ticker] 
                ? (portfolio.constraints.assets[ticker].max * 100) : '';
            addAssetRow(ticker, weight, minW, maxW);
        });
        
        document.getElementById('portfolioName').value = portfolio.name;
        bootstrap.Modal.getInstance(document.getElementById('loadModal')).hide();
    } catch(e) {
        alert('Load failed: ' + e.message);
    }
}

// ============================================================================
// CSV IMPORT/EXPORT
// ============================================================================

window.exportPortfolioCSV = async function() {
    // Check feature access
    if (!canAccessFeature('csv_import_export')) {
        showUpgradePrompt('csv_import_export', 'CSV Export');
        return;
    }
    
    const rows = document.querySelectorAll('#assetsTableBody tr');
    const tickers = [];
    const weights = {};
    const constraints = { assets: {} };

    rows.forEach(row => {
        const ticker = row.querySelector('.asset-ticker').value.trim();
        if (ticker) {
            tickers.push(ticker);
            weights[ticker] = parseFloat(row.querySelector('.asset-alloc').value) / 100.0 || 0;
            
            const minVal = parseFloat(row.querySelector('.asset-min').value);
            const maxVal = parseFloat(row.querySelector('.asset-max').value);
            
            if (!isNaN(minVal) || !isNaN(maxVal)) {
                constraints.assets[ticker] = {
                    min: isNaN(minVal) ? 0 : minVal / 100.0,
                    max: isNaN(maxVal) ? 1 : maxVal / 100.0
                };
            }
        }
    });

    if (tickers.length === 0) {
        alert('No assets to export');
        return;
    }

    try {
        const response = await authenticatedFetch('/api/portfolios/export-csv', {
            method: 'POST',
            body: JSON.stringify({ tickers, weights, constraints })
        });
        
        const data = await response.json();
        
        if (data.error) {
            if (handleTierError(data)) return;
            alert('Export error: ' + data.error);
            return;
        }
        
        const blob = new Blob([data.csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = data.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
    } catch (e) {
        alert('Export failed: ' + e.message);
    }
};

window.importPortfolioCSV = async function() {
    // Check feature access
    if (!canAccessFeature('csv_import_export')) {
        showUpgradePrompt('csv_import_export', 'CSV Import');
        return;
    }
    
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv,.txt';
    
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = async (event) => {
            const csvContent = event.target.result;
            
            try {
                const response = await authenticatedFetch('/api/portfolios/import-csv', {
                    method: 'POST',
                    body: JSON.stringify({ csv: csvContent })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    if (handleTierError(data)) return;
                    alert('Import error: ' + data.error);
                    return;
                }
                
                document.getElementById('assetsTableBody').innerHTML = '';
                rowCount = 0;
                
                data.tickers.forEach(ticker => {
                    const weight = (data.weights[ticker] || 0) * 100;
                    const assetConstraints = data.constraints.assets[ticker] || {};
                    const minW = assetConstraints.min !== undefined ? assetConstraints.min * 100 : '';
                    const maxW = assetConstraints.max !== undefined ? assetConstraints.max * 100 : '';
                    
                    addAssetRow(ticker, weight.toFixed(1), minW, maxW);
                });
                
                let msg = data.message;
                if (data.invalid_tickers && data.invalid_tickers.length > 0) {
                    msg += '\n\nNot found in database:\n' + data.invalid_tickers.join(', ');
                }
                alert(msg);
                
            } catch (e) {
                alert('Import failed: ' + e.message);
            }
        };
        
        reader.readAsText(file);
    };
    
    input.click();
};

window.quickPasteTickers = function() {
    const maxAssets = getMaxAssets();
    const tier = getUserTier();
    
    const input = prompt(
        `Enter tickers separated by commas:\n\n` +
        `Example: AAPL, MSFT, GOOGL, TLT, GLD\n\n` +
        `(Will auto-append .US if needed)\n` +
        `${tier !== 'pro' ? `\nNote: Your ${tier} plan allows up to ${maxAssets} assets` : ''}`
    );
    
    if (!input) return;
    
    let tickers = input.split(',')
        .map(t => t.trim().toUpperCase())
        .filter(t => t.length > 0)
        .map(t => t.includes('.') ? t : t + '.US');
    
    if (tickers.length === 0) {
        alert('No valid tickers entered');
        return;
    }
    
    // Enforce asset limit
    if (tickers.length > maxAssets && tier !== 'pro') {
        alert(`Your ${tier} plan allows up to ${maxAssets} assets. Only the first ${maxAssets} will be added.\n\nUpgrade to add more.`);
        tickers = tickers.slice(0, maxAssets);
    }
    
    document.getElementById('assetsTableBody').innerHTML = '';
    rowCount = 0;
    
    const equalWeight = (100 / tickers.length).toFixed(1);
    
    tickers.forEach(ticker => {
        addAssetRow(ticker, equalWeight, '', '');
    });
    
    alert(`Added ${tickers.length} tickers with equal weights (${equalWeight}% each)`);
};

// ============================================================================
// DOM READY
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    const today = new Date().toISOString().split('T')[0];
    const endInput = document.getElementById('endDate');
    if (endInput && !endInput.value) {
        endInput.value = today;
    }
    
    // Default assets
    addAssetRow('AAPL.US', 25);
    addAssetRow('MSFT.US', 25);
    addAssetRow('TLT.US', 25);
    addAssetRow('GLD.US', 25);
    
    refreshPortfolioLists();
    
    document.getElementById('runOptimizeBtn').addEventListener('click', runOptimization);
    
    document.querySelectorAll('.health-weight').forEach(input => {
        input.addEventListener('change', updateHealthWeightTotal);
    });
    
    document.getElementById('showDiversification')?.addEventListener('change', function() {
        const tier = getUserTier();
        if (tier !== 'pro' && this.checked) {
            this.checked = false;
            showUpgradePrompt('diversification_analytics', 'Diversification Analytics');
            return;
        }
        document.getElementById('healthScoreCard').style.display = this.checked ? 'block' : 'none';
    });
});

function updateHealthWeightTotal() {
    const sharpe = parseInt(document.getElementById('healthSharpe').value) || 0;
    const divRatio = parseInt(document.getElementById('healthDivRatio').value) || 0;
    const hhi = parseInt(document.getElementById('healthHHI').value) || 0;
    const drawdown = parseInt(document.getElementById('healthDrawdown').value) || 0;
    
    const total = sharpe + divRatio + hhi + drawdown;
    const totalEl = document.getElementById('healthWeightTotal');
    totalEl.innerText = total;
    totalEl.className = total === 100 ? 'small fw-bold text-success' : 'small fw-bold text-danger';
}

// ============================================================================
// OPTIMIZATION REQUEST
// ============================================================================

async function runOptimization() {
    const rows = document.querySelectorAll('#assetsTableBody tr');
    const tickers = [];
    const user_weights = {};
    const constraints = { assets: {} };

    rows.forEach(row => {
        const ticker = row.querySelector('.asset-ticker').value.trim();
        if (ticker) {
            tickers.push(ticker);
            user_weights[ticker] = parseFloat(row.querySelector('.asset-alloc').value) / 100.0 || 0;
            
            const minVal = parseFloat(row.querySelector('.asset-min').value);
            const maxVal = parseFloat(row.querySelector('.asset-max').value);
            
            constraints.assets[ticker] = {
                min: (isNaN(minVal) ? 0 : minVal / 100.0),
                max: (isNaN(maxVal) ? 1 : maxVal / 100.0)
            };
        }
    });

    if (tickers.length < 2) {
        alert("Please add at least 2 assets.");
        return;
    }

    document.getElementById('resultsPlaceholder').style.display = 'none';
    document.getElementById('resultsContent').style.display = 'none';
    document.getElementById('loadingSpinner').style.display = 'block';

    const useConstraints = document.getElementById('useConstraints').checked;
    const useGroupConstraints = document.getElementById('useGroupConstraints')?.checked || false;
    const groupConstraints = useGroupConstraints ? collectGroupConstraints() : {};
    const showDiversification = document.getElementById('showDiversification')?.checked || false;
    
    let healthScoreWeights = null;
    if (showDiversification) {
        const sharpe = parseInt(document.getElementById('healthSharpe').value) || 40;
        const divRatio = parseInt(document.getElementById('healthDivRatio').value) || 30;
        const hhi = parseInt(document.getElementById('healthHHI').value) || 10;
        const drawdown = parseInt(document.getElementById('healthDrawdown').value) || 20;
        
        if (sharpe + divRatio + hhi + drawdown === 100) {
            healthScoreWeights = { sharpe, div_ratio: divRatio, hhi, drawdown };
        }
    }

    try {
        const useUserBench = document.getElementById('useUserBenchmark').checked;
        const userBenchmarkId = useUserBench ? document.getElementById('userBenchmark').value : null;
        const optGoal = document.getElementById('optGoal').value;
        
        const response = await authenticatedFetch('/api/optimize', {
            method: 'POST',
            body: JSON.stringify({
                tickers: tickers,
                user_weights: user_weights,
                constraints: useConstraints ? constraints : {},
                use_group_constraints: useGroupConstraints,
                group_constraints: groupConstraints,
                optimization_goal: optGoal,
                target_return: document.getElementById('targetReturn').value,
                target_volatility: document.getElementById('targetVolatility').value,
                target_cvar: document.getElementById('targetCVaR').value,
                target_tracking_error: document.getElementById('targetTE').value,
                benchmark: document.getElementById('benchmark').value,
                user_benchmark_id: userBenchmarkId,
                start_date: document.getElementById('startDate').value,
                end_date: document.getElementById('endDate').value,
                include_diversification: showDiversification,
                health_score_weights: healthScoreWeights,
                robust_resamples: optGoal.startsWith('robust_') ? parseInt(document.getElementById('robustResamples').value) : null
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            if (handleTierError(data)) {
                document.getElementById('resultsPlaceholder').style.display = 'block';
            } else if (data.error === 'coverage_gap') {
                alert(data.message + "\n\nSuggested Start: " + data.suggested_start_date);
                document.getElementById('resultsPlaceholder').style.display = 'block';
            } else {
                alert("Error: " + (data.message || data.error));
                document.getElementById('resultsPlaceholder').style.display = 'block';
            }
        } else {
            renderResults(data);
        }
        
    } catch (err) {
        console.error('Optimization failed:', err);
        alert("System Error: " + err.message);
        document.getElementById('resultsPlaceholder').style.display = 'block';
    } finally {
        document.getElementById('loadingSpinner').style.display = 'none';
    }
}

// ============================================================================
// RESULTS RENDERING
// ============================================================================

function renderResults(data) {
    document.getElementById('resultsContent').style.display = 'block';
    
    const opt = data.optimized_portfolio;
    const user = data.user_portfolio;
    const bench = data.benchmark_portfolio;
    
    const goalName = document.getElementById('optGoal').selectedOptions[0].text.replace(' 🔒', '');
    setText('optCardTitle', goalName);
    
    if (bench && bench.name) {
        setText('benchCardTitle', bench.name);
        setText('colBench', bench.name);
    } else {
        setText('benchCardTitle', 'Benchmark');
        setText('colBench', 'Benchmark');
    }
    
    // Comparison Table
    const metrics = [
        {label: 'Annualized Return (CAGR)', key: 'return', suffix: '%'},
        {label: 'Standard Deviation', key: 'volatility', suffix: '%'},
        {label: 'Sharpe Ratio', key: 'sharpe_ratio', suffix: ''},
        {label: 'Sortino Ratio', key: 'sortino_ratio', suffix: ''},
        {label: 'Max Drawdown', key: 'max_drawdown', suffix: '%'},
        {label: 'VaR (95%, Daily)', key: 'var_95_daily', suffix: '%'},
        {label: 'CVaR (95%)', key: 'cvar_95_daily', suffix: '%'}
    ];
    
    const tbody = document.getElementById('comparisonBody');
    tbody.innerHTML = '';
    
    metrics.forEach(m => {
        const row = document.createElement('tr');
        const optVal = opt[m.key] !== undefined ? opt[m.key] + m.suffix : 'N/A';
        const userVal = user && user[m.key] !== undefined ? user[m.key] + m.suffix : '-';
        const benchVal = bench && bench[m.key] !== undefined ? bench[m.key] + m.suffix : '-';
        
        row.innerHTML = `
            <td>${m.label}</td>
            <td>${userVal}</td>
            <td class="fw-bold text-primary">${optVal}</td>
            <td class="text-muted">${benchVal}</td>
        `;
        tbody.appendChild(row);
    });
    
    // Diversification metrics (Pro only)
    if (data.diversification && data.tier_info?.diversification_enabled) {
        const divData = data.diversification;
        const optDiv = divData.optimized;
        const userDiv = divData.user;
        const benchDiv = divData.benchmark;
        
        const sepRow = document.createElement('tr');
        sepRow.innerHTML = `<td colspan="4" class="bg-light small text-muted fw-bold pt-2">DIVERSIFICATION METRICS <span class="badge bg-warning text-dark">Pro</span></td>`;
        tbody.appendChild(sepRow);
        
        const divMetrics = [
            {label: 'Portfolio Health Score', key: 'health_score', suffix: '/100', decimals: 1},
            {label: 'HHI (Concentration)', key: 'hhi', suffix: '', decimals: 4},
            {label: 'Diversification Ratio', key: 'diversification_ratio', suffix: '', decimals: 2},
            {label: 'Effective # of Bets', key: 'effective_num_bets', suffix: '', decimals: 1}
        ];
        
        divMetrics.forEach(m => {
            const row = document.createElement('tr');
            
            const formatVal = (divObj) => {
                if (!divObj || divObj[m.key] === undefined) return '-';
                return divObj[m.key].toFixed(m.decimals) + m.suffix;
            };
            
            row.innerHTML = `
                <td>${m.label}</td>
                <td>${formatVal(userDiv)}</td>
                <td class="fw-bold text-primary">${formatVal(optDiv)}</td>
                <td class="text-muted">${formatVal(benchDiv)}</td>
            `;
            tbody.appendChild(row);
        });
    }
    
    // Allocation Tables
    const optTable = document.getElementById('optTable');
    optTable.innerHTML = '';
    Object.entries(opt.weights).sort((a, b) => b[1] - a[1]).forEach(([ticker, weight]) => {
        optTable.innerHTML += `<tr><td>${ticker}</td><td class="text-end fw-bold">${weight}%</td></tr>`;
    });
    
    const yourTable = document.getElementById('yourTable');
    if (user && user.weights) {
        yourTable.innerHTML = '';
        Object.entries(user.weights).sort((a, b) => b[1] - a[1]).forEach(([ticker, weight]) => {
            yourTable.innerHTML += `<tr><td>${ticker}</td><td class="text-end">${weight}%</td></tr>`;
        });
    } else {
        yourTable.innerHTML = '<tr><td colspan="2" class="text-center text-muted p-3">No allocation</td></tr>';
    }
    
    const benchTable = document.getElementById('benchTable');
    if (bench && bench.weights) {
        benchTable.innerHTML = '';
        Object.entries(bench.weights).sort((a, b) => b[1] - a[1]).forEach(([ticker, weight]) => {
            benchTable.innerHTML += `<tr><td>${ticker}</td><td class="text-end">${weight}%</td></tr>`;
        });
    } else {
        benchTable.innerHTML = '<tr><td colspan="2" class="text-center text-muted p-3">No benchmark</td></tr>';
    }
    
    // Group Allocations
    if (data.group_allocations) {
        const groupAllocSection = document.getElementById('groupAllocationsSection');
        if (groupAllocSection) {
            groupAllocSection.style.display = 'block';
            
            const groupAllocBody = document.getElementById('groupAllocBody');
            groupAllocBody.innerHTML = '';
            
            const allGroups = new Set([
                ...Object.keys(data.group_allocations.user || {}),
                ...Object.keys(data.group_allocations.optimized || {})
            ]);
            
            allGroups.forEach(group => {
                const userAlloc = data.group_allocations.user[group] || 0;
                const optAlloc = data.group_allocations.optimized[group] || 0;
                const constraint = data.group_allocations.constraints[group];
                
                let constraintText = '-';
                let violationClass = '';
                
                if (constraint) {
                    const minBound = constraint.min || 0;
                    const maxBound = constraint.max || 100;
                    constraintText = `${minBound}% - ${maxBound}%`;
                    
                    if (optAlloc < minBound || optAlloc > maxBound) {
                        violationClass = 'table-danger';
                    }
                }
                
                const row = document.createElement('tr');
                row.className = violationClass;
                row.innerHTML = `
                    <td>${group}</td>
                    <td class="text-end">${userAlloc.toFixed(1)}%</td>
                    <td class="text-end fw-bold text-primary">${optAlloc.toFixed(1)}%</td>
                    <td class="text-center text-muted small">${constraintText}</td>
                `;
                groupAllocBody.appendChild(row);
            });
        }
    } else {
        const groupAllocSection = document.getElementById('groupAllocationsSection');
        if (groupAllocSection) {
            groupAllocSection.style.display = 'none';
        }
    }
    
    // Charts
    if (typeof Plotly !== 'undefined') {
        // Efficient Frontier
        const scatterX = data.frontier_scatter.map(p => p.volatility);
        const scatterY = data.frontier_scatter.map(p => p.return);

        const traces = [{
            x: scatterX, 
            y: scatterY, 
            mode: 'markers', 
            type: 'scatter', 
            marker: { color: scatterY, colorscale: 'Viridis', size: 6, opacity: 0.6 }, 
            name: 'Portfolios',
            hovertemplate: 'Risk: %{x:.2f}%<br>Return: %{y:.2f}%<extra></extra>'
        },
        {
            x: [opt.volatility], 
            y: [opt.return], 
            mode: 'markers+text', 
            marker: { color: '#dc3545', size: 16, symbol: 'star', line: {color: 'white', width: 2} }, 
            text: ['Optimized'],
            textposition: 'top center',
            name: 'Optimized'
        }];
        
        if (user) {
            traces.push({
                x: [user.volatility], 
                y: [user.return], 
                mode: 'markers+text', 
                marker: { color: '#6c757d', size: 14, symbol: 'circle', line: {color: 'white', width: 2} }, 
                text: ['Your'],
                textposition: 'bottom center',
                name: 'Your Portfolio'
            });
        }
        
        if (bench) {
            traces.push({
                x: [bench.volatility], 
                y: [bench.return], 
                mode: 'markers+text', 
                marker: { color: '#28a745', size: 14, symbol: 'diamond', line: {color: 'white', width: 2} }, 
                text: ['Benchmark'],
                textposition: 'top right',
                name: 'Benchmark'
            });
        }

        Plotly.newPlot('frontierChart', traces, {
            title: {text: 'Efficient Frontier', font: {size: 16}},
            xaxis: {title: 'Volatility (%)', showgrid: true},
            yaxis: {title: 'Return (%)', showgrid: true},
            hovermode: 'closest',
            plot_bgcolor: '#f8f9fa'
        });

        // Drawdown
        if (opt.drawdown_curve && opt.drawdown_curve.length > 0) {
            const dates = opt.drawdown_curve.map(d => d.date);
            const vals = opt.drawdown_curve.map(d => d.value * 100);
            
            Plotly.newPlot('drawdownChart', [{
                x: dates, 
                y: vals, 
                fill: 'tozeroy', 
                type: 'scatter', 
                line: {color: '#d9534f', width: 2},
                fillcolor: 'rgba(217, 83, 79, 0.1)'
            }], {
                title: {text: 'Portfolio Drawdown', font: {size: 16}},
                xaxis: {title: 'Date'},
                yaxis: {title: 'Drawdown (%)'},
                hovermode: 'x unified',
                plot_bgcolor: '#f8f9fa',
                height: 400
            });
        }

        // Stress Tests
        const stressBody = document.getElementById('stressTableBody');
        stressBody.innerHTML = '';
        if (opt.stress_tests && opt.stress_tests.length > 0) {
            opt.stress_tests.forEach(test => {
                const color = test.return >= 0 ? 'text-success' : 'text-danger';
                stressBody.innerHTML += `<tr>
                    <td>${test.name}</td>
                    <td>${test.start}</td>
                    <td>${test.end}</td>
                    <td class="text-end ${color} fw-bold">${test.return}%</td>
                </tr>`;
            });
        }

        // Monthly Heatmap
        if (opt.monthly_heatmap) {
            const hm = opt.monthly_heatmap;
            const dynamicHeight = Math.max(450, (hm.years.length * 45) + 120);
            
            Plotly.newPlot('monthlyHeatmap', [{
                z: hm.z,
                x: hm.months,
                y: hm.years,
                type: 'heatmap',
                colorscale: [
                    [0, '#d32f2f'],
                    [0.4, '#ff6b6b'],
                    [0.5, '#ffffff'],
                    [0.6, '#81c784'],
                    [1, '#2e7d32']
                ],
                zmid: 0,
                xgap: 3,
                ygap: 3,
                hovertemplate: '%{y} %{x}: %{z:.2f}%<extra></extra>',
                colorbar: {title: 'Return %'}
            }], {
                height: dynamicHeight,
                title: {text: 'Monthly Returns (%)', font: {size: 16}},
                xaxis: {side: 'top'},
                yaxis: {type: 'category', dtick: 1, autorange: 'reversed'},
                plot_bgcolor: '#ffffff'
            });
        }

        // Correlation Matrix
        const corrData = data.correlation_matrix;
        const assets = Object.keys(corrData);
        const z = assets.map(r => assets.map(c => corrData[r][c]));
        
        const annotations = [];
        for (let i = 0; i < assets.length; i++) {
            for (let j = 0; j < assets.length; j++) {
                annotations.push({
                    x: assets[j],
                    y: assets[i],
                    text: z[i][j].toFixed(2),
                    font: {
                        color: Math.abs(z[i][j]) > 0.5 ? 'white' : 'black',
                        size: 11
                    },
                    showarrow: false
                });
            }
        }
        
        Plotly.newPlot('corrHeatmap', [{
            z: z,
            x: assets,
            y: assets,
            type: 'heatmap',
            colorscale: [
                [0, '#d32f2f'],
                [0.5, '#ffffff'],
                [1, '#1976d2']
            ],
            zmin: -1,
            zmax: 1,
            hovertemplate: '%{y} vs %{x}: %{z:.2f}<extra></extra>',
            colorbar: {title: 'Correlation'},
            showscale: true
        }], {
            title: {text: 'Asset Correlation Matrix', font: {size: 16}},
            xaxis: {tickangle: -45, side: 'bottom'},
            yaxis: {autorange: 'reversed'},
            height: 500,
            annotations: annotations
        });
        
        // Diversification Tab
        if (data.diversification && data.tier_info?.diversification_enabled) {
            renderDiversificationMetrics(data.diversification);
        } else {
            // Show upgrade prompt in diversification tab
            const divBody = document.getElementById('diversificationBody');
            if (divBody) {
                divBody.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center py-4">
                            <i class="fas fa-lock fa-2x text-muted mb-3"></i>
                            <p class="mb-2">Diversification Analytics requires Pro subscription</p>
                            <a href="/pricing" class="btn btn-sm btn-primary">Upgrade to Pro</a>
                        </td>
                    </tr>
                `;
            }
            
            // Hide health score cards
            document.getElementById('optHealthScore').innerText = '🔒';
            document.getElementById('userHealthScore').innerText = '🔒';
            document.getElementById('benchHealthScore').innerText = '🔒';
        }
    }
}

function renderDiversificationMetrics(divData) {
    const optDiv = divData.optimized;
    const userDiv = divData.user;
    const benchDiv = divData.benchmark;
    
    document.getElementById('optHealthScore').innerText = optDiv ? optDiv.health_score : '--';
    document.getElementById('userHealthScore').innerText = userDiv ? userDiv.health_score : '--';
    document.getElementById('benchHealthScore').innerText = benchDiv ? benchDiv.health_score : '--';
    
    const scoreColor = (score) => {
        if (!score) return '';
        if (score >= 70) return 'text-success';
        if (score >= 40) return 'text-warning';
        return 'text-danger';
    };
    
    document.getElementById('optHealthScore').className = `display-4 mb-0 ${scoreColor(optDiv?.health_score)}`;
    document.getElementById('userHealthScore').className = `display-4 mb-0 ${scoreColor(userDiv?.health_score)}`;
    document.getElementById('benchHealthScore').className = `display-4 mb-0 ${scoreColor(benchDiv?.health_score)}`;
    
    const tbody = document.getElementById('diversificationBody');
    tbody.innerHTML = '';
    
    const metrics = [
        {
            label: 'HHI (Concentration)',
            key: 'hhi',
            format: v => v?.toFixed(4) || '-',
            interpret: optDiv?.hhi_interpretation || '-'
        },
        {
            label: 'Diversification Ratio',
            key: 'diversification_ratio',
            format: v => v?.toFixed(2) || '-',
            interpret: optDiv?.dr_interpretation || '-'
        },
        {
            label: 'Effective # of Bets',
            key: 'effective_num_bets',
            format: v => v?.toFixed(1) || '-',
            interpret: optDiv?.enb_interpretation || '-'
        },
        {
            label: 'Health Score',
            key: 'health_score',
            format: v => v ? `${v}/100` : '-',
            interpret: 'Composite quality metric'
        }
    ];
    
    metrics.forEach(m => {
        const row = document.createElement('tr');
        const userVal = userDiv ? m.format(userDiv[m.key]) : '-';
        const optVal = optDiv ? m.format(optDiv[m.key]) : '-';
        const benchVal = benchDiv ? m.format(benchDiv[m.key]) : '-';
        
        row.innerHTML = `
            <td>${m.label}</td>
            <td class="text-center">${userVal}</td>
            <td class="text-center fw-bold text-primary">${optVal}</td>
            <td class="text-center text-muted">${benchVal}</td>
            <td class="small text-muted">${m.interpret}</td>
        `;
        tbody.appendChild(row);
    });
    
    // Radar chart
    if (optDiv && optDiv.health_components && typeof Plotly !== 'undefined') {
        const categories = ['Sharpe', 'Diversification', 'Concentration', 'Drawdown'];
        
        const traces = [];
        
        traces.push({
            type: 'scatterpolar',
            r: [
                optDiv.health_components.sharpe_score,
                optDiv.health_components.div_ratio_score,
                optDiv.health_components.hhi_score,
                optDiv.health_components.drawdown_score,
                optDiv.health_components.sharpe_score
            ],
            theta: [...categories, categories[0]],
            fill: 'toself',
            name: 'Optimized',
            line: {color: '#0d6efd'},
            fillcolor: 'rgba(13, 110, 253, 0.2)'
        });
        
        if (userDiv && userDiv.health_components) {
            traces.push({
                type: 'scatterpolar',
                r: [
                    userDiv.health_components.sharpe_score,
                    userDiv.health_components.div_ratio_score,
                    userDiv.health_components.hhi_score,
                    userDiv.health_components.drawdown_score,
                    userDiv.health_components.sharpe_score
                ],
                theta: [...categories, categories[0]],
                fill: 'toself',
                name: 'Your Portfolio',
                line: {color: '#6c757d'},
                fillcolor: 'rgba(108, 117, 125, 0.2)'
            });
        }
        
        if (benchDiv && benchDiv.health_components) {
            traces.push({
                type: 'scatterpolar',
                r: [
                    benchDiv.health_components.sharpe_score,
                    benchDiv.health_components.div_ratio_score,
                    benchDiv.health_components.hhi_score,
                    benchDiv.health_components.drawdown_score,
                    benchDiv.health_components.sharpe_score
                ],
                theta: [...categories, categories[0]],
                fill: 'toself',
                name: 'Benchmark',
                line: {color: '#198754'},
                fillcolor: 'rgba(25, 135, 84, 0.2)'
            });
        }
        
        Plotly.newPlot('radarChart', traces, {
            polar: {
                radialaxis: {
                    visible: true,
                    range: [0, 100]
                }
            },
            showlegend: true,
            title: {text: 'Health Score Components (0-100)', font: {size: 16}},
            height: 450
        });
    }
}
