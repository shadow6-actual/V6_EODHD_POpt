#Database review:
# Quick Database Inspector
import config_v6
from models_v6 import Asset, AssetPrice, get_session
from sqlalchemy import inspect, text

print("=" * 70)
print("DATABASE INSPECTOR")
print("=" * 70)
print()

# ============================================================================
# POSTGRESQL INSPECTION
# ============================================================================
print("📊 POSTGRESQL (Master Database)")
print("=" * 70)

pg_engine = config_v6.get_postgres_engine()

with get_session(pg_engine) as session:
    # Total assets
    total_assets = session.query(Asset).count()
    active_assets = session.query(Asset).filter_by(is_active=True).count()
    inactive_assets = session.query(Asset).filter_by(is_active=False).count()
    
    print(f"Assets:")
    print(f"  Total: {total_assets:,}")
    print(f"  Active: {active_assets:,}")
    print(f"  Inactive: {inactive_assets:,}")
    print()
    
    # Assets by exchange (top 10)
    print("Top 10 Exchanges by Asset Count:")
    result = session.execute(text("""
        SELECT exchange, COUNT(*) as count 
        FROM assets 
        WHERE is_active = true
        GROUP BY exchange 
        ORDER BY count DESC 
        LIMIT 10
    """))
    for row in result:
        print(f"  {row.exchange}: {row.count:,}")
    print()
    
    # Total price records
    total_prices = session.query(AssetPrice).count()
    print(f"Price Records: {total_prices:,}")
    print()
    
    # Sample assets
    print("Sample Assets (first 5):")
    samples = session.query(Asset).limit(5).all()
    for asset in samples:
        print(f"  {asset.symbol} | {asset.name} | {asset.exchange} | Active: {asset.is_active}")
    print()
    
    # Check for 402 errors (inactive TO assets)
    to_inactive = session.query(Asset).filter_by(exchange='TO', is_active=False).count()
    to_active = session.query(Asset).filter_by(exchange='TO', is_active=True).count()
    print(f"Toronto Exchange (TO):")
    print(f"  Active: {to_active:,}")
    print(f"  Inactive (potential 402 errors): {to_inactive:,}")
    print()

# List all tables
print("PostgreSQL Tables:")
inspector = inspect(pg_engine)
for table_name in inspector.get_table_names():
    print(f"  - {table_name}")
print()

# ============================================================================
# SQLITE INSPECTION
# ============================================================================
print("=" * 70)
print("💾 SQLITE (Working Database)")
print("=" * 70)

sqlite_engine = config_v6.get_sqlite_engine()

with get_session(sqlite_engine) as session:
    # Check if any data exists
    total_assets = session.query(Asset).count()
    total_prices = session.query(AssetPrice).count()
    
    print(f"Assets: {total_assets:,}")
    print(f"Price Records: {total_prices:,}")
    print()
    
    if total_assets > 0:
        print("Sample Assets (first 5):")
        samples = session.query(Asset).limit(5).all()
        for asset in samples:
            print(f"  {asset.symbol} | {asset.name}")
        print()
    else:
        print("⚠️  No data in SQLite yet. Run 04_materialize_sqlite.py")
        print()

# List all tables
print("SQLite Tables:")
inspector = inspect(sqlite_engine)
for table_name in inspector.get_table_names():
    print(f"  - {table_name}")
print()

# ============================================================================
# FIELD INSPECTION
# ============================================================================
print("=" * 70)
print("📋 ASSET TABLE FIELDS")
print("=" * 70)

inspector = inspect(pg_engine)
columns = inspector.get_columns('assets')
print("\nAsset Table Columns:")
for col in columns:
    print(f"  {col['name']:<25} {str(col['type']):<20} Nullable: {col['nullable']}")
print()

print("=" * 70)
print("📋 ASSET_PRICES TABLE FIELDS")
print("=" * 70)

columns = inspector.get_columns('asset_prices')
print("\nAssetPrice Table Columns:")
for col in columns:
    print(f"  {col['name']:<25} {str(col['type']):<20} Nullable: {col['nullable']}")

print()
print("=" * 70)
print("✅ Inspection Complete")
print("=" * 70)

# Price Coverage and Data Quality Inspector
import config_v6
from models_v6 import Asset, AssetPrice, get_session
from sqlalchemy import text, func
from datetime import datetime

print("=" * 70)
print("PRICE DATA COVERAGE ANALYSIS")
print("=" * 70)
print()

pg_engine = config_v6.get_postgres_engine()

