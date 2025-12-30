# webapp/data_manager.py
# PURPOSE: Handles data movement between Master DB (Postgres), Working DB (SQLite),
#          and the Application (Pandas DataFrames).

import os
import pandas as pd
import logging
from datetime import datetime
from sqlalchemy import text, select, and_, func
from sqlalchemy.orm import Session

# Import project config - use production config in cloud environments
if os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_ENVIRONMENT_NAME') or os.getenv('PRODUCTION'):
    import config_production as config_v6
else:
    import config_v6
from models_v6 import Asset, AssetPrice, Base

# Setup Logging
logger = logging.getLogger("DataManager")

class DataManager:
    # Asset Type to Portfolio Group Mapping
    ASSET_TYPE_TO_GROUP = {
        'Common Stock': 'Equities',
        'Preferred Stock': 'Equities',
        'ETF': 'Funds',
        'FUND': 'Funds',
        'INDEX': 'Funds',
        'Closed-End Fund': 'Funds',
        'BOND': 'Fixed Income',
        'REIT': 'Real Estate',
        'Unit': 'Other',
        'Right': 'Other',
        'Warrant': 'Other',
    }
    
    def __init__(self):
        # We maintain two engines:
        # 1. READ-ONLY connection to Master (Postgres)
        self.pg_engine = config_v6.get_postgres_engine()
        # 2. READ-WRITE connection to Cache (SQLite)
        self.sqlite_engine = config_v6.get_sqlite_engine()
        
        # Initialize SQLite tables if they don't exist
        self._init_sqlite_tables()

    def _init_sqlite_tables(self):
        """Create SQLite cache tables if they don't exist"""
        try:
            Base.metadata.create_all(self.sqlite_engine)
            logger.info("SQLite cache tables initialized")
        except Exception as e:
            logger.warning(f"Could not initialize SQLite tables: {e}")

    def _get_postgres_session(self):
        return Session(self.pg_engine)

    def _get_sqlite_session(self):
        return Session(self.sqlite_engine)

    def ensure_tickers_in_cache(self, tickers):
        """
        Checks if tickers exist in SQLite. If not, fetches them from Postgres.
        Returns list of tickers that were successfully found/synced.
        """
        valid_tickers = []
        missing_in_cache = []

        # 1. Check SQLite Cache
        with self._get_sqlite_session() as session:
            existing = session.query(Asset.symbol).filter(Asset.symbol.in_(tickers)).all()
            existing_symbols = {r[0] for r in existing}
            
            for t in tickers:
                if t in existing_symbols:
                    valid_tickers.append(t)
                else:
                    missing_in_cache.append(t)

        if not missing_in_cache:
            return valid_tickers

        # 2. Fetch Missing from Postgres
        logger.info(f"Fetching {len(missing_in_cache)} tickers from Master DB...")
        
        with self._get_postgres_session() as pg_session:
            # Get Asset Metadata
            assets = pg_session.query(Asset).filter(Asset.symbol.in_(missing_in_cache)).all()
            
            if not assets:
                logger.warning(f"Tickers not found in Master DB: {missing_in_cache}")
                return valid_tickers

            # Get Price History (All available history)
            found_symbols = [a.symbol for a in assets]
            
            prices = pg_session.query(AssetPrice)\
                .filter(AssetPrice.symbol.in_(found_symbols))\
                .order_by(AssetPrice.date).all()

            # 3. Write to SQLite Cache
            with self._get_sqlite_session() as sqlite_session:
                try:
                    # Insert Assets
                    for asset in assets:
                        new_asset = Asset(
                            symbol=asset.symbol, code=asset.code, exchange=asset.exchange,
                            name=asset.name, asset_type=asset.asset_type, currency=asset.currency,
                            is_active=True, is_in_working_db=True
                        )
                        sqlite_session.merge(new_asset) 

                    # Insert Prices (Bulk insert is faster)
                    price_mappings = []
                    for p in prices:
                        price_mappings.append({
                            'symbol': p.symbol,
                            'date': p.date,
                            'close': p.close,
                            'adjusted_close': p.adjusted_close,
                            'volume': p.volume
                        })
                    
                    if price_mappings:
                        sqlite_session.execute(
                            AssetPrice.__table__.insert(),
                            price_mappings
                        )
                    
                    sqlite_session.commit()
                    valid_tickers.extend(found_symbols)
                    logger.info(f"Successfully cached {len(found_symbols)} tickers.")
                    
                except Exception as e:
                    sqlite_session.rollback()
                    logger.error(f"Failed to cache data: {e}")

        return valid_tickers

    def get_ticker_coverage(self, tickers):
        """
        Returns the min/max date for each ticker in the SQLite cache.
        Used to validate if the user's start_date is safe.
        """
        self.ensure_tickers_in_cache(tickers)
        coverage = {}
        
        with self._get_sqlite_session() as session:
            # ORM Query: Group by symbol, get Min/Max date
            results = session.query(
                AssetPrice.symbol,
                func.min(AssetPrice.date),
                func.max(AssetPrice.date)
            ).filter(
                AssetPrice.symbol.in_(tickers)
            ).group_by(AssetPrice.symbol).all()
            
            for row in results:
                sym, min_val, max_val = row
                start_date = self._parse_date(min_val)
                end_date = self._parse_date(max_val)
                
                if start_date and end_date:
                    coverage[sym] = {'start': start_date, 'end': end_date}
                    
        return coverage

    def _parse_date(self, val):
        """Helper to safely ensure we have a python date object"""
        if val is None: return None
        if hasattr(val, 'date'): return val.date()
        if isinstance(val, str):
            try: return datetime.strptime(val[:10], '%Y-%m-%d').date()
            except: pass
        return val

    def get_price_history(self, tickers, start_date=None, end_date=None):
        """
        Returns a Pandas DataFrame of Adjusted Close prices.
        Index: Date, Columns: Tickers
        
        FIX: Uses Pure ORM to avoid SQLAlchemy 2.0 list-parameter crashes.
        """
        valid_tickers = self.ensure_tickers_in_cache(tickers)
        if not valid_tickers:
            return pd.DataFrame()
        
        try:
            with self._get_sqlite_session() as session:
                # 1. Build Query using ORM (Safe)
                query = session.query(
                    AssetPrice.date, 
                    AssetPrice.symbol, 
                    AssetPrice.adjusted_close
                ).filter(
                    AssetPrice.symbol.in_(valid_tickers)
                )
                
                # 2. Apply Date Filters
                if start_date:
                    query = query.filter(AssetPrice.date >= start_date)
                if end_date:
                    query = query.filter(AssetPrice.date <= end_date)
                
                query = query.order_by(AssetPrice.date)
                
                # 3. Execute and fetch all rows
                # Returns list of tuples: [(date, symbol, price), ...]
                data = query.all()
                
                if not data:
                    return pd.DataFrame()

                # 4. Convert to DataFrame
                df = pd.DataFrame(data, columns=['date', 'symbol', 'adjusted_close'])
                
                # 5. Pivot to Wide Format
                pivot_df = df.pivot(index='date', columns='symbol', values='adjusted_close')
                
                # 6. Clean Data
                pivot_df.fillna(method='ffill', inplace=True)
                pivot_df.dropna(inplace=True)
                
                return pivot_df
                
        except Exception as e:
            logger.error(f"Error building dataframe: {e}")
            return pd.DataFrame()

    def get_asset_metadata(self, tickers):
        """
        Returns asset metadata including group classification.
        Returns: dict {ticker: {'name': str, 'asset_type': str, 'group': str}}
        """
        self.ensure_tickers_in_cache(tickers)
        metadata = {}
        
        with self._get_sqlite_session() as session:
            assets = session.query(Asset).filter(Asset.symbol.in_(tickers)).all()
            
            for asset in assets:
                # Map database asset_type to portfolio group
                group = self.ASSET_TYPE_TO_GROUP.get(asset.asset_type, 'Other')
                
                metadata[asset.symbol] = {
                    'name': asset.name or asset.symbol,
                    'asset_type': asset.asset_type,
                    'group': group,
                    'exchange': asset.exchange,
                    'currency': asset.currency
                }
        
        return metadata

# Singleton Instance
data_manager = DataManager()
