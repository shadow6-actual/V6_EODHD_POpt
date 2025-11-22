# Script 04: Materialize SQLite - Create Fast Working Database
# Copies your portfolio tickers from PostgreSQL to SQLite

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_v6
from models_v6 import Asset, AssetPrice, CorporateActions, AssetFundamentals, AssetClassification, get_session

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config_v6.LOGS_DIR / "materialize_sqlite.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_tickers_to_materialize():
    """
    Get list of tickers that should be in the working database
    
    Returns:
        Set of ticker symbols
    """
    tickers = set()
    
    # Add your portfolio
    tickers.update(config_v6.MY_PORTFOLIO_TICKERS)
    
    # Add your watchlist
    tickers.update(config_v6.MY_WATCHLIST_TICKERS)
    
    # Add benchmark tickers
    tickers.update(config_v6.BENCHMARK_TICKERS)
    
    logger.info(f"📊 Tickers to materialize:")
    logger.info(f"  Portfolio: {len(config_v6.MY_PORTFOLIO_TICKERS)}")
    logger.info(f"  Watchlist: {len(config_v6.MY_WATCHLIST_TICKERS)}")
    logger.info(f"  Benchmarks: {len(config_v6.BENCHMARK_TICKERS)}")
    logger.info(f"  Total: {len(tickers)}")
    
    return tickers


def copy_asset(pg_session, sqlite_session, symbol):
    """Copy asset and related data from PostgreSQL to SQLite"""
    try:
        # Get asset from PostgreSQL
        pg_asset = pg_session.query(Asset).filter_by(symbol=symbol).first()
        
        if not pg_asset:
            logger.warning(f"  ⚠️  {symbol} not found in PostgreSQL")
            return False
        
        # Check if already exists in SQLite
        sqlite_asset = sqlite_session.query(Asset).filter_by(symbol=symbol).first()
        
        if sqlite_asset:
            logger.debug(f"  ↻ {symbol} already in SQLite, updating...")
            # Update existing
            sqlite_asset.name = pg_asset.name
            sqlite_asset.asset_type = pg_asset.asset_type
            sqlite_asset.is_active = pg_asset.is_active
            sqlite_asset.last_updated = datetime.utcnow()
        else:
            # Create new
            sqlite_asset = Asset(
                symbol=pg_asset.symbol,
                code=pg_asset.code,
                exchange=pg_asset.exchange,
                name=pg_asset.name,
                asset_type=pg_asset.asset_type,
                isin=pg_asset.isin,
                currency=pg_asset.currency,
                country=pg_asset.country,
                is_active=pg_asset.is_active,
                is_in_working_db=True,
                first_seen=pg_asset.first_seen,
                last_updated=datetime.utcnow(),
                last_price_date=pg_asset.last_price_date,
                data_source=pg_asset.data_source
            )
            sqlite_session.add(sqlite_asset)
        
        sqlite_session.flush()
        
        # Copy price data
        pg_prices = pg_session.query(AssetPrice).filter_by(symbol=symbol).all()
        
        if pg_prices:
            logger.info(f"  📈 {symbol}: {len(pg_prices):,} price records")
            
            # Delete existing prices in SQLite
            sqlite_session.query(AssetPrice).filter_by(symbol=symbol).delete()
            
            # Insert new prices
            for pg_price in pg_prices:
                sqlite_price = AssetPrice(
                    symbol=pg_price.symbol,
                    date=pg_price.date,
                    open=pg_price.open,
                    high=pg_price.high,
                    low=pg_price.low,
                    close=pg_price.close,
                    adjusted_close=pg_price.adjusted_close,
                    volume=pg_price.volume,
                    dividend=pg_price.dividend,
                    is_validated=pg_price.is_validated,
                    data_source=pg_price.data_source,
                    loaded_at=pg_price.loaded_at
                )
                sqlite_session.add(sqlite_price)
            
            # Commit prices in batches
            if len(pg_prices) % 500 == 0:
                sqlite_session.commit()
        
        # Copy corporate actions
        pg_actions = pg_session.query(CorporateActions).filter_by(symbol=symbol).all()
        
        if pg_actions:
            logger.info(f"  💰 {symbol}: {len(pg_actions)} corporate actions")
            
            # Delete existing in SQLite
            sqlite_session.query(CorporateActions).filter_by(symbol=symbol).delete()
            
            # Insert new
            for pg_action in pg_actions:
                sqlite_action = CorporateActions(
                    symbol=pg_action.symbol,
                    action_date=pg_action.action_date,
                    action_type=pg_action.action_type,
                    split_ratio=pg_action.split_ratio,
                    split_from=pg_action.split_from,
                    split_to=pg_action.split_to,
                    dividend_amount=pg_action.dividend_amount,
                    dividend_currency=pg_action.dividend_currency,
                    ex_dividend_date=pg_action.ex_dividend_date,
                    record_date=pg_action.record_date,
                    payment_date=pg_action.payment_date,
                    declaration_date=pg_action.declaration_date,
                    details=pg_action.details,
                    data_source=pg_action.data_source
                )
                sqlite_session.add(sqlite_action)
        
        # Copy fundamentals (if exists)
        pg_fundamentals = pg_session.query(AssetFundamentals).filter_by(symbol=symbol).first()
        
        if pg_fundamentals:
            sqlite_fundamentals = sqlite_session.query(AssetFundamentals).filter_by(symbol=symbol).first()
            
            if sqlite_fundamentals:
                # Update existing
                sqlite_fundamentals.beta = pg_fundamentals.beta
                sqlite_fundamentals.volatility_1y = pg_fundamentals.volatility_1y
                # ... copy other fields
            else:
                # Create new
                sqlite_fundamentals = AssetFundamentals(
                    symbol=pg_fundamentals.symbol,
                    market_cap=pg_fundamentals.market_cap,
                    beta=pg_fundamentals.beta,
                    volatility_30d=pg_fundamentals.volatility_30d,
                    volatility_90d=pg_fundamentals.volatility_90d,
                    volatility_1y=pg_fundamentals.volatility_1y,
                    average_volume_30d=pg_fundamentals.average_volume_30d,
                    dividend_yield_ttm=pg_fundamentals.dividend_yield_ttm,
                    last_calculated=pg_fundamentals.last_calculated
                )
                sqlite_session.add(sqlite_fundamentals)
        
        # Copy classification (if exists)
        pg_classification = pg_session.query(AssetClassification).filter_by(symbol=symbol).first()
        
        if pg_classification:
            sqlite_classification = sqlite_session.query(AssetClassification).filter_by(symbol=symbol).first()
            
            if sqlite_classification:
                # Update
                sqlite_classification.asset_class = pg_classification.asset_class
                sqlite_classification.sector = pg_classification.sector
                # ... copy other fields
            else:
                # Create new
                sqlite_classification = AssetClassification(
                    symbol=pg_classification.symbol,
                    asset_class=pg_classification.asset_class,
                    asset_subclass=pg_classification.asset_subclass,
                    geography=pg_classification.geography,
                    sector=pg_classification.sector,
                    last_updated=pg_classification.last_updated
                )
                sqlite_session.add(sqlite_classification)
        
        # Commit all changes for this ticker
        sqlite_session.commit()
        
        return True
        
    except Exception as e:
        logger.error(f"  ❌ Error copying {symbol}: {e}")
        sqlite_session.rollback()
        return False