with get_session(pg_engine) as session:
    
    # ========================================================================
    # OVERALL COVERAGE
    # ========================================================================
    print("📊 OVERALL COVERAGE")
    print("-" * 70)
    
    total_active = session.query(Asset).filter_by(is_active=True).count()
    
    # Assets with ANY price data
    assets_with_prices = session.execute(text("""
        SELECT COUNT(DISTINCT symbol) 
        FROM asset_prices
    """)).scalar()
    
    # Assets with NO price data
    assets_without_prices = total_active - assets_with_prices
    
    coverage_pct = (assets_with_prices / total_active * 100) if total_active > 0 else 0
    
    print(f"Total Active Assets: {total_active:,}")
    print(f"Assets WITH Price Data: {assets_with_prices:,} ({coverage_pct:.1f}%)")
    print(f"Assets WITHOUT Price Data: {assets_without_prices:,}")
    print()
    
    # Total price records
    total_records = session.query(AssetPrice).count()
    avg_records = total_records / assets_with_prices if assets_with_prices > 0 else 0
    print(f"Total Price Records: {total_records:,}")
    print(f"Average Records per Asset: {avg_records:.0f}")
    print()
    
    # ========================================================================
    # COVERAGE BY EXCHANGE
    # ========================================================================
    print("=" * 70)
    print("📈 COVERAGE BY EXCHANGE")
    print("-" * 70)
    
    result = session.execute(text("""
        SELECT 
            a.exchange,
            COUNT(DISTINCT a.symbol) as total_assets,
            COUNT(DISTINCT p.symbol) as assets_with_data,
            COALESCE(SUM(price_count), 0) as total_prices,
            ROUND(100.0 * COUNT(DISTINCT p.symbol) / COUNT(DISTINCT a.symbol), 1) as coverage_pct
        FROM assets a
        LEFT JOIN (
            SELECT symbol, COUNT(*) as price_count
            FROM asset_prices
            GROUP BY symbol
        ) p ON a.symbol = p.symbol
        WHERE a.is_active = true
        GROUP BY a.exchange
        ORDER BY total_assets DESC
        LIMIT 20
    """))
    
    print(f"{'Exchange':<15} {'Total':<10} {'Loaded':<10} {'Remaining':<10} {'Coverage':<10} {'Avg Records'}")
    print("-" * 70)
    
    for row in result:
        remaining = row.total_assets - row.assets_with_data
        avg_records = row.total_prices / row.assets_with_data if row.assets_with_data > 0 else 0
        print(f"{row.exchange:<15} {row.total_assets:<10,} {row.assets_with_data:<10,} "
              f"{remaining:<10,} {row.coverage_pct:<9.1f}% {avg_records:<.0f}")
    
    print()
    
    # ========================================================================
    # DATA FRESHNESS
    # ========================================================================
    print("=" * 70)
    print("📅 DATA FRESHNESS")
    print("-" * 70)
    
    result = session.execute(text("""
        SELECT 
            a.exchange,
            MAX(p.date) as latest_date,
            MIN(p.date) as earliest_date,
            COUNT(DISTINCT a.symbol) as assets_with_data
        FROM assets a
        INNER JOIN asset_prices p ON a.symbol = p.symbol
        WHERE a.is_active = true
        GROUP BY a.exchange
        ORDER BY assets_with_data DESC
        LIMIT 10
    """))
    
    print(f"{'Exchange':<15} {'Earliest':<15} {'Latest':<15} {'Assets'}")
    print("-" * 70)
    
    for row in result:
        print(f"{row.exchange:<15} {str(row.earliest_date):<15} {str(row.latest_date):<15} {row.assets_with_data:,}")
    
    print()
    
    # ========================================================================
    # RECENTLY LOADED ASSETS
    # ========================================================================
    print("=" * 70)
    print("🕐 RECENTLY LOADED ASSETS (Last 20)")
    print("-" * 70)
    
    result = session.execute(text("""
        SELECT 
            a.symbol,
            a.name,
            a.exchange,
            COUNT(p.price_id) as price_records,
            MIN(p.date) as earliest_price,
            MAX(p.date) as latest_price,
            MAX(p.loaded_at) as loaded_at
        FROM assets a
        INNER JOIN asset_prices p ON a.symbol = p.symbol
        WHERE a.is_active = true
        GROUP BY a.symbol, a.name, a.exchange
        ORDER BY MAX(p.loaded_at) DESC
        LIMIT 20
    """))
    
    for row in result:
        print(f"\n{row.symbol} ({row.exchange})")
        print(f"  Name: {row.name}")
        print(f"  Records: {row.price_records:,}")
        print(f"  Date Range: {row.earliest_price} to {row.latest_price}")
        print(f"  Loaded: {row.loaded_at}")
    
    print()
    
    # ========================================================================
    # ASSETS NEVER LOADED (Sample)
    # ========================================================================
    print("=" * 70)
    print("⚠️  NEVER LOADED ASSETS (Sample 20)")
    print("-" * 70)
    
    result = session.execute(text("""
        SELECT 
            a.symbol,
            a.name,
            a.exchange,
            a.asset_type,
            a.is_active
        FROM assets a
        LEFT JOIN asset_prices p ON a.symbol = p.symbol
        WHERE p.symbol IS NULL
        AND a.is_active = true
        ORDER BY a.exchange, a.symbol
        LIMIT 20
    """))
    
    print(f"{'Symbol':<20} {'Exchange':<10} {'Type':<15} {'Name'}")
    print("-" * 70)
    
    for row in result:
        name = (row.name[:30] + '...') if row.name and len(row.name) > 30 else (row.name or '')
        print(f"{row.symbol:<20} {row.exchange:<10} {row.asset_type:<15} {name}")
    
    print()
    
    # ========================================================================
    # TORONTO EXCHANGE SPECIFIC (since you have 402 errors)
    # ========================================================================
    print("=" * 70)
    print("🍁 TORONTO EXCHANGE (TO) DETAILED ANALYSIS")
    print("-" * 70)
    
    to_total = session.query(Asset).filter_by(exchange='TO', is_active=True).count()
    to_with_data = session.execute(text("""
        SELECT COUNT(DISTINCT a.symbol)
        FROM assets a
        INNER JOIN asset_prices p ON a.symbol = p.symbol
        WHERE a.exchange = 'TO' AND a.is_active = true
    """)).scalar()
    
    to_inactive = session.query(Asset).filter_by(exchange='TO', is_active=False).count()
    to_without_data = to_total - to_with_data
    
    print(f"Total Active TO Assets: {to_total:,}")
    print(f"TO Assets WITH Data: {to_with_data:,}")
    print(f"TO Assets WITHOUT Data: {to_without_data:,}")
    print(f"TO Assets Marked Inactive: {to_inactive:,}")
    print()
    
    # Sample TO assets with data
    print("Sample TO Assets WITH Price Data:")
    result = session.execute(text("""
        SELECT a.symbol, a.name, COUNT(p.price_id) as records
        FROM assets a
        INNER JOIN asset_prices p ON a.symbol = p.symbol
        WHERE a.exchange = 'TO'
        GROUP BY a.symbol, a.name
        ORDER BY records DESC
        LIMIT 5
    """))
    
    for row in result:
        print(f"  {row.symbol}: {row.records:,} records")
    
    print()
    
    # Sample TO assets without data
    print("Sample TO Assets WITHOUT Price Data (Active):")
    result = session.execute(text("""
        SELECT a.symbol, a.name, a.asset_type
        FROM assets a
        LEFT JOIN asset_prices p ON a.symbol = p.symbol
        WHERE a.exchange = 'TO' 
        AND p.symbol IS NULL
        AND a.is_active = true
        LIMIT 10
    """))
    
    for row in result:
        print(f"  {row.symbol} ({row.asset_type})")
    
    print()
    
    # ========================================================================
    # EXCHANGES WITH 100% FAILURE RATE
    # ========================================================================
    print("=" * 70)
    print("🚨 EXCHANGES WITH NO SUCCESSFUL LOADS")
    print("-" * 70)
    
    result = session.execute(text("""
        SELECT 
            a.exchange,
            COUNT(DISTINCT a.symbol) as total_assets,
            COUNT(DISTINCT p.symbol) as assets_with_data
        FROM assets a
        LEFT JOIN asset_prices p ON a.symbol = p.symbol
        WHERE a.is_active = true
        GROUP BY a.exchange
        HAVING COUNT(DISTINCT p.symbol) = 0
        ORDER BY total_assets DESC
    """))
    
    zero_coverage = []
    for row in result:
        zero_coverage.append((row.exchange, row.total_assets))
        print(f"  {row.exchange}: {row.total_assets:,} assets (0% loaded)")
    
    if not zero_coverage:
        print("  ✅ All exchanges have at least some data loaded")
    
    print()

print("=" * 70)
print("✅ Analysis Complete")
print("=" * 70)