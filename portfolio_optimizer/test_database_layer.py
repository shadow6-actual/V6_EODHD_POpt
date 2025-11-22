"""
Test script for database connection and queries
Run this to verify everything is working correctly
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import our new modules
from backend.database import (
    get_db_engine,
    get_db_session,
    check_database_connection,
    get_database_stats,
    search_assets,
    get_asset_by_symbol,
    get_all_exchanges,
    get_price_data,
    get_latest_price,
    get_price_range,
    get_correlation_matrix,
    get_returns_dataframe,
    validate_symbol_exists
)

def print_separator(title=""):
    """Print a nice separator"""
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}\n")
    else:
        print(f"{'='*70}\n")


def test_connection():
    """Test database connection"""
    print_separator("TEST 1: Database Connection")
    
    connected = check_database_connection()
    if connected:
        print("✅ PostgreSQL connection: SUCCESS")
    else:
        print("❌ PostgreSQL connection: FAILED")
        return False
    
    return True


def test_database_stats():
    """Test getting database statistics"""
    print_separator("TEST 2: Database Statistics")
    
    stats = get_database_stats()
    
    if 'error' in stats:
        print(f"❌ Failed to get stats: {stats['error']}")
        return False
    
    print(f"Total Assets:      {stats['total_assets']:,}")
    print(f"Active Assets:     {stats['active_assets']:,}")
    print(f"Inactive Assets:   {stats['inactive_assets']:,}")
    print(f"Price Records:     {stats['total_price_records']:,}")
    print(f"Exchanges:         {stats['exchanges_tracked']}")
    print(f"Database Type:     {stats['database_type']}")
    print(f"Status:            {stats['connection_status']}")
    print("\n✅ Database statistics retrieved successfully")
    
    return True


def test_exchanges():
    """Test getting all exchanges"""
    print_separator("TEST 3: Exchange Listing")
    
    exchanges = get_all_exchanges()
    
    if not exchanges:
        print("❌ No exchanges found")
        return False
    
    print(f"Found {len(exchanges)} exchanges:")
    
    # Print in columns
    for i in range(0, len(exchanges), 5):
        row = exchanges[i:i+5]
        print("  " + "  ".join(f"{ex:8s}" for ex in row))
    
    print("\n✅ Exchange listing successful")
    return True


def test_asset_search():
    """Test asset search functionality"""
    print_separator("TEST 4: Asset Search")
    
    # Test search for AAPL
    search_term = "AAPL"
    print(f"Searching for: {search_term}")
    
    assets = search_assets(search_term, limit=5)
    
    if not assets:
        print(f"❌ No assets found for '{search_term}'")
        return False
    
    print(f"\nFound {len(assets)} results:")
    for asset in assets:
        print(f"  {asset.symbol:15s} {asset.name:40s} ({asset.exchange})")
    
    print("\n✅ Asset search successful")
    return True


def test_asset_lookup():
    """Test getting specific asset"""
    print_separator("TEST 5: Asset Lookup")
    
    symbol = "AAPL.US"
    print(f"Looking up: {symbol}")
    
    asset = get_asset_by_symbol(symbol)
    
    if not asset:
        print(f"❌ Asset not found: {symbol}")
        # Try alternative
        symbol = "AAPL"
        print(f"Trying: {symbol}")
        asset = get_asset_by_symbol(symbol)
    
    if not asset:
        print("❌ Could not find AAPL asset")
        return False
    
    print(f"\nAsset Details:")
    print(f"  Symbol:        {asset.symbol}")
    print(f"  Code:          {asset.code}")
    print(f"  Name:          {asset.name}")
    print(f"  Exchange:      {asset.exchange}")
    print(f"  Asset Type:    {asset.asset_type}")
    print(f"  Active:        {asset.is_active}")
    print(f"  Last Updated:  {asset.last_updated}")
    
    print("\n✅ Asset lookup successful")
    return True, asset.symbol


def test_price_data(symbol):
    """Test getting price data"""
    print_separator("TEST 6: Price Data")
    
    print(f"Getting price data for: {symbol}")
    
    # Get date range
    start, end = get_price_range(symbol)
    
    if not start or not end:
        print(f"❌ No price data available for {symbol}")
        return False
    
    print(f"\nPrice Data Range:")
    print(f"  Earliest: {start}")
    print(f"  Latest:   {end}")
    print(f"  Span:     {(end - start).days} days")
    
    # Get latest price
    latest = get_latest_price(symbol)
    if latest:
        print(f"\nLatest Price:")
        print(f"  Date:     {latest.date}")
        print(f"  Close:    ${latest.close:.2f}")
        if latest.adjusted_close:
            print(f"  Adj Close: ${latest.adjusted_close:.2f}")
    
    # Get last year of data
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365)
    
    print(f"\nFetching 1 year of data ({start_date} to {end_date})...")
    df = get_price_data(symbol, start_date, end_date)
    
    if df.empty:
        print(f"❌ No price data retrieved")
        return False
    
    print(f"  Records: {len(df)}")
    print(f"  Columns: {', '.join(df.columns)}")
    print(f"\nFirst few rows:")
    print(df.head(3))
    
    print("\n✅ Price data retrieval successful")
    return True


def test_returns_calculation():
    """Test returns calculation for multiple assets"""
    print_separator("TEST 7: Returns Calculation")
    
    symbols = ["AAPL.US", "MSFT.US", "GOOGL.US"]
    
    # Try to find valid symbols
    valid_symbols = []
    for sym in symbols:
        if validate_symbol_exists(sym):
            valid_symbols.append(sym)
        else:
            # Try without exchange suffix
            alt_sym = sym.split('.')[0]
            if validate_symbol_exists(alt_sym):
                valid_symbols.append(alt_sym)
    
    if not valid_symbols:
        print("❌ No valid symbols found for returns calculation")
        return False
    
    print(f"Calculating returns for: {', '.join(valid_symbols)}")
    
    # Get 6 months of monthly returns
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=180)
    
    returns_df = get_returns_dataframe(
        valid_symbols,
        start_date=start_date,
        end_date=end_date,
        frequency='M'
    )
    
    if returns_df.empty:
        print("❌ Could not calculate returns")
        return False
    
    print(f"\nMonthly Returns:")
    print(f"  Shape: {returns_df.shape}")
    print(f"  Periods: {len(returns_df)}")
    print(returns_df)
    
    print("\n✅ Returns calculation successful")
    return True, valid_symbols


def test_correlation_matrix(symbols):
    """Test correlation matrix calculation"""
    print_separator("TEST 8: Correlation Matrix")
    
    print(f"Calculating correlations for: {', '.join(symbols)}")
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365)
    
    corr = get_correlation_matrix(symbols, start_date, end_date)
    
    if corr.empty:
        print("❌ Could not calculate correlation matrix")
        return False
    
    print(f"\nCorrelation Matrix:")
    print(corr)
    
    print("\n✅ Correlation matrix calculation successful")
    return True


def run_all_tests():
    """Run all tests"""
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║       PORTFOLIO OPTIMIZER - DATABASE LAYER TEST SUITE             ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Connection
    if test_connection():
        tests_passed += 1
    else:
        tests_failed += 1
        print("\n❌ CRITICAL: Database connection failed. Cannot continue.")
        return
    
    # Test 2: Database Stats
    if test_database_stats():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 3: Exchanges
    if test_exchanges():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 4: Asset Search
    if test_asset_search():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 5: Asset Lookup
    result = test_asset_lookup()
    if result:
        tests_passed += 1
        symbol = result[1] if isinstance(result, tuple) else None
    else:
        tests_failed += 1
        symbol = None
    
    # Test 6: Price Data
    if symbol:
        if test_price_data(symbol):
            tests_passed += 1
        else:
            tests_failed += 1
    else:
        print_separator("TEST 6: SKIPPED (no valid symbol)")
    
    # Test 7: Returns Calculation
    result = test_returns_calculation()
    if result:
        tests_passed += 1
        valid_symbols = result[1] if isinstance(result, tuple) else []
    else:
        tests_failed += 1
        valid_symbols = []
    
    # Test 8: Correlation Matrix
    if valid_symbols and len(valid_symbols) >= 2:
        if test_correlation_matrix(valid_symbols):
            tests_passed += 1
        else:
            tests_failed += 1
    else:
        print_separator("TEST 8: SKIPPED (need multiple valid symbols)")
    
    # Summary
    print_separator("TEST SUMMARY")
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print(f"Total Tests:  {tests_passed + tests_failed}")
    
    if tests_failed == 0:
        print("\n✅✅✅ ALL TESTS PASSED! ✅✅✅")
        print("\nDatabase layer is working correctly!")
        print("Ready to proceed to Phase 2 (Optimizer Migration)")
    else:
        print(f"\n⚠️  {tests_failed} test(s) failed")
        print("Please review the errors above")


if __name__ == "__main__":
    try:
        run_all_tests()
    except Exception as e:
        print(f"\n❌ TEST SUITE CRASHED: {e}")
        import traceback
        traceback.print_exc()
