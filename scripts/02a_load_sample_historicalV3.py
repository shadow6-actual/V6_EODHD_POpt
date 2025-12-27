# Script 02A: Smart Batch Historical Data Loader
# Loads 5,000 tickers per run with intelligent prioritization
# Fully resumable - tracks what's been loaded in database

import sys
import time
import logging
import requests
from pathlib import Path
from datetime import datetime, timedelta
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
        logging.FileHandler(config_v6.LOGS_DIR / "load_batch_historical.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

MAX_BATCH_SIZE = 15000  # Maximum tickers per run
HISTORICAL_START_DATE = "1995-01-01"  # Start from 1995 (30 years)
API_RATE_LIMIT_DELAY = 0.3  # Seconds between API calls (0.3 = very aggressive, ~75 min runtime)

# Exchange priority (higher = load first)
EXCHANGE_PRIORITY = {
    'US': 100,      # U.S. consolidated
    'LSE': 90,      # London
    'XETRA': 85,    # Germany
    'TO': 80,       # Toronto
    'HK': 75,       # Hong Kong
    # 'JPX': 70,    # Removed - not a valid EODHD exchange code
    'PA': 60,       # Paris
    'AS': 55,       # Amsterdam
    'SW': 50,       # Switzerland
    'KO': 48,       # Korea Exchange (KRX)
    'KQ': 46,       # KOSDAQ
    'TW': 44,       # Taiwan (TWSE)
    'TWO': 42,      # Taiwan OTC
    'AU': 40,       # Australia
    # All others default to priority 10 (handled downstream)
}


# Asset type priority
ASSET_TYPE_PRIORITY = {
    'Common Stock': 100,
    'ETF': 95,
    'Preferred Stock': 80,
    'FUND': 75,
    'Index': 70,
    'REIT': 65,
    'Closed-End Fund': 60,
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_ticker_historical_data(client: EODHDClient, symbol: str, from_date: str, to_date: str):
    """
    Get historical data for a single ticker using EODHD API.

    Args:
        client: EODHD API client
        symbol: Ticker symbol (e.g. 'AAPL.US')
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)

    Returns:
        Tuple[List[dict] | None, str] where str is one of:
          'ok'          -> data list is non-empty
          'no_data'     -> call succeeded but returned empty
          'paywall'     -> 402 subscription issue
          'not_found'   -> 404 or symbol missing
          'error'       -> other HTTP errors/exceptions
    """
    try:
        url = f"{config_v6.EODHD_BASE_URL}/eod/{symbol}"
        params = {
            'api_token': client.api_token,
            'from': from_date,
            'to': to_date,
            'fmt': 'json',
            'period': 'd'   # <--- ADD THIS FORCE DAILY DATA
        }

        response = requests.get(url, params=params, timeout=30)
        # Count the API call
        try:
            client.calls_today += 1
        except Exception:
            pass

        if response.status_code == 200:
            try:
                data = response.json()
            except Exception:
                return None, 'error'
            # EODHD returns [] when symbol exists but has no EOD data in range or at all
            if isinstance(data, list) and len(data) > 0:
                return data, 'ok'
            else:
                return None, 'no_data'
        elif response.status_code == 402:
            # Subscription/plan issue for this instrument/exchange
            return None, 'paywall'
        elif response.status_code == 404:
            return None, 'not_found'
        else:
            return None, 'error'

    except requests.Timeout:
        return None, 'error'
    except Exception:
        return None, 'error'



def get_loading_statistics(engine) -> dict:
    """
    Get current loading statistics from database
    
    Returns:
        dict with loading stats
    """
    with get_session(engine) as session:
        # Total assets in universe
        total_assets = session.query(Asset).filter_by(is_active=True).count()
        
        # Assets with any price data (subquery for performance)
        assets_with_data = session.query(
            func.count(func.distinct(AssetPrice.symbol))
        ).scalar() or 0
        
        # Assets never loaded
        never_loaded = total_assets - assets_with_data
        
        # Total price records
        total_prices = session.query(AssetPrice).count()
        
        return {
            'total_assets': total_assets,
            'assets_with_data': assets_with_data,
            'assets_never_loaded': never_loaded,
            'total_price_records': total_prices,
            'percent_loaded': (assets_with_data / total_assets * 100) if total_assets > 0 else 0
        }


def calculate_asset_priority(asset: Asset) -> int:
    """
    Calculate priority score for loading an asset
    Higher score = load sooner
    
    Args:
        asset: Asset object
        
    Returns:
        Priority score (0-200)
    """
    score = 0
    
    # Exchange priority
    score += EXCHANGE_PRIORITY.get(asset.exchange, 10)
    
    # Asset type priority
    score += ASSET_TYPE_PRIORITY.get(asset.asset_type, 10)
    
    return score

def get_next_batch_to_load(engine, batch_size: int = MAX_BATCH_SIZE) -> List[dict]:
    """
    Get next batch of tickers to load, intelligently prioritized
    
    Strategy:
    1. Never loaded assets first (prioritized by exchange/type)
    2. Partially loaded assets (missing recent data)
    3. Old data (not updated in 90+ days)
    
    Args:
        engine: Database engine
        batch_size: Number of assets to return
        
    Returns:
        List of dicts with asset info (avoids SQLAlchemy session issues)
    """
    with get_session(engine) as session:
        logger.info(f"🔍 Finding next {batch_size:,} tickers to load...")
        
        # Subquery: Get all symbols that have ANY price data
        symbols_with_data_subq = session.query(
            AssetPrice.symbol.distinct()
        ).subquery()
        
        # Query 1: Never loaded assets (prioritized)
        never_loaded = session.query(Asset).filter(
            and_(
                Asset.is_active == True,
                ~Asset.symbol.in_(session.query(symbols_with_data_subq))
            )
        ).all()
        
        # Calculate priority for never-loaded assets
        never_loaded_prioritized = sorted(
            never_loaded,
            key=lambda a: calculate_asset_priority(a),
            reverse=True
        )
        
        logger.info(f"  Found {len(never_loaded_prioritized):,} never-loaded assets")
        
        # If we have enough never-loaded, return those
        if len(never_loaded_prioritized) >= batch_size:
            logger.info(f"  ✅ Returning {batch_size:,} highest-priority never-loaded assets")
            # Convert to dicts to avoid SQLAlchemy session detachment
            return [
                {
                    'symbol': a.symbol,
                    'code': a.code,
                    'exchange': a.exchange,
                    'asset_type': a.asset_type,
                    'name': a.name
                }
                for a in never_loaded_prioritized[:batch_size]
            ]
        
        # Otherwise, add partially loaded or old data
        batch = never_loaded_prioritized.copy()
        remaining_needed = batch_size - len(batch)
        
        logger.info(f"  Need {remaining_needed:,} more assets...")
        
        # Query 2: Assets with old data (not updated in 90 days)
        cutoff_date = datetime.now() - timedelta(days=90)
        
        old_data_assets = session.query(Asset).join(
            AssetPrice, Asset.symbol == AssetPrice.symbol
        ).filter(
            and_(
                Asset.is_active == True,
                Asset.symbol.notin_([a.symbol for a in batch])  # Exclude already selected
            )
        ).group_by(Asset.id).having(
            func.max(AssetPrice.date) < cutoff_date.date()
        ).limit(remaining_needed).all()
        
        logger.info(f"  Found {len(old_data_assets):,} assets with old data")
        batch.extend(old_data_assets)
        
        logger.info(f"  ✅ Selected {len(batch):,} total assets for this batch")
        
        # Convert to dicts to avoid SQLAlchemy session detachment
        batch_dicts = [
            {
                'symbol': a.symbol,
                'code': a.code,
                'exchange': a.exchange,
                'asset_type': a.asset_type,
                'name': a.name
            }
            for a in batch
        ]
        
        return batch_dicts


def load_ticker_historical_data(client: EODHDClient, engine, asset: dict) -> Tuple[int, bool]:
    """
    Load historical price data for a single ticker
    
    Args:
        client: EODHD API client
        engine: Database engine
        asset: Asset dict with 'symbol', 'code', 'exchange', etc.
        
    Returns:
        Tuple of (records_inserted, success_flag)
    """
    try:
        symbol = asset['symbol']
        
        # Use the helper function to get data
        data, status = get_ticker_historical_data(
            client, 
            symbol, 
            HISTORICAL_START_DATE,
            datetime.utcnow().strftime("%Y-%m-%d")
        )
        
        # Handle different status codes
        if status == 'ok' and data:
            # Insert data into database
            with get_session(engine) as session:
                records_inserted = 0
                
                for record in data:
                    try:
                        price_date = datetime.strptime(record.get('date'), '%Y-%m-%d').date()
                        
                        # Check if price already exists
                        existing = session.query(AssetPrice).filter_by(
                            symbol=symbol,
                            date=price_date
                        ).first()
                        
                        if not existing:
                            price = AssetPrice(
                                symbol=symbol,
                                date=price_date,
                                open=record.get('open'),
                                high=record.get('high'),
                                low=record.get('low'),
                                close=record.get('close'),
                                adjusted_close=record.get('adjusted_close'),
                                volume=record.get('volume'),
                                data_source='EODHD',
                                is_validated=True
                            )
                            session.add(price)
                            records_inserted += 1
                        
                        # Commit in batches
                        if records_inserted % 500 == 0:
                            session.commit()
                            
                    except Exception as e:
                        logger.debug(f"  Error processing record for {symbol}: {e}")
                        continue
                
                # Final commit
                session.commit()
                
                # Update asset last_updated timestamp
                asset_obj = session.query(Asset).filter_by(symbol=symbol).first()
                if asset_obj:
                    asset_obj.last_updated = datetime.utcnow()
                    session.commit()
                
                return records_inserted, True
        
        elif status == 'no_data':
            # No data available from EODHD
            return 0, False
        
        elif status == 'paywall':
            # Subscription tier issue
            logger.debug(f"  {symbol}: Requires subscription upgrade (402)")
            return 0, False
        
        elif status == 'not_found':
            # Symbol doesn't exist on EODHD
            logger.debug(f"  {symbol}: Not found on EODHD (404)")
            return 0, False
        
        else:
            # Generic error
            return 0, False
            
    except Exception as e:
        logger.error(f"  ❌ Error loading {asset.get('symbol', 'UNKNOWN')}: {e}")
        return 0, False


def process_batch(client: EODHDClient, engine, batch: List[dict]) -> dict:
    """
    Process a batch of assets
    
    Args:
        client: EODHD API client
        engine: Database engine
        batch: List of asset dicts to load
        
    Returns:
        dict with statistics
    """
    stats = {
        'total_attempted': len(batch),
        'successful': 0,
        'failed': 0,
        'total_records': 0,
        'start_time': time.time()
    }
    
    logger.info(f"\n{'='*70}")
    logger.info(f"🚀 PROCESSING BATCH OF {len(batch):,} TICKERS")
    logger.info(f"{'='*70}\n")
    
    for i, asset in enumerate(batch, 1):
        # Progress indicator
        if i % 100 == 0 or i == 1:
            elapsed = time.time() - stats['start_time']
            rate = i / elapsed if elapsed > 0 else 0
            eta_seconds = (len(batch) - i) / rate if rate > 0 else 0
            eta_minutes = eta_seconds / 60
            
            logger.info(f"\n[{i:,}/{len(batch):,}] Progress: {i/len(batch)*100:.1f}%")
            logger.info(f"  Rate: {rate:.1f} tickers/sec")
            logger.info(f"  ETA: {eta_minutes:.1f} minutes")
            logger.info(f"  Success: {stats['successful']:,} | Failed: {stats['failed']:,}")
            logger.info(f"  API calls: {client.calls_today:,}")
        
        # Load the ticker
        logger.info(f"\n[{i}] {asset['symbol']} ({asset['exchange']} - {asset['asset_type']})")
        
        # PRE-VALIDATION: Skip obviously invalid symbols before API call
        symbol_code = asset['code']
        exchange = asset['exchange']
        
        # Check for common cross-listing errors (US tickers on wrong exchanges)
        common_us_tickers = {'AAPL','MSFT','AMZN','GOOGL','GOOG','META','TSLA','NVDA','AMD',
                           'NFLX','DIS','PYPL','INTC','CSCO','ADBE','CRM','ORCL','IBM',
                           'QCOM','TXN','AVGO','SBUX','BA','COST','PEP','KO','MCD','WMT',
                           'HD','UNH','JNJ','PFE','ABBV','LLY','MRK','TMO','CVX','XOM',
                           'BRKB','V','MA','JPM','BAC','WFC','GS','MS','C','AXP',
                           'SPY','QQQ','DIA','IWM','VTI','VOO','IVV'}
        
        invalid_combos = [
            # US mega-caps that should never be on these exchanges
            (exchange in ['TO','V','CN','MX','PA','AS','BR','LSE','XETRA','HK','TW','AU','SG'], 
             symbol_code in common_us_tickers),
            # Very short codes (1-2 chars) often problematic outside major exchanges
            (exchange not in ['US','HK','AU','LSE','XETRA'], len(symbol_code) <= 2),
        ]
        
        if any(combo[0] and combo[1] for combo in invalid_combos):
            logger.info(f"  ⏭️  SKIPPED - Likely invalid cross-listing")
            logger.info(f"     (US ticker '{symbol_code}' should not exist on {exchange})")
            stats['failed'] += 1
            
            # Mark this asset as invalid in database so we don't retry
            with get_session(engine) as mark_session:
                try:
                    invalid_asset = mark_session.query(Asset).filter_by(symbol=asset['symbol']).first()
                    if invalid_asset:
                        invalid_asset.is_active = False
                        mark_session.commit()
                        logger.info(f"     (Marked as inactive in database)")
                except Exception as e:
                    logger.debug(f"Could not mark asset inactive: {e}")
            
            continue  # Skip to next ticker

        # Proceed with API call - CORRECT FUNCTION SIGNATURE
        records, success = load_ticker_historical_data(client, engine, asset)

        if success and records > 0:
            stats['successful'] += 1
            stats['total_records'] += records
            logger.info(f"  ✅ Loaded {records:,} price records")
        else:
            stats['failed'] += 1
            
            # Check WHY it failed
            data, status = get_ticker_historical_data(
                client,
                asset['symbol'],
                HISTORICAL_START_DATE,
                datetime.utcnow().strftime("%Y-%m-%d")
            )
            
            # ONLY mark inactive if it's truly gone (404) or empty (no_data)
            # Do NOT mark inactive for 'error' (timeouts) or 'paywall'
            if status in ['not_found', 'no_data']:
                logger.info(f"     (Marking {asset['symbol']} as inactive - Reason: {status})")
                with get_session(engine) as mark_session:
                    try:
                        failed_asset = mark_session.query(Asset).filter_by(symbol=asset['symbol']).first()
                        if failed_asset:
                            failed_asset.is_active = False
                            mark_session.commit()
                    except Exception as e:
                        logger.debug(f"Could not mark asset inactive: {e}")
                    except Exception as e:
                        logger.debug(f"Could not mark asset inactive: {e}")

        # Rate limiting
        time.sleep(API_RATE_LIMIT_DELAY)
    
    stats['end_time'] = time.time()
    stats['duration_seconds'] = stats['end_time'] - stats['start_time']
    stats['duration_minutes'] = stats['duration_seconds'] / 60
    
    return stats


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function to load batch of historical data"""
    logger.info("=" * 70)
    logger.info("SMART BATCH HISTORICAL DATA LOADER")
    logger.info(f"Max Batch Size: {MAX_BATCH_SIZE:,} tickers")
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
    logger.info("📊 Current Database Statistics:")
    logger.info("=" * 70)
    stats = get_loading_statistics(engine)
    logger.info(f"  Total assets in universe: {stats['total_assets']:,}")
    logger.info(f"  Assets with data: {stats['assets_with_data']:,}")
    logger.info(f"  Assets never loaded: {stats['assets_never_loaded']:,}")
    logger.info(f"  Total price records: {stats['total_price_records']:,}")
    logger.info(f"  Coverage: {stats['percent_loaded']:.1f}%")
    logger.info("")
    
    # Check if we're done
    if stats['assets_never_loaded'] == 0:
        logger.info("🎉 All assets have been loaded!")
        logger.info("   Run script 02b to refresh old data")
        return
    
    # Get next batch
    # Calculate dynamic batch size
    remaining = stats['assets_never_loaded']
    batch_size = min(remaining, MAX_BATCH_SIZE) if remaining > 0 else 0
    remaining = stats['assets_never_loaded']
    batch_size = min(remaining, MAX_BATCH_SIZE) if remaining > 0 else MAX_BATCH_SIZE
    batch = get_next_batch_to_load(engine, batch_size)
    
    if not batch:
        logger.warning("⚠️  No assets found to load")
        return
    
    # Show batch summary
    logger.info(f"\n📋 Batch Summary:")
    logger.info("=" * 70)
    
    # Count by exchange
    from collections import Counter
    exchange_counts = Counter(a['exchange'] for a in batch)
    for exchange, count in sorted(exchange_counts.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {exchange}: {count:,} tickers")
    
    logger.info("")
    
    # Estimate runtime
    estimated_minutes = (len(batch) * API_RATE_LIMIT_DELAY) / 60
    logger.info(f"⏱️  Estimated runtime: {estimated_minutes:.1f} minutes ({estimated_minutes/60:.1f} hours)")
    logger.info(f"⚡ API calls: ~{len(batch):,} (under {client.max_calls_per_day:,} daily limit)")
    logger.info("")
    
    # Confirm
    response = input("Press Enter to begin (or 'q' to quit): ")
    if response.lower() == 'q':
        logger.info("Cancelled by user")
        return
    
    # Process the batch
    result_stats = process_batch(client, engine, batch)
    
    # Log to database
    with get_session(engine) as session:
        log_entry = UpdateLog(
            update_type='batch_historical_load',
            status='success',
            message=f"Loaded {result_stats['successful']:,}/{result_stats['total_attempted']:,} tickers",
            api_calls_made=result_stats['total_attempted'],
            rows_affected=result_stats['total_records'],
            duration_seconds=result_stats['duration_seconds']
        )
        session.add(log_entry)
        session.commit()
    
    # Final summary
    logger.info("\n" + "=" * 70)
    logger.info("🎉 BATCH LOADING COMPLETE")
    logger.info("=" * 70)
    logger.info(f"  Attempted: {result_stats['total_attempted']:,} tickers")
    logger.info(f"  ✅ Successful: {result_stats['successful']:,}")
    logger.info(f"  ⚠️  Failed: {result_stats['failed']:,}")
    logger.info(f"  📊 Price records added: {result_stats['total_records']:,}")
    logger.info(f"  ⏱️  Duration: {result_stats['duration_minutes']:.1f} minutes")
    logger.info(f"  🔌 API calls used: {client.calls_today:,}")
    logger.info("")
    
    # Get updated statistics
    logger.info("📊 Updated Database Statistics:")
    logger.info("=" * 70)
    updated_stats = get_loading_statistics(engine)
    logger.info(f"  Assets with data: {updated_stats['assets_with_data']:,}")
    logger.info(f"  Assets remaining: {updated_stats['assets_never_loaded']:,}")
    logger.info(f"  Coverage: {updated_stats['percent_loaded']:.1f}%")
    logger.info(f"  Total price records: {updated_stats['total_price_records']:,}")
    logger.info("")
    
    # Calculate runs needed
    if updated_stats['assets_never_loaded'] > 0:
        runs_needed = (updated_stats['assets_never_loaded'] + MAX_BATCH_SIZE - 1) // MAX_BATCH_SIZE
        logger.info(f"💡 Runs remaining: ~{runs_needed} (at {MAX_BATCH_SIZE:,} tickers per run)")
        logger.info(f"💡 Run again tomorrow to load next batch")
    else:
        logger.info(f"🎉 All assets loaded! Database is complete.")
    
    logger.info("")


if __name__ == "__main__":
    try:
        start_time = time.time()
        main()
        elapsed = time.time() - start_time
        logger.info(f"Total execution time: {elapsed/60:.1f} minutes")
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Process cancelled by user")
        logger.info("   Progress has been saved. Run again to continue.")
    except Exception as e:
        logger.error(f"\n\n❌ Process failed: {e}")
        import traceback
        traceback.print_exc()
