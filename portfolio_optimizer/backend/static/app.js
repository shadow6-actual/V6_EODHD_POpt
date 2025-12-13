// Portfolio Optimizer JavaScript
// Handles all UI interactions, API calls, and data visualization

// Configuration
const API_BASE_URL = 'http://localhost:5000/api';
let searchTimeout = null;
let selectedAssets = [];
let optimizationResults = null;
let allocationChart = null;
let frontierChart = null;

// Method descriptions
const METHOD_DESCRIPTIONS = {
    'max_sharpe': 'Maximizes the risk-adjusted return (Sharpe ratio) by finding the portfolio with the best expected return per unit of risk. Best for investors seeking optimal risk-adjusted performance.',
    'min_volatility': 'Minimizes portfolio volatility (standard deviation) to create the most stable portfolio. Ideal for risk-averse investors prioritizing capital preservation.',
    'risk_parity': 'Allocates capital so each asset contributes equally to total portfolio risk. Provides better diversification than market-cap weighting.',
    'hrp': 'Uses hierarchical clustering to build robust portfolios that are less sensitive to estimation errors. Based on machine learning techniques by Marcos López de Prado.',
    'max_return': 'Maximizes expected return subject to a maximum volatility constraint. Allows you to target a specific return while capping downside risk.'
};

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    initializeDates();
    setupEventListeners();
    updateMethodDescription();
});

function initializeDates() {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setFullYear(startDate.getFullYear() - 5);
    
    document.getElementById('endDate').valueAsDate = endDate;
    document.getElementById('startDate').valueAsDate = startDate;
}

function setupEventListeners() {
    // Asset search
    document.getElementById('assetSearch').addEventListener('input', handleAssetSearch);
    
    // Method selection
    document.getElementById('optimizationMethod').addEventListener('change', function() {
        updateMethodDescription();
        toggleMaxReturnInputs();
    });
    
    // Click outside to close search results
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.asset-search')) {
            document.getElementById('searchResults').classList.remove('active');
        }
    });
}

// ============================================================================
// DATE RANGE HELPERS
// ============================================================================

function setDateRange(years) {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setFullYear(startDate.getFullYear() - years);
    
    document.getElementById('endDate').valueAsDate = endDate;
    document.getElementById('startDate').valueAsDate = startDate;
}

// ============================================================================
// ASSET SEARCH
// ============================================================================

function handleAssetSearch(e) {
    const query = e.target.value.trim();
    
    if (searchTimeout) {
        clearTimeout(searchTimeout);
    }
    
    if (query.length < 1) {
        document.getElementById('searchResults').classList.remove('active');
        return;
    }
    
    searchTimeout = setTimeout(() => searchAssets(query), 300);
}

async function searchAssets(query) {
    try {
        const response = await fetch(`${API_BASE_URL}/search_assets?query=${encodeURIComponent(query)}&limit=20`);
        const data = await response.json();
        
        if (data.assets) {
            displaySearchResults(data.assets);
        }
    } catch (error) {
        console.error('Search error:', error);
    }
}

function displaySearchResults(assets) {
    const resultsDiv = document.getElementById('searchResults');
    
    if (assets.length === 0) {
        resultsDiv.innerHTML = '<div style="padding: 1rem; text-align: center; color: #64748b;">No assets found</div>';
        resultsDiv.classList.add('active');
        return;
    }
    
    resultsDiv.innerHTML = assets.map(asset => `
        <div class="search-result-item" onclick="selectAsset('${asset.symbol}', '${asset.name}', '${asset.exchange}')">
            <div class="search-result-symbol">${asset.symbol}</div>
            <div class="search-result-name">${asset.name}</div>
            <div class="search-result-meta">${asset.exchange} • ${asset.type}</div>
        </div>
    `).join('');
    
    resultsDiv.classList.add('active');
}

