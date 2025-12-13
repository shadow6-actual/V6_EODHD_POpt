# Script: Force Reload Ticker
# UTILITY: Deletes all price history for a symbol and re-downloads fresh Daily data.
# Use this to fix corrupted or sparse data.

import sys
import logging
import requests
from pathlib import Path
from datetime import datetime
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_v6
from models_v6 import AssetPrice, get_session
from eodhd_client import EODHDClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def delete_price_history(engine, symbol):
    """Delete all price records for a specific symbol"""
    print(f"🗑️  Deleting existing data for {symbol}...")
    with get_session(engine) as session:
        # Direct SQL delete is often safer/faster for bulk deletes
        session.execute(text("DELETE FROM asset_prices WHERE symbol = :sym"), {"sym": symbol})
        session.commit()
        print(f"   Records deleted.")

def download_full_history(client, engine, symbol):
    """Download fresh daily history from 1995"""
    print(f"📥 Downloading fresh DAILY history for {symbol}...")
    
    url = f"{config_v6.EODHD_BASE_URL}/eod/{symbol}"
    params = {
        'api_token': client.api_token,
        'from': '1995-01-01',  # Force deep history
        'fmt': 'json',
        'period': 'd'          # EXPLICITLY request Daily data
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            return

        data = response.json()
        if not data:
            print("❌ No data returned from API")
            return

        print(f"   Received {len(data):,} records from API. Saving to DB...")

        with get_session(engine) as session:
            count = 0
            for row in data:
                try:
                    p = AssetPrice(
                        symbol=symbol,
                        date=datetime.strptime(row['date'], '%Y-%m-%d').date(),
                        open=row.get('open'),
                        high=row.get('high'),
                        low=row.get('low'),
                        close=row.get('close'),
                        adjusted_close=row.get('adjusted_close'),
                        volume=row.get('volume'),
                        data_source='EODHD_RELOAD',
                        is_validated=True
                    )
                    session.add(p)
                    count += 1
                except Exception:
                    pass # Skip duplicates
            
            session.commit()
            print(f"✅ Successfully saved {count:,} daily records.")

    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    client = EODHDClient(config_v6.EODHD_API_TOKEN)
    engine = config_v6.get_postgres_engine()

    while True:
        print("\n" + "="*50)
        symbol = input("Enter Ticker to FORCE RELOAD (e.g. GALDY.US) or 'q': ").strip().upper()
        
        if symbol == 'Q':
            break
        if not symbol:
            continue

        # 1. Delete bad data
        delete_price_history(engine, symbol)
        
        # 2. Download fresh data
        download_full_history(client, engine, symbol)

if __name__ == "__main__":
    main()