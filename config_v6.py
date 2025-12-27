# Configuration for V6 EODHD Hybrid System
# Portfolio Optimization Database - Master (PostgreSQL) + Working (SQLite)

import os
from pathlib import Path

# ============================================================================
# PROJECT PATHS
# ============================================================================

PROJECT_ROOT = Path(r"D:/FolioData/FolioF/PortfolioOptimizationPythonFiles/V6_EODHD_Hybrid")
LOGS_DIR = PROJECT_ROOT / "logs"
DATA_DIR = Path(r"D:/FolioData/FolioF")

# Ensure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# DATABASE CONNECTIONS
# ============================================================================

# PostgreSQL - Master Database (all 150K tickers)
POSTGRES_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'portfolio_master',
    #'database': 'portfolio_master_test',  # TEST MODE
    'user': 'postgres',
    'password': 'Germany11',  
}

# Build PostgreSQL connection string
PG_CONNECTION = (
    f"postgresql://{POSTGRES_CONFIG['user']}:{POSTGRES_CONFIG['password']}"
    f"@{POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']}/{POSTGRES_CONFIG['database']}"
)

# SQLite - Working Database (your active portfolio + watchlist)
SQLITE_DB_PATH = DATA_DIR / "portfolio_working_v6.db"
SQLITE_CONNECTION = f"sqlite:///{str(SQLITE_DB_PATH).replace(chr(92), '/')}"

# ============================================================================
# EODHD API CONFIGURATION
# ============================================================================

EODHD_API_TOKEN = "6911009b164320.89580145"  
EODHD_BASE_URL = "https://eodhd.com/api"

# API Rate Limits
EODHD_MAX_CALLS_PER_DAY = 100000
EODHD_CALLS_WARNING_THRESHOLD = 90000  # Warn at 90% usage

# API Timeouts and Retries
API_TIMEOUT_SECONDS = 30
API_MAX_RETRIES = 3
API_RETRY_DELAY_SECONDS = 5

# ============================================================================
# DATA LOADING CONFIGURATION
# ============================================================================

# Update frequency
UPDATE_FREQUENCY = "weekly"  # Options: daily, weekly, monthly

# Historical data depth
HISTORICAL_START_DATE = "1980-01-01"  # Load data from this date onwards
DEFAULT_LOOKBACK_YEARS = 30

# Bulk loading settings
BULK_BATCH_SIZE = 50000  # Rows to insert per batch (PostgreSQL handles this easily)
BULK_COMMIT_FREQUENCY = 10000  # Commit every N rows

# Data quality
MIN_TRADING_DAYS_PER_YEAR = 200  # Flag tickers with less activity
MAX_PRICE_JUMP_PERCENT = 200  # Flag potential data errors (200% daily change)

# ============================================================================
# EXCHANGE CONFIGURATION
# ============================================================================

