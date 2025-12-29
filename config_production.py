# config_production.py
# Production Configuration - Uses Environment Variables
# This replaces config_v6.py for cloud deployment

import os
from pathlib import Path

# ============================================================================
# ENVIRONMENT DETECTION
# ============================================================================

IS_PRODUCTION = os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RENDER') or os.getenv('PRODUCTION')

# ============================================================================
# PROJECT PATHS (Platform-agnostic)
# ============================================================================

if IS_PRODUCTION:
    # Cloud deployment paths
    PROJECT_ROOT = Path("/app")
    LOGS_DIR = Path("/tmp/logs")
    DATA_DIR = Path("/tmp/data")
else:
    # Local development paths (Windows)
    PROJECT_ROOT = Path(os.getenv('PROJECT_ROOT', 'D:/FolioData/FolioF/PortfolioOptimizationPythonFiles/V6_EODHD_Hybrid'))
    LOGS_DIR = PROJECT_ROOT / "logs"
    DATA_DIR = Path(os.getenv('DATA_DIR', 'D:/FolioData/FolioF'))

# Ensure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# DATABASE CONNECTIONS
# ============================================================================

# PostgreSQL - Primary Database
# In production, use DATABASE_URL from Railway/Render
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # Railway/Render provide this automatically
    # Fix for SQLAlchemy 2.x (postgres:// -> postgresql://)
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    PG_CONNECTION = DATABASE_URL
else:
    # Local development fallback
    POSTGRES_CONFIG = {
        'host': os.getenv('PG_HOST', 'localhost'),
        'port': int(os.getenv('PG_PORT', 5432)),
        'database': os.getenv('PG_DATABASE', 'portfolio_master'),
        'user': os.getenv('PG_USER', 'postgres'),
        'password': os.getenv('PG_PASSWORD', ''),  # NEVER hardcode in production
    }
    PG_CONNECTION = (
        f"postgresql://{POSTGRES_CONFIG['user']}:{POSTGRES_CONFIG['password']}"
        f"@{POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']}/{POSTGRES_CONFIG['database']}"
    )

# SQLite - Working Database (session cache)
# CRITICAL: In Railway, this must point to the persistent volume mount
if IS_PRODUCTION:
    # Railway persistent volume mount path (configured in Railway dashboard)
    SQLITE_DATA_DIR = Path(os.getenv('SQLITE_DATA_PATH', '/app/data'))
    SQLITE_DB_PATH = SQLITE_DATA_DIR / "portfolio_working_v6.db"
else:
    SQLITE_DB_PATH = DATA_DIR / "portfolio_working_v6.db"

# Ensure SQLite directory exists
SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SQLITE_CONNECTION = f"sqlite:///{str(SQLITE_DB_PATH).replace(chr(92), '/')}"

# ============================================================================
# EODHD API CONFIGURATION
# ============================================================================

EODHD_API_TOKEN = os.getenv('EODHD_API_TOKEN', '')
EODHD_BASE_URL = "https://eodhd.com/api"

if not EODHD_API_TOKEN and IS_PRODUCTION:
    raise ValueError("EODHD_API_TOKEN environment variable is required in production")

# API Rate Limits
EODHD_MAX_CALLS_PER_DAY = 100000
EODHD_CALLS_WARNING_THRESHOLD = 90000

# API Timeouts and Retries
API_TIMEOUT_SECONDS = 30
API_MAX_RETRIES = 3
API_RETRY_DELAY_SECONDS = 5

# ============================================================================
# APPLICATION SETTINGS
# ============================================================================

# Flask
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
DEBUG = not IS_PRODUCTION

# Data Loading
HISTORICAL_START_DATE = "1980-01-01"
DEFAULT_LOOKBACK_YEARS = 30
BULK_BATCH_SIZE = 50000
BULK_COMMIT_FREQUENCY = 10000

# ============================================================================
# EXCHANGE CONFIGURATION (unchanged from original)
# ============================================================================

PRIORITY_EXCHANGES = ['US', 'LSE', 'XETRA', 'HK', 'TO', 'PA', 'TW']

BENCHMARK_TICKERS = [
    'SPY.US', 'QQQ.US', 'DIA.US', 'IWM.US',
    'VTI.US', 'VOO.US', 'IVV.US',
    'XLK.US', 'XLF.US', 'XLE.US', 'XLV.US', 'XLI.US',
    'XLY.US', 'XLP.US', 'XLB.US', 'XLRE.US', 'XLU.US', 'XLC.US',
    'EFA.US', 'VEA.US', 'IEFA.US',
    'EEM.US', 'VWO.US', 'IEMG.US',
    'TLT.US', 'IEF.US', 'SHY.US',
    'AGG.US', 'BND.US',
    'LQD.US', 'HYG.US',
    'GLD.US', 'SLV.US',
    'VNQ.US', 'VNQI.US',
]

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# ============================================================================
# DATABASE CONNECTION POOL
# ============================================================================

PG_POOL_SIZE = int(os.getenv('PG_POOL_SIZE', 5))
PG_MAX_OVERFLOW = int(os.getenv('PG_MAX_OVERFLOW', 10))
PG_POOL_TIMEOUT = 30

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_postgres_engine():
    """Get PostgreSQL engine with connection pooling"""
    from sqlalchemy import create_engine
    return create_engine(
        PG_CONNECTION,
        pool_size=PG_POOL_SIZE,
        max_overflow=PG_MAX_OVERFLOW,
        pool_timeout=PG_POOL_TIMEOUT,
        pool_pre_ping=True,  # Verify connections before use
        echo=False,
    )

def get_sqlite_engine():
    """Get SQLite engine for session cache"""
    from sqlalchemy import create_engine, text
    engine = create_engine(SQLITE_CONNECTION, echo=False)
    
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        conn.execute(text("PRAGMA synchronous=NORMAL;"))
        conn.execute(text("PRAGMA cache_size=-64000;"))
        conn.commit()
    
    return engine

def validate_config():
    """Validate configuration on startup"""
    errors = []
    
    if IS_PRODUCTION:
        if not EODHD_API_TOKEN:
            errors.append("EODHD_API_TOKEN not set")
        if not DATABASE_URL:
            errors.append("DATABASE_URL not set")
        if SECRET_KEY == 'dev-key-change-in-production':
            errors.append("SECRET_KEY should be changed in production")
    
    if errors:
        print("⚠️  CONFIGURATION ERRORS:")
        for error in errors:
            print(f"   - {error}")
        return False
    
    return True

# Validate on import
validate_config()
