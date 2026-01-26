# webapp/data_updater.py
# PURPOSE: Auto-update price data from EODHD API for Railway deployment
# Designed for: 500 tickers (testing) scaling to 167K (production)

import os
import logging
import requests
import threading
import time
from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional, Dict
from contextlib import contextmanager

from sqlalchemy import func, and_, create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger("DataUpdater")

# ============================================================================
# CONFIGURATION
# ============================================================================

# EODHD API Configuration
EODHD_API_TOKEN = os.environ.get('EODHD_API_TOKEN')
EODHD_BASE_URL = "https://eodhd.com/api"

# Update Settings
STALE_DATA_DAYS = 7           # Data older than this needs refresh
BATCH_SIZE = 100              # Tickers per batch (conservative for Railway)
API_RATE_LIMIT_DELAY = 0.5    # Seconds between API calls
MAX_DAILY_UPDATES = 5000      # Max tickers to update per day (stay under API limits)

# Background update settings
UPDATE_INTERVAL_HOURS = 6     # How often to check for updates
UPDATE_ENABLED = True         # Master switch


# ============================================================================
# DATABASE HELPERS
# ============================================================================

def get_database_url():
    """Get database URL from environment"""
    return os.environ.get('DATABASE_URL')


@contextmanager
def get_db_session():
    """Create a database session"""
    engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()


# ============================================================================
# EODHD API FUNCTIONS
# ============================================================================

