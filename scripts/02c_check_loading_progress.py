# Script 02C: Check Loading Progress
# Shows what's been loaded and what remains

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_v6
from models_v6 import Asset, AssetPrice, get_session
from sqlalchemy import func, and_

def main():
    """Display loading progress statistics"""
    print("=" * 70)
    print("📊 DATABASE LOADING PROGRESS")
    print("=" * 70)
    print()
    
    engine = config_v6.get_postgres_engine()
    
    with get_session(engine) as session:
        # Total assets
        total_assets = session.query(Asset).filter_by(is_active=True).count()
        
        # Assets with data
        assets_with_data = session.query(
            func.count(func.distinct(AssetPrice.symbol))
        ).scalar() or 0
        
        # Never loaded
        never_loaded = total_assets - assets_with_data
        
        # Total price records
        total_prices = session.query(AssetPrice).count()
        
        # Coverage
        coverage = (assets_with_data / total_assets * 100) if total_assets > 0 else 0
        
        print(f"📈 Overall Statistics:")
        print(f"  Total assets in universe: {total_assets:,}")
        print(f"  Assets with data: {assets_with_data:,}")
        print(f"  Assets never loaded: {never_loaded:,}")
        print(f"  Coverage: {coverage:.1f}%")
        print(f"  Total price records: {total_prices:,}")
        print()
        
        # Breakdown by exchange
        print(f"📊 Coverage by Exchange:")
        print("  " + "-" * 66)
        print(f"  {'Exchange':<15} {'Total':<12} {'Loaded':<12} {'Remaining':<12} {'%':<8}")
        print("  " + "-" * 66)
        
        # Get all exchanges
        exchanges = session.query(Asset.exchange, func.count(Asset.symbol)).filter_by(
            is_active=True
        ).group_by(Asset.exchange).order_by(func.count(Asset.symbol).desc()).all()
        
        for exchange, count in exchanges:
            # Count loaded for this exchange
            loaded = session.query(
                func.count(func.distinct(AssetPrice.symbol))
            ).filter(
                AssetPrice.symbol.like(f'%.{exchange}')
            ).scalar() or 0
            
            remaining = count - loaded
            pct = (loaded / count * 100) if count > 0 else 0
            
            print(f"  {exchange:<15} {count:<12,} {loaded:<12,} {remaining:<12,} {pct:<7.1f}%")
        
        print("  " + "-" * 66)
        print()
        
        # Recent activity
        print(f"⏱️  Recent Loading Activity:")
        
        # Most recently loaded symbol
        latest = session.query(
            AssetPrice.symbol,
            func.max(AssetPrice.created_at)
        ).group_by(AssetPrice.symbol).order_by(
            func.max(AssetPrice.created_at).desc()
        ).first()
        
        if latest:
            print(f"  Last loaded: {latest[0]}")
            if latest[1]:
                print(f"  Time: {latest[1].strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Count loaded in last 24 hours
        yesterday = datetime.now() - timedelta(hours=24)
        recent_count = session.query(
            func.count(func.distinct(AssetPrice.symbol))
        ).filter(
            AssetPrice.created_at >= yesterday
        ).scalar() or 0
        
        print(f"  Loaded in last 24h: {recent_count:,} tickers")
        print()
        
        # Estimates
        if never_loaded > 0:
            BATCH_SIZE = 15000
            runs_needed = (never_loaded + BATCH_SIZE - 1) // BATCH_SIZE
            days_needed = runs_needed  # One run per day
            
            print(f"💡 Completion Estimates:")
            print(f"  Runs remaining: ~{runs_needed} (at {BATCH_SIZE:,}/run)")
            print(f"  Days to completion: ~{days_needed} days")
            print()
            
            print(f"🚀 Next Steps:")
            print(f"  Run: python scripts/02a_load_sample_historical.py")
            print(f"  Let it run overnight (~75 minutes)")
            print(f"  Repeat daily until complete")
        else:
            print(f"🎉 Database loading is COMPLETE!")
            print(f"  All {total_assets:,} assets have been loaded")
            print(f"  Total of {total_prices:,} price records")
        
        print()
        print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