function selectAsset(symbol, name, exchange) {
    // Check if already selected
    if (selectedAssets.find(a => a.symbol === symbol)) {
        showError('Asset already selected');
        return;
    }
    
    selectedAssets.push({ symbol, name, exchange });
    updateSelectedAssetsDisplay();
    
    // Clear search
    document.getElementById('assetSearch').value = '';
    document.getElementById('searchResults').classList.remove('active');
}

function removeAsset(symbol) {
    selectedAssets = selectedAssets.filter(a => a.symbol !== symbol);
    updateSelectedAssetsDisplay();
}

function updateSelectedAssetsDisplay() {
    const container = document.getElementById('selectedAssets');
    
    if (selectedAssets.length === 0) {
        container.innerHTML = '<div class="no-assets">No assets selected. Search and click to add.</div>';
        return;
    }
    
    container.innerHTML = selectedAssets.map(asset => `
        <div class="asset-chip">
            <span><strong>${asset.symbol}</strong></span>
            <span class="asset-chip-remove" onclick="removeAsset('${asset.symbol}')">&times;</span>
        </div>
    `).join('');
}

// ============================================================================
// METHOD DESCRIPTION
// ============================================================================

function updateMethodDescription() {
    const method = document.getElementById('optimizationMethod').value;
    const description = METHOD_DESCRIPTIONS[method] || '';
    document.getElementById('methodDescription').innerHTML = description;
}

function toggleMaxReturnInputs() {
    const method = document.getElementById('optimizationMethod').value;
    const inputs = document.getElementById('maxReturnInputs');
    inputs.style.display = method === 'max_return' ? 'block' : 'none';
}

// ============================================================================
// COLLAPSIBLE SECTIONS
// ============================================================================

function toggleSection(id) {
    const content = document.getElementById(id);
    const icon = event.target.querySelector('.toggle-icon');
    
    content.classList.toggle('collapsed');
    icon.style.transform = content.classList.contains('collapsed') ? 'rotate(-90deg)' : 'rotate(0deg)';
}

// ============================================================================
// OPTIMIZATION
// ============================================================================

async function runOptimization() {
    // Validation
    if (selectedAssets.length < 2) {
        showError('Please select at least 2 assets');
        return;
    }
    
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;
    
    if (!startDate || !endDate) {
        showError('Please select start and end dates');
        return;
    }
    
    if (new Date(startDate) >= new Date(endDate)) {
        showError('Start date must be before end date');
        return;
    }
    
    // Prepare request data
    const requestData = {
        symbols: selectedAssets.map(a => a.symbol),
        method: document.getElementById('optimizationMethod').value,
        start_date: startDate,
        end_date: endDate,
        risk_free_rate: parseFloat(document.getElementById('riskFreeRate').value) / 100,
        include_frontier: document.getElementById('includeFrontier').checked,
        constraints: {
            min_weight: parseFloat(document.getElementById('minWeight').value) / 100,
            max_weight: parseFloat(document.getElementById('maxWeight').value) / 100
        }
    };
    
    if (requestData.method === 'max_return') {
        requestData.constraints.max_volatility = parseFloat(document.getElementById('maxVolatility').value) / 100;
    }
    
    // Show loading
    showLoading(true);
    
    try {
        const response = await fetch(`${API_BASE_URL}/optimize`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Optimization failed');
        }
        
        const data = await response.json();
        optimizationResults = data;
        
        displayResults(data);
        
    } catch (error) {
        showError(error.message);
    } finally {
        showLoading(false);
    }
}

// ============================================================================
// RESULTS DISPLAY
// ============================================================================

function displayResults(data) {
    // Hide initial state, show results
    document.getElementById('initialState').style.display = 'none';
    document.getElementById('resultsDisplay').style.display = 'block';
    
    // Scroll to results
    document.getElementById('resultsDisplay').scrollIntoView({ behavior: 'smooth', block: 'start' });
    
    // Display summary
    displaySummary(data);
    
    // Display metrics
    displayMetrics(data.metrics);
    
    // Display allocation
    displayAllocation(data.metrics.weights);
    
    // Display efficient frontier (if available)
    if (data.frontier) {
        displayEfficientFrontier(data.frontier, data.metrics);
    } else {
        document.getElementById('frontierCard').style.display = 'none';
    }
}

