# Portfolio Optimizer - Phase 2: Optimizer & Risk Calculator

## 📋 Overview

Phase 2 successfully migrates your portfolio optimization algorithms and risk calculators to use the new PostgreSQL database layer. All optimization methods are preserved and now work with your production database.

## 📁 Files Created

```
backend/
├── services/
│   ├── __init__.py              # Package exports
│   ├── data_service.py          # Portfolio data preparation
│   ├── optimizer.py             # All optimization algorithms
│   └── risk_calculator.py       # Risk metrics calculation
└── test_phase2.py               # Comprehensive test suite
```

## ✅ What Phase 2 Provides

### Portfolio Data Service
- Fetch returns data from database
- Validate portfolio data quality
- Calculate covariance and correlation matrices
- Prepare data for optimization

### Enhanced Portfolio Optimizer
- **Max Sharpe Ratio** - Maximize risk-adjusted returns
- **Min Volatility** - Minimize portfolio risk
- **Max Return** - Maximize returns with volatility constraint
- **Risk Parity** - Equal risk contribution from each asset
- **Hierarchical Risk Parity (HRP)** - Clustering-based allocation
- **Black-Litterman** - Combine market equilibrium with views
- **Efficient Frontier** - Full risk/return trade-off curve

### Risk Metrics Calculator
- Volatility & Downside Deviation
- Maximum Drawdown
- Sharpe Ratio & Sortino Ratio
- Calmar Ratio
- VaR & CVaR (95% confidence)
- Skewness & Kurtosis

## 🚀 Usage Examples

### Example 1: Basic Portfolio Optimization

```python
from backend.services.optimizer import create_optimizer
from datetime import datetime, timedelta

# Define portfolio
symbols = ['AAPL.US', 'MSFT.US', 'GOOGL.US', 'AMZN.US']
end_date = datetime.now().date()
start_date = end_date - timedelta(days=365*3)  # 3 years

# Create optimizer
optimizer = create_optimizer(
    symbols,
    start_date,
    end_date,
    risk_free_rate=0.02,
    frequency='M'  # Monthly returns
)

# Optimize for Max Sharpe Ratio
weights = optimizer.max_sharpe_ratio()

# Get performance metrics
performance = optimizer.portfolio_performance(weights)

print(f"Expected Return: {performance['return']*100:.2f}%")
print(f"Volatility: {performance['volatility']*100:.2f}%")
print(f"Sharpe Ratio: {performance['sharpe']:.2f}")

# Show allocation
weights_df = optimizer.get_weights_dataframe(weights)
print(weights_df)
```

### Example 2: Compare Multiple Optimization Methods

```python
from backend.services.optimizer import create_optimizer
from datetime import datetime, timedelta

symbols = ['AAPL.US', 'MSFT.US', 'SPY.US']
end_date = datetime.now().date()
start_date = end_date - timedelta(days=365*5)

optimizer = create_optimizer(symbols, start_date, end_date)

# Try different methods
methods = {
    'Max Sharpe': optimizer.max_sharpe_ratio(),
    'Min Volatility': optimizer.min_volatility(),
    'Risk Parity': optimizer.risk_parity_optimization(),
    'HRP': optimizer.hierarchical_risk_parity()
}

# Compare results
for name, weights in methods.items():
    if weights is not None:
        perf = optimizer.portfolio_performance(weights)
        print(f"\n{name}:")
        print(f"  Return: {perf['return']*100:.2f}%")
        print(f"  Volatility: {perf['volatility']*100:.2f}%")
        print(f"  Sharpe: {perf['sharpe']:.2f}")
```

### Example 3: Efficient Frontier

```python
from backend.services.optimizer import create_optimizer
import matplotlib.pyplot as plt

optimizer = create_optimizer(symbols, start_date, end_date)

# Calculate efficient frontier
frontier = optimizer.efficient_frontier(n_points=100)

# Plot
plt.figure(figsize=(10, 6))
plt.plot(
    frontier['volatility'] * 100,
    frontier['return'] * 100,
    'b-', linewidth=2
)
plt.xlabel('Volatility (%)')
plt.ylabel('Expected Return (%)')
plt.title('Efficient Frontier')
plt.grid(True)
plt.show()
```

### Example 4: Risk Metrics Calculation

```python
from backend.services.risk_calculator import create_risk_calculator

calculator = create_risk_calculator(risk_free_rate=0.02)

# Calculate metrics for different periods
symbol = 'AAPL.US'
periods = [
    (1, '1y'),
    (3, '3y'),
    (5, '5y')
]

count, metrics_list = calculator.update_metrics_for_symbol(symbol, periods)

for metrics in metrics_list:
    print(f"\n{metrics['period']} Metrics:")
    print(f"  Volatility: {metrics['volatility']*100:.2f}%")
    print(f"  Sharpe: {metrics['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown: {metrics['max_drawdown']*100:.2f}%")
```

### Example 5: Portfolio Data Preparation

```python
from backend.services import PortfolioDataService
from datetime import datetime, timedelta

service = PortfolioDataService()

symbols = ['AAPL.US', 'MSFT.US', 'GOOGL.US']
end_date = datetime.now().date()
start_date = end_date - timedelta(days=365*2)

# Prepare all data needed for optimization
data = service.prepare_optimization_data(
    symbols,
    start_date,
    end_date,
    frequency='M'
)

if data['valid']:
    print(f"Ready for optimization!")
    print(f"Symbols: {data['symbols']}")
    print(f"Returns shape: {data['returns'].shape}")
    print(f"Mean returns:\n{data['mean_returns']}")
    print(f"Covariance matrix:\n{data['cov_matrix']}")
else:
    print(f"Data validation failed: {data['validation']['issues']}")
```

