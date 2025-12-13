
# Script 02: Load Historical Data - Bulk Download Price History
# This is the BIG one - loads 20+ years of monthly data for all tickers

import sys
import time
import logging
from pathlib import Path
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_v6
from models_v6 import (
    Asset, AssetPrice, CorporateActions, UpdateLog, 
    get_session, DataQualityIssue
)
from eodhd_client import EODHDClient
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config_v6.LOGS_DIR / "load_historical_data.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def validate_api_access(client: EODHDClient, engine):
    """
    Validate API access before starting bulk load
    
    Args:
        client: EODHD API client
        engine: Database engine
    
    Returns:
        bool: True if validated, False if issues found
    """
    logger.info("🔍 Validating API access...")
    
    try:
        # Check API quota
        logger.info(f"  API calls used today: {client.calls_today:,}")
        logger.info(f"  API calls limit: {client.max_calls_per_day:,}")
        
        remaining = client.max_calls_per_day - client.calls_today
        logger.info(f"  Remaining calls: {remaining:,}")
        
        if remaining < 1000:
            logger.warning("⚠️  Low API quota! Consider running tomorrow.")
            return False
        
        # Try a test call
        logger.info("  Testing API with small request...")
        test_data = client.get_eod_bulk('US', date='2024-01-01')
        
        if test_data and len(test_data) > 0:
            logger.info(f"  ✅ API test successful ({len(test_data)} records)")
            return True
        else:
            logger.warning("⚠️  API test returned no data")
            return False
            
    except Exception as e:
        logger.error(f"❌ API validation failed: {e}")
        return False


def get_date_range_for_bulk_load():
    """
    Get list of dates to load (monthly intervals from historical start to present)
    
    Returns:
        List of date strings in YYYY-MM-DD format
    """
    start_date = datetime.strptime(config_v6.HISTORICAL_START_DATE, '%Y-%m-%d')
    end_date = datetime.now()
    
    dates = []
    current_date = start_date
    
    while current_date <= end_date:
        # Use first day of month
        first_of_month = current_date.replace(day=1)
        dates.append(first_of_month.strftime('%Y-%m-%d'))
        
        # Move to next month
        current_date += relativedelta(months=1)
    
    return dates


