# Script 02D: Cleanup Invalid Symbols
# Removes obviously invalid symbols from the database
# Run this ONCE to clean up bad data before continuing batch loads

import sys
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_v6
from models_v6 import Asset, AssetPrice, get_session
from sqlalchemy import func

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config_v6.LOGS_DIR / "cleanup_invalid_symbols.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def find_invalid_cross_listings(session):
    """
    Find symbols that are obviously invalid cross-listings
    (e.g., US mega-caps listed on non-US exchanges)
    
    Returns:
        List of invalid Asset objects
    """
    # Major US tickers that should ONLY be on US exchange
    us_only_tickers = {
        'AAPL','MSFT','AMZN','GOOGL','GOOG','META','TSLA','NVDA','AMD',
        'NFLX','DIS','PYPL','INTC','CSCO','ADBE','CRM','ORCL','IBM',
        'QCOM','TXN','AVGO','SBUX','BA','COST','PEP','KO','MCD','WMT',
        'HD','UNH','JNJ','PFE','ABBV','LLY','MRK','TMO','CVX','XOM',
        'BRKB','V','MA','JPM','BAC','WFC','GS','MS','C','AXP',
        'SPY','QQQ','DIA','IWM','VTI','VOO','IVV'  # Major ETFs
    }
    
    invalid_assets = []
    
    # Find all active assets
    all_assets = session.query(Asset).filter_by(is_active=True).all()
    
    for asset in all_assets:
        # Check if this is a US ticker on a non-US exchange
        if asset.code in us_only_tickers and asset.exchange != 'US':
            invalid_assets.append(asset)
    
    return invalid_assets


def find_assets_without_data(session):
    """
    Find assets that have been loaded but have zero price records
    These are likely invalid or delisted
    
    Returns:
        List of Asset objects with no data
    """
    # Subquery: All symbols that have price data
    symbols_with_data = session.query(
        AssetPrice.symbol.distinct()
    ).subquery()
    
    # Assets that exist but have no prices
    assets_without_data = session.query(Asset).filter(
        Asset.is_active == True,
        ~Asset.symbol.in_(session.query(symbols_with_data))
    ).all()
    
    return assets_without_data


def find_very_short_codes(session):
    """
    Find assets with suspiciously short codes (1-2 characters)
    outside major exchanges where this is normal
    
    Returns:
        List of potentially invalid Assets
    """
    # Exchanges where 1-2 char codes are normal
    valid_short_code_exchanges = ['US', 'HK', 'AU', 'LSE', 'XETRA', 'TO']
    
    suspicious_assets = []
    
    all_assets = session.query(Asset).filter_by(is_active=True).all()
    
    for asset in all_assets:
        if asset.exchange not in valid_short_code_exchanges:
            if len(asset.code) <= 2:
                # Check if it has any data
                has_data = session.query(AssetPrice).filter_by(
                    symbol=asset.symbol
                ).count() > 0
                
                if not has_data:
                    suspicious_assets.append(asset)
    
    return suspicious_assets


def deactivate_assets(session, assets, reason):
    """
    Mark a list of assets as inactive
    
    Args:
        session: Database session
        assets: List of Asset objects to deactivate
        reason: Reason for deactivation (for logging)
    """
    if not assets:
        return 0
    
    count = 0
    for asset in assets:
        asset.is_active = False
        asset.last_updated = datetime.utcnow()
        count += 1
        
        if count % 100 == 0:
            session.commit()
            logger.info(f"  Deactivated {count}/{len(assets)} assets...")
    
    session.commit()
    return count


def main():
    """Main cleanup function"""
    logger.info("=" * 70)
    logger.info("DATABASE CLEANUP - REMOVING INVALID SYMBOLS")
    logger.info("=" * 70)
    logger.info("")
    
    engine = config_v6.get_postgres_engine()
    
    with get_session(engine) as session:
        # Get statistics before cleanup
        total_active = session.query(Asset).filter_by(is_active=True).count()
        logger.info(f"📊 Current Database State:")
        logger.info(f"  Active assets: {total_active:,}")
        logger.info("")
        
        # Find different types of invalid assets
        logger.info("🔍 Scanning for invalid symbols...")
        logger.info("")
        
        # 1. Invalid cross-listings
        logger.info("1️⃣  Checking for invalid cross-listings...")
        invalid_cross = find_invalid_cross_listings(session)
        logger.info(f"   Found: {len(invalid_cross):,} invalid cross-listings")
        
        if invalid_cross[:5]:  # Show first 5 examples
            logger.info("   Examples:")
            for asset in invalid_cross[:5]:
                logger.info(f"     - {asset.symbol} ({asset.name})")
        logger.info("")
        
        # 2. Very short codes on unusual exchanges
        logger.info("2️⃣  Checking for suspicious short codes...")
        short_codes = find_very_short_codes(session)
        logger.info(f"   Found: {len(short_codes):,} suspicious short-code symbols")
        
        if short_codes[:5]:
            logger.info("   Examples:")
            for asset in short_codes[:5]:
                logger.info(f"     - {asset.symbol} (code: '{asset.code}')")
        logger.info("")
        
        # Calculate total to remove
        # Deduplicate (an asset might be in multiple categories)
        all_invalid = list(set(invalid_cross + short_codes))
        
        logger.info(f"📋 Summary:")
        logger.info(f"  Total invalid symbols found: {len(all_invalid):,}")
        logger.info("")
        
        if not all_invalid:
            logger.info("✅ No invalid symbols found! Database is clean.")
            return
        
        # Confirm before proceeding
        logger.info("⚠️  These assets will be marked as INACTIVE (not deleted)")
        logger.info("   They will be skipped in future data loads")
        logger.info("")
        
        response = input("Proceed with cleanup? (yes/no): ").strip().lower()
        
        if response != 'yes':
            logger.info("❌ Cleanup cancelled by user")
            return
        
        # Deactivate invalid assets
        logger.info("")
        logger.info("🧹 Deactivating invalid assets...")
        deactivated = deactivate_assets(session, all_invalid, "Invalid symbol detected")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ CLEANUP COMPLETE")
        logger.info("=" * 70)
        logger.info(f"  Assets deactivated: {deactivated:,}")
        
        # Show updated statistics
        new_total_active = session.query(Asset).filter_by(is_active=True).count()
        logger.info(f"  Active assets remaining: {new_total_active:,}")
        logger.info(f"  Reduction: {total_active - new_total_active:,} assets")
        logger.info("")
        
        logger.info("💡 Next Steps:")
        logger.info("   1. Run: python scripts/02a_load_sample_historical.py")
        logger.info("   2. Invalid symbols will now be skipped automatically")
        logger.info("")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Cleanup cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n❌ Cleanup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
