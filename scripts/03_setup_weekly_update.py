# Script 03: Weekly Update - Incremental Data Updates
# Runs weekly to update PostgreSQL with latest price data

import sys
import time
import logging
from pathlib import Path
from datetime import datetime, date, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_v6
from models_v6 import Asset, AssetPrice, CorporateActions, UpdateLog, get_session
from eodhd_client import EODHDClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config_v6.LOGS_DIR / "weekly_update.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_last_week_trading_days():
    """Get list of trading days from last week (excludes weekends)"""
    today = date.today()
    last_week = today - timedelta(days=7)
    
    dates = []
    current = last_week
    
    while current <= today:
        # Skip weekends (Monday=0, Sunday=6)
        if current.weekday() < 5:
            dates.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    
    return dates


def update_exchange_prices(client: EODHDClient, engine, exchange: str, date_str: str):
    """Update prices for an exchange on a specific date"""
    try:
        # Use bulk API to get all prices for the exchange
        bulk_data = client.get_eod_bulk(exchange, date=date_str)
        
        if not bulk_data:
            return 0
        
        with get_session(engine) as session:
            rows_inserted = 0
            rows_updated = 0
            
            for item in bulk_data:
                symbol_code = item.get('code')
                if not symbol_code:
                    continue
                
                full_symbol = f"{symbol_code}.{exchange}"
                price_date = datetime.strptime(item.get('date', date_str), '%Y-%m-%d').date()
                
                # Check if price already exists
                existing = session.query(AssetPrice).filter_by(
                    symbol=full_symbol,
                    date=price_date
                ).first()
                
                if existing:
                    # Update existing
                    existing.open = item.get('open')
                    existing.high = item.get('high')
                    existing.low = item.get('low')
                    existing.close = item.get('close')
                    existing.adjusted_close = item.get('adjusted_close')
                    existing.volume = item.get('volume')
                    rows_updated += 1
                else:
                    # Insert new
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
                if (rows_inserted + rows_updated) % 1000 == 0:
                    session.commit()
            
            session.commit()
            
            # Update asset last_price_date
            session.execute(
                f"""
                UPDATE assets 
                SET last_price_date = '{price_date}'
                WHERE exchange = '{exchange}' 
                AND last_price_date < '{price_date}'
                """
            )
            session.commit()
            
            return rows_inserted + rows_updated
            
    except Exception as e:
        logger.error(f"  Error updating {exchange} on {date_str}: {e}")
        return 0


def update_exchange_corporate_actions(client: EODHDClient, engine, exchange: str, date_str: str):
    """Update splits and dividends for an exchange"""
    splits_count = 0
    dividends_count = 0
    
    try:
        # Get splits
        splits_data = client.get_bulk_splits(exchange, date=date_str)
        
        if splits_data:
            with get_session(engine) as session:
                for item in splits_data:
                    symbol_code = item.get('code')
                    if not symbol_code:
                        continue
                    
                    full_symbol = f"{symbol_code}.{exchange}"
                    split_date = datetime.strptime(item.get('date', date_str), '%Y-%m-%d').date()
                    
                    # Check if already exists
                    existing = session.query(CorporateActions).filter_by(
                        symbol=full_symbol,
                        action_date=split_date,
                        action_type='split'
                    ).first()
                    
                    if not existing:
                        split_str = item.get('split', '1/1')
                        try:
                            numerator, denominator = split_str.split('/')
                            split_ratio = float(numerator) / float(denominator)
                        except:
                            split_ratio = 1.0
                        
                        action = CorporateActions(
                            symbol=full_symbol,
                            action_date=split_date,
                            action_type='split',
                            split_ratio=split_ratio,
                            details=split_str,
                            data_source='EODHD'
                        )
                        session.add(action)
                        splits_count += 1
                
                session.commit()
        
        # Get dividends
        dividends_data = client.get_bulk_dividends(exchange, date=date_str)
        
        if dividends_data:
            with get_session(engine) as session:
                for item in dividends_data:
                    symbol_code = item.get('code')
                    if not symbol_code:
                        continue
                    
                    full_symbol = f"{symbol_code}.{exchange}"
                    div_date = datetime.strptime(item.get('date', date_str), '%Y-%m-%d').date()
                    
                    # Check if already exists
                    existing = session.query(CorporateActions).filter_by(
                        symbol=full_symbol,
                        action_date=div_date,
                        action_type='dividend'
                    ).first()
                    
                    if not existing:
                        action = CorporateActions(
                            symbol=full_symbol,
                            action_date=div_date,
                            action_type='dividend',
                            dividend_amount=item.get('value') or item.get('unadjustedValue'),
                            dividend_currency=item.get('currency', 'USD'),
                            ex_dividend_date=div_date,
                            data_source='EODHD'
                        )
                        session.add(action)
                        dividends_count += 1
                
                session.commit()
        
    except Exception as e:
        logger.error(f"  Error updating corporate actions for {exchange}: {e}")
    
    return splits_count, dividends_count


