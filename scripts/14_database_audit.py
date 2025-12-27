# -*- coding: utf-8 -*-
"""
Created on Sat Dec 13 15:17:39 2025

@author: Wes
"""

# Script 14: Final Database Audit
# PURPOSE: detailed "Report Card" for your database before optimization work.

import sys
from pathlib import Path
from sqlalchemy import text, func
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_v6
from models_v6 import Asset, AssetPrice, get_session

def run_audit():
    engine = config_v6.get_postgres_engine()
    
    print("=" * 70)
    print("🎓 FINAL DATABASE REPORT CARD")
    print("=" * 70)
    
    with get_session(engine) as session:
        # 1. UNIVERSE COVERAGE
        print("\n1️⃣  UNIVERSE COVERAGE")
        print("-" * 30)
        
        exchanges = ['US', 'LSE', 'TO', 'XETRA']
        for ex in exchanges:
            total = session.query(Asset).filter_by(exchange=ex).count()
            loaded = session.query(Asset).join(AssetPrice).filter(Asset.exchange==ex).distinct().count()
            pct = (loaded / total * 100) if total > 0 else 0
            
            status = "✅" if pct > 90 else "⚠️" if pct > 50 else "❌"
            print(f"   {status} {ex:<5}: {loaded:,} / {total:,} tickers ({pct:.1f}%)")

        # 2. DATA DEPTH (The "30-Year" Check)
        print("\n2️⃣  DATA DEPTH (Quality Check)")
        print("-" * 30)
        
        # We check a random sample of 1,000 active US stocks
        query = text("""
            SELECT 
                COUNT(*) as price_count,
                MIN(date) as start_date,
                MAX(date) as end_date
            FROM asset_prices 
            WHERE symbol IN (
                SELECT symbol FROM assets 
                WHERE exchange = 'US' 
                ORDER BY RANDOM() 
                LIMIT 1000
            )
            GROUP BY symbol
        """)
        
        df = pd.read_sql(query, session.bind)
        
        if not df.empty:
            # Metrics
            df['years'] = df['price_count'] / 252
            
            deep_history = len(df[df['years'] >= 20])
            mid_history = len(df[(df['years'] >= 10) & (df['years'] < 20)])
            new_listings = len(df[df['years'] < 5])
            
            print(f"   Based on a sample of {len(df):,} US stocks:")
            print(f"   🏆 Deep History (>20 yrs):  {deep_history} ({deep_history/len(df)*100:.1f}%)")
            print(f"   🥈 Mid History (10-20 yrs): {mid_history} ({mid_history/len(df)*100:.1f}%)")
            print(f"   👶 New Listings (<5 yrs):   {new_listings} ({new_listings/len(df)*100:.1f}%)")
            print(f"   📅 Avg Start Date:          {df['start_date'].min()}")
        else:
            print("   ❌ No price data found to analyze.")

        # 3. ZOMBIE CHECK
        print("\n3️⃣  ZOMBIE CHECK (Active vs Inactive)")
        print("-" * 30)
        active_cnt = session.query(Asset).filter_by(is_active=True).count()
        inactive_cnt = session.query(Asset).filter_by(is_active=False).count()
        print(f"   🟢 Active Assets:   {active_cnt:,}")
        print(f"   🔴 Inactive/Dead:   {inactive_cnt:,} (Failed downloads/Delisted)")

    print("\n" + "=" * 70)
    print("👨‍🏫 VERDICT:")
    if pct > 90:
        print("   PASS. You are ready to build the Optimization Engine.")
    else:
        print("   INCOMPLETE. Run 02a for another night.")

if __name__ == "__main__":
    run_audit()