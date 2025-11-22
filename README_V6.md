# V6 EODHD Hybrid Portfolio Database System

## 🎯 Overview

Professional-grade portfolio optimization database system with:
- **PostgreSQL Master Database**: 150,000+ tickers from 70+ global exchanges
- **SQLite Working Database**: Fast, portable database for your active portfolio
- **EODHD Data Source**: Reliable, comprehensive financial data
- **Hybrid Architecture**: Best of both worlds - complete data archive + lightning-fast analysis

---

## 📁 Project Structure

```
V6_EODHD_Hybrid/
├── config_v6.py              # Main configuration (EDIT THIS!)
├── models_v6.py               # Database models (PostgreSQL + SQLite)
├── eodhd_client.py            # EODHD API client
├── setup_v6.py                # One-time setup script
│
├── scripts/                   # Data loading and maintenance scripts
│   ├── 01_load_universe.py   # Load all ticker symbols
│   ├── 02_load_historical_data.py  # Load historical prices
│   ├── 03_setup_weekly_update.py   # Set up automation
│   └── 04_materialize_sqlite.py    # Create working database
│
└── logs/                      # Log files
    ├── portfolio_system_v6.log
    ├── eodhd_api_calls.log
    └── errors.log
```

---

## 🚀 Quick Start Guide

### Step 1: Configure Settings

1. **Open `config_v6.py` in a text editor**

2. **Set your PostgreSQL password:**
```python
POSTGRES_CONFIG = {
    'password': 'YOUR_ACTUAL_PASSWORD',  # Change this!
}
```

3. **Set your EODHD API token:**
   - Log in to https://eodhd.com/cp/settings
   - Copy your API key
   - Paste it in config_v6.py:
```python
EODHD_API_TOKEN = "paste_your_token_here"
```

4. **Edit your portfolio tickers (optional):**
```python
MY_PORTFOLIO_TICKERS = [
    'AAPL.US',
    'MSFT.US',
    'GOOGL.US',
    # ... add your holdings
]
```

5. **Save the file**

### Step 2: Install Dependencies

```bash
pip install sqlalchemy psycopg2-binary pandas requests numpy
```

### Step 3: Run Setup

```bash
python setup_v6.py
```

This will:
- ✅ Check all dependencies
- ✅ Validate your configuration
- ✅ Test PostgreSQL connection
- ✅ Test EODHD API connection
- ✅ Create database tables
- ✅ Initialize both PostgreSQL and SQLite databases

**If setup succeeds**, you'll see:
```
🎉 SETUP COMPLETE!
```

**If setup fails**, fix the reported errors and run again.

---

## 📊 Data Loading Process

### Phase 1: Load Universe (~5 minutes)

```bash
python scripts/01_load_universe.py
```

What this does:
- Fetches all 70+ exchanges from EODHD
- Downloads complete ticker list for each exchange
- Populates `assets` table with ~150,000 tickers
- API calls: ~70-100

**Expected output:**
```
Loaded 51,234 US tickers
Loaded 15,678 LSE tickers
...
Total: 147,892 tickers loaded
```

### Phase 2: Load Historical Data (~2-8 hours)

```bash
python scripts/02_load_historical_data.py
```

What this does:
- For each exchange, downloads historical monthly data using **Bulk API**
- Loads data from 1980-present (where available)
- Downloads splits and dividends
- Validates data quality
- API calls: ~200-500 per exchange

**Progress tracking:**
- Watch the console output
- Check `logs/portfolio_system_v6.log`
- Monitor API usage: `tail -f logs/eodhd_api_calls.log`

**This will take time!** Grab coffee ☕. The script can be safely interrupted and resumed.

### Phase 3: Set Up Weekly Updates (~2 minutes)

```bash
python scripts/03_setup_weekly_update.py
```

What this does:
- Creates a scheduled task (Windows Task Scheduler / cron)
- Runs every Sunday at 2:00 AM
- Updates PostgreSQL with last week's data
- API calls: ~200-300 per week