function displaySummary(data) {
    const html = `
        <div class="summary-method">${data.method}</div>
        <div class="summary-period">
            Analysis Period: ${data.period.start} to ${data.period.end}
        </div>
    `;
    document.getElementById('optimizationSummary').innerHTML = html;
}

function displayMetrics(metrics) {
    const metricsData = [
        { label: 'Expected Return', value: (metrics.return * 100).toFixed(2) + '%', positive: metrics.return > 0 },
        { label: 'Volatility', value: (metrics.volatility * 100).toFixed(2) + '%', positive: false },
        { label: 'Sharpe Ratio', value: metrics.sharpe_ratio.toFixed(3), positive: metrics.sharpe_ratio > 0 },
        { label: 'Sortino Ratio', value: metrics.sortino_ratio.toFixed(3), positive: metrics.sortino_ratio > 0 },
        { label: 'Max Drawdown', value: (metrics.max_drawdown * 100).toFixed(2) + '%', positive: false },
        { label: 'Calmar Ratio', value: metrics.calmar_ratio.toFixed(3), positive: metrics.calmar_ratio > 0 },
        { label: 'VaR (95%)', value: (metrics.var_95 * 100).toFixed(2) + '%', positive: false },
        { label: 'CVaR (95%)', value: (metrics.cvar_95 * 100).toFixed(2) + '%', positive: false }
    ];
    
    const html = metricsData.map(m => `
        <div class="metric-card">
            <div class="metric-label">${m.label}</div>
            <div class="metric-value ${m.positive ? 'positive' : ''}">${m.value}</div>
        </div>
    `).join('');
    
    document.getElementById('portfolioMetrics').innerHTML = html;
}

function displayAllocation(weights) {
    // Sort by weight descending
    const sortedWeights = Object.entries(weights)
        .sort((a, b) => b[1] - a[1])
        .filter(([symbol, weight]) => weight > 0.0001); // Filter out very small weights
    
    // Create pie chart
    const ctx = document.getElementById('allocationChart');
    
    if (allocationChart) {
        allocationChart.destroy();
    }
    
    allocationChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: sortedWeights.map(([symbol]) => symbol),
            datasets: [{
                data: sortedWeights.map(([, weight]) => weight * 100),
                backgroundColor: generateColors(sortedWeights.length),
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        padding: 15,
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ${context.parsed.toFixed(2)}%`;
                        }
                    }
                }
            }
        }
    });
    
    // Create allocation table
    const tableHtml = sortedWeights.map(([symbol, weight]) => {
        const percentage = weight * 100;
        return `
            <div class="allocation-row">
                <div class="allocation-symbol">${symbol}</div>
                <div class="allocation-bar-container">
                    <div class="allocation-bar" style="width: ${percentage}%"></div>
                </div>
                <div class="allocation-weight">${percentage.toFixed(2)}%</div>
            </div>
        `;
    }).join('');
    
    document.getElementById('allocationTable').innerHTML = tableHtml;
}

function displayEfficientFrontier(frontier, currentPortfolio) {
    document.getElementById('frontierCard').style.display = 'block';
    
    const ctx = document.getElementById('frontierChart');
    
    if (frontierChart) {
        frontierChart.destroy();
    }
    
    // Convert to percentage for display
    const returns = frontier.returns.map(r => r * 100);
    const volatilities = frontier.volatilities.map(v => v * 100);
    
    frontierChart = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [
                {
                    label: 'Efficient Frontier',
                    data: volatilities.map((vol, i) => ({ x: vol, y: returns[i] })),
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    showLine: true,
                    pointRadius: 2,
                    borderWidth: 2
                },
                {
                    label: 'Optimized Portfolio',
                    data: [{ 
                        x: currentPortfolio.volatility * 100, 
                        y: currentPortfolio.return * 100 
                    }],
                    backgroundColor: '#10b981',
                    borderColor: '#059669',
                    pointRadius: 8,
                    pointHoverRadius: 10,
                    borderWidth: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Volatility (%)',
                        font: { size: 14, weight: 'bold' }
                    },
                    ticks: {
                        callback: function(value) {
                            return value.toFixed(1) + '%';
                        }
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Expected Return (%)',
                        font: { size: 14, weight: 'bold' }
                    },
                    ticks: {
                        callback: function(value) {
                            return value.toFixed(1) + '%';
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Return: ${context.parsed.y.toFixed(2)}%, Vol: ${context.parsed.x.toFixed(2)}%`;
                        }
                    }
                }
            }
        }
    });
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function generateColors(count) {
    const baseHues = [217, 160, 48, 142, 0, 290, 31];
    const colors = [];
    
    for (let i = 0; i < count; i++) {
        const hue = baseHues[i % baseHues.length];
        const saturation = 70 - (Math.floor(i / baseHues.length) * 10);
        const lightness = 50 + (Math.floor(i / baseHues.length) * 5);
        colors.push(`hsl(${hue}, ${saturation}%, ${lightness}%)`);
    }
    
    return colors;
}

