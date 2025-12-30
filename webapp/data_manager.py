# webapp/data_manager.py
# PURPOSE: Direct PostgreSQL queries for production deployment
# All data (prices, assets, saved portfolios) stored in PostgreSQL

import os
import pandas as pd
import logging
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

# Import project config - use production config in cloud environments
if os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_ENVIRONMENT_NAME') or os.getenv('PRODUCTION'):
    import config_production as config_v6
else:
    import config_v6
from models_v6 import Asset, AssetPrice, Base, SavedPortfolio

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
        # Single PostgreSQL connection
        self.engine = config_v6.get_postgres_engine()
        # Alias for backward compatibility with app.py
        self.pg_engine = self.engine
        logger.info("DataManager initialized with PostgreSQL")

    def _get_session(self):
        """Get a PostgreSQL session"""
        return Session(self.engine)
    
    # Backward compatibility aliases
    def _get_postgres_session(self):
        return self._get_session()
    
    def _get_sqlite_session(self):
        """Redirects to PostgreSQL - SQLite not used in production"""
        return self._get_session()

    def get_ticker_coverage(self, tickers):
        """
        Returns the min/max date for each ticker.
        """
        coverage = {}
        
        try:
            with self._get_session() as session:
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
        except Exception as e:
            logger.error(f"Error getting ticker coverage: {e}")
                    
        return coverage

    def _parse_date(self, val):
        """Helper to safely ensure we have a python date object"""
        if val is None: 
            return None
        if hasattr(val, 'date'): 
            return val.date()
        if isinstance(val, str):
            try: 
                return datetime.strptime(val[:10], '%Y-%m-%d').date()
            except: 
                pass
        return val

    def get_price_history(self, tickers, start_date=None, end_date=None):
        """
        Returns a Pandas DataFrame of Adjusted Close prices.
        Index: Date, Columns: Tickers
        """
        if not tickers:
            return pd.DataFrame()
        
        try:
            with self._get_session() as session:
                query = session.query(
                    AssetPrice.date, 
                    AssetPrice.symbol, 
                    AssetPrice.adjusted_close
                ).filter(
                    AssetPrice.symbol.in_(tickers)
                )
                
                if start_date:
                    query = query.filter(AssetPrice.date >= start_date)
                if end_date:
                    query = query.filter(AssetPrice.date <= end_date)
                
                query = query.order_by(AssetPrice.date)
                
                data = query.all()
                
                if not data:
                    logger.warning(f"No price data found for tickers: {tickers}")
                    return pd.DataFrame()

                df = pd.DataFrame(data, columns=['date', 'symbol', 'adjusted_close'])
                pivot_df = df.pivot(index='date', columns='symbol', values='adjusted_close')
                pivot_df.fillna(method='ffill', inplace=True)
                pivot_df.dropna(inplace=True)
                
                return pivot_df
                
        except Exception as e:
            logger.error(f"Error getting price history: {e}")
            return pd.DataFrame()

    def get_asset_metadata(self, tickers):
        """
        Returns asset metadata including group classification.
        """
        metadata = {}
        
        try:
            with self._get_session() as session:
                assets = session.query(Asset).filter(Asset.symbol.in_(tickers)).all()
                
                for asset in assets:
                    group = self.ASSET_TYPE_TO_GROUP.get(asset.asset_type, 'Other')
                    
                    metadata[asset.symbol] = {
                        'name': asset.name or asset.symbol,
                        'asset_type': asset.asset_type,
                        'group': group,
                        'exchange': asset.exchange,
                        'currency': asset.currency
                    }
        except Exception as e:
            logger.error(f"Error getting asset metadata: {e}")
        
        return metadata

    # =========================================================================
    # CACHE COMPATIBILITY - These methods now just validate tickers exist
    # =========================================================================
    
    def ensure_tickers_in_cache(self, tickers):
        """
        Validates that tickers exist in the database.
        Returns list of valid tickers.
        """
        valid_tickers = []
        try:
            with self._get_session() as session:
                existing = session.query(Asset.symbol).filter(
                    Asset.symbol.in_(tickers)
                ).all()
                valid_tickers = [r[0] for r in existing]
        except Exception as e:
            logger.error(f"Error validating tickers: {e}")
        
        return valid_tickers


# Singleton Instance
data_manager = DataManager()