def materialize_working_database(rebuild=False):
    """
    Copy tickers from PostgreSQL to SQLite working database
    
    Args:
        rebuild: If True, delete and rebuild entire SQLite database
    """
    logger.info("=" * 70)
    logger.info("MATERIALIZING SQLITE WORKING DATABASE")
    logger.info("=" * 70)
    logger.info("")
    
    # Get engines
    pg_engine = config_v6.get_postgres_engine()
    sqlite_engine = config_v6.get_sqlite_engine()
    
    if rebuild:
        logger.info("🗑️  Rebuilding SQLite database from scratch...")
        from models_v6 import Base
        Base.metadata.drop_all(sqlite_engine)
        Base.metadata.create_all(sqlite_engine)
        logger.info("✅ SQLite database rebuilt")
        logger.info("")
    
    # Get tickers to materialize
    tickers = get_tickers_to_materialize()
    
    if not tickers:
        logger.warning("⚠️  No tickers to materialize!")
        logger.info("   Edit config_v6.py and add tickers to:")
        logger.info("   - MY_PORTFOLIO_TICKERS")
        logger.info("   - MY_WATCHLIST_TICKERS")
        return
    
    logger.info(f"\n📦 Starting materialization of {len(tickers)} tickers...")
    logger.info("")
    
    # Copy each ticker
    success_count = 0
    fail_count = 0
    
    with get_session(pg_engine) as pg_session:
        with get_session(sqlite_engine) as sqlite_session:
            for i, symbol in enumerate(sorted(tickers), 1):
                logger.info(f"[{i}/{len(tickers)}] {symbol}")
                
                if copy_asset(pg_session, sqlite_session, symbol):
                    success_count += 1
                else:
                    fail_count += 1
                
                # Progress update every 10 tickers
                if i % 10 == 0:
                    logger.info(f"  Progress: {i}/{len(tickers)} ({success_count} success, {fail_count} failed)")
                    logger.info("")
    
    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("✅ MATERIALIZATION COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Successfully copied: {success_count}")
    logger.info(f"Failed: {fail_count}")
    logger.info(f"SQLite database: {config_v6.SQLITE_DB_PATH}")
    
    # Get database size
    if config_v6.SQLITE_DB_PATH.exists():
        size_mb = config_v6.SQLITE_DB_PATH.stat().st_size / (1024 * 1024)
        logger.info(f"Database size: {size_mb:.1f} MB")
    
    logger.info("")
    logger.info("🎯 Your working database is ready!")
    logger.info("   Use this for your Portfolio Visualizer and analysis tools")
    logger.info("")


def add_single_ticker(symbol: str):
    """
    Add a single ticker to the working database on-demand
    
    Args:
        symbol: Ticker symbol (e.g., 'AAPL.US')
    """
    logger.info(f"📥 Adding {symbol} to working database...")
    
    pg_engine = config_v6.get_postgres_engine()
    sqlite_engine = config_v6.get_sqlite_engine()
    
    with get_session(pg_engine) as pg_session:
        with get_session(sqlite_engine) as sqlite_session:
            success = copy_asset(pg_session, sqlite_session, symbol)
    
    if success:
        logger.info(f"✅ {symbol} added successfully")
    else:
        logger.error(f"❌ Failed to add {symbol}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Materialize SQLite working database')
    parser.add_argument('--rebuild', action='store_true', help='Rebuild database from scratch')
    parser.add_argument('--add', type=str, help='Add single ticker (e.g., NVDA.US)')
    
    args = parser.parse_args()
    
    if args.add:
        add_single_ticker(args.add)
    else:
        materialize_working_database(rebuild=args.rebuild)


if __name__ == "__main__":
    try:
        start_time = time.time()
        main()
        elapsed = time.time() - start_time
        logger.info(f"Execution time: {elapsed:.1f} seconds")
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Process cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n❌ Process failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
