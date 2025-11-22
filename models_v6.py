# Database Models V6 - Enhanced for EODHD Hybrid System
# Works with both PostgreSQL (master) and SQLite (working)

import logging
from datetime import date, datetime
from contextlib import contextmanager

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date, DateTime,
    ForeignKey, UniqueConstraint, Boolean, Text, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

# ORM Base
Base = declarative_base()

# ============================================================================
# CORE TABLES
# ============================================================================

class Asset(Base):
    """Core asset table with EODHD-specific fields"""
    __tablename__ = 'assets'
    
    # Primary identification
    symbol = Column(String(20), primary_key=True, index=True)  # e.g., 'AAPL.US'
    code = Column(String(20), nullable=False, index=True)  # Changed from String(10)
    exchange = Column(String(10), nullable=False, index=True)  # e.g., 'US'
    
    # Basic info
    name = Column(String(255))
    asset_type = Column(String(50))  # Common Stock, ETF, FUND, etc.
    isin = Column(String(20))        # International Securities ID
    currency = Column(String(10))     # USD, GBP, EUR, etc.
    country = Column(String(50))      # Country of exchange
    
    # Status tracking
    is_active = Column(Boolean, default=True, index=True)  # Track delistings
    is_in_working_db = Column(Boolean, default=False)      # Is it in SQLite?
    
    # Timestamps
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_price_date = Column(Date)  # Date of most recent price data
    
    # Data source tracking
    data_source = Column(String(20), default='EODHD')  # EODHD, Yahoo, etc.
    
    # Relationships
    prices = relationship("AssetPrice", back_populates="asset", cascade="all, delete-orphan")
    asset_metadata = relationship("AssetMetadata", back_populates="asset", cascade="all, delete-orphan")
    fundamentals = relationship("AssetFundamentals", back_populates="asset", uselist=False, cascade="all, delete-orphan")
    classification = relationship("AssetClassification", back_populates="asset", uselist=False, cascade="all, delete-orphan")
    corporate_actions = relationship("CorporateActions", back_populates="asset", cascade="all, delete-orphan")
    risk_metrics = relationship("RiskMetrics", back_populates="asset", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Asset(symbol='{self.symbol}', name='{self.name}', type='{self.asset_type}')>"


class AssetPrice(Base):
    """Historical price data (OHLCV)"""
    __tablename__ = 'asset_prices'
    
    price_id = Column(Integer, primary_key=True)
    symbol = Column(String(20), ForeignKey('assets.symbol'), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # OHLC (raw, not adjusted)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    
    # Adjusted close (adjusted for splits and dividends)
    adjusted_close = Column(Float)
    
    # Volume (adjusted for splits)
    volume = Column(Float)
    
    # Dividend paid on this date
    dividend = Column(Float, default=0.0)
    
    # Data quality flags
    is_validated = Column(Boolean, default=False)
    has_quality_issues = Column(Boolean, default=False)
    
    # Source tracking
    data_source = Column(String(20), default='EODHD')
    loaded_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    asset = relationship("Asset", back_populates="prices")
    
    __table_args__ = (
        UniqueConstraint('symbol', 'date', name='_symbol_date_uc'),
        Index('idx_date_symbol', 'date', 'symbol'),  # For date-range queries
    )
    
    def __repr__(self):
        return f"<AssetPrice(symbol='{self.symbol}', date='{self.date}', close={self.close})>"


class AssetMetadata(Base):
    """Flexible key-value metadata storage"""
    __tablename__ = 'asset_metadata'
    
    metadata_id = Column(Integer, primary_key=True)
    symbol = Column(String(20), ForeignKey('assets.symbol'), nullable=False, index=True)
    key = Column(String(100), nullable=False)
    value = Column(Text)
    category = Column(String(50))  # For grouping metadata
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    asset = relationship("Asset", back_populates="asset_metadata")  # ← FIXED
    
    __table_args__ = (
        UniqueConstraint('symbol', 'key', name='_symbol_key_uc'),
    )


class UpdateLog(Base):
    """Track all data updates and API calls"""
    __tablename__ = 'update_log'
    
    log_id = Column(Integer, primary_key=True)
    update_time = Column(DateTime, default=datetime.utcnow, index=True)
    
    # What was updated
    update_type = Column(String(50))  # 'prices', 'splits', 'dividends', 'universe'
    exchange = Column(String(10))     # Which exchange
    symbol = Column(String(20))       # Specific ticker (if applicable)
    
    # Status
    status = Column(String(20), nullable=False)  # success, error, warning
    message = Column(Text)
    
    # API usage tracking
    api_calls_made = Column(Integer, default=0)
    rows_affected = Column(Integer, default=0)
    
    # Performance metrics
    duration_seconds = Column(Float)
    
    def __repr__(self):
        return f"<UpdateLog(type='{self.update_type}', status='{self.status}', time='{self.update_time}')>"


# ============================================================================
# ENHANCED TABLES (Fundamentals, Classification, etc.)
# ============================================================================

class AssetFundamentals(Base):
    """Fundamental data (price-based calculations since we're not subscribing to Fundamentals API)"""
    __tablename__ = 'asset_fundamentals'
    
    symbol = Column(String(20), ForeignKey('assets.symbol'), primary_key=True)
    
    # Price-based metrics (we can calculate these ourselves)
    market_cap = Column(Float)            # Estimated from price * shares
    beta = Column(Float)                   # Calculated vs market index
    volatility_30d = Column(Float)         # 30-day rolling volatility
    volatility_90d = Column(Float)         # 90-day rolling volatility
    volatility_1y = Column(Float)          # 1-year volatility
    
    # Trading metrics
    average_volume_30d = Column(Float)     # 30-day average volume
    average_volume_90d = Column(Float)     # 90-day average volume
    
    # Dividend metrics (calculated from dividend history)
    dividend_yield_ttm = Column(Float)     # Trailing twelve month yield
    dividend_frequency = Column(String(20)) # Annual, Quarterly, Monthly, etc.
    last_dividend_date = Column(Date)
    last_dividend_amount = Column(Float)
    
    # For ETFs/Funds (if available from EODHD or calculated)
    expense_ratio = Column(Float)          # Annual expense ratio
    assets_under_management = Column(Float) # AUM
    
    # Timestamps
    last_calculated = Column(DateTime, default=datetime.utcnow)
    calculation_period_end = Column(Date)   # Data current as of this date
    
    asset = relationship("Asset", back_populates="fundamentals")
    
    def __repr__(self):
        return f"<AssetFundamentals(symbol='{self.symbol}', beta={self.beta}, vol_1y={self.volatility_1y})>"


class AssetClassification(Base):
    """Detailed asset classification and categorization"""
    __tablename__ = 'asset_classification'
    
    symbol = Column(String(20), ForeignKey('assets.symbol'), primary_key=True)
    
    # Primary classification
    asset_class = Column(String(50))       # equity, fixed_income, commodity, real_estate, cash, alternative
    asset_subclass = Column(String(50))    # large_cap, mid_cap, small_cap, micro_cap
    
    # Geographic classification
    geography = Column(String(50))         # us, international, emerging, developed, global
    region = Column(String(50))            # north_america, europe, asia_pacific, etc.
    country_exposure = Column(String(50))  # Primary country exposure
    
    # Sector classification (for stocks)
    sector = Column(String(100))           # Technology, Healthcare, Financials, etc.
    industry = Column(String(100))         # Software, Biotechnology, Banks, etc.
    
    # Fund-specific classification
    fund_category = Column(String(100))    # Large Cap Growth, Bond Fund, etc.
    morningstar_category = Column(String(100))
    
    # Special characteristics
    is_leveraged = Column(Boolean, default=False)
    leverage_factor = Column(Float)        # 2x, 3x, etc.
    is_inverse = Column(Boolean, default=False)
    is_esg = Column(Boolean, default=False)
    is_dividend_focused = Column(Boolean, default=False)
    
    # Timestamps
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    asset = relationship("Asset", back_populates="classification")
    
    def __repr__(self):
        return f"<AssetClassification(symbol='{self.symbol}', class='{self.asset_class}', sector='{self.sector}')>"


class CorporateActions(Base):
    """Track splits, dividends, and other corporate actions"""
    __tablename__ = 'corporate_actions'
    
    action_id = Column(Integer, primary_key=True)
    symbol = Column(String(20), ForeignKey('assets.symbol'), nullable=False, index=True)
    
    # Action details
    action_date = Column(Date, nullable=False, index=True)
    action_type = Column(String(50), nullable=False)  # split, dividend, special_dividend, merger, spinoff
    
    # Split information
    split_ratio = Column(Float)            # e.g., 2.0 for 2-for-1 split
    split_from = Column(Float)             # Numerator
    split_to = Column(Float)               # Denominator
    
    # Dividend information
    dividend_amount = Column(Float)        # Amount per share
    dividend_currency = Column(String(10)) # Currency of dividend
    dividend_type = Column(String(50))     # regular, special, etc.
    
    # Extended dividend dates (for US stocks, available from EODHD)
    ex_dividend_date = Column(Date)        # Ex-dividend date
    record_date = Column(Date)             # Record date
    payment_date = Column(Date)            # Payment date
    declaration_date = Column(Date)        # Declaration date
    
    # Additional details
    details = Column(Text)
    notes = Column(Text)
    
    # Source tracking
    data_source = Column(String(20), default='EODHD')
    loaded_at = Column(DateTime, default=datetime.utcnow)
    
    asset = relationship("Asset", back_populates="corporate_actions")
    
    __table_args__ = (
        Index('idx_action_date_type', 'action_date', 'action_type'),
    )
    
    def __repr__(self):
        return f"<CorporateAction(symbol='{self.symbol}', type='{self.action_type}', date='{self.action_date}')>"


class RiskMetrics(Base):
    """Pre-calculated risk metrics for performance optimization"""
    __tablename__ = 'risk_metrics'
    
    metric_id = Column(Integer, primary_key=True)
    symbol = Column(String(20), ForeignKey('assets.symbol'), nullable=False, index=True)
    
    # Period covered
    period = Column(String(10), nullable=False)  # 1m, 3m, 6m, 1y, 3y, 5y, 10y, all
    start_date = Column(Date)
    end_date = Column(Date)
    
    # Return metrics
    total_return = Column(Float)           # Total return over period
    annualized_return = Column(Float)      # Annualized return
    cagr = Column(Float)                   # Compound annual growth rate
    
    # Volatility metrics
    volatility = Column(Float)             # Annualized standard deviation
    downside_deviation = Column(Float)     # Downside volatility (semi-deviation)
    upside_capture = Column(Float)         # Upside capture ratio
    downside_capture = Column(Float)       # Downside capture ratio
    
    # Drawdown metrics
    max_drawdown = Column(Float)           # Maximum peak-to-trough decline
    max_drawdown_duration = Column(Integer) # Days in max drawdown
    current_drawdown = Column(Float)       # Current drawdown from peak
    
    # Risk-adjusted returns
    sharpe_ratio = Column(Float)           # Risk-adjusted return (vs risk-free rate)
    sortino_ratio = Column(Float)          # Return vs downside risk
    calmar_ratio = Column(Float)           # Return vs max drawdown
    omega_ratio = Column(Float)            # Probability-weighted ratio
    
    # Value at Risk
    var_95 = Column(Float)                 # Value at Risk (95% confidence)
    var_99 = Column(Float)                 # Value at Risk (99% confidence)
    cvar_95 = Column(Float)                # Conditional VaR (Expected Shortfall)
    
    # Distribution metrics
    skewness = Column(Float)               # Return distribution skewness
    kurtosis = Column(Float)               # Return distribution kurtosis
    
    # Correlation (vs market benchmark)
    correlation_spy = Column(Float)        # Correlation with S&P 500
    correlation_agg = Column(Float)        # Correlation with bond aggregate
    
    # Timestamps
    last_calculated = Column(DateTime, default=datetime.utcnow)
    
    asset = relationship("Asset", back_populates="risk_metrics")
    
    __table_args__ = (
        UniqueConstraint('symbol', 'period', name='_symbol_period_uc'),
    )
    
    def __repr__(self):
        return f"<RiskMetrics(symbol='{self.symbol}', period='{self.period}', sharpe={self.sharpe_ratio})>"


# ============================================================================
# API USAGE TRACKING
# ============================================================================

class APIUsage(Base):
    """Track EODHD API usage to stay under limits"""
    __tablename__ = 'api_usage'
    
    usage_id = Column(Integer, primary_key=True)
    date = Column(Date, default=date.today, index=True)
    
    # Call tracking
    total_calls = Column(Integer, default=0)
    bulk_eod_calls = Column(Integer, default=0)
    individual_eod_calls = Column(Integer, default=0)
    splits_calls = Column(Integer, default=0)
    dividends_calls = Column(Integer, default=0)
    fundamentals_calls = Column(Integer, default=0)
    universe_calls = Column(Integer, default=0)
    other_calls = Column(Integer, default=0)
    
    # Status
    limit_reached = Column(Boolean, default=False)
    warning_threshold_reached = Column(Boolean, default=False)
    
    # Timestamps
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('date', name='_date_uc'),
    )


# ============================================================================
# DATA QUALITY TRACKING
# ============================================================================

class DataQualityIssue(Base):
    """Track data quality issues for investigation"""
    __tablename__ = 'data_quality_issues'
    
    issue_id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # Issue details
    issue_type = Column(String(50), nullable=False)  # missing_data, outlier, suspicious_jump, etc.
    severity = Column(String(20))                     # low, medium, high, critical
    description = Column(Text)
    
    # Values involved
    expected_value = Column(Float)
    actual_value = Column(Float)
    
    # Status
    is_resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text)
    
    # Timestamps
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime)


