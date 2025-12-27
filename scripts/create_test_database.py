# Create Test Database - Safe Copy of Production Data
# Copies 1% of tickers (prioritizing US markets) for testing refresh scripts

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models_v6 import Base, Asset, AssetPrice
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# HARDCODED - Production database (NEVER changes)
PROD_DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'portfolio_master',  # ALWAYS production
    'user': 'postgres',
    'password': 'Germany11',
}

# Test database connection
TEST_DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'portfolio_master_test',  # NEW test database
    'user': 'postgres',
    'password': 'Germany11',
}

PROD_PG_CONNECTION = (
    f"postgresql://{PROD_DB_CONFIG['user']}:{PROD_DB_CONFIG['password']}"
    f"@{PROD_DB_CONFIG['host']}:{PROD_DB_CONFIG['port']}/{PROD_DB_CONFIG['database']}"
)

TEST_PG_CONNECTION = (
    f"postgresql://{TEST_DB_CONFIG['user']}:{TEST_DB_CONFIG['password']}"
    f"@{TEST_DB_CONFIG['host']}:{TEST_DB_CONFIG['port']}/{TEST_DB_CONFIG['database']}"
)

@contextmanager
def get_session(engine):
    """Session context manager"""
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

# Sample size configuration
TARGET_TICKERS = 1650  # ~1% of 165k tickers
US_MARKET_PERCENTAGE = 70  # 70% US tickers, 30% international

