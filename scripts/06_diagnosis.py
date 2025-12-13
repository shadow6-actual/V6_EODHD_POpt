# Script 06: Diagnosis Sampler
# Checks data density across different exchanges to identify corruption scope.

import sys
import random
import logging
from pathlib import Path
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_v6
from models_v6 import get_session

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

def check_exchange_health(engine, exchange_code):
    print(f"\n🔍 DIAGNOSING EXCHANGE: {exchange_code}")
    print("-" * 60)
    
    with get_session(engine) as session:
        # 1. Get total assets for this exchange
        total_assets = session.execute(text(
            "SELECT COUNT(*) FROM assets WHERE exchange = :ex"
        ), {"ex": exchange_code}).scalar()
        
        if total_assets == 0:
            print(f"   ⚠️  No assets found in Universe for {exchange_code}")
            return

        # 2. Get 5 random symbols that HAVE price data
        # We look for symbols that actually have at least 1 price record
        query = text("""
            SELECT DISTINCT symbol 
            FROM asset_prices 
            WHERE symbol LIKE :pattern
            LIMIT 100
        """)
        # Pattern match for the exchange (e.g., %.US or %.LSE)
        pattern = f"%.{exchange_code}"
        
        result = session.execute(query, {"pattern": pattern}).fetchall()
        available_symbols = [row[0] for row in result]
        
        if not available_symbols:
            print(f"   ❌ No price data found for ANY ticker in {exchange_code}")
            return

        # Pick up to 5 random ones
        sample_size = min(5, len(available_symbols))
        samples = random.sample(available_symbols, sample_size)
        
        # 3. Analyze depth for these samples
        print(f"   Analzying {sample_size} random samples:")
        for sym in samples:
            count = session.execute(text(
                "SELECT COUNT(*) FROM asset_prices WHERE symbol = :sym"
            ), {"sym": sym}).scalar()
            
            min_date = session.execute(text(
                "SELECT MIN(date) FROM asset_prices WHERE symbol = :sym"
            ), {"sym": sym}).scalar()
            
            max_date = session.execute(text(
                "SELECT MAX(date) FROM asset_prices WHERE symbol = :sym"
            ), {"sym": sym}).scalar()
            
            # VERDICT LOGIC
            status = "✅ HEALTHY"
            if count < 500: status = "❌ CORRUPT/SPARSE"
            elif count < 2000: status = "⚠️  SUSPICIOUS"
            
            print(f"   - {sym:<15} | Records: {count:<6} | Range: {min_date} to {max_date} | {status}")

def main():
    engine = config_v6.get_postgres_engine()
    
    # Check the major markets you care about
    exchanges_to_check = ['US', 'LSE', 'TO', 'XETRA', 'HK']
    
    for ex in exchanges_to_check:
        check_exchange_health(engine, ex)
        
    print("\n" + "="*60)
    print("DIAGNOSIS COMPLETE")
    print("="*60)
    print("If you see 'CORRUPT/SPARSE' across all exchanges, the previous download method was flawed.")
    print("If only US is sparse, we only need to wipe US data.")

if __name__ == "__main__":
    main()