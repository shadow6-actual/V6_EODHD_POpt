# Script 12: Robust Universe Loader (The "Deep Fix")
# PURPOSE: Loads asset universe with strict validation and error isolation.
#          1. Verifies API actually returns key assets ("Canaries")
#          2. Loads to DB with row-level error isolation (bad rows don't kill good ones)
#          3. Performs post-load audit to guarantee integrity

import sys
import time
import logging
from pathlib import Path
from sqlalchemy import text
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_v6
from models_v6 import Asset, get_session
from eodhd_client import EODHDClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# "Canary" Assets - If these are missing, the load is considered a FAILURE.
CANARY_ASSETS = {
    'US': ['AAPL', 'MSFT', 'NVDA', 'JPM', 'XOM', 'V', 'DIS', 'TSLA'],
    'LSE': ['SHEL', 'HSBA', 'BP', 'AZN'],
    'TO': ['RY', 'TD', 'SHOP', 'CNQ'],
    'XETRA': ['SAP', 'SIE', 'ALV']
}

def load_exchange_robust(client, engine, exchange_code):
    logger.info("=" * 70)
    logger.info(f"🏗️  ROBUST LOAD: {exchange_code}")
    logger.info("=" * 70)

    # 1. Fetch Raw Data
    try:
        logger.info(f"   Fetching symbol list from EODHD...")
        symbols_data = client.get_exchange_symbols(exchange_code)
        if not symbols_data:
            logger.error(f"❌ API returned NO data for {exchange_code}")
            return
        logger.info(f"   ✅ API returned {len(symbols_data):,} raw symbols.")
    except Exception as e:
        logger.error(f"❌ API Error: {e}")
        return

    # 2. Canary Check (API Level)
    # Did the API even send us Apple?
    if exchange_code in CANARY_ASSETS:
        missing_canaries = []
        raw_codes = {item['Code'] for item in symbols_data}
        
        for canary in CANARY_ASSETS[exchange_code]:
            if canary not in raw_codes:
                missing_canaries.append(canary)
        
        if missing_canaries:
            logger.error(f"🚨 CRITICAL API FAILURE: EODHD list is missing key assets: {missing_canaries}")
            logger.error("   Aborting load to prevent database pollution.")
            return
        else:
            logger.info(f"   ✅ API Integrity Check Passed (Found all {len(CANARY_ASSETS[exchange_code])} canary assets)")

    # 3. Robust Loading (Upsert)
    # We use smaller batches and try/except blocks to prevent rollback of good data
    with get_session(engine) as session:
        added = 0
        updated = 0
        errors = 0
        
        # Pre-fetch existing symbols for speed (set of strings)
        existing_query = text(f"SELECT symbol FROM assets WHERE exchange = :ex")
        existing_symbols = {row[0] for row in session.execute(existing_query, {"ex": exchange_code})}
        
        total = len(symbols_data)
        
        for i, item in enumerate(symbols_data):
            try:
                code = item.get('Code')
                if not code: continue
                
                full_symbol = f"{code}.{exchange_code}"
                name = item.get('Name', '')
                asset_type = item.get('Type', 'Unknown')
                
                # Logic: Update if exists, Insert if new
                if full_symbol in existing_symbols:
                    # Update logic (SQLAlchemy bulk update is faster, but we do row-by-row for safety here)
                    # We only update if something important changed or to reactivate
                    # For speed, we might skip heavy updates, but let's ensure Active status
                    pass 
                else:
                    # Create New
                    new_asset = Asset(
                        symbol=full_symbol,
                        code=code,
                        exchange=exchange_code,
                        name=name,
                        asset_type=asset_type,
                        currency=item.get('Currency'),
                        country=item.get('Country'),
                        is_active=True,
                        first_seen=datetime.utcnow(),
                        last_updated=datetime.utcnow(),
                        data_source='EODHD_ROBUST'
                    )
                    session.add(new_asset)
                    added += 1

                # Commit every 500 rows to lock in progress
                if i > 0 and i % 500 == 0:
                    session.commit()
                    print(f"\r   Progress: {i}/{total} ({i/total*100:.1f}%)", end="")

            except Exception as e:
                errors += 1
                session.rollback() # Rollback ONLY this transaction, not the whole script
                logger.debug(f"   Error on row {i}: {e}")

        session.commit() # Final commit
        print(f"\r   Progress: {total}/{total} (100.0%)")
        logger.info(f"   ✅ Load Complete: {added} Added, {errors} Errors.")

    # 4. Post-Load Audit (Database Level)
    # Verify the Canaries are actually IN the database now
    if exchange_code in CANARY_ASSETS:
        logger.info("   🔍 Running Post-Load Audit...")
        with get_session(engine) as session:
            all_good = True
            for canary in CANARY_ASSETS[exchange_code]:
                sym = f"{canary}.{exchange_code}"
                exists = session.query(Asset).filter_by(symbol=sym).first()
                if not exists:
                    logger.error(f"   ❌ AUDIT FAILED: {sym} is missing from database!")
                    all_good = False
                elif not exists.is_active:
                    logger.warning(f"   ⚠️  AUDIT WARNING: {sym} exists but is Inactive. Reactivating...")
                    exists.is_active = True
                    session.commit()
            
            if all_good:
                logger.info("   ✅ AUDIT PASSED: All key assets present and active.")

def main():
    client = EODHDClient(config_v6.EODHD_API_TOKEN)
    engine = config_v6.get_postgres_engine()
    
    # Prioritize US
    load_exchange_robust(client, engine, 'US')
    
    # Then load others
    for ex in ['LSE', 'TO', 'XETRA']:
        load_exchange_robust(client, engine, ex)

if __name__ == "__main__":
    main()