# FastAPI Backend - Quick Start

## Install Dependencies

```bash
pip install fastapi uvicorn[standard] pydantic
```

## Run the API

```bash
cd backend
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## Test the API

```bash
python test_api.py
```

## Access API Documentation

Open browser: `http://localhost:8000/docs`

## Endpoints

### Assets
- `GET /assets/search?q={query}` - Search assets
- `GET /assets/{symbol}` - Get asset info
- `GET /assets/{symbol}/prices` - Get price data
- `GET /assets/exchanges/list` - List exchanges

### Optimization
- `POST /optimize/` - Optimize portfolio
- `POST /optimize/efficient-frontier` - Calculate frontier
- `POST /optimize/performance` - Calculate performance
- `GET /optimize/risk-metrics/{symbol}` - Get risk metrics

## Example Usage

```python
import requests

# Search for assets
r = requests.get("http://localhost:8000/assets/search?q=AAPL&limit=5")
print(r.json())

# Optimize portfolio
payload = {
    "symbols": ["AAPL.US", "MSFT.US", "GOOGL.US"],
    "start_date": "2021-01-01",
    "end_date": "2024-01-01",
    "method": "max_sharpe",
    "risk_free_rate": 0.02,
    "frequency": "M"
}
r = requests.post("http://localhost:8000/optimize/", json=payload)
print(r.json())
```

## Methods Available

- `max_sharpe` - Maximum Sharpe Ratio
- `min_volatility` - Minimum Volatility
- `risk_parity` - Risk Parity
- `hrp` - Hierarchical Risk Parity
- `equal_weight` - Equal Weight

## Troubleshooting

**Port already in use:**
```bash
uvicorn api.main:app --port 8001
```

**Module not found:**
```bash
# Make sure you're in the backend directory
cd backend
python -m uvicorn api.main:app --reload
```
