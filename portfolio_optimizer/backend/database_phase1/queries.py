"""
Database Queries Module
Common query functions for assets, prices, and risk metrics
"""

import sys
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Tuple
from sqlalchemy import func, and_, or_, desc, distinct
from sqlalchemy.orm import Session

# Add parent directories to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from models_v6 import Asset, AssetPrice
from .connection import get_db_session, get_working_db_session

logger = logging.getLogger(__name__)


# ============================================================================
# ASSET QUERIES
# ============================================================================

def search_assets(
    query: str,
    limit: int = 50,
    exchanges: List[str] = None,
    asset_types: List[str] = None,
    active_only: bool = True,
    session: Session = None
) -> List[Asset]:
    """
    Search for assets by symbol, name, or code
    
    Args:
        query: Search string (matches symbol, code, or name)
        limit: Maximum number of results to return
        exchanges: Filter by specific exchanges (e.g., ['US', 'LSE'])
        asset_types: Filter by asset types (e.g., ['Common Stock', 'ETF'])
        active_only: If True, only return active assets
        session: Optional database session (creates new if None)
        
    Returns:
        List of Asset objects matching search criteria
        
    Example:
        >>> assets = search_assets('AAPL', exchanges=['US'])
        >>> for asset in assets:
        ...     print(f"{asset.symbol}: {asset.name}")
    """
    close_session = False
    if session is None:
        session = get_db_session().__enter__()
        close_session = True
    
    try:
        # Build query
        q = session.query(Asset)
        
        # Active filter
        if active_only:
            q = q.filter(Asset.is_active == True)
        
        # Search filter (symbol, code, or name)
        search_pattern = f"%{query.upper()}%"
        q = q.filter(
            or_(
                Asset.symbol.ilike(search_pattern),
                Asset.code.ilike(search_pattern),
                Asset.name.ilike(search_pattern)
            )
        )
        
        # Exchange filter
        if exchanges:
            q = q.filter(Asset.exchange.in_(exchanges))
        
        # Asset type filter
        if asset_types:
            q = q.filter(Asset.asset_type.in_(asset_types))
        
        # Order by: exact matches first, then alphabetically
        # Exact symbol matches get highest priority
        results = q.limit(limit * 2).all()  # Get more for sorting
        
        # Sort results: exact symbol matches first
        results.sort(key=lambda x: (
            x.symbol.upper() != query.upper(),  # Exact match first
            x.code.upper() != query.upper(),    # Then exact code match
            x.symbol.upper()                     # Then alphabetically
        ))
        
        return results[:limit]
        
    except Exception as e:
        logger.error(f"Asset search failed for query '{query}': {e}")
        return []
    finally:
        if close_session:
            session.close()


def get_asset_by_symbol(symbol: str, session: Session = None) -> Optional[Asset]:
    """
    Get a single asset by symbol (primary key lookup)
    
    Args:
        symbol: Asset symbol (e.g., 'AAPL.US')
        session: Optional database session
        
    Returns:
        Asset object or None if not found
        
    Example:
        >>> asset = get_asset_by_symbol('AAPL.US')
        >>> if asset:
        ...     print(f"{asset.name} - {asset.exchange}")
    """
    close_session = False
    if session is None:
        session = get_db_session().__enter__()
        close_session = True
    
    try:
        return session.query(Asset).filter_by(symbol=symbol).first()
    except Exception as e:
        logger.error(f"Failed to get asset {symbol}: {e}")
        return None
    finally:
        if close_session:
            session.close()


def get_assets_by_exchange(
    exchange: str,
    asset_type: str = None,
    active_only: bool = True,
    limit: int = None,
    session: Session = None
) -> List[Asset]:
    """
    Get all assets for a specific exchange
    
    Args:
        exchange: Exchange code (e.g., 'US', 'LSE', 'XETRA')
        asset_type: Optional asset type filter (e.g., 'Common Stock')
        active_only: If True, only return active assets
        limit: Optional limit on number of results
        session: Optional database session
        
    Returns:
        List of Asset objects
        
    Example:
        >>> us_stocks = get_assets_by_exchange('US', asset_type='Common Stock', limit=100)
    """
    close_session = False
    if session is None:
        session = get_db_session().__enter__()
        close_session = True
    
    try:
        q = session.query(Asset).filter_by(exchange=exchange)
        
        if active_only:
            q = q.filter_by(is_active=True)
        
        if asset_type:
            q = q.filter_by(asset_type=asset_type)
        
        q = q.order_by(Asset.symbol)
        
        if limit:
            q = q.limit(limit)
        
        return q.all()
        
    except Exception as e:
        logger.error(f"Failed to get assets for exchange {exchange}: {e}")
        return []
    finally:
        if close_session:
            session.close()


