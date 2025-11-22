# Portfolio Optimizer - Quick Reference Card

## 🚀 Getting Started (5 Minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Server
```bash
python start_optimizer.py
# OR
python portfolio_optimizer_api_v5.py
```

### 3. Open Browser
```
http://localhost:5000
```

---

## 📁 File Structure

```
portfolio_optimizer/
├── portfolio_optimizer_api_v5.py    # Main API server (use this one!)
├── start_optimizer.py               # Startup script with checks
├── db_config.py                     # Database configuration
├── requirements.txt                 # Python dependencies
│
├── DatabaseV5_Enhanced.py           # Your existing DB module
├── EnhancedPortfolioOptimizer.py    # Your existing optimizer
├── RiskMetricsCalculator.py         # Your existing risk calculator
│
└── static/
    ├── index.html                   # Web interface
    ├── styles.css                   # Styling
    └── app.js                       # Frontend logic
```

---

## 🔧 Common Tasks

### Search for Assets
Type symbol or name in search box:
- `SPY` → finds S&P 500 ETF
- `Apple` → finds AAPL
- `Vanguard` → finds all Vanguard funds

### Optimize Portfolio
1. Select 2+ assets
2. Choose time period (or use quick buttons)
3. Select optimization method
4. Click "Optimize Portfolio"

### Export Results
- CSV: Tabular data for Excel
- JSON: Complete data structure
- Print: PDF via browser print

### Change Optimization Settings
- Risk-free rate: Adjust for current T-bill rates
- Constraints: Set min/max weights per asset
- Efficient frontier: Enable for risk/return visualization

---

## 🎯 Optimization Methods

| Method | Best For | When to Use |
|--------|----------|-------------|
| **Max Sharpe** | Risk-adjusted returns | Most common, balanced approach |
| **Min Volatility** | Risk averse | Capital preservation priority |
| **Risk Parity** | Diversification | Equal risk contribution |
| **HRP** | Robust portfolios | Unstable correlation periods |
| **Max Return** | Aggressive growth | With volatility constraint |

---

## 💡 Pro Tips

### Performance
- Add database indexes for faster queries:
```sql
CREATE INDEX idx_prices_symbol_date ON asset_prices(symbol, date);
```

### Data Quality
- Need minimum 12 months of price data
- Longer periods (5+ years) give better optimization
- Watch for assets with data gaps

### Interpretation
- **Sharpe > 1.0**: Good risk-adjusted performance
- **Max Drawdown**: Worst peak-to-trough decline
- **Sortino**: Like Sharpe but focuses on downside risk
- **VaR/CVaR**: Expected loss at confidence level

### Troubleshooting
```bash
# Check if server is running
curl http://localhost:5000/api/health

# View server logs
# Look in terminal where you started the server

# Test database connection
python -c "from DatabaseV5_Enhanced import session_scope; print('✓ DB OK')"
```

---

## 🌐 API Endpoints

### Search Assets
```bash
curl "http://localhost:5000/api/search_assets?query=SPY"
```

### Optimize
```bash
curl -X POST http://localhost:5000/api/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["SPY", "AGG", "GLD"],
    "method": "max_sharpe",
    "start_date": "2019-01-01",
    "end_date": "2024-01-01",
    "risk_free_rate": 0.02
  }'
```

---

## 🔐 Security for Production

### Disable Debug Mode
```python
# In portfolio_optimizer_api_v5.py
app.run(debug=False, host='0.0.0.0', port=5000)
```

### Use Environment Variables
```bash
export DATABASE_URL="postgresql://user:pass@localhost/db"
export FLASK_SECRET_KEY="your-secret-key"
```

### Enable HTTPS
Use nginx or Apache as reverse proxy with SSL certificate

---

## 📊 Database Statistics (Your Data)

- **Total Assets**: 157,044
- **Assets with Data**: 152,706 (97.2%)
- **Price Records**: 109.5 million
- **Coverage**: 30 years (1995-2025)
- **Exchanges**: 45+ global exchanges

---

## 🆘 Quick Fixes

### "Database not configured"
→ Check DatabaseV5_Enhanced.py is in same directory
→ Verify DB_FILE path is correct

### "Optimization failed to converge"
→ Try different method (Risk Parity is most stable)
→ Check for highly correlated assets
→ Ensure sufficient data history

### "Insufficient data"
→ Need minimum 12 months
→ Try longer time period
→ Verify assets have continuous data

### "Search returns no results"
→ Check asset is marked as is_active=True
→ Try searching by partial symbol

---

## 📚 Further Reading

- Modern Portfolio Theory: Harry Markowitz
- Risk Parity: Edward Qian
- Hierarchical Risk Parity: Marcos López de Prado
- Black-Litterman Model: Fischer Black, Robert Litterman

---

## 🎓 Example Portfolios to Try

### Conservative (Low Risk)
- 40% AGG (Bonds)
- 30% SPY (US Stocks)
- 20% VNQ (REITs)
- 10% GLD (Gold)
→ Use: Min Volatility

### Balanced (Moderate Risk)
- 50% VTI (Total US Market)
- 30% VXUS (International)
- 15% AGG (Bonds)
- 5% VNQ (REITs)
→ Use: Max Sharpe

### Aggressive (High Risk)
- 70% QQQ (Tech-heavy)
- 20% EEM (Emerging Markets)
- 10% VNQ (REITs)
→ Use: Max Return with 20% max volatility

---

## 📞 Need Help?

1. Check the full README.md for detailed documentation
2. Review troubleshooting section
3. Check server terminal for error messages
4. Verify database connection with test script

---

**Remember**: Past performance does not guarantee future results. Use this tool for analysis and research, not as investment advice.
