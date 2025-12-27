# Database Models V6 - Enhanced for EODHD Hybrid System
# Works with both PostgreSQL (master) and SQLite (working)

import logging
from datetime import date, datetime
from contextlib import contextmanager

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date, DateTime, BigInteger,
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
    code = Column(String(20), nullable=False, index=True)
    exchange = Column(String(10), nullable=False, index=True)  # e.g., 'US'
    
    # Basic info
    name = Column(String(255))
    asset_type = Column(String(50))  # Common Stock, ETF, FUND, etc.
    isin = Column(String(20))
    currency = Column(String(10))
    country = Column(String(50))
    
    # Status tracking
    is_active = Column(Boolean, default=True, index=True)
    is_in_working_db = Column(Boolean, default=False)
    
    # Timestamps
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_price_date = Column(Date)
    
    # Data source tracking
    data_source = Column(String(20), default='EODHD')
    
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
        Index('idx_date_symbol', 'date', 'symbol'),
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
    category = Column(String(50))
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    asset = relationship("Asset", back_populates="asset_metadata")
    
    __table_args__ = (
        UniqueConstraint('symbol', 'key', name='_symbol_key_uc'),
    )


class UpdateLog(Base):
    """Track all data updates and API calls"""
    __tablename__ = 'update_log'
    
    log_id = Column(Integer, primary_key=True)
    update_time = Column(DateTime, default=datetime.utcnow, index=True)
    
    # What was updated
    update_type = Column(String(50))
    exchange = Column(String(10))
    symbol = Column(String(20))
    
    # Status
    status = Column(String(20), nullable=False)
    message = Column(Text)
    
    # API usage tracking
    api_calls_made = Column(Integer, default=0)
    rows_affected = Column(Integer, default=0)
    
    # Performance metrics
    duration_seconds = Column(Float)
    
    def __repr__(self):
        return f"<UpdateLog(type='{self.update_type}', status='{self.status}', time='{self.update_time}')>"


# ============================================================================
# SAVED PORTFOLIOS (NEW FOR WEB APP)
# ============================================================================

class SavedPortfolio(Base):
    """User-saved portfolio configurations"""
    __tablename__ = 'saved_portfolios'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, index=True)
    tickers = Column(Text, nullable=False)  # JSON: ["AAPL.US", "MSFT.US"]
    weights = Column(Text, nullable=False)  # JSON: {"AAPL.US": 0.50, "MSFT.US": 0.50}
    constraints = Column(Text)  # JSON: {"AAPL.US": {"min": 0.1, "max": 0.7}}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<SavedPortfolio(name='{self.name}', created='{self.created_at}')>"


# ============================================================================
# ENHANCED TABLES (Fundamentals, Classification, etc.)
# ============================================================================

class AssetFundamentals(Base):
    """Fundamental data (price-based calculations)"""
    __tablename__ = 'asset_fundamentals'
    
    symbol = Column(String(20), ForeignKey('assets.symbol'), primary_key=True)
    
    # Price-based metrics
    market_cap = Column(Float)
    beta = Column(Float)
    volatility_30d = Column(Float)
    volatility_90d = Column(Float)
    volatility_1y = Column(Float)
    
    # Trading metrics
    average_volume_30d = Column(Float)
    average_volume_90d = Column(Float)
    
    # Dividend metrics
    dividend_yield_ttm = Column(Float)
    dividend_frequency = Column(String(20))
    last_dividend_date = Column(Date)
    last_dividend_amount = Column(Float)
    
    # For ETFs/Funds
    expense_ratio = Column(Float)
    assets_under_management = Column(Float)
    
    # Timestamps
    last_calculated = Column(DateTime, default=datetime.utcnow)
    calculation_period_end = Column(Date)
    
    asset = relationship("Asset", back_populates="fundamentals")
    
    def __repr__(self):
        return f"<AssetFundamentals(symbol='{self.symbol}', beta={self.beta}, vol_1y={self.volatility_1y})>"


class AssetClassification(Base):
    """Detailed asset classification and categorization"""
    __tablename__ = 'asset_classification'
    
    symbol = Column(String(20), ForeignKey('assets.symbol'), primary_key=True)
    
    # Primary classification
    asset_class = Column(String(50))
    asset_subclass = Column(String(50))
    
    # Geographic classification
    geography = Column(String(50))
    region = Column(String(50))
    country_exposure = Column(String(50))
    
    # Sector classification
    sector = Column(String(100))
    industry = Column(String(100))
    
    # Fund-specific classification
    fund_category = Column(String(100))
    fund_family = Column(String(100))
    fund_strategy = Column(String(100))
    
    # Factor exposures
    value_score = Column(Float)
    growth_score = Column(Float)
    momentum_score = Column(Float)
    quality_score = Column(Float)
    
    # Timestamps
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    asset = relationship("Asset", back_populates="classification")


class CorporateActions(Base):
    """Stock splits, dividends, and other corporate actions"""
    __tablename__ = 'corporate_actions'
    
    action_id = Column(Integer, primary_key=True)
    symbol = Column(String(20), ForeignKey('assets.symbol'), nullable=False, index=True)
    action_date = Column(Date, nullable=False, index=True)
    action_type = Column(String(20), nullable=False)
    
    # Split data
    split_ratio = Column(Float)
    
    # Dividend data
    dividend_amount = Column(Float)
    dividend_currency = Column(String(10))
    ex_dividend_date = Column(Date)
    payment_date = Column(Date)
    
    # Status
    is_processed = Column(Boolean, default=False)
    data_source = Column(String(20), default='EODHD')
    loaded_at = Column(DateTime, default=datetime.utcnow)
    
    asset = relationship("Asset", back_populates="corporate_actions")
    
    __table_args__ = (
        Index('idx_symbol_action_date', 'symbol', 'action_date'),
    )


class RiskMetrics(Base):
    """Pre-calculated risk metrics for various periods"""
    __tablename__ = 'risk_metrics'
    
    metric_id = Column(Integer, primary_key=True)
    symbol = Column(String(20), ForeignKey('assets.symbol'), nullable=False, index=True)
    
    # Period covered
    period = Column(String(10), nullable=False)
    start_date = Column(Date)
    end_date = Column(Date)
    
    # Return metrics
    total_return = Column(Float)
    annualized_return = Column(Float)
    cagr = Column(Float)
    
    # Volatility metrics
    volatility = Column(Float)
    downside_deviation = Column(Float)
    upside_capture = Column(Float)
    downside_capture = Column(Float)
    
    # Drawdown metrics
    max_drawdown = Column(Float)
    max_drawdown_duration = Column(Integer)
    current_drawdown = Column(Float)
    
    # Risk-adjusted returns
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    calmar_ratio = Column(Float)
    omega_ratio = Column(Float)
    
    # Value at Risk
    var_95 = Column(Float)
    var_99 = Column(Float)
    cvar_95 = Column(Float)
    
    # Distribution metrics
    skewness = Column(Float)
    kurtosis = Column(Float)
    
    # Correlation
    correlation_spy = Column(Float)
    correlation_agg = Column(Float)
    
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
    issue_type = Column(String(50), nullable=False)
    severity = Column(String(20))
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