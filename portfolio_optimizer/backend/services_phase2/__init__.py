# Database package for Portfolio Optimizer
# Provides clean abstractions over PostgreSQL database

from .connection import (
    get_db_engine,
    get_db_session,
    get_working_db_engine,
    get_working_db_session,
    SessionManager
)

from .queries import (
    # Asset queries
    search_assets,
    get_asset_by_symbol,
    get_assets_by_exchange,
    get_all_exchanges,
    
    # Price queries
    get_price_data,
    get_latest_price,
    get_price_range,
    
    # Risk metrics queries
    get_risk_metrics,
    get_risk_metrics_for_period,
    
    # Bulk queries
    get_multiple_asset_prices,
    get_correlation_matrix,
)

__all__ = [
    # Connection management
    'get_db_engine',
    'get_db_session',
    'get_working_db_engine',
    'get_working_db_session',
    'SessionManager',
    
    # Asset queries
    'search_assets',
    'get_asset_by_symbol',
    'get_assets_by_exchange',
    'get_all_exchanges',
    
    # Price queries
    'get_price_data',
    'get_latest_price',
    'get_price_range',
    
    # Risk metrics
    'get_risk_metrics',
    'get_risk_metrics_for_period',
    
    # Bulk queries
    'get_multiple_asset_prices',
    'get_correlation_matrix',
]