def fetch_ticker_prices(symbol: str, from_date: str, to_date: str) -> Tuple[Optional[List[Dict]], str]:
    """
    Fetch historical prices for a single ticker from EODHD.
    
    Args:
        symbol: Ticker symbol (e.g., 'AAPL.US')
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        
    Returns:
        Tuple of (data_list, status) where status is:
        - 'ok': Success with data
        - 'no_data': API returned empty
        - 'paywall': 402 subscription issue
        - 'not_found': 404 symbol not found
        - 'error': Other error
    """
    if not EODHD_API_TOKEN:
        logger.error("EODHD_API_TOKEN not configured!")
        return None, 'error'
    
    try:
        url = f"{EODHD_BASE_URL}/eod/{symbol}"
        params = {
            'api_token': EODHD_API_TOKEN,
            'from': from_date,
            'to': to_date,
            'fmt': 'json',
            'period': 'd'
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return data, 'ok'
            return None, 'no_data'
        elif response.status_code == 402:
            return None, 'paywall'
        elif response.status_code == 404:
            return None, 'not_found'
        else:
            logger.warning(f"API returned {response.status_code} for {symbol}")
            return None, 'error'
            
    except requests.Timeout:
        logger.warning(f"Timeout fetching {symbol}")
        return None, 'error'
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return None, 'error'


# ============================================================================
# UPDATE FUNCTIONS
# ============================================================================

def get_stale_tickers(limit: int = BATCH_SIZE) -> List[Dict]:
    """
    Get tickers that haven't been updated recently.
    
    Returns list of dicts with 'symbol' and 'latest_date'
    """
    stale_cutoff = date.today() - timedelta(days=STALE_DATA_DAYS)
    
    with get_db_session() as session:
        # Get symbols with their latest price date
        result = session.execute(text("""
            SELECT 
                ap.symbol,
                MAX(ap.date) as latest_date
            FROM asset_prices ap
            JOIN assets a ON ap.symbol = a.symbol
            WHERE a.is_active = true
            GROUP BY ap.symbol
            HAVING MAX(ap.date) < :cutoff
            ORDER BY MAX(ap.date) ASC
            LIMIT :limit
        """), {'cutoff': stale_cutoff, 'limit': limit})
        
        return [{'symbol': row[0], 'latest_date': row[1]} for row in result]


def get_update_statistics() -> Dict:
    """Get current data freshness statistics"""
    with get_db_session() as session:
        # Total active assets
        total_assets = session.execute(text("""
            SELECT COUNT(*) FROM assets WHERE is_active = true
        """)).scalar() or 0
        
        # Assets with price data
        assets_with_data = session.execute(text("""
            SELECT COUNT(DISTINCT symbol) FROM asset_prices
        """)).scalar() or 0
        
        # Stale assets (not updated in STALE_DATA_DAYS)
        stale_cutoff = date.today() - timedelta(days=STALE_DATA_DAYS)
        stale_count = session.execute(text("""
            SELECT COUNT(DISTINCT ap.symbol)
            FROM asset_prices ap
            JOIN assets a ON ap.symbol = a.symbol
            WHERE a.is_active = true
            GROUP BY ap.symbol
            HAVING MAX(ap.date) < :cutoff
        """), {'cutoff': stale_cutoff}).scalar() or 0
        
        # Total price records
        total_prices = session.execute(text("""
            SELECT COUNT(*) FROM asset_prices
        """)).scalar() or 0
        
        # Most recent update
        latest_date = session.execute(text("""
            SELECT MAX(date) FROM asset_prices
        """)).scalar()
        
        return {
            'total_assets': total_assets,
            'assets_with_data': assets_with_data,
            'stale_assets': stale_count,
            'total_price_records': total_prices,
            'latest_price_date': str(latest_date) if latest_date else None,
            'stale_cutoff_days': STALE_DATA_DAYS
        }


def update_single_ticker(symbol: str, from_date: date) -> Tuple[int, bool]:
    """
    Update prices for a single ticker from a given date.
    
    Returns (records_inserted, success)
    """
    to_date = date.today()
    
    data, status = fetch_ticker_prices(
        symbol,
        from_date.strftime('%Y-%m-%d'),
        to_date.strftime('%Y-%m-%d')
    )
    
    if status != 'ok' or not data:
        return 0, False
    
    records_inserted = 0
    
    with get_db_session() as session:
        for record in data:
            try:
                price_date = datetime.strptime(record.get('date'), '%Y-%m-%d').date()
                
                # Check if exists
                existing = session.execute(text("""
                    SELECT 1 FROM asset_prices 
                    WHERE symbol = :symbol AND date = :date
                """), {'symbol': symbol, 'date': price_date}).first()
                
                if existing:
                    # Update existing
                    session.execute(text("""
                        UPDATE asset_prices SET
                            open = :open,
                            high = :high,
                            low = :low,
                            close = :close,
                            adjusted_close = :adj_close,
                            volume = :volume,
                            loaded_at = NOW()
                        WHERE symbol = :symbol AND date = :date
                    """), {
                        'symbol': symbol,
                        'date': price_date,
                        'open': record.get('open'),
                        'high': record.get('high'),
                        'low': record.get('low'),
                        'close': record.get('close'),
                        'adj_close': record.get('adjusted_close'),
                        'volume': record.get('volume')
                    })
                else:
                    # Insert new
                    session.execute(text("""
                        INSERT INTO asset_prices 
                        (symbol, date, open, high, low, close, adjusted_close, volume, 
                         data_source, is_validated, loaded_at)
                        VALUES 
                        (:symbol, :date, :open, :high, :low, :close, :adj_close, :volume,
                         'EODHD', true, NOW())
                    """), {
                        'symbol': symbol,
                        'date': price_date,
                        'open': record.get('open'),
                        'high': record.get('high'),
                        'low': record.get('low'),
                        'close': record.get('close'),
                        'adj_close': record.get('adjusted_close'),
                        'volume': record.get('volume')
                    })
                    records_inserted += 1
                    
            except Exception as e:
                logger.debug(f"Error processing record for {symbol}: {e}")
                continue
        
        # Update asset's last_updated timestamp
        session.execute(text("""
            UPDATE assets SET last_updated = NOW() WHERE symbol = :symbol
        """), {'symbol': symbol})
    
    return records_inserted, True


def run_batch_update(batch_size: int = BATCH_SIZE) -> Dict:
    """
    Run a batch update of stale tickers.
    
    Returns statistics about the update.
    """
    start_time = time.time()
    
    stats = {
        'started_at': datetime.utcnow().isoformat(),
        'batch_size': batch_size,
        'attempted': 0,
        'successful': 0,
        'failed': 0,
        'records_added': 0,
        'errors': []
    }
    
    # Get stale tickers
    stale_tickers = get_stale_tickers(batch_size)
    
    if not stale_tickers:
        stats['message'] = 'No stale tickers found - all data is current!'
        return stats
    
    logger.info(f"Starting batch update of {len(stale_tickers)} tickers")
    
    for ticker_info in stale_tickers:
        symbol = ticker_info['symbol']
        latest_date = ticker_info['latest_date']
        from_date = latest_date + timedelta(days=1)
        
        stats['attempted'] += 1
        
        try:
            records, success = update_single_ticker(symbol, from_date)
            
            if success:
                stats['successful'] += 1
                stats['records_added'] += records
                logger.debug(f"Updated {symbol}: +{records} records")
            else:
                stats['failed'] += 1
                
        except Exception as e:
            stats['failed'] += 1
            stats['errors'].append({'symbol': symbol, 'error': str(e)})
            logger.error(f"Failed to update {symbol}: {e}")
        
        # Rate limiting
        time.sleep(API_RATE_LIMIT_DELAY)
    
    stats['duration_seconds'] = round(time.time() - start_time, 2)
    stats['completed_at'] = datetime.utcnow().isoformat()
    
    logger.info(f"Batch update complete: {stats['successful']}/{stats['attempted']} successful, "
                f"{stats['records_added']} records added in {stats['duration_seconds']}s")
    
    return stats


# ============================================================================
# BACKGROUND UPDATER
# ============================================================================

class BackgroundUpdater:
    """
    Background thread that periodically updates stale data.
    """
    
    def __init__(self):
        self.is_running = False
        self.thread = None
        self.last_run = None
        self.last_stats = None
        self.interval_hours = UPDATE_INTERVAL_HOURS
    
    def start(self):
        """Start the background updater"""
        if self.is_running:
            logger.warning("Background updater already running")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info(f"Background updater started (interval: {self.interval_hours}h)")
    
    def stop(self):
        """Stop the background updater"""
        self.is_running = False
        logger.info("Background updater stopped")
    
    def _run_loop(self):
        """Main loop for background updates"""
        while self.is_running:
            try:
                # Check if we should run (based on time since last run)
                if self.last_run:
                    hours_since = (datetime.utcnow() - self.last_run).total_seconds() / 3600
                    if hours_since < self.interval_hours:
                        time.sleep(60)  # Check again in 1 minute
                        continue
                
                logger.info("Background updater running scheduled update...")
                self.last_stats = run_batch_update(BATCH_SIZE)
                self.last_run = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Background updater error: {e}")
            
            # Sleep for a bit before checking again
            time.sleep(60)
    
    def get_status(self) -> Dict:
        """Get current status of the background updater"""
        return {
            'is_running': self.is_running,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'last_stats': self.last_stats,
            'interval_hours': self.interval_hours,
            'next_run_estimate': (
                (self.last_run + timedelta(hours=self.interval_hours)).isoformat()
                if self.last_run else 'Soon'
            )
        }


# Global instance
background_updater = BackgroundUpdater()


# ============================================================================
# MANUAL TRIGGER FUNCTIONS
# ============================================================================

def trigger_manual_update(batch_size: int = None) -> Dict:
    """
    Trigger a manual update (can be called via API endpoint).
    """
    if batch_size is None:
        batch_size = BATCH_SIZE
    
    return run_batch_update(batch_size)


def update_specific_tickers(symbols: List[str]) -> Dict:
    """
    Update specific tickers by symbol.
    """
    stats = {
        'started_at': datetime.utcnow().isoformat(),
        'tickers_requested': symbols,
        'successful': 0,
        'failed': 0,
        'records_added': 0
    }
    
    for symbol in symbols:
        # Get last date for this ticker
        with get_db_session() as session:
            result = session.execute(text("""
                SELECT MAX(date) FROM asset_prices WHERE symbol = :symbol
            """), {'symbol': symbol}).scalar()
        
        if result:
            from_date = result + timedelta(days=1)
        else:
            from_date = date.today() - timedelta(days=365 * 10)  # 10 years back
        
        records, success = update_single_ticker(symbol, from_date)
        
        if success:
            stats['successful'] += 1
            stats['records_added'] += records
        else:
            stats['failed'] += 1
        
        time.sleep(API_RATE_LIMIT_DELAY)
    
    stats['completed_at'] = datetime.utcnow().isoformat()
    return stats
