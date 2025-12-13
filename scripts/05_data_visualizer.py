1# Script 05: Data Visualizer & Quality Inspector
# Generates charts to verify data integrity before optimization

import sys
import logging
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_v6
from models_v6 import get_session

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def fetch_price_data(engine, symbol):
    """Fetch historical data for a symbol into a Pandas DataFrame"""
    query = text("""
        SELECT date, open, high, low, close, adjusted_close, volume 
        FROM asset_prices 
        WHERE symbol = :symbol 
        ORDER BY date ASC
    """)
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"symbol": symbol})
    
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
    return df

def plot_asset_history(df, symbol):
    """Create a professional financial chart to inspect quality"""
    if df.empty:
        logger.warning(f"⚠️ No data found for {symbol}")
        return

    # Setup figure with 2 subplots (Price and Volume)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, 
                                   gridspec_kw={'height_ratios': [3, 1]})
    
    # Plot 1: Adjusted Close vs Raw Close
    # This visualizes Splits and Dividends. If Adjusted diverges from Close, 
    # it means corporate actions were captured (Good).
    ax1.plot(df.index, df['close'], label='Raw Close', color='gray', alpha=0.5, linewidth=1)
    ax1.plot(df.index, df['adjusted_close'], label='Adjusted Close', color='blue', linewidth=1.5)
    
    ax1.set_title(f"Data Quality Inspection: {symbol}")
    ax1.set_ylabel("Price")
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # Plot 2: Volume
    # Look for "Zero Volume" days which might indicate bad data or trading halts
    ax2.bar(df.index, df['volume'], color='black', alpha=0.7, width=1)
    ax2.set_ylabel("Volume")
    ax2.grid(True, alpha=0.3)

    # Formatting Date Axis
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax2.xaxis.set_major_locator(mdates.YearLocator())
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    # Show the plot
    print(f"Displaying plot for {symbol}...")
    plt.show()

def analyze_gaps(df, symbol):
    """Check for missing trading days"""
    if df.empty: return

    # Create a complete range of business days
    start_date = df.index.min()
    end_date = df.index.max()
    business_days = pd.date_range(start=start_date, end=end_date, freq='B') # 'B' is business days (Mon-Fri)
    
    # Identify missing dates (Business days that are not in our DB)
    missing_days = business_days.difference(df.index)
    
    print(f"\n📊 GAP ANALYSIS: {symbol}")
    print(f"   Date Range: {start_date.date()} to {end_date.date()}")
    print(f"   Total Records: {len(df)}")
    print(f"   Potential Missing Business Days: {len(missing_days)}")
    
    if len(missing_days) > 0:
        print("   Last 5 missing business days (sample):")
        for d in missing_days[-5:]:
            print(f"    - {d.date()}")
    else:
        print("   ✅ Continuous data (no missing Mon-Fri days)")

def main():
    print("="*70)
    print("DATA VISUALIZER & INSPECTOR")
    print("="*70)
    
    # Ask user which DB to check
    print("1. PostgreSQL (Master Archive)")
    print("2. SQLite (Working DB)")
    choice = input("Select Database [1]: ").strip()
    
    if choice == '2':
        engine = config_v6.get_sqlite_engine()
        print("Connected to SQLite Working DB")
    else:
        engine = config_v6.get_postgres_engine()
        print("Connected to PostgreSQL Master DB")

    while True:
        print("\n" + "-"*50)
        symbol = input("Enter Ticker to Inspect (e.g., AAPL.US) or 'q' to quit: ").strip().upper()
        
        if symbol == 'Q':
            break
            
        if not symbol:
            continue
            
        try:
            # 1. Get Data
            df = fetch_price_data(engine, symbol)
            
            # 2. Analyze Gaps (Math Check)
            analyze_gaps(df, symbol)
            
            # 3. Plot (Visual Check)
            plot_asset_history(df, symbol)
            
        except Exception as e:
            logger.error(f"Error: {e}")

if __name__ == "__main__":
    main()