# ============================================================================
# DATABASE SETUP AND UTILITIES
# ============================================================================

def create_all_tables(engine):
    """Create all tables in the database"""
    Base.metadata.create_all(engine)
    logger.info(f"Created all tables in database")


def drop_all_tables(engine):
    """Drop all tables (use with caution!)"""
    Base.metadata.drop_all(engine)
    logger.warning(f"Dropped all tables from database")


@contextmanager
def get_session(engine):
    """Provide a transactional scope for database operations"""
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()


def init_database(engine, drop_existing=False):
    """Initialize database with tables and indexes"""
    if drop_existing:
        drop_all_tables(engine)
    
    create_all_tables(engine)
    
    # Create additional indexes for performance
    logger.info("Database initialized successfully")


# ============================================================================
# QUERY HELPERS
# ============================================================================

def get_asset(session, symbol):
    """Get an asset by symbol"""
    return session.query(Asset).filter_by(symbol=symbol).first()


def get_active_assets(session, exchange=None, asset_type=None):
    """Get all active assets, optionally filtered by exchange or type"""
    query = session.query(Asset).filter_by(is_active=True)
    
    if exchange:
        query = query.filter_by(exchange=exchange)
    
    if asset_type:
        query = query.filter_by(asset_type=asset_type)
    
    return query.all()


def get_price_data(session, symbol, start_date=None, end_date=None):
    """Get price data for a symbol within a date range"""
    query = session.query(AssetPrice).filter_by(symbol=symbol)
    
    if start_date:
        query = query.filter(AssetPrice.date >= start_date)
    
    if end_date:
        query = query.filter(AssetPrice.date <= end_date)
    
    return query.order_by(AssetPrice.date).all()


def get_corporate_actions(session, symbol, action_type=None, start_date=None):
    """Get corporate actions for a symbol"""
    query = session.query(CorporateActions).filter_by(symbol=symbol)
    
    if action_type:
        query = query.filter_by(action_type=action_type)
    
    if start_date:
        query = query.filter(CorporateActions.action_date >= start_date)
    
    return query.order_by(CorporateActions.action_date).all()


if __name__ == "__main__":
    print("Database Models V6 loaded successfully")
    print(f"Tables defined: {', '.join([table.name for table in Base.metadata.sorted_tables])}")
