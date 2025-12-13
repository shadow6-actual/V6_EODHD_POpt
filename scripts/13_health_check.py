
# Script 13: Database Health & Forensics
# PURPOSE: Diagnoses the state of the DB after a crash/restart.
#          Tells you exactly when the last save happened and what is missing.

import sys
from pathlib import Path
from sqlalchemy import text, func
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_v6
from models_v6 import Asset, AssetPrice, UpdateLog, get_session

def run_health_check():
    engine = config_v6.get_postgres_engine()
    
    print("=" * 70)
    print("🏥 DATABASE HEALTH & FORENSICS REPORT")
    print("=" * 70)
    
    with get_session(engine) as session:
        # 1. TIME OF DEATH (Last successful write)
        last_write = session.query(func.max(AssetPrice.loaded_at)).scalar()
        
        if last_write:
            print(f"⏱️  Last Successful Data Save: {last_write}")
            time_since = datetime.utcnow() - last_write
            print(f"    (System has been idle for: {time_since})")
        else:
            print("⏱️  Last Successful Data Save: NEVER (No data found)")

        print("-" * 70)

        # 2. VITAL SIGNS (US Exchange)
        # We focus on US since that's what you were loading
        total_us = session.query(Asset).filter_by(exchange='US').count()
        
        # Count distinct US symbols that have price data
        loaded_us = session.query(func.count(func.distinct(AssetPrice.symbol)))\
                           .join(Asset, AssetPrice.symbol == Asset.symbol)\
                           .filter(Asset.exchange == 'US')\
                           .scalar()
        
        pct = (loaded_us / total_us * 100) if total_us > 0 else 0
        
        print(f"📊 US MARKET PROGRESS:")
        print(f"   Total Universe:  {total_us:,} tickers")
        print(f"   Fully Loaded:    {loaded_us:,} tickers")
        print(f"   Remaining:       {total_us - loaded_us:,} tickers")
        print(f"   Completion:      {pct:.1f}%")
        
        print("-" * 70)

        # 3. RECENT ACTIVITY LOG
        # Check the internal app logs
        print("📜 LAST 5 BATCH LOGS:")
        logs = session.query(UpdateLog)\
                      .order_by(UpdateLog.update_time.desc())\
                      .limit(5)\
                      .all()
        
        if logs:
            for log in logs:
                print(f"   [{log.update_time}] {log.status.upper()}: {log.message}")
        else:
            print("   (No logs found)")

        print("-" * 70)

        # 4. RECOMMENDATION
        print("👨‍⚕️  DIAGNOSIS:")
        if loaded_us == 0:
            print("   CRITICAL: No US data loaded. The script likely crashed immediately.")
        elif loaded_us < total_us:
            print("   NORMAL: Loading was interrupted but data is safe.")
            print("   Action: You can simply RESUME the script (02a).")
        else:
            print("   SUCCESS: US Market appears fully loaded.")

if __name__ == "__main__":
    run_health_check()