# All exchanges to track - ONLY VALID EODHD EXCHANGE CODES
# Official list: https://eodhd.com/financial-apis/list-supported-exchanges
EXCHANGES_TO_TRACK = [
    # North America
    'US',      # United States (NYSE, NASDAQ, AMEX consolidated)
    'TO',      # Toronto Stock Exchange (TSX)
    'V',       # TSX Venture Exchange
    'NEO',     # NEO Exchange (Canada)
    'CN',      # Canadian Securities Exchange
    'MX',      # Mexico Stock Exchange
    
    # Europe - Major Markets
    'LSE',     # London Stock Exchange
    'XETRA',   # Deutsche Börse XETRA (Germany)
    'F',       # Frankfurt Stock Exchange
    'MU',      # Munich Stock Exchange
    'STU',     # Stuttgart Stock Exchange
    'HA',      # Hamburg Stock Exchange
    'DU',      # Dusseldorf Stock Exchange
    
    # Europe - Euronext
    'PA',      # Euronext Paris
    'AS',      # Euronext Amsterdam
    'BR',      # Euronext Brussels
    'LS',      # Euronext Lisbon
    
    # Europe - Nordic
    'OL',      # Oslo Børs (Norway)
    'ST',      # Nasdaq Stockholm (Sweden)
    'CO',      # Nasdaq Copenhagen (Denmark)
    'HE',      # Nasdaq Helsinki (Finland)
    'IC',      # Nasdaq Iceland
    
    # Europe - Other
    'SW',      # SIX Swiss Exchange
    'VI',      # Vienna Stock Exchange (Austria)
    'MC',      # Bolsa de Madrid (Spain)
    'WAR',     # Warsaw Stock Exchange (Poland)
    'PR',      # Prague Stock Exchange (Czech Republic)
    'BUD',     # Budapest Stock Exchange (Hungary)
    'AT',      # Athens Stock Exchange (Greece)
    'IR',      # Irish Stock Exchange
    'RO',      # Bucharest Stock Exchange (Romania)
    'IL',      # Tel Aviv Stock Exchange (Israel)
    
    # Asia-Pacific - Major Markets
    'HK',      # Hong Kong Stock Exchange
    'SHG',     # Shanghai Stock Exchange (China)
    'SHE',     # Shenzhen Stock Exchange (China)
    'TW',      # Taiwan Stock Exchange (TWSE)
    'TWO',     # Taipei Exchange (OTC)
    'KO',      # Korea Exchange (KRX) - Main Board
    'KQ',      # Korea Exchange - KOSDAQ
    'AU',      # Australian Securities Exchange
    
    # Asia-Pacific - Emerging Markets
    'NSE',     # National Stock Exchange of India
    'BSE',     # Bombay Stock Exchange (India) - Note: Limited data
    'KLSE',    # Bursa Malaysia
    'BK',      # Stock Exchange of Thailand
    'JK',      # Indonesia Stock Exchange
    'PSE',     # Philippine Stock Exchange
    'SG',      # Singapore Exchange
    'VN',      # Ho Chi Minh Stock Exchange (Vietnam)
    
    # Middle East & Africa
    'SR',      # Saudi Stock Exchange (Tadawul)
    'EGX',     # Egyptian Exchange
    'JSE',     # Johannesburg Stock Exchange (South Africa)
    'KAR',     # Pakistan Stock Exchange (Karachi)
    
    # Latin America
    'SA',      # B3 - Brasil Bolsa Balcão (Brazil)
    'BA',      # Buenos Aires Stock Exchange (Argentina)
    'SN',      # Bolsa de Santiago (Chile)
    'MX',      # Bolsa Mexicana de Valores (Mexico)
    'LIM',     # Lima Stock Exchange (Peru)
    'CM',      # Colombia Stock Exchange
    
    # ❌ REMOVED - NOT SUPPORTED BY EODHD:
    # 'JPX' - Japan not available
    # 'MI' - Milan not available
    # 'IS' - Istanbul not available  
    # 'NZE' - New Zealand not available
]

# Priority exchanges (loaded first, updated more frequently)
# ONLY INCLUDE EXCHANGES FROM THE LIST ABOVE
PRIORITY_EXCHANGES = ['US', 'LSE', 'XETRA', 'HK', 'TO', 'PA', 'TW']

# Asset types to include (you said "all assets")
ASSET_TYPES_TO_TRACK = [
    'Common Stock',
    'Preferred Stock',
    'ETF',
    'FUND',  # Mutual Funds
    'INDEX',
    'BOND',
    'REIT',
    'Closed-End Fund',
    'Unit',
    'Right',
    'Warrant',
]

# ============================================================================
# WORKING DATABASE (SQLite) CONFIGURATION
# ============================================================================

# Criteria for automatically including tickers in working database
WORKING_DB_AUTO_INCLUDE = {
    'min_market_cap_usd': 1_000_000_000,  # $1B+ companies
    'min_avg_volume': 100_000,            # 100K+ shares daily
    'exchanges': ['US', 'LSE', 'XETRA', 'HK', 'T'],  # Major exchanges
    'max_tickers_per_exchange': 500,      # Top 500 from each
}

# Your portfolio tickers (manually specified) - EDIT THIS!
MY_PORTFOLIO_TICKERS = [
    # Add your actual holdings here, format: 'SYMBOL.EXCHANGE'
    # Examples:
    # 'AAPL.US',
    # 'MSFT.US',
    # 'GOOGL.US',
]

# Your watchlist - EDIT THIS!
MY_WATCHLIST_TICKERS = [
    # Add tickers you're researching
]