def create_test_database():
    """Create empty test database with same schema"""
    logger.info("=" * 70)
    logger.info("STEP 1: Creating Test Database")
    logger.info("=" * 70)
    
    # Connect to postgres (default db) to create new database
    master_engine = create_engine(
        f"postgresql://{TEST_DB_CONFIG['user']}:{TEST_DB_CONFIG['password']}"
        f"@{TEST_DB_CONFIG['host']}:{TEST_DB_CONFIG['port']}/postgres",
        isolation_level="AUTOCOMMIT"
    )
    
    with master_engine.connect() as conn:
        # Terminate existing connections to test database
        conn.execute(text(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{TEST_DB_CONFIG['database']}'
            AND pid <> pg_backend_pid()
        """))
        logger.info(f"✅ Terminated existing connections to test database")
        
        # Drop if exists
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_CONFIG['database']}"))
        logger.info(f"✅ Dropped old test database (if existed)")
        
        # Create new
        conn.execute(text(f"CREATE DATABASE {TEST_DB_CONFIG['database']}"))
        logger.info(f"✅ Created new test database: {TEST_DB_CONFIG['database']}")
    
    master_engine.dispose()
    
    # Create tables in test database
    test_engine = create_engine(TEST_PG_CONNECTION)
    Base.metadata.create_all(test_engine)
    logger.info(f"✅ Created all tables in test database")
    logger.info("")
    
    return test_engine


def select_test_tickers(prod_engine):
    """Select diverse sample of tickers prioritizing US markets"""
    logger.info("=" * 70)
    logger.info("STEP 2: Selecting Test Tickers")
    logger.info("=" * 70)
    
    us_target = int(TARGET_TICKERS * US_MARKET_PERCENTAGE / 100)
    intl_target = TARGET_TICKERS - us_target
    
    selected_tickers = []
    
    with get_session(prod_engine) as session:
        # Get US tickers (prioritize those with price data)
        us_tickers = session.query(AssetPrice.symbol.distinct()).join(
            Asset, Asset.symbol == AssetPrice.symbol
        ).filter(
            Asset.exchange == 'US',
            Asset.is_active == True
        ).limit(us_target).all()
        
        us_list = [t[0] for t in us_tickers]
        selected_tickers.extend(us_list)
        logger.info(f"✅ Selected {len(us_list):,} US tickers")
        
        # Get international tickers (diverse exchanges)
        intl_exchanges = ['LSE', 'XETRA', 'TO', 'HK', 'PA', 'AS', 'TW', 'AU']
        per_exchange = intl_target // len(intl_exchanges)
        
        for exchange in intl_exchanges:
            exchange_tickers = session.query(AssetPrice.symbol.distinct()).join(
                Asset, Asset.symbol == AssetPrice.symbol
            ).filter(
                Asset.exchange == exchange,
                Asset.is_active == True
            ).limit(per_exchange).all()
            
            exchange_list = [t[0] for t in exchange_tickers]
            selected_tickers.extend(exchange_list)
        
        logger.info(f"✅ Selected {intl_target:,} international tickers from {len(intl_exchanges)} exchanges")
        logger.info(f"📊 Total tickers selected: {len(selected_tickers):,}")
        logger.info("")
    
    return selected_tickers


def copy_assets(prod_engine, test_engine, ticker_list):
    """Copy asset metadata for selected tickers"""
    logger.info("=" * 70)
    logger.info("STEP 3: Copying Asset Metadata")
    logger.info("=" * 70)
    
    with get_session(prod_engine) as prod_session:
        assets = prod_session.query(Asset).filter(
            Asset.symbol.in_(ticker_list)
        ).all()
        
        with get_session(test_engine) as test_session:
            for asset in assets:
                # Create new asset object (detached from prod session)
                test_asset = Asset(
                    symbol=asset.symbol,
                    code=asset.code,
                    exchange=asset.exchange,
                    name=asset.name,
                    asset_type=asset.asset_type,
                    isin=asset.isin,
                    currency=asset.currency,
                    country=asset.country,
                    is_active=asset.is_active,
                    is_in_working_db=asset.is_in_working_db,
                    data_source=asset.data_source,
                    first_seen=asset.first_seen,
                    last_updated=asset.last_updated,
                    last_price_date=asset.last_price_date
                )
                test_session.add(test_asset)
            
            test_session.commit()
            logger.info(f"✅ Copied {len(assets):,} asset records")
            logger.info("")


def copy_price_data(prod_engine, test_engine, ticker_list):
    """Copy price data for selected tickers"""
    logger.info("=" * 70)
    logger.info("STEP 4: Copying Price Data (This may take a few minutes)")
    logger.info("=" * 70)
    
    total_rows = 0
    batch_size = 50  # Process 50 tickers at a time
    
    for i in range(0, len(ticker_list), batch_size):
        batch = ticker_list[i:i + batch_size]
        
        with get_session(prod_engine) as prod_session:
            prices = prod_session.query(AssetPrice).filter(
                AssetPrice.symbol.in_(batch)
            ).all()
            
            with get_session(test_engine) as test_session:
                for price in prices:
                    test_price = AssetPrice(
                        symbol=price.symbol,
                        date=price.date,
                        open=price.open,
                        high=price.high,
                        low=price.low,
                        close=price.close,
                        adjusted_close=price.adjusted_close,
                        volume=price.volume,
                        dividend=price.dividend,
                        is_validated=price.is_validated,
                        has_quality_issues=price.has_quality_issues,
                        data_source=price.data_source,
                        loaded_at=price.loaded_at
                    )
                    test_session.add(test_price)
                    total_rows += 1
                
                test_session.commit()
        
        if (i // batch_size + 1) % 10 == 0:
            logger.info(f"  Progress: {i + len(batch):,}/{len(ticker_list):,} tickers | {total_rows:,} price records")
    
    logger.info(f"✅ Copied {total_rows:,} price records")
    logger.info("")


def verify_test_database(test_engine):
    """Verify test database integrity"""
    logger.info("=" * 70)
    logger.info("STEP 5: Verifying Test Database")
    logger.info("=" * 70)
    
    with get_session(test_engine) as session:
        asset_count = session.query(Asset).count()
        price_count = session.query(AssetPrice).count()
        
        if asset_count == 0:
            logger.warning("⚠️  No assets copied - check production database has data")
            return
        
        # Count by exchange
        us_count = session.query(Asset).filter(Asset.exchange == 'US').count()
        
        # Get date range
        min_date = session.query(func.min(AssetPrice.date)).scalar()
        max_date = session.query(func.max(AssetPrice.date)).scalar()
        
        logger.info(f"📊 Test Database Statistics:")
        logger.info(f"  Total assets: {asset_count:,}")
        us_pct = (us_count/asset_count*100) if asset_count > 0 else 0
        logger.info(f"  US assets: {us_count:,} ({us_pct:.1f}%)")
        logger.info(f"  International assets: {asset_count - us_count:,}")
        logger.info(f"  Total price records: {price_count:,}")
        logger.info(f"  Date range: {min_date} to {max_date}")
        avg_records = price_count/asset_count if asset_count > 0 else 0
        logger.info(f"  Avg records per ticker: {avg_records:.0f}")
        logger.info("")
        
        # Sample verification
        logger.info("📋 Sample Tickers in Test Database:")
        samples = session.query(Asset.symbol, Asset.exchange, Asset.name).limit(10).all()
        for symbol, exchange, name in samples:
            logger.info(f"  {symbol:15} | {exchange:8} | {name[:40]}")
        logger.info("")


def main():
    """Main execution"""
    logger.info("\n")
    logger.info("🧪 TEST DATABASE BUILDER")
    logger.info("Creating safe copy of production data for testing refresh scripts")
    logger.info("\n")
    
    # Connect to production (HARDCODED - ignores config_v6)
    prod_engine = create_engine(PROD_PG_CONNECTION)
    logger.info(f"✅ Connected to production: {PROD_DB_CONFIG['database']}")
    logger.info("")
    
    # Build test database
    test_engine = create_test_database()
    
    # Select tickers
    ticker_list = select_test_tickers(prod_engine)
    
    if not ticker_list:
        logger.error("❌ No tickers selected - production database may be empty")
        return
    
    # Copy data
    copy_assets(prod_engine, test_engine, ticker_list)
    copy_price_data(prod_engine, test_engine, ticker_list)
    
    # Verify
    verify_test_database(test_engine)
    
    # Cleanup connections
    prod_engine.dispose()
    test_engine.dispose()
    
    # Final summary
    logger.info("=" * 70)
    logger.info("✅ TEST DATABASE CREATION COMPLETE!")
    logger.info("=" * 70)
    logger.info("")
    logger.info("📌 NEXT STEPS:")
    logger.info("  1. Update config_v6.py to point to test database:")
    logger.info("     POSTGRES_CONFIG['database'] = 'portfolio_master_test'")
    logger.info("")
    logger.info("  2. Run your refresh script (02b) against test database")
    logger.info("")
    logger.info("  3. Verify results, iterate until confident")
    logger.info("")
    logger.info("  4. Switch back to production:")
    logger.info("     POSTGRES_CONFIG['database'] = 'portfolio_master'")
    logger.info("")
    logger.info("🛡️  Your production database remains untouched!")
    logger.info("")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()