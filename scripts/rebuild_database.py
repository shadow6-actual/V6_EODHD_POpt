# Script: Rebuild Database
# PURPOSE: Drops corrupt DB, Creates fresh DB, Initializes Tables, Loads Universe
# RUN THIS IN SPYDER

import sys
import os
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pathlib import Path
import runpy 

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_v6

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def terminate_connections(cursor, db_name):
    """Forcefully kills all connections to the target database"""
    logger.info(f"🔫 Terminating existing connections to '{db_name}'...")
    kill_query = f"""
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '{db_name}'
          AND pid <> pg_backend_pid();
    """
    cursor.execute(kill_query)
    logger.info("   ✅ Connections terminated.")

def recreate_database():
    """Connects to System DB to drop and recreate portfolio_master"""
    logger.info("🔨 Connecting to System Database...")
    
    # Connect to 'postgres' (the default system database)
    conn = psycopg2.connect(
        user=config_v6.POSTGRES_CONFIG['user'],
        password=config_v6.POSTGRES_CONFIG['password'],
        host=config_v6.POSTGRES_CONFIG['host'],
        port=config_v6.POSTGRES_CONFIG['port'],
        dbname='postgres' 
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    db_name = config_v6.POSTGRES_CONFIG['database']
    
    # Check if exists
    cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
    exists = cursor.fetchone()
    
    if exists:
        # STEP 1: KILL ZOMBIE CONNECTIONS
        terminate_connections(cursor, db_name)
        
        # STEP 2: DROP
        logger.warning(f"⚠️  Database '{db_name}' exists. DROPPING it...")
        cursor.execute(f"DROP DATABASE {db_name}")
        logger.info("   ✅ Dropped.")
    
    # STEP 3: CREATE
    logger.info(f"🏗️  Creating Database '{db_name}'...")
    cursor.execute(f"CREATE DATABASE {db_name}")
    logger.info("   ✅ Created.")
    
    cursor.close()
    conn.close()

def main():
    logger.info("="*70)
    logger.info("🚨 SYSTEM REBUILD INITIATED")
    logger.info("="*70)
    
    # 1. Recreate Empty Database
    try:
        recreate_database()
    except Exception as e:
        logger.error(f"❌ Failed to create database: {e}")
        return

    # 2. Initialize Tables (Run setup_v6 logic)
    logger.info("\n" + "="*30 + "\n⚙️  INITIALIZING TABLES\n" + "="*30)
    try:
        import setup_v6
        # Force reload to avoid stale connections in cached modules
        import importlib
        importlib.reload(setup_v6)
        setup_v6.initialize_postgres_database()
    except Exception as e:
        logger.error(f"❌ Failed to init tables: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Load Universe (Run 01_load_universe.py)
    logger.info("\n" + "="*30 + "\n🌍 LOADING UNIVERSE (150k Tickers)\n" + "="*30)
    script_path = Path(__file__).parent / "01_load_universeV2.py"
    try:
        runpy.run_path(str(script_path), run_name="__main__")
    except Exception as e:
        logger.error(f"❌ Failed to load universe: {e}")
        return

    logger.info("\n" + "="*70)
    logger.info("🎉 REBUILD COMPLETE")
    logger.info("="*70)
    logger.info("👉 NEXT STEP: Run 'backup_manager.py' to save this checkpoint!")

if __name__ == "__main__":
    main()