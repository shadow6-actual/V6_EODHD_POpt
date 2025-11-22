# AGGRESSIVE BATCH LOADING SYSTEM
## Load 15,000 Tickers Per Night - Complete Universe in ~10 Days

---

## 📋 OVERVIEW

Your portfolio optimization database needs ~150K tickers loaded. With your current API plan, 
we're using an aggressive nightly batch strategy:

- **15,000 tickers per run** (~75 minutes with 0.3s rate limiting)
- **~10 nights to complete** (150K ÷ 15K = 10 runs)
- **Fully resumable** - tracks progress in database
- **Smart prioritization** - loads best data first

---

## 🚀 HOW TO USE

### **Night 1-10: Run the Batch Loader**

```bash
# Navigate to your scripts directory
cd D:/FolioData/FolioF/PortfolioOptimizationPythonFiles/V6_EODHD_Hybrid/scripts

# Run the batch loader
python 02a_load_sample_historical.py
```

**What happens:**
1. Shows current database statistics
2. Selects next 15,000 tickers (smart prioritization)
3. Shows batch summary and estimated runtime
4. Loads all 15,000 tickers (~75 minutes)
5. Updates database and shows new statistics

**Prioritization:**
- ✅ US exchange first (most important)
- ✅ Major exchanges next (LSE, XETRA, HK, TO, JPX)
- ✅ Common stocks before other asset types
- ✅ ETFs prioritized highly
- ✅ Never-loaded assets before old data

---

## 📊 CHECK YOUR PROGRESS ANYTIME

```bash
python 02c_check_loading_progress.py
```

**Shows you:**
- Total assets loaded vs remaining
- Coverage by exchange
- Recent loading activity
- Estimated runs/days to completion

---

## 💡 RECOMMENDED SCHEDULE

### **Overnight Runs (While You Sleep)**

```
Night 1:  Load 15,000 tickers (mostly US)         →  15K / 150K  (10%)
Night 2:  Load 15,000 tickers (US + major EU)     →  30K / 150K  (20%)
Night 3:  Load 15,000 tickers (US + LSE + TO)     →  45K / 150K  (30%)
Night 4:  Load 15,000 tickers (mixed)             →  60K / 150K  (40%)
Night 5:  Load 15,000 tickers (mixed)             →  75K / 150K  (50%)
Night 6:  Load 15,000 tickers (mixed)             →  90K / 150K  (60%)
Night 7:  Load 15,000 tickers (smaller exchanges) → 105K / 150K  (70%)
Night 8:  Load 15,000 tickers (smaller exchanges) → 120K / 150K  (80%)
Night 9:  Load 15,000 tickers (remaining)         → 135K / 150K  (90%)
Night 10: Load 15,000 tickers (final batch)       → 150K / 150K  (100%) ✅
```

**Runtime:** ~75 minutes per night

---

## 🛡️ SAFETY FEATURES

### **Fully Resumable**
- Can stop anytime (Ctrl+C)
- Progress saved in database
- Next run picks up where you left off

### **No Duplicates**
- Checks database before inserting
- Won't reload same ticker twice

### **API Protection**
- Rate limited to stay under 100K daily limit
- 15,000 calls << 100,000 limit (only 15% of quota)

### **Error Handling**
- Failed tickers logged
- Script continues on errors
- Can review failures in log files

---

## 📈 WHAT YOU'LL HAVE AFTER 10 DAYS

```
✅ ~150,000 tickers loaded
✅ ~30 years of historical data per ticker (1995-2025)
✅ All major exchanges covered
✅ Mix of stocks, ETFs, funds, bonds
✅ Ready for portfolio optimization
✅ Total price records: ~50-100 million
```

---

## 🔧 CONFIGURATION OPTIONS

### **Want to be MORE aggressive?**

Edit `02a_load_sample_historical.py`:

```python
BATCH_SIZE = 20000  # Load 20K per night (5-7 days to complete)
API_RATE_LIMIT_DELAY = 0.2  # Faster (more risky)
```

### **Want to be LESS aggressive?**

```python
BATCH_SIZE = 10000  # Load 10K per night (15 days to complete)
API_RATE_LIMIT_DELAY = 0.5  # Safer
```

### **Change historical depth:**

```python
HISTORICAL_START_DATE = "2000-01-01"  # Only last 25 years
HISTORICAL_START_DATE = "1980-01-01"  # Full 45 years (slower)
```

---

## 📁 FILE LOCATIONS

```
Scripts:
  02a_load_sample_historical.py     - Main batch loader
  02c_check_loading_progress.py     - Progress checker

Logs:
  D:/FolioData/FolioF/PortfolioOptimizationPythonFiles/V6_EODHD_Hybrid/logs/
    load_batch_historical.log       - Detailed run log

Database:
  PostgreSQL: portfolio_master
    Tables: assets, asset_prices, update_log
```

---

## 🎯 TYPICAL WORKFLOW

### **Day 1:**
```bash
# Check what you have
python 02c_check_loading_progress.py

# Start first batch (before bed)
python 02a_load_sample_historical.py

# Go to sleep 😴
# Wake up to 15K tickers loaded ☕
```

### **Days 2-10:**
```bash
# Check progress
python 02c_check_loading_progress.py

# Run next batch
python 02a_load_sample_historical.py
```

### **Day 11:**
```bash
# Check - should be 100%!
python 02c_check_loading_progress.py

# Start building your optimization engine! 🎉
```

---

## 🐛 TROUBLESHOOTING

### **Script stops early?**
- Check logs/load_batch_historical.log
- Check API quota: might have hit daily limit
- Run again tomorrow - it will resume

### **Want to skip some exchanges?**
- Edit EXCHANGE_PRIORITY in 02a script
- Set unwanted exchanges to priority: 0

### **Getting 402 errors?**
- This is expected - your plan doesn't include bulk API
- Script is already using individual ticker endpoint
- Just more API calls but still works

### **Want to reload specific exchange?**
- Delete records for that exchange in database
- Script will reload them in next batch

---

## 📞 NEXT STEPS AFTER LOADING COMPLETE

Once all tickers are loaded:

1. **Build optimization engine** - Start replicating Portfolio Visualizer
2. **Run 03_setup_weekly_update.py** - Keep data fresh
3. **Create working database** (SQLite) - Fast local queries
4. **Build dashboard** - Visualize your universe

---

## ⚡ QUICK REFERENCE

```bash
# Check progress
python 02c_check_loading_progress.py

# Load next batch
python 02a_load_sample_historical.py

# View detailed logs
type logs\load_batch_historical.log
```

---

**Questions? Issues?**
- Check log files first: `logs/load_batch_historical.log`
- Review error messages
- Script is safe to run multiple times
- Each run is independent and resumable

**Let it run, let it load, let your database grow! 🚀**
