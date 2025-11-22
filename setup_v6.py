# Setup Script for V6 EODHD Hybrid System
# Run this ONCE to initialize PostgreSQL database and validate configuration

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if all required Python packages are installed"""
    logger.info("🔍 Checking dependencies...")
    
    required_packages = {
        'sqlalchemy': 'SQLAlchemy',
        'psycopg2': 'psycopg2-binary',
        'pandas': 'pandas',
        'requests': 'requests',
        'numpy': 'numpy',
    }
    
    missing = []
    
    for package, install_name in required_packages.items():
        try:
            __import__(package)
            logger.info(f"  ✅ {package}")
        except ImportError:
            logger.error(f"  ❌ {package} (install with: pip install {install_name})")
            missing.append(install_name)
    
    if missing:
        logger.error(f"\n❌ Missing packages. Install with:")
        logger.error(f"   pip install {' '.join(missing)}")
        return False
    
    logger.info("✅ All dependencies installed\n")
    return True


def validate_config():
    """Validate configuration file"""
    logger.info("🔍 Validating configuration...")
    
    try:
        # Import config to trigger validation
        sys.path.insert(0, str(Path(__file__).parent))
        import config_v6 as config
        
        # Check critical settings
        errors = []
        
        if config.EODHD_API_TOKEN == "YOUR_EODHD_API_TOKEN_HERE":
            errors.append("EODHD_API_TOKEN not set")
        
        if config.POSTGRES_CONFIG['password'] == "YOUR_PASSWORD_HERE":
            errors.append("PostgreSQL password not set")
        
        if errors:
            logger.error("❌ Configuration errors:")
            for error in errors:
                logger.error(f"   - {error}")
            logger.error("\n📝 Please edit config_v6.py and set:")
            logger.error("   - EODHD_API_TOKEN (from your EODHD account)")
            logger.error("   - POSTGRES_CONFIG['password'] (your PostgreSQL password)")
            return False
        
        logger.info("✅ Configuration valid\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error loading config: {e}")
        return False


def test_postgres_connection():
    """Test PostgreSQL connection"""
    logger.info("🔍 Testing PostgreSQL connection...")
    
    try:
        import config_v6 as config
        from sqlalchemy import create_engine, text
        
        # Try to connect
        engine = create_engine(config.PG_CONNECTION, echo=False)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            logger.info(f"  ✅ Connected to PostgreSQL")
            logger.info(f"  Version: {version.split(',')[0]}")
        
        logger.info("✅ PostgreSQL connection successful\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
        logger.error("\n🔧 Troubleshooting:")
        logger.error("   1. Is PostgreSQL running? Check with: pg_ctl status")
        logger.error("   2. Is the password correct in config_v6.py?")
        logger.error("   3. Does the database 'portfolio_master' exist?")
        logger.error("      Create it with: createdb -U postgres portfolio_master")
        return False


def test_eodhd_api():
    """Test EODHD API connection"""
    logger.info("🔍 Testing EODHD API connection...")
    
    try:
        import config_v6 as config
        from eodhd_client import EODHDClient
        
        # Create client
        client = EODHDClient(config.EODHD_API_TOKEN)
        
        # Try a simple API call (get exchanges list)
        exchanges = client.get_exchanges_list()
        
        if exchanges and len(exchanges) > 0:
            logger.info(f"  ✅ API connection successful")
            logger.info(f"  Available exchanges: {len(exchanges)}")
            logger.info(f"  API calls used today: {client.calls_today}")
        else:
            logger.error("  ❌ API returned empty response")
            return False
        
        logger.info("✅ EODHD API connection successful\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ EODHD API connection failed: {e}")
        logger.error("\n🔧 Troubleshooting:")
        logger.error("   1. Is your API token correct in config_v6.py?")
        logger.error("   2. Check your EODHD subscription at: https://eodhd.com/cp/settings")
        logger.error("   3. Have you reached your daily API limit?")
        return False


def initialize_postgres_database():
    """Initialize PostgreSQL database with tables"""
    logger.info("🔍 Initializing PostgreSQL database...")
    
    try:
        import config_v6 as config
        import models_v6
        
        # Get engine
        engine = config.get_postgres_engine()
        
        # Create all tables
        models_v6.create_all_tables(engine)
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        logger.info(f"  ✅ Created {len(tables)} tables:")
        for table in tables:
            logger.info(f"     - {table}")
        
        logger.info("✅ PostgreSQL database initialized\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False


def create_sqlite_working_database():
    """Create SQLite working database (empty for now)"""
    logger.info("🔍 Creating SQLite working database...")
    
    try:
        import config_v6 as config
        import models_v6
        
        # Get engine
        engine = config.get_sqlite_engine()
        
        # Create all tables
        models_v6.create_all_tables(engine)
        
        # Verify
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        logger.info(f"  ✅ Created SQLite database at: {config.SQLITE_DB_PATH}")
        logger.info(f"  Tables: {len(tables)}")
        
        logger.info("✅ SQLite working database created\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ SQLite creation failed: {e}")
        return False


def print_next_steps():
    """Print next steps for user"""
    logger.info("=" * 70)
    logger.info("🎉 SETUP COMPLETE!")
    logger.info("=" * 70)
    logger.info("\n📋 Next Steps:\n")
    logger.info("1. Load universe of all tickers:")
    logger.info("   python scripts/01_load_universe.py")
    logger.info("")
    logger.info("2. Load historical price data:")
    logger.info("   python scripts/02_load_historical_data.py")
    logger.info("")
    logger.info("3. Set up weekly updates:")
    logger.info("   python scripts/03_setup_weekly_update.py")
    logger.info("")
    logger.info("4. Materialize working database:")
    logger.info("   python scripts/04_materialize_sqlite.py")
    logger.info("")
    logger.info("=" * 70)
    logger.info("\n💡 Tips:")
    logger.info("   - Initial data load will take several hours")
    logger.info("   - You can monitor progress in logs/ directory")
    logger.info("   - API usage is tracked in database (api_usage table)")
    logger.info("")


def main():
    """Main setup function"""
    logger.info("=" * 70)
    logger.info("V6 EODHD HYBRID SYSTEM - SETUP")
    logger.info("=" * 70)
    logger.info("")
    
    steps = [
        ("Checking dependencies", check_dependencies),
        ("Validating configuration", validate_config),
        ("Testing PostgreSQL connection", test_postgres_connection),
        ("Testing EODHD API", test_eodhd_api),
        ("Initializing PostgreSQL database", initialize_postgres_database),
        ("Creating SQLite working database", create_sqlite_working_database),
    ]
    
    for step_name, step_func in steps:
        logger.info(f"⚙️  {step_name}...")
        if not step_func():
            logger.error(f"\n❌ Setup failed at: {step_name}")
            logger.error("Please fix the issues above and run setup again.")
            sys.exit(1)
        logger.info("")
    
    print_next_steps()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n❌ Setup failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