def get_all_exchanges(session: Session = None) -> List[str]:
    """
    Get list of all exchanges in the database
    
    Args:
        session: Optional database session
        
    Returns:
        List of exchange codes
        
    Example:
        >>> exchanges = get_all_exchanges()
        >>> print(f"Tracking {len(exchanges)} exchanges")
    """
    close_session = False
    if session is None:
        session = get_db_session().__enter__()
        close_session = True
    
    try:
        results = session.query(distinct(Asset.exchange)).order_by(Asset.exchange).all()
        return [r[0] for r in results if r[0]]
    except Exception as e:
        logger.error(f"Failed to get exchanges: {e}")
        return []
    finally:
        if close_session:
            session.close()


def get_asset_types(exchange: str = None, session: Session = None) -> List[str]:
    """
    Get list of all asset types (optionally filtered by exchange)
    
    Args:
        exchange: Optional exchange code filter
        session: Optional database session
        
    Returns:
        List of asset types
    """
    close_session = False
    if session is None:
        session = get_db_session().__enter__()
        close_session = True
    
    try:
        q = session.query(distinct(Asset.asset_type))
        
        if exchange:
            q = q.filter_by(exchange=exchange)
        
        results = q.order_by(Asset.asset_type).all()
        return [r[0] for r in results if r[0]]
    except Exception as e:
        logger.error(f"Failed to get asset types: {e}")
        return []
    finally:
        if close_session:
            session.close()


# ============================================================================
# PRICE QUERIES
# ============================================================================