def run_weekly_update():
    """Main weekly update function"""
    logger.info("=" * 70)
    logger.info("WEEKLY UPDATE - Updating PostgreSQL Database")
    logger.info("=" * 70)
    logger.info(f"Update time: {datetime.now()}")
    logger.info("")
    
    # Initialize
    client = EODHDClient(config_v6.EODHD_API_TOKEN)
    engine = config_v6.get_postgres_engine()
    
    # Get last week's dates
    dates = get_last_week_trading_days()
    logger.info(f"📅 Updating dates: {dates[0]} to {dates[-1]} ({len(dates)} days)")
    logger.info("")
    
    # Get exchanges to update
    exchanges = config_v6.PRIORITY_EXCHANGES
    logger.info(f"📊 Exchanges to update: {', '.join(exchanges)}")
    logger.info("")
    
    # Track totals
    total_prices = 0
    total_splits = 0
    total_dividends = 0
    
    # Update each exchange
    for exchange in exchanges:
        logger.info(f"\n{'='*50}")
        logger.info(f"Updating: {exchange}")
        logger.info(f"{'='*50}")
        
        exchange_prices = 0
        exchange_splits = 0
        exchange_dividends = 0
        
        # Update most recent date only (last trading day)
        latest_date = dates[-1]
        
        logger.info(f"📈 Updating prices for {latest_date}...")
        prices = update_exchange_prices(client, engine, exchange, latest_date)
        exchange_prices += prices
        logger.info(f"  ✅ {prices:,} price records")
        
        logger.info(f"💰 Checking corporate actions...")
        splits, dividends = update_exchange_corporate_actions(client, engine, exchange, latest_date)
        exchange_splits += splits
        exchange_dividends += dividends
        
        if splits > 0:
            logger.info(f"  ✅ {splits} splits")
        if dividends > 0:
            logger.info(f"  ✅ {dividends} dividends")
        
        # Update totals
        total_prices += exchange_prices
        total_splits += exchange_splits
        total_dividends += exchange_dividends
        
        # Log to database
        with get_session(engine) as session:
            log_entry = UpdateLog(
                update_type='weekly_update',
                exchange=exchange,
                status='success',
                message=f"Updated {exchange_prices:,} prices, {exchange_splits} splits, {exchange_dividends} dividends",
                api_calls_made=300,  # Approximate: 100 prices + 100 splits + 100 dividends
                rows_affected=exchange_prices + exchange_splits + exchange_dividends,
                duration_seconds=0  # Will be updated later
            )
            session.add(log_entry)
        
        # Pause between exchanges
        time.sleep(5)
    
    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("✅ WEEKLY UPDATE COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Prices updated: {total_prices:,}")
    logger.info(f"Splits added: {total_splits}")
    logger.info(f"Dividends added: {total_dividends}")
    logger.info(f"API calls used: {client.calls_today:,}")
    logger.info(f"API calls remaining: {client.max_calls_per_day - client.calls_today:,}")
    logger.info("")


def setup_windows_task():
    """Create Windows Task Scheduler task for weekly updates"""
    logger.info("=" * 70)
    logger.info("SETTING UP WINDOWS TASK SCHEDULER")
    logger.info("=" * 70)
    logger.info("")
    
    script_path = Path(__file__).resolve()
    python_exe = sys.executable
    
    # Create task command
    task_command = f'''schtasks /create /tn "Portfolio_Weekly_Update" /tr "{python_exe} {script_path}" /sc weekly /d SUN /st 02:00 /f'''
    
    logger.info("To set up automatic weekly updates:")
    logger.info("")
    logger.info("1. Open Command Prompt as Administrator")
    logger.info("2. Run this command:")
    logger.info("")
    logger.info(task_command)
    logger.info("")
    logger.info("This will run the update every Sunday at 2:00 AM")
    logger.info("")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Weekly database update')
    parser.add_argument('--setup-task', action='store_true', help='Show Windows Task Scheduler setup')
    parser.add_argument('--run-now', action='store_true', help='Run update immediately')
    
    args = parser.parse_args()
    
    if args.setup_task:
        setup_windows_task()
    elif args.run_now:
        run_weekly_update()
    else:
        # Interactive mode
        print("\nWeekly Update Script")
        print("=" * 50)
        print("1. Run update now")
        print("2. Show Windows Task Scheduler setup")
        print("3. Exit")
        
        choice = input("\nSelect option (1-3): ").strip()
        
        if choice == '1':
            run_weekly_update()
        elif choice == '2':
            setup_windows_task()
        else:
            print("Exiting...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Process cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n❌ Process failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
