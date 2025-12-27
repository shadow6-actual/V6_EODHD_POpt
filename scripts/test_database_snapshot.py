# -*- coding: utf-8 -*-
"""
Created on Sat Dec 27 13:01:10 2025

@author: Wes
"""

# Test Database Snapshot Tool
# Captures detailed before/after state for refresh script validation

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models_v6 import Asset, AssetPrice
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import pandas as pd
from datetime import datetime
import json

# Test database connection (hardcoded)
TEST_DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'portfolio_master_test',
    'user': 'postgres',
    'password': 'Germany11',
}

TEST_PG_CONNECTION = (
    f"postgresql://{TEST_DB_CONFIG['user']}:{TEST_DB_CONFIG['password']}"
    f"@{TEST_DB_CONFIG['host']}:{TEST_DB_CONFIG['port']}/{TEST_DB_CONFIG['database']}"
)

@contextmanager
def get_session(engine):
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def capture_snapshot(output_dir: Path, snapshot_name: str = "before"):
    """Capture complete snapshot of test database state"""
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    
    engine = create_engine(TEST_PG_CONNECTION)
    
    print(f"\n{'='*70}")
    print(f"📸 CAPTURING SNAPSHOT: {snapshot_name.upper()}")
    print(f"{'='*70}\n")
    
    # ========================================================================
    # 1. SUMMARY STATISTICS
    # ========================================================================
    print("📊 Collecting summary statistics...")
    
    with get_session(engine) as session:
        # Overall counts
        total_assets = session.query(Asset).count()
        total_prices = session.query(AssetPrice).count()
        
        # Date range
        min_date = session.query(func.min(AssetPrice.date)).scalar()
        max_date = session.query(func.max(AssetPrice.date)).scalar()
        
        # Per-ticker price counts
        ticker_counts = session.query(
            AssetPrice.symbol,
            func.count(AssetPrice.price_id).label('price_count'),
            func.min(AssetPrice.date).label('first_date'),
            func.max(AssetPrice.date).label('last_date')
        ).group_by(AssetPrice.symbol).all()
        
        summary = {
            'snapshot_name': snapshot_name,
            'timestamp': datetime.now().isoformat(),
            'total_assets': total_assets,
            'total_price_records': total_prices,
            'date_range_start': str(min_date) if min_date else None,
            'date_range_end': str(max_date) if max_date else None,
            'avg_prices_per_ticker': total_prices / total_assets if total_assets > 0 else 0
        }
    
    # Save summary
    summary_file = output_dir / f"{snapshot_name}_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"  ✅ Summary saved: {summary_file.name}")
    
    # ========================================================================
    # 2. PER-TICKER PRICE COUNTS
    # ========================================================================
    print("📋 Collecting per-ticker price counts...")
    
    ticker_df = pd.DataFrame([
        {
            'symbol': row.symbol,
            'price_count': row.price_count,
            'first_date': row.first_date,
            'last_date': row.last_date,
            'days_coverage': (row.last_date - row.first_date).days if row.last_date and row.first_date else 0
        }
        for row in ticker_counts
    ])
    
    ticker_df = ticker_df.sort_values('symbol')
    
    # Save to CSV
    ticker_file = output_dir / f"{snapshot_name}_ticker_counts.csv"
    ticker_df.to_csv(ticker_file, index=False)
    print(f"  ✅ Ticker counts saved: {ticker_file.name} ({len(ticker_df)} tickers)")
    
    # ========================================================================
    # 3. FULL PRICE HISTORY (Sample Tickers)
    # ========================================================================
    print("📈 Capturing full price history for sample tickers...")
    
    # Select diverse sample: top 3 by price count from US, LSE, and one other
    sample_tickers = []
    
    with get_session(engine) as session:
        # US tickers
        us_tickers = session.query(AssetPrice.symbol, func.count(AssetPrice.price_id).label('cnt'))\
            .join(Asset, Asset.symbol == AssetPrice.symbol)\
            .filter(Asset.exchange == 'US')\
            .group_by(AssetPrice.symbol)\
            .order_by(func.count(AssetPrice.price_id).desc())\
            .limit(3).all()
        sample_tickers.extend([t[0] for t in us_tickers])
        
        # LSE tickers
        lse_tickers = session.query(AssetPrice.symbol, func.count(AssetPrice.price_id).label('cnt'))\
            .join(Asset, Asset.symbol == AssetPrice.symbol)\
            .filter(Asset.exchange == 'LSE')\
            .group_by(AssetPrice.symbol)\
            .order_by(func.count(AssetPrice.price_id).desc())\
            .limit(2).all()
        sample_tickers.extend([t[0] for t in lse_tickers])
        
        # One from any other exchange
        other_ticker = session.query(AssetPrice.symbol, func.count(AssetPrice.price_id).label('cnt'))\
            .join(Asset, Asset.symbol == AssetPrice.symbol)\
            .filter(Asset.exchange.notin_(['US', 'LSE']))\
            .group_by(AssetPrice.symbol)\
            .order_by(func.count(AssetPrice.price_id).desc())\
            .limit(1).all()
        if other_ticker:
            sample_tickers.append(other_ticker[0][0])
    
    # Capture full history for each sample ticker
    for ticker in sample_tickers:
        with get_session(engine) as session:
            prices = session.query(
                AssetPrice.date,
                AssetPrice.open,
                AssetPrice.high,
                AssetPrice.low,
                AssetPrice.close,
                AssetPrice.adjusted_close,
                AssetPrice.volume
            ).filter(
                AssetPrice.symbol == ticker
            ).order_by(AssetPrice.date).all()
            
            if prices:
                price_df = pd.DataFrame([
                    {
                        'date': p.date,
                        'open': p.open,
                        'high': p.high,
                        'low': p.low,
                        'close': p.close,
                        'adjusted_close': p.adjusted_close,
                        'volume': p.volume
                    }
                    for p in prices
                ])
                
                # Clean ticker symbol for filename (remove dots)
                clean_ticker = ticker.replace('.', '_')
                price_file = output_dir / f"{snapshot_name}_prices_{clean_ticker}.csv"
                price_df.to_csv(price_file, index=False)
                print(f"  ✅ {ticker}: {len(price_df)} records saved")
    
    # ========================================================================
    # 4. SUMMARY DISPLAY
    # ========================================================================
    print(f"\n{'='*70}")
    print(f"📊 SNAPSHOT SUMMARY: {snapshot_name.upper()}")
    print(f"{'='*70}")
    print(f"  Total Assets: {summary['total_assets']:,}")
    print(f"  Total Price Records: {summary['total_price_records']:,}")
    print(f"  Date Range: {summary['date_range_start']} to {summary['date_range_end']}")
    print(f"  Avg Prices/Ticker: {summary['avg_prices_per_ticker']:.0f}")
    print(f"\n  Files saved to: {output_dir}")
    print(f"  - {snapshot_name}_summary.json")
    print(f"  - {snapshot_name}_ticker_counts.csv")
    print(f"  - {snapshot_name}_prices_*.csv (sample tickers)")
    print(f"{'='*70}\n")
    
    engine.dispose()
    return summary