def get_price_data(
    symbol: str,
    start_date: date = None,
    end_date: date = None,
    session: Session = None
) -> pd.DataFrame:
    """
    Get historical price data for a symbol
    
    Args:
        symbol: Asset symbol (e.g., 'AAPL.US')
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        session: Optional database session
        
    Returns:
        DataFrame with columns: date, open, high, low, close, adjusted_close, volume
        
    Example:
        >>> from datetime import datetime, timedelta
        >>> end = datetime.now().date()
        >>> start = end - timedelta(days=365)
        >>> prices = get_price_data('AAPL.US', start_date=start, end_date=end)
        >>> print(f"Retrieved {len(prices)} trading days")
    """
    close_session = False
    if session is None:
        session = get_db_session().__enter__()
        close_session = True
    
    try:
        q = session.query(AssetPrice).filter_by(symbol=symbol)
        
        if start_date:
            q = q.filter(AssetPrice.date >= start_date)
        
        if end_date:
            q = q.filter(AssetPrice.date <= end_date)
        
        results = q.order_by(AssetPrice.date).all()
        
        if not results:
            logger.warning(f"No price data found for {symbol}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        data = []
        for r in results:
            data.append({
                'date': r.date,
                'open': float(r.open) if r.open else None,
                'high': float(r.high) if r.high else None,
                'low': float(r.low) if r.low else None,
                'close': float(r.close) if r.close else None,
                'adjusted_close': float(r.adjusted_close) if r.adjusted_close else float(r.close),
                'volume': int(r.volume) if r.volume else 0
            })
        
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        return df
        
    except Exception as e:
        logger.error(f"Failed to get price data for {symbol}: {e}")
        return pd.DataFrame()
    finally:
        if close_session:
            session.close()


def get_latest_price(symbol: str, session: Session = None) -> Optional[AssetPrice]:
    """
    Get the most recent price record for a symbol
    
    Args:
        symbol: Asset symbol
        session: Optional database session
        
    Returns:
        Most recent AssetPrice object or None
        
    Example:
        >>> latest = get_latest_price('AAPL.US')
        >>> if latest:
        ...     print(f"Latest close: ${latest.close} on {latest.date}")
    """
    close_session = False
    if session is None:
        session = get_db_session().__enter__()
        close_session = True
    
    try:
        return session.query(AssetPrice).filter_by(
            symbol=symbol
        ).order_by(desc(AssetPrice.date)).first()
    except Exception as e:
        logger.error(f"Failed to get latest price for {symbol}: {e}")
        return None
    finally:
        if close_session:
            session.close()


def get_price_range(
    symbol: str,
    session: Session = None
) -> Tuple[Optional[date], Optional[date]]:
    """
    Get the date range of available price data for a symbol
    
    Args:
        symbol: Asset symbol
        session: Optional database session
        
    Returns:
        Tuple of (earliest_date, latest_date) or (None, None) if no data
        
    Example:
        >>> start, end = get_price_range('AAPL.US')
        >>> if start and end:
        ...     print(f"Data available from {start} to {end}")
    """
    close_session = False
    if session is None:
        session = get_db_session().__enter__()
        close_session = True
    
    try:
        result = session.query(
            func.min(AssetPrice.date),
            func.max(AssetPrice.date)
        ).filter_by(symbol=symbol).first()
        
        return result if result else (None, None)
    except Exception as e:
        logger.error(f"Failed to get price range for {symbol}: {e}")
        return (None, None)
    finally:
        if close_session:
            session.close()


def get_price_count(symbol: str, session: Session = None) -> int:
    """
    Get the count of price records for a symbol
    
    Args:
        symbol: Asset symbol
        session: Optional database session
        
    Returns:
        Number of price records
    """
    close_session = False
    if session is None:
        session = get_db_session().__enter__()
        close_session = True
    
    try:
        return session.query(AssetPrice).filter_by(symbol=symbol).count()
    except Exception as e:
        logger.error(f"Failed to count prices for {symbol}: {e}")
        return 0
    finally:
        if close_session:
            session.close()


# ============================================================================
# BULK QUERIES (Multiple Assets)
# ============================================================================

def get_multiple_asset_prices(
    symbols: List[str],
    start_date: date = None,
    end_date: date = None,
    session: Session = None
) -> Dict[str, pd.DataFrame]:
    """
    Get price data for multiple symbols
    
    Args:
        symbols: List of asset symbols
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        session: Optional database session
        
    Returns:
        Dictionary mapping symbol to DataFrame of prices
        
    Example:
        >>> prices = get_multiple_asset_prices(['AAPL.US', 'MSFT.US', 'GOOGL.US'])
        >>> for symbol, df in prices.items():
        ...     print(f"{symbol}: {len(df)} days")
    """
    result = {}
    
    for symbol in symbols:
        df = get_price_data(symbol, start_date, end_date, session)
        if not df.empty:
            result[symbol] = df
    
    return result


def get_correlation_matrix(
    symbols: List[str],
    start_date: date = None,
    end_date: date = None,
    session: Session = None
) -> pd.DataFrame:
    """
    Calculate correlation matrix for multiple assets
    
    Args:
        symbols: List of asset symbols
        start_date: Start date for analysis
        end_date: End date for analysis
        session: Optional database session
        
    Returns:
        DataFrame with correlation matrix (symbols as both rows and columns)
        
    Example:
        >>> corr = get_correlation_matrix(['AAPL.US', 'MSFT.US', 'GOOGL.US'])
        >>> print(corr)
    """
    try:
        # Get prices for all symbols
        prices_dict = get_multiple_asset_prices(symbols, start_date, end_date, session)
        
        if not prices_dict:
            logger.warning("No price data available for correlation calculation")
            return pd.DataFrame()
        
        # Create a combined DataFrame with adjusted close prices
        combined_data = {}
        for symbol, df in prices_dict.items():
            if 'adjusted_close' in df.columns:
                combined_data[symbol] = df['adjusted_close']
        
        if not combined_data:
            logger.warning("No adjusted close prices available")
            return pd.DataFrame()
        
        # Combine into single DataFrame
        prices_df = pd.DataFrame(combined_data)
        
        # Calculate returns (percentage change)
        returns_df = prices_df.pct_change().dropna()
        
        # Calculate correlation matrix
        correlation_matrix = returns_df.corr()
        
        return correlation_matrix
        
    except Exception as e:
        logger.error(f"Failed to calculate correlation matrix: {e}")
        return pd.DataFrame()


def get_returns_dataframe(
    symbols: List[str],
    start_date: date = None,
    end_date: date = None,
    frequency: str = 'D',
    session: Session = None
) -> pd.DataFrame:
    """
    Get returns data for multiple symbols as a DataFrame
    
    Args:
        symbols: List of asset symbols
        start_date: Start date
        end_date: End date
        frequency: Resampling frequency ('D'=daily, 'W'=weekly, 'M'=monthly)
        session: Optional database session
        
    Returns:
        DataFrame with returns (rows=dates, columns=symbols)
        
    Example:
        >>> returns = get_returns_dataframe(['AAPL.US', 'MSFT.US'], frequency='M')
        >>> print(f"Monthly returns shape: {returns.shape}")
    """
    try:
        # Get prices for all symbols
        prices_dict = get_multiple_asset_prices(symbols, start_date, end_date, session)
        
        if not prices_dict:
            return pd.DataFrame()
        
        # Create combined price DataFrame
        prices_data = {}
        for symbol, df in prices_dict.items():
            if 'adjusted_close' in df.columns:
                prices_data[symbol] = df['adjusted_close']
        
        prices_df = pd.DataFrame(prices_data)
        
        # Resample if needed
        if frequency != 'D':
            prices_df = prices_df.resample(frequency).last()
        
        # Calculate returns
        returns_df = prices_df.pct_change().dropna()
        
        return returns_df
        
    except Exception as e:
        logger.error(f"Failed to get returns dataframe: {e}")
        return pd.DataFrame()


# ============================================================================
# RISK METRICS QUERIES
# ============================================================================

def get_risk_metrics(
    symbol: str,
    session: Session = None
) -> Optional[object]:
    """
    Get risk metrics for a symbol (all periods)
    
    Args:
        symbol: Asset symbol
        session: Optional database session
        
    Returns:
        List of RiskMetrics objects or None
        
    Note:
        Risk metrics may not be available for all assets.
        Requires RiskMetrics table to be populated.
    """
    close_session = False
    if session is None:
        session = get_db_session().__enter__()
        close_session = True
    
    try:
        # Try to import RiskMetrics (may not exist yet)
        from models_v6 import RiskMetrics
        
        return session.query(RiskMetrics).filter_by(symbol=symbol).all()
    except ImportError:
        logger.debug("RiskMetrics table not available")
        return None
    except Exception as e:
        logger.error(f"Failed to get risk metrics for {symbol}: {e}")
        return None
    finally:
        if close_session:
            session.close()


def get_risk_metrics_for_period(
    symbol: str,
    period: str = '1y',
    session: Session = None
) -> Optional[object]:
    """
    Get risk metrics for a specific time period
    
    Args:
        symbol: Asset symbol
        period: Time period ('1y', '3y', '5y', '10y', 'all')
        session: Optional database session
        
    Returns:
        RiskMetrics object or None
    """
    close_session = False
    if session is None:
        session = get_db_session().__enter__()
        close_session = True
    
    try:
        from models_v6 import RiskMetrics
        
        return session.query(RiskMetrics).filter_by(
            symbol=symbol,
            period=period
        ).first()
    except ImportError:
        logger.debug("RiskMetrics table not available")
        return None
    except Exception as e:
        logger.error(f"Failed to get {period} risk metrics for {symbol}: {e}")
        return None
    finally:
        if close_session:
            session.close()


# ============================================================================
# VALIDATION & UTILITY
# ============================================================================

def validate_symbol_exists(symbol: str, session: Session = None) -> bool:
    """
    Check if a symbol exists in the database
    
    Args:
        symbol: Asset symbol to check
        session: Optional database session
        
    Returns:
        True if symbol exists, False otherwise
    """
    asset = get_asset_by_symbol(symbol, session)
    return asset is not None


def validate_symbols_exist(symbols: List[str], session: Session = None) -> Dict[str, bool]:
    """
    Check which symbols exist in the database
    
    Args:
        symbols: List of symbols to check
        session: Optional database session
        
    Returns:
        Dictionary mapping symbol to existence (True/False)
    """
    result = {}
    for symbol in symbols:
        result[symbol] = validate_symbol_exists(symbol, session)
    return result


def get_data_quality_info(symbol: str, session: Session = None) -> Dict:
    """
    Get data quality information for a symbol
    
    Args:
        symbol: Asset symbol
        session: Optional database session
        
    Returns:
        Dictionary with data quality metrics
    """
    asset = get_asset_by_symbol(symbol, session)
    
    if not asset:
        return {'exists': False}
    
    price_count = get_price_count(symbol, session)
    date_range = get_price_range(symbol, session)
    latest = get_latest_price(symbol, session)
    
    return {
        'exists': True,
        'is_active': asset.is_active,
        'exchange': asset.exchange,
        'asset_type': asset.asset_type,
        'price_records': price_count,
        'earliest_date': date_range[0],
        'latest_date': date_range[1],
        'latest_price': float(latest.close) if latest and latest.close else None,
        'last_updated': asset.last_updated,
        'last_price_date': asset.last_price_date
    }