# Benchmark indices and ETFs (always included)
BENCHMARK_TICKERS = [
    # US Indices
    'SPY.US', 'QQQ.US', 'DIA.US', 'IWM.US',  # Major index ETFs
    'VTI.US', 'VOO.US', 'IVV.US',             # Total market/S&P 500
    
    # Sector ETFs
    'XLK.US', 'XLF.US', 'XLE.US', 'XLV.US', 'XLI.US',
    'XLY.US', 'XLP.US', 'XLB.US', 'XLRE.US', 'XLU.US', 'XLC.US',
    
    # International
    'EFA.US', 'VEA.US', 'IEFA.US',  # Developed markets
    'EEM.US', 'VWO.US', 'IEMG.US',  # Emerging markets
    'FXI.US',                        # China
    
    # Bonds
    'TLT.US', 'IEF.US', 'SHY.US',   # Treasuries
    'AGG.US', 'BND.US',              # Aggregate bonds
    'LQD.US', 'HYG.US',              # Corporate bonds
    'TIP.US',                         # TIPS
    
    # Commodities
    'GLD.US', 'SLV.US', 'USO.US', 'DBA.US',
    
    # Real Estate
    'VNQ.US', 'VNQI.US',
    
    # Alternatives
    'DBMF.US',  # Managed futures
]

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL = "INFO"  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Log files
MAIN_LOG_FILE = LOGS_DIR / "portfolio_system_v6.log"
API_LOG_FILE = LOGS_DIR / "eodhd_api_calls.log"
ERROR_LOG_FILE = LOGS_DIR / "errors.log"
DATA_QUALITY_LOG_FILE = LOGS_DIR / "data_quality.log"

# Log rotation (prevent huge files)
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5  # Keep 5 old log files

# ============================================================================
# PERFORMANCE & OPTIMIZATION
# ============================================================================

# PostgreSQL connection pool
PG_POOL_SIZE = 5
PG_MAX_OVERFLOW = 10
PG_POOL_TIMEOUT = 30

# Parallel processing
PARALLEL_WORKERS = 4  # For multi-exchange processing
USE_MULTIPROCESSING = True

# Memory management
CHUNK_SIZE_ROWS = 10000  # Process data in chunks

# ============================================================================
# VALIDATION & ALERTS
# ============================================================================

# Email alerts (optional - configure if you want notifications)
ENABLE_EMAIL_ALERTS = False
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'your_email@gmail.com',
    'sender_password': 'your_app_password',
    'recipient_email': 'your_email@gmail.com',
}

# Alert conditions
ALERT_ON_API_LIMIT_90_PERCENT = True
ALERT_ON_DATA_QUALITY_ISSUES = True
ALERT_ON_UPDATE_FAILURE = True

# ============================================================================
# FEATURE FLAGS
# ============================================================================

# Enable/disable specific features
FEATURES = {
    'load_splits_dividends': True,
    'calculate_risk_metrics': True,
    'validate_data_quality': True,
    'compress_old_data': False,  # Archive data older than X years
    'export_to_csv_backup': True,
    'generate_summary_reports': True,
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_all_working_tickers():
    """Get complete list of tickers for working database"""
    return list(set(
        MY_PORTFOLIO_TICKERS +
        MY_WATCHLIST_TICKERS +
        BENCHMARK_TICKERS
    ))

def is_priority_exchange(exchange_code):
    """Check if exchange is in priority list"""
    return exchange_code in PRIORITY_EXCHANGES

def get_postgres_engine():
    """Get PostgreSQL engine (lazy import to avoid circular dependencies)"""
    from sqlalchemy import create_engine
    return create_engine(
        PG_CONNECTION,
        pool_size=PG_POOL_SIZE,
        max_overflow=PG_MAX_OVERFLOW,
        pool_timeout=PG_POOL_TIMEOUT,
        echo=False,
    )

def get_sqlite_engine():
    """Get SQLite engine"""
    from sqlalchemy import create_engine, text
    engine = create_engine(SQLITE_CONNECTION, echo=False)
    
    # SQLite optimizations
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        conn.execute(text("PRAGMA synchronous=NORMAL;"))
        conn.execute(text("PRAGMA cache_size=-64000;"))
        conn.commit()
    
    return engine

# ============================================================================
# VALIDATION
# ============================================================================

def validate_config():
    """Validate configuration on import"""
    errors = []
    
    if EODHD_API_TOKEN == "YOUR_EODHD_API_TOKEN_HERE":
        errors.append("EODHD_API_TOKEN not set in config_v6.py")
    
    if POSTGRES_CONFIG['password'] == "YOUR_PASSWORD_HERE":
        errors.append("PostgreSQL password not set in config_v6.py")
    
    if errors:
        print("⚠️  CONFIGURATION ERRORS:")
        for error in errors:
            print(f"   - {error}")
        print("\nPlease edit config_v6.py and set the required values.")
        return False
    
    return True

# Validate on import
if __name__ != "__main__":
    validate_config()
