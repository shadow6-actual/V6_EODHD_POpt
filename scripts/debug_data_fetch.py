# scripts/debug_data_fetch.py
import sys
import logging
from pathlib import Path
import pandas as pd
from sqlalchemy import text  # <--- Added this

# Setup path to import from parent directory
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
sys.path.append(str(root_dir))

logging.basicConfig(level=logging.INFO)

try:
    from webapp.data_manager import data_manager
    from models_v6 import Asset, AssetPrice
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test_fetch():
    print("="*60)
    print("🕵️‍♂️ DATA FETCH DIAGNOSTIC")
    print("="*60)

    test_tickers = ['AAPL.US', 'MSFT.US', 'SPY.US']
    print(f"1. Testing Tickers: {test_tickers}")

    # Check Master DB
    print("\n--- Checking Master DB (Postgres) ---")
    with data_manager._get_postgres_session() as session:
        found_assets = session.query(Asset.symbol).filter(Asset.symbol.in_(test_tickers)).all()
        found_symbols = [r[0] for r in found_assets]
        print(f"   Found in Assets Table: {found_symbols}")
        
        if found_symbols:
            sample_ticker = found_symbols[0]
            price_count = session.query(AssetPrice).filter(AssetPrice.symbol == sample_ticker).count()
            print(f"   Price records for {sample_ticker}: {price_count}")

    # Test Cache
    print("\n--- Testing Data Manager Cache ---")
    try:
        valid = data_manager.ensure_tickers_in_cache(test_tickers)
        print(f"   ensure_tickers_in_cache returned: {valid}")
    except Exception as e:
        print(f"   ❌ Cache Sync Failed: {e}")
        return

    # Test DataFrame
    print("\n--- Testing DataFrame Retrieval ---")
    start_date = "2020-01-01"
    try:
        df = data_manager.get_price_history(test_tickers, start_date=start_date)
        print(f"   Querying from {start_date}...")
        
        if df.empty:
            print("   ❌ RESULT: DataFrame is EMPTY.")
            # Debug SQLite Content safely
            with data_manager._get_sqlite_session() as s:
                # FIXED: Wrapped in text() for SQLAlchemy 2.0 compliance
                count = s.execute(text("SELECT count(*) FROM asset_prices")).scalar()
                print(f"      (Debug) Total rows in SQLite 'asset_prices': {count}")
                if count > 0:
                    sample = s.execute(text("SELECT * FROM asset_prices LIMIT 5")).fetchall()
                    print(f"      (Debug) Sample rows in SQLite: {sample}")
        else:
            print(f"   ✅ SUCCESS: Retrieved {len(df)} rows.")
            print(df.head())

    except Exception as e:
        print(f"   ❌ DataFrame Fetch Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fetch()