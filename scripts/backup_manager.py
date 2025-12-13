# Script: Backup Manager
# PURPOSE: Creates a full SQL backup of the database
# RUN THIS: Daily, or after major data loads

import sys
import os
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_v6

# CONFIGURATION
# Update this if your bin folder is different!
PG_BIN_PATH = r"D:\PostgreSQL_18.1\bin"  
BACKUP_DIR = Path(r"D:\FolioData\FolioF\backups")

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def perform_backup():
    # Ensure backup directory exists
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"portfolio_master_backup_{timestamp}.sql"
    filepath = BACKUP_DIR / filename
    
    logger.info("="*60)
    logger.info(f"💾 STARTING BACKUP: {filename}")
    logger.info("="*60)
    
    # Construct the pg_dump command
    # -F c : Custom format (compressed, fastest)
    # -b : Include blobs
    # -v : Verbose
    dump_exe = os.path.join(PG_BIN_PATH, "pg_dump.exe")
    
    cmd = [
        dump_exe,
        "-h", config_v6.POSTGRES_CONFIG['host'],
        "-p", str(config_v6.POSTGRES_CONFIG['port']),
        "-U", config_v6.POSTGRES_CONFIG['user'],
        "-F", "c", 
        "-b", 
        "-v", 
        "-f", str(filepath),
        config_v6.POSTGRES_CONFIG['database']
    ]
    
    # Set password in environment variable so it doesn't prompt
    env = os.environ.copy()
    env['PGPASSWORD'] = config_v6.POSTGRES_CONFIG['password']
    
    try:
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            env=env,
            text=True
        )
        
        # Stream output
        while True:
            output = process.stderr.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
                
        if process.returncode == 0:
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            logger.info(f"\n✅ BACKUP SUCCESSFUL!")
            logger.info(f"📍 Location: {filepath}")
            logger.info(f"📦 Size: {size_mb:.2f} MB")
        else:
            logger.error("\n❌ BACKUP FAILED")
            
    except Exception as e:
        logger.error(f"Error executing backup: {e}")

if __name__ == "__main__":
    perform_backup()