def compare_snapshots(output_dir: Path):
    """Compare before/after snapshots and generate diff report"""
    
    output_dir = Path(output_dir)
    
    print(f"\n{'='*70}")
    print(f"🔍 COMPARING SNAPSHOTS")
    print(f"{'='*70}\n")
    
    # Load summaries
    try:
        with open(output_dir / "before_summary.json") as f:
            before = json.load(f)
        with open(output_dir / "after_summary.json") as f:
            after = json.load(f)
    except FileNotFoundError as e:
        print(f"❌ Error: Missing snapshot file - {e}")
        return
    
    # Load ticker counts
    before_tickers = pd.read_csv(output_dir / "before_ticker_counts.csv")
    after_tickers = pd.read_csv(output_dir / "after_ticker_counts.csv")
    
    # ========================================================================
    # OVERALL COMPARISON
    # ========================================================================
    print("📊 OVERALL CHANGES:")
    print(f"  Total Price Records: {before['total_price_records']:,} → {after['total_price_records']:,} "
          f"({after['total_price_records'] - before['total_price_records']:+,})")
    print(f"  Date Range End: {before['date_range_end']} → {after['date_range_end']}")
    print()
    
    # ========================================================================
    # PER-TICKER CHANGES
    # ========================================================================
    print("📋 PER-TICKER CHANGES:")
    
    # Merge before/after
    comparison = before_tickers.merge(
        after_tickers,
        on='symbol',
        how='outer',
        suffixes=('_before', '_after')
    )
    
    # Calculate differences
    comparison['price_count_before'] = comparison['price_count_before'].fillna(0).astype(int)
    comparison['price_count_after'] = comparison['price_count_after'].fillna(0).astype(int)
    comparison['price_diff'] = comparison['price_count_after'] - comparison['price_count_before']
    
    # Show tickers with changes
    changed = comparison[comparison['price_diff'] != 0].sort_values('price_diff', ascending=False)
    
    if len(changed) > 0:
        print(f"\n  Tickers with changes: {len(changed)}")
        print(f"\n  Top 10 Updated Tickers:")
        print(f"  {'Symbol':<15} {'Before':>8} {'After':>8} {'Change':>8}")
        print(f"  {'-'*45}")
        for _, row in changed.head(10).iterrows():
            print(f"  {row['symbol']:<15} {row['price_count_before']:>8,} "
                  f"{row['price_count_after']:>8,} {row['price_diff']:>+8,}")
    else:
        print("  ⚠️  No changes detected")
    
    # Save comparison
    comparison_file = output_dir / "comparison.csv"
    comparison.to_csv(comparison_file, index=False)
    print(f"\n  ✅ Full comparison saved: {comparison_file.name}")
    
    # ========================================================================
    # SAMPLE TICKER DETAILED COMPARISON
    # ========================================================================
    print(f"\n📈 SAMPLE TICKER DETAILED COMPARISON:")
    
    # Find sample ticker files
    before_files = list(output_dir.glob("before_prices_*.csv"))
    
    for before_file in before_files:
        ticker_part = before_file.name.replace("before_prices_", "").replace(".csv", "")
        after_file = output_dir / f"after_prices_{ticker_part}.csv"
        
        if after_file.exists():
            before_prices = pd.read_csv(before_file)
            after_prices = pd.read_csv(after_file)
            
            # Convert back to ticker symbol
            ticker = ticker_part.replace('_', '.')
            
            print(f"\n  {ticker}:")
            print(f"    Records: {len(before_prices)} → {len(after_prices)} ({len(after_prices) - len(before_prices):+})")
            print(f"    Date Range: {before_prices['date'].min()} to {before_prices['date'].max()}")
            print(f"             → {after_prices['date'].min()} to {after_prices['date'].max()}")
            
            # Check for new dates
            before_dates = set(before_prices['date'])
            after_dates = set(after_prices['date'])
            new_dates = after_dates - before_dates
            
            if new_dates:
                print(f"    New dates added: {len(new_dates)}")
                sorted_new = sorted(list(new_dates))
                if len(sorted_new) <= 5:
                    print(f"      {', '.join(sorted_new)}")
                else:
                    print(f"      {sorted_new[0]} ... {sorted_new[-1]}")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Capture test database snapshots')
    parser.add_argument('action', choices=['before', 'after', 'compare'],
                       help='Action to perform')
    parser.add_argument('--output-dir', default='./test_snapshots',
                       help='Directory to save snapshots (default: ./test_snapshots)')
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    
    if args.action == 'before':
        capture_snapshot(output_dir, 'before')
    elif args.action == 'after':
        capture_snapshot(output_dir, 'after')
    elif args.action == 'compare':
        compare_snapshots(output_dir)