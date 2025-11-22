# Script 02B: Data Refresh & Update System
# Updates existing tickers with latest data
# Handles: stale data, missing recent dates, data gaps

import sys
import time
import logging
import requests
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_v6
from models_v6 import Asset, AssetPrice, UpdateLog, get_session
from eodhd_client import EODHDClient
from sqlalchemy import func, and_, or_, text

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config_v6.LOGS_DIR / "refresh_historical_data.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Update modes
UPDATE_MODE_STALE = 'stale'          # Assets not updated in X days
UPDATE_MODE_RECENT = 'recent'        # Just add last few days of data
UPDATE_MODE_GAPS = 'gaps'            # Fill missing date ranges
UPDATE_MODE_ALL = 'all'              # Update everything

# Batch sizes
BATCH_SIZE_STALE = 5000      # For stale data updates
BATCH_SIZE_RECENT = 10000    # For recent updates (faster)
BATCH_SIZE_GAPS = 2000       # For gap filling (slower)

# Thresholds
STALE_DATA_DAYS = 7          # Data is "stale" if not updated in 7 days
RECENT_DAYS_TO_UPDATE = 30   # When doing recent update, get last 30 days

API_RATE_LIMIT_DELAY = 0.3   # Seconds between API calls


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_ticker_historical_data(client: EODHDClient, symbol: str, from_date: str, to_date: str):
    """
    Get historical data for a single ticker using EODHD API
    
    Workaround for missing get_eod_data method - uses direct API call
    
    Args:
        client: EODHD API client
        symbol: Ticker symbol (e.g., 'AAPL.US')
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        
    Returns:
        List of price data dicts or None if error
    """
    try:
        url = f"{config_v6.EODHD_BASE_URL}/eod/{symbol}"
        params = {
            'api_token': client.api_token,
            'from': from_date,
            'to': to_date,
            'fmt': 'json'
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 402:
            logger.debug(f"402 error for {symbol} - may be subscription issue")
            return None
        else:
            logger.debug(f"API returned {response.status_code} for {symbol}")
            return None
            
    except Exception as e:
        logger.debug(f"Error fetching {symbol}: {e}")
        return None


def get_refresh_statistics(engine) -> dict:
    """
    Get statistics about data freshness
    
    Returns:
        dict with refresh statistics
    """
    with get_session(engine) as session:
        # Total assets with data
        total_with_data = session.query(
            func.count(func.distinct(AssetPrice.symbol))
        ).scalar() or 0
        
        # Get today's date
        today = date.today()
        stale_cutoff = today - timedelta(days=STALE_DATA_DAYS)
        
        # Assets with stale data (most recent price is old)
        stale_assets_query = session.query(
            AssetPrice.symbol,
            func.max(AssetPrice.date).label('latest_date')
        ).group_by(AssetPrice.symbol).having(
            func.max(AssetPrice.date) < stale_cutoff
        )
        
        stale_count = stale_assets_query.count()
        
        # Assets current (updated within last 7 days)
        current_count = total_with_data - stale_count
        
        # Average staleness
        avg_days_old = session.query(
            func.avg(func.julianday(today) - func.julianday(func.max(AssetPrice.date)))
        ).scalar() or 0
        
        return {
            'total_assets_with_data': total_with_data,
            'current_assets': current_count,
            'stale_assets': stale_count,
            'avg_days_old': avg_days_old,
            'stale_cutoff_date': stale_cutoff
        }


def get_stale_assets(engine, limit: int = BATCH_SIZE_STALE) -> List[Tuple[str, date]]:
    """
    Get assets with stale data (not updated recently)
    
    Args:
        engine: Database engine
        limit: Maximum number to return
        
    Returns:
        List of (symbol, latest_date) tuples
    """
    with get_session(engine) as session:
        stale_cutoff = date.today() - timedelta(days=STALE_DATA_DAYS)
        
        # Get symbols with their latest date
        stale_assets = session.query(
            AssetPrice.symbol,
            func.max(AssetPrice.date).label('latest_date')
        ).group_by(
            AssetPrice.symbol
        ).having(
            func.max(AssetPrice.date) < stale_cutoff
        ).order_by(
            func.max(AssetPrice.date).asc()  # Oldest first
        ).limit(limit).all()
        
        return [(symbol, latest_date) for symbol, latest_date in stale_assets]


def get_assets_for_recent_update(engine, limit: int = BATCH_SIZE_RECENT) -> List[Tuple[str, date]]:
    """
    Get assets for recent update (adding last few days)
    
    Args:
        engine: Database engine
        limit: Maximum number to return
        
    Returns:
        List of (symbol, latest_date) tuples
    """
    with get_session(engine) as session:
        recent_cutoff = date.today() - timedelta(days=3)
        
        # Get symbols that are close to current but not quite
        assets = session.query(
            AssetPrice.symbol,
            func.max(AssetPrice.date).label('latest_date')
        ).group_by(
            AssetPrice.symbol
        ).having(
            and_(
                func.max(AssetPrice.date) >= recent_cutoff - timedelta(days=7),
                func.max(AssetPrice.date) < recent_cutoff
            )
        ).order_by(
            func.max(AssetPrice.date).asc()
        ).limit(limit).all()
        
        return [(symbol, latest_date) for symbol, latest_date in assets]


def update_ticker_data(client: EODHDClient, engine, symbol: str, from_date: date, 
                       to_date: Optional[date] = None) -> Tuple[int, bool]:
    """
    Update historical data for a single ticker from a specific date
    
    Args:
        client: EODHD API client
        engine: Database engine
        symbol: Ticker symbol
        from_date: Start date for update
        to_date: End date (default: today)
        
    Returns:
        tuple: (records_inserted, success)
    """
    if to_date is None:
        to_date = date.today()
    
    try:
        # Get data from API using helper function
        data = get_ticker_historical_data(
            client=client,
            symbol=symbol,
            from_date=from_date.strftime('%Y-%m-%d'),
            to_date=to_date.strftime('%Y-%m-%d')
        )
        
        if not data:
            return 0, False
        
        # Insert into database
        with get_session(engine) as session:
            records_inserted = 0
            
            for item in data:
                try:
                    # Parse date
                    price_date = datetime.strptime(item.get('date'), '%Y-%m-%d').date()
                    
                    # Skip if before from_date (shouldn't happen but be safe)
                    if price_date < from_date:
                        continue
                    
                    # Check if already exists
                    existing = session.query(AssetPrice).filter_by(
                        symbol=symbol,
                        date=price_date
                    ).first()
                    
                    if existing:
                        # Update existing record
                        existing.open = item.get('open')
                        existing.high = item.get('high')
                        existing.low = item.get('low')
                        existing.close = item.get('close')
                        existing.adjusted_close = item.get('adjusted_close')
                        existing.volume = item.get('volume')
                        existing.last_updated = datetime.utcnow()
                    else:
                        # Create new record
                        price = AssetPrice(
                            symbol=symbol,
                            date=price_date,
                            open=item.get('open'),
                            high=item.get('high'),
                            low=item.get('low'),
                            close=item.get('close'),
                            adjusted_close=item.get('adjusted_close'),
                            volume=item.get('volume'),
                            data_source='EODHD',
                            is_validated=True
                        )
                        session.add(price)
                        records_inserted += 1
                    
                    # Commit in batches
                    if records_inserted % 500 == 0:
                        session.commit()
                        
                except Exception as e:
                    logger.debug(f"  Error processing record: {e}")
                    continue
            
            # Final commit
            session.commit()
            
            return records_inserted, True
            
    except Exception as e:
        logger.error(f"  ❌ Error updating {symbol}: {e}")
        return 0, False


def process_stale_data_batch(client: EODHDClient, engine, batch_size: int) -> dict:
    """
    Process a batch of stale data updates
    
    Args:
        client: EODHD API client
        engine: Database engine
        batch_size: Number of assets to update
        
    Returns:
        dict with statistics
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"🔄 UPDATING STALE DATA")
    logger.info(f"{'='*70}\n")
    
    # Get stale assets
    stale_assets = get_stale_assets(engine, batch_size)
    
    if not stale_assets:
        logger.info("✅ No stale assets found - all data is current!")
        return {
            'total_attempted': 0,
            'successful': 0,
            'failed': 0,
            'total_records': 0,
            'duration_seconds': 0
        }
    
    logger.info(f"Found {len(stale_assets):,} stale assets to update")
    logger.info("")
    
    stats = {
        'total_attempted': len(stale_assets),
        'successful': 0,
        'failed': 0,
        'total_records': 0,
        'start_time': time.time()
    }
    
    for i, (symbol, latest_date) in enumerate(stale_assets, 1):
        # Progress indicator
        if i % 100 == 0 or i == 1:
            elapsed = time.time() - stats['start_time']
            rate = i / elapsed if elapsed > 0 else 0
            eta_seconds = (len(stale_assets) - i) / rate if rate > 0 else 0
            eta_minutes = eta_seconds / 60
            
            logger.info(f"\n[{i:,}/{len(stale_assets):,}] Progress: {i/len(stale_assets)*100:.1f}%")
            logger.info(f"  Rate: {rate:.1f} tickers/sec")
            logger.info(f"  ETA: {eta_minutes:.1f} minutes")
            logger.info(f"  Success: {stats['successful']:,} | Failed: {stats['failed']:,}")
        
        # Calculate date range to update
        from_date = latest_date + timedelta(days=1)  # Day after latest
        days_behind = (date.today() - latest_date).days
        
        logger.info(f"\n[{i}] {symbol}")
        logger.info(f"  Latest date: {latest_date} ({days_behind} days behind)")
        
        # Update the ticker
        records, success = update_ticker_data(client, engine, symbol, from_date)
        
        if success:
            stats['successful'] += 1
            stats['total_records'] += records
            logger.info(f"  ✅ Added {records:,} new price records")
        else:
            stats['failed'] += 1
            logger.info(f"  ⚠️  Update failed")
        
        # Rate limiting
        time.sleep(API_RATE_LIMIT_DELAY)
    
    stats['end_time'] = time.time()
    stats['duration_seconds'] = stats['end_time'] - stats['start_time']
    stats['duration_minutes'] = stats['duration_seconds'] / 60
    
    return stats


def process_recent_update_batch(client: EODHDClient, engine, batch_size: int) -> dict:
    """
    Quick update for assets that are close to current
    
    Args:
        client: EODHD API client
        engine: Database engine
        batch_size: Number of assets to update
        
    Returns:
        dict with statistics
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"⚡ QUICK RECENT UPDATE")
    logger.info(f"{'='*70}\n")
    
    assets = get_assets_for_recent_update(engine, batch_size)
    
    if not assets:
        logger.info("✅ All assets are up to date!")
        return {
            'total_attempted': 0,
            'successful': 0,
            'failed': 0,
            'total_records': 0,
            'duration_seconds': 0
        }
    
    logger.info(f"Found {len(assets):,} assets for recent update")
    logger.info("")
    
    stats = {
        'total_attempted': len(assets),
        'successful': 0,
        'failed': 0,
        'total_records': 0,
        'start_time': time.time()
    }
    
    for i, (symbol, latest_date) in enumerate(assets, 1):
        if i % 500 == 0 or i == 1:
            elapsed = time.time() - stats['start_time']
            rate = i / elapsed if elapsed > 0 else 0
            logger.info(f"[{i:,}/{len(assets):,}] Rate: {rate:.1f}/sec | Success: {stats['successful']:,}")
        
        # Update from day after latest
        from_date = latest_date + timedelta(days=1)
        
        records, success = update_ticker_data(client, engine, symbol, from_date)
        
        if success:
            stats['successful'] += 1
            stats['total_records'] += records
        else:
            stats['failed'] += 1
        
        time.sleep(API_RATE_LIMIT_DELAY)
    
    stats['end_time'] = time.time()
    stats['duration_seconds'] = stats['end_time'] - stats['start_time']
    stats['duration_minutes'] = stats['duration_seconds'] / 60
    
    return stats


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function for data refresh"""
    logger.info("=" * 70)
    logger.info("DATA REFRESH & UPDATE SYSTEM")
    logger.info("=" * 70)
    logger.info("")
    
    # Initialize
    try:
        client = EODHDClient(config_v6.EODHD_API_TOKEN)
        engine = config_v6.get_postgres_engine()
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        return
    
    # Get current statistics
    logger.info("📊 Data Freshness Statistics:")
    logger.info("=" * 70)
    stats = get_refresh_statistics(engine)
    logger.info(f"  Total assets with data: {stats['total_assets_with_data']:,}")
    logger.info(f"  Current (within {STALE_DATA_DAYS} days): {stats['current_assets']:,}")
    logger.info(f"  Stale (needs update): {stats['stale_assets']:,}")
    logger.info(f"  Average age: {stats['avg_days_old']:.1f} days")
    logger.info(f"  Stale cutoff: {stats['stale_cutoff_date']}")
    logger.info("")
    
    # Check if updates needed
    if stats['stale_assets'] == 0:
        logger.info("🎉 All data is current! Nothing to update.")
        logger.info("")
        logger.info("💡 You can:")
        logger.info("   - Run this script daily/weekly to keep data fresh")
        logger.info("   - Use it after market hours to get latest prices")
        return
    
    # Choose update mode
    logger.info("🔧 Update Modes Available:")
    logger.info("=" * 70)
    logger.info(f"  1. STALE UPDATE - Update {min(stats['stale_assets'], BATCH_SIZE_STALE):,} oldest assets")
    logger.info(f"  2. RECENT UPDATE - Quick update for {BATCH_SIZE_RECENT:,} near-current assets")
    logger.info(f"  3. BOTH - Do stale update then recent update")
    logger.info("")
    
    choice = input("Select mode (1, 2, or 3) or press Enter for default [1]: ").strip()
    if not choice:
        choice = "1"
    
    # Estimate runtime
    if choice == "1":
        batch_size = min(stats['stale_assets'], BATCH_SIZE_STALE)
        estimated_minutes = (batch_size * API_RATE_LIMIT_DELAY) / 60
    elif choice == "2":
        batch_size = BATCH_SIZE_RECENT
        estimated_minutes = (batch_size * API_RATE_LIMIT_DELAY) / 60
    else:  # Both
        batch_size = min(stats['stale_assets'], BATCH_SIZE_STALE) + BATCH_SIZE_RECENT
        estimated_minutes = (batch_size * API_RATE_LIMIT_DELAY) / 60
    
    logger.info(f"⏱️  Estimated runtime: {estimated_minutes:.1f} minutes")
    logger.info(f"⚡ API calls: ~{batch_size:,}")
    logger.info("")
    
    response = input("Press Enter to begin (or 'q' to quit): ")
    if response.lower() == 'q':
        logger.info("Cancelled by user")
        return
    
    # Execute updates
    if choice in ["1", "3"]:
        result_stats = process_stale_data_batch(client, engine, BATCH_SIZE_STALE)
        
        # Log to database
        if result_stats['total_attempted'] > 0:
            with get_session(engine) as session:
                log_entry = UpdateLog(
                    update_type='stale_data_refresh',
                    status='success',
                    message=f"Updated {result_stats['successful']:,}/{result_stats['total_attempted']:,} stale assets",
                    api_calls_made=result_stats['total_attempted'],
                    rows_affected=result_stats['total_records'],
                    duration_seconds=result_stats['duration_seconds']
                )
                session.add(log_entry)
                session.commit()
    
    if choice in ["2", "3"]:
        result_stats = process_recent_update_batch(client, engine, BATCH_SIZE_RECENT)
        
        # Log to database
        if result_stats['total_attempted'] > 0:
            with get_session(engine) as session:
                log_entry = UpdateLog(
                    update_type='recent_data_refresh',
                    status='success',
                    message=f"Updated {result_stats['successful']:,}/{result_stats['total_attempted']:,} recent assets",
                    api_calls_made=result_stats['total_attempted'],
                    rows_affected=result_stats['total_records'],
                    duration_seconds=result_stats['duration_seconds']
                )
                session.add(log_entry)
                session.commit()
    
    # Final summary
    logger.info("\n" + "=" * 70)
    logger.info("🎉 DATA REFRESH COMPLETE")
    logger.info("=" * 70)
    
    # Get updated statistics
    updated_stats = get_refresh_statistics(engine)
    logger.info(f"  Current assets: {updated_stats['current_assets']:,}")
    logger.info(f"  Stale assets remaining: {updated_stats['stale_assets']:,}")
    logger.info(f"  Average age: {updated_stats['avg_days_old']:.1f} days")
    logger.info(f"  🔌 API calls used: {client.calls_today:,}")
    logger.info("")
    
    if updated_stats['stale_assets'] > 0:
        logger.info(f"💡 {updated_stats['stale_assets']:,} assets still need updates")
        logger.info(f"   Run again to continue updating")
    else:
        logger.info(f"🎉 All data is now current!")
    
    logger.info("")


if __name__ == "__main__":
    try:
        start_time = time.time()
        main()
        elapsed = time.time() - start_time
        logger.info(f"Total execution time: {elapsed/60:.1f} minutes")
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Process cancelled by user")
        logger.info("   Progress has been saved.")
    except Exception as e:
        logger.error(f"\n\n❌ Process failed: {e}")
        import traceback
        traceback.print_exc()