function showLoading(show) {
    document.getElementById('loadingOverlay').style.display = show ? 'flex' : 'none';
}

function showError(message) {
    document.getElementById('errorMessage').textContent = message;
    document.getElementById('errorModal').style.display = 'flex';
}

function closeErrorModal() {
    document.getElementById('errorModal').style.display = 'none';
}

function clearForm() {
    selectedAssets = [];
    updateSelectedAssetsDisplay();
    document.getElementById('assetSearch').value = '';
    document.getElementById('optimizationMethod').value = 'max_sharpe';
    document.getElementById('riskFreeRate').value = '2.0';
    document.getElementById('includeFrontier').checked = false;
    document.getElementById('minWeight').value = '0';
    document.getElementById('maxWeight').value = '100';
    initializeDates();
    updateMethodDescription();
    
    // Hide results
    document.getElementById('initialState').style.display = 'block';
    document.getElementById('resultsDisplay').style.display = 'none';
}

// ============================================================================
// EXPORT FUNCTIONS
// ============================================================================

function exportToCSV() {
    if (!optimizationResults) return;
    
    const weights = optimizationResults.metrics.weights;
    const metrics = optimizationResults.metrics;
    
    let csv = 'Portfolio Optimization Results\n\n';
    csv += 'Method,' + optimizationResults.method + '\n';
    csv += 'Period,' + optimizationResults.period.start + ' to ' + optimizationResults.period.end + '\n\n';
    
    csv += 'Portfolio Metrics\n';
    csv += 'Metric,Value\n';
    csv += `Expected Return,${(metrics.return * 100).toFixed(2)}%\n`;
    csv += `Volatility,${(metrics.volatility * 100).toFixed(2)}%\n`;
    csv += `Sharpe Ratio,${metrics.sharpe_ratio.toFixed(3)}\n`;
    csv += `Sortino Ratio,${metrics.sortino_ratio.toFixed(3)}\n`;
    csv += `Max Drawdown,${(metrics.max_drawdown * 100).toFixed(2)}%\n`;
    csv += `Calmar Ratio,${metrics.calmar_ratio.toFixed(3)}\n`;
    csv += `VaR (95%),${(metrics.var_95 * 100).toFixed(2)}%\n`;
    csv += `CVaR (95%),${(metrics.cvar_95 * 100).toFixed(2)}%\n\n`;
    
    csv += 'Asset Allocation\n';
    csv += 'Symbol,Weight\n';
    Object.entries(weights).forEach(([symbol, weight]) => {
        csv += `${symbol},${(weight * 100).toFixed(2)}%\n`;
    });
    
    downloadFile('portfolio_optimization.csv', csv, 'text/csv');
}

function exportToJSON() {
    if (!optimizationResults) return;
    
    const json = JSON.stringify(optimizationResults, null, 2);
    downloadFile('portfolio_optimization.json', json, 'application/json');
}

function downloadFile(filename, content, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function printResults() {
    window.print();
}