def load_bulk_eod_for_date(client: EODHDClient, engine, exchange: str, target_date: str):
    """
    Load all EOD data for an exchange on a specific date using Bulk API
    
    Args:
        client: EODHD API client
        engine: Database engine
        exchange: Exchange code
        target_date: Date in YYYY-MM-DD format
    """
    try:
        # Fetch bulk data
        bulk_data = client.get_eod_bulk(exchange, date=target_date)
        
        if not bulk_data:
            logger.debug(f"  No data for {exchange} on {target_date}")
            return 0
        
        # Process and insert
        with get_session(engine) as session:
            rows_inserted = 0
            
            for item in bulk_data:
                symbol_code = item.get('code')
                if not symbol_code:
                    continue
                
                # Construct full symbol
                full_symbol = f"{symbol_code}.{exchange}"
                
                # Check if asset exists (should exist from universe load)
                asset = session.query(Asset).filter_by(symbol=full_symbol).first()
                if not asset:
                    # Create asset if missing (shouldn't happen often)
                    asset = Asset(
                        symbol=full_symbol,
                        code=symbol_code,
                        exchange=exchange,
                        is_active=True,
                        data_source='EODHD'
                    )
                    session.add(asset)
                    session.flush()
                
                # Extract price data
                price_date = datetime.strptime(item.get('date', target_date), '%Y-%m-%d').date()
                
                # Check if we already have this price
                existing = session.query(AssetPrice).filter_by(
                    symbol=full_symbol,
                    date=price_date
                ).first()
                
                if existing:
                    continue  # Skip duplicates
                
                # Create price record
                price = AssetPrice(
                    symbol=full_symbol,
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
                rows_inserted += 1
                
                # Commit in batches
                if rows_inserted % 1000 == 0:
                    session.commit()
            
            # Final commit
            session.commit()
            
            return rows_inserted
            
    except Exception as e:
        logger.error(f"  Error loading bulk data for {exchange} on {target_date}: {e}")
        return 0


def load_bulk_splits_for_date(client: EODHDClient, engine, exchange: str, target_date: str):
    """Load splits for an exchange on a specific date"""
    try:
        splits_data = client.get_bulk_splits(exchange, date=target_date)
        
        if not splits_data:
            return 0
        
        with get_session(engine) as session:
            count = 0
            
            for item in splits_data:
                symbol_code = item.get('code')
                if not symbol_code:
                    continue
                
                full_symbol = f"{symbol_code}.{exchange}"
                split_date = datetime.strptime(item.get('date', target_date), '%Y-%m-%d').date()
                
                # Check if already exists
                existing = session.query(CorporateActions).filter_by(
                    symbol=full_symbol,
                    action_date=split_date,
                    action_type='split'
                ).first()
                
                if existing:
                    continue
                
                # Parse split ratio (e.g., "2/1" means 2-for-1)
                split_str = item.get('split', '1/1')
                try:
                    numerator, denominator = split_str.split('/')
                    split_ratio = float(numerator) / float(denominator)
                except:
                    split_ratio = 1.0
                
                # Create corporate action
                action = CorporateActions(
                    symbol=full_symbol,
                    action_date=split_date,
                    action_type='split',
                    split_ratio=split_ratio,
                    split_from=float(numerator) if 'numerator' in locals() else None,
                    split_to=float(denominator) if 'denominator' in locals() else None,
                    details=split_str,
                    data_source='EODHD'
                )
                session.add(action)
                count += 1
            
            session.commit()
            return count
            
    except Exception as e:
        logger.error(f"  Error loading splits for {exchange} on {target_date}: {e}")
        return 0


def load_bulk_dividends_for_date(client: EODHDClient, engine, exchange: str, target_date: str):
    """Load dividends for an exchange on a specific date"""
    try:
        dividends_data = client.get_bulk_dividends(exchange, date=target_date)
        
        if not dividends_data:
            return 0
        
        with get_session(engine) as session:
            count = 0
            
            for item in dividends_data:
                symbol_code = item.get('code')
                if not symbol_code:
                    continue
                
                full_symbol = f"{symbol_code}.{exchange}"
                div_date = datetime.strptime(item.get('date', target_date), '%Y-%m-%d').date()
                
                # Check if already exists
                existing = session.query(CorporateActions).filter_by(
                    symbol=full_symbol,
                    action_date=div_date,
                    action_type='dividend'
                ).first()
                
                if existing:
                    continue
                
                # Create corporate action
                action = CorporateActions(
                    symbol=full_symbol,
                    action_date=div_date,
                    action_type='dividend',
                    dividend_amount=item.get('value') or item.get('unadjustedValue'),
                    dividend_currency=item.get('currency', 'USD'),
                    ex_dividend_date=div_date,  # The date in bulk API is ex-dividend date
                    data_source='EODHD'
                )
                session.add(action)
                count += 1
            
            session.commit()
            return count
            
    except Exception as e:
        logger.error(f"  Error loading dividends for {exchange} on {target_date}: {e}")
        return 0


def load_exchange_historical_data(client: EODHDClient, engine, exchange: str):
    """
    Load all historical data for an exchange
    
    Args:
        client: EODHD API client
        engine: Database engine
        exchange: Exchange code
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"📈 Loading historical data for: {exchange}")
    logger.info(f"{'='*70}")
    
    start_time = time.time()
    total_prices = 0
    total_splits = 0
    total_dividends = 0
    
    # Get date range (monthly intervals)
    dates = get_date_range_for_bulk_load()
    logger.info(f"Date range: {dates[0]} to {dates[-1]} ({len(dates)} months)")
    
    # Sample dates (every 3 months for efficiency during initial load)
    # You can change this to load ALL months if you prefer
    sampled_dates = dates[::3]  # Every 3rd month
    logger.info(f"Loading {len(sampled_dates)} sampled dates (every 3 months)")
    logger.info("")
    
    for i, target_date in enumerate(sampled_dates, 1):
        logger.info(f"[{i}/{len(sampled_dates)}] {target_date}")
        
        # Load prices
        prices = load_bulk_eod_for_date(client, engine, exchange, target_date)
        total_prices += prices
        logger.info(f"  Prices: {prices:,}")
        
        # Load splits (less frequent, so check every date)
        if i % 12 == 0:  # Check annually
            splits = load_bulk_splits_for_date(client, engine, exchange, target_date)
            total_splits += splits
            if splits > 0:
                logger.info(f"  Splits: {splits}")
        
        # Load dividends (less frequent, so check every date)
        if i % 3 == 0:  # Check quarterly
            dividends = load_bulk_dividends_for_date(client, engine, exchange, target_date)
            total_dividends += dividends
            if dividends > 0:
                logger.info(f"  Dividends: {dividends}")
        
        # Rate limiting pause
        if i % 10 == 0:
            time.sleep(5)  # Longer pause every 10 requests
        else:
            time.sleep(1)
    
    elapsed = time.time() - start_time
    
    # Log summary
    logger.info("")
    logger.info(f"✅ {exchange} complete:")
    logger.info(f"  Prices: {total_prices:,}")
    logger.info(f"  Splits: {total_splits:,}")
    logger.info(f"  Dividends: {total_dividends:,}")
    logger.info(f"  Time: {elapsed/60:.1f} minutes")
    logger.info(f"  API calls: ~{len(sampled_dates) * 100}")
    
    # Log to database
    with get_session(engine) as session:
        log_entry = UpdateLog(
            update_type='historical_prices',
            exchange=exchange,
            status='success',
            message=f"Loaded {total_prices:,} prices, {total_splits} splits, {total_dividends} dividends",
            api_calls_made=len(sampled_dates) * 100,
            rows_affected=total_prices + total_splits + total_dividends,
            duration_seconds=elapsed
        )
        session.add(log_entry)
    
    return total_prices, total_splits, total_dividends

def check_exchange_has_data(engine, exchange: str, min_records: int = 10000):
    """
    Check if exchange already has substantial historical data
    
    Args:
        engine: Database engine
        exchange: Exchange code
        min_records: Minimum records to consider "already loaded"
    
    Returns:
        tuple: (has_data, record_count)
    """
    try:
        with get_session(engine) as session:
            count = session.query(AssetPrice).filter(
                AssetPrice.symbol.like(f'%.{exchange}')
            ).count()
            
            return (count >= min_records, count)
    except Exception as e:
        logger.error(f"Error checking data for {exchange}: {e}")
        return (False, 0)


def should_skip_exchange(exchange: str, failed_dates: int, total_dates: int, 
                        failure_threshold: float = 0.5):
    """
    Determine if exchange should be skipped due to repeated failures
    
    Args:
        exchange: Exchange code
        failed_dates: Number of dates that returned errors
        total_dates: Total dates attempted
        failure_threshold: Skip if failure rate exceeds this (0.5 = 50%)
    
    Returns:
        bool: True if should skip
    """
    if total_dates == 0:
        return False
    
    failure_rate = failed_dates / total_dates
    
    if failure_rate >= failure_threshold:
        logger.warning(f"⚠️  {exchange} has {failure_rate:.1%} failure rate - skipping")
        return True
    
    return False


def load_exchange_historical_data(client: EODHDClient, engine, exchange: str, 
                                  check_existing: bool = True):
    """
    Load all historical data for an exchange with smart skip logic
    
    Args:
        client: EODHD API client
        engine: Database engine
        exchange: Exchange code
        check_existing: If True, skip if exchange already has data
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"📈 Loading historical data for: {exchange}")
    logger.info(f"{'='*70}")
    
    # Check if exchange already has substantial data
    if check_existing:
        has_data, record_count = check_exchange_has_data(engine, exchange)
        if has_data:
            logger.info(f"✅ {exchange} already has {record_count:,} price records - SKIPPING")
            logger.info(f"   (Use check_existing=False to reload)")
            return 0, 0, 0  # Return zeros to continue loop
    
    start_time = time.time()
    total_prices = 0
    total_splits = 0
    total_dividends = 0
    failed_dates = 0
    
    # Get date range (monthly intervals)
    dates = get_date_range_for_bulk_load()
    logger.info(f"Date range: {dates[0]} to {dates[-1]} ({len(dates)} months)")
    
    # Sample dates (every 3 months for efficiency during initial load)
    sampled_dates = dates[::3]  # Every 3rd month
    logger.info(f"Loading {len(sampled_dates)} sampled dates (every 3 months)")
    logger.info("")
    
    for i, target_date in enumerate(sampled_dates, 1):
        logger.info(f"[{i}/{len(sampled_dates)}] {target_date}")
        
        # Load prices
        prices = load_bulk_eod_for_date(client, engine, exchange, target_date)
        
        if prices == 0:
            failed_dates += 1
            logger.debug(f"  No data returned for {target_date}")
        else:
            total_prices += prices
            logger.info(f"  Prices: {prices:,}")
        
        # Early exit if too many failures (check every 10 dates)
        if i >= 10 and i % 10 == 0:
            if should_skip_exchange(exchange, failed_dates, i, failure_threshold=0.8):
                logger.error(f"❌ Too many failures for {exchange} - stopping early")
                logger.error(f"   This likely means:")
                logger.error(f"   1. Your API subscription doesn't cover this exchange")
                logger.error(f"   2. Historical bulk data not available for {exchange}")
                logger.error(f"   3. API quota exceeded")
                break
        
        # Load splits (less frequent, so check every date)
        if i % 12 == 0:  # Check annually
            splits = load_bulk_splits_for_date(client, engine, exchange, target_date)
            total_splits += splits
            if splits > 0:
                logger.info(f"  Splits: {splits}")
        
        # Load dividends (less frequent, so check every date)
        if i % 3 == 0:  # Check quarterly
            dividends = load_bulk_dividends_for_date(client, engine, exchange, target_date)
            total_dividends += dividends
            if dividends > 0:
                logger.info(f"  Dividends: {dividends}")
        
        # Rate limiting pause
        if i % 10 == 0:
            time.sleep(5)  # Longer pause every 10 requests
        else:
            time.sleep(1)
    
    elapsed = time.time() - start_time
    
    # Log summary
    logger.info("")
    if total_prices > 0:
        logger.info(f"✅ {exchange} complete:")
    else:
        logger.warning(f"⚠️  {exchange} returned NO data:")
    
    logger.info(f"  Prices: {total_prices:,}")
    logger.info(f"  Splits: {total_splits:,}")
    logger.info(f"  Dividends: {total_dividends:,}")
    logger.info(f"  Failed dates: {failed_dates}/{len(sampled_dates)}")
    logger.info(f"  Time: {elapsed/60:.1f} minutes")
    
    # Log to database
    status = 'success' if total_prices > 0 else 'failed'
    with get_session(engine) as session:
        log_entry = UpdateLog(
            update_type='historical_prices',
            exchange=exchange,
            status=status,
            message=f"Loaded {total_prices:,} prices, {total_splits} splits, {total_dividends} dividends. Failed: {failed_dates}",
            api_calls_made=len(sampled_dates),
            rows_affected=total_prices + total_splits + total_dividends,
            duration_seconds=elapsed
        )
        session.add(log_entry)
        session.commit()
    
    return total_prices, total_splits, total_dividends