### Phase 4: Create Working Database (~5 minutes)

```bash
python scripts/04_materialize_sqlite.py
```

What this does:
- Copies your portfolio holdings from PostgreSQL → SQLite
- Copies benchmark tickers (SPY, QQQ, etc.)
- Copies any watchlist tickers
- Creates a fast, portable SQLite database for analysis

**Result:** A ~100-200 MB SQLite database with just the tickers you need.

---

## 💾 Database Architecture

### PostgreSQL (Master Database)

**Purpose:** Long-term data archive of ALL 150K tickers

**Location:** `localhost:5432/portfolio_master`

**Size:** ~15-20 GB

**Tables:**
- `assets` - All ticker symbols and metadata
- `asset_prices` - Historical OHLCV data
- `corporate_actions` - Splits and dividends
- `asset_fundamentals` - Calculated metrics
- `risk_metrics` - Pre-calculated risk measures
- `update_log` - Change tracking
- `api_usage` - API call tracking

**When to use:**
- Researching new tickers
- Historical backtesting
- Building custom screening tools
- Exploring correlations across markets

### SQLite (Working Database)

**Purpose:** Fast analysis of your active portfolio

**Location:** `D:/FolioData/FolioF/portfolio_working_v6.db`

**Size:** ~100-500 MB

**Contains:**
- Your portfolio holdings
- Your watchlist
- Benchmark indices (SPY, QQQ, AGG, etc.)
- Sector ETFs
- Any manually added tickers

**When to use:**
- Portfolio optimization
- Daily performance tracking
- Your Portfolio Visualizer clone
- Any analysis requiring fast queries

---

## 🔄 Daily/Weekly Operations

### Add a New Ticker to Working Database

```python
from materialization.on_demand_add import add_ticker_to_working_db

add_ticker_to_working_db('NVDA.US')  # Copies from PostgreSQL to SQLite
```

### Check API Usage

```python
from eodhd_client import EODHDClient
import config_v6

client = EODHDClient(config_v6.EODHD_API_TOKEN)
usage = client.get_api_usage_today()
print(f"API calls today: {usage['total_calls']:,}")
print(f"Remaining: {usage['remaining_calls']:,}")
```

### Query Price Data

```python
from sqlalchemy import create_engine
import config_v6
import models_v6

# Use SQLite for fast queries
engine = config_v6.get_sqlite_engine()
from models_v6 import get_session, get_price_data

with get_session(engine) as session:
    prices = get_price_data(
        session, 
        symbol='AAPL.US',
        start_date='2023-01-01',
        end_date='2024-01-01'
    )
    print(f"Retrieved {len(prices)} price records")
```

### Regenerate Working Database

If you want to rebuild your SQLite database from scratch:

```bash
python scripts/04_materialize_sqlite.py --rebuild
```

---

## 📈 API Usage Management

### Daily Limits

- **EODHD Plan:** 100,000 API calls per day
- **Weekly updates:** ~200-300 calls per week
- **Initial load:** ~5,000-10,000 calls (one-time)

### API Call Costs

| Operation | API Calls |
|-----------|-----------|
| Get exchange ticker list | 1 per exchange |
| Bulk EOD download (entire exchange) | 100 per exchange |
| Individual ticker EOD | 1 per ticker |
| Bulk splits (entire exchange) | 100 |
| Bulk dividends (entire exchange) | 100 |

**Example: Weekly US market update**
- Bulk EOD (US): 100 calls
- Bulk splits (US): 100 calls
- Bulk dividends (US): 100 calls
- **Total: 300 calls** (0.3% of daily limit)

### Monitoring

All API calls are logged in:
- `api_usage` table (PostgreSQL)
- `logs/eodhd_api_calls.log`

---

## 🛠️ Maintenance Tasks

### Weekly: Automatic Updates

The weekly update script runs automatically:
- **When:** Every Sunday at 2:00 AM
- **What:** Updates PostgreSQL with last week's data
- **Time:** ~5-10 minutes
- **API calls:** ~200-300

**Check status:**
```bash
# View recent update logs
tail -100 logs/portfolio_system_v6.log
```

### Monthly: Refresh Working Database

Regenerate your SQLite working database to pick up new data:

```bash
python scripts/04_materialize_sqlite.py
```

### Quarterly: Data Quality Check

```bash
python scripts/data_quality_check.py
```

This will:
- Identify missing data
- Flag suspicious price jumps
- Check for stale tickers
- Generate quality report

### Annually: Database Maintenance

```bash
python scripts/database_maintenance.py
```

This will:
- Vacuum PostgreSQL database
- Reindex tables
- Archive very old data (optional)
- Optimize query performance

---

## 🔒 Backup Strategy

### PostgreSQL Backup

**Option 1: Built-in backup**
```bash
# Full backup
pg_dump -U postgres -d portfolio_master -f backup_$(date +%Y%m%d).sql

# Restore
psql -U postgres -d portfolio_master -f backup_20241109.sql
```

**Option 2: Export critical tickers to CSV**
```python
python scripts/export_to_csv.py --tickers MY_PORTFOLIO_TICKERS
```

### SQLite Backup

Simply copy the file:
```bash
cp portfolio_working_v6.db portfolio_working_v6_backup.db
```

---

## 🆘 Troubleshooting

### PostgreSQL won't connect

**Error:** `psycopg2.OperationalError: could not connect to server`

**Solutions:**
1. Check if PostgreSQL is running:
   ```bash
   pg_ctl status
   ```
2. Verify password in `config_v6.py`
3. Ensure database exists:
   ```bash
   createdb -U postgres portfolio_master
   ```

### EODHD API errors

**Error:** `401 Unauthorized`
- Invalid API token in `config_v6.py`
- Check your token at: https://eodhd.com/cp/settings

**Error:** `429 Too Many Requests`
- You've hit daily API limit (100,000 calls)
- Wait until tomorrow
- Check usage: `SELECT * FROM api_usage ORDER BY date DESC LIMIT 1;`

### Import errors

**Error:** `ModuleNotFoundError: No module named 'psycopg2'`

**Solution:**
```bash
pip install psycopg2-binary
```

### Setup script fails

Run each validation manually:
```python
import setup_v6
setup_v6.check_dependencies()
setup_v6.validate_config()
setup_v6.test_postgres_connection()
setup_v6.test_eodhd_api()
```

---

## 📚 Additional Resources

### EODHD Documentation
- API Docs: https://eodhd.com/financial-apis/
- Control Panel: https://eodhd.com/cp/settings
- Supported Exchanges: https://eodhd.com/list-of-stock-markets

### PostgreSQL Resources
- Documentation: https://www.postgresql.org/docs/
- pgAdmin GUI: Installed with PostgreSQL

### Support

For issues with:
- **This system:** Review logs in `logs/` directory
- **EODHD API:** Contact support@eodhd.com (24/7 live chat)
- **PostgreSQL:** Check postgresql.org documentation

---

## 🎯 What's Next?

After setup is complete, you can:

1. **Build your Portfolio Visualizer clone**
   - Use SQLite working database
   - Lightning-fast queries
   - All the tickers you need

2. **Create custom screening tools**
   - Query PostgreSQL for research
   - Scan all 150K tickers
   - Find hidden opportunities

3. **Backtest strategies**
   - 30+ years of data
   - Multiple asset classes
   - Global diversification

4. **Track portfolio performance**
   - Real-time monitoring (with working DB)
   - Historical analysis
   - Risk metrics

---

## 📞 Questions?

Before asking for help, check:
1. ✅ Logs in `logs/` directory
2. ✅ This README
3. ✅ EODHD documentation
4. ✅ PostgreSQL is running

---

**Ready to begin?** Start with Step 1: Configure Settings!

**Good luck! 🚀**
