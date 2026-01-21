// ============================================================================
// PORTFOLIO OPTIMIZER V6 - MAIN JAVASCRIPT (PHASE 3)
// Includes Group Constraints functionality
// ============================================================================

let rowCount = 0;
let currentGroupData = null; // Stores current group metadata

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
    
    // Update group constraints display when allocations change
    updateGroupConstraintsDisplay();
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
        
        // Update manager dropdown
        const managerSelect = document.getElementById('portfolioManager');
        managerSelect.innerHTML = '<option value="">Select to manage...</option>';
        portfolios.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.text = p.name;
            managerSelect.appendChild(opt);
        });
        
        // Update user benchmark dropdown
        loadUserBenchmarkOptions();
    } catch(e) {
        console.error('Refresh portfolios error:', e);
    }
};

// ============================================================================
// GROUP CONSTRAINTS FUNCTIONS (NEW)
// ============================================================================

async function fetchAssetMetadata(tickers) {
    /**
     * Fetch asset metadata including group classifications
     * Returns: {metadata: {}, group_summary: {}}
     */
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
    /**
     * Updates the group constraints UI based on current tickers
     * Called when: tickers change, allocations change, optimization method changes
     */
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
    if (!card) return; // Card not yet in DOM
    
    // Hide if less than 2 tickers or incompatible optimization method
    if (tickers.length < 2) {
        card.style.display = 'none';
        return;
    }
    
    // Check if current optimization method allows group constraints
    const optGoal = document.getElementById('optGoal').value;
    if (optGoal === 'equal_weight' || optGoal === 'risk_parity') {
        card.style.display = 'none';
        return;
    }
    
    // Fetch metadata
    const data = await fetchAssetMetadata(tickers);
    if (!data || !data.group_summary) {
        card.style.display = 'none';
        return;
    }
    
    currentGroupData = data;
    const groups = data.group_summary;
    
    // Hide if only 1 group
    if (Object.keys(groups).length < 2) {
        card.style.display = 'none';
        return;
    }
    
    // Show card and populate table
    card.style.display = 'block';
    
    const tbody = document.getElementById('groupConstraintsBody');
    tbody.innerHTML = '';
    
    // Calculate current group allocations
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
    /**
     * Collects group constraint inputs from the UI
     * Returns: {GroupName: {min: number, max: number}}
     */
    const constraints = {};
    const useGroupConstraints = document.getElementById('useGroupConstraints')?.checked;
    
    if (!useGroupConstraints) return constraints;
    
    const rows = document.querySelectorAll('#groupConstraintsBody tr');
    rows.forEach(row => {
        const groupName = row.querySelector('.group-min').dataset.group;
        const minVal = parseFloat(row.querySelector('.group-min').value);
        const maxVal = parseFloat(row.querySelector('.group-max').value);
        
        // Only include if at least one bound is set
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
// CONDITIONAL FIELDS (MODIFIED TO INCLUDE GROUP CONSTRAINTS)
// ============================================================================

window.updateConditionalFields = function() {
    const goal = document.getElementById('optGoal').value;
    
    // Hide all conditional fields first
    document.getElementById('targetReturnField').style.display = 'none';
    document.getElementById('targetVolField').style.display = 'none';
    document.getElementById('targetCVaRField').style.display = 'none';
    document.getElementById('targetTEField').style.display = 'none';
    document.getElementById('robustResamplesField').style.display = 'none';
    
    // Show robust resamples for robust methods
    if (goal.startsWith('robust_')) {
        document.getElementById('robustResamplesField').style.display = 'block';
    }
    
    // Show relevant field based on goal
    if (goal === 'min_vol_target_return' || 
        goal === 'min_cvar_target_return' || 
        goal === 'min_drawdown_target_return' || 
        goal === 'max_omega_target_return' || 
        goal === 'max_sortino_target_return') {
        document.getElementById('targetReturnField').style.display = 'block';
    }
    
    if (goal === 'max_return_target_vol') {
        document.getElementById('targetVolField').style.display = 'block';
    }
    
    if (goal === 'max_return_target_cvar') {
        document.getElementById('targetCVaRField').style.display = 'block';
    }
    
    if (goal === 'max_excess_return_target_te') {
        document.getElementById('targetTEField').style.display = 'block';
    }
    
    // Update group constraints visibility (NEW)
    updateGroupConstraintsDisplay();
};

// ============================================================================
// ASSET TABLE MANAGEMENT
// ============================================================================

window.addAssetRow = function(ticker = '', alloc = 0, min = '', max = '') {
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
    
    // Trigger group constraints update if ticker is already filled
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

    try {
        const res = await fetch('/api/portfolios', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name, tickers, weights, constraints })
        });
        const data = await res.json();
        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            alert('Portfolio saved successfully!');
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
        
        // Clear current assets
        document.getElementById('assetsTableBody').innerHTML = '';
        rowCount = 0;
        
        // Load assets
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
// CSV IMPORT/EXPORT FUNCTIONS
// ============================================================================

window.exportPortfolioCSV = async function() {
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
        const response = await fetch('/api/portfolios/export-csv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tickers, weights, constraints })
        });
        
        const data = await response.json();
        
        if (data.error) {
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
                const response = await fetch('/api/portfolios/import-csv', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ csv: csvContent })
                });
                
                const data = await response.json();
                
                if (data.error) {
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
    const input = prompt(
        'Enter tickers separated by commas:\n\n' +
        'Example: AAPL, MSFT, GOOGL, TLT, GLD\n\n' +
        '(Will auto-append .US if needed)'
    );
    
    if (!input) return;
    
    const tickers = input.split(',')
        .map(t => t.trim().toUpperCase())
        .filter(t => t.length > 0)
        .map(t => t.includes('.') ? t : t + '.US');
    
    if (tickers.length === 0) {
        alert('No valid tickers entered');
        return;
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
    
    // Load portfolio lists
    refreshPortfolioLists();
    
    document.getElementById('runOptimizeBtn').addEventListener('click', runOptimization);
    
    // Health score weight validation
    document.querySelectorAll('.health-weight').forEach(input => {
        input.addEventListener('change', updateHealthWeightTotal);
    });
    
    // Show/hide health score settings based on diversification toggle
    document.getElementById('showDiversification').addEventListener('change', function() {
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
// OPTIMIZATION REQUEST (MODIFIED TO INCLUDE GROUP CONSTRAINTS)
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
    const showDiversification = document.getElementById('showDiversification').checked;
    
    // Collect health score weights if customized
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
        
        const response = await fetch('/api/optimize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
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
            if (data.error === 'coverage_gap') {
                alert(data.message + "\n\nSuggested Start: " + data.suggested_start_date);
            } else {
                alert("Error: " + data.message || data.error);
            }
            document.getElementById('resultsPlaceholder').style.display = 'block';
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
// RESULTS RENDERING (MODIFIED TO SHOW GROUP ALLOCATIONS)
// ============================================================================

function renderResults(data) {
    document.getElementById('resultsContent').style.display = 'block';
    
    const opt = data.optimized_portfolio;
    const user = data.user_portfolio;
    const bench = data.benchmark_portfolio;
    
    // Update card titles
    const goalName = document.getElementById('optGoal').selectedOptions[0].text;
    setText('optCardTitle', goalName);
    
    // Update benchmark title dynamically
    if (bench && bench.name) {
        setText('benchCardTitle', bench.name);
        setText('colBench', bench.name);
    } else {
        setText('benchCardTitle', 'Benchmark');
        setText('colBench', 'Benchmark');
    }
    
    // ========================================================================
    // COMPARISON TABLE
    // ========================================================================
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
    
    // Add diversification metrics if available
    if (data.diversification) {
        const divData = data.diversification;
        const optDiv = divData.optimized;
        const userDiv = divData.user;
        const benchDiv = divData.benchmark;
        
        // Add separator row
        const sepRow = document.createElement('tr');
        sepRow.innerHTML = `<td colspan="4" class="bg-light small text-muted fw-bold pt-2">DIVERSIFICATION METRICS</td>`;
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
    
    // ========================================================================
    // ALLOCATION TABLES
    // ========================================================================
    
    // Optimized Portfolio Table
    const optTable = document.getElementById('optTable');
    optTable.innerHTML = '';
    Object.entries(opt.weights).sort((a, b) => b[1] - a[1]).forEach(([ticker, weight]) => {
        optTable.innerHTML += `<tr><td>${ticker}</td><td class="text-end fw-bold">${weight}%</td></tr>`;
    });
    
    // User Portfolio Table
    const yourTable = document.getElementById('yourTable');
    if (user && user.weights) {
        yourTable.innerHTML = '';
        Object.entries(user.weights).sort((a, b) => b[1] - a[1]).forEach(([ticker, weight]) => {
            yourTable.innerHTML += `<tr><td>${ticker}</td><td class="text-end">${weight}%</td></tr>`;
        });
    } else {
        yourTable.innerHTML = '<tr><td colspan="2" class="text-center text-muted p-3">No allocation</td></tr>';
    }
    
    // Benchmark Table
    const benchTable = document.getElementById('benchTable');
    if (bench && bench.weights) {
        benchTable.innerHTML = '';
        Object.entries(bench.weights).sort((a, b) => b[1] - a[1]).forEach(([ticker, weight]) => {
            benchTable.innerHTML += `<tr><td>${ticker}</td><td class="text-end">${weight}%</td></tr>`;
        });
    } else {
        benchTable.innerHTML = '<tr><td colspan="2" class="text-center text-muted p-3">No benchmark</td></tr>';
    }
    
    // ========================================================================
    // GROUP ALLOCATIONS DISPLAY (NEW)
    // ========================================================================
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
                    
                    // Check if optimized allocation violates constraints
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
    
    // ========================================================================
    // PLOTLY CHARTS
    // ========================================================================
    if (typeof Plotly !== 'undefined') {
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

        // ====================================================================
        // DRAWDOWN
        // ====================================================================
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

        // ====================================================================
        // MONTHLY HEATMAP (Green=High, Red=Low)
        // ====================================================================
        if (opt.monthly_heatmap) {
            const hm = opt.monthly_heatmap;
            const dynamicHeight = Math.max(450, (hm.years.length * 45) + 120);
            
            Plotly.newPlot('monthlyHeatmap', [{
                z: hm.z,
                x: hm.months,
                y: hm.years,
                type: 'heatmap',
                colorscale: [
                    [0, '#d32f2f'],    // Deep red for negative
                    [0.4, '#ff6b6b'],  // Light red
                    [0.5, '#ffffff'],  // White at zero
                    [0.6, '#81c784'],  // Light green
                    [1, '#2e7d32']     // Deep green for high positive
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

        // ====================================================================
        // CORRELATION MATRIX (Blue=High, Red=Low)
        // ====================================================================
        const corrData = data.correlation_matrix;
        const assets = Object.keys(corrData);
        const z = assets.map(r => assets.map(c => corrData[r][c]));
        
        // Create annotations with correlation values
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
                [0, '#d32f2f'],     // Red for -1 (negative correlation)
                [0.5, '#ffffff'],   // White for 0
                [1, '#1976d2']      // Blue for +1 (positive correlation)
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
        
        // ====================================================================
        // DIVERSIFICATION METRICS
        // ====================================================================
        if (data.diversification) {
            renderDiversificationMetrics(data.diversification);
        }
    }
}

function renderDiversificationMetrics(divData) {
    const optDiv = divData.optimized;
    const userDiv = divData.user;
    const benchDiv = divData.benchmark;
    
    // Update health score cards
    document.getElementById('optHealthScore').innerText = optDiv ? optDiv.health_score : '--';
    document.getElementById('userHealthScore').innerText = userDiv ? userDiv.health_score : '--';
    document.getElementById('benchHealthScore').innerText = benchDiv ? benchDiv.health_score : '--';
    
    // Color code based on score
    const scoreColor = (score) => {
        if (!score) return '';
        if (score >= 70) return 'text-success';
        if (score >= 40) return 'text-warning';
        return 'text-danger';
    };
    
    document.getElementById('optHealthScore').className = `display-4 mb-0 ${scoreColor(optDiv?.health_score)}`;
    document.getElementById('userHealthScore').className = `display-4 mb-0 ${scoreColor(userDiv?.health_score)}`;
    document.getElementById('benchHealthScore').className = `display-4 mb-0 ${scoreColor(benchDiv?.health_score)}`;
    
    // Build metrics table
    const tbody = document.getElementById('diversificationBody');
    tbody.innerHTML = '';
    
    const metrics = [
        {
            label: 'HHI (Concentration)',
            key: 'hhi',
            format: v => v?.toFixed(4) || '-',
            interpret: optDiv?.hhi_interpretation || '-',
            tooltip: 'Lower is better. 1/N is perfectly diversified, 1.0 is single asset.'
        },
        {
            label: 'Diversification Ratio',
            key: 'diversification_ratio',
            format: v => v?.toFixed(2) || '-',
            interpret: optDiv?.dr_interpretation || '-',
            tooltip: 'Higher is better. Shows how much volatility is cancelled by diversification.'
        },
        {
            label: 'Effective # of Bets',
            key: 'effective_num_bets',
            format: v => v?.toFixed(1) || '-',
            interpret: optDiv?.enb_interpretation || '-',
            tooltip: 'How many independent risk exposures you actually have.'
        },
        {
            label: 'Health Score',
            key: 'health_score',
            format: v => v ? `${v}/100` : '-',
            interpret: 'Composite quality metric',
            tooltip: 'Weighted combination of Sharpe, DR, HHI, and Drawdown Duration.'
        }
    ];
    
    metrics.forEach(m => {
        const row = document.createElement('tr');
        const userVal = userDiv ? m.format(userDiv[m.key]) : '-';
        const optVal = optDiv ? m.format(optDiv[m.key]) : '-';
        const benchVal = benchDiv ? m.format(benchDiv[m.key]) : '-';
        
        row.innerHTML = `
            <td title="${m.tooltip}">${m.label} <i class="fas fa-info-circle text-muted small"></i></td>
            <td class="text-center">${userVal}</td>
            <td class="text-center fw-bold text-primary">${optVal}</td>
            <td class="text-center text-muted">${benchVal}</td>
            <td class="small text-muted">${m.interpret}</td>
        `;
        tbody.appendChild(row);
    });
    
    // Radar chart for health components
    if (optDiv && optDiv.health_components && typeof Plotly !== 'undefined') {
        const categories = ['Sharpe', 'Diversification', 'Concentration', 'Drawdown'];
        
        const traces = [];
        
        // Optimized portfolio
        traces.push({
            type: 'scatterpolar',
            r: [
                optDiv.health_components.sharpe_score,
                optDiv.health_components.div_ratio_score,
                optDiv.health_components.hhi_score,
                optDiv.health_components.drawdown_score,
                optDiv.health_components.sharpe_score  // Close the loop
            ],
            theta: [...categories, categories[0]],
            fill: 'toself',
            name: 'Optimized',
            line: {color: '#0d6efd'},
            fillcolor: 'rgba(13, 110, 253, 0.2)'
        });
        
        // User portfolio
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
        
        // Benchmark
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
                    range: [0, 100],
                    ticksuffix: '',
                    showline: false
                }
            },
            showlegend: true,
            title: {text: 'Health Score Components (0-100)', font: {size: 16}},
            height: 450
        });
    }
}