def main():
    """Main function to load historical data for all exchanges"""
    logger.info("=" * 70)
    logger.info("LOADING HISTORICAL DATA - BULK DOWNLOAD")
    logger.info("=" * 70)
    logger.info("")
    
    # Initialize
    try:
        client = EODHDClient(config_v6.EODHD_API_TOKEN)
        engine = config_v6.get_postgres_engine()
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        sys.exit(1)
    
    # Validate API access
    if not validate_api_access(client, engine):
        logger.error("❌ API validation failed")
        logger.error("   Please check:")
        logger.error("   1. Your API token in config_v6.py")
        logger.error("   2. Your subscription at https://eodhd.com/cp/settings")
        logger.error("   3. Your API quota hasn't been exceeded")
        response = input("\nContinue anyway? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Exiting...")
            sys.exit(1)
    logger.info("")
    
    # Get exchanges to load
    exchanges = config_v6.PRIORITY_EXCHANGES  # Start with priority exchanges

    logger.info(f"DEBUG: Exchanges list = {exchanges}")
    logger.info(f"DEBUG: Number of exchanges = {len(exchanges)}")
    
    logger.info(f"📊 Exchanges to load: {len(exchanges)}")
    logger.info(f"📅 Date range: {config_v6.HISTORICAL_START_DATE} to present")
    logger.info(f"⚡ Using BULK API (100 calls per exchange per date)")
    logger.info("")
    logger.info("⚠️  This will take several hours. You can stop and resume anytime.")
    logger.info("")
    
    input("Press Enter to begin...")
    
    # Track totals
    grand_total_prices = 0
    grand_total_splits = 0
    grand_total_dividends = 0
    exchanges_completed = []
    exchanges_skipped = []
    exchanges_failed = []
    
    logger.info(f"📊 Exchanges to process: {len(exchanges)}")
    logger.info(f"📅 Date range: {config_v6.HISTORICAL_START_DATE} to present")
    logger.info(f"⚡ Using BULK API")
    logger.info("")
    
    # Check which exchanges already have data
    logger.info("🔍 Checking existing data...")
    for exchange in exchanges:
        has_data, count = check_exchange_has_data(engine, exchange)
        if has_data:
            logger.info(f"  ✅ {exchange}: {count:,} records (will skip)")
        else:
            logger.info(f"  📥 {exchange}: {count:,} records (will load)")
    logger.info("")
    
    logger.info("⚠️  This will take several hours. You can stop and resume anytime.")
    logger.info("")
    
    response = input("Press Enter to begin (or 'force' to reload all exchanges): ")
    check_existing = response.lower() != 'force'
    
    if not check_existing:
        logger.warning("⚠️  FORCE MODE: Will reload all exchanges (including existing data)")
    
    logger.info("")
    
    # Load each exchange
    for idx, exchange in enumerate(exchanges, 1):
        logger.info(f"\n{'='*70}")
        logger.info(f"EXCHANGE {idx}/{len(exchanges)}: {exchange}")
        logger.info(f"{'='*70}")
        
        try:
            prices, splits, dividends = load_exchange_historical_data(
                client, engine, exchange, check_existing=check_existing
            )
            
            if prices > 0:
                grand_total_prices += prices
                grand_total_splits += splits
                grand_total_dividends += dividends
                exchanges_completed.append(exchange)
                logger.info(f"✅ {exchange} completed successfully")
            elif prices == 0 and splits == 0 and dividends == 0:
                # Check if it was skipped or failed
                has_data, _ = check_exchange_has_data(engine, exchange)
                if has_data:
                    exchanges_skipped.append(exchange)
                else:
                    exchanges_failed.append(exchange)
                    logger.warning(f"⚠️  {exchange} returned no data")
            
        except KeyboardInterrupt:
            logger.info("\n\n⚠️  Process interrupted by user")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error processing {exchange}: {e}")
            import traceback
            traceback.print_exc()
            exchanges_failed.append(exchange)
            logger.info("Continuing to next exchange...")
        
        # Show API usage
        try:
            logger.info(f"\n📊 API Usage: {client.calls_today:,} / {client.max_calls_per_day:,}")
            remaining = client.max_calls_per_day - client.calls_today
            logger.info(f"📊 Remaining today: {remaining:,}")
            
            if remaining < 1000:
                logger.warning("⚠️  API quota running low!")
        except:
            pass
        
        # Pause between exchanges (unless last one)
        if idx < len(exchanges):
            logger.info(f"💤 Pausing 30 seconds before next exchange...")
            time.sleep(30)
    
    # Final summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("📊 HISTORICAL DATA LOADING COMPLETE")
    logger.info("=" * 70)
    logger.info("")
    logger.info("📈 Data Loaded:")
    logger.info(f"  Prices: {grand_total_prices:,}")
    logger.info(f"  Splits: {grand_total_splits:,}")
    logger.info(f"  Dividends: {grand_total_dividends:,}")
    logger.info("")
    
    logger.info("📋 Exchange Status:")
    logger.info(f"  ✅ Completed: {len(exchanges_completed)} - {', '.join(exchanges_completed) if exchanges_completed else 'None'}")
    logger.info(f"  ⏭️  Skipped: {len(exchanges_skipped)} - {', '.join(exchanges_skipped) if exchanges_skipped else 'None'}")
    logger.info(f"  ❌ Failed: {len(exchanges_failed)} - {', '.join(exchanges_failed) if exchanges_failed else 'None'}")
    logger.info("")
    
    try:
        logger.info(f"🔌 API Usage: {client.calls_today:,} / {client.max_calls_per_day:,}")
    except:
        pass
    
    logger.info("")
    
    # Next steps guidance
    if exchanges_failed:
        logger.warning("⚠️  Some exchanges failed. Common reasons:")
        logger.warning("   1. API subscription doesn't include those exchanges")
        logger.warning("   2. Bulk historical data not available for those exchanges")
        logger.warning("   3. Exchange codes may be incorrect")
        logger.warning("")
        logger.warning("   Check your EODHD subscription at: https://eodhd.com/cp/settings")
        logger.warning("   Or contact support about bulk data availability")
        logger.warning("")
    
    if exchanges_completed:
        logger.info("✅ Next step: Set up weekly updates")
        logger.info("   python scripts/03_setup_weekly_update.py")
    else:
        logger.warning("⚠️  No data was loaded. Please check:")
        logger.warning("   1. Your EODHD API subscription and quota")
        logger.warning("   2. Exchange codes in config_v6.py")
        logger.warning("   3. Error log: logs/load_historical_data.log")
    logger.info("")


if __name__ == "__main__":
    try:
        start_time = time.time()
        main()
        elapsed = time.time() - start_time
        logger.info(f"Total execution time: {elapsed/3600:.1f} hours")
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Process cancelled by user (can resume later)")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n❌ Process failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