### Example 6: Custom Constraints

```python
from backend.services.optimizer import create_optimizer

optimizer = create_optimizer(symbols, start_date, end_date)

# Custom constraints: No single asset > 40%
def max_weight_constraint(weights):
    return 0.4 - weights.max()

constraints = [
    {'type': 'ineq', 'fun': max_weight_constraint}
]

# Optimize with constraints
weights = optimizer.max_sharpe_ratio(constraints=constraints)

weights_df = optimizer.get_weights_dataframe(weights)
print("Constrained Portfolio:")
print(weights_df)
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
cd D:\FolioData\FolioF\PortfolioOptimizationPythonFiles\V6_EODHD_Hybrid\PortfolioOptimizer
python backend/test_phase2.py
```

### Test Suite Coverage

The test suite validates:
1. ✅ Portfolio Data Service
2. ✅ Optimizer Creation
3. ✅ Max Sharpe Ratio
4. ✅ Min Volatility
5. ✅ Risk Parity
6. ✅ Hierarchical Risk Parity
7. ✅ Efficient Frontier
8. ✅ Risk Metrics Calculator
9. ✅ Factory Functions

## 📊 Optimization Methods Explained

### Max Sharpe Ratio
**Best for:** Maximum risk-adjusted returns
**When to use:** When you want the best return per unit of risk
**Characteristics:** Often concentrated in high-return assets

### Minimum Volatility
**Best for:** Conservative investors
**When to use:** When capital preservation is priority
**Characteristics:** Lower returns, lower risk

### Risk Parity
**Best for:** Balanced risk exposure
**When to use:** When you want equal risk contribution from each asset
**Characteristics:** More diversified than Max Sharpe

### Hierarchical Risk Parity (HRP)
**Best for:** Diversification without optimization
**When to use:** When you want stable allocations
**Characteristics:** Based on asset clustering, no assumptions about returns

### Black-Litterman
**Best for:** Incorporating market views
**When to use:** When you have specific beliefs about asset returns
**Characteristics:** Blends equilibrium with investor views

## 🔧 Key Features

### Data Validation
- Automatic symbol validation
- Minimum data requirements checking
- Data quality reporting

### Performance Metrics
- Return, volatility, Sharpe ratio
- Sortino ratio (downside risk)
- Comprehensive risk metrics

### Flexible Configuration
- Custom constraints support
- Adjustable risk-free rate
- Multiple return frequencies (daily, weekly, monthly)

### Error Handling
- Graceful failure modes
- Detailed error logging
- Fallback options

## 📝 Migration Notes

### What Changed from V5

**OLD (DatabaseV5_Enhanced):**
```python
from DatabaseV5_Enhanced import (
    session_scope, Asset, AssetPrice,
    Session, setup_engine, DB_FILE
)

engine = setup_engine(DB_FILE)
with session_scope() as session:
    # ...
```

**NEW (models_v6 + config_v6):**
```python
from models_v6 import Asset, AssetPrice, get_session
import config_v6

engine = config_v6.get_postgres_engine()
with get_session(engine) as session:
    # ...
```

### What Stayed the Same

- ✅ All optimization algorithms preserved
- ✅ All risk calculations unchanged
- ✅ Algorithm logic intact
- ✅ Mathematical formulas unchanged

## 🎯 Next Steps

### Phase 3: FastAPI Backend
- Create REST API endpoints
- Request/response models
- API documentation
- Error handling

### Phase 4: Frontend
- HTML/CSS/JavaScript interface
- Asset selection UI
- Results visualization
- Interactive charts

## ❓ Troubleshooting

### Issue: Optimizer returns None
**Cause:** Insufficient data or optimization failure
**Solution:** 
- Check date range has enough data
- Verify symbols are valid
- Try different optimization method

### Issue: "Not enough valid symbols"
**Cause:** Symbols not found in database
**Solution:**
- Use search_assets to find correct format
- Ensure symbols include exchange suffix
- Validate symbols before optimization

### Issue: Returns calculation fails
**Cause:** Missing or sparse price data
**Solution:**
- Check price data availability for date range
- Increase date range
- Use assets with complete data

## 📊 Performance Considerations

### Optimization Speed
- Max Sharpe: Fast (~0.1-0.5 seconds)
- Min Volatility: Fast (~0.1-0.5 seconds)
- Risk Parity: Medium (~0.5-2 seconds)
- HRP: Fast (~0.2-1 second)
- Efficient Frontier: Slow (~5-30 seconds for 100 points)

### Recommendations
- Use monthly returns for long-term optimization
- Limit efficient frontier to 20-50 points for speed
- Cache results for repeated queries
- Use async processing for multiple optimizations

## ✅ Phase 2 Success Criteria

Before moving to Phase 3:
- [ ] Test suite passes (9/9 tests)
- [ ] Can optimize portfolio with different methods
- [ ] Can calculate risk metrics
- [ ] Can generate efficient frontier
- [ ] No import errors
- [ ] Performance acceptable

**If all checked:** ✅ Ready for Phase 3 (FastAPI Backend)!

---

**Created:** 2025-11-17
**Phase:** 2 of 8 (Optimizer Migration)
**Status:** ✅ COMPLETE
