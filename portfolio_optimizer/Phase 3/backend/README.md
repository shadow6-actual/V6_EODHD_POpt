# Portfolio Optimizer - Phase 1: Database Layer

## 📋 Overview

This is the database abstraction layer for the Portfolio Optimizer web application. It provides clean, reusable functions for accessing your PostgreSQL database containing 152K+ assets and 109M+ price records.

## 📁 Files Created

```
backend/
├── database/
│   ├── __init__.py           # Package exports
│   ├── connection.py         # Database connection management
│   └── queries.py            # Common database queries
└── test_database_layer.py    # Test suite
```

## ✅ What This Layer Provides

### Connection Management
- **PostgreSQL** - Master database (all 150K+ tickers)
- **SQLite** - Working database (portfolios, watchlists)
- Connection pooling and session management
- Health checks and statistics

### Asset Queries
- Search assets by symbol, name, or code
- Get asset details by symbol
- Filter by exchange and asset type
- List all exchanges

### Price Queries
- Get historical price data (OHLCV)
- Get latest price for a symbol
- Get date range of available data
- Bulk queries for multiple assets

### Returns & Analytics
- Calculate returns (daily, weekly, monthly)
- Correlation matrix calculation
- Data validation utilities

## 🚀 Usage Examples

### Basic Asset Search

```python
from backend.database import search_assets, get_asset_by_symbol

# Search for assets
assets = search_assets('AAPL', exchanges=['US'], limit=10)
for asset in assets:
    print(f"{asset.symbol}: {asset.name}")

# Get specific asset
asset = get_asset_by_symbol('AAPL.US')
if asset:
    print(f"{asset.name} - {asset.exchange}")
```

### Get Price Data

```python
from backend.database import get_price_data, get_latest_price
from datetime import datetime, timedelta

# Get 1 year of price data
end_date = datetime.now().date()
start_date = end_date - timedelta(days=365)

prices = get_price_data('AAPL.US', start_date, end_date)
print(f"Retrieved {len(prices)} trading days")

# Get latest price
latest = get_latest_price('AAPL.US')
if latest:
    print(f"Latest close: ${latest.close} on {latest.date}")
```

### Calculate Returns and Correlation

```python
from backend.database import get_returns_dataframe, get_correlation_matrix
from datetime import datetime, timedelta

symbols = ['AAPL.US', 'MSFT.US', 'GOOGL.US']
end_date = datetime.now().date()
start_date = end_date - timedelta(days=365)

# Get monthly returns
returns = get_returns_dataframe(
    symbols, 
    start_date, 
    end_date, 
    frequency='M'
)
print(returns)

# Get correlation matrix
corr = get_correlation_matrix(symbols, start_date, end_date)
print(corr)
```

### Session Management (Advanced)

```python
from backend.database import get_db_session, SessionManager

# Context manager approach
with get_db_session() as session:
    # Your database operations here
    pass

# Reusable session manager
manager = SessionManager()
with manager.session() as session:
    # Database operations
    pass
manager.close()
```

## 🧪 Testing

Run the test suite to verify everything is working:

```bash
cd /path/to/V6_EODHD_Hybrid/PortfolioOptimizer
python backend/test_database_layer.py
```

### Expected Output

The test suite will verify:
1. ✅ Database connection
2. ✅ Database statistics (asset count, price records, exchanges)
3. ✅ Exchange listing
4. ✅ Asset search
5. ✅ Asset lookup
6. ✅ Price data retrieval
7. ✅ Returns calculation
8. ✅ Correlation matrix

## 📊 Database Schema Reference

### Asset Table
- `symbol` (primary key) - e.g., 'AAPL.US'
- `code` - Ticker code without exchange
- `exchange` - Exchange code (US, LSE, XETRA, etc.)
- `name` - Company/fund name
- `asset_type` - Common Stock, ETF, etc.
- `is_active` - Boolean flag
- `last_updated` - Last metadata update
- `last_price_date` - Most recent price date

### AssetPrice Table
- `price_id` (primary key) - Auto-increment ID
- `symbol` (foreign key) - References Asset.symbol
- `date` - Trading date
- `open`, `high`, `low`, `close` - OHLC prices
- `adjusted_close` - Adjusted for splits/dividends
- `volume` - Trading volume
- `loaded_at` - Timestamp when loaded (NOT created_at!)

### RiskMetrics Table (if available)
- `symbol` (primary key)
- `period` (primary key) - '1y', '3y', '5y', '10y', 'all'
- Risk metrics: volatility, sharpe, sortino, max_drawdown, etc.

## 🔧 Configuration

The database layer uses your existing configuration from:
- `config_v6.py` - Database connections, API keys
- `models_v6.py` - SQLAlchemy models

No additional configuration needed!

## 📝 Key Design Decisions

1. **No Framework Lock-in**: Pure SQLAlchemy, no Django/Flask dependencies
2. **Session Safety**: All functions handle their own sessions by default
3. **Pandas Integration**: Returns data as DataFrames for easy analysis
4. **Error Handling**: Comprehensive logging and graceful failures
5. **PostgreSQL Primary**: Master database for all queries
6. **SQLite Optional**: Working database for portfolio-specific data

## 🎯 Next Steps

**Phase 2: Optimizer Migration**
- Migrate `EnhancedPortfolioOptimizer.py` to use this database layer
- Migrate `RiskMetricsCalculator.py`
- Test all optimization methods

**Phase 3: FastAPI Backend**
- Create REST API endpoints
- Request/response models (Pydantic)
- API documentation

**Phase 4: Frontend**
- HTML/CSS/JavaScript interface
- Asset selection UI
- Results visualization

## ❓ Troubleshooting

### Import Errors
If you get import errors for `config_v6` or `models_v6`:
1. Ensure files are in your project root
2. Check Python path in connection.py
3. Verify config_v6.py has correct database credentials

### Connection Errors
If database connection fails:
1. Verify PostgreSQL is running
2. Check credentials in config_v6.py
3. Test connection: `python -c "import config_v6; config_v6.get_postgres_engine()"`

### Empty Results
If queries return no data:
1. Verify symbol format (e.g., 'AAPL.US' not just 'AAPL')
2. Check if asset is marked as active
3. Verify price data exists for the symbol

## 📞 Support

For issues specific to:
- **Database schema**: Check models_v6.py
- **Connection issues**: Check config_v6.py
- **Query problems**: See queries.py documentation

---

## ✅ Phase 1 Complete!

You now have a production-ready database abstraction layer. Run the test suite to verify, then we can move to Phase 2!
