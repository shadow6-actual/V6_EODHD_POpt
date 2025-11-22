# Script 01: Load Universe - Fetch All Tickers from All Exchanges
# This populates the assets table with ~150K tickers

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_v6
from models_v6 import Asset, UpdateLog, get_session
from eodhd_client import EODHDClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config_v6.LOGS_DIR / "load_universe.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_exchange_symbols(client: EODHDClient, engine, exchange_code: str):
    """
    Load all symbols for a given exchange
    
    Args:
        client: EODHD API client
        engine: Database engine
        exchange_code: Exchange code (e.g., 'US', 'LSE')
    """
    logger.info(f"📊 Loading symbols for exchange: {exchange_code}")
    
    try:
        start_time = time.time()
        
        # Fetch symbols from EODHD
        symbols_data = client.get_exchange_symbols(exchange_code)
        
        if not symbols_data:
            logger.warning(f"No symbols returned for {exchange_code}")
            return 0
        
        logger.info(f"  Retrieved {len(symbols_data):,} symbols from API")
        
        # Insert into database
        with get_session(engine) as session:
            new_count = 0
            updated_count = 0
            
            for symbol_data in symbols_data:
                # Extract fields
                code = symbol_data.get('Code', '')
                name = symbol_data.get('Name', '')
                asset_type = symbol_data.get('Type', 'Unknown')
                isin = symbol_data.get('Isin', '')
                currency = symbol_data.get('Currency', '')
                country = symbol_data.get('Country', '')
                exchange = symbol_data.get('Exchange', exchange_code)
                
                # Construct full symbol (CODE.EXCHANGE)
                full_symbol = f"{code}.{exchange}"
                
                # Check if asset already exists
                asset = session.query(Asset).filter_by(symbol=full_symbol).first()
                
                if asset:
                    # Update existing
                    asset.name = name or asset.name
                    asset.asset_type = asset_type or asset.asset_type
                    asset.isin = isin or asset.isin
                    asset.currency = currency or asset.currency
                    asset.country = country or asset.country
                    asset.last_updated = datetime.utcnow()
                    asset.is_active = True  # Mark as active
                    updated_count += 1
                else:
                    # Create new
                    asset = Asset(
                        symbol=full_symbol,
                        code=code,
                        exchange=exchange,
                        name=name,
                        asset_type=asset_type,
                        isin=isin,
                        currency=currency,
                        country=country,
                        is_active=True,
                        first_seen=datetime.utcnow(),
                        last_updated=datetime.utcnow(),
                        data_source='EODHD'
                    )
                    session.add(asset)
                    new_count += 1
                
                # Commit every 1000 symbols
                if (new_count + updated_count) % 1000 == 0:
                    session.commit()
                    logger.info(f"  Progress: {new_count + updated_count:,} symbols processed")
            
            # Final commit
            session.commit()
            
            # Log the update
            log_entry = UpdateLog(
                update_type='universe',
                exchange=exchange_code,
                status='success',
                message=f"Loaded {new_count} new, updated {updated_count} existing symbols",
                api_calls_made=1,
                rows_affected=new_count + updated_count,
                duration_seconds=time.time() - start_time
            )
            session.add(log_entry)
            session.commit()
        
        elapsed = time.time() - start_time
        logger.info(f"  ✅ {exchange_code}: {new_count} new, {updated_count} updated ({elapsed:.1f}s)")
        
        return new_count + updated_count
        
    except Exception as e:
        logger.error(f"  ❌ Error loading {exchange_code}: {e}")
        
        # Log the error
        try:
            with get_session(engine) as session:
                log_entry = UpdateLog(
                    update_type='universe',
                    exchange=exchange_code,
                    status='error',
                    message=str(e),
                    duration_seconds=time.time() - start_time
                )
                session.add(log_entry)
        except:
            pass
        
        return 0


def main():
    """Main function to load all tickers from all exchanges"""
    logger.info("=" * 70)
    logger.info("LOADING UNIVERSE - ALL TICKERS FROM ALL EXCHANGES")
    logger.info("=" * 70)
    logger.info("")
    
    # Initialize
    client = EODHDClient(config_v6.EODHD_API_TOKEN)
    engine = config_v6.get_postgres_engine()
    
    # Get list of exchanges to track
    exchanges_to_load = config_v6.EXCHANGES_TO_TRACK
    priority_exchanges = config_v6.PRIORITY_EXCHANGES
    
    logger.info(f"📋 Exchanges to load: {len(exchanges_to_load)}")
    logger.info(f"🎯 Priority exchanges: {', '.join(priority_exchanges)}")
    logger.info("")
    
    # Load priority exchanges first
    logger.info("🚀 Loading priority exchanges first...")
    total_loaded = 0
    priority_loaded = 0
    
    for exchange in priority_exchanges:
        if exchange in exchanges_to_load:
            count = load_exchange_symbols(client, engine, exchange)
            total_loaded += count
            priority_loaded += count
            time.sleep(2)  # Polite pause between exchanges
    
    logger.info(f"\n✅ Priority exchanges loaded: {priority_loaded:,} symbols")
    logger.info("")
    
    # Load remaining exchanges
    remaining_exchanges = [ex for ex in exchanges_to_load if ex not in priority_exchanges]
    
    if remaining_exchanges:
        logger.info(f"📊 Loading {len(remaining_exchanges)} remaining exchanges...")
        
        for i, exchange in enumerate(remaining_exchanges, 1):
            logger.info(f"\n[{i}/{len(remaining_exchanges)}] {exchange}")
            count = load_exchange_symbols(client, engine, exchange)
            total_loaded += count
            time.sleep(2)  # Polite pause
    
    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("📊 UNIVERSE LOADING COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total tickers loaded: {total_loaded:,}")
    logger.info(f"API calls used: {client.calls_today}")
    logger.info(f"API calls remaining: {client.max_calls_per_day - client.calls_today:,}")
    logger.info("")
    
    # Verify in database
    with get_session(engine) as session:
        total_in_db = session.query(Asset).count()
        active_in_db = session.query(Asset).filter_by(is_active=True).count()
        
        logger.info(f"Database verification:")
        logger.info(f"  Total assets in database: {total_in_db:,}")
        logger.info(f"  Active assets: {active_in_db:,}")
        logger.info("")
    
    logger.info("✅ Next step: Load historical price data")
    logger.info("   python scripts/02_load_historical_data.py")
    logger.info("")


if __name__ == "__main__":
    try:
        start_time = time.time()
        main()
        elapsed = time.time() - start_time
        logger.info(f"Total execution time: {elapsed/60:.1f} minutes")
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Process cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n❌ Process failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
