# Portfolio Optimization Tool

A sophisticated web-based portfolio optimization platform inspired by portfoliovisualizer.com, built to work with your extensive global market database (152K+ assets, 109.5M price records).

## 🎯 Features

### Optimization Methods
- **Maximum Sharpe Ratio** - Optimal risk-adjusted returns
- **Minimum Volatility** - Capital preservation focus
- **Risk Parity** - Equal risk contribution from each asset
- **Hierarchical Risk Parity (HRP)** - Machine learning-based approach
- **Maximum Return** - Return maximization with volatility constraints
- **Black-Litterman** - Bayesian approach with investor views (in EnhancedPortfolioOptimizer)

### Analytics
- Comprehensive risk metrics (Sharpe, Sortino, Calmar ratios)
- Value at Risk (VaR) and Conditional VaR
- Maximum drawdown analysis
- Efficient frontier visualization
- Interactive allocation charts
- Correlation matrix analysis

### Data Coverage
- 152,706 assets with historical data
- 109.5 million price records
- Global exchange coverage (US, LSE, XETRA, HK, etc.)
- 30 years of historical data (from 1995)

## 📋 Requirements

### System Requirements
- Python 3.8+
- PostgreSQL or SQLite database
- 4GB+ RAM recommended
- Modern web browser (Chrome, Firefox, Safari, Edge)

### Python Dependencies
```bash
pip install flask flask-cors pandas numpy scipy sqlalchemy psycopg2-binary
```

## 🚀 Installation

### 1. Clone/Download Files

Create a project directory and place these files:
```
portfolio_optimizer/
├── portfolio_optimizer_api.py    # Flask backend
├── db_config.py                  # Database configuration
├── EnhancedPortfolioOptimizer.py # Your existing optimizer
├── static/
│   ├── index.html               # Web interface
│   ├── styles.css              # Styling
│   └── app.js                  # Frontend logic
└── README.md
```

### 2. Configure Database Connection

Edit `db_config.py`:

**For PostgreSQL:**
```python
DB_TYPE = 'postgresql'

POSTGRES_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'your_database_name',
    'user': 'your_username',
    'password': 'your_password'
}
```

**For SQLite:**
```python
DB_TYPE = 'sqlite'
SQLITE_DB_PATH = 'D:/FolioData/FolioF/portfolio_database.db'
```

### 3. Update API to Use Your Database

**IMPORTANT:** Update the `DATABASE_URL` in `portfolio_optimizer_api.py` line 41:

```python
# Import your config
from db_config import get_database_url

# Use your database
DATABASE_URL = get_database_url()
```

### 4. Verify Database Schema

The API expects these tables:
- `assets` (symbol, name, exchange, asset_type, currency, is_active)
- `asset_prices` (symbol, date, open, high, low, close, adjclose, volume)
- `risk_metrics` (symbol, period, volatility, sharpe_ratio, etc.)

If your table names differ, update the model classes in `portfolio_optimizer_api.py` (lines 51-88).

### 5. Install Dependencies

```bash
pip install flask flask-cors pandas numpy scipy sqlalchemy psycopg2-binary
```

## 🏃 Running the Application

### Start the Server

```bash
python portfolio_optimizer_api.py
```

The server will start on `http://localhost:5000`

### Access the Web Interface

Open your browser and navigate to:
```
http://localhost:5000
```

## 📖 User Guide

### Basic Workflow

1. **Select Assets**
   - Search by symbol or name (e.g., "SPY", "AAPL", "VANGUARD")
   - Click to add assets to your portfolio
   - Need at least 2 assets for optimization

2. **Set Time Period**
   - Choose start and end dates
   - Or use quick buttons (1Y, 3Y, 5Y, 10Y)
   - Longer periods provide more robust analysis

3. **Choose Optimization Method**
   - **Max Sharpe**: Best risk-adjusted returns
   - **Min Volatility**: Lowest risk portfolio
   - **Risk Parity**: Equal risk contribution
   - **HRP**: Advanced ML-based approach

4. **Configure Parameters**
   - Set risk-free rate (default 2%)
   - Optional: Add weight constraints
   - Optional: Enable efficient frontier calculation

5. **Optimize & Analyze**
   - Click "Optimize Portfolio"
   - Review allocation, metrics, and charts
   - Export results to CSV/JSON

### Advanced Features

#### Constraints
- **Min/Max Weight**: Limit individual asset allocation
- Example: Min 5%, Max 30% prevents over-concentration

#### Efficient Frontier
- Enable to visualize risk/return tradeoffs
- Shows your optimized portfolio position
- Helps understand diversification benefits

## 🔧 Customization

### Adding New Optimization Methods

Edit `portfolio_optimizer_api.py` to add new methods:

```python
elif method == 'your_method':
    weights = optimizer.your_custom_method()
    method_name = "Your Method Name"
```

Update `app.js` to add UI option:

```javascript
METHOD_DESCRIPTIONS['your_method'] = 'Description of your method';
```

### Modifying Database Schema

If your schema differs, update the SQLAlchemy models in `portfolio_optimizer_api.py`:

```python
class Asset(Base):
    __tablename__ = 'your_table_name'
    # Update column definitions
```

### Styling Changes

Edit `static/styles.css` to customize appearance:
- Change `--primary-color` for different color scheme
- Modify grid layouts for different screen sizes
- Adjust chart heights and spacing

## 🐛 Troubleshooting

### Database Connection Issues

**Error: "Can't connect to database"**
- Verify credentials in `db_config.py`
- Check PostgreSQL is running: `pg_ctl status`
- Test connection: `psql -U username -d database_name`

**Error: "Table does not exist"**
- Verify table names match your schema
- Run: `SELECT table_name FROM information_schema.tables;`

### Optimization Failures

**Error: "Insufficient data"**
- Assets need at least 12 months of data
- Try longer time period or different assets
- Check for gaps in price data

**Error: "Optimization failed to converge"**
- Try different optimization method
- Relax weight constraints
- Check for highly correlated assets

### Performance Issues

**Slow optimization (>30 seconds)**
- Add database indexes on (symbol, date)
- Enable query result caching
- Reduce efficient frontier points

**Database query optimization:**
```sql
CREATE INDEX idx_prices_symbol_date ON asset_prices(symbol, date);
CREATE INDEX idx_assets_symbol ON assets(symbol);
```

## 📊 API Endpoints

### Search Assets
```
GET /api/search_assets?query=SPY&limit=20
```

### Asset Information
```
POST /api/asset_info
Body: { "symbols": ["SPY", "AGG"], "period": "5y" }
```

### Run Optimization
```
POST /api/optimize
Body: {
  "symbols": ["SPY", "AGG", "GLD"],
  "method": "max_sharpe",
  "start_date": "2019-01-01",
  "end_date": "2024-01-01",
  "risk_free_rate": 0.02,
  "include_frontier": true
}
```

### Efficient Frontier
```
POST /api/efficient_frontier
Body: { "symbols": [...], "start_date": "...", "n_points": 100 }
```

### Correlation Matrix
```
POST /api/correlation_matrix
Body: { "symbols": [...], "start_date": "...", "end_date": "..." }
```

## 🔐 Security Considerations

### Production Deployment

1. **Disable Debug Mode**
```python
app.run(debug=False)
```

2. **Use Environment Variables**
```python
import os
DATABASE_URL = os.environ.get('DATABASE_URL')
```

3. **Add Authentication** (optional)
```python
from flask_httpauth import HTTPBasicAuth
auth = HTTPBasicAuth()
```

4. **Enable HTTPS**
- Use reverse proxy (nginx)
- Configure SSL certificates

5. **Rate Limiting**
```python
from flask_limiter import Limiter
limiter = Limiter(app, default_limits=["100 per hour"])
```

## 📈 Performance Optimization

### Database Indexing
```sql
-- Critical indexes for performance
CREATE INDEX idx_prices_symbol_date ON asset_prices(symbol, date);
CREATE INDEX idx_prices_date ON asset_prices(date);
CREATE INDEX idx_assets_active ON assets(is_active);
CREATE INDEX idx_risk_metrics_symbol_period ON risk_metrics(symbol, period);
```

### Caching
Consider implementing Redis caching for:
- Frequently requested assets
- Historical price data
- Optimization results

### Query Optimization
- Use connection pooling
- Limit result sets
- Pre-calculate risk metrics (you already have this!)

## 🤝 Integration with Your Existing Code

Your existing code already provides:

1. **Data Loading**: `02a_load_sample_historicalV2.py`
2. **Risk Metrics**: `RiskMetricsCalculator.py`
3. **Optimization Engine**: `EnhancedPortfolioOptimizer.py`

This web interface adds:
- User-friendly visualization
- Interactive portfolio construction
- Real-time optimization
- Export capabilities

## 📝 Next Steps

### Enhancements to Consider

1. **Backtesting**
   - Historical performance simulation
   - Walk-forward analysis
   - Out-of-sample testing

2. **Additional Visualizations**
   - Returns distribution histogram
   - Drawdown charts
   - Rolling performance metrics

3. **Portfolio Comparison**
   - Compare multiple strategies
   - Benchmark against indices
   - Statistical significance tests

4. **Advanced Analytics**
   - Factor exposure analysis
   - Style drift detection
   - Regime detection

5. **User Features**
   - Save/load portfolios
   - Portfolio history tracking
   - Email reports

## 📧 Support

For issues specific to:
- **Database schema**: Review your DatabaseV5_Enhanced.py
- **Optimization methods**: Check EnhancedPortfolioOptimizer.py
- **Data loading**: See 02a_load_sample_historicalV2.py

## 📄 License

This tool is designed for personal/internal use with your proprietary market data.

---

## Quick Start Checklist

- [ ] Install Python dependencies
- [ ] Update `db_config.py` with database credentials
- [ ] Verify database connection
- [ ] Run `python portfolio_optimizer_api.py`
- [ ] Open `http://localhost:5000` in browser
- [ ] Search and add 2+ assets
- [ ] Select time period
- [ ] Click "Optimize Portfolio"
- [ ] Review results and export

**Questions?** Check the Troubleshooting section above.
