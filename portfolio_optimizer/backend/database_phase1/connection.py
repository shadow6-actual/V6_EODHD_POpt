"""
Database Connection Module
Provides clean abstractions over config_v6 database connections
"""

import sys
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine

# Add parent directories to path to import config_v6 and models_v6
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import config_v6
    from models_v6 import get_session
except ImportError as e:
    logging.error(f"Failed to import config_v6 or models_v6: {e}")
    logging.error(f"Project root: {project_root}")
    logging.error("Ensure config_v6.py and models_v6.py are in the project root")
    raise

logger = logging.getLogger(__name__)


# ============================================================================
# ENGINE MANAGEMENT
# ============================================================================

def get_db_engine() -> Engine:
    """
    Get PostgreSQL database engine (master database with all 150K+ tickers)
    
    Returns:
        SQLAlchemy Engine for PostgreSQL
        
    Example:
        >>> engine = get_db_engine()
        >>> with get_session(engine) as session:
        ...     assets = session.query(Asset).limit(10).all()
    """
    try:
        engine = config_v6.get_postgres_engine()
        logger.debug("PostgreSQL engine created successfully")
        return engine
    except Exception as e:
        logger.error(f"Failed to create PostgreSQL engine: {e}")
        raise


def get_working_db_engine() -> Engine:
    """
    Get SQLite working database engine (for active portfolios and watchlists)
    
    Returns:
        SQLAlchemy Engine for SQLite
        
    Note:
        The working database is optimized for quick queries on a smaller
        subset of assets (your portfolio + watchlist + benchmarks)
    """
    try:
        engine = config_v6.get_sqlite_engine()
        logger.debug("SQLite working database engine created successfully")
        return engine
    except Exception as e:
        logger.error(f"Failed to create SQLite engine: {e}")
        raise


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

@contextmanager
def get_db_session(engine: Engine = None) -> Generator[Session, None, None]:
    """
    Context manager for PostgreSQL database sessions
    
    Args:
        engine: Optional SQLAlchemy engine. If None, creates new PostgreSQL engine
        
    Yields:
        Database session
        
    Example:
        >>> with get_db_session() as session:
        ...     assets = session.query(Asset).filter_by(exchange='US').limit(10).all()
        ...     for asset in assets:
        ...         print(asset.symbol, asset.name)
    """
    if engine is None:
        engine = get_db_engine()
    
    with get_session(engine) as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            raise


@contextmanager
def get_working_db_session(engine: Engine = None) -> Generator[Session, None, None]:
    """
    Context manager for SQLite working database sessions
    
    Args:
        engine: Optional SQLAlchemy engine. If None, creates new SQLite engine
        
    Yields:
        Database session
        
    Example:
        >>> with get_working_db_session() as session:
        ...     portfolio_assets = session.query(Asset).filter_by(
        ...         is_in_working_db=True
        ...     ).all()
    """
    if engine is None:
        engine = get_working_db_engine()
    
    with get_session(engine) as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Working database session error: {e}")
            raise


# ============================================================================
# SESSION MANAGER CLASS
# ============================================================================

class SessionManager:
    """
    Reusable session manager for long-running operations
    
    Usage:
        >>> manager = SessionManager()
        >>> with manager.session() as session:
        ...     # Perform database operations
        ...     pass
    """
    
    def __init__(self, use_working_db: bool = False):
        """
        Initialize session manager
        
        Args:
            use_working_db: If True, use SQLite working database
                          If False, use PostgreSQL master database (default)
        """
        self.use_working_db = use_working_db
        self._engine = None
    
    @property
    def engine(self) -> Engine:
        """Get or create database engine (lazy initialization)"""
        if self._engine is None:
            if self.use_working_db:
                self._engine = get_working_db_engine()
            else:
                self._engine = get_db_engine()
        return self._engine
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Get database session context manager
        
        Yields:
            Database session
        """
        with get_session(self.engine) as session:
            try:
                yield session
            except Exception as e:
                logger.error(f"Session error: {e}")
                raise
    
    def close(self):
        """Close the engine and cleanup connections"""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            logger.debug("Database engine disposed")


# ============================================================================
# DATABASE HEALTH CHECK
# ============================================================================

def check_database_connection(use_working_db: bool = False) -> bool:
    """
    Check if database connection is healthy
    
    Args:
        use_working_db: If True, check SQLite database
                       If False, check PostgreSQL database (default)
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        if use_working_db:
            with get_working_db_session() as session:
                # Try a simple query
                result = session.execute("SELECT 1").scalar()
                logger.info("Working database (SQLite) connection: OK")
                return result == 1
        else:
            with get_db_session() as session:
                # Try a simple query
                result = session.execute("SELECT 1").scalar()
                logger.info("Master database (PostgreSQL) connection: OK")
                return result == 1
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def get_database_stats() -> dict:
    """
    Get basic database statistics
    
    Returns:
        Dictionary with database statistics
    """
    from models_v6 import Asset, AssetPrice
    
    stats = {}
    
    try:
        with get_db_session() as session:
            # Count assets
            total_assets = session.query(Asset).count()
            active_assets = session.query(Asset).filter_by(is_active=True).count()
            
            # Count prices (may be slow on large database)
            # For production, consider caching this value
            logger.debug("Counting price records (may take a moment)...")
            total_prices = session.query(AssetPrice).count()
            
            # Count exchanges
            from sqlalchemy import func, distinct
            exchanges = session.query(
                func.count(distinct(Asset.exchange))
            ).scalar() or 0
            
            stats = {
                'total_assets': total_assets,
                'active_assets': active_assets,
                'inactive_assets': total_assets - active_assets,
                'total_price_records': total_prices,
                'exchanges_tracked': exchanges,
                'database_type': 'PostgreSQL',
                'connection_status': 'connected'
            }
            
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        stats = {
            'error': str(e),
            'connection_status': 'error'
        }
    
    return stats


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def execute_raw_query(query: str, params: dict = None, use_working_db: bool = False):
    """
    Execute a raw SQL query
    
    Args:
        query: SQL query string
        params: Query parameters (for parameterized queries)
        use_working_db: If True, use SQLite database
        
    Returns:
        Query results
        
    Example:
        >>> results = execute_raw_query(
        ...     "SELECT symbol, name FROM assets WHERE exchange = :exchange LIMIT 10",
        ...     params={'exchange': 'US'}
        ... )
    """
    if use_working_db:
        session_func = get_working_db_session
    else:
        session_func = get_db_session
    
    try:
        with session_func() as session:
            result = session.execute(query, params or {})
            return result.fetchall()
    except Exception as e:
        logger.error(f"Raw query execution failed: {e}")
        raise


# ============================================================================
# MODULE INITIALIZATION
# ============================================================================

# Verify database connections on import (optional - can be disabled)
VERIFY_ON_IMPORT = False

if VERIFY_ON_IMPORT:
    if check_database_connection():
        logger.info("Database connection verified successfully")
    else:
        logger.warning("Database connection could not be